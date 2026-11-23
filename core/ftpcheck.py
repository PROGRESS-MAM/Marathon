"""Final EditShare and Veritone check for clips prepared for FTP transfer."""
# --------- IMPORTS ---------
from collections import defaultdict

from .search import search_clips
from .veritone import intersect, veritone_clip_ids, veritone_token
from .util import context, normalize


# --------- FUNC ---------
def final_check(clips: list[dict], mapping: list[dict]) -> dict[str, str | None]:
    """Search EditShare and Veritone for the collections of clips; {clip_id: None if the clip is unique in both, else the reason}."""
    names = {clip["collection"] for clip in clips}
    entries = [entry for entry in mapping if entry["name"] in names]
    mapped_names = {entry["name"] for entry in entries}
    if not entries:
        return {clip["clip_id"]: "Kollektion nicht im Kollektionsmapping" for clip in clips}

    ctx = context()
    found = search_clips(entries, ctx)
    veritone = veritone_clip_ids(entries, veritone_token(), ctx)
    owners = defaultdict(set)
    for clip_id, hits in found.items():
        for hit in hits:
            for value in hit["identifiers"]:
                owners[(hit["collection"], normalize(value))].add(clip_id)

    kept, dropped = intersect(found, veritone, entries, ctx)
    results = {}
    for clip in clips:
        clip_id = clip["clip_id"]
        all_hits, hits = found.get(clip_id, []), kept.get(clip_id, [])
        reason = None
        if clip["collection"] not in mapped_names:
            reason = "Kollektion nicht im Kollektionsmapping"
        elif len(all_hits) > 1:
            reason = "Clip-ID in mehreren Kollektionen: " + ", ".join(sorted(hit["collection"] for hit in all_hits))
        elif not hits and clip_id in dropped:
            reason = dropped[clip_id][1]
        elif not hits:
            reason = "Nicht in der EditShare-Suche gefunden"
        elif hits[0]["invalid"]:
            reason = "Metadaten in EditShare unvollständig oder widersprüchlich: " + hits[0]["invalid"][0]
        elif hits[0]["collection"] != clip["collection"]:
            reason = f"Kollektion in EditShare geändert: {clip['collection']} → {hits[0]['collection']}"
        elif normalize(hits[0]["identifier"]) != normalize(clip["identifier"]):
            reason = f"001 Identifier in EditShare geändert: {clip['identifier']} → {hits[0]['identifier']}"
        elif normalize(hits[0]["title"]) != normalize(clip["title"]):
            reason = f"014 Title Original in EditShare geändert: {clip['title']} → {hits[0]['title']}"
        elif len(ids := owners[(clip["collection"], normalize(clip["identifier"]))]) > 1:
            reason = "001 Identifier mehrfach in EditShare: clip_id " + ", ".join(sorted(ids, key=int))
        elif hits[0]["veritone_id"] is None:
            reason = "Barcode mehrfach bei Veritone"
        elif hits[0]["veritone_id"] != clip["veritone_id"]:
            reason = f"Veritone-ID geändert: {clip['veritone_id']} → {hits[0]['veritone_id']}"
        results[clip_id] = reason
    return results
