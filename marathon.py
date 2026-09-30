# --------- IMPORTS ---------
import argparse
import configparser
import json
import os
import queue
import re
import shutil
import string
import tempfile
import threading
import traceback
import unicodedata
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from time import perf_counter

from toolbox import tb_write_log

# --------- STATIC ---------
modules = {  # module: (worker job, allowed keys, required keys)
    "restore": (True, {"ausgang", "parameter"}, {"ausgang"}),
    "transcode": (True, {"eingang", "ausgang", "dateiname", "parameter", "abkuerzung"}, {"eingang", "ausgang", "dateiname"}),
    "qc": (True, {"eingang", "ausgang", "parameter", "abkuerzung"}, {"eingang"}),
    "delete": (False, {"dateien"}, {"dateien"}),
}
job_modules = tuple(name for name, (worker, _, _) in modules.items() if worker)
key_labels = {"modul": "Modul", "eingang": "Eingang", "ausgang": "Ausgang", "dateiname": "Dateiname",
              "parameter": "Parameter", "abkuerzung": "Abkürzung", "dateien": "Dateien"}
operators = ("is", "is not", "contains", "contains not", "starts_with", "ends_with",
             ">", "<", ">=", "<=", "not >", "not <", "not >=", "not <=")
compare_operators = frozenset(op for op in operators if op[-1] in "<>=")
template_fields = ("clip_id", "identifier", "title", "clip_name", "collection")
field_keys = ("clip_id", "identifier", "title", "clip_name", "hash", "userpath", "status_flags")
arrow_pattern = re.compile(r"\s*(?:-{1,2}>|—>|–>|→)\s*")
simple_name = re.compile(r"[A-Za-z0-9_-]+")
master_set, jobs_dir = "master", "jobs"
job_boxes = ("offen", "laufend", "fertig", "archiv", "zurueckgezogen", "ausgang")
outbox, unknown_dir, worker_dir = "ausgang", "unbekannt", "worker"
report_statuses = ("ok", "failed", "rejected")
system_files = frozenset({"thumbs.db", "desktop.ini", ".ds_store"})
busy_suffixes = (".tmp", ".part", ".partial")
protocol_suffixes = (".json", ".txt", ".log")
summary_name = "Summe"
fixed_columns = ("Kollektion", "Prio", "Gesamt", "Bereit", "%")
reserved_steps = frozenset(name.casefold() for name in (*fixed_columns, master_set))
invalid_path_chars = frozenset('<>:"/\\|?*' + "".join(map(chr, range(32))))
reserved_names = frozenset({"CON", "PRN", "AUX", "NUL",
                            *(f"{kind}{number}" for kind in ("COM", "LPT") for number in range(1, 10))})
issue_sections = {
    "skipped": "Gefunden, aber nicht aufgenommen (nicht in Gesamt)",
    "inactive": "Im Zustand, aber nicht mehr aktiv (nicht in Gesamt)",
    "note": "Hinweise (betroffene Clips zählen weiter)",
}
problem_categories = {  # kind: (category for new clips, category for known clips, clip status)
    "missing": (None, "Verloren – nicht mehr in der Suche", "verloren"),
    "placeholder": (None, "Jetzt Platzhalter", "platzhalter"),
    "multi": ("Clip-ID in mehreren Kollektionen", "Clip-ID in mehreren Kollektionen (nach Aufnahme)", "duplikat"),
    "invalid": ("Unvollständige oder widersprüchliche Metadaten",
                "Unvollständige oder widersprüchliche Metadaten (nach Aufnahme)", "ungueltig"),
    "duplicate": ("Gleicher Dateiname bei mehreren Clips", "Gleicher Dateiname bei mehreren Clips (nach Aufnahme)", "duplikat"),
    "restore": ("Dateinamen und Hashes passen nicht zusammen",
                "Dateinamen und Hashes passen nicht zusammen (nach Aufnahme)", "ungueltig"),
}
lost_file, no_order = "Verloren – Datei fehlt", "Kollektion in keiner Auftragsliste"
qc_rejected, job_failed = "QC nicht bestanden", "Job endgültig fehlgeschlagen"
status_codes = {existing: code for _, existing, code in problem_categories.values()} | {
    lost_file: "verloren", no_order: "verloren", qc_rejected: "qc_abgelehnt", job_failed: "fehlgeschlagen"}
issue_kinds = ("sticky", "file", "setup", "search")
waiting_note, ambiguous_note = "Wartet auf Eingang", "Mehrere passende Dateien in Eingängen (nicht übernommen)"
transient_notes = frozenset({waiting_note, ambiguous_note})  # Recomputed by every report, not kept from cycles.
order_label, overview_title = "Auftragsliste", "Alle Auftragslisten"
reserved_rows = frozenset(name.casefold() for name in (summary_name, fixed_columns[0], order_label))
missing_job_grace = timedelta(minutes=30)  # Before a vanished job file is recreated.
tracked_fields = {"collection": "Kollektion", "identifier": "Identifier", "title": "Titel",
                  "clip_name_with_extension": "Clipname", "master_files": "Master-Dateien", "filehashes": "Hashes"}

# --------- CONFIG ---------
app_name = "Marathon"
app_version = "1.1.0"
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
    "paths": {"root_path": "text", "work_dir": "name", "cred_file": "text", "pipelines_file": "text", "orders_dir": "text"},
    "fields": {**{key: "text" for key in field_keys}, "placeholder_flag": "text"},
    "operation": {"report_only": "bool", "auto_report_time": "time", "retry_minutes": "number"},
    "timing": {"cycle_seconds": "number", "max_job_attempts": "number", "stable_minutes": "count"},
    "limits": {module: "count" for module in job_modules},
    "heartbeat": {"worker_timeout_minutes": "number", "max_job_hours": "number"},
}
restart_sections = ("paths", "fields")

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
    if kind == "bool":
        if raw.casefold() not in ("true", "false"):
            raise ValueError("erwartet true oder false")
        return raw.casefold() == "true"
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
    if kind == "name" and (any(char in invalid_path_chars for char in raw) or raw in (".", "..")):
        raise ValueError("muss ein einfacher Ordnername sein")
    return raw


def _read_config() -> dict:
    parser = configparser.ConfigParser(interpolation=None)
    with config_path.open(encoding="utf-8-sig") as handle:
        parser.read_file(handle)
    problems = [f"[{section}] {key} ist unbekannt" for section in parser.sections() for key in parser[section]
                if key not in config_schema.get(section, {})]
    values = {}
    for section, keys in config_schema.items():
        for key, kind in keys.items():
            try:
                values[key] = _parse_value(kind, parser.get(section, key, fallback="").strip())
            except ValueError as exc:
                problems.append(f"[{section}] {key}: {exc}")
    for key in ("cred_file", "pipelines_file"):
        if key in values and not (res_dir / values[key]).is_file():
            problems.append(f"[paths] {key}: Datei {res_dir / values[key]} fehlt")
    if "orders_dir" in values and not (res_dir / values["orders_dir"]).is_dir():
        problems.append(f"[paths] orders_dir: Ordner {res_dir / values['orders_dir']} fehlt")
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
    changed = [key for section in restart_sections for key in config_schema[section] if cfg and values[key] != cfg[key]]
    if changed:
        sections = ", ".join(f"[{section}]" for section in restart_sections)
        return (f"Änderung in {sections} ({', '.join(changed)}) – Marathon pausiert; "
                "Neustart nötig oder Änderung zurücknehmen.")
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
        raise ValueError(f"Aus {name!r} lässt sich kein Ordnername bilden.")
    return key


def _path(relative: str) -> Path:
    return Path(cfg["root_path"]).joinpath(*relative.split("/"))


def _check_root() -> None:
    if not Path(cfg["root_path"]).is_dir():
        raise FileNotFoundError(f"Netzlaufwerk nicht erreichbar: {cfg['root_path']}; Zustand unverändert.")


# --------- FUNC: PIPELINES AND ORDER LISTS ---------
def _key(raw: str) -> str:
    key = " ".join(raw.split()).casefold()
    for old, new in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        key = key.replace(old, new)
    return key


def _lines(path: Path):
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if raw.strip() and not raw.lstrip().startswith("#"):
            yield number, raw.rstrip()


def _items(raw: str, where: str) -> list[str]:
    items = [item.strip() for item in raw.split(",")]
    if not all(items):
        raise ValueError(f"{where}: leere Angabe in der Liste {raw!r}")
    return items


def _segments(raw: str, where: str) -> str:
    parts = [part.strip() for part in raw.replace("\\", "/").split("/") if part.strip()]
    for part in parts:
        if (any(char in invalid_path_chars for char in part) or part.startswith(".")
                or part.split(".")[0].upper() in reserved_names or part.casefold() == cfg["work_dir"].casefold()):
            raise ValueError(f"{where}: ungültiger Ordner {raw!r} (verbotenes Zeichen, Punkt am Anfang, reservierter Name "
                             f"oder {cfg['work_dir']})")
    if not parts:
        raise ValueError(f"{where}: Ordnerangabe leer")
    return "/".join(parts)


def _folder_spec(raw: str, where: str) -> tuple[str, str]:
    """Parse a folder of a step: ("int", name), ("ext", share path) or ("target", sub path)."""
    if raw.casefold().startswith("{target}"):
        rest = raw[len("{target}"):].strip()
        if rest and not rest.startswith(("/", "\\")):
            raise ValueError(f"{where}: nach {{target}} darf nur /Unterordner folgen ({raw!r})")
        return "target", _segments(rest, where) if rest.strip("/\\ ") else ""
    if raw.startswith(("/", "\\")):
        return "ext", _segments(raw, where)
    if not simple_name.fullmatch(raw) or raw.casefold() == jobs_dir:
        raise ValueError(f"{where}: interner Ordner {raw!r} muss ein einfacher Name sein (Buchstaben, Ziffern, _ und -; "
                         f"nicht {jobs_dir!r}); extern mit / oder {{target}} beginnen")
    return "int", raw.casefold()


def _check_template(template: str, where: str) -> None:
    try:
        parts = list(string.Formatter().parse(template))
    except ValueError as exc:
        raise ValueError(f"{where}: Dateiname fehlerhaft ({exc})") from None
    for _, field, spec, conversion in parts:
        if field is not None and (field not in template_fields or spec or conversion):
            allowed = ", ".join(f"{{{name}}}" for name in template_fields)
            raise ValueError(f"{where}: Platzhalter {{{field}}} ungültig; erlaubt: {allowed}")


def _build_step(path: Path, step: dict) -> None:
    raw, where = step.pop("raw"), f"{path.name} Step [{step['name']}]"

    def single(key: str) -> str | None:
        entries = raw.get(key, [])
        if len(entries) > 1:
            raise ValueError(f"{path.name} Zeile {entries[1][0]}: {key_labels.get(key, key)} doppelt in [{step['name']}]")
        return entries[0][1] if entries else None

    module = (single("modul") or "").casefold()
    if module not in modules:
        raise ValueError(f"{where}: Modul fehlt oder ist unbekannt ({module!r}); erlaubt: {', '.join(modules)}")
    _, allowed, required = modules[module]
    unknown = [key_labels.get(key, key) for key in raw if key not in allowed | {"modul"}]
    if unknown:
        raise ValueError(f"{where}: {', '.join(unknown)} ist bei Modul {module} nicht erlaubt")
    missing = [key_labels[key] for key in sorted(required) if not single(key)]
    if missing:
        raise ValueError(f"{where}: {', '.join(missing)} fehlt")
    params = {}
    for number, value in raw.get("parameter", []):
        name, separator, content = (part.strip() for part in value.partition("="))
        if not separator or not name or name in params:
            raise ValueError(f"{path.name} Zeile {number}: Parameter erwartet 'schlüssel = wert' mit eindeutigem Schlüssel")
        params[name] = content
    shortcut = (single("abkuerzung") or "nein").casefold()
    if shortcut not in ("ja", "nein"):
        raise ValueError(f"{where}: Abkürzung erwartet ja oder nein")
    inputs, output, files = single("eingang"), single("ausgang"), single("dateien")
    step.update(module=module, params=params, file_name=single("dateiname"), shortcut=shortcut == "ja",
                inputs=[_folder_spec(item, where) for item in _items(inputs, where)] if inputs else [],
                output=_folder_spec(output, where) if output else None, files=_items(files, where) if files else [])
    if step["file_name"]:
        _check_template(step["file_name"], where)
    if step["shortcut"] and all(kind == "int" for kind, _ in step["inputs"]):
        raise ValueError(f"{where}: Abkürzung braucht einen externen Eingang")


def _parse_pipelines(path: Path) -> tuple[dict, dict]:
    steps, pipelines, current = {}, {}, None
    for number, raw in _lines(path):
        where, line = f"{path.name} Zeile {number}", raw.strip()
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            if not simple_name.fullmatch(name) or name.casefold() in reserved_steps:
                raise ValueError(f"{where}: ungültiger Step-Name {name!r} (Buchstaben, Ziffern, _ und -; nicht {master_set!r})")
            if name.casefold() in steps:
                raise ValueError(f"{where}: Step [{name}] doppelt")
            current = steps[name.casefold()] = {"name": name, "line": number, "raw": defaultdict(list)}
            continue
        label, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"{where}: erwartet [Step], 'Schlüssel: Wert' oder 'Pipeline <Name>: Step --> Step'")
        if _key(label).startswith("pipeline "):
            current, name = None, " ".join(label.split()[1:])
            names = [part.strip() for part in arrow_pattern.split(value.strip())]
            if not all(names):
                raise ValueError(f"{where}: Pipeline {name!r} braucht Steps, getrennt mit -->")
            if name.casefold() in pipelines:
                raise ValueError(f"{where}: Pipeline {name!r} doppelt")
            pipelines[name.casefold()] = {"name": name, "line": number, "steps": names}
            continue
        if current is None:
            raise ValueError(f"{where}: {label.strip()!r} steht außerhalb eines Steps")
        current["raw"][_key(label)].append((number, value.strip()))
    for step in steps.values():
        _build_step(path, step)
    renditions = {step["name"].casefold(): step["name"] for step in steps.values() if step["module"] == "transcode"}
    for step in steps.values():
        unknown = [name for name in step["files"] if name.casefold() != master_set and name.casefold() not in renditions]
        if unknown:
            raise ValueError(f"{path.name} Step [{step['name']}]: Dateien kennt nur {master_set} und Transcode-Steps, "
                             f"nicht {', '.join(unknown)}")
        step["files"] = list(dict.fromkeys(master_set if name.casefold() == master_set else renditions[name.casefold()]
                                           for name in step["files"]))
    for pipeline in pipelines.values():
        where = f"{path.name} Zeile {pipeline['line']}"
        unknown = [name for name in pipeline["steps"] if name.casefold() not in steps]
        if unknown:
            raise ValueError(f"{where}: Pipeline {pipeline['name']!r} nutzt unbekannte Steps: {', '.join(unknown)}")
        pipeline["steps"] = [steps[name.casefold()]["name"] for name in pipeline["steps"]]
        twice = sorted({name for name in pipeline["steps"] if pipeline["steps"].count(name) > 1})
        if twice:
            raise ValueError(f"{where}: Step {', '.join(twice)} zweimal in Pipeline {pipeline['name']!r}")
    return {step["name"]: step for step in steps.values()}, {item["name"]: item for item in pipelines.values()}


def _parse_search(path: Path, lines: list[tuple[int, str]]) -> tuple:
    request = []
    for index, (number, line) in enumerate(lines):
        where = f"{path.name} Zeile {number}"
        if index % 2:
            if line.casefold() not in ("and", "or"):
                raise ValueError(f"{where}: Verknüpfung and oder or erwartet, gefunden {line!r}")
            request.append(line.casefold())
            continue
        parts = [part.strip() for part in line.split("|", 2)]
        if len(parts) != 3 or not all(parts):
            hint = "Bedingung erwartet, Verknüpfung gefunden" if line.casefold() in ("and", "or") else \
                "erwartet 'Feld | Operator | Wert'"
            raise ValueError(f"{where}: {hint}")
        field, operator, value = parts[0], " ".join(parts[1].casefold().split()), parts[2]
        if operator not in operators:
            raise ValueError(f"{where}: Operator {parts[1]!r} unbekannt; erlaubt: {', '.join(operators)}")
        values = [part.strip() for part in value.split(";")] if operator == "contains" else [value]
        if not all(values):
            raise ValueError(f"{where}: leerer Wert in {value!r}")
        if operator in compare_operators:
            values = [int(item) if re.fullmatch(r"-?\d+", item) else float(item)
                      if re.fullmatch(r"-?\d+\.\d+", item) else item for item in values]
        request.append((field, operator, values if len(values) > 1 else values[0]))
    if len(lines) % 2 == 0:
        raise ValueError(f"{path.name} Zeile {lines[-1][0]}: Suche endet mit einer Verknüpfung")
    return tuple(request)


def _build_collection(path: Path, item: dict) -> dict:
    where, name = f"{path.name} Zeile {item['line']}", item["name"]
    if not name:
        raise ValueError(f"{where}: Name fehlt")
    if name.casefold() in reserved_rows:
        raise ValueError(f"{where}: der Name {name!r} ist für den Bericht reserviert")
    prio = None
    if item["prio"]:
        number, raw = item["prio"]
        if not raw.isdecimal() or int(raw) < 1:
            raise ValueError(f"{path.name} Zeile {number}: Prio erwartet eine ganze Zahl ab 1")
        prio = int(raw)
    if not item["search"]:
        raise ValueError(f"{where}: Suche fehlt oder ist leer für {name!r} (Zeilen unter 'Suche:' einrücken)")
    try:
        key = _folder_key(name)
        target = _segments(item["target"][1], f"{path.name} Zeile {item['target'][0]}") if item["target"] else key
    except ValueError as exc:
        raise ValueError(f"{where}: {exc}") from None
    return {"name": name, "prio": prio, "target": target, "request": _parse_search(path, item["search"]),
            "work": f"{target}/{cfg['work_dir']}/{key}"}


def _parse_order_list(path: Path) -> dict:
    if path.stem.casefold() in reserved_rows:
        raise ValueError(f"{path.name}: der Name {path.stem!r} ist für den Bericht reserviert; Datei bitte umbenennen")
    pipeline, collections, current, in_search = None, [], None, False
    for number, raw in _lines(path):
        where = f"{path.name} Zeile {number}"
        if in_search and raw[:1].isspace():
            current["search"].append((number, raw.strip()))
            continue
        in_search = False
        label, separator, value = raw.strip().partition(":")
        key, value = _key(label), value.strip()
        if not separator or not value and key != "suche":
            raise ValueError(f"{where}: erwartet 'Schlüssel: Wert' (Suchzeilen unter 'Suche:' einrücken)")
        if key == "pipeline":
            if pipeline or current:
                raise ValueError(f"{where}: genau eine Pipeline-Zeile, vor der ersten Kollektion")
            pipeline = (value, number)
        elif key == "name":
            current = {"name": value, "line": number, "prio": None, "target": None, "search": [], "has_search": False}
            collections.append(current)
        elif key in ("prio", "ziel", "suche"):
            slot = {"prio": "prio", "ziel": "target", "suche": "has_search"}[key]
            if current is None:
                raise ValueError(f"{where}: {label.strip()} steht vor der ersten Kollektion (Name:)")
            if current[slot]:
                raise ValueError(f"{where}: {label.strip()} doppelt bei {current['name']!r}")
            if key == "suche":
                if value:
                    raise ValueError(f"{where}: Suchzeilen bitte eingerückt unter 'Suche:' schreiben")
                current["has_search"] = in_search = True
            else:
                current[slot] = (number, value)
        else:
            raise ValueError(f"{where}: unbekannter Schlüssel {label.strip()!r}; erlaubt: Pipeline, Name, Prio, Ziel, Suche")
    if pipeline is None:
        raise ValueError(f"{path.name}: Pipeline-Zeile fehlt (Pipeline: <Name>)")
    if not collections:
        raise ValueError(f"{path.name}: keine Kollektion (Name:)")
    return {"name": path.stem, "file": path.name, "pipeline": pipeline,
            "collections": [_build_collection(path, item) for item in collections]}


def _load_setup() -> dict:
    """Read pipelines.txt and all order lists; raises ValueError with file and line on operating errors."""
    steps, pipelines = _parse_pipelines(_res("pipelines_file"))
    folder = _res("orders_dir")
    files = sorted((path for path in folder.glob("*.txt") if path.is_file()), key=lambda path: path.name.casefold())
    if not files:
        raise ValueError(f"Keine Auftragsliste (*.txt) in {folder}")
    by_key = {name.casefold(): name for name in pipelines}
    orders, owners, collections, works = [], {}, {}, {}
    for path in files:
        order = _parse_order_list(path)
        name, number = order["pipeline"]
        where = f"{path.name} Zeile {number}"
        pipeline = by_key.get(name.casefold())
        if pipeline is None:
            raise ValueError(f"{where}: Pipeline {name!r} fehlt in {cfg['pipelines_file']}")
        if pipeline in owners:
            raise ValueError(f"{where}: Pipeline {pipeline!r} gehört schon zu {owners[pipeline]}; "
                             f"jede Pipeline hat höchstens eine Auftragsliste")
        owners[pipeline], order["pipeline"] = path.name, pipeline
        for coll in order["collections"]:
            other = collections.get(coll["name"].casefold()) or works.get(coll["work"].casefold())
            if other:
                raise ValueError(f"{path.name}: Kollektion {coll['name']!r} kollidiert mit {other['name']!r} "
                                 f"({other['order_list']}): gleicher Name oder Arbeitsordner")
            coll.update(order_list=order["name"], pipeline=pipeline, steps=pipelines[pipeline]["steps"])
            collections[coll["name"].casefold()] = works[coll["work"].casefold()] = coll
        orders.append(order)
    ranked = sorted(collections.values(), key=lambda coll: coll["prio"] or float("inf"))  # Stable: file order for ties.
    for rank, coll in enumerate(ranked):
        coll["rank"] = rank
    uses, labels = defaultdict(lambda: defaultdict(set)), {}
    for coll in collections.values():
        for name in coll["steps"]:
            step = steps[name]
            for role, specs in (("Eingang", step["inputs"]), ("Ausgang", [step["output"]] if step["output"] else [])):
                for spec in specs:
                    if spec[0] != "int":
                        folder = _place(spec, coll, "")
                        labels.setdefault(folder.casefold(), folder)
                        uses[folder.casefold()][role].add(name)
    clashes = [f"{labels[key]} (Eingang bei {', '.join(sorted(roles['Eingang']))}; "
               f"Ausgang bei {', '.join(sorted(roles['Ausgang']))})" for key, roles in uses.items() if len(roles) > 1]
    if clashes:
        raise ValueError(f"{cfg['pipelines_file']}: externer Ordner zugleich Eingang und Ausgang: {'; '.join(clashes)}")
    notes = [("Step ohne Pipeline", name) for name in steps if not any(name in item["steps"] for item in pipelines.values())]
    notes += [("Pipeline ohne Auftragsliste", name) for name in pipelines if name not in owners]
    return {"steps": steps, "pipelines": pipelines, "orders": orders, "notes": notes,
            "collections": {coll["name"]: coll for coll in collections.values()},
            "templates": [(step["name"], step["file_name"]) for step in steps.values() if step["module"] == "transcode"]}


def _place(spec: tuple[str, str], coll: dict, clip_id: str) -> str:
    kind, value = spec
    if kind == "int":
        return f"{coll['work']}/{value}/{clip_id}"
    if kind == "target":
        return f"{coll['target']}/{value}" if value else coll["target"]
    return value


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


def _render(template: str, meta: dict) -> str:
    """File name (without extension) from a template; characters not allowed on Windows become "_"."""
    text = template.format_map({key: meta[key] for key in template_fields})
    return "".join("_" if char in invalid_path_chars else char for char in text).strip()


def _meta(clip: dict) -> dict:
    return {"clip_id": clip["clip_id"], "identifier": clip["identifier"], "title": clip["title"],
            "clip_name": clip["clip_name_with_extension"], "collection": clip["collection"]}


def _matches(name: str, base: str) -> bool:
    return _normalize(base) in (_normalize(name), _normalize(Path(name).stem))


def _context() -> dict:
    return {"issues": [], "listings": {}, "indexes": {}, "touched": set(), "claims": {}, "known": None}


def _issue(ctx: dict, section: str, category: str, key: str, detail: str) -> None:
    ctx["issues"].append({"section": section, "category": category, "key": key, "detail": detail})


def _clip_text(clip: dict) -> str:
    return (f"Clip_ID={clip['clip_id']}, Kollektion={clip['collection']}, "
            f"Clipname={clip['clip_name_with_extension']}")


def _position(clip: dict) -> str:
    if clip["ready"]:
        return "Bereit"
    job = clip["job"]
    text = f"Step {clip['step'] or '?'}" + (", wartet auf Eingang" if clip["waiting"] else "")
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


def _info_text(info: dict) -> str:
    return "".join(f", {key}={value}" for key, value in info.items())


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
    except (FileNotFoundError, NotADirectoryError):
        return {}
    except OSError as exc:
        raise RuntimeError(f"Ordner nicht lesbar: {_path(relative)}; Zustand unverändert.") from exc
    return entries


def _subfolders(relative: str) -> list[str]:
    try:
        with os.scandir(_path(relative)) as items:
            return sorted(item.name for item in items if item.is_dir(follow_symlinks=False))
    except (FileNotFoundError, NotADirectoryError):
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
        ctx["listings"][key] = {name.casefold() for name in _subfolders(relative)}
    return ctx["listings"][key]


def _listed(ctx: dict, folder: str) -> bool:
    """False if a folder in the work area is missing in its parent's listing; saves one scan per clip."""
    parent, _, leaf = folder.rpartition("/")
    return not (parent and _owned_path(parent) and leaf.casefold() not in _dirs(ctx, parent))


def _present(ctx: dict, folder: str, names: list[str]) -> list[str]:
    """Names missing (or empty) in folder."""
    if not _listed(ctx, folder):
        return list(names)
    listing = _listing(ctx, folder)
    return [name for name in names if not (listing.get(name.casefold()) or ("", 0))[1]]


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


def _owned_path(relative: str) -> bool:
    return f"/{cfg['work_dir']}/".casefold() in f"/{relative}/".casefold()


def _remove_tree(relative: str, ctx: dict, category: str) -> None:
    if not _owned_path(relative):  # Safety net: Marathon never deletes folders outside its work area.
        _issue(ctx, "note", "Löschen außerhalb des Arbeitsordners verweigert", relative, relative)
        return
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


def _index(ctx: dict, folder: str) -> dict:
    """Normalized name and stem -> file names, for matching renditions by their Dateiname."""
    if folder not in ctx["indexes"]:
        index = defaultdict(list)
        for name, size in _listing(ctx, folder).values():
            if size and not _ignored(name) and not name.casefold().endswith(protocol_suffixes):
                for key in dict.fromkeys((_normalize(name), _normalize(Path(name).stem))):
                    index[key].append(name)
        ctx["indexes"][folder] = index
    return ctx["indexes"][folder]


def _lookup(ctx: dict, folder: str, base: str) -> list[str]:
    return sorted(_index(ctx, folder).get(_normalize(base), []), key=str.casefold)


def _job_folder(coll: dict, step: str) -> str:
    return f"{coll['work']}/{jobs_dir}/{step}"


def _ensure_folders(setup: dict) -> None:
    folders = [cfg["work_dir"], f"{cfg['work_dir']}/{worker_dir}"]
    for coll in setup["collections"].values():
        for name in coll["steps"]:
            if modules[setup["steps"][name]["module"]][0]:
                folders += [f"{_job_folder(coll, name)}/{box}" for box in job_boxes]
    for relative in folders:
        if relative not in ensured_folders:
            _path(relative).mkdir(parents=True, exist_ok=True)
            ensured_folders.add(relative)


def _write_priority_file(setup: dict) -> None:
    ranked = sorted(setup["collections"].values(), key=lambda coll: coll["rank"])
    data = {"schema_version": 2, "modules": {module: [
        {"collection": coll["name"], "order_list": coll["order_list"], "pipeline": coll["pipeline"], "step": name,
         **{box: f"{_job_folder(coll, name)}/{box}" for box in ("offen", "laufend", "fertig")}}
        for coll in ranked for name in coll["steps"] if setup["steps"][name]["module"] == module] for module in job_modules}}
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
    problems = [f"{cfg[field]}: {len(row[field])} Werte" for row in rows for field in fields if len(row[field]) != 1]
    if problems:
        hit["invalid"] = "; ".join(dict.fromkeys(problems))
        return hit
    single = {field: {row[field][0] for row in rows} for field in fields}
    conflicts = [f"{cfg[field]}: {' / '.join(sorted(values))}" for field, values in single.items() if len(values) > 1]
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


def _search_clips(setup: dict, ctx: dict) -> dict[str, list[dict]]:
    import searcher

    api_fields = tuple(cfg[key] for key in field_keys)
    collections = list(setup["collections"].values())
    _log(f"API-Verbindung herstellen: {len(collections)} Kollektionen vorgesehen.")
    searcher.link("api", _res("cred_file"), on_progress=_search_progress)
    found = defaultdict(dict)
    invalid_category, flag = problem_categories["invalid"][0], cfg["placeholder_flag"].casefold()
    for coll in collections:
        name, started = coll["name"], perf_counter()
        _log(f"API-Suche gestartet: {name!r}.")
        matches, _, error = searcher.find({"name": name, "request_fields": coll["request"], "return_fields": api_fields})
        if error:
            raise RuntimeError(f"API-Suche für {name!r} ({coll['order_list']}) fehlgeschlagen; Zustand unverändert: {error}")
        placeholders = 0
        for number, row in enumerate(matches, 1):
            if len(row) != len(api_fields) or not all(isinstance(value, str) for value in row):
                _issue(ctx, "skipped", invalid_category, f"{name}#{number}", f"Kollektion={name!r}, Rückgabefelder={row!r}")
                continue
            values = {key: _values(raw) for key, raw in zip(field_keys, row)}
            ids = values["clip_id"]
            if len(ids) != 1 or not (ids[0].isascii() and ids[0].isdecimal()):
                _issue(ctx, "skipped", invalid_category, f"{name}#{number}", f"Kollektion={name!r}, Clip-ID-Rohwert={row[0]!r}")
                continue
            hit = found[ids[0]].setdefault(name, {"collection": name, "placeholder": False, "invalid": None, "rows": []})
            if flag in (value.casefold() for value in values["status_flags"]):
                hit["placeholder"] = True
                placeholders += 1
                continue
            hit["rows"].append(values)
        _log(f"API-Suche abgeschlossen: {name!r}: {len(matches)} Trefferzeilen, davon {placeholders} Platzhalter; "
             f"{perf_counter() - started:.1f} s.")
    return {clip_id: [_merge_hit(hit) for hit in hits.values()] for clip_id, hits in found.items()}


# --------- FUNC: STATE ---------
def _empty_state() -> dict:
    return {"schema_version": 4, "notes": [], "workers": {}, "files_seen": {}, "clips": {}}


def _clip_problem(clip_id: str, clip) -> str | None:
    if not isinstance(clip, dict) or clip.get("clip_id") != clip_id:
        return "Clip_ID passt nicht zum Eintrag"
    if not all(isinstance(clip.get(key), bool) for key in ("active", "ready", "waiting")):
        return "active/ready/waiting fehlt"
    if not isinstance(clip.get("step"), (str, type(None))) or (clip["ready"] and clip["step"] is not None):
        return "Step passt nicht zu bereit"
    kinds = (("history", list), ("sets", dict), ("issues", dict), ("done", list), ("input_sets", list), ("info", dict))
    if not all(isinstance(clip.get(key), kind) for key, kind in kinds) or set(clip["issues"]) != set(issue_kinds):
        return "Struktur unvollständig"
    if any(not isinstance(entry, dict) or not isinstance(entry.get("folder"), str) or not isinstance(entry.get("names"), list)
           for entry in clip["sets"].values()):
        return "Dateisatz unvollständig"
    job = clip.get("job")
    keys = ("id", "step", "module", "folder", "file", "output_folder", "state")
    if job is not None and (not isinstance(job, dict) or not all(isinstance(job.get(key), str) for key in keys)):
        return "Job-Eintrag unvollständig"
    return None


def _load_state() -> dict:
    if not state_path.exists():
        return _empty_state()
    with state_path.open(encoding="utf-8") as handle:
        state = json.load(handle)
    version = state.get("schema_version") if isinstance(state, dict) else None
    if version in (1, 2, 3):
        raise ValueError(f"Zustand hat ein altes Format (Version {version}). Bitte state/marathon.json löschen; "
                         "Marathon sammelt den Stand beim nächsten Bericht aus den Ordnern neu ein.")
    if version != 4 or not isinstance(state.get("clips"), dict):
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


# --------- FUNC: CLIPS AND STEPS ---------
def _coll(setup: dict, clip: dict) -> dict | None:
    return setup["collections"].get(clip["collection"])


def _next_step(setup: dict, clip: dict) -> dict | None:
    coll = _coll(setup, clip)
    return next((setup["steps"][name] for name in coll["steps"] if name not in clip["done"]), None) if coll else None


def _sync_step(setup: dict, clip: dict) -> dict | None:
    """Current step = first step of the pipeline that is not done; records a change as new queue position."""
    step = _next_step(setup, clip)
    name = step["name"] if step else None
    if name != clip["step"] and not clip["ready"]:
        clip.update(step=name, queued_at=_stamp(), waiting=False, input_sets=[])
        if name:
            _event(clip, f"Weiter an {name}")
    return step


def _entry(folder: str, names: list[str], spec_kind: str, slot: str | None, source: str) -> dict:
    return {"folder": folder, "names": list(names), "slot": slot if spec_kind == "int" else None,
            "delivered": spec_kind != "int" and source != "taken", "source": source, "last_seen_at": _now()}


def _external_matches(state: dict, setup: dict, clip: dict, coll: dict, step: dict,
                      ctx: dict) -> dict[str, tuple[str, list[str]]]:
    """Unique, stable files of the clip in the external inputs of a step: set name -> (folder, names)."""
    candidates, problems = defaultdict(list), []
    for spec in step["inputs"]:
        if spec[0] == "int":
            continue
        folder = _place(spec, coll, clip["clip_id"])
        listing = _listing(ctx, folder)
        if master_set not in clip["sets"] and clip["master_files"]:
            items = [listing.get(name.casefold()) for name in clip["master_files"]]
            if all(item and item[1] for item in items):
                shared = [name for name in clip["master_files"] if len(ctx["claims"].get(name.casefold(), ())) > 1]
                if shared:
                    problems.append(f"{folder}: Master-Datei passt zu mehreren Clips ({', '.join(shared)})")
                elif all([_stable(state, ctx, f"{folder}/{item[0]}", item[1]) for item in items]):
                    candidates[master_set].append((folder, [item[0] for item in items]))
        for name, template in setup["templates"]:
            if name in clip["sets"]:
                continue
            files = _lookup(ctx, folder, _render(template, _meta(clip)))
            if len(files) > 1:
                problems.append(f"{folder}: mehrere Dateien für {name} ({', '.join(files)})")
            elif files and _stable(state, ctx, f"{folder}/{files[0]}", listing[files[0].casefold()][1]):
                candidates[name].append((folder, files))
    found = {}
    for name, places in candidates.items():
        if len(places) > 1:
            problems.append(f"{name} in mehreren Eingängen ({', '.join(folder for folder, _ in places)})")
        else:
            found[name] = places[0]
    for problem in problems:
        _issue(ctx, "note", ambiguous_note, f"{clip['clip_id']}#{problem}",
               f"{_clip_text(clip)}: {problem}")
    return found


def _take(clip: dict, found: dict[str, tuple[str, list[str]]], step: dict) -> None:
    for name, (folder, files) in found.items():
        clip["sets"][name] = _entry(folder, files, "ext", None, "taken")
        _event(clip, f"{name} übernommen", f"{step['name']}: {folder}/{', '.join(files)}")


def _shortcut(state: dict, setup: dict, clip: dict, coll: dict, ctx: dict) -> None:
    job = clip["job"]
    if clip["issues"]["search"] or (job and job["state"] == "laufend"):
        return
    steps = [setup["steps"][name] for name in coll["steps"]]
    current = next((index for index, step in enumerate(steps) if step["name"] not in clip["done"]), len(steps))
    for step in steps[current + 1:]:
        if not step["shortcut"]:
            continue
        found = _external_matches(state, setup, clip, coll, step, ctx)
        if not found or not _withdraw(clip):
            continue
        skipped = [item["name"] for item in steps[current:steps.index(step)] if item["name"] not in clip["done"]]
        clip["done"] += skipped
        clip["attempts"] = 0
        _set_issue(clip, "sticky")  # Failed earlier steps are lifted by the shortcut.
        _take(clip, found, step)
        _event(clip, f"Abkürzung zu {step['name']}", "übersprungen: " + ", ".join(skipped))
        _issue(ctx, "note", "Abkürzung genommen", clip["clip_id"], f"{_clip_text(clip)}: {step['name']}, übersprungen: "
               f"{', '.join(skipped)}")
        return


def _gather_inputs(state: dict, setup: dict, clip: dict, coll: dict, step: dict, ctx: dict) -> list[str]:
    """Set names of the clip that lie in the inputs of a step; takes over matching external files."""
    _take(clip, _external_matches(state, setup, clip, coll, step, ctx), step)
    internal = {value for kind, value in step["inputs"] if kind == "int"}
    external = {_place(spec, coll, clip["clip_id"]).casefold() for spec in step["inputs"] if spec[0] != "int"}
    return [name for name, entry in clip["sets"].items() if not entry["delivered"] and
            ((entry["slot"] or "") in internal or (not entry["slot"] and entry["folder"].casefold() in external))]


def _delete_sets(clip: dict, step: dict, ctx: dict, writing: bool) -> bool:
    """Delete the sets of a delete step that Marathon owns; False if this has to wait (report_only or an error)."""
    names = [name for name in step["files"] if name in clip["sets"]]
    if not writing and any(not clip["sets"][name]["delivered"] for name in names):
        return False
    for name in names:
        entry = clip["sets"][name]
        if entry["delivered"]:
            _issue(ctx, "note", "Delete übersprungen – Datei ausgeliefert", f"{clip['clip_id']}#{name}",
                   f"{_clip_text(clip)}: {name} in {entry['folder']}")
            continue
        try:
            for file in entry["names"]:
                _path(f"{entry['folder']}/{file}").unlink(missing_ok=True)
        except OSError as exc:
            _issue(ctx, "note", "Löschen fehlgeschlagen (nächster Versuch im nächsten Zyklus)", f"{clip['clip_id']}#{name}",
                   f"{_clip_text(clip)}: {name}: {exc}")
            return False
        if entry["slot"]:
            _rmdir(entry["folder"])
        del clip["sets"][name]
        _event(clip, f"{name} gelöscht", f"{step['name']}: {entry['folder']}")
    return True


def _move_on(state: dict, setup: dict, clip: dict, coll: dict, ctx: dict, writing: bool) -> None:
    while True:
        step = _sync_step(setup, clip)
        if step is None:
            if clip["job"] and not _withdraw(clip):
                return  # A job of a removed step still runs; its result is discarded later.
            clip.update(ready=True, step=None, waiting=False, input_sets=[])
            _event(clip, "Bereit", ", ".join(f"{name}: {entry['folder']}" for name, entry in clip["sets"].items()))
            return
        if step["module"] != "delete":
            clip["input_sets"] = [] if step["module"] == "restore" else _gather_inputs(state, setup, clip, coll, step, ctx)
            clip["waiting"] = step["module"] != "restore" and not clip["input_sets"]
            if clip["waiting"]:
                _issue(ctx, "note", waiting_note, clip["clip_id"], f"{_clip_text(clip)}: Step {step['name']}")
            return
        if not _delete_sets(clip, step, ctx, writing):
            return
        clip["done"].append(step["name"])


# --------- FUNC: RECONCILE ---------
def _classify(hits: list[dict]) -> tuple[dict | None, tuple[str, str] | None]:
    if not hits:
        return None, ("missing", "Nicht mehr in der Suche gefunden (Metadaten nicht abrufbar oder Kollektion geändert)")
    if any(hit["placeholder"] for hit in hits):
        return None, ("placeholder", "Suche meldet Platzhalter")
    if len(hits) > 1:
        return None, ("multi", "Kollektionen: " + ", ".join(sorted(hit["collection"] for hit in hits)))
    return (None, ("invalid", hits[0]["invalid"])) if hits[0]["invalid"] else (hits[0], None)


def _hit_meta(clip_id: str, hit: dict) -> dict:
    return {"clip_id": clip_id, "identifier": hit["identifier"], "title": hit["title"], "clip_name": hit["clip_name"],
            "collection": hit["collection"]}


def _new_clip(clip_id: str, hit: dict, coll: dict) -> dict:
    return {"clip_id": clip_id, "collection": hit["collection"], "order_list": coll["order_list"], "pipeline": coll["pipeline"],
            "identifier": hit["identifier"], "title": hit["title"], "clip_name_with_extension": hit["clip_name"],
            "filehashes": hit["hashes"], "master_files": hit["masters"], "status": "wartet", "active": True, "ready": False,
            "step": None, "done": [], "waiting": False, "input_sets": [], "queued_at": _stamp(), "job": None, "job_count": 0,
            "attempts": 0, "sets": {}, "info": {}, "issues": {kind: None for kind in issue_kinds}, "history": []}


def _existing_result(ctx: dict, setup: dict, clip: dict, coll: dict, step: dict) -> dict[str, list[str]]:
    """Sets of a new clip that already lie in the output of a step."""
    folder = _place(step["output"], coll, clip["clip_id"])
    if not _listed(ctx, folder):
        return {}
    listing, result = _listing(ctx, folder), {}
    if step["module"] in ("restore", "qc") and clip["master_files"] and not _present(ctx, folder, clip["master_files"]):
        result[master_set] = [listing[name.casefold()][0] for name in clip["master_files"]]
    if step["module"] == "restore":
        return result
    templates = [(step["name"], step["file_name"])] if step["module"] == "transcode" else setup["templates"]
    for name, template in templates:
        files = _lookup(ctx, folder, _render(template, _meta(clip)))
        if len(files) == 1:
            result[name] = files
    return result


def _admit(state: dict, clip_id: str, hit: dict, setup: dict, ctx: dict) -> None:
    coll = setup["collections"][hit["collection"]]
    clip, steps = _new_clip(clip_id, hit, coll), [setup["steps"][name] for name in coll["steps"]]
    results = {index: _existing_result(ctx, setup, clip, coll, step) for index, step in enumerate(steps)
               if step["module"] != "delete" and step["output"]}
    last = max((index for index, sets in results.items() if sets), default=-1)
    for index in range(last + 1):
        step = steps[index]
        if step["module"] == "delete":
            continue  # Deletes before the last result run again, so nothing stays behind.
        clip["done"].append(step["name"])
        for name, files in results.get(index, {}).items():
            folder = _place(step["output"], coll, clip_id)
            clip["sets"][name] = _entry(folder, files, step["output"][0], step["output"][1], step["name"])
    first = next((step for step in steps if step["name"] not in clip["done"]), None)
    if first and first["module"] == "restore" and hit["restore_problem"]:
        _issue(ctx, "skipped", problem_categories["restore"][0], clip_id,
               f"Clip_ID={clip_id}, Kollektion={coll['name']}, Clipname={hit['clip_name']}: {hit['restore_problem']}")
        return
    found = ", ".join(f"{name}: {entry['folder']}" for name, entry in clip["sets"].items())
    _event(clip, "Aufgenommen" + (f" – erledigt bis {steps[last]['name']}" if last >= 0 else ""), found)
    state["clips"][clip_id] = clip


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


def _reconcile(state: dict, setup: dict, found: dict[str, list[dict]], ctx: dict) -> None:
    clips = state["clips"]
    classified = {clip_id: _classify(found.get(clip_id, [])) for clip_id in {*found, *clips}}
    groups = defaultdict(set)
    for clip_id, (hit, _) in classified.items():
        if hit:
            meta = _hit_meta(clip_id, hit)
            for _, template in setup["templates"]:
                groups[_normalize(_render(template, meta))].add(clip_id)
    for key, group in groups.items():
        if len(group) > 1:
            text = f"Dateiname {key!r}: Clip_IDs " + ", ".join(sorted(group, key=int))
            for clip_id in group:
                classified[clip_id] = (classified[clip_id][0], ("duplicate", text))
    for clip_id in sorted(classified, key=int):
        hit, problem = classified[clip_id]
        clip = clips.get(clip_id)
        if clip is None:
            if problem is None:
                _admit(state, clip_id, hit, setup, ctx)
            elif problem_categories[problem[0]][0]:
                collections = ", ".join(sorted(item["collection"] for item in found[clip_id]))
                _issue(ctx, "skipped", problem_categories[problem[0]][0], clip_id,
                       f"Clip_ID={clip_id}, Kollektion={collections}: {problem[1]}")
            continue
        if hit:
            _update_metadata(clip, hit, ctx)
            step = _next_step(setup, clip)
            if problem is None and not clip["ready"] and step and step["module"] == "restore" and hit["restore_problem"]:
                problem = ("restore", hit["restore_problem"])
        _set_issue(clip, "search", *((problem_categories[problem[0]][1], problem[1]) if problem else ()))


# --------- FUNC: WORKERS ---------
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
            "raw": text, "changed_at": _now(), "module": str(data.get("module") or ""),
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
            lines.append(f"  {_clip_text(clip)}; Step {job['step']} ({job['module']}), Job {job['id']}; Worker {job['worker']}; "
                         f"läuft seit {since}; {'; '.join(reasons)}")
    return lines


def _worker_lines(state: dict) -> list[str]:
    return [f"  {name}, {worker['module'] or '?'}, Rechner {worker['host'] or '?'}, letztes Lebenszeichen vor "
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
    if not isinstance(report.get("info", {}), (dict, type(None))):
        return "info ist kein Objekt"
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
            _issue(ctx, "note", "Ausgang nicht archivierbar (bleibt liegen)", job["output_folder"],
                   f"{job['output_folder']}: {exc}")
        return
    _remove_tree(job["output_folder"], ctx, "Ausgang nicht löschbar (bleibt liegen)")


def _known_files(state: dict, ctx: dict) -> dict[tuple[str, str], str]:
    """(folder, name) of all files recorded outside the work area -> clip id."""
    if ctx["known"] is None:
        ctx["known"] = {(entry["folder"].casefold(), name.casefold()): clip["clip_id"] for clip in state["clips"].values()
                        for entry in clip["sets"].values() if not entry["slot"] for name in entry["names"]}
    return ctx["known"]


def _store(state: dict, clip: dict, coll: dict, step: dict, name: str, files: list[tuple[str, str]], ctx: dict) -> str | None:
    """Move files (source path, file name) into the step output and record them as set name; returns a problem."""
    kind, value = step["output"]
    target, known = _place(step["output"], coll, clip["clip_id"]), _known_files(state, ctx)
    if kind != "int":
        for _, file in files:
            owner = known.get((target.casefold(), file.casefold()))
            if owner and owner != clip["clip_id"]:
                return f"Namenskonflikt in {target}: {file} gehört zu Clip_ID {owner}"
        for _, file in files:
            if known.get((target.casefold(), file.casefold())) is None and _path(f"{target}/{file}").exists():
                _move(f"{target}/{file}", f"{target}/{unknown_dir}")
                _issue(ctx, "note", "Unbekannte Datei nach unbekannt verschoben", f"{target}/{file}",
                       f"{target}/{file} → {target}/{unknown_dir}/ (Namenskonflikt beim Ausliefern)")
    old = clip["sets"].get(name)
    for source, file in files:
        _move(source, target, file, replace=True)
        if kind != "int":
            known[(target.casefold(), file.casefold())] = clip["clip_id"]
    if old and old["slot"] and old["folder"] != target:
        _rmdir(old["folder"])
    clip["sets"][name] = _entry(target, [file for _, file in files], kind, value, step["name"])
    return None


def _take_outputs(state: dict, setup: dict, clip: dict, job: dict, ctx: dict) -> str | None:
    """Move the results of a successful job into the step output; returns a problem text instead."""
    step, coll, out = setup["steps"][job["step"]], _coll(setup, clip), job["output_folder"]
    delivered = {key: name for key, (name, size) in _scan(out).items() if size and not key.endswith(busy_suffixes)}
    try:
        if step["module"] == "restore":
            missing = [name for name in clip["master_files"] if name.casefold() not in delivered]
            if missing:
                return f"Restore unvollständig, fehlend: {', '.join(missing)}"
            return _store(state, clip, coll, step, master_set,
                          [(f"{out}/{delivered[name.casefold()]}", name) for name in clip["master_files"]], ctx)
        if step["module"] == "transcode":
            files = [name for key, name in delivered.items() if not key.endswith(protocol_suffixes)]
            if len(files) != 1:
                return f"Transcode-Ausgang enthält {len(files)} Dateien statt einer"
            base = _render(step["file_name"], _meta(clip))
            if not _matches(files[0], base):
                return f"Dateiname {files[0]!r} passt nicht zu {base!r}"
            return _store(state, clip, coll, step, step["name"], [(f"{out}/{files[0]}", files[0])], ctx)
        if step["output"] is None:
            return None
        entries = {name: clip["sets"].get(name) for name in job.get("input_sets", [])}
        for name, entry in entries.items():
            missing = [file for file in entry["names"] if not _path(f"{entry['folder']}/{file}").is_file()] if entry else [name]
            if missing:
                return f"{name} vor dem Verschieben nicht mehr vorhanden: {', '.join(missing)}"
        for name, entry in entries.items():
            problem = _store(state, clip, coll, step, name, [(f"{entry['folder']}/{file}", file) for file in entry["names"]], ctx)
            if problem:
                return problem
    except OSError as exc:
        return f"Verschieben in den Ausgang fehlgeschlagen: {exc}"
    return None


def _apply_report(state: dict, setup: dict, clip: dict, job: dict, report: dict, worker: str | None, ctx: dict) -> None:
    name, status, result = job["step"], report["status"], str(report.get("result") or "").strip()
    by, info = f"Worker {worker or 'unbekannt'}", report.get("info") or {}
    clip["job"] = None
    current = _next_step(setup, clip)
    if clip["ready"] or current is None or current["name"] != name:
        _event(clip, f"Ergebnis von {name} verworfen", "Step ist nicht mehr aktuell")
        _finish_output(job, True, ctx)
        return
    if info:
        clip["info"][name] = info
    if status == "rejected" and current["module"] != "qc":
        status = "failed"
    if status == "ok":
        _event(clip, f"{name} fertig", by + _info_text(info))
        problem = _take_outputs(state, setup, clip, job, ctx)
        if problem is None:
            clip["attempts"] = 0
            clip["done"].append(name)
            _finish_output(job, True, ctx)
            return
        status, result = "failed", problem
    if status == "rejected":
        _set_issue(clip, "sticky", qc_rejected, f"{name}: {result}")
        _event(clip, qc_rejected, f"{by}: {result}")
        _finish_output(job, True, ctx)
        return
    clip["attempts"] += 1
    _event(clip, f"{name} fehlgeschlagen", f"{by}: {result}")
    _finish_output(job, False, ctx)
    if clip["attempts"] >= cfg["max_job_attempts"]:
        _set_issue(clip, "sticky", job_failed, f"{name}, {clip['attempts']} Versuche: {result}")
    else:
        _issue(ctx, "note", "Job fehlgeschlagen – neuer Versuch", clip["clip_id"], f"{_clip_text(clip)}: {name}: {result}")


def _retire(folder: str, job_id: str, ctx: dict) -> None:
    """Archive job file and output folder of a job Marathon no longer tracks, if they exist."""
    found = _running(ctx, folder).get(f"{job_id}.json".casefold())
    if found:
        _move(f"{folder}/laufend/{found[0]}/{found[1]}", f"{folder}/archiv")
    if job_id.casefold() in _dirs(ctx, f"{folder}/{outbox}"):
        _move(f"{folder}/{outbox}/{job_id}", f"{folder}/archiv", f"{job_id}.{outbox}")


def _collect_reports(state: dict, setup: dict, folder: str, jobs: dict[str, dict], ctx: dict) -> None:
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
        _apply_report(state, setup, clip, job, report, _archive_job(job) or job.get("worker"), ctx)
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
        _issue(ctx, "note", "Job-Datei nicht auffindbar (wird beobachtet)", clip["clip_id"],
               f"{_clip_text(clip)}: {folder}/…/{name}")
    elif _age(job["missing_since"]) >= missing_job_grace:
        _issue(ctx, "note", "Job-Datei verschwunden – Job neu erstellt", clip["clip_id"],
               f"{_clip_text(clip)}: {folder}/…/{name}")
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


def _check_files(setup: dict, clip: dict, ctx: dict) -> tuple[str, str] | tuple[()]:
    job = clip["job"]
    if job and job["state"] == "laufend":
        return ()
    names = [name for name, entry in clip["sets"].items() if entry["delivered"] or
             (not clip["ready"] and name in clip["input_sets"])]
    for name in names:
        entry = clip["sets"][name]
        missing = _present(ctx, entry["folder"], entry["names"])
        if missing:
            return lost_file, (f"{name}: {entry['folder']}, fehlend: {', '.join(missing)}, "
                               f"zuletzt vollständig gesehen {entry['last_seen_at']}")
        entry["last_seen_at"] = _now()
    return ()


def _update_activity(clip: dict, ctx: dict) -> None:
    reasons = [reason for reason in (clip["issues"][kind] for kind in issue_kinds) if reason]
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
    for kind in issue_kinds:
        if clip["issues"][kind]:
            return status_codes.get(clip["issues"][kind]["category"], "ungueltig")
    if clip["ready"]:
        return "bereit"
    return "laufend" if clip["job"] and clip["job"]["state"] == "laufend" else "wartet"


def _external_folders(setup: dict, role: str) -> dict[str, list[dict]]:
    """External input or output folders -> collections that use them."""
    result = defaultdict(list)
    for coll in setup["collections"].values():
        for name in coll["steps"]:
            step = setup["steps"][name]
            specs = step["inputs"] if role == "input" else [step["output"]] if step["output"] else []
            for spec in specs:
                if spec[0] != "int" and coll not in result[_place(spec, coll, "")]:
                    result[_place(spec, coll, "")].append(coll)
    return result


def _sweep_outputs(state: dict, setup: dict, ctx: dict) -> None:
    known = _known_files(state, ctx)
    for folder in sorted(_external_folders(setup, "output")):
        for key, (name, size) in sorted(_listing(ctx, folder).items()):
            if (folder.casefold(), key) in known or _ignored(name):
                continue
            relative = f"{folder}/{name}"
            if cfg["report_only"]:
                _issue(ctx, "note", "Unbekannte Datei im Ausgang (report_only – nicht verschoben)", relative, relative)
                continue
            if not _stable(state, ctx, relative, size):
                continue
            try:
                moved = _move(relative, f"{folder}/{unknown_dir}")
            except OSError as exc:
                _issue(ctx, "note", "Unbekannte Datei noch in Benutzung (nächster Versuch im nächsten Zyklus)", relative,
                       f"{relative}: {exc}")
                continue
            if moved:
                _issue(ctx, "note", "Unbekannte Datei nach unbekannt verschoben", relative,
                       f"{relative} → {folder}/{unknown_dir}/")


def _leftovers(state: dict, setup: dict, ctx: dict) -> None:
    clips = state["clips"].values()
    folders = {entry["folder"].casefold() for clip in clips for entry in clip["sets"].values()}
    files = {(entry["folder"].casefold(), name.casefold()) for clip in clips for entry in clip["sets"].values()
             for name in entry["names"]}
    jobs = {clip["job"]["id"] for clip in clips if clip["job"]}
    wanted = {name.casefold() for clip in clips for name in clip["master_files"]}
    wanted |= {_normalize(_render(template, _meta(clip))) for clip in clips for _, template in setup["templates"]}
    for coll in setup["collections"].values():
        for slot in _subfolders(coll["work"]):
            if slot.casefold() == jobs_dir:
                for step in _subfolders(f"{coll['work']}/{jobs_dir}"):
                    outputs = f"{coll['work']}/{jobs_dir}/{step}/{outbox}"
                    for job_id in sorted(set(_subfolders(outputs)) - jobs):
                        _issue(ctx, "note", "Ausgang ohne aktuellen Job", f"{outputs}/{job_id}", f"{outputs}/{job_id}")
                continue
            for clip_id in _subfolders(f"{coll['work']}/{slot}"):
                folder = f"{coll['work']}/{slot}/{clip_id}"
                if folder.casefold() not in folders:
                    _issue(ctx, "note", "Ordner ohne passenden Clip (Arbeitsordner)", folder, folder)
    for folder in sorted(_external_folders(setup, "input")):
        for key, (name, size) in sorted(_listing(ctx, folder).items()):
            if _ignored(name) or (folder.casefold(), key) in files or not size:
                continue
            match = key in wanted or _normalize(name) in wanted or _normalize(Path(name).stem) in wanted
            if match or not key.endswith(protocol_suffixes):
                category = "Datei im Eingang nicht übernommen (Clip schon weiter, inaktiv, mehrdeutig oder unvollständig)" \
                    if match else "Datei im Eingang ohne passenden Clip"
                _issue(ctx, "note", category, f"{folder}/{key}", f"{folder}/{name}")


def _job_payload(setup: dict, clip: dict, step: dict, coll: dict, job_id: str, folder: str) -> dict:
    payload = {"schema_version": 3, "job_id": job_id, "module": step["module"], "step": step["name"],
               "pipeline": coll["pipeline"], "order_list": coll["order_list"], "collection": clip["collection"],
               "clip_id": clip["clip_id"], "identifier": clip["identifier"], "title": clip["title"],
               "clip_name": clip["clip_name_with_extension"], "params": step["params"],
               "inputs": [f"{clip['sets'][name]['folder']}/{file}" for name in clip["input_sets"]
                          for file in clip["sets"][name]["names"]],
               "output_folder": f"{folder}/{outbox}/{job_id}", "report_folder": f"{folder}/fertig", "created_at": _now()}
    if step["module"] == "restore":
        payload.update(hashes=clip["filehashes"], files=clip["master_files"])
    elif step["module"] == "transcode":
        payload["file_name"] = _render(step["file_name"], _meta(clip))
    return payload


def _create_job(setup: dict, clip: dict) -> None:
    step, coll = setup["steps"][clip["step"]], _coll(setup, clip)
    folder = _job_folder(coll, step["name"])
    clip["job_count"] += 1
    job_id = f"{clip['queued_at']}__{clip['clip_id']}__{step['name']}{clip['job_count']}"
    payload = _job_payload(setup, clip, step, coll, job_id, folder)
    _path(payload["output_folder"]).mkdir(parents=True, exist_ok=True)
    _write_text_atomic(_path(f"{folder}/offen/{job_id}.json"), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    clip["job"] = {"id": job_id, "step": step["name"], "module": step["module"], "folder": folder, "file": f"{job_id}.json",
                   "output_folder": payload["output_folder"], "input_sets": list(clip["input_sets"]), "state": "offen",
                   "worker": None, "created_at": payload["created_at"], "running_since": None, "missing_since": None}
    _event(clip, f"{step['name']}-Job erstellt", job_id)


def _schedule(state: dict, setup: dict) -> None:
    clips = state["clips"].values()
    for clip in clips:
        job, coll = clip["job"], _coll(setup, clip)
        expected = _job_folder(coll, clip["step"]) if coll and clip["step"] and not clip["ready"] else None
        if job and (not clip["active"] or clip["waiting"] or job.get("outdated") or job["folder"] != expected
                    or job["step"] != clip["step"] or job.get("input_sets", []) != clip["input_sets"]):
            _withdraw(clip)
    pools = defaultdict(list)
    for clip in clips:
        step = setup["steps"].get(clip["step"]) if clip["step"] else None
        if (step and clip["active"] and not clip["ready"] and not clip["waiting"] and _coll(setup, clip)
                and (clip["job"]["state"] == "offen" if clip["job"] else True)):
            pools[step["module"]].append(clip)
    for module, pool in pools.items():
        if module not in job_modules:
            continue
        pool.sort(key=lambda clip: (setup["collections"][clip["collection"]]["rank"], clip["queued_at"]))
        limit = cfg[module]
        for clip in pool[limit:]:
            if clip["job"]:
                _withdraw(clip)
        for clip in pool[:limit]:
            if clip["job"] is None:
                _create_job(setup, clip)


def _handle_clip(state: dict, setup: dict, clip: dict, ctx: dict, writing: bool) -> None:
    coll = _coll(setup, clip)
    _set_issue(clip, "setup", *(() if coll else (no_order, f"Kollektion {clip['collection']!r}")))
    if coll and not clip["ready"]:
        clip["order_list"], clip["pipeline"] = coll["order_list"], coll["pipeline"]
        _sync_step(setup, clip)
        _shortcut(state, setup, clip, coll, ctx)
    _set_issue(clip, "file", *_check_files(setup, clip, ctx))
    _update_activity(clip, ctx)
    if coll and not clip["ready"] and clip["active"]:
        _move_on(state, setup, clip, coll, ctx, writing)
    elif not clip["ready"]:
        clip["waiting"], clip["input_sets"] = False, []


def _process(state: dict, setup: dict, ctx: dict) -> None:
    clips, writing = state["clips"], not cfg["report_only"]
    _read_workers(state)
    if writing:
        _ensure_folders(setup)
        _write_priority_file(setup)
        jobs = {clip["job"]["id"]: clip for clip in clips.values() if clip["job"]}
        folders = sorted({_job_folder(coll, name) for coll in setup["collections"].values() for name in coll["steps"]
                          if modules[setup["steps"][name]["module"]][0]} | {clip["job"]["folder"] for clip in jobs.values()})
        for folder in folders:
            _collect_reports(state, setup, folder, jobs, ctx)
        ctx["listings"].clear()  # Reports moved files around.
        ctx["indexes"].clear()
        for clip in clips.values():
            if clip["job"]:
                _locate_job(clip, ctx)
        known = {clip["job"]["file"].casefold() for clip in clips.values() if clip["job"]}
        for folder in folders:
            _sweep_unknown_jobs(folder, known, ctx)
    claims = defaultdict(set)
    for clip in clips.values():
        if clip["active"] and not clip["ready"] and master_set not in clip["sets"]:
            for name in clip["master_files"]:
                claims[name.casefold()].add(clip["clip_id"])
    ctx["claims"] = claims
    for clip_id in sorted(clips, key=int):
        _handle_clip(state, setup, clips[clip_id], ctx, writing)
    _sweep_outputs(state, setup, ctx)
    if writing:
        _schedule(state, setup)
    for clip in clips.values():
        clip["status"] = _status(clip)
    for key in set(state["files_seen"]) - ctx["touched"]:
        del state["files_seen"][key]


# --------- FUNC: REPORT ---------
def _totals(state: dict, setup: dict) -> dict[str, list[int]]:
    """Active clips per collection: Gesamt, Bereit and one count per step of its pipeline."""
    totals = {name: [0] * (2 + len(coll["steps"])) for name, coll in setup["collections"].items()}
    for clip in state["clips"].values():
        row, coll = totals.get(clip["collection"]), _coll(setup, clip)
        if row is None or not clip["active"]:
            continue
        row[0] += 1
        if clip["ready"]:
            row[1] += 1
        elif clip["step"] in coll["steps"]:
            row[2 + coll["steps"].index(clip["step"])] += 1
    return totals


def _previous(kind: str) -> Path | None:
    files = sorted(reports_dir.glob(f"{kind}_*.txt"))
    return files[-1] if files else None


def _read_previous(path: Path | None) -> dict[tuple[str, str], dict[str, float]]:
    """(order list, row) -> counts of the previous report; the overview table uses the order list ""."""
    if path is None:
        return {}
    result, header, current = {}, None, None
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.split("|")]
        if not line.strip():
            header = None
        elif parts[0] in (fixed_columns[0], order_label) and len(parts) > 1:
            header = parts
        elif line.startswith(f"{order_label} "):
            current, header = line[len(order_label) + 1:].split(" | ")[0].strip(), None
        elif line.strip() == overview_title:
            current, header = "", None
        elif current is not None and header and len(parts) == len(header) and parts[0]:
            try:
                result[(current, parts[0])] = {column: (float if column == "%" else int)(cell.split()[0])
                                               for column, cell in zip(header[1:], parts[1:]) if column != "Prio"}
            except (ValueError, IndexError) as exc:
                raise ValueError(f"Vorgängerbericht {path.name} ist nicht lesbar.") from exc
    return result


def _format_int(value: int, previous: int | None) -> str:
    return str(value) if previous is None else f"{value} ({value - previous:+d})"


def _row(name: str, prio: tuple[str, ...], counts: dict[str, int], old: dict) -> tuple[str, ...]:
    total, ready = counts["Gesamt"], counts["Bereit"]
    percent = 100 * ready / total if total else 0.0
    percent_text = (f"{percent:.1f}" if total else "0") + " %"
    if "%" in old:
        percent_text += f" ({round(round(percent, 1) - old['%'], 1) + 0.0:+.1f} pp)"  # + 0.0 avoids "-0.0".
    cells = [_format_int(value, old.get(column)) for column, value in counts.items()]
    return name, *prio, cells[0], cells[1], percent_text, *cells[2:]


def _table(columns: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    widths = [max(len(row[index]) for row in (columns, *rows)) for index in range(len(columns))]

    def line(cells) -> str:
        return " | ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()

    separator = "-+-".join("-" * width for width in widths)
    return [line(columns), separator, *(line(row) for row in rows[:-1]), separator, line(rows[-1])]


def _render_tables(setup: dict, totals: dict[str, list[int]], previous: dict) -> list[str]:
    lines, overview = [], []
    for order in setup["orders"]:
        steps = setup["pipelines"][order["pipeline"]]["steps"]
        columns, rows = ("Gesamt", "Bereit", *steps), []
        summary = [sum(values) for values in zip(*(totals[coll["name"]] for coll in order["collections"]))]
        for name, prio, values in (*((coll["name"], str(coll["prio"] or ""), totals[coll["name"]])
                                     for coll in order["collections"]), (summary_name, "", summary)):
            rows.append(_row(name, (prio,), dict(zip(columns, values)), previous.get((order["name"], name), {})))
        lines += [f"{order_label} {order['name']} | Pipeline {order['pipeline']}: {' --> '.join(steps)}",
                  *_table((*fixed_columns, *steps), rows), ""]
        overview.append((order["name"], summary[:2]))
    overview.append((summary_name, [sum(values[index] for _, values in overview) for index in range(2)]))
    rows = [_row(name, (), dict(zip(("Gesamt", "Bereit"), values)), previous.get(("", name), {})) for name, values in overview]
    return [*lines, overview_title, *_table((order_label, *fixed_columns[2:]), rows)]


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


def _report(kind: str, setup: dict) -> Path:
    started = perf_counter()
    _log(f"{kind}-Bericht gestartet.")
    _check_root()
    state = _load_state()
    ctx = _context()
    ctx["issues"].extend(state["notes"])
    state["notes"] = []
    for category, name in setup["notes"]:
        _issue(ctx, "note", category, name, name)
    found = _search_clips(setup, ctx)
    _reconcile(state, setup, found, ctx)
    _process(state, setup, ctx)
    ctx["listings"].clear()
    ctx["indexes"].clear()
    _leftovers(state, setup, ctx)
    totals = _totals(state, setup)
    try:
        previous = _read_previous(_previous(kind))
    except (OSError, UnicodeError, ValueError) as exc:
        previous = {}
        _issue(ctx, "note", "Vorbericht nicht lesbar – keine Deltas", "previous", str(exc))
    when = datetime.now().astimezone()
    name = f"{kind}_{when.strftime('%Y-%m-%d_%H-%M-%S-%f')}"
    watch, workers = _watch_lines(state), _worker_lines(state)
    text = f"{app_name} {app_version} | {kind} | {when.isoformat(timespec='seconds')}\n\n"
    text += "\n".join(_render_tables(setup, totals, previous)) + "\n\n" + "\n".join(_summary_lines(ctx["issues"])) + "\n"
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
         f"{len(state['clips'])} Clips im Zustand; {len(ctx['issues'])} Meldungen; {len(watch)} auffällige Jobs; "
         f"Dauer: {perf_counter() - started:.1f} s.")
    return path


# --------- FUNC: RUN ---------
def _load_all() -> tuple[str | None, dict | None]:
    """Config, pipelines and order lists; returns (reason to pause, None) instead of running with wrong input."""
    problem = _load_config()
    if problem:
        return problem, None
    try:
        return None, _load_setup()
    except (OSError, UnicodeError, ValueError) as exc:
        return f"Pipelines oder Auftragslisten fehlerhaft – Marathon pausiert, bis sie korrigiert sind: {exc}", None


def _cycle(setup: dict) -> str | None:
    """Run one job cycle with the loaded setup; returns the reason if it was skipped."""
    if cfg["report_only"]:
        return "Job-Zyklus übersprungen: report_only ist aktiv."
    if not state_path.exists():
        return "Job-Zyklus wartet auf den ersten Bericht (noch kein Zustand; Befehl 'report')."
    _check_root()
    state = _load_state()
    ctx = _context()
    _process(state, setup, ctx)
    known = {(item["category"], item["key"], item["detail"]) for item in state["notes"]}
    for item in ctx["issues"]:
        key = (item["category"], item["key"], item["detail"])
        if item["section"] == "note" and item["category"] not in transient_notes and key not in known:
            state["notes"].append(item)
            known.add(key)
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


def _log_failure(message: str) -> None:
    _log(message)
    tb_write_log(main_log, traceback.format_exc())


# --------- MAIN ---------
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Marathon: Pipeliner mit Suchabgleich, Job-Steuerung und Berichten")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--manual", action="store_true", help="Manuellen Bericht erstellen und beenden")
    modes.add_argument("--auto-once", action="store_true", help="Auto-Bericht erstellen und beenden")
    modes.add_argument("--cycle-once", action="store_true", help="Einen Job-Zyklus ausführen und beenden")
    args = parser.parse_args(argv)
    _prepare()
    _acquire_lock()
    _log(f"{app_name} {app_version} gestartet.")
    if args.manual or args.auto_once or args.cycle_once:
        problem, setup = _load_all()
        if problem:
            raise RuntimeError(problem)
        if args.cycle_once:
            skipped = _cycle(setup)
            if skipped:
                _log(skipped)
        else:
            _report("manual" if args.manual else "auto", setup)
        return
    commands: queue.Queue[str] = queue.Queue()
    threading.Thread(target=_console, args=(commands,), daemon=True).start()
    _log("Marathon läuft. 'report' = manueller Bericht, 'quit' = beenden.")
    next_retry, next_cycle = None, datetime.now().astimezone()
    last_problem, last_mode, last_cycle = None, None, None
    while True:
        problem, setup = _load_all()
        if problem != last_problem:
            _log(problem or "Konfiguration, Pipelines und Auftragslisten gültig – Marathon arbeitet weiter.")
            last_problem = problem
        now = datetime.now().astimezone()
        if not problem and cfg["report_only"] != last_mode:
            _log("report_only aktiv: keine Jobs." if cfg["report_only"] else "Jobbetrieb aktiv.")
            last_mode = cfg["report_only"]
        if not problem and _auto_due(now) and (next_retry is None or now >= next_retry):
            try:
                _report("auto", setup)
                next_retry = None
            except Exception as exc:
                next_retry = now + timedelta(minutes=cfg["retry_minutes"])
                _log_failure(f"Auto-Bericht fehlgeschlagen: {exc}; erneuter Versuch in {cfg['retry_minutes']} min.")
        if not problem and not cfg["report_only"] and now >= next_cycle:
            try:
                outcome = _cycle(setup)
            except Exception as exc:
                outcome = f"Job-Zyklus fehlgeschlagen: {exc}; Zustand unverändert."
                if outcome != last_cycle:
                    _log_failure(outcome)
            else:
                if outcome != last_cycle:
                    _log(outcome or "Job-Zyklen laufen.")
            last_cycle = outcome
            next_cycle = now + timedelta(seconds=cfg["cycle_seconds"])
        try:
            command = commands.get(timeout=5)
        except queue.Empty:
            continue
        if command == "report" and problem:
            _log(f"Kein Bericht während der Pause: {problem}")
        elif command == "report":
            try:
                _report("manual", setup)
            except Exception as exc:
                _log_failure(f"Manueller Bericht fehlgeschlagen: {exc}")
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
            tb_write_log(main_log, traceback.format_exc())
        except OSError:
            pass
        raise SystemExit(1) from exc
