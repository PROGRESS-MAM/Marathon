"""Run the FTP worker job cycle and take over its reports."""
# --------- IMPORTS ---------
import json
import os
from pathlib import Path

from .config import cfg
from .constants import ftp_label, ftp_stage, missing_job_grace, outbox
from .editshare import request_field, write_fields
from .layout import final_folder, job_folder, join, share_path
from .naming import ftp_name, proxy_name
from .state import add_event, ftp_record, position
from .util import age, clip_text, issue, now, stamp
from .audit import report_problem
from .jobs import _sweep_unknown_jobs
from .share import (
    archive_job, delete_job_file, listing, move, retire_job, rmdir, running, safe_work_path, scan,
    share_path as _share_path, write_text_atomic)


# --------- FUNC ---------
def _prepare_folders(folder: str) -> None:
    for box in ("offen", "laufend", "fertig", "archiv", outbox):
        safe_work_path(f"{folder}/{box}").mkdir(parents=True, exist_ok=True)


def _report_result(folder: str, name: str, ctx: dict) -> dict | None:
    relative = f"{folder}/fertig/{name}"
    try:
        report = json.loads(_share_path(relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        issue(ctx, "note", "Jobreport unlesbar (wird erneut versucht)", relative, f"{relative}: {exc}")
        return None
    problem = report_problem(report)
    if not problem and report["status"] == "ok" and (
            not isinstance(report.get("ftp_file"), str) or type(report.get("size")) is not int):
        problem = "ftp_file fehlt oder size ist keine Ganzzahl"
    if problem:
        issue(ctx, "note", "Jobreport ungültig (wird erneut versucht)", relative, f"{relative}: {problem}")
        return None
    return report


def _archive_report(folder: str, relative: str, job_id: str, job: dict | None, ctx: dict) -> str | None:
    worker = archive_job(job) if job else None
    move(relative, f"{folder}/archiv", f"{job_id}.report.json")
    if job:
        output = job["output_folder"]
        path = safe_work_path(output)
        if path.is_dir() and any(path.iterdir()):
            move(output, f"{folder}/archiv", f"{job_id}.{outbox}")
        else:
            rmdir(output)
    return worker or (job or {}).get("worker")


def _failed(clip: dict, record: dict, result: str, ctx: dict) -> None:
    record["attempts"] += 1
    add_event(clip, "FTP-Job fehlgeschlagen", result)
    if record["attempts"] >= cfg["max_job_attempts"]:
        record["error"] = {"category": "FTP-Job endgültig fehlgeschlagen", "detail": result, "at": now()}
        record["requested_at"] = None
        return
    issue(ctx, "note", "FTP-Job fehlgeschlagen – neuer Versuch", clip["clip_id"],
          f"{clip_text(clip)}: {result}")


def _collect_reports(folder: str, records: dict[str, tuple[dict, dict]], ctx: dict) -> None:
    for name, _ in sorted(scan(f"{folder}/fertig").values()):
        if not name.casefold().endswith(".json"):
            continue
        relative = f"{folder}/fertig/{name}"
        report = _report_result(folder, name, ctx)
        if report is None:
            continue
        job_id = report["job_id"]
        found = records.get(job_id)
        if found is None or found[1]["job"].get("folder") != folder:
            issue(ctx, "note", "Veralteter Jobreport (ignoriert und archiviert)", relative, relative)
            try:
                _archive_report(folder, relative, job_id, None, ctx)
                retire_job(folder, job_id, ctx)
            except OSError as exc:
                issue(ctx, "note", "FTP-Job konnte nicht archiviert werden", relative, f"{relative}: {exc}")
            continue

        clip, record = found
        if report["status"] == "ok" and report["ftp_file"] != record["job"]["ftp_name"]:
            issue(ctx, "note", "Jobreport ungültig (wird erneut versucht)", relative,
                  f"{relative}: ftp_file passt nicht zum Job")
            continue
        records.pop(job_id, None)
        job = record["job"]
        try:
            worker = _archive_report(folder, relative, job_id, job, ctx)
        except OSError as exc:
            issue(ctx, "note", "FTP-Job konnte nicht archiviert werden", relative, f"{relative}: {exc}")
            continue
        record["job"] = None
        result = str(report.get("result") or "").strip()
        status = report["status"]
        if status == "rejected":
            record["error"] = {"category": "Vom FTP-Worker abgelehnt", "detail": result, "at": now()}
            record["requested_at"] = None
            add_event(clip, "FTP abgelehnt", result)
            continue
        if status == "ok":
            target = Path(job["ftp_dir"]) / job["ftp_name"]
            try:
                confirmed = target.is_file() and target.stat().st_size == job["size"] == report["size"]
            except OSError:
                confirmed = False
            if confirmed:
                new_name = ftp_name(clip)
                record.update(target=str(target), size=job["size"], old_name=clip["files"]["proxy"]["name"],
                              new_name=new_name, copied_at=now(), error=None, attempts=0)
                add_event(clip, "An FTP kopiert", f"{target}, Worker {worker or 'unbekannt'}")
                continue
            result = f"Marathon: Kopie auf dem FTP nicht bestätigt: {target}"
        _failed(clip, record, result, ctx)


def _complete_rename(clip: dict, record: dict, final: str, old_name: str, new_name: str) -> None:
    clip["files"]["proxy"] = dict(clip["files"]["proxy"], name=new_name, last_seen_at=now())
    record.update(renamed_at=now(), requested_at=None, error=None)
    add_event(clip, "Quelle umbenannt", f"{final}/{old_name} → {final}/{new_name}")
    request_field(clip, final, new_name)


def _rename_source(clip: dict, record: dict) -> None:
    final, old_name, new_name = final_folder(clip["collection"]), record["old_name"], record["new_name"]
    source, target = share_path(join(final, old_name)), share_path(join(final, new_name))
    try:
        if not source.exists() and target.is_file() and target.stat().st_size == record["size"]:
            _complete_rename(clip, record, final, old_name, new_name)
            return
        names = scan(final)
        if ((os.name != "nt" and os.path.lexists(target)) or
                any(key == new_name.casefold() and key != old_name.casefold() for key in names)):
            raise FileExistsError(f"Datei bereits vorhanden: {target}")
        os.rename(source, target)
    except FileExistsError as exc:
        record["error"] = {"category": "Namenskonflikt im Zielordner", "detail": str(exc), "at": now()}
        return
    except OSError as exc:
        category = "Namenskonflikt im Zielordner" if isinstance(exc, FileExistsError) else "Umbenennen nicht möglich"
        detail = f"Umbenennen nicht möglich: {exc}"
        if category == "Namenskonflikt im Zielordner":
            detail = f"Datei bereits vorhanden: {target}"
        record["error"] = {"category": category, "detail": detail, "at": now()}
        return
    _complete_rename(clip, record, final, old_name, new_name)


def _locate_job(clip: dict, record: dict, ctx: dict) -> None:
    job = record["job"]
    folder, name = job["folder"], job["file"]
    if name.casefold() in listing(ctx, f"{folder}/offen"):
        if job["state"] == "laufend":
            add_event(clip, "FTP-Job wieder offen", f"von {job.get('worker') or 'unbekannt'} zurückgegeben")
        job.update(state="offen", worker=None, running_since=None, missing_since=None)
        return
    worker = running(ctx, folder).get(name.casefold(), (None,))[0]
    if worker:
        taken = job.get("worker") != worker
        job.update(state="laufend", worker=worker, missing_since=None)
        if taken:
            job["running_since"] = now()
            add_event(clip, "FTP-Job übernommen", worker)
        return
    if _share_path(f"{folder}/fertig/{job['id']}.json").exists():
        return
    if not job.get("missing_since"):
        job.update(state="fehlt", missing_since=now())
        issue(ctx, "note", "FTP-Job-Datei nicht auffindbar (wird beobachtet)", clip["clip_id"],
              f"{clip_text(clip)}: {folder}/…/{name}")
    elif age(job["missing_since"]) >= missing_job_grace:
        issue(ctx, "note", "FTP-Job-Datei verschwunden – Job neu erstellt", clip["clip_id"],
              f"{clip_text(clip)}: {folder}/…/{name}")
        rmdir(job["output_folder"])
        record["job"] = None
        add_event(clip, "FTP-Job-Datei verschwunden", name)


def _withdraw(clip: dict, record: dict) -> None:
    job = record["job"]
    if not job or job["state"] != "offen" or (clip["ready"] and clip["active"]):
        return
    delete_job_file(f"{job['folder']}/offen/{job['file']}")
    rmdir(job["output_folder"])
    record["job"] = None
    record["requested_at"] = None
    record["error"] = {"category": "Nicht mehr bereit", "detail": position(clip), "at": now()}
    add_event(clip, "FTP-Job zurückgezogen", job["file"])


def _create_job(clip: dict, record: dict, ctx: dict) -> None:
    folder = job_folder(ftp_stage)
    proxy = clip["files"]["proxy"]
    source = share_path(join(proxy["folder"], proxy["name"]))
    try:
        if not source.is_file() or source.stat().st_size == 0:
            record["error"] = {"category": "Proxy im Zielordner fehlt oder ist leer",
                               "detail": "Proxy im Zielordner fehlt oder ist leer", "at": now()}
            record["requested_at"] = None
            return
        size = source.stat().st_size
        record["job_count"] += 1
        job_id = f"{stamp()}__{clip['clip_id']}__ftp{record['job_count']}"
        output = f"{folder}/{outbox}/{job_id}"
        payload = {
            "schema_version": 6, "job_id": job_id, "stage": ftp_label, "clip_id": clip["clip_id"],
            "collection": clip["collection"], "identifier": clip["identifier"], "title": clip["title"],
            "clip_name": clip["clip_name_with_extension"], "created_at": now(),
            "report_folder": f"{folder}/fertig", "output_folder": output,
            "input": join(proxy["folder"], proxy["name"]), "size": size, "ftp_dir": cfg["ftp_dir"],
            "ftp_name": proxy_name(clip),
        }
        job_path = safe_work_path(f"{folder}/offen/{job_id}.json")
        if os.path.lexists(job_path):
            raise FileExistsError(f"FTP-Job-Datei bereits vorhanden: {job_path}")
        safe_work_path(output).mkdir(parents=True, exist_ok=True)
        write_text_atomic(job_path,
                          json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    except OSError as exc:
        issue(ctx, "note", "FTP-Job konnte nicht erstellt werden", clip["clip_id"], str(exc))
        return
    record["job"] = {
        "id": job_id, "folder": folder, "file": f"{job_id}.json", "output_folder": output,
        "state": "offen", "worker": None, "created_at": payload["created_at"], "running_since": None,
        "missing_since": None, "size": size, "ftp_dir": cfg["ftp_dir"], "ftp_name": payload["ftp_name"],
    }
    add_event(clip, "FTP-Job erstellt", job_id)


def ftp_cycle(state: dict, ctx: dict) -> None:
    """FTP jobs of the job loop: collect reports, confirm copies, rename sources, locate, withdraw and create jobs."""
    folder = job_folder(ftp_stage)
    _prepare_folders(folder)
    records = {record["job"]["id"]: (clip, record) for clip in state["clips"].values()
               if clip.get("ftp") is not None and (record := ftp_record(clip)).get("job")}
    _collect_reports(folder, records, ctx)
    ctx["listings"].clear()

    records_by_clip = {clip["clip_id"]: (clip, ftp_record(clip)) for clip in state["clips"].values()
                       if clip.get("ftp") is not None}
    for clip, record in records_by_clip.values():
        if record["copied_at"] and not record["renamed_at"] and clip["ready"] and clip["active"]:
            _rename_source(clip, record)

    for clip, record in records_by_clip.values():
        if record["job"]:
            _locate_job(clip, record, ctx)
    known = {record["job"]["file"].casefold() for _, record in records_by_clip.values() if record["job"]}
    _sweep_unknown_jobs(folder, known, ctx)

    for clip, record in records_by_clip.values():
        _withdraw(clip, record)
    waiting = sorted(((clip, record) for clip, record in records_by_clip.values()
                      if clip["ready"] and clip["active"] and clip["files"]["proxy"] and record["requested_at"]
                      and record["job"] is None and record["copied_at"] is None),
                     key=lambda item: (item[1]["requested_at"], int(item[0]["clip_id"])))
    free = max(0, cfg["ftp"] - sum(record["job"] is not None and record["job"]["state"] == "offen"
                                    for _, record in records_by_clip.values()))
    for clip, record in waiting[:free]:
        _create_job(clip, record, ctx)
    write_fields(state)
