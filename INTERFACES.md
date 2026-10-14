# Marathon – Schnittstellenprotokoll

Stand: 2026-10-14 · gültig für die Versionen in Abschnitt 1

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
10. Wer den Fahrplan (Abschnitt 6) abarbeitet, hält die Reihenfolge ein, beginnt einen Schritt erst, wenn seine Voraussetzungen erfüllt sind, und trägt jeden abgeschlossenen Schritt dort mit Datum und Version ein.

## 1. Komponenten und Versionen

| Komponente | Version | Dateien |
|---|---|---|
| Marathon | 1.16.0 | `marathon.py`, `core/` |
| Marathon-Adapter (gemeinsamer Teil aller Worker-Adapter) | 1.2.0 (Referenzkopie in AQC; QC Marathon 2.2.0 enthält noch 1.1.1, ES-Restore noch keine Kopie) | `marathon/marathon_adapter.py` |
| QC Marathon (QC-Adapter) | 2.2.0 | `marathon/qc_marathon.py`, `marathon/configs/` |
| QC Worker | 2.1.0 | `qc_worker.py` |
| AQC (Prüftools) | 0.4.0 | `aqc/`, `aqc/tools/` |
| Restore-Worker (ES-Restore) | 0.2.1 (Restorer 0.2.1, Restore Marathon 0.1.1) | `restorer/`, `marathon/restore_marathon.py`; läuft mit Marathon erst nach CR-006 bis CR-011 |
| Transcode-Worker | nicht dokumentiert | – |

Job-`schema_version`: Marathon 1.16.0 schreibt **5** (alle Stufen). Der Marathon-Adapter 1.2.0 nimmt nur `(6,)` an; Marathon schreibt 6 ab Fahrplan-Schritt 3. Keine Abwärtskompatibilität: alle Komponenten werden gemeinsam auf 6 umgestellt.

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

**QC (QC Marathon 2.2.0)**

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
- Stand: umgesetzt in Marathon-Adapter 1.2.0
- Inhalt:
  - Regel für alle Worker: Marathon benennt Pfade, der Worker benutzt sie ohne weitere Prüfung. `share_path(path)` hängt einen relativen Pfad (`/` als Trenner) an `root_path` an und gibt einen vollständigen Pfad (Laufwerk oder UNC) unverändert zurück; `..` ist erlaubt. Nur ein leerer Pfad ergibt `ValueError`. Zugriff auf die Pfade stellt der Betrieb sicher.
  - `JobReport` hat das optionale Feld `new_master`; ist es gesetzt, steht es im Report.
- Version: Marathon-Adapter 1.2.0; keine neue `schema_version`; Marathon unverändert
- Übergang: keiner; gilt mit Adapter 1.2.0 für QC, Restore und Transcode

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

### CR-004 Run-Status ohne Testlauf-Angaben

- Von → an: Bedienung → Marathon
- Stand: offen
- Inhalt: Beim Start mit Befehl `run` enthält die Statuszeile keine Angaben zum letzten Test-Lauf mehr. Bisher: `Status: Job-Schleife läuft; Test-Modus aus (Test-Lauf 20261009T140942525261 abgeschlossen: 3041/3041 fertig (abgebrochen 2957, ok 44, rejected 40)); Auto-Bericht aus.` Künftig: `Status: Job-Schleife läuft; Test-Modus aus; Auto-Bericht aus.` Nur Konsolenausgabe; Schnittstelle unverändert.
- Version: Marathon 1.16.1; keine neue `schema_version`
- Übergang: Worker unverändert

### CR-005 AQC-Konsolenpfade gekürzt

- Von → an: Bedienung → AQC
- Stand: offen
- Inhalt: Alle Pfade in den Konsolenausgaben (`print`) von AQC werden ab einschließlich `.marathon` gekürzt, z. B. `.marathon/qc/…`. Nur Konsolenausgabe; Prüfbericht (3.12) und Schnittstelle unverändert.
- Version: AQC 0.4.1; keine neue `schema_version`
- Übergang: Marathon und QC Marathon unverändert

### CR-006 Restore-Sammeljobs mit Clip-Ordnern und Teilergebnis

- Von → an: Marathon → Restore-Worker (ES-Restore), Marathon-Adapter
- Stand: umgesetzt in Restore-Worker 0.2.1 und Marathon-Adapter 1.2.0; offen in Marathon
- Inhalt:
  - Ein Restore-Job enthält Dateien mehrerer Clips; Marathon fasst sie nach Band zusammen.
  - Job (3.3), Stufe Restore: `clip_id`, `collection`, `identifier`, `title`, `clip_name`, `files` und `hashes` entfallen. Neu `items` (list[object], mindestens ein Eintrag, je Datei ein Eintrag):

    | Feld | Typ | Pflicht | Inhalt |
    |---|---|---|---|
    | `clip_id` | str | ja | EditShare-`clip_id`; Einträge mit gleicher `clip_id` gehören zu einem Clip |
    | `clip_name` | str | ja | Name des Clip-Ordners im Ausgang |
    | `file` | str | ja | physischer Dateiname aus dem Userpath, kein Clip- oder Asset-Name |
    | `flow_hash` | str | ja | FLOW-Hash Version 2, Form `2:<hex>` |
    | `tape` | str | ja | Barcode des Bands |
    | `size` | int | ja | Dateigröße in Byte |

  - `job_id` bleibt der Dateiname ohne `.json`; die Form für Sammeljobs legt Marathon fest.
  - Ergebnis (3.4), Restore: je Eintrag `<output_folder>/<Clip-Ordner>/<file>`.
    - Clip-Ordner = `clip_name`; Zeichen `<>:"/\|?*` und Steuerzeichen werden zu `_`, Punkte und Leerzeichen am Ende entfallen.
    - Ergibt sich derselbe Clip-Ordner (ohne Unterscheidung von Groß-/Kleinschreibung) für verschiedene `clip_id` im selben Job, erhält der erste Clip den Namen ohne Zusatz, jeder weitere `<Clip-Ordner>__2`, `__3` … in der Reihenfolge des ersten Auftretens in `items`.
    - Dateinamen werden nie verändert. Eine Datei zählt nach den Regeln oben in 3.4 und nur, wenn ihre Größe `size` entspricht.
  - Report (3.5): zusätzliches Feld `items` (list[object]), jeder Job-Eintrag genau einmal:

    | Feld | Typ | Inhalt |
    |---|---|---|
    | `clip_id` | str | wie im Job |
    | `flow_hash` | str | wie im Job |
    | `status` | str | `restored` oder `failed` |
    | `path` | str/null | bei `restored`: Datei relativ zu `root_path` mit `/` als Trenner, sonst null |
    | `reason` | str/null | bei `failed`: Kurztext, sonst null |

    Report-`status` ist `ok`, wenn alle Einträge `restored` sind, sonst `failed`.
  - Auswertung (3.6), Restore, Status `ok` und `failed`, je Clip (alle Einträge mit derselben `clip_id`):
    - Vollständiger Clip: alle Einträge `restored` und nach 3.4 vorhanden. Er gilt als restauriert, auch wenn der Job `failed` ist, und geht mit den Dateien aus `path` in den Transcode-Eingang (`…/transcode/eingang/<clip_id>/`).
    - Unvollständiger Clip: mindestens ein Eintrag fehlt. Marathon löscht seinen Clip-Ordner samt bereits restaurierter Dateien und meldet die Gründe aus `reason` im Bericht. Restore hat je Clip genau einen Versuch, unabhängig von `max_job_attempts` (gilt für Transcode und QC unverändert): kein neuer Job, Clip inaktiv „Job endgültig fehlgeschlagen“.
    - Fehlt `items` im Report oder ist es ungültig, gilt jeder Clip als unvollständig.
    - Danach wird der Ausgang gelöscht.
- Version: `schema_version` 6 für alle Stufen; Marathon-Adapter nimmt nur `(6,)` an (CR-007); Restore-Worker nimmt `6` an
- Übergang: keiner; Marathon und alle Worker werden gemeinsam auf `schema_version` 6 umgestellt. QC- und Transcode-Felder unverändert; QC-Worker brauchen nur den Marathon-Adapter 1.2.0

### CR-007 Report-Feld `items` und `schema_version` 6 im Marathon-Adapter

- Von → an: Restore-Worker (ES-Restore) → Marathon-Adapter
- Stand: umgesetzt in Marathon-Adapter 1.2.0
- Inhalt: `JobReport` erhält das optionale Feld `items` (list[dict] oder `None`); ist es gesetzt, schreibt der Adapter es unverändert als `items` in den Report (3.5). Ist `items` keine Liste von Objekten, wird der Report `failed` ohne `items`. `schema_versions` wird `(6,)`; Jobs mit anderer Version werden `failed` „Job ungültig“.
- Version: Marathon-Adapter 1.2.0, gemeinsam mit CR-001; keine weitere `schema_version`
- Übergang: keiner; QC Marathon braucht nur einen neuen Build mit Adapter 1.2.0, das Feld ist optional

### CR-008 Wiederaufnahme laufender Jobs nach Neustart des Workers

- Von → an: Restore-Worker (ES-Restore) → Marathon-Adapter
- Stand: umgesetzt in Marathon-Adapter 1.2.0
- Inhalt: `Settings` erhält das optionale Feld `resume` (bool, Standard `False`, letzte Stelle). Mit `resume=True` meldet der Adapter beim Start eigene Jobs in `laufend/<worker>/` ohne Report nicht als `failed`, sondern gibt sie vor neuen Jobs erneut aus: mit `run` über `run_job(job, output_folder, log_path)`, mit `run_stream` (CR-009) als erste Ergebnisse von `claim()`. Der Report wird danach wie gewohnt geschrieben. Mit `resume=False` bleibt das Verhalten aus 3.9 unverändert.
- Version: Marathon-Adapter 1.2.0, gemeinsam mit CR-001, CR-007 und CR-009; keine weitere `schema_version`; Marathon unverändert
- Übergang: QC Marathon bleibt ohne Änderung lauffähig (`resume=False`)

### CR-009 Mehrere laufende Jobs je Worker

- Von → an: Restore-Worker (ES-Restore) → Marathon-Adapter, Marathon
- Stand: umgesetzt in Marathon-Adapter 1.2.0; offen in Marathon
- Inhalt:
  - Marathon-Adapter, neue Funktion `run_stream(settings, work)`: Start wie `run` (Prüfungen, Eindeutigkeit, Heartbeat, Wiederaufnahme nach CR-008), dann Aufruf von `work()` bis Strg+C. Hilfen für den Stufen-Adapter:
    - `claim()` liefert den nächsten Job als `ClaimedJob(job, output_folder)` oder `None`, wenn keiner vorliegt. Übernahme nach 3.2, Prüfung nach 3.9; ungültige Jobs meldet der Adapter selbst als `failed` und liefert den nächsten. `output_folder` ist angelegt.
    - `report(job_id, report)` schreibt den Report nach 3.5 und nimmt den Job aus dem Heartbeat.
    - `report` für einen nicht übernommenen oder schon gemeldeten Job ergibt `ValueError`; `claim` und `report` außerhalb von `run_stream` ergeben `RuntimeError`.
    - Endet `work()` mit einer Ausnahme oder mit Strg+C, bleiben offene Jobs in `laufend/<worker>/` und werden beim nächsten Start nach CR-008 behandelt. Die Ausnahme wird weitergegeben; endet `work()` ohne Ausnahme, endet `run_stream`.
    - `run` nutzt intern `run_stream`, `claim` und `report` und verhält sich nach außen wie bisher.
  - Heartbeat (3.7): neues Feld `job_ids` (list[str]) mit allen übernommenen Jobs ohne Report in der Reihenfolge der Übernahme; `job_id` ist der älteste davon oder null. Der Adapter schreibt `job_ids` bei `run` und `run_stream`.
  - Marathon: Ein Worker darf mehrere Jobs in `laufend/<worker>/` haben. Die Meldung „Worker mit anderem Job als erwartet“ und die Sperre von `delete-folder` berücksichtigen `job_ids`, wenn vorhanden.
- Version: Marathon-Adapter 1.2.0, gemeinsam mit CR-001, CR-007 und CR-008; Marathon neue Version; keine neue `schema_version`
- Übergang: `run` bleibt unverändert; Heartbeats ohne `job_ids` werden über `job_id` geprüft

### CR-010 Mehrzeilige Statusanzeige im Marathon-Adapter

- Von → an: Restore-Worker (ES-Restore) → Marathon-Adapter
- Stand: umgesetzt in Marathon-Adapter 1.2.0
- Inhalt: `status(message)` nimmt auch mehrzeiligen Text an (Zeilen mit `\n` getrennt). Der ganze Block wird in der Konsole an Ort und Stelle angezeigt; die nächste Ausgabe (`status` oder `log`) ersetzt den ganzen Block. Uhrzeit nur vor der ersten Zeile, jede Zeile auf Konsolenbreite gekürzt; leerer Text entfernt den Block. Weiterhin nur Konsole, nicht im Log.
- Version: Marathon-Adapter 1.2.0, gemeinsam mit CR-001 und CR-007 bis CR-009; keine neue `schema_version`; Marathon unverändert
- Übergang: einzeilige Aufrufe (QC Marathon) verhalten sich unverändert

### CR-011 Worker-Name je Rechner und Stufe

- Von → an: Restore-Worker (ES-Restore) → Marathon-Adapter
- Stand: umgesetzt in Marathon-Adapter 1.2.0
- Inhalt: Worker-Name (2.) = `<Rechnername>-<stage>`, z. B. `PC-MAM-01-Restore`, `PC-MAM-01-QC`; Zeichenersetzung wie bisher. Er bleibt Name der Heartbeat-Datei (3.7) und des Ordners unter `laufend/` (3.1); `host` im Heartbeat bleibt der Rechnername. Je Rechner läuft je Stufe ein Worker; die Eindeutigkeitsprüfung (3.9) gilt damit je Rechner und Stufe. Marathon wertet den Namen nicht aus. `worker_name()` ist erst nach dem Start mit `run` oder `run_stream` verfügbar, vorher `RuntimeError`.
- Version: Marathon-Adapter 1.2.0, gemeinsam mit CR-001 und CR-007 bis CR-010; keine neue `schema_version`; Marathon unverändert
- Übergang: keiner; vor dem ersten Start mit Adapter 1.2.0 alte Heartbeat-Dateien `<work_dir>/worker/<Rechnername>.json` und Ordner `<work_dir>/<stufe>/laufend/<Rechnername>/` von Hand löschen, sonst führt Marathon sie weiter als Worker ohne Lebenszeichen. QC Marathon braucht nur die neue Adapter-Kopie; seine README („Der Worker heißt wie der Rechner“) anpassen.

### CR-012 Größe der Restore-Sammeljobs

- Von → an: Bedienung → Marathon
- Stand: offen
- Inhalt:
  - Marathon schreibt je Restore-Job mehrere Dateien in `items` (CR-006), höchstens `[restore] max_job_files` aus `res/config.ini` (Pflichteintrag, ganze Zahl ≥ 1; 1 ergibt einen Clip je Job).
  - Ein Clip wird nie auf mehrere Jobs verteilt. Hat ein Clip mehr Dateien als `max_job_files`, kommt er allein in einen Job.
  - Clips werden nach Band zusammengefasst (`tape` der Einträge); ein Job enthält möglichst nur Clips desselben Bands. Wie Clips mit Dateien auf mehreren Bändern zugeordnet werden, legt Marathon fest.
  - Liegen weniger offene Dateien vor, wird der Job mit weniger Einträgen ausgelegt; Marathon wartet nicht, bis `max_job_files` erreicht ist.
  - Der Restore-Worker nimmt jede Anzahl von Einträgen an; seine Seite ändert sich nicht.
- Version: Marathon 1.17.0, gemeinsam mit CR-006; keine weitere `schema_version`
- Übergang: wie CR-006

## 5. Änderungsprotokoll

| Datum | Antrag | Änderung |
|---|---|---|
| 2026-10-14 | CR-001, CR-007 bis CR-011 | Marathon-Adapter 1.2.0 (Referenzkopie in AQC): `share_path` nach neuer Regel (Marathon benennt Pfade, Worker benutzen sie; relativ oder vollständig), `JobReport` mit `items` und `new_master`, nur `schema_version` 6, `Settings.resume`, `run_stream`/`claim`/`report`, Heartbeat `job_ids`, mehrzeiliges `status`, Worker-Name `<Rechnername>-<stage>`; Abwärtskompatibilität gestrichen (CR-006, CR-007, CR-011, Fahrplan); Vertrag (Abschnitt 3) unverändert bis Schritt 5 |
| 2026-10-14 | – | Restore-Worker 0.2.1: Restorer als Paket `restorer/`; Schnittstelle unverändert |
| 2026-10-14 | – | Restore-Worker 0.2.0: Speicherplatz je Ark-Job vor dem Senden, Benachrichtigungen bei jeder Abfrage; Schnittstelle unverändert |
| 2026-10-14 | CR-006 | Restore-Worker 0.1.0: nimmt `schema_version` 6 mit `items` an, Ergebnis je Eintrag in Clip-Ordnern, Report mit `items`; nutzt `run_stream`, `claim`, `report`, `resume` und mehrzeiliges `status` (CR-007 bis CR-010) und den Worker-Namen nach CR-011; Vertrag (Abschnitt 3) unverändert, bis die Gegenseiten umgesetzt sind |
| 2026-10-12 | – | AQC 0.4.0, QC Marathon 2.2.0: `digital_silence` prüft je Kanal, ob er Ton enthält (Anteil der Fenster mit RMS ab `threshold` mindestens `min_active`), statt einzelne Stille-Abschnitte zu melden; Config `keine_stille` mit `threshold`, `min_active`, `window`. Prüfbericht (3.12): je stummem Kanal ein Eintrag in `failures` mit `criterion` `min_active` und `tc` null, `info` je Stream mit `Ist-Werte:`; Label `digital_silence(keine_stille)` unverändert; Schnittstelle unverändert |
| 2026-10-12 | – | Marathon 1.16.0: Bericht zählt alle Clips der JSON, auch inaktive, in Gesamt und ihrer Stufe; Befehle `retry-restore`, `retry-transcode`, `retry-qc` geben alle inaktiven Clips einer Stufe ohne Bestätigung frei (Versuche auf 0); `update-index` setzt nicht mehr gefundene Clips inaktiv („Nicht mehr im Index“); Schnittstelle unverändert |
| 2026-10-09 | – | Marathon 1.15.0: Befehl `retry-qc` gibt Clips mit „QC nicht bestanden“ zur QC-Neuprüfung frei; Schnittstelle unverändert |
| 2026-10-09 | CR-003 | Marathon 1.14.0: liest den QC-Prüfbericht (3.12) für Detail- und Testbericht; QC-Ausgang mit nur dem Prüfbericht wird als `<work_dir>/qc/archiv/<job_id>.aqc.json` archiviert (3.6); Worker unverändert |
| 2026-10-09 | – | QC Marathon 2.1.1: Prüfbericht in Konsole und Log ab `<work_dir>` gekürzt; Schnittstelle unverändert |
| 2026-10-09 | – | Worker: detaillierte Konsolenausgaben; Marathon-Adapter 1.1.1 mit Hilfe `status(message)`, QC Marathon 2.1.0, QC Worker 2.1.0, AQC 0.3.1; Schnittstelle zu Marathon unverändert |
| 2026-10-09 | – | Marathon 1.12.0: Befehl `test-qc` erzeugt Test-Jobs nach 3.11 aus der JSON; Schnittstelle unverändert |
| 2026-10-09 | CR-002 | Marathon 1.11.0: Test-Modus mit Test-Jobs (3.1, 3.3 Feld `test`, 3.11); Worker unverändert |
| 2026-10-09 | – | QC: Prüftools in `aqc/tools`, Plan-Schlüssel `tool`, Job-`schema_version` 5, FFE-Entscheidung und Referenzbild aus dem Job; Marathon unverändert |
| 2026-10-09 | – | Protokoll angelegt aus Marathon 1.10.0, Marathon-Adapter 1.1.0, QC Marathon 2.0.0, QC Worker 2.0.0, AQC 0.3.0 |

## 6. Fahrplan: Umstellung auf Restore-Sammeljobs

Alle offenen Anträge außer CR-001 (Transcode) dienen dieser Umstellung. Reihenfolge verbindlich (Regel 10); ein Schritt gilt erst als erledigt, wenn seine Prüfung bestanden ist. Je Schritt nur die genannten Dateien hochladen, dazu diese Datei.

| Schritt | Komponente, neue Version | Anträge | Dateien | Voraussetzung | Prüfung | Erledigt |
|---|---|---|---|---|---|---|
| 1 | Marathon-Adapter 1.2.0 (Referenzkopie) | CR-001, CR-007, CR-008, CR-009 (Adapter-Teil), CR-010, CR-011 | `marathon/marathon_adapter.py`; `marathon/qc_marathon.py` nur zum Prüfen | – | QC Marathon läuft unverändert mit `run` und `resume=False` auf Jobs mit `schema_version` 6, Jobs mit 5 werden `failed`; Worker-Name `<Rechnername>-QC`; `run_stream`, `claim`, `report` mit `items`, `resume`, `job_ids` und mehrzeiliges `status` lokal geprüft | 2026-10-14, Marathon-Adapter 1.2.0 (lokal geprüft mit Platzhaltern für `qc_worker`, `restorer` und `toolbox`; QC Marathon 2.2.0 und Restore Marathon 0.1.1 unverändert) |
| 2 | QC Marathon 2.2.1 (Kopie des Adapters 1.2.0, README zum Worker-Namen); optional AQC 0.4.1 | CR-011 (Betrieb), optional CR-005 | `marathon/qc_marathon.py`, `marathon/marathon_adapter.py` 1.2.0, `README.md`; bei CR-005 `aqc/` | Schritt 1 | Neue EXE gebaut; je Rechner vor dem ersten Start alte Datei `<work_dir>/worker/<Rechnername>.json` und Ordner `<work_dir>/qc/laufend/<Rechnername>/` löschen, neue EXE starten; Heartbeat `<Rechnername>-QC.json` erscheint. QC-Jobs laufen erst mit Marathon 1.17.0 (Schritt 3) | |
| 3 | Marathon 1.17.0 | CR-006, CR-009 (Marathon-Teil), CR-012, optional CR-004 | `marathon.py`, `core/` (mindestens `jobs.py`, `workers.py`, `cleanup.py`, `config.py`), `res/config.ini` | Schritt 2 (Marathon schreibt dann `schema_version` 6 für alle Stufen); vor dem Start keine Jobs mit `schema_version` 5 in `*/offen/` oder `*/laufend/` (von Hand löschen) | Im Thread zu klären: Quelle von `file`, `tape` und `size` je Datei, Form der `job_id` für Sammeljobs. Prüfen: Restore-Jobs mit `items` nach CR-006 und CR-012 (vor dem Start eines Restore-Workers in `restore/offen/` ansehen); Auswertung je Clip mit einem Report von Hand (vollständiger und unvollständiger Clip); QC-Jobs mit `schema_version` 6 laufen durch; Meldung „anderer Job“ und Sperre von `delete-folder` mit `job_ids` | |
| 4 | ES-Restore 0.2.1 / Restore Marathon 0.1.1 in Betrieb | – (Seite bereits umgesetzt) | `marathon/marathon_adapter.py` 1.2.0 nach ES-Restore kopieren; `marathon/cred.env` | Schritt 3 | EXE gebaut; erster Lauf mit kleinem `max_job_files` (z. B. 2) und einem Restore-Worker; Report `items` je Datei, Marathon übernimmt vollständige Clips nach Transcode und löscht unvollständige; Neustart des Workers während eines laufenden Ark-Jobs übernimmt ihn ohne zweiten Ark-Job; danach `max_job_files` erhöhen | |
| 5 | Abschluss dieser Datei | Regel 4 | `INTERFACES.md` | Schritte 1 bis 4 | Abschnitt 3 nachgezogen: 2. Worker-Name und Pfade (relativ oder vollständig), 3.3 Restore-Felder, 3.4 Restore-Ergebnis, 3.5 Report-Feld `items`, 3.6 Auswertung je Clip, 3.7 `job_ids`, 3.9 Adapter-Schnittstelle 1.2.0 (inkl. `share_path` nach CR-001), 3.10 Restore-Worker; CR-001 und CR-006 bis CR-012 auf `erledigt`; Abschnitt 1 und 5 aktualisiert | |

Nicht Teil der Umstellung: CR-001 kommt mit Schritt 1 in den Adapter; die neue `share_path`-Regel gilt damit für alle Worker, `new_master` wird erst mit dem Transcode-Worker genutzt; CR-005 und CR-004 sind unabhängig und nur der Einfachheit halber bei Schritt 2 bzw. 3 genannt.
