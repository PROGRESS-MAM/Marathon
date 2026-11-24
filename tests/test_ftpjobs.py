import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
toolbox = types.ModuleType("toolbox")
toolbox.tb_write_log = lambda *a, **k: None
toolbox.tb_link_api = lambda *a, **k: None
sys.modules.setdefault("toolbox", toolbox)

import pytest
from core import config, ftpjobs, state as state_module


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = tmp_path / "share"
    root.mkdir()
    ftp_dir = tmp_path / "ftp"
    ftp_dir.mkdir()
    settings = {
        "root_path": str(root), "defa_dir": "DEFA", "work_dir": ".marathon", "defa_marker": "DEFA",
        "proxy_name": "{veritone_id}_{clip_id}_10Mbit.mp4", "ftp_dir": str(ftp_dir), "ftp": 2,
        "max_job_attempts": 2,
    }
    for key, value in settings.items():
        monkeypatch.setitem(config.cfg, key, value)
    clip = _clip()
    state_module.ftp_record(clip)["requested_at"] = "2026-01-01T00:00:00+00:00"
    proxy = root / "DEFA" / clip["files"]["proxy"]["name"]
    proxy.parent.mkdir(parents=True)
    proxy.write_bytes(b"x" * 1000)
    state = {"clips": {clip["clip_id"]: clip}}
    ctx = {"issues": [], "listings": {}}
    return root, ftp_dir, clip, state, ctx, proxy


def _clip(clip_id="98765", ready=True):
    hit = {
        "collection": "DEFA", "identifier": "1234567", "veritone_id": "1234567", "title": "Titel",
        "clip_name": "clip.mxf", "masters": [], "master_files": [], "lto_tapes": [], "master_size": 1,
    }
    clip = state_module.new_clip(clip_id, hit)
    clip.update(ready=ready, stage=None if ready else "qc", active=True)
    clip["files"]["proxy"] = {"folder": "DEFA", "name": f"1234567_{clip_id}_10Mbit.mp4", "source": "QC", "last_seen_at": None}
    return clip


def _report(env, job_id, **fields):
    _, _, _, _, _, _ = env
    folder = Path(env[0]) / ".marathon" / "ftp" / "fertig"
    folder.mkdir(parents=True, exist_ok=True)
    payload = {"job_id": job_id, "status": "ok", "result": "", "preset": None, "new_master": None}
    payload.update(fields)
    (folder / f"{job_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def _cycle(env):
    env[4]["listings"].clear()
    ftpjobs.ftp_cycle(env[3], env[4])


def _create(env):
    _cycle(env)
    return env[2]["ftp"]["job"]


def test_creates_job_with_payload(env):
    for clip_id in ("10001", "10002"):
        clip = _clip(clip_id)
        state_module.ftp_record(clip)["requested_at"] = "2026-02-01T00:00:00+00:00"
        proxy = env[0] / "DEFA" / clip["files"]["proxy"]["name"]
        proxy.write_bytes(b"y" * 1000)
        env[3]["clips"][clip_id] = clip
    _cycle(env)
    job = env[2]["ftp"]["job"]
    payload = json.loads((env[0] / ".marathon" / "ftp" / "offen" / job["file"]).read_text())
    assert payload == {
        "schema_version": 6, "job_id": job["id"], "stage": "FTP", "clip_id": "98765", "collection": "DEFA",
        "identifier": "1234567", "title": "Titel", "clip_name": "clip.mxf", "created_at": payload["created_at"],
        "report_folder": ".marathon/ftp/fertig", "output_folder": f".marathon/ftp/ausgang/{job['id']}",
        "input": "DEFA/1234567_98765_10Mbit.mp4", "size": 1000, "ftp_dir": str(env[1]),
        "ftp_name": "1234567_98765_10Mbit.mp4",
    }
    assert job["state"] == "offen" and env[2]["ftp"]["requested_at"]
    assert sum(bool(item.get("ftp", {}).get("job") and item["ftp"]["job"]["state"] == "offen")
               for item in env[3]["clips"].values()) == config.cfg["ftp"]


def test_ok_confirms_renames_and_requests_field(env, monkeypatch):
    job = _create(env)
    target = env[1] / job["ftp_name"] if "ftp_name" in job else env[1] / "1234567_98765_10Mbit.mp4"
    target.write_bytes(b"x" * 1000)
    called = []
    monkeypatch.setattr(ftpjobs, "request_field", lambda clip, folder, name: called.append((folder, name)))
    _report(env, job["id"], ftp_file=target.name, size=1000)
    _cycle(env)
    assert env[2]["ftp"]["copied_at"] and env[2]["ftp"]["renamed_at"]
    assert env[2]["files"]["proxy"]["name"] == "1234567__Titel.mp4"
    assert called == [("DEFA", "1234567__Titel.mp4")]
    assert env[2]["ftp"]["requested_at"] is None


def test_ok_size_mismatch_counts_as_failed(env):
    job = _create(env)
    _report(env, job["id"], ftp_file="1234567_98765_10Mbit.mp4", size=999)
    _cycle(env)
    assert env[2]["ftp"]["attempts"] == 1
    assert env[2]["ftp"]["requested_at"] is not None
    assert env[2]["ftp"]["error"] is None


def test_rejected_sets_error_clip_stays_ready(env):
    job = _create(env)
    (env[0] / ".marathon" / "ftp" / "fertig").mkdir(parents=True, exist_ok=True)
    _report(env, job["id"], status="rejected", result="Tonprüfung")
    _cycle(env)
    assert env[2]["ftp"]["error"]["category"] == "Vom FTP-Worker abgelehnt"
    assert env[2]["ftp"]["requested_at"] is None and env[2]["ready"]


def test_failed_retry_then_final(env):
    job = _create(env)
    (env[0] / ".marathon" / "ftp" / "fertig").mkdir(parents=True, exist_ok=True)
    _report(env, job["id"], status="failed", result="Fehler")
    _cycle(env)
    assert env[2]["ftp"]["attempts"] == 1 and env[2]["ftp"]["requested_at"]
    job = _create(env)
    _report(env, job["id"], status="failed", result="Fehler erneut")
    _cycle(env)
    assert env[2]["ftp"]["error"]["category"] == "FTP-Job endgültig fehlgeschlagen"
    assert env[2]["ftp"]["requested_at"] is None


def test_rename_conflict_keeps_pending_and_retries_next_cycle(env):
    job = _create(env)
    (env[1] / "1234567_98765_10Mbit.mp4").write_bytes(b"x" * 1000)
    (env[0] / "DEFA" / "1234567__Titel.mp4").write_bytes(b"other")
    _report(env, job["id"], ftp_file="1234567_98765_10Mbit.mp4", size=1000)
    _cycle(env)
    assert env[2]["ftp"]["copied_at"] and not env[2]["ftp"]["renamed_at"]
    assert env[2]["ftp"]["error"]["category"] == "Namenskonflikt im Zielordner"
    (env[0] / "DEFA" / "1234567__Titel.mp4").unlink()
    _cycle(env)
    assert env[2]["ftp"]["renamed_at"]


def test_legacy_1_19_entry_renamed(env, monkeypatch):
    record = state_module.ftp_record(env[2])
    record.update(copied_at="2020-01-01T00:00:00+00:00", old_name=env[5].name, new_name="1234567__Titel.mp4", size=1000)
    called = []
    monkeypatch.setattr(ftpjobs, "request_field", lambda *args: called.append(args))
    _cycle(env)
    assert record["renamed_at"] and not record["requested_at"]
    assert called


def test_vanished_job_relaid_after_grace(env, monkeypatch):
    job = _create(env)
    job_path = env[0] / ".marathon" / "ftp" / "offen" / job["file"]
    job_path.unlink()
    job["missing_since"] = "2020-01-01T00:00:00+00:00"
    monkeypatch.setattr(ftpjobs, "age", lambda _: ftpjobs.missing_job_grace)
    _cycle(env)
    assert env[2]["ftp"]["job"] is not None
    assert env[2]["ftp"]["job"]["id"] != job["id"]


def test_withdraw_when_not_ready(env):
    job = _create(env)
    env[2]["ready"] = False
    env[2]["stage"] = "qc"
    env[2]["active"] = False
    _cycle(env)
    assert env[2]["ftp"]["job"] is None
    assert env[2]["ftp"]["requested_at"] is None
    assert not (env[0] / ".marathon" / "ftp" / "offen" / job["file"]).exists()


def test_unknown_report_archived(env):
    _create(env)
    folder = env[0] / ".marathon" / "ftp" / "fertig"
    (folder / "unknown.json").write_text(json.dumps({"job_id": "unknown", "status": "failed", "result": "late"}))
    _cycle(env)
    assert (folder.parent / "archiv" / "unknown.report.json").exists()


def test_invalid_ok_report_without_ftp_file_ignored(env):
    job = _create(env)
    _report(env, job["id"], size=1000)
    _cycle(env)
    assert env[2]["ftp"]["job"]["id"] == job["id"]
    assert any(item["category"] == "Jobreport ungültig (wird erneut versucht)" for item in env[4]["issues"])


def test_invalid_ok_report_with_wrong_ftp_file_ignored(env):
    job = _create(env)
    _report(env, job["id"], ftp_file="different.mp4", size=1000)
    _cycle(env)
    assert env[2]["ftp"]["job"]["id"] == job["id"]
    assert any(item["category"] == "Jobreport ungültig (wird erneut versucht)" for item in env[4]["issues"])


def test_clips_without_ftp_untouched(env):
    clip = env[2]
    clip.pop("ftp", None)
    ftpjobs.ftp_cycle({"clips": {clip["clip_id"]: clip}}, env[4])
    assert "ftp" not in clip

def test_one_report_archive_error_does_not_block_another(env, monkeypatch):
    first = env[2]
    second = _clip("98766")
    state_module.ftp_record(second)["requested_at"] = "2026-01-02T00:00:00+00:00"
    (env[0] / "DEFA" / second["files"]["proxy"]["name"]).write_bytes(b"y" * 1000)
    env[3]["clips"][second["clip_id"]] = second
    _cycle(env)
    jobs = {clip["clip_id"]: clip["ftp"]["job"] for clip in (first, second)}
    for clip in (first, second):
        target = env[1] / jobs[clip["clip_id"]]["ftp_name"]
        target.write_bytes(b"x" * 1000)
        _report(env, jobs[clip["clip_id"]]["id"], ftp_file=target.name, size=1000)
    original = ftpjobs._archive_report
    failing_id = jobs[first["clip_id"]]["id"]

    def fail_first(folder, relative, job_id, job, ctx):
        if job_id == failing_id:
            raise OSError("isolated archive failure")
        return original(folder, relative, job_id, job, ctx)

    monkeypatch.setattr(ftpjobs, "_archive_report", fail_first)
    _cycle(env)

    assert first["ftp"]["job"] is not None
    assert second["ftp"]["copied_at"] and second["ftp"]["renamed_at"]
    assert any(item["category"] == "FTP-Job konnte nicht archiviert werden" for item in env[4]["issues"])

