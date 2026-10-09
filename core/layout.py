"""Folder layout on the share, collection mapping and the single-instance lock."""
# --------- IMPORTS ---------
import json
import os
import unicodedata
from collections import defaultdict
from pathlib import Path

from .constants import inbox, invalid_path_chars, reserved_names, summary_name
from .config import cfg, error_dir, lock_path, log_dir, reports_dir, res_dir, state_dir, state_path, test_dir


# --------- INIT ---------
lock_handle = None


# --------- FUNC ---------
def res(key: str) -> Path:
    """Path of the res file configured under key."""
    return res_dir / cfg[key]


def prepare() -> None:
    """Create the local project folders; raises if state holds another JSON file."""
    for folder in (res_dir, log_dir, state_dir, reports_dir, error_dir, test_dir):
        folder.mkdir(parents=True, exist_ok=True)
    if any(path != state_path for path in state_dir.glob("*.json")):
        raise RuntimeError("Weitere JSON-Datei in state gefunden; bitte Quelle des Zustands klären.")


def acquire_lock() -> None:
    """Lock state/marathon.lock for the whole run; raises if Marathon is already running."""
    global lock_handle
    handle = lock_path.open("a+")
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise RuntimeError(f"Marathon läuft bereits (Sperre {lock_path}); zweiter Start abgebrochen.") from exc
    lock_handle = handle  # The OS releases the lock when the process ends, also after a crash.


def _folder_key(name: str) -> str:
    key = "".join("_" if char in invalid_path_chars else char for char in unicodedata.normalize("NFC", name))
    key = key.strip().rstrip(". ")
    if not key or key.startswith(".") or key.split(".")[0].upper() in reserved_names:
        raise ValueError(f"Aus dem Kollektionsnamen {name!r} lässt sich kein Ordnername bilden.")
    return key


def _is_defa(collection: str) -> bool:
    return cfg["defa_marker"].casefold() in collection.casefold()


def final_folder(collection: str) -> str:
    """Final delivery folder of a collection, relative to root_path."""
    return cfg["defa_dir"] if _is_defa(collection) else _folder_key(collection)


def _work_folder(collection: str) -> str:
    base = f"{final_folder(collection)}/{cfg['work_dir']}"
    return f"{base}/{_folder_key(collection)}" if _is_defa(collection) else base


def stage_folder(collection: str, stage: str) -> str:
    """Stage folder of a collection inside its work folder."""
    return f"{_work_folder(collection)}/{stage}"


def job_folder(stage: str) -> str:
    """Central job pool folder of a stage."""
    return f"{cfg['work_dir']}/{stage}"


def master_root(collection: str) -> str:
    """Transcode inbox of a collection; holds one master folder per clip."""
    return f"{stage_folder(collection, 'transcode')}/{inbox}"


def master_folder(collection: str, clip_id: str) -> str:
    """Master folder of a clip in the transcode inbox."""
    return f"{master_root(collection)}/{clip_id}"


def qc_inbox(collection: str) -> str:
    """QC inbox of a collection."""
    return f"{stage_folder(collection, 'qc')}/{inbox}"


def share_path(relative: str) -> Path:
    """Share path of a folder relative to root_path; absolute paths (ingested masters) stay as they are."""
    return Path(relative) if Path(relative).is_absolute() else Path(cfg["root_path"]).joinpath(*relative.split("/"))


def join(folder: str, name: str) -> str:
    """Join folder and name; absolute folders as local path, share folders with "/"."""
    return str(Path(folder) / name) if Path(folder).is_absolute() else f"{folder}/{name}"


def _filter_ids(value) -> list[str] | None:
    """Veritone filter IDs as unique decimal strings, or None if the list is missing or invalid."""
    if not isinstance(value, list) or not value:
        return None
    texts = [str(item) if type(item) is int else item.strip() if isinstance(item, str) else "" for item in value]
    if not all(text.isascii() and text.isdecimal() and int(text) > 0 for text in texts):
        return None
    return list(dict.fromkeys(str(int(text)) for text in texts))


def load_mapping() -> list[dict]:
    """Load and check the collection mapping; raises ValueError on invalid content."""
    with res("mapping_file").open(encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("Unbekanntes Format im Kollektionsmapping.")
    entries = document.get("collections")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Im Kollektionsmapping fehlen Kollektionen.")
    seen, folders = set(), defaultdict(list)
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Jede Kollektion muss ein Objekt sein.")
        name, filters = (entry.get(key) for key in ("name", "filters"))
        if not isinstance(name, str) or not name.strip() or name.casefold() in seen:
            raise ValueError(f"Ungültiger oder doppelter Kollektionsname: {name!r}")
        if name.strip().casefold() == summary_name.casefold():
            raise ValueError(f"Der Kollektionsname {name!r} ist für die Summenzeile reserviert.")
        if not isinstance(filters, list) or not filters:
            raise ValueError(f"Suchbedingungen fehlen für {name!r}.")
        for item in filters:
            if not isinstance(item, dict) or any(not isinstance(item.get(key), str) or not item[key].strip()
                                                  for key in ("field", "value")):
                raise ValueError(f"Ungültige Suchbedingung für {name!r}.")
        filter_ids = _filter_ids(entry.get("veritone_filter_ids"))
        if not filter_ids:
            raise ValueError(f"veritone_filter_ids fehlen oder ungültig für {name!r} (Liste von Veritone-Filter-IDs, "
                             f"z. B. [10196, 14794]).")
        entry["veritone_filter_ids"] = filter_ids
        seen.add(name.casefold())
        folders[_work_folder(name).casefold()].append(name)
    work_key = cfg["work_dir"].rstrip(". ").casefold()
    if work_key in {final_folder(entry["name"]).rstrip(". ").casefold() for entry in entries}:
        raise ValueError("Arbeitsordner und finaler Ablageordner dürfen nicht denselben Namen haben.")
    clashes = [" / ".join(names) for names in folders.values() if len(names) > 1]
    if clashes:
        raise ValueError(f"Kollektionen ergeben denselben Arbeitsordner: {'; '.join(clashes)}")
    return entries


def check_root() -> None:
    """Raise FileNotFoundError if root_path is not reachable."""
    if not Path(cfg["root_path"]).is_dir():
        raise FileNotFoundError(f"Netzlaufwerk nicht erreichbar: {cfg['root_path']}; Zustand unverändert.")
