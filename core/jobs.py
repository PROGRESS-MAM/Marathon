"""Create, distribute and collect jobs; take over worker results.

Worker rules (paths relative to the share root, "/" as separator):
- Heartbeat at least once a minute: <work_dir>/worker/<worker>.json, temp name + rename:
  {"worker": str, "stage": "Restore"|"Transcode"|"QC", "host": str, "job_id": str|null, "beat": <changes>}
- Take the first *.json in <work_dir>/<stage>/offen (sorted by name) by renaming it into laufend/<worker>/;
  FileNotFoundError or PermissionError: another worker was faster or the job was withdrawn, try the next one.
- Read inputs only where the job says; write results only into the job's output_folder.
  Restore: all names from "files"; Transcode: exactly one proxy named exactly "proxy_name", optionally one new master
  (repaired and/or with FFE title) named <identifier>__<title>.<suffix>; QC: never move the proxy.
- Leave the job file in laufend; write the report as <report_folder>/<job_id>.json via a temp name not ending
  in ".json": {"job_id": str, "status": "ok"|"failed"|"rejected" (QC only), "result": str (required unless ok),
  "preset": str|null, "new_master": str|null (Transcode only: file name of the new master)}.
- FFE: every QC and Transcode job carries "ffe_tafel" (bool). QC jobs name the reference screenshot in
  "ffe_reference_image", Transcode jobs list all FFE title clips in "ffe_reference_clips". Marathon keeps these
  files in <work_dir>/worker/; workers only read them and never write into that folder except their heartbeat.
- Marathon moves results on (a new master into master_dir, never overwriting), archives job, report and output
  leftovers (a lone QC test report as <work_dir>/qc/archiv/<job_id>.aqc.json), deletes failed partial results and
  withdrawn jobs. Every collected production report goes into the job journal (core.details).
- Test jobs (core.testrun) share the pools; the job loop skips their job files and reports (test_ids).
"""
# --------- IMPORTS ---------
import json
from pathlib import Path

from .constants import (
    blocked_outcome, busy_suffixes, delivery_blocked, ffe_flag, ingest_source, invalid_path_chars, job_failed, limit_keys,
    master_blocked, missing_job_grace, outbox, protocol_suffixes, qc_rejected, qc_report_suffix, stage_labels, stages)
from .config import cfg, ignored
from .util import age, clip_text, file_name, format_detail, issue, normalize, now, stamp
from .layout import final_folder, job_folder, join, master_folder, qc_inbox, share_path, stage_folder
from .share import (
    DeliveryBlocked, MasterBlocked, delete_job_file, deliver_proxy, ensure_folders, job_output, listing, move,
    output_archive, remove_tree, rmdir, running, scan, store_master, subfolders, write_text_atomic)
from .state import add_event, enter, file_entry, set_issue
from .naming import defa_id, proxy_name
from .ffe import reference_clips, reference_image, sync_references
from .editshare import request_field, write_fields
from .workers import read_workers
from .audit import check_files, report_problem, status, update_activity
from .details import record_job


# --------- FUNC ---------
def archive_job(job: dict) -> str | None:
    """Move the job file (job["folder"], job["file"]) to archiv; returns the worker folder it was found in."""
    folder, name = job["folder"], job["file"]
    for worker in subfolders(f"{folder}/laufend"):
        if move(f"{folder}/laufend/{worker}/{name}", f"{folder}/archiv"):
            return worker
    move(f"{folder}/offen/{name}", f"{folder}/archiv")
    return None


def _finish_output(job: dict, keep: bool, ctx: dict) -> str | None:
    """Archive (keep=True) or delete whatever is left in the job's output folder; returns the archived file or folder.

    A QC output holding only its test report is archived flat as <work_dir>/qc/archiv/<job_id>.aqc.json.
    """
    out = job["output_folder"]
    path = share_path(out)
    if not path.is_dir():
        return None
    if keep and (items := list(path.iterdir())):
        lone = items[0] if len(items) == 1 and items[0].is_file() else None
        flat = job["stage"] == "qc" and lone is not None and lone.name.casefold().endswith(qc_report_suffix)
        source, target, name = (f"{out}/{lone.name}", f"{job_folder('qc')}/archiv", f"{job['id']}{qc_report_suffix}") if flat \
            else (out, output_archive(out), f"{job['id']}.{outbox}")
        try:
            moved = move(source, target, name)
        except OSError as exc:
            issue(ctx, "note", "Ausgang nicht archivierbar (bleibt liegen)", out, f"{out}: {exc}")
            return None
        rmdir(out)
        return f"{target}/{name}" if moved else None
    remove_tree(out, ctx, "Ausgang nicht löschbar (bleibt liegen)")
    return None


def _master_problem(clip: dict, name: str, delivered: dict[str, str]) -> str | None:
    """Reason why a reported new master cannot be taken over; None if it can."""
    if file_name(name) != name or any(char in invalid_path_chars for char in name) or ignored(name) or \
            name.casefold().endswith(protocol_suffixes) or normalize(defa_id(name) or "") != normalize(clip["identifier"]):
        return f"Neuer Master {name!r} passt nicht zum Schema <DEFA-ID>__<Titel>.<Endung> mit DEFA-ID {clip['identifier']}"
    if name.casefold() not in delivered:
        return f"Neuer Master {name!r} fehlt im Transcode-Ausgang oder ist leer"
    return None


def _take_outputs(clip: dict, job: dict, report: dict, ctx: dict) -> str | None:
    """Move the results of a successful job to the next stage; returns a problem text instead."""
    stage, out, collection = job["stage"], job["output_folder"], clip["collection"]
    delivered = {key: name for key, (name, size) in scan(out).items() if size and not key.endswith(busy_suffixes)}
    if stage == "restore":
        missing = [name for name in clip["master_files"] if name.casefold() not in delivered]
        if missing:
            return f"Restore unvollständig, fehlend: {', '.join(missing)}"
        target = master_folder(collection, clip["clip_id"])
        for name in clip["master_files"]:
            move(f"{out}/{delivered[name.casefold()]}", target, name, replace=True)
        clip["files"]["master"] = {"folder": target, "names": list(clip["master_files"]), "source": "Restore",
                                   "last_seen_at": now()}
        enter(clip, "transcode")
    elif stage == "transcode":
        new_master = str(report.get("new_master") or "").strip()
        if new_master and (problem := _master_problem(clip, new_master, delivered)):
            return problem
        proxies = [name for key, name in delivered.items() if not key.endswith(protocol_suffixes) and key != new_master.casefold()]
        if len(proxies) != 1:
            return f"Transcode-Ausgang enthält {len(proxies)} Proxy-Dateien statt einer"
        name, expected = proxies[0], proxy_name(clip)
        if not expected or name.casefold() != expected.casefold():
            return f"Proxy-Name {name!r} statt {expected!r} (proxy_name im Job)"
        if new_master:  # Not tracked further; master_dir belongs to the operator.
            new_master = delivered[new_master.casefold()]
            store_master(f"{out}/{new_master}", cfg["master_dir"], new_master)
            add_event(clip, "Neuer Master abgelegt", join(cfg["master_dir"], new_master))
        move(f"{out}/{name}", qc_inbox(collection), expected, replace=True)
        clip["files"]["proxy"] = file_entry(qc_inbox(collection), expected, "Transcode")
        clip["preset"] = report.get("preset")
        enter(clip, "qc")
    else:
        proxy, final = clip["files"]["proxy"], final_folder(collection)
        source = f"{proxy['folder']}/{proxy['name']}"
        if not share_path(source).is_file() or not share_path(source).stat().st_size:
            return f"Proxy {source} vor der Auslieferung nicht vorhanden oder leer"
        deliver_proxy(source, final, proxy["name"])
        clip["files"]["proxy"] = file_entry(final, proxy["name"], "QC")
        master = clip["files"]["master"]
        if master and not master.get("deleted_at") and master["source"] != ingest_source:  # Ingested masters are kept.
            remove_tree(master["folder"], ctx, "Master nicht löschbar (bleiben liegen)")
            if not share_path(master["folder"]).exists():
                master["deleted_at"] = now()
        clip.update(ready=True, stage=None)
        add_event(clip, "Bereit", f"{final}/{proxy['name']}")
        request_field(clip, final, proxy["name"])
    return None


def _apply_report(clip: dict, job: dict, report: dict, worker: str | None, ctx: dict) -> tuple[str, str, str | None]:
    """Take over a report; returns journal status, result text and archived output."""
    stage, label = job["stage"], stage_labels[job["stage"]]
    status, result = report["status"], str(report.get("result") or "").strip()
    by = f"Worker {worker or 'unbekannt'}"

    def job_text(result: str) -> str:
        return (f"stage={label}, job_id={job['id']}, worker={worker or 'unbekannt'}, "
                f"attempts={clip['attempts']}, result={result}")

    clip["job"] = None
    if status == "rejected" and stage != "qc":
        status = "failed"
    if status == "ok":
        add_event(clip, f"{label}-Job fertig", by + (f", Preset {report['preset']}" if report.get("preset") else ""))
        try:
            problem = _take_outputs(clip, job, report, ctx)
        except DeliveryBlocked as exc:
            category = master_blocked if isinstance(exc, MasterBlocked) else delivery_blocked
            set_issue(clip, "sticky", category, job_text(str(exc)))
            add_event(clip, category, str(exc))
            return blocked_outcome, f"Marathon: {exc}", _finish_output(job, True, ctx)
        if problem is None:
            clip["attempts"] = 0
            return "ok", result, _finish_output(job, True, ctx)
        status, result, report_result = "failed", problem, f"Marathon: {problem}"
    else:
        report_result = result
    if status == "rejected":
        set_issue(clip, "sticky", qc_rejected, job_text(result))
        add_event(clip, qc_rejected, f"{by}: {result}")
        return "rejected", report_result, _finish_output(job, True, ctx)
    clip["attempts"] += 1
    add_event(clip, f"{label}-Job fehlgeschlagen", f"{by}: {result}")
    _finish_output(job, False, ctx)
    if clip["attempts"] >= cfg["max_job_attempts"]:
        set_issue(clip, "sticky", job_failed, job_text(result))
    else:
        issue(ctx, "note", "Job fehlgeschlagen – neuer Versuch", clip["clip_id"], format_detail(clip_text(clip), job_text(result)))
    return "failed", report_result, None


def _retire(folder: str, job_id: str, ctx: dict) -> None:
    """Archive job file and output folder of a job Marathon no longer tracks, if they exist."""
    found = running(ctx, folder).get(f"{job_id}.json".casefold())
    if not found:
        return
    relative = f"{folder}/laufend/{found[0]}/{found[1]}"
    output = job_output(relative, Path(found[1]).stem)
    move(relative, f"{folder}/archiv")
    if output and share_path(output).is_dir():
        move(output, output_archive(output), f"{Path(found[1]).stem}.{outbox}")


def _collect_reports(folder: str, jobs: dict[str, dict], ctx: dict, test_ids: frozenset[str]) -> None:
    for name, _ in sorted(scan(f"{folder}/fertig").values()):
        if not name.casefold().endswith(".json") or Path(name).stem.casefold() in test_ids:
            continue
        relative, archived = f"{folder}/fertig/{name}", f"{Path(name).stem}.report.json"
        try:
            report = json.loads(share_path(relative).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            issue(ctx, "note", "Jobreport unlesbar (wird erneut versucht)", relative, f"{relative}: {exc}")
            continue
        problem = report_problem(report)
        if problem:
            issue(ctx, "note", "Jobreport ungültig (wird erneut versucht)", relative, f"{relative}: {problem}")
            continue
        clip = jobs.get(report["job_id"])
        if clip is None or clip["job"]["folder"] != folder:
            issue(ctx, "note", "Veralteter Jobreport (ignoriert und archiviert)", relative, relative)
            move(relative, f"{folder}/archiv", archived)
            _retire(folder, report["job_id"], ctx)
            continue
        job = jobs.pop(report["job_id"])["job"]
        worker = archive_job(job) or job.get("worker")
        outcome, result, output = _apply_report(clip, job, report, worker, ctx)
        move(relative, f"{folder}/archiv", archived)
        failed = outcome == "failed"
        record_job({"at": now(), "stage": job["stage"], "job_id": job["id"], "clip_id": clip["clip_id"],
                    "identifier": clip["identifier"], "title": clip["title"], "collection": clip["collection"],
                    "status": outcome, "result": result, "preset": report.get("preset"), "worker": worker,
                    "attempt": clip["attempts"] if failed else None, "max_attempts": cfg["max_job_attempts"] if failed else None,
                    "final": failed and clip["attempts"] >= cfg["max_job_attempts"], "output": output})


def _locate_job(clip: dict, ctx: dict) -> None:
    job = clip["job"]
    folder, name = job["folder"], job["file"]
    if name.casefold() in listing(ctx, f"{folder}/offen"):
        if job["state"] == "laufend":
            add_event(clip, "Job wieder offen", f"von {job.get('worker') or 'unbekannt'} zurückgegeben")
        job.update(state="offen", worker=None, running_since=None, missing_since=None)
        return
    worker = running(ctx, folder).get(name.casefold(), (None,))[0]
    if worker:
        taken = job.get("worker") != worker
        job.update(state="laufend", worker=worker, missing_since=None)
        if taken:
            job["running_since"] = now()
            add_event(clip, "Job übernommen", worker)
        return
    if share_path(f"{folder}/fertig/{job['id']}.json").exists():
        return  # Report arrived during this run; it is collected next time.
    if not job.get("missing_since"):
        job.update(state="fehlt", missing_since=now())
        issue(ctx, "note", "Job-Datei nicht auffindbar (wird beobachtet)", clip["clip_id"], f"{clip_text(clip)}: {folder}/…/{name}")
    elif age(job["missing_since"]) >= missing_job_grace:
        issue(ctx, "note", "Job-Datei verschwunden – Job neu erstellt", clip["clip_id"], f"{clip_text(clip)}: {folder}/…/{name}")
        clip["job"] = None
        rmdir(job["output_folder"])
        add_event(clip, "Job-Datei verschwunden", name)


def _sweep_unknown_jobs(folder: str, known: set[str], ctx: dict) -> None:
    for key, (name, _) in listing(ctx, f"{folder}/offen").items():
        if not key.endswith(".json") or key in known:
            continue
        relative = f"{folder}/offen/{name}"
        output = job_output(relative, Path(name).stem)
        if delete_job_file(relative):
            if output:
                rmdir(output)
            issue(ctx, "note", "Unbekannte Job-Datei gelöscht", f"{folder}/{key}", relative)
    for key, (worker, name) in running(ctx, folder).items():
        if key.endswith(".json") and key not in known:
            issue(ctx, "note", "Unbekannter laufender Job (Ergebnis wird ignoriert)", f"{folder}/{key}",
                   f"{folder}/laufend/{worker}/{name}")


def withdraw(clip: dict) -> bool:
    """Delete a job that no worker has taken; False if it is running, was just taken or cannot be deleted yet."""
    job = clip["job"]
    if job is None:
        return True
    if job["state"] == "laufend":
        return False
    if job["state"] == "offen" and not delete_job_file(f"{job['folder']}/offen/{job['file']}"):
        return False
    rmdir(job["output_folder"])
    clip["job"] = None
    add_event(clip, "Job zurückgezogen", job["file"])
    return True


def _stage_fields(clip: dict, stage: str) -> dict:
    """Stage fields of a job; values are built lazily so that test jobs can replace fields the clip cannot provide."""
    master, proxy = clip["files"]["master"], clip["files"]["proxy"]
    if stage == "restore":
        return {"hashes": lambda: clip["filehashes"], "files": lambda: clip["master_files"]}
    if stage == "transcode":
        return {ffe_flag: lambda: clip[ffe_flag], "ffe_reference_clips": reference_clips, "proxy_name": lambda: proxy_name(clip),
                "inputs": lambda: [join(master["folder"], name) for name in master["names"]]}
    return {ffe_flag: lambda: clip[ffe_flag], "ffe_reference_image": reference_image,
            "input": lambda: f"{proxy['folder']}/{proxy['name']}"}


def job_payload(clip: dict, stage: str, job_id: str, report_folder: str, output_folder: str,
                overrides: dict | None = None) -> dict:
    """Job file content (schema_version 5); overrides replace or add fields (test jobs only)."""
    overrides = overrides or {}
    payload = {"schema_version": 5, "job_id": job_id, "stage": stage_labels[stage], "clip_id": clip["clip_id"],
               "collection": clip["collection"], "identifier": clip["identifier"], "title": clip["title"],
               "clip_name": clip["clip_name_with_extension"], "created_at": now(),
               "report_folder": report_folder, "output_folder": output_folder}
    payload.update({key: value() for key, value in _stage_fields(clip, stage).items() if key not in overrides})
    payload.update(overrides)
    return payload


def _create_job(clip: dict) -> None:
    stage = clip["stage"]
    folder = job_folder(stage)
    clip["job_count"] += 1
    job_id = f"{stamp()}__{clip['clip_id']}__{stage_labels[stage].casefold()}{clip['job_count']}"
    payload = job_payload(clip, stage, job_id, f"{folder}/fertig", f"{stage_folder(clip['collection'], stage)}/{outbox}/{job_id}")
    share_path(payload["output_folder"]).mkdir(parents=True, exist_ok=True)
    write_text_atomic(share_path(f"{folder}/offen/{job_id}.json"), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    clip["job"] = {"id": job_id, "stage": stage, "folder": folder, "file": f"{job_id}.json",
                   "output_folder": payload["output_folder"], "state": "offen", "worker": None,
                   "created_at": payload["created_at"], "running_since": None, "missing_since": None}
    add_event(clip, f"{stage_labels[stage]}-Job erstellt", job_id)


def _schedule(state: dict, prio: dict[str, list[str]], ctx: dict) -> None:
    clips = state["clips"].values()
    for clip in clips:
        job = clip["job"]
        if job and (not clip["active"] or job["stage"] != clip["stage"]):
            withdraw(clip)
    for stage in stages:
        ranks = {name: rank for rank, name in enumerate(prio[stage])}
        waiting = sorted((clip for clip in clips if clip["active"] and not clip["ready"] and clip["stage"] == stage and
                          clip["job"] is None),
                         key=lambda clip: (ranks.get(clip["collection"], len(ranks)), clip["queued_at"]))
        pending = sum(1 for clip in clips if clip["job"] and clip["job"]["stage"] == stage and clip["job"]["state"] == "offen")
        free = max(0, cfg[limit_keys[stage]] - pending)
        for clip in waiting[:free]:
            _create_job(clip)


def process(state: dict, mapping: list[dict], prio: dict[str, list[str]], ctx: dict, writing: bool,
            test_ids: frozenset[str] = frozenset()) -> None:
    """Evaluate all clips; writing=False only reads the share (reports). Test jobs (casefolded test_ids) stay untouched."""
    clips = state["clips"]
    read_workers(state)
    if writing:
        ensure_folders(mapping)
        sync_references(ctx)
        jobs = {clip["job"]["id"]: clip for clip in clips.values() if clip["job"]}
        folders = [job_folder(stage) for stage in stages]
        for folder in folders:
            _collect_reports(folder, jobs, ctx, test_ids)
        write_fields(state)
        ctx["listings"].clear()  # Reports moved files around.
        for clip in clips.values():
            if clip["job"]:
                _locate_job(clip, ctx)
        known = {clip["job"]["file"].casefold() for clip in clips.values() if clip["job"]} | {f"{job_id}.json" for job_id in test_ids}
        for folder in folders:
            _sweep_unknown_jobs(folder, known, ctx)
    for clip in clips.values():
        set_issue(clip, "file", *check_files(clip, ctx))
        update_activity(clip, ctx)
    if writing:
        _schedule(state, prio, ctx)
    for clip in clips.values():
        clip["status"] = status(clip)
