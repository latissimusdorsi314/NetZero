#!/usr/bin/env python3
"""Create a local participant contract and a plain-text email draft from verified inputs."""

import argparse
import json
import os
import re
import sys
from datetime import date
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import urlsplit


ASSETS = Path(__file__).resolve().parent.parent / "assets"
REQUIRED = {
    "traeger_name": "Name des Bildungsträgers",
    "traeger_anschrift": "Anschrift des Bildungsträgers",
    "traeger_kontakt": "Kontakt des Bildungsträgers",
    "teilnehmer_vorname": "Vorname",
    "teilnehmer_nachname": "Nachname",
    "teilnehmer_anschrift": "Anschrift der teilnehmenden Person",
    "teilnehmer_email": "E-Mail-Adresse für den Versand",
    "kurs": "Kursbezeichnung",
    "startdatum": "Startdatum",
    "enddatum": "Kursende",
    "startstatus": "Startstatus: geplant oder bestaetigt",
    "startuhrzeit": "Uhrzeit des ersten Kurstags",
    "format_ort": "Durchführungsform und Kursort",
    "umfang_abschluss": "Unterrichtsumfang und Abschluss",
    "leistungsbeschreibung": "Vereinbarter Leistungsumfang",
    "gesamtpreis": "Vereinbarter Gesamtpreis mit Währung und Steuerangabe",
    "kostenregelung": "Kostentragung, Eigenanteil, Fälligkeit und Regelung bei offener oder abweichender Förderung",
    "foerderstatus": "Belegter Förderstatus",
    "weitere_regelungen": "Vereinbarte weitere Regelungen oder Verweise",
    "vertragsunterlagen": "Tatsächlich beigefügte Vertragsunterlagen mit Stand",
    "bestaetigungsweg": "Vereinbarter Weg der Vertragsbestätigung",
    "rueckgabefrist": "Rückgabefrist für den Vertrag",
    "rueckgabeweg": "Rückgabeweg für den Vertrag",
}
OPTIONAL = {"geburtsdatum", "modul", "massnahmenummer", "zugangslink", "treffpunkt", "absenderteam"}
MULTILINE = {
    "traeger_anschrift", "teilnehmer_anschrift", "leistungsbeschreibung", "kostenregelung",
    "weitere_regelungen", "vertragsunterlagen",
}


def read_data(path):
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("Die Eingabe muss ein JSON-Objekt mit Textwerten sein.")
    unknown = raw.keys() - (REQUIRED.keys() | OPTIONAL)
    if unknown:
        raise ValueError("Unbekannte Felder: " + ", ".join(sorted(unknown)))
    result = {}
    for key, value in raw.items():
        if not isinstance(value, str):
            raise ValueError(f"{key}: Textwert erwartet.")
        value = value.strip()
        if key in MULTILINE:
            value = value.replace("\r\n", "\n")
        if any(ord(char) < 32 and (char != "\n" or key not in MULTILINE) for char in value):
            raise ValueError(f"{key}: Unzulässiger Zeilenumbruch oder Steuerzeichen.")
        if value:
            result[key] = value
    return result


def parse_date(value, field):
    try:
        if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", value):
            day, month, year = (int(part) for part in value.split("."))
            return date(year, month, day)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value)
    except ValueError:
        pass
    raise ValueError(f"{field}: Gültiges Datum im Format TT.MM.JJJJ oder JJJJ-MM-TT erwartet.")


def validate(data):
    if data.get("startstatus", "geplant") not in {"geplant", "bestaetigt"}:
        raise ValueError("startstatus: geplant oder bestaetigt erwartet.")
    date_keys = ("geburtsdatum", "startdatum", "enddatum", "rueckgabefrist")
    dates = {key: parse_date(data[key], key) for key in date_keys if key in data}
    if "startdatum" in dates and "enddatum" in dates and dates["enddatum"] < dates["startdatum"]:
        raise ValueError("enddatum muss am oder nach dem Startdatum liegen.")
    for key, value in dates.items():
        data[key] = value.strftime("%d.%m.%Y")
    if "startuhrzeit" in data and not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", data["startuhrzeit"]):
        raise ValueError("startuhrzeit: Uhrzeit im Format HH:MM erwartet.")
    if "teilnehmer_email" in data and not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", data["teilnehmer_email"]):
        raise ValueError("teilnehmer_email: einzelne E-Mail-Adresse erwartet.")
    if "zugangslink" in data:
        link = urlsplit(data["zugangslink"])
        if link.scheme != "https" or not link.hostname or link.username or any(c.isspace() for c in data["zugangslink"]):
            raise ValueError("zugangslink: HTTPS-Link ohne Leerzeichen oder Anmeldedaten erwartet.")
    missing = [key for key in REQUIRED if key not in data]
    if not ("zugangslink" in data or "treffpunkt" in data):
        missing.append("zugangslink oder treffpunkt")
    return missing


def contract_values(data, values, confirmed, approved):
    view = {key: escape(value) for key, value in values.items()}
    view.update({
        "dokumentstatus": "Individuelle Vereinbarung" if approved else "Entwurf zur Prüfung",
        "startstatus_text": "Bestätigter Start" if confirmed else "Geplanter Start · Bestätigung folgt",
        "startuhrzeit_text": f"{view['startuhrzeit']} Uhr",
        "geburtsdatum_block": f"<div>Geburtsdatum: {escape(data['geburtsdatum'])}</div>" if "geburtsdatum" in data else "",
        "massnahmenummer_block": f"<dt>Maßnahmenummer</dt><dd>{escape(data['massnahmenummer'])}</dd>" if "massnahmenummer" in data else "",
    })
    return view


def mail_values(data, values, confirmed):
    view = dict(values)
    access = []
    if "zugangslink" in data:
        access_label = "Zugangslink zum ersten Kurstag" if confirmed else "Zugangslink für den geplanten ersten Kurstag"
        access.append(f"{access_label}: {data['zugangslink']}")
    if "treffpunkt" in data:
        access.append(f"Treffpunkt: {data['treffpunkt']}")
    if confirmed:
        subject = f"Dein Teilnehmervertrag und Kursstart am {values['startdatum']}"
        booking = "Hiermit bestätigen wir Deine Buchung zum folgenden Starttermin."
        confirmation = "Bestätige uns bitte auch kurz den Starttermin."
        attendance = "Die Teilnahme am ersten Kurstag ist verpflichtend."
    else:
        subject = "Dein Teilnehmervertrag und die Vormerkung für den Kursstart"
        booking = "Wir haben Deinen Platz für den geplanten Start vorgemerkt. Den tatsächlichen Start bestätigen wir Dir, sobald er geklärt ist."
        confirmation = "Gib uns bitte kurz Bescheid, ob der geplante Termin für Dich passt."
        attendance = "Sobald der Starttermin bestätigt ist, ist die Teilnahme an diesem ersten Kurstag verpflichtend."
    view.update({
        "mail_betreff": f"{subject} | {values['kurs']}",
        "mail_buchung": booking,
        "mail_start_label": "Start" if confirmed else "Geplanter Start",
        "startzeit_zusatz": f" um {values['startuhrzeit']} Uhr",
        "mail_zugang": "\n".join(access) or "Zugang: [HTTPS-Zugangslink oder Treffpunkt ergänzen]",
        "mail_start_bestaetigen": confirmation,
        "mail_teilnahmepflicht": attendance,
        "absenderteam": data.get("absenderteam", values["traeger_name"]),
    })
    return view


def render_asset(name, values):
    return Template((ASSETS / name).read_text(encoding="utf-8")).substitute(values)


def write_private(path, contents):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(contents)


def prepare(data, output, approved):
    missing = validate(data)
    if approved and missing:
        raise ValueError("Felder für die freigegebene Fassung fehlen: " + ", ".join(missing))
    values = {key: data.get(key, f"[{label} ergänzen]") for key, label in REQUIRED.items()}
    values["modul_zusatz"] = f" · {data['modul']}" if "modul" in data else ""
    confirmed = data.get("startstatus") == "bestaetigt" and "startdatum" in data
    contract = render_asset("teilnehmervertrag.html", contract_values(data, values, confirmed, approved))
    mail = render_asset("teilnehmervertrag-mail.txt", mail_values(data, values, confirmed))
    output.mkdir(mode=0o700, exist_ok=False)
    write_private(output / "Teilnehmervertrag.html", contract)
    write_private(output / "Versandmail-Entwurf.txt", mail)
    print(json.dumps({"dateien": ["Teilnehmervertrag.html", "Versandmail-Entwurf.txt"],
                      "offene_felder": missing, "startstatus": "bestaetigt" if confirmed else "geplant"},
                     ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daten", default="-", help="JSON-Datei oder Standardeingabe")
    parser.add_argument("--ausgabe", required=True, type=Path, help="Neuer Ausgabeordner in der Fallakte")
    parser.add_argument("--freigegeben", action="store_true", help="Nur nach dokumentierter Freigabe der konkreten Fassung verwenden")
    args = parser.parse_args()
    try:
        prepare(read_data(args.daten), args.ausgabe, args.freigegeben)
    except (OSError, ValueError) as exc:
        print(f"Teilnehmervertrag: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
