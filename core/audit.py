"""File checks per clip, activity and status, final folder audit, leftovers and worker report checks."""
# --------- IMPORTS ---------
from collections import defaultdict

from .constants import (
    lost_master, lost_proxy, outbox, protocol_suffixes, report_statuses, stages, status_codes, veritone_missing)
from .config import ignored
from .util import clip_text, format_detail, issue, now
from .layout import final_folder, master_folder, master_root, qc_inbox, stage_folder
from .share import dirs, has_file, listing
from .state import add_event, position
from .naming import proxy_ids, proxy_text


# --------- FUNC ---------
def missing_masters(ctx: dict, collection: str, clip_id: str, names: list[str]) -> list[str] | None:
    """Master names missing in the clip's transcode inbox; None if that folder does not exist."""
    if not names or clip_id not in dirs(ctx, master_root(collection)):
        return None
    return [name for name in names if not has_file(ctx, master_folder(collection, clip_id), name)]


def report_problem(report: object) -> str | None:
    """Reason why a worker report is invalid; None if it is valid."""
    if not isinstance(report, dict) or not isinstance(report.get("job_id"), str) or not report["job_id"]:
        return "job_id fehlt"
    if report.get("status") not in report_statuses:
        return f"unbekannter status {report.get('status')!r}"
    result = report.get("result", "")
    if not isinstance(result, str) or (report["status"] != "ok" and not result.strip()):
        return "result fehlt (Pflicht, wenn status nicht ok ist)"
    if not isinstance(report.get("preset"), (str, type(None))):
        return "preset ist kein Text"
    return None


def check_files(clip: dict, ctx: dict) -> tuple[str, str] | tuple[()]:
    """Check the files a clip needs now; returns (category, detail) of a problem, otherwise ()."""
    job, files = clip["job"], clip["files"]
    if clip["ready"] or clip["stage"] == "qc":
        proxy = files["proxy"]
        if has_file(ctx, proxy["folder"], proxy["name"]):
            proxy["last_seen_at"] = now()
            return ()
        return lost_proxy, f"Datei {proxy['folder']}/{proxy['name']} (Quelle {proxy['source']}), zuletzt gesehen {proxy['last_seen_at']}"
    if clip["stage"] == "transcode" and not (job and job["state"] == "laufend"):
        if not clip.get("veritone_id"):
            return veritone_missing, "Kein Proxy-Name möglich; update-index ergänzt die Veritone-ID, sobald Veritone sie eindeutig liefert"
        master = files["master"]
        missing = [name for name in master["names"] if not has_file(ctx, master["folder"], name)]
        if not missing:
            master["last_seen_at"] = now()
            return ()
        return lost_master, (f"Ordner {master['folder']}, fehlend: {', '.join(missing)}, "
                             f"zuletzt vollständig gesehen {master['last_seen_at']}")
    return ()


def update_activity(clip: dict, ctx: dict) -> None:
    """Set a clip active or inactive by its issues; inactive reasons go into the run context."""
    reasons = [reason for reason in (clip["issues"][kind] for kind in ("sticky", "file")) if reason]
    active = not reasons
    if active != clip["active"]:
        if active:
            add_event(clip, "Wieder aktiv")
            issue(ctx, "note", "Wieder aktiv", clip["clip_id"], clip_text(clip))
        else:
            add_event(clip, "Inaktiv", "; ".join(reason["category"] for reason in reasons))
        clip["active"] = active
    last = next((item for item in reversed(clip["history"]) if item["event"] != "Inaktiv"), None)
    last_text = f"; letztes Ereignis: {last['at']} {last['event']} ({last['position']})" if last else ""
    for reason in reasons:
        issue(ctx, "inactive", reason["category"], clip["clip_id"],
               format_detail(f"{clip_text(clip)}; letzter Stand: {position(clip)}; {reason['detail']}; seit {reason['since']}{last_text}",
                       matches=reason["matches"]))


def status(clip: dict) -> str:
    """Status code of a clip for the JSON."""
    for kind in ("sticky", "file"):
        if clip["issues"][kind]:
            return status_codes.get(clip["issues"][kind]["category"], "inaktiv")
    if clip["ready"]:
        return "bereit"
    return "laufend" if clip["job"] and clip["job"]["state"] == "laufend" else "wartet"


def final_audit(state: dict, mapping: list[dict], ctx: dict) -> None:
    """Count unexpected and unknown final files without changing files or JSON status."""
    clips, by_name = state["clips"], defaultdict(dict)
    for clip_id, clip in clips.items():
        if clip["files"]["proxy"]:
            by_name[clip["files"]["proxy"]["name"].casefold()][clip_id] = clip
    finals = {final_folder(entry["name"]) for entry in mapping} | {final_folder(c["collection"]) for c in clips.values()}
    counts, matched = {}, defaultdict(list)
    for final in sorted(finals, key=str.casefold):
        counts[final] = {"unknown": 0, "unexpected": 0}
        for name, size in sorted(listing(ctx, final).values()):
            if ignored(name) or name.casefold().endswith(protocol_suffixes):
                continue
            candidates, ids = dict(by_name.get(name.casefold(), {})), proxy_ids(name)
            if ids and ids[1] in clips and clips[ids[1]].get("veritone_id") == ids[0]:
                candidates[ids[1]] = clips[ids[1]]
            relative = f"{final}/{name}"
            if len(candidates) != 1:
                counts[final]["unknown"] += 1
                matches = [clip_text(candidates[clip_id]) for clip_id in sorted(candidates, key=int)]
                issue(ctx, "final", "Unbekannte finale Clip-Datei", relative,
                       format_detail(f"Fundort={relative}{proxy_text(name)}", "Kein JSON-Eintrag zuordenbar", matches))
                continue
            clip_id, clip = next(iter(candidates.items()))
            matched[clip_id].append((final, name, size, clip))
    for files in matched.values():
        for final, name, size, clip in files:
            proxy = clip["files"]["proxy"]
            expected = f"{proxy['folder']}/{proxy['name']}" if proxy else "Kein Proxy im JSON vermerkt"
            actual = f"{final}/{name}"
            reasons = []
            if clip["status"] != "bereit" or not clip["ready"] or clip["stage"] is not None or not clip["active"]:
                reasons.append(f"JSON: Status={clip['status']}, Stufe={clip['stage']}, aktiv={clip['active']}")
            if final_folder(clip["collection"]).casefold() != final.casefold():
                reasons.append(f"Falscher Ablageordner; final erwartet={final_folder(clip['collection'])}")
            if not proxy or expected.casefold() != actual.casefold():
                reasons.append(f"JSON-Fundort abweichend; erwartet={expected}")
            if len(files) > 1:
                reasons.append("Mehrere finale Dateien für diesen Clip")
            if not size:
                reasons.append("Datei ist leer")
            if reasons:
                counts[final]["unexpected"] += 1
                issue(ctx, "final", "Unerwartete finale Clip-Datei", actual,
                       format_detail(f"Fundort={actual}; {clip_text(clip)}; " + "; ".join(reasons),
                               matches=[f"{f}/{n}" for f, n, _, _ in files] if len(files) > 1 else None))
    ctx["final_counts"] = counts


def final_lines(ctx: dict) -> list[str]:
    """Report table of unknown and unexpected files per final folder."""
    counts = ctx["final_counts"]
    unknown = sum(row["unknown"] for row in counts.values())
    unexpected = sum(row["unexpected"] for row in counts.values())
    return ["Finale Ablage (Dateianzahl, gemeinsamer DEFA-Ordner nur einmal):",
            "Ablageordner | Unbekannt | Unerwartet", *[
                f"{folder} | {row['unknown']} | {row['unexpected']}" for folder, row in counts.items()],
            f"Summe | {unknown} | {unexpected}"]


def leftovers(state: dict, mapping: list[dict], ctx: dict) -> None:
    """Add notes for outputs and master folders without a current job or clip."""
    clips = state["clips"].values()
    proxies = {(clip["files"]["proxy"]["folder"], clip["files"]["proxy"]["name"].casefold())
               for clip in clips if clip["files"]["proxy"]}
    masters = {clip["files"]["master"]["folder"] for clip in clips
               if clip["files"]["master"] and not clip["files"]["master"].get("deleted_at")}
    jobs = {clip["job"]["id"] for clip in clips if clip["job"]}
    for entry in mapping:
        for stage in stages:
            outputs = f"{stage_folder(entry['name'], stage)}/{outbox}"
            for job_id in sorted(dirs(ctx, outputs) - jobs):
                issue(ctx, "note", "Ausgang ohne aktuellen Job", f"{outputs}/{job_id}", f"{outputs}/{job_id}")
        root = master_root(entry["name"])
        for clip_id in sorted(dirs(ctx, root)):
            if f"{root}/{clip_id}" not in masters:
                issue(ctx, "note", "Master-Ordner ohne passenden Clip (Transcode-Eingang)", f"{root}/{clip_id}", f"{root}/{clip_id}")
        folder = qc_inbox(entry["name"])
        for key, (name, _) in sorted(listing(ctx, folder).items()):
            if (folder, key) not in proxies and not ignored(name):
                issue(ctx, "note", "Datei ohne passenden Clip (QC-Eingang)", f"{folder}/{key}", f"{folder}/{name}{proxy_text(name)}")
