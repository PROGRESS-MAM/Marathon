"""retry-restore, retry-transcode, retry-qc: reactivate all clips of a stage that a sticky reason made inactive.

The clips stay in their stage and keep their queue time; the job loop lays out their jobs like any other, following
the priority list and [limits]. Reasons Marathon checks itself in every cycle (files, Veritone-ID) are not touched.
"""
# --------- IMPORTS ---------
from collections import Counter

from .constants import stage_labels
from .config import state_path
from .console import log
from .util import context
from .state import add_event, load_state, save_state, set_issue
from .audit import status, update_activity


# --------- FUNC ---------
def _load() -> dict:
    if not state_path.exists():
        raise RuntimeError("Noch keine JSON – zuerst 'update-index' oder 'run'.")
    state = load_state()
    if state.get("cleanup", {}).get("pending"):
        raise RuntimeError("Bereinigung noch unvollständig; zuerst 'delete-folder' erneut ausführen.")
    return state


def _release(clip: dict, label: str) -> None:
    sticky = clip["issues"]["sticky"]
    set_issue(clip, "sticky")
    clip["attempts"] = 0
    add_event(clip, f"Für {label} wieder freigegeben", f"bisher {sticky['category']}: {sticky['detail']}")
    update_activity(clip, context())  # Own context: "Wieder aktiv" notes do not belong into the report.
    clip["status"] = status(clip)


# --------- COMMAND ---------
def retry(stage: str) -> None:
    """Clear the sticky reason and the attempts of all clips in stage without a job; no preview, no confirmation."""
    state, label = _load(), stage_labels[stage]
    blocked = [clip for clip in state["clips"].values() if clip["stage"] == stage and clip["issues"]["sticky"]]
    picked = [clip for clip in blocked if not clip["job"]]
    for clip in picked:
        _release(clip, label)
    if picked:
        save_state(state)
    per_collection = Counter(clip["collection"] for clip in picked)
    busy = len(blocked) - len(picked)
    log(f"retry-{stage}: {len(picked)} Clips für {label} wieder freigegeben" +
        (f", {busy} mit laufendem Job übersprungen" if busy else "") +
        "".join(f"\n  {name}: {count}" for name, count in sorted(per_collection.items(), key=lambda item: item[0].casefold())))
