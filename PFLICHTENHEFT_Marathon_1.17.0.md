# Pflichtenheft Marathon 1.17.0 – Restore-Sammeljobs

Stand: 2026-10-15 (Fassung 1: Ordnerumbau im Transfer-Script) · Status: **zur Freigabe** · Grundlage: `INTERFACES-4.md` (Fahrplan Schritt 3), Code Marathon 1.16.0
Markierung „(selbst entschieden)“ = von CodeZilla festgelegt, bei der Freigabe bitte mit prüfen.

## 1. Ziel und Umfang

- Marathon 1.17.0 legt Restore-Sammeljobs nach Band an und wertet sie je Clip aus (CR-006, CR-012, CR-014 Marathon-Teil).
- Alle Stufen schreiben `schema_version` 6; Transcode- und QC-Felder unverändert. Keine Abwärtskompatibilität.
- CR-009 Marathon-Teil: `job_ids` im Heartbeat für „Worker mit anderem Job als erwartet“ und die Sperre von `delete-folder`.
- CR-004: Statuszeile bei `run` ohne Testlauf-Angaben.
- Index liest Dateien je Clip neu aus EditShare; JSON-Version 8; Transfer-Script 7 → 8.
- Neuer Befehl `test-restore`.
- Unverändert: Transcode- und QC-Ablauf, Auslegen nach Prio für Transcode/QC, Berichte (außer neuen Gründen), Ingest, FFE.

## 2. Konfiguration (`res/config.ini`)

- Neu `[restore] small_job_clips` (Pflicht, ganze Zahl ≥ 1, vorgesehen 10): höchstens so viele Clips im kleinen Job.
- `[limits] restore` neu: Zahl gleichzeitiger Restore-Jobs (offen oder laufend): `0` = keine neuen, `1` = nur großer Job, `2` = großer und kleiner Job; andere Werte = Config-Fehler (selbst entschieden). Martins Config: von 1 auf 2 setzen.
- Keine Einträge `max_job_gb`, `clips_per_job`, `max_job_files`, `carry_max_clips`.

## 3. Index (`update-index`) und JSON 8

- Suche fragt `video.file`, `audio.file`, `data.file` ab statt userpath/hash/filesize/display_backups. Searcher liefert je Feld Python-repr-Dicts, mehrere mit „; “ verbunden → zurückparsen (nur außerhalb von Zeichenketten und Klammern trennen); unlesbar = Inkonsistenz.
- Je Datei: Name per bestehender Logik aus allen Userpaths (casefold), `hash`, `filesize`, Bänder aus `backup_locations[].tapes` (Schreibweise des ersten Vorkommens, keine Formatprüfung). Genaue Schlüsselnamen beim Umsetzen an einem echten Treffer prüfen (z. B. Clip 641094).
- Dateien eines Clips über `flow_hash` (casefold) zusammenfassen (selbst entschieden). Inkonsistenz, wenn: Name fehlt oder mehrdeutig, Hash fehlt oder nicht `2:<hex>`, Größe fehlt oder keine ganze Zahl, kein Band, gleicher Hash mit verschiedenen Namen/Größen, gleicher Name mit verschiedenen Hashes (selbst entschieden).
- Inkonsistenz wirkt wie bisher `restore_problem`: Clip nicht aufgenommen, wenn er einen Restore braucht; Eintrag in der Index-Fehlerliste. Platzhalter wie bisher über `status_flags`.
- Clip-Feld neu `masters`: Liste `{file, flow_hash, size, tapes}`, sortiert nach `file` (casefold). `filehashes` entfällt.
- Abgeleitet (bleiben): `master_files` = Namen, `lto_tapes` = alle Bänder, `master_size` = Summe aller Dateigrößen (jede Datei zählt, auch gleich große).
- Bekannte Clips: `masters` wird ergänzt, wenn es fehlt; Abweichungen werden wie bisher nur gemeldet (`masters` statt `filehashes` in den überwachten Feldern).
- JSON 8 zusätzlich: Restore-Sammeljobs (je Job: Art groß/klein, Hauptband, Clips, Datei, Ordner, Zustand, Worker, Zeiten, ausgewertete Clips und Teilberichte), Zähler `<n>` für die `job_id`. Clip-`job` verweist auf seinen Sammeljob.
- Marathon 1.17.0 lädt nur JSON 8; bei 7 Abbruch mit Hinweis auf das Transfer-Script.

## 4. Transfer-Script JSON 7 → 8 (`tools/transfer_json_v8.py`, Name selbst entschieden)

- Start im Marathon-Ordner; nutzt Marathons Config, Zugang und Suchcode.
- Abbruch ohne Änderung, wenn: JSON nicht Version 7, Marathon läuft (Lock `state/marathon.lock`), Jobs in `<work_dir>/*/offen/` oder `*/laufend/` liegen.
- Sicherung vorab: `state/marathon.v7_<stempel>.json`.
- Fragt EditShare selbst ab (wie §3) und bildet `masters` für **jeden** Clip der JSON.
- Prüfung je Clip: nicht gefunden, Inkonsistenz oder abweichende Dateinamen gegenüber `master_files` (casefold) = Fehler. Abweichende Bänder oder Größen werden übernommen und im Bericht protokolliert.
- Ordnerstruktur anpassen:
  - Neu anlegen: `<work_dir>/restore/ausgang/`.
  - Entfernen: Restore-Ordner je Kollektion `<Ziel>/<work_dir>[/<Kollektion>]/restore/` samt Unterordnern (`ausgang/`, `archiv/`), nur wenn sie keine Datei enthalten.
  - Löscht nie Dateien. Jede Datei zählt, auch versteckte, System- und 0-Byte-Dateien.
  - Liegt in einem dieser Ordner eine Datei: Abbruch, Fehlerbericht nennt jeden betroffenen Ordner mit seinen Dateien.
- Reihenfolge: erst alle Prüfungen (JSON, Lock, Jobs, EditShare, Ordner), dann Sicherung, Ordner anpassen, zuletzt JSON 8 schreiben. Scheitert eine Ordneränderung trotz Prüfung (z. B. Datei neu hinzugekommen, keine Rechte): sofort Abbruch, JSON bleibt Version 7, Fehlerbericht nennt bereits entfernte leere Ordner.
- Bei irgendeinem Fehler: **nichts** in die JSON schreiben, Fehlerbericht `reports/errors/transfer_<stempel>_errors.txt`.
- Ohne Fehler: JSON 8 schreiben (`masters`, abgeleitete Felder neu, `filehashes` entfernt, `job` aller Clips auf null – schema-5-Jobs sind vorher gelöscht, selbst entschieden); Status, Aktiv-Flag, Versuche und Historie unverändert; Bericht `reports/transfer_<stempel>.txt` mit Zahlen und übernommenen Abweichungen.

## 5. Auswahl der Restore-Jobs (je Job-Zyklus)

- Wartender Clip: aktiv, nicht bereit, Stufe Restore, ohne Job, `masters` vorhanden.
- **Hauptband** je Clip: Bänder, auf denen jede Datei eine Kopie hat. Mehrere → das mit den meisten wartenden Clips, dann Name (selbst entschieden). Keines → Band mit den meisten Dateien des Clips (Gleichstand: meiste wartende Clips, dann Name); jede übrige Datei bekommt ihr Band mit den meisten wartenden Clips, dann Name (selbst entschieden). `tape` je Eintrag = so gewähltes Band.
- Gesperrt: Hauptbänder aller offenen oder laufenden Restore-Jobs. Clips mit gesperrtem Hauptband warten.
- **Großer Job** (`[limits] restore` ≥ 1, kein großer Job offen/laufend): oberste Kollektion der Prioliste mit wartenden Clips auf freien Hauptbändern → deren Hauptband mit den meisten Clips dieser Kollektion (Gleichstand: meiste wartende Clips gesamt, dann Name) → alle wartenden Clips mit diesem Hauptband aus allen Kollektionen. Keine Obergrenze.
- **Kleiner Job** (`[limits] restore` = 2, kein kleiner Job offen/laufend), nach dem großen Job gewählt: freies Hauptband mit ≤ `small_job_clips` wartenden Clips; bei mehreren das mit den meisten Clips der obersten Prio-Kollektion, dann der nächsten usw., dann Name. Gibt es keines: die `small_job_clips` höchstpriorisierten Clips des Hauptbands, das als nächster großer Job gewählt würde; der Rest bleibt wartend.
- Reihenfolge in `items`: Clips nach Prio (Kollektionsrang, `queued_at`), Dateien je Clip nach Name.
- Prioliste wirkt nur auf neu ausgelegte Jobs.
- Clip in offenem Sammeljob wird inaktiv oder verlässt Restore → Job zurückziehen und im selben Zyklus neu planen; Job läuft schon → Job läuft weiter, Ergebnis dieses Clips wird verworfen und sein Clip-Ordner gelöscht (selbst entschieden).

## 6. Job-Datei und Ablage

- Job nach CR-006: `schema_version` 6, `job_id` `<Zeitstempel>__<n>_restore`, `stage` `Restore`, `created_at`, `report_folder` `<work_dir>/restore/fertig`, `output_folder` `<work_dir>/restore/ausgang/<job_id>`, `items` (`clip_id`, `clip_name`, `file`, `flow_hash`, `tape`, `size`).
- Ein Restore-Ausgang für alle Kollektionen unter `<work_dir>/restore/ausgang/`; Restore-Ordner je Kollektion werden nicht mehr angelegt (bestätigt). Die bestehenden baut das Transfer-Script um (§4). `delete-folder` bereinigt den neuen Ausgang mit.
- Job-Datei weg ohne Report: nach 30 Minuten werden alle noch nicht ausgewerteten Clips wieder wartend.

## 7. Auswertung (Teilberichte und Report)

- Teilberichte `<job_id>.teil-<Zeitstempel>.json` in `restore/fertig/` (CR-014): schon während des Jobs, in Namensreihenfolge, je Clip; archiviert als `restore/archiv/<Name>.report.json`.
- Je Clip (CR-006): vollständig = alle Einträge `restored`, `path` liegt im `output_folder` des Jobs (selbst entschieden), Datei vorhanden und Größe = `size` → Dateien nach `…/transcode/eingang/<clip_id>/` der Kollektion, weiter an Transcode, Versuche 0.
- Unvollständig → Clip-Ordner löschen, Gründe aus `reason` in den Bericht, Clip inaktiv „Job endgültig fehlgeschlagen“, kein zweiter Versuch (wieder frei mit `retry-restore`).
- Jeder Clip wird nur einmal ausgewertet; Teilbericht mit unvollständigem Clip → dieser Clip erst mit dem Report. Clips ohne Eintrag im Report oder `items` fehlt/ungültig → unvollständig.
- Report: übrige Clips auswerten, Ausgang löschen, Job-Datei und Report archivieren. Job-Protokoll (`state/journal_restore.jsonl`) je Clip wie bisher.

## 8. Worker-Überwachung, `delete-folder`, CR-004

- Heartbeat: `job_ids` (falls vorhanden, sonst `job_id`) für „Worker mit anderem Job als erwartet“; ein Worker darf mehrere Jobs in `laufend/<worker>/` haben.
- `delete-folder` gesperrt, solange ein frischer Heartbeat `job_ids`/`job_id` meldet oder Jobs ohne Report in `laufend/` liegen.
- `run`: `Status: Job-Schleife läuft; Test-Modus aus; Auto-Bericht aus.`

## 9. `test-restore`

- Legt einen Test-Lauf mit genau einem Restore-Test-Job nach 3.11 an; Clips nach der Regel des kleinen Jobs (selbst entschieden). `marathon.json` bleibt unberührt.
- `output_folder` `<work_dir>/test/restore/ausgang/<job_id>`; Ergebnis bleibt liegen; Job-Datei, Report und Teilberichte werden archiviert, nichts ausgewertet.
- Testbericht je Clip: vollständig/unvollständig mit Gründen. Gesperrt bei offenem Test-Lauf (wie `test-qc`).

## 10. Erfolgskriterien

- Transfer: JSON 8 mit `masters` für alle Clips, `restore/ausgang/` angelegt, leere Restore-Ordner je Kollektion entfernt, keine Datei gelöscht; bei Fehler JSON unverändert plus Fehlerbericht; Sicherung vorhanden.
- `update-index` mit JSON 8: neue Clips mit `masters`, Inkonsistenzen in der Index-Fehlerliste.
- Job-Zyklus: höchstens ein großer und ein kleiner Restore-Job, nie dasselbe Hauptband, Inhalt nach §5/§6 (in `restore/offen/` prüfbar, bevor ein Worker startet).
- Von Hand gelegter Teilbericht und Report: vollständiger Clip im Transcode-Eingang, unvollständiger gelöscht und inaktiv, Ausgang danach gelöscht, alles archiviert.
- QC-Jobs mit `schema_version` 6 laufen mit QC Marathon 2.2.1 durch.
- „anderer Job“ und `delete-folder`-Sperre berücksichtigen `job_ids`; Statuszeile nach CR-004.
- Lokal: Syntax, Imports, Auswahl- und Auswertungslogik mit Testdaten.

## 11. Grenzen

- Marathon prüft keinen Speicherplatz und keinen LTO-Formatfehler; Platz und Bandsperre regelt der Restore-Worker (CR-013).
- Kein Zugriff von Marathon auf Ark.
- Große Jobs können `max_job_hours` (24) überschreiten; das ergibt nur eine Meldung im Bericht.
- Keine Tests gegen EditShare, Share oder Worker durch CodeZilla; nur lokal.

## 12. Nächste Schritte

1. Pflichtenheft freigeben (oder ändern).
2. README Marathon 1.17.0 (inkl. Transfer-Script, `test-restore`, Config) → Freigabe.
3. Code Marathon 1.17.0 und Transfer-Script.
- Für den neuen Thread hochladen: `INTERFACES-4.md`, dieses Pflichtenheft, `marathon.py`, `core/`, `res/config.ini`, `README.md`.
