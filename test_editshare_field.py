"""One-off test: set the EditShare proxy path field for one clip via the same code path as Marathon."""
# --------- IMPORTS ---------
import sys

from core.config import load_config, state_path
from core.constants import editshare_field
from core.state import load_state
from core.editshare import _asset, _connect, _write  # Same functions Marathon uses in the job cycle.


# --------- CONFIG ---------
app_name = "Marathon EditShare-Feldtest"
app_version = "0.1"
test_value = r"\\10.0.77.11\Ablage KI Proxy_1\Proxy 10 Mbit\DEFA\MARATHON_TEST_10Mbit.mp4"


# --------- FUNC ---------
def _pick_clip(api, key: str, clips: dict) -> dict | None:
    """First clip of the JSON (lowest clip_id) whose field is still empty; never overwrites a value."""
    for clip in sorted(clips.values(), key=lambda item: int(item["clip_id"])):
        if not (_asset(api, clip["clip_id"]).get("custom") or {}).get(key):
            return clip
    return None


# --------- MAIN ---------
def main() -> None:
    print(f"{app_name} {app_version}")
    problem = load_config()
    if problem:
        raise RuntimeError(problem)
    if not state_path.exists():
        raise FileNotFoundError(f"JSON fehlt: {state_path}")
    clips = load_state()["clips"]
    if not clips:
        raise RuntimeError("Keine Clips in der JSON")
    api, key = _connect()
    print(f"Feld {editshare_field!r} gefunden (db_key {key})")
    clip = _pick_clip(api, key, clips)
    if clip is None:
        raise RuntimeError("Bei keinem Clip der JSON ist das Feld leer; nichts geschrieben")
    print(f"clip_id:        {clip['clip_id']}")
    print(f"001 Identifier: {clip['identifier']}")
    print(f"Titel:          {clip['title']}")
    _write(api, key, clip["clip_id"], test_value)
    print(f"OK: {editshare_field} = {test_value} (zurückgelesen und bestätigt)")


# --------- EXEC ---------
if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # FLOW raises its own error types; show every failure plainly.
        print(f"FEHLER: {exc}")
        sys.exit(1)
