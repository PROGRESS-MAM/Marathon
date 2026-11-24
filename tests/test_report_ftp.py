import sys, types
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
toolbox = types.ModuleType("toolbox")
toolbox.tb_write_log = lambda *a, **k: None
toolbox.tb_link_api = lambda *a, **k: None
sys.modules.setdefault("toolbox", toolbox)

from core import config, report, state as state_module
from core.constants import columns


def _hit():
    return {
        "collection": "K",
        "identifier": "ID1",
        "veritone_id": "123",
        "title": "Titel",
        "clip_name": "clip.mxf",
        "masters": [{"file": "master.mxf", "flow_hash": "2:ab", "size": 1, "tapes": ["T1"]}],
        "master_files": ["master.mxf"],
        "lto_tapes": ["T1"],
        "master_size": 1,
    }


def _clip(clip_id, ready=False, stage="qc", ftp=None):
    clip = state_module.new_clip(clip_id, _hit())
    clip["ready"] = ready
    clip["stage"] = None if ready else stage
    if ftp is not None:
        clip["ftp"] = ftp
    return clip


def test_columns():
    assert columns == (
        "Kollektion", "Prio Restore", "Prio Transcode", "Prio QC", "Gesamt", "Bereit", "FTP", "%",
        "Queue Restore", "Queue Transcode", "Queue QC",
    )


def test_totals_ftp():
    clips = {
        "1": _clip("1", ready=True, ftp={"copied_at": "x"}),
        "2": _clip("2", ready=True),
        "3": _clip("3", stage="qc"),
    }
    assert report._totals({"clips": clips}, [{"name": "K"}]) == {"K": (3, 2, 1, 0, 0, 1)}


def test_render_ftp_column():
    text = report._render(
        "daily", datetime(2026, 1, 1), {"K": (3, 2, 1, 0, 0, 1)},
        {"restore": [], "transcode": [], "qc": []}, {},
    )
    header = next(line for line in text.splitlines() if line.startswith("Kollektion"))
    summary = next(line for line in text.splitlines() if line.startswith("Summe"))
    header_cells, summary_cells = [cell.strip() for cell in header.split("|")], [cell.strip() for cell in summary.split("|")]
    assert "Bereit | FTP | %" in header
    assert summary_cells[header_cells.index("FTP")] == "1"
    assert summary_cells[header_cells.index("%")] == "66.7 %"


def test_read_previous_old_report(tmp_path):
    old_header = "Kollektion | Prio Restore | Prio Transcode | Prio QC | Gesamt | Bereit | % | Queue Restore | Queue Transcode | Queue QC"
    path = tmp_path / "old.txt"
    path.write_text(old_header + "\nK | | | | 3 | 2 | 66.7 % | 0 | 0 | 1\n", encoding="utf-8")
    result = report._read_previous(path)
    assert "K" in result
    assert "FTP" not in result["K"]


def test_ftp_issues():
    clip = _clip("1", ftp={"error": {"category": "Vom FTP-Worker abgelehnt", "detail": "Kanal 2 stumm", "at": "t"}})
    state = {"clips": {"1": clip, "2": _clip("2")}}
    ctx = {"issues": []}
    report._ftp_issues(state, ctx)
    assert len(ctx["issues"]) == 1
    assert ctx["issues"][0]["section"] == "ftp_error"
    assert ctx["issues"][0]["category"] == "Vom FTP-Worker abgelehnt"


def test_ftp_record_completes_old_entry():
    clip = {"ftp": {"copied_at": "x", "renamed_at": None, "old_name": "a", "new_name": "b", "target": "t", "size": 1}}
    result = state_module.ftp_record(clip)
    assert set(result) == {
        "requested_at", "job", "job_count", "attempts", "target", "size", "old_name", "new_name",
        "copied_at", "renamed_at", "error",
    }
    assert result["copied_at"] == "x"
    assert result["attempts"] == 0


def test_limits_ftp():
    assert config.config_schema["limits"]["ftp"] == "count"
