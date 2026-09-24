# Marathon: erster Reporting-Stand

Voraussetzungen: Python >= 3.11, Windows für den Searcher-Dateimodus, erreichbares SMB-Metadatenexport-Share. Das Skript selbst verwendet keine HTTP-Verbindung.

1. TOOLBOX und Searcher gemäß ihren Projekt-READMEs installieren. Für TOOLBOX muss der EditShare-Paketindex konfiguriert sein.
2. res/cred.env.example nach res/cred.env kopieren und SMB_HOST sowie gegebenenfalls SMB_USER/SMB_PASSWORD lokal eintragen. Niemals Zugangsdaten ins Repository einchecken.
3. In marathon.py oben collections, Such-/Hash-Felder und auto_report_time prüfen. Die Namen der Hash-Felder sind mangels Beispielexport noch nicht verifiziert. Fehlende Hashes erscheinen in reports/errors/; vor Restore-Anbindung müssen sie bestätigt werden.
4. Start: python marathon.py. In der Konsole erzeugt report einen manuellen Bericht; quit beendet. Ein Auto-Bericht entsteht ab 09:00 lokaler Rechnerzeit einmal pro Kalendertag. Einzelläufe: python marathon.py --manual bzw. python marathon.py --auto-once.

Berichte: reports/manual_*.txt und reports/auto_*.txt mit unabhängigen Deltas. Fehlerlisten: reports/errors/. Einzige Zustands-JSON: state/marathon.json, atomar ersetzt; Clips bleiben bei Abgängen enthalten, sind aber nicht mehr aktiv. Bereit ist zunächst false; nur ein späterer bestätigter Erfolg des Transcode-Workers darf ready=true setzen. Queues beginnen bei 0 und werden anhand des queue-Feldes gezählt.

report_only=True: Es werden keinerlei Worker-Aufträge angelegt oder Dateien verschoben. report_only=False wird absichtlich mit einem Fehler abgewiesen, bis der Worker-Vertrag implementiert ist. Nicht mehrere Marathon-Instanzen gleichzeitig starten. Zugangsdaten, Zustand, Logs und Berichte nicht ins Repository einchecken.
