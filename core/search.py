"""EditShare search."""
# --------- IMPORTS ---------
from collections import defaultdict
from time import perf_counter

from .constants import editshare_filter_fields, field_names, problem_categories
from .console import log, search_progress
from .util import file_name, issue, joined, split_values
from .layout import res


# --------- FUNC ---------
def _merge_hit(hit: dict) -> dict:
    rows = hit.pop("rows")
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
    tapes = {}
    for tape in (tape for row in rows for value in row["backups"] for tape in map(str.strip, value.split(",")) if tape):
        tapes.setdefault(tape.casefold(), tape)  # Keep the first spelling.
    if not tapes:
        raw = "; ".join(value for row in rows for value in row["backups"])
        hit["invalid"] = (f"keine LTO-Tapenummer; {field_names['backups']}={raw!r}", None)
        return hit
    sizes = [value for row in rows for value in row["size"]]
    if not sizes or not all(value.isascii() and value.isdecimal() for value in sizes):
        hit["invalid"] = (f"Dateigröße fehlt oder ungültig; {field_names['size']}={'; '.join(sizes)!r}", None)
        return hit
    names = {file_name(path).casefold(): file_name(path) for row in rows for path in row["userpath"] if file_name(path)}
    hashes = {value.casefold(): value for row in rows for value in row["hash"]}
    masters, hash_list = (sorted(values.values(), key=str.casefold) for values in (names, hashes))
    restore_problem = None if masters and len(masters) == len(hash_list) else (
        f"{len(masters)} Dateinamen ({field_names['userpath']}), {len(hash_list)} Hashes; "
        f"{field_names['userpath']}={joined(masters)}, {field_names['hash']}={joined(hash_list)}, "
        f"{field_names['backups']}={joined(tapes.values())}")
    hit.update({field: seen[field][0] for field in fields}, hashes=hash_list, masters=masters,
               lto_tapes=list(tapes.values()), master_size=sum(map(int, sizes)), restore_problem=restore_problem)
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
            values = {key: split_values(str(raw)) for key, raw in zip(keys, row)}
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
