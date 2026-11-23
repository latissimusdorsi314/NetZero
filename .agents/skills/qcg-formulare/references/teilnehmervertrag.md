# Teilnehmervertrag und Versandmail vorbereiten

Der [Vertragshelfer](../scripts/teilnehmervertrag.py) erzeugt eine druckbare HTML-Datei und einen kopierbaren Mailentwurf. Die [Vertragsvorlage](../assets/teilnehmervertrag.html) und die [Mailvorlage](../assets/teilnehmervertrag-mail.txt) verwenden neutrale Platzhalter. Die Textdatei enthält den Entwurf, keinen versendeten Eintrag im Postfach.

1. Übernimm Teilnehmername und Anschrift, Lehrgang/Modul, Termine, Durchführungsform, Umfang, Abschluss und die bestätigten Anbieterangaben aus der Fallakte. Das Geburtsdatum ist optional und kommt nur in den Vertrag, soweit erforderlich. In der Mail steht allein die für Versand und Kursstart nötige Information.
2. Nutze vorhandene freigegebene Vertragsbedingungen, Lehrgangsangebot und Vertragsunterlagen als Grundlage. Prüfe Vertragspartner und Kostenträger getrennt. Übernimm Gesamtpreis, Steuerangabe, Fälligkeit, etwaige Eigenleistung und die bestätigte Regelung für ausstehende, abweichende oder ausbleibende Förderung. Aus einer BA-Rückmeldung allein folgt keine Zahlungspflicht der teilnehmenden Person. Setze bei offenen Angaben sichtbare Platzhalter und frage sie gebündelt bei der zuständigen Rolle ab.
3. Bei Verbraucherverträgen über organisierte Fernkommunikation die erforderlichen Vorabinformationen und Widerrufsunterlagen für den konkreten Vertriebsweg prüfen. Bei einem entgeltlichen Online- oder Hybridangebot Anwendungsbereich des FernUSG, gegebenenfalls Zulassung und Pflichtinformationen gesondert klären. Die neutrale Vorlage übernimmt Hinweise, Vertragsbedingungen und Anlagen in der tatsächlich freigegebenen Fassung. [§ 312c BGB](https://www.gesetze-im-internet.de/bgb/__312c.html) · [§ 312d BGB](https://www.gesetze-im-internet.de/bgb/__312d.html) · [§ 312g BGB](https://www.gesetze-im-internet.de/bgb/__312g.html) · [§§ 1, 3 und 12 FernUSG](https://www.gesetze-im-internet.de/fernusg/)
4. Verifiziere den Startstatus. Für `bestaetigt` muss der konkrete Beginn feststehen. Eine Vormerkung verwendet `geplant` und nennt die Teilnahmepflicht für den später bestätigten ersten Kurstag. Sind Zustelladresse, Uhrzeit, Zugangslink oder Treffpunkt bzw. Rückgabefrist noch offen, den Entwurf erstellen und diese Punkte nennen. Frage bei reinen Onlinekursen nach dem vorgesehenen Zugangslink. Zugriff und funktionierenden Link über die bereitgestellten Kursdaten prüfen. Private oder personalisierte Links nicht an externe Prüfdienste übermitteln.
5. Prüfe beide Dateien gemeinsam und gleiche Kurs, Modul, Datum, Uhrzeit, Adressat und Rückgabe ab. Für die PDF-Anlage die HTML-Fassung im Browser öffnen und als PDF drucken, anschließend Seitenumbrüche und Signaturfelder prüfen. Nur tatsächlich beigefügte Unterlagen in Abschnitt 5 aufführen. Zur Freigabe auch Gültigkeit des Angebots, passende Anlagen und die zeichnungsberechtigte Person prüfen. Sende den Vertrag und die bezeichneten Anlagen nur bei ausdrücklichem Auftrag.

## Felder und Aufruf

Der Helfer benötigt Python 3. Gib JSON lokal aus der geschützten Fallakte oder über Standardeingabe weiter. Fehlende Textwerte bleiben im Entwurf als Platzhalter stehen. Die Ausgabe meldet die **Feldnamen** ohne private Werte. Verwende einen neuen Ausgabeordner in der Fallakte.

```bash
python3 /pfad/zum/skill/scripts/teilnehmervertrag.py \
  --daten /geschuetzte-fallakte/daten.json \
  --ausgabe /geschuetzte-fallakte/vertrag-entwurf
```

| Gruppe | Eingabefelder |
|---|---|
| Träger und Teilnehmer:in | `traeger_name`, `traeger_anschrift`, `traeger_kontakt`, `teilnehmer_vorname`, `teilnehmer_nachname`, `teilnehmer_anschrift`, `teilnehmer_email`. Optional `geburtsdatum`. |
| Weiterbildung | `kurs`, `startdatum`, `enddatum`, `startstatus`, `startuhrzeit`, `format_ort`, `umfang_abschluss`, `leistungsbeschreibung`. Optional `modul`, `massnahmenummer`. |
| Kosten und Vertrag | `gesamtpreis`, `kostenregelung`, `foerderstatus`, `weitere_regelungen`, `vertragsunterlagen`, `bestaetigungsweg`. Beträge, Bedingungen, Anlagen und Rechtsinformationen aus bestätigter Quelle übernehmen. |
| Versand | `zugangslink` als HTTPS-Link oder `treffpunkt`, `rueckgabefrist`, `rueckgabeweg`. Optional `absenderteam`. |

Datumseingaben `TT.MM.JJJJ` oder `JJJJ-MM-TT`. Uhrzeit `HH:MM`. `--freigegeben` entfernt die Entwurfskennzeichnung ausschließlich nach dokumentierter Freigabe der konkreten Fassung. Das Programm prüft hierfür die Vollständigkeit der erforderlichen Felder. Die interne Freigabe prüft die tatsächlichen Vertragsbedingungen, Unterlagen und ggf. die Zulassung. Unterschriften und tatsächliche Bestätigungsdaten werden durch die Beteiligten gesetzt.
