# Marathon

Marathon baut aus EditShare-Suche und Veritone einen Clip-Index (JSON), legt Restore-Sammeljobs je Band sowie Transcode- und QC-Jobs nach Prioliste für die Worker aus und erstellt Berichte. Zusätzlich markiert Marathon Clips, die die FFE-Filmtafel benötigen, stellt den Workern die Referenzdateien bereit und übernimmt auf Befehl vorhandene Master (`ingest-master`) und vorhandene Proxys (`ingest-proxy`). Im Test-Modus (`test`) laufen Test-Jobs durch die Worker, ohne den Produktionsstand zu ändern.

## Installation

Voraussetzung: Windows-Rechner mit Zugriff auf das Netzlaufwerk, Python 3.10 oder neuer.

~~~bash
pip config set global.extra-index-url https://artifacts.editshare.com/artifactory/api/pypi/editshare-pypi-public/simple
pip install "toolbox @ git+https://github.com/PROGRESS-MAM/TOOLBOX.git@main"
pip install "searcher[api] @ git+https://github.com/PROGRESS-MAM/ES-Search.git@main"
~~~

Projektordner:

~~~text
marathon.py                            Startdatei
core/                                  Programmteile von Marathon
tools/transfer_json_v8.py              Einmalige Übertragung der JSON von Version 7 auf 8 (Update auf 1.17.0)
res/
  config.ini                           Konfiguration (siehe unten)
  cred.env                             FLOW_HOST, FLOW_USER, FLOW_PASSWORD (Suche, EditShare-Feld) und vt_api_token=<Token>
  collections.json                     Kollektionsmapping
  priority.txt                         Prioliste (wird beim ersten Lauf als Vorlage angelegt)
  test_jobs.json                       Testliste für den Test-Modus (nur für `test` nötig)
  test_jobs_qc.json                    QC-Testliste, von `test-qc` erzeugt
  FFE Filmerbe/
    FFE-Filmerbe-DEFA-Titel_ids.json   FFE-Liste
    FFE-Filmerbe-DEFA-Titel_Tafel.png  Referenz-Screenshot der FFE-Filmtafel
    *.mov                              alle FFE-Filmtafel-Clips, z. B. 2K_2_35.mov
~~~

`marathon.py`, `core/` und `tools/` gehören immer zusammen: Bei einem Update alle vollständig ersetzen; `res/`, `log/`, `state/`, `reports/` und `test/` bleiben unverändert.

`log/`, `state/`, `reports/`, `reports/errors/` und `test/` legt Marathon selbst an. Der Index liegt in `state/marathon.json` (JSON-Version 8), das Job-Protokoll für die Detailberichte in `state/journal_<stufe>.jsonl`, der Stand des Test-Modus in `test/test.json`.

## Update auf 1.17.0 (JSON 7 → 8)

Marathon 1.17.0 lädt nur JSON-Version 8 und bricht bei Version 7 mit einem Hinweis auf das Transfer-Script ab. Ablauf:

1. Marathon mit `quit` beenden; alle Worker beenden.
2. Alle Jobs in `<work_dir>/*/offen/` und `<work_dir>/*/laufend/` von Hand löschen (Jobs mit `schema_version` 5).
3. `marathon.py`, `core/` und `tools/` ersetzen; `res/config.ini` anpassen (`[limits] restore_big_job`, `restore_small_job`, `[restore] small_job_clips`, `[limits] restore` entfernen).
4. Transfer im Marathon-Ordner starten:

~~~bash
python tools/transfer_json_v8.py
~~~

Das Script nutzt Config, Zugang und Suche von Marathon und fragt EditShare selbst ab. Es prüft zuerst alles, ändert erst danach etwas und schreibt die JSON zuletzt:

| Prüfung | Abbruch, wenn |
| --- | --- |
| JSON | `state/marathon.json` nicht Version 7 |
| Sperre | Marathon läuft (`state/marathon.lock`) |
| Jobs | eine Job-Datei in `<work_dir>/*/offen/` oder `<work_dir>/*/laufend/` liegt |
| Ordner | ein Restore-Ordner je Kollektion (`<Ziel>/<work_dir>[/<Kollektion>]/restore/` samt `ausgang/`, `archiv/`) eine Datei enthält, auch versteckte, System- oder 0-Byte-Dateien |
| EditShare | ein Clip der JSON nicht gefunden wird, seine Dateien unvollständig oder widersprüchlich sind oder die Dateinamen von `master_files` abweichen |

Ohne Fehler:

- Sicherung `state/backup/marathon.v7_<stempel>.json`,
- `<work_dir>/restore/ausgang/` anlegen, leere Restore-Ordner je Kollektion entfernen (es wird nie eine Datei gelöscht),
- JSON 8 schreiben: je Clip `masters`, `master_files`, `lto_tapes`, `master_size` neu aus EditShare, `filehashes` entfernt, `job` auf `null`; Status, Aktiv-Flag, Versuche und Historie bleiben,
- Bericht `reports/transfer_<stempel>.txt` mit Zahlen und übernommenen Abweichungen bei Bändern und Größen.

Bei einem Fehler bleibt die JSON Version 7; der Fehlerbericht `reports/errors/transfer_<stempel>_errors.txt` nennt alle Gründe, bei Ordnern jeden betroffenen Ordner mit seinen Dateien. Scheitert das Entfernen eines Ordners trotz Prüfung, nennt er die bereits entfernten leeren Ordner.

## Start

~~~bash
python marathon.py                 # Konsole, Befehle mit Enter eingeben
python marathon.py run auto-report # Befehle direkt nach dem Start ausführen
python marathon.py test            # Test-Modus direkt nach dem Start
~~~

Marathon läuft nur einmal pro Rechner (Sperre in `state/marathon.lock`).

## Befehle

| Befehl | Wirkung |
| --- | --- |
| `run` | Ordner und Referenzdateien anlegen, Index aufbauen falls keine JSON existiert, dann Job-Schleife starten |
| `stop` | Job-Schleife bzw. Test-Modus anhalten |
| `test` | Test-Modus: Test-Lauf aus der Testliste starten oder offenen Test-Lauf fortsetzen; hält die Job-Schleife an (siehe Test-Modus) |
| `test-qc` | QC-Testliste aus der JSON erzeugen (alle Clips mit vorhandenem Proxy im QC-Eingang) und Test-Lauf starten (siehe Test-Modus) |
| `test-restore` | Test-Lauf mit genau einem Restore-Test-Job starten; Clips nach der Regel des kleinen Jobs (siehe Test-Modus) |
| `test-cancel` | Offenen Test-Lauf beenden: nicht übernommene Test-Jobs zurückziehen, Testbericht schreiben |
| `auto-report` | Täglichen Auto-Bericht einschalten (ab `auto_report_time`); danach je Stufe ein Detailbericht |
| `auto-report-off` | Täglichen Auto-Bericht ausschalten |
| `report` | Manuellen Bericht sofort erstellen |
| `create-folders` | Ordnerstruktur aller Kollektionen anlegen und FFE-Referenzen bereitstellen |
| `update-index` | Neue Suche (EditShare ∩ Veritone), neue Clips aufnehmen, fehlende Felder (z. B. Veritone-ID) ergänzen, Abweichungen melden, danach FFE-Abgleich |
| `update-ffe` | Nur FFE-Liste mit der bestehenden JSON abgleichen, ohne Suche |
| `ingest-master` | Masterdateien aus `master_dir` über die DEFA-ID abgleichen und eintragen (weiter an Transcode); nur auf Befehl |
| `ingest-proxy` | Proxys aus `proxy_dir` über die DEFA-ID abgleichen, umbenannt in den QC-Eingang verschieben (weiter an QC); nur auf Befehl |
| `retry-restore` | Alle inaktiven Clips der Stufe Restore wieder freigeben (siehe Wieder freigeben) |
| `retry-transcode` | Alle inaktiven Clips der Stufe Transcode wieder freigeben (siehe Wieder freigeben) |
| `retry-qc` | Alle inaktiven Clips der Stufe QC wieder freigeben (siehe Wieder freigeben) |
| `delete-folder` | SMB-Arbeitsordner bereinigen; Index bleibt, Prozesszustand wird neu aufgebaut (Restore-Jobs entfallen). Bei Clip-/Mediendateien Bestätigung mit `loeschen`; gesperrt bei offenem Test-Lauf, frischem Heartbeat, Heartbeat mit `job_id`/`job_ids` oder Jobs ohne Report in `laufend/` |
| `status` | Anzeigen, was eingeschaltet ist (Job-Schleife, Test-Modus, Auto-Bericht) |
| `help` | Befehlsübersicht |
| `quit` | Marathon beenden |

## Proxy-Namen

- Alle Proxys heißen nach `[paths] proxy_name`, Standard `{veritone_id}_{clip_id}_10Mbit.mp4`, z. B. `1234567_98765_10Mbit.mp4`.
- `veritone_id` = Veritone-Asset-ID (in Veritone „Record ID“, Adresse `…/search/asset/<id>`), `clip_id` = EditShare-`clip_id`. Identifier und Titel stehen über die `clip_id` in der JSON.
- Marathon erkennt Proxys im Zielordner und im QC-Eingang nur unter diesem Namen (Groß-/Kleinschreibung egal), auch bei `update-index` und `delete-folder`.
- Transcode-Worker liefern genau den Namen aus `proxy_name` im Job; ein anderer Name lässt den Job fehlschlagen.
- Clip ohne Veritone-ID: Der Restore läuft, vor dem Transcode wird der Clip inaktiv (`Veritone-ID fehlt`), bis `update-index` die ID ergänzt.

## Index (`update-index`)

- Aufgenommen werden Clips, deren `001 Identifier` bei Veritone in derselben Kollektion als Barcode vorkommt; neue Clips erhalten `veritone_id`.
- Barcode mit mehreren Assets: Clip ohne Veritone-ID, Eintrag in der Index-Fehlerliste (Abschnitt „Barcode mehrfach bei Veritone“).
- Clips in der JSON: Fehlende Felder und eine leere Veritone-ID werden aus der Suche ergänzt (History `Fehlende Felder ergänzt`). Vorhandene Werte bleiben; Abweichungen stehen nur in der Index-Fehlerliste.
- Clips in der JSON, die die Suche (EditShare ∩ Veritone) nicht mehr findet: Der Clip wird inaktiv (`Nicht mehr im Index`), bleibt in seiner Stufe und zählt weiter in Gesamt. Eintrag in der Index-Fehlerliste; der Bericht zeigt die Anzahl in der Zeile `Nicht mehr im Index`. Bereite Clips bleiben aktiv und werden nur gemeldet; ein bereits inaktiver Clip behält seinen bisherigen Grund.
- Ein später wieder gefundener Clip bleibt inaktiv, bis er mit `retry-<stufe>` freigegeben wird.
- Dateien je Clip: aus `video.file`, `audio.file` und `data.file`. Je Datei Name = `display_name` + „.“ + `display_fileext`, Hash = `file.hash` (Form `2:<hex>`), Größe = `file.filesize`, Bänder = alle `backup_locations[].tapes`. Dateien mit gleichem Hash werden zusammengefasst. Am Clip stehen sie in `masters` (`file`, `flow_hash`, `size`, `tapes`, sortiert nach Name), daraus `master_files`, `lto_tapes` und `master_size` (Summe aller Dateien).
- Fehlt bei einer Datei Name, Endung, Hash, Größe oder Band, ist ein Name unzulässig (`<>:"/\|?*` oder Steuerzeichen), hat ein Hash mehrere Namen oder Größen oder ein Name mehrere Hashes, wird ein neuer Clip, der einen Restore braucht, nicht aufgenommen (Index-Fehlerliste: „Dateien in EditShare unvollständig oder widersprüchlich“). Bei Clips in der JSON stehen geänderte Dateien nur unter „Metadaten in der Suche geändert“.
- Nur `update-index` sucht. `run` führt `update-index` nur aus, wenn noch keine JSON existiert; Job-Schleife und Berichte suchen nie.

## Prioliste und Jobs

- `res/priority.txt`: je Abschnitt `[Restore]`, `[Transcode]`, `[QC]` eine Kollektion pro Zeile, oben = höchste Priorität. Nicht aufgeführte Kollektionen folgen in der Reihenfolge von `collections.json`.
- Marathon liest die Prioliste in jedem Job-Zyklus und legt für Transcode und QC höchstens so viele Jobs nach `<work_dir>/<stufe>/offen`, wie `[limits]` erlaubt (gezählt werden offene Jobs).
- Worker nehmen den ersten Job in `offen` (nach Dateiname = Erstellreihenfolge). Eine geänderte Prioliste wirkt auf neu ausgelegte Jobs.

### Restore-Sammeljobs

Ein Restore-Job enthält die Dateien mehrerer Clips, zusammengefasst nach Band.

- **Wartender Clip:** aktiv, nicht bereit, Stufe Restore, ohne Job. Ein Clip steht nie in zwei Jobs.
- **Hauptband** je Clip: ein Band, auf dem jede Datei des Clips eine Kopie hat; bei mehreren das mit den meisten wartenden Clips, dann nach Name. Gibt es keines, das Band mit den meisten Dateien des Clips; jede übrige Datei wird von ihrem Band mit den meisten wartenden Clips gelesen. „Wartende Clips eines Bands“ = wartende Clips mit mindestens einer Datei auf dem Band.
- **Gesperrt** sind die Hauptbänder aller offenen und laufenden Restore-Jobs; Clips darauf warten.
- **Große Jobs** (bis `[limits] restore_big_job` gleichzeitig): oberste Kollektion der Prioliste mit wartenden Clips auf freien Hauptbändern → deren Hauptband mit den meisten Clips dieser Kollektion (bei Gleichstand meiste wartende Clips insgesamt, dann Name) → alle wartenden Clips mit diesem Hauptband aus allen Kollektionen, ohne Obergrenze.
- **Kleine Jobs** (bis `[limits] restore_small_job` gleichzeitig, nach den großen Jobs): ein freies Hauptband mit höchstens `[restore] small_job_clips` wartenden Clips; bei mehreren das mit den meisten Clips der obersten Kollektion der Prioliste, dann der nächsten usw., dann Name. Gibt es keines: die `small_job_clips` höchstpriorisierten Clips des Hauptbands, das als nächster großer Job gewählt würde; der Rest wartet.
- Reihenfolge im Job: Clips nach Prioliste und Eingangszeit, Dateien je Clip nach Name.
- Wird ein Clip eines offenen Jobs inaktiv oder verlässt er den Restore, zieht Marathon den ganzen Job zurück und plant im selben Zyklus neu. Läuft der Job schon, läuft er weiter; das Ergebnis dieses Clips wird verworfen und sein Clip-Ordner gelöscht.
- Verschwindet die Job-Datei ohne Report, warten alle noch nicht ausgewerteten Clips nach 30 Minuten wieder.
- Marathon prüft keinen Speicherplatz; Platz und Bandsperre regelt der Restore-Worker. Große Jobs dürfen `max_job_hours` überschreiten (nur Meldung im Bericht).

**Job-Datei** (`<work_dir>/restore/offen/<job_id>.json`, `schema_version` 6):

~~~json
{
  "schema_version": 6,
  "job_id": "20261016T091446301058__1_restore",
  "stage": "Restore",
  "created_at": "2026-10-16T11:14:46+02:00",
  "report_folder": ".marathon/restore/fertig",
  "output_folder": ".marathon/restore/ausgang/20261016T091446301058__1_restore",
  "items": [
    { "clip_id": "641094", "clip_name": "Blick in die Welt 1962_33_HLS Video_m8324_BIDW20460.new.01.mxf",
      "file": "Blick in dA01.5FC65FC65B66A.mxf", "flow_hash": "2:74265de8cd65de5fb3fd9f41b388372e",
      "tape": "LS2032L8", "size": 79835745 }
  ]
}
~~~

`<n>` in der `job_id` ist die laufende Nummer der Restore-Jobs. Ein Restore-Ausgang für alle Kollektionen: `<work_dir>/restore/ausgang/<job_id>/<Clip-Ordner>/<Datei>`.

## FFE-Filmtafel

**FFE-Liste** (`res/FFE Filmerbe/FFE-Filmerbe-DEFA-Titel_ids.json`):

~~~json
{
  "titel": [
    { "title": "Schatten über den Inseln", "defa_id": "DEFA14342" }
  ]
}
~~~

**Abgleich** (bei `update-index` und `update-ffe`):

- Ein Eintrag trifft einen Clip, wenn `defa_id` genau dem Identifier und `title` genau dem Titel des Clips in der JSON entspricht (inklusive Groß-/Kleinschreibung und Zusätzen wie `__24fps`).
- Genau ein Treffer: Der Clip bekommt `"ffe_tafel": true`.
- Mehrere Treffer: kein Flag; Eintrag in `reports/errors/<index|ffe>_<stempel>_ffe_uneindeutig.txt`.
- Kein Treffer: Eintrag in der allgemeinen Fehlerliste `reports/errors/<index|ffe>_<stempel>_errors.txt`, Abschnitt „FFE-Titel nicht in der JSON“. Gibt es einen Clip mit abweichender Schreibweise, steht er als Hinweis dabei.
- Bei jedem Abgleich wird `ffe_tafel` für alle Clips neu gesetzt: Clips ohne eindeutigen Treffer in der aktuellen Liste erhalten `false`.
- Ist die FFE-Liste ungültig, bricht der Befehl ab, ohne die JSON zu ändern (bei `update-index` vor der Suche).
- Der Bericht zeigt den letzten Stand in der Zeile `FFE-Stand`.

Nach Änderungen an der FFE-Liste genügt `update-ffe`. Nach `update-index` ist kein eigenes `update-ffe` nötig: Der FFE-Abgleich läuft dort immer automatisch mit.

**Referenzdateien für Worker:**

- Marathon kopiert `res/FFE Filmerbe/FFE-Filmerbe-DEFA-Titel_Tafel.png` nach `<root_path>/<work_dir>/worker/` und spiegelt alle `.mov`-Dateien aus `res/FFE Filmerbe/` nach `<root_path>/<work_dir>/worker/FFE Filmerbe/` – bei `run`, `create-folders` und in jedem Job-Zyklus. Geänderte Dateien (Größe oder Änderungszeit) werden neu kopiert, im lokalen Ordner entfernte Clips und andere Dateien im Clip-Ordner auf dem SMB gelöscht.
- `delete-folder` löscht die Referenzdateien mit dem Arbeitsordner, ohne Bestätigung dafür zu verlangen; `run` oder `create-folders` legen sie wieder ab.

**Job-Felder (Job-`schema_version` 6), Pfade relativ zu `root_path` (Ausnahme: `inputs` von Ingest-Mastern):**

| Job | Feld | Inhalt |
| --- | --- | --- |
| Transcode | `ffe_tafel` | `true`/`false` |
| Transcode | `ffe_reference_clips` | Liste aller FFE-Clips, z. B. `.marathon/worker/FFE Filmerbe/2K_2_35.mov` |
| Transcode | `proxy_name` | Dateiname, unter dem der Proxy im Ausgang liegen muss, z. B. `1234567_98765_10Mbit.mp4` |
| Transcode | `inputs` | Masterdateien; nach `ingest-master` vollständiger Pfad, z. B. `\\10.0.77.11\Ablage KI Proxy_1\++ Master repariert\DEFA14097__….mov` |
| QC | `ffe_tafel` | `true`/`false` |
| QC | `ffe_reference_image` | `.marathon/worker/FFE-Filmerbe-DEFA-Titel_Tafel.png` |

Maßgeblich ist der Wert beim Erstellen des Jobs.

## Worker-Ergebnis und Auslieferung

**Restore** – Auswertung je Clip:

- Teilberichte `<job_id>.teil-<stempel>.json` in `<work_dir>/restore/fertig/` wertet Marathon schon während des Jobs in Namensreihenfolge aus, den Report `<job_id>.json` zuletzt. Jeder Clip wird nur einmal ausgewertet; ein Clip, dessen Einträge ein Teilbericht nicht alle enthält, erst mit dem Report.
- **Vollständig**: alle Einträge `restored`, `path` liegt im `output_folder` des Jobs, die Datei ist vorhanden und so groß wie `size`. Die Dateien gehen nach `…/transcode/eingang/<clip_id>/` der Kollektion, weiter an Transcode, Versuche 0.
- **Unvollständig**: Clip-Ordner wird gelöscht, die Gründe (`reason` bzw. Marathons Prüfung) stehen in der History, im Job-Protokoll und im Detailbericht; der Clip wird inaktiv (`Job endgültig fehlgeschlagen`). Kein zweiter Versuch – wieder frei mit `retry-restore`. Fehlt `items` im Report oder ist es ungültig, gilt jeder noch nicht ausgewertete Clip als unvollständig.
- Nach dem Report: Ausgang löschen; Job-Datei, Report (`<job_id>.report.json`) und Teilberichte (`<Name>.report.json`) liegen in `<work_dir>/restore/archiv/`.

**Transcode-Ausgang** (Ordner `output_folder` des Jobs):

- genau ein Proxy mit dem Namen aus `proxy_name`,
- optional ein neuer Master (repariert und/oder mit FFE-Tafel) mit dem Namen `<DEFA-ID>__<Titel>.<Endung>`; die DEFA-ID muss dem Identifier des Clips entsprechen,
- Protokolldateien (`.json`, `.txt`, `.log`) sind erlaubt.

**Report** (`<report_folder>/<job_id>.json`):

~~~json
{ "job_id": "...", "status": "ok", "result": "", "preset": "...", "new_master": "DEFA14097__Rosa Luxemburg.mov" }
~~~

`new_master` nur bei Transcode und nur, wenn ein neuer Master im Ausgang liegt, sonst `null` oder weglassen.

**Prüfung nach Transcode:**

- Proxy und gemeldeter neuer Master müssen vorhanden und größer als 0 Byte sein, Namen wie oben. Sonst gilt der Job als fehlgeschlagen: Teilergebnisse werden gelöscht, neuer Versuch bis `max_job_attempts`. Eine nicht gemeldete zweite Mediendatei zählt als zweiter Proxy und lässt den Job ebenfalls fehlschlagen.
- Der neue Master wird nach `[ingest] master_dir` verschoben, nie überschrieben. Bei Namenskonflikt oder wenn das Verschieben nicht möglich ist, wird der Clip inaktiv (`Neuer Master blockiert`), der Ausgang archiviert, nichts gelöscht. Konflikt in `master_dir` lösen, dann `retry-transcode` (der Transcode läuft neu).
- Danach verfolgt Marathon den neuen Master nicht weiter (nur History `Neuer Master abgelegt`); `delete-folder` ordnet ihn nicht wieder zu.

**Nach QC:**

| QC | Proxy | Master aus Restore | Neuer Master in `master_dir` | EditShare-Feld |
| --- | --- | --- | --- | --- |
| bestanden | in den Zielordner | sofort gelöscht | bleibt | wird gesetzt |
| nicht bestanden | bleibt im QC-Eingang | bleibt | bleibt | – |

- Reihenfolge bei bestandenem QC: Proxy ausliefern, Master aus Restore löschen, EditShare-Feld setzen. Masterdateien aus `ingest-master` werden nie gelöscht.
- Vor der Auslieferung muss der Proxy vorhanden und größer als 0 Byte sein.
- QC nicht bestanden: Clip inaktiv (`QC nicht bestanden`), Eintrag in der Fehlerliste des Berichts, Gründe im Detailbericht QC.
- Zielordner enthält schon eine Datei mit dem Proxy-Namen: Clip inaktiv (`Auslieferung blockiert`), Proxy bleibt im QC-Eingang. Datei im Zielordner entfernen, dann `retry-qc` (der QC läuft neu, danach die Auslieferung).
- Archiv: Job-Datei und Report liegen in `<work_dir>/<stufe>/archiv/`. Enthält der QC-Ausgang nur den Prüfbericht, liegt er dort als `<job_id>.aqc.json`; sonst wird der Ausgang als Ordner `…/<stufe>/archiv/<job_id>.ausgang` archiviert.

**EditShare-Feld:**

- Nach jeder Auslieferung (auch nach `ingest-proxy`) setzt Marathon im selben Job-Zyklus das Custom-Feld `39d 10 Mbit Proxy Path` des Clips auf den Pfad des ausgelieferten Proxys, z. B. `\\10.0.77.11\Ablage KI Proxy_1\Proxy 10 Mbit\DEFA\1234567_98765_10Mbit.mp4`.
- Zugang über `cred_file`; der FLOW-Benutzer braucht Schreibrecht auf das Feld.
- Scheitert das Setzen, bleibt eine offene Aufgabe in der JSON (`editshare`), und Marathon versucht es in jedem Job-Zyklus erneut. Ab 3 gescheiterten Zyklen steht der Clip im Bericht unter „EditShare-Feld nicht gesetzt“; er zählt weiter als bereit.
- Proxys, die vor Version 1.10.0 ausgeliefert wurden, bekommen das Feld nicht nachträglich.

## Detailberichte

Nur mit eingeschaltetem `auto-report`: Direkt nach jedem täglichen Auto-Bericht schreibt Marathon je Stufe einen Detailbericht. Der Auto-Bericht selbst bleibt unverändert; `report` erzeugt keine Detailberichte.

- Dateien: `reports/details_restore_<stempel>.txt`, `reports/details_transcode_<stempel>.txt`, `reports/details_qc_<stempel>.txt`; jeden Tag alle drei, auch ohne Jobs.
- Zeitraum: alle Jobs, deren Report die Job-Schleife (`run`) seit dem letzten Detailbericht der Stufe eingesammelt hat, ohne Lücke und ohne Überschneidung. Test-Jobs zählen nicht.
- Schlägt ein Detailbericht fehl, steht das im Protokoll; der nächste Detailbericht der Stufe deckt den Zeitraum mit ab.
- Erfasst werden Jobs ab Version 1.14.0.

**Kopf:**

| Stufe | Zahlen |
| --- | --- |
| Restore | Jobs insgesamt, ok, Fehlgeschlagen (davon endgültig) |
| Transcode | Jobs insgesamt, ok, Fehlgeschlagen (davon endgültig), Blockiert |
| QC | Jobs insgesamt, QC bestanden, QC nicht bestanden, QC-Fehler (davon endgültig), Blockiert |

QC zusätzlich: „Nicht bestanden nach Kriterium“ – wie oft jedes Kriterium bei den abgelehnten Jobs durchgefallen ist (je Job einmal gezählt), häufigstes zuerst.

**Details:** ein Block je Job, der nicht ok war, in der Reihenfolge des Einsammelns. Bestandene Jobs stehen nur als Zahl im Kopf.

~~~text
#1  REJECTED  DEFA01078 ... bißchen Liebe
    clip_id 412505 · Kollektion DEFA Dokumentation · Preset proxy_standard · Worker PP-DESKTOP-05
    Job      20261009T121652905452__412505__qc1
    Zeit     2026-10-09 14:17:40
    Ergebnis 50566716_412505_10Mbit.mp4: nicht bestanden (1 von 3 Tools): stream_specs(video_1080p)
    Fehler   stream_specs(video_1080p): fps erwartet 24 | 25, gefunden 50 (Stream 0)
    Ist      Stream 0: width=1920, height=1080, scan=progressive, fps=50, codec=h264, bitrate=10.04M
    Ablage   .marathon/qc/archiv/20261009T121652905452__412505__qc1.aqc.json
~~~

| Status | Bedeutung |
| --- | --- |
| `REJECTED` | QC nicht bestanden; `Fehler` (Soll/Ist je Abweichung) und `Ist` bzw. `Info` aus dem Prüfbericht; „Prüfbericht fehlt“, wenn keiner lesbar ist |
| `FAILED` | vom Worker als `failed` gemeldet oder von Marathon verworfen (Ergebnis beginnt mit `Marathon:`); `Versuch n von max_job_attempts`, „(endgültig)“ beim letzten Versuch |
| `BLOCKIERT` | Ergebnis ok, aber Auslieferung oder neuer Master blockiert (`Marathon: …`) |

`Ablage` zeigt den archivierten Ausgang des Jobs, sofern vorhanden.

## Wieder freigeben (`retry-restore`, `retry-transcode`, `retry-qc`)

Gibt alle inaktiven Clips einer Stufe wieder frei, z. B. nach einer geänderten QC-Metrik oder nachdem eine Blockierung beseitigt wurde.

- Restore hat je Clip genau einen Versuch; `retry-restore` gibt unvollständig restaurierte Clips für einen neuen Sammeljob frei.
- Freigegeben werden alle Clips der Stufe ohne laufenden Job mit einem dieser Gründe: `QC nicht bestanden`, `Job endgültig fehlgeschlagen`, `Neuer Master blockiert`, `Auslieferung blockiert`, `Zuordnung beim Neuaufbau unklar`, `Nicht mehr im Index`.
- Ohne Vorschau und ohne Bestätigung. Das Log zeigt die Anzahl je Kollektion und die Anzahl der Clips mit laufendem Job (übersprungen).
- Die Versuche werden auf 0 gesetzt. Die Clips bleiben in ihrer Stufe und behalten ihre Eingangszeit; die Job-Schleife legt die Jobs wie gewohnt nach Prioliste und `[limits]` aus.
- Gründe, die Marathon in jedem Job-Zyklus selbst prüft (`Verloren – Master fehlt vor Transcode`, `Verloren – Proxy fehlt`, `Veritone-ID fehlt`), bleiben unberührt; sie entfallen von selbst, sobald Datei bzw. ID vorhanden sind.
- Im Verlauf des Clips steht „Für <Stufe> wieder freigegeben“ mit dem bisherigen Grund.
- Auch bei angehaltener Job-Schleife oder offenem Test-Lauf möglich; die Jobs entstehen, sobald die Job-Schleife läuft.

Empfohlener Ablauf nach einer geänderten QC-Metrik: Metrik anpassen → `test-qc` (Testbericht prüfen) → `retry-qc`.

## Ingest (vorhandene Master und Proxys)

~~~bash
Marathon> ingest-master
Marathon> ingest-proxy
python marathon.py ingest-proxy    # oder direkt beim Start
~~~

- Laufen nur, wenn der Befehl eingegeben wird – nie automatisch. Die Job-Schleife darf dabei laufen.
- Geprüft werden nur Dateien direkt im Ordner; Unterordner, Systemdateien und Dateien auf `.tmp`, `.part`, `.partial`, `.json`, `.txt`, `.log` werden übersprungen.
- DEFA-ID = Text bis zum nächsten `__`. Titel und Zusätze spielen für den Abgleich keine Rolle.
- Abgleich: DEFA-ID gegen den Identifier (`001 Identifier`) der Clips in der JSON, ohne Unterscheidung von Groß-/Kleinschreibung.
- Beide Befehle können beliebig oft laufen.

### `ingest-master`

**Masterordner** (`[ingest] master_dir`, vollständiger Pfad), Namensschema `<DEFA-ID>__<Titel>.<Endung>`, z. B. `DEFA14097__Rosa Luxemburg - Stationen ihres Lebens.mov`. Hier legt Marathon auch neue Master aus Transcode ab; für deren Clips meldet `ingest-master` nur den Hinweis `Clip nicht mehr im Restore` und ändert nichts.

**Eintrag** – bei genau einer Masterdatei und genau einem Clip in `Queue Restore`:

~~~json
"files": {
  "master": {
    "folder": "\\\\10.0.77.11\\Ablage KI Proxy_1\\++ Master repariert",
    "names": ["DEFA14097__Rosa Luxemburg - Stationen ihres Lebens.mov"],
    "source": "Ingest",
    "last_seen_at": "..."
  },
  "proxy": null
}
~~~

- Der Restore gilt als abgeschlossen: Stufe `transcode`, Versuche auf 0; ein endgültig fehlgeschlagener Job wird aufgehoben, der Clip ist wieder aktiv.
- Ein offener Restore-Sammeljob wird als Ganzes zurückgezogen; seine übrigen Clips plant der nächste Job-Zyklus neu, ebenso den Transcode-Job. Läuft der Sammeljob, wird nichts eingetragen (Fehler „Job läuft“).
- History: `Restore abgeschlossen – Master per Ingest` (mit Pfad der Masterdatei) und `Weiter an Transcode`.
- Masterdateien im Masterordner werden nie verschoben oder gelöscht, auch nicht nach bestandenem QC. Fehlt eine eingetragene Masterdatei vor dem Transcode, wird der Clip als `Verloren – Master fehlt vor Transcode` inaktiv.
- `delete-folder` behält eingetragene Ingest-Master, solange die Datei vorhanden ist.

### `ingest-proxy`

**Proxyordner** (`[ingest] proxy_dir`, vollständiger Pfad auf demselben Netzlaufwerk wie `root_path`), Namensschema `<proxy_prefix>__<DEFA-ID>__<Titel>.mp4`, z. B. `(c)PROGRESS__10Mbit__DEFA14097__Rosa Luxemburg - Stationen ihres Lebens.mp4`. Die Endung entspricht der von `proxy_name`.

**Eintrag** – bei genau einer Proxydatei und genau einem Clip in `Queue Restore` oder `Queue Transcode` mit Veritone-ID:

- Die Datei wird in den QC-Eingang der Kollektion verschoben und nach `proxy_name` umbenannt (DEFA: `<defa_dir>/<work_dir>/<Kollektion>/qc/eingang`, sonst `<Kollektion>/<work_dir>/qc/eingang`).

~~~json
"files": {
  "master": null,
  "proxy": {
    "folder": "DEFA/.marathon/<Kollektion>/qc/eingang",
    "name": "1234567_98765_10Mbit.mp4",
    "source": "Ingest",
    "last_seen_at": "..."
  }
}
~~~

- Restore und Transcode gelten als abgeschlossen: Stufe `qc`, Versuche auf 0; ein endgültig fehlgeschlagener Job wird aufgehoben, ein offener Job zurückgezogen. `files.master` bleibt unverändert (ohne Restore `null`). Der nächste Job-Zyklus legt den QC-Job aus.
- History: `Restore und Transcode abgeschlossen – Proxy per Ingest` bzw. `Transcode abgeschlossen – Proxy per Ingest` mit `<alter Pfad> → <neuer Pfad>`, danach `Weiter an QC`.
- Danach läuft der Proxy wie ein transkodierter durch QC und wird nach bestandenem QC in den Zielordner ausgeliefert.

### Fehler und Hinweise

Nicht eingetragene Dateien bleiben unverändert liegen.

| Art | Meldung | Befehl |
| --- | --- | --- |
| Fehler | DEFA-ID mehrfach in der JSON | beide |
| Fehler | Mehrere Dateien mit derselben DEFA-ID | beide |
| Fehler | Dateiname passt nicht zum Schema | beide |
| Fehler | Datei ist leer | beide |
| Fehler | Job läuft oder wurde gerade übernommen (Befehl später wiederholen) | beide |
| Fehler | Clip inaktiv (anderer Grund als fehlgeschlagener Job, z. B. Zuordnung unklar) | beide |
| Fehler | Veritone-ID fehlt (zuerst `update-index`) | `ingest-proxy` |
| Fehler | Namenskonflikt im QC-Eingang | `ingest-proxy` |
| Fehler | QC-Eingang nicht nutzbar / Verschieben nicht möglich | `ingest-proxy` |
| Hinweis | DEFA-ID nicht in der JSON | beide |
| Hinweis | Bereits per Ingest eingetragen | `ingest-master` |
| Hinweis | Clip nicht mehr im Restore (Transcode, QC oder bereit) | `ingest-master` |
| Hinweis | Clip schon in QC oder bereit | `ingest-proxy` |
| Hinweis | Andere Endung als `.mp4` (ignoriert) | `ingest-proxy` |

Fehler und Hinweise stehen in `reports/errors/ingest-master_<stempel>_errors.txt` bzw. `reports/errors/ingest-proxy_<stempel>_errors.txt`, die Zahlen im Protokoll.

## Test-Modus

Test-Jobs laufen wie Produktions-Jobs durch die Worker (Restore, Transcode, QC); Marathon sammelt die Reports ein, ändert aber weder `state/marathon.json` noch Dateien der Produktion.

~~~bash
Marathon> test           # Test-Lauf starten oder offenen Test-Lauf fortsetzen
Marathon> test-qc        # QC-Testliste aus der JSON erzeugen und Test-Lauf starten
Marathon> test-restore   # Test-Lauf mit einem Restore-Test-Job (Clips wie kleiner Job)
Marathon> test-cancel    # Test-Lauf vorzeitig beenden
python marathon.py test  # oder direkt beim Start
python marathon.py test-qc
~~~

**Testliste** (`res/test_jobs.json`, Name über `[test] test_file`):

~~~json
{
  "schema_version": 1,
  "tests": [
    { "name": "Proxy mit FFE-Tafel", "stage": "QC", "clip_id": "98765" },
    { "name": "Kalibrierclip Stille", "stage": "QC", "clip_id": "98765",
      "fields": { "input": "DEFA/AQC/Kalibrierung/stille.mp4", "ffe_tafel": false } },
    { "stage": "Transcode", "clip_id": "98766" },
    { "stage": "Restore", "clip_id": "98767" }
  ]
}
~~~

| Schlüssel | Pflicht | Bedeutung |
| --- | --- | --- |
| `stage` | ja | `Restore`, `Transcode` oder `QC` |
| `clip_id` | ja | Clip aus `state/marathon.json`; liefert alle Job-Felder |
| `name` | nein | Bezeichnung im Testbericht (Standard `<Stufe> <clip_id>`) |
| `fields` | nein | Job-Felder, die ersetzt oder ergänzt werden; nicht erlaubt: `schema_version`, `job_id`, `stage`, `clip_id`, `created_at`, `report_folder`, `output_folder`, `test` |

- Job-Felder ohne Angabe in `fields` kommen wie im Produktionsbetrieb aus der JSON: QC `input` = aktueller Proxy des Clips (QC-Eingang oder Zielordner), Transcode `inputs` = Master des Clips und `proxy_name`, Restore `items` = alle Dateien des Clips (ein Sammeljob mit einem Clip; Bänder wie im Produktionsbetrieb). Hat der Clip keinen Proxy bzw. Master oder keine Veritone-ID, müssen `fields` die Werte angeben.
- Werte in `fields` prüft Marathon nicht; so lassen sich auch ungültige Jobs testen.
- Ist ein Eintrag ungültig, startet kein Test-Lauf; das Protokoll nennt alle fehlerhaften Einträge.

**QC-Testliste aus der JSON (`test-qc`):**

- `test-qc` schreibt `res/test_jobs_qc.json` neu und startet damit einen Test-Lauf wie `test`. `res/test_jobs.json` bleibt unberührt.
- Aufgenommen wird jeder Clip, dessen Proxy laut JSON im QC-Eingang seiner Kollektion liegt (z. B. nach `ingest-proxy`), aktiv oder inaktiv. Die Proxy-Datei muss vorhanden und größer als 0 Byte sein.
- Übersprungene Clips (Proxy fehlt oder ist leer) zählt das Protokoll; Details in `reports/errors/test-qc_<stempel>_errors.txt`.
- Reihenfolge: Abschnitt `[QC]` der Prioliste, dann Eingangszeit in der QC-Queue.
- Je Clip ein Eintrag `{ "name": "<Identifier> <Titel>", "stage": "QC", "clip_id": "…" }` ohne `fields`; `input`, `ffe_tafel` und `ffe_reference_image` kommen beim Auslegen aus der JSON.
- Ist ein Test-Lauf offen, erzeugt `test-qc` keine Liste und bricht ab (`test` setzt fort, `test-cancel` beendet). Ohne passenden Clip startet kein Test-Lauf.

**Restore-Test aus der JSON (`test-restore`):**

- Legt einen Test-Lauf mit genau einem Restore-Test-Job an. Die Clips wählt Marathon aus den wartenden Clips der JSON nach der Regel des kleinen Jobs; Hauptbänder offener und laufender Produktions-Jobs sind gesperrt. `state/marathon.json` bleibt unberührt.
- `output_folder` = `<work_dir>/test/restore/ausgang/<job_id>`; das Ergebnis bleibt liegen. Job-Datei, Report und Teilberichte werden archiviert, nichts ausgewertet.
- Der Testbericht zeigt je Clip `vollständig` oder `unvollständig` mit Gründen.
- Ist ein Test-Lauf offen, bricht `test-restore` ab (wie `test-qc`). Ohne wartenden Clip auf einem freien Band startet kein Test-Lauf.

**Ablauf:**

- `test` und `test-qc` halten die Job-Schleife an und legen aus der Testliste einen Test-Lauf an. Ist noch ein Test-Lauf offen, wird er mit seiner ursprünglichen Testliste fortgesetzt.
- Jeder Test-Zyklus (`cycle_seconds`) legt Test-Jobs in der Reihenfolge der Testliste nach `<work_dir>/<stufe>/offen`, höchstens so viele offene Test-Jobs je Stufe, wie `[limits]` erlaubt (Restore: `restore_big_job` + `restore_small_job`), verfolgt die Übernahme und sammelt die Reports ein.
- Job-Datei und Report werden wie im Produktionsbetrieb nach `<work_dir>/<stufe>/archiv/` verschoben. Das Ergebnis jedes Test-Jobs bleibt in `<work_dir>/test/<stufe>/ausgang/<job_id>` liegen (z. B. die `.aqc.json` des QC).
- Ohne Wirkung auf die Produktion: Die JSON wird nicht geschrieben; Proxys, Master und Eingänge werden weder verschoben noch gelöscht oder ausgeliefert; kein EditShare-Feld; kein neuer Versuch bei `failed`. Eine verschwundene Test-Job-Datei wird nach 30 Minuten neu ausgelegt.
- Arbeitsordner und FFE-Referenzdateien stellt Marathon wie in jedem Job-Zyklus bereit.
- Sind alle Tests fertig, schreibt Marathon den Testbericht `reports/test_<stempel>.txt` und beendet den Test-Modus.
- `test-cancel` sammelt vorliegende Reports ein, zieht nicht übernommene Test-Jobs zurück und schreibt den Testbericht. Reports bereits laufender Test-Jobs werden im nächsten Test-Lauf archiviert, aber nicht gewertet.
- `run` und `stop` halten den Test-Modus an; der Test-Lauf bleibt offen. Die Job-Schleife lässt Test-Jobs und ihre Reports liegen, der Test-Modus ebenso Produktions-Jobs und deren Reports.
- Liegen beim Start noch Produktions-Jobs in `offen` oder `laufend`, meldet Marathon das: Worker nehmen ältere Jobs zuerst.
- `delete-folder` ist gesperrt, solange ein Test-Lauf offen ist; danach löscht es auch `<work_dir>/test/` mit dem Arbeitsordner.

**Testbericht** (`reports/test_<stempel>.txt`):

- Kopf: Testliste, Start, Bericht, Anzahl Tests, `Ergebnisse` (vom Worker gemeldet, nach Status) und getrennt davon `Abgebrochen` bzw. `Nicht ausgelegt`. Sind Stufe, Preset oder Ausgangsordner bei allen Tests gleich, stehen sie nur im Kopf.
- Je Test ein Block wie im Detailbericht: `#<Nr>  <STATUS>  <Test>`, dann clip_id, Worker, Job und Ergebnis. Bei abgelehnten QC-Tests zusätzlich `Fehler` und `Ist` aus dem Prüfbericht im Test-Ausgang, bei Restore-Tests je Clip eine Zeile `Clip` mit `vollständig`/`unvollständig` und Gründen.
- Am Ende die Hinweise des Test-Laufs.

| Status | Bedeutung |
| --- | --- |
| `ok`, `failed`, `rejected` | vom Worker gemeldet |
| `nicht ausgelegt` | Clip liefert die Job-Felder beim Auslegen nicht mehr |
| `abgebrochen` | durch `test-cancel` beendet |

## Konfiguration (`res/config.ini`)

Alle Einträge sind Pflicht. Fehlt die Datei oder ist ein Eintrag fehlerhaft, pausiert Marathon, bis sie korrigiert ist. Änderungen in `[paths]` sowie an `reference_image` und `reference_clip_dir` pausieren Marathon bis zum Neustart oder zur Rücknahme; Änderungen in `[ingest]` und `[test]` gelten ohne Neustart.

| Abschnitt | Eintrag | Bedeutung |
| --- | --- | --- |
| paths | root_path | Netzlaufwerk mit allen Zielordnern |
| paths | defa_dir | Zielordner aller DEFA-Kollektionen |
| paths | work_dir | Arbeitsordner von Marathon (z. B. `.marathon`) |
| paths | defa_marker | Kollektionen mit diesem Text im Namen liefern nach `defa_dir` |
| paths | proxy_name | Dateiname aller Proxys mit den Platzhaltern `{veritone_id}` und `{clip_id}` (beide genau einmal, mit Endung), z. B. `{veritone_id}_{clip_id}_10Mbit.mp4` |
| paths | cred_file | Searcher-Zugang im res-Ordner |
| paths | mapping_file | Kollektionsmapping im res-Ordner |
| paths | priority_file | Prioliste im res-Ordner |
| operation | auto_report_time | Uhrzeit des täglichen Auto-Berichts (HH:MM) |
| operation | retry_minutes | Wartezeit nach fehlgeschlagenem Auto-Bericht |
| timing | cycle_seconds | Sekunden zwischen zwei Job-Zyklen |
| timing | max_job_attempts | Versuche je Job, danach dauerhaft fehlgeschlagen |
| limits | restore_big_job | Maximal gleichzeitige große Restore-Jobs, offen oder laufend (0 = keine neuen großen Jobs) |
| limits | restore_small_job | Maximal gleichzeitige kleine Restore-Jobs, offen oder laufend (0 = keine neuen kleinen Jobs) |
| limits | transcode / qc | Maximal offene Jobs je Stufe (0 = keine neuen Jobs) |
| restore | small_job_clips | Höchstens so viele Clips in einem kleinen Restore-Job (ab 1, vorgesehen 10) |
| heartbeat | worker_timeout_minutes | Minuten ohne Lebenszeichen, bis ein Worker als ausgefallen gilt |
| heartbeat | max_job_hours | Stunden, ab denen ein laufender Job im Bericht gemeldet wird |
| veritone | base_url | Basis-URL der Veritone Assets-API |
| veritone | token_file | `.env`-Datei im res-Ordner mit der Zeile `vt_api_token=<Token>` |
| veritone | field_clip_id | Veritone-Feld mit dem Barcode (= 001 Identifier) |
| ffe | list_file | FFE-Liste, Pfad relativ zum res-Ordner |
| ffe | reference_image | Referenz-Screenshot im Ordner `reference_clip_dir`; Name auch auf dem SMB |
| ffe | reference_clip_dir | Ordner im res-Ordner mit allen FFE-Filmtafel-Clips; nur `.mov` zählen als Clips, mindestens einer nötig; Name auch auf dem SMB |
| ingest | master_dir | Ordner mit Masterdateien `<DEFA-ID>__<Titel>.<Endung>` (vollständiger Pfad, gleiches Netzlaufwerk wie `root_path`); `ingest-master` liest ihn, neue Master aus Transcode legt Marathon hier ab (ohne Überschreiben) |
| ingest | proxy_dir | Ordner mit vorhandenen Proxys `<proxy_prefix>__<DEFA-ID>__<Titel>.mp4` (vollständiger Pfad, gleiches Netzlaufwerk wie `root_path`); nur `ingest-proxy` liest ihn |
| ingest | proxy_prefix | Namensanfang der Proxys in `proxy_dir` (ohne das folgende `__`), z. B. `(c)PROGRESS__10Mbit` |
| test | test_file | Testliste im res-Ordner für `test` (z. B. `test_jobs.json`); wird bei jedem neuen Test-Lauf gelesen, muss erst dann vorhanden sein |

## Ausgaben

- `log/marathon.log` – Protokoll
- `reports/<art>_<stempel>.txt` – Berichte; Gesamt zählt alle Clips der JSON, auch inaktive, jeweils in ihrer aktuellen Stufe bzw. unter Bereit
- `reports/errors/index_<stempel>_errors.txt` – Fehlerliste von `update-index` (inklusive nicht gefundener FFE-Titel)
- `reports/errors/ffe_<stempel>_errors.txt` – nicht gefundene FFE-Titel von `update-ffe`
- `reports/errors/<index|ffe>_<stempel>_ffe_uneindeutig.txt` – uneindeutige FFE-Treffer
- `reports/errors/ingest-master_<stempel>_errors.txt` – nicht eingetragene Masterdateien und Hinweise von `ingest-master`
- `reports/errors/ingest-proxy_<stempel>_errors.txt` – nicht übernommene Proxys und Hinweise von `ingest-proxy`
- `reports/details_<restore|transcode|qc>_<stempel>.txt` – Detailberichte, täglich nach dem Auto-Bericht
- `reports/test_<stempel>.txt` – Testbericht eines Test-Laufs
- `state/journal_<stufe>.jsonl` – Job-Protokoll seit dem letzten Detailbericht; danach in `state/journal/details_<stufe>_<stempel>.jsonl`
- `reports/errors/test-qc_<stempel>_errors.txt` – von `test-qc` übersprungene Clips
- `reports/transfer_<stempel>.txt`, `reports/errors/transfer_<stempel>_errors.txt`, `state/backup/marathon.v7_<stempel>.json` – Bericht, Fehlerbericht und Sicherung des Transfer-Scripts
- `test/test.json` – Stand des Test-Modus (offener Test-Lauf, IDs aller Test-Jobs); nicht löschen, solange Test-Jobs auf dem SMB liegen
