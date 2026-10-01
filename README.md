# Marathon 1.2.0

Marathon verwaltet den Clip-Index aus ES-Search, steuert Restore-, Transcode- und QC-Worker und erstellt Berichte.

## Installation und Umstieg

Voraussetzungen: Python 3.10+, `toolbox` (`tb_write_log`) und `searcher` (ES-Search) im Python-Pfad sowie Zugriff auf das Netzlaufwerk.

1. Skript als `marathon.py` im bisherigen Projektordner speichern.
2. Unter `res/` ablegen: `config.ini`, `cred.env`, `collections.json` und optional `priority.txt`.
3. `python marathon.py` starten. Marathon wartet auf Befehle.

Lokale Ordner `log/`, `state/` und `reports/errors/` legt Marathon an. Zugangsdaten nur in der lokalen Konfiguration, nicht im Skript speichern.

**Von 1.1.0:** Bestehende Config und JSON weiterverwenden. `stable_minutes` wird nicht mehr verwendet; ein vorhandener Eintrag wird zur Kompatibilität akzeptiert und kann entfernt werden. AQC-Sort bleibt unverändert.

**Von 1.0.x:** `report_only` und `aqc_dir` entfernen, `[limits] lto` in `restore` umbenennen; Priolistenabschnitt `[Restore]` statt `[LTO]`. JSON-Version 3 wird übernommen. Versionen 1 und 2 werden nicht automatisch umgestellt.

## Befehle

Job-Schleife und Auto-Berichte sind beim Start ausgeschaltet. Befehle in der Konsole:

| Befehl | Funktion |
|---|---|
| `run` | Fehlende Ordner anlegen; nur bei fehlender JSON den Index aus der Suche aufbauen; dann Job-Schleife starten |
| `stop` | Job-Schleife anhalten; externe Worker werden nicht gestoppt |
| `auto-report` | Auto-Berichte täglich ab `auto_report_time` einschalten |
| `auto-report-off` | Auto-Berichte ausschalten |
| `report` | Manuellen Bericht sofort erstellen, ohne Suche oder SMB-Änderungen |
| `create-folders` | Arbeitsordner aller Kollektionen anlegen |
| `update-index` | Neue Suche; neue Clips aufnehmen, Abweichungen zu bekannten Clips nur melden |
| `delete-folder` | SMB-Arbeitsordner bereinigen; Index behalten und Prozesszustand neu aufbauen |
| `status` / `help` | Betriebszustand / Befehlsübersicht |
| `quit` / `exit` | Marathon beenden |

Groß-/Kleinschreibung, Leerzeichen und Unterstriche sind egal: `Update Index` = `update-index`. Auch `auto-report on`, `auto-report off` und `manual report` sind möglich. Nach einem Neustart ist alles wieder ausgeschaltet.

Befehle können beim Start mitgegeben werden:

```console
python marathon.py run auto-report
python marathon.py update-index quit
python marathon.py report quit
python marathon.py delete-folder
```

Die Befehle werden in Reihenfolge abgearbeitet. Ohne `quit` bleibt die Konsole geöffnet. Bei `delete-folder` mit Clips kein vorab übergebenes `quit` verwenden: es würde die ausstehende Bestätigung abbrechen.

## SMB zum Abschluss bereinigen: delete-folder

1. Externe Worker beenden und laufende Jobs abschließen bzw. klären.
2. `delete-folder` eingeben. Marathon hält seine eigene Job-Schleife an.
3. Löschumfang prüfen. Gelöscht werden ausschließlich die Marathon-Arbeitsordner:
   - `<root_path>/.marathon/` einschließlich Prioliste und Heartbeats;
   - `<root_path>/<Ablageordner>/.marathon/` samt Kollektions- und Stufen-Unterordnern;
   - entsprechende Arbeitsordner ehemaliger Kollektionen direkt unter den SMB-Ablageordnern.
4. Bei Clip-/Mediendateien erscheint eine vollständige Dateiliste. Mit `loeschen` unwiderruflich bestätigen, mit `abbrechen` abbrechen. Jede andere Eingabe und EOF gelten nicht als Zustimmung.
5. Leere Ordner und Ordner mit nur Job-/Protokolldateien werden ohne zusätzliche Rückfrage gelöscht. `.json`, `.txt` und `.log` gelten als Job-/Protokolldateien; Medien und `.part/.tmp/.partial` lösen eine Warnung aus.

**Niemals gelöscht oder verändert:** finale Ablageordner und vorhandene Dateien darin, AQC, bestehende `unbekannt`-Ordner sowie lokale JSON, Logs, Reports und Konfiguration. Verknüpfungen/Junctions im Löschumfang führen zum Abbruch. AQC und beliebige andere Unterordner werden nicht nach Arbeitsordnern durchsucht.

**Worker-Schutz:** Ungeklärte Jobs unter `laufend/` blockieren, auch ohne frischen Heartbeat. Ein gültiger fertiger Jobreport kann den entsprechenden laufenden Job als abgeschlossen belegen. Frische Heartbeats, weiterhin gemeldete Jobs und nicht prüfbare Worker-Daten blockieren ebenfalls. Nach dem Beenden eines Workers mit leerem `job_id` muss dessen letzter Heartbeat mindestens `worker_timeout_minutes` alt sein. Marathon kann externe Prozesse nicht selbst beenden: Worker bis zum Abschluss ausgeschaltet lassen.

Direkt vor der Löschung werden Umfang, Datei-Größen/Änderungszeiten, Worker-Status und JSON erneut geprüft. Bei Änderungen ist `delete-folder` erneut nötig.

### JSON und Betrieb danach

- Keine neue Datenbanksuche; Clip-Index, Metadaten und Historie bleiben erhalten.
- Alte Job-Verweise und Fehlversuchszähler werden zurückgesetzt; Blockierungen aus dem alten Prozesszustand werden neu bewertet.
- Eindeutiger Proxy im richtigen finalen Ordner → `bereit`; verbliebener Proxy im QC-Eingang → QC; vollständige verbliebene Master → Transcode; sonst Restore.
- Mehrdeutige Zuordnung → inaktiv, `zuordnung_ungeklaert`, mit Fehlerdetails.
- Keine Ordner oder Jobs beim Neuaufbau. Die Job-Schleife bleibt auch nach Abbruch/Fehler aus. Auto-Berichte werden nicht automatisch ausgeschaltet.
- Erst ein erneutes `run` stellt fehlende Arbeitsordner wieder her und startet Jobs.
- Unvollständige/unterbrochene Bereinigung wird in der JSON markiert und verhindert `run`. Mit `delete-folder` erneut bereinigen. Lösch- und Neuaufbau-Ergebnisse stehen im lokalen Log.

## Berichte: finale Ablage

Zusätzlich zur Kollektions-Tabelle mit Deltas enthält jeder Report eine Tabelle **pro finalem Ablageordner**:

- **Unbekannt:** keine eindeutige Zuordnung zur JSON, einschließlich mehrdeutiger Zuordnung.
- **Unerwartet:** eindeutig zugeordnet, aber JSON-Status, Aktivität, Stufe oder gespeicherter/erwarteter Fundort passen nicht. Auch zusätzliche finale Dateien zum selben Clip und leere zugeordnete Dateien zählen hierzu.

Gezählt werden Dateien, nicht eindeutige Datenbank-Clips. Gemeinsamer DEFA-Ablageordner nur einmal. Nur Dateien direkt im finalen Ordner werden geprüft; Unterordner wie AQC und alte `unbekannt`-Ordner bleiben außen vor. System-, Protokoll- und temporäre Dateien werden nicht mitgezählt. Andere Dateien ohne passendes Namensschema werden als unbekannt gemeldet.

Zuordnung über gespeicherten Proxy-Dateinamen bzw. Identifier/Titel im Proxy-Namensschema. Im Error-Report: Datei/Fundort, Fehlergrund und bei eindeutiger Zuordnung Clip-Eintrag samt erwartetem Status/Ablageort.

**Nur melden:** Weder der Audit noch die Job-Schleife sortieren finale Dateien aus. Der Audit verändert keinen JSON-Status. Außerhalb des Prozesses abgelegte Clips dürfen liegen bleiben. Bei erstmaliger Aufnahme durch `update-index` oder beim ausdrücklich angeforderten Neuaufbau nach `delete-folder` kann ein bereits final vorhandener Proxy als Startzustand übernommen werden.

Ordner und Verschiebelogik für `unbekannt` entfallen. Bestehende Ordner bleiben unberührt.

## QC-Auslieferung und Namenskonflikte

Bei QC-Erfolg wird der Proxy final geliefert und erst nach bestätigter Auslieferung der Arbeits-Master entfernt.

Existiert bereits eine gleichnamige finale Datei:

- vorhandene Datei niemals überschreiben, löschen oder verschieben;
- neuen Proxy im QC-Eingang und Master behalten;
- `auslieferung_blockiert` statt `bereit`, Konflikt auf die Fehlerliste;
- kein automatischer weiterer QC-Versuch und kein zusätzlicher Fehlversuch.

Auch andere Auslieferungsfehler blockieren und erhalten Quelldaten soweit vorhanden. Unter Windows wird ohne Überschreiben umbenannt. Auf anderen Systemen wird der Zielname exklusiv neu angelegt und kopiert; bei Kopierfehlern können neue Teildaten im Ziel liegen, die nicht automatisch gelöscht werden. Bereits vorher vorhandene finale Dateien bleiben geschützt.

## Index

- Suche nur bei `update-index` und beim ersten `run` ohne JSON.
- Neue Clips werden aufgenommen. Metadatenänderungen, Kollektionswechsel und nicht mehr gefundene bekannte Clips nur melden; Indexdaten bleiben unverändert.
- Nicht aufgenommene Treffer: mehrere Kollektionen, ungültige Metadaten, doppelter Identifier/Titel, ungeeignete Dateinamen-/Hash-Angaben, mehrere passende Proxies, Platzhalter.
- Bei unvollständiger Suche bleibt die JSON unverändert. Meldungen des letzten Index-Laufs stehen bis zur nächsten Aktualisierung in jedem Bericht.
- `state/marathon.json` enthält Clip-Index und Prozesszustand; `res/collections.json` nur Suchbedingungen.

Beispiel für `collections.json`:

```json
{"schema_version": 1, "collections": [
  {"name": "Spielfilme", "filters": [{"field": "007 Collection PROGRESS", "value": "Spielfilme"}]}
]}
```

Erlaubte Suchfelder: `006 Source PROGRESS`, `007 Collection PROGRESS`, `101a Genre German`. Mehrere Filter werden mit UND verknüpft.

Aufnahme nach Ist-Zustand: finaler Proxy → bereit; Proxy im QC-Eingang → QC; vollständige Master im Transcode-Eingang → Transcode; sonst Restore.

## Ordner und Lebenszyklus

```text
<Projektordner>/
  marathon.py
  res/       config.ini, cred.env, collections.json, priority.txt
  state/     marathon.json, marathon.lock
  log/       marathon.log
  reports/   manual_*.txt, auto_*.txt
    errors/  *_errors.txt

<root_path>/
  .marathon/priority.json
  .marathon/worker/<worker>.json
  <Kollektion>/                        finale Proxies
    .marathon/
      restore/
      transcode/
      qc/
  DEFA/                                finale Proxies aller DEFA-Kollektionen
    .marathon/<DEFA-Kollektion>/
      restore/
      transcode/
      qc/

Jede Stufe: offen/, laufend/<worker>/, fertig/, archiv/, zurueckgezogen/, ausgang/<job_id>/
Zusätzlich: transcode/eingang/<clip_id>/ für Master, qc/eingang/ für Proxies
```

Clip-Weg: Restore → `restore/ausgang/<job_id>` → `transcode/eingang/<clip_id>` → Transcode → `transcode/ausgang/<job_id>` → `qc/eingang` → QC → finaler Ordner; danach Arbeits-Master entfernen.

Proxy-Namensschema: `<proxy_prefix>__<Identifier>__<Titel>.<Endung>`.

## Worker-Schnittstelle und Priorität

Job-Pfade relativ zu `root_path` mit `/`. Stufen: `Restore`, `Transcode`, `QC`.

1. Heartbeat mindestens einmal pro Minute atomar nach `.marathon/worker/<worker>.json`: `{worker, stage, host, job_id, beat}`. Name identisch zum Worker-Unterordner.
2. `priority.json` lesen; ersten offenen Job nach Kollektions-Reihenfolge und Dateiname atomar nach `laufend/<worker>/` verschieben. Bei fehlgeschlagener Übernahme nächsten Job versuchen.
3. Job-Felder: `schema_version, job_id, stage, clip_id, collection, identifier, title, clip_name, created_at, report_folder, output_folder`.
   - Restore: `hashes`, `files`; alle Master liefern.
   - Transcode: `inputs`, `preset` (null); genau einen Proxy im Namensschema liefern.
   - QC: `input`; Proxy nicht verschieben.
4. Ausgaben nur in `output_folder`; `.log/.txt/.json` als Protokolle erlaubt.
5. Report atomar nach `fertig/<job_id>.json`: `{job_id, status: ok|failed|rejected, result, preset}`. `rejected` nur QC; `result` Pflicht bei Fehler/Ablehnung. Vorläufiger Dateiname ohne Endung `.json`.
6. Marathon archiviert Job und Report; Worker lassen die Job-Datei unter `laufend` liegen.

`priority.txt`: Abschnitte `[Restore]`, `[Transcode]`, `[QC]`; je Zeile eine Kollektion, oben höchste Priorität. Nicht aufgeführte Kollektionen folgen in Mapping-Reihenfolge. Ungültige Liste → letzte gültige Reihenfolge. Limits zählen nur offene Jobs über alle Kollektionen; `0` pausiert eine Stufe.

## Config-Einträge

Alle verwendeten Einträge sind Pflicht. Ungültige Config pausiert Marathon; Pfadänderungen erfordern einen Neustart. `stable_minutes` ist nicht mehr erforderlich.

| Abschnitt / Eintrag | Bedeutung |
|---|---|
| paths / root_path | SMB-Wurzel für finale Ablage und Arbeitsordner |
| paths / defa_dir | Gemeinsamer finaler DEFA-Ordner |
| paths / work_dir | Arbeitsordnername, normalerweise `.marathon` |
| paths / defa_marker | Text zur Erkennung von DEFA-Kollektionen |
| paths / proxy_prefix | Präfix des Proxy-Namensschemas |
| paths / cred_file | ES-Search-Zugang im res-Ordner |
| paths / mapping_file | Kollektionsmapping im res-Ordner |
| paths / priority_file | Prioliste im res-Ordner |
| operation / auto_report_time | Tägliche Auto-Berichtszeit, lokale Uhr des Rechners |
| operation / retry_minutes | Wiederholungsabstand nach fehlgeschlagenem Auto-Bericht |
| timing / cycle_seconds | Abstand der Job-Zyklen |
| timing / max_job_attempts | Fehlversuche bis zum dauerhaften Job-Fehler |
| limits / restore, transcode, qc | Maximal offene Jobs je Stufe; 0 pausiert |
| heartbeat / worker_timeout_minutes | Heartbeat-Timeout und Sicherheitswartezeit vor Bereinigung |
| heartbeat / max_job_hours | Laufzeitgrenze für Auffälligkeiten im Report |

Auto-Berichte nur nach Aktivierung, einmal je Kalendertag ab der Uhrzeit. Nach dieser Uhrzeit kann der erste Bericht sofort kommen. Wiederholung bei Fehler nach `retry_minutes`.

## Fehler und Wiederanlauf

- Fehlende Master/Proxies: `verloren`, wieder aktiv sobald Dateien zurück sind.
- Job-Fehler: neuer Versuch; nach `max_job_attempts` dauerhaft `fehlgeschlagen`.
- QC-Ablehnung: `qc_abgelehnt`; Proxy bleibt im QC-Eingang.
- Verschwundene Job-Datei: Beobachtung, nach 30 Minuten erneut anbieten.
- Unlesbare/ungültige Jobreports erneut prüfen; veraltete Ergebnisse archivieren.
- Unbekannte Jobs, Master-Ordner, QC-Dateien und Ausgänge auf der Fehlerliste.
- Lokale Startsperre verhindert doppelten Start im selben Projektordner; JSON atomar speichern.
- Marathon-Absturz stoppt keine Worker. Ergebnisse beim nächsten `run` übernehmen.

## AQC-Sort

Die bestehende erste Stufe `python aqc_sort.py` erstellt ausschließlich eine Dateiliste von `<root_path>/<defa_dir>/AQC` inklusive Unterordnern unter `reports/aqc/aqc_files_<Zeit>.csv`. Keine Verschiebung oder JSON-Änderung. Anderer Quellordner: `--source <Pfad>`.

Die anschließende einmalige DEFA-Zuordnung wird separat vorbereitet. Marathon selbst greift nicht auf AQC zu. Bis zur Übernahme kann `[limits] restore = 0` zusätzliche Restore-Anforderungen verhindern.
