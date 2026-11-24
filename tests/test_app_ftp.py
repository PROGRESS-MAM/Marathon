import sys, types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
toolbox = types.ModuleType("toolbox")
toolbox.tb_write_log = lambda *a, **k: None
toolbox.tb_link_api = lambda *a, **k: None
sys.modules.setdefault("toolbox", toolbox)

from core import app


def test_cycle_saves_state_when_ftp_cycle_fails(tmp_path, monkeypatch):
    state = {"clips": {}, "notes": []}
    saves = []
    state_path = tmp_path / "state.json"
    state_path.touch()
    monkeypatch.setattr(app, "state_path", state_path)
    monkeypatch.setattr(app, "load_mapping", lambda: [])
    monkeypatch.setattr(app, "check_root", lambda: None)
    monkeypatch.setattr(app, "load_state", lambda: state)
    monkeypatch.setattr(app, "cleanup_review", lambda *args: None)
    monkeypatch.setattr(app, "process", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "priority", lambda *args: [])
    monkeypatch.setattr(app, "test_job_ids", lambda: [])
    monkeypatch.setattr(app, "save_state", lambda value: saves.append(value))
    monkeypatch.setattr(app, "ftp_cycle", lambda *args: (_ for _ in ()).throw(RuntimeError("x")))

    assert app._cycle() is None
    assert saves == [state]
    assert any(note["category"] == "FTP-Zyklus fehlgeschlagen – nächster Job-Zyklus versucht es erneut"
               for note in state["notes"])
