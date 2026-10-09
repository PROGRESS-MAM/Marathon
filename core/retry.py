"""retry-qc: release all clips rejected by QC for a new QC check, e.g. after the QC metric changed.

The clips stay in stage QC with their proxy in the QC inbox and keep their queue time; the job loop lays out the new
QC jobs like any other, following the priority list and [limits] qc.
"""
# --------- IMPORTS ---------
from collections import Counter
from datetime import datetime

from .constants import qc_rejected, retry_qc_sections
from .config import error_dir, state_path
from .console import log
from .util import clip_text, context, file_stamp, format_errors, issue, write_new
from .layout import check_root, qc_inbox
from .share import listing
from .state import add_event, load_state, save_state, set_issue
from .audit import status, update_activity


# --------- FUNC ---------
def _load() -> dict:
    check_root()
    if not state_path.exists():
        raise RuntimeError("Noch keine JSON – zuerst 'update-index' oder 'run'.")
    state = load_state()
    if state.get("cleanup", {}).get("pending"):
        raise RuntimeError("Bereinigung noch unvollständig; zuerst 'delete-folder' erneut ausführen.")
    return state


def _rejected(state: dict, ctx: dict, clip_ids: set[str] | None = None) -> list[dict]:
    """Clips with 'QC nicht bestanden' whose proxy lies non-empty in their QC inbox; all others become skip issues."""
    picked = []
    for clip in state["clips"].values():
        sticky = clip["issues"]["sticky"]
        if not sticky or sticky["category"] != qc_rejected or (clip_ids is not None and clip["clip_id"] not in clip_ids):
            continue
        proxy = clip["files"]["proxy"]
        in_inbox = proxy and proxy["folder"].casefold() == qc_inbox(clip["collection"]).casefold()
        found = listing(ctx, proxy["folder"]).get(proxy["name"].casefold()) if in_inbox else None
        if clip["stage"] == "qc" and not clip["job"] and found and found[1]:
            picked.append(clip)
            continue
        reason = ("nicht in der Stufe QC" if clip["stage"] != "qc" else "Job läuft noch" if clip["job"] else
                  "Proxy ist leer" if found else "Proxy fehlt im QC-Eingang")
        where = f"; Datei {proxy['folder']}/{proxy['name']}" if proxy else ""
        issue(ctx, "retry_qc_skipped", reason, clip["clip_id"], f"{clip_text(clip)}{where}")
    return picked


def begin_retry_qc() -> list[str] | None:
    """Log what retry-qc would release; returns the clip ids to confirm with 'freigeben', None if there is nothing to release."""
    state, ctx = _load(), context()
    picked = _rejected(state, ctx)
    text = f"retry-qc: {len(picked)} Clips mit „{qc_rejected}“ werden freigegeben, {len(ctx['issues'])} übersprungen"
    if ctx["issues"]:
        when = datetime.now().astimezone()
        name = f"{file_stamp('retry-qc', when)}_errors.txt"
        write_new(error_dir / name, format_errors(ctx["issues"], when, "retry-qc-Fehlerliste", retry_qc_sections))
        text += f"; Details: errors/{name}"
    if not picked:
        log(f"{text}. Nichts geändert.")
        return None
    per_collection = Counter(clip["collection"] for clip in picked)
    log(f"{text}:\n" + "\n".join(f"  {name}: {count}" for name, count in sorted(per_collection.items(), key=lambda item: item[0].casefold())) +
        "\nZum Bestätigen 'freigeben' eingeben, sonst 'abbrechen'.")
    return [clip["clip_id"] for clip in picked]


def retry_qc(clip_ids: list[str]) -> None:
    """Release the confirmed clips; clips that changed since the preview (no longer rejected, proxy gone) stay as they are."""
    state, ctx = _load(), context()
    picked = _rejected(state, ctx, set(clip_ids))
    for clip in picked:
        detail = clip["issues"]["sticky"]["detail"]
        set_issue(clip, "sticky")
        add_event(clip, "Zur QC-Neuprüfung freigegeben", f"bisher {qc_rejected}: {detail}")
        update_activity(clip, context())  # Own context: "Wieder aktiv" notes do not belong into the report.
        clip["status"] = status(clip)
    save_state(state)
    changed = len(clip_ids) - len(picked)
    log(f"retry-qc: {len(picked)} Clips freigegeben; die Job-Schleife legt die QC-Jobs nach Prioliste und [limits] qc aus." +
        (f" {changed} Clips seit der Vorschau geändert, nicht freigegeben." if changed else ""))
