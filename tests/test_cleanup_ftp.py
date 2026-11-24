import sys, types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
toolbox = types.ModuleType("toolbox")
toolbox.tb_write_log = lambda *a, **k: None
toolbox.tb_link_api = lambda *a, **k: None
sys.modules.setdefault("toolbox", toolbox)

from core import cleanup, config, state as state_module


def _state(tmp_path, monkeypatch, ftp=None):
    for key, value in {
        "root_path": str(tmp_path),
        "defa_dir": "DEFA",
        "work_dir": ".marathon",
        "defa_marker": "DEFA",
        "proxy_name": "{veritone_id}_{clip_id}_10Mbit.mp4",
    }.items():
        monkeypatch.setitem(config.cfg, key, value)
    hit = {
        "collection": "DEFA Spielfilm",
        "identifier": "DEFA14097",
        "veritone_id": "1234567",
        "title": "Rosa",
        "clip_name": "r.mxf",
        "masters": [{"file": "a.mxf", "flow_hash": "2:ab", "size": 1, "tapes": ["T1"]}],
        "master_files": ["a.mxf"],
        "lto_tapes": ["T1"],
        "master_size": 1,
    }
    clip = state_module.new_clip("98765", hit)
    if ftp is not None:
        clip["ftp"] = ftp
    return {"clips": {"98765": clip}, "restore": {"counter": 0, "jobs": {}}, "workers": {}, "notes": []}, clip


def _ftp_entry():
    return {
        "target": "x",
        "size": 1,
        "old_name": "1234567_98765_10Mbit.mp4",
        "new_name": "DEFA14097__Rosa.mp4",
        "copied_at": "2026-11-23T10:00:00+01:00",
        "renamed_at": "2026-11-23T10:00:01+01:00",
    }


def test_rebuild_keeps_renamed_proxy(tmp_path, monkeypatch):
    ftp = _ftp_entry()
    state, clip = _state(tmp_path, monkeypatch, ftp)
    (tmp_path / "DEFA").mkdir()
    (tmp_path / "DEFA" / "DEFA14097__Rosa.mp4").write_bytes(b"x")

    cleanup._rebuild_process_state(state)

    assert clip["ready"] is True
    assert clip["stage"] is None
    assert clip["files"]["proxy"]["folder"] == "DEFA"
    assert clip["files"]["proxy"]["name"] == "DEFA14097__Rosa.mp4"
    assert clip["ftp"] == ftp


def test_rebuild_unsent_clip(tmp_path, monkeypatch):
    state, clip = _state(tmp_path, monkeypatch)
    (tmp_path / "DEFA").mkdir()
    (tmp_path / "DEFA" / "1234567_98765_10Mbit.mp4").write_bytes(b"x")

    cleanup._rebuild_process_state(state)

    assert clip["ready"] is True
    assert clip["files"]["proxy"]["name"] == "1234567_98765_10Mbit.mp4"


def test_rebuild_renamed_missing_falls_back(tmp_path, monkeypatch):
    state, clip = _state(tmp_path, monkeypatch, _ftp_entry())
    (tmp_path / "DEFA").mkdir()
    (tmp_path / "DEFA" / "1234567_98765_10Mbit.mp4").write_bytes(b"x")

    cleanup._rebuild_process_state(state)

    assert clip["ready"] is True
    assert clip["files"]["proxy"]["name"] == "1234567_98765_10Mbit.mp4"


def test_rebuild_resets_ftp_job(tmp_path, monkeypatch):
    ftp = {"job": {"id": "job-1"}, "requested_at": "t"}
    state, clip = _state(tmp_path, monkeypatch, ftp)

    cleanup._rebuild_process_state(state)

    assert clip["ftp"]["job"] is None
    assert clip["ftp"]["requested_at"] == "t"
