"""Final check and release of ready proxies to the FTP worker."""
# --------- IMPORTS ---------
from datetime import datetime
from pathlib import Path
from time import perf_counter

from .config import cfg, error_dir, state_path
from .console import log
from .constants import ftp_sections
from .ftpcheck import final_check
from .layout import check_root, final_folder, join, load_mapping, share_path
from .naming import ftp_name, proxy_name
from .share import scan
from .state import add_event, ftp_record, load_state, save_state
from .util import clip_text, context, details, file_stamp, format_errors, issue, now, write_new


# --------- COMMAND ---------
def send_to_ftp() -> None:
    """Final check of ready clips; passed clips are released for the FTP worker (the job loop creates the jobs)."""
    started, ftp_dir = perf_counter(), cfg["ftp_dir"]
    log(f"send-to-ftp gestartet: {ftp_dir}")
    if not state_path.exists():
        raise RuntimeError("Noch keine JSON – zuerst 'update-index' oder 'run'.")
    if not Path(ftp_dir).is_absolute():
        raise ValueError(f"[ftp] ftp_dir muss ein vollständiger Pfad sein: {ftp_dir}; Zustand unverändert.")
    check_root()
    if not Path(ftp_dir).is_dir():
        raise FileNotFoundError(f"FTP-Pfad nicht erreichbar: {ftp_dir}; Zustand unverändert.")

    state = load_state()
    if state.get("cleanup", {}).get("pending"):
        raise RuntimeError("Bereinigung noch unvollständig; zuerst 'delete-folder' erneut ausführen.")

    clips = list(state["clips"].values())

    def ftp_state(clip: dict) -> dict:
        return clip.get("ftp") or {}

    ready_clips = [clip for clip in clips if clip["ready"] and clip["active"]]
    candidates = sorted((clip for clip in ready_clips if clip.get("files", {}).get("proxy") and
                         not ftp_state(clip).get("copied_at") and not ftp_state(clip).get("job") and
                         not ftp_state(clip).get("requested_at")), key=lambda clip: int(clip["clip_id"]))
    skipped = sum(1 for clip in ready_clips if not ftp_state(clip).get("copied_at") and
                  (ftp_state(clip).get("requested_at") or ftp_state(clip).get("job")))
    if not candidates:
        log("send-to-ftp: keine bereiten Clips freizugeben.")
        return

    results = final_check(candidates, load_mapping())
    ctx, released, failed = context(), 0, 0
    try:
        for clip in candidates:
            proxy = clip["files"]["proxy"]
            final = final_folder(clip["collection"])
            source = share_path(join(final, proxy["name"]))
            result = results[clip["clip_id"]]
            failure: tuple[str, str] | None = None

            if result is not None:
                failure = ("Letzte Prüfung nicht bestanden", result)
            elif proxy["folder"].casefold() != final.casefold() or not source.is_file() or source.stat().st_size == 0:
                reason = "Proxy im Zielordner fehlt oder ist leer"
                failure = (reason, reason)
            else:
                expected_name = proxy_name(clip)
                if expected_name is None or proxy["name"].casefold() != expected_name.casefold():
                    failure = ("Proxy-Name weicht von proxy_name ab",
                               f"Ist {proxy['name']!r}, erwartet {expected_name!r}")
                else:
                    new_name = ftp_name(clip)
                    if new_name is None:
                        reason = "Kein Dateiname aus Identifier/Titel möglich"
                        failure = (reason, reason)
                    else:
                        existing = scan(final).get(new_name.casefold())
                        if existing is not None and existing[0].casefold() != proxy["name"].casefold():
                            failure = ("Namenskonflikt im Zielordner", f"Datei bereits vorhanden: {existing[0]}")

            if failure is not None:
                category, detail = failure
                issue(ctx, "ftp_error", category, clip["clip_id"], f"{clip_text(clip)}: {detail}")
                record = ftp_record(clip)
                record["error"] = {"category": category, "detail": detail, "at": now()}
                record["requested_at"] = None
                failed += 1
                continue

            record = ftp_record(clip)
            record["requested_at"], record["error"], record["attempts"] = now(), None, 0
            add_event(clip, "Für FTP freigegeben", new_name)
            released += 1
    finally:
        state["updated_at"] = now()
        save_state(state)

    when = datetime.now().astimezone()
    error_list = f"{file_stamp('send-to-ftp', when)}_errors.txt" if ctx["issues"] else None
    if error_list:
        write_new(error_dir / error_list, format_errors(ctx["issues"], when, "send-to-ftp-Fehlerliste", ftp_sections))
    log(f"send-to-ftp abgeschlossen: {len(candidates)} bereite Clips geprüft, {released} für den FTP-Worker freigegeben, "
        f"{failed} nicht freigegeben, {skipped} bereits freigegeben oder in Arbeit{details(error_list)}; "
        f"Dauer: {perf_counter() - started:.1f} s.")
