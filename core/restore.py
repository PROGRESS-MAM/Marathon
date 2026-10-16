"""Restore collective jobs: selection by tape, job files, partial reports and evaluation per clip.

state["restore"] = {"counter": int, "jobs": {job_id: record}}. A record holds kind ("gross"/"klein"), main tape, member
clips, items, clip folders, location state of the job file, evaluated clips ("done") and processed partial reports.
Every member clip carries a copy of the record's location fields in clip["job"] (stage "restore") until it is evaluated.
"""
# --------- IMPORTS ---------
import json
from collections import Counter, defaultdict
from pathlib import Path

from .constants import (
    busy_suffixes, invalid_path_chars, job_failed, missing_job_grace, outbox, partial_marker, restore_kind_labels,
    restore_kinds, stage_labels)
from .config import cfg
from .util import age, clip_text, issue, now, stamp
from .layout import job_folder, master_folder, share_path
from .share import (
    archive_job, delete_job_file, listing, move, remove_tree, retire_job, rmdir, running, scan, write_text_atomic)
from .state import add_event, enter, set_issue
from .audit import report_problem
from .details import record_job


# --------- STATIC ---------
mirror_keys = ("id", "stage", "folder", "file", "output_folder", "state", "worker", "created_at", "running_since",
               "missing_since")
item_keys = {"clip_id": str, "clip_name": str, "file": str, "flow_hash": str, "tape": str, "size": int}


# --------- SELECTION ---------
def waiting_clips(clips) -> list[dict]:
    """Clips waiting for a restore job: active, not ready, stage restore, no job, with master files."""
    return [clip for clip in clips if clip["active"] and not clip["ready"] and clip["stage"] == "restore" and
            clip["job"] is None and clip["masters"]]


def tape_counts(clips: list[dict]) -> Counter:
    """Waiting clips per casefolded tape: clips with at least one file on the tape."""
    return Counter(tape for clip in clips for tape in {tape.casefold() for entry in clip["masters"] for tape in entry["tapes"]})


def main_tape(clip: dict, counts: Counter) -> tuple[str, list[str]]:
    """Casefolded main tape of a clip and the tape each master file is read from (own spelling, master order)."""
    files = [{tape.casefold(): tape for tape in entry["tapes"]} for entry in clip["masters"]]

    def rank(tape: str) -> tuple:
        return -counts[tape], tape

    full = set(files[0]).intersection(*files[1:])
    if full:
        main = min(full, key=rank)
    else:
        per_tape = Counter(tape for tapes in files for tape in tapes)
        main = min(per_tape, key=lambda tape: (-per_tape[tape], *rank(tape)))
    return main, [tapes[main] if main in tapes else tapes[min(tapes, key=rank)] for tapes in files]


def job_items(clips: list[dict], counts: Counter) -> list[dict]:
    """Job items of clips in the given order, files by name."""
    return [{"clip_id": clip["clip_id"], "clip_name": clip["clip_name_with_extension"], "file": entry["file"],
             "flow_hash": entry["flow_hash"], "tape": tape, "size": entry["size"]}
            for clip in clips for entry, tape in zip(clip["masters"], main_tape(clip, counts)[1])]


def plan_jobs(waiting: list[dict], ranks: dict[str, int], locked: set[str], free: dict[str, int],
              small_clips: int) -> list[tuple[str, str, list[dict], list[dict]]]:
    """New jobs as (kind, main tape, clips, items): first big jobs, then small jobs, never on a locked main tape."""
    counts = tape_counts(waiting)
    pool = sorted(waiting, key=lambda clip: (ranks.get(clip["collection"], len(ranks)), clip["queued_at"]))
    mains = {clip["clip_id"]: main_tape(clip, counts)[0] for clip in pool}
    spelling = {}
    for tape in (tape for clip in pool for entry in clip["masters"] for tape in entry["tapes"]):
        spelling.setdefault(tape.casefold(), tape)
    locked, jobs = set(locked), []

    def candidates() -> list[dict]:
        return [clip for clip in pool if mains[clip["clip_id"]] not in locked]

    def big_tape(clips: list[dict]) -> str:
        top = clips[0]["collection"]  # Highest priority collection with waiting clips on free main tapes.
        inside = Counter(mains[clip["clip_id"]] for clip in clips if clip["collection"] == top)
        total = Counter(mains[clip["clip_id"]] for clip in clips)
        return min(inside, key=lambda tape: (-inside[tape], -total[tape], tape))

    def add(kind: str, tape: str, clips: list[dict]) -> None:
        jobs.append((kind, spelling[tape], clips, job_items(clips, counts)))
        locked.add(tape)

    for _ in range(free["gross"]):
        if not (clips := candidates()):
            break
        tape = big_tape(clips)
        add("gross", tape, [clip for clip in clips if mains[clip["clip_id"]] == tape])
    for _ in range(free["klein"]):
        if not (clips := candidates()):
            break
        groups, order = defaultdict(list), list(dict.fromkeys(clip["collection"] for clip in clips))
        for clip in clips:
            groups[mains[clip["clip_id"]]].append(clip)
        small = [tape for tape, members in groups.items() if len(members) <= small_clips]
        if small:
            tape = min(small, key=lambda tape: (*(-sum(clip["collection"] == name for clip in groups[tape]) for name in order), tape))
            add("klein", tape, groups[tape])
        else:
            tape = big_tape(clips)
            add("klein", tape, groups[tape][:small_clips])
    return jobs


# --------- JOB FILE ---------
def clip_folders(items: list[dict]) -> dict[str, str]:
    """Clip folder in the output per clip_id: invalid characters to "_", no trailing dots/spaces, __2, __3 for repeats."""
    folders, seen = {}, Counter()
    for item in items:
        if item["clip_id"] in folders:
            continue
        base = "".join("_" if char in invalid_path_chars else char for char in str(item["clip_name"])).rstrip(". ")
        seen[base.casefold()] += 1
        folders[item["clip_id"]] = base if seen[base.casefold()] == 1 else f"{base}__{seen[base.casefold()]}"
    return folders


def job_payload(job_id: str, report_folder: str, output_folder: str, items: list[dict] | None) -> dict:
    """Restore job file content (schema_version 6); items None leaves them to the caller (test jobs)."""
    payload = {"schema_version": 6, "job_id": job_id, "stage": stage_labels["restore"], "created_at": now(),
               "report_folder": report_folder, "output_folder": output_folder}
    return payload | ({"items": items} if items is not None else {})


def write_job(folder: str, payload: dict) -> None:
    """Create the output folder, then the job file in offen."""
    share_path(payload["output_folder"]).mkdir(parents=True, exist_ok=True)
    write_text_atomic(share_path(f"{folder}/offen/{payload['job_id']}.json"), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _mirror(record: dict) -> dict:
    return {key: record[key] for key in mirror_keys}


def _open_clips(record: dict) -> list[str]:
    return [clip_id for clip_id in record["clips"] if clip_id not in record["done"]]


def _members(state: dict, record: dict) -> list[dict]:
    """Clips that still carry this job."""
    clips = (state["clips"].get(clip_id) for clip_id in _open_clips(record))
    return [clip for clip in clips if clip and clip["job"] and clip["job"]["id"] == record["id"]]


def _create(state: dict, kind: str, tape: str, clips: list[dict], items: list[dict]) -> None:
    restore, folder = state["restore"], job_folder("restore")
    job_id = f"{stamp()}__{restore['counter'] + 1}_restore"
    payload = job_payload(job_id, f"{folder}/fertig", f"{folder}/{outbox}/{job_id}", items)
    write_job(folder, payload)
    restore["counter"] += 1
    record = {"id": job_id, "stage": "restore", "kind": kind, "tape": tape, "folder": folder, "file": f"{job_id}.json",
              "output_folder": payload["output_folder"], "state": "offen", "worker": None,
              "created_at": payload["created_at"], "running_since": None, "missing_since": None,
              "clips": [clip["clip_id"] for clip in clips], "items": items, "folders": clip_folders(items), "done": {},
              "partials": []}
    restore["jobs"][job_id] = record
    for clip in clips:
        clip["job"] = _mirror(record)
        add_event(clip, "Restore-Job erstellt", f"{job_id} ({restore_kind_labels[kind]}, Band {tape}, {len(clips)} Clips)")


def _release(state: dict, record: dict, event: str) -> None:
    """Put the clips of a job back into the queue and forget the job."""
    for clip in _members(state, record):
        clip["job"] = None
        add_event(clip, event, record["file"])
    del state["restore"]["jobs"][record["id"]]


def withdraw(state: dict, record: dict) -> bool:
    """Withdraw a job no worker has taken; False if it is running or its file cannot be deleted yet."""
    if record["state"] == "laufend":
        return False
    if record["state"] == "offen" and not delete_job_file(f"{record['folder']}/offen/{record['file']}"):
        return False
    rmdir(record["output_folder"])
    _release(state, record, "Job zurückgezogen")
    return True


def withdraw_clip(state: dict, clip: dict) -> bool:
    """Withdraw the restore job of a clip (all its clips go back into the queue); False if it is running."""
    record = state["restore"]["jobs"].get(clip["job"]["id"])
    if record is None:
        clip["job"] = None
        return True
    return withdraw(state, record)


def _left(clip: dict | None) -> bool:
    return clip is None or not clip["active"] or clip["ready"] or clip["stage"] != "restore"


def schedule(state: dict, order: list[str]) -> None:
    """Withdraw open jobs with a clip that left the queue, then lay out big and small jobs up to [limits]."""
    jobs = state["restore"]["jobs"]
    for record in list(jobs.values()):
        if record["state"] == "offen" and any(_left(state["clips"].get(clip_id)) for clip_id in _open_clips(record)):
            withdraw(state, record)
    busy = Counter(record["kind"] for record in jobs.values())
    free = {kind: max(0, cfg[key] - busy[kind]) for kind, key in restore_kinds.items()}
    locked = {record["tape"].casefold() for record in jobs.values()}
    ranks = {name: rank for rank, name in enumerate(order)}
    for kind, tape, clips, items in plan_jobs(waiting_clips(state["clips"].values()), ranks, locked, free,
                                              cfg["small_job_clips"]):
        _create(state, kind, tape, clips, items)


# --------- LOCATE ---------
def _locate(state: dict, record: dict, ctx: dict) -> None:
    folder, name, clips = record["folder"], record["file"], _members(state, record)
    if name.casefold() in listing(ctx, f"{folder}/offen"):
        if record["state"] == "laufend":
            for clip in clips:
                add_event(clip, "Job wieder offen", f"von {record.get('worker') or 'unbekannt'} zurückgegeben")
        record.update(state="offen", worker=None, running_since=None, missing_since=None)
        return
    worker = running(ctx, folder).get(name.casefold(), (None,))[0]
    if worker:
        taken = record.get("worker") != worker
        record.update(state="laufend", worker=worker, missing_since=None)
        if taken:
            record["running_since"] = now()
            for clip in clips:
                add_event(clip, "Job übernommen", worker)
        return
    if share_path(f"{folder}/fertig/{record['id']}.json").exists():
        return  # Report arrived during this run; it is collected next time.
    detail = f"Restore-Job {record['id']} ({len(clips)} Clips): {folder}/…/{name}"
    if not record.get("missing_since"):
        record.update(state="fehlt", missing_since=now())
        issue(ctx, "note", "Job-Datei nicht auffindbar (wird beobachtet)", record["id"], detail)
    elif age(record["missing_since"]) >= missing_job_grace:
        issue(ctx, "note", "Job-Datei verschwunden – Clips wieder wartend", record["id"], detail)
        rmdir(record["output_folder"])
        _release(state, record, "Job-Datei verschwunden")


def locate(state: dict, ctx: dict) -> None:
    """Follow all restore job files and copy their location to the member clips."""
    for record in list(state["restore"]["jobs"].values()):
        _locate(state, record, ctx)
    for record in state["restore"]["jobs"].values():
        for clip in _members(state, record):
            clip["job"].update(_mirror(record))


# --------- EVALUATION ---------
def valid_items(items) -> bool:
    """True if items is a non-empty list of job items with all fields."""
    return isinstance(items, list) and bool(items) and all(
        isinstance(item, dict) and all(type(item.get(key)) is kind for key, kind in item_keys.items()) for item in items)


def report_entries(items) -> dict[tuple[str, str], dict | None] | None:
    """Report entries by (clip_id, casefolded flow_hash); None for repeated keys; None if items is no list of objects."""
    if not isinstance(items, list) or not all(isinstance(entry, dict) for entry in items):
        return None
    found = {}
    for entry in items:
        if isinstance(entry.get("clip_id"), (str, int)) and isinstance(entry.get("flow_hash"), str):
            key = (str(entry["clip_id"]), entry["flow_hash"].casefold())
            found[key] = None if key in found else entry
    return found


def _keys(job: dict, clip_id: str) -> list[tuple[str, str]]:
    return [(clip_id, item["flow_hash"].casefold()) for item in job["items"] if item["clip_id"] == clip_id]


def _file_problem(job: dict, item: dict, entry: dict | None, missing: str) -> str | None:
    """Reason why one job item is not restored completely; None if its file is in place."""
    if entry is False:
        return missing
    if entry is None:
        return "Eintrag mehrfach im Report"
    if entry.get("status") != "restored":
        return str(entry.get("reason") or f"status {entry.get('status')!r}").strip()
    path = entry.get("path")
    parts = path.split("/") if isinstance(path, str) else []
    if not parts or any(part in ("", ".", "..") for part in parts) or \
            not path.casefold().startswith(f"{job['output_folder'].casefold()}/"):
        return f"path {path!r} liegt nicht im output_folder des Jobs"
    if parts[-1].casefold() != item["file"].casefold() or parts[-1].casefold().endswith(busy_suffixes):
        return f"path {path!r} passt nicht zum Dateinamen"
    try:
        size = share_path(path).stat().st_size if share_path(path).is_file() else None
    except OSError:
        size = None
    if size is None:
        return f"Datei {path} fehlt"
    if not size or size != item["size"]:
        return f"Datei {path}: {size} Byte statt {item['size']}"
    return None


def clip_check(job: dict, clip_id: str, entries: dict, missing: str = "kein Eintrag im Report") -> tuple[list[tuple[dict, str]], list[str]]:
    """Restored files (item, path) of one clip and the reasons why it is incomplete (none = complete); only reads."""
    files, reasons = [], []
    for item in (item for item in job["items"] if item["clip_id"] == clip_id):
        entry = entries.get((clip_id, item["flow_hash"].casefold()), False)
        if problem := _file_problem(job, item, entry, missing):
            reasons.append(f"{item['file']}: {problem}")
        else:
            files.append((item, entry["path"]))
    return files, reasons


def _evaluate(state: dict, record: dict, clip_id: str, entries: dict, missing: str, ctx: dict) -> None:
    """Take over or discard the result of one clip; every clip of a job is evaluated once."""
    clip, folder = state["clips"].get(clip_id), f"{record['output_folder']}/{record['folders'][clip_id]}"
    worker = record.get("worker") or "unbekannt"
    if clip is None or not clip["job"] or clip["job"]["id"] != record["id"] or _left(clip):
        remove_tree(folder, ctx, "Clip-Ordner nicht löschbar (bleibt liegen)")
        record["done"][clip_id] = "verworfen"
        if clip and clip["job"] and clip["job"]["id"] == record["id"]:
            clip["job"] = None
            add_event(clip, "Restore-Ergebnis verworfen", f"{record['id']}: Clip inaktiv oder nicht mehr im Restore")
        issue(ctx, "note", "Restore-Ergebnis verworfen (Clip inaktiv oder nicht mehr im Restore)", clip_id,
              clip_text(clip) if clip else f"clip_id={clip_id} nicht in der JSON")
        return
    files, reasons = clip_check(record, clip_id, entries, missing)
    clip["job"] = None
    if not reasons:
        target = master_folder(clip["collection"], clip_id)
        for item, path in files:
            move(path, target, item["file"], replace=True)
        clip["files"]["master"] = {"folder": target, "names": list(clip["master_files"]), "source": "Restore",
                                   "last_seen_at": now()}
        clip["attempts"] = 0
        add_event(clip, "Restore-Job fertig", f"Worker {worker}, Job {record['id']}")
        enter(clip, "transcode")
    else:
        clip["attempts"] += 1
        add_event(clip, "Restore-Job fehlgeschlagen", f"Worker {worker}: {'; '.join(reasons)}")
        set_issue(clip, "sticky", job_failed, f"stage=Restore, job_id={record['id']}, worker={worker}, result={'; '.join(reasons)}")
    remove_tree(folder, ctx, "Clip-Ordner nicht löschbar (bleibt liegen)")
    record["done"][clip_id] = "unvollständig" if reasons else "vollständig"
    failed = bool(reasons)
    record_job({"at": now(), "stage": "restore", "job_id": record["id"], "clip_id": clip_id, "identifier": clip["identifier"],
                "title": clip["title"], "collection": clip["collection"], "status": "failed" if failed else "ok",
                "result": "; ".join(reasons), "preset": None, "worker": record.get("worker"),
                "attempt": 1 if failed else None, "max_attempts": 1 if failed else None, "final": failed, "output": None})


def _read(relative: str, ctx: dict, label: str):
    try:
        return json.loads(share_path(relative).read_text(encoding="utf-8")), True
    except (OSError, UnicodeError, ValueError) as exc:
        issue(ctx, "note", f"{label} unlesbar (wird erneut versucht)", relative, f"{relative}: {exc}")
        return None, False


def _partial(state: dict, folder: str, name: str, job_id: str, ctx: dict) -> None:
    relative, archived = f"{folder}/fertig/{name}", f"{Path(name).stem}.report.json"
    data, ok = _read(relative, ctx, "Teilbericht")
    if not ok:
        return
    entries = report_entries(data.get("items")) if isinstance(data, dict) else None
    if not entries or data.get("job_id") != job_id:
        issue(ctx, "note", "Teilbericht ungültig (wird erneut versucht)", relative,
              f"{relative}: erwartet {{\"job_id\": \"{job_id}\", \"items\": [...]}}")
        return
    record = state["restore"]["jobs"].get(job_id)
    if record is None:
        issue(ctx, "note", "Veralteter Teilbericht (ignoriert und archiviert)", relative, relative)
        move(relative, f"{folder}/archiv", archived)
        return
    for clip_id in _open_clips(record):
        if all(entries.get(key) for key in _keys(record, clip_id)):  # Clips not complete in here wait for the report.
            _evaluate(state, record, clip_id, entries, "kein Eintrag im Teilbericht", ctx)
    record["partials"].append(name)
    move(relative, f"{folder}/archiv", archived)


def _report(state: dict, folder: str, name: str, ctx: dict) -> None:
    relative = f"{folder}/fertig/{name}"
    report, ok = _read(relative, ctx, "Jobreport")
    if not ok:
        return
    if problem := report_problem(report):
        issue(ctx, "note", "Jobreport ungültig (wird erneut versucht)", relative, f"{relative}: {problem}")
        return
    job_id, archived = report["job_id"], f"{Path(name).stem}.report.json"
    record = state["restore"]["jobs"].get(job_id)
    if record is None:
        issue(ctx, "note", "Veralteter Jobreport (ignoriert und archiviert)", relative, relative)
        move(relative, f"{folder}/archiv", archived)
        retire_job(folder, job_id, ctx)
        return
    record["worker"] = archive_job(record) or record.get("worker")
    entries = report_entries(report.get("items"))
    result = str(report.get("result") or "").strip()
    missing = "items fehlt oder ungültig im Report" if entries is None else "kein Eintrag im Report"
    missing += f" (Report: {result})" if result else ""
    for clip_id in _open_clips(record):
        _evaluate(state, record, clip_id, entries or {}, missing, ctx)
    remove_tree(record["output_folder"], ctx, "Ausgang nicht löschbar (bleibt liegen)")
    move(relative, f"{folder}/archiv", archived)
    del state["restore"]["jobs"][job_id]


def split_name(name: str) -> tuple[str, bool]:
    """Job id of a file in fertig and whether it is a partial report."""
    stem, index = Path(name).stem, name.casefold().find(partial_marker)
    return (name[:index], True) if index > 0 else (stem, False)


def collect(state: dict, ctx: dict, test_ids: frozenset[str]) -> None:
    """Evaluate partial reports (in name order), then reports; test jobs stay untouched."""
    folder = job_folder("restore")
    files = []
    for name, _ in scan(f"{folder}/fertig").values():
        job_id, partial = split_name(name)
        if name.casefold().endswith(".json") and job_id.casefold() not in test_ids:
            files.append((not partial, name, job_id))
    for report, name, job_id in sorted(files):
        if report:
            _report(state, folder, name, ctx)
        else:
            _partial(state, folder, name, job_id, ctx)


# --------- REPORT ---------
def job_lines(state: dict) -> list[tuple[str, dict]]:
    """Description and record of every restore job for the report checks."""
    return [(f"Restore-Sammeljob ({restore_kind_labels[record['kind']]}, Band {record['tape']}, "
             f"{len(_open_clips(record))} von {len(record['clips'])} Clips offen)", record)
            for record in state["restore"]["jobs"].values()]
