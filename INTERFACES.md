# Marathon – Schnittstellenprotokoll

Stand: 2026-10-09 · gültig für die Versionen in Abschnitt 1

Dieses Protokoll beschreibt alles, was zwischen Marathon und den Workern ausgetauscht wird. Es ersetzt das Hochladen der gesamten Codebase: Jeder Thread erhält diese Datei und nur den Code, der bearbeitet wird.

## 0. Regeln für KI-Instanzen

1. Diese Datei vollständig lesen, bevor Code geändert wird.
2. Abschnitt 3 ist der verbindliche Ist-Stand. Code, der eine Schnittstelle nutzt, hält sich genau daran.
3. Nur den hochgeladenen Code ändern. Was die andere Seite neu tun oder liefern muss, wird als Antrag in Abschnitt 4 eingetragen – nie als bereits umgesetzt angenommen.
4. Abschnitt 3 wird erst geändert, wenn alle betroffenen Seiten umgesetzt sind. Dann: Vertrag anpassen, Antrag auf `erledigt`, Zeile im Änderungsprotokoll (Abschnitt 5).
5. Neue Pflichtfelder oder geänderte Bedeutung eines Feldes erfordern eine neue `schema_version`. Marathon schreibt genau eine Version; Worker dürfen für den Übergang mehrere annehmen.
6. Nur Schnittstellen dokumentieren: Felder, Dateien, Ordner, Status, Reihenfolgen. Keine Interna, keine Begründungen, keine Historie im Vertragsteil.
7. Widerspricht der Code diesem Protokoll, nicht stillschweigend angleichen: Abweichung nennen und als Antrag eintragen.
8. Am Ende jedes Threads die vollständige, aktualisierte Datei zurückgeben, mit neuem Datum unter „Stand“ und aktuellen Versionen in Abschnitt 1.
9. Immer nur ein Thread ändert diese Datei. Arbeiten Threads parallel, hängen sie nur neue Anträge an.

## 1. Komponenten und Versionen

| Komponente | Version | Dateien |
|---|---|---|
| Marathon | 1.15.0 | `marathon.py`, `core/` |
| Marathon-Adapter (gemeinsamer Teil aller Worker-Adapter) | 1.1.1 | `marathon/marathon_adapter.py` |
| QC Marathon (QC-Adapter) | 2.1.1 | `marathon/qc_marathon.py`, `marathon/configs/` |
| QC Worker | 2.1.0 | `qc_worker.py` |
| AQC (Prüftools) | 0.3.1 | `aqc/`, `aqc/tools/` |
| Restore-Worker | nicht dokumentiert | – |
| Transcode-Worker | nicht dokumentiert | – |

Job-`schema_version`: **5** (alle Stufen). Der Marathon-Adapter nimmt `(5,)` an.

## 2. Begriffe

- **Freigabe**: Netzlaufwerk `root_path` aus Marathons `res/config.ini`. Alle Pfade in Jobs sind relativ zu `root_path` mit `/` als Trenner. Ausnahme: Transcode-`inputs` nach `ingest-master` sind vollständige Pfade.
- **`work_dir`**: Arbeitsordner von Marathon (Standard `.marathon`).
- **Stufen**: `Restore`, `Transcode`, `QC` (im Job), Ordnernamen `restore`, `transcode`, `qc`.
- **Worker-Name**: Rechnername; Zeichen `<>:"/\|?*` und Steuerzeichen werden zu `_`. Er ist Name der Heartbeat-Datei und des Ordners unter `laufend/`.

## 3. Vertrag (Ist-Stand)

### 3.1 Ordner

| Pfad | Inhalt | angelegt von |
|---|---|---|
| `<work_dir>/<stufe>/offen/` | neue Jobs | Marathon |
| `<work_dir>/<stufe>/laufend/<worker>/` | übernommene Jobs | Worker |
| `<work_dir>/<stufe>/fertig/` | Reports der Worker | Marathon |
| `<work_dir>/<stufe>/archiv/` | archivierte Jobs und Reports | Marathon |
| `<work_dir>/worker/` | Heartbeats, FFE-Referenzdateien | Marathon |
| `<Ziel>/<work_dir>[/<Kollektion>]/<stufe>/` mit `eingang/`, `ausgang/`, `archiv/` | Arbeitsordner je Kollektion; `eingang` nicht bei Restore; `/<Kollektion>` nur bei DEFA-Kollektionen | Marathon |
| `output_folder` = `…/<stufe>/ausgang/<job_id>` | Ergebnis eines Jobs | Marathon (vor dem Auslegen) |
| `<work_dir>/test/<stufe>/ausgang/<job_id>` | Ergebnis eines Test-Jobs (`output_folder`, siehe 3.11) | Marathon (vor dem Auslegen) |

### 3.2 Job-Übernahme

- Worker nehmen die erste Datei `*.json` in `offen/`, sortiert nach Dateiname, ohne Dateien mit Punkt am Anfang.
- Übernahme durch Umbenennen nach `laufend/<worker>/`. `FileNotFoundError` oder `PermissionError`: ein anderer Worker war schneller oder Marathon hat den Job zurückgezogen – nächste Datei versuchen.
- Die Job-Datei bleibt in `laufend/<worker>/`; Marathon archiviert sie nach dem Report.
- Marathon darf Jobs in `offen/` jederzeit zurückziehen (löschen). Unbekannte Dateien in `offen/` löscht Marathon.
- Ist eine Job-Datei weder in `offen/` noch in `laufend/` und liegt kein Report vor, legt Marathon nach 30 Minuten einen neuen Job an.
- Worker lesen Eingaben nur dort, wo der Job es angibt, und schreiben Ergebnisse nur in `output_folder`.

### 3.3 Job-Datei

Alle Stufen:

| Feld | Typ | Inhalt |
|---|---|---|
| `schema_version` | int | `5` |
| `job_id` | str | Dateiname ohne `.json`, Form `<Zeitstempel>__<clip_id>__<stufe><n>` |
| `stage` | str | `Restore`, `Transcode` oder `QC` |
| `clip_id` | str | EditShare-`clip_id` |
| `collection` | str | Kollektionsname |
| `identifier` | str | `001 Identifier` (bei DEFA die DEFA-ID) |
| `title` | str | `014 Title Original` |
| `clip_name` | str | `clip_name_with_extension` |
| `created_at` | str | ISO-Zeitstempel |
| `report_folder` | str | `<work_dir>/<stufe>/fertig` |
| `output_folder` | str | `…/<stufe>/ausgang/<job_id>` |
| `test` | object | nur bei Test-Jobs: `{"run": str, "number": int, "name": str}`; Worker ignorieren es |

Zusätzlich je Stufe:

| Stufe | Feld | Typ | Inhalt |
|---|---|---|---|
| Restore | `files` | list[str] | Dateinamen der Master |
| Restore | `hashes` | list[str] | Hashes der Master; eigene Sortierung, keine Zuordnung zu `files` über die Position |
| Transcode | `inputs` | list[str] | Masterdateien; nach `ingest-master` vollständige Pfade |
| Transcode | `proxy_name` | str | Dateiname, unter dem der Proxy im Ausgang liegen muss |
| Transcode | `ffe_tafel` | bool | Clip braucht die FFE-Filmtafel |
| Transcode | `ffe_reference_clips` | list[str] | alle FFE-Tafel-Clips, z. B. `.marathon/worker/FFE Filmerbe/2K_2_35.mov` |
| QC | `input` | str | Proxy im QC-Eingang |
| QC | `ffe_tafel` | bool | Clip braucht die FFE-Filmtafel |
| QC | `ffe_reference_image` | str | Referenzbild der Tafel, z. B. `.marathon/worker/FFE-Filmerbe-DEFA-Titel_Tafel.png` |

Maßgeblich sind die Werte beim Erstellen des Jobs. Worker ignorieren unbekannte Felder.

### 3.4 Ergebnis im `output_folder`

Dateien mit 0 Byte oder auf `.tmp`, `.part`, `.partial` zählen nicht. Dateinamen werden ohne Unterscheidung von Groß-/Kleinschreibung verglichen.

| Stufe | Erwartet |
|---|---|
| Restore | alle Dateien aus `files` |
| Transcode | genau ein Proxy mit dem Namen `proxy_name`; optional ein neuer Master `<DEFA-ID>__<Titel>.<Endung>` mit DEFA-ID = `identifier` (im Report als `new_master` gemeldet); Protokolldateien `.json`, `.txt`, `.log` erlaubt. Jede weitere Mediendatei zählt als zweiter Proxy. |
| QC | Prüfberichte; der Proxy (`input`) wird nur gelesen, nie verschoben oder geändert |

### 3.5 Report

- Datei `<report_folder>/<job_id>.json`, geschrieben unter einem temporären Namen, der nicht auf `.json` endet, dann umbenannt.

| Feld | Typ | Pflicht | Inhalt |
|---|---|---|---|
| `job_id` | str | ja | wie im Job |
| `status` | str | ja | `ok`, `failed` oder `rejected` (nur QC; bei anderen Stufen wie `failed`) |
| `result` | str | wenn nicht `ok` | Kurztext |
| `preset` | str/null | nein | Name des Presets bzw. Prüfplans |
| `new_master` | str/null | nein | nur Transcode: Dateiname des neuen Masters |

- Weitere Felder sind erlaubt und werden von Marathon ignoriert (der Marathon-Adapter schreibt `worker` und `versions`).
- Unlesbare oder ungültige Reports bleiben liegen; Marathon versucht sie im nächsten Zyklus erneut.
- Reports zu Jobs, die Marathon nicht mehr führt, werden ignoriert und archiviert.

### 3.6 Was Marathon mit dem Report macht

| Stufe / Status | Marathon |
|---|---|
| Restore `ok` | Master in den Transcode-Eingang (`…/transcode/eingang/<clip_id>/`), weiter an Transcode |
| Transcode `ok` | prüft Ausgang nach 3.4; neuer Master nach `[ingest] master_dir` (nie überschreiben, bei Konflikt Clip inaktiv „Neuer Master blockiert“); Proxy in den QC-Eingang; `preset` wird am Clip gespeichert; weiter an QC |
| QC `ok` | Proxy muss vorhanden und > 0 Byte sein; Auslieferung in den Zielordner (nie überschreiben), Master aus Restore löschen (Ingest-Master bleiben), EditShare-Feld `039d 10 Mbit Proxy Path` setzen; Clip bereit |
| QC `rejected` | Clip inaktiv „QC nicht bestanden“; Proxy bleibt im QC-Eingang |
| `failed` oder Prüfung nach 3.4 fehlgeschlagen | Versuch zählt; Ausgang wird gelöscht; neuer Job bis `max_job_attempts`, danach Clip inaktiv „Job endgültig fehlgeschlagen“ |

Danach archiviert Marathon Job-Datei und Report (`<job_id>.report.json`) in `<work_dir>/<stufe>/archiv/`. Reste im Ausgang werden bei `ok` und `rejected` nach `…/<stufe>/archiv/<job_id>.ausgang` verschoben. Ausnahme QC: Enthält der Ausgang genau eine Datei `*.aqc.json` und sonst nichts, wird sie als `<work_dir>/qc/archiv/<job_id>.aqc.json` archiviert und der leere Ausgang entfernt.

### 3.7 Heartbeat

- Datei `<work_dir>/worker/<worker>.json`, mindestens einmal pro Minute neu geschrieben, über temporären Namen und Umbenennen.

| Feld | Typ | Inhalt |
|---|---|---|
| `worker` | str | Worker-Name |
| `stage` | str | `Restore`, `Transcode` oder `QC` |
| `host` | str | Rechnername |
| `job_id` | str/null | laufender Job |
| `beat` | str | muss sich bei jedem Schreiben ändern |

- Weitere Felder sind erlaubt (der Marathon-Adapter schreibt `instance` und `versions`).
- Marathon meldet im Bericht: Worker ohne Änderung länger als `worker_timeout_minutes`, Worker mit anderem Job als erwartet, Jobs länger als `max_job_hours`. Jobs werden dabei nicht automatisch zurückgeholt.
- `delete-folder` ist gesperrt, solange ein Heartbeat jünger als `worker_timeout_minutes` ist, einen `job_id` meldet oder Jobs in `laufend/` ohne Report liegen.

### 3.8 FFE-Referenzdateien

- `<work_dir>/worker/<reference_image>` (Standard `FFE-Filmerbe-DEFA-Titel_Tafel.png`) und alle `.mov` in `<work_dir>/worker/<reference_clip_dir>/` (Standard `FFE Filmerbe`).
- Marathon spiegelt sie in jedem Zyklus aus `res/`. Worker lesen sie nur und schreiben in `<work_dir>/worker/` ausschließlich ihren Heartbeat.

### 3.9 Marathon-Adapter (gemeinsamer Teil)

- Wird unverändert in jeden Worker kopiert. Änderungen nur in der Referenzkopie, mit neuer `app_version`, eingetragen in Abschnitt 1 und 5.
- Schnittstelle für Stufen-Adapter:
  - `Settings(root_path, work_dir, stage, poll_seconds, heartbeat_seconds, log_path, versions)`
  - `run(settings, run_job)`; `run_job(job, output_folder, log_path)` liefert `JobReport(status, result, preset)`
  - Hilfen: `share_path(relative)`, `log(message)` (Konsole mit Uhrzeit und Log), `status(message)` (Laufzeile nur in der Konsole, die nächste Ausgabe ersetzt sie), `worker_name()`
- Der Adapter prüft vor `run_job`: `schema_version`, `job_id` = Dateiname, `stage`, `output_folder` und `report_folder` vorhanden. Sonst Report `failed` „Job ungültig“.
- Ausnahmen in `run_job` werden zum Report `failed`.
- Ein zweiter Start mit demselben Worker-Namen bricht ab, solange dessen Heartbeat aktualisiert wird. Beim Start werden eigene Jobs in `laufend/` ohne Report als `failed` gemeldet.
- `share_path` lehnt leere, absolute und `..`-Pfade ab.

### 3.10 Stufen-Worker

**QC (QC Marathon 2.1.1)**

- Prüfplan `proxy_standard`: `stream_specs(video_1080p)`, `stream_specs(audio_aac_stereo)`, `digital_silence(keine_stille)`.
- Bei `ffe_tafel: true` zusätzlich `ffe_tafel`: `reference_frame(FFE_tafel_start_ok)` und `reference_frame(FFE_tafel_ende_not_ok)` mit `must_fail`; Referenzbild aus `ffe_reference_image`.
- `preset`: `proxy_standard` bzw. `proxy_standard+ffe_tafel`.
- Status: alle Tools bestanden `ok`, ein Tool nicht bestanden `rejected`, sonst `failed`.
- `failed` „Job ungültig“ bei fehlendem `input`, fehlendem oder nicht booleschem `ffe_tafel`, oder `ffe_tafel: true` ohne `ffe_reference_image`.
- Ausgang: je Clip `<clip>.aqc.json` (Prüfbericht, Aufbau 3.12).

**Restore, Transcode**: nicht dokumentiert – beim ersten Thread zum jeweiligen Worker ergänzen.

### 3.11 Test-Jobs

- Test-Jobs sind Jobs nach 3.2 bis 3.5 in denselben Ordnern `offen/`, `laufend/`, `fertig/`; Worker behandeln sie wie jeden Job.
- Abweichend: `output_folder` = `<work_dir>/test/<stufe>/ausgang/<job_id>`; zusätzliches Feld `test`; alle übrigen Felder können vom Testplan ersetzt sein, auch durch ungültige Werte.
- Marathon wertet Reports von Test-Jobs nicht nach 3.6 aus: Job-Datei und Report werden archiviert, der Ausgang bleibt liegen, kein neuer Job bei `failed`. Für den Testbericht liest Marathon den QC-Prüfbericht (3.12) aus dem Ausgang.
- Der Job-Zyklus lässt Test-Jobs in `offen/` und `laufend/` sowie ihre Reports liegen; der Test-Modus lässt Produktions-Jobs und ihre Reports liegen.

### 3.12 QC-Prüfbericht

- Datei `<clip>.aqc.json` im `output_folder` eines QC-Jobs (3.10). Marathon liest sie nur, für Detail- und Testbericht bei `rejected`; der Ablauf nach 3.6 hängt nicht von ihr ab.
- Gelesene Felder:

| Feld | Typ | Inhalt |
|---|---|---|
| `tools` | list | je Prüftool ein Objekt |
| `tools[].label` | str | Tool und Prüfplan-Schlüssel, z. B. `stream_specs(video_1080p)`; ersatzweise `tools[].name` |
| `tools[].status` | str | `BESTANDEN`; jeder andere Wert gilt als nicht bestanden |
| `tools[].message` | str/null | Grund, wenn `failures` leer ist |
| `tools[].failures` | list | je Abweichung `criterion`, `expected`, `actual`, `stream`, `channel`, `tc` (jeweils str/int/null) |
| `tools[].info` | list of str | Hinweise; ein Eintrag mit `Ist-Werte:` enthält die gemessenen Werte, z. B. `Stream 0 Ist-Werte: width=1920, …` |

- Weitere Felder werden ignoriert. Fehlt die Datei, ist sie unlesbar oder fehlt `tools`, meldet Marathon „Prüfbericht fehlt“.

## 4. Anträge

Vorlage:

~~~text
### CR-<nnn> <Kurztitel>
- Von → an: <Komponente> → <Komponente>
- Stand: offen | umgesetzt in <Komponente> | erledigt
- Inhalt: <was genau sich ändert: Felder, Dateien, Status, Verhalten>
- Version: <neue schema_version / Komponentenversion oder „keine“>
- Übergang: <ob alte und neue Version parallel funktionieren müssen>
~~~

### CR-001 Transcode-Fähigkeit des Marathon-Adapters

- Von → an: künftiger Transcode-Adapter → Marathon-Adapter
- Stand: offen
- Inhalt: `share_path` muss vollständige Pfade annehmen (Transcode-`inputs` nach `ingest-master`). `JobReport` braucht ein optionales Feld `new_master`, das in den Report geschrieben wird.
- Version: Marathon-Adapter 1.2.0; keine neue `schema_version`; Marathon unverändert
- Übergang: bestehende QC-Worker bleiben ohne Änderung lauffähig

### CR-002 Test-Jobs

- Von → an: Marathon → alle Worker
- Stand: erledigt
- Inhalt: Test-Jobs nach 3.11 (Ordner `<work_dir>/test/<stufe>/ausgang/<job_id>`, Feld `test`, keine Auswertung nach 3.6). Worker brauchen keine Änderung, sofern sie 3.2 einhalten (Ergebnisse nur in `output_folder`, unbekannte Felder ignorieren).
- Version: Marathon 1.11.0; keine neue `schema_version`
- Übergang: bestehende Worker bleiben unverändert lauffähig

### CR-003 QC-Prüfbericht für Berichte

- Von → an: Marathon → QC Worker
- Stand: erledigt
- Inhalt: Marathon liest den bestehenden Prüfbericht `<clip>.aqc.json` nach 3.12 (Detail- und Testbericht) und archiviert einen QC-Ausgang, der nur den Prüfbericht enthält, als `<work_dir>/qc/archiv/<job_id>.aqc.json` (3.6). Der QC Worker braucht keine Änderung; die Felder aus 3.12 dürfen nur mit neuer Version und Eintrag in Abschnitt 5 umbenannt oder entfernt werden.
- Version: Marathon 1.14.0; keine neue `schema_version`
- Übergang: bestehende Worker bleiben unverändert lauffähig

## 5. Änderungsprotokoll

| Datum | Antrag | Änderung |
|---|---|---|
| 2026-10-09 | – | Marathon 1.15.0: Befehl `retry-qc` gibt Clips mit „QC nicht bestanden“ zur QC-Neuprüfung frei; Schnittstelle unverändert |
| 2026-10-09 | CR-003 | Marathon 1.14.0: liest den QC-Prüfbericht (3.12) für Detail- und Testbericht; QC-Ausgang mit nur dem Prüfbericht wird als `<work_dir>/qc/archiv/<job_id>.aqc.json` archiviert (3.6); Worker unverändert |
| 2026-10-09 | – | QC Marathon 2.1.1: Prüfbericht in Konsole und Log ab `<work_dir>` gekürzt; Schnittstelle unverändert |
| 2026-10-09 | – | Worker: detaillierte Konsolenausgaben; Marathon-Adapter 1.1.1 mit Hilfe `status(message)`, QC Marathon 2.1.0, QC Worker 2.1.0, AQC 0.3.1; Schnittstelle zu Marathon unverändert |
| 2026-10-09 | – | Marathon 1.12.0: Befehl `test-qc` erzeugt Test-Jobs nach 3.11 aus der JSON; Schnittstelle unverändert |
| 2026-10-09 | CR-002 | Marathon 1.11.0: Test-Modus mit Test-Jobs (3.1, 3.3 Feld `test`, 3.11); Worker unverändert |
| 2026-10-09 | – | QC: Prüftools in `aqc/tools`, Plan-Schlüssel `tool`, Job-`schema_version` 5, FFE-Entscheidung und Referenzbild aus dem Job; Marathon unverändert |
| 2026-10-09 | – | Protokoll angelegt aus Marathon 1.10.0, Marathon-Adapter 1.1.0, QC Marathon 2.0.0, QC Worker 2.0.0, AQC 0.3.0 |
