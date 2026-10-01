# Marathon 1.1.0

Marathon führt einen Index der Clips aus ES-Search (JSON), steuert Restore-, Transcode- und QC-Jobs für externe Worker und erstellt Berichte.

## Installation

Voraussetzungen: Python 3.10+, die Module `toolbox` (`tb_write_log`) und `searcher` (ES-Search) im Python-Pfad sowie Schreibzugriff auf das Netzlaufwerk.

1. `marathon.py` (und `aqc_sort.py`) in einen Projektordner legen.
2. Im Unterordner `res\` ablegen:
   - `config.ini` – mitgelieferte Vorlage, `root_path` anpassen
   - `cred.env` – Zugang für ES-Search
   - `collections.json` – Kollektionen (siehe unten)
   - `priority.txt` – optional, fehlt sie, legt Marathon eine Vorlage an
3. Starten: `python marathon.py`, dann `run` eingeben.

`log\`, `state\` und `reports\` legt Marathon selbst an.

**Umstieg von 1.0.x:** Die neue `config.ini` verwenden (`report_only` und `aqc_dir` entfallen, `[limits] lto` heißt `restore`). In `priority.txt` heißt der Abschnitt `[Restore]` statt `[LTO]`. Eine vorhandene `state\marathon.json` (Version 3) wird übernommen.

## Befehle

Marathon startet im Leerlauf und tut nichts, bis ein Befehl kommt. Nach einem Neustart ist alles wieder aus.

| Befehl | Funktion |
|---|---|
| `run` | Fehlende Ordner anlegen, JSON aus der Suche aufbauen (nur wenn sie fehlt), dann Job-Schleife alle `cycle_seconds` |
| `stop` | Job-Schleife anhalten |
| `auto-report` | Täglicher Auto-Bericht ab `auto_report_time` (ist die Uhrzeit heute schon vorbei, kommt der erste sofort) |
| `auto-report-off` | Auto-Bericht ausschalten |
| `report` | Manuellen Bericht sofort erstellen |
| `create-folders` | Komplette Ordnerstruktur aller Kollektionen anlegen |
| `update-index` | Neue Suche: neue Clips aufnehmen, Abweichungen nur melden |
| `status` | Anzeigen, was eingeschaltet ist |
| `help` / `quit` | Übersicht / beenden |

Groß-/Kleinschreibung, Leerzeichen und Unterstriche sind egal (`Update Index` = `update-index`). Befehle können auch beim Start übergeben werden, dann mit Bindestrich:

```
python marathon.py run auto-report          Start mit Job-Schleife und Auto-Bericht
python marathon.py update-index quit        Nur Index aktualisieren und beenden
python marathon.py report quit              Nur Bericht und beenden
```

## Index (JSON)

- Die Suche läuft nur bei `update-index` und beim ersten `run` ohne JSON. Berichte und Job-Zyklen suchen nie.
- `update-index` nimmt nur **neue** Clips auf. Bekannte Clips bleiben unverändert; Abweichungen (Metadaten geändert, nicht mehr gefunden, jetzt Platzhalter, jetzt in mehreren Kollektionen, jetzt ungültig) stehen auf der Fehlerliste.
- Nicht aufgenommen (Fehlerliste): Clip in mehreren Kollektionen, widersprüchliche oder unvollständige Metadaten, doppelter Identifier/Titel, Anzahl Dateinamen ≠ Anzahl Hashes, mehrere passende Proxies, Platzhalter.
- Die Meldungen des letzten `update-index` stehen in jedem Bericht, bis zum nächsten `update-index`. Zusätzlich schreibt jeder Lauf `reports\errors\index_*_errors.txt`.
- Clips verschwinden nie aus der JSON.
- **Aufnahme nach Ist-Zustand:** Proxy im Zielordner → bereit; Proxy im QC-Eingang → QC; vollständiger Master in `transcode\eingang\<clip_id>` → Transcode; sonst Restore.

### collections.json

```json
{"schema_version": 1, "collections": [
  {"name": "Spielfilme", "filters": [{"field": "007 Collection PROGRESS", "value": "Spielfilme"}]}
]}
```

Erlaubte Suchfelder: `006 Source PROGRESS`, `007 Collection PROGRESS`, `101a Genre German`. Mehrere Filter werden mit UND verknüpft.

### priority.txt

```
[Restore]
Kinderfilme
Spielfilme

[Transcode]

[QC]
DEFA Dokumentarfilme
```

Oben steht die höchste Priorität. Nicht aufgeführte Kollektionen folgen in der Reihenfolge von `collections.json`.

## Ordnerstruktur

```
<Projektordner>
├─ marathon.py, aqc_sort.py
├─ res        config.ini, cred.env, collections.json, priority.txt
├─ state      marathon.json (Index und Zustand), marathon.lock (Startsperre)
├─ log        marathon.log, aqc_sort.log
└─ reports    manual_*.txt, auto_*.txt
   ├─ errors  *_errors.txt (Fehlerliste zu jedem Bericht und jedem update-index)
   └─ aqc     aqc_files_*.csv (Dateiliste des Nebenscripts)

<root_path>
├─ .marathon
│  ├─ priority.json               Reihenfolge je Stufe für die Worker
│  └─ worker<worker>.json        Heartbeats
├─ <Kollektion>                  Zielordner (fertige Proxies)
│  ├─ unbekannt                  aussortierte fremde Dateien
│  └─ .marathon
│     ├─ restore    offen  laufend<worker>  fertig  archiv  zurueckgezogen  ausgang<job_id>
│     ├─ transcode  wie restore + eingang<clip_id>   (Master)
│     └─ qc         wie restore + eingang             (Proxies)
└─ DEFA                          Zielordner aller DEFA-Kollektionen
   ├─ unbekannt
   └─ .marathon<Kollektion>estore|transcode|qc (wie oben)
```

Proxy-Namensschema: `<proxy_prefix>__<Identifier>__<Titel>.<Endung>`

## Ablauf eines Clips

```
Restore → restoreausgang<job> → transcodeeingang<clip_id> → Transcode → transcodeausgang<job>
        → qceingang → QC → Zielordner, Master gelöscht → bereit
```

Job-Dateien: `offen` → `laufend\<worker>` → `archiv` (bzw. `zurueckgezogen`).

Status je Clip in `marathon.json`: `bereit`, `wartet`, `laufend`, `verloren`, `fehlgeschlagen`, `qc_abgelehnt`.

## Worker-Schnittstelle

Pfade in Jobs sind relativ zu `root_path`, Trenner `/`.

1. **Heartbeat** mindestens einmal pro Minute nach `.marathon/worker/<worker>.json`: `{worker, stage, host, job_id, beat}`, `stage` = `Restore` | `Transcode` | `QC`. Der Name muss dem Ordner in `laufend\` entsprechen.
2. **Job holen:** `priority.json` lesen, `offen\` der eigenen Stufe in dieser Reihenfolge durchgehen, ersten Job (nach Name) nach `laufend/<worker>/` umbenennen. Schlägt das fehl, den nächsten nehmen.
3. **Job-Datei:** `schema_version`, `job_id`, `stage`, `clip_id`, `collection`, `identifier`, `title`, `clip_name`, `created_at`, `report_folder`, `output_folder`
   - Restore: `hashes`, `files` – alle Dateien liefern
   - Transcode: `inputs`, `preset` (null) – genau ein Proxy im Namensschema
   - QC: `input` – Proxy nicht verschieben
4. **Ergebnisse** nur in `output_folder` schreiben. Protokolle (`.log`, `.txt`, `.json`) sind erlaubt.
5. **Report** nach `fertig/<job_id>.json`, zuerst unter einem Namen ohne Endung `.json` schreiben, dann umbenennen:
   `{job_id, status: ok|failed|rejected (nur QC), result (Pflicht, wenn nicht ok), preset (Transcode)}`
6. Die Job-Datei bleibt in `laufend\`. Verschieben, archivieren und aufräumen macht Marathon.

## Fehlerliste

Alles, was sich über den normalen Ablauf nicht zuordnen lässt, steht in `reports\errors\*_errors.txt`:

- **Nicht aufgenommen** und **Abweichungen Suche ↔ JSON** (letzter `update-index`)
- **Nicht aktiv:** `verloren` (Proxy oder Master fehlt; wieder aktiv, sobald die Datei zurück ist), `fehlgeschlagen` (nach `max_job_attempts`), `qc_abgelehnt` (Proxy bleibt im QC-Eingang)
- **Hinweise:** fremde Dateien im Zielordner (bei `run` nach `unbekannt\`), Dateien im QC-Eingang ohne Clip, Master-Ordner ohne Clip, Ausgänge ohne Job, unbekannte Job-Dateien, ungültige Reports, Fehlversuche, ungültige Prioliste

## Besondere Verhaltensmuster

- **Berichte** lesen nur: keine Suche, keine Jobs, keine Verschiebungen auf dem Netzlaufwerk. Sie zeigen Tabelle je Kollektion mit Veränderung zum letzten Bericht gleicher Art, Index-Stand, Zusammenfassung, auffällige laufende Jobs und Worker.
- **Config fehlt oder ist fehlerhaft:** Marathon meldet es und pausiert, bis die Datei korrigiert ist. Änderungen in `[paths]` pausieren bis zum Neustart.
- **Grenzen** gelten über alle Kollektionen und zählen nur offene Jobs. Überzählige offene Jobs werden zurückgezogen (Prio, dann Queue-Reihenfolge). `0` pausiert eine Stufe.
- **Nach QC ok:** Proxy in den Zielordner, Master-Ordner gelöscht, Protokolle als `archiv\<job_id>.ausgang`. Bei Fehlschlag werden Teilergebnisse gelöscht.
- **Fremde Dateien in Zielordnern** kommen bei `run` nach `stable_minutes` nach `unbekannt\`. Unberührt bleiben Unterordner (auch `DEFA\AQC`), `Thumbs.db`, `desktop.ini`, `.DS_Store`, Punkt- und `~$`-Dateien sowie `.tmp`/`.part`/`.partial`.
- **Zustand neu aufbauen:** Marathon beenden, `state\marathon.json` löschen, `run`. Unbekannte offene Jobs werden zurückgezogen; Ergebnisse unbekannter laufender Jobs werden archiviert, nicht übernommen.

## Robust bei

- Suchfehler oder unvollständiger Suche – JSON bleibt unverändert.
- Netzlaufwerk nicht erreichbar – Zustand bleibt unverändert, nächster Zyklus versucht es erneut.
- Ausfall oder Absturz von Marathon – Worker arbeiten weiter, Ergebnisse werden beim nächsten `run` übernommen; Zustand wird atomar geschrieben.
- Doppeltem Start – Startsperre auf `state\marathon.lock`, wird auch nach Absturz freigegeben.
- Zwei Workern auf demselben Job – nur einer bekommt ihn. Job-Übernahme während des Zurückziehens – der Job läuft regulär weiter.
- Halb geschriebenen, unlesbaren oder ungültigen Reports (erneuter Versuch) und veralteten Reports (archiviert).
- Verschwundenem Master vor Transcode, Proxy im QC-Eingang oder im Zielordner – Clip inaktiv, wieder aktiv, sobald die Datei zurück ist.
- Unvollständigem Restore – Fehlversuch, neuer Job. Verschwundener Job-Datei – nach 30 min neuer Job. Zurückgegebenem Job – wird wieder angeboten.
- Worker-Ausfall – Meldung im Bericht (kein Heartbeat, kein Lebenszeichen > `worker_timeout_minutes`, anderer Job, Laufzeit > `max_job_hours`).
- Ungültiger Prioliste – letzte gültige Reihenfolge gilt.
- Namenskonflikt bei der Auslieferung – vorhandene Datei kommt nach `unbekannt\`.
- Fehlgeschlagenem Auto-Bericht – neuer Versuch nach `retry_minutes`.

## Nebenscript aqc_sort.py (einmalige Übernahme aus DEFAAQC)

Marathon selbst schaut nicht in `DEFA\AQC`. Das Nebenscript bringt die vorhandenen Clips einmalig auf die richtigen Schienen.

Stufe 1 (aktuell): `python aqc_sort.py` listet alle Dateien in `<root_path>\<defa_dir>\AQC` inklusive Unterordnern nach `reports\aqc\aqc_files_<Zeit>.csv` (Semikolon, Excel-tauglich): Unterordner, Datei, Endung, Größe, Änderungszeit, Namensschema ja/nein, Identifier, Titel. Liest nur, ändert nichts. Anderer Ordner: `--source <Pfad>`.

Nächste Stufe: Zuordnung zur JSON und Verschieben eindeutiger Treffer nach `DEFA\.marathon\<Kollektion>\qc\eingang` inklusive Anpassung der JSON.

**Tipp bis dahin:** `[limits] restore = 0` setzen, damit `run` keine Bänder für Clips anfordert, deren Proxy noch in AQC liegt.
