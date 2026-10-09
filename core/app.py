"""Job cycle, console and command loop."""
# --------- IMPORTS ---------
import argparse
import queue
import threading
from datetime import datetime, timedelta

from . import app_name, app_version
from .constants import commands_help
from .config import cfg, load_config, reports_dir, state_path
from .console import log
from .util import context, now
from .layout import acquire_lock, check_root, load_mapping, prepare
from .share import ensure_folders
from .state import keep_notes, load_state, save_state
from .priority import priority
from .ffe import sync_references, update_ffe
from .index import update_index
from .jobs import process
from .cleanup import begin_delete, delete_folders
from .report import report
from .details import write_details
from .ingest import ingest
from .testrun import cancel_test, start_qc_test, start_test, test_cycle, test_job_ids, test_status


# --------- FUNC ---------
def _cycle() -> str | None:
    """Run one job cycle with the loaded configuration; returns the reason if it was skipped."""
    if not state_path.exists():
        return "Job-Zyklus übersprungen: keine JSON ('update-index' ausführen oder 'run' erneut eingeben)."
    mapping = load_mapping()
    check_root()
    state, ctx = load_state(), context()
    if state.get("cleanup", {}).get("pending"):
        return "Bereinigung noch unvollständig; zuerst delete-folder erneut ausführen."
    process(state, mapping, priority(mapping, state, ctx), ctx, writing=True, test_ids=test_job_ids())
    keep_notes(state, ctx["issues"])
    state["updated_at"] = now()
    save_state(state)
    return None


def _create_folders() -> None:
    mapping = load_mapping()
    check_root()
    created, ctx = ensure_folders(mapping, force=True), context()
    copied = sync_references(ctx)
    log(f"Ordnerstruktur für {len(mapping)} Kollektionen geprüft: {created} Ordner neu angelegt; "
         f"FFE-Referenzen: {copied} Dateien aktualisiert.")
    for item in ctx["issues"]:
        log(f"{item['category']}: {item['detail']}")


def _start_run() -> None:
    """Quick start: create missing folders and build the JSON if it does not exist yet."""
    if state_path.exists() and load_state().get("cleanup", {}).get("pending"):
        raise RuntimeError("Bereinigung noch unvollständig; zuerst 'delete-folder' erneut ausführen.")
    _create_folders()
    if not state_path.exists():
        log("Noch keine JSON – Index wird aus der Suche aufgebaut.")
        update_index()


def _auto_due(now: datetime) -> bool:
    return now.time() >= cfg["auto_report_time"] and not any(reports_dir.glob(f"auto_{now:%Y-%m-%d}_*.txt"))


def _command(raw: str) -> str:
    return "-".join(raw.casefold().replace("_", " ").replace("-", " ").split())


def _help_text() -> str:
    return "Befehle:\n" + "\n".join(f"  {name:<16} {text}" for name, text in commands_help.items())


def _status_text(mode: str | None, auto: bool) -> str:
    when = cfg.get("auto_report_time")
    auto_text = (f"an (täglich ab {when:%H:%M})" if when else "an") if auto else "aus"
    return (f"Status: Job-Schleife {'läuft' if mode == 'run' else 'aus'}; Test-Modus {'läuft' if mode == 'test' else 'aus'} "
            f"({test_status()}); Auto-Bericht {auto_text}.")


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
    """Start Marathon: run the startup commands, then process console commands until quit."""
    parser = argparse.ArgumentParser(description="Marathon: Index, Job-Steuerung und Berichte", epilog=_help_text(),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("commands", nargs="*", metavar="befehl", help="Befehle, die direkt nach dem Start laufen")
    startup = [_command(item) for item in parser.parse_args(argv).commands]
    unknown = [item for item in startup if item not in commands_help]
    if unknown:
        parser.error(f"Unbekannte Befehle: {', '.join(unknown)}")
    prepare()
    acquire_lock()
    log(f"{app_name} {app_version} gestartet.")
    commands: queue.Queue[str] = queue.Queue()
    for item in startup:
        commands.put(item)
    if "quit" not in startup:
        threading.Thread(target=_console, args=(commands,), daemon=True).start()
    log("Marathon wartet auf Befehle ('help' zeigt alle).")
    mode, auto = None, False  # mode: None, "run" (job loop) or "test" (test mode); never both at once.
    pending_delete = None
    next_cycle = next_retry = last_problem = last_skip = None
    while True:
        problem = load_config()
        if problem != last_problem:
            log(problem or "Konfiguration gültig.")
            last_problem = problem
        now = datetime.now().astimezone()
        try:
            command = commands.get(timeout=0.5)
        except queue.Empty:
            if auto and not problem and _auto_due(now) and (next_retry is None or now >= next_retry):
                try:
                    report("auto")
                    next_retry = None
                    write_details()
                except Exception as exc:
                    next_retry = now + timedelta(minutes=cfg["retry_minutes"])
                    log(f"Auto-Bericht fehlgeschlagen: {exc}; neuer Versuch in {cfg['retry_minutes']} min.")
            if mode and not problem and now >= next_cycle:
                try:
                    if mode == "test":
                        if test_cycle():
                            mode = None
                            log(_status_text(mode, auto))
                    else:
                        skipped = _cycle()
                        if skipped and skipped != last_skip:
                            log(skipped)
                        last_skip = skipped
                except Exception as exc:
                    log(f"Test-Zyklus fehlgeschlagen: {exc}; Test-Modus bleibt aktiv." if mode == "test" else
                        f"Job-Zyklus fehlgeschlagen: {exc}; Job-Schleife bleibt aktiv.")
                next_cycle = now + timedelta(seconds=cfg["cycle_seconds"])
            continue
        if pending_delete is not None:
            plan, pending_delete = pending_delete, None
            if command == "loeschen" and not problem:
                try:
                    delete_folders(plan)
                except Exception as exc:
                    log(f"Bereinigung fehlgeschlagen: {exc}")
                continue
            log("Bereinigung abgebrochen. Nichts gelöscht; Job-Schleife bleibt aus.")
            if command not in ("quit", "__eof__"):
                continue
        if command == "__eof__":
            continue
        if command == "quit":
            log("Marathon beendet.")
            return
        if command not in commands_help or command == "help":
            log(("" if command in ("", "help") else f"Unbekannter Befehl {command!r}.\n") + _help_text())
            continue
        if command in ("stop", "auto-report-off", "status"):
            mode, auto = None if command == "stop" else mode, auto and command != "auto-report-off"
            log(_status_text(mode, auto))
            continue
        if command == "delete-folder":
            mode = None
            log("Job-Schleife und Test-Modus für Bereinigung angehalten.")
        if problem:
            log(f"{command!r} während der Pause nicht möglich: {problem}")
            continue
        try:
            if command == "run":
                _start_run()
                if mode == "test":
                    log("Test-Modus angehalten; der Test-Lauf bleibt offen ('test' setzt ihn fort).")
                mode, next_cycle, last_skip = "run", now, None
            elif command in ("test", "test-qc"):
                (start_qc_test if command == "test-qc" else start_test)()
                if mode == "run":
                    log("Job-Schleife angehalten; Produktions-Jobs und JSON bleiben unverändert.")
                mode, next_cycle = "test", now
            elif command == "test-cancel":
                cancel_test()
                mode = None if mode == "test" else mode
            elif command == "auto-report":
                auto, next_retry = True, None
            elif command == "report":
                report("manual")
            elif command == "create-folders":
                _create_folders()
            elif command == "delete-folder":
                pending_delete = begin_delete()
            elif command == "update-ffe":
                update_ffe()
            elif command in ("ingest-master", "ingest-proxy"):
                ingest(command.removeprefix("ingest-"))
            else:
                update_index()
            if command in ("run", "test", "test-qc", "test-cancel", "auto-report"):
                log(_status_text(mode, auto))
        except Exception as exc:
            log(f"{command!r} fehlgeschlagen: {exc}")
