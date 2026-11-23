import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
toolbox = types.ModuleType("toolbox")
toolbox.tb_write_log = lambda *args, **kwargs: None
toolbox.tb_link_api = lambda *args, **kwargs: None
sys.modules.setdefault("toolbox", toolbox)

from core import ftpcheck, veritone
from core.util import normalize


COLLECTION = "DEFA Spielfilm"
OTHER_COLLECTION = "DEFA Doku"
MAPPING = {"name": COLLECTION, "filters": [], "veritone_filter_ids": ["1"]}
OTHER_MAPPING = {"name": OTHER_COLLECTION, "filters": [], "veritone_filter_ids": ["2"]}


def _clip(clip_id="1", collection=COLLECTION, identifier="X1", title="Film", veritone_id="asset-1"):
    return {"clip_id": clip_id, "collection": collection, "identifier": identifier,
            "title": title, "veritone_id": veritone_id}


def _hit(clip_id="1", collection=COLLECTION, identifier="X1", title="Film", invalid=None):
    return {"collection": collection, "clip_id": clip_id, "invalid": invalid, "identifier": identifier,
            "title": title, "clip_name": "x.mxf", "identifiers": [identifier]}


def _veritone(*, collection=COLLECTION, identifier="X1", asset_ids=("asset-1",)):
    return {collection: {normalize(identifier): (identifier, list(asset_ids))}}


def _install(monkeypatch, found, veritone_ids, mapping=None):
    mapping = mapping or [MAPPING]
    monkeypatch.setattr(ftpcheck, "search_clips", lambda entries, ctx: found)
    monkeypatch.setattr(ftpcheck, "veritone_token", lambda: "test-token")
    monkeypatch.setattr(ftpcheck, "veritone_clip_ids", lambda entries, token, ctx: veritone_ids)
    monkeypatch.setattr(veritone, "log", lambda *args, **kwargs: None)
    return mapping


def test_unique_passes(monkeypatch):
    _install(monkeypatch, {"1": [_hit()]}, _veritone())
    assert ftpcheck.final_check([_clip()], [MAPPING]) == {"1": None}


def test_only_collections_of_clips_searched(monkeypatch):
    searched = []
    _install(monkeypatch, {"1": [_hit()]}, _veritone(), [MAPPING, OTHER_MAPPING])
    monkeypatch.setattr(ftpcheck, "search_clips", lambda entries, ctx: searched.append(entries) or {"1": [_hit()]})
    veritone_calls = []
    monkeypatch.setattr(ftpcheck, "veritone_clip_ids",
                        lambda entries, token, ctx: veritone_calls.append(entries) or _veritone())
    assert ftpcheck.final_check([_clip()], [MAPPING, OTHER_MAPPING]) == {"1": None}
    assert searched == [[MAPPING]]
    assert veritone_calls == [[MAPPING]]


def test_not_mapped_no_search(monkeypatch):
    monkeypatch.setattr(ftpcheck, "search_clips", lambda *args: (_ for _ in ()).throw(AssertionError("searched")))
    monkeypatch.setattr(ftpcheck, "veritone_clip_ids", lambda *args: (_ for _ in ()).throw(AssertionError("queried")))
    assert ftpcheck.final_check([_clip(collection="Unmapped")], [MAPPING]) == {
        "1": "Kollektion nicht im Kollektionsmapping"}


def test_multi_collection(monkeypatch):
    mapping = [MAPPING, OTHER_MAPPING]
    found = {"1": [_hit(), _hit(collection=OTHER_COLLECTION)]}
    ids = {**_veritone(), **_veritone(collection=OTHER_COLLECTION)}
    _install(monkeypatch, found, ids, mapping)
    assert ftpcheck.final_check([_clip()], mapping)["1"] == \
        "Clip-ID in mehreren Kollektionen: DEFA Doku, DEFA Spielfilm"


def test_not_at_veritone(monkeypatch):
    _install(monkeypatch, {"1": [_hit()]}, {COLLECTION: {}})
    reason = ftpcheck.final_check([_clip()], [MAPPING])["1"]
    assert reason.startswith("In der EditShare-Suche, aber nicht bei Veritone")


def test_not_in_search(monkeypatch):
    _install(monkeypatch, {}, _veritone())
    assert ftpcheck.final_check([_clip()], [MAPPING]) == {"1": "Nicht in der EditShare-Suche gefunden"}


def test_invalid(monkeypatch):
    _install(monkeypatch, {"1": [_hit(invalid=("Widersprüchlich", ["x"]))]}, _veritone())
    assert ftpcheck.final_check([_clip()], [MAPPING])["1"] == \
        "Metadaten in EditShare unvollständig oder widersprüchlich: Widersprüchlich"


def test_title_changed(monkeypatch):
    _install(monkeypatch, {"1": [_hit(title="Changed") ]}, _veritone())
    assert ftpcheck.final_check([_clip()], [MAPPING])["1"] == \
        "014 Title Original in EditShare geändert: Film → Changed"


def test_identifier_twice(monkeypatch):
    found = {"1": [_hit(clip_id="1")], "2": [_hit(clip_id="2")]}
    _install(monkeypatch, found, _veritone())
    clips = [_clip(clip_id="1"), _clip(clip_id="2")]
    expected = "001 Identifier mehrfach in EditShare: clip_id 1, 2"
    assert ftpcheck.final_check(clips, [MAPPING]) == {"1": expected, "2": expected}


def test_barcode_multiple_assets(monkeypatch):
    _install(monkeypatch, {"1": [_hit()]}, _veritone(asset_ids=("asset-1", "asset-2")))
    assert ftpcheck.final_check([_clip(veritone_id=None)], [MAPPING])["1"] == "Barcode mehrfach bei Veritone"


def test_veritone_id_changed(monkeypatch):
    _install(monkeypatch, {"1": [_hit()]}, _veritone(asset_ids=("asset-new",)))
    assert ftpcheck.final_check([_clip()], [MAPPING])["1"] == \
        "Veritone-ID geändert: asset-1 → asset-new"


def test_search_error_propagates(monkeypatch):
    monkeypatch.setattr(ftpcheck, "search_clips", lambda *args: (_ for _ in ()).throw(RuntimeError("search failed")))
    monkeypatch.setattr(ftpcheck, "veritone_token", lambda: "test-token")
    monkeypatch.setattr(ftpcheck, "veritone_clip_ids", lambda *args: {})
    with pytest.raises(RuntimeError, match="search failed"):
        ftpcheck.final_check([_clip()], [MAPPING])
