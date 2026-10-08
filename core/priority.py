"""Priority list."""
# --------- IMPORTS ---------
from .constants import stage_labels, stages
from .console import log
from .util import issue
from .layout import res


# --------- FUNC ---------
def _write_priority_template(mapping: list[dict]) -> None:
    lines = ["# Marathon – Prioliste",
             "# Je Abschnitt eine Kollektion pro Zeile; oben = höchste Priorität.",
             "# Nicht aufgeführte Kollektionen folgen in der Reihenfolge von collections.json.",
             "# Verfügbare Kollektionen:", *(f"#   {entry['name']}" for entry in mapping), ""]
    for stage in stages:
        lines += [f"[{stage_labels[stage]}]", ""]
    res("priority_file").write_text("\n".join(lines), encoding="utf-8")


def _read_priority(mapping: list[dict]) -> dict[str, list[str]]:
    names = {entry["name"].casefold(): entry["name"] for entry in mapping}
    sections = {stage_labels[stage].casefold(): stage for stage in stages}
    result, current = {stage: [] for stage in stages}, None
    for number, raw in enumerate(res("priority_file").read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = sections.get(line[1:-1].strip().casefold())
            if current is None:
                allowed = ", ".join(f"[{label}]" for label in stage_labels.values())
                raise ValueError(f"Zeile {number}: unbekannter Abschnitt {line}; erlaubt: {allowed}.")
            continue
        name = names.get(line.casefold())
        if current is None or name is None or name in result[current]:
            reason = ("steht vor dem ersten Abschnitt" if current is None else
                      "ist keine Kollektion aus collections.json" if name is None else "steht doppelt im Abschnitt")
            raise ValueError(f"Zeile {number}: {line!r} {reason}.")
        result[current].append(name)
    return result


def priority(mapping: list[dict], state: dict, ctx: dict) -> dict[str, list[str]]:
    """Collection order per stage: priority list first, then mapping order; invalid list keeps the last valid one."""
    if not res("priority_file").exists():
        _write_priority_template(mapping)
        log(f"Prioliste angelegt: {res('priority_file')}")
    try:
        explicit = _read_priority(mapping)
        state["priority"] = explicit
    except (OSError, UnicodeError, ValueError) as exc:
        known = {entry["name"] for entry in mapping}
        stored = state.get("priority") or {}
        explicit = {stage: [name for name in stored.get(stage, []) if name in known] for stage in stages}
        issue(ctx, "note", "Prioliste ungültig – letzte gültige Reihenfolge gilt", "priority", str(exc))
    order = [entry["name"] for entry in mapping]
    return {stage: [*explicit[stage], *(name for name in order if name not in explicit[stage])] for stage in stages}
