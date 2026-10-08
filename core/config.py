"""Project paths, config schema and loading of res/config.ini into cfg."""
# --------- IMPORTS ---------
import configparser
import string
from datetime import time
from pathlib import Path

from .constants import busy_suffixes, ffe_clip_suffix, ffe_share_keys, invalid_path_chars, limit_keys, system_files


# --------- CONFIG ---------
project_dir = Path(__file__).resolve().parent.parent
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
              "proxy_name": "pattern", "cred_file": "text", "mapping_file": "text", "priority_file": "text"},
    "operation": {"auto_report_time": "time", "retry_minutes": "number"},
    "timing": {"cycle_seconds": "number", "max_job_attempts": "number"},
    "limits": {key: "count" for key in limit_keys.values()},
    "heartbeat": {"worker_timeout_minutes": "number", "max_job_hours": "number"},
    "veritone": {"base_url": "text", "token_file": "text", "field_clip_id": "text"},
    "ffe": {"list_file": "text", "reference_image": "name", "reference_clip_dir": "name"},
    "ingest": {"master_dir": "text", "proxy_dir": "text", "proxy_prefix": "text"},
}


# --------- INIT ---------
cfg: dict = {}


# --------- FUNC ---------
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
    if kind == "pattern":
        try:
            parts = list(string.Formatter().parse(raw))
        except ValueError:
            parts = None
        literal = "".join(text for text, *_ in parts or ())
        if not parts or sorted(field for _, field, _, _ in parts if field is not None) != ["clip_id", "veritone_id"] or \
                any(spec or conversion for _, _, spec, conversion in parts) or any(char in invalid_path_chars for char in literal) or \
                not Path(literal).suffix:
            raise ValueError("erwartet einen Dateinamen mit genau {veritone_id} und {clip_id} und Endung, "
                             "z. B. {veritone_id}_{clip_id}_10Mbit.mp4")
        return raw
    if kind == "name" and (any(char in invalid_path_chars for char in raw) or raw in (".", "..") or raw != raw.rstrip(". ")):
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
    for section, key in (("paths", "mapping_file"), ("paths", "cred_file"), ("veritone", "token_file"),
                         ("ffe", "list_file")):
        if key in values and not (res_dir / values[key]).is_file():
            problems.append(f"[{section}] {key}: Datei {res_dir / values[key]} fehlt")
    if "reference_clip_dir" in values:
        folder = res_dir / values["reference_clip_dir"]
        if not folder.is_dir() or not any(is_clip(path) for path in folder.iterdir()):
            problems.append(f"[ffe] reference_clip_dir: Ordner {folder} fehlt oder enthält keine {ffe_clip_suffix}-Dateien")
        elif "reference_image" in values and not (folder / values["reference_image"]).is_file():
            problems.append(f"[ffe] reference_image: Datei {folder / values['reference_image']} fehlt")
    if problems:
        raise ValueError("; ".join(problems))
    return values


def load_config() -> str | None:
    """Load res/config.ini into cfg; returns the reason why Marathon has to pause instead."""
    try:
        values = _read_config()
    except FileNotFoundError:
        return f"{config_path} fehlt – Marathon pausiert, bis die Datei vorhanden ist."
    except (OSError, UnicodeError, configparser.Error, ValueError) as exc:
        return f"{config_path.name} fehlerhaft – Marathon pausiert, bis sie korrigiert ist: {exc}"
    changed = [key for key in (*config_schema["paths"], *ffe_share_keys) if cfg and values[key] != cfg[key]]
    if changed:
        return (f"Änderung in [paths]/[ffe] ({', '.join(changed)}) – Marathon pausiert; "
                f"Neustart nötig oder Änderung zurücknehmen.")
    cfg.update(values)
    return None


def ignored(name: str) -> bool:
    """True for system, hidden and temporary files that never count as content."""
    key = name.casefold()
    return key in system_files or name.startswith((".", "~$")) or key.endswith(busy_suffixes)


def is_clip(path: Path) -> bool:
    """True for an FFE title clip file (suffix ffe_clip_suffix, not ignored)."""
    return path.is_file() and path.suffix.casefold() == ffe_clip_suffix and not ignored(path.name)
