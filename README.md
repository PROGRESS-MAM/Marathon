# Marathon 1.0.1

Marathon gleicht Clips aus ES-Search mit dem Netzlaufwerk ab, steuert LTO-, Transcode- und QC-Jobs für externe Worker und erstellt Berichte.

## Installation

Voraussetzungen: Python 3.10+, die Module `toolbox` und `searcher` im Python-Pfad sowie Schreibzugriff auf das Netzlaufwerk.

1. `marathon.py` in einen Projektordner legen.
2. Im Unterordner `res\` ablegen:
   - `config.ini` – mitgelieferte Vorlage, `root_path` anpassen
   - `cred.env` – Zugang für ES-Search
   - `collections.json` – Kollektionen (siehe unten)
   - `priority.txt` – optional, fehlt sie, legt Marathon eine Vorlage an
3. Erster Start mit `report_only = true`, Bericht prüfen, dann `report_only = false`.

`log\`, `state\` und `reports\` legt Marathon selbst an.

### collections.json

```json
{"schema_version": 1, "collections": [
  {"name": "Spielfilme", "filters": [{"field": "007 Collection PROGRESS", "value": "Spielfilme"}]}
]}
```

Erlaubte Suchfelder: `006 Source PROGRESS`, `007 Collection PROGRESS`, `101a Genre German`. Mehrere Filter werden mit UND verknüpft.

### priority.txt

```
[LTO]
Kinderfilme
Spielfilme

[Transcode]

[QC]
DEFA Dokumentarfilme
```

Oben steht die höchste Priorität. Nicht aufgeführte Kollektionen folgen in der Reihenfolge von `collections.json`.

## Befehle

| Aufruf | Funktion |
|---|---|
| `python marathon.py` | Dauerbetrieb: Job-Zyklus alle `cycle_seconds`, täglicher Auto-Bericht ab `auto_report_time` |
| `python marathon.py --manual` | Manuellen Bericht erstellen und beenden |
| `python marathon.py --auto-once` | Auto-Bericht erstellen und beenden |
| `python marathon.py --cycle-once` | Einen Job-Zyklus ausführen und beenden |

Konsole im Dauerbetrieb:

| Eingabe | Funktion |
|---|---|
| `report` | Manuellen Bericht erstellen |
| `quit` / `exit` | Marathon beenden |

Die Suche läuft nur in Berichten. Job-Zyklen arbeiten mit dem Stand aus dem letzten Bericht.

## Ordnerstrukturen

```
<Projektordner>├─ marathon.py
├─ res        config.ini, cred.env, collections.json, priority.txt
├─ state      marathon.json (Zustand), marathon.lock (Startsperre)
├─ log        marathon.log
└─ reports    manual_*.txt, auto_*.txt
   └─ errors  *_errors.txt (Details zu jedem Bericht)

<root_path>├─ .marathon│  ├─ priority.json               Reihenfolge je Stufe für die Worker
│  └─ worker<worker>.json        Heartbeats
├─ <Kollektion>                  Zielordner (fertige Proxies)
│  ├─ unbekannt                  aussortierte fremde Dateien
│  └─ .marathon│     ├─ restore    offen laufend<worker> fertig archiv zurueckgezogen ausgang<job_id>│     ├─ transcode  wie restore + eingang<clip_id>   (Master)
│     └─ qc         wie restore + eingang             (Proxies)
└─ DEFA                          Zielordner aller DEFA-Kollektionen
   ├─ AQC                        Proxies der Kollegen → direkt an QC
   ├─ unbekannt   └─ .marathon<Kollektion>
estore|transcode|qc (wie oben)
```

Proxy-Namensschema: `<proxy_prefix>__<Identifier>__<Titel>.<Endung>`

## Ablauf eines Clips

```
LTO → restoreausgang → transcodeeingang<clip_id> → Transcode → transcodeausgang
    → qceingang (bzw. DEFAAQC) → QC → Zielordner, Master gelöscht → bereit
```

Status je Clip in `marathon.json`: `bereit`, `wartet`, `laufend`, `verloren`, `fehlgeschlagen`, `qc_abgelehnt`, `platzhalter`, `duplikat`, `ungueltig`.

## Worker-Schnittstelle

Pfade in Jobs sind relativ zu `root_path`, Trenner `/`.

1. **Heartbeat** mindestens einmal pro Minute nach `.marathon/worker/<worker>.json`: `{worker, stage, host, job_id, beat}`. Der Name muss dem Ordner in `laufend\` entsprechen.
2. **Job holen:** `priority.json` lesen, `offen\` der eigenen Stufe in dieser Reihenfolge durchgehen, ersten Job (nach Name) nach `laufend/<worker>/` umbenennen. Schlägt das fehl, den nächsten nehmen.
3. **Job-Datei:** `schema_version`, `job_id`, `stage`, `clip_id`, `collection`, `identifier`, `title`, `clip_name`, `created_at`, `report_folder`, `output_folder`
   - LTO: `hashes`, `files` – alle Dateien liefern
   - Transcode: `inputs`, `preset` (null) – genau ein Proxy im Namensschema
   - QC: `input` – Proxy nicht verschieben
4. **Ergebnisse** nur in `output_folder` schreiben. Protokolle (`.log`, `.txt`, `.json`) sind erlaubt.
5. **Report** nach `fertig/<job_id>.json`, zuerst unter einem Namen ohne Endung `.json` schreiben, dann umbenennen:
   `{job_id, status: ok|failed|rejected (nur QC), result (Pflicht, wenn nicht ok), preset (Transcode)}`
6. Die Job-Datei bleibt in `laufend\`. Verschieben, archivieren und aufräumen macht Marathon.

## Besondere Verhaltensmuster

- **report_only:** keine Jobs, keine Schreibzugriffe auf das Netzlaufwerk; unbekannte Dateien werden nur gemeldet.
- **Config fehlt oder ist fehlerhaft:** Marathon meldet es und pausiert, bis die Datei korrigiert ist. Änderungen in `[paths]` pausieren bis zum Neustart. Einmal-Aufrufe brechen ab.
- **Ohne Zustand** (`state\marathon.json` fehlt) warten Job-Zyklen auf den ersten Bericht.
- **Aufnahme neuer Clips nach Ist-Zustand:** Proxy im Zielordner → bereit; Proxy in QC-Eingang/AQC → QC; vollständiger Master in `transcode\eingang\<clip_id>` → Transcode; sonst LTO.
- **Nicht aufgenommen (Fehlerliste):** Clip in mehreren Kollektionen, widersprüchliche Metadaten, doppelter Identifier/Titel, Anzahl Dateinamen ≠ Anzahl Hashes, mehrere passende Proxies. Platzhalter werden still übergangen.
- **Clips verschwinden nie aus der JSON.** Bei Problemen werden sie inaktiv (nicht in „Gesamt“) und bei Wegfall des Grundes automatisch wieder aktiv, mit alter Queue-Position.
- **Dauerhaft inaktiv:** `fehlgeschlagen` (nach `max_job_attempts` Fehlversuchen) und `qc_abgelehnt` (Proxy bleibt im QC-Eingang bzw. AQC).
- **AQC:** Ein passender AQC-Proxy schickt einen DEFA-Clip direkt an QC, auch nach fehlgeschlagenem LTO/Transcode. Offene Jobs früherer Stufen werden zurückgezogen.
- **Grenzen** gelten über alle Kollektionen und zählen nur offene Jobs. Überzählige offene Jobs werden zurückgezogen (Prio, dann Queue-Reihenfolge).
- **Metadaten ändern sich:** Ein offener Job wird neu erstellt, ein laufender läuft weiter.
- **Nach QC ok:** Proxy in den Zielordner, Master-Ordner gelöscht, Protokolle als `archiv\<job_id>.ausgang`. Bei Fehlschlag werden Teilergebnisse gelöscht.
- **Fremde Dateien in Zielordnern** kommen nach `stable_minutes` nach `unbekannt\`. Unberührt bleiben Unterordner, `Thumbs.db`, `desktop.ini`, `.DS_Store`, Punkt- und `~$`-Dateien sowie `.tmp`/`.part`/`.partial`.
- **Zustand neu aufbauen:** `report_only = true` setzen, `state\marathon.json` löschen, `report` ausführen, Fehlerliste prüfen, `report_only = false`. Unbekannte offene Jobs werden zurückgezogen; Ergebnisse unbekannter laufender Jobs werden archiviert, nicht übernommen.
- **Bericht:** Tabelle je Kollektion mit Veränderung zum letzten Bericht gleicher Art, Zusammenfassung der Auffälligkeiten, auffällige laufende Jobs, Worker-Liste; Details unter `reports\errors\`.

## Robust bei

- Suchfehler oder unvollständiger Suche – Zustand bleibt unverändert.
- Suche mit 0 Treffern – Clips werden inaktiv und im Delta sichtbar, danach automatisch wieder aktiv.
- Netzlaufwerk nicht erreichbar – Zustand bleibt unverändert, nächster Zyklus versucht es erneut.
- Ausfall oder Absturz von Marathon – Worker arbeiten weiter, Ergebnisse werden beim Neustart übernommen; Zustand wird atomar geschrieben.
- Doppeltem Start – Startsperre auf `state\marathon.lock`, wird auch nach Absturz freigegeben.
- Zwei Workern auf demselben Job – nur einer bekommt ihn.
- Job-Übernahme während des Zurückziehens – der Job läuft regulär weiter.
- Halb geschriebenen Reports und Heartbeats; unlesbaren oder ungültigen Reports (werden erneut versucht) und veralteten Reports (werden archiviert).
- Dateien, die noch kopiert werden (AQC, Zielordner) – Verarbeitung erst nach `stable_minutes` ohne Größenänderung.
- Verschwundenem Master vor Transcode, Proxy im QC-Eingang oder im Zielordner – Clip wird inaktiv und ist wieder aktiv, sobald die Datei zurück ist.
- Master, der nach Übernahme durch den Transcode-Worker verschwindet.
- Unvollständigem Restore – Fehlversuch, neuer Job.
- Verschwundener Job-Datei – nach 30 min neuer Job.
- Worker-Ausfall – Meldung im Bericht (kein Heartbeat, kein Lebenszeichen > `worker_timeout_minutes`, anderer Job, Laufzeit > `max_job_hours`).
- Zurückgegebenem Job (Worker legt ihn wieder nach `offen\`).
- Kollektionswechsel eines Clips, auch bei laufendem Job.
- Ungültiger Prioliste – letzte gültige Reihenfolge gilt.
- Fehlerhafter Config – Pause statt Betrieb mit falschen Werten.
- Namenskonflikt bei der Auslieferung – vorhandene Datei kommt nach `unbekannt\`.
- Fehlgeschlagenem Auto-Bericht – neuer Versuch nach `retry_minutes`.
- Gelöschtem Zustand – Neuaufbau aus den Ordnern beim nächsten Bericht.
