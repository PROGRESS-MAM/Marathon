"""EditShare search; master files of a clip from video.file, audio.file and data.file."""
# --------- IMPORTS ---------
import ast
import re
from collections import defaultdict
from time import perf_counter

from .constants import editshare_filter_fields, field_names, file_kinds, invalid_path_chars, problem_categories
from .console import log, search_progress
from .util import issue, split_values
from .layout import res


# --------- STATIC ---------
flow_hash_pattern = re.compile(r"2:[0-9a-f]+", re.IGNORECASE)


# --------- FILES ---------
def split_objects(text: str) -> list[str]:
    """Parts of a "; "-joined field value, split only outside quotes and brackets (Python repr of file objects)."""
    parts, depth, quote, start, index = [], 0, None, 0, 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 1
            elif char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char in "{[(":
            depth += 1
        elif char in "}])":
            depth -= 1
        elif not depth and text.startswith("; ", index):
            parts.append(text[start:index])
            start, index = index + 2, index + 1
        index += 1
    parts.append(text[start:])
    return [part.strip() for part in parts if part.strip()]


def _tapes(raw: dict) -> list[str]:
    """Tapes of all backup locations, first spelling kept."""
    tapes = {}
    for location in raw.get("backup_locations") or []:
        values = location.get("tapes") if isinstance(location, dict) else None
        for tape in [values] if isinstance(values, str) else values if isinstance(values, list) else []:
            if isinstance(tape, str) and tape.strip():
                tapes.setdefault(tape.strip().casefold(), tape.strip())
    return list(tapes.values())


def _master(raw) -> tuple[dict | None, str | None]:
    """Master file {file, flow_hash, size, tapes} of one EditShare file object, or the reason why it is unusable."""
    if not isinstance(raw, dict):
        return None, f"Dateiobjekt ist kein Objekt: {str(raw)[:80]!r}"
    stem, suffix = (str(raw.get(key) or "").strip() for key in ("display_name", "display_fileext"))
    info = raw.get("file") if isinstance(raw.get("file"), dict) else {}
    name, flow_hash, size, tapes = f"{stem}.{suffix}", info.get("hash"), info.get("filesize"), _tapes(raw)
    if not stem or not suffix:
        return None, f"display_name/display_fileext fehlt (display_name={stem!r}, display_fileext={suffix!r})"
    if any(char in invalid_path_chars for char in name):
        return None, f"{name}: unzulässige Zeichen im Dateinamen"
    if not isinstance(flow_hash, str) or not flow_hash_pattern.fullmatch(flow_hash.strip()):
        return None, f"{name}: Hash fehlt oder nicht 2:<hex> (file.hash={flow_hash!r})"
    if type(size) is not int or size < 0:
        return None, f"{name}: Dateigröße fehlt oder keine ganze Zahl (file.filesize={size!r})"
    if not tapes:
        return None, f"{name}: kein Band in backup_locations[].tapes"
    return {"file": name, "flow_hash": flow_hash.strip(), "size": size, "tapes": tapes}, None


def masters_of(texts: list[str]) -> tuple[list[dict], str | None]:
    """Master files of a clip from the file field values, merged by flow_hash and sorted by name.

    Returns (masters, None) or ([], problem) if any file object is unreadable, incomplete or contradictory.
    """
    by_hash, problems = {}, []
    for text in texts:
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            problems.append(f"Dateiobjekt unlesbar: {text[:80]!r}")
            continue
        for raw in parsed if isinstance(parsed, list) else [parsed]:
            entry, problem = _master(raw)
            if problem:
                problems.append(problem)
                continue
            known = by_hash.setdefault(entry["flow_hash"].casefold(), entry)
            if known is entry:
                continue
            if known["file"].casefold() != entry["file"].casefold() or known["size"] != entry["size"]:
                problems.append(f"Hash {entry['flow_hash']} mit verschiedenen Namen oder Größen: "
                                f"{known['file']} ({known['size']}), {entry['file']} ({entry['size']})")
            seen = {tape.casefold() for tape in known["tapes"]}
            known["tapes"] += [tape for tape in entry["tapes"] if tape.casefold() not in seen]
    hashes = defaultdict(list)
    for entry in by_hash.values():
        hashes[entry["file"].casefold()].append(entry)
    problems += [f"Dateiname {found[0]['file']} mit {len(found)} Hashes: {', '.join(entry['flow_hash'] for entry in found)}"
                 for found in hashes.values() if len(found) > 1]
    if not by_hash and not problems:
        problems.append(f"keine Dateien in {', '.join(field_names[kind] for kind in file_kinds)}")
    if problems:
        return [], "; ".join(dict.fromkeys(problems))
    return sorted(by_hash.values(), key=lambda entry: entry["file"].casefold()), None


# --------- HITS ---------
def _merge_hit(hit: dict) -> dict:
    rows = hit.pop("rows")
    masters, restore_problem = masters_of([text for row in rows for kind in file_kinds for text in row[kind]])
    tapes = {}
    for tape in (tape for entry in masters for tape in entry["tapes"]):
        tapes.setdefault(tape.casefold(), tape)
    hit.update(masters=masters, master_files=[entry["file"] for entry in masters], lto_tapes=list(tapes.values()),
               master_size=sum(entry["size"] for entry in masters), restore_problem=restore_problem)
    fields = ("identifier", "title", "clip_name")
    seen = {field: list(dict.fromkeys(value for row in rows for value in row[field])) for field in fields}
    hit.update(identifier=" / ".join(seen["identifier"]), title=" / ".join(seen["title"]),  # Shown in error lines.
               identifiers=seen["identifier"])
    problems = [f"{field_names[field]}: {len(row[field])} Werte" for row in rows for field in fields if len(row[field]) != 1]
    if problems:
        hit["invalid"] = ("; ".join(dict.fromkeys(problems)), None)
        return hit
    conflicts = [f"{field_names[field]}={value}" for field in fields if len(seen[field]) > 1 for value in seen[field]]
    if conflicts:
        hit["invalid"] = ("Widersprüchlich", conflicts)
        return hit
    hit.update({field: seen[field][0] for field in fields})
    return hit


def _raw_text(row) -> str:
    if not isinstance(row, (list, tuple)):
        return f"Rohwert={row!r}"
    text = ", ".join(f"{field}={value!r}" for field, value in zip(field_names.values(), row))
    return text + (f", weitere Werte={list(row[len(field_names):])!r}" if len(row) > len(field_names) else "")


def search_clips(mapping: list[dict], ctx: dict) -> dict[str, list[dict]]:
    """EditShare hits of all collections by Clip_ID; invalid rows become issues in the run context."""
    import searcher

    keys, api_fields = tuple(field_names), tuple(field_names.values())
    allowed_filters = editshare_filter_fields
    for entry in mapping:
        unknown = {item["field"] for item in entry["filters"]} - allowed_filters
        if unknown:
            raise ValueError(f"API-Suchfeld in {entry['name']!r} nicht geprüft: {', '.join(sorted(unknown))}.")
    log(f"API-Verbindung herstellen: {len(mapping)} Kollektionen vorgesehen.")
    searcher.link("api", res("cred_file"), on_progress=search_progress)
    found = defaultdict(dict)
    invalid_category = problem_categories["invalid"][0]
    for entry in mapping:
        name, started = entry["name"], perf_counter()
        log(f"API-Suche gestartet: {name!r}.")
        request = tuple(part for index, item in enumerate(entry["filters"])
                        for part in (("and",) if index else ()) + ((item["field"], "is", item["value"]),))
        matches, _, error = searcher.find({"name": name, "request_fields": request, "return_fields": api_fields})
        if error:
            raise RuntimeError(f"API-Suche für {name!r} unvollständig; Zustand unverändert: {error}")
        placeholders = 0
        for number, row in enumerate(matches, 1):
            if len(row) != len(api_fields) or not all(isinstance(value, str) or type(value) is int for value in row):
                issue(ctx, "skipped", invalid_category, f"{name}#{number}",
                      f"Kollektion={name}, Trefferzeile={number}: Rückgabefelder unvollständig oder kein Text; {_raw_text(row)}")
                continue
            values = {key: (split_objects if key in file_kinds else split_values)(str(raw)) for key, raw in zip(keys, row)}
            if "placeholder" in (flag.casefold() for flag in values["status_flags"]):
                placeholders += 1
                continue  # Placeholders are ignored completely, also in the error report.
            ids = values["clip_id"]
            if len(ids) != 1 or not (ids[0].isascii() and ids[0].isdecimal()):
                issue(ctx, "skipped", invalid_category, f"{name}#{number}",
                      f"Kollektion={name}, Trefferzeile={number}: {field_names['clip_id']} ungültig; {_raw_text(row)}")
                continue
            found[ids[0]].setdefault(name, {"collection": name, "clip_id": ids[0], "invalid": None, "rows": []})["rows"].append(values)
        log(f"API-Suche abgeschlossen: {name!r}: {len(matches)} Trefferzeilen, davon {placeholders} Platzhalter; "
            f"{perf_counter() - started:.1f} s.")
    return {clip_id: [_merge_hit(hit) for hit in hits.values()] for clip_id, hits in found.items()}
