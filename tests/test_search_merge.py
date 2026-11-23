import sys, types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
toolbox = types.ModuleType("toolbox")
toolbox.tb_write_log = lambda *a, **k: None
toolbox.tb_link_api = lambda *a, **k: None
sys.modules.setdefault("toolbox", toolbox)

from core import search
from core.util import split_values


def _row(**fields):
    values = {"clip_id": ["1"], "identifier": ["X1"], "title": ["A"], "clip_name": ["n.mxf"],
              "status_flags": [], "video": [], "audio": [], "data": []}
    values.update(fields)
    return values


def _merge(*rows):
    return search._merge_hit({"collection": "C", "clip_id": "1", "invalid": None, "rows": list(rows)})


def test_multi_title_joined():
    hit = _merge(_row(title=split_values("Unruhe; Wopyt")))
    assert hit["invalid"] is None
    assert hit["title"] == "Unruhe; Wopyt"


def test_multi_clip_name_joined():
    hit = _merge(_row(title=["Die Schmerzen der Lausitz; Žałosći nam Łužyca"],
                      clip_name=["Die Schmerzen der Lausitz", "Žałosći nam Łužyca.mxf"]))
    assert hit["invalid"] is None
    assert hit["clip_name"] == "Die Schmerzen der Lausitz; Žałosći nam Łužyca.mxf"


def test_three_parts_joined():
    hit = _merge(_row(title=["Ford Saf", "Poissy", "France"]))
    assert hit["title"] == "Ford Saf; Poissy; France"


def test_single_title_unchanged():
    hit = _merge(_row(title=["Harvest / State visit of Mussolini in Berlin"]))
    assert hit["invalid"] is None
    assert hit["title"] == "Harvest / State visit of Mussolini in Berlin"


def test_empty_title_invalid():
    hit = _merge(_row(title=[]))
    assert hit["invalid"] == ("014 Title Original: 0 Werte", None)


def test_multi_identifier_invalid():
    hit = _merge(_row(identifier=["X1", "X2"]))
    assert hit["invalid"] == ("001 Identifier: 2 Werte", None)


def test_rows_conflict_after_join():
    hit = _merge(_row(title=["A", "B"]), _row(title=["A", "C"]))
    assert hit["invalid"] == ("Widersprüchlich", ["014 Title Original=A; B", "014 Title Original=A; C"])


def test_rows_equal_after_join():
    hit = _merge(_row(title=["A", "B"]), _row(title=["A", "B"]))
    assert hit["invalid"] is None
    assert hit["title"] == "A; B"
