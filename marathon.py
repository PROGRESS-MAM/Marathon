# --------- IMPORTS ---------
import argparse
import configparser
import json
import os
import queue
import shutil
import tempfile
import threading
import unicodedata
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from time import perf_counter

from toolbox import tb_write_log

# --------- STATIC ---------
field_names = {
    "clip_id": "clip_id",
    "identifier": "001 Identifier",
    "title": "014 Title Original",
    "clip_name": "clip_name_with_extension",
    "hash": "hash",
    "userpath": "userpath",
    "status_flags": "status_flags",
}
stages = ("restore", "transcode", "qc")  # Also the stage folder names.
stage_labels = {"restore": "LTO", "transcode": "Transcode", "qc": "QC"}
limit_keys = {stage: stage_labels[stage].casefold() for stage in stages}
job_boxes = ("offen", "laufend", "fertig", "archiv", "zurueckgezogen", "ausgang")
inbox, outbox, unknown_dir, worker_dir = "eingang", "ausgang", "unbekannt", "worker"
report_statuses = ("ok", "failed", "rejected")
system_files = frozenset({"thumbs.db", "desktop.ini", ".ds_store"})
busy_suffixes = (".tmp", ".part", ".partial")
protocol_suffixes = (".json", ".txt", ".log")
prio_columns = tuple(f"Prio {stage_labels[stage]}" for stage in stages)
queue_columns = tuple(f"Queue {stage_labels[stage]}" for stage in stages)
count_columns = ("Gesamt", "Bereit", *queue_columns)
columns = ("Kollektion", *prio_columns, "Gesamt", "Bereit", "%", *queue_columns)
summary_name = "Summe"
invalid_path_chars = frozenset('<>:"/\\|?*' + "".join(map(chr, range(32))))
reserved_names = frozenset({"CON", "PRN", "AUX", "NUL", *(f"{kind}{number}" for kind in ("COM", "LPT") for number in range(1, 10))})
issue_sections = {
    "skipped": "Gefunden, aber nicht aufgenommen (nicht in Gesamt)",
    "inactive": "In der JSON, aber nicht mehr aktiv (nicht in Gesamt)",
    "note": "Hinweise (betroffene Clips zählen weiter)",
}
problem_categories = {  # kind: (category for new clips, category for clips in the JSON, clip status)
    "missing": (None, "Verloren – nicht mehr in der Suche", "verloren"),
    "placeholder": (None, "Jetzt Platzhalter", "platzhalter"),
    "multi": ("Clip-ID in mehreren Kollektionen", "Clip-ID in mehreren Kollektionen (nach Aufnahme)", "duplikat"),
    "invalid": ("Unvollständige oder widersprüchliche Metadaten",
                "Unvollständige oder widersprüchliche Metadaten (nach Aufnahme)", "ungueltig"),
    "duplicate": ("Doppelter Identifier/Titel", "Doppelter Identifier/Titel (nach Aufnahme)", "duplikat"),
    "restore": ("Dateinamen und Hashes passen nicht zusammen",
                "Dateinamen und Hashes passen nicht zusammen (nach Aufnahme)", "ungueltig"),
}
lost_proxy, lost_master = "Verloren – Proxy fehlt", "Verloren – Master fehlt vor Transcode"
qc_rejected, job_failed = "QC nicht bestanden", "Job endgültig fehlgeschlagen"
status_codes = {existing: code for _, existing, code in problem_categories.values()} | {
    lost_proxy: "verloren", lost_master: "verloren", qc_rejected: "qc_abgelehnt", job_failed: "fehlgeschlagen"}
tracked_fields = {"collection": "Kollektion", "identifier": "Identifier", "title": "Titel",
                  "clip_name_with_extension": "Clipname", "master_files": "Master-Dateien", "filehashes": "Hashes"}

# --------- CONFIG ---------
app_name = "Marathon"
app_version = "1.0.0"
project_dir = Path(__file__).resolve().parent
res_dir = project_dir / "res"
log_dir = project_dir / "log"
state_dir = project_dir / "state"
reports_dir = project_dir / "reports"
error_dir = reports_dir / "errors"
config_path = res_dir / "config.ini"
state_path = state_dir / "marathon.json"
lock_path = state_dir / "marathon.lock"
main_log = log_dir / "marathon.log"
config_defaults = {  # section: {key: (default, comment)}; values live in res/config.ini
    "paths": {
        "root_path": (r"\\10.0.77.11\Ablage KI Proxy_1\Proxy 10 Mbit", "Netzlaufwerk mit allen Zielordnern"),
        "defa_dir": ("DEFA", "Zielordner aller DEFA-Kollektionen"),
        "aqc_dir": ("AQC", "Proxies der Kollegen unterhalb von defa_dir; gehen direkt an QC"),
        "work_dir": (".marathon", "Arbeitsordner von Marathon"),
        "defa_marker": ("defa", "Kollektionen mit diesem Text im Namen liefern nach defa_dir"),
        "proxy_prefix": ("(c)PROGRESS__10Mbit", "Proxy-Namensschema: <proxy_prefix>__<Identifier>__<Titel>.<Endung>"),
        "cred_file": ("cred.env", "Searcher-Zugang im res-Ordner"),
        "mapping_file": ("collections.json", "Kollektionsmapping im res-Ordner"),
        "priority_file": ("priority.txt", "Prioliste im res-Ordner"),
    },
    "operation": {
        "report_only": (True, "true = keine Jobs und keine Schreibzugriffe auf das Netzlaufwerk"),
        "auto_report_time": (time(9, 0), "Uhrzeit des täglichen Auto-Berichts (HH:MM, Uhr dieses Rechners)"),
        "retry_minutes": (60, "Wartezeit nach einem fehlgeschlagenen Auto-Bericht"),
    },
    "timing": {
        "cycle_seconds": (60, "Abstand der Job-Zyklen"),
        "max_job_attempts": (2, "Versuche je Job, danach dauerhaft fehlgeschlagen"),
        "missing_job_minutes": (30, "Karenz, bevor eine verschwundene Job-Datei neu erstellt wird"),
        "stable_minutes": (2, "Dateien in AQC und Zielordnern gelten erst nach so vielen Minuten ohne Größenänderung "
                              "als fertig kopiert (0 = sofort)"),
    },
    "limits": {
        "lto": (1, "Maximal offene LTO-Jobs über alle Kollektionen (0 = Stufe pausiert)"),
        "transcode": (8, "Maximal offene Transcode-Jobs über alle Kollektionen (0 = Stufe pausiert)"),
        "qc": (8, "Maximal offene QC-Jobs über alle Kollektionen (0 = Stufe pausiert)"),
    },
    "heartbeat": {
        "worker_timeout_minutes": (10, "Worker ohne Lebenszeichen gilt danach als ausgefallen"),
        "max_job_hours": (24, "Laufende Jobs, die länger brauchen, werden im Bericht gemeldet"),
    },
}
zero_allowed = frozenset({"stable_minutes", *limit_keys.values()})

# --------- INIT ---------
cfg: dict = {}
ensured_folders: set[str] = set()
lock_handle = None
progress_lock = threading.Lock()
progress_width = 0


# --------- FUNC: CONSOLE AND LOG ---------
def _finish_progress() -> None:
    global progress_width
    with progress_lock:
        if progress_width:
            print(flush=True)
            progress_width = 0


def _search_progress(message: str) -> None:
    global progress_width
    transient = message.startswith("Cached [") or "warte seit " in message or "lade " in message
    with progress_lock:
        if transient:
            print("\r" + message + " " * max(0, progress_width - len(message)), end="", flush=True)
            progress_width = len(message)
        else:
            if progress_width:
                print(flush=True)
                progress_width = 0
            print(message, flush=True)


def _log(message: str) -> None:
    _finish_progress()
    print(message, flush=True)
    tb_write_log(main_log, message)


# --------- FUNC: CONFIG ---------
def _format_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return value.strftime("%H:%M") if isinstance(value, time) else str(value)


def _write_config_template() -> None:
    lines = [f"# {app_name} – Konfiguration",
             "# Wird in jedem Zyklus neu gelesen; Änderungen in [paths] wirken erst nach einem Neustart.",
             "# Bei ungültigen Werten gelten die letzten gültigen weiter; der Bericht meldet das.", ""]
    for section, keys in config_defaults.items():
        lines.append(f"[{section}]")
        for key, (default, comment) in keys.items():
            lines += [f"# {comment}", f"{key} = {_format_value(default)}"]
        lines.append("")
    config_path.write_text("\n".join(lines), encoding="utf-8")


def _parse_value(raw: str, default):
    if isinstance(default, bool):
        if raw.casefold() not in ("true", "false", "ja", "nein", "1", "0"):
            raise ValueError("erwartet true oder false")
        return raw.casefold() in ("true", "ja", "1")
    if isinstance(default, int):
        if not raw.isdecimal():
            raise ValueError("erwartet eine ganze Zahl")
        return int(raw)
    if isinstance(default, time):
        try:
            return time.fromisoformat(raw)
        except ValueError:
            raise ValueError("erwartet HH:MM") from None
    return raw


def _read_config() -> dict:
    parser = configparser.ConfigParser(interpolation=None)
    with config_path.open(encoding="utf-8-sig") as handle:
        parser.read_file(handle)
    unknown = [f"[{section}] {key}" for section in parser.sections() for key in parser[section]
               if key not in config_defaults.get(section, {})]
    if unknown:
        raise ValueError(f"unbekannte Einträge: {', '.join(unknown)}")
    values = {}
    for section, keys in config_defaults.items():
        for key, (default, _) in keys.items():
            raw = parser.get(section, key, fallback="").strip()
            try:
                value = _parse_value(raw, default) if raw else default
            except ValueError as exc:
                raise ValueError(f"[{section}] {key} = {raw!r} ist ungültig ({exc})") from exc
            minimum = 0 if key in zero_allowed else 1
            if isinstance(value, int) and not isinstance(value, bool) and value < minimum:
                raise ValueError(f"[{section}] {key} muss mindestens {minimum} sein")
            values[key] = value
    for key in ("defa_dir", "aqc_dir", "work_dir"):
        if any(char in invalid_path_chars for char in values[key]):
            raise ValueError(f"[paths] {key} muss ein einfacher Ordnername sein")
    return values


def _load_config() -> list[str]:
    """Load res/config.ini into cfg; returns problems while the last valid values stay active."""
    if not cfg and not config_path.exists():
        _write_config_template()
    try:
        values = _read_config()
    except (OSError, UnicodeError, configparser.Error, ValueError) as exc:
        if not cfg:
            raise ValueError(f"{config_path.name} ungültig: {exc}") from exc
        return [f"{config_path.name} ungültig – letzte gültige Werte gelten: {exc}"]
    fixed = [key for key in config_defaults["paths"] if cfg and values[key] != cfg[key]]
    values.update({key: cfg[key] for key in fixed})
    cfg.update(values)
    return [f"Änderung in [paths] ({', '.join(fixed)}) wirkt erst nach einem Neustart."] if fixed else []


# --------- FUNC: SETUP ---------
def _res(key: str) -> Path:
    return res_dir / cfg[key]


def _prepare() -> None:
    for folder in (res_dir, log_dir, state_dir, reports_dir, error_dir):
        folder.mkdir(parents=True, exist_ok=True)
    created = not config_path.exists()
    for problem in _load_config():
        _log(problem)
    if created:
        _log(f"Konfiguration mit Standardwerten angelegt: {config_path}")
    if any(path != state_path for path in state_dir.glob("*.json")):
        raise RuntimeError("Weitere JSON-Datei in state gefunden; bitte Quelle des Zustands klären.")
    for key in ("mapping_file", "cred_file"):
        if not _res(key).is_file():
            raise FileNotFoundError(f"Datei fehlt: {_res(key)} (siehe [paths] {key} in {config_path.name}).")


def _acquire_lock() -> None:
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


def _final_folder(collection: str) -> str:
    return cfg["defa_dir"] if _is_defa(collection) else _folder_key(collection)


def _work_folder(collection: str) -> str:
    base = f"{_final_folder(collection)}/{cfg['work_dir']}"
    return f"{base}/{_folder_key(collection)}" if _is_defa(collection) else base


def _stage_folder(collection: str, stage: str) -> str:
    return f"{_work_folder(collection)}/{stage}"


def _master_root(collection: str) -> str:
    return f"{_stage_folder(collection, 'transcode')}/{inbox}"


def _master_folder(collection: str, clip_id: str) -> str:
    return f"{_master_root(collection)}/{clip_id}"


def _qc_inbox(collection: str) -> str:
    return f"{_stage_folder(collection, 'qc')}/{inbox}"


def _aqc_folder() -> str:
    return f"{cfg['defa_dir']}/{cfg['aqc_dir']}"


def _path(relative: str) -> Path:
    return Path(cfg["root_path"]).joinpath(*relative.split("/"))


def _load_mapping() -> list[dict]:
    with _res("mapping_file").open(encoding="utf-8") as handle:
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
        seen.add(name.casefold())
        folders[_work_folder(name).casefold()].append(name)
    clashes = [" / ".join(names) for names in folders.values() if len(names) > 1]
    if clashes:
        raise ValueError(f"Kollektionen ergeben denselben Arbeitsordner: {'; '.join(clashes)}")
    return entries


def _check_root() -> None:
    if not Path(cfg["root_path"]).is_dir():
        raise FileNotFoundError(f"Netzlaufwerk nicht erreichbar: {cfg['root_path']}; Zustand unverändert.")


# --------- FUNC: HELPERS ---------
def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _age(stamp: str) -> timedelta:
    return datetime.now().astimezone() - datetime.fromisoformat(stamp)


def _duration(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    return f"{minutes // 60} h {minutes % 60} min" if minutes >= 60 else f"{minutes} min"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().casefold()


def _values(value: str) -> list[str]:
    return [part.strip() for part in value.split("; ") if part.strip()]


def _ignored(name: str) -> bool:
    key = name.casefold()
    return key in system_files or name.startswith((".", "~$")) or key.endswith(busy_suffixes)


def _file_name(userpath: str) -> str:
    return userpath.replace("\\", "/").rsplit("/", 1)[-1].strip()


def _context() -> dict:
    return {"issues": [], "listings": {}, "indexes": {}, "touched": set()}


def _issue(ctx: dict, section: str, category: str, key: str, detail: str) -> None:
    ctx["issues"].append({"section": section, "category": category, "key": key, "detail": detail})


def _clip_text(clip: dict) -> str:
    return (f"Clip_ID={clip['clip_id']}, Kollektion={clip['collection']}, "
            f"Clipname={clip['clip_name_with_extension']}")


def _position(clip: dict) -> str:
    if clip["ready"]:
        return "Bereit"
    job = clip["job"]
    text = f"Queue {stage_labels[clip['stage']]}"
    if job:
        text += f", Job {job['state']}" + (f" bei {job['worker']}" if job.get("worker") else "")
    return text


def _event(clip: dict, event: str, detail: str = "") -> None:
    clip["history"].append({"at": _now(), "event": event, "position": _position(clip), "detail": detail})


def _set_issue(clip: dict, kind: str, category: str | None = None, detail: str = "") -> None:
    old = clip["issues"][kind]
    if category is None:
        clip["issues"][kind] = None
        return
    since = old["since"] if old and old["category"] == category else _now()
    clip["issues"][kind] = {"category": category, "detail": detail, "since": since}


def _file_entry(folder: str, name: str, source: str) -> dict:
    return {"folder": folder, "name": name, "source": source, "last_seen_at": _now()}


def _enter(clip: dict, stage: str) -> None:
    clip["stage"], clip["queued_at"] = stage, _stamp()
    _event(clip, f"Weiter an {stage_labels[stage]}")


# --------- FUNC: SHARE ACCESS ---------
def _scan(relative: str) -> dict[str, tuple[str, int]]:
    entries = {}
    try:
        with os.scandir(_path(relative)) as items:
            for item in items:
                try:
                    if item.is_file(follow_symlinks=False):
                        entries[item.name.casefold()] = (item.name, item.stat(follow_symlinks=False).st_size)
                except FileNotFoundError:
                    continue  # Files may arrive or disappear during the scan.
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise RuntimeError(f"Ordner nicht lesbar: {_path(relative)}; Zustand unverändert.") from exc
    return entries


def _subfolders(relative: str) -> list[str]:
    try:
        with os.scandir(_path(relative)) as items:
            return sorted(item.name for item in items if item.is_dir(follow_symlinks=False))
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise RuntimeError(f"Ordner nicht lesbar: {_path(relative)}; Zustand unverändert.") from exc


def _listing(ctx: dict, relative: str) -> dict[str, tuple[str, int]]:
    if relative not in ctx["listings"]:
        ctx["listings"][relative] = _scan(relative)
    return ctx["listings"][relative]


def _dirs(ctx: dict, relative: str) -> set[str]:
    key = ("dirs", relative)
    if key not in ctx["listings"]:
        ctx["listings"][key] = set(_subfolders(relative))
    return ctx["listings"][key]


def _has_file(ctx: dict, relative: str, name: str) -> bool:
    item = _listing(ctx, relative).get(name.casefold())
    return item is not None and item[1] > 0


def _running(ctx: dict, folder: str) -> dict[str, tuple[str, str]]:
    """Job files in laufend: casefolded name -> (worker, real name)."""
    key = ("running", folder)
    if key not in ctx["listings"]:
        ctx["listings"][key] = {name_key: (worker, name) for worker in _subfolders(f"{folder}/laufend")
                                for name_key, (name, _) in _scan(f"{folder}/laufend/{worker}").items()}
    return ctx["listings"][key]


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _move(relative: str, target_folder: str, name: str | None = None, replace: bool = False) -> bool:
    """Move a file or folder on the share; False if another process moved it first."""
    source = _path(relative)
    target = _path(target_folder) / (name or source.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not replace:
        target = target.with_name(f"{target.stem}.{_stamp()}{target.suffix}")
    try:
        (os.replace if replace else os.rename)(source, target)
    except FileNotFoundError:
        return False
    return True


def _remove_tree(relative: str, ctx: dict, category: str) -> None:
    try:
        shutil.rmtree(_path(relative))
    except FileNotFoundError:
        pass
    except OSError as exc:
        _issue(ctx, "note", category, relative, f"{relative}: {exc}")


def _rmdir(relative: str) -> None:
    try:
        _path(relative).rmdir()
    except OSError:
        pass  # Not empty or already gone.


def _stable(state: dict, ctx: dict, relative: str, size: int) -> bool:
    """True once a file kept its size for stable_minutes, measured with Marathon's own clock."""
    ctx["touched"].add(relative)
    entry = state["files_seen"].get(relative)
    if entry is None or entry["size"] != size:
        entry = state["files_seen"][relative] = {"size": size, "since": _now()}
    return _age(entry["since"]) >= timedelta(minutes=cfg["stable_minutes"])


def _ensure_folders(mapping: list[dict]) -> None:
    folders = [cfg["work_dir"], f"{cfg['work_dir']}/{worker_dir}"]
    for entry in mapping:
        for stage in stages:
            base = _stage_folder(entry["name"], stage)
            folders += [f"{base}/{box}" for box in job_boxes] + ([f"{base}/{inbox}"] if stage != "restore" else [])
    for relative in folders:
        if relative not in ensured_folders:
            _path(relative).mkdir(parents=True, exist_ok=True)
            ensured_folders.add(relative)


# --------- FUNC: PRIORITY ---------
def _write_priority_template(mapping: list[dict]) -> None:
    lines = ["# Marathon – Prioliste",
             "# Je Abschnitt eine Kollektion pro Zeile; oben = höchste Priorität.",
             "# Nicht aufgeführte Kollektionen folgen in der Reihenfolge von collections.json.",
             "# Verfügbare Kollektionen:", *(f"#   {entry['name']}" for entry in mapping), ""]
    for stage in stages:
        lines += [f"[{stage_labels[stage]}]", ""]
    _res("priority_file").write_text("\n".join(lines), encoding="utf-8")


def _read_priority(mapping: list[dict]) -> dict[str, list[str]]:
    names = {entry["name"].casefold(): entry["name"] for entry in mapping}
    sections = {stage_labels[stage].casefold(): stage for stage in stages}
    result, current = {stage: [] for stage in stages}, None
    for number, raw in enumerate(_res("priority_file").read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = sections.get(line[1:-1].strip().casefold())
            if current is None:
                allowed = ", ".join(f"[{label}]" for label in stage_labels.values())
                raise ValueError(f"Zeile {number}: unbekannter Abschnitt {line}; erlaubt: {allowed}.")
            continue
        name = names.get(line.casefold())
        if current is None or name is None or name in result[current]:
            reason = ("steht vor dem ersten Abschnitt" if current is None else
                      "ist keine Kollektion aus collections.json" if name is None else "steht doppelt im Abschnitt")
            raise ValueError(f"Zeile {number}: {line!r} {reason}.")
        result[current].append(name)
    return result


def _priority(mapping: list[dict], state: dict, ctx: dict) -> dict[str, list[str]]:
    if not _res("priority_file").exists():
        _write_priority_template(mapping)
        _log(f"Prioliste angelegt: {_res('priority_file')}")
    try:
        explicit = _read_priority(mapping)
        state["priority"] = explicit
    except (OSError, UnicodeError, ValueError) as exc:
        known = {entry["name"] for entry in mapping}
        stored = state.get("priority") or {}
        explicit = {stage: [name for name in stored.get(stage, []) if name in known] for stage in stages}
        _issue(ctx, "note", "Prioliste ungültig – letzte gültige Reihenfolge gilt", "priority", str(exc))
    order = [entry["name"] for entry in mapping]
    return {stage: [*explicit[stage], *(name for name in order if name not in explicit[stage])] for stage in stages}


def _write_priority_file(prio: dict[str, list[str]]) -> None:
    data = {"schema_version": 1, "stages": {
        stage_labels[stage]: [{"collection": name, **{box: f"{_stage_folder(name, stage)}/{box}"
                                                      for box in ("offen", "laufend", "fertig")}}
                              for name in prio[stage]] for stage in stages}}
    path, text = _path(f"{cfg['work_dir']}/priority.json"), json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    try:
        if path.read_text(encoding="utf-8") == text:
            return
    except (FileNotFoundError, UnicodeError):
        pass
    _write_text_atomic(path, text)


# --------- FUNC: SEARCH ---------
def _merge_hit(hit: dict) -> dict:
    rows = hit.pop("rows")
    if hit["placeholder"]:
        return hit
    fields = ("identifier", "title", "clip_name")
    problems = [f"{field_names[field]}: {len(row[field])} Werte" for row in rows for field in fields if len(row[field]) != 1]
    if problems:
        hit["invalid"] = "; ".join(dict.fromkeys(problems))
        return hit
    single = {field: {row[field][0] for row in rows} for field in fields}
    conflicts = [f"{field_names[field]}: {' / '.join(sorted(values))}" for field, values in single.items() if len(values) > 1]
    if conflicts:
        hit["invalid"] = "Widersprüchlich: " + "; ".join(conflicts)
        return hit
    names = {_file_name(path).casefold(): _file_name(path) for row in rows for path in row["userpath"] if _file_name(path)}
    hashes = {value.casefold(): value for row in rows for value in row["hash"]}
    masters, hash_list = (sorted(values.values(), key=str.casefold) for values in (names, hashes))
    hit.update({field: next(iter(single[field])) for field in fields}, hashes=hash_list, masters=masters,
               restore_problem=None if masters and len(masters) == len(hash_list) else
               f"{len(masters)} Dateinamen (userpath), {len(hash_list)} Hashes")
    return hit


def _search_clips(mapping: list[dict], ctx: dict) -> dict[str, list[dict]]:
    import searcher

    keys, api_fields = tuple(field_names), tuple(field_names.values())
    allowed_filters = {"006 Source PROGRESS", "007 Collection PROGRESS", "101a Genre German"}
    for entry in mapping:
        unknown = {item["field"] for item in entry["filters"]} - allowed_filters
        if unknown:
            raise ValueError(f"API-Suchfeld in {entry['name']!r} nicht geprüft: {', '.join(sorted(unknown))}.")
    _log(f"API-Verbindung herstellen: {len(mapping)} Kollektionen vorgesehen.")
    searcher.link("api", _res("cred_file"), on_progress=_search_progress)
    found = defaultdict(dict)
    invalid_category = problem_categories["invalid"][0]
    for entry in mapping:
        name, started = entry["name"], perf_counter()
        _log(f"API-Suche gestartet: {name!r}.")
        request = tuple(part for index, item in enumerate(entry["filters"])
                        for part in (("and",) if index else ()) + ((item["field"], "is", item["value"]),))
        matches, _, error = searcher.find({"name": name, "request_fields": request, "return_fields": api_fields})
        if error:
            raise RuntimeError(f"API-Suche für {name!r} unvollständig; Zustand unverändert: {error}")
        placeholders = 0
        for number, row in enumerate(matches, 1):
            if len(row) != len(api_fields) or not all(isinstance(value, str) for value in row):
                _issue(ctx, "skipped", invalid_category, f"{name}#{number}", f"Kollektion={name!r}, Rückgabefelder={row!r}")
                continue
            values = {key: _values(raw) for key, raw in zip(keys, row)}
            ids = values["clip_id"]
            if len(ids) != 1 or not (ids[0].isascii() and ids[0].isdecimal()):
                _issue(ctx, "skipped", invalid_category, f"{name}#{number}", f"Kollektion={name!r}, Clip-ID-Rohwert={row[0]!r}")
                continue
            hit = found[ids[0]].setdefault(name, {"collection": name, "placeholder": False, "invalid": None, "rows": []})
            if "placeholder" in (flag.casefold() for flag in values["status_flags"]):
                hit["placeholder"] = True
                placeholders += 1
                continue
            hit["rows"].append(values)
        _log(f"API-Suche abgeschlossen: {name!r}: {len(matches)} Trefferzeilen, davon {placeholders} Platzhalter; "
             f"{perf_counter() - started:.1f} s.")
    return {clip_id: [_merge_hit(hit) for hit in hits.values()] for clip_id, hits in found.items()}


# --------- FUNC: PROXY FILES ---------
def _proxy_keys(name: str) -> list[tuple[str, str]] | None:
    prefix = cfg["proxy_prefix"] + "__"
    if not name.casefold().startswith(prefix.casefold()):
        return None
    identifier, separator, title = name[len(prefix):].partition("__")
    if not separator or not identifier.strip() or not title.strip():
        return None
    return list(dict.fromkeys((_normalize(identifier), _normalize(value)) for value in (title, Path(title).stem)))


def _proxy_index(ctx: dict, folder: str) -> dict:
    if folder in ctx["indexes"]:
        return ctx["indexes"][folder]
    strict, index = folder == _aqc_folder(), defaultdict(list)
    for name, size in _listing(ctx, folder).values():
        if _ignored(name) or name.casefold().endswith(protocol_suffixes):
            continue
        keys = _proxy_keys(name)
        if keys is None or not size:
            if strict:
                category = "AQC-Dateiname nicht zuordenbar" if keys is None else "AQC-Datei noch leer (nicht gezählt)"
                _issue(ctx, "note", category, name, f"Datei={name!r}")
            continue
        for key in keys:
            if name not in index[key]:
                index[key].append(name)
    ctx["indexes"][folder] = index
    return index


def _lookup(ctx: dict, folder: str, identifier: str, title: str) -> list[str]:
    return sorted(_proxy_index(ctx, folder).get((_normalize(identifier), _normalize(title)), []), key=str.casefold)


# --------- FUNC: STATE ---------
def _empty_state() -> dict:
    return {"schema_version": 3, "priority": None, "notes": [], "workers": {}, "files_seen": {}, "clips": {}}


def _clip_problem(clip_id: str, clip) -> str | None:
    if not isinstance(clip, dict) or clip.get("clip_id") != clip_id:
        return "Clip_ID passt nicht zum Eintrag"
    if not all(isinstance(clip.get(key), bool) for key in ("active", "ready")):
        return "active/ready fehlt"
    if clip.get("stage") not in (*stages, None) or clip["ready"] != (clip["stage"] is None):
        return "Stufe passt nicht zu bereit"
    if not all(isinstance(clip.get(key), kind) for key, kind in (("history", list), ("files", dict), ("issues", dict))):
        return "Struktur unvollständig"
    job = clip.get("job")
    keys = ("id", "stage", "folder", "file", "output_folder", "state")
    if job is not None and (not isinstance(job, dict) or not all(isinstance(job.get(key), str) for key in keys)):
        return "Job-Eintrag unvollständig"
    return None


def _load_state() -> dict:
    if not state_path.exists():
        return _empty_state()
    with state_path.open(encoding="utf-8") as handle:
        state = json.load(handle)
    version = state.get("schema_version") if isinstance(state, dict) else None
    if version in (1, 2):
        raise ValueError(f"Zustand hat ein altes Format (Version {version}). Bitte state/marathon.json löschen; "
                         "Marathon sammelt den Stand beim nächsten Bericht aus den Ordnern neu ein.")
    if version != 3 or not isinstance(state.get("clips"), dict):
        raise ValueError("Unbekanntes Zustandsformat; keine Aktualisierung.")
    for key, default in _empty_state().items():
        state.setdefault(key, default)
    for clip_id, clip in state["clips"].items():
        problem = _clip_problem(clip_id, clip)
        if problem:
            raise ValueError(f"Ungültiger Zustand für Clip_ID {clip_id!r}: {problem}; keine Aktualisierung.")
    return state


def _save_state(state: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=state_dir,
                                         prefix=".marathon-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, state_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


# --------- FUNC: RECONCILE ---------
def _classify(hits: list[dict]) -> tuple[dict | None, tuple[str, str] | None]:
    if not hits:
        return None, ("missing", "Nicht mehr in der Suche gefunden (Metadaten nicht abrufbar oder Kollektion geändert)")
    if any(hit["placeholder"] for hit in hits):
        return None, ("placeholder", "Suche meldet Platzhalter")
    if len(hits) > 1:
        return None, ("multi", "Kollektionen: " + ", ".join(sorted(hit["collection"] for hit in hits)))
    return (None, ("invalid", hits[0]["invalid"])) if hits[0]["invalid"] else (hits[0], None)


def _new_clip(clip_id: str, hit: dict) -> dict:
    return {"clip_id": clip_id, "collection": hit["collection"], "identifier": hit["identifier"],
            "title": hit["title"], "clip_name_with_extension": hit["clip_name"], "filehashes": hit["hashes"],
            "master_files": hit["masters"], "status": "wartet", "active": True, "ready": False, "stage": "restore",
            "queued_at": _stamp(), "preset": None, "job": None, "job_count": 0, "attempts": 0,
            "files": {"master": None, "proxy": None},
            "issues": {"search": None, "file": None, "sticky": None}, "history": []}


def _missing_masters(ctx: dict, collection: str, clip_id: str, names: list[str]) -> list[str] | None:
    """Master names missing in the clip's transcode inbox; None if that folder does not exist."""
    if not names or clip_id not in _dirs(ctx, _master_root(collection)):
        return None
    return [name for name in names if not _has_file(ctx, _master_folder(collection, clip_id), name)]


def _admit(clips: dict, clip_id: str, hit: dict, ctx: dict) -> None:
    collection, identifier, title = hit["collection"], hit["identifier"], hit["title"]
    text = f"Clip_ID={clip_id}, Kollektion={collection}, Clipname={hit['clip_name']}"
    places = [(_final_folder(collection), "Zielordner"), (_qc_inbox(collection), "QC-Eingang"),
              *([(_aqc_folder(), "AQC")] if _is_defa(collection) else [])]
    found = [(folder, source, _lookup(ctx, folder, identifier, title)) for folder, source in places]
    crowded = [f"{source}: {', '.join(names)}" for _, source, names in found if len(names) > 1]
    if crowded:
        _issue(ctx, "skipped", "Mehrere Proxy-Dateien gefunden", clip_id, f"{text}: {'; '.join(crowded)}")
        return
    proxy = next(((folder, names[0], source) for folder, source, names in found if names), None)
    missing = _missing_masters(ctx, collection, clip_id, hit["masters"])
    if proxy is None and missing != [] and hit["restore_problem"]:
        _issue(ctx, "skipped", problem_categories["restore"][0], clip_id, f"{text}: {hit['restore_problem']}")
        return
    clip, ready = _new_clip(clip_id, hit), bool(proxy) and proxy[2] == "Zielordner"
    if missing is not None and not ready:  # Recorded so the folder is deleted once the clip is ready.
        clip["files"]["master"] = {"folder": _master_folder(collection, clip_id), "names": list(hit["masters"]),
                                   "source": "Transcode-Eingang", "last_seen_at": _now()}
    if proxy:
        clip["files"]["proxy"] = _file_entry(*proxy)
    if ready:
        clip.update(ready=True, stage=None, status="bereit")
        _event(clip, "Aufgenommen – bereits im Zielordner", proxy[1])
    elif proxy:
        clip["stage"] = "qc"
        _event(clip, f"Aufgenommen – Proxy im {proxy[2]}", proxy[1])
    elif missing == []:
        clip["stage"] = "transcode"
        _event(clip, "Aufgenommen – Master im Transcode-Eingang", ", ".join(hit["masters"]))
    else:
        if missing:
            _issue(ctx, "note", "Master unvollständig im Transcode-Eingang – neuer Restore", clip_id,
                   f"{text}: fehlend {', '.join(missing)}")
        _event(clip, "Aufgenommen – wartet auf LTO-Restore", ", ".join(hit["masters"]))
    clips[clip_id] = clip


def _update_metadata(clip: dict, hit: dict, ctx: dict) -> None:
    new = {"collection": hit["collection"], "identifier": hit["identifier"], "title": hit["title"],
           "clip_name_with_extension": hit["clip_name"], "master_files": hit["masters"], "filehashes": hit["hashes"]}
    changed = [f"{label}: {clip[key]!r} → {new[key]!r}" for key, label in tracked_fields.items() if clip[key] != new[key]]
    clip.update(new)
    if changed:
        detail = "; ".join(changed)
        _event(clip, "Metadaten geändert", detail)
        if clip["job"]:
            clip["job"]["outdated"] = True
        _issue(ctx, "note", "Metadaten geändert", clip["clip_id"], f"{_clip_text(clip)}: {detail}")


def _reconcile(state: dict, found: dict[str, list[dict]], ctx: dict) -> None:
    clips = state["clips"]
    classified = {clip_id: _classify(found.get(clip_id, [])) for clip_id in {*found, *clips}}
    groups = defaultdict(list)
    for clip_id, (hit, _) in classified.items():
        if hit:
            groups[(_normalize(hit["identifier"]), _normalize(hit["title"]))].append(clip_id)
    for group in groups.values():
        if len(group) > 1:
            text = "Clip_IDs: " + ", ".join(sorted(group, key=int))
            for clip_id in group:
                classified[clip_id] = (classified[clip_id][0], ("duplicate", text))
    for clip_id in sorted(classified, key=int):
        hit, problem = classified[clip_id]
        clip = clips.get(clip_id)
        if clip is None:
            if problem is None:
                _admit(clips, clip_id, hit, ctx)
            elif problem_categories[problem[0]][0]:
                collections = ", ".join(sorted(item["collection"] for item in found[clip_id]))
                _issue(ctx, "skipped", problem_categories[problem[0]][0], clip_id,
                       f"Clip_ID={clip_id}, Kollektion={collections}: {problem[1]}")
            continue
        if hit:
            _update_metadata(clip, hit, ctx)
            if problem is None and clip["stage"] == "restore" and hit["restore_problem"]:
                problem = ("restore", hit["restore_problem"])
        _set_issue(clip, "search", *((problem_categories[problem[0]][1], problem[1]) if problem else ()))


# --------- FUNC: WORKERS ---------
# Worker rules (provisional until the tools exist; paths are relative to the share root with "/" as separator):
# - Heartbeat at least once a minute: <root>/<work_dir>/worker/<worker>.json, written via temporary name + rename:
#   {"worker": str, "stage": "LTO" | "Transcode" | "QC", "host": str, "job_id": str | null, "beat": <changes each time>}
# - Read <root>/<work_dir>/priority.json and walk the collections of the own stage in the given order.
# - Take the first *.json in "offen" (sorted by name) by renaming it into "laufend/<worker>/";
#   if the rename fails because the file is gone, another worker was faster: try the next file.
# - Read inputs only where the job says; write results only into the job's output_folder (ausgang/<job_id>).
#   LTO: all names from "files" (restored via "hashes"); Transcode: exactly one proxy named by the proxy scheme,
#   otherwise the job fails; QC: never move the proxy. Protocol files (.log/.txt/.json) are archived.
# - Leave the job file in "laufend"; write the report as "fertig/<job_id>.json" via a temporary name that does not
#   end in ".json", then rename: {"job_id": str, "status": "ok" | "failed" | "rejected" (QC only),
#   "result": str (required unless ok), "preset": str (Transcode)}.
# - Marathon moves results to the next stage, archives job, report and leftovers, and deletes failed partial results.
def _read_workers(state: dict) -> None:
    folder, current = f"{cfg['work_dir']}/{worker_dir}", {}
    for key, (name, _) in sorted(_scan(folder).items()):
        if not key.endswith(".json"):
            continue
        worker, old = Path(name).stem, state["workers"].get(Path(name).stem)
        try:
            text = _path(f"{folder}/{name}").read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, UnicodeError, ValueError):
            data = None
        if not isinstance(data, dict):
            if old:
                current[worker] = old  # Half-written heartbeat; the timeout reveals real outages.
            continue
        current[worker] = old if old and old["raw"] == text else {
            "raw": text, "changed_at": _now(), "stage": str(data.get("stage") or ""),
            "host": str(data.get("host") or ""), "job_id": data.get("job_id")}
    state["workers"] = current


def _watch_lines(state: dict) -> list[str]:
    timeout, lines = timedelta(minutes=cfg["worker_timeout_minutes"]), []
    for clip in sorted(state["clips"].values(), key=lambda item: int(item["clip_id"])):
        job = clip["job"]
        if not job or job["state"] != "laufend":
            continue
        since = job.get("running_since") or job["created_at"]
        worker, reasons = state["workers"].get(job["worker"]), []
        if worker is None:
            reasons.append("kein Heartbeat vom Worker")
        elif _age(worker["changed_at"]) > timeout:
            reasons.append(f"Worker ohne Lebenszeichen seit {_duration(_age(worker['changed_at']))}")
        elif worker["job_id"] != job["id"] and _age(since) > timeout:
            reasons.append(f"Worker meldet anderen Job ({worker['job_id'] or 'keinen'})")
        if _age(since) > timedelta(hours=cfg["max_job_hours"]):
            reasons.append(f"läuft länger als {cfg['max_job_hours']} h")
        if reasons:
            lines.append(f"  {_clip_text(clip)}; {stage_labels[job['stage']]}-Job {job['id']}; Worker {job['worker']}; "
                         f"läuft seit {since}; {'; '.join(reasons)}")
    return lines


def _worker_lines(state: dict) -> list[str]:
    return [f"  {name}, {worker['stage'] or '?'}, Rechner {worker['host'] or '?'}, letztes Lebenszeichen vor "
            f"{_duration(_age(worker['changed_at']))}, Job {worker['job_id'] or '–'}"
            for name, worker in sorted(state["workers"].items())]


# --------- FUNC: JOBS ---------
def _report_problem(report) -> str | None:
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


def _archive_job(job: dict) -> str | None:
    """Move the job file to archiv; returns the worker folder it was found in."""
    folder, name = job["folder"], job["file"]
    for worker in _subfolders(f"{folder}/laufend"):
        if _move(f"{folder}/laufend/{worker}/{name}", f"{folder}/archiv"):
            return worker
    _move(f"{folder}/offen/{name}", f"{folder}/archiv")
    return None


def _finish_output(job: dict, keep: bool, ctx: dict) -> None:
    """Archive (keep=True) or delete whatever is left in the job's output folder."""
    path = _path(job["output_folder"])
    if not path.is_dir():
        return
    if keep and any(path.iterdir()):
        try:
            _move(job["output_folder"], f"{job['folder']}/archiv", f"{job['id']}.{outbox}")
        except OSError as exc:
            _issue(ctx, "note", "Ausgang nicht archivierbar (bleibt liegen)", job["output_folder"], f"{job['output_folder']}: {exc}")
        return
    _remove_tree(job["output_folder"], ctx, "Ausgang nicht löschbar (bleibt liegen)")


def _take_outputs(clip: dict, job: dict, report: dict, ctx: dict) -> str | None:
    """Move the results of a successful job to the next stage; returns a problem text instead."""
    stage, out, collection = job["stage"], job["output_folder"], clip["collection"]
    delivered = {key: name for key, (name, size) in _scan(out).items() if size and not key.endswith(busy_suffixes)}
    if stage == "restore":
        missing = [name for name in clip["master_files"] if name.casefold() not in delivered]
        if missing:
            return f"Restore unvollständig, fehlend: {', '.join(missing)}"
        target = _master_folder(collection, clip["clip_id"])
        for name in clip["master_files"]:
            _move(f"{out}/{delivered[name.casefold()]}", target, name, replace=True)
        clip["files"]["master"] = {"folder": target, "names": list(clip["master_files"]), "source": "Restore",
                                   "last_seen_at": _now()}
        _enter(clip, "transcode")
    elif stage == "transcode":
        proxies = [name for key, name in delivered.items() if not key.endswith(protocol_suffixes)]
        if len(proxies) != 1:
            return f"Transcode-Ausgang enthält {len(proxies)} Proxy-Dateien statt einer"
        name = proxies[0]
        if (_normalize(clip["identifier"]), _normalize(clip["title"])) not in (_proxy_keys(name) or []):
            return f"Proxy-Name {name!r} entspricht nicht dem Namensschema"
        _move(f"{out}/{name}", _qc_inbox(collection), replace=True)
        clip["files"]["proxy"] = _file_entry(_qc_inbox(collection), name, "Transcode")
        clip["preset"] = report.get("preset")
        _enter(clip, "qc")
    else:
        proxy, final = clip["files"]["proxy"], _final_folder(collection)
        source = f"{proxy['folder']}/{proxy['name']}"
        if not _path(source).is_file():
            return f"Proxy {source} vor der Auslieferung nicht mehr vorhanden"
        if _path(f"{final}/{proxy['name']}").exists():
            _move(f"{final}/{proxy['name']}", f"{final}/{unknown_dir}")
            _issue(ctx, "note", "Unbekannte Datei nach unbekannt verschoben", f"{final}/{proxy['name']}",
                   f"{final}/{proxy['name']} → {final}/{unknown_dir}/ (Namenskonflikt bei Auslieferung)")
        _move(source, final)
        clip["files"]["proxy"] = _file_entry(final, proxy["name"], "QC")
        master = clip["files"]["master"]
        if master and not master.get("deleted_at"):
            _remove_tree(master["folder"], ctx, "Master nicht löschbar (bleiben liegen)")
            master["deleted_at"] = _now()
        clip.update(ready=True, stage=None)
        _event(clip, "Bereit", f"{final}/{proxy['name']}")
    return None


def _apply_report(clip: dict, job: dict, report: dict, worker: str | None, ctx: dict) -> None:
    stage, label = job["stage"], stage_labels[job["stage"]]
    status, result = report["status"], str(report.get("result") or "").strip()
    by = f"Worker {worker or 'unbekannt'}"
    clip["job"] = None
    if status == "rejected" and stage != "qc":
        status = "failed"
    if status == "ok":
        _event(clip, f"{label}-Job fertig", by + (f", Preset {report['preset']}" if report.get("preset") else ""))
        problem = _take_outputs(clip, job, report, ctx)
        if problem is None:
            clip["attempts"] = 0
            _finish_output(job, True, ctx)
            return
        status, result = "failed", problem
    if status == "rejected":
        _set_issue(clip, "sticky", qc_rejected, result)
        _event(clip, qc_rejected, f"{by}: {result}")
        _finish_output(job, True, ctx)
        return
    clip["attempts"] += 1
    _event(clip, f"{label}-Job fehlgeschlagen", f"{by}: {result}")
    _finish_output(job, False, ctx)
    if clip["attempts"] >= cfg["max_job_attempts"]:
        _set_issue(clip, "sticky", job_failed, f"{label}, {clip['attempts']} Versuche: {result}")
    else:
        _issue(ctx, "note", "Job fehlgeschlagen – neuer Versuch", clip["clip_id"], f"{_clip_text(clip)}: {label}: {result}")


def _retire(folder: str, job_id: str, ctx: dict) -> None:
    """Archive job file and output folder of a job Marathon no longer tracks, if they exist."""
    found = _running(ctx, folder).get(f"{job_id}.json".casefold())
    if found:
        _move(f"{folder}/laufend/{found[0]}/{found[1]}", f"{folder}/archiv")
    if job_id in _dirs(ctx, f"{folder}/{outbox}"):
        _move(f"{folder}/{outbox}/{job_id}", f"{folder}/archiv", f"{job_id}.{outbox}")


def _collect_reports(folder: str, jobs: dict[str, dict], ctx: dict) -> None:
    for name, _ in sorted(_scan(f"{folder}/fertig").values()):
        if not name.casefold().endswith(".json"):
            continue
        relative, archived = f"{folder}/fertig/{name}", f"{Path(name).stem}.report.json"
        try:
            report = json.loads(_path(relative).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            _issue(ctx, "note", "Jobreport unlesbar (wird erneut versucht)", relative, f"{relative}: {exc}")
            continue
        problem = _report_problem(report)
        if problem:
            _issue(ctx, "note", "Jobreport ungültig (wird erneut versucht)", relative, f"{relative}: {problem}")
            continue
        clip = jobs.get(report["job_id"])
        if clip is None or clip["job"]["folder"] != folder:
            _issue(ctx, "note", "Veralteter Jobreport (ignoriert und archiviert)", relative, relative)
            _move(relative, f"{folder}/archiv", archived)
            _retire(folder, report["job_id"], ctx)
            continue
        job = jobs.pop(report["job_id"])["job"]
        _apply_report(clip, job, report, _archive_job(job) or job.get("worker"), ctx)
        _move(relative, f"{folder}/archiv", archived)


def _locate_job(clip: dict, ctx: dict) -> None:
    job = clip["job"]
    folder, name = job["folder"], job["file"]
    if name.casefold() in _listing(ctx, f"{folder}/offen"):
        if job["state"] == "laufend":
            _event(clip, "Job wieder offen", f"von {job.get('worker') or 'unbekannt'} zurückgegeben")
        job.update(state="offen", worker=None, running_since=None, missing_since=None)
        return
    worker = _running(ctx, folder).get(name.casefold(), (None,))[0]
    if worker:
        taken = job.get("worker") != worker
        job.update(state="laufend", worker=worker, missing_since=None)
        if taken:
            job["running_since"] = _now()
            _event(clip, "Job übernommen", worker)
        return
    if _path(f"{folder}/fertig/{job['id']}.json").exists():
        return  # Report arrived during this run; it is collected next time.
    if not job.get("missing_since"):
        job.update(state="fehlt", missing_since=_now())
        _issue(ctx, "note", "Job-Datei nicht auffindbar (wird beobachtet)", clip["clip_id"], f"{_clip_text(clip)}: {folder}/…/{name}")
    elif _age(job["missing_since"]) >= timedelta(minutes=cfg["missing_job_minutes"]):
        _issue(ctx, "note", "Job-Datei verschwunden – Job neu erstellt", clip["clip_id"], f"{_clip_text(clip)}: {folder}/…/{name}")
        clip["job"] = None
        _rmdir(job["output_folder"])
        _event(clip, "Job-Datei verschwunden", name)


def _sweep_unknown_jobs(folder: str, known: set[str], ctx: dict) -> None:
    for key, (name, _) in _listing(ctx, f"{folder}/offen").items():
        if key.endswith(".json") and key not in known and _move(f"{folder}/offen/{name}", f"{folder}/zurueckgezogen"):
            _rmdir(f"{folder}/{outbox}/{Path(name).stem}")
            _issue(ctx, "note", "Unbekannte Job-Datei zurückgezogen", f"{folder}/{key}", f"{folder}/offen/{name}")
    for key, (worker, name) in _running(ctx, folder).items():
        if key.endswith(".json") and key not in known:
            _issue(ctx, "note", "Unbekannter laufender Job (Ergebnis wird ignoriert)", f"{folder}/{key}",
                   f"{folder}/laufend/{worker}/{name}")


def _withdraw(clip: dict) -> bool:
    """Withdraw a job that no worker has taken; False if the job is (or just became) running."""
    job = clip["job"]
    if job is None:
        return True
    if cfg["report_only"] or job["state"] == "laufend":
        return False
    if job["state"] == "offen" and not _move(f"{job['folder']}/offen/{job['file']}", f"{job['folder']}/zurueckgezogen"):
        return False  # A worker took it meanwhile.
    _rmdir(job["output_folder"])
    clip["job"] = None
    _event(clip, "Job zurückgezogen", job["file"])
    return True


def _discover(clip: dict, ctx: dict) -> None:
    job = clip["job"]
    if clip["ready"] or clip["stage"] == "qc" or not _is_defa(clip["collection"]) or (job and job["state"] == "laufend"):
        return
    aqcs = _lookup(ctx, _aqc_folder(), clip["identifier"], clip["title"])
    if len(aqcs) > 1:
        _issue(ctx, "note", "Mehrere AQC-Dateien", clip["clip_id"], f"{_clip_text(clip)}: {', '.join(aqcs)}")
    elif aqcs and _withdraw(clip):
        clip["files"]["proxy"] = _file_entry(_aqc_folder(), aqcs[0], "AQC")
        clip["attempts"] = 0
        _set_issue(clip, "sticky")  # A failed LTO/Transcode stage is skipped by the AQC proxy.
        _enter(clip, "qc")
        _issue(ctx, "note", "AQC-Proxy gefunden – direkt an QC", clip["clip_id"], f"{_clip_text(clip)}: {aqcs[0]}")


def _check_files(clip: dict, ctx: dict) -> tuple[str, str] | tuple[()]:
    job, files = clip["job"], clip["files"]
    if clip["ready"] or clip["stage"] == "qc":
        proxy = files["proxy"]
        if _has_file(ctx, proxy["folder"], proxy["name"]):
            proxy["last_seen_at"] = _now()
            return ()
        return lost_proxy, f"Datei {proxy['folder']}/{proxy['name']} (Quelle {proxy['source']}), zuletzt gesehen {proxy['last_seen_at']}"
    if clip["stage"] == "transcode" and not (job and job["state"] == "laufend"):
        master = files["master"]
        missing = [name for name in master["names"] if not _has_file(ctx, master["folder"], name)]
        if not missing:
            master["last_seen_at"] = _now()
            return ()
        return lost_master, (f"Ordner {master['folder']}, fehlend: {', '.join(missing)}, "
                             f"zuletzt vollständig gesehen {master['last_seen_at']}")
    return ()


def _update_activity(clip: dict, ctx: dict) -> None:
    reasons = [reason for reason in (clip["issues"][kind] for kind in ("sticky", "file", "search")) if reason]
    active = not reasons
    if active != clip["active"]:
        if active:
            _event(clip, "Wieder aktiv")
            _issue(ctx, "note", "Wieder aktiv", clip["clip_id"], _clip_text(clip))
        else:
            _event(clip, "Inaktiv", "; ".join(reason["category"] for reason in reasons))
        clip["active"] = active
    last = next((item for item in reversed(clip["history"]) if item["event"] != "Inaktiv"), None)
    last_text = f"; letztes Ereignis: {last['at']} {last['event']} ({last['position']})" if last else ""
    for reason in reasons:
        _issue(ctx, "inactive", reason["category"], clip["clip_id"],
               f"{_clip_text(clip)}; letzter Stand: {_position(clip)}; {reason['detail']}; seit {reason['since']}{last_text}")


def _status(clip: dict) -> str:
    for kind in ("sticky", "file", "search"):
        if clip["issues"][kind]:
            return status_codes.get(clip["issues"][kind]["category"], "inaktiv")
    if clip["ready"]:
        return "bereit"
    return "laufend" if clip["job"] and clip["job"]["state"] == "laufend" else "wartet"


def _sweep_final(state: dict, mapping: list[dict], ctx: dict) -> None:
    known = defaultdict(set)
    for clip in state["clips"].values():
        if clip["ready"] and clip["files"]["proxy"]:
            known[clip["files"]["proxy"]["folder"]].add(clip["files"]["proxy"]["name"].casefold())
    for final in sorted({_final_folder(entry["name"]) for entry in mapping}):
        for key, (name, size) in sorted(_listing(ctx, final).items()):
            if key in known[final] or _ignored(name):
                continue
            relative = f"{final}/{name}"
            if cfg["report_only"]:
                _issue(ctx, "note", "Unbekannte Datei im Zielordner (report_only – nicht verschoben)", relative, relative)
                continue
            if not _stable(state, ctx, relative, size):
                continue
            try:
                moved = _move(relative, f"{final}/{unknown_dir}")
            except OSError as exc:
                _issue(ctx, "note", "Unbekannte Datei noch in Benutzung (nächster Versuch im nächsten Zyklus)", relative, f"{relative}: {exc}")
                continue
            if moved:
                _issue(ctx, "note", "Unbekannte Datei nach unbekannt verschoben", relative, f"{relative} → {final}/{unknown_dir}/")


def _leftovers(state: dict, mapping: list[dict], ctx: dict) -> None:
    clips = state["clips"].values()
    proxies = {(clip["files"]["proxy"]["folder"], clip["files"]["proxy"]["name"].casefold())
               for clip in clips if clip["files"]["proxy"]}
    masters = {clip["files"]["master"]["folder"] for clip in clips
               if clip["files"]["master"] and not clip["files"]["master"].get("deleted_at")}
    jobs = {clip["job"]["id"] for clip in clips if clip["job"]}
    for entry in mapping:
        for stage in stages:
            outputs = f"{_stage_folder(entry['name'], stage)}/{outbox}"
            for job_id in sorted(_dirs(ctx, outputs) - jobs):
                _issue(ctx, "note", "Ausgang ohne aktuellen Job", f"{outputs}/{job_id}", f"{outputs}/{job_id}")
        root = _master_root(entry["name"])
        for clip_id in sorted(_dirs(ctx, root)):
            if f"{root}/{clip_id}" not in masters:
                _issue(ctx, "note", "Master-Ordner ohne passenden Clip (Transcode-Eingang)", f"{root}/{clip_id}", f"{root}/{clip_id}")
        folder = _qc_inbox(entry["name"])
        for key, (name, _) in sorted(_listing(ctx, folder).items()):
            if (folder, key) not in proxies and not _ignored(name):
                _issue(ctx, "note", "Datei ohne passenden Clip (QC-Eingang)", f"{folder}/{key}", f"{folder}/{name}")
    if any(_is_defa(entry["name"]) for entry in mapping):
        folder = _aqc_folder()
        for key, (name, size) in sorted(_listing(ctx, folder).items()):
            if size and _proxy_keys(name) and (folder, key) not in proxies:
                _issue(ctx, "note", "AQC-Datei ohne aufgenommenen Clip", f"{folder}/{key}", f"{folder}/{name}")


def _job_payload(clip: dict, job_id: str, folder: str) -> dict:
    stage = clip["stage"]
    payload = {"schema_version": 2, "job_id": job_id, "stage": stage_labels[stage], "clip_id": clip["clip_id"],
               "collection": clip["collection"], "identifier": clip["identifier"], "title": clip["title"],
               "clip_name": clip["clip_name_with_extension"], "created_at": _now(),
               "report_folder": f"{folder}/fertig", "output_folder": f"{folder}/{outbox}/{job_id}"}
    if stage == "restore":
        payload.update(hashes=clip["filehashes"], files=clip["master_files"])
    elif stage == "transcode":
        master = clip["files"]["master"]
        payload.update(inputs=[f"{master['folder']}/{name}" for name in master["names"]], preset=None)
    else:
        payload["input"] = f"{clip['files']['proxy']['folder']}/{clip['files']['proxy']['name']}"
    return payload


def _create_job(clip: dict) -> None:
    stage = clip["stage"]
    folder = _stage_folder(clip["collection"], stage)
    clip["job_count"] += 1
    job_id = f"{clip['queued_at']}__{clip['clip_id']}__{stage_labels[stage].casefold()}{clip['job_count']}"
    payload = _job_payload(clip, job_id, folder)
    _path(payload["output_folder"]).mkdir(parents=True, exist_ok=True)
    _write_text_atomic(_path(f"{folder}/offen/{job_id}.json"), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    clip["job"] = {"id": job_id, "stage": stage, "folder": folder, "file": f"{job_id}.json",
                   "output_folder": payload["output_folder"], "state": "offen", "worker": None,
                   "created_at": payload["created_at"], "running_since": None, "missing_since": None}
    _event(clip, f"{stage_labels[stage]}-Job erstellt", job_id)


def _ready_for_job(state: dict, clip: dict, ctx: dict) -> bool:
    proxy = clip["files"]["proxy"]
    if clip["stage"] != "qc" or proxy["folder"] != _aqc_folder():
        return True
    item = _listing(ctx, proxy["folder"]).get(proxy["name"].casefold())
    return item is not None and _stable(state, ctx, f"{proxy['folder']}/{proxy['name']}", item[1])


def _schedule(state: dict, prio: dict[str, list[str]], ctx: dict) -> None:
    clips = state["clips"].values()
    for clip in clips:
        job = clip["job"]
        expected = None if clip["ready"] else _stage_folder(clip["collection"], clip["stage"])
        if job and (not clip["active"] or job.get("outdated") or job["folder"] != expected or job["stage"] != clip["stage"]):
            _withdraw(clip)
    for stage in stages:
        ranks = {name: rank for rank, name in enumerate(prio[stage])}
        pool = sorted((clip for clip in clips if clip["active"] and not clip["ready"] and clip["stage"] == stage and
                       (clip["job"]["state"] == "offen" if clip["job"] else _ready_for_job(state, clip, ctx))),
                      key=lambda clip: (ranks.get(clip["collection"], len(ranks)), clip["queued_at"]))
        limit = cfg[limit_keys[stage]]
        for clip in pool[limit:]:
            if clip["job"]:
                _withdraw(clip)
        for clip in pool[:limit]:
            if clip["job"] is None:
                _create_job(clip)


def _process(state: dict, mapping: list[dict], prio: dict[str, list[str]], ctx: dict) -> None:
    clips, writing = state["clips"], not cfg["report_only"]
    _read_workers(state)
    if writing:
        _ensure_folders(mapping)
        _write_priority_file(prio)
        jobs = {clip["job"]["id"]: clip for clip in clips.values() if clip["job"]}
        folders = sorted({_stage_folder(entry["name"], stage) for entry in mapping for stage in stages} |
                         {clip["job"]["folder"] for clip in jobs.values()})
        for folder in folders:
            _collect_reports(folder, jobs, ctx)
        ctx["listings"].clear()  # Reports moved files around.
        ctx["indexes"].clear()
        for clip in clips.values():
            if clip["job"]:
                _locate_job(clip, ctx)
        known = {clip["job"]["file"].casefold() for clip in clips.values() if clip["job"]}
        for folder in folders:
            _sweep_unknown_jobs(folder, known, ctx)
    for clip in clips.values():
        _discover(clip, ctx)
        _set_issue(clip, "file", *_check_files(clip, ctx))
        _update_activity(clip, ctx)
    _sweep_final(state, mapping, ctx)
    if writing:
        _schedule(state, prio, ctx)
    for clip in clips.values():
        clip["status"] = _status(clip)
    for key in set(state["files_seen"]) - ctx["touched"]:
        del state["files_seen"][key]


# --------- FUNC: REPORT ---------
def _totals(state: dict, mapping: list[dict]) -> dict[str, tuple[int, ...]]:
    totals = {entry["name"]: [0] * len(count_columns) for entry in mapping}
    for clip in state["clips"].values():
        row = totals.get(clip["collection"])
        if row is None or not clip["active"]:
            continue
        row[0] += 1
        row[1 if clip["ready"] else 2 + stages.index(clip["stage"])] += 1
    return {name: tuple(row) for name, row in totals.items()}


def _previous(kind: str) -> Path | None:
    files = sorted(reports_dir.glob(f"{kind}_*.txt"))
    return files[-1] if files else None


def _read_previous(path: Path | None) -> dict[str, dict[str, float]]:
    if path is None:
        return {}
    result, header = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.split("|")]
        if parts[0] == "Kollektion":
            header = parts
            continue
        if header is None or len(parts) != len(header) or not parts[0]:
            continue
        try:
            result[parts[0]] = {column: (float if column == "%" else int)(cell.split()[0])
                                for column, cell in zip(header, parts) if column in (*count_columns, "%")}
        except (ValueError, IndexError) as exc:
            raise ValueError(f"Vorgängerbericht {path.name} ist nicht lesbar.") from exc
    return result


def _format_int(value: int, previous: int | None) -> str:
    return str(value) if previous is None else f"{value} ({value - previous:+d})"


def _render(kind: str, when: datetime, totals: dict, prio: dict[str, list[str]], previous: dict) -> str:
    ranks = {stage: {name: str(rank) for rank, name in enumerate(prio[stage], 1)} for stage in stages}
    summary = tuple(sum(values[index] for values in totals.values()) for index in range(len(count_columns)))
    rows = []
    for name, values in (*totals.items(), (summary_name, summary)):
        old, (total, ready) = previous.get(name, {}), values[:2]
        percent = 100 * ready / total if total else 0.0
        percent_text = (f"{percent:.1f}" if total else "0") + " %"
        if "%" in old:
            percent_text += f" ({round(round(percent, 1) - old['%'], 1) + 0.0:+.1f} pp)"  # + 0.0 avoids "-0.0".
        counts = [_format_int(value, old.get(column)) for column, value in zip(count_columns, values)]
        rows.append((name, *(ranks[stage].get(name, "") for stage in stages), *counts[:2], percent_text, *counts[2:]))
    widths = [max(len(row[index]) for row in (columns, *rows)) for index in range(len(columns))]

    def line(cells) -> str:
        return " | ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()

    separator = "-+-".join("-" * width for width in widths)
    table = [line(columns), separator, *(line(row) for row in rows[:-1]), separator, line(rows[-1])]
    return f"{app_name} {app_version} | {kind} | {when.isoformat(timespec='seconds')}\n\n" + "\n".join(table) + "\n"


def _summary_lines(issues: list[dict]) -> list[str]:
    if not issues:
        return ["Keine Auffälligkeiten."]
    lines = []
    for section, title in issue_sections.items():
        categories = defaultdict(set)
        for item in issues:
            if item["section"] == section:
                categories[item["category"]].add(item["key"])
        if not categories:
            continue
        clips = {key for keys in categories.values() for key in keys}
        total = sum(map(len, categories.values())) if section == "note" else len(clips)
        lines.append(f"{title}: {total}" + ("" if section == "note" else " Clips"))
        lines += [f"  {category}: {len(keys)}" for category, keys in
                  sorted(categories.items(), key=lambda item: (-len(item[1]), item[0].casefold()))]
    return lines


def _format_errors(issues: list[dict], when: datetime) -> str:
    lines = [f"{app_name} {app_version} | Fehlerbericht | {when.isoformat(timespec='seconds')}", "", *_summary_lines(issues)]
    for section, title in issue_sections.items():
        grouped = defaultdict(list)
        for item in issues:
            if item["section"] == section:
                grouped[item["category"]].append(item["detail"])
        for category in sorted(grouped, key=str.casefold):
            details = sorted(dict.fromkeys(grouped[category]), key=str.casefold)
            lines += ["", f"=== {title.split(' (')[0]} – {category} ({len(details)}) ===", *details]
    return "\n".join(lines) + "\n"


def _write_new(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)


def _report(kind: str) -> Path:
    started = perf_counter()
    _log(f"{kind}-Bericht gestartet.")
    problems = _load_config()
    mapping = _load_mapping()
    _check_root()
    state = _load_state()
    ctx = _context()
    ctx["issues"].extend(state["notes"])
    state["notes"] = []
    for problem in problems:
        _issue(ctx, "note", "Konfiguration", "config", problem)
    prio = _priority(mapping, state, ctx)
    found = _search_clips(mapping, ctx)
    _reconcile(state, found, ctx)
    _process(state, mapping, prio, ctx)
    ctx["listings"].clear()
    ctx["indexes"].clear()
    _leftovers(state, mapping, ctx)
    totals = _totals(state, mapping)
    try:
        previous = _read_previous(_previous(kind))
    except (OSError, UnicodeError, ValueError) as exc:
        previous = {}
        _issue(ctx, "note", "Vorbericht nicht lesbar – keine Deltas", "previous", str(exc))
    when = datetime.now().astimezone()
    name = f"{kind}_{when.strftime('%Y-%m-%d_%H-%M-%S-%f')}"
    watch, workers = _watch_lines(state), _worker_lines(state)
    text = _render(kind, when, totals, prio, previous) + "\n" + "\n".join(_summary_lines(ctx["issues"])) + "\n"
    text += f"\nAuffällige laufende Jobs: {len(watch)}\n" + "".join(f"{line}\n" for line in watch)
    text += f"\nWorker (Heartbeat): {len(workers)}\n" + "".join(f"{line}\n" for line in workers)
    if ctx["issues"]:
        text += f"\nDetails: errors/{name}_errors.txt\n"
    state["updated_at"] = _now()
    _save_state(state)
    path = reports_dir / f"{name}.txt"
    _write_new(path, text)
    if ctx["issues"]:
        _write_new(error_dir / f"{name}_errors.txt", _format_errors(ctx["issues"], when))
    _log(f"{kind}-Bericht: {path.name}; {sum(row[0] for row in totals.values())} aktive Clips; "
         f"{len(state['clips'])} Clips in der JSON; {len(ctx['issues'])} Meldungen; {len(watch)} auffällige Jobs; "
         f"Dauer: {perf_counter() - started:.1f} s.")
    return path


def _cycle() -> str | None:
    """Run one job cycle; returns the reason if it was skipped."""
    problems = _load_config()
    if cfg["report_only"]:
        return "Job-Zyklus übersprungen: report_only ist aktiv."
    if not state_path.exists():
        return "Job-Zyklus wartet auf den ersten Bericht (noch kein Zustand; Befehl 'report')."
    mapping = _load_mapping()
    _check_root()
    state = _load_state()
    ctx = _context()
    for problem in problems:
        _issue(ctx, "note", "Konfiguration", "config", problem)
    prio = _priority(mapping, state, ctx)
    _process(state, mapping, prio, ctx)
    known = {(item["category"], item["key"], item["detail"]) for item in state["notes"]}
    for item in ctx["issues"]:
        if item["section"] == "note" and (item["category"], item["key"], item["detail"]) not in known:
            state["notes"].append(item)
            known.add((item["category"], item["key"], item["detail"]))
    state["updated_at"] = _now()
    _save_state(state)
    return None


def _auto_due(now: datetime) -> bool:
    return now.time() >= cfg["auto_report_time"] and not any(reports_dir.glob(f"auto_{now:%Y-%m-%d}_*.txt"))


def _console(commands: queue.Queue[str]) -> None:
    while True:
        try:
            command = input("Marathon> ").strip().casefold()
        except EOFError:
            return
        commands.put(command)
        if command in ("quit", "exit"):
            return


# --------- MAIN ---------
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Marathon: Suchabgleich, Job-Steuerung und Berichte")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--manual", action="store_true", help="Manuellen Bericht erstellen und beenden")
    modes.add_argument("--auto-once", action="store_true", help="Auto-Bericht erstellen und beenden")
    modes.add_argument("--cycle-once", action="store_true", help="Einen Job-Zyklus ausführen und beenden")
    args = parser.parse_args(argv)
    _prepare()
    _acquire_lock()
    _log(f"{app_name} {app_version} gestartet.")
    if args.manual or args.auto_once:
        _report("manual" if args.manual else "auto")
        return
    if args.cycle_once:
        skipped = _cycle()
        if skipped:
            _log(skipped)
        return
    commands: queue.Queue[str] = queue.Queue()
    threading.Thread(target=_console, args=(commands,), daemon=True).start()
    _log("Marathon läuft. 'report' = manueller Bericht, 'quit' = beenden.")
    next_retry, next_cycle, last_problems, last_mode, last_skip = None, datetime.now().astimezone(), [], None, None
    while True:
        problems = _load_config()
        if problems != last_problems:
            for problem in problems:
                _log(problem)
            last_problems = problems
        if cfg["report_only"] != last_mode:
            _log("report_only aktiv: keine Jobs." if cfg["report_only"] else "Jobbetrieb aktiv.")
            last_mode = cfg["report_only"]
        now = datetime.now().astimezone()
        if _auto_due(now) and (next_retry is None or now >= next_retry):
            try:
                _report("auto")
                next_retry = None
            except Exception as exc:
                next_retry = now + timedelta(minutes=cfg["retry_minutes"])
                _log(f"Auto-Bericht fehlgeschlagen: {exc}; erneuter Versuch später.")
        if not cfg["report_only"] and now >= next_cycle:
            try:
                skipped = _cycle()
                if skipped and skipped != last_skip:
                    _log(skipped)
                last_skip = skipped
            except Exception as exc:
                _log(f"Job-Zyklus fehlgeschlagen: {exc}; Zustand unverändert.")
            next_cycle = now + timedelta(seconds=cfg["cycle_seconds"])
        try:
            command = commands.get(timeout=5)
        except queue.Empty:
            continue
        if command == "report":
            try:
                _report("manual")
            except Exception as exc:
                _log(f"Manueller Bericht fehlgeschlagen: {exc}")
        elif command in ("quit", "exit"):
            return
        elif command:
            _log("Befehle: report, quit")


# --------- EXEC ---------
if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print(f"Marathon abgebrochen: {exc}")
        try:
            tb_write_log(main_log, f"Marathon abgebrochen: {exc}")
        except OSError:
            pass
        raise SystemExit(1) from exc
