"""POC 2 - toon mijn Digitap/Moodle-deadlines uit de ICS-kalender.

Gebruik:
    uv run python deadlines.py
    uv run python deadlines.py --vak "Trends in AI"
    uv run python deadlines.py --dagen 14

Haalt de ICS-feed (DIGITAP_ICS_URL uit .env) op en toont de komende deadlines,
gesorteerd op datum, in de tijdzone Europe/Brussels.
"""

import argparse
import os

import requests
from dotenv import load_dotenv

import ics_parser


def haal_ics(url):
    """Download de ICS-feed en geef de ruwe bytes terug."""
    antwoord = requests.get(url, timeout=30)
    antwoord.raise_for_status()
    return antwoord.content


def main():
    parser = argparse.ArgumentParser(description="Toon mijn Digitap/Moodle-deadlines.")
    parser.add_argument("--vak", help="Filter op (een deel van) de vaknaam.")
    parser.add_argument(
        "--dagen", type=int, help="Toon enkel deadlines binnen dit aantal dagen."
    )
    args = parser.parse_args()

    load_dotenv()
    url = os.getenv("DIGITAP_ICS_URL", "").strip()
    if not url:
        raise SystemExit("Zet DIGITAP_ICS_URL in .env (zie .env.example en README).")

    try:
        ics = haal_ics(url)
        alle = ics_parser.parse_deadlines(ics)
    except Exception as fout:
        # Toon de exacte foutmelding en stop (geen nepdata).
        print(f"FOUT: {fout}")
        raise SystemExit(1)

    # Waarschuw als de feed enkel de lopende maand lijkt te bevatten.
    if ics_parser.enkel_lopende_maand(alle):
        print(
            "LET OP: de feed lijkt enkel de lopende maand te bevatten. Pas "
            "'preset_time' in DIGITAP_ICS_URL aan (bv. monthnow -> recentupcoming) "
            "als je meer deadlines verwacht.\n"
        )

    komend = ics_parser.filter_deadlines(alle, vak=args.vak, dagen=args.dagen)
    if not komend:
        extra = f" voor vak '{args.vak}'" if args.vak else ""
        print(f"Geen komende deadlines gevonden{extra}.")
        return

    print(f"Komende deadlines ({len(komend)}):\n")
    for deadline in komend:
        if deadline["heeft_tijd"]:
            wanneer = deadline["wanneer"].strftime("%a %d/%m/%Y om %H:%M")
        else:
            wanneer = deadline["wanneer"].strftime("%a %d/%m/%Y")
        print(f"- [{deadline['vak']}] {deadline['titel']}")
        print(f"    vervalt: {wanneer}")


if __name__ == "__main__":
    main()
