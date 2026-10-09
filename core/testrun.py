"""Test mode: test jobs from the test list run through the workers exactly like production jobs.

Marathon lays out test jobs into the normal job pools, follows them and collects their reports, but never evaluates
them: marathon.json is only read, worker results stay in <work_dir>/test/<stage>/ausgang/<job_id>, nothing is moved on,
retried or deleted. Job file and report are archived like in production. Production cycles skip all test job ids.
"""
# --------- IMPORTS ---------
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import app_name, app_version
from .constants import (
    limit_keys, missing_job_grace, outbox, stage_labels, stages, test_box, test_entry_keys, test_protected)
from .config import cfg, reports_dir, state_path, test_state_path
from .console import log
from .util import age, context, file_stamp, now, stamp, write_new
from .layout import check_root, job_folder, load_mapping, res, share_path
from .share import delete_job_file, ensure_folders, listing, move, rmdir, running, scan, write_text_atomic
from .state import load_state, save_state
from .ffe import sync_references
from .audit import report_problem
from .jobs import archive_job, job_payload


# --------- STATE ---------
def _load() -> dict:
    if not test_state_path.exists():
        return {"schema_version": 1, "run": None, "job_ids": []}
    data = json.loads(test_state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("job_ids"), list):
        raise ValueError(f"Unbekanntes Format in {test_state_path}; Test-Jobs nicht erkennbar, keine Änderung.")
    return data


def _open_run(data: dict) -> dict | None:
    run = data["run"]
    return run if run and not run["finished_at"] else None


def test_job_ids() -> frozenset[str]:
    """Casefolded ids of all test jobs ever laid out; production cycles leave these jobs and reports alone."""
    return frozenset(job_id.casefold() for job_id in _load()["job_ids"])


def open_test_run() -> str | None:
    """Id of the unfinished test run, if any."""
    run = _open_run(_load())
    return run["id"] if run else None


def _progress(run: dict) -> str:
    counts = Counter(case["result"]["status"] for case in run["cases"] if case["result"])
    details = ", ".join(f"{status} {count}" for status, count in sorted(counts.items()))
    return f"{sum(counts.values())}/{len(run['cases'])} fertig" + (f" ({details})" if details else "")


def test_status() -> str:
    """Short status of the last test run for the console."""
    try:
        run = _load()["run"]
    except (OSError, UnicodeError, ValueError) as exc:
        return f"Teststand nicht lesbar: {exc}"
    if not run:
        return "kein Test-Lauf"
    return f"Test-Lauf {run['id']} {'abgeschlossen' if run['finished_at'] else 'offen'}: {_progress(run)}"


def _note(run: dict, text: str) -> None:
    """Log a note once per test run and keep it for the test report."""
    if text not in run["notes"]:
        run["notes"].append(text)
        log(text)


# --------- TEST LIST ---------
def _source_problem(stage: str, fields: dict, clip: dict | None) -> str | None:
    """Reason why the clip cannot provide the default job fields of the stage; None if it can."""
    if clip is None:
        return "nicht in marathon.json"
    master = clip["files"]["master"]
    if stage == "transcode" and "inputs" not in fields and (not master or master.get("deleted_at")):
        return "kein vorhandener Master; \"inputs\" in \"fields\" angeben"
    if stage == "transcode" and "proxy_name" not in fields and not clip.get("veritone_id"):
        return "Veritone-ID fehlt; \"proxy_name\" in \"fields\" angeben"
    if stage == "qc" and "input" not in fields and not clip["files"]["proxy"]:
        return "kein Proxy; \"input\" in \"fields\" angeben"
    return None


def _case(number: int, entry, labels: dict[str, str], clips: dict) -> dict:
    """Checked test case of a test list entry; raises ValueError with the reason."""
    if not isinstance(entry, dict):
        raise ValueError("ist kein Objekt")
    if unknown := sorted(set(entry) - test_entry_keys):
        raise ValueError(f"unbekannte Schlüssel {', '.join(unknown)} (erlaubt: {', '.join(sorted(test_entry_keys))})")
    stage = labels.get(str(entry.get("stage", "")).casefold())
    if stage is None:
        raise ValueError(f"stage {entry.get('stage')!r} unbekannt (erlaubt: {', '.join(stage_labels.values())})")
    clip_id, name, fields = entry.get("clip_id"), entry.get("name"), entry.get("fields", {})
    if type(clip_id) not in (str, int) or not str(clip_id).strip():
        raise ValueError("clip_id fehlt")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise ValueError("name ist kein Text")
    if not isinstance(fields, dict):
        raise ValueError("fields ist kein Objekt")
    if protected := sorted(test_protected & set(fields)):
        raise ValueError(f"fields darf {', '.join(protected)} nicht setzen (vergibt Marathon)")
    clip_id = str(clip_id).strip()
    if problem := _source_problem(stage, fields, clips.get(clip_id)):
        raise ValueError(f"clip_id {clip_id}: {problem}")
    return {"number": number, "name": (name or f"{stage_labels[stage]} {clip_id}").strip(), "stage": stage,
            "clip_id": clip_id, "fields": fields, "job": None, "job_count": 0, "result": None}


def _read_cases(clips: dict) -> list[dict]:
    """All test cases of the test list; raises ValueError listing every invalid entry."""
    path = res("test_file")
    if not path.is_file():
        raise ValueError(f"Testliste {path} fehlt (Aufbau siehe README, Abschnitt Test-Modus).")
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    tests = document.get("tests") if isinstance(document, dict) and document.get("schema_version") == 1 else None
    if not isinstance(tests, list) or not tests:
        raise ValueError(f"Testliste {path.name}: erwartet {{\"schema_version\": 1, \"tests\": [...]}} mit mindestens einem Test.")
    labels = {label.casefold(): stage for stage, label in stage_labels.items()}
    cases, problems = [], []
    for number, entry in enumerate(tests, 1):
        try:
            cases.append(_case(number, entry, labels, clips))
        except ValueError as exc:
            problems.append(f"Test {number}: {exc}")
    if problems:
        raise ValueError(f"Testliste {path.name} ungültig, kein Test-Lauf gestartet:\n" + "\n".join(problems))
    return cases


# --------- JOBS ---------
def _close(case: dict, status: str, text: str) -> None:
    """Result set by Marathon itself (job not laid out or test run cancelled)."""
    case["result"] = {"status": status, "result": text, "preset": None, "new_master": None,
                      "worker": (case["job"] or {}).get("worker"), "at": now(), "report": None}


def _record(case: dict, report: dict, worker: str | None) -> None:
    result = str(report.get("result") or "").strip()
    case["job"].update(state="fertig", worker=worker)
    case["result"] = {"status": report["status"], "result": result, "preset": report.get("preset"),
                      "new_master": report.get("new_master"), "worker": worker, "at": now(), "report": report}
    log(f"Test {case['number']} ({case['name']}): {report['status']}" + (f" – {result}" if result else "") +
        f"; Ergebnis bleibt in {case['job']['output_folder']}")


def _collect(run: dict, folder: str, known: set[str]) -> None:
    """Take over reports of test jobs; reports without an open test job are archived without evaluation."""
    cases = {case["job"]["id"]: case for case in run["cases"] if case["job"] and not case["result"]}
    for name, _ in sorted(scan(f"{folder}/fertig").values()):
        job_id = Path(name).stem
        if not name.casefold().endswith(".json") or job_id.casefold() not in known:
            continue  # Production reports wait for the job loop.
        relative = f"{folder}/fertig/{name}"
        try:
            report = json.loads(share_path(relative).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            _note(run, f"Test-Report unlesbar (wird erneut versucht): {relative}: {exc}")
            continue
        problem = report_problem(report) or ("job_id passt nicht zum Dateinamen" if report["job_id"] != job_id else None)
        if problem:
            _note(run, f"Test-Report ungültig (wird erneut versucht): {relative}: {problem}")
            continue
        case = cases.get(job_id)
        worker = archive_job(case["job"] if case else {"folder": folder, "file": f"{job_id}.json"})
        move(relative, f"{folder}/archiv", f"{job_id}.report.json")
        if case is None:
            _note(run, f"Test-Report ohne offenen Test-Job archiviert (nicht gewertet): {relative}")
            continue
        _record(case, report, worker or case["job"]["worker"])


def _locate(run: dict, case: dict, ctx: dict) -> None:
    """Follow a test job like a production job; a vanished job file is laid out again after the grace time."""
    job = case["job"]
    folder, key = job["folder"], job["file"].casefold()
    if key in listing(ctx, f"{folder}/offen"):
        job.update(state="offen", worker=None, missing_since=None)
        return
    worker = running(ctx, folder).get(key, (None,))[0]
    if worker:
        if job["worker"] != worker:
            job["running_since"] = now()
        job.update(state="laufend", worker=worker, missing_since=None)
        return
    if share_path(f"{folder}/fertig/{job['file']}").exists():
        return  # Report arrived during this cycle; it is collected next time.
    if not job["missing_since"]:
        job.update(state="fehlt", missing_since=now())
        _note(run, f"Test-Job-Datei nicht auffindbar (wird beobachtet): {folder}/…/{job['file']}")
    elif age(job["missing_since"]) >= missing_job_grace:
        _note(run, f"Test-Job-Datei verschwunden – Test-Job wird neu erstellt: {folder}/…/{job['file']}")
        rmdir(job["output_folder"])
        case["job"] = None


def _create_job(data: dict, run: dict, case: dict, clip: dict | None) -> None:
    stage, folder = case["stage"], job_folder(case["stage"])
    if problem := _source_problem(stage, case["fields"], clip):
        _close(case, "nicht ausgelegt", f"clip_id {case['clip_id']}: {problem}")
        log(f"Test {case['number']} ({case['name']}) nicht ausgelegt: {case['result']['result']}")
        return
    case["job_count"] += 1
    job_id = f"{stamp()}__{clip['clip_id']}__{stage_labels[stage].casefold()}{case['job_count']}"
    output = f"{cfg['work_dir']}/{test_box}/{stage}/{outbox}/{job_id}"
    marker = {"run": run["id"], "number": case["number"], "name": case["name"]}
    payload = job_payload(clip, stage, job_id, f"{folder}/fertig", output, {**case["fields"], "test": marker})
    data["job_ids"].append(job_id)
    share_path(output).mkdir(parents=True, exist_ok=True)
    write_text_atomic(share_path(f"{folder}/offen/{job_id}.json"), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    case["job"] = {"id": job_id, "folder": folder, "file": f"{job_id}.json", "output_folder": output, "state": "offen",
                   "worker": None, "created_at": payload["created_at"], "running_since": None, "missing_since": None}
    log(f"Test-Job erstellt: {job_id} (Test {case['number']}: {case['name']})")


def _schedule(data: dict, run: dict, clips: dict) -> None:
    """Lay out test jobs in list order, at most [limits] open test jobs per stage."""
    for stage in stages:
        cases = [case for case in run["cases"] if case["stage"] == stage and not case["result"]]
        pending = sum(1 for case in cases if case["job"] and case["job"]["state"] == "offen")
        for case in [case for case in cases if not case["job"]][:max(0, cfg[limit_keys[stage]] - pending)]:
            _create_job(data, run, case, clips.get(case["clip_id"]))


def _production_jobs(data: dict) -> int:
    """Number of job files in offen/laufend that are not test jobs."""
    known, ctx = {f"{job_id}.json".casefold() for job_id in data["job_ids"]}, context()
    return sum(1 for stage in stages for key in (*listing(ctx, f"{job_folder(stage)}/offen"), *running(ctx, job_folder(stage)))
               if key.endswith(".json") and key not in known)


# --------- REPORT ---------
def _summary(run: dict, when: datetime) -> str:
    head = ("Nr", "Test", "Stufe", "clip_id", "Status", "Preset", "Worker", "Job", "Ausgang", "Ergebnis")
    rows = []
    for case in run["cases"]:
        result, job = case["result"] or {}, case["job"] or {}
        rows.append((str(case["number"]), case["name"], stage_labels[case["stage"]], case["clip_id"],
                     *(str(result.get(key) or "–") for key in ("status", "preset", "worker")),
                     job.get("id") or "–", job.get("output_folder") or "–", result.get("result") or ""))
    lines = [f"{app_name} {app_version} | Test-Lauf {run['id']} | {when.isoformat(timespec='seconds')}", "",
             f"Testliste: {run['test_file']}; gestartet: {run['started_at']}; {_progress(run)}", "",
             " | ".join(head), *(" | ".join(row).rstrip() for row in rows)]
    if run["notes"]:
        lines += ["", f"Hinweise: {len(run['notes'])}", *(f"  {note}" for note in run["notes"])]
    return "\n".join(lines) + "\n"


def _finish(run: dict) -> None:
    when = datetime.now().astimezone()
    name = f"{file_stamp('test', when)}.txt"
    write_new(reports_dir / name, _summary(run, when))
    run.update(finished_at=now(), report=name)
    log(f"Test-Lauf {run['id']} abgeschlossen: {_progress(run)}; Testbericht: reports/{name}")


# --------- COMMAND ---------
def start_test() -> None:
    """Start a new test run from the test list, or resume the unfinished one."""
    check_root()
    data = _load()
    if run := _open_run(data):
        log(f"Test-Lauf {run['id']} wird fortgesetzt: {_progress(run)}.")
        return
    if not state_path.exists():
        raise RuntimeError("Noch keine JSON – Test-Jobs brauchen die Clips aus marathon.json (zuerst 'update-index' oder 'run').")
    cases = _read_cases(load_state()["clips"])
    data["run"] = {"id": stamp(), "test_file": cfg["test_file"], "started_at": now(), "finished_at": None, "report": None,
                   "notes": [], "cases": cases}
    save_state(data, test_state_path)
    log(f"Test-Lauf {data['run']['id']} gestartet: {len(cases)} Tests aus {cfg['test_file']}.")
    if busy := _production_jobs(data):
        log(f"Hinweis: {busy} Produktions-Jobs liegen in offen/laufend. Worker nehmen ältere Jobs zuerst; "
            f"deren Reports bleiben liegen, bis 'run' sie einsammelt.")


def test_cycle() -> bool:
    """One test cycle: collect test reports, follow and lay out test jobs; True once no test run is open."""
    data = _load()
    run = _open_run(data)
    if not run:
        return True
    mapping = load_mapping()
    check_root()
    clips = load_state()["clips"] if state_path.exists() else {}  # Read only; test mode never saves marathon.json.
    ctx = context()
    ensure_folders(mapping)
    sync_references(ctx)
    known = {job_id.casefold() for job_id in data["job_ids"]}
    for stage in stages:
        _collect(run, job_folder(stage), known)
    for case in run["cases"]:
        if case["job"] and not case["result"]:
            _locate(run, case, ctx)
    _schedule(data, run, clips)
    for item in ctx["issues"]:
        _note(run, f"{item['category']}: {item['detail']}")
    if all(case["result"] for case in run["cases"]):
        _finish(run)
    save_state(data, test_state_path)
    return bool(run["finished_at"])


def cancel_test() -> None:
    """Finish the open test run: collect waiting reports, withdraw test jobs no worker has taken, write the test report."""
    data = _load()
    run = _open_run(data)
    if not run:
        log("Kein offener Test-Lauf.")
        return
    check_root()
    known = {job_id.casefold() for job_id in data["job_ids"]}
    for stage in stages:
        _collect(run, job_folder(stage), known)
    for case in run["cases"]:
        job = case["job"]
        if case["result"]:
            continue
        if job and delete_job_file(f"{job['folder']}/offen/{job['file']}"):
            rmdir(job["output_folder"])
            _close(case, "abgebrochen", "Test-Job zurückgezogen")
        elif job:
            _close(case, "abgebrochen", f"Job {job['state']}" + (f" bei {job['worker']}" if job["worker"] else "") +
                   "; ein späterer Report wird im nächsten Test-Lauf archiviert, aber nicht gewertet")
        else:
            _close(case, "abgebrochen", "nicht ausgelegt")
    _finish(run)
    save_state(data, test_state_path)
