# Marathon

Marathon baut aus EditShare-Suche und Veritone einen Clip-Index (JSON), legt Restore-, Transcode- und QC-Jobs nach Prioliste für die Worker aus und erstellt Berichte. Zusätzlich markiert Marathon Clips, die die FFE-Filmtafel benötigen, und stellt den Workern die Referenzdateien bereit.

## Installation

Voraussetzung: Windows-Rechner mit Zugriff auf das Netzlaufwerk, Python 3.10 oder neuer.

~~~bash
pip config set global.extra-index-url https://artifacts.editshare.com/artifactory/api/pypi/editshare-pypi-public/simple
pip install "toolbox @ git+https://github.com/PROGRESS-MAM/TOOLBOX.git@main"
pip install "searcher[api] @ git+https://github.com/PROGRESS-MAM/ES-Search.git@main"
~~~

Projektordner:

~~~text
marathon.py
res/
  config.ini                           Konfiguration (siehe unten)
  cred.env                             FLOW_HOST, FLOW_USER, FLOW_PASSWORD und Veritone-Token
  collections.json                     Kollektionsmapping
  priority.txt                         Prioliste (wird beim ersten Lauf als Vorlage angelegt)
  FFE Filmerbe/
    FFE-Filmerbe-DEFA-Titel_ids.json   FFE-Liste
    FFE-Filmerbe-DEFA-Titel_Tafel.png  Referenz-Screenshot der FFE-Filmtafel
    *.mov                              alle FFE-Filmtafel-Clips, z. B. 2K_2_35.mov
~~~

`log/`, `state/`, `reports/` und `reports/errors/` legt Marathon selbst an. Der Index liegt in `state/marathon.json`.

Version 1.6.0 nutzt ein neues JSON- und Job-Format. Für den Umstieg `state/marathon.json` entfernen und mit `run` neu aufbauen.

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
| `update-index` | Neue Suche (EditShare ∩ Veritone), neue Clips aufnehmen, Abweichungen melden, danach FFE-Abgleich |
| `update-ffe` | Nur FFE-Liste mit der bestehenden JSON abgleichen, ohne Suche |
| `delete-folder` | SMB-Arbeitsordner bereinigen; Index bleibt, Prozesszustand wird neu aufgebaut. Bei Clip-/Mediendateien Bestätigung mit `loeschen` |
| `status` | Anzeigen, was eingeschaltet ist |
| `help` | Befehlsübersicht |
| `quit` | Marathon beenden |

Aliase: `exit` = `quit`, `manual-report` = `report`, `auto-report-on` = `auto-report`.

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

**Job-Felder (Job-`schema_version` 4), Pfade relativ zu `root_path`:**

| Job | Feld | Inhalt |
| --- | --- | --- |
| Transcode | `ffe_tafel` | `true`/`false` |
| Transcode | `ffe_reference_clips` | Liste aller FFE-Clips, z. B. `.marathon/worker/FFE Filmerbe/2K_2_35.mov` |
| QC | `ffe_tafel` | `true`/`false` |
| QC | `ffe_reference_image` | `.marathon/worker/FFE-Filmerbe-DEFA-Titel_Tafel.png` |

Maßgeblich ist der Wert beim Erstellen des Jobs.

## Konfiguration (`res/config.ini`)

Alle Einträge sind Pflicht. Fehlt die Datei oder ist ein Eintrag fehlerhaft, pausiert Marathon, bis sie korrigiert ist. Änderungen in `[paths]` sowie an `reference_image` und `reference_clip_dir` pausieren Marathon bis zum Neustart oder zur Rücknahme.

| Abschnitt | Eintrag | Bedeutung |
| --- | --- | --- |
| paths | root_path | Netzlaufwerk mit allen Zielordnern |
| paths | defa_dir | Zielordner aller DEFA-Kollektionen |
| paths | work_dir | Arbeitsordner von Marathon (z. B. `.marathon`) |
| paths | defa_marker | Kollektionen mit diesem Text im Namen liefern nach `defa_dir` |
| paths | proxy_prefix | Proxy-Namensschema `<proxy_prefix>__<Identifier>__<Titel>.<Endung>` |
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
| veritone | token_file | Veritone-Zugang im res-Ordner |
| veritone | field_clip_id | Veritone-Feld mit dem Barcode (= 001 Identifier) |
| ffe | list_file | FFE-Liste, Pfad relativ zum res-Ordner |
| ffe | reference_image | Referenz-Screenshot im Ordner `reference_clip_dir`; Name auch auf dem SMB |
| ffe | reference_clip_dir | Ordner im res-Ordner mit allen FFE-Filmtafel-Clips; nur `.mov` zählen als Clips, mindestens einer nötig; Name auch auf dem SMB |

## Ausgaben

- `log/marathon.log` – Protokoll
- `reports/<art>_<stempel>.txt` – Berichte
- `reports/errors/index_<stempel>_errors.txt` – Fehlerliste von `update-index` (inklusive nicht gefundener FFE-Titel)
- `reports/errors/ffe_<stempel>_errors.txt` – nicht gefundene FFE-Titel von `update-ffe`
- `reports/errors/<index|ffe>_<stempel>_ffe_uneindeutig.txt` – uneindeutige FFE-Treffer
