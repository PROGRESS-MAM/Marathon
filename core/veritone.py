"""Veritone query and intersection with the EditShare search."""
# --------- IMPORTS ---------
import json
from collections import defaultdict
from time import perf_counter, sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .constants import (
    barcode_missing, token_key, veritone_ambiguous, veritone_page_size, veritone_passes, veritone_placeholder,
    veritone_settle_seconds, veritone_timeout, veritone_unmatched)
from .config import cfg
from .console import log, search_progress
from .util import clip_text, format_detail, issue, normalize
from .layout import res


# --------- FUNC ---------
def veritone_token() -> str:
    """Token from the line vt_api_token=<token> in token_file (.env)."""
    for line in res("token_file").read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == token_key and value.strip().strip("\"'"):
            return value.strip().strip("\"'")
    raise ValueError(f"{cfg['token_file']}: keine Zeile {token_key}=<Token> gefunden.")


def _veritone_get(path: str, token: str, params: dict):
    url = f"{cfg['base_url'].rstrip('/')}{path}?{urlencode({**params, 'api_key': token})}"
    request = Request(url, headers={"Accept": "application/json"})
    # Errors are raised without the URL, it contains the token.
    try:
        with urlopen(request, timeout=veritone_timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"Veritone antwortet mit HTTP {exc.code} ({exc.reason}) auf {path}; Zustand unverändert.") from None
    except (URLError, OSError, ValueError) as exc:
        raise RuntimeError(f"Veritone nicht erreichbar oder Antwort ungültig ({path}): {exc}; Zustand unverändert.") from None


def _scalars(value) -> list[str]:
    if isinstance(value, list):
        return [text for part in value for text in _scalars(part)]
    if isinstance(value, str) or type(value) is int:
        return [str(value).strip()] if str(value).strip() else []
    return []


def _item_values(item, name: str) -> list[str]:
    """All values of a field anywhere in a Veritone item, as key or as name/value pair."""
    if isinstance(item, list):
        return [text for part in item for text in _item_values(part, name)]
    if not isinstance(item, dict):
        return []
    found = _scalars(item["value"]) if item.get("name") == name and "value" in item else []
    return found + [text for key, value in item.items() for text in (_scalars(value) if key == name else _item_values(value, name))]


def _veritone_params(entry: dict) -> dict:
    return {"q": "", "filterIds": ",".join(entry["veritone_filter_ids"]), "n": veritone_page_size, "i": 0}


def _veritone_pages(entry: dict, token: str, ids: dict) -> tuple[int, int, int]:
    """Read all search pages once into ids; returns totalCount, hits read and distinct assets of this pass."""
    name, read, seen, params = entry["name"], 0, set(), _veritone_params(entry)
    while True:
        page = _veritone_get("/v1/search", token, params)
        if not isinstance(page, dict) or not isinstance(page.get("items"), list) or type(page.get("totalCount")) is not int:
            raise RuntimeError(f"Unerwartete Veritone-Antwort auf die Suche für {name!r}; Zustand unverändert.")
        for item in page["items"]:
            asset_id = item.get("assetId") if isinstance(item, dict) else None
            if asset_id is None:
                raise RuntimeError(f"Veritone-Treffer ohne assetId in {name!r}; Zustand unverändert.")
            seen.add(str(asset_id))
            ids.setdefault(str(asset_id), None)
        read += len(page["items"])
        search_progress(f"Veritone {name!r}: lade Suche {len(ids)}/{page['totalCount']}")
        pages = -(-page["totalCount"] // veritone_page_size)  # Upper bound, so a wrong hasNextPage cannot loop forever.
        if not page["items"] or not page.get("hasNextPage") or params["i"] + 1 >= pages:
            return page["totalCount"], read, len(seen)
        params["i"] += 1


def _veritone_assets(entry: dict, token: str) -> tuple[list[str], int]:
    """Asset IDs of one collection and the passes needed; raises unless totalCount assets were found in time."""
    name, ids = entry["name"], {}
    _veritone_get("/v1/search", token, {**_veritone_params(entry), "n": 1})  # Only triggers the search.
    search_progress(f"Veritone {name!r}: Suche ausgelöst, lade Ergebnisse in {veritone_settle_seconds} s")
    sleep(veritone_settle_seconds)
    for number in range(1, veritone_passes + 1):
        total, read, distinct = _veritone_pages(entry, token, ids)
        if len(ids) >= total:
            return list(ids), number
        log(f"Veritone-Suche {name!r}, Durchlauf {number}/{veritone_passes}: {read} Treffer gelesen, davon {read - distinct} "
             f"doppelt; bisher {len(ids)} von {total} Assets.")
    raise RuntimeError(f"Veritone-Suche für {name!r} unvollständig: {len(ids)} von {total} Assets nach {veritone_passes} "
                       f"Durchläufen; Zustand unverändert.")


def _veritone_barcodes(name: str, asset_ids: list[str], token: str, ctx: dict) -> tuple[dict[str, tuple[str, list[str]]], int, int]:
    """Barcodes of one collection as {normalized: (barcode, [assetIds])}, assets without one (reported) and placeholders.

    Placeholder assets are ignored completely, like placeholders in the EditShare search.
    """
    field, codec_field = cfg["field_clip_id"], veritone_placeholder[0]
    barcodes, missing, placeholders = {}, 0, 0
    for start in range(0, len(asset_ids), veritone_page_size):
        batch = asset_ids[start:start + veritone_page_size]
        data = _veritone_get("/v1/clip/byIds", token, {"ids": ",".join(batch), "fields": f"{field},{codec_field}"})
        clips = data.get("list") if isinstance(data, dict) else None
        if not isinstance(clips, list):
            raise RuntimeError(f"Unerwartete Veritone-Antwort auf byIds für {name!r}; Zustand unverändert.")
        values, codecs = defaultdict(list), defaultdict(set)
        for clip in (clip for clip in clips if isinstance(clip, dict)):
            values[str(clip.get("id"))] += _item_values(clip, field)
            codecs[str(clip.get("id"))] |= {value.casefold() for value in _item_values(clip, codec_field)}
        for asset_id in batch:
            if veritone_placeholder[1] in codecs[asset_id]:
                placeholders += 1
                continue
            if not values[asset_id]:
                missing += 1
                issue(ctx, "veritone_only", barcode_missing, f"{name}#{asset_id}", f"Kollektion={name}, assetId={asset_id}")
            for barcode in values[asset_id]:
                assets = barcodes.setdefault(normalize(barcode), (barcode, []))[1]
                if asset_id not in assets:
                    assets.append(asset_id)
        search_progress(f"Veritone {name!r}: lade Barcodes {start + len(batch)}/{len(asset_ids)}")
    if len(asset_ids) > placeholders and not barcodes:
        raise RuntimeError(f"Veritone liefert in {name!r} kein Feld {field!r}; [veritone] field_clip_id prüfen. "
                           f"Zustand unverändert.")
    return barcodes, missing, placeholders


def veritone_clip_ids(mapping: list[dict], token: str, ctx: dict) -> dict[str, dict[str, tuple[str, list[str]]]]:
    """Barcodes per collection: {collection: {normalized barcode: (barcode, [assetIds])}}."""
    log(f"Veritone-Abfrage gestartet: {len(mapping)} Kollektionen.")
    result = {}
    for entry in mapping:
        name, started = entry["name"], perf_counter()
        assets, passes = _veritone_assets(entry, token)
        result[name], missing, placeholders = _veritone_barcodes(name, assets, token, ctx)
        log(f"Veritone-Abfrage abgeschlossen: {name!r}: {len(assets)} Assets ({passes} Durchl.), {placeholders} Platzhalter, "
             f"{len(result[name])} Barcodes{f', {missing} ohne Barcode' if missing else ''}; {perf_counter() - started:.1f} s.")
    return result


def intersect(found: dict[str, list[dict]], veritone: dict[str, dict[str, tuple[str, list[str]]]], mapping: list[dict],
               ctx: dict) -> tuple[dict[str, list[dict]], dict[str, tuple[str, str]]]:
    """Keep hits whose 001 Identifier is a barcode of the same collection at Veritone.

    Kept hits get the assetId as veritone_id (None if the barcode has several assets, reported).
    Returns the kept hits and {Clip_ID: (text, reason)} for clips without any match; Veritone-only barcodes are reported.
    """
    kept, dropped, counts = {}, {}, defaultdict(lambda: [0, 0])  # collection: [only EditShare, both]
    seen = defaultdict(set)  # collection: normalized identifiers of all EditShare hits
    for clip_id, hits in found.items():
        matched, elsewhere = [], set()
        for hit in hits:
            keys, barcodes = {normalize(value) for value in hit["identifiers"]}, veritone[hit["collection"]]
            seen[hit["collection"]] |= keys
            assets = list(dict.fromkeys(asset for key in keys & barcodes.keys() for asset in barcodes[key][1]))
            counts[hit["collection"]][bool(assets)] += 1
            if assets:
                hit["veritone_id"] = assets[0] if len(assets) == 1 else None
                if len(assets) > 1:
                    issue(ctx, "veritone_multi", veritone_ambiguous, clip_id,
                           format_detail(clip_text(hit), matches=[f"assetId={asset}" for asset in assets]))
                matched.append(hit)
            else:
                elsewhere |= {name for name, barcodes in veritone.items() if name != hit["collection"] and barcodes.keys() & keys}
        if matched:
            kept[clip_id] = matched
            continue
        others = ", ".join(sorted(elsewhere, key=str.casefold))
        dropped[clip_id] = (clip_text(hits[0]), "In der EditShare-Suche, aber nicht bei Veritone in derselben Kollektion"
                            + (f"; bei Veritone in: {others}" if others else ""))
    for entry in mapping:
        name = entry["name"]
        only_veritone = [item for key, item in veritone[name].items() if key not in seen[name]]
        for barcode, assets in only_veritone:
            for asset_id in assets:
                issue(ctx, "veritone_only", veritone_unmatched, f"{name}#{asset_id}",
                       f"Kollektion={name}, Barcode={barcode}, assetId={asset_id}")
        only, both = counts[name]
        log(f"Abgleich {name!r}: EditShare {only + both}, Veritone {len(veritone[name])}, Schnittmenge {both}; "
             f"nur EditShare {only}, nur Veritone {len(only_veritone)}.")
    return kept, dropped
