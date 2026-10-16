"""Transfer state/marathon.json from JSON version 7 to 8 for Marathon 1.17.0; start in the Marathon folder.

Checks everything first (JSON, lock, jobs, restore folders, EditShare), then backs up the JSON, adapts the folders and
writes JSON 8 last. Any error leaves the JSON at version 7 and writes reports/errors/transfer_<stamp>_errors.txt.
"""
# --------- IMPORTS ---------
import json
import os
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # Marathon folder: core package and res/.

from toolbox import tb_write_log  # noqa: E402

from core.constants import outbox  # noqa: E402
from core.config import cfg, error_dir, load_config, main_log, reports_dir, state_dir, state_path  # noqa: E402
from core.console import log  # noqa: E402
from core.util import clip_text, context, file_stamp, write_new  # noqa: E402
from core.layout import acquire_lock, check_root, job_folder, load_mapping, prepare, stage_folder, share_path  # noqa: E402
from core.share import safe_work_path, scan, subfolders  # noqa: E402
from core.state import check_state, load_state, save_state  # noqa: E402
from core.search import search_clips  # noqa: E402


# --------- CONFIG ---------
app_name = "Marathon Transfer JSON 7 → 8"
app_version = "1.0.0"
backup_dir = state_dir / "backup"  # Not directly in state/: Marathon refuses to start with a second JSON there.


# --------- CHECKS ---------
class TransferError(Exception):
    """Transfer stopped; lines go into the error report."""

    def __init__(self, lines: list[str]):
        super().__init__(lines[0])
        self.lines = lines


def _load_v7() -> dict:
    if not state_path.exists():
        raise TransferError([f"{state_path} fehlt."])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("schema_version") != 7 or not isinstance(state.get("clips"), dict):
        version = state.get("schema_version") if isinstance(state, dict) else None
        raise TransferError([f"JSON ist nicht Version 7 (schema_version={version!r}); nichts geändert."])
    return state


def _pending_jobs() -> list[str]:
    """Job files in <work_dir>/*/offen/ and <work_dir>/*/laufend/<worker>/."""
    found = []
    for stage in subfolders(cfg["work_dir"]):
        base = f"{cfg['work_dir']}/{stage}"
        boxes = [f"{base}/offen", *(f"{base}/laufend/{worker}" for worker in subfolders(f"{base}/laufend"))]
        found += [f"{box}/{name}" for box in boxes for name, _ in scan(box).values()
                  if name.casefold().endswith(".json") and not name.startswith(".")]
    return found


def _tree(relative: str) -> tuple[list[str], list[str]]:
    """Files (every non-folder entry, also hidden, system, empty files and links) and folders, deepest folders first."""
    files, folders, pending = [], [], [safe_work_path(relative)]
    while pending:
        path = pending.pop()
        folders.append(path)
        with os.scandir(path) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                link = entry.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400)
                (pending if entry.is_dir(follow_symlinks=False) and not link else files).append(Path(entry.path))
    root = share_path("")
    return [str(path.relative_to(root).as_posix()) for path in files], [str(path) for path in reversed(folders)]


def _old_restore_folders(mapping: list[dict], state: dict) -> dict[str, tuple[list[str], list[str]]]:
    """Existing restore folders per collection: relative folder -> (files, folders deepest first)."""
    names = {entry["name"] for entry in mapping} | {clip["collection"] for clip in state["clips"].values()}
    result = {}
    for relative in sorted({stage_folder(name, "restore") for name in names}, key=str.casefold):
        if os.path.lexists(share_path(relative)):
            result[relative] = _tree(relative)
    return result


def _masters(state: dict, mapping: list[dict]) -> tuple[dict[str, dict], list[str], list[str]]:
    """New file fields per clip, errors and accepted deviations (tapes, sizes)."""
    ctx = context()
    found = search_clips(mapping, ctx)
    new, errors, deviations = {}, [], []
    for clip_id, clip in sorted(state["clips"].items(), key=lambda item: int(item[0])):
        hits, text = found.get(clip_id, []), clip_text(clip)
        hit = next((hit for hit in hits if hit["collection"] == clip["collection"]), hits[0] if hits else None)
        if hit is None:
            errors.append(f"{text}: nicht in der EditShare-Suche gefunden")
            continue
        if hit["restore_problem"]:
            errors.append(f"{text}: {hit['restore_problem']}")
            continue
        old_names = sorted(name.casefold() for name in clip.get("master_files") or [])
        if sorted(name.casefold() for name in hit["master_files"]) != old_names:
            errors.append(f"{text}: Dateinamen abweichend; bisher {' | '.join(clip.get('master_files') or [])}; "
                          f"jetzt {' | '.join(hit['master_files'])}")
            continue
        if {tape.casefold() for tape in clip.get("lto_tapes") or []} != {tape.casefold() for tape in hit["lto_tapes"]}:
            deviations.append(f"{text}: Bänder {', '.join(clip.get('lto_tapes') or [])} → {', '.join(hit['lto_tapes'])}")
        if clip.get("master_size") != hit["master_size"]:
            deviations.append(f"{text}: Größe {clip.get('master_size')} → {hit['master_size']} Byte")
        new[clip_id] = {key: hit[key] for key in ("masters", "master_files", "lto_tapes", "master_size")}
    errors += [f"Suche: {item['category']}: {item['detail']}" for item in ctx["issues"]]
    return new, errors, deviations


# --------- CHANGES ---------
def _convert(state: dict, new: dict[str, dict]) -> dict:
    for clip_id, clip in state["clips"].items():
        clip.pop("filehashes", None)
        clip.update(new[clip_id], job=None)  # Version-5 jobs were deleted before the transfer.
    state.update(schema_version=8, restore={"counter": 0, "jobs": {}})
    return state


def _remove_folders(folders: dict[str, tuple[list[str], list[str]]], removed: list[str]) -> None:
    for _, paths in folders.values():
        for path in paths:
            os.rmdir(path)  # Fails for a folder that is not empty: files are never deleted.
            removed.append(path)


def _write(path: Path, title: str, when: datetime, lines: list[str]) -> None:
    write_new(path, "\n".join([f"{app_name} {app_version} | {title} | {when.isoformat(timespec='seconds')}", "", *lines]) + "\n")


# --------- MAIN ---------
def main() -> int:
    """Run the transfer; returns the exit code (0 = JSON 8 written)."""
    log(f"{app_name} {app_version} gestartet.")
    prepare()
    when = datetime.now().astimezone()
    stamp = file_stamp("transfer", when)
    removed: list[str] = []
    try:
        if problem := load_config():
            raise TransferError([problem])
        acquire_lock()  # Marathon must not run; the lock also keeps it from starting during the transfer.
        state, mapping = _load_v7(), load_mapping()
        check_root()
        if jobs := _pending_jobs():
            raise TransferError([f"{len(jobs)} Jobs in offen/laufend; zuerst von Hand löschen:", *(f"  {job}" for job in jobs)])
        folders = _old_restore_folders(mapping, state)
        if busy := {relative: files for relative, (files, _) in folders.items() if files}:
            raise TransferError(["Restore-Ordner je Kollektion enthalten Dateien; nichts gelöscht:",
                                 *(line for relative, files in busy.items() for line in (f"  {relative}", *(f"    {file}" for file in files)))])
        new, errors, deviations = _masters(state, mapping)
        if errors:
            raise TransferError([f"{len(errors)} Fehler bei der EditShare-Prüfung:", *(f"  {line}" for line in errors)])
        converted = _convert(json.loads(json.dumps(state)), new)
        check_state(converted)
        backup = backup_dir / f"marathon.v7_{stamp.removeprefix('transfer_')}.json"
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(state_path, backup)
        outbox_folder = f"{job_folder('restore')}/{outbox}"
        safe_work_path(outbox_folder).mkdir(parents=True, exist_ok=True)
        try:
            _remove_folders(folders, removed)
        except OSError as exc:
            raise TransferError([f"Ordner nicht entfernbar: {exc}; JSON bleibt Version 7.",
                                 f"Bereits entfernte leere Ordner: {len(removed)}", *(f"  {path}" for path in removed)]) from exc
        save_state(converted)
        if load_state() != converted:
            raise TransferError(["JSON 8 geschrieben, aber nicht bestätigt; Sicherung prüfen:", f"  {backup}"])
    except Exception as exc:
        lines = exc.lines if isinstance(exc, TransferError) else [
            f"Fehler: {exc}", f"Bereits entfernte leere Ordner: {len(removed)}", *(f"  {path}" for path in removed),
            "", traceback.format_exc()]
        name = f"{stamp}_errors.txt"
        _write(error_dir / name, "Fehlerbericht", when, lines)
        log(f"Transfer abgebrochen: {lines[0]} Details: reports/errors/{name}")
        return 1
    name = f"{stamp}.txt"
    _write(reports_dir / name, "Bericht", when, [
        f"Clips: {len(converted['clips'])} (masters aus EditShare)",
        f"Sicherung: {backup}",
        f"Restore-Ausgang angelegt: {outbox_folder}",
        f"Leere Restore-Ordner je Kollektion entfernt: {len(folders)} ({len(removed)} Ordner)",
        *(f"  {relative}" for relative in folders),
        f"Übernommene Abweichungen (Bänder, Größen): {len(deviations)}", *(f"  {line}" for line in deviations)])
    log(f"Transfer abgeschlossen: JSON-Version 8 mit {len(converted['clips'])} Clips; Bericht: reports/{name}")
    return 0


# --------- EXEC ---------
if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        error_message = f"Unhandled error in main: {exc}"
        print(error_message)
        tb_write_log(main_log, error_message)
        tb_write_log(main_log, traceback.format_exc())
        raise SystemExit(1) from exc
