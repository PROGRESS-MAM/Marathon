# Marathon 0.2 — Reporting

Python >=3.11, TOOLBOX und Searcher (PROGRESS-MAM/ES-Search) installieren. Der Searcher-Dateimodus braucht derzeit Windows und Zugriff auf die Parquet-Datei per SMB. Keine produktiven Jobs oder Dateiverschiebungen: report_only=True; False bricht absichtlich ab.

res/cred.env.example nach res/cred.env kopieren und SMB_HOST, bei Bedarf SMB_USER und SMB_PASSWORD eintragen. Keine echten Zugangsdaten, state/, reports/ oder log/ einchecken.

res/collections.json enthält die geordnete Liste der Kollektionen, Solltreffer und pro Kollektion exakte Feld-Wert-Filter. Mehrere Filter werden mit AND kombiniert. Pro Report startet jede Suche erneut. Die Solltreffer stehen im Bericht als Gesamt, auch wenn Searcher weniger/mehr findet. Abweichungen landen in reports/errors/ und als Hinweis im Report. Ein im aktuellen Suchlauf fehlender Clip wird nicht aus der einzigen JSON unter state/ entfernt oder deaktiviert. Hashes werden aus dem Searcher-Rückgabefeld hash gesammelt; Clip_ID und clip_name_with_extension stehen beim Clip in der JSON. Fehlende Hashes und unklare Treffer erscheinen in der Fehlerliste.

Start: python marathon.py. Im laufenden Prozess erzeugt report einen manuellen Bericht; quit beendet. Ab auto_report_time (Standard 09:00 Uhr Rechnerzeit) einmal täglich ein Auto-Bericht. Für einen Einmallauf: python marathon.py --manual oder python marathon.py --auto-once. Beide Linien vergleichen nur mit ihrem eigenen Vorgänger. Der Zustand wird atomar ersetzt. Noch keine Worker-Verarbeitung: ready bleibt bei neuen Clips false, alle Queues beginnen mit 0. Nicht mehrere Marathon-Instanzen parallel starten.
