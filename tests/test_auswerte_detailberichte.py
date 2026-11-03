from datetime import date, timedelta
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import auswerte_detailberichte as analyzer


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests/fixtures/details_transcode_2026-10-30_09-00-07-352001.txt"
MASTER_FOLDER = "DEFA/.marathon/DEFA Videoarchive B-Roll/transcode/eingang/415477"

REPORT = """Marathon 1.18.3 · Detailbericht Transcode
Zeitraum        2026-11-03 09:00:00 – 2026-11-03 10:00:00
Jobs insgesamt  2
ok              0
Fehlgeschlagen  1  (davon endgültig 1)
Blockiert       0
Details: 2

#1  FAILED  0042 Beispielclip
    clip_id 4711 · Kollektion Demo · Preset h264 · Worker encode-02
    Job      20261103T091122123456__4711__transcode1
    Zeit     2026-11-03 09:12:30
    Versuch  3 von 3 (endgültig)
    Ergebnis Marathon: Transcode-Ausgang enthält 2 Proxy-Dateien statt einer

#2  REJECTED  0043 Weiterer Clip
    clip_id 4712 · Kollektion Demo · Worker encode-02
    Job      20261103T091200123456__4712__transcode1
    Zeit     2026-11-03 09:14:00
    Ergebnis Worker: manuelle Prüfung nötig
    Ablage   Demo/work/Transcode/archiv/20261103T091200123456__4712__transcode1.zip
"""


def write_report(archive: Path, filename: str, text: str = REPORT) -> Path:
    archive.mkdir(parents=True, exist_ok=True)
    path = archive / filename
    path.write_text(text, encoding="utf-8")
    return path


def write_state(path: Path, clips) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 8, "clips": clips}), encoding="utf-8")


def state_clip(clip_id, folder=None):
    master = {"folder": folder} if folder is not None else {}
    return {"clip_id": clip_id, "files": {"master": master}}


def test_parses_failure_blocks_and_german_categories():
    cases = analyzer.parse_cases(REPORT, "transcode")
    assert len(cases) == 2
    assert cases[0].clip_id == "4711"
    assert cases[0].collection == "Demo"
    assert cases[0].category == "transcode_output_contract"
    assert cases[1].category == "worker_failed"
    assert cases[1].result == "Worker: manuelle Prüfung nötig"
    assert analyzer.CATEGORY_LABELS[cases[0].category] == "Transcode-Ausgabe fehlerhaft"

    qc_report = REPORT.replace("Detailbericht Transcode", "Detailbericht QC").replace(
        "Marathon: Transcode-Ausgang enthält 2 Proxy-Dateien statt einer",
        "QC: stream_specs(video_1080p): bitrate nicht bestanden",
    )
    assert analyzer.parse_cases(qc_report, "qc")[0].category == "qc_rejected"


def test_clip_folder_index_supports_state_dict_list_and_numeric_ids():
    by_id = analyzer.build_clip_folder_index({
        "clips": {"415477": state_clip(415477, MASTER_FOLDER), "999": state_clip("999")}
    })
    assert by_id == {"415477": MASTER_FOLDER}

    by_list = analyzer.build_clip_folder_index({
        "clips": [state_clip("415477", MASTER_FOLDER), state_clip(888)]
    })
    assert by_list == {"415477": MASTER_FOLDER}


def test_missing_clip_or_master_folder_uses_not_found_text():
    report = analyzer.parse_report(Path("details_transcode_2026-11-03_09-00-00-000000.txt"), REPORT)
    cases = analyzer.collect_cases([report], {"4711": MASTER_FOLDER})
    assert cases[0].folder == MASTER_FOLDER
    assert cases[1].folder == analyzer.MISSING_FOLDER

    no_folder = analyzer.build_clip_folder_index({"clips": {"4712": state_clip("4712")}})
    assert analyzer.collect_cases([report], no_folder)[1].folder == analyzer.MISSING_FOLDER


def test_missing_marathon_json_warns_and_returns_empty_index(tmp_path):
    folders, warning = analyzer.load_clip_folder_index(tmp_path / "marathon.json")
    assert folders == {}
    assert warning is not None
    assert "marathon.json nicht gefunden" in warning


def test_report_jobs_are_deduplicated(tmp_path):
    first = analyzer.parse_report(
        write_report(tmp_path, "details_transcode_2026-11-03_09-00-00-000000.txt"), REPORT
    )
    second = analyzer.parse_report(
        write_report(tmp_path, "details_transcode_2026-11-03_10-00-00-000000.txt"), REPORT
    )
    folders = {"4711": MASTER_FOLDER, "4712": "other/folder"}
    cases = analyzer.collect_cases([first, second], folders)
    assert len(cases) == 2
    assert {case.folder for case in cases} == {MASTER_FOLDER, "other/folder"}

    first_text = REPORT.replace("clip_id 4712", "clip_id 9999")
    first = analyzer.parse_report(Path("first.txt"), first_text)
    second = analyzer.parse_report(Path("second.txt"), REPORT)
    deduplicated = analyzer.collect_cases([first, second], folders)
    rejected = next(case for case in deduplicated if case.status == "REJECTED")
    assert len(deduplicated) == 2
    assert rejected.folder == "other/folder"


def test_days_filter_prefers_filename_and_falls_back_to_period(tmp_path):
    today = date.today()
    recent = today - timedelta(days=2)
    old = today - timedelta(days=4)
    recent_report = analyzer.parse_report(
        write_report(tmp_path, f"details_transcode_{recent}_09-00-00-000000.txt"), REPORT
    )
    old_report = analyzer.parse_report(
        write_report(tmp_path, f"details_transcode_{old}_09-00-00-000000.txt"), REPORT
    )
    assert analyzer.date_in_window(recent_report, 3, today)
    assert not analyzer.date_in_window(old_report, 3, today)
    fallback_text = REPORT.replace("2026-11-03", today.isoformat())
    fallback = analyzer.parse_report(write_report(tmp_path, "details_transcode_no-date.txt", fallback_text), fallback_text)
    assert fallback.report_date == today


def test_main_keeps_tage_filter_and_writes_plain_text(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    today = date.today()
    recent = today - timedelta(days=2)
    old = today - timedelta(days=4)
    report_today = REPORT.replace("2026-11-03", today.isoformat())
    write_report(archive, f"details_transcode_{today}_09-00-00-000000.txt", report_today)
    write_report(archive, f"details_transcode_{recent}_09-00-00-000000.txt", report_today)
    write_report(archive, f"details_transcode_{old}_09-00-00-000000.txt", report_today)
    monkeypatch.setattr(analyzer, "STATE_PATH", tmp_path / "missing.json")

    monkeypatch.setattr(analyzer, "TAGE", 3)
    output = tmp_path / "summary.txt"
    assert analyzer.main(["--archiv", str(archive), "--ausgabe", str(output), "--leise"]) == 0
    content = output.read_text(encoding="utf-8")
    assert "Anzahl Berichte: 2" in content
    assert "Gesamtzahl Fälle: 2" in content
    assert "nicht in marathon.json gefunden" in content
    assert "##" not in content and "`" not in content

    monkeypatch.setattr(analyzer, "TAGE", None)
    all_output = tmp_path / "all.txt"
    assert analyzer.main(["--archiv", str(archive), "--ausgabe", str(all_output), "--leise"]) == 0
    assert "Anzahl Berichte: 3" in all_output.read_text(encoding="utf-8")


def test_no_argument_cli_writes_384_cases_and_state_folder(tmp_path):
    repo = tmp_path / "repo"
    archive = repo / "reports" / "archive"
    archive.mkdir(parents=True)
    script = repo / "auswerte_detailberichte.py"
    shutil.copyfile(REPO_ROOT / "auswerte_detailberichte.py", script)
    shutil.copyfile(FIXTURE, archive / FIXTURE.name)
    write_state(repo / "state" / "marathon.json", {"415477": state_clip(415477, MASTER_FOLDER)})

    result = subprocess.run(
        [sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    output = repo / "auswertung_detailberichte.txt"
    content = output.read_text(encoding="utf-8")
    case_lines = [line for line in content.splitlines() if "Clip-ID:" in line]
    assert "Gesamtzahl Fälle: 384" in content
    assert len(case_lines) == 384
    assert f"Ordner: {MASTER_FOLDER}" in content
    assert "nicht in marathon.json gefunden" in content
    assert "Tonkanal unsicher: 170" in content
    assert "audio_channel_uncertain" not in content
    assert not (repo / "auswertung_detailberichte.md").exists()


def test_missing_json_warning_does_not_stop_main(tmp_path, monkeypatch, capsys):
    archive = tmp_path / "archive"
    today = date.today()
    text = REPORT.replace("2026-11-03", today.isoformat())
    write_report(archive, f"details_transcode_{today}_09-00-00-000000.txt", text)
    monkeypatch.setattr(analyzer, "STATE_PATH", tmp_path / "missing" / "marathon.json")
    monkeypatch.setattr(analyzer, "TAGE", None)
    output = tmp_path / "summary.txt"
    assert analyzer.main(["--archiv", str(archive), "--ausgabe", str(output)]) == 0
    assert "marathon.json nicht gefunden" in capsys.readouterr().err
    assert output.exists()
    assert analyzer.MISSING_FOLDER in output.read_text(encoding="utf-8")


def test_30_mb_state_index_and_report_run_in_seconds(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    shutil.copyfile(FIXTURE, write_report(archive, FIXTURE.name))
    state_path = tmp_path / "state" / "marathon.json"
    state_path.parent.mkdir(parents=True)
    target_bytes = 30_000_000
    folder_padding = "x" * 300
    sample = {"clip_id": 123456, "files": {"master": {"folder": "DEFA/" + folder_padding}}}
    sample_size = len(json.dumps("123456")) + 1 + len(json.dumps(sample, separators=(",", ":"))) + 1
    clip_count = (target_bytes - 40) // sample_size
    with state_path.open("w", encoding="utf-8") as handle:
        handle.write('{"schema_version":8,"clips":{')
        for clip_id in range(clip_count):
            if clip_id:
                handle.write(",")
            entry = {
                "clip_id": clip_id,
                "files": {"master": {"folder": f"DEFA/{clip_id:06d}/" + folder_padding}},
            }
            json.dump(str(clip_id), handle)
            handle.write(":")
            json.dump(entry, handle, separators=(",", ":"))
        if clip_count:
            handle.write(",")
        json.dump("415477", handle)
        handle.write(":")
        json.dump(state_clip(415477, MASTER_FOLDER), handle, separators=(",", ":"))
        handle.write("}}")
    size = state_path.stat().st_size
    assert 29_000_000 <= size <= 31_000_000

    monkeypatch.setattr(analyzer, "STATE_PATH", state_path)
    monkeypatch.setattr(analyzer, "TAGE", None)
    output = tmp_path / "summary.txt"
    started = time.perf_counter()
    assert analyzer.main(["--archiv", str(archive), "--ausgabe", str(output), "--leise"]) == 0
    elapsed = time.perf_counter() - started
    content = output.read_text(encoding="utf-8")
    assert "Gesamtzahl Fälle: 384" in content
    assert f"Ordner: {MASTER_FOLDER}" in content
    assert elapsed < 10, f"30 MB state run took {elapsed:.2f}s"


def test_only_matching_transcode_reports_are_opened(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    today = date.today()
    valid = write_report(archive, f"details_transcode_{today}_09-00-00-000000.txt")
    for name in (
        f"details_qc_{today}_09-00-00-000000.txt",
        f"details_restore_{today}_09-00-00-000000.txt",
        f"details_transcode_{today}_09-00-00.txt",
        "details_transcode_no-date.txt",
        "error_report.txt",
    ):
        write_report(archive, name, "must not be read")

    opened = []
    original = analyzer.read_report_text

    def record_read(path):
        opened.append(path)
        return original(path)

    monkeypatch.setattr(analyzer, "read_report_text", record_read)
    monkeypatch.setattr(analyzer, "TAGE", None)
    monkeypatch.setattr(analyzer, "STATE_PATH", tmp_path / "missing.json")
    output = tmp_path / "summary.txt"
    assert analyzer.main(["--archiv", str(archive), "--ausgabe", str(output), "--leise"]) == 0
    assert opened == [valid]
    assert "Anzahl Berichte: 1" in output.read_text(encoding="utf-8")


def test_removed_selector_arguments_are_rejected():
    script = REPO_ROOT / "auswerte_detailberichte.py"
    for selector in ("--alle", "--tage"):
        result = subprocess.run([sys.executable, str(script), selector], capture_output=True, text=True)
        assert result.returncode == 2
        assert selector in result.stderr
