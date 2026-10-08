"""Commands ingest-master and ingest-proxy."""
# --------- IMPORTS ---------
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from time import perf_counter

from .constants import ingest_sections, ingest_source, job_failed, protocol_suffixes, stage_labels, veritone_missing
from .config import cfg, error_dir, ignored, state_path
from .console import log
from .util import (
    clip_text, context, details, file_stamp, format_detail, format_errors, issue, normalize, now, write_new)
from .layout import check_root, join, qc_inbox
from .share import safe_work_path, scan
from .state import add_event, enter, file_entry, load_state, position, save_state, set_issue
from .naming import defa_id, proxy_defa_id, proxy_name
from .audit import status, update_activity
from .jobs import withdraw


# --------- FUNC ---------
def _ingest_files(folder: str, parse, suffix: str | None, schema: str, ctx: dict) -> tuple[dict[str, list[tuple[str, int]]], int]:
    """Files directly in folder grouped by normalized DEFA-ID and the number of checked files; others are reported."""
    groups, checked = defaultdict(list), 0
    for name, size in sorted(scan(folder).values(), key=lambda item: item[0].casefold()):
        if ignored(name) or name.casefold().endswith(protocol_suffixes):
            continue
        checked += 1
        if suffix and not name.casefold().endswith(suffix.casefold()):
            issue(ctx, "ingest_info", f"Andere Endung als {suffix} (ignoriert)", name, join(folder, name))
        elif (defa_id := parse(name)) is None:
            issue(ctx, "ingest_error", f"Dateiname passt nicht zum Schema {schema}", name, join(folder, name))
        else:
            groups[normalize(defa_id)].append((name, size))
    return groups, checked


def _ingest_ready(clip: dict, head: str, name: str, ctx: dict) -> bool:
    """Checks shared by both ingests; withdraws an open job. False (reported) if the clip cannot take the file."""
    sticky = clip["issues"]["sticky"]
    if sticky and sticky["category"] != job_failed:
        issue(ctx, "ingest_error", "Clip inaktiv", name, f"{head}; {sticky['category']}: {sticky['detail']}")
        return False
    if not withdraw(clip):
        job = clip["job"]
        issue(ctx, "ingest_error", "Job läuft oder wurde gerade übernommen", name,
               f"{head}; {stage_labels[job['stage']]}-Job {job['id']} bei {job.get('worker') or 'unbekannt'}")
        return False
    return True


def _ingest_done(clip: dict, event: str, detail: str, stage: str) -> None:
    clip["attempts"] = 0
    set_issue(clip, "sticky")  # Only a failed job can be left here; the file now exists.
    add_event(clip, event, detail)
    enter(clip, stage)
    update_activity(clip, context())  # Own context: general notes do not belong into the ingest list.
    clip["status"] = status(clip)


def _ingest_master(clip: dict, folder: str, name: str, ctx: dict) -> bool:
    """Enter one master for a clip waiting for restore; returns True if entered."""
    path, master = join(folder, name), clip["files"]["master"]
    head = f"{path}; {clip_text(clip)}"
    if master and master["source"] == ingest_source and normalize(master["folder"]) == normalize(folder) and \
            [item.casefold() for item in master["names"]] == [name.casefold()]:
        issue(ctx, "ingest_info", "Bereits per Ingest eingetragen", name, f"{head}; Stand: {position(clip)}")
        return False
    if clip["ready"] or clip["stage"] != "restore":
        issue(ctx, "ingest_info", "Clip nicht mehr im Restore (unverändert)", name, f"{head}; Stand: {position(clip)}")
        return False
    if not _ingest_ready(clip, head, name, ctx):
        return False
    clip["files"]["master"] = {"folder": folder, "names": [name], "source": ingest_source, "last_seen_at": now()}
    _ingest_done(clip, "Restore abgeschlossen – Master per Ingest", path, "transcode")
    return True


def _ingest_proxy(clip: dict, folder: str, name: str, ctx: dict) -> bool:
    """Move one proxy, renamed by proxy_name, into the QC inbox of a clip before QC; returns True if entered."""
    path, target_folder, target = join(folder, name), qc_inbox(clip["collection"]), proxy_name(clip)
    head = f"{path}; {clip_text(clip)}"
    if clip["ready"] or clip["stage"] == "qc":
        issue(ctx, "ingest_info", "Clip schon in QC oder bereit (unverändert)", name, f"{head}; Stand: {position(clip)}")
        return False
    if not target:
        issue(ctx, "ingest_error", veritone_missing, name, f"{head}; zuerst update-index")
        return False
    try:
        target_path = safe_work_path(target_folder) / target
        conflict = os.path.lexists(target_path)
    except (OSError, ValueError) as exc:
        issue(ctx, "ingest_error", "QC-Eingang nicht nutzbar", name, f"{head}; {exc}")
        return False
    if conflict:
        issue(ctx, "ingest_error", "Namenskonflikt im QC-Eingang", name, f"{head}; {target_folder}/{target} existiert bereits")
        return False
    if not _ingest_ready(clip, head, name, ctx):
        return False
    restored = clip["stage"] == "restore"
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        os.rename(Path(folder) / name, target_path)  # Windows refuses an existing target.
    except OSError as exc:
        issue(ctx, "ingest_error", "Verschieben nicht möglich", name, f"{head}; {exc}")
        return False
    clip["files"]["proxy"] = file_entry(target_folder, target, ingest_source)
    _ingest_done(clip, f"{'Restore und Transcode' if restored else 'Transcode'} abgeschlossen – Proxy per Ingest",
                 f"{path} → {target_folder}/{target}", "qc")
    return True


def _ingest_group(key: str, files: list[tuple[str, int]], clips: list[dict], folder: str, enter, ctx: dict) -> bool:
    """Check one DEFA-ID of the ingest folder; returns True if a clip took the file."""
    names = [name for name, _ in files]
    head = join(folder, names[0])
    if len(files) > 1:
        detail = format_detail(f"DEFA-ID={key.upper()}", matches=[join(folder, name) for name in names])
        for name in names:
            issue(ctx, "ingest_error", "Mehrere Dateien mit derselben DEFA-ID", name, detail)
    elif not files[0][1]:
        issue(ctx, "ingest_error", "Datei ist leer", names[0], head)
    elif not clips:
        issue(ctx, "ingest_info", "DEFA-ID nicht in der JSON", names[0], head)
    elif len(clips) > 1:
        issue(ctx, "ingest_error", "DEFA-ID mehrfach in der JSON", names[0], format_detail(head, matches=[clip_text(clip) for clip in clips]))
    else:
        return enter(clips[0], folder, names[0], ctx)
    return False


# --------- COMMAND ---------
def ingest(kind: str) -> None:
    """ingest-master or ingest-proxy: match the files in <kind>_dir via DEFA-ID with the JSON; only started by the command."""
    started, folder, command, master = perf_counter(), cfg[f"{kind}_dir"], f"ingest-{kind}", kind == "master"
    log(f"{command} gestartet: {folder}")
    if not state_path.exists():
        raise RuntimeError("Noch keine JSON – zuerst 'update-index' oder 'run'.")
    if not Path(folder).is_absolute():
        raise ValueError(f"[ingest] {kind}_dir muss ein vollständiger Pfad sein: {folder}; Zustand unverändert.")
    check_root()
    if not Path(folder).is_dir():
        raise FileNotFoundError(f"Ordner nicht erreichbar: {folder}; Zustand unverändert.")
    state, ctx = load_state(), context()
    if state.get("cleanup", {}).get("pending"):
        raise RuntimeError("Bereinigung noch unvollständig; zuerst 'delete-folder' erneut ausführen.")
    by_id = defaultdict(list)
    for clip in sorted(state["clips"].values(), key=lambda item: int(item["clip_id"])):
        by_id[normalize(clip["identifier"])].append(clip)
    if master:
        parse, suffix, schema, enter, stage = defa_id, None, "<DEFA-ID>__<Titel>", _ingest_master, "Transcode"
    else:
        parse, suffix, schema, enter, stage = (proxy_defa_id, Path(cfg["proxy_name"]).suffix,
                                               f"{cfg['proxy_prefix']}__<DEFA-ID>__<Titel>", _ingest_proxy, "QC")
    groups, checked = _ingest_files(folder, parse, suffix, schema, ctx)
    try:
        entered = sum(_ingest_group(key, files, by_id.get(key, []), folder, enter, ctx) for key, files in groups.items())
    finally:  # Files may already be moved; the JSON must follow.
        state["updated_at"] = now()
        save_state(state)
    when = datetime.now().astimezone()
    error_list = f"{file_stamp(command, when)}_errors.txt" if ctx["issues"] else None
    if error_list:
        write_new(error_dir / error_list, format_errors(ctx["issues"], when, f"{command}-Fehlerliste", ingest_sections))
    counts = {section: len({item["key"] for item in ctx["issues"] if item["section"] == section}) for section in ingest_sections}
    log(f"{command} abgeschlossen: {checked} Dateien geprüft, {entered} eingetragen (weiter an {stage}), "
         f"{counts['ingest_error']} nicht eingetragen (Fehler), {counts['ingest_info']} Hinweise{details(error_list)}; "
         f"Dauer: {perf_counter() - started:.1f} s.")
