"""Fixed texts, field names, stages, categories and the command overview."""
# --------- IMPORTS ---------
from datetime import timedelta


# --------- STATIC ---------
field_names = {
    "clip_id": "clip_id",
    "identifier": "001 Identifier",
    "title": "014 Title Original",
    "clip_name": "clip_name_with_extension",
    "hash": "hash",
    "userpath": "userpath",
    "status_flags": "status_flags",
    "backups": "display_backups",
    "size": "filesize",
}
stages = ("restore", "transcode", "qc")  # Also the stage folder names.
stage_labels = {"restore": "Restore", "transcode": "Transcode", "qc": "QC"}
limit_keys = {stage: stage_labels[stage].casefold() for stage in stages}
pool_boxes = ("offen", "laufend", "fertig", "archiv")
collection_boxes = ("ausgang", "archiv")
inbox, outbox, worker_dir = "eingang", "ausgang", "worker"
report_statuses = ("ok", "failed", "rejected")
system_files = frozenset({"thumbs.db", "desktop.ini", ".ds_store"})
busy_suffixes = (".tmp", ".part", ".partial")
protocol_suffixes = (".json", ".txt", ".log")
prio_columns = tuple(f"Prio {stage_labels[stage]}" for stage in stages)
queue_columns = tuple(f"Queue {stage_labels[stage]}" for stage in stages)
count_columns = ("Gesamt", "Bereit", *queue_columns)
columns = ("Kollektion", *prio_columns, "Gesamt", "Bereit", "%", *queue_columns)
summary_name = "Summe"
match_separator = "———"
invalid_path_chars = frozenset('<>:"/\\|?*' + "".join(map(chr, range(32))))
reserved_names = frozenset({"CON", "PRN", "AUX", "NUL", *(f"{kind}{number}" for kind in ("COM", "LPT") for number in range(1, 10))})
editshare_field, editshare_attempts = "39d 10 Mbit Proxy Path", 3  # Field for the delivered proxy path; failed cycles until reported.
issue_sections = {
    "skipped": "Gefunden, aber nicht aufgenommen (letzter update-index, nicht in Gesamt)",
    "deviation": "Suche weicht von der JSON ab (letzter update-index, nicht übernommen)",
    "veritone_only": "Nur bei Veritone gefunden (letzter update-index, nicht in Gesamt)",
    "veritone_multi": "Barcode mehrfach bei Veritone (letzter update-index, Veritone-ID nicht übernommen)",
    "ffe_missing": "FFE-Titel nicht in der JSON (letzter FFE-Abgleich)",
    "inactive": "In der JSON, aber nicht aktiv (nicht in Gesamt)",
    "final": "Auffällige Clip-Dateien in finalen Ablageordnern",
    "editshare": f"EditShare-Feld nicht gesetzt (ab {editshare_attempts} gescheiterten Job-Zyklen; wird weiter versucht, Clip zählt als bereit)",
    "note": "Hinweise (betroffene Clips zählen weiter)",
}
index_sections = ("skipped", "deviation", "veritone_only", "veritone_multi")
index_labels = {"skipped": "nicht aufgenommen", "deviation": "Abweichungen", "veritone_only": "nur bei Veritone",
                "veritone_multi": "Veritone-ID uneindeutig"}
problem_categories = {  # kind: (category for new clips, category for clips already in the JSON)
    "missing": (None, "Nicht mehr in der Suche"),
    "multi": ("Clip-ID in mehreren Kollektionen", "Clip-ID jetzt in mehreren Kollektionen"),
    "invalid": ("Unvollständige oder widersprüchliche Metadaten",
                "Metadaten in der Suche jetzt unvollständig oder widersprüchlich"),
    "duplicate": ("Doppelter Identifier/Titel", None),
    "restore": ("Dateinamen und Hashes passen nicht zusammen", None),
    "veritone": ("Nicht bei Veritone", "Nicht mehr bei Veritone"),
}
metadata_changed = "Metadaten in der Suche geändert"
veritone_missing, veritone_ambiguous = "Veritone-ID fehlt", "Mehrere Assets mit demselben Barcode"
veritone_unmatched, barcode_missing = "Kein passender Clip in der EditShare-Suche dieser Kollektion", "Ohne Barcode bei Veritone"
lost_proxy, lost_master = "Verloren – Proxy fehlt", "Verloren – Master fehlt vor Transcode"
qc_rejected, job_failed = "QC nicht bestanden", "Job endgültig fehlgeschlagen"
delivery_blocked, assignment_unclear = "Auslieferung blockiert", "Zuordnung beim Neuaufbau unklar"
master_blocked, editshare_failed = "Neuer Master blockiert", "EditShare-Feld nicht gesetzt"
status_codes = {delivery_blocked: "auslieferung_blockiert", master_blocked: "master_blockiert", assignment_unclear: "zuordnung_ungeklaert", lost_proxy: "verloren", lost_master: "verloren", qc_rejected: "qc_abgelehnt", job_failed: "fehlgeschlagen"}
commands_help = {
    "run": "Ordner und JSON anlegen, falls sie fehlen; dann Job-Schleife starten",
    "stop": "Job-Schleife anhalten",
    "auto-report": "Täglichen Auto-Bericht einschalten (ab auto_report_time)",
    "auto-report-off": "Täglichen Auto-Bericht ausschalten",
    "report": "Manuellen Bericht sofort erstellen",
    "create-folders": "Ordnerstruktur aller Kollektionen anlegen",
    "update-index": "Neue Suche (EditShare ∩ Veritone); neue Clips aufnehmen, fehlende Felder ergänzen, Abweichungen in die Index-Fehlerliste; FFE-Abgleich",
    "update-ffe": "Nur FFE-Liste mit der bestehenden JSON abgleichen (ffe_tafel neu setzen), ohne Suche",
    "ingest-master": "Masterdateien aus master_dir über die DEFA-ID mit der JSON abgleichen und eintragen (nur manuell)",
    "ingest-proxy": "Proxys aus proxy_dir über die DEFA-ID abgleichen, umbenannt in den QC-Eingang verschieben (nur manuell)",
    "delete-folder": "SMB-Arbeitsordner bereinigen; Index behalten, Prozesszustand neu aufbauen",
    "status": "Anzeigen, was eingeschaltet ist",
    "help": "Diese Übersicht",
    "quit": "Marathon beenden",
}
missing_job_grace = timedelta(minutes=30)  # Before a vanished job file is recreated.
editshare_filter_fields = frozenset({"006 Source PROGRESS", "007 Collection PROGRESS", "101a Genre German"})
token_key = "vt_api_token"  # KEY=VALUE line in token_file
veritone_page_size, veritone_timeout = 200, 120  # Search and byIds take at most 200 per call.
veritone_placeholder = ("Production.Codec", "placeholder")  # Field and casefolded value of placeholder assets.
veritone_passes = 3  # Paging is not always stable; missing assets are searched again in further passes.
veritone_settle_seconds = 30  # Wait between triggering a search and reading its pages; the API has no "done" signal.
tracked_fields = {"collection": "Kollektion", "identifier": field_names["identifier"], "title": field_names["title"],
                  "clip_name_with_extension": field_names["clip_name"], "master_files": field_names["userpath"],
                  "filehashes": field_names["hash"], "veritone_id": "Veritone-ID"}
ffe_flag = "ffe_tafel"
ffe_missing = "Kein Clip mit genau dieser defa_id und diesem title"
ffe_ambiguous = "Mehrere Clips mit genau dieser defa_id und diesem title"
ffe_ambiguous_sections = {"ffe_ambiguous": "FFE-Titel uneindeutig (letzter FFE-Abgleich, nicht markiert)"}
ffe_share_keys = ("reference_image", "reference_clip_dir")  # Names on the share; a change needs a restart like [paths].
ffe_clip_suffix = ".mov"  # Only these files in reference_clip_dir count as FFE title clips.
ffe_mtime_tolerance = 2  # Seconds; SMB servers may store modification times with reduced precision.
ingest_source, ingest_separator = "Ingest", "__"  # files.master source of ingested masters; master name <DEFA-ID>__<title>
ingest_sections = {"ingest_error": "Nicht eingetragen (Fehler)", "ingest_info": "Hinweise (kein Fehler, nicht eingetragen)"}
