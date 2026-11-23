# Marathon – Mehrfachtitel aufnehmen

## Globale Vorgaben
- Trenner für zusammengesetzte Mehrfachwerte: "; " (Original aus EditShare), z. B. `Unruhe; Wopyt`
- Betroffene Felder: `014 Title Original` (title) und `clip_name_with_extension` (clip_name)
- `001 Identifier` mit mehreren Werten bleibt Fehler; 0 Werte bleiben Fehler
- app_version: 1.18.4
- Tests: pytest mit `-p no:cacheprovider`

## Tabelle
| ID | Paket | Dateien | Abhängig von | Modus | Review | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | Mehrfachtitel/-clipnamen mit "; " zusammensetzen | core/search.py, core/__init__.py, README.md, tests/test_search_merge.py | – | direct | B | fertig |

## Entscheidungen
- T1: Titel-Teile mit "; " zusammensetzen – Martin, entspricht EditShare und FFE-Liste
- T1: Clipnamen ebenso mit "; " – echter EditShare-Name, im Restore genutzt
- T1: Einzelwerte bleiben exakt wie bisher (split_values) – keine neuen Abweichungen bei Clips in der JSON
- T1: Leerer Titel, clip_id ungültig, Identifier mehrfach bleiben ausgeschlossen
- T1: Basisstand-Nachweis selbst geführt (Reviewer-Snapshot enthielt bereits die Änderung): 5 failed / 3 passed → 8 passed
