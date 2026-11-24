import copy
import importlib.util
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
toolbox = types.ModuleType("toolbox")
toolbox.tb_write_log = lambda *args, **kwargs: None
toolbox.tb_link_api = lambda *args, **kwargs: None
sys.modules.setdefault("toolbox", toolbox)

from core.config import cfg
from core.layout import qc_inbox
from core.state import _clip_problem, _empty_state, check_state, new_clip

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "reset_qc.py"
spec = importlib.util.spec_from_file_location("reset_qc", MODULE_PATH)
reset_qc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset_qc)


def _clip(clip_id="621226"):
    hit = {"collection": "DEFA Dokumentation", "identifier": "DEFA01087", "title": "Titel",
           "veritone_id": "987654", "clip_name": "Titel.mxf",
           "masters": [{"file": "a.mxf", "flow_hash": "h", "size": 1, "tapes": ["T1"]}],
           "master_files": [], "lto_tapes": [], "master_size": 1}
    clip = new_clip(clip_id, hit)
    clip.update(stage="qc", ready=False, active=False, status="QC nicht bestanden", attempts=2)
    clip["issues"]["sticky"] = {"category": "QC nicht bestanden", "detail": "x", "matches": None, "since": "x"}
    return clip


def _setup(monkeypatch, tmp_path):
    root_path = tmp_path / "share"
    root_path.mkdir()
    for key, value in {"root_path": str(root_path), "defa_dir": "DEFA", "work_dir": ".marathon",
                       "defa_marker": "DEFA", "proxy_name": "{veritone_id}_{clip_id}_10Mbit.mp4"}.items():
        monkeypatch.setitem(cfg, key, value)
    return root_path


def _proxy(root_path, clip, name="proxy.mp4"):
    folder = qc_inbox(clip["collection"])
    path = root_path.joinpath(*folder.split("/"), name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"proxy")
    clip["files"]["proxy"] = {"folder": folder, "name": name, "source": "Transcode", "last_seen_at": "x"}
    return path


def _report(categories):
    lines = ["Auswertung", "  [ 1]   2  Übersicht", "Fälle je Kategorie"]
    for number, ids in categories:
        lines.append(f"[{number}] Kategorie {number} ({len(ids)})")
        lines.extend(f"  {clip_id} · DEFA01087 Titel · REJECTED · 2026-11-23 16:58:06\n    /pfad\n    Grund" for clip_id in ids)
    return "\r\n".join(lines)


def test_parse_report_categories():
    text = _report([(1, ["621226", "621227"]), (2, ["621228"]), (3, ["621229"])])
    assert reset_qc.parse_report(text) == {1: ["621226", "621227"], 2: ["621228"], 3: ["621229"]}


def test_parse_report_count_mismatch():
    text = "Fälle je Kategorie\n[1] Kategorie 1 (3)\n  621226 · Titel\n  621227 · Titel"
    with pytest.raises(ValueError, match="erwartet 3 Fälle, gefunden 2"):
        reset_qc.parse_report(text)


def test_select_excludes_keep():
    reset, kept = reset_qc.select_clips({1: ["a", "b", "c"], 2: ["d", "a"], 3: ["c", "e"]}, {3})
    assert reset == ["a", "b", "d"]
    assert kept == {"c", "e"}


def test_select_unknown_keep():
    with pytest.raises(ValueError, match=r"Kategorie \[9\] nicht in der Auswertung"):
        reset_qc.select_clips({1: ["a"]}, {9})


def test_reset_clip_resets_and_deletes_proxy(monkeypatch, tmp_path):
    root_path = _setup(monkeypatch, tmp_path)
    clip = _clip()
    proxy = _proxy(root_path, clip)
    master_path = root_path / "DEFA" / ".marathon" / "DEFA Dokumentation" / "transcode" / "eingang" / clip["clip_id"] / "a.mxf"
    master_path.parent.mkdir(parents=True)
    master_path.write_bytes(b"master")
    clip["files"]["master"] = {"folder": str(master_path.parent.relative_to(root_path)), "names": ["a.mxf"],
                                 "source": "Restore", "last_seen_at": "x"}
    state = {"clips": {clip["clip_id"]: clip}}

    ok, text = reset_qc.reset_clip(clip, state)

    assert (ok, text) == (True, "Proxy gelöscht: DEFA/.marathon/DEFA Dokumentation/qc/eingang/proxy.mp4")
    assert not proxy.exists()
    assert (clip["stage"], clip["ready"], clip["active"], clip["attempts"]) == ("restore", False, True, 0)
    assert (clip["job"], clip["status"]) == (None, "wartet")
    assert clip["files"] == {"master": None, "proxy": None}
    assert clip["issues"] == {"file": None, "sticky": None}
    assert clip["history"][-1]["event"] == "Für Restore zurückgesetzt (QC-Neustart)"
    assert _clip_problem(clip["clip_id"], clip) is None
    assert master_path.is_file()


def test_reset_clip_proxy_error_keeps_clip_unchanged(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    clip = _clip()
    clip["files"]["proxy"] = {"folder": qc_inbox(clip["collection"]), "name": "proxy.mp4",
                               "source": "Transcode", "last_seen_at": "x"}
    state = {"clips": {clip["clip_id"]: clip}}
    before = copy.deepcopy(clip)

    class UnwritableProxy:
        def __truediv__(self, name):
            return self

        def is_file(self):
            return True

        def unlink(self):
            raise OSError("denied")

    monkeypatch.setattr(reset_qc, "safe_work_path", lambda _: UnwritableProxy())
    ok, text = reset_qc.reset_clip(clip, state)

    assert ok is False
    assert text == "Proxy nicht löschbar: denied"
    assert clip == before


def test_reset_clip_proxy_error_after_withdraw(monkeypatch, tmp_path):
    root_path = _setup(monkeypatch, tmp_path)
    clip = _clip()
    proxy = {"folder": qc_inbox(clip["collection"]), "name": "proxy.mp4",
             "source": "Transcode", "last_seen_at": "x"}
    clip["files"]["proxy"] = proxy.copy()
    sticky = copy.deepcopy(clip["issues"]["sticky"])
    job_file = root_path / ".marathon" / "qc" / "offen" / "job-1.json"
    job_file.parent.mkdir(parents=True)
    job_file.write_text("{}", encoding="utf-8")
    clip["job"] = {"id": "job-1", "stage": "qc", "folder": ".marathon/qc", "file": "job-1.json",
                   "output_folder": ".marathon/qc/ausgang/job-1", "state": "offen"}
    state = {"clips": {clip["clip_id"]: clip}}

    class UnwritableProxy:
        def __truediv__(self, name):
            return self

        def is_file(self):
            return True

        def unlink(self):
            raise OSError("denied")

    monkeypatch.setattr(reset_qc, "safe_work_path", lambda _: UnwritableProxy())
    ok, text = reset_qc.reset_clip(clip, state)

    assert (ok, text) == (False, "Proxy nicht löschbar: denied")
    assert not job_file.exists()
    assert clip["job"] is None
    assert clip["stage"] == "qc"
    assert clip["issues"]["sticky"] == sticky
    assert clip["files"]["proxy"] == proxy
    assert _clip_problem(clip["clip_id"], clip) is None


def test_reset_clip_withdraws_open_job(monkeypatch, tmp_path):
    root_path = _setup(monkeypatch, tmp_path)
    clip = _clip()
    job_file = root_path / ".marathon" / "qc" / "offen" / "job-1.json"
    job_file.parent.mkdir(parents=True)
    job_file.write_text("{}", encoding="utf-8")
    clip["job"] = {"id": "job-1", "stage": "qc", "folder": ".marathon/qc", "file": "job-1.json",
                   "output_folder": ".marathon/qc/ausgang/job-1", "state": "offen"}
    state = {"clips": {clip["clip_id"]: clip}}

    ok, _ = reset_qc.reset_clip(clip, state)

    assert ok is True
    assert not job_file.exists()
    assert clip["job"] is None
    assert clip["stage"] == "restore"


def test_plan_skips(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    not_qc = _clip("2")
    not_qc.update(ready=True, stage=None)
    running = _clip("3")
    running["job"] = {"state": "laufend", "worker": "w"}
    no_masters = _clip("4")
    no_masters["masters"] = []
    wrong_proxy = _clip("5")
    wrong_proxy["files"]["proxy"] = {"folder": "elsewhere", "name": "p.mp4"}
    clips = {clip["clip_id"]: clip for clip in (not_qc, running, no_masters, wrong_proxy)}
    before = copy.deepcopy(clips)

    reset, skips = reset_qc.plan_reset({"clips": clips}, ["missing", "2", "3", "4", "5"])

    assert reset == []
    assert skips == [("missing", "nicht in der JSON"),
                     ("2", "nicht in QC (Stand: Bereit)"),
                     ("3", "QC-Job läuft bei w"),
                     ("4", "keine Masterdateien aus EditShare (kein Restore möglich)"),
                     ("5", "Proxy nicht im QC-Eingang: elsewhere/p.mp4")]
    assert clips == before


def _main_setup(monkeypatch, tmp_path, report_text):
    root_path = _setup(monkeypatch, tmp_path)
    report = tmp_path / "report.txt"
    report.write_text(report_text, encoding="utf-8")
    state_path = tmp_path / "marathon.json"
    state_path.touch()
    clip = _clip()
    proxy = _proxy(root_path, clip)
    skipped = _clip("621227")
    skipped["ready"], skipped["stage"] = True, None
    state = {"clips": {clip["clip_id"]: clip, skipped["clip_id"]: skipped}, "cleanup": {}}
    monkeypatch.setattr(reset_qc, "load_config", lambda: None)
    monkeypatch.setattr(reset_qc, "acquire_lock", lambda: None)
    monkeypatch.setattr(reset_qc, "check_root", lambda: None)
    monkeypatch.setattr(reset_qc, "state_path", state_path)
    monkeypatch.setattr(reset_qc, "load_state", lambda: state)
    saves = []
    monkeypatch.setattr(reset_qc, "save_state", lambda value: saves.append(copy.deepcopy(value)))
    return report, state, clip, skipped, proxy, saves


def test_main_preview_changes_nothing(monkeypatch, tmp_path, capsys):
    report, state, clip, skipped, proxy, saves = _main_setup(monkeypatch, tmp_path, _report([(1, ["621226", "621227"]), (2, ["621228"])]))
    before = copy.deepcopy(state)

    result = reset_qc.main([str(report), "--keep", "2"])

    assert result == 0
    assert not saves
    assert proxy.is_file()
    assert state == before
    assert "Vorschau – nichts geändert." in capsys.readouterr().out


def test_main_apply(monkeypatch, tmp_path, capsys):
    report, state, clip, skipped, proxy, saves = _main_setup(monkeypatch, tmp_path, _report([(1, ["621226", "621227"]), (2, ["621228"])]))
    skipped_before = copy.deepcopy(skipped)

    result = reset_qc.main([str(report), "--keep", "2", "--apply"])

    assert result == 0
    assert len(saves) == 1
    assert not proxy.exists()
    assert skipped == skipped_before
    assert clip["stage"] == "restore"
    assert "1 Clips auf Restore zurückgesetzt" in capsys.readouterr().out


def test_main_lock_busy(monkeypatch, tmp_path):
    report = tmp_path / "report.txt"
    report.write_text("", encoding="utf-8")
    monkeypatch.setattr(reset_qc, "load_config", lambda: None)
    monkeypatch.setattr(reset_qc, "acquire_lock", lambda: (_ for _ in ()).throw(RuntimeError("busy")))
    saves = []
    monkeypatch.setattr(reset_qc, "save_state", lambda value: saves.append(value))

    assert reset_qc.main([str(report), "--keep", "1", "--apply"]) == 1
    assert not saves



def test_reset_clip_rejects_proxy_name_traversal(monkeypatch, tmp_path):
    root_path = _setup(monkeypatch, tmp_path)
    clip = _clip()
    master_path = root_path / "DEFA" / ".marathon" / "DEFA Dokumentation" / "transcode" / "eingang" / clip["clip_id"] / "master.mxf"
    master_path.parent.mkdir(parents=True)
    master_path.write_bytes(b"master")
    clip["files"]["proxy"] = {"folder": qc_inbox(clip["collection"]),
                               "name": "../../transcode/eingang/621226/master.mxf",
                               "source": "Transcode", "last_seen_at": "x"}

    ok, text = reset_qc.reset_clip(clip, {"clips": {clip["clip_id"]: clip}})

    assert ok is False
    assert text.startswith("Proxy nicht löschbar:")
    assert master_path.is_file()
    assert clip["stage"] == "qc"
    assert clip["files"]["proxy"]["name"].startswith("../")


def test_reset_clip_exception_before_delete_keeps_proxy_and_state(monkeypatch, tmp_path):
    root_path = _setup(monkeypatch, tmp_path)
    clip = _clip()
    proxy = _proxy(root_path, clip)
    state = _empty_state()
    state["clips"][clip["clip_id"]] = clip
    before = copy.deepcopy(state)
    check_state(state)
    monkeypatch.setattr(reset_qc, "stamp", lambda: (_ for _ in ()).throw(RuntimeError("clock failed")))

    with pytest.raises(RuntimeError, match="clock failed"):
        reset_qc.reset_clip(clip, state)

    assert proxy.is_file()
    assert state == before
    check_state(state)


def test_reset_clip_result_passes_full_schema_v8_validation(monkeypatch, tmp_path):
    root_path = _setup(monkeypatch, tmp_path)
    clip = _clip()
    _proxy(root_path, clip)
    state = _empty_state()
    state["clips"][clip["clip_id"]] = clip
    check_state(state)

    ok, _ = reset_qc.reset_clip(clip, state)

    assert ok is True
    check_state(state)


def test_main_saves_state_after_reset_exception(monkeypatch, tmp_path, capsys):
    report, state, clip, skipped, proxy, saves = _main_setup(
        monkeypatch, tmp_path, _report([(1, ["621226"]), (2, ["621228"])])
    )
    monkeypatch.setattr(reset_qc, "stamp", lambda: (_ for _ in ()).throw(RuntimeError("clock failed")))

    result = reset_qc.main([str(report), "--keep", "2", "--apply"])

    assert result == 1
    assert len(saves) == 1
    assert proxy.is_file()
    assert clip["stage"] == "qc"
    assert "clock failed" in capsys.readouterr().out


def test_reset_clip_withdraw_false_keeps_clip_and_proxy(monkeypatch, tmp_path):
    root_path = _setup(monkeypatch, tmp_path)
    clip = _clip()
    proxy = _proxy(root_path, clip)
    before = copy.deepcopy(clip)
    monkeypatch.setattr(reset_qc, "withdraw", lambda _clip, _state: False)

    ok, text = reset_qc.reset_clip(clip, {"clips": {clip["clip_id"]: clip}})

    assert (ok, text) == (False, "Job läuft oder wurde gerade übernommen")
    assert clip == before
    assert proxy.is_file()
