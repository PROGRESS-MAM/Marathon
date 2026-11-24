# --------- IMPORTS ---------
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import load_config, state_path
from core.constants import invalid_path_chars
from core.console import log
from core.jobs import withdraw
from core.layout import acquire_lock, check_root, qc_inbox
from core.share import safe_work_path
from core.state import add_event, load_state, position, save_state
from core.util import clip_text, stamp


# --------- CONFIG ---------
app_name = "reset_qc"
app_version = "1.0.0"
category_pattern = re.compile(r"^\[(\d+)\] .+ \((\d+)\)$")
case_pattern = re.compile(r"^  (\d+) · ")


# --------- FUNC ---------
def parse_report(text: str) -> dict[int, list[str]]:
    """Extract unique clip IDs by category from a QC evaluation report."""
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if line.strip() == "Fälle je Kategorie"), None)
    if start is None:
        raise ValueError("Auswertung enthält keine Zeile 'Fälle je Kategorie'.")

    categories: dict[int, list[str]] = {}
    expected: dict[int, int] = {}
    found: dict[int, int] = {}
    current = None
    for line in lines[start + 1:]:
        header = category_pattern.fullmatch(line)
        if header:
            current = int(header.group(1))
            categories[current] = []
            expected[current] = int(header.group(2))
            found[current] = 0
            continue
        case = case_pattern.match(line) if current is not None else None
        if case:
            clip_id = case.group(1)
            found[current] += 1
            if clip_id not in categories[current]:
                categories[current].append(clip_id)

    if not categories:
        raise ValueError("Auswertung enthält keine Kategorien.")
    for number, clip_ids in categories.items():
        if found[number] != expected[number]:
            raise ValueError(f"Kategorie [{number}]: erwartet {expected[number]} Fälle, gefunden {found[number]}")
    return categories


def select_clips(categories: dict[int, list[str]], keep: set[int]) -> tuple[list[str], set[str]]:
    """Return unique reset IDs in report order and all IDs belonging to kept categories."""
    for number in sorted(keep):
        if number not in categories:
            raise ValueError(f"Kategorie [{number}] nicht in der Auswertung")

    kept = {clip_id for number in keep for clip_id in categories[number]}
    reset, seen = [], set()
    for number, clip_ids in categories.items():
        if number in keep:
            continue
        for clip_id in clip_ids:
            if clip_id not in kept and clip_id not in seen:
                reset.append(clip_id)
                seen.add(clip_id)
    return reset, kept


def plan_reset(state: dict, clip_ids: list[str]) -> tuple[list[dict], list[tuple[str, str]]]:
    """Partition requested IDs into resettable clips and skips without changing state."""
    clips, reset, skips = state["clips"], [], []
    for clip_id in clip_ids:
        clip = clips.get(clip_id)
        if clip is None:
            skips.append((clip_id, "nicht in der JSON"))
            continue
        if clip["ready"] or clip["stage"] != "qc":
            skips.append((clip_id, f"nicht in QC (Stand: {position(clip)})"))
            continue
        job = clip["job"]
        if job and job["state"] == "laufend":
            skips.append((clip_id, f"QC-Job läuft bei {job.get('worker') or 'unbekannt'}"))
            continue
        if not clip["masters"]:
            skips.append((clip_id, "keine Masterdateien aus EditShare (kein Restore möglich)"))
            continue
        proxy = clip["files"]["proxy"]
        if proxy and proxy["folder"].casefold() != qc_inbox(clip["collection"]).casefold():
            skips.append((clip_id, f"Proxy nicht im QC-Eingang: {proxy['folder']}/{proxy['name']}"))
            continue
        reset.append(clip)
    return reset, skips


def reset_clip(clip: dict, state: dict) -> tuple[bool, str]:
    """Withdraw a planned clip's job, delete its QC proxy and queue it for restore."""
    previous = position(clip)
    if not withdraw(clip, state):
        return False, "Job läuft oder wurde gerade übernommen"

    proxy = clip["files"]["proxy"]
    path = None
    try:
        if not proxy:
            text = "kein Proxy eingetragen"
        else:
            folder, name = proxy.get("folder"), proxy.get("name")
            if not isinstance(folder, str) or folder.casefold() != qc_inbox(clip["collection"]).casefold():
                raise ValueError("Proxy nicht im QC-Eingang")
            if not isinstance(name, str) or not name or name in (".", "..") or any(char in invalid_path_chars for char in name):
                raise ValueError(f"Unsicherer Proxy-Dateiname: {name!r}")
            path = safe_work_path(folder) / name
            exists = path.is_file()
            text = f"Proxy {'gelöscht' if exists else 'fehlte bereits'}: {folder}/{name}"

        pending = clip.copy()
        pending["history"] = clip["history"].copy()
        pending.update(job=None, attempts=0, ready=False, active=True, stage="restore", status="wartet",
                       queued_at=stamp(), preset=None)
        pending["files"] = {"master": None, "proxy": None}
        pending["issues"] = {"file": None, "sticky": None}
        add_event(pending, "Für Restore zurückgesetzt (QC-Neustart)", f"Vorher: {previous}; {text}")
        if path is not None and exists:
            path.unlink()
    except (OSError, ValueError) as exc:
        return False, f"Proxy nicht löschbar: {exc}"

    clip.update(pending)
    return True, text


# --------- MAIN ---------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=app_name)
    parser.add_argument("report", help="Pfad zur QC-Auswertung")
    parser.add_argument("--keep", type=int, nargs="+", required=True, help="Kategorien, die nicht zurückgesetzt werden")
    parser.add_argument("--apply", action="store_true", help="Änderungen ausführen")
    args = parser.parse_args(argv)

    try:
        if reason := load_config():
            print(reason)
            return 1
        acquire_lock()
        check_root()
        if not state_path.exists():
            print("Noch keine JSON")
            return 1
        state = load_state()
        if state.get("cleanup", {}).get("pending"):
            print("Bereinigung noch unvollständig; zuerst 'delete-folder' erneut ausführen.")
            return 1

        categories = parse_report(Path(args.report).read_text(encoding="utf-8-sig"))
        keep = set(args.keep)
        clip_ids, kept = select_clips(categories, keep)
        reset, skips = plan_reset(state, clip_ids)
        print(f"Auswertung: {len(reset) + len(skips)} Clips zum Zurücksetzen ausgewählt, {len(kept)} bleiben (Kategorien {keep})")
        for clip in reset:
            print("  " + clip_text(clip))
        if skips:
            print("Übersprungen:")
            for clip_id, reason in skips:
                print(f"  {clip_id}: {reason}")
        if not args.apply:
            print("Vorschau – nichts geändert. Zum Ausführen --apply anhängen.")
            return 0

        changed = False
        reset_ids, failed_results = [], []
        deleted = missing = failed = 0
        try:
            for clip in reset:
                previous_job = clip["job"]
                try:
                    ok, text = reset_clip(clip, state)
                except Exception:
                    changed = True
                    raise
                changed = changed or ok or (previous_job is not None and clip["job"] is None)
                if ok:
                    reset_ids.append(clip["clip_id"])
                    deleted += text.startswith("Proxy gelöscht:")
                    missing += text.startswith("Proxy fehlte bereits:")
                else:
                    failed += 1
                    failed_results.append((clip["clip_id"], text))
        finally:
            if changed:
                save_state(state)

        check = load_state()
        for clip_id in reset_ids:
            clip = check["clips"].get(clip_id)
            if not clip or clip["stage"] != "restore" or clip["files"]["proxy"] is not None:
                print("JSON-Kontrolle fehlgeschlagen")
                return 1
        log(f"reset_qc: {len(reset_ids)} Clips auf Restore zurückgesetzt ({deleted} Proxys gelöscht, {missing} fehlten bereits), "
            f"{len(skips) + failed} übersprungen")
        for clip_id, text in failed_results:
            log(f"  {clip_id}: {text}")
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(exc)
        return 1


# --------- EXEC ---------
if __name__ == "__main__":
    raise SystemExit(main())
