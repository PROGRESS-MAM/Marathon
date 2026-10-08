"""Reports; command report."""
# --------- IMPORTS ---------
import copy
from datetime import datetime
from pathlib import Path
from time import perf_counter

from . import app_name, app_version
from .constants import columns, count_columns, index_labels, index_sections, stages, summary_name
from .config import error_dir, reports_dir, state_path
from .console import log
from .util import context, file_stamp, format_errors, issue, now, summary_lines, write_new
from .layout import check_root, load_mapping
from .state import load_state, save_state
from .priority import priority
from .ffe import ffe_line
from .workers import watch_lines, worker_lines
from .audit import final_audit, final_lines, leftovers
from .jobs import process


# --------- FUNC ---------
def _totals(state: dict, mapping: list[dict]) -> dict[str, tuple[int, ...]]:
    totals = {entry["name"]: [0] * len(count_columns) for entry in mapping}
    for clip in state["clips"].values():
        row = totals.get(clip["collection"])
        if row is None or not clip["active"]:
            continue
        row[0] += 1
        row[1 if clip["ready"] else 2 + stages.index(clip["stage"])] += 1
    return {name: tuple(row) for name, row in totals.items()}


def _previous(kind: str) -> Path | None:
    files = sorted(reports_dir.glob(f"{kind}_*.txt"))
    return files[-1] if files else None


def _read_previous(path: Path | None) -> dict[str, dict[str, float]]:
    if path is None:
        return {}
    result, header = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.split("|")]
        if parts[0] == "Kollektion":
            header = parts
            continue
        if header is None or len(parts) != len(header) or not parts[0]:
            continue
        try:
            result[parts[0]] = {column: (float if column == "%" else int)(cell.split()[0])
                                for column, cell in zip(header, parts) if column in (*count_columns, "%")}
        except (ValueError, IndexError) as exc:
            raise ValueError(f"Vorgängerbericht {path.name} ist nicht lesbar.") from exc
    return result


def _format_int(value: int, previous: int | None) -> str:
    return str(value) if previous is None else f"{value} ({value - previous:+d})"


def _render(kind: str, when: datetime, totals: dict, prio: dict[str, list[str]], previous: dict) -> str:
    ranks = {stage: {name: str(rank) for rank, name in enumerate(prio[stage], 1)} for stage in stages}
    summary = tuple(sum(values[index] for values in totals.values()) for index in range(len(count_columns)))
    rows = []
    for name, values in (*totals.items(), (summary_name, summary)):
        old, (total, ready) = previous.get(name, {}), values[:2]
        percent = 100 * ready / total if total else 0.0
        percent_text = (f"{percent:.1f}" if total else "0") + " %"
        if "%" in old:
            percent_text += f" ({round(round(percent, 1) - old['%'], 1) + 0.0:+.1f} pp)"  # + 0.0 avoids "-0.0".
        counts = [_format_int(value, old.get(column)) for column, value in zip(count_columns, values)]
        rows.append((name, *(ranks[stage].get(name, "") for stage in stages), *counts[:2], percent_text, *counts[2:]))
    widths = [max(len(row[index]) for row in (columns, *rows)) for index in range(len(columns))]

    def line(cells) -> str:
        return " | ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()

    separator = "-+-".join("-" * width for width in widths)
    table = [line(columns), separator, *(line(row) for row in rows[:-1]), separator, line(rows[-1])]
    return f"{app_name} {app_version} | {kind} | {when.isoformat(timespec='seconds')}\n\n" + "\n".join(table) + "\n"


# --------- COMMAND ---------
def _index_line(index: dict) -> str:
    """Summary of the last update-index; its details are only in the index error list."""
    text = f"Index-Stand: {index.get('updated_at') or 'unbekannt'}"
    counts = index.get("counts") or {}
    if counts:
        text += "; " + ", ".join(f"{index_labels[section]}: {counts.get(section, 0)}" for section in index_sections)
    return text + (f"; Details: errors/{index['error_list']}" if index.get("error_list") else "")


def report(kind: str) -> Path:
    """Report from the JSON and the folders; no search and no changes on the share."""
    started = perf_counter()
    log(f"{kind}-Bericht gestartet.")
    mapping = load_mapping()
    check_root()
    if not state_path.exists():
        raise RuntimeError("Noch keine JSON – zuerst 'update-index' oder 'run'.")
    state, ctx = load_state(), context()
    ctx["issues"].extend(state["notes"])
    prio = priority(mapping, state, ctx)
    view = copy.deepcopy(state)  # The report only looks; jobs and moves stay with 'run'.
    process(view, mapping, prio, ctx, writing=False)
    ctx["listings"].clear()
    leftovers(view, mapping, ctx)
    final_audit(state, mapping, ctx)
    totals = _totals(view, mapping)
    try:
        previous = _read_previous(_previous(kind))
    except (OSError, UnicodeError, ValueError) as exc:
        previous = {}
        issue(ctx, "note", "Vorbericht nicht lesbar – keine Deltas", "previous", str(exc))
    when = datetime.now().astimezone()
    name = file_stamp(kind, when)
    watch, workers = watch_lines(view), worker_lines(view)
    text = _render(kind, when, totals, prio, previous) + f"\n{_index_line(state['index'])}\n{ffe_line(state['ffe'])}\n\n"
    text += "\n".join(final_lines(ctx)) + "\n\n"
    text += "\n".join(summary_lines(ctx["issues"])) + "\n"
    text += f"\nAuffällige laufende Jobs: {len(watch)}\n" + "".join(f"{line}\n" for line in watch)
    text += f"\nWorker (Heartbeat): {len(workers)}\n" + "".join(f"{line}\n" for line in workers)
    if ctx["issues"]:
        text += f"\nDetails: errors/{name}_errors.txt\n"
    state.update(notes=[], workers=view["workers"], updated_at=now())
    save_state(state)
    path = reports_dir / f"{name}.txt"
    write_new(path, text)
    if ctx["issues"]:
        write_new(error_dir / f"{name}_errors.txt", format_errors(ctx["issues"], when))
    log(f"{kind}-Bericht: {path.name}; {sum(row[0] for row in totals.values())} aktive Clips; "
         f"{len(state['clips'])} Clips in der JSON; {len(ctx['issues'])} Meldungen; {len(watch)} auffällige Jobs; "
         f"Dauer: {perf_counter() - started:.1f} s.")
    return path
