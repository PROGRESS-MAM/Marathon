"""EditShare custom field with the UNC path of the delivered proxy."""
# --------- IMPORTS ---------
from pathlib import PureWindowsPath

from toolbox import tb_link_api

from .constants import editshare_attempts, editshare_failed, editshare_field
from .config import cfg
from .util import clip_text, issue, normalize, now
from .layout import res
from .state import add_event


# --------- FUNC ---------
def request_field(clip: dict, folder: str, name: str) -> None:
    """Note that the EditShare field of a clip has to be set to the path of its proxy delivered to folder/name."""
    value = str(PureWindowsPath(cfg["root_path"], *folder.split("/"), name))
    clip["editshare"] = {"field": editshare_field, "value": value, "pending": True, "attempts": 0, "last_error": None,
                         "requested_at": now(), "written_at": None}


def _connect() -> tuple[object, str]:
    """Metadata API and db_key of the custom field."""
    api = tb_link_api(res("cred_file"), "metadata")
    if api is None:
        raise RuntimeError("Keine Verbindung zur EditShare-Metadaten-API")
    fields = api.getCustomMetadataFields()
    if api.last_return_code() != 200:
        raise RuntimeError(f"Custom-Felder nicht abrufbar (Code {api.last_return_code()})")
    keys = [item.get("db_key") for item in fields or () if normalize(str(item.get("name") or "")) == normalize(editshare_field)]
    if len(keys) != 1:
        raise RuntimeError(f"Custom-Feld {editshare_field!r} {'fehlt' if not keys else 'mehrfach vorhanden'} in EditShare")
    return api, keys[0]


def _asset(api, clip_id: str) -> dict:
    clips = api.getClipsByIDs([int(clip_id)])
    if api.last_return_code() != 200 or not clips or not isinstance(clips[0].get("asset"), dict):
        raise RuntimeError(f"Clip {clip_id} in EditShare nicht abrufbar (Code {api.last_return_code()})")
    return clips[0]["asset"]


def _write(api, key: str, clip_id: str, value: str) -> None:
    """Set the field unless it already holds the value, then read it back."""
    asset = _asset(api, clip_id)
    if (asset.get("custom") or {}).get(key) == value:
        return
    if not api.update_asset(asset["asset_id"], {"custom": {key: value}}):
        raise RuntimeError(f"Schreiben abgelehnt (Code {api.last_return_code()}): {api.last_response()}")
    if (_asset(api, clip_id).get("custom") or {}).get(key) != value:
        raise RuntimeError("Wert nach dem Schreiben nicht bestätigt")


def _failed(clip: dict, exc: Exception) -> None:
    task = clip["editshare"]
    task.update(attempts=task["attempts"] + 1, last_error=str(exc) or type(exc).__name__)
    if task["attempts"] == editshare_attempts:
        add_event(clip, editshare_failed, f"{task['attempts']} Job-Zyklen; {task['last_error']}; wird weiter versucht")


def write_fields(state: dict) -> None:
    """Set all pending EditShare fields; a failure stays pending for the next job cycle."""
    pending = [clip for clip in state["clips"].values() if clip.get("editshare") and clip["editshare"]["pending"] and clip["ready"] and clip["active"]]
    if not pending:
        return
    try:
        api, key = _connect()
    except Exception as exc:  # FLOW raises its own error types; every failure only delays the field.
        for clip in pending:
            _failed(clip, exc)
        return
    for clip in pending:
        task = clip["editshare"]
        try:
            _write(api, key, clip["clip_id"], task["value"])
        except Exception as exc:  # See above.
            _failed(clip, exc)
            continue
        task.update(pending=False, last_error=None, written_at=now())
        add_event(clip, "EditShare-Feld gesetzt", f"{task['field']} = {task['value']}")


def field_issue(clip: dict, ctx: dict) -> None:
    """Report an EditShare field that is still not set after editshare_attempts job cycles."""
    task = clip.get("editshare")
    if task and task["pending"] and task["attempts"] >= editshare_attempts:
        issue(ctx, "editshare", editshare_failed, clip["clip_id"],
               f"{clip_text(clip)}; {task['field']} = {task['value']}; {task['attempts']} gescheiterte Job-Zyklen; "
               f"letzter Fehler: {task['last_error']}")
