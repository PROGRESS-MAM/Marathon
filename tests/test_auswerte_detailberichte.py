from datetime import date, timedelta
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import auswerte_detailberichte as analyzer


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


def test_parses_failure_blocks_and_categories():
    cases = analyzer.parse_cases(REPORT, "transcode")
    assert len(cases) == 2
    assert cases[0].clip_id == "4711"
    assert cases[0].collection == "Demo"
    assert cases[0].category == "transcode_output_contract"
    assert cases[1].category == "worker_failed"

    qc_report = REPORT.replace("Detailbericht Transcode", "Detailbericht QC").replace(
        "Marathon: Transcode-Ausgang enthält 2 Proxy-Dateien statt einer",
        "AQC Fehler Kriterium Audio",
    )
    assert analyzer.parse_cases(qc_report, "qc")[0].category == "qc_rejected"
    assert analyzer.normalize_category_text("clip_id 4711 had 2 proxy files") == "clip_id <id> had <number> proxy files"


def test_transcode_rejected_uses_archived_output_candidate():
    text = REPORT.replace("#1  FAILED", "#1  REJECTED", 1)
    case = analyzer.parse_cases(text, "transcode")[0]
    path = analyzer.reconstructed_path(case)
    assert path.startswith("Kandidaten:")
    assert "/transcode/archiv/" in path
    assert case.job_id in path
    assert ".<outbox>" in path
    assert "/ausgang/" not in path


def test_transcode_failed_output_is_not_inferred():
    case = analyzer.parse_cases(REPORT, "transcode")[0]
    assert case.status == "FAILED"
    assert analyzer.reconstructed_path(case) == "Pfad nicht ableitbar"


def test_qc_rejected_lists_flat_report_and_archived_output_candidates():
    text = REPORT.replace("Detailbericht Transcode", "Detailbericht QC").replace("#1  FAILED", "#1  REJECTED", 1)
    case = analyzer.parse_cases(text, "qc")[0]
    path = analyzer.reconstructed_path(case)
    assert path.startswith("Kandidaten:")
    assert f"/qc/archiv/{case.job_id}.aqc.json" in path
    assert f"/qc/archiv/{case.job_id}.<outbox>" in path
    formatted = analyzer.format_case_path(path)
    assert formatted.startswith("Kandidaten: `")
    assert "; `" in formatted


def test_blockiert_transcode_uses_archived_output_candidate():
    text = REPORT.replace("#1  FAILED", "#1  BLOCKIERT", 1)
    case = analyzer.parse_cases(text, "transcode")[0]
    assert "/transcode/archiv/" in analyzer.reconstructed_path(case)


def test_report_ablagge_is_preferred_and_jobs_are_deduplicated(tmp_path):
    first_text = REPORT.replace(
        "    Ablage   Demo/work/Transcode/archiv/20261103T091200123456__4712__transcode1.zip\n",
        "",
    )
    first = analyzer.read_report(write_report(tmp_path, "details_transcode_2026-11-03_09-00-00-000000.txt", first_text))
    second_text = REPORT.replace("Demo/work/Transcode/archiv/", "chosen/archive/")
    second = analyzer.read_report(write_report(tmp_path, "details_transcode_2026-11-03_10-00-00-000000.txt", second_text))
    cases = analyzer.collect_cases([first, second])
    rejected = next(case for case in cases if case.status == "REJECTED")
    assert len(cases) == 2
    assert rejected.path.startswith("chosen/archive/")


def test_days_filter_prefers_filename_and_falls_back_to_period(tmp_path):
    today = date.today()
    recent = today - timedelta(days=2)
    old = today - timedelta(days=4)
    recent_report = analyzer.read_report(write_report(tmp_path, f"details_transcode_{recent}_09-00-00-000000.txt"))
    old_report = analyzer.read_report(write_report(tmp_path, f"details_transcode_{old}_09-00-00-000000.txt"))
    assert analyzer.date_in_window(recent_report, 3, today)
    assert not analyzer.date_in_window(old_report, 3, today)
    fallback_path = tmp_path / "details_transcode_no-date.txt"
    fallback = analyzer.read_report(write_report(tmp_path, fallback_path.name, REPORT.replace("2026-11-03", today.isoformat())))
    assert fallback.report_date == today


def test_cli_all_and_days_dedupe_and_write_summary(tmp_path):
    archive = tmp_path / "archive"
    today = date.today()
    write_report(archive, f"details_transcode_{today}_09-00-00-000000.txt")
    write_report(archive, f"details_transcode_{today}_10-00-00-000000.txt")
    script = Path(__file__).resolve().parents[1] / "auswerte_detailberichte.py"
    for selector_args, label in ((("--alle",), "alle"), (("--tage", "3"), "tage")):
        output = tmp_path / f"summary_{label}.md"
        result = subprocess.run(
            [sys.executable, str(script), *selector_args, "--archiv", str(archive), "--ausgabe", str(output)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        content = output.read_text(encoding="utf-8")
        assert "Fehlerfälle gesamt: 2" in content
        assert "transcode_output_contract" in content
        assert "worker_failed" in content
        assert "Demo/work/Transcode/archiv/" in content
        assert "Pfad nicht ableitbar" in content


def test_cli_labels_qc_archive_options_as_candidates(tmp_path):
    archive = tmp_path / "archive"
    qc_report = REPORT.replace("Detailbericht Transcode", "Detailbericht QC").replace("#1  FAILED", "#1  REJECTED", 1)
    today = date.today()
    write_report(archive, f"details_qc_{today}_09-00-00-000000.txt", qc_report)
    script = Path(__file__).resolve().parents[1] / "auswerte_detailberichte.py"
    output = tmp_path / "summary.md"
    result = subprocess.run(
        [sys.executable, str(script), "--alle", "--archiv", str(archive), "--ausgabe", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    assert "Kandidaten:" in content
    assert ".aqc.json" in content
    assert ".<outbox>" in content


def test_cli_requires_exactly_one_selector(tmp_path):
    script = Path(__file__).resolve().parents[1] / "auswerte_detailberichte.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "one of the arguments --alle --tage is required" in result.stderr
