# --------- IMPORTS ---------
import argparse
import configparser
import json
import os
import re
import shutil
import tempfile
import traceback
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from toolbox import tb_write_log

# --------- STATIC ---------
invalid_path_chars = frozenset('<>:"/\\|?*' + "".join(map(chr, range(32))))
system_files = frozenset({"thumbs.db", "desktop.ini", ".ds_store"})
busy_suffixes = (".tmp", ".part", ".partial")
save_every = 100
api_identifier, api_title = "001 Identifier", "014 Title Original"
lookup_fields = ("clip_id", api_identifier, api_title, "006 Source PROGRESS", "007 Collection PROGRESS", "101a Genre German",
                 "status_flags")
lookup_chunk = 50  # Identifiers per API search
# Clip Flattener naming rules: DEFA + digits [+ _suffix]; "Titel, Teil 1/2"; name segment T1/P1/Hermlin -> ID suffix _1
defa_id_pattern = re.compile(r"(?i)defa[\s_.-]*(\d+)(?:_([a-z]|\d+))?")
combined_parts_pattern = re.compile(r"(?i)^(.+?),\s*teil\s+(\d+)\.?\s*/\s*(\d+)\.?\s*$")
numbered_variant_pattern = re.compile(r"[pt](\d+)")
named_variants = {"hermlin": 1, "schnitzler": 2}
error_labels = {  # Order of the categories in the error list
    "schema": "Nicht im Namensschema",
    "subfolder": "Unterordner wird nicht verarbeitet",
    "empty": "Datei ist leer",
    "skipped": "Von Marathon beim Indexieren nicht aufgenommen",  # + ": <Marathon category>"
    "expected": "Nicht in der JSON und nicht als übersprungen gemeldet, obwohl in einer gesuchten Kollektion "
                "(erst 'update-index' in Marathon)",
    "title": "Nicht in der JSON: DEFA-ID in der API nur mit anderem Suffix, Titel weicht ab",
    "no_hit": "Nicht in der JSON: DEFA-ID nicht in der API",
    "api_failed": "Nicht in der JSON: API-Suche fehlgeschlagen",
    "ambiguous": "Mehrere JSON-Einträge passen zur Datei",
    "not_defa": "Clip gehört nicht zu DEFA",
    "inactive": "Clip inaktiv oder mit offenem Problem",
    "not_queued": "Clip nicht mehr in der Restore-Queue",
    "multi_files": "Mehrere AQC-Dateien für denselben Clip",
    "no_inbox": "QC-Eingang fehlt (erst 'create-folders' in Marathon)",
    "exists": "Datei existiert bereits im QC-Eingang",
    "move_failed": "Verschieben fehlgeschlagen",
}

# --------- CONFIG ---------
app_name = "AQC-Sort"
app_version = "0.7.1"
project_dir = Path(__file__).resolve().parent
config_path = project_dir / "res" / "config.ini"  # Marathon's config
state_dir = project_dir / "state"
state_path = state_dir / "marathon.json"
lock_path = state_dir / "marathon.lock"  # Same lock as Marathon: never run both at once.
backup_dir = state_dir / "backup"
output_dir = project_dir / "reports" / "aqc"
main_log = project_dir / "log" / "aqc_sort.log"
aqc_dir = "AQC"  # Below defa_dir

# --------- INIT ---------
main_log.parent.mkdir(parents=True, exist_ok=True)
tb_write_log(main_log, f"{app_name} {app_version} started.")
lock_handle = None


# --------- FUNC: SETUP ---------
def _log(message: str) -> None:
    print(message, flush=True)
    tb_write_log(main_log, message)


def _read_config() -> dict[str, str]:
    parser = configparser.ConfigParser(interpolation=None)
    with config_path.open(encoding="utf-8-sig") as handle:
        parser.read_file(handle)
    keys = ("root_path", "defa_dir", "work_dir", "defa_marker", "proxy_prefix", "cred_file", "mapping_file")
    values = {key: parser.get("paths", key, fallback="").strip() for key in keys}
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ValueError(f"In {config_path} fehlt [paths] {', '.join(missing)}.")
    return values


def _load_mapping(cfg: dict) -> list[dict]:
    path = config_path.parent / cfg["mapping_file"]
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    entries = document.get("collections") if isinstance(document, dict) and document.get("schema_version") == 1 else None
    valid = isinstance(entries, list) and entries and all(
        isinstance(entry, dict) and isinstance(entry.get("name"), str) and isinstance(entry.get("filters"), list) and entry["filters"]
        and all(isinstance(item, dict) and isinstance(item.get("value"), str) and item.get("field") in lookup_fields
                for item in entry["filters"]) for entry in entries)
    if not valid:
        raise ValueError(f"Kollektionsmapping {path}: unbekanntes Format oder Suchfeld außerhalb von {', '.join(lookup_fields[3:6])}.")
    return entries


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
        raise RuntimeError(f"Marathon läuft (Sperre {lock_path}). Erst 'quit' in Marathon, dann AQC-Sort.") from exc
    lock_handle = handle  # The OS releases the lock when the process ends.


def _load_state() -> dict:
    if not state_path.is_file():
        raise FileNotFoundError(f"Kein Marathon-Zustand: {state_path}. Erst 'update-index' in Marathon.")
    with state_path.open(encoding="utf-8") as handle:
        state = json.load(handle)
    if not isinstance(state, dict) or state.get("schema_version") != 4 or not isinstance(state.get("clips"), dict):
        raise ValueError("Unbekanntes Zustandsformat (erwartet: Marathon-JSON Version 4). Nichts geändert.")
    return state


def _save_state(state: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=state_dir, prefix=".marathon-",
                                         suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, state_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


# --------- FUNC: MARATHON RULES ---------
def _normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().casefold()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")


def _folder_key(name: str) -> str:
    key = "".join("_" if char in invalid_path_chars else char for char in unicodedata.normalize("NFC", name))
    return key.strip().rstrip(". ")


def _qc_inbox(cfg: dict, collection: str) -> Path:
    return Path(cfg["root_path"]) / cfg["defa_dir"] / cfg["work_dir"] / _folder_key(collection) / "qc" / "eingang"


def _proxy_parts(name: str, prefix: str) -> tuple[str, str] | None:
    """(identifier, rest) from <prefix>__<identifier>__<rest>; rest = title, name segments and extension."""
    prefix += "__"
    if not name.casefold().startswith(prefix.casefold()):
        return None
    identifier, separator, rest = name[len(prefix):].partition("__")
    if not separator or not identifier.strip() or not rest.strip():
        return None
    return unicodedata.normalize("NFC", identifier).strip(), rest


def _ignored(name: str) -> bool:
    key = name.casefold()
    return key in system_files or name.startswith((".", "~$")) or key.endswith(busy_suffixes)


# --------- FUNC: CLIP FLATTENER NAMES ---------
def _id_keys(value: str) -> tuple[str, str]:
    """(full, base) key of a DEFA ID as the Clip Flattener writes it (DEFA + digits [+ _suffix]); other IDs normalized."""
    match = defa_id_pattern.fullmatch(unicodedata.normalize("NFC", value).strip())
    if not match:
        key = _normalize(value)
        return key, key
    base, suffix = f"DEFA{match.group(1)}", match.group(2) or ""
    suffix = str(int(suffix)) if suffix.isdigit() else suffix.upper()
    return (f"{base}_{suffix}" if suffix else base), base


def _variant(segments: tuple[str, ...] | list[str]) -> str:
    """DEFA ID suffix the Clip Flattener derives from a name segment T1/P1/Hermlin/Schnitzler; "" if there is none."""
    for segment in (value.casefold() for value in segments):
        if match := numbered_variant_pattern.fullmatch(segment):
            return str(int(match.group(1)))
        if segment in named_variants:
            return str(named_variants[segment])
    return ""


def _title_suffixes(rest: str, title: str) -> tuple[str, ...] | None:
    """Casefolded name segments after the title if <rest> starts with the title as the Clip Flattener writes it
    (invalid characters as "_", "Titel, Teil 1/2" also as "Titel"); None if the title does not match."""
    combined = combined_parts_pattern.fullmatch(title)
    keys = {_folder_key(value).casefold() for value in (title, combined.group(1) if combined else "")} - {""}
    for name in dict.fromkeys(unicodedata.normalize("NFC", value).casefold() for value in (Path(rest).stem, rest)):
        for key in keys:
            if name == key:
                return ()
            if name.startswith(f"{key}__"):
                return tuple(name[len(key) + 2:].split("__"))
    return None


def _matches(identifier: str, rest: str, records: list[tuple]) -> tuple[list, list]:
    """(matches, base matches): payloads of the records (payload, full DEFA keys, title) whose title fits the name;
    like the Clip Flattener the exact DEFA ID wins, then the ID suffix of a variant segment (T1 -> _1). Records with
    only the same DEFA base are no match: the file's exact ID can exist outside the JSON (DEFA09240 vs. DEFA09240_A)."""
    full, base = _id_keys(identifier)
    titled = [(payload, keys, segments) for payload, keys, title in records
              if (segments := _title_suffixes(rest, title)) is not None]
    exact = [payload for payload, keys, _ in titled if full in keys]
    variant = [payload for payload, keys, segments in titled if (number := _variant(segments)) and f"{base}_{number}" in keys]
    return exact or variant, [payload for payload, _, _ in titled]


# --------- FUNC: MATCHING ---------
def _blocker(clip: dict, cfg: dict) -> tuple[str, str] | None:
    if cfg["defa_marker"].casefold() not in clip["collection"].casefold():
        return "not_defa", f"Kollektion={clip['collection']}"
    if not clip["active"] or any(clip["issues"].values()):
        return "inactive", f"Status={clip['status']}"
    if clip["ready"] or clip["stage"] != "restore" or clip["job"] or clip["files"].get("proxy"):
        return "not_queued", f"Stufe={clip['stage']}, Status={clip['status']}"
    return None


def _scan(cfg: dict, state: dict, source: Path) -> tuple[list[tuple], list[tuple[str, str, str]], list[tuple]]:
    """(file, Clip_ID, False) for files matching one JSON clip by DEFA ID and title, errors (category, name, detail)
    and (file, identifier, rest, IDs of JSON clips with the same DEFA base and title) of the other files."""
    by_base = defaultdict(list)
    for clip_id, clip in state["clips"].items():
        if identifier := str(clip.get("identifier") or "").strip():
            full, base = _id_keys(identifier)
            by_base[base].append((clip_id, {full}, str(clip.get("title") or "")))
    found, errors, missing = [], [], []
    for item in sorted(source.iterdir(), key=lambda path: path.name.casefold()):
        if item.is_dir():
            errors.append(("subfolder", f"{item.name}{os.sep}", ""))
            continue
        if not item.is_file() or _ignored(item.name):
            continue
        if not (parts := _proxy_parts(item.name, cfg["proxy_prefix"])):
            errors.append(("schema", item.name, ""))
            continue
        if not item.stat().st_size:
            errors.append(("empty", item.name, ""))
            continue
        ids, base_ids = _matches(*parts, by_base.get(_id_keys(parts[0])[1], []))
        ids = sorted(ids, key=int)
        if len(ids) > 1:
            errors.append(("ambiguous", item.name, f"Clip_IDs={', '.join(ids)}"))
        elif ids:
            found.append((item, ids[0], False))
        else:
            missing.append((item, *parts, [state["clips"][clip_id]["identifier"] for clip_id in base_ids]))
    return found, errors, missing


def _plan_moves(cfg: dict, clips: dict, found: list[tuple]) -> tuple[list[dict], list[tuple[str, str, str]]]:
    """Moves for clips with exactly one AQC file and a free QC inbox; errors for the other files."""
    errors, candidates = [], defaultdict(list)
    for item, clip_id, via_api in found:
        if problem := _blocker(clips[clip_id], cfg):
            errors.append((problem[0], item.name, f"{problem[1]}; Clip_ID={clip_id}"))
        else:
            candidates[clip_id].append((item, via_api))
    moves = []
    for clip_id, files in candidates.items():
        target = _qc_inbox(cfg, clips[clip_id]["collection"])
        problem = (("multi_files", ", ".join(path.name for path, _ in files)) if len(files) > 1
                   else ("no_inbox", str(target)) if not target.is_dir()
                   else ("exists", str(target)) if (target / files[0][0].name).exists() else None)
        if problem:
            errors += [(problem[0], path.name, f"{problem[1]}; Clip_ID={clip_id}") for path, _ in files]
        else:
            moves.append({"clip_id": clip_id, "source": files[0][0], "target": target, "via_api": files[0][1]})
    return sorted(moves, key=lambda move: move["source"].name.casefold()), errors


# --------- FUNC: TRANSFER ---------
def _take_over(clip: dict, move: dict, cfg: dict) -> None:
    folder = move["target"].relative_to(cfg["root_path"]).as_posix()
    clip["files"]["proxy"] = {"folder": folder, "name": move["source"].name, "source": "AQC", "last_seen_at": _now()}
    clip.update(stage="qc", queued_at=_stamp(), status="wartet")
    clip["history"].append({"at": _now(), "event": "Aus AQC übernommen – wartet auf QC", "position": "Queue QC",
                            "detail": f"{cfg['defa_dir']}/{aqc_dir}/{move['source'].name}"})


def _apply(cfg: dict, state: dict, moves: list[dict], errors: list[tuple[str, str, str]]) -> list[dict]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"marathon_before_aqc_{datetime.now():%Y-%m-%d_%H-%M-%S}.json"
    shutil.copyfile(state_path, backup)
    _log(f"Sicherung des Zustands: {backup}")
    done, pending = [], 0
    try:
        for move in moves:
            target = move["target"] / move["source"].name
            try:
                if target.exists():
                    raise FileExistsError("Zieldatei existiert bereits")
                os.rename(move["source"], target)
            except OSError as exc:
                errors.append(("move_failed", move["source"].name, f"{exc}; Clip_ID={move['clip_id']}"))
                continue
            _take_over(state["clips"][move["clip_id"]], move, cfg)
            done.append(move)
            pending += 1
            if pending >= save_every:
                state["updated_at"] = _now()
                _save_state(state)
                pending = 0
                _log(f"{len(done)} von {len(moves)} übernommen.")
    finally:
        # Also on Ctrl+C or an unexpected error: moved files must be recorded.
        if pending:
            state["updated_at"] = _now()
            _save_state(state)
    return done


# --------- FUNC: API LOOKUP ---------
def _search_values(identifier: str, rest: str) -> list[str]:
    """001 values to search for a file: as named, canonical, base ID and the ID of a variant segment (T1 -> _1)."""
    full, base = _id_keys(identifier)
    variant = _variant(Path(rest).stem.split("__")[1:])
    return list(dict.fromkeys((identifier, full, base) + ((f"{base}_{variant}",) if variant else ())))


def _search_identifiers(cfg: dict, identifiers: list[str]) -> dict[str, list[dict]]:
    """API rows per DEFA base key, row["keys"] = full keys of its 001 values; raises RuntimeError if a search is incomplete."""
    import searcher

    searcher.link("api", config_path.parent / cfg["cred_file"])
    found, seen = defaultdict(list), set()
    for start in range(0, len(identifiers), lookup_chunk):
        chunk = identifiers[start:start + lookup_chunk]
        request = tuple(part for index, value in enumerate(chunk)
                        for part in (("or",) if index else ()) + ((api_identifier, "is", value),))
        matches, _, error = searcher.find({"name": f"{app_name} {api_identifier} {start + 1}-{start + len(chunk)}",
                                           "request_fields": request, "return_fields": lookup_fields})
        if error:
            raise RuntimeError(error)
        for row in matches:
            if len(row) != len(lookup_fields):
                continue
            values = dict(zip(lookup_fields, map(str, row)))
            keys = [_id_keys(part) for part in values[api_identifier].split("; ") if part.strip()]
            values["keys"] = {full for full, _ in keys}
            for base in {base for _, base in keys}:
                if (marker := (base, values["clip_id"] or tuple(map(str, row)))) not in seen:
                    seen.add(marker)
                    found[base].append(values)
    return found


def _placeholder(row: dict) -> bool:
    return "placeholder" in {_normalize(flag) for flag in row["status_flags"].split("; ")}


def _collections(row: dict, mapping: list[dict]) -> list[str]:
    """Names of all mapping collections whose filters (all "is") match this API row."""
    return [entry["name"] for entry in mapping
            if all(_normalize(item["value"]) in {_normalize(value) for value in row[item["field"]].split("; ")}
                   for item in entry["filters"])]


def _skipped(state: dict) -> dict[str, list[str]]:
    """Marathon categories per Clip_ID of 'Gefunden, aber nicht aufgenommen' from the last update-index."""
    skipped = defaultdict(dict)
    for item in (state.get("index") or {}).get("issues") or []:
        if isinstance(item, dict) and item.get("section") == "skipped":
            skipped[str(item.get("key"))][str(item.get("category"))] = None
    return {key: list(categories) for key, categories in skipped.items()}


def _select(identifier: str, rest: str, rows: list[dict]) -> list[dict]:
    """Rows with the file's DEFA ID: exact ID, else the ID of a variant segment (T1 -> _1); a fitting title narrows
    them, otherwise small title deviations are accepted. Rows with only the same DEFA base need a fitting title."""
    full, base = _id_keys(identifier)
    variant = _variant(Path(rest).stem.split("__")[1:])
    pool = ([row for row in rows if full in row["keys"]]
            or [row for row in rows if variant and f"{base}_{variant}" in row["keys"]])
    titled = [row for row in pool or rows if _title_suffixes(rest, row[api_title]) is not None]
    return titled or pool


def _reason(rows: list[dict], fitting: list[dict], selected: list[dict], in_json: list[str], mapping: list[dict],
            skipped: dict[str, list[str]]) -> str | None:
    """Error category of a file without a unique JSON clip; None if Marathon rightly ignores its clips
    (not in the searched collections, placeholder)."""
    if not rows:
        return "no_hit"
    if in_json:
        return "ambiguous"
    if not selected:
        return None if fitting or all(map(_placeholder, rows)) else "title"
    if any(_collections(row, mapping) and row["clip_id"] not in skipped for row in selected):
        return "expected"
    categories = list(dict.fromkeys(category for row in selected for category in skipped.get(row["clip_id"], [])))
    return f"skipped|{' / '.join(categories)}" if categories else None


def _hit_line(row: dict, collections: list[str], clips: dict, skipped: dict[str, list[str]]) -> str:
    fields = " | ".join(f"{field.split()[0]}={row[field] or '–'}" for field in lookup_fields[1:6])
    clip = clips.get(row["clip_id"])
    return (f"API: Clip_ID={row['clip_id'] or '–'} | {fields}" + (" | Platzhalter" if _placeholder(row) else "")
            + (f" -> {', '.join(collections)}" if collections else "")
            + (f" | Marathon: {' / '.join(skipped[row['clip_id']])}" if row["clip_id"] in skipped else "")
            + (f"\n      JSON: 001={clip.get('identifier')} | 014={clip.get('title')}" if clip else ""))


def _check_missing(cfg: dict, mapping: list[dict], state: dict,
                   missing: list[tuple]) -> tuple[list[tuple], list[tuple[str, str, str]], list[str]]:
    """Files without JSON match by DEFA ID and title: (file, Clip_ID, True) if the API, ignoring placeholders, leads
    by DEFA ID to exactly one clip in the JSON; errors for the others and report lines for files whose clips
    Marathon rightly ignores (not in the searched collections, placeholder)."""
    if not missing:
        return [], [], []
    identifiers = list(dict.fromkeys(value for _, identifier, rest, base_ids in missing
                                     for value in (*_search_values(identifier, rest), *base_ids)))
    _log(f"API-Suche nach {api_identifier}: {len(identifiers)} Werte für {len(missing)} Dateien ...")
    try:
        found, failure = _search_identifiers(cfg, identifiers), None
    except Exception as exc:  # The sort result stays valid; the error list only lacks the API data.
        reason = str(exc).strip().splitlines()[-1] if str(exc).strip() else type(exc).__name__
        found, failure = {}, f"Grund: {reason}"
        _log(f"API-Suche fehlgeschlagen: {reason}")
        tb_write_log(main_log, traceback.format_exc())
    clips, skipped = state["clips"], _skipped(state)
    resolved, errors, outside, label = [], [], [], api_identifier.split()[0]
    for item, identifier, rest, _ in missing:
        if failure:
            errors.append(("api_failed", item.name, f"{label}={identifier}\n    {failure}"))
            continue
        rows = found.get(_id_keys(identifier)[1], [])
        selected = _select(identifier, rest, [row for row in rows if not _placeholder(row)])
        in_json = sorted({row["clip_id"] for row in selected if row["clip_id"] in clips}, key=int)
        if len(in_json) == 1:
            resolved.append((item, in_json[0], True))
            continue
        fitting = _select(identifier, rest, rows)
        category = _reason(rows, fitting, selected, in_json, mapping, skipped)
        detail = f"{label}={identifier}" + "".join(f"\n    {_hit_line(row, _collections(row, mapping), clips, skipped)}"
                                                   for row in fitting or rows)
        if category:
            errors.append((category, item.name, detail))
        else:
            outside.append(f"{item.name}: {detail}")
    return resolved, errors, outside


# --------- FUNC: REPORT ---------
def _label(category: str) -> str:
    kind, _, extra = category.partition("|")
    return f"{error_labels[kind]}: {extra}" if extra else error_labels[kind]


def _via_api(state: dict, move: dict) -> str:
    clip = state["clips"][move["clip_id"]]
    return f" | per API (JSON: 001={clip.get('identifier')} | 014={clip.get('title')})" if move["via_api"] else ""


def _write_reports(state: dict, moves: list[dict], errors: list[tuple[str, str, str]], outside: list[str],
                   applied: bool) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y-%m-%d_%H-%M-%S}"
    report, error_file = output_dir / f"aqc_sort_{stamp}.txt", output_dir / f"aqc_sort_{stamp}_errors.txt"
    per_collection = Counter(state["clips"][move["clip_id"]]["collection"] for move in moves)
    verb = "übernommen" if applied else "würden übernommen (Vorschau, nichts geändert)"
    lines = [f"{app_name} {app_version} | {'Ausführung' if applied else 'Vorschau'} | {_now()}", "",
             f"{len(moves)} Dateien {verb}; {len(errors) + len(outside)} bleiben in {aqc_dir}: "
             f"{len(errors)} auf der Fehlerliste, {len(outside)} nicht in den gesuchten Kollektionen.", "",
             *[f"  {name}: {count}" for name, count in sorted(per_collection.items(), key=lambda item: item[0].casefold())],
             "", *[f"{move['source'].name} -> {move['target']} | Clip_ID={move['clip_id']}" + _via_api(state, move)
                   for move in moves],
             *(["", f"Nicht in den gesuchten Kollektionen oder Platzhalter (nicht auf der Fehlerliste): {len(outside)}",
                *sorted(outside, key=str.casefold)] if outside else [])]
    with report.open("x", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    grouped = defaultdict(list)
    for category, name, detail in errors:
        grouped[category].append(f"{name}: {detail}" if detail else name)
    order = sorted(grouped, key=lambda category: (list(error_labels).index(category.partition("|")[0]), category.casefold()))
    body = [line for category in order
            for line in ("", f"[{_label(category)}] {len(grouped[category])}", *sorted(grouped[category], key=str.casefold))]
    with error_file.open("x", encoding="utf-8") as handle:
        handle.write("\n".join([f"{app_name} {app_version} | AQC-Fehlerliste | {_now()}", "",
                                f"{len(errors)} Dateien nicht übernommen:", *body]) + "\n")
    return report, error_file


# --------- MAIN ---------
def main() -> None:
    parser = argparse.ArgumentParser(description="Eindeutige DEFA-Proxies aus AQC an Marathon übergeben")
    parser.add_argument("--apply", action="store_true", help="wirklich verschieben und JSON ändern (sonst nur Vorschau)")
    args = parser.parse_args()
    cfg = _read_config()
    mapping = _load_mapping(cfg)
    source = Path(cfg["root_path"]) / cfg["defa_dir"] / aqc_dir
    if not source.is_dir():
        raise FileNotFoundError(f"AQC-Ordner nicht erreichbar: {source}")
    _acquire_lock()
    state = _load_state()
    _log(f"{'Ausführung' if args.apply else 'Vorschau'}: prüfe {source} ...")
    found, errors, missing = _scan(cfg, state, source)
    resolved, missing_errors, outside = _check_missing(cfg, mapping, state, missing)
    moves, move_errors = _plan_moves(cfg, state["clips"], found + resolved)
    errors += missing_errors + move_errors
    if args.apply and moves:
        moves = _apply(cfg, state, moves, errors)
    report, error_file = _write_reports(state, moves, errors, outside, args.apply)
    _log(f"{len(moves)} {'übernommen' if args.apply else 'übernehmbar'}, {len(errors)} auf der Fehlerliste. "
         f"Bericht: {report}; Fehlerliste: {error_file}")


# --------- EXEC ---------
if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        error_message = f"Unhandled error in main: {exc}"
        print(error_message)
        tb_write_log(main_log, error_message)
        tb_write_log(main_log, traceback.format_exc())
        raise SystemExit(1) from exc
