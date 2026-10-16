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
from .restore import job_lines


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
        job_ids = data.get("job_ids")
        current[worker] = old if old and old["raw"] == text else {
            "raw": text, "changed_at": now(), "stage": str(data.get("stage") or ""),
            "host": str(data.get("host") or ""), "job_id": data.get("job_id"),
            "job_ids": [str(item) for item in job_ids] if isinstance(job_ids, list) else None}
    state["workers"] = current


def reported_jobs(worker: dict) -> list[str]:
    """Jobs a heartbeat reports: job_ids if present, else job_id."""
    if isinstance(worker.get("job_ids"), list):
        return worker["job_ids"]
    return [str(worker["job_id"])] if worker.get("job_id") else []


def watch_lines(state: dict) -> list[str]:
    """Report lines for running jobs without a fitting heartbeat or running too long."""
    timeout, lines = timedelta(minutes=cfg["worker_timeout_minutes"]), []
    jobs = [(clip_text(clip), clip["job"]) for clip in sorted(state["clips"].values(), key=lambda item: int(item["clip_id"]))
            if clip["job"] and clip["job"]["stage"] != "restore"] + job_lines(state)
    for text, job in jobs:
        if job["state"] != "laufend":
            continue
        since = job.get("running_since") or job["created_at"]
        worker, reasons = state["workers"].get(job["worker"]), []
        if worker is None:
            reasons.append("kein Heartbeat vom Worker")
        elif age(worker["changed_at"]) > timeout:
            reasons.append(f"Worker ohne Lebenszeichen seit {duration(age(worker['changed_at']))}")
        elif job["id"] not in reported_jobs(worker) and age(since) > timeout:
            reasons.append(f"Worker meldet anderen Job ({', '.join(reported_jobs(worker)) or 'keinen'})")
        if age(since) > timedelta(hours=cfg["max_job_hours"]):
            reasons.append(f"läuft länger als {cfg['max_job_hours']} h")
        if reasons:
            lines.append(f"  {text}; {stage_labels[job['stage']]}-Job {job['id']}; Worker {job['worker']}; "
                         f"läuft seit {since}; {'; '.join(reasons)}")
    return lines


def worker_lines(state: dict) -> list[str]:
    """Report lines of all known workers."""
    return [f"  {name}, {worker['stage'] or '?'}, Rechner {worker['host'] or '?'}, letztes Lebenszeichen vor "
            f"{duration(age(worker['changed_at']))}, Jobs {', '.join(reported_jobs(worker)) or '–'}"
            for name, worker in sorted(state["workers"].items())]
