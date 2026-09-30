# Marathon 1.1.0

Marathon ist ein Pipeliner. Es holt Clips über ES-Search, schickt jeden Clip durch die Steps seiner Pipeline und erstellt Berichte. Die eigentliche Arbeit machen externe Worker. Marathon verteilt die Jobs, bewegt die Dateien und führt Buch.

## Installation

Voraussetzungen: Python 3.10+, die Module `toolbox` (`tb_write_log`) und `searcher` (ES-Search) im Python-Pfad sowie Schreibzugriff auf das Netzlaufwerk.

1. `marathon-5.py` als `marathon.py` in einen Projektordner legen.
2. Im Unterordner `res\` ablegen:
   - `config.ini` – Vorlage `config-2.ini`; Werte anpassen
   - `cred.env` – Zugang für ES-Search
   - `pipelines.txt` – Steps und Pipelines (Vorlage liegt bei)
   - `auftragslisten\*.txt` – eine Datei je Auftragsliste (Beispiel `DEFA.txt`)
3. Beim ersten Start `report_only = true` setzen, den Bericht prüfen und danach `report_only = false` setzen.

`log\`, `state\` und `reports\` legt Marathon selbst an.

## Umstieg von 1.0.x

1. Laufende Jobs abarbeiten lassen. 1.1.0 nutzt eine neue Ordner- und Job-Struktur und findet Zwischenstände aus 1.0.x nicht (z. B. Master in `transcode\eingang`).
2. `config.ini` durch die neue Vorlage ersetzen. Alte Schlüssel wie `defa_dir`, `mapping_file` oder `priority_file` meldet Marathon als unbekannt und pausiert.
3. Den Inhalt von `collections.json` und `priority.txt` in Auftragslisten übertragen. Beide Dateien liest Marathon nicht mehr.
4. Worker auf das neue `priority.json` (`schema_version` 2) und die neuen Job-Dateien (`schema_version` 3) umstellen, siehe *Worker-Schnittstelle*.
5. `state\marathon.json` löschen (Marathon lehnt den alten Zustand mit einem Hinweis ab), `report_only = true` setzen, `report` ausführen und die Fehlerliste prüfen. Bereits ausgelieferte Dateien übernimmt der Bericht (*Aufnahme von hinten*); diese Clips sind sofort bereit.
6. `report_only = false` setzen.
7. Alte Arbeitsordner von 1.0.x von Hand löschen. Liegen sie im neuen Arbeitsordner einer Kollektion, meldet der Bericht sie bis dahin als „Ordner ohne passenden Clip“.

## Begriffe

- **Clip:** ein Treffer der Suche, erkennbar an der Clip-ID. Er hat Metadaten (Identifier, Titel, Clipname, Hashes, Master-Dateinamen) und Dateisätze.
- **Dateisätze:** Jeder Clip hat einen `master` (eine Datei oder mehrere, z. B. bei OpAtom) und beliebig viele **Renditions** (je eine Datei). Jede Rendition trägt den Namen des Transcode-Steps, der sie erzeugt.
- **Step:** ein benannter Arbeitsschritt mit einem Modul. Du beschreibst ihn einmal und kannst ihn in mehreren Pipelines verwenden.
- **Pipeline:** eine benannte Folge von Steps. Module dürfen mehrfach vorkommen; die Reihenfolge ist frei.
- **Auftragsliste:** eine oder mehrere Kollektionen, jeweils mit Suche, Prio und Zielordner. **Jede Auftragsliste gehört zu genau einer Pipeline, und jede Pipeline hat höchstens eine Auftragsliste.**
- Jeder Clip steht an genau einem Step und hat einen Status und eine Historie.

## Schreibweise beider Dateien

- Eine Angabe pro Zeile: `Schlüssel: Wert`. Schlüssel sind unabhängig von Groß- und Kleinschreibung; statt `Abkürzung` geht auch `Abkuerzung`.
- Anführungszeichen braucht es nicht. Leerzeichen in Werten sind erlaubt.
- **Kommentare** stehen in eigenen Zeilen, die mit `#` beginnen, auch eingerückt. Ein `#` mitten in einer Zeile gehört zum Wert.
- Leerzeilen werden ignoriert.
- Marathon liest beide Dateien alle paar Sekunden neu und meldet Fehler mit Datei und Zeilennummer.

## pipelines.txt

```
# Steps
[restore]
Modul: restore
Ausgang: master

[proxy_10]
Modul: transcode
Eingang: master
Ausgang: proxy_10
Dateiname: (c)PROGRESS__10Mbit__{identifier}__{title}
Parameter: preset = 10Mbit

[proxy_50]
Modul: transcode
Eingang: master
Ausgang: proxy_50
Dateiname: (c)PROGRESS__50Mbit__{identifier}__{title}
Parameter: preset = 50Mbit

[qc]
Modul: qc
Eingang: proxy_10, proxy_50, /DEFA/AQC
Ausgang: {target}
Abkürzung: ja

[cleanup]
Modul: delete
Dateien: master

# Pipelines
Pipeline DEFA Proxy: restore --> proxy_10 --> proxy_50 --> qc --> cleanup
```

- **Step:** `[name]` beginnt einen Step. Der Name besteht aus Buchstaben, Ziffern, `_` und `-`. Nicht erlaubt sind `master` und die Spaltennamen `Kollektion`, `Prio`, `Gesamt` und `Bereit`.
- **Pipeline:** `Pipeline <Name>: Step --> Step --> …`. Als Pfeil gehen `-->`, `->`, `—>`, `–>` und `→`. Ein Step darf in einer Pipeline nur einmal vorkommen.

### Module

| Modul | Arbeit | Pflicht | Ergebnis |
|---|---|---|---|
| `restore` | Worker | `Ausgang` | `master` aus den Hashes der Suche; im Ausgang liegen alle Master-Dateinamen |
| `transcode` | Worker | `Eingang`, `Ausgang`, `Dateiname` | genau eine Datei `<Dateiname>.<Endung>` im Ausgang = Rendition mit dem Step-Namen |
| `qc` | Worker | `Eingang` | `ok`: die geprüften Dateien wandern nach `Ausgang` (falls angegeben); `rejected`: Dateien bleiben liegen, der Clip wird inaktiv |
| `delete` | Marathon | `Dateien` | löscht die genannten Dateisätze (`master` oder Rendition-Namen) |

Optional für jeden Step:
- `Parameter: schlüssel = wert`: geht unverändert in den Job; die Zeile darf mehrfach vorkommen.
- `Abkürzung: ja`: nur bei Steps mit externem Eingang (siehe *Abkürzung*).

`Eingang` und `Dateien` nehmen mehrere Angaben, getrennt mit Komma.

Platzhalter in `Dateiname`: `{clip_id}`, `{identifier}`, `{title}`, `{clip_name}`, `{collection}`. Zeichen, die in Windows-Dateinamen nicht erlaubt sind, werden zu `_`.

### Ordnerangaben

| Schreibweise | Ort | Besitz |
|---|---|---|
| `master` (einfacher Name) | intern: `<Zielordner>\.marathon\<Kollektion>\master\<Clip_ID>\` | Marathon |
| `/DEFA/AQC` | extern, relativ zu `root_path`; Dateien liegen direkt im Ordner | fremd |
| `{target}` oder `{target}/Sichtung` | extern, Zielordner der Kollektion | fremd |

- Interne Namen bestehen aus Buchstaben, Ziffern, `_` und `-`; `jobs` ist reserviert.
- Externe Angaben dürfen keinen Ordner enthalten, der mit einem Punkt beginnt oder wie `work_dir` heißt.
- Ein externer Ordner ist entweder Eingang oder Ausgang, über alle Pipelines hinweg.

## Auftragslisten

`res\auftragslisten\<Name>.txt` – der Dateiname ist der Name der Auftragsliste.

```
Pipeline: DEFA Proxy

Name: DEFA Dokumentation
Prio: 1
Ziel: DEFA
Suche:
    006 Source PROGRESS | is | DEFA
    and
    007 Collection PROGRESS | is | East German Film Archives (DEFA)
    and
    101a Genre German | is | Dokumentarfilm

Name: DEFA Spielfilm
Prio: 2
Ziel: DEFA
Suche:
    006 Source PROGRESS | is | DEFA
    and
    101a Genre German | contains | Spielfilm; Kinderfilm
```

| Angabe | Bedeutung |
|---|---|
| `Pipeline` | genau einmal, vor der ersten Kollektion |
| `Name` | beginnt eine Kollektion; eindeutig über alle Auftragslisten |
| `Prio` | ganze Zahl ab 1; 1 ist die höchste Priorität. Sie gilt für alle Module und über alle Auftragslisten. Bei gleicher Prio entscheidet die Reihenfolge der Dateien (alphabetisch) und darin der Kollektionen. Ohne Prio steht die Kollektion hinten. |
| `Ziel` | Zielordner relativ zu `root_path` (`{target}`); Standard ist der Kollektionsname |
| `Suche` | eingerückte Zeilen, abwechselnd Bedingung `Feld \| Operator \| Wert` und Verknüpfung `and` oder `or` |

- **Operatoren:** `is`, `is not`, `contains`, `contains not`, `starts_with`, `ends_with`, `>`, `<`, `>=`, `<=`, `not >`, `not <`, `not >=`, `not <=`.
- **Mehrere Werte:** `contains` nimmt mehrere Werte, getrennt mit `;`; dann reicht einer der Werte.
- **Zahlen:** Nur bei `>`, `<`, `>=`, `<=` und ihren `not`-Formen sucht Marathon ganze Zahlen und Dezimalzahlen mit Punkt als Zahl. Sonst ist der Wert immer Text: `Jahr | is | 1990` sucht den Text `1990`.
- **Reihenfolge der Verknüpfung:** strikt von links nach rechts, ohne Klammern. `A or B and C` bedeutet `(A or B) and C`.
- **Feldprüfung:** Ob ein Feld existiert und den Operator erlaubt, prüft ES-Search beim Bericht.
- **Reservierte Namen:** Kollektionen und Auftragslisten dürfen nicht `Summe`, `Kollektion` oder `Auftragsliste` heißen; diese Namen braucht der Bericht.

## Prüfung der Dateien

Marathon prüft nur den Aufbau. Ob die Reihenfolge der Steps sinnvoll ist, entscheidet der Ersteller.

Bei einem **Fehler pausieren Job-Zyklen und Berichte**, bis er behoben ist. Der Zustand bleibt unverändert, und die Konsole nennt Datei, Zeile und Grund. Fehler sind:
- unbekannter Schlüssel, unbekanntes Modul, fehlende Pflichtangabe
- doppelter Step oder doppelte Pipeline
- unbekannter Step in einer Pipeline oder ein Step zweimal in derselben Pipeline
- `Dateien` nennt etwas anderes als `master` oder einen Transcode-Step
- `Abkürzung` ohne externen Eingang
- externer Ordner zugleich als Eingang und als Ausgang
- ungültiger Platzhalter, ungültiger Step-Name oder ungültige Ordnerangabe
- Auftragsliste ohne `Pipeline`, mit mehreren `Pipeline`-Zeilen oder mit einer unbekannten Pipeline
- **zwei Auftragslisten mit derselben Pipeline**
- doppelter Kollektionsname, fehlende oder fehlerhafte Suche, ungültige `Prio`, ungültiges `Ziel`, reservierter Name
- zwei Kollektionen, die denselben Arbeitsordner ergeben
- kein Auftragslisten-Ordner oder keine Auftragsliste darin

Hinweise im Bericht, ohne Pause: Step, den keine Pipeline nutzt; Pipeline ohne Auftragsliste.

## Ablauf eines Clips

1. Die Suche läuft nur in Berichten; neue Clips kommen also mit dem nächsten Bericht hinzu. Ein neuer Clip startet am ersten Step. Liegen schon Ergebnisse vor, sucht Marathon von hinten den letzten Step, dessen Ergebnis im Ausgang liegt (*Aufnahme von hinten*). Dieser Step und alle davor gelten als erledigt; `delete`-Steps davor laufen trotzdem.
2. Am Step sucht Marathon die Dateien des Clips in den Eingängen:
   - **intern:** im Unterordner `<Clip_ID>`
   - **extern:** Die Datei muss nach Namen passen (Master-Dateiname oder `Dateiname` einer Rendition, Endung beliebig), `stable_minutes` unverändert sein und eindeutig einem Clip zuzuordnen sein. Ein Master zählt nur, wenn er vollständig in einem Ordner liegt.
3. Ohne Eingang wartet der Clip; der Bericht zeigt „Wartet auf Eingang“. Mit Eingang erstellt Marathon einen Job mit allen gefundenen Dateipfaden. `delete` erledigt Marathon sofort selbst.
4. Ergebnisse verschiebt Marathon vom Job-Ausgang in den `Ausgang` des Steps. Danach geht der Clip zum ersten noch nicht erledigten Step der Pipeline.
5. Nach dem letzten Step ist der Clip **bereit**.

**Abkürzung:** Findet Marathon in einem externen Eingang dieses Steps eine passende Datei, springt der Clip von einem früheren Step direkt hierher.
- Offene Jobs werden zurückgezogen; fehlgeschlagene oder abgelehnte frühere Steps werden aufgehoben.
- Übersprungene Steps werden nicht nachgeholt.
- Läuft gerade ein Job, wartet Marathon, bis er fertig ist.

**Pipeline ändern:** Marathon merkt sich je Clip die erledigten Steps nach Namen.
- Neue Steps gelten für alle Clips, die noch nicht bereit sind. Entfernte Steps werden übersprungen.
- Den laufenden Job eines entfernten Steps lässt Marathon zu Ende laufen; sein Ergebnis wird nicht übernommen, sondern archiviert.
- Einen Step umbenennen heißt: neuer Step.

**Kollektion oder Pipeline wechselt:** Für den Clip gilt ab sofort die neue Pipeline, nach denselben Regeln. Schon erledigte Steps mit gleichem Namen laufen nicht noch einmal.

Status je Clip: `bereit`, `wartet`, `laufend`, `verloren`, `fehlgeschlagen`, `qc_abgelehnt`, `platzhalter`, `duplikat`, `ungueltig`.

## Besitz

- Marathon **besitzt** Dateien, die es selbst erzeugt hat (Restore, Transcode), und Dateien, die ein Step aus einem externen Eingang übernommen hat. Übernommene Dateien bleiben liegen, bis ein Step sie verschiebt oder löscht.
- **Ausgeliefert** ist eine Datei, sobald sie in einem externen Ausgang liegt: von Marathon dorthin verschoben oder bei der Aufnahme dort gefunden. Ab dann beobachtet Marathon sie nur noch und verschiebt oder löscht sie nicht mehr; ein `delete`-Step überspringt sie mit Hinweis.
- **Gelöscht** werden nur Dateien, die Marathon besitzt: durch `delete` und bei Resten fehlgeschlagener Jobs.
- Dateien in Eingängen, die kein Step übernommen hat, bleiben unangetastet. Der Fehlerbericht nennt sie: „ohne passenden Clip“ oder „nicht übernommen“ (Clip schon weiter, inaktiv, mehrdeutig oder unvollständig).
- Fremde Dateien in externen Ausgängen verschiebt Marathon nach `stable_minutes` nach `unbekannt\`. Das gilt auch für Dateien von Clips, die noch nicht aufgenommen sind. Vorhandene Bestände deshalb mit einem Bericht aufnehmen, bevor Job-Zyklen laufen (siehe *Umstieg*).

## Ordnerstruktur

```
<Projektordner>
├─ marathon.py
├─ res        config.ini, cred.env, pipelines.txt, auftragslisten\*.txt
├─ state      marathon.json (Zustand), marathon.lock (Startsperre)
├─ log        marathon.log
└─ reports    manual_*.txt, auto_*.txt
   └─ errors  *_errors.txt

<root_path>
├─ .marathon
│  ├─ priority.json                 Reihenfolge je Modul für die Worker
│  └─ worker\<worker>.json          Heartbeats
├─ <Zielordner>                     {target}, z. B. DEFA
│  ├─ unbekannt
│  └─ .marathon\<Kollektion>
│     ├─ <Ordner>\<Clip_ID>\        interne Ordner, z. B. master, proxy_10
│     └─ jobs\<Step>\               offen, laufend\<worker>, fertig, archiv, zurueckgezogen, ausgang\<job_id>
└─ DEFA\AQC                         Beispiel für einen externen Eingang
```

## config.ini

| Abschnitt | Inhalt |
|---|---|
| `[paths]` | `root_path`, `work_dir`, `cred_file`, `pipelines_file`, `orders_dir` (Ordner der Auftragslisten in `res\`) |
| `[fields]` | Suchfelder für `clip_id`, `identifier`, `title`, `clip_name`, `hash`, `userpath`, `status_flags` sowie `placeholder_flag` |
| `[operation]` | `report_only`, `auto_report_time`, `retry_minutes` |
| `[timing]` | `cycle_seconds`, `max_job_attempts`, `stable_minutes` |
| `[limits]` | maximal offene Jobs je Modul (`restore`, `transcode`, `qc`), über alle Pipelines und Steps; 0 = Modul pausiert |
| `[heartbeat]` | `worker_timeout_minutes`, `max_job_hours` |

Alle Einträge sind Pflicht. Marathon liest die Datei alle paar Sekunden neu. Änderungen in `[paths]` und `[fields]` wirken erst nach einem Neustart; bis dahin pausiert Marathon.

## Befehle

| Aufruf | Funktion |
|---|---|
| `python marathon.py` | Dauerbetrieb: Job-Zyklus alle `cycle_seconds`, täglicher Auto-Bericht ab `auto_report_time` |
| `python marathon.py --manual` | manuellen Bericht erstellen und beenden |
| `python marathon.py --auto-once` | Auto-Bericht erstellen und beenden |
| `python marathon.py --cycle-once` | einen Job-Zyklus ausführen und beenden |

Konsole im Dauerbetrieb: `report` erstellt einen manuellen Bericht, `quit` oder `exit` beendet Marathon. Während einer Pause lehnt Marathon `report` mit dem Grund ab.
Die Suche läuft nur in Berichten. Job-Zyklen arbeiten mit dem Stand des letzten Berichts.

## Worker-Schnittstelle

Pfade sind relativ zu `root_path`, Trennzeichen `/`.

1. **Heartbeat** mindestens einmal pro Minute nach `.marathon/worker/<worker>.json`: `{worker, module, host, job_id, beat}`.
2. **Job holen:** `.marathon/priority.json` lesen: `{"schema_version": 2, "modules": {"<modul>": [{collection, order_list, pipeline, step, offen, laufend, fertig}, …]}}`. Die Liste je Modul ist nach Prio sortiert. In dieser Reihenfolge die `offen`-Ordner durchgehen und den ersten Job (nach Name) nach `laufend/<worker>/` umbenennen. Schlägt das fehl, den nächsten nehmen.
3. **Job-Datei** (`schema_version` 3): `job_id`, `module`, `step`, `pipeline`, `order_list`, `collection`, `clip_id`, `identifier`, `title`, `clip_name`, `params`, `inputs` (Dateipfade), `output_folder`, `report_folder`, `created_at`
   - `restore`: zusätzlich `hashes` und `files`; alle Dateien liefern
   - `transcode`: zusätzlich `file_name`; genau eine Datei `<file_name>.<Endung>` liefern
   - `qc`: Eingangsdateien nicht verschieben
4. **Ergebnisse** nur in `output_folder` schreiben. Protokolle (`.log`, `.txt`, `.json`) sind erlaubt und werden archiviert.
5. **Report** nach `fertig/<job_id>.json`: zuerst unter einem Namen ohne Endung `.json` schreiben, dann umbenennen.
   Inhalt: `{job_id, status: ok|failed|rejected (nur qc), result (Pflicht, wenn nicht ok), info (optionales Objekt)}`. `info` erscheint in der Historie des Clips.
6. Die Job-Datei bleibt in `laufend\`. Verschieben, Archivieren und Aufräumen übernimmt Marathon.

## Bericht

- Eine Tabelle je Auftragsliste mit ihrer Pipeline im Titel. Spalten: Kollektion, Prio, Gesamt, Bereit, %, eine Spalte je Step (aktive Clips an diesem Step), dazu eine Summenzeile.
- Danach die Tabelle „Alle Auftragslisten“ mit Gesamt, Bereit und % je Auftragsliste und der Gesamtsumme.
- In Klammern stehen die Veränderungen zum letzten Bericht gleicher Art (Anzahl bzw. Prozentpunkte). Neue Zeilen und Spalten erscheinen ohne Veränderung.
- Danach: Zusammenfassung der Auffälligkeiten, auffällige laufende Jobs, Worker-Liste.
- Details stehen unter `reports\errors\`.

Beispiel:

```
Auftragsliste DEFA | Pipeline DEFA Proxy: restore --> proxy_10 --> proxy_50 --> qc --> cleanup
Kollektion         | Prio | Gesamt    | Bereit    | %                | restore    | proxy_10 | proxy_50 | qc       | cleanup
-------------------+------+-----------+-----------+------------------+------------+----------+----------+----------+--------
DEFA Dokumentation | 1    | 1200 (+5) | 450 (+40) | 37.5 % (+3.2 pp) | 600 (-40)  | 8 (+2)   | 12 (+3)  | 130 (+0) | 0 (+0)
DEFA Spielfilm     | 2    | 800 (+0)  | 0 (+0)    | 0.0 % (+0.0 pp)  | 800 (+0)   | 0 (+0)   | 0 (+0)   | 0 (+0)   | 0 (+0)
-------------------+------+-----------+-----------+------------------+------------+----------+----------+----------+--------
Summe              |      | 2000 (+5) | 450 (+40) | 22.5 % (+1.9 pp) | 1400 (-40) | 8 (+2)   | 12 (+3)  | 130 (+0) | 0 (+0)

Alle Auftragslisten
Auftragsliste | Gesamt    | Bereit    | %
--------------+-----------+-----------+-----------------
DEFA          | 2000 (+5) | 450 (+40) | 22.5 % (+1.9 pp)
--------------+-----------+-----------+-----------------
Summe         | 2000 (+5) | 450 (+40) | 22.5 % (+1.9 pp)
```

## Verhaltensmuster

- **report_only:** keine Jobs und keine Schreibzugriffe auf das Netzlaufwerk; `delete`-Steps warten. Übernahmen aus Eingängen und Abkürzungen vermerkt Marathon nur im Zustand. Auffälligkeiten werden nur gemeldet.
- **Ohne Zustand** (`state\marathon.json` fehlt) warten Job-Zyklen auf den ersten Bericht.
- **Nicht aufgenommen (Fehlerliste):**
  - Clip in mehreren Kollektionen
  - unvollständige oder widersprüchliche Metadaten
  - gleicher `Dateiname` bei zwei Clips
  - Anzahl der Dateinamen ≠ Anzahl der Hashes (nur vor einem Restore)
  - Platzhalter werden still übergangen.
- **Mehrere passende Dateien** in Eingängen: Marathon übernimmt keine davon und meldet sie.
- **Clips verschwinden nie aus dem Zustand.** Bei Problemen werden sie inaktiv (nicht in „Gesamt“). Fällt der Grund weg, werden sie automatisch wieder aktiv, an ihrem alten Step.
- **Dauerhaft inaktiv:** `fehlgeschlagen` (nach `max_job_attempts` Fehlversuchen) und `qc_abgelehnt`. Eine Abkürzung hebt beides für frühere Steps auf.
- **Limits** zählen nur offene Jobs. Überzählige offene Jobs werden zurückgezogen, zuerst nach Prio, dann nach Reihenfolge der Queue.
- **Metadaten ändern sich:** Ein offener Job wird neu erstellt, ein laufender läuft weiter.
- **Fehlgeschlagener Job:** Teilergebnisse werden gelöscht; beim nächsten Versuch gibt es einen neuen Job.
- **Datei eines Clips verschwindet** (intern oder ausgeliefert): Der Clip wird inaktiv (`verloren`) und ist wieder aktiv, sobald die Datei zurück ist.
- **Zustand neu aufbauen:** `report_only = true` setzen, `state\marathon.json` löschen, `report` ausführen, die Fehlerliste prüfen, dann `report_only = false` setzen.
- **Unbeachtet** bleiben Unterordner externer Ordner, `Thumbs.db`, `desktop.ini`, `.DS_Store`, Punkt- und `~$`-Dateien sowie `.tmp`, `.part` und `.partial`.

## Robust bei

- Suchfehler, Filterfehler oder unvollständiger Suche – der Zustand bleibt unverändert.
- Bedienfehlern in `pipelines.txt` oder Auftragslisten – Pause mit Datei, Zeile und Grund statt Betrieb mit falschen Angaben.
- Netzlaufwerk nicht erreichbar – der Zustand bleibt unverändert; der nächste Zyklus versucht es erneut.
- Absturz von Marathon – Worker arbeiten weiter; Ergebnisse werden beim Neustart übernommen. Der Zustand wird atomar geschrieben.
- Doppeltem Start – Startsperre, die auch nach einem Absturz freigegeben wird.
- Zwei Workern auf demselben Job – nur einer bekommt ihn.
- Halb geschriebenen, unlesbaren oder veralteten Reports und Heartbeats.
- Dateien, die noch kopiert werden – Verarbeitung erst nach `stable_minutes`.
- Verschwundener Job-Datei – nach 30 min neuer Job.
- Worker-Ausfall – Meldung im Bericht.
- Fehlerhafter Config – Pause statt Betrieb mit falschen Werten.
- Namenskonflikt beim Ausliefern – die fremde Datei kommt nach `unbekannt\`.
