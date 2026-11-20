# PDF-Bearbeitung und Prüfung

Der Helfer benötigt Python 3 und `qpdf` mit JSON-Version 2. Verwende pro Datei eine separate Feldliste mit den technischen Namen des konkreten PDFs. `inspect` gibt standardmäßig keine eingetragenen Werte aus. Die Pflichtfelder und Signaturblöcke zusätzlich am sichtbaren Formular prüfen. Das PDF-Pflichtflag kann von den gedruckten Sternchen abweichen. Eingabedaten gehören ausschließlich in den freigegebenen Fallordner oder in eine geschützte temporäre Eingabe. Keine Stammdaten im Skill oder in wiederverwendbaren Beispielen speichern.

```bash
python3 /pfad/zum/skill/scripts/ba_pdf.py inspect /fall/blanko.pdf
python3 /pfad/zum/skill/scripts/ba_pdf.py fill /fall/blanko.pdf /fall/vorbereitet.pdf --edits /fall/felder.json
python3 /pfad/zum/skill/scripts/ba_pdf.py fill /fall/vollmacht.pdf /fall/vollmacht-seite-1.pdf --edits /fall/felder.json --pages 1
```

Das Eingabeformat ist ein JSON-Objekt wie `{"technischer_feldname":"Beispielwert"}`. Bei Kontrollkästchen und Ja/Nein-Gruppen den exakten von `inspect` gemeldeten Zustand verwenden, einschließlich `/`. Für einen bewusst bestätigten Widerspruch zum bereits vorhandenen PDF-Wert steht `--replace` bereit. Bereits vorhandene Fallwerte bleiben ohne Feldanweisung erhalten. Prüfe sie deshalb auch dann auf ihre Gültigkeit, wenn der Helfer sie nicht ändert. Zum Auszug ohne Änderungen `{}` übergeben. Signatur- und Datumsfelder des Unterzeichners sowie Stempelbereiche bleiben manuell. Bestehende Papier- oder Bildunterschriften vor Änderungen visuell erkennen. Originale erhalten und eine unsignierte Quelle suchen.

Der Helfer schreibt neue Kopien, erhält die Formularfelder und prüft Seitenzahl, Werte und PDF-Struktur. Er unterstützt gewöhnliche Textfelder und Auswahlmarkierungen. Bei Spezialfeldern, Scans, fremdsprachigen Zeichen außerhalb der unterstützten Kodierung, Platzmangel, PDF-Warnungen oder ungewöhnlichen Vorlagen das Ergebnis im PDF-Viewer prüfen und bei Bedarf einen lokalen Editor verwenden. Die Sichtprüfung ist auch bei erfolgreichem Lauf erforderlich. `pdftoppm` rendert die neuen Seiten, `pdftotext -layout` erleichtert den Vergleich von Formulartitel, Versionsstand und Inhalt. Bei der Ausgabe von Auszügen auch prüfen, dass im Dokument und im Formularbereich nur die vorgesehenen Seiten und zugehörigen Felder enthalten sind. Die unterschriftsreife Fassung visuell mit dem Original vergleichen.
