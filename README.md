# Marathon

Marathon baut aus EditShare-Suche und Veritone einen Clip-Index (JSON), legt Restore-, Transcode- und QC-Jobs nach Prioliste für die Worker aus und erstellt Berichte. Zusätzlich markiert Marathon Clips, die die FFE-Filmtafel benötigen, stellt den Workern die Referenzdateien bereit und übernimmt auf Befehl vorhandene Master (`ingest-master`) und vorhandene Proxys (`ingest-proxy`). Im Test-Modus (`test`) laufen Test-Jobs durch die Worker, ohne den Produktionsstand zu ändern.

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

`marathon.py` und `core/` gehören immer zusammen: Bei einem Update beide vollständig ersetzen; `res/`, `log/`, `state/`, `reports/` und `test/` bleiben unverändert.

`log/`, `state/`, `reports/`, `reports/errors/` und `test/` legt Marathon selbst an. Der Index liegt in `state/marathon.json` (JSON-Version 7), das Job-Protokoll für die Detailberichte in `state/journal_<stufe>.jsonl`, der Stand des Test-Modus in `test/test.json`.

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
| `test-cancel` | Offenen Test-Lauf beenden: nicht übernommene Test-Jobs zurückziehen, Testbericht schreiben |
| `auto-report` | Täglichen Auto-Bericht einschalten (ab `auto_report_time`); danach je Stufe ein Detailbericht |
| `auto-report-off` | Täglichen Auto-Bericht ausschalten |
| `report` | Manuellen Bericht sofort erstellen |
| `create-folders` | Ordnerstruktur aller Kollektionen anlegen und FFE-Referenzen bereitstellen |
| `update-index` | Neue Suche (EditShare ∩ Veritone), neue Clips aufnehmen, fehlende Felder (z. B. Veritone-ID) ergänzen, Abweichungen melden, danach FFE-Abgleich |
| `update-ffe` | Nur FFE-Liste mit der bestehenden JSON abgleichen, ohne Suche |
| `ingest-master` | Masterdateien aus `master_dir` über die DEFA-ID abgleichen und eintragen (weiter an Transcode); nur auf Befehl |
| `ingest-proxy` | Proxys aus `proxy_dir` über die DEFA-ID abgleichen, umbenannt in den QC-Eingang verschieben (weiter an QC); nur auf Befehl |
| `retry-qc` | Alle Clips mit „QC nicht bestanden“ zur QC-Neuprüfung freigeben; Bestätigung mit `freigeben` (siehe QC-Neuprüfung) |
| `delete-folder` | SMB-Arbeitsordner bereinigen; Index bleibt, Prozesszustand wird neu aufgebaut. Bei Clip-/Mediendateien Bestätigung mit `loeschen`; gesperrt bei offenem Test-Lauf |
| `status` | Anzeigen, was eingeschaltet ist, und Stand des Test-Laufs |
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

## Prioliste und Jobs

- `res/priority.txt`: je Abschnitt `[Restore]`, `[Transcode]`, `[QC]` eine Kollektion pro Zeile, oben = höchste Priorität. Nicht aufgeführte Kollektionen folgen in der Reihenfolge von `collections.json`.
- Marathon liest die Prioliste in jedem Job-Zyklus und legt pro Stufe höchstens so viele Jobs nach `<work_dir>/<stufe>/offen`, wie `[limits]` erlaubt (gezählt werden offene Jobs).
- Worker nehmen den ersten Job in `offen` (nach Dateiname = Erstellreihenfolge). Eine geänderte Prioliste wirkt auf neu ausgelegte Jobs.

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

**Job-Felder (Job-`schema_version` 5), Pfade relativ zu `root_path` (Ausnahme: `inputs` von Ingest-Mastern):**

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
- Der neue Master wird nach `[ingest] master_dir` verschoben, nie überschrieben. Bei Namenskonflikt oder wenn das Verschieben nicht möglich ist, wird der Clip inaktiv (`Neuer Master blockiert`), der Ausgang archiviert, nichts gelöscht.
- Danach verfolgt Marathon den neuen Master nicht weiter (nur History `Neuer Master abgelegt`); `delete-folder` ordnet ihn nicht wieder zu.

**Nach QC:**

| QC | Proxy | Master aus Restore | Neuer Master in `master_dir` | EditShare-Feld |
| --- | --- | --- | --- | --- |
| bestanden | in den Zielordner | sofort gelöscht | bleibt | wird gesetzt |
| nicht bestanden | bleibt im QC-Eingang | bleibt | bleibt | – |

- Reihenfolge bei bestandenem QC: Proxy ausliefern, Master aus Restore löschen, EditShare-Feld setzen. Masterdateien aus `ingest-master` werden nie gelöscht.
- Vor der Auslieferung muss der Proxy vorhanden und größer als 0 Byte sein.
- QC nicht bestanden: Clip inaktiv (`QC nicht bestanden`), Eintrag in der Fehlerliste des Berichts, Gründe im Detailbericht QC.
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

## QC-Neuprüfung (`retry-qc`)

Gibt alle Clips mit „QC nicht bestanden“ erneut zur QC frei, z. B. nach einer geänderten QC-Metrik.

- `retry-qc` zeigt zuerst eine Vorschau: Anzahl der Clips je Kollektion und Anzahl der übersprungenen. Erst `freigeben` führt die Freigabe aus; jede andere Eingabe bricht ab, ohne etwas zu ändern.
- Freigegeben werden Clips in der Stufe QC ohne laufenden Job, deren Proxy im QC-Eingang liegt und nicht leer ist. Alle anderen stehen in `reports/errors/retry-qc_<stempel>_errors.txt`, Abschnitt „Nicht zur QC-Neuprüfung freigegeben“.
- Die Clips behalten ihre ursprüngliche Eingangszeit. Die Job-Schleife legt die neuen QC-Jobs wie gewohnt nach Prioliste und `[limits] qc` aus; die Ergebnisse stehen im nächsten Detailbericht QC.
- Im Verlauf des Clips steht „Zur QC-Neuprüfung freigegeben“ mit dem bisherigen Grund.
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
- Ein offener Restore-Job wird zurückgezogen. Der nächste Job-Zyklus legt den Transcode-Job aus.
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
Marathon> status         # Fortschritt des Test-Laufs
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

- Job-Felder ohne Angabe in `fields` kommen wie im Produktionsbetrieb aus der JSON: QC `input` = aktueller Proxy des Clips (QC-Eingang oder Zielordner), Transcode `inputs` = Master des Clips und `proxy_name`, Restore `files` und `hashes`. Hat der Clip keinen Proxy bzw. Master oder keine Veritone-ID, müssen `fields` die Werte angeben.
- Werte in `fields` prüft Marathon nicht; so lassen sich auch ungültige Jobs testen.
- Ist ein Eintrag ungültig, startet kein Test-Lauf; das Protokoll nennt alle fehlerhaften Einträge.

**QC-Testliste aus der JSON (`test-qc`):**

- `test-qc` schreibt `res/test_jobs_qc.json` neu und startet damit einen Test-Lauf wie `test`. `res/test_jobs.json` bleibt unberührt.
- Aufgenommen wird jeder Clip, dessen Proxy laut JSON im QC-Eingang seiner Kollektion liegt (z. B. nach `ingest-proxy`), aktiv oder inaktiv. Die Proxy-Datei muss vorhanden und größer als 0 Byte sein.
- Übersprungene Clips (Proxy fehlt oder ist leer) zählt das Protokoll; Details in `reports/errors/test-qc_<stempel>_errors.txt`.
- Reihenfolge: Abschnitt `[QC]` der Prioliste, dann Eingangszeit in der QC-Queue.
- Je Clip ein Eintrag `{ "name": "<Identifier> <Titel>", "stage": "QC", "clip_id": "…" }` ohne `fields`; `input`, `ffe_tafel` und `ffe_reference_image` kommen beim Auslegen aus der JSON.
- Ist ein Test-Lauf offen, erzeugt `test-qc` keine Liste und bricht ab (`test` setzt fort, `test-cancel` beendet). Ohne passenden Clip startet kein Test-Lauf.

**Ablauf:**

- `test` und `test-qc` halten die Job-Schleife an und legen aus der Testliste einen Test-Lauf an. Ist noch ein Test-Lauf offen, wird er mit seiner ursprünglichen Testliste fortgesetzt.
- Jeder Test-Zyklus (`cycle_seconds`) legt Test-Jobs in der Reihenfolge der Testliste nach `<work_dir>/<stufe>/offen`, höchstens so viele offene Test-Jobs je Stufe, wie `[limits]` erlaubt, verfolgt die Übernahme und sammelt die Reports ein.
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
- Je Test ein Block wie im Detailbericht: `#<Nr>  <STATUS>  <Test>`, dann clip_id, Worker, Job und Ergebnis. Bei abgelehnten QC-Tests zusätzlich `Fehler` und `Ist` aus dem Prüfbericht im Test-Ausgang.
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
| limits | restore / transcode / qc | Maximal offene Jobs je Stufe (0 = keine neuen Jobs) |
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
- `reports/<art>_<stempel>.txt` – Berichte
- `reports/errors/index_<stempel>_errors.txt` – Fehlerliste von `update-index` (inklusive nicht gefundener FFE-Titel)
- `reports/errors/ffe_<stempel>_errors.txt` – nicht gefundene FFE-Titel von `update-ffe`
- `reports/errors/<index|ffe>_<stempel>_ffe_uneindeutig.txt` – uneindeutige FFE-Treffer
- `reports/errors/ingest-master_<stempel>_errors.txt` – nicht eingetragene Masterdateien und Hinweise von `ingest-master`
- `reports/errors/ingest-proxy_<stempel>_errors.txt` – nicht übernommene Proxys und Hinweise von `ingest-proxy`
- `reports/details_<restore|transcode|qc>_<stempel>.txt` – Detailberichte, täglich nach dem Auto-Bericht
- `reports/test_<stempel>.txt` – Testbericht eines Test-Laufs
- `state/journal_<stufe>.jsonl` – Job-Protokoll seit dem letzten Detailbericht; danach in `state/journal/details_<stufe>_<stempel>.jsonl`
- `reports/errors/test-qc_<stempel>_errors.txt` – von `test-qc` übersprungene Clips
- `reports/errors/retry-qc_<stempel>_errors.txt` – von `retry-qc` übersprungene Clips
- `test/test.json` – Stand des Test-Modus (offener Test-Lauf, IDs aller Test-Jobs); nicht löschen, solange Test-Jobs auf dem SMB liegen
