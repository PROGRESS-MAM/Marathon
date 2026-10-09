"""Daily detail reports per stage from the job journal; QC findings from the AQC test reports (<clip>.aqc.json).

Every production report the job loop collects becomes one line in state/journal_<stage>.jsonl. Together with the
auto report, write_details() turns each journal into reports/details_<stage>_<stamp>.txt and moves it to
state/journal/, so every detail report covers exactly the jobs since the previous one.
"""
# --------- IMPORTS ---------
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import app_name, app_version
from .constants import aqc_actual_marker, aqc_passed, blocked_outcome, qc_report_suffix, stage_labels, stages
from .config import reports_dir, state_dir
from .console import log
from .util import file_stamp, write_new
from .layout import share_path


# --------- FORMAT ---------
def clock(iso: str | None) -> str:
    """ISO time stamp as 'YYYY-MM-DD HH:MM:SS'; '–' if missing."""
    return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M:%S") if iso else "–"


def head(title: str, rows: list[tuple[str, object]]) -> list[str]:
    """Report head: title, underline and aligned 'label  value' rows, then a blank line."""
    width = max((len(label) for label, _ in rows), default=0)
    return [title, "=" * len(title), *(f"{label:<{width}}  {value}" for label, value in rows), ""]


def block(number: int, status: str, title: str, facts: list[tuple[str, object]], rows: list[tuple[str, str]]) -> list[str]:
    """One report entry: '#<n>  <STATUS>  <title>', a fact line 'label value · …' and labelled rows; empty values are left out."""
    lines = [f"#{number}  {status.upper()}  {title}".rstrip()]
    if facts := [f"{label} {value}" for label, value in facts if value]:
        lines.append(f"    {' · '.join(facts)}")
    return [*lines, *(f"    {label:<8} {value}" for label, value in rows if value), ""]


# --------- QC FINDINGS ---------
def _aqc_file(relative: str | None) -> Path | None:
    if not relative:
        return None
    path = share_path(relative)
    if path.is_file():
        return path
    try:
        return next((item for item in sorted(path.iterdir()) if item.name.casefold().endswith(qc_report_suffix)), None)
    except OSError:
        return None


def _failure_text(failure: dict) -> str:
    where = ", ".join(f"{label} {failure[key]}" for key, label in (("stream", "Stream"), ("channel", "Kanal"), ("tc", "TC"))
                      if failure.get(key) is not None)
    text = f"{failure.get('criterion') or '?'} erwartet {failure.get('expected') or '–'}, gefunden {failure.get('actual') or '–'}"
    return f"{text} ({where})" if where else text


def qc_findings(relative: str | None) -> tuple[list[tuple[str, str]], list[str]] | None:
    """Rows ('Fehler', 'Ist', 'Info') and tally keys '<tool> · <criterion>' of all failed tools of an AQC test report.

    relative is the .aqc.json itself or a folder containing it; None if there is no readable test report.
    """
    path = _aqc_file(relative)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig")) if path else None
    except (OSError, UnicodeError, ValueError):
        return None
    tools = data.get("tools") if isinstance(data, dict) else None
    if not isinstance(tools, list):
        return None
    rows, keys = [], []
    for tool in (tool for tool in tools if isinstance(tool, dict) and tool.get("status") != aqc_passed):
        label = tool.get("label") or tool.get("name") or "?"
        failures = [failure for failure in tool.get("failures") or [] if isinstance(failure, dict)]
        rows += [("Fehler", f"{label}: {_failure_text(failure)}") for failure in failures]
        keys += [f"{label} · {failure.get('criterion') or '?'}" for failure in failures]
        if not failures:
            rows.append(("Fehler", f"{label}: {tool.get('message') or tool.get('status') or 'nicht bestanden'}"))
            keys.append(label)
        info = [(line, *line.partition(aqc_actual_marker)) for line in map(str, tool.get("info") or [])]
        actual = [("Ist", f"{before.strip()}: {values.strip()}" if before.strip() else values.strip())
                  for _, before, found, values in info if found]
        rows += actual or [("Info", line) for line, *_ in info]
    return rows, list(dict.fromkeys(keys))


def qc_rows(findings: tuple[list[tuple[str, str]], list[str]] | None) -> list[tuple[str, str]]:
    """Rows of qc_findings() for a rejected QC job; a single 'Prüfbericht fehlt' row without a readable test report."""
    return findings[0] if findings else [("Fehler", "Prüfbericht fehlt")]


# --------- JOURNAL ---------
def _journal(stage: str) -> Path:
    return state_dir / f"journal_{stage}.jsonl"


def record_job(entry: dict) -> None:
    """Append a collected production job to the journal of entry['stage'].

    Keys: at, stage, job_id, clip_id, identifier, title, collection, status (ok, rejected, failed, blockiert), result,
    preset, worker, attempt, max_attempts, final (attempt and final only for failed), output (archived output or None).
    """
    try:
        with _journal(entry["stage"]).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:  # The job cycle must go on; only the detail report misses this job.
        log(f"Job-Protokoll nicht schreibbar ({exc}); Job {entry['job_id']} fehlt im Detailbericht.")


def _read_journal(path: Path) -> tuple[list[dict], int]:
    """Entries of a journal and the number of unreadable lines (e.g. cut off by a crash)."""
    if not path.exists():
        return [], 0
    entries, broken = [], 0
    for line in filter(str.strip, path.read_text(encoding="utf-8").splitlines()):
        try:
            entries.append(json.loads(line))
        except ValueError:
            broken += 1
    return entries, broken


# --------- REPORT ---------
def _previous_time(kind: str) -> str:
    files = sorted(reports_dir.glob(f"{kind}_*.txt"))
    if not files:
        return "Beginn der Aufzeichnung"
    return datetime.strptime(files[-1].stem[len(kind) + 1:], "%Y-%m-%d_%H-%M-%S-%f").strftime("%Y-%m-%d %H:%M:%S")


def _counts(stage: str, entries: list[dict]) -> list[tuple[str, object]]:
    counts = Counter(entry["status"] for entry in entries)
    failed = f"{counts['failed']}  (davon endgültig {sum(1 for entry in entries if entry.get('final'))})"
    rows = [("Jobs insgesamt", len(entries))]
    rows += ([("QC bestanden", counts["ok"]), ("QC nicht bestanden", counts["rejected"]), ("QC-Fehler", failed)] if stage == "qc"
             else [("ok", counts["ok"]), ("Fehlgeschlagen", failed)])
    return rows + ([("Blockiert", counts[blocked_outcome])] if stage != "restore" else [])


def _tally(found: dict[str, tuple | None]) -> list[str]:
    tally = Counter()
    for findings in found.values():
        tally.update(findings[1] if findings and findings[1] else ["Prüfbericht fehlt"])
    if not tally:
        return []
    width, ranked = max(map(len, tally)), sorted(tally.items(), key=lambda item: (-item[1], item[0].casefold()))
    return ["Nicht bestanden nach Kriterium", *(f"  {key:<{width}}  {count:>4}" for key, count in ranked), ""]


def _entry_block(number: int, entry: dict, findings: tuple | None) -> list[str]:
    attempt = f"{entry['attempt']} von {entry['max_attempts']}" + (" (endgültig)" if entry.get("final") else "") \
        if entry["status"] == "failed" and entry.get("attempt") else ""
    rows = [("Job", entry["job_id"]), ("Zeit", clock(entry["at"])), ("Versuch", attempt), ("Ergebnis", entry.get("result")),
            *(qc_rows(findings) if entry["status"] == "rejected" else []), ("Ablage", entry.get("output"))]
    facts = [("clip_id", entry["clip_id"]), ("Kollektion", entry.get("collection")), ("Preset", entry.get("preset")),
             ("Worker", entry.get("worker"))]
    return block(number, entry["status"], f"{entry.get('identifier') or ''} {entry.get('title') or ''}".strip(), facts, rows)


def _render(stage: str, entries: list[dict], since: str, when: datetime, broken: int) -> str:
    label = stage_labels[stage]
    rows = [("Zeitraum", f"{since} – {when:%Y-%m-%d %H:%M:%S}"), *_counts(stage, entries)]
    if broken:
        rows.append(("Unlesbar", f"{broken} Zeilen im Job-Protokoll"))
    issues = [entry for entry in entries if entry["status"] != "ok"]
    found = {entry["job_id"]: qc_findings(entry.get("output")) for entry in issues if entry["status"] == "rejected"}
    lines = head(f"{app_name} {app_version} · Detailbericht {label}", rows)
    lines += _tally(found) if stage == "qc" else []
    lines += [f"Details: {len(issues)}", ""]
    for number, entry in enumerate(issues, 1):
        lines += _entry_block(number, entry, found.get(entry["job_id"]))
    return "\n".join(lines).rstrip() + "\n"


def _write_stage(stage: str, when: datetime) -> None:
    kind, journal = f"details_{stage}", _journal(stage)
    entries, broken = _read_journal(journal)
    name = f"{file_stamp(kind, when)}.txt"
    write_new(reports_dir / name, _render(stage, entries, _previous_time(kind), when, broken))
    if journal.exists():
        (state_dir / "journal").mkdir(exist_ok=True)
        journal.replace(state_dir / "journal" / f"{Path(name).stem}.jsonl")
    log(f"Detailbericht {stage_labels[stage]}: {name}; {len(entries)} Jobs, "
        f"{sum(1 for entry in entries if entry['status'] != 'ok')} Auffälligkeiten.")


def write_details() -> None:
    """Write one detail report per stage covering all jobs since its previous one; a failed stage keeps its journal."""
    when = datetime.now().astimezone()
    for stage in stages:
        try:
            _write_stage(stage, when)
        except Exception as exc:  # One broken stage must not stop the others; its jobs move to the next report.
            log(f"Detailbericht {stage_labels[stage]} fehlgeschlagen: {exc}; der nächste Detailbericht deckt den Zeitraum mit ab.")
