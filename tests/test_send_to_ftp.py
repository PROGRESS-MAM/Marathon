import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
toolbox = types.ModuleType("toolbox")
toolbox.tb_write_log = lambda *args, **kwargs: None
toolbox.tb_link_api = lambda *args, **kwargs: None
sys.modules.setdefault("toolbox", toolbox)

from core import ftp
from core.config import cfg
from core.state import new_clip


PROXY_NAME = "1234567_98765_10Mbit.mp4"
FTP_NAME = "DEFA14097__Rosa.mp4"
PAYLOAD = b"proxy contents"


def _make_clip(clip_id="98765"):
    hit = {
        "collection": "DEFA Spielfilm", "identifier": "DEFA14097", "title": "Rosa",
        "veritone_id": "1234567", "clip_name": "Rosa.mxf", "masters": [],
        "master_files": [], "lto_tapes": [], "master_size": 0,
    }
    clip = new_clip(clip_id, hit)
    clip.update(ready=True, stage=None, status="bereit")
    clip["files"]["proxy"] = {
        "folder": "DEFA", "name": PROXY_NAME, "source": "QC", "last_seen_at": "x",
    }
    return clip


def _setup(monkeypatch, tmp_path):
    root_path = tmp_path / "share"
    final_dir = root_path / "DEFA"
    ftp_dir = tmp_path / "ftp"
    error_dir = tmp_path / "errors"
    final_dir.mkdir(parents=True)
    ftp_dir.mkdir()
    error_dir.mkdir()
    for key, value in {
        "root_path": str(root_path), "defa_dir": "DEFA", "work_dir": ".marathon",
        "defa_marker": "DEFA", "proxy_name": "{veritone_id}_{clip_id}_10Mbit.mp4",
        "ftp_dir": str(ftp_dir),
    }.items():
        monkeypatch.setitem(cfg, key, value)

    clip = _make_clip()
    source = final_dir / PROXY_NAME
    source.write_bytes(PAYLOAD)
    state = {"clips": {clip["clip_id"]: clip}, "cleanup": {}, "updated_at": None}
    state_file = tmp_path / "state.json"
    state_file.touch()
    saves, logs = [], []
    monkeypatch.setattr(ftp, "state_path", state_file)
    monkeypatch.setattr(ftp, "load_state", lambda: state)
    monkeypatch.setattr(ftp, "save_state", lambda value: saves.append(value))
    monkeypatch.setattr(ftp, "check_root", lambda: None)
    monkeypatch.setattr(ftp, "load_mapping", lambda: [])
    monkeypatch.setattr(ftp, "final_check", lambda clips, mapping: {item["clip_id"]: None for item in clips})
    monkeypatch.setattr(ftp, "error_dir", error_dir)
    monkeypatch.setattr(ftp, "log", logs.append)
    return root_path, final_dir, ftp_dir, error_dir, clip, state, source, saves, logs


def test_releases_passed_clip(monkeypatch, tmp_path):
    _, _, ftp_dir, _, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    source_before = source.read_bytes()
    monkeypatch.setattr(ftp, "scan", lambda relative: {})

    ftp.send_to_ftp()

    assert clip["ftp"]["requested_at"]
    assert clip["ftp"]["error"] is None
    assert clip["ftp"]["attempts"] == 0
    assert source.read_bytes() == source_before
    assert list(ftp_dir.iterdir()) == []
    assert clip["history"][-1]["event"] == "Für FTP freigegeben"
    assert clip["history"][-1]["detail"] == FTP_NAME


def test_check_failed_sets_error_and_list(monkeypatch, tmp_path):
    _, _, ftp_dir, error_dir, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(ftp, "final_check", lambda clips, mapping: {"98765": "Prüfgrund"})

    ftp.send_to_ftp()

    assert clip["ftp"]["error"]["category"] == "Letzte Prüfung nicht bestanden"
    assert clip["ftp"]["error"]["detail"] == "Prüfgrund"
    assert clip["ftp"]["error"]["at"]
    assert clip["ftp"]["requested_at"] is None
    assert source.is_file() and list(ftp_dir.iterdir()) == []
    reports = list(error_dir.glob("send-to-ftp_*_errors.txt"))
    assert len(reports) == 1 and "Prüfgrund" in reports[0].read_text(encoding="utf-8")


def test_rereleases_clip_with_error(monkeypatch, tmp_path):
    *_, clip, _, _, _, _ = _setup(monkeypatch, tmp_path)
    clip["ftp"] = {"error": {"category": "old", "detail": "old error", "at": "yesterday"},
                     "requested_at": None, "job": None, "copied_at": None, "attempts": 4}
    monkeypatch.setattr(ftp, "scan", lambda relative: {})

    ftp.send_to_ftp()

    assert clip["ftp"]["requested_at"]
    assert clip["ftp"]["error"] is None
    assert clip["ftp"]["attempts"] == 0


def test_skips_requested_and_running(monkeypatch, tmp_path):
    *_, clip, state, _, _, logs = _setup(monkeypatch, tmp_path)
    clip["ftp"] = {"requested_at": "requested", "job": None, "copied_at": None}
    running = _make_clip("98766")
    running["ftp"] = {"requested_at": None, "job": "job-1", "copied_at": None}
    state["clips"][running["clip_id"]] = running
    available = _make_clip("98767")
    state["clips"][available["clip_id"]] = available
    monkeypatch.setattr(ftp, "final_check", lambda clips, mapping: {item["clip_id"]: None for item in clips})
    monkeypatch.setattr(ftp, "scan", lambda relative: {})

    ftp.send_to_ftp()

    assert any("2 bereits freigegeben oder in Arbeit" in line for line in logs)


def test_skips_copied(monkeypatch, tmp_path):
    *_, clip, _, _, _, _ = _setup(monkeypatch, tmp_path)
    clip["ftp"] = {"requested_at": None, "job": None, "copied_at": "copied"}
    monkeypatch.setattr(ftp, "final_check", lambda *args: pytest.fail("copied clip must not be checked"))
    monkeypatch.setattr(ftp, "scan", lambda *args: pytest.fail("copied clip must not be searched"))

    ftp.send_to_ftp()


def test_proxy_name_mismatch(monkeypatch, tmp_path):
    _, _, _, _, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    clip["files"]["proxy"]["name"] = "wrong.mp4"
    source.rename(source.with_name("wrong.mp4"))

    ftp.send_to_ftp()

    assert clip["ftp"]["error"]["category"] == "Proxy-Name weicht von proxy_name ab"
    assert clip["ftp"]["requested_at"] is None


def test_target_name_conflict(monkeypatch, tmp_path):
    _, final_dir, ftp_dir, _, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    conflict = final_dir / FTP_NAME.swapcase()
    conflict.write_bytes(b"keep this")

    ftp.send_to_ftp()

    assert clip["ftp"]["error"]["category"] == "Namenskonflikt im Zielordner"
    assert source.is_file() and conflict.read_bytes() == b"keep this"
    assert list(ftp_dir.iterdir()) == []


def test_no_candidates_no_search(monkeypatch, tmp_path):
    *_, clip, _, _, saves, logs = _setup(monkeypatch, tmp_path)
    clip["active"] = False
    monkeypatch.setattr(ftp, "load_mapping", lambda: pytest.fail("mapping must not be loaded"))
    monkeypatch.setattr(ftp, "final_check", lambda *args: pytest.fail("final check must not run"))
    monkeypatch.setattr(ftp, "scan", lambda *args: pytest.fail("folder scan must not run"))

    ftp.send_to_ftp()

    assert logs[-1] == "send-to-ftp: keine bereiten Clips freizugeben."
    assert saves == []


def test_no_ftp_dir_raises(monkeypatch, tmp_path):
    _, _, ftp_dir, _, _, _, _, _, _ = _setup(monkeypatch, tmp_path)
    ftp_dir.rmdir()

    with pytest.raises(FileNotFoundError, match="FTP-Pfad nicht erreichbar"):
        ftp.send_to_ftp()


def test_final_check_exception_propagates_unchanged(monkeypatch, tmp_path):
    *_, clip, state, source, saves, _ = _setup(monkeypatch, tmp_path)
    before = repr(state)
    monkeypatch.setattr(ftp, "final_check", lambda *args: (_ for _ in ()).throw(RuntimeError("check failed")))

    with pytest.raises(RuntimeError, match="check failed"):
        ftp.send_to_ftp()

    assert repr(state) == before
    assert source.read_bytes() == PAYLOAD
    assert saves == []
