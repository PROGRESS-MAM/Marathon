"""Time stamps, normalizing, message texts and error lists."""
# --------- IMPORTS ---------
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import app_name, app_version
from .constants import ffe_ambiguous_sections, field_names, issue_sections, match_separator
from .config import error_dir


# --------- INIT ---------
last_stamp = datetime.min.replace(tzinfo=timezone.utc)


# --------- FUNC ---------
def now() -> str:
    """Local time as ISO text with seconds."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def age(stamp: str) -> timedelta:
    """Time passed since an ISO time stamp."""
    return datetime.now().astimezone() - datetime.fromisoformat(stamp)


def duration(delta: timedelta) -> str:
    """Duration as "X min" or "X h Y min"."""
    minutes = int(delta.total_seconds() // 60)
    return f"{minutes // 60} h {minutes % 60} min" if minutes >= 60 else f"{minutes} min"


def stamp() -> str:
    """Strictly increasing UTC stamp for job ids and file names."""
    global last_stamp
    # datetime.now() repeats for about 15 ms on Windows before Python 3.13; job ids must still sort in creation order.
    last_stamp = max(datetime.now(timezone.utc), last_stamp + timedelta(microseconds=1))
    return last_stamp.strftime("%Y%m%dT%H%M%S%f")


def normalize(value: str) -> str:
    """Text for loose comparison: NFC, stripped, casefolded."""
    return unicodedata.normalize("NFC", value).strip().casefold()


def split_values(value: str) -> list[str]:
    """Non-empty parts of a "; "-separated field value."""
    return [part.strip() for part in value.split("; ") if part.strip()]


def file_name(userpath: str) -> str:
    """Last component of a Windows or POSIX path."""
    return userpath.replace("\\", "/").rsplit("/", 1)[-1].strip()


def context() -> dict:
    """New run context: issues, cached listings and final folder counts."""
    return {"issues": [], "listings": {}, "final_counts": {}}


def issue(ctx: dict, section: str, category: str, key: str, detail: str) -> None:
    """Add an issue to the run context."""
    ctx["issues"].append({"section": section, "category": category, "key": key, "detail": detail})


def clip_text(item: dict) -> str:
    """One-line description of a clip for messages and error lists."""
    return (f"Kollektion={item['collection']}, {field_names['clip_id']}={item['clip_id']}, "
            f"{field_names['identifier']}={item['identifier']}, {field_names['title']}={item['title']}")


def joined(values: Iterable[str]) -> str:
    """Values joined with " | "."""
    return " | ".join(values)


def format_detail(head: str, reason: str = "", matches: list[str] | None = None) -> str:
    """Format A: one line. Format B (several matches, one expected): head, separator, one match per line."""
    if matches:
        return "\n".join((head, match_separator, *matches))
    return f"{head}: {reason}" if reason else head


def write_lists(issues: list[dict], when: datetime, name: str, title: str) -> tuple[str | None, str | None]:
    """Write the general error list and the separate list of ambiguous FFE entries; returns the file names."""
    general = [item for item in issues if item["section"] not in ffe_ambiguous_sections]
    ambiguous = [item for item in issues if item["section"] in ffe_ambiguous_sections]
    files = []
    for items, suffix, heading, sections in ((general, "errors", title, issue_sections),
                                             (ambiguous, "ffe_uneindeutig", "FFE uneindeutig", ffe_ambiguous_sections)):
        file = f"{name}_{suffix}.txt" if items else None
        if file:
            write_new(error_dir / file, format_errors(items, when, heading, sections))
        files.append(file)
    return files[0], files[1]


def details(*files: str | None) -> str:
    """Reference to the written error list files; empty without files."""
    names = [f"errors/{name}" for name in files if name]
    return f"; Details: {', '.join(names)}" if names else ""


def summary_lines(issues: list[dict], sections: dict[str, str] = issue_sections) -> list[str]:
    """Summary lines of issues per section and category."""
    if not issues:
        return ["Keine Auffälligkeiten."]
    lines = []
    for section, title in sections.items():
        categories = defaultdict(set)
        for item in issues:
            if item["section"] == section:
                categories[item["category"]].add(item["key"])
        if not categories:
            continue
        clips = {key for keys in categories.values() for key in keys}
        total = sum(map(len, categories.values())) if section == "note" else len(clips)
        unit = ("" if section == "note" else " Einträge" if section.startswith("ffe_") else
                " Dateien" if section.startswith("ingest_") else " Clips")
        lines.append(f"{title}: {total}{unit}")
        lines += [f"  {category}: {len(keys)}" for category, keys in
                  sorted(categories.items(), key=lambda item: (-len(item[1]), item[0].casefold()))]
    return lines


def format_errors(issues: list[dict], when: datetime, title: str = "Fehlerbericht",
                   sections: dict[str, str] = issue_sections) -> str:
    """Error list text: header, summary and details per section and category."""
    lines = [f"{app_name} {app_version} | {title} | {when.isoformat(timespec='seconds')}", "", *summary_lines(issues, sections)]
    for section, heading in sections.items():
        grouped = defaultdict(list)
        for item in issues:
            if item["section"] == section:
                grouped[item["category"]].append(item["detail"])
        for category in sorted(grouped, key=str.casefold):
            details = sorted(dict.fromkeys(grouped[category]), key=str.casefold)
            lines += ["", f"=== {heading.split(' (')[0]} – {category} ({len(details)}) ==="]
            for index, detail in enumerate(details):
                if index and "\n" in detail + details[index - 1]:
                    lines.append("")  # Blank line around multi-line blocks (format B).
                lines.append(detail)
    return "\n".join(lines) + "\n"


def write_new(path: Path, text: str) -> None:
    """Write a new text file; raises FileExistsError if it already exists."""
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)


def file_stamp(kind: str, when: datetime) -> str:
    """File name stem <kind>_<time stamp> for reports and error lists."""
    return f"{kind}_{when.strftime('%Y-%m-%d_%H-%M-%S-%f')}"
