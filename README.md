# Marathon

Marathon baut aus EditShare-Suche und Veritone einen Clip-Index (JSON), legt Restore-, Transcode- und QC-Jobs nach Prioliste für die Worker aus und erstellt Berichte. Zusätzlich markiert Marathon Clips, die die FFE-Filmtafel benötigen, stellt den Workern die Referenzdateien bereit und übernimmt auf Befehl vorhandene Master (`ingest-master`) und vorhandene Proxys (`ingest-proxy`).

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
  cred.env                             FLOW_HOST, FLOW_USER, FLOW_PASSWORD und vt_api_token=<Token>
  collections.json                     Kollektionsmapping
  priority.txt                         Prioliste (wird beim ersten Lauf als Vorlage angelegt)
  FFE Filmerbe/
    FFE-Filmerbe-DEFA-Titel_ids.json   FFE-Liste
    FFE-Filmerbe-DEFA-Titel_Tafel.png  Referenz-Screenshot der FFE-Filmtafel
    *.mov                              alle FFE-Filmtafel-Clips, z. B. 2K_2_35.mov
~~~

`marathon.py` und `core/` gehören immer zusammen: Bei einem Update beide vollständig ersetzen; `res/`, `log/`, `state/` und `reports/` bleiben unverändert.

`log/`, `state/`, `reports/` und `reports/errors/` legt Marathon selbst an. Der Index liegt in `state/marathon.json` (JSON-Version 7).

## Start

~~~bash
python marathon.py                 # Konsole, Befehle mit Enter eingeben
python marathon.py run auto-report # Befehle direkt nach dem Start ausführen
~~~

Marathon läuft nur einmal pro Rechner (Sperre in `state/marathon.lock`).

## Befehle

| Befehl | Wirkung |
| --- | --- |
| `run` | Ordner und Referenzdateien anlegen, Index aufbauen falls keine JSON existiert, dann Job-Schleife starten |
| `stop` | Job-Schleife anhalten |
| `auto-report` | Täglichen Auto-Bericht einschalten (ab `auto_report_time`) |
| `auto-report-off` | Täglichen Auto-Bericht ausschalten |
| `report` | Manuellen Bericht sofort erstellen |
| `create-folders` | Ordnerstruktur aller Kollektionen anlegen und FFE-Referenzen bereitstellen |
| `update-index` | Neue Suche (EditShare ∩ Veritone), neue Clips aufnehmen, fehlende Felder (z. B. Veritone-ID) ergänzen, Abweichungen melden, danach FFE-Abgleich |
| `update-ffe` | Nur FFE-Liste mit der bestehenden JSON abgleichen, ohne Suche |
| `ingest-master` | Masterdateien aus `master_dir` über die DEFA-ID abgleichen und eintragen (weiter an Transcode); nur auf Befehl |
| `ingest-proxy` | Proxys aus `proxy_dir` über die DEFA-ID abgleichen, umbenannt in den QC-Eingang verschieben (weiter an QC); nur auf Befehl |
| `delete-folder` | SMB-Arbeitsordner bereinigen; Index bleibt, Prozesszustand wird neu aufgebaut. Bei Clip-/Mediendateien Bestätigung mit `loeschen` |
| `status` | Anzeigen, was eingeschaltet ist |
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

Nach Änderungen an der FFE-Liste genügt `update-ffe`.

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

**Masterordner** (`[ingest] master_dir`, vollständiger Pfad), Namensschema `<DEFA-ID>__<Titel>.<Endung>`, z. B. `DEFA14097__Rosa Luxemburg - Stationen ihres Lebens.mov`.

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

## Konfiguration (`res/config.ini`)

Alle Einträge sind Pflicht. Fehlt die Datei oder ist ein Eintrag fehlerhaft, pausiert Marathon, bis sie korrigiert ist. Änderungen in `[paths]` sowie an `reference_image` und `reference_clip_dir` pausieren Marathon bis zum Neustart oder zur Rücknahme; Änderungen in `[ingest]` gelten ohne Neustart.

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
| ingest | master_dir | Ordner mit vorhandenen Masterdateien `<DEFA-ID>__<Titel>.<Endung>` (vollständiger Pfad); nur `ingest-master` liest ihn |
| ingest | proxy_dir | Ordner mit vorhandenen Proxys `<proxy_prefix>__<DEFA-ID>__<Titel>.mp4` (vollständiger Pfad, gleiches Netzlaufwerk wie `root_path`); nur `ingest-proxy` liest ihn |
| ingest | proxy_prefix | Namensanfang der Proxys in `proxy_dir` (ohne das folgende `__`), z. B. `(c)PROGRESS__10Mbit` |

## Ausgaben

- `log/marathon.log` – Protokoll
- `reports/<art>_<stempel>.txt` – Berichte
- `reports/errors/index_<stempel>_errors.txt` – Fehlerliste von `update-index` (inklusive nicht gefundener FFE-Titel)
- `reports/errors/ffe_<stempel>_errors.txt` – nicht gefundene FFE-Titel von `update-ffe`
- `reports/errors/<index|ffe>_<stempel>_ffe_uneindeutig.txt` – uneindeutige FFE-Treffer
- `reports/errors/ingest-master_<stempel>_errors.txt` – nicht eingetragene Masterdateien und Hinweise von `ingest-master`
- `reports/errors/ingest-proxy_<stempel>_errors.txt` – nicht übernommene Proxys und Hinweise von `ingest-proxy`
