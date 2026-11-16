# Tasks – Universelle Auswertung der Detailberichte

## Globale Vorgaben
- Ziel-Datei: Auswertung/auswerte_detailberichte.py (Basis: Martins Transcode-Skript 2.0.0, Zusammenfassungsformat beibehalten)
- Pfade absolut: marathon_root = C:\Users\Martin\OneDrive - LOOKS Film & TV Produktionen GmbH\Desktop\Code\Marathon; Archiv = marathon_root\reports\archive; State = marathon_root\state\marathon.json
- Aufruf: genau eines von --restore | --transcode | --qc (Pflicht)
- --kollektion NAME: nur Einträge, deren Kollektion NAME enthält (casefold, Teilstring); ohne Angabe alle
- --n N bzw. Kurzform --N (z. B. --5): nur die letzten N Reports (nach Dateiname); ohne Angabe alle
- Namensschema: details_<typ>_YYYY-MM-DD_HH-MM-SS-ffffff.txt
- Kategorien: Meldungsmuster wie im Beispiel; QC-REJECTED nach Kriterium "tool(name) · kriterium"
- app_version = "3.0.0"

## Tabelle
| ID | Paket | Dateien | Abhängig von | Modus | Review | Status |
|----|-------|---------|--------------|-------|--------|--------|
| T1 | CLI, Berichtsauswahl, Kollektionsfilter, Clip-Dedup, Ausgabename | Auswertung/auswerte_detailberichte.py, Auswertung/test_auswerte_detailberichte.py | – | direct | A | fertig |
| T2 | Typabhängige Kategorisierung (restore/qc/transcode) | Auswertung/auswerte_detailberichte.py, Auswertung/test_auswerte_detailberichte.py | T1 | direct | A | fertig |

## Entscheidungen
- T1: Dedup pro clip_id, neuester Eintrag gewinnt – Restore-Batchjobs teilen eine Job-ID; QC-Wiederholungen nur einmal
- T1: Ausgabe neben dem Skript: auswertung_<typ>[_<kollektion>].txt, überschreibbar mit --ausgabe
- T2: Restore-Kategorie = Meldung ohne "Source <datei>:"-Präfix, Band als <band>, Zahlen als # (Martin)
- T2: QC FAILED = Meldung ohne Dateipräfixe; [..]-Blöcke entfernt, UNC-Pfade als <pfad>, TC als <tc>
- T2: Auswertung/__init__.py ergänzt – Basisnamen-Konflikt mit tests/test_auswerte_detailberichte.py bei pytest an der Repo-Wurzel
- T2: Reviewer-Zusatz _split_reasons zurückgenommen – nicht beauftragt, Transcode-Verhalten wie im Beispiel
