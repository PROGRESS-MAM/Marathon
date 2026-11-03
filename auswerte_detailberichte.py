#!/usr/bin/env python3
"""Summarize failed detail-report cases in reports/archive.

For --tage, the archive filename date takes precedence; the report period's
start date is the fallback. The window includes today and the preceding X-1
calendar days. Rejected or blocked job outputs are archived; failed outputs
are deleted. QC output may be a flat AQC report or an archived stage output.
Reconstructed paths remain candidates because runtime paths and the outbox
suffix are not present in detail reports.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

BLOCK_START = re.compile(r"^#\s*\d+\s+(FAILED|REJECTED|BLOCKIERT)\b(.*)$", re.I)
FIELD = re.compile(
    r"^\s*(clip_id|Job|Zeit|Versuch|Ergebnis|Fehler|Ist|Info|Ablage)\s+(.*?)\s*$",
    re.I,
)
DATE_IN_NAME = re.compile(r"_(\d{4}-\d{2}-\d{2})_")
DATE_IN_TEXT = re.compile(r"Zeitraum\s+(.+?)\s+(?:–|—|-)\s+(.+?)\s*$", re.I)
DATE_VALUE = re.compile(r"\d{4}-\d{2}-\d{2}")
VARIABLES = (
    (re.compile(r"\b\d{8}T\d{6}\d+\b", re.I), "<job-time>"),
    (re.compile(r"\bclip_id\s*\d+\b", re.I), "clip_id <id>"),
    (re.compile(r"\b(?:clip|id|job)\s*#?\d+\b", re.I), "<identifier>"),
    (re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:bytes?|mb|gb|tb|streams?|kanäle?)\b", re.I), "<amount>"),
    (re.compile(r"\b\d+\s+von\s+\d+\b", re.I), "<attempt>"),
    (re.compile(r"\b(?:\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\b"), "<timecode>"),
    (re.compile(r"\b\d+\b"), "<number>"),
)


@dataclass
class ReportCase:
    status: str
    title: str
    clip_id: str = ""
    collection: str = ""
    job_id: str = ""
    result: str = ""
    path: str = ""
    stage: str = ""
    category: str = ""


@dataclass
class Report:
    path: Path
    cases: list[ReportCase]
    report_start: date | None
    report_end: date | None
    report_date: date | None


def parse_date(value: str) -> date | None:
    match = DATE_VALUE.search(value)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group())
    except ValueError:
        return None


def report_dates(text: str) -> tuple[date | None, date | None]:
    for line in text.splitlines():
        match = DATE_IN_TEXT.match(line)
        if match:
            return parse_date(match.group(1)), parse_date(match.group(2))
    return None, None


def report_filename_date(path: Path) -> date | None:
    match = DATE_IN_NAME.search(path.name)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def extract_stage(path: Path, text: str) -> str:
    match = re.match(r"details_([a-z]+)_", path.name, re.I)
    if match:
        return match.group(1).lower()
    match = re.search(r"Detailbericht\s+([\w-]+)", text, re.I)
    return match.group(1).lower() if match else ""


def parse_cases(text: str, stage: str) -> list[ReportCase]:
    cases = []
    current = None
    fields = {}

    def finish_case():
        if current is None:
            return
        current.clip_id = fields.get("clip_id", "")
        fact_segments = current.clip_id.split("·")
        current.clip_id = fact_segments[0].strip()
        for segment in fact_segments[1:]:
            collection_match = re.match(r"\s*Kollektion\s+(.+?)\s*$", segment, re.I)
            if collection_match:
                current.collection = collection_match.group(1).strip()
        current.job_id = fields.get("job", "").strip()
        current.result = " ".join(fields.get(key, "") for key in ("ergebnis", "fehler", "ist", "info") if fields.get(key))
        current.path = fields.get("ablage", "").strip()
        current.stage = stage
        current.category = categorize(current)
        cases.append(current)

    for line in text.splitlines():
        block_match = BLOCK_START.match(line)
        if block_match:
            finish_case()
            current = ReportCase(status=block_match.group(1).upper(), title=block_match.group(2).strip())
            fields = {}
            continue
        if current is None:
            continue
        field_match = FIELD.match(line)
        if not field_match:
            continue
        label, value = field_match.groups()
        label = label.lower()
        if label == "clip_id":
            fields[label] = value
        else:
            fields[label] = value

    finish_case()
    return cases


def categorize(case: ReportCase) -> str:
    text = normalize_category_text(f"{case.stage} {case.status} {case.title} {case.result}")
    if any(term in text for term in ("restore", "tape", "prüfbericht fehlt", "prüfbericht fehlt", "größenabweich", "groessenabweich", "doppelte einträge", "fehlende datei")):
        return "restore_incomplete"
    if any(term in text for term in ("proxy", "mastername", "master name", "proxy-datei", "proxy-dateien", "ausgang enthält", "ausgang enthaelt")):
        return "transcode_output_contract"
    if case.stage == "qc" or any(term in text for term in ("aqc", "kriterium", "stream", "kanal")):
        return "qc_rejected"
    if case.status == "BLOCKIERT" or any(term in text for term in ("kollision", "ablage", "ausliefer", "master")):
        return "delivery_or_master_blocked"
    return "worker_failed"


def archive_path_pattern(case: ReportCase) -> str:
    collection_layout = (
        "<final_folder>/<work_dir>[/<sanitisierte Kollektion> bei DEFA]"
    )
    return f"<root_path>/{collection_layout}/{case.stage}/archiv/{case.job_id}.<outbox>"


def reconstructed_path(case: ReportCase) -> str:
    if case.path:
        return case.path
    if not case.job_id or case.status not in {"REJECTED", "BLOCKIERT"}:
        return "Pfad nicht ableitbar"
    if case.stage == "transcode":
        return f"Kandidaten: {archive_path_pattern(case)}"
    if case.stage == "qc":
        flat_report = f"<root_path>/<work_dir>/qc/archiv/{case.job_id}.aqc.json"
        archived_output = archive_path_pattern(case)
        return f"Kandidaten: {flat_report}; {archived_output}"
    return "Pfad nicht ableitbar"


def path_quality(path: str) -> int:
    if not path or path == "Pfad nicht ableitbar":
        return 0
    if path.startswith("Kandidaten:"):
        return 1
    return 2


def format_case_path(path: str) -> str:
    if path.startswith("Kandidaten:"):
        candidates = path.removeprefix("Kandidaten:").strip().split("; ")
        return "Kandidaten: " + "; ".join(f"`{candidate}`" for candidate in candidates)
    if path == "Pfad nicht ableitbar":
        return path
    return f"`{path}`"


def read_report(path: Path) -> Report | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        print(f"Warnung: Bericht nicht lesbar, übersprungen: {path.name} ({error})", file=sys.stderr)
        return None
    if not text.strip():
        print(f"Warnung: leeren Bericht übersprungen: {path.name}", file=sys.stderr)
        return None
    start, end = report_dates(text)
    report_date = report_filename_date(path) or start
    stage = extract_stage(path, text)
    return Report(path, parse_cases(text, stage), start, end, report_date)


def normalize_category_text(text: str) -> str:
    normalized = text.lower()
    for pattern, replacement in VARIABLES:
        normalized = pattern.sub(replacement, normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def date_in_window(report: Report, days: int, today: date) -> bool:
    if report.report_date is None:
        return False
    return today - timedelta(days=days - 1) <= report.report_date <= today


def collect_cases(reports: list[Report]) -> list[ReportCase]:
    unique = {}
    for report in reports:
        for index, case in enumerate(report.cases):
            case.path = reconstructed_path(case)
            key = case.job_id or f"{report.path.name}:{index}"
            previous = unique.get(key)
            if previous is None or path_quality(case.path) > path_quality(previous.path):
                unique[key] = case
    return list(unique.values())


def period_label(reports: list[Report]) -> str:
    dates = []
    for report in reports:
        dates.extend(value for value in (report.report_start, report.report_end, report.report_date) if value)
    if not dates:
        return "nicht bestimmbar"
    return f"{min(dates).isoformat()} bis {max(dates).isoformat()}"


def write_summary(path: Path, reports: list[Report], cases: list[ReportCase]) -> None:
    counts = {}
    for case in cases:
        counts[case.category] = counts.get(case.category, 0) + 1
    lines = [
        "# Auswertung der Detailberichte",
        "",
        f"- Auswertezeitraum: {period_label(reports)}",
        f"- Gelesene Berichte: {len(reports)}",
        f"- Fehlerfälle gesamt: {len(cases)}",
        "",
        "## Fehlerfälle je Kategorie",
        "",
    ]
    if counts:
        lines.extend(f"- `{category}`: {count}" for category, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])))
    else:
        lines.append("- Keine Fehlerfälle gefunden.")
    lines.extend(("", "## Fehlerfälle", ""))
    if cases:
        for case in sorted(cases, key=lambda item: (item.category, item.job_id, item.title)):
            identifier = f"`{case.job_id}`" if case.job_id else "`Job-ID fehlt`"
            lines.append(f"- {identifier} — `{case.category}` — Pfad: {format_case_path(case.path)}")
    else:
        lines.append("- Keine Fehlerfälle gefunden.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detailberichte aus reports/archive zusammenfassen.")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--alle", action="store_true", help="alle passenden Detailberichte auswerten")
    selection.add_argument("--tage", type=int, metavar="X", help="Berichte der letzten X Kalendertage auswerten (inklusive heute)")
    parser.add_argument("--archiv", type=Path, default=Path("reports/archive"), help="Archivverzeichnis (Standard: reports/archive)")
    parser.add_argument("--ausgabe", type=Path, default=Path("auswertung_detailberichte.md"), help="Zieldatei (Standard: auswertung_detailberichte.md)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.tage is not None and args.tage < 1:
        parser.error("--tage muss mindestens 1 sein")
    if not args.archiv.is_dir():
        print(f"Warnung: Archivverzeichnis nicht gefunden: {args.archiv}", file=sys.stderr)
        reports = []
    else:
        reports = []
        for path in sorted(args.archiv.glob("details_*.txt")):
            report = read_report(path)
            if report is None:
                continue
            if args.tage is not None and not date_in_window(report, args.tage, date.today()):
                continue
            reports.append(report)
    cases = collect_cases(reports)
    write_summary(args.ausgabe, reports, cases)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
