# Marathon 1.4.3

Index, Job-Steuerung und Berichte für die Proxy-Erstellung (Restore → Transcode → QC) aus EditShare-Kollektionen.

## Installation

- Python 3.10 oder neuer
- Module `toolbox` (Logging) und `searcher` (EditShare-Suche) im Python-Pfad
- Ordnerstruktur neben `marathon.py`:

```
marathon.py
res/        config.ini, collections.json, Prioliste, Zugangsdateien
state/      marathon.json (Datenbestand), marathon.lock
reports/    Berichte; reports/errors/ Fehlerlisten
log/        marathon.log
```

`log/`, `state/` und `reports/` legt Marathon beim Start selbst an.

## Start

```
python marathon.py                      # interaktive Konsole (Marathon>)
python marathon.py run auto-report      # Befehle direkt nach dem Start ausführen
python marathon.py update-index quit    # Index aktualisieren und beenden
python marathon.py --help
```

## Befehle

| Befehl | Wirkung |
|---|---|
| `run` | Fehlende Ordner und JSON anlegen, dann Job-Schleife starten |
| `stop` | Job-Schleife anhalten |
| `auto-report` | Täglichen Auto-Bericht einschalten (ab `auto_report_time`) |
| `auto-report-off` | Täglichen Auto-Bericht ausschalten |
| `report` | Manuellen Bericht sofort erstellen |
| `create-folders` | Ordnerstruktur aller Kollektionen anlegen |
| `update-index` | Neue Suche (EditShare ∩ Veritone); neue Clips aufnehmen, alles andere in die Index-Fehlerliste |
| `delete-folder` | SMB-Arbeitsordner bereinigen; Index bleibt, Prozesszustand wird neu aufgebaut. Bei Mediendateien Bestätigung mit `loeschen` |
| `status` | Anzeigen, was eingeschaltet ist |
| `help` | Befehlsübersicht |
| `quit` | Marathon beenden (Alias `exit`) |

Aliase: `manual-report`, `manueller-report` → `report`; `auto-report-on` → `auto-report`.

## update-index

1. EditShare-Suche je Kollektion mit den `filters` aus collections.json.
2. Veritone-Suche je Kollektion mit den `veritone_filter_ids`: Suche auslösen, 30 s warten, dann alle Seiten lesen; anschließend Barcodes (`field_clip_id`) aller Treffer. Platzhalter (`Production.Codec` = Placeholder) werden komplett ignoriert und nur im Log gezählt.
3. Abgleich je Kollektion: `001 Identifier` = Barcode (Groß-/Kleinschreibung und Leerzeichen am Rand egal, sonst exakt, z. B. `DEFA13815` ≠ `DEFA13815_1`).
4. Nur Clips der Schnittmenge ohne weitere Probleme werden neu in die JSON aufgenommen.

Bereits vorhandene Clips der JSON werden nie geändert; Abweichungen (z. B. „Nicht mehr bei Veritone“) werden nur gemeldet, die Clips laufen weiter.
Liefert die Veritone-Suche weniger Assets als gemeldet, sucht Marathon die Kollektion bis zu 3-mal erneut (Log: „Durchlauf …“).
Bricht die EditShare- oder Veritone-Abfrage ab (Netz, HTTP-Fehler, nach 3 Durchläufen immer noch unvollständig), bleibt die JSON unverändert.

Das Log zeigt je Kollektion: EditShare, Veritone, Schnittmenge, nur EditShare, nur Veritone.

### Index-Fehlerliste (`reports/errors/index_<Zeitstempel>_errors.txt`)

| Abschnitt | Inhalt |
|---|---|
| Gefunden, aber nicht aufgenommen | Neue Clips mit Problem, u. a. „Nicht bei Veritone“ (mit Hinweis, falls der Barcode bei Veritone in einer anderen Kollektion liegt), doppelte Identifier/Titel, unvollständige Metadaten |
| Suche weicht von der JSON ab | Clips der JSON mit geänderten Metadaten, nicht mehr in der Suche oder nicht mehr bei Veritone |
| Nur bei Veritone gefunden | Barcodes ohne passenden EditShare-Clip in derselben Kollektion; Assets ohne Barcode |

Die JSON speichert davon nur Zeitpunkt, Anzahlen und den Namen der Liste.

## Berichte

- `reports/manual_…txt` / `reports/auto_…txt`: Tabelle je Kollektion mit Prio, Gesamt, Bereit, %, Queues; Deltas zum Vorbericht.
- Zeile „Index-Stand“: Zeitpunkt und Anzahlen des letzten update-index mit Verweis auf die Index-Fehlerliste.
- `reports/errors/<Bericht>_errors.txt`: Details zu Auffälligkeiten des Berichts (inaktive Clips, Zielordner, Hinweise).

## collections.json

```json
{
  "schema_version": 1,
  "collections": [
    {
      "name": "DEFA Dokumentation",
      "filters": [
        {"field": "006 Source PROGRESS", "value": "DEFA"},
        {"field": "007 Collection PROGRESS", "value": "East German Film Archives (DEFA)"},
        {"field": "101a Genre German", "value": "Dokumentarfilm"}
      ],
      "veritone_filter_ids": [10196, 10236, 14794]
    }
  ]
}
```

| Eintrag | Bedeutung |
|---|---|
| `name` | Kollektionsname, eindeutig; bestimmt die Ordnernamen. „Summe“ ist reserviert |
| `filters` | EditShare-Suchbedingungen (UND); erlaubte Felder: `006 Source PROGRESS`, `007 Collection PROGRESS`, `101a Genre German` |
| `veritone_filter_ids` | Pflicht: Veritone-Filter-IDs (UND), wie in der Veritone-Websuche `filterIds=…` |

## config.ini (`res/config.ini`)

Alle Einträge sind Pflicht. Ist die Datei fehlerhaft, pausiert Marathon, bis sie korrigiert ist; sie wird laufend neu gelesen. Änderungen in `[paths]` erfordern einen Neustart.

| Abschnitt | Eintrag | Bedeutung |
|---|---|---|
| paths | `root_path` | Netzlaufwerk mit allen Zielordnern |
| paths | `defa_dir` | Zielordner aller DEFA-Kollektionen |
| paths | `work_dir` | Arbeitsordner von Marathon (einfacher Ordnername) |
| paths | `defa_marker` | Kollektionen mit diesem Text im Namen liefern nach `defa_dir` |
| paths | `proxy_prefix` | Proxy-Namensschema `<proxy_prefix>__<Identifier>__<Titel>.<Endung>` |
| paths | `cred_file` | Searcher-Zugang im res-Ordner |
| paths | `mapping_file` | Kollektionsmapping im res-Ordner |
| paths | `priority_file` | Prioliste im res-Ordner (fehlt sie, wird eine Vorlage angelegt) |
| operation | `auto_report_time` | Uhrzeit des Auto-Berichts (HH:MM) |
| operation | `retry_minutes` | Wartezeit nach fehlgeschlagenem Auto-Bericht |
| timing | `cycle_seconds` | Sekunden zwischen zwei Job-Zyklen |
| timing | `max_job_attempts` | Versuche je Job |
| limits | `restore`, `transcode`, `qc` | Maximal offene Jobs je Stufe (0 = Stufe pausiert) |
| heartbeat | `worker_timeout_minutes` | Minuten ohne Lebenszeichen, bis ein Worker als ausgefallen gilt |
| heartbeat | `max_job_hours` | Stunden, ab denen ein laufender Job gemeldet wird |
| veritone | `base_url` | Basis-URL der Veritone Assets-API |
| veritone | `token_file` | Zugang im res-Ordner: JSON-Objekt oder `KEY=VALUE`-Zeilen mit `vt_api_token`, `api_key`, `apiKey`, `token` oder `access_token` |
| veritone | `field_clip_id` | Veritone-Feld mit dem Barcode: `Supplier.Barcode` |

## Prioliste

Abschnitte `[Restore]`, `[Transcode]`, `[QC]`, je Zeile eine Kollektion, oben = höchste Priorität. Nicht aufgeführte Kollektionen folgen in der Reihenfolge von collections.json.
