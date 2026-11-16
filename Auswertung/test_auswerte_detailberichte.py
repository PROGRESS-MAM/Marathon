import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auswerte_detailberichte as ad


def make_case(clip_id, collection, result, job_id="same-job"):
    return ad.Case(
        status="FAILED",
        title=f"Titel {clip_id}",
        rows={"job": [job_id], "ergebnis": [result]},
        clip_id=clip_id,
        collection=collection,
    )


def make_report(path, cases):
    return ad.Report(Path(path), cases, date(2026, 10, 25), date(2026, 10, 26), date(2026, 10, 26))


def restore_text(blocks):
    lines = [
        "Marathon 1.17.0 · Detailbericht Restore",
        "Zeitraum        2026-10-25 09:00:05 – 2026-10-26 09:00:05",
        "Details: 2",
        "",
    ]
    for number, (clip_id, collection, result) in enumerate(blocks, 1):
        lines.extend([
            f"#{number}  FAILED  PROB{number:04d} Synthetischer Fall {number}",
            f"    clip_id {clip_id} · Kollektion {collection} · Worker Test-Restore",
            "    Job      20261025T002140324290__57_restore",
            "    Zeit     2026-10-25 18:26:54",
            "    Versuch  1 von 1 (endgültig)",
            f"    Ergebnis {result}",
            "",
        ])
    return "\n".join(lines)


def test_normalize_argv():
    assert ad.normalize_argv(["--qc", "--5"]) == ["--qc", "--n", "5"]
    assert ad.normalize_argv(["--qc", "--n", "3"]) == ["--qc", "--n", "3"]


def test_discover_reports_filters_type(tmp_path):
    qc = tmp_path / "details_qc_2026-10-01_09-00-00-000000.txt"
    for name in [qc.name, "details_restore_2026-10-01_09-00-00-000000.txt", "notes.txt"]:
        (tmp_path / name).write_text("sample", encoding="utf-8")
    paths, warning = ad.discover_reports(tmp_path, "qc")
    assert warning is None
    assert paths == [qc]


def test_select_latest():
    paths = [Path(f"details_qc_2026-10-{day:02d}_09-00-00-000000.txt") for day in (1, 2, 3)]
    assert ad.select_latest(paths, 2) == paths[-2:]
    assert ad.select_latest(paths, None) == paths


def test_filter_collection_casefold_substring():
    cases = [make_case("1", "DEFA Dokumentation", "Fehler A"), make_case("2", "DEFA Animation", "Fehler B")]
    assert ad.filter_collection(cases, "dokumentation") == cases[:1]
    assert ad.filter_collection(cases, None) == cases


def test_collect_cases_dedup_by_clip():
    first = make_report("details_restore_2026-10-25.txt", [make_case("clip-1", "LYNXarchive", "alt")])
    later = make_report("details_restore_2026-10-26.txt", [make_case("clip-1", "DEFA Dokumentation", "neu")])
    three = make_report("details_restore_2026-10-27.txt", [
        make_case("clip-2", "DEFA Dokumentation", "eins"),
        make_case("clip-3", "DEFA Dokumentation", "zwei"),
        make_case("clip-4", "DEFA Dokumentation", "drei"),
    ])
    cases = ad.collect_cases([first, later, three], {})
    assert len(cases) == 4
    assert next(case for case in cases if case.clip_id == "clip-1").result == "neu"
    assert {case.clip_id for case in cases} == {"clip-1", "clip-2", "clip-3", "clip-4"}


def test_default_output_name():
    assert ad.default_output_name("restore", None) == "auswertung_restore.txt"
    assert ad.default_output_name("qc", "DEFA Dokumentation") == "auswertung_qc_DEFA_Dokumentation.txt"


def test_cli_errors(monkeypatch, tmp_path):
    monkeypatch.setattr(ad, "state_path", tmp_path / "missing-state.json")
    for argv in [[], ["--qc", "--restore"], ["--qc", "--n", "0"], ["--qc", "--kollektion", " "]]:
        try:
            ad.main(argv)
        except SystemExit as error:
            assert error.code == 2
        else:
            raise AssertionError(f"expected argparse error for {argv!r}")


def test_main_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(ad, "state_path", tmp_path / "missing-state.json")
    archive = tmp_path / "archive"
    archive.mkdir()
    old_report = archive / "details_restore_2026-10-25_09-00-00-000000.txt"
    old_report.write_text(restore_text([
        ("clip-1", "LYNXarchive", "TAPE_DEFECT: Band A"),
        ("clip-2", "DEFA Dokumentation", "TAPE_DEFECT: Band B"),
    ]), encoding="utf-8")
    new_report = archive / "details_restore_2026-10-26_09-00-00-000000.txt"
    new_report.write_text(restore_text([("clip-2", "DEFA Dokumentation", "TAPE_DEFECT: aktualisiert")]), encoding="utf-8")

    out = tmp_path / "all.txt"
    assert ad.main(["--restore", "--archiv", str(archive), "--ausgabe", str(out), "--leise"]) == 0
    text = out.read_text(encoding="utf-8")
    assert "· Restore" in text
    assert "Kollektion: alle" in text
    assert "Gesamtzahl Fälle: 2" in text

    filtered = tmp_path / "filtered.txt"
    assert ad.main(["--restore", "--archiv", str(archive), "--ausgabe", str(filtered), "--kollektion", "defa", "--leise"]) == 0
    filtered_text = filtered.read_text(encoding="utf-8")
    assert "Kollektion: defa" in filtered_text
    assert "Gesamtzahl Fälle: 1" in filtered_text

    latest = tmp_path / "latest.txt"
    assert ad.main(["--restore", "--archiv", str(archive), "--ausgabe", str(latest), "--1", "--leise"]) == 0
    assert "Anzahl Berichte: 1" in latest.read_text(encoding="utf-8")


def parse_synthetic_case(status, title, rows):
    lines = [
        "Marathon 1.17.0 · Detailbericht",
        "Zeitraum        2026-10-25 09:00:05 – 2026-10-26 09:00:05",
        "Details: 1",
        "",
        f"#1  {status}  {title}",
        "    clip_id test-clip · Kollektion DEFA Test · Worker Test",
        "    Job      20261025T002140324290__57_test",
    ]
    lines.extend(f"    {label:<8} {value}" for label, value in rows)
    return ad.parse_cases("\n".join(lines))[0]


def test_categories_restore():
    cases = [
        parse_synthetic_case("FAILED", "Restore A", [("Ergebnis", "Source PacA01.5FC75FC79CD5A.mxf: TAPE_DEFECT: Band LS2037L8 meldet Medienfehler (früherer Ark-Job)")]),
        parse_synthetic_case("FAILED", "Restore B", [("Ergebnis", "Q6UJ9A004XA01.5FCE5FCEBA4AA.mxf: TAPE_DEFECT: Media-Alarm auf LS2037L8, Laufwerk 0 (restorejob_b2P5P1)")]),
    ]
    assert [ad.categories(case, "restore") for case in cases] == [
        ["TAPE_DEFECT: Band <band> meldet Medienfehler"],
        ["TAPE_DEFECT: Media-Alarm auf <band>, Laufwerk #"],
    ]


def test_categories_qc_rejected():
    case = parse_synthetic_case("REJECTED", "QC rejected", [
        ("Ergebnis", "67640789_1918900_10Mbit.mp4: nicht bestanden (2 von 3 Tools): stream_specs(audio_aac_stereo), digital_silence(keine_stille)"),
        ("Fehler", "stream_specs(audio_aac_stereo): codec erwartet aac, gefunden ac3 (Stream 1)"),
        ("Fehler", "stream_specs(audio_aac_stereo): channels erwartet 2, gefunden 5 (Stream 1)"),
        ("Fehler", "digital_silence(keine_stille): min_active erwartet >= 1% Ton über -60 dBFS, gefunden 0.00% Ton (Stream 1, Kanal 2)"),
    ])
    assert ad.categories(case, "qc") == [
        "stream_specs(audio_aac_stereo) · codec",
        "stream_specs(audio_aac_stereo) · channels",
        "digital_silence(keine_stille) · min_active",
    ]


def test_categories_qc_failed():
    rows = [
        ("Ergebnis", "50742356_415224_10Mbit.mp4: nicht ausführbar: 50742356_415224_10Mbit.mp4: Start-TC '106:57:29:23' der Datei ist ungültig."),
    ]
    start_tc = parse_synthetic_case("FAILED", "Start TC", rows)
    ffprobe_results = [
        r"50491069_420893_10Mbit.mp4: nicht ausführbar: 50491069_420893_10Mbit.mp4: ffprobe fehlgeschlagen (Code 1): [mov,mp4,m4a,3gp,3g2,mj2 @ 0000021125a880c0] moov atom not found / \\10.0.77.11\Ablage KI Proxy_1\Proxy 10 Mbit\DEFA\.marathon\DEFA Spielfilme\qc\eingang\50491069_420893_10Mbit.mp4: Invalid data found when processing input",
        r"50758874_422976_10Mbit.mp4: nicht ausführbar: 50758874_422976_10Mbit.mp4: ffprobe fehlgeschlagen (Code 1): [mov,mp4,m4a,3gp,3g2,mj2 @ 00000196e4a184c0] moov atom not found / \\10.0.77.11\Ablage KI Proxy_1\Proxy 10 Mbit\DEFA\.marathon\DEFA Spielfilme\qc\eingang\50758874_422976_10Mbit.mp4: Invalid data found when processing input",
    ]
    ffprobe_cases = [parse_synthetic_case("FAILED", f"ffprobe {index}", [("Ergebnis", result)]) for index, result in enumerate(ffprobe_results)]
    expected = "nicht ausführbar: ffprobe fehlgeschlagen: moov atom not found / <pfad>: Invalid data found when processing input"
    assert ad.categories(start_tc, "qc") == ["nicht ausführbar: Start-TC '<tc>' der Datei ist ungültig"]
    assert [ad.categories(case, "qc") for case in ffprobe_cases] == [[expected], [expected]]


def test_categories_transcode_unchanged():
    case = parse_synthetic_case("FAILED", "Transcode", [
        ("Ergebnis", "Manuelle Prüfung: Proxy fix:audio: Ton: Kanal 3 hörbar und nicht doppelt zu Kanal 1/2 (Ähnlichkeit 0.95)"),
    ])
    assert ad.categories(case, "transcode") == ["Proxy fix:audio: Ton: Kanal # hörbar und nicht doppelt zu Kanal #/#"]
