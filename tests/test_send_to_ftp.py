import sys
import types
from pathlib import Path, PureWindowsPath

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
toolbox = types.ModuleType("toolbox")
toolbox.tb_write_log = lambda *args, **kwargs: None
toolbox.tb_link_api = lambda *args, **kwargs: None
sys.modules.setdefault("toolbox", toolbox)

from core import ftp
from core.config import cfg
from core.state import new_clip


OLD_NAME = "1234567_98765_10Mbit.mp4"
NEW_NAME = "DEFA14097__Rosa.mp4"
PAYLOAD = b"p" * 1000


def _setup(monkeypatch, tmp_path):
    root_path = tmp_path / "share"
    final_dir = root_path / "DEFA"
    ftp_dir = tmp_path / "ftp"
    final_dir.mkdir(parents=True)
    ftp_dir.mkdir()
    error_dir = tmp_path / "errors"
    error_dir.mkdir()
    for key, value in {
        "root_path": str(root_path), "defa_dir": "DEFA", "work_dir": ".marathon",
        "defa_marker": "DEFA", "proxy_name": "{veritone_id}_{clip_id}_10Mbit.mp4",
        "ftp_dir": str(ftp_dir),
    }.items():
        monkeypatch.setitem(cfg, key, value)

    hit = {"collection": "DEFA Spielfilm", "identifier": "DEFA14097", "title": "Rosa",
           "veritone_id": "1234567", "clip_name": "Rosa.mxf", "masters": [],
           "master_files": [], "lto_tapes": [], "master_size": 0}
    clip = new_clip("98765", hit)
    clip.update(ready=True, stage=None, status="bereit")
    clip["files"]["proxy"] = {"folder": "DEFA", "name": OLD_NAME, "source": "QC", "last_seen_at": "x"}
    state = {"clips": {clip["clip_id"]: clip}, "cleanup": {}, "updated_at": None}
    source = final_dir / OLD_NAME
    source.write_bytes(PAYLOAD)
    state_file = tmp_path / "state.json"
    state_file.touch()
    saves, field_writes = [], []
    monkeypatch.setattr(ftp, "state_path", state_file)
    monkeypatch.setattr(ftp, "load_state", lambda: state)
    monkeypatch.setattr(ftp, "save_state", lambda value: saves.append(value))
    monkeypatch.setattr(ftp, "check_root", lambda: None)
    monkeypatch.setattr(ftp, "load_mapping", lambda: [])
    monkeypatch.setattr(ftp, "final_check", lambda clips, mapping: {item["clip_id"]: None for item in clips})
    monkeypatch.setattr(ftp, "write_fields", lambda value: field_writes.append(value))
    monkeypatch.setattr(ftp, "error_dir", error_dir)
    return root_path, final_dir, ftp_dir, error_dir, clip, state, source, saves, field_writes


def _record(ftp_dir, copied_at="copied", renamed_at=None):
    return {"target": str(ftp_dir / OLD_NAME), "size": len(PAYLOAD), "old_name": OLD_NAME,
            "new_name": NEW_NAME, "copied_at": copied_at, "renamed_at": renamed_at}


def test_sends_and_renames(monkeypatch, tmp_path):
    root, final_dir, ftp_dir, _, clip, _, source, _, field_writes = _setup(monkeypatch, tmp_path)

    ftp.send_to_ftp()

    assert (ftp_dir / OLD_NAME).read_bytes() == PAYLOAD
    assert (final_dir / NEW_NAME).read_bytes() == PAYLOAD
    assert not source.exists()
    assert not list(ftp_dir.glob("*.part"))
    assert clip["files"]["proxy"]["name"] == NEW_NAME
    assert clip["editshare"]["value"] == str(PureWindowsPath(root, "DEFA", NEW_NAME))
    assert clip["editshare"]["pending"] is True
    assert clip["ftp"]["renamed_at"]
    assert field_writes


def test_check_failed_not_copied(monkeypatch, tmp_path):
    _, _, ftp_dir, error_dir, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(ftp, "final_check", lambda clips, mapping: {"98765": "Prüfgrund"})

    ftp.send_to_ftp()

    assert "ftp" not in clip
    assert source.exists()
    assert not list(ftp_dir.iterdir())
    assert "Prüfgrund" in next(error_dir.iterdir()).read_text(encoding="utf-8")


def test_ftp_conflict_not_overwritten(monkeypatch, tmp_path):
    _, _, ftp_dir, _, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    existing = ftp_dir / OLD_NAME
    existing.write_bytes(b"do not overwrite")
    monkeypatch.setattr(ftp, "_copy", lambda *args: pytest.fail("copy must not run"))

    ftp.send_to_ftp()

    assert existing.read_bytes() == b"do not overwrite"
    assert source.exists()
    assert "ftp" not in clip


def test_rename_conflict_before_copy(monkeypatch, tmp_path):
    _, final_dir, ftp_dir, _, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    conflict = final_dir / NEW_NAME
    conflict.write_bytes(b"keep destination")
    monkeypatch.setattr(ftp, "_copy", lambda *args: pytest.fail("copy must not run"))

    ftp.send_to_ftp()

    assert conflict.read_bytes() == b"keep destination"
    assert source.exists()
    assert not list(ftp_dir.iterdir())
    assert "ftp" not in clip


def test_size_mismatch_removes_part(monkeypatch, tmp_path):
    _, _, ftp_dir, _, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)

    def short_copy(source_path, part_path):
        part_path.write_bytes(b"short")
        return len(PAYLOAD) - 1

    monkeypatch.setattr(ftp, "_copy", short_copy)
    ftp.send_to_ftp()

    assert not list(ftp_dir.glob("*.part"))
    assert not (ftp_dir / OLD_NAME).exists()
    assert source.exists()
    assert clip["ftp"]["copied_at"] is None


def test_resume_copy_pending(monkeypatch, tmp_path):
    _, final_dir, ftp_dir, _, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    copied_events_before = sum(item["event"] == "An FTP kopiert" for item in clip["history"])
    clip["ftp"] = _record(ftp_dir, copied_at=None)
    (ftp_dir / OLD_NAME).write_bytes(PAYLOAD)
    monkeypatch.setattr(ftp, "_copy", lambda *args: pytest.fail("resume must not copy"))

    ftp.send_to_ftp()

    assert not source.exists()
    assert (final_dir / NEW_NAME).read_bytes() == PAYLOAD
    assert clip["ftp"]["renamed_at"]
    assert clip["ftp"]["copied_at"]
    assert sum(item["event"] == "An FTP kopiert" for item in clip["history"]) - copied_events_before == 1


def test_resume_after_copy(monkeypatch, tmp_path):
    _, final_dir, ftp_dir, _, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    copied_events_before = sum(item["event"] == "An FTP kopiert" for item in clip["history"])
    clip["ftp"] = _record(ftp_dir)
    (ftp_dir / OLD_NAME).write_bytes(PAYLOAD)
    monkeypatch.setattr(ftp, "_copy", lambda *args: pytest.fail("resume must not copy"))

    ftp.send_to_ftp()

    assert not source.exists()
    assert (final_dir / NEW_NAME).read_bytes() == PAYLOAD
    assert clip["ftp"]["renamed_at"]
    assert sum(item["event"] == "An FTP kopiert" for item in clip["history"]) - copied_events_before == 0


def test_resume_after_rename(monkeypatch, tmp_path):
    _, final_dir, ftp_dir, _, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    (final_dir / NEW_NAME).write_bytes(PAYLOAD)
    source.unlink()
    clip["ftp"] = _record(ftp_dir, renamed_at=None)
    monkeypatch.setattr(ftp, "_copy", lambda *args: pytest.fail("resume must not copy"))

    ftp.send_to_ftp()

    assert clip["files"]["proxy"]["name"] == NEW_NAME
    assert clip["ftp"]["renamed_at"]
    assert clip["editshare"]["pending"] is True


def test_already_sent_skipped(monkeypatch, tmp_path):
    _, _, ftp_dir, _, clip, _, _, _, _ = _setup(monkeypatch, tmp_path)
    clip["ftp"] = _record(ftp_dir, renamed_at="done")
    monkeypatch.setattr(ftp, "final_check", lambda *args: pytest.fail("already sent clip must be skipped"))

    ftp.send_to_ftp()


def test_no_ftp_dir_raises(monkeypatch, tmp_path):
    *_, ftp_dir, _, _, _, _, _, _ = _setup(monkeypatch, tmp_path)
    ftp_dir.rmdir()

    with pytest.raises(FileNotFoundError, match="FTP-Pfad nicht erreichbar"):
        ftp.send_to_ftp()


def test_final_conflict_is_case_insensitive(monkeypatch, tmp_path):
    _, final_dir, ftp_dir, _, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    conflict = final_dir / NEW_NAME.swapcase()
    conflict.write_bytes(b"keep destination")
    monkeypatch.setattr(ftp, "_copy", lambda *args: pytest.fail("copy must not run"))

    ftp.send_to_ftp()

    assert conflict.read_bytes() == b"keep destination"
    assert source.exists()
    assert not list(ftp_dir.iterdir())
    assert "ftp" not in clip


def test_ftp_conflict_is_case_insensitive(monkeypatch, tmp_path):
    _, _, ftp_dir, _, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    conflict = ftp_dir / OLD_NAME.swapcase()
    conflict.write_bytes(b"do not overwrite")
    monkeypatch.setattr(ftp, "_copy", lambda *args: pytest.fail("copy must not run"))

    ftp.send_to_ftp()

    assert conflict.read_bytes() == b"do not overwrite"
    assert source.exists()
    assert "ftp" not in clip


def test_source_name_is_not_a_destination_conflict(monkeypatch, tmp_path):
    _, final_dir, ftp_dir, _, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(ftp, "ftp_name", lambda item: OLD_NAME)

    ftp.send_to_ftp()

    assert source.is_file()
    assert (ftp_dir / OLD_NAME).read_bytes() == PAYLOAD
    assert clip["files"]["proxy"]["name"] == OLD_NAME
    assert (final_dir / OLD_NAME).is_file()


def test_final_check_exception_propagates_before_copy(monkeypatch, tmp_path):
    _, _, ftp_dir, _, clip, _, source, _, _ = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(ftp, "final_check", lambda *args: (_ for _ in ()).throw(RuntimeError("check failed")))
    monkeypatch.setattr(ftp, "_copy", lambda *args: pytest.fail("copy must not run"))

    with pytest.raises(RuntimeError, match="check failed"):
        ftp.send_to_ftp()

    assert source.exists()
    assert not list(ftp_dir.iterdir())
    assert "ftp" not in clip
