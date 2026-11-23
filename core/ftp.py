"""Send ready proxies to the configured FTP folder."""
# --------- IMPORTS ---------
import os
import shutil
from datetime import datetime
from pathlib import Path
from time import perf_counter

from .config import cfg, error_dir, state_path
from .console import log
from .constants import ftp_sections
from .editshare import request_field, write_fields
from .ftpcheck import final_check
from .layout import check_root, final_folder, join, load_mapping, share_path
from .naming import ftp_name, proxy_name
from .state import add_event, load_state, save_state
from .util import clip_text, context, details, file_stamp, format_errors, issue, now, write_new


# --------- FUNC ---------
class _ClipFailure(Exception):
    def __init__(self, category: str, detail: str) -> None:
        super().__init__(detail)
        self.category = category
        self.detail = detail


def _copy(source: Path, part: Path) -> int:
    with source.open("rb") as source_file, part.open("wb") as part_file:
        shutil.copyfileobj(source_file, part_file, 16 * 1024 * 1024)
        part_file.flush()
        os.fsync(part_file.fileno())
    return part.stat().st_size


def _directory_names(folder: Path, cache: dict[Path, set[str]]) -> set[str]:
    if folder not in cache:
        cache[folder] = {entry.name for entry in folder.iterdir()}
    return cache[folder]


def _matching_name(names: set[str], name: str, exclude: str | None = None) -> str | None:
    matches = sorted((item for item in names if item.casefold() == name.casefold() and item != exclude),
                     key=lambda item: (item.casefold(), item))
    return matches[0] if matches else None


def _conflict_path(target: Path, source: Path, names: set[str], source_name: str) -> Path | None:
    match = _matching_name(names, target.name, source_name)
    if match is not None:
        return target.parent / match
    if os.path.lexists(target) and target != source:
        return target
    return None


def _remove_part(part: Path) -> str:
    try:
        part.unlink(missing_ok=True)
    except OSError as exc:
        return f"; .part konnte nicht entfernt werden: {exc}"
    return ""


def _report(ctx: dict, clip: dict, category: str, detail: str) -> None:
    issue(ctx, "ftp_error", category, clip["clip_id"], f"{clip_text(clip)}: {detail}")


def _send_clip(clip: dict, state: dict, result: str | None, ftp_path: Path,
               ftp_names: dict[Path, set[str]], final_names: dict[Path, set[str]]) -> None:
    if result is not None:
        raise _ClipFailure("Letzte Prüfung nicht bestanden", result)

    collection = clip["collection"]
    final = final_folder(collection)
    proxy = clip["files"]["proxy"]
    if proxy["folder"].casefold() != final.casefold():
        raise _ClipFailure("Proxy im Zielordner fehlt oder ist leer", "Proxy im Zielordner fehlt oder ist leer")

    record = clip.get("ftp")
    if record is not None:
        old, new = record["old_name"], record["new_name"]
    else:
        old = proxy["name"]
        expected = proxy_name(clip)
        if not expected or old.casefold() != expected.casefold():
            raise _ClipFailure("Proxy-Name weicht von proxy_name ab",
                               f"Ist {old!r}, erwartet {expected!r}")
        new = ftp_name(clip)
        if new is None:
            raise _ClipFailure("Kein Dateiname aus Identifier/Titel möglich",
                               "Kein Dateiname aus Identifier/Titel möglich")

    src = share_path(join(final, old))
    dst = share_path(join(final, new))
    target = ftp_path / old
    part = ftp_path / f"{old}.part"

    if record is not None and record["copied_at"] and not src.exists() and dst.is_file() and \
            dst.stat().st_size == record["size"]:
        _complete_rename(clip, state, proxy, record, final, old, new)
        return

    if not src.is_file() or not src.stat().st_size:
        raise _ClipFailure("Proxy im Zielordner fehlt oder ist leer", "Proxy im Zielordner fehlt oder ist leer")
    size = src.stat().st_size

    folder = share_path(final)
    names = _directory_names(folder, final_names)
    conflict = _conflict_path(dst, src, names, old)
    if conflict is not None:
        raise _ClipFailure("Namenskonflikt im Zielordner", f"Datei bereits vorhanden: {conflict}")

    names = _directory_names(ftp_path, ftp_names)
    ftp_match = _matching_name(names, old)
    ftp_exists = os.path.lexists(target) or ftp_match is not None
    if ftp_exists:
        if record is not None and target.is_file() and target.stat().st_size == size:
            if record["copied_at"] is None:
                record["copied_at"] = now()
                add_event(clip, "An FTP kopiert", str(target))
                save_state(state)
        else:
            conflict_path = target if os.path.lexists(target) else ftp_path / ftp_match
            raise _ClipFailure("Namenskonflikt auf dem FTP", f"Datei bereits vorhanden: {conflict_path}")
    else:
        clip["ftp"] = {"target": str(target), "size": size, "old_name": old, "new_name": new,
                       "copied_at": None, "renamed_at": None}
        record = clip["ftp"]
        save_state(state)
        try:
            written = _copy(src, part)
        except Exception as exc:
            cleanup = _remove_part(part)
            raise _ClipFailure("Kopieren nicht möglich", f"Kopieren nicht möglich: {exc}{cleanup}") from exc
        try:
            part_size, source_size = part.stat().st_size, src.stat().st_size
        except OSError as exc:
            cleanup = _remove_part(part)
            raise _ClipFailure("Kopieren nicht möglich", f"Kopieren nicht möglich: {exc}{cleanup}") from exc
        if written != size or part_size != size or source_size != size:
            cleanup = _remove_part(part)
            raise _ClipFailure("Kopie unvollständig", f"Kopie unvollständig: erwartet {size}, geschrieben {written}, "
                               f"Part {part_size}, Quelle {source_size}{cleanup}")
        try:
            if os.name != "nt" and os.path.lexists(target):
                cleanup = _remove_part(part)
                raise _ClipFailure("Namenskonflikt auf dem FTP", f"Datei bereits vorhanden: {target}{cleanup}")
            os.rename(part, target)
        except FileExistsError as exc:
            cleanup = _remove_part(part)
            raise _ClipFailure("Namenskonflikt auf dem FTP", f"Datei bereits vorhanden: {target}{cleanup}") from exc
        except OSError as exc:
            cleanup = _remove_part(part)
            raise _ClipFailure("Kopieren nicht möglich", f"Kopieren nicht möglich: {exc}{cleanup}") from exc
        names.add(old)
        record["copied_at"] = now()
        add_event(clip, "An FTP kopiert", str(target))
        save_state(state)

    if os.name != "nt" and dst.name != old and os.path.lexists(dst):
        raise _ClipFailure("Namenskonflikt im Zielordner", f"Datei bereits vorhanden: {dst}")
    try:
        if dst.name != old:
            os.rename(src, dst)
    except FileExistsError as exc:
        raise _ClipFailure("Namenskonflikt im Zielordner", f"Datei bereits vorhanden: {dst}") from exc
    except OSError as exc:
        raise _ClipFailure("Umbenennen nicht möglich", f"Umbenennen nicht möglich: {exc}") from exc

    if folder in final_names:
        final_names[folder].discard(old)
        final_names[folder].add(new)
    _complete_rename(clip, state, proxy, record, final, old, new)


def _complete_rename(clip: dict, state: dict, proxy: dict, record: dict, final: str, old: str, new: str) -> None:
    clip["files"]["proxy"] = dict(proxy, name=new, last_seen_at=now())
    record["renamed_at"] = now()
    add_event(clip, "Quelle umbenannt", f"{final}/{old} → {final}/{new}")
    request_field(clip, final, new)
    save_state(state)


# --------- COMMAND ---------
def send_to_ftp() -> None:
    """Copy ready proxies to FTP, rename their sources, and request EditShare updates."""
    started, ftp_dir = perf_counter(), cfg["ftp_dir"]
    log(f"send-to-ftp gestartet: {ftp_dir}")
    if not state_path.exists():
        raise RuntimeError("Noch keine JSON – zuerst 'update-index' oder 'run'.")
    if not Path(ftp_dir).is_absolute():
        raise ValueError(f"[ftp] ftp_dir muss ein vollständiger Pfad sein: {ftp_dir}; Zustand unverändert.")
    check_root()
    if not Path(ftp_dir).is_dir():
        raise FileNotFoundError(f"FTP-Pfad nicht erreichbar: {ftp_dir}; Zustand unverändert.")

    state = load_state()
    if state.get("cleanup", {}).get("pending"):
        raise RuntimeError("Bereinigung noch unvollständig; zuerst 'delete-folder' erneut ausführen.")
    ctx = context()
    candidates = sorted((clip for clip in state["clips"].values()
                         if clip["ready"] and clip["active"] and clip["files"]["proxy"] and
                         not (clip.get("ftp") or {}).get("renamed_at")), key=lambda clip: int(clip["clip_id"]))
    if not candidates:
        log("send-to-ftp: keine bereiten Clips zu senden.")
        return

    results = final_check(candidates, load_mapping())
    ftp_path = Path(ftp_dir)
    ftp_names: dict[Path, set[str]] = {}
    final_names: dict[Path, set[str]] = {}
    sent_clips = []
    try:
        for clip in candidates:
            try:
                _send_clip(clip, state, results[clip["clip_id"]], ftp_path, ftp_names, final_names)
            except _ClipFailure as exc:
                _report(ctx, clip, exc.category, exc.detail)
                continue
            except OSError as exc:
                _report(ctx, clip, "Kopieren nicht möglich", f"Kopieren nicht möglich: {exc}")
                continue
            sent_clips.append(clip)
        write_fields(state)
    finally:
        state["updated_at"] = now()
        save_state(state)

    when = datetime.now().astimezone()
    error_list = f"{file_stamp('send-to-ftp', when)}_errors.txt" if ctx["issues"] else None
    if error_list:
        write_new(error_dir / error_list,
                  format_errors(ctx["issues"], when, "send-to-ftp-Fehlerliste", ftp_sections))
    failed = len({item["key"] for item in ctx["issues"] if item["section"] == "ftp_error"})
    pending = sum(bool(clip.get("editshare") and clip["editshare"]["pending"]) for clip in sent_clips)
    log(f"send-to-ftp abgeschlossen: {len(candidates)} bereite Clips geprüft, {len(sent_clips)} gesendet, "
        f"{failed} nicht gesendet, EditShare-Feld offen: {pending}{details(error_list)}; "
        f"Dauer: {perf_counter() - started:.1f} s.")
