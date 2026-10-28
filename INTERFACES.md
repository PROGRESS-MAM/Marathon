# Marathon – Schnittstellenprotokoll

Stand: 2026-10-19 · gültig für die Versionen in Abschnitt 1

Dieses Protokoll beschreibt alles, was zwischen Marathon und den Workern ausgetauscht wird. Es ersetzt das Hochladen der gesamten Codebase: Jeder Thread erhält diese Datei und nur den Code, der bearbeitet wird.

## 0. Regeln für KI-Instanzen

1. Diese Datei vollständig lesen, bevor Code geändert wird.
2. Abschnitt 3 ist der verbindliche Ist-Stand. Code, der eine Schnittstelle nutzt, hält sich genau daran. Abschnitt 2.2 dient der Orientierung; bei Widerspruch gilt Abschnitt 3.
3. Nur den hochgeladenen Code ändern. Was die andere Seite neu tun oder liefern muss, wird als Antrag in Abschnitt 4 eingetragen – nie als bereits umgesetzt angenommen.
4. Abschnitt 3 wird erst geändert, wenn alle betroffenen Seiten umgesetzt sind. Dann: Vertrag anpassen, Antrag auf `erledigt`, Zeile im Änderungsprotokoll (Abschnitt 5).
5. Neue Pflichtfelder oder geänderte Bedeutung eines Feldes erfordern eine neue `schema_version`. Marathon schreibt genau eine Version; Worker dürfen für den Übergang mehrere annehmen.
6. Nur Schnittstellen dokumentieren: Felder, Dateien, Ordner, Status, Reihenfolgen. Keine Interna, keine Begründungen, keine Historie im Vertragsteil.
7. Widerspricht der Code diesem Protokoll, nicht stillschweigend angleichen: Abweichung nennen und als Antrag eintragen.
8. Am Ende jedes Threads die vollständige, aktualisierte Datei zurückgeben, mit neuem Datum unter „Stand“ und aktuellen Versionen in Abschnitt 1.
9. Immer nur ein Thread ändert diese Datei. Arbeiten Threads parallel, hängen sie nur neue Anträge an.
10. Betrifft eine Änderung mehrere Komponenten, die nacheinander umgestellt werden müssen, wird ein Fahrplan als Abschnitt 6 angelegt (Schritte, Voraussetzungen, Prüfung, Erledigt). Er wird in der Reihenfolge abgearbeitet; ein Schritt gilt erst als erledigt, wenn seine Prüfung bestanden ist. Nach dem letzten Schritt wird der Fahrplan entfernt.

## 1. Komponenten und Versionen

| Komponente | Version | Dateien |
|---|---|---|
| Marathon | 1.17.0 | `marathon.py`, `core/`, `res/config.ini` |
| Marathon-Adapter (gemeinsamer Teil aller Worker-Adapter) | 1.3.0 (Referenzkopie in AQC, Kopie in ES-Restore) | `marathon/marathon_adapter.py` |
| QC Marathon (QC-Adapter) | 2.2.1 (enthält Marathon-Adapter 1.2.0 = 1.3.0 ohne `report_items`; übernimmt 1.3.0 beim nächsten Build) | `marathon/qc_marathon.py`, `marathon/configs/` |
| QC Worker | 2.1.0 | `qc_worker.py` |
| AQC (Prüftools) | 0.4.1 | `aqc/`, `aqc/tools/` |
| Restore-Worker (ES-Restore) | 0.3.0 (Restorer 0.3.0, Restore Marathon 0.2.0) | `restorer/`, `marathon/restore_marathon.py`, `marathon/marathon_adapter.py` |
| Transcode-Worker (Transcoder) | 0.1.0 (Transcoder 0.1.0, Transcode Marathon 0.1.0, enthält Marathon-Adapter 1.3.0) | `transcoder/`, `marathon/transcode_marathon.py`, `marathon/marathon_adapter.py` |

Job-`schema_version`: **6** für alle Stufen. Marathon schreibt nur 6; der Marathon-Adapter nimmt nur `(6,)` an.

## 2. Begriffe und Zusammenspiel

### 2.1 Begriffe

- **Freigabe**: Netzlaufwerk `root_path` aus Marathons `res/config.ini`. Pfade in Jobs und Reports sind relativ zu `root_path` mit `/` als Trenner. Ausnahme: Transcode-`inputs` nach `ingest-master` sind vollständige Pfade.
- **`work_dir`**: Arbeitsordner von Marathon (Standard `.marathon`).
- **Stufen**: `Restore`, `Transcode`, `QC` (im Job), Ordnernamen `restore`, `transcode`, `qc`.
- **Zielordner einer Kollektion** (`<Ziel>`): `defa_dir` bei DEFA-Kollektionen (Name enthält `defa_marker`), sonst der Kollektionsname als Ordnername.
- **Worker-Name**: `<Rechnername>-<stage>`, z. B. `PC-MAM-01-Restore`; Zeichen `<>:"/\|?*` und Steuerzeichen werden zu `_`. Er ist Name der Heartbeat-Datei und des Ordners unter `laufend/`. Je Rechner läuft je Stufe ein Worker.
- **Hauptband eines Clips**: ein Band, auf dem jede Masterdatei des Clips eine Kopie hat; gibt es keines, das Band mit den meisten Dateien des Clips. Bei Gleichstand das Band mit den meisten wartenden Clips.
- **Wartender Clip**: aktiv, nicht bereit, Stufe Restore, ohne Job, mit Masterdateien.

### 2.2 Zusammenspiel (Überblick)

**Rollen**

- Marathon läuft einmal (Sperre `state/marathon.lock`) und führt den Zustand aller Clips in `state/marathon.json`. Es legt Jobs in die zentralen Pools `<work_dir>/<stufe>/`, wertet Reports aus, verschiebt Dateien zwischen den Stufen, liefert aus und schreibt die Berichte.
- Worker laufen auf beliebigen Rechnern mit Zugriff auf die Freigabe. Sie sprechen mit Marathon nur über Dateien: Job übernehmen (`offen/` → `laufend/<worker>/`), Ergebnis in `output_folder`, Report (und bei Restore Teilberichte) in `report_folder`, Heartbeat in `<work_dir>/worker/`.
- Der Marathon-Adapter ist in jedem Worker derselbe Code (3.9); der Stufen-Adapter (`qc_marathon.py`, `restore_marathon.py`) verbindet ihn mit der eigentlichen Arbeit.

**Weg eines Clips**

| Stufe | Marathon legt aus | Worker | Marathon bei Erfolg | Marathon bei Fehler |
|---|---|---|---|---|
| Restore | Sammeljob mit vielen Clips je Hauptband | holt die Masterdateien über Ark vom Band in je einen Clip-Ordner, meldet fertige Clips sofort per Teilbericht | Master in den Transcode-Eingang, weiter an Transcode – schon während der Job läuft | Clip-Ordner löschen, Clip inaktiv (ein Versuch je Clip) |
| Transcode | ein Job je Clip | erzeugt den Proxy | Proxy in den QC-Eingang, ggf. neuer Master nach `master_dir`, weiter an QC | neuer Job bis `max_job_attempts`, danach inaktiv |
| QC | ein Job je Clip | prüft den Proxy mit AQC | Proxy in den Zielordner, Master aus Restore abhängig von `keep_old_master` löschen oder sichern, EditShare-Feld setzen, Clip bereit | `rejected`: inaktiv „QC nicht bestanden“; `failed`: neuer Job bis `max_job_attempts` |

Inaktive Clips gibt `retry-restore`, `retry-transcode` bzw. `retry-qc` wieder frei. `ingest-master` und `ingest-proxy` setzen Clips mit vorhandenen Dateien direkt in Transcode bzw. QC.

**Restore im Detail**

1. In jedem Zyklus legt Marathon bis zu `[limits] restore_big_job` große und `restore_small_job` kleine Restore-Jobs aus (gezählt: offen oder laufend). Zwei Restore-Jobs haben nie dasselbe Hauptband; ein Clip steht nie in mehreren Jobs.
   - Großer Job: oberste Kollektion der Prioliste (`[Restore]`) mit wartenden Clips auf freien Hauptbändern; deren Hauptband mit den meisten Clips dieser Kollektion; der Job enthält alle wartenden Clips mit diesem Hauptband aus allen Kollektionen, ohne Obergrenze.
   - Kleiner Job: höchstens `[restore] small_job_clips` Clips. Ein ganzes Hauptband mit höchstens so vielen wartenden Clips (bei mehreren das mit den meisten Clips der obersten Kollektionen); gibt es keines, die höchstpriorisierten Clips des Bands, das als nächster großer Job gewählt würde.
   - Dateien eines Clips, die nicht auf dem Hauptband liegen, stehen mit einem ihrer eigenen Bänder im selben Job.
2. Der Restore-Worker übernimmt mehrere Restore-Jobs gleichzeitig. Je Job und Band (bzw. Bandkombination) legt er einen Ark-Job an. Steuerung: Ein neuer Ark-Job wird nur gesendet, wenn in Ark kein Job wartet, auch kein fremder (`max_ark_queue = 1`), kein eigener Ark-Job dasselbe Band belegt (Bandsperre, auch über Jobs hinweg) und der Platz an der Freigabe reicht (sonst wartet er; Reserve `reserve_gb`). Einen neuen Restore-Job holt er nur, wenn er einen Ark-Job senden könnte.
3. Sind alle Dateien eines Clips fertig (alle Ark-Jobs mit seinen Dateien beendet), schreibt der Worker einen Teilbericht für diesen Clip und fasst dessen Ordner nicht mehr an. Marathon wertet den Clip im nächsten Zyklus aus: vollständig → Master in den Transcode-Eingang, weiter an Transcode; unvollständig → Clip-Ordner löschen, Clip inaktiv. Liegt ein Job auf einem einzigen Band, kommen seine Teilberichte gesammelt am Ende dieses Ark-Jobs.
4. Zum Schluss schreibt der Worker den Report mit allen Einträgen. Marathon wertet die noch offenen Clips aus, löscht den Ausgang und archiviert Job-Datei, Teilberichte und Report.

**Transcode und QC**: Je Stufe höchstens `[limits] transcode` bzw. `qc` offene Jobs im Pool; Reihenfolge nach Prioliste und Eingangszeit. QC Marathon bearbeitet einen Job nach dem anderen.

**Überwachung**: Worker schreiben ihren Heartbeat spätestens jede Minute. Marathon meldet im Bericht Worker ohne Lebenszeichen, Worker mit anderem Job als erwartet und zu lange laufende Jobs; es holt keine Jobs automatisch zurück. `delete-folder` ist gesperrt, solange Worker aktiv sind oder Jobs laufen.

**Neustart**

- Restore-Worker (`resume=True`): übernommene Jobs werden wieder aufgenommen; laufende Ark-Jobs werden aus dem Journal des Workers weiter verfolgt, ohne zweiten Ark-Job; schon gemeldete Clips werden nicht erneut angefordert oder gemeldet. Das Journal liegt neben der EXE und darf nicht gelöscht werden, solange Jobs offen sind.
- QC Marathon (`resume=False`): übernommene Jobs ohne Report werden als `failed` gemeldet; Marathon legt einen neuen Versuch an.
- Marathon: Zustand in `state/marathon.json`; Jobs in den Pools laufen weiter und werden nach dem Start wieder verfolgt.

**Test-Modus**: `test`, `test-qc` und `test-restore` legen Test-Jobs (3.11) in dieselben Pools; Worker bearbeiten sie wie andere Jobs. Marathon wertet sie nur für den Testbericht aus und ändert weder Zustand noch Produktionsdateien. Während des Test-Modus ruht die Job-Schleife; danach mit `run` fortsetzen und den Test-Ausgang von Hand löschen.

**Betriebswerte**

| Wo | Eintrag | Wert |
|---|---|---|
| Marathon `res/config.ini` | `[limits] restore_big_job`, `restore_small_job` | je `1` |
| Marathon `res/config.ini` | `[restore] small_job_clips` | `10` |
| Marathon `res/config.ini` | `[timing] max_job_attempts` (Transcode, QC) | `2` |
| Marathon `res/config.ini` | `[heartbeat] worker_timeout_minutes`, `max_job_hours` | `10`, `24` |
| Restore Marathon (Build) | `max_ark_queue`, `reserve_gb`, `stall_minutes`, `resume` | `1`, `500`, `60`, `True` |

## 3. Vertrag (Ist-Stand)

### 3.1 Ordner

| Pfad | Inhalt | angelegt von |
|---|---|---|
| `<work_dir>/<stufe>/offen/` | neue Jobs | Marathon |
| `<work_dir>/<stufe>/laufend/<worker>/` | übernommene Jobs, auch mehrere je Worker | Worker |
| `<work_dir>/<stufe>/fertig/` | Reports, bei Restore auch Teilberichte | Marathon |
| `<work_dir>/<stufe>/archiv/` | archivierte Jobs, Reports, Teilberichte, Reste aus Ausgängen | Marathon |
| `<work_dir>/worker/` | Heartbeats, FFE-Referenzdateien | Marathon |
| `<work_dir>/restore/ausgang/<job_id>` | `output_folder` eines Restore-Jobs; ein Ausgang für alle Kollektionen | Marathon (vor dem Auslegen) |
| `<Ziel>/<work_dir>[/<Kollektion>]/transcode/` und `…/qc/`, je mit `eingang/`, `ausgang/`, `archiv/` | Arbeitsordner je Kollektion; `/<Kollektion>` nur bei DEFA-Kollektionen | Marathon |
| `…/transcode/eingang/<clip_id>/` | Master eines Clips nach Restore | Marathon |
| `…/<stufe>/ausgang/<job_id>` | `output_folder` eines Transcode- oder QC-Jobs | Marathon (vor dem Auslegen) |
| `<work_dir>/test/<stufe>/ausgang/<job_id>` | `output_folder` eines Test-Jobs (3.11) | Marathon (vor dem Auslegen) |

### 3.2 Job-Übernahme

- Worker nehmen die erste Datei `*.json` in `offen/`, sortiert nach Dateiname, ohne Dateien mit Punkt am Anfang.
- Übernahme durch Umbenennen nach `laufend/<worker>/`. `FileNotFoundError` oder `PermissionError`: ein anderer Worker war schneller oder Marathon hat den Job zurückgezogen – nächste Datei versuchen.
- Die Job-Datei bleibt in `laufend/<worker>/`, bis Marathon sie nach dem Report archiviert. Ein Worker darf mehrere Jobs gleichzeitig dort haben.
- Marathon darf Jobs in `offen/` jederzeit zurückziehen (löschen). Unbekannte Dateien `*.json` in `offen/` löscht Marathon samt Ausgang.
- Ist eine Job-Datei weder in `offen/` noch in `laufend/` und liegt kein Report vor, legt Marathon nach 30 Minuten neu aus (Transcode, QC: neuer Job; Restore: die Clips warten wieder).
- Worker lesen Eingaben nur dort, wo der Job es angibt, und schreiben Ergebnisse nur in `output_folder`.

### 3.3 Job-Datei

Alle Stufen:

| Feld | Typ | Inhalt |
|---|---|---|
| `schema_version` | int | `6` |
| `job_id` | str | Dateiname ohne `.json` (Formen unten) |
| `stage` | str | `Restore`, `Transcode` oder `QC` |
| `created_at` | str | ISO-Zeitstempel |
| `report_folder` | str | `<work_dir>/<stufe>/fertig` |
| `output_folder` | str | siehe 3.1 |
| `test` | object | nur bei Test-Jobs: `{"run": str, "number": int, "name": str}`; Worker ignorieren es |

`job_id`: `<Zeitstempel>__<clip_id>__<stufe><n>` bei Transcode und QC (`<stufe>` klein, `<n>` = Nummer des Jobs dieses Clips), `<Zeitstempel>__<n>_restore` bei Restore (`<n>` = laufende Nummer der Restore-Jobs), `<Zeitstempel>__test<Nr>-<n>_restore` bei Restore-Test-Jobs. `<Zeitstempel>` = UTC `YYYYMMDDTHHMMSSffffff`, streng steigend.

Transcode und QC zusätzlich:

| Feld | Typ | Inhalt |
|---|---|---|
| `clip_id` | str | EditShare-`clip_id` |
| `collection` | str | Kollektionsname |
| `identifier` | str | `001 Identifier` (bei DEFA die DEFA-ID) |
| `title` | str | `014 Title Original` |
| `clip_name` | str | `clip_name_with_extension` |

Je Stufe:

| Stufe | Feld | Typ | Inhalt |
|---|---|---|---|
| Restore | `items` | list[object] | mindestens ein Eintrag, je Masterdatei ein Eintrag (Tabelle unten); Clips in Reihenfolge der Prioliste, Dateien eines Clips zusammen |
| Transcode | `inputs` | list[str] | Masterdateien (`…/transcode/eingang/<clip_id>/<Datei>`); nach `ingest-master` vollständige Pfade |
| Transcode | `proxy_name` | str | Dateiname, unter dem der Proxy im Ausgang liegen muss |
| Transcode | `ffe_tafel` | bool | Clip braucht die FFE-Filmtafel |
| Transcode | `ffe_reference_clips` | list[str] | alle FFE-Tafel-Clips, z. B. `.marathon/worker/FFE Filmerbe/2K_2_35.mov` |
| QC | `input` | str | Proxy im QC-Eingang |
| QC | `ffe_tafel` | bool | Clip braucht die FFE-Filmtafel |
| QC | `ffe_reference_image` | str | Referenzbild der Tafel, z. B. `.marathon/worker/FFE-Filmerbe-DEFA-Titel_Tafel.png` |

Restore-Eintrag in `items` (alle Felder Pflicht):

| Feld | Typ | Inhalt |
|---|---|---|
| `clip_id` | str | EditShare-`clip_id`; Einträge mit gleicher `clip_id` gehören zu einem Clip |
| `clip_name` | str | Name des Clip-Ordners im Ausgang (`clip_name_with_extension`) |
| `file` | str | physischer Dateiname: EditShare `display_name` + „.“ + `display_fileext`, kein Clip- oder Asset-Name |
| `flow_hash` | str | FLOW-Hash Version 2, Form `2:<hex>` (EditShare `file.hash`) |
| `tape` | str | Barcode des Bands, von dem die Datei gelesen wird: das Hauptband des Clips, wenn die Datei dort eine Kopie hat, sonst eines ihrer eigenen Bänder (EditShare `backup_locations[].tapes`) |
| `size` | int | Dateigröße in Byte (EditShare `file.filesize`) |

Maßgeblich sind die Werte beim Erstellen des Jobs. Worker ignorieren unbekannte Felder.

### 3.4 Ergebnis im `output_folder`

Dateien mit 0 Byte oder auf `.tmp`, `.part`, `.partial` zählen nicht. Dateinamen werden ohne Unterscheidung von Groß-/Kleinschreibung verglichen.

| Stufe | Erwartet |
|---|---|
| Restore | je Eintrag `<output_folder>/<Clip-Ordner>/<file>` mit genau `size` Byte. Clip-Ordner = `clip_name`; `<>:"/\|?*` und Steuerzeichen werden zu `_`, Punkte und Leerzeichen am Ende entfallen. Ergibt sich derselbe Clip-Ordner (ohne Unterscheidung von Groß-/Kleinschreibung) für verschiedene `clip_id` im selben Job, erhält der erste Clip den Namen ohne Zusatz, jeder weitere `<Clip-Ordner>__2`, `__3` … in der Reihenfolge des ersten Auftretens in `items`. Dateinamen werden nie verändert. |
| Transcode | genau ein Proxy mit dem Namen `proxy_name`; optional ein neuer Master `<DEFA-ID>__<Titel>.<Endung>` mit DEFA-ID = `identifier` (im Report als `new_master` gemeldet); Protokolldateien `.json`, `.txt`, `.log` erlaubt. Jede weitere Mediendatei zählt als zweiter Proxy. |
| QC | Prüfberichte (3.12); der Proxy (`input`) wird nur gelesen, nie verschoben oder geändert |

### 3.5 Report und Teilbericht

Report: Datei `<report_folder>/<job_id>.json`, geschrieben unter einem temporären Namen, der nicht auf `.json` endet, dann umbenannt.

| Feld | Typ | Pflicht | Inhalt |
|---|---|---|---|
| `job_id` | str | ja | wie im Job |
| `status` | str | ja | `ok`, `failed` oder `rejected` (QC und Transcode; Transcode-`rejected` sperrt zur manuellen Prüfung). Restore: `ok`, wenn alle Einträge `restored` sind, sonst `failed` |
| `result` | str | wenn nicht `ok` | Kurztext |
| `preset` | str/null | nein | Name des Presets bzw. Prüfplans |
| `new_master` | str/null | nein | nur Transcode: Dateiname des neuen Masters |
| `items` | list[object] | Restore | jeder Job-Eintrag genau einmal (Tabelle unten) |

Eintrag in Report-`items` und Teilbericht-`items`:

| Feld | Typ | Inhalt |
|---|---|---|
| `clip_id` | str | wie im Job |
| `flow_hash` | str | wie im Job |
| `status` | str | `restored` oder `failed` |
| `path` | str/null | bei `restored`: Datei relativ zu `root_path` mit `/` als Trenner, sonst null |
| `reason` | str/null | bei `failed`: Kurztext (Restore-Worker: höchstens 300 Zeichen), sonst null |

Teilbericht (nur Restore): Datei `<report_folder>/<job_id>.teil-<Zeitstempel>.json` (`<Zeitstempel>` UTC `YYYYMMDDTHHMMSSffffff`, je Job streng steigend), geschrieben wie der Report. Inhalt `{"job_id": str, "items": list[object]}` mit allen Einträgen eines oder mehrerer Clips, deren Einträge alle `restored` oder `failed` sind. Nach dem Teilbericht verändert der Worker diese Clip-Ordner nicht mehr. Teilberichte sind optional; der Report enthält trotzdem alle Einträge.

- Weitere Felder sind erlaubt und werden von Marathon ignoriert (der Marathon-Adapter schreibt `worker` und `versions`).
- Unlesbare oder ungültige Reports und Teilberichte bleiben liegen; Marathon versucht sie im nächsten Zyklus erneut. Ungültig: Report ohne `job_id`, mit unbekanntem `status`, ohne `result` bei `status` ≠ `ok`, `preset` oder `new_master` kein Text; Teilbericht mit `job_id` ≠ Dateiname vor `.teil-` oder `items` leer bzw. keine Liste von Objekten.
- Reports und Teilberichte zu Jobs, die Marathon nicht mehr führt, werden ignoriert und archiviert.

### 3.6 Was Marathon mit Report und Teilbericht macht

Je Zyklus zuerst Teilberichte in Namensreihenfolge, dann Reports.

**Restore** (wertet `items` je Clip aus, `status` nicht; jeder Clip eines Jobs wird genau einmal ausgewertet):

- Vollständiger Clip: alle Einträge des Clips `restored`, `path` liegt im `output_folder` des Jobs, endet auf `file` und die Datei hat `size` Byte. Er geht mit den Dateien in den Transcode-Eingang (`…/transcode/eingang/<clip_id>/`), weiter an Transcode, auch wenn der Job `failed` ist.
- Unvollständiger Clip: mindestens ein Eintrag fehlt, ist doppelt oder erfüllt die Bedingungen nicht. Marathon löscht seinen Clip-Ordner und meldet die Gründe aus `reason` im Bericht. Ein Versuch je Clip: kein neuer Job, Clip inaktiv „Job endgültig fehlgeschlagen“.
- Teilbericht: ausgewertet werden nur Clips, deren Einträge alle darin stehen; die übrigen warten auf weitere Teilberichte oder den Report.
- Report: alle noch offenen Clips werden ausgewertet; fehlt `items` oder ist es ungültig, gelten sie als unvollständig. Danach löscht Marathon den Ausgang.
- Ist ein Clip bei der Auswertung nicht mehr aktiv oder nicht mehr in Restore, wird sein Ergebnis verworfen und sein Clip-Ordner gelöscht.
- Archiv: Job-Datei, Report als `<job_id>.report.json` und jeder Teilbericht als `<Dateiname ohne .json>.report.json` in `<work_dir>/restore/archiv/`.

**Transcode und QC**:

| Status | Marathon |
|---|---|
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
| `job_id` | str/null | ältester übernommener Job ohne Report |
| `job_ids` | list[str] | alle übernommenen Jobs ohne Report, in der Reihenfolge der Übernahme |
| `beat` | str | muss sich bei jedem Schreiben ändern |

- Weitere Felder sind erlaubt (der Marathon-Adapter schreibt `instance` und `versions`).
- Marathon liest `job_ids`, ohne dieses Feld `job_id`. Im Bericht meldet es: Worker ohne Änderung länger als `worker_timeout_minutes`, Worker, der einen laufenden Job nicht meldet, Jobs länger als `max_job_hours`. Jobs werden dabei nicht automatisch zurückgeholt.
- `delete-folder` ist gesperrt, solange ein Heartbeat jünger als `worker_timeout_minutes` ist, `job_id` oder `job_ids` einen Job meldet oder Jobs in `laufend/` ohne Report liegen.

### 3.8 FFE-Referenzdateien

- `<work_dir>/worker/<reference_image>` (Standard `FFE-Filmerbe-DEFA-Titel_Tafel.png`) und alle `.mov` in `<work_dir>/worker/<reference_clip_dir>/` (Standard `FFE Filmerbe`).
- Marathon spiegelt sie in jedem Zyklus aus `res/`. Worker lesen sie nur und schreiben in `<work_dir>/worker/` ausschließlich ihren Heartbeat.

### 3.9 Marathon-Adapter (gemeinsamer Teil)

- Wird unverändert in jeden Worker kopiert. Änderungen nur in der Referenzkopie (AQC), mit neuer `app_version`, eingetragen in Abschnitt 1 und 5.
- Schnittstelle für Stufen-Adapter:
  - `Settings(root_path, work_dir, stage, poll_seconds, heartbeat_seconds, log_path, versions={}, resume=False)`; `heartbeat_seconds` 1 bis 60.
  - `JobReport(status, result="", preset=None, items=None, new_master=None)`; `items` und `new_master` stehen nur im Report, wenn sie gesetzt sind.
  - `run(settings, run_job)`: ein Job nach dem anderen bis Strg+C; `run_job(job, output_folder, log_path)` liefert einen `JobReport`; Ausnahmen werden zum Report `failed` „Fehler im Worker: …“.
  - `run_stream(settings, work)`: Start wie `run`, dann `work()` bis zu dessen Ende oder Strg+C. Innerhalb von `work()`:
    - `claim()` liefert den nächsten Job als `ClaimedJob(job, output_folder)` oder `None`; `output_folder` ist angelegt. Ungültige Jobs meldet der Adapter selbst als `failed` und liefert den nächsten.
    - `report(job_id, report)` schreibt den Report (3.5) und nimmt den Job aus dem Heartbeat.
    - `report_items(job_id, items)` schreibt einen Teilbericht (3.5); Heartbeat unverändert. `ValueError`, wenn ein Eintrag kein Objekt ist, `clip_id` oder `flow_hash` kein Text ist oder `status` nicht `restored`/`failed` ist, bei leerem `items` oder nicht als JSON schreibbarem Inhalt.
    - `report` und `report_items` für einen nicht übernommenen oder schon gemeldeten Job: `ValueError`; `claim`, `report`, `report_items` außerhalb von `run_stream`: `RuntimeError`.
    - Endet `work()` mit einer Ausnahme oder mit Strg+C, bleiben offene Jobs in `laufend/<worker>/`; die Ausnahme wird weitergegeben.
  - Hilfen: `share_path(path)`, `log(message)` (Konsole mit Uhrzeit und Log), `status(message)` (Statusblock nur in der Konsole, auch mehrzeilig mit `\n`; die nächste Ausgabe ersetzt ihn, leerer Text entfernt ihn), `worker_name()` (erst nach dem Start, sonst `RuntimeError`).
- `share_path(path)`: Marathon benennt Pfade, der Worker benutzt sie. Ein relativer Pfad (`/` als Trenner) wird an `root_path` angehängt, ein vollständiger Pfad (Laufwerk oder UNC) unverändert zurückgegeben; `..` ist erlaubt. Nur ein leerer Pfad ergibt `ValueError`.
- Der Adapter prüft jeden Job vor der Ausgabe: `schema_version` in `(6,)`, `job_id` = Dateiname, `stage` = eigene Stufe, `output_folder` und `report_folder` nicht leer. Sonst Report `failed` „Job ungültig: …“. Lässt sich `output_folder` nicht anlegen: Report `failed` „Fehler im Worker: …“.
- Ein ungültiger `JobReport` wird zum Report `failed`; fehlt `result` bei `status` ≠ `ok`, schreibt der Adapter „ohne Angabe“.
- Report und Teilbericht werden wiederholt geschrieben, bis die Freigabe erreichbar ist; in dieser Zeit wartet der Aufruf.
- Ein zweiter Start mit demselben Worker-Namen bricht ab, solange dessen Heartbeat aktualisiert wird.
- Beim Start: eigene Jobs in `laufend/<worker>/` ohne Report werden mit `resume=False` als `failed` „Worker neu gestartet; Job wurde abgebrochen.“ gemeldet, mit `resume=True` vor neuen Jobs wieder ausgegeben (nach Dateiname; bei `run` über `run_job`, bei `run_stream` als erste Ergebnisse von `claim()`).

### 3.10 Stufen-Worker

**QC (QC Marathon 2.2.1)**

- Läuft mit `run` und `resume=False`, ein Job nach dem anderen.
- Prüfplan `proxy_standard`: `stream_specs(video_1080p)`, `stream_specs(audio_aac_stereo)`, `digital_silence(keine_stille)`.
- Bei `ffe_tafel: true` zusätzlich `ffe_tafel`: `reference_frame(FFE_tafel_start_ok)` und `reference_frame(FFE_tafel_ende_not_ok)` mit `must_fail`; Referenzbild aus `ffe_reference_image`.
- `preset`: `proxy_standard` bzw. `proxy_standard+ffe_tafel`.
- Status: alle Tools bestanden `ok`, ein Tool nicht bestanden `rejected`, sonst `failed`.
- `failed` „Job ungültig“ bei fehlendem `input`, fehlendem oder nicht booleschem `ffe_tafel`, oder `ffe_tafel: true` ohne `ffe_reference_image`.
- Ausgang: je Clip `<clip>.aqc.json` (Prüfbericht, Aufbau 3.12).

**Restore (Restore-Worker 0.3.0)**

- Läuft mit `run_stream` und `resume=True`; bearbeitet mehrere Jobs gleichzeitig.
- `output_folder` muss auf einer Freigabe `\\server\freigabe\…` liegen, die einem aktiven Media Space in Ark entspricht; sonst scheitert der ganze Job mit `INVALID_INPUT`.
- Je Eintrag: Pflichtfelder nach 3.3, `flow_hash` `2:` + 32 Hex-Zeichen, `file` ohne unzulässige Zeichen; sonst `failed` mit `INVALID_INPUT`. Gleicher `file` im selben Clip-Ordner mit verschiedenem `flow_hash`: alle betroffenen Einträge `failed` mit `DUPLICATE_FILE`.
- Eine Datei, die schon vollständig am Ziel liegt (3.4), gilt als `restored`, ohne Ark.
- Ark-Jobs: je Job und Band bzw. Bandkombination einer; Bandsperre über alle eigenen Ark-Jobs; mit `max_ark_queue = 1` gesendet, wenn in Ark kein Job wartet (eigene und fremde); reicht der Platz an der Freigabe nicht (ausstehende Restores zum selben Media Space plus `reserve_gb`), wartet der Ark-Job.
- Teilbericht je Clip, sobald alle seine Einträge fertig sind; danach bleibt der Clip-Ordner unverändert, auch nach einem Neustart. Einträge ohne gültige `clip_id` stehen nur im Report.
- Report: `status` nach 3.5, `result` Kurztext, z. B. `12 von 14 Dateien restauriert; gescheitert: TAPES_OFFLINE 2`, `preset` null, `items` mit jedem Job-Eintrag.
- `reason`: `<Code>: <Text>`, wenn bekannt mit Band, Laufwerk und kurzer Session-ID, z. B. `TAPE_DEFECT: Media-Alarm auf LS2048L8, Laufwerk 1 (restorejob_N9SMTL)`. Codes: `INVALID_INPUT`, `NOT_IN_ARK`, `TAPE_MISMATCH`, `TAPES_OFFLINE`, `TAPE_DEFECT`, `DRIVE_ERROR`, `ARK_ERROR`, `STALLED`, `INCOMPLETE`, `NO_SPACE`, `DUPLICATE_FILE`, `ORPHANED`, `CANCELLED`. Marathon zeigt `reason` nur als Text im Bericht.
- Jobs mit `schema_version` ≠ 6 werden `failed` „Job ungültig“.

**Transcode (Transcode-Worker 0.1.0)**

- Läuft mit `run` und `resume=False`, ein Job nach dem anderen.
- `failed` „Job ungültig: …“ bei fehlendem `inputs` (nicht leere Liste von Pfaden), fehlendem `proxy_name` oder `proxy_name` mit Ordner, fehlendem oder nicht booleschem `ffe_tafel`, `ffe_tafel: true` ohne `ffe_reference_clips` (nicht leere Liste), fehlendem `identifier` oder `title`.
- Ausgang bei `ok`: Proxy `proxy_name` (Preset `h264_10mbit_1080p`), optional neuer Master `<identifier>__<title>.mov` (`<>:"/\|?*` und Steuerzeichen → `_`; Preset `dnxhr_hqx`, bei interlaced Quellen `dnxhd_185x`), je Datei `<Datei>.render.json`.
- Neuer Master, wenn genau ein Tonkanal hörbar ist, eine progressive Quelle schwarze Ränder hat oder `ffe_tafel: true`.
- Bei `ffe_tafel: true`: vor dem Film der eine Clip aus `ffe_reference_clips` mit Bildgröße und fps der Quelle, danach 1 s Schwarz; Start-TC so, dass der Film beim Start-TC der Quelle beginnt. Gilt für Proxy und neuen Master.
- `preset`: `h264_10mbit_1080p`, mit neuem Master `h264_10mbit_1080p+dnxhr_hqx` bzw. `h264_10mbit_1080p+dnxhd_185x`. `new_master`: Dateiname des neuen Masters, nur bei `ok`.
- Status: `ok`, wenn alle Dateien erzeugt sind; `rejected` „Manuelle Prüfung: …“, wenn Analyse oder Reparatur nicht eindeutig sind, keine oder mehrere FFE-Tafeln passen oder ein neuer Master bei unklarem Interlacing nötig ist (CR-015); sonst `failed` (ffmpeg, Dateizugriff, Job ungültig). Bei `rejected` und `failed` enthält der Ausgang keine Mediendateien, höchstens `.render.json`.

### 3.11 Test-Jobs

- Test-Jobs sind Jobs nach 3.2 bis 3.5 in denselben Ordnern `offen/`, `laufend/`, `fertig/`; Worker behandeln sie wie jeden Job.
- Abweichend: `output_folder` = `<work_dir>/test/<stufe>/ausgang/<job_id>`; zusätzliches Feld `test`; alle übrigen Felder können vom Testplan ersetzt sein, auch durch ungültige Werte. Restore-Test-Jobs haben `job_id` `<Zeitstempel>__test<Nr>-<n>_restore`; `test-restore` legt genau einen an, mit den Clips eines kleinen Jobs.
- Marathon wertet Test-Jobs nicht nach 3.6 aus: Job-Datei, Report und Teilberichte werden archiviert, der Ausgang bleibt liegen, kein neuer Job bei `failed`. Für den Testbericht liest Marathon bei QC den Prüfbericht (3.12) und bei Restore die Report-`items` mit den Dateien im Ausgang (je Clip vollständig oder unvollständig nach 3.6).
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

Nächste Nummer: **CR-016**.

### CR-015 Transcode: manuelle Prüfung ohne neuen Versuch
- Von → an: Transcode-Worker → Marathon
- Stand: offen (Transcode-Worker 0.1.0 meldet `rejected` bereits, Fälle in 3.10; die Schwellen werden mit Archivmaterial noch kalibriert)
- Inhalt: Transcode-Report mit `status` `rejected`, wenn der Worker den Clip nicht transcodiert, weil eine manuelle Prüfung nötig ist; `result` = `Manuelle Prüfung: <Gründe>`; kein Proxy und kein neuer Master im Ausgang. Marathon: Versuch zählt nicht als Fehlversuch, kein neuer Job, Clip inaktiv „Manuelle Prüfung nötig“, Ausgang nach `…/transcode/archiv/<job_id>.ausgang`, `result` im Detailbericht; `retry-transcode` gibt Clips mit diesem Grund wieder frei.
- Version: keine neue `schema_version`; Marathon neue Minor-Version
- Übergang: Bis zur Umsetzung behandelt Marathon `rejected` bei Transcode wie `failed` (3.5); der Transcode-Worker darf `rejected` bereits melden.

Vorlage:

~~~text
### CR-<nnn> <Kurztitel>
- Von → an: <Komponente> → <Komponente>
- Stand: offen | umgesetzt in <Komponente> | erledigt
- Inhalt: <was genau sich ändert: Felder, Dateien, Status, Verhalten>
- Version: <neue schema_version / Komponentenversion oder „keine“>
- Übergang: <ob alte und neue Version parallel funktionieren müssen>
~~~

## 5. Änderungsprotokoll

| Datum | Antrag | Änderung |
|---|---|---|
| 2026-10-19 | CR-015 (offen) | Transcode-Worker 0.1.0 in Abschnitt 1 und 3.10 ergänzt; meldet `rejected` bereits (Übergang nach CR-015). |
| 2026-10-16 | – | Neuer Ausgangspunkt mit den Versionen aus Abschnitt 1: Restore-Sammeljobs mit Teilberichten, `schema_version` 6 für alle Stufen, Marathon-Adapter 1.3.0. Frühere Anträge (bis CR-014) und Einträge abgeschlossen und nicht mehr aufgeführt. |

## Masterablage ab 1.18.0

Die Worker-Schnittstelle bleibt unverändert. Der bestehende Transcode-Report meldet `new_master` wie bisher. Marathon wählt die Ablage über `[ingest] keep_old_master`: `true` für `manuelle Überprüfung/<Clipname>/neu`, `false` für die direkte finale Ablage. Bei `false` löst Marathon vorhandene Prüfungsablagen auf. Aktuelle neue Master-Pfade stehen im jeweils letzten vorhandenen History-Ereignis `Neuer Master abgelegt`; alte Master und Proxy behalten ihre bisherigen Dateieinträge. JSON-Version 8 und Job-Schema 6 bleiben unverändert.

Ab 1.18.0 ist der bereits vorhandene Report-Status `rejected` auch für Transcode nutzbar: Der Clip wird zur manuellen Prüfung blockiert, ohne automatischen zweiten Versuch. Das Report-Schema wird nicht erweitert.
