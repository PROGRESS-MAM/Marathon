"""FFE list, FFE match and reference files for workers; command update-ffe."""
# --------- IMPORTS ---------
import json
import os
import shutil
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from time import perf_counter

from .constants import ffe_ambiguous, ffe_flag, ffe_missing, ffe_mtime_tolerance, worker_dir
from .config import cfg, ignored, is_clip, state_path
from .console import log
from .util import clip_text, context, details, file_stamp, format_detail, issue, normalize, now, write_lists
from .layout import res
from .share import safe_work_path, scan
from .state import add_event, load_state, save_state


# --------- FUNC ---------
def reference_image() -> str:
    """Share path of the reference screenshot for QC workers."""
    return f"{cfg['work_dir']}/{worker_dir}/{cfg['reference_image']}"


def _reference_clip_folder() -> str:
    return f"{cfg['work_dir']}/{worker_dir}/{cfg['reference_clip_dir']}"


def is_reference(relative: str) -> bool:
    """True if the share path is one of the reference files in the worker folder."""
    key = relative.casefold()
    return key == reference_image().casefold() or key.rsplit("/", 1)[0] == _reference_clip_folder().casefold()


def _local_image() -> Path:
    return res("reference_clip_dir") / cfg["reference_image"]


def _local_clips() -> list[Path]:
    return sorted((path for path in res("reference_clip_dir").iterdir() if is_clip(path)),
                  key=lambda path: path.name.casefold())


def reference_clips() -> list[str]:
    """Share paths of all FFE title clips for Transcode workers."""
    return [f"{_reference_clip_folder()}/{path.name}" for path in _local_clips()]


def sync_references(ctx: dict) -> int:
    """Mirror screenshot and clip folder from res into the worker folder; returns copied plus removed files."""
    pairs = [(_local_image(), reference_image()),
             *((path, f"{_reference_clip_folder()}/{path.name}") for path in _local_clips())]
    changed = 0
    for source, relative in pairs:
        target, info = safe_work_path(relative), source.stat()
        try:
            current = target.stat()
            if current.st_size == info.st_size and abs(current.st_mtime - info.st_mtime) <= ffe_mtime_tolerance:
                continue
        except FileNotFoundError:
            pass
        temporary = target.with_name(f".{target.name}.tmp")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, temporary)  # Keeps the modification time for the next comparison.
            if temporary.stat().st_size != info.st_size:
                raise OSError("Dateigröße nach dem Kopieren abweichend")
            os.replace(temporary, target)
        except OSError as exc:
            issue(ctx, "note", "FFE-Referenz nicht bereitgestellt (neuer Versuch im nächsten Zyklus)", relative,
                   f"{relative}: {exc}")
            continue
        finally:
            temporary.unlink(missing_ok=True)
        changed += 1
        log(f"FFE-Referenz bereitgestellt: {relative}")
    expected = {Path(relative).name.casefold() for _, relative in pairs[1:]}
    for key, (name, _) in scan(_reference_clip_folder()).items():
        if key in expected or ignored(name):
            continue
        relative = f"{_reference_clip_folder()}/{name}"
        try:
            safe_work_path(relative).unlink()
        except OSError as exc:
            issue(ctx, "note", "Veraltete FFE-Referenz nicht löschbar", relative, f"{relative}: {exc}")
            continue
        changed += 1
        log(f"Veraltete FFE-Referenz entfernt: {relative}")
    return changed


def load_ffe_list() -> list[dict]:
    """Load and check the FFE list; raises ValueError on invalid entries."""
    with res("list_file").open(encoding="utf-8-sig") as handle:
        document = json.load(handle)
    entries = document.get("titel") if isinstance(document, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"{cfg['list_file']}: erwartet ein Objekt mit der Liste \"titel\"; keine Änderung.")
    problems = [f"Eintrag {number}: {entry!r}" for number, entry in enumerate(entries, 1)
                if not isinstance(entry, dict) or set(entry) != {"title", "defa_id"}
                or not all(isinstance(value, str) and value.strip() for value in entry.values())]
    if problems:
        more = f"; … {len(problems) - 5} weitere" if len(problems) > 5 else ""
        raise ValueError(f"{cfg['list_file']}: {len(problems)} ungültige Einträge (erwartet genau title und defa_id); "
                         f"keine Änderung: {'; '.join(problems[:5])}{more}")
    return entries


def _exact(value: str) -> str:
    return unicodedata.normalize("NFC", value)  # Same visible text, but composed umlauts.


def apply_ffe(state: dict, entries: list[dict], ctx: dict) -> dict:
    """Recompute ffe_tafel for all clips; only a single clip with identical defa_id and title is marked."""
    exact, loose = defaultdict(list), defaultdict(list)
    for clip in sorted(state["clips"].values(), key=lambda item: int(item["clip_id"])):
        exact[(_exact(clip["identifier"]), _exact(clip["title"]))].append(clip)
        loose[(normalize(clip["identifier"]), normalize(clip["title"]))].append(clip)
    keys = list(dict.fromkeys((_exact(entry["defa_id"]), _exact(entry["title"])) for entry in entries))
    marked, counts = set(), {"entries": len(entries), "unique": len(keys), "marked": 0, "missing": 0, "ambiguous": 0}
    for defa_id, title in keys:
        hits, head, key = exact.get((defa_id, title), []), f"defa_id={defa_id}, title={title}", f"{defa_id}|{title}"
        if len(hits) == 1:
            marked.add(hits[0]["clip_id"])
            counts["marked"] += 1
        elif hits:
            counts["ambiguous"] += 1
            issue(ctx, "ffe_ambiguous", ffe_ambiguous, key, format_detail(head, matches=[clip_text(clip) for clip in hits]))
        else:
            counts["missing"] += 1
            similar = [clip_text(clip) for clip in loose.get((normalize(defa_id), normalize(title)), [])]
            issue(ctx, "ffe_missing", ffe_missing, key,
                   format_detail(f"{head}; ähnliche Schreibweise in der JSON", matches=similar) if similar else head)
    counts["changed"] = 0
    for clip in state["clips"].values():
        flag = clip["clip_id"] in marked
        if clip[ffe_flag] != flag:
            clip[ffe_flag] = flag
            counts["changed"] += 1
            add_event(clip, f"{ffe_flag} gesetzt" if flag else f"{ffe_flag} entfernt")
    return counts


def ffe_text(counts: dict) -> str:
    """Summary text of the FFE match counts."""
    return (f"FFE {counts['entries']} Einträge ({counts['unique']} verschieden): {counts['marked']} markiert, "
            f"{counts['missing']} nicht gefunden, {counts['ambiguous']} uneindeutig; {counts['changed']} Clips geändert")


def ffe_line(ffe: dict) -> str:
    """Summary of the last FFE match for the report."""
    counts = ffe.get("counts") or {}
    text = f"FFE-Stand: {ffe.get('updated_at') or 'unbekannt'}" + (f"; {ffe_text(counts)}" if counts else "")
    return text + details(ffe.get("error_list"), ffe.get("ambiguous_list"))


# --------- COMMAND ---------
def update_ffe() -> None:
    """Match only the FFE list against the existing JSON; no search and no access to the share."""
    started = perf_counter()
    log("FFE-Abgleich gestartet.")
    if not state_path.exists():
        raise RuntimeError("Noch keine JSON – zuerst 'update-index' oder 'run'.")
    entries = load_ffe_list()
    state, ctx = load_state(), context()
    counts = apply_ffe(state, entries, ctx)
    when = datetime.now().astimezone()
    error_list, ambiguous_list = write_lists(ctx["issues"], when, file_stamp("ffe", when), "FFE-Fehlerliste")
    state["ffe"] = {"updated_at": now(), "counts": counts, "error_list": error_list, "ambiguous_list": ambiguous_list}
    state["updated_at"] = now()
    save_state(state)
    log(f"FFE-Abgleich abgeschlossen: {ffe_text(counts)}{details(error_list, ambiguous_list)}; "
         f"Dauer: {perf_counter() - started:.1f} s.")
