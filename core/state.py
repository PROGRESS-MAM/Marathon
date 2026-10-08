"""JSON state: load, check, save; new clips; history and issues of a clip."""
# --------- IMPORTS ---------
import json
import os
import tempfile
from pathlib import Path

from .constants import ffe_flag, stage_labels, stages
from .config import state_dir, state_path
from .util import now, stamp


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
    return {"schema_version": 7, "priority": None, "notes": [], "index": {"updated_at": None, "counts": {}, "error_list": None},
            "ffe": {"updated_at": None, "counts": {}, "error_list": None, "ambiguous_list": None}, "workers": {}, "clips": {}}


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
    job = clip.get("job")
    keys = ("id", "stage", "folder", "file", "output_folder", "state")
    if job is not None and (not isinstance(job, dict) or not all(isinstance(job.get(key), str) for key in keys)):
        return "Job-Eintrag unvollständig"
    task = clip.get("editshare")
    if task is not None and (not isinstance(task, dict) or not isinstance(task.get("pending"), bool) or
                             not isinstance(task.get("value"), str) or type(task.get("attempts")) is not int):
        return "EditShare-Eintrag unvollständig"
    return None


def load_state() -> dict:
    """Load and check the JSON; empty state if the file does not exist yet."""
    if not state_path.exists():
        return _empty_state()
    with state_path.open(encoding="utf-8") as handle:
        state = json.load(handle)
    if not isinstance(state, dict) or state.get("schema_version") != 7 or not isinstance(state.get("clips"), dict) or \
            not isinstance(state.get("ffe"), dict):
        raise ValueError("Unbekanntes Zustandsformat; keine Aktualisierung.")
    for clip_id, clip in state["clips"].items():
        problem = _clip_problem(clip_id, clip)
        if problem:
            raise ValueError(f"Ungültiger Zustand für Clip_ID {clip_id!r}: {problem}; keine Aktualisierung.")
    return state


def save_state(state: dict) -> None:
    """Write the JSON atomically."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=state_dir,
                                         prefix=".marathon-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, state_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def new_clip(clip_id: str, hit: dict) -> dict:
    """New clip entry from a search hit."""
    return {"clip_id": clip_id, "collection": hit["collection"], "identifier": hit["identifier"], "veritone_id": hit["veritone_id"],
            "title": hit["title"], "clip_name_with_extension": hit["clip_name"], "filehashes": hit["hashes"],
            "master_files": hit["masters"], "lto_tapes": hit["lto_tapes"], "master_size": hit["master_size"], "status": "wartet", "active": True, "ready": False, ffe_flag: False, "stage": "restore",
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
