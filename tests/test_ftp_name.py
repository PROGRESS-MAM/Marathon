import sys, types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
toolbox = types.ModuleType("toolbox")
toolbox.tb_write_log = lambda *a, **k: None
toolbox.tb_link_api = lambda *a, **k: None
sys.modules.setdefault("toolbox", toolbox)

from core.config import config_schema, cfg
from core.constants import commands_help, ftp_sections
from core.naming import ftp_name


def _clip(identifier, title):
    return {"identifier": identifier, "title": title}


def test_ftp_name_basic(monkeypatch):
    monkeypatch.setitem(cfg, "proxy_name", "{veritone_id}_{clip_id}_10Mbit.mp4")
    assert ftp_name(_clip("DEFA14097", "Rosa Luxemburg - Stationen ihres Lebens")) == \
        "DEFA14097__Rosa Luxemburg - Stationen ihres Lebens.mp4"


def test_ftp_name_invalid_chars(monkeypatch):
    monkeypatch.setitem(cfg, "proxy_name", "{veritone_id}_{clip_id}_10Mbit.mp4")
    assert ftp_name(_clip("DEFA1", 'Wer? Wo: "Hier"/Dort')) == "DEFA1__Wer_ Wo_ _Hier__Dort.mp4"


def test_ftp_name_strip_and_empty(monkeypatch):
    monkeypatch.setitem(cfg, "proxy_name", "{veritone_id}_{clip_id}_10Mbit.mp4")
    assert ftp_name(_clip(" DEFA2 ", " Titel ")) == "DEFA2__Titel.mp4"
    assert ftp_name(_clip("DEFA2", "  ")) is None
    assert ftp_name(_clip("", "Titel")) is None


def test_ftp_name_semicolon(monkeypatch):
    monkeypatch.setitem(cfg, "proxy_name", "{veritone_id}_{clip_id}_10Mbit.mp4")
    assert ftp_name(_clip("DEFA3", "Unruhe; Wopyt")) == "DEFA3__Unruhe; Wopyt.mp4"


def test_schema_and_command():
    assert config_schema["ftp"] == {"ftp_dir": "text"}
    assert list(config_schema).index("ftp") == list(config_schema).index("ingest") + 1
    assert commands_help["send-to-ftp"] == (
        "Bereite Clips nach letzter Prüfung (EditShare ∩ Veritone) für den FTP-Worker freigeben; "
        "Kopie, Umbenennen und EditShare-Feld in der Job-Schleife (nur manuell)"
    )
    assert list(commands_help).index("send-to-ftp") == list(commands_help).index("ingest-proxy") + 1
    assert ftp_sections == {"ftp_error": "Nicht gesendet (Fehler)"}
