#!/usr/bin/env python3
"""Group failed jobs of the Marathon detail reports (Restore, Transcode, QC) by reason pattern."""

# --------- IMPORTS ---------
import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


# --------- CONFIG ---------
app_name = "Auswertung Detailberichte"
app_version = "3.0.0"

marathon_root = Path(r"C:\Users\Martin\OneDrive - LOOKS Film & TV Produktionen GmbH\Desktop\Code\Marathon")
archive_dir = marathon_root / "reports" / "archive"
state_path = marathon_root / "state" / "marathon.json"
output_dir = Path(__file__).resolve().parent


# --------- STATIC ---------
report_types: dict[str, str] = {"restore": "Restore", "transcode": "Transcode", "qc": "QC"}
missing_folder = "nicht in marathon.json gefunden"
manual_prefix = re.compile(r"^\s*manuelle prüfung:\s*", re.I)
# Marathon adds this row to every rejected job because it looks for an AQC test report; meaningless for Transcode.
noise_rows = {"prüfbericht fehlt"}
row_labels = {"job", "zeit", "versuch", "ergebnis", "fehler", "ist", "info", "ablage"}

block_start = re.compile(r"^#\s*\d+\s+([A-ZÄÖÜ]+)\b\s*(.*)$")
row_line = re.compile(r"^\s{2,}(\S+)\s+(.*?)\s*$")
date_in_name = re.compile(r"(\d{4}-\d{2}-\d{2})_")
period_line = re.compile(r"^Zeitraum\s+(.+?)\s+[–—-]\s+(.+?)\s*$", re.I)
date_value = re.compile(r"\d{4}-\d{2}-\d{2}")

# Order matters: specific patterns first, plain numbers last.
placeholders = (
    (re.compile(r"\d{8}T\d+__\d+__\w+"), "<job>"),
    (re.compile(r"\\\\[^;:]+"), "<pfad>"),
    # Two separators at least, so that "Kanal 1/2" stays readable.
    (re.compile(r"[A-Za-z]:\\[^\s;]+|(?:[A-Za-z]:)?[\\/]*(?:[\w.-]+[\\/]){2,}[\w.-]*"), "<pfad>"),
    (re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.[A-Za-z][A-Za-z0-9]{1,4}\b"), "<datei>"),
    (re.compile(r"\b\d+:\d{2}:\d{2}(?:[:;.,]\d+)?\b"), "<tc>"),
    (re.compile(r"\b[A-Z0-9]{6}L\d\b"), "<band>"),
    (re.compile(r"\d+(?:[.,]\d+)?"), "#"),
)
parentheses = re.compile(r"\s*\([^()]*\)")
square_brackets = re.compile(r"\s*\[[^\[\]]*\]")
source_prefix = re.compile(r"^(?:Source\s+)?\S+\.[A-Za-z0-9]{2,4}:\s*")
qc_criterion = re.compile(r"^(?P<tool>[\w-]+\([^()]*\)):\s*(?P<krit>\S+)\s+erwartet")
qc_failed_prefix = re.compile(r"^\S+\.[A-Za-z0-9]{2,4}:\s*(nicht ausführbar:)\s*\S+\.[A-Za-z0-9]{2,4}:\s*")
repeated_items = re.compile(r"(?P<item>[^\s,]+)(?:\s*,\s*(?P=item))+(?![^\s,])")


# --------- PARSE ---------
@dataclass
class Case:
    status: str
    title: str
    rows: dict[str, list[str]] = field(default_factory=dict)
    clip_id: str = ""
    collection: str = ""
    folder: str = ""

    def value(self, label: str) -> str:
        return " ".join(self.rows.get(label, []))

    @property
    def job_id(self) -> str:
        return self.value("job")

    @property
    def result(self) -> str:
        return self.value("ergebnis")

    @property
    def extras(self) -> list[str]:
        return [value for label in ("fehler", "ist", "info") for value in self.rows.get(label, [])
                if value.casefold() not in noise_rows]


@dataclass
class Report:
    path: Path
    cases: list[Case]
    start: date | None
    end: date | None
    day: date | None


def parse_date(value: str) -> date | None:
    match = date_value.search(value)
    try:
        return date.fromisoformat(match.group()) if match else None
    except ValueError:
        return None


def parse_facts(case: Case, line: str) -> None:
    for segment in line.split("·"):
        label, _, value = segment.strip().partition(" ")
        if label.casefold() == "clip_id":
            case.clip_id = value.strip()
        elif label.casefold() == "kollektion":
            case.collection = value.strip()


def parse_cases(text: str) -> list[Case]:
    cases, current, last_label = [], None, None
    for line in text.splitlines():
        if match := block_start.match(line):
            current, last_label = Case(match.group(1), match.group(2).strip()), None
            cases.append(current)
            continue
        if current is None or not line.strip():
            last_label = None
            continue
        if line.strip().casefold().startswith("clip_id "):
            parse_facts(current, line)
            continue
        match = row_line.match(line)
        if match and match.group(1).casefold() in row_labels:
            last_label = match.group(1).casefold()
            current.rows.setdefault(last_label, []).append(match.group(2))
        elif last_label:
            # Multi-line values (e.g. exception texts) continue without row label.
            current.rows[last_label][-1] += f" {line.strip()}"
    return cases


def parse_report(path: Path, text: str) -> Report:
    start = end = None
    for line in text.splitlines():
        if match := period_line.match(line):
            start, end = parse_date(match.group(1)), parse_date(match.group(2))
            break
    match = date_in_name.search(path.name)
    return Report(path, parse_cases(text), start, end, (parse_date(match.group(1)) if match else None) or start)


def read_report_text(path: Path) -> tuple[str | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        return None, f"Warnung: Bericht nicht lesbar, übersprungen: {path.name} ({error})"
    return (text, None) if text.strip() else (None, f"Warnung: leeren Bericht übersprungen: {path.name}")


def discover_reports(archive: Path, typ: str) -> tuple[list[Path], str | None]:
    prefix = f"details_{typ}_".casefold()
    try:
        paths = [path for path in archive.iterdir()
                 if path.name.casefold().startswith(prefix) and path.name.casefold().endswith(".txt") and path.is_file()]
    except OSError as error:
        return [], f"Warnung: Archivverzeichnis nicht lesbar: {archive} ({error})"
    return sorted(paths, key=lambda path: path.name), None


def select_latest(paths: list[Path], n: int | None) -> list[Path]:
    return paths[-n:] if n is not None else paths


def filter_collection(cases: list[Case], kollektion: str | None) -> list[Case]:
    if kollektion is None:
        return cases
    needle = kollektion.casefold()
    return [case for case in cases if needle in case.collection.casefold()]


def default_output_name(typ: str, kollektion: str | None) -> str:
    if kollektion is None:
        return f"auswertung_{typ}.txt"
    safe = re.sub(r"[^\w-]+", "_", kollektion).strip("_")
    return f"auswertung_{typ}_{safe}.txt"


def normalize_argv(argv: list[str]) -> list[str]:
    normalized = []
    for argument in argv:
        match = re.fullmatch(r"--(\d+)", argument)
        normalized.extend(("--n", match.group(1)) if match else (argument,))
    return normalized


# --------- STATE ---------
def build_clip_folder_index(state) -> dict[str, str]:
    clips = state.get("clips") if isinstance(state, dict) else None
    entries = clips.items() if isinstance(clips, dict) else ((None, clip) for clip in clips) if isinstance(clips, list) else ()
    folders = {}
    for key, clip in entries:
        if not isinstance(clip, dict):
            continue
        clip_id = next((str(value) for value in (clip.get("clip_id"), key)
                        if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value)), None)
        files = clip.get("files")
        master = files.get("master") if isinstance(files, dict) else None
        folder = master.get("folder") if isinstance(master, dict) else None
        if clip_id and isinstance(folder, str) and folder:
            folders[clip_id] = folder
    return folders


def load_clip_folder_index(path: Path) -> tuple[dict[str, str], str | None]:
    try:
        state = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}, f"Warnung: {path} nicht gefunden; Ordner werden als „{missing_folder}“ ausgegeben."
    except (OSError, UnicodeError, ValueError) as error:
        return {}, f"Warnung: {path} nicht lesbar; Ordner werden als „{missing_folder}“ ausgegeben. ({error})"
    return build_clip_folder_index(state), None


# --------- CATEGORIZE ---------
def reasons(case: Case, typ: str) -> list[str]:
    """Return the report-specific raw reason texts for a case."""
    if typ == "qc":
        criteria = [f"{match['tool']} · {match['krit']}" for line in case.rows.get("fehler", [])
                    if (match := qc_criterion.match(line))]
        if criteria:
            return criteria
        text = qc_failed_prefix.sub(r"\1 ", case.result) if case.result else "; ".join(case.extras)
        return [text.strip()] if text.strip() else ["Ohne Angabe im Bericht"]

    text = case.result if case.result else "; ".join(case.extras)
    if typ == "restore":
        parts = [source_prefix.sub("", part.strip()).strip() for part in text.split(";") if part.strip()]
    else:
        text = manual_prefix.sub("", text)
        parts = [part.strip() for part in text.split(";") if part.strip()]
    return parts or ["Ohne Angabe im Bericht"]


def pattern(reason: str) -> str:
    """Category key: variable parts replaced by placeholders, details in brackets dropped."""
    text = reason
    while True:
        stripped = square_brackets.sub("", parentheses.sub("", text))
        if stripped == text:
            break
        text = stripped
    for regex, replacement in placeholders:
        text = regex.sub(replacement, text)
    text = repeated_items.sub(r"\g<item>", text)
    return re.sub(r"\s+", " ", text).strip(" .;:") or reason


def categories(case: Case, typ: str) -> list[str]:
    raw_reasons = reasons(case, typ)
    if typ == "qc" and any(qc_criterion.match(line) for line in case.rows.get("fehler", [])):
        return list(dict.fromkeys(raw_reasons))
    return list(dict.fromkeys(pattern(reason) for reason in raw_reasons))


# --------- COLLECT ---------
def collect_cases(reports: list[Report], clip_folders: dict[str, str]) -> list[Case]:
    """Deduplicate clips, keeping the last case in report-name order."""
    unique = {}
    for report in reports:
        for index, case in enumerate(report.cases):
            case.folder = clip_folders.get(case.clip_id, missing_folder)
            unique[case.clip_id or f"{report.path.name}:{index}"] = case
    return list(unique.values())


def period_label(reports: list[Report]) -> str:
    dates = [value for report in reports for value in (report.start, report.end, report.day) if value]
    return f"{min(dates).isoformat()} bis {max(dates).isoformat()}" if dates else "nicht bestimmbar"


# --------- OUTPUT ---------
def case_lines(case: Case) -> list[str]:
    head = " · ".join(value for value in (case.clip_id or "Clip-ID fehlt", case.title, case.status, case.value("zeit")) if value)
    rows = [("Pfad", case.folder), ("Grund", case.result), *(("Zusatz", extra) for extra in case.extras), ("Job", case.job_id)]
    return [f"  {head}", *(f"    {label:<6} {value}" for label, value in rows if value)]


def render_summary(reports: list[Report], cases: list[Case], typ: str, kollektion: str | None) -> str:
    grouped: dict[str, list[Case]] = {}
    for case in cases:
        for category in categories(case, typ):
            grouped.setdefault(category, []).append(case)
    ranked = sorted(grouped, key=lambda category: (-len(grouped[category]), category.casefold()))
    width = len(str(len(ranked)))
    title = f"{app_name} {app_version} · {report_types[typ]}"
    lines = [title, "=" * len(title), f"Zeitraum: {period_label(reports)}", f"Kollektion: {kollektion or 'alle'}",
             f"Anzahl Berichte: {len(reports)}", f"Gesamtzahl Fälle: {len(cases)}", f"Kategorien: {len(ranked)}",
             "Fälle mit mehreren Gründen stehen in jeder passenden Kategorie.", "",
             "Kategorien nach Häufigkeit", "--------------------------"]
    lines += [f"  [{number:>{width}}] {len(grouped[category]):>5}  {category}" for number, category in enumerate(ranked, 1)]
    lines += [] if ranked else ["  Keine Fälle gefunden."]
    lines += ["", "Fälle je Kategorie", "------------------"]
    for number, category in enumerate(ranked, 1):
        lines += ["", f"[{number}] {category} ({len(grouped[category])})"]
        for case in sorted(grouped[category], key=lambda item: (item.job_id, item.title)):
            lines += case_lines(case)
    return "\n".join(lines) + "\n"


# --------- CONSOLE ---------
def show_progress(quiet: bool, message: str) -> None:
    if not quiet:
        sys.stderr.write(f"\r{message}")
        sys.stderr.flush()


def print_warning(quiet: bool, message: str) -> None:
    if not quiet:
        sys.stderr.write(f"\n{message}\n")
        sys.stderr.flush()


def load_reports(paths: list[Path], quiet: bool) -> tuple[list[Report], int]:
    reports, failed = [], 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        for index, (path, (text, warning)) in enumerate(zip(paths, executor.map(read_report_text, paths)), 1):
            show_progress(quiet, f"Auswerten [{index}/{len(paths)}] {path.name}")
            if warning:
                failed += 1
                print_warning(quiet, warning)
                continue
            reports.append(parse_report(path, text))
    return reports, failed


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--n erwartet eine ganze Zahl >= 1") from error
    if number < 1:
        raise argparse.ArgumentTypeError("--n erwartet eine ganze Zahl >= 1")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fehlerfälle aus Marathon-Detailberichten (Restore, Transcode, QC) nach Grund kategorisieren.")
    report_group = parser.add_mutually_exclusive_group(required=True)
    for typ in report_types:
        report_group.add_argument(f"--{typ}", action="store_const", dest="typ", const=typ)
    parser.add_argument("--kollektion", help="Kollektion als Teilzeichenfolge filtern (Standard: alle)")
    parser.add_argument("--n", type=positive_int, help="Nur die neuesten N Berichte lesen; Kurzform --N (z. B. --5)")
    parser.add_argument("--archiv", type=Path, default=archive_dir, help=f"Archivverzeichnis (Standard: {archive_dir})")
    parser.add_argument("--ausgabe", type=Path, default=None, help="Zieldatei (Standard: automatisch nach Typ und Kollektion)")
    parser.add_argument("--leise", action="store_true", help="Fortschritts- und Warnmeldungen unterdrücken")
    return parser


# --------- MAIN ---------
def main(argv: list[str] | None = None) -> int:
    argv = normalize_argv(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.kollektion is not None and not args.kollektion.strip():
        parser.error("--kollektion darf nicht leer sein")
    started = time.perf_counter()

    paths, warning = discover_reports(args.archiv, args.typ)
    if warning:
        print_warning(args.leise, warning)
    selected_paths = select_latest(paths, args.n)
    reports, failed = load_reports(selected_paths, args.leise)
    clip_folders, warning = load_clip_folder_index(state_path)
    if warning:
        print_warning(args.leise, warning)
    cases = filter_collection(collect_cases(reports, clip_folders), args.kollektion)
    output_path = args.ausgabe or output_dir / default_output_name(args.typ, args.kollektion)
    show_progress(args.leise, f"Schreiben: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_summary(reports, cases, args.typ, args.kollektion), encoding="utf-8")

    if not args.leise:
        print(f"\nFertig in {time.perf_counter() - started:.2f}s — Berichte: {len(reports)}/{len(paths)}, "
              f"Fehlerfälle: {len(cases)}, fehlerhafte Berichte: {failed}", file=sys.stderr)
    return 0


# --------- EXEC ---------
if __name__ == "__main__":
    raise SystemExit(main())
