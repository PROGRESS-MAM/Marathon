# Findings: Detailberichte und Dateipfade

## 1. Detailbericht parsen

**Erzeugung:** `core/details.py` (`_entry_block`, `_render`, `_write_stage`, `write_details`) formatiert `state/journal_<stage>.jsonl` als `Marathon 1.18.3 · Detailbericht <Stufe>`. Danach folgen Zeitraum/Zähler, `Details: N` und Blöcke `#N  <STATUS>  <Identifier + Titel>`. Faktenzeile: `clip_id · Kollektion · [Preset] · [Worker]`; Zeilenfelder: `Job`, `Zeit`, optional `Versuch`, `Ergebnis`, QC-`Fehler`/`Ist`/`Info`, optional `Ablage`. Leere Felder fehlen. Zeit ist auf Sekunden gekürzt und ohne Zeitzonenoffset; Identifier und Titel sind ungetrennt kombiniert.

**Parser:** Blockstart an `^#\d+\s+`, Status aus `FAILED|REJECTED|BLOCKIERT`; indizierte Werte anhand ihrer Labels lesen, nicht per Zeilenposition. `clip_id` und `Job` sind die Schlüssel. Fakten an ` · ` teilen, soweit Inhalte diese Trennzeichen nicht selbst enthalten. Es gibt keine verlässliche `Fehler:`-Zeile: Ursache steht als freier Text unter `Ergebnis`; QC-Funde haben Label `Fehler` (ohne Doppelpunkt). In Transcode erscheinen `REJECTED`-Blöcke, aber `_counts()` zählt sie weder als eigene Zeile noch als `Fehlgeschlagen`.

Synthetisches Beispiel (zeigt auch die fehlende Transcode-REJECTED-Zählung):

```text
Marathon 1.18.3 · Detailbericht Transcode
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
    Ablage   Demo/work/Demo/transcode/archiv/<job_id>.ausgang
```

Weitere Detailtypen: `details_restore`, `details_qc`, `details_transcode` (`core/constants.py: stages`). QC kann AQC-Kriterium/Soll/Ist/Stream/Kanal/TC oder `Prüfbericht fehlt` ausgeben (`core/details.py: qc_findings`, `qc_rows`). Restore nennt z. B. fehlende Datei, Größenabweichung oder doppelte Einträge (`core/restore.py: _file_problem`, `_evaluate`); Restore-Fehlercodes: `INTERFACES.md` §3.12. Separate Textformate sind `<kind>_<Zeit>.txt` und Fehlerlisten `reports/errors/` (u. a. `index_*_errors.txt`, `*_ffe_uneindeutig.txt`; `core/report.py: report`, `core/index.py: update_index`, `core/util.py: write_lists`, `format_errors`).

**Kategorienvorschlag:** `worker_failed`, `transcode_output_contract` (Proxy-Anzahl/-Name, Mastername), `qc_rejected` (Kriterium), `delivery_or_master_blocked` (Kollision/Ablage/Master), `restore_incomplete` (Datei/Report/Größe/Tape-Code). In einer normalisierten Kopie Job-ID/Zeitstempel, Clip-ID, Versuch, Mengen/Bytes, Stream/Kanal/TC entfernen; Rohwerte und stabile Fehlercodes für Nachverfolgung bewahren.

## 2. Pfad je Fehlerfall

Der Bericht enthält keinen allgemeinen Clip-Quellpfad. `Ablage` ist optional und bezeichnet archivierten **Job-Ausgang**: `failed` löscht den Rest-Ausgang, also meist keine Ablage; `rejected`/`blockiert` archivieren ihn (`core/jobs.py: _finish_output`, `_apply_report`). Ausnahme QC: einzelnes `.aqc.json` wird flach `<work_dir>/qc/archiv/<job_id>.aqc.json` abgelegt.

**Regeln:** `core/layout.py: final_folder`, `_work_folder`, `stage_folder`, `job_folder`, `master_folder`, `qc_inbox`, `share_path` bauen aus Laufzeit-`root_path` den Pfad `<final_folder>/<work_dir>[/<sanitisierte Kollektion> bei DEFA]/<Stufe>`. Restore-Pool: `<root>/<work_dir>/restore/`; Ausgang `ausgang/<job_id>/<Clipname-Ordner>` (Duplikate `__2` usw.; `core/restore.py: _create`, `clip_folders`). Transcode/QC: je Kollektion `<Stufe>/{eingang,ausgang,archiv}`; Job-Ausgang `.../<Stufe>/ausgang/<job_id>` (`core/jobs.py: _create_job`). Restore-Master: `.../transcode/eingang/<clip_id>` (`core/restore.py: _evaluate`); Transcode-Proxy: `.../qc/eingang/<konfigurierter Proxyname>`; QC-Auslieferung: finaler Kollektion-Ordner (`core/jobs.py: _take_outputs`). Neuer Master: konfiguriertes `master_dir`, optional `manuelle Überprüfung/<Clipname>/{neu,alt}` (`core/masters.py: new_master_target`, `review_folder`, `archive_old_master`).

Aus Berichtstitel, Kollektion, `clip_id` und `Job` sind Stufe, Job-Ausgang und Restore-Master-Eingang nach Auflösen der Konfiguration ableitbar. Proxyname erfordert zusätzlich Veritone-ID/`proxy_name`; Restore-Unterordner den tatsächlichen Clip-Dateinamen. Ursprungs-Master/Tape-Dateien und aktueller Ablageort sind nicht eindeutig ableitbar; dafür Index-/State-Daten oder Share-Abgleich nötig. `root_path`, `work_dir`, `defa_dir`, `defa_marker`, `master_dir` und Proxy-Muster stehen in Laufzeit-`res/config.ini` (`core/config.py: config_schema`).

## Archivnamen / offene Punkte

`core/util.py: file_stamp` erzeugt `details_<stage>_YYYY-MM-DD_HH-MM-SS-ffffff.txt` in `reports/`; `core/details.py: _write_stage` verschiebt das Journal nach `state/journal/details_<stage>_<stamp>.jsonl`. Im geprüften Code gibt es kein `reports/archive/` und kein Archivieren alter Detailberichte. Der Bericht ist kein versioniertes Parsingformat: `Ablage` bevorzugen; sonst Pfade nur als konfigurationsabhängige Kandidaten behandeln.
