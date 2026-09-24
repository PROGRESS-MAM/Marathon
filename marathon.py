# --------- IMPORTS ---------
import argparse
import json
import os
import queue
import tempfile
import threading
from collections import defaultdict
from datetime import datetime, time, timedelta
from pathlib import Path

from toolbox import tb_write_log

# --------- CONFIG ---------
app_name = "Marathon"
app_version = "0.1"
project_dir = Path(__file__).resolve().parent
res_dir = project_dir / "res"
log_dir = project_dir / "log"
state_dir = project_dir / "state"
reports_dir = project_dir / "reports"
error_dir = reports_dir / "errors"
cred_path = res_dir / "cred.env"
state_path = state_dir / "marathon.json"
main_log = log_dir / "marathon.log"
collections = ("Cintec", "Historiathek", "Katholisches Filmwerk", "Lynxarchive", "Doclights", "DEFA")
collection_field = "007 Collection PROGRESS"
identifier_field = "001 Identifier"
title_field = "014 Title Original"
clip_id_field = "clip_id"
# Verify these field paths against the Parquet export before any restore integration.
hash_fields = ("file_hash", "flow_hash", "files.hash")
report_only = True
auto_report_time = time(9, 0)  # Local machine time
retry_minutes = 60
allow_empty_search = False
queue_names = ("restore", "qc", "transcode")
columns = ("Kollektion", "Gesamt", "Bereit", "%", "Queue LTO", "Queue QC", "Queue Transcode")

# --------- FUNC ---------
def _log(message: str) -> None:
    print(message, flush=True)
    tb_write_log(main_log, message)


def _prepare() -> None:
    for folder in (res_dir, log_dir, state_dir, reports_dir, error_dir):
        folder.mkdir(parents=True, exist_ok=True)
    if not report_only:
        raise RuntimeError("report_only=False ist noch nicht implementiert; keine Jobs werden erstellt.")
    if not collections or any(not name.strip() for name in collections):
        raise ValueError("collections muss nichtleere Kollektionsnamen enthalten.")
    if len({name.casefold() for name in collections}) != len(collections):
        raise ValueError("collections enthält doppelte Kollektionsnamen.")
    if not hash_fields or any(not field for field in hash_fields):
        raise ValueError("hash_fields muss Metadatenfelder enthalten.")
    if retry_minutes <= 0:
        raise ValueError("retry_minutes muss größer als 0 sein.")
    if any(path != state_path for path in state_dir.glob("*.json")):
        raise RuntimeError("Weitere JSON-Datei in state gefunden; bitte Quelle des Zustands klären.")
    if not cred_path.is_file():
        raise FileNotFoundError(f"Lege die Searcher-Zugangskonfiguration unter {cred_path} ab.")


def _values(value: str) -> list[str]:
    return [part.strip() for part in value.split("; ") if part.strip()]


def _search_clips() -> tuple[list[dict], list[str]]:
    import searcher

    searcher.link("file", cred_path)
    conditions = []
    for name in collections:
        if conditions:
            conditions.append("or")
        conditions.append((collection_field, "is", name))
    fields = tuple(dict.fromkeys((collection_field, identifier_field, title_field, clip_id_field, *hash_fields)))
    matches, _, error = searcher.find({"name": "Marathon collections",
                                       "request_fields": tuple(conditions), "return_fields": fields})
    if error:
        raise RuntimeError(f"Searcher lieferte nur Teilergebnisse; Zustand unverändert: {error}")
    if not matches and not allow_empty_search:
        raise RuntimeError("Keine Suchtreffer. Prüfe Feldnamen und Parquet-Datei; Zustand unverändert.")
    configured = {name.casefold(): name for name in collections}
    records, errors = [], []
    for row in matches:
        if len(row) != len(fields):
            raise ValueError("Searcher lieferte eine unerwartete Feldanzahl; Zustand unverändert.")
        values = dict(zip(fields, row))
        found = {configured[name.casefold()] for name in _values(values[collection_field])
                 if name.casefold() in configured}
        clip_id, identifier, title = (values[field].strip() for field in
                                      (clip_id_field, identifier_field, title_field))
        if len(found) != 1 or not all((clip_id, identifier, title)):
            errors.append(f"Ungültiger Treffer: Clip_ID={clip_id!r}, Kollektion={values[collection_field]!r}, "
                          f"Identifier={identifier!r}, Titel={title!r}")
            continue
        hashes = list(dict.fromkeys(hash for field in hash_fields for hash in _values(values[field])))
        if not hashes:
            errors.append(f"Keine Filehashes: Clip_ID={clip_id}, Kollektion={next(iter(found))}")
        records.append({"clip_id": clip_id, "collection": next(iter(found)),
                        "identifier": identifier, "title": title, "filehashes": hashes})
    return records, errors


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
    seen = set(ids)
    for clip_id, old in state["clips"].items():
        if clip_id not in seen:
            old["active"] = False
            errors.append(f"Abgang (im Zustand behalten): Clip_ID={clip_id}, Kollektion={old['collection']}")
        elif any(id(item) in duplicated for item in ids[clip_id]):
            old["active"] = False
    for item in records:
        if id(item) in duplicated:
            continue
        clip_id = item["clip_id"]
        old = state["clips"].get(clip_id, {})
        state["clips"][clip_id] = {**old, **item, "active": True,
                                   "ready": old.get("ready", False), "queue": old.get("queue"),
                                   "status": old.get("status", "new")}
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


def _totals(state: dict) -> dict[str, tuple[int, int, int, int, int]]:
    totals = {name: [0, 0, 0, 0, 0] for name in collections}
    for item in state["clips"].values():
        if not item["active"] or item["collection"] not in totals:
            continue
        row = totals[item["collection"]]
        row[0] += 1
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
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != len(columns) or parts[0] in (columns[0], "") or set(parts[0]) == {"-"}:
            continue
        try:
            result[parts[0]] = (int(parts[1].split()[0].split("(")[0]),
                                int(parts[2].split()[0].split("(")[0]),
                                float(parts[3].split()[0]),
                                *(int(part.split()[0].split("(")[0]) for part in parts[4:]))
        except (ValueError, IndexError) as exc:
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


def _write_new(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)


def _report(kind: str) -> Path:
    records, errors = _search_clips()
    state = _reconcile(_load_state(), records, errors)
    previous = _read_previous(_previous(kind))
    totals = _totals(state)
    when = datetime.now().astimezone()
    name = f"{kind}_{when.strftime('%Y-%m-%d_%H-%M-%S-%f')}"
    text = _render(kind, when, totals, previous)
    _save_state(state)
    path = reports_dir / f"{name}.txt"
    _write_new(path, text)
    if errors:
        _write_new(error_dir / f"{name}_errors.txt", "\n".join(errors) + "\n")
    _log(f"{kind}-Bericht: {path.name}; {sum(row[0] for row in totals.values())} aktive Clips; "
         f"{len(errors)} Auffälligkeiten")
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
