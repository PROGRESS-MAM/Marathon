# --------- IMPORTS ---------
import argparse
import configparser
import copy
import hashlib
import json
import stat
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
    "backups": "display_backups",
}
stages = ("restore", "transcode", "qc")  # Also the stage folder names.
stage_labels = {"restore": "Restore", "transcode": "Transcode", "qc": "QC"}
limit_keys = {stage: stage_labels[stage].casefold() for stage in stages}
job_boxes = ("offen", "laufend", "fertig", "archiv", "zurueckgezogen", "ausgang")
inbox, outbox, worker_dir = "eingang", "ausgang", "worker"
report_statuses = ("ok", "failed", "rejected")
system_files = frozenset({"thumbs.db", "desktop.ini", ".ds_store"})
busy_suffixes = (".tmp", ".part", ".partial")
protocol_suffixes = (".json", ".txt", ".log")
prio_columns = tuple(f"Prio {stage_labels[stage]}" for stage in stages)
queue_columns = tuple(f"Queue {stage_labels[stage]}" for stage in stages)
count_columns = ("Gesamt", "Bereit", *queue_columns)
columns = ("Kollektion", *prio_columns, "Gesamt", "Bereit", "%", *queue_columns)
summary_name = "Summe"
match_separator = "———"
invalid_path_chars = frozenset('<>:"/\\|?*' + "".join(map(chr, range(32))))
reserved_names = frozenset({"CON", "PRN", "AUX", "NUL", *(f"{kind}{number}" for kind in ("COM", "LPT") for number in range(1, 10))})
issue_sections = {
    "skipped": "Gefunden, aber nicht aufgenommen (letzter update-index, nicht in Gesamt)",
    "deviation": "Suche weicht von der JSON ab (letzter update-index, nicht übernommen)",
    "inactive": "In der JSON, aber nicht aktiv (nicht in Gesamt)",
    "final": "Auffällige Clip-Dateien in finalen Ablageordnern",
    "note": "Hinweise (betroffene Clips zählen weiter)",
}
index_sections = ("skipped", "deviation")
problem_categories = {  # kind: (category for new clips, category for clips already in the JSON)
    "missing": (None, "Nicht mehr in der Suche"),
    "multi": ("Clip-ID in mehreren Kollektionen", "Clip-ID jetzt in mehreren Kollektionen"),
    "invalid": ("Unvollständige oder widersprüchliche Metadaten",
                "Metadaten in der Suche jetzt unvollständig oder widersprüchlich"),
    "duplicate": ("Doppelter Identifier/Titel", None),
    "restore": ("Dateinamen und Hashes passen nicht zusammen", None),
}
metadata_changed = "Metadaten in der Suche geändert"
lost_proxy, lost_master = "Verloren – Proxy fehlt", "Verloren – Master fehlt vor Transcode"
qc_rejected, job_failed = "QC nicht bestanden", "Job endgültig fehlgeschlagen"
delivery_blocked, assignment_unclear = "Auslieferung blockiert", "Zuordnung beim Neuaufbau unklar"
status_codes = {delivery_blocked: "auslieferung_blockiert", assignment_unclear: "zuordnung_ungeklaert", lost_proxy: "verloren", lost_master: "verloren", qc_rejected: "qc_abgelehnt", job_failed: "fehlgeschlagen"}
commands_help = {
    "run": "Ordner und JSON anlegen, falls sie fehlen; dann Job-Schleife starten",
    "stop": "Job-Schleife anhalten",
    "auto-report": "Täglichen Auto-Bericht einschalten (ab auto_report_time)",
    "auto-report-off": "Täglichen Auto-Bericht ausschalten",
    "report": "Manuellen Bericht sofort erstellen",
    "create-folders": "Ordnerstruktur aller Kollektionen anlegen",
    "update-index": "Neue Suche; neue Clips aufnehmen, Abweichungen nur melden",
    "delete-folder": "SMB-Arbeitsordner bereinigen; Index behalten, Prozesszustand neu aufbauen",
    "status": "Anzeigen, was eingeschaltet ist",
    "help": "Diese Übersicht",
    "quit": "Marathon beenden",
}
command_aliases = {"exit": "quit", "manual-report": "report", "manueller-report": "report", "auto-report-on": "auto-report"}
missing_job_grace = timedelta(minutes=30)  # Before a vanished job file is recreated.
tracked_fields = {"collection": "Kollektion", "identifier": field_names["identifier"], "title": field_names["title"],
                  "clip_name_with_extension": field_names["clip_name"], "master_files": field_names["userpath"],
                  "filehashes": field_names["hash"]}

# --------- CONFIG ---------
app_name = "Marathon"
app_version = "1.2.0"
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
config_schema = {  # section: {key: kind}; all values and their explanations live in res/config.ini
    "paths": {"root_path": "text", "defa_dir": "name", "work_dir": "name", "defa_marker": "text",
              "proxy_prefix": "text", "cred_file": "text", "mapping_file": "text", "priority_file": "text"},
    "operation": {"auto_report_time": "time", "retry_minutes": "number"},
    "timing": {"cycle_seconds": "number", "max_job_attempts": "number"},
    "limits": {key: "count" for key in limit_keys.values()},
    "heartbeat": {"worker_timeout_minutes": "number", "max_job_hours": "number"},
}

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
def _parse_value(kind: str, raw: str):
    if not raw:
        raise ValueError("fehlt oder ist leer")
    if kind in ("count", "number"):
        minimum = int(kind == "number")
        if not raw.isdecimal() or int(raw) < minimum:
            raise ValueError(f"erwartet eine ganze Zahl ab {minimum}")
        return int(raw)
    if kind == "time":
        try:
            return time.fromisoformat(raw)
        except ValueError:
            raise ValueError("erwartet HH:MM") from None
    if kind == "name" and (any(char in invalid_path_chars for char in raw) or raw in (".", "..") or raw != raw.rstrip(". ")):
        raise ValueError("muss ein einfacher Ordnername sein")
    return raw


def _read_config() -> dict:
    parser = configparser.ConfigParser(interpolation=None)
    with config_path.open(encoding="utf-8-sig") as handle:
        parser.read_file(handle)
    problems = [f"[{section}] {key} ist unbekannt" for section in parser.sections() for key in parser[section]
                if key not in config_schema.get(section, {}) and (section, key) != ("timing", "stable_minutes")]
    values = {}
    for section, keys in config_schema.items():
        for key, kind in keys.items():
            try:
                values[key] = _parse_value(kind, parser.get(section, key, fallback="").strip())
            except ValueError as exc:
                problems.append(f"[{section}] {key}: {exc}")
    for key in ("mapping_file", "cred_file"):
        if key in values and not (res_dir / values[key]).is_file():
            problems.append(f"[paths] {key}: Datei {res_dir / values[key]} fehlt")
    if problems:
        raise ValueError("; ".join(problems))
    return values


def _load_config() -> str | None:
    """Load res/config.ini into cfg; returns the reason why Marathon has to pause instead."""
    try:
        values = _read_config()
    except FileNotFoundError:
        return f"{config_path} fehlt – Marathon pausiert, bis die Datei vorhanden ist."
    except (OSError, UnicodeError, configparser.Error, ValueError) as exc:
        return f"{config_path.name} fehlerhaft – Marathon pausiert, bis sie korrigiert ist: {exc}"
    changed = [key for key in config_schema["paths"] if cfg and values[key] != cfg[key]]
    if changed:
        return (f"Änderung in [paths] ({', '.join(changed)}) – Marathon pausiert; "
                f"Neustart nötig oder Änderung zurücknehmen.")
    cfg.update(values)
    return None


# --------- FUNC: SETUP ---------
def _res(key: str) -> Path:
    return res_dir / cfg[key]


def _prepare() -> None:
    for folder in (res_dir, log_dir, state_dir, reports_dir, error_dir):
        folder.mkdir(parents=True, exist_ok=True)
    if any(path != state_path for path in state_dir.glob("*.json")):
        raise RuntimeError("Weitere JSON-Datei in state gefunden; bitte Quelle des Zustands klären.")


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
    work_key = cfg["work_dir"].rstrip(". ").casefold()
    if work_key in {_final_folder(entry["name"]).rstrip(". ").casefold() for entry in entries}:
        raise ValueError("Arbeitsordner und finaler Ablageordner dürfen nicht denselben Namen haben.")
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
    return {"issues": [], "listings": {}, "indexes": {}, "final_counts": {}}


def _issue(ctx: dict, section: str, category: str, key: str, detail: str) -> None:
    ctx["issues"].append({"section": section, "category": category, "key": key, "detail": detail})


def _clip_text(item: dict) -> str:
    return (f"Kollektion={item['collection']}, {field_names['clip_id']}={item['clip_id']}, "
            f"{field_names['identifier']}={item['identifier']}, {field_names['title']}={item['title']}")


def _joined(values) -> str:
    return " | ".join(values)


def _detail(head: str, reason: str = "", matches: list[str] | None = None) -> str:
    """Format A: one line. Format B (several matches, one expected): head, separator, one match per line."""
    if matches:
        return "\n".join((head, match_separator, *matches))
    return f"{head}: {reason}" if reason else head


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


def _set_issue(clip: dict, kind: str, category: str | None = None, detail: str = "", matches: list[str] | None = None) -> None:
    old = clip["issues"].get(kind)
    if category is None:
        clip["issues"][kind] = None
        return
    since = old["since"] if old and old["category"] == category else _now()
    clip["issues"][kind] = {"category": category, "detail": detail, "matches": matches, "since": since}


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
    source = _safe_work_path(relative)
    target_name = name or source.name
    if _file_name(target_name) != target_name or any(char in invalid_path_chars for char in target_name):
        raise ValueError(f"Unsicherer Arbeitsdateiname: {target_name!r}")
    target = _safe_work_path(target_folder) / target_name
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
        path = _safe_work_path(relative)
        _work_inventory([relative])
        shutil.rmtree(path)
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        _issue(ctx, "note", category, relative, f"{relative}: {exc}")


def _rmdir(relative: str) -> None:
    try:
        _safe_work_path(relative).rmdir()
    except (OSError, ValueError):
        pass  # Not empty, outside work folders or already gone.


class DeliveryBlocked(Exception):
    pass


def _is_link(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _safe_work_path(relative: str) -> Path:
    """Allow only root/work_dir and root/<collection>/work_dir; reject links and path aliases."""
    parts = relative.split("/")
    if any(not part or part in (".", "..") or part != part.rstrip(". ") or
           any(char in invalid_path_chars for char in part) for part in parts):
        raise ValueError(f"Unsicherer Arbeitsordner-Pfad: {relative}")
    work = cfg["work_dir"].casefold()
    positions = [i for i, part in enumerate(parts) if part.casefold() == work]
    if not positions or positions[0] not in (0, 1):
        raise ValueError(f"Nicht innerhalb eines Marathon-Arbeitsordners: {relative}")
    root = Path(cfg["root_path"])
    path = root
    for part in parts:
        path /= part
        if os.path.lexists(path) and _is_link(path):
            raise ValueError(f"Verknüpfung/Junction wird nicht verändert: {relative}")
    return path


def _deliver_proxy(relative: str, final: str, name: str) -> None:
    """Deliver without overwriting final files, even when a file arrives after the existence check."""
    source = _safe_work_path(relative)
    target = _path(final) / name
    if _file_name(name) != name or any(c in invalid_path_chars for c in name):
        raise DeliveryBlocked(f"Unsicherer Proxy-Dateiname: {name!r}; Proxy und Master bleiben erhalten")
    if any(key == name.casefold() for key in _scan(final)) or os.path.lexists(target):
        raise DeliveryBlocked(f"Namenskonflikt: {target}; neuer Proxy={source}; Proxy und Master bleiben erhalten")
    try:
        if os.name == "nt":
            os.rename(source, target)  # Windows refuses an existing target.
        else:
            size = source.stat().st_size
            with source.open("rb") as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
                writer.flush()
                os.fsync(writer.fileno())
            if source.stat().st_size != size or target.stat().st_size != size:
                raise DeliveryBlocked(f"Dateigröße bei Auslieferung nach {target} geändert; Quelldatei und Master bleiben erhalten")
            source.unlink()
    except FileExistsError:
        raise DeliveryBlocked(f"Namenskonflikt: {target}; Proxy und Master bleiben erhalten") from None
    except OSError as exc:
        raise DeliveryBlocked(f"Auslieferung nach {target} nicht möglich: {exc}; Master bleibt erhalten") from exc
    if not target.is_file() or target.stat().st_size == 0:
        raise DeliveryBlocked(f"Auslieferung nach {target} konnte nicht bestätigt werden; Master bleibt erhalten")


def _work_roots(mapping: list[dict], state: dict) -> list[str]:
    """Include former collection work roots directly below root, but never search in AQC or other subfolders."""
    work = cfg["work_dir"]
    roots = {work} | {f"{_final_folder(c)}/{work}" for c in
                     [*(e["name"] for e in mapping), *(c["collection"] for c in state["clips"].values())]}
    for folder in _subfolders(""):
        if folder.casefold() == work.casefold():
            continue
        candidate = f"{folder}/{work}"
        if os.path.lexists(_path(candidate)):
            roots.add(candidate)
    result = []
    seen = set()
    for relative in sorted(roots, key=str.casefold):
        path = _safe_work_path(relative)
        if os.path.lexists(path):
            if not path.is_dir():
                raise ValueError(f"Arbeitsordner ist keine normale Ordnerstruktur: {relative}")
            key = str(path.resolve()).casefold()
            if key not in seen:
                seen.add(key)
                result.append(relative)
    return result


def _work_inventory(roots: list[str]) -> dict[str, tuple[str, int, int]]:
    """Snapshot all entries; any links, special files or unreadable folders block deletion."""
    entries = {}
    for relative in roots:
        pending = [_safe_work_path(relative)]
        while pending:
            path = pending.pop()
            if _is_link(path):
                raise ValueError(f"Verknüpfung/Junction im Löschumfang: {path}")
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) and not stat.S_ISREG(info.st_mode):
                raise ValueError(f"Kein normaler Ordner oder normale Datei: {path}")
            is_dir = stat.S_ISDIR(info.st_mode)
            key = path.relative_to(Path(cfg["root_path"])).as_posix()
            entries[key] = ("dir" if is_dir else "file", info.st_size, info.st_mtime_ns)
            if is_dir:
                pending.extend(path.iterdir())
    return dict(sorted(entries.items()))


def _busy_workers(entries: dict[str, tuple[str, int, int]]) -> list[str]:
    """Fail closed for unfinished running jobs or recent/invalid worker heartbeats."""
    problems, finished = [], set()
    for relative, (kind, _, _) in entries.items():
        path = Path(relative)
        if kind != "file" or path.suffix.casefold() != ".json" or path.parent.name != "fertig":
            continue
        try:
            report = json.loads(_path(relative).read_text(encoding="utf-8"))
            if _report_problem(report) is None and report["job_id"] == path.stem:
                finished.add((path.parent.parent.as_posix(), report["job_id"]))
        except (OSError, ValueError, UnicodeError):
            continue
    for relative, (kind, _, mtime) in entries.items():
        parts = relative.split("/")
        if kind != "file":
            continue
        if "laufend" in parts:
            pos = parts.index("laufend")
            job_id = Path(parts[-1]).stem
            if Path(parts[-1]).suffix.casefold() == ".json" and ("/".join(parts[:pos]), job_id) not in finished:
                problems.append(f"Laufender/ungeklärter Job: {relative}")
        if len(parts) == 3 and parts[:2] == [cfg["work_dir"], worker_dir]:
            try:
                data = json.loads(_path(relative).read_text(encoding="utf-8"))
                if not isinstance(data, dict) or "job_id" not in data:
                    raise ValueError("ungültiger Heartbeat")
                fresh = datetime.now().timestamp() - mtime / 1_000_000_000 < cfg["worker_timeout_minutes"] * 60
                if fresh or data["job_id"]:
                    problems.append(f"Worker noch aktiv oder Job gemeldet: {relative}")
            except (OSError, ValueError, UnicodeError):
                problems.append(f"Worker-Status nicht prüfbar: {relative}")
    return problems


def _cleanup_plan() -> dict:
    mapping = _load_mapping()
    _check_root()
    state = _load_state()
    roots = _work_roots(mapping, state)
    entries = _work_inventory(roots)
    busy = _busy_workers(entries)
    if busy:
        raise RuntimeError("Bereinigung blockiert. Worker zuerst beenden und laufende Jobs klären.\n" + "\n".join(busy))
    clips = [relative for relative, (kind, _, _) in entries.items() if kind == "file" and
             Path(relative).suffix.casefold() not in protocol_suffixes and
             Path(relative).name.casefold() not in system_files]
    # A .part/.tmp may itself contain media. Never delete it without a confirmation.
    clips += [relative for relative, (kind, _, _) in entries.items() if kind == "file" and
              Path(relative).suffix.casefold() in busy_suffixes]
    fingerprint = hashlib.sha256(state_path.read_bytes()).hexdigest() if state_path.exists() else None
    return {"roots": roots, "entries": entries, "clips": sorted(set(clips)), "state_hash": fingerprint}


def _rebuild_process_state(state: dict) -> dict:
    """Keep index, metadata and history; rediscover remaining files without search, jobs or directory creation."""
    ctx, groups = _context(), defaultdict(list)
    for clip in state["clips"].values():
        groups[(_normalize(clip["identifier"]), _normalize(clip["title"]))].append(clip["clip_id"])
    for clip in state["clips"].values():
        previous = _position(clip)
        collection, clip_id = clip["collection"], clip["clip_id"]
        clip.update(job=None, attempts=0, ready=False, active=True, stage="restore", status="wartet", queued_at=_stamp())
        clip["files"] = {"master": None, "proxy": None}
        clip["issues"] = {"file": None, "sticky": None}
        found = [(folder, source, _lookup(ctx, folder, clip["identifier"], clip["title"])) for folder, source in
                 [(_final_folder(collection), "Zielordner"), (_qc_inbox(collection), "QC-Eingang")]]
        group = groups[(_normalize(clip["identifier"]), _normalize(clip["title"]))]
        crowded = [f"{folder}/{name}" for folder, _, names in found if len(names) > 1 for name in names]
        if len(group) > 1:
            _set_issue(clip, "sticky", assignment_unclear, "Doppelte Index-Zuordnung",
                       [f"Kollektion={state['clips'][other]['collection']}, {field_names['clip_id']}={other}"
                        for other in sorted(group, key=int)])
        elif crowded:
            _set_issue(clip, "sticky", assignment_unclear, "Mehrere Proxy-Dateien gefunden", crowded)
        else:
            proxy = next(((folder, names[0], source) for folder, source, names in found if names), None)
            missing = _missing_masters(ctx, collection, clip_id, clip["master_files"])
            if missing is not None:
                clip["files"]["master"] = {"folder": _master_folder(collection, clip_id),
                                           "names": list(clip["master_files"]), "source": "Neuaufbau", "last_seen_at": _now()}
            if proxy:
                clip["files"]["proxy"] = _file_entry(*proxy)
                clip.update(ready=proxy[2] == "Zielordner", stage=None if proxy[2] == "Zielordner" else "qc")
            elif missing == []:
                clip["stage"] = "transcode"
            elif not clip["master_files"] or len(clip["master_files"]) != len(clip["filehashes"]):
                _set_issue(clip, "sticky", assignment_unclear,
                           f"Dateinamen und Hashes reichen nicht für Restore; {field_names['userpath']}={_joined(clip['master_files'])}, "
                           f"{field_names['hash']}={_joined(clip['filehashes'])}, {field_names['backups']}={_joined(clip['lto_tapes'])}")
        _update_activity(clip, ctx)
        clip["status"] = _status(clip)
        _event(clip, "Prozesszustand nach Bereinigung neu aufgebaut", f"Vorher: {previous}")
    state.update(workers={}, files_seen={}, updated_at=_now())
    _keep_notes(state, [dict(item, section="note") for item in ctx["issues"]])
    return state


def _delete_folders(plan: dict) -> None:
    """Execute only an unchanged preflight; persist a marker before the first irreversible deletion."""
    fresh = _cleanup_plan()
    if fresh != plan:
        raise RuntimeError("Dateien, Worker oder JSON haben sich geändert. Nichts gelöscht; 'delete-folder' erneut eingeben.")
    state = _load_state()
    had_state = state_path.exists()
    if had_state:
        state["cleanup"] = {"pending": True, "at": _now(), "folders": plan["roots"]}
        _save_state(state)
    _log(f"Bereinigung beginnt: {len(plan['roots'])} Arbeitsordner, {len(plan['clips'])} Clip-/Mediendateien.")
    errors = []
    for relative in plan["roots"]:
        try:
            path = _safe_work_path(relative)
            _work_inventory([relative])
            shutil.rmtree(path)
            if os.path.lexists(path):
                raise OSError("Arbeitsordner nach Löschung weiterhin vorhanden")
            _log(f"Arbeitsordner gelöscht: {relative}")
        except (OSError, ValueError) as exc:
            errors.append(f"{relative}: {exc}")
    ensured_folders.clear()
    if had_state:
        state = _rebuild_process_state(state)
        state["cleanup"] = {"pending": bool(errors), "at": _now(), "folders": plan["roots"], "errors": errors}
        _save_state(state)
        if _load_state() != state:
            raise RuntimeError("JSON-Neuaufbau konnte nicht bestätigt werden; Job-Schleife bleibt aus.")
    if errors:
        raise RuntimeError("Bereinigung unvollständig; Job-Schleife bleibt aus.\n" + "\n".join(errors))
    _log(f"Bereinigung abgeschlossen: {len(plan['roots'])} Arbeitsordner entfernt. "
         "Finale Dateien erhalten; Index behalten; Job-Schleife bleibt aus.")


def _begin_delete() -> dict | None:
    plan = _cleanup_plan()
    _log(f"Löschumfang: {len(plan['roots'])} Arbeitsordner samt Unterordnern:\n" + "\n".join(plan["roots"]))
    if not plan["roots"]:
        if state_path.exists() and _load_state().get("cleanup", {}).get("pending"):
            _delete_folders(plan)
        else:
            _log("Keine Marathon-Arbeitsordner auf dem SMB gefunden.")
        return None
    if plan["clips"]:
        _log(f"WARNUNG: {len(plan['clips'])} Clip-/Mediendateien werden unwiderruflich gelöscht:\n" +
             "\n".join(plan["clips"]) + "\nZum Bestätigen 'loeschen' eingeben, sonst 'abbrechen'.")
        return plan
    _delete_folders(plan)
    return None


def _ensure_folders(mapping: list[dict], force: bool = False) -> int:
    """Create missing work and stage folders; returns how many were created."""
    folders = {cfg["work_dir"], f"{cfg['work_dir']}/{worker_dir}"}
    for entry in mapping:
        for stage in stages:
            base = _stage_folder(entry["name"], stage)
            folders |= {f"{base}/{box}" for box in (*job_boxes, *((inbox,) if stage != "restore" else ()))}
    parts = [relative.split("/") for relative in folders]
    folders |= {"/".join(items[:end]) for items in parts for end in range(1, len(items))}
    created = 0
    for relative in sorted(folders):  # Parents sort before their children.
        if cfg["work_dir"] in relative.split("/"):
            _safe_work_path(relative)
        if force or relative not in ensured_folders:
            if not _path(relative).is_dir():
                _path(relative).mkdir(parents=True, exist_ok=True)
                created += 1
            ensured_folders.add(relative)
    return created


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
    fields = ("identifier", "title", "clip_name")
    seen = {field: list(dict.fromkeys(value for row in rows for value in row[field])) for field in fields}
    hit.update(identifier=" / ".join(seen["identifier"]), title=" / ".join(seen["title"]))  # Shown in error lines.
    problems = [f"{field_names[field]}: {len(row[field])} Werte" for row in rows for field in fields if len(row[field]) != 1]
    if problems:
        hit["invalid"] = ("; ".join(dict.fromkeys(problems)), None)
        return hit
    conflicts = [f"{field_names[field]}={value}" for field in fields if len(seen[field]) > 1 for value in seen[field]]
    if conflicts:
        hit["invalid"] = ("Widersprüchlich", conflicts)
        return hit
    tapes = {}
    for tape in (tape for row in rows for value in row["backups"] for tape in map(str.strip, value.split(",")) if tape):
        tapes.setdefault(tape.casefold(), tape)  # Keep the first spelling.
    if not tapes:
        raw = "; ".join(value for row in rows for value in row["backups"])
        hit["invalid"] = (f"keine LTO-Tapenummer; {field_names['backups']}={raw!r}", None)
        return hit
    names = {_file_name(path).casefold(): _file_name(path) for row in rows for path in row["userpath"] if _file_name(path)}
    hashes = {value.casefold(): value for row in rows for value in row["hash"]}
    masters, hash_list = (sorted(values.values(), key=str.casefold) for values in (names, hashes))
    restore_problem = None if masters and len(masters) == len(hash_list) else (
        f"{len(masters)} Dateinamen ({field_names['userpath']}), {len(hash_list)} Hashes; "
        f"{field_names['userpath']}={_joined(masters)}, {field_names['hash']}={_joined(hash_list)}, "
        f"{field_names['backups']}={_joined(tapes.values())}")
    hit.update({field: seen[field][0] for field in fields}, hashes=hash_list, masters=masters,
               lto_tapes=list(tapes.values()), restore_problem=restore_problem)
    return hit


def _raw_text(row) -> str:
    if not isinstance(row, (list, tuple)):
        return f"Rohwert={row!r}"
    text = ", ".join(f"{field}={value!r}" for field, value in zip(field_names.values(), row))
    return text + (f", weitere Werte={list(row[len(field_names):])!r}" if len(row) > len(field_names) else "")


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
                _issue(ctx, "skipped", invalid_category, f"{name}#{number}",
                       f"Kollektion={name}, Trefferzeile={number}: Rückgabefelder unvollständig oder kein Text; {_raw_text(row)}")
                continue
            values = {key: _values(raw) for key, raw in zip(keys, row)}
            if "placeholder" in (flag.casefold() for flag in values["status_flags"]):
                placeholders += 1
                continue  # Placeholders are ignored completely, also in the error report.
            ids = values["clip_id"]
            if len(ids) != 1 or not (ids[0].isascii() and ids[0].isdecimal()):
                _issue(ctx, "skipped", invalid_category, f"{name}#{number}",
                       f"Kollektion={name}, Trefferzeile={number}: {field_names['clip_id']} ungültig; {_raw_text(row)}")
                continue
            found[ids[0]].setdefault(name, {"collection": name, "clip_id": ids[0], "invalid": None, "rows": []})["rows"].append(values)
        _log(f"API-Suche abgeschlossen: {name!r}: {len(matches)} Trefferzeilen, davon {placeholders} Platzhalter; "
             f"{perf_counter() - started:.1f} s.")
    return {clip_id: [_merge_hit(hit) for hit in hits.values()] for clip_id, hits in found.items()}


# --------- FUNC: PROXY FILES ---------
def _proxy_parts(name: str) -> tuple[str, str] | None:
    prefix = cfg["proxy_prefix"] + "__"
    if not name.casefold().startswith(prefix.casefold()):
        return None
    identifier, separator, title = name[len(prefix):].partition("__")
    if not separator or not identifier.strip() or not title.strip():
        return None
    return identifier, title


def _proxy_keys(name: str) -> list[tuple[str, str]] | None:
    parts = _proxy_parts(name)
    if parts is None:
        return None
    identifier, title = parts
    return list(dict.fromkeys((_normalize(identifier), _normalize(value)) for value in (title, Path(title).stem)))


def _proxy_text(name: str) -> str:
    parts = _proxy_parts(name)
    return f", {field_names['identifier']}={parts[0]}, {field_names['title']}={Path(parts[1]).stem}" if parts else ""


def _proxy_index(ctx: dict, folder: str) -> dict:
    if folder in ctx["indexes"]:
        return ctx["indexes"][folder]
    index = defaultdict(list)
    for name, size in _listing(ctx, folder).values():
        skip = _ignored(name) or name.casefold().endswith(protocol_suffixes) or not size
        for key in (None if skip else _proxy_keys(name)) or ():
            if name not in index[key]:
                index[key].append(name)
    ctx["indexes"][folder] = index
    return index


def _lookup(ctx: dict, folder: str, identifier: str, title: str) -> list[str]:
    return sorted(_proxy_index(ctx, folder).get((_normalize(identifier), _normalize(title)), []), key=str.casefold)


# --------- FUNC: STATE ---------
def _empty_state() -> dict:
    return {"schema_version": 4, "priority": None, "notes": [], "index": {"updated_at": None, "issues": []},
            "workers": {}, "files_seen": {}, "clips": {}}


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
                         "'run' oder 'update-index' baut den Index neu auf.")
    if version not in (3, 4) or not isinstance(state.get("clips"), dict):
        raise ValueError("Unbekanntes Zustandsformat; keine Aktualisierung.")
    for key, default in _empty_state().items():
        state.setdefault(key, default)
    if version == 3:  # Version 3 tracked search problems per clip; now the JSON itself is the index.
        state["schema_version"] = 4
        for clip in state["clips"].values():
            for key, item in (("issues", "search"), ("job", "outdated")):
                if isinstance(clip, dict) and isinstance(clip.get(key), dict):
                    clip[key].pop(item, None)
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
def _classify(clip_id: str, hits: list[dict]) -> tuple[dict | None, dict | None]:
    """Return the usable hit or a problem with kind, reason and optional head/matches for format B."""
    if not hits:
        return None, {"kind": "missing", "reason": "Nicht mehr in der Suche gefunden (Metadaten nicht abrufbar oder Kollektion geändert)"}
    if len(hits) > 1:
        matches = [f"Kollektion={hit['collection']}, {field_names['identifier']}={hit['identifier']}, {field_names['title']}={hit['title']}"
                   for hit in sorted(hits, key=lambda hit: hit["collection"].casefold())]
        return None, {"kind": "multi", "head": f"{field_names['clip_id']}={clip_id}", "matches": matches}
    if hits[0]["invalid"]:
        reason, matches = hits[0]["invalid"]
        return None, {"kind": "invalid", "reason": reason, "matches": matches}
    return hits[0], None


def _new_clip(clip_id: str, hit: dict) -> dict:
    return {"clip_id": clip_id, "collection": hit["collection"], "identifier": hit["identifier"],
            "title": hit["title"], "clip_name_with_extension": hit["clip_name"], "filehashes": hit["hashes"],
            "master_files": hit["masters"], "lto_tapes": hit["lto_tapes"], "status": "wartet", "active": True, "ready": False, "stage": "restore",
            "queued_at": _stamp(), "preset": None, "job": None, "job_count": 0, "attempts": 0,
            "files": {"master": None, "proxy": None},
            "issues": {"file": None, "sticky": None}, "history": []}


def _missing_masters(ctx: dict, collection: str, clip_id: str, names: list[str]) -> list[str] | None:
    """Master names missing in the clip's transcode inbox; None if that folder does not exist."""
    if not names or clip_id not in _dirs(ctx, _master_root(collection)):
        return None
    return [name for name in names if not _has_file(ctx, _master_folder(collection, clip_id), name)]


def _admit(clips: dict, clip_id: str, hit: dict, ctx: dict) -> None:
    collection, identifier, title = hit["collection"], hit["identifier"], hit["title"]
    text = _clip_text(hit)
    places = [(_final_folder(collection), "Zielordner"), (_qc_inbox(collection), "QC-Eingang")]
    found = [(folder, source, _lookup(ctx, folder, identifier, title)) for folder, source in places]
    crowded = [f"{folder}/{name}" for folder, _, names in found if len(names) > 1 for name in names]
    if crowded:
        _issue(ctx, "skipped", "Mehrere Proxy-Dateien gefunden", clip_id, _detail(text, matches=crowded))
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
        _event(clip, "Aufgenommen – wartet auf Restore", ", ".join(hit["masters"]))
    clips[clip_id] = clip


def _changes(clip: dict, hit: dict) -> str:
    new = {"collection": hit["collection"], "identifier": hit["identifier"], "title": hit["title"],
           "clip_name_with_extension": hit["clip_name"], "master_files": hit["masters"], "filehashes": hit["hashes"]}
    return "; ".join(f"{label}: {clip[key]!r} → {new[key]!r}" for key, label in tracked_fields.items() if clip[key] != new[key])


def _reconcile(state: dict, found: dict[str, list[dict]], ctx: dict) -> None:
    """Admit new clips; for clips already in the JSON differences are only reported, the JSON stays the index."""
    clips = state["clips"]
    classified = {clip_id: _classify(clip_id, found.get(clip_id, [])) for clip_id in {*found, *clips}}
    groups, sources = defaultdict(list), {}
    for clip_id, (hit, _) in classified.items():
        source = clips.get(clip_id) or hit
        if source:
            sources[clip_id] = source
            groups[(_normalize(source["identifier"]), _normalize(source["title"]))].append(clip_id)
    for group in (sorted(group, key=int) for group in groups.values() if len(group) > 1):
        first = sources[group[0]]
        problem = {"kind": "duplicate",
                   "head": f"{field_names['identifier']}={first['identifier']}, {field_names['title']}={first['title']}",
                   "matches": [f"Kollektion={sources[clip_id]['collection']}, {field_names['clip_id']}={clip_id}" for clip_id in group]}
        for clip_id in (clip_id for clip_id in group if clip_id not in clips):
            classified[clip_id] = (None, problem)
    for clip_id in sorted(classified, key=int):
        (hit, problem), clip = classified[clip_id], clips.get(clip_id)
        if clip is None and problem is None:
            _admit(clips, clip_id, hit, ctx)
        elif problem:
            section, index = ("deviation", 1) if clip else ("skipped", 0)
            head = problem.get("head") or _clip_text(clip or found[clip_id][0])
            _issue(ctx, section, problem_categories[problem["kind"]][index], clip_id,
                   _detail(head, problem.get("reason", ""), problem.get("matches")))
        elif changes := _changes(clip, hit):
            _issue(ctx, "deviation", metadata_changed, clip_id, _detail(_clip_text(clip), changes))


# --------- FUNC: WORKERS ---------
# Worker rules (provisional until the tools exist; paths are relative to the share root with "/" as separator):
# - Heartbeat at least once a minute: <root>/<work_dir>/worker/<worker>.json, written via temporary name + rename:
#   {"worker": str, "stage": "Restore" | "Transcode" | "QC", "host": str, "job_id": str | null, "beat": <changes each time>}
# - Read <root>/<work_dir>/priority.json and walk the collections of the own stage in the given order.
# - Take the first *.json in "offen" (sorted by name) by renaming it into "laufend/<worker>/";
#   if the rename fails because the file is gone, another worker was faster: try the next file.
# - Read inputs only where the job says; write results only into the job's output_folder (ausgang/<job_id>).
#   Restore: all names from "files" (restored via "hashes"); Transcode: exactly one proxy named by the proxy scheme,
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
        _deliver_proxy(source, final, proxy["name"])
        clip["files"]["proxy"] = _file_entry(final, proxy["name"], "QC")
        master = clip["files"]["master"]
        if master and not master.get("deleted_at"):
            _remove_tree(master["folder"], ctx, "Master nicht löschbar (bleiben liegen)")
            if not _path(master["folder"]).exists():
                master["deleted_at"] = _now()
        clip.update(ready=True, stage=None)
        _event(clip, "Bereit", f"{final}/{proxy['name']}")
    return None


def _apply_report(clip: dict, job: dict, report: dict, worker: str | None, ctx: dict) -> None:
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
        _event(clip, f"{label}-Job fertig", by + (f", Preset {report['preset']}" if report.get("preset") else ""))
        try:
            problem = _take_outputs(clip, job, report, ctx)
        except DeliveryBlocked as exc:
            _set_issue(clip, "sticky", delivery_blocked, job_text(str(exc)))
            _event(clip, delivery_blocked, str(exc))
            _finish_output(job, True, ctx)
            return
        if problem is None:
            clip["attempts"] = 0
            _finish_output(job, True, ctx)
            return
        status, result = "failed", problem
    if status == "rejected":
        _set_issue(clip, "sticky", qc_rejected, job_text(result))
        _event(clip, qc_rejected, f"{by}: {result}")
        _finish_output(job, True, ctx)
        return
    clip["attempts"] += 1
    _event(clip, f"{label}-Job fehlgeschlagen", f"{by}: {result}")
    _finish_output(job, False, ctx)
    if clip["attempts"] >= cfg["max_job_attempts"]:
        _set_issue(clip, "sticky", job_failed, job_text(result))
    else:
        _issue(ctx, "note", "Job fehlgeschlagen – neuer Versuch", clip["clip_id"], _detail(_clip_text(clip), job_text(result)))


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
    elif _age(job["missing_since"]) >= missing_job_grace:
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
    if job["state"] == "laufend":
        return False
    if job["state"] == "offen" and not _move(f"{job['folder']}/offen/{job['file']}", f"{job['folder']}/zurueckgezogen"):
        return False  # A worker took it meanwhile.
    _rmdir(job["output_folder"])
    clip["job"] = None
    _event(clip, "Job zurückgezogen", job["file"])
    return True


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
    reasons = [reason for reason in (clip["issues"][kind] for kind in ("sticky", "file")) if reason]
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
               _detail(f"{_clip_text(clip)}; letzter Stand: {_position(clip)}; {reason['detail']}; seit {reason['since']}{last_text}",
                       matches=reason["matches"]))


def _status(clip: dict) -> str:
    for kind in ("sticky", "file"):
        if clip["issues"][kind]:
            return status_codes.get(clip["issues"][kind]["category"], "inaktiv")
    if clip["ready"]:
        return "bereit"
    return "laufend" if clip["job"] and clip["job"]["state"] == "laufend" else "wartet"


def _final_audit(state: dict, mapping: list[dict], ctx: dict) -> None:
    """Count unexpected and unknown final files without changing files or JSON status."""
    by_key, by_name = defaultdict(dict), defaultdict(dict)
    clips = state["clips"]
    for clip_id, clip in clips.items():
        by_key[(_normalize(clip["identifier"]), _normalize(clip["title"]))][clip_id] = clip
        proxy = clip["files"].get("proxy")
        if proxy:
            by_name[proxy["name"].casefold()][clip_id] = clip
    finals = {_final_folder(entry["name"]) for entry in mapping} | {_final_folder(c["collection"]) for c in clips.values()}
    counts, matched = {}, defaultdict(list)
    for final in sorted(finals, key=str.casefold):
        counts[final] = {"unknown": 0, "unexpected": 0}
        for name, size in sorted(_listing(ctx, final).values()):
            if _ignored(name) or name.casefold().endswith(protocol_suffixes):
                continue
            candidates = dict(by_name.get(name.casefold(), {}))
            for key in _proxy_keys(name) or ():
                candidates.update(by_key.get(key, {}))
            relative = f"{final}/{name}"
            if len(candidates) != 1:
                counts[final]["unknown"] += 1
                matches = [_clip_text(candidates[clip_id]) for clip_id in sorted(candidates, key=int)]
                _issue(ctx, "final", "Unbekannte finale Clip-Datei", relative,
                       _detail(f"Fundort={relative}{_proxy_text(name)}", "Kein JSON-Eintrag zuordenbar", matches))
                continue
            clip_id, clip = next(iter(candidates.items()))
            matched[clip_id].append((final, name, size, clip))
    for files in matched.values():
        for final, name, size, clip in files:
            proxy = clip["files"].get("proxy")
            expected = f"{proxy['folder']}/{proxy['name']}" if proxy else "Kein Proxy im JSON vermerkt"
            actual = f"{final}/{name}"
            reasons = []
            if clip["status"] != "bereit" or not clip["ready"] or clip["stage"] is not None or not clip["active"]:
                reasons.append(f"JSON: Status={clip['status']}, Stufe={clip['stage']}, aktiv={clip['active']}")
            if _final_folder(clip["collection"]).casefold() != final.casefold():
                reasons.append(f"Falscher Ablageordner; final erwartet={_final_folder(clip['collection'])}")
            if not proxy or expected.casefold() != actual.casefold():
                reasons.append(f"JSON-Fundort abweichend; erwartet={expected}")
            if len(files) > 1:
                reasons.append("Mehrere finale Dateien für diesen Clip")
            if not size:
                reasons.append("Datei ist leer")
            if reasons:
                counts[final]["unexpected"] += 1
                _issue(ctx, "final", "Unerwartete finale Clip-Datei", actual,
                       _detail(f"Fundort={actual}; {_clip_text(clip)}; " + "; ".join(reasons),
                               matches=[f"{f}/{n}" for f, n, _, _ in files] if len(files) > 1 else None))
    ctx["final_counts"] = counts


def _final_lines(ctx: dict) -> list[str]:
    counts = ctx["final_counts"]
    unknown = sum(row["unknown"] for row in counts.values())
    unexpected = sum(row["unexpected"] for row in counts.values())
    return ["Finale Ablage (Dateianzahl, gemeinsamer DEFA-Ordner nur einmal):",
            "Ablageordner | Unbekannt | Unerwartet", *[
                f"{folder} | {row['unknown']} | {row['unexpected']}" for folder, row in counts.items()],
            f"Summe | {unknown} | {unexpected}"]


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
                _issue(ctx, "note", "Datei ohne passenden Clip (QC-Eingang)", f"{folder}/{key}", f"{folder}/{name}{_proxy_text(name)}")


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


def _schedule(state: dict, prio: dict[str, list[str]], ctx: dict) -> None:
    clips = state["clips"].values()
    for clip in clips:
        job = clip["job"]
        expected = None if clip["ready"] else _stage_folder(clip["collection"], clip["stage"])
        if job and (not clip["active"] or job["folder"] != expected or job["stage"] != clip["stage"]):
            _withdraw(clip)
    for stage in stages:
        ranks = {name: rank for rank, name in enumerate(prio[stage])}
        pool = sorted((clip for clip in clips if clip["active"] and not clip["ready"] and clip["stage"] == stage and
                       (not clip["job"] or clip["job"]["state"] == "offen")),
                      key=lambda clip: (ranks.get(clip["collection"], len(ranks)), clip["queued_at"]))
        limit = cfg[limit_keys[stage]]
        for clip in pool[limit:]:
            if clip["job"]:
                _withdraw(clip)
        for clip in pool[:limit]:
            if clip["job"] is None:
                _create_job(clip)


def _process(state: dict, mapping: list[dict], prio: dict[str, list[str]], ctx: dict, writing: bool) -> None:
    """Evaluate all clips; writing=False only reads the share (reports)."""
    clips = state["clips"]
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
        _set_issue(clip, "file", *_check_files(clip, ctx))
        _update_activity(clip, ctx)
    if writing:
        _schedule(state, prio, ctx)
    for clip in clips.values():
        clip["status"] = _status(clip)
    state["files_seen"] = {}  # Compatibility with states from earlier versions.


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


def _format_errors(issues: list[dict], when: datetime, title: str = "Fehlerbericht") -> str:
    lines = [f"{app_name} {app_version} | {title} | {when.isoformat(timespec='seconds')}", "", *_summary_lines(issues)]
    for section, heading in issue_sections.items():
        grouped = defaultdict(list)
        for item in issues:
            if item["section"] == section:
                grouped[item["category"]].append(item["detail"])
        for category in sorted(grouped, key=str.casefold):
            details = sorted(dict.fromkeys(grouped[category]), key=str.casefold)
            lines += ["", f"=== {heading.split(' (')[0]} – {category} ({len(details)}) ==="]
            for index, detail in enumerate(details):
                if index and "\n" in detail + details[index - 1]:
                    lines.append("")  # Blank line around multi-line blocks (format B).
                lines.append(detail)
    return "\n".join(lines) + "\n"


def _write_new(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)


def _file_stamp(kind: str, when: datetime) -> str:
    return f"{kind}_{when.strftime('%Y-%m-%d_%H-%M-%S-%f')}"


def _keep_notes(state: dict, issues: list[dict]) -> None:
    """Keep new notes for the next report, without duplicates."""
    known = {(item["category"], item["key"], item["detail"]) for item in state["notes"]}
    for item in issues:
        key = (item["category"], item["key"], item["detail"])
        if item["section"] == "note" and key not in known:
            state["notes"].append(item)
            known.add(key)


# --------- FUNC: COMMANDS ---------
def _update_index() -> None:
    """Search all collections; admit new clips, report differences for known clips without changing them."""
    started = perf_counter()
    _log("Index-Aktualisierung gestartet.")
    mapping = _load_mapping()
    _check_root()
    state, ctx = _load_state(), _context()
    before = len(state["clips"])
    _reconcile(state, _search_clips(mapping, ctx), ctx)
    index_issues = [item for item in ctx["issues"] if item["section"] in index_sections]
    state["index"] = {"updated_at": _now(), "issues": index_issues}
    _keep_notes(state, ctx["issues"])
    state["updated_at"] = _now()
    _save_state(state)
    when = datetime.now().astimezone()
    name = _file_stamp("index", when)
    if ctx["issues"]:
        _write_new(error_dir / f"{name}_errors.txt", _format_errors(ctx["issues"], when, "Index-Fehlerliste"))
    counts = {section: len({item["key"] for item in index_issues if item["section"] == section}) for section in index_sections}
    _log(f"Index aktualisiert: {len(state['clips']) - before} Clips neu aufgenommen, {len(state['clips'])} in der JSON; "
         f"{counts['skipped']} nicht aufgenommen; {counts['deviation']} Abweichungen"
         f"{f'; Details: errors/{name}_errors.txt' if ctx['issues'] else ''}; Dauer: {perf_counter() - started:.1f} s.")


def _report(kind: str) -> Path:
    """Report from the JSON and the folders; no search and no changes on the share."""
    started = perf_counter()
    _log(f"{kind}-Bericht gestartet.")
    mapping = _load_mapping()
    _check_root()
    if not state_path.exists():
        raise RuntimeError("Noch keine JSON – zuerst 'update-index' oder 'run'.")
    state, ctx = _load_state(), _context()
    ctx["issues"].extend([*state["index"]["issues"], *state["notes"]])
    prio = _priority(mapping, state, ctx)
    view = copy.deepcopy(state)  # The report only looks; jobs and moves stay with 'run'.
    _process(view, mapping, prio, ctx, writing=False)
    ctx["listings"].clear()
    ctx["indexes"].clear()
    _leftovers(view, mapping, ctx)
    _final_audit(state, mapping, ctx)
    totals = _totals(view, mapping)
    try:
        previous = _read_previous(_previous(kind))
    except (OSError, UnicodeError, ValueError) as exc:
        previous = {}
        _issue(ctx, "note", "Vorbericht nicht lesbar – keine Deltas", "previous", str(exc))
    when = datetime.now().astimezone()
    name = _file_stamp(kind, when)
    watch, workers = _watch_lines(view), _worker_lines(view)
    text = _render(kind, when, totals, prio, previous) + f"\nIndex-Stand: {state['index']['updated_at'] or 'unbekannt'}\n\n"
    text += "\n".join(_final_lines(ctx)) + "\n\n"
    text += "\n".join(_summary_lines(ctx["issues"])) + "\n"
    text += f"\nAuffällige laufende Jobs: {len(watch)}\n" + "".join(f"{line}\n" for line in watch)
    text += f"\nWorker (Heartbeat): {len(workers)}\n" + "".join(f"{line}\n" for line in workers)
    if ctx["issues"]:
        text += f"\nDetails: errors/{name}_errors.txt\n"
    state.update(notes=[], workers=view["workers"], updated_at=_now())
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
    """Run one job cycle with the loaded configuration; returns the reason if it was skipped."""
    if not state_path.exists():
        return "Job-Zyklus übersprungen: keine JSON ('update-index' ausführen oder 'run' erneut eingeben)."
    mapping = _load_mapping()
    _check_root()
    state, ctx = _load_state(), _context()
    if state.get("cleanup", {}).get("pending"):
        return "Bereinigung noch unvollständig; zuerst delete-folder erneut ausführen."
    _process(state, mapping, _priority(mapping, state, ctx), ctx, writing=True)
    _keep_notes(state, ctx["issues"])
    state["updated_at"] = _now()
    _save_state(state)
    return None


def _create_folders() -> None:
    mapping = _load_mapping()
    _check_root()
    created = _ensure_folders(mapping, force=True)
    _log(f"Ordnerstruktur für {len(mapping)} Kollektionen geprüft: {created} Ordner neu angelegt.")


def _start_run() -> None:
    """Quick start: create missing folders and build the JSON if it does not exist yet."""
    if state_path.exists() and _load_state().get("cleanup", {}).get("pending"):
        raise RuntimeError("Bereinigung noch unvollständig; zuerst 'delete-folder' erneut ausführen.")
    _create_folders()
    if not state_path.exists():
        _log("Noch keine JSON – Index wird aus der Suche aufgebaut.")
        _update_index()


def _auto_due(now: datetime) -> bool:
    return now.time() >= cfg["auto_report_time"] and not any(reports_dir.glob(f"auto_{now:%Y-%m-%d}_*.txt"))


def _command(raw: str) -> str:
    key = "-".join(raw.casefold().replace("_", " ").replace("-", " ").split())
    return command_aliases.get(key, key)


def _help_text() -> str:
    return "Befehle:\n" + "\n".join(f"  {name:<16} {text}" for name, text in commands_help.items())


def _status_text(running: bool, auto: bool) -> str:
    when = cfg.get("auto_report_time")
    auto_text = (f"an (täglich ab {when:%H:%M})" if when else "an") if auto else "aus"
    return f"Status: Job-Schleife {'läuft' if running else 'aus'}; Auto-Bericht {auto_text}."


def _console(commands: queue.Queue[str]) -> None:
    while True:
        try:
            command = _command(input("Marathon> "))
        except EOFError:
            commands.put("__eof__")
            return
        commands.put(command)
        if command == "quit":
            return


# --------- MAIN ---------
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Marathon: Index, Job-Steuerung und Berichte", epilog=_help_text(),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("commands", nargs="*", metavar="befehl", help="Befehle, die direkt nach dem Start laufen")
    startup = [_command(item) for item in parser.parse_args(argv).commands]
    unknown = [item for item in startup if item not in commands_help]
    if unknown:
        parser.error(f"Unbekannte Befehle: {', '.join(unknown)}")
    _prepare()
    _acquire_lock()
    _log(f"{app_name} {app_version} gestartet.")
    commands: queue.Queue[str] = queue.Queue()
    for item in startup:
        commands.put(item)
    if "quit" not in startup:
        threading.Thread(target=_console, args=(commands,), daemon=True).start()
    _log("Marathon wartet auf Befehle ('help' zeigt alle).")
    running = auto = False
    pending_delete = None
    next_cycle = next_retry = last_problem = last_skip = None
    while True:
        problem = _load_config()
        if problem != last_problem:
            _log(problem or "Konfiguration gültig.")
            last_problem = problem
        now = datetime.now().astimezone()
        try:
            command = commands.get(timeout=0.5)
        except queue.Empty:
            if auto and not problem and _auto_due(now) and (next_retry is None or now >= next_retry):
                try:
                    _report("auto")
                    next_retry = None
                except Exception as exc:
                    next_retry = now + timedelta(minutes=cfg["retry_minutes"])
                    _log(f"Auto-Bericht fehlgeschlagen: {exc}; neuer Versuch in {cfg['retry_minutes']} min.")
            if running and not problem and now >= next_cycle:
                try:
                    skipped = _cycle()
                    if skipped and skipped != last_skip:
                        _log(skipped)
                    last_skip = skipped
                except Exception as exc:
                    _log(f"Job-Zyklus fehlgeschlagen: {exc}; Job-Schleife bleibt aktiv.")
                next_cycle = now + timedelta(seconds=cfg["cycle_seconds"])
            continue
        if pending_delete is not None:
            plan, pending_delete = pending_delete, None
            if command == "loeschen" and not problem:
                try:
                    _delete_folders(plan)
                except Exception as exc:
                    _log(f"Bereinigung fehlgeschlagen: {exc}")
                continue
            _log("Bereinigung abgebrochen. Nichts gelöscht; Job-Schleife bleibt aus.")
            if command not in ("quit", "__eof__"):
                continue
        if command == "__eof__":
            continue
        if command == "quit":
            _log("Marathon beendet.")
            return
        if command not in commands_help or command == "help":
            _log(("" if command in ("", "help") else f"Unbekannter Befehl {command!r}.\n") + _help_text())
            continue
        if command in ("stop", "auto-report-off", "status"):
            running, auto = running and command != "stop", auto and command != "auto-report-off"
            _log(_status_text(running, auto))
            continue
        if command == "delete-folder":
            running = False
            _log("Job-Schleife für Bereinigung angehalten.")
        if problem:
            _log(f"{command!r} während der Pause nicht möglich: {problem}")
            continue
        try:
            if command == "run":
                _start_run()
                running, next_cycle, last_skip = True, now, None
            elif command == "auto-report":
                auto, next_retry = True, None
            elif command == "report":
                _report("manual")
            elif command == "create-folders":
                _create_folders()
            elif command == "delete-folder":
                pending_delete = _begin_delete()
            else:
                _update_index()
            if command in ("run", "auto-report"):
                _log(_status_text(running, auto))
        except Exception as exc:
            _log(f"{command!r} fehlgeschlagen: {exc}")


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
