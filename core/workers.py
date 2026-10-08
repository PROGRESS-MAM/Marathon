"""Worker heartbeats."""
# --------- IMPORTS ---------
import json
from datetime import timedelta
from pathlib import Path

from .constants import stage_labels, worker_dir
from .config import cfg
from .util import age, clip_text, duration, now
from .layout import share_path
from .share import scan


# --------- FUNC ---------
def read_workers(state: dict) -> None:
    """Read all heartbeats from the worker folder into state["workers"]."""
    folder, current = f"{cfg['work_dir']}/{worker_dir}", {}
    for key, (name, _) in sorted(scan(folder).items()):
        if not key.endswith(".json"):
            continue
        worker, old = Path(name).stem, state["workers"].get(Path(name).stem)
        try:
            text = share_path(f"{folder}/{name}").read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, UnicodeError, ValueError):
            data = None
        if not isinstance(data, dict):
            if old:
                current[worker] = old  # Half-written heartbeat; the timeout reveals real outages.
            continue
        current[worker] = old if old and old["raw"] == text else {
            "raw": text, "changed_at": now(), "stage": str(data.get("stage") or ""),
            "host": str(data.get("host") or ""), "job_id": data.get("job_id")}
    state["workers"] = current


def watch_lines(state: dict) -> list[str]:
    """Report lines for running jobs without a fitting heartbeat or running too long."""
    timeout, lines = timedelta(minutes=cfg["worker_timeout_minutes"]), []
    for clip in sorted(state["clips"].values(), key=lambda item: int(item["clip_id"])):
        job = clip["job"]
        if not job or job["state"] != "laufend":
            continue
        since = job.get("running_since") or job["created_at"]
        worker, reasons = state["workers"].get(job["worker"]), []
        if worker is None:
            reasons.append("kein Heartbeat vom Worker")
        elif age(worker["changed_at"]) > timeout:
            reasons.append(f"Worker ohne Lebenszeichen seit {duration(age(worker['changed_at']))}")
        elif worker["job_id"] != job["id"] and age(since) > timeout:
            reasons.append(f"Worker meldet anderen Job ({worker['job_id'] or 'keinen'})")
        if age(since) > timedelta(hours=cfg["max_job_hours"]):
            reasons.append(f"läuft länger als {cfg['max_job_hours']} h")
        if reasons:
            lines.append(f"  {clip_text(clip)}; {stage_labels[job['stage']]}-Job {job['id']}; Worker {job['worker']}; "
                         f"läuft seit {since}; {'; '.join(reasons)}")
    return lines


def worker_lines(state: dict) -> list[str]:
    """Report lines of all known workers."""
    return [f"  {name}, {worker['stage'] or '?'}, Rechner {worker['host'] or '?'}, letztes Lebenszeichen vor "
            f"{duration(age(worker['changed_at']))}, Job {worker['job_id'] or '–'}"
            for name, worker in sorted(state["workers"].items())]
