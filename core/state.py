"""JSON state (version 8): load, check, save; new clips; history and issues of a clip."""
# --------- IMPORTS ---------
import json
import os
import tempfile
from pathlib import Path

from .constants import ffe_flag, restore_kinds, stage_labels, stages
from .config import state_path
from .util import now, stamp


# --------- STATIC ---------
state_version = 8
record_keys = ("id", "stage", "kind", "tape", "folder", "file", "output_folder", "state")  # Text fields of a restore job.


# --------- FUNC ---------
def position(clip: dict) -> str:
    """Current position of a clip, e.g. "Queue Transcode, Job laufend bei <worker>"."""
    if clip["ready"]:
        return "Bereit"
    job = clip["job"]
    text = f"Queue {stage_labels[clip['stage']]}"
    if job:
        text += f", Job {job['state']}" + (f" bei {job['worker']}" if job.get("worker") else "")
    return text


def add_event(clip: dict, event: str, detail: str = "") -> None:
    """Append an event to the clip history."""
    clip["history"].append({"at": now(), "event": event, "position": position(clip), "detail": detail})


def set_issue(clip: dict, kind: str, category: str | None = None, detail: str = "", matches: list[str] | None = None) -> None:
    """Set an issue of a clip or clear it with category None; since stays while the category stays."""
    old = clip["issues"].get(kind)
    if category is None:
        clip["issues"][kind] = None
        return
    since = old["since"] if old and old["category"] == category else now()
    clip["issues"][kind] = {"category": category, "detail": detail, "matches": matches, "since": since}


def file_entry(folder: str, name: str, source: str) -> dict:
    """File entry for clip["files"]."""
    return {"folder": folder, "name": name, "source": source, "last_seen_at": now()}


def enter(clip: dict, stage: str) -> None:
    """Queue a clip in a stage and record it in the history."""
    clip["stage"], clip["queued_at"] = stage, stamp()
    add_event(clip, f"Weiter an {stage_labels[stage]}")


def _empty_state() -> dict:
    return {"schema_version": state_version, "restore": {"counter": 0, "jobs": {}}, "priority": None, "notes": [], "index": {"updated_at": None, "counts": {}, "error_list": None},
            "ffe": {"updated_at": None, "counts": {}, "error_list": None, "ambiguous_list": None}, "workers": {}, "clips": {}}


def _master_ok(entry) -> bool:
    return isinstance(entry, dict) and isinstance(entry.get("file"), str) and isinstance(entry.get("flow_hash"), str) and \
        type(entry.get("size")) is int and isinstance(entry.get("tapes"), list) and bool(entry["tapes"]) and \
        all(isinstance(tape, str) for tape in entry["tapes"])


def _record_problem(job_id: str, record) -> str | None:
    if not isinstance(record, dict) or record.get("id") != job_id or record.get("kind") not in restore_kinds:
        return "job_id oder Art passt nicht"
    if not all(isinstance(record.get(key), str) for key in record_keys):
        return "Felder unvollständig"
    if not all(isinstance(record.get(key), kind) for key, kind in (("clips", list), ("items", list), ("folders", dict),
                                                                  ("done", dict), ("partials", list))):
        return "Struktur unvollständig"
    return None


def _clip_problem(clip_id: str, clip) -> str | None:
    if not isinstance(clip, dict) or clip.get("clip_id") != clip_id:
        return "Clip_ID passt nicht zum Eintrag"
    if not all(isinstance(clip.get(key), bool) for key in ("active", "ready", ffe_flag)):
        return f"active/ready/{ffe_flag} fehlt"
    if not isinstance(clip.get("veritone_id"), (str, type(None))):  # Filled by update-index if missing.
        return "veritone_id ist kein Text"
    if clip.get("stage") not in (*stages, None) or clip["ready"] != (clip["stage"] is None):
        return "Stufe passt nicht zu bereit"
    if not all(isinstance(clip.get(key), kind) for key, kind in (("history", list), ("files", dict), ("issues", dict))):
        return "Struktur unvollständig"
    masters = clip.get("masters")
    if not isinstance(masters, list) or not all(_master_ok(entry) for entry in masters):
        return "masters fehlt oder ungültig"
    job = clip.get("job")
    keys = ("id", "stage", "folder", "file", "output_folder", "state")
    if job is not None and (not isinstance(job, dict) or not all(isinstance(job.get(key), str) for key in keys)):
        return "Job-Eintrag unvollständig"
    task = clip.get("editshare")
    if task is not None and (not isinstance(task, dict) or not isinstance(task.get("pending"), bool) or
                             not isinstance(task.get("value"), str) or type(task.get("attempts")) is not int):
        return "EditShare-Eintrag unvollständig"
    return None


def check_state(state) -> None:
    """Raise ValueError if state is no valid JSON version 8."""
    if isinstance(state, dict) and state.get("schema_version") == 7:
        raise ValueError("JSON-Version 7: zuerst mit tools/transfer_json_v8.py auf Version 8 übertragen; keine Aktualisierung.")
    restore = state.get("restore") if isinstance(state, dict) else None
    if not isinstance(state, dict) or state.get("schema_version") != state_version or not isinstance(state.get("clips"), dict) or \
            not isinstance(state.get("ffe"), dict) or not isinstance(restore, dict) or type(restore.get("counter")) is not int or \
            not isinstance(restore.get("jobs"), dict):
        raise ValueError("Unbekanntes Zustandsformat; keine Aktualisierung.")
    for job_id, record in restore["jobs"].items():
        if problem := _record_problem(job_id, record):
            raise ValueError(f"Ungültiger Restore-Job {job_id!r}: {problem}; keine Aktualisierung.")
    for clip_id, clip in state["clips"].items():
        problem = _clip_problem(clip_id, clip)
        job = clip.get("job") if isinstance(clip, dict) else None
        if not problem and job and job["stage"] == "restore" and job["id"] not in restore["jobs"]:
            problem = f"Restore-Job {job['id']} fehlt"
        if problem:
            raise ValueError(f"Ungültiger Zustand für Clip_ID {clip_id!r}: {problem}; keine Aktualisierung.")


def load_state() -> dict:
    """Load and check the JSON; empty state if the file does not exist yet."""
    if not state_path.exists():
        return _empty_state()
    with state_path.open(encoding="utf-8") as handle:
        state = json.load(handle)
    check_state(state)
    return state


def save_state(state: dict, path: Path = state_path) -> None:
    """Write the JSON (or another state file such as the test state) atomically."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.stem}-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def new_clip(clip_id: str, hit: dict) -> dict:
    """New clip entry from a search hit."""
    return {"clip_id": clip_id, "collection": hit["collection"], "identifier": hit["identifier"], "veritone_id": hit["veritone_id"],
            "title": hit["title"], "clip_name_with_extension": hit["clip_name"], "masters": hit["masters"],
            "master_files": hit["master_files"], "lto_tapes": hit["lto_tapes"], "master_size": hit["master_size"], "status": "wartet", "active": True, "ready": False, ffe_flag: False, "stage": "restore",
            "queued_at": stamp(), "preset": None, "job": None, "job_count": 0, "attempts": 0,
            "files": {"master": None, "proxy": None},
            "issues": {"file": None, "sticky": None}, "history": []}


def keep_notes(state: dict, issues: list[dict]) -> None:
    """Keep new notes for the next report, without duplicates."""
    known = {(item["category"], item["key"], item["detail"]) for item in state["notes"]}
    for item in issues:
        key = (item["category"], item["key"], item["detail"])
        if item["section"] == "note" and key not in known:
            state["notes"].append(item)
            known.add(key)
