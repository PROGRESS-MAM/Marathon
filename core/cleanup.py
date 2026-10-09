"""delete-folder: inventory, deletion plan and rebuild of the process state."""
# --------- IMPORTS ---------
import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .constants import (
    assignment_unclear, busy_suffixes, field_names, ingest_source, protocol_suffixes, system_files, worker_dir)
from .config import cfg, state_path
from .console import log
from .util import context, joined, now, stamp
from .layout import check_root, final_folder, load_mapping, master_folder, qc_inbox, share_path
from .share import ensured_folders, has_file, safe_work_path, subfolders, work_inventory
from .state import add_event, file_entry, keep_notes, load_state, position, save_state, set_issue
from .naming import find_proxy
from .ffe import is_reference
from .audit import missing_masters, report_problem, status, update_activity
from .testrun import open_test_run


# --------- FUNC ---------
def _work_roots(mapping: list[dict], state: dict) -> list[str]:
    """Include former collection work roots directly below root, but never search in AQC or other subfolders."""
    work = cfg["work_dir"]
    roots = {work} | {f"{final_folder(c)}/{work}" for c in
                     [*(e["name"] for e in mapping), *(c["collection"] for c in state["clips"].values())]}
    for folder in subfolders(""):
        if folder.casefold() == work.casefold():
            continue
        candidate = f"{folder}/{work}"
        if os.path.lexists(share_path(candidate)):
            roots.add(candidate)
    result = []
    seen = set()
    for relative in sorted(roots, key=str.casefold):
        path = safe_work_path(relative)
        if os.path.lexists(path):
            if not path.is_dir():
                raise ValueError(f"Arbeitsordner ist keine normale Ordnerstruktur: {relative}")
            key = str(path.resolve()).casefold()
            if key not in seen:
                seen.add(key)
                result.append(relative)
    return result


def _busy_workers(entries: dict[str, tuple[str, int, int]]) -> list[str]:
    """Fail closed for unfinished running jobs or recent/invalid worker heartbeats."""
    problems, finished = [], set()
    for relative, (kind, _, _) in entries.items():
        path = Path(relative)
        if kind != "file" or path.suffix.casefold() != ".json" or path.parent.name != "fertig":
            continue
        try:
            report = json.loads(share_path(relative).read_text(encoding="utf-8"))
            if report_problem(report) is None and report["job_id"] == path.stem:
                finished.add((path.parent.parent.as_posix(), report["job_id"]))
        except (OSError, ValueError, UnicodeError):
            continue
    for relative, (kind, _, mtime) in entries.items():
        parts = relative.split("/")
        if kind != "file":
            continue
        if "laufend" in parts:
            pos = parts.index("laufend")
            job_id = Path(parts[-1]).stem
            if Path(parts[-1]).suffix.casefold() == ".json" and ("/".join(parts[:pos]), job_id) not in finished:
                problems.append(f"Laufender/ungeklärter Job: {relative}")
        if len(parts) == 3 and parts[:2] == [cfg["work_dir"], worker_dir] and parts[2].casefold().endswith(".json"):
            try:
                data = json.loads(share_path(relative).read_text(encoding="utf-8"))
                if not isinstance(data, dict) or "job_id" not in data:
                    raise ValueError("ungültiger Heartbeat")
                fresh = datetime.now().timestamp() - mtime / 1_000_000_000 < cfg["worker_timeout_minutes"] * 60
                if fresh or data["job_id"]:
                    problems.append(f"Worker noch aktiv oder Job gemeldet: {relative}")
            except (OSError, ValueError, UnicodeError):
                problems.append(f"Worker-Status nicht prüfbar: {relative}")
    return problems


def _cleanup_plan() -> dict:
    mapping = load_mapping()
    check_root()
    if run_id := open_test_run():
        raise RuntimeError(f"Bereinigung blockiert: Test-Lauf {run_id} ist offen; abschließen lassen oder 'test-cancel'.")
    state = load_state()
    roots = _work_roots(mapping, state)
    entries = work_inventory(roots)
    busy = _busy_workers(entries)
    if busy:
        raise RuntimeError("Bereinigung blockiert. Worker zuerst beenden und laufende Jobs klären.\n" + "\n".join(busy))
    clips = [relative for relative, (kind, _, _) in entries.items() if kind == "file" and
             Path(relative).suffix.casefold() not in protocol_suffixes and
             Path(relative).name.casefold() not in system_files and not is_reference(relative)]
    # A .part/.tmp may itself contain media. Never delete it without a confirmation.
    clips += [relative for relative, (kind, _, _) in entries.items() if kind == "file" and
              Path(relative).suffix.casefold() in busy_suffixes and not is_reference(relative)]
    fingerprint = hashlib.sha256(state_path.read_bytes()).hexdigest() if state_path.exists() else None
    return {"roots": roots, "entries": entries, "clips": sorted(set(clips)), "state_hash": fingerprint}


def _rebuild_process_state(state: dict) -> dict:
    """Keep index, metadata and history; rediscover remaining files without search, jobs or directory creation."""
    ctx = context()
    for clip in state["clips"].values():
        previous, master = position(clip), clip["files"]["master"]
        ingested = master if master and master["source"] == ingest_source else None
        collection, clip_id = clip["collection"], clip["clip_id"]
        clip.update(job=None, attempts=0, ready=False, active=True, stage="restore", status="wartet", queued_at=stamp())
        clip["files"] = {"master": None, "proxy": None}
        clip["issues"] = {"file": None, "sticky": None}
        places = ((final_folder(collection), "Zielordner"), (qc_inbox(collection), "QC-Eingang"))
        proxy = next(((folder, name, source) for folder, source in places if (name := find_proxy(ctx, folder, clip))), None)
        missing = missing_masters(ctx, collection, clip_id, clip["master_files"])
        if missing is not None:
            clip["files"]["master"] = {"folder": master_folder(collection, clip_id),
                                       "names": list(clip["master_files"]), "source": "Neuaufbau", "last_seen_at": now()}
        if missing != [] and ingested and all(has_file(ctx, ingested["folder"], name) for name in ingested["names"]):
            clip["files"]["master"], missing = dict(ingested, last_seen_at=now()), []  # Outside the work folders.
        if proxy:
            clip["files"]["proxy"] = file_entry(*proxy)
            clip.update(ready=proxy[2] == "Zielordner", stage=None if proxy[2] == "Zielordner" else "qc")
        elif missing == []:
            clip["stage"] = "transcode"
        elif not clip["master_files"] or len(clip["master_files"]) != len(clip["filehashes"]):
            set_issue(clip, "sticky", assignment_unclear,
                       f"Dateinamen und Hashes reichen nicht für Restore; {field_names['userpath']}={joined(clip['master_files'])}, "
                       f"{field_names['hash']}={joined(clip['filehashes'])}, {field_names['backups']}={joined(clip['lto_tapes'])}")
        update_activity(clip, ctx)
        clip["status"] = status(clip)
        add_event(clip, "Prozesszustand nach Bereinigung neu aufgebaut", f"Vorher: {previous}")
    state.update(workers={}, updated_at=now())
    keep_notes(state, [dict(item, section="note") for item in ctx["issues"]])
    return state


def delete_folders(plan: dict) -> None:
    """Execute only an unchanged preflight; persist a marker before the first irreversible deletion."""
    fresh = _cleanup_plan()
    if fresh != plan:
        raise RuntimeError("Dateien, Worker oder JSON haben sich geändert. Nichts gelöscht; 'delete-folder' erneut eingeben.")
    state = load_state()
    had_state = state_path.exists()
    if had_state:
        state["cleanup"] = {"pending": True, "at": now(), "folders": plan["roots"]}
        save_state(state)
    log(f"Bereinigung beginnt: {len(plan['roots'])} Arbeitsordner, {len(plan['clips'])} Clip-/Mediendateien.")
    errors = []
    for relative in plan["roots"]:
        try:
            path = safe_work_path(relative)
            work_inventory([relative])
            shutil.rmtree(path)
            if os.path.lexists(path):
                raise OSError("Arbeitsordner nach Löschung weiterhin vorhanden")
            log(f"Arbeitsordner gelöscht: {relative}")
        except (OSError, ValueError) as exc:
            errors.append(f"{relative}: {exc}")
    ensured_folders.clear()
    if had_state:
        state = _rebuild_process_state(state)
        state["cleanup"] = {"pending": bool(errors), "at": now(), "folders": plan["roots"], "errors": errors}
        save_state(state)
        if load_state() != state:
            raise RuntimeError("JSON-Neuaufbau konnte nicht bestätigt werden; Job-Schleife bleibt aus.")
    if errors:
        raise RuntimeError("Bereinigung unvollständig; Job-Schleife bleibt aus.\n" + "\n".join(errors))
    log(f"Bereinigung abgeschlossen: {len(plan['roots'])} Arbeitsordner entfernt. "
         "Finale Dateien erhalten; Index behalten; Job-Schleife bleibt aus. "
         "FFE-Referenzen werden bei 'run' oder 'create-folders' neu abgelegt.")


def begin_delete() -> dict | None:
    """Log the deletion scope; returns the plan if confirmation is needed, otherwise deletes directly."""
    plan = _cleanup_plan()
    log(f"Löschumfang: {len(plan['roots'])} Arbeitsordner samt Unterordnern:\n" + "\n".join(plan["roots"]))
    if not plan["roots"]:
        if state_path.exists() and load_state().get("cleanup", {}).get("pending"):
            delete_folders(plan)
        else:
            log("Keine Marathon-Arbeitsordner auf dem SMB gefunden.")
        return None
    if plan["clips"]:
        log(f"WARNUNG: {len(plan['clips'])} Clip-/Mediendateien werden unwiderruflich gelöscht:\n" +
             "\n".join(plan["clips"]) + "\nZum Bestätigen 'loeschen' eingeben, sonst 'abbrechen'.")
        return plan
    delete_folders(plan)
    return None
