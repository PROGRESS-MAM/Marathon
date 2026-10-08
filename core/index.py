"""Reconcile search hits with the JSON; command update-index."""
# --------- IMPORTS ---------
from collections import defaultdict
from datetime import datetime
from time import perf_counter

from .constants import field_names, index_sections, metadata_changed, problem_categories, tracked_fields
from .console import log
from .util import clip_text, context, details, file_stamp, format_detail, issue, normalize, now, write_lists
from .layout import check_root, final_folder, load_mapping, master_folder, qc_inbox
from .state import add_event, file_entry, keep_notes, load_state, new_clip, save_state
from .naming import find_proxy
from .ffe import apply_ffe, ffe_text, load_ffe_list
from .search import search_clips
from .veritone import intersect, veritone_clip_ids, veritone_token
from .audit import missing_masters


# --------- FUNC ---------
def _classify(clip_id: str, hits: list[dict], dropped: dict[str, tuple[str, str]]) -> tuple[dict | None, dict | None]:
    """Return the usable hit or a problem with kind, reason and optional head/matches for format B."""
    if not hits and clip_id in dropped:
        head, reason = dropped[clip_id]
        return None, {"kind": "veritone", "head": head, "reason": reason}
    if not hits:
        return None, {"kind": "missing", "reason": "Nicht mehr in der Suche gefunden (Metadaten nicht abrufbar oder Kollektion geändert)"}
    if len(hits) > 1:
        matches = [f"Kollektion={hit['collection']}, {field_names['identifier']}={hit['identifier']}, {field_names['title']}={hit['title']}"
                   for hit in sorted(hits, key=lambda hit: hit["collection"].casefold())]
        return None, {"kind": "multi", "head": f"{field_names['clip_id']}={clip_id}", "matches": matches}
    if hits[0]["invalid"]:
        reason, matches = hits[0]["invalid"]
        return None, {"kind": "invalid", "reason": reason, "matches": matches}
    return hits[0], None


def _admit(clips: dict, clip_id: str, hit: dict, ctx: dict) -> None:
    collection, clip, text = hit["collection"], new_clip(clip_id, hit), clip_text(hit)
    places = ((final_folder(collection), "Zielordner"), (qc_inbox(collection), "QC-Eingang"))
    proxy = next(((folder, name, source) for folder, source in places if (name := find_proxy(ctx, folder, clip))), None)
    missing = missing_masters(ctx, collection, clip_id, hit["masters"])
    if proxy is None and missing != [] and hit["restore_problem"]:
        issue(ctx, "skipped", problem_categories["restore"][0], clip_id, f"{text}: {hit['restore_problem']}")
        return
    ready = bool(proxy) and proxy[2] == "Zielordner"
    if missing is not None and not ready:  # Recorded so the folder is deleted once the clip is ready.
        clip["files"]["master"] = {"folder": master_folder(collection, clip_id), "names": list(hit["masters"]),
                                   "source": "Transcode-Eingang", "last_seen_at": now()}
    if proxy:
        clip["files"]["proxy"] = file_entry(*proxy)
    if ready:
        clip.update(ready=True, stage=None, status="bereit")
        add_event(clip, "Aufgenommen – bereits im Zielordner", proxy[1])
    elif proxy:
        clip["stage"] = "qc"
        add_event(clip, f"Aufgenommen – Proxy im {proxy[2]}", proxy[1])
    elif missing == []:
        clip["stage"] = "transcode"
        add_event(clip, "Aufgenommen – Master im Transcode-Eingang", ", ".join(hit["masters"]))
    else:
        if missing:
            issue(ctx, "note", "Master unvollständig im Transcode-Eingang – neuer Restore", clip_id,
                   f"{text}: fehlend {', '.join(missing)}")
        add_event(clip, "Aufgenommen – wartet auf Restore", ", ".join(hit["masters"]))
    clips[clip_id] = clip


def _changes(clip: dict, hit: dict) -> str:
    """Differences between JSON and search; an unknown Veritone-ID on either side is no difference."""
    new = {"collection": hit["collection"], "identifier": hit["identifier"], "title": hit["title"],
           "clip_name_with_extension": hit["clip_name"], "master_files": hit["masters"], "filehashes": hit["hashes"],
           "veritone_id": hit["veritone_id"]}
    return "; ".join(f"{label}: {clip.get(key)!r} → {new[key]!r}" for key, label in tracked_fields.items()
                     if clip.get(key) is not None and new[key] is not None and clip[key] != new[key])


def _fill(clip: dict, hit: dict) -> list[str]:
    """Add fields missing in a known clip (and an empty Veritone-ID) from the search; existing values stay."""
    template = new_clip(clip["clip_id"], hit)
    keys = [key for key in template if key not in clip or (key == "veritone_id" and clip[key] is None and template[key])]
    for key in keys:
        clip[key] = template[key]
    if keys:
        add_event(clip, "Fehlende Felder ergänzt", ", ".join(keys))
    return keys


def _reconcile(state: dict, found: dict[str, list[dict]], ctx: dict, dropped: dict[str, tuple[str, str]] | None = None) -> int:
    """Admit new clips and fill missing fields of known clips; other differences are only reported. Returns filled clips."""
    clips, dropped, filled = state["clips"], dropped or {}, 0
    classified = {clip_id: _classify(clip_id, found.get(clip_id, []), dropped) for clip_id in {*found, *clips, *dropped}}
    groups, sources = defaultdict(list), {}
    for clip_id, (hit, _) in classified.items():
        source = clips.get(clip_id) or hit
        if source:
            sources[clip_id] = source
            groups[(normalize(source["identifier"]), normalize(source["title"]))].append(clip_id)
    for group in (sorted(group, key=int) for group in groups.values() if len(group) > 1):
        first = sources[group[0]]
        problem = {"kind": "duplicate",
                   "head": f"{field_names['identifier']}={first['identifier']}, {field_names['title']}={first['title']}",
                   "matches": [f"Kollektion={sources[clip_id]['collection']}, {field_names['clip_id']}={clip_id}" for clip_id in group]}
        for clip_id in (clip_id for clip_id in group if clip_id not in clips):
            classified[clip_id] = (None, problem)
    for clip_id in sorted(classified, key=int):
        (hit, problem), clip = classified[clip_id], clips.get(clip_id)
        if clip is None and problem is None:
            _admit(clips, clip_id, hit, ctx)
        elif problem:
            section, index = ("deviation", 1) if clip else ("skipped", 0)
            head = problem.get("head") or clip_text(clip or found[clip_id][0])
            issue(ctx, section, problem_categories[problem["kind"]][index], clip_id,
                   format_detail(head, problem.get("reason", ""), problem.get("matches")))
        else:
            filled += bool(_fill(clip, hit))
            if changes := _changes(clip, hit):
                issue(ctx, "deviation", metadata_changed, clip_id, format_detail(clip_text(clip), changes))
    return filled


# --------- COMMAND ---------
def update_index() -> None:
    """Search all collections; admit new clips, report differences for known clips without changing them; FFE match."""
    started = perf_counter()
    log("Index-Aktualisierung gestartet.")
    mapping = load_mapping()
    entries = load_ffe_list()  # Checked before the long search.
    check_root()
    state, ctx = load_state(), context()
    before, token = len(state["clips"]), veritone_token()
    found = search_clips(mapping, ctx)
    found, dropped = intersect(found, veritone_clip_ids(mapping, token, ctx), mapping, ctx)
    filled = _reconcile(state, found, ctx, dropped)
    ffe_counts = apply_ffe(state, entries, ctx)
    index_issues = [item for item in ctx["issues"] if item["section"] in index_sections]
    counts = {section: len({item["key"] for item in index_issues if item["section"] == section}) for section in index_sections}
    when = datetime.now().astimezone()
    error_list, ambiguous_list = write_lists(ctx["issues"], when, file_stamp("index", when), "Index-Fehlerliste")
    state["index"] = {"updated_at": now(), "counts": counts, "error_list": error_list}
    state["ffe"] = {"updated_at": now(), "counts": ffe_counts, "error_list": error_list if ffe_counts["missing"] else None,
                    "ambiguous_list": ambiguous_list}
    keep_notes(state, ctx["issues"])
    state["updated_at"] = now()
    save_state(state)
    log(f"Index aktualisiert: {len(state['clips']) - before} Clips neu aufgenommen, {filled} Clips ergänzt, "
         f"{len(state['clips'])} in der JSON; {counts['skipped']} nicht aufgenommen; {counts['deviation']} Abweichungen; "
         f"{counts['veritone_only']} nur bei Veritone; {counts['veritone_multi']} Veritone-ID uneindeutig"
         f"; {ffe_text(ffe_counts)}{details(error_list, ambiguous_list)}; Dauer: {perf_counter() - started:.1f} s.")
