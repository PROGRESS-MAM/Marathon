# --------- IMPORTS ---------
import argparse
import json
import os
import queue
import tempfile
import threading
import unicodedata
from stat import S_ISREG
from collections import defaultdict
from datetime import datetime, time, timedelta
from pathlib import Path
from time import perf_counter

from toolbox import tb_write_log

# --------- STATIC ---------
field_names = {
    "identifier": "001 Identifier",
    "title": "014 Title Original",
    "clip_id": "clip_id",
    "clip_name": "clip_name_with_extension",
    "hash": "hash",
}

# --------- CONFIG ---------
app_name = "Marathon"
app_version = "0.5"
project_dir = Path(__file__).resolve().parent
res_dir = project_dir / "res"
log_dir = project_dir / "log"
state_dir = project_dir / "state"
reports_dir = project_dir / "reports"
error_dir = reports_dir / "errors"
cred_path = res_dir / "cred.env"
mapping_path = res_dir / "collections.json"
state_path = state_dir / "marathon.json"
main_log = log_dir / "marathon.log"
root_path = Path("//10.0.77.11") / "Ablage KI Proxy_1" / "Proxy 10 Mbit" / "DEFA"
target_path = root_path / "AQC"
aqc_prefix = ("(c)PROGRESS", "10Mbit")
aqc_ignored_suffixes = (".tmp", ".part", ".partial", ".json", ".txt")
report_only = True
auto_report_time = time(9, 0)  # Local machine time
retry_minutes = 60
queue_names = ("restore", "transcode", "qc")
columns = ("Kollektion", "Gesamt", "Bereit", "%", "Queue LTO", "Queue Transcode", "Queue QC")

# --------- FUNC ---------
def _log(message: str) -> None:
    print(message, flush=True)
    tb_write_log(main_log, message)


def _prepare() -> None:
    for folder in (res_dir, log_dir, state_dir, reports_dir, error_dir):
        folder.mkdir(parents=True, exist_ok=True)
    if not report_only:
        raise RuntimeError("report_only=False ist noch nicht implementiert; keine Jobs werden erstellt.")
    if retry_minutes <= 0:
        raise ValueError("retry_minutes muss größer als 0 sein.")
    if any(path != state_path for path in state_dir.glob("*.json")):
        raise RuntimeError("Weitere JSON-Datei in state gefunden; bitte Quelle des Zustands klären.")
    if not mapping_path.is_file():
        raise FileNotFoundError(f"Kollektionsmapping fehlt: {mapping_path}")
    if not cred_path.is_file():
        raise FileNotFoundError(f"Lege die Searcher-Zugangskonfiguration unter {cred_path} ab.")


def _load_mapping() -> list[dict]:
    with mapping_path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("Unbekanntes Format im Kollektionsmapping.")
    entries = document.get("collections")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Im Kollektionsmapping fehlen Kollektionen.")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Jede Kollektion muss ein Objekt sein.")
        name, expected, filters = (entry.get(key) for key in ("name", "expected_hits", "filters"))
        if not isinstance(name, str) or not name.strip() or name.casefold() in seen:
            raise ValueError(f"Ungültiger oder doppelter Kollektionsname: {name!r}")
        if type(expected) is not int or expected < 0:
            raise ValueError(f"Ungültige Sollmenge für {name!r}.")
        if not isinstance(filters, list) or not filters:
            raise ValueError(f"Suchbedingungen fehlen für {name!r}.")
        for item in filters:
            if not isinstance(item, dict) or any(not isinstance(item.get(key), str) or not item[key].strip()
                                                  for key in ("field", "value")):
                raise ValueError(f"Ungültige Suchbedingung für {name!r}.")
        seen.add(name.casefold())
    return entries


def _values(value: str) -> list[str]:
    return [part.strip() for part in value.split("; ") if part.strip()]


def _search_clips(mapping: list[dict]) -> tuple[list[dict], list[str], dict[str, int]]:
    import searcher

    api_fields = (field_names["clip_id"], field_names["identifier"],
                  field_names["title"], field_names["clip_name"], field_names["hash"])
    allowed_filters = {"006 Source PROGRESS", "007 Collection PROGRESS", "101a Genre German"}
    for entry in mapping:
        unknown = {item["field"] for item in entry["filters"]} - allowed_filters
        if unknown:
            raise ValueError(f"API-Suchfeld in {entry['name']!r} nicht geprüft: {', '.join(sorted(unknown))}.")

    searches = [
        {
            "name": entry["name"],
            "request_fields": tuple(part for index, item in enumerate(entry["filters"])
                                    for part in (("and",) if index else ()) +
                                    ((item["field"], "is", item["value"]),)),
            "return_fields": api_fields,
        }
        for entry in mapping
    ]
    _log(f"API-Verbindung herstellen: {len(searches)} Kollektionen vorgesehen.")
    searcher.link("api", cred_path)
    api_records, errors, hit_counts = {}, [], {}
    for search, entry in zip(searches, mapping):
        _log(f"API-Suche gestartet: {entry['name']!r}.")
        started = perf_counter()
        matches, _, error = searcher.find(search)
        if error:
            raise RuntimeError(f"API-Suche für {entry['name']!r} unvollständig; Zustand unverändert: {error}")
        hit_counts[entry["name"]] = len(matches)
        repeated_ids, repeated_rows = set(), 0
        if len(matches) != entry["expected_hits"]:
            delta = len(matches) - entry["expected_hits"]
            errors.append(f"Suchabweichung: {entry['name']}: Soll={entry['expected_hits']}, "
                          f"Ist={len(matches)}, Differenz={delta:+d}; Gesamt im Report bleibt Soll.")
        for row in matches:
            if len(row) != len(api_fields) or not all(isinstance(value, str) for value in row):
                raise ValueError(f"API-Suche für {entry['name']!r} lieferte unerwartete Rückgabefelder; "
                                 "Zustand unverändert.")
            clip_ids = _values(row[0])
            if len(clip_ids) != 1 or not clip_ids[0].isascii() or not clip_ids[0].isdecimal():
                raise ValueError(f"API-Suche für {entry['name']!r} lieferte keine eindeutige Clip-ID: "
                                 f"{row[0]!r}; Zustand unverändert.")
            clip_id = clip_ids[0]
            metadata = [_values(value) for value in row[1:4]]
            if any(len(values) != 1 for values in metadata):
                raise ValueError(f"API-Suche für {entry['name']!r}, Clip-ID {clip_id!r}: "
                                 "Kennung, Titel oder Clipname fehlen oder sind mehrdeutig; Zustand unverändert.")
            identifier, title, clip_name = (values[0] for values in metadata)
            hashes = list(dict.fromkeys(_values(row[4])))
            key = (entry["name"], clip_id)
            if key in api_records:
                record = api_records[key]
                if (record["identifier"], record["title"], record["clip_name_with_extension"]) != (identifier, title, clip_name):
                    raise ValueError(f"Widersprüchliche API-Daten für Clip-ID {clip_id!r} "
                                     f"in {entry['name']!r}; Zustand unverändert.")
                record["filehashes"] = list(dict.fromkeys((*record["filehashes"], *hashes)))
                repeated_ids.add(clip_id)
                repeated_rows += 1
                continue
            api_records[key] = {"clip_id": clip_id, "clip_name_with_extension": clip_name,
                                "collection": entry["name"], "identifier": identifier, "title": title,
                                "filehashes": hashes}
        if repeated_rows:
            examples = ', '.join(sorted(repeated_ids)[:5])
            errors.append(f"Mehrfach gelieferte API-Clip-IDs: Kollektion={entry['name']!r}, "
                          f"API-Trefferzeilen={len(matches)}, eindeutige Clip-IDs={len(matches) - repeated_rows}, "
                          f"zusätzliche Zeilen={repeated_rows}, betroffene Clip-IDs={len(repeated_ids)} "
                          f"(Beispiele: {examples}); Hashes je Clip-ID zusammengeführt.")
        _log(f"API-Suche abgeschlossen: {entry['name']!r}: {len(matches)} Trefferzeilen, "
             f"{len(matches) - repeated_rows} eindeutige Clip-IDs; {perf_counter() - started:.1f} s.")

    records = list(api_records.values())
    for record in records:
        if not record["filehashes"]:
            errors.append(f"Keine Flow-Hashes: Kollektion={record['collection']!r}, "
                          f"Clip_ID={record['clip_id']}, Clipname={record['clip_name_with_extension']!r}")
    _log(f"API-Daten geprüft: {len(records)} Kollektion/Clip-Zuordnungen, "
         f"{sum(not record['filehashes'] for record in records)} ohne Hash.")
    return records, errors, hit_counts


def _empty_transcode() -> dict:
    return {"phase": None, "analysis_started_at": None, "analysis_finished_at": None,
            "conversion_started_at": None, "conversion_finished_at": None}


def _load_state() -> dict:
    if not state_path.exists():
        return {"schema_version": 1, "clips": {}}
    with state_path.open(encoding="utf-8") as handle:
        state = json.load(handle)
    if not isinstance(state, dict) or state.get("schema_version") != 1 or not isinstance(state.get("clips"), dict):
        raise ValueError("Unbekanntes Zustandsformat; keine Aktualisierung.")
    for clip_id, item in state["clips"].items():
        if not isinstance(item, dict) or item.get("clip_id") != clip_id or not isinstance(item.get("ready"), bool):
            raise ValueError(f"Ungültiger Zustand für Clip_ID {clip_id!r}; keine Aktualisierung.")
        if item.get("queue") not in (*queue_names, None) or not isinstance(item.get("active"), bool):
            raise ValueError(f"Ungültige Queue/Aktivität für Clip_ID {clip_id!r}; keine Aktualisierung.")
        if item["ready"] and item["queue"] is not None:
            raise ValueError(f"Clip_ID {clip_id!r} ist zugleich bereit und in einer Queue.")
        if not isinstance(item.get("clip_name_with_extension", ""), str):
            raise ValueError(f"Ungültiger Clipname für Clip_ID {clip_id!r}.")
        item.setdefault("clip_name_with_extension", "")
        transcode = item.setdefault("transcode", _empty_transcode())
        if not isinstance(transcode, dict) or transcode.get("phase") not in (None, "analysis", "conversion", "completed"):
            raise ValueError(f"Ungültige Transcode-Phase für Clip_ID {clip_id!r}.")
        for key in _empty_transcode():
            transcode.setdefault(key, None)
            if key != "phase" and transcode[key] is not None and not isinstance(transcode[key], str):
                raise ValueError(f"Ungültige Transcode-Zeit für Clip_ID {clip_id!r}.")
        aqc = item.setdefault("aqc", {"present": False, "filename": None, "matched_by": None, "last_seen_at": None})
        if not isinstance(aqc, dict) or not isinstance(aqc.get("present"), bool):
            raise ValueError(f"Ungültiger AQC-Status für Clip_ID {clip_id!r}.")
    return state


def _reconcile(state: dict, records: list[dict], errors: list[str]) -> dict:
    pairs, ids = defaultdict(list), defaultdict(list)
    for item in records:
        pairs[(item["identifier"], item["title"])].append(item)
        ids[item["clip_id"]].append(item)
    duplicated = {id(item) for group in (*pairs.values(), *ids.values()) if len(group) > 1 for item in group}
    for (identifier, title), group in pairs.items():
        if len(group) > 1:
            errors.append(f"Duplikat Identifier/Titel: {identifier!r} / {title!r}; "
                          f"Clip_IDs: {', '.join(item['clip_id'] for item in group)}")
    for clip_id, group in ids.items():
        if len(group) > 1:
            errors.append(f"Clip_ID mehrfach in Suche: {clip_id!r}; alle Treffer übersprungen")
    for clip_id, old in state["clips"].items():
        if clip_id not in ids:
            errors.append(f"Im aktuellen Suchlauf nicht gefunden (im Zustand behalten): "
                          f"Clip_ID={clip_id}, Clipname={old['clip_name_with_extension'] or 'unbekannt'}, "
                          f"Kollektion={old['collection']}")
        elif any(id(item) in duplicated for item in ids[clip_id]):
            old["active"] = False
    for item in records:
        if id(item) in duplicated:
            continue
        clip_id = item["clip_id"]
        old = state["clips"].get(clip_id, {})
        state["clips"][clip_id] = {**old, **item, "active": True,
                                   "ready": old.get("ready", False), "queue": old.get("queue"),
                                   "status": old.get("status", "new"),
                                   "transcode": old.get("transcode", _empty_transcode()),
                                   "aqc": old.get("aqc", {"present": False, "filename": None,
                                                           "matched_by": None, "last_seen_at": None})}
    state["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
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


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().casefold()


def _scan_aqc(state: dict, mapping: list[dict], errors: list[str]) -> tuple[int, int]:
    if not target_path.is_dir():
        raise FileNotFoundError(f"AQC-Verzeichnis nicht erreichbar: {target_path}; Zustand unverändert.")
    defa_names = {entry["name"] for entry in mapping if any(
        item["field"].casefold() == "006 source progress" and item["value"].casefold() == "defa"
        for item in entry["filters"])}
    index = defaultdict(list)
    for item in state["clips"].values():
        if item["active"] and item["collection"] in defa_names and item["identifier"] and item["title"]:
            index[(_normalize(item["identifier"]), _normalize(item["title"]))].append(item)
    assigned, unmatched = defaultdict(list), 0
    checked, last_progress = 0, perf_counter()
    try:
        for path in target_path.iterdir():
            checked += 1
            now = perf_counter()
            if now - last_progress >= 30:
                _log(f"AQC-Scan läuft: {checked} Verzeichniseinträge erfasst.")
                last_progress = now
            try:
                info = path.stat(follow_symlinks=False)
            except FileNotFoundError:
                continue  # Files may arrive or disappear during the directory scan.
            if not S_ISREG(info.st_mode) or path.suffix.casefold() in aqc_ignored_suffixes:
                continue
            parts = path.name.split("__", 3)
            if len(parts) != 4 or tuple(parts[:2]) != aqc_prefix or not parts[2].strip() or not parts[3].strip():
                errors.append(f"AQC-Dateiname nicht zuordenbar: {path.name!r}")
                continue
            if info.st_size == 0:
                errors.append(f"AQC-Datei noch leer (nicht gezählt): {path.name!r}")
                continue
            titles = (parts[3], Path(parts[3]).stem)
            candidates = {item["clip_id"]: item for title in titles
                          for item in index.get((_normalize(parts[2]), _normalize(title)), ())}
            if not candidates:
                unmatched += 1
            elif len(candidates) != 1:
                errors.append(f"AQC-Datei mehrfach zuordenbar: {path.name!r}; "
                              f"Clip_IDs: {', '.join(candidates)}")
            else:
                assigned[next(iter(candidates))].append(path.name)
    except OSError as exc:
        raise RuntimeError(f"AQC-Verzeichnis nicht vollständig lesbar: {target_path}; Zustand unverändert.") from exc
    _log(f"AQC-Verzeichnis geprüft: {checked} Einträge erfasst.")
    seen_at = datetime.now().astimezone().isoformat(timespec="seconds")
    count = 0
    for clip_id, paths in assigned.items():
        if len(paths) != 1:
            errors.append(f"Mehrere AQC-Dateien für Clip_ID {clip_id}: {', '.join(paths)}; nicht neu zugeordnet")
            continue
        item = state["clips"][clip_id]
        item["aqc"] = {"present": True, "filename": paths[0],
                       "matched_by": "identifier_title", "last_seen_at": seen_at}
        item["transcode"]["phase"] = "completed"
        if not item["ready"] and item["queue"] != "qc":
            item["queue"] = "qc"
            item["status"] = "waiting_qc"
        count += 1
    for clip_id, item in state["clips"].items():
        if clip_id in assigned:
            continue
        if item["aqc"]["present"]:
            item["aqc"]["present"] = False
            errors.append(f"Bisherige AQC-Datei nicht mehr gesehen: Clip_ID={clip_id}, "
                          f"Datei={item['aqc']['filename']!r}; Queue bleibt zur Prüfung erhalten.")
    return count, unmatched


def _totals(state: dict, mapping: list[dict]) -> dict[str, tuple[int, int, int, int, int]]:
    totals = {entry["name"]: [entry["expected_hits"], 0, 0, 0, 0] for entry in mapping}
    for item in state["clips"].values():
        if not item["active"] or item["collection"] not in totals:
            continue
        row = totals[item["collection"]]
        row[1] += int(item["ready"])
        if item["queue"] in queue_names:
            row[2 + queue_names.index(item["queue"])] += 1
    return {name: tuple(row) for name, row in totals.items()}


def _previous(kind: str) -> Path | None:
    files = sorted(reports_dir.glob(f"{kind}_*.txt"))
    return files[-1] if files else None


def _read_previous(path: Path | None) -> dict[str, tuple[int, int, float, int, int, int]]:
    if path is None:
        return {}
    result, header = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.split("|")]
        if parts[0] == "Kollektion" and len(parts) == len(columns):
            if set(parts) != set(columns):
                raise ValueError(f"Vorgängerbericht {path.name} enthält unbekannte Spalten.")
            header = parts
            continue
        if header is None or len(parts) != len(columns) or not parts[0] or set(parts[0]) == {"-"}:
            continue
        row = dict(zip(header, parts))
        try:
            def number(key: str, convert):
                return convert(row[key].split()[0].split("(")[0])
            result[parts[0]] = (number("Gesamt", int), number("Bereit", int), number("%", float),
                                number("Queue LTO", int), number("Queue Transcode", int),
                                number("Queue QC", int))
        except (ValueError, IndexError, KeyError) as exc:
            raise ValueError(f"Vorgängerbericht {path.name} ist nicht lesbar; kein neuer Bericht.") from exc
    if not result:
        raise ValueError(f"Vorgängerbericht {path.name} enthält keine vollständige Tabelle; kein neuer Bericht.")
    return result


def _format_int(value: int, previous: int | None) -> str:
    return str(value) if previous is None else f"{value} ({value - previous:+d})"


def _render(kind: str, when: datetime, totals: dict, previous: dict) -> str:
    rows = []
    for name, (total, ready, *queues) in totals.items():
        percent = 100 * ready / total if total else 0.0
        old = previous.get(name, (None,) * 6)
        percent_text = "0" if total == 0 else f"{percent:.1f}"
        percent_text += " %" if old[2] is None else f" % ({percent - old[2]:+.1f} pp)"
        rows.append((name, _format_int(total, old[0]), _format_int(ready, old[1]), percent_text,
                     *(_format_int(value, prior) for value, prior in zip(queues, old[3:]))))
    widths = [max(len(str(row[i])) for row in (columns, *rows)) for i in range(len(columns))]
    table = [" | ".join(str(cell).ljust(width) for cell, width in zip(columns, widths)),
             "-+-".join("-" * width for width in widths)]
    table += [" | ".join(str(cell).ljust(width) for cell, width in zip(row, widths)) for row in rows]
    return f"{app_name} {app_version} | {kind} | {when.isoformat(timespec='seconds')}\n\n" + "\n".join(table) + "\n"


def _format_errors(errors: list[str]) -> str:
    grouped = defaultdict(list)
    for message in errors:
        kind = message.partition(":")[0].strip() or "Sonstige"
        if kind.startswith("Mehrere AQC-Dateien für Clip_ID "):
            kind = "Mehrere AQC-Dateien für Clip_ID"
        grouped[kind].append(message)
    kinds = sorted(grouped, key=lambda kind: (len(grouped[kind]), kind.casefold()))
    type_label = "Fehlertyp" if len(kinds) == 1 else "Fehlertypen"
    lines = [f"{app_name} {app_version} | Fehlerbericht",
             f"Gesamt: {len(errors)} Meldungen in {len(kinds)} {type_label}", "",
             "Übersicht nach Fehlertyp:"]
    lines.extend(f"{kind}: {len(grouped[kind])}" for kind in kinds)
    for kind in kinds:
        lines.extend(("", f"=== {kind} ({len(grouped[kind])}) ==="))
        lines.extend(sorted(grouped[kind], key=str.casefold))
    return "\n".join(lines) + "\n"


def _write_new(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)


def _report(kind: str) -> Path:
    started = perf_counter()
    _log(f"{kind}-Bericht gestartet: Kollektionsmapping laden.")
    mapping = _load_mapping()
    _log(f"Kollektionsmapping geladen: {len(mapping)} Kollektionen.")
    records, errors, _ = _search_clips(mapping)
    _log(f"Zustandsabgleich gestartet: {len(records)} Kollektions-/Clip-Zuordnungen.")
    step_started = perf_counter()
    state = _reconcile(_load_state(), records, errors)
    _log(f"Zustandsabgleich abgeschlossen: {len(state['clips'])} Clips im Zustand; "
         f"{perf_counter() - step_started:.1f} s.")
    _log("AQC-Scan gestartet.")
    step_started = perf_counter()
    aqc_assigned, aqc_unmatched = _scan_aqc(state, mapping, errors)
    _log(f"AQC-Scan abgeschlossen: {aqc_assigned} zugeordnet, {aqc_unmatched} ohne Metadatenzuordnung; "
         f"{perf_counter() - step_started:.1f} s.")
    _log("Vorbericht lesen und Summen berechnen.")
    previous = _read_previous(_previous(kind))
    totals = _totals(state, mapping)
    for collection, (total, ready, *queues) in totals.items():
        if ready > total or sum(queues) > total:
            errors.append(f"Zustandsabweichung: {collection}: Soll={total}, Bereit={ready}, "
                          f"Queues={sum(queues)}; Zustand bitte prüfen.")
    when = datetime.now().astimezone()
    name = f"{kind}_{when.strftime('%Y-%m-%d_%H-%M-%S-%f')}"
    text = _render(kind, when, totals, previous)
    if errors:
        text += f"\nHinweis: {len(errors)} Auffälligkeiten; Details: errors/{name}_errors.txt\n"
    _log(f"Bericht vorbereitet: {len(errors)} Auffälligkeiten. Zustand speichern und Bericht schreiben.")
    _save_state(state)
    path = reports_dir / f"{name}.txt"
    _write_new(path, text)
    if errors:
        _write_new(error_dir / f"{name}_errors.txt", _format_errors(errors))
    active_count = sum(item["active"] and item["collection"] in totals for item in state["clips"].values())
    _log(f"{kind}-Bericht: {path.name}; {active_count} aktive Clips im Zustand; "
         f"{sum(row[0] for row in totals.values())} Soll; {len(errors)} Auffälligkeiten; "
         f"AQC zugeordnet: {aqc_assigned}, ohne Metadatenzuordnung: {aqc_unmatched}; "
         f"Dauer: {perf_counter() - started:.1f} s.")
    return path


def _auto_due(now: datetime) -> bool:
    return now.time() >= auto_report_time and not any(reports_dir.glob(f"auto_{now:%Y-%m-%d}_*.txt"))


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
    parser = argparse.ArgumentParser(description="Marathon: Suchabgleich und getrennte Report-Linien")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--manual", action="store_true", help="Manuellen Bericht erstellen und beenden")
    modes.add_argument("--auto-once", action="store_true", help="Auto-Bericht erstellen und beenden")
    args = parser.parse_args(argv)
    _prepare()
    if args.manual or args.auto_once:
        _report("manual" if args.manual else "auto")
        return
    commands: queue.Queue[str] = queue.Queue()
    threading.Thread(target=_console, args=(commands,), daemon=True).start()
    _log("Marathon läuft. 'report' = manueller Bericht, 'quit' = beenden.")
    next_retry = None
    while True:
        now = datetime.now().astimezone()
        if _auto_due(now) and (next_retry is None or now >= next_retry):
            try:
                _report("auto")
                next_retry = None
            except Exception as exc:
                next_retry = now + timedelta(minutes=retry_minutes)
                _log(f"Auto-Bericht fehlgeschlagen: {exc}; erneuter Versuch später.")
        try:
            command = commands.get(timeout=30)
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
        raise SystemExit(1) from exc
