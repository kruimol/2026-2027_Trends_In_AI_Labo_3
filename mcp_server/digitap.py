"""Digitap/Moodle-laag voor de MCP-server: ICS-feed ophalen en deadlines teruggeven.

Deze module bindt de bewezen POC 2-code (ics_parser.py) samen met het ophalen over
het netwerk. De ICS-URL is PER GEBRUIKER (op het gebruikersrecord in SQLite); is die
er niet, dan valt de server terug op één GEDEELDE DIGITAP_ICS_URL uit .env.
"""

import os

import requests

import ics_parser


def kies_url(persoonlijke_url):
    """Kies de ICS-URL: de persoonlijke (uit de databank) of de gedeelde uit .env."""
    url = (persoonlijke_url or os.getenv("DIGITAP_ICS_URL", "")).strip()
    if not url:
        raise RuntimeError(
            "Geen Digitap ICS-URL gevonden: stel er een in per gebruiker (beheer.py) "
            "of zet een gedeelde DIGITAP_ICS_URL in .env."
        )
    return url


def haal_deadlines(persoonlijke_url, vak=None, dagen=None):
    """Haal de ICS-feed op, parse ze en filter op (komende) deadlines.

    Geeft een tuple terug: (lijst komende deadlines, bool 'lijkt enkel lopende maand').
    """
    url = kies_url(persoonlijke_url)
    antwoord = requests.get(url, timeout=30)
    antwoord.raise_for_status()

    alle = ics_parser.parse_deadlines(antwoord.content)
    komend = ics_parser.filter_deadlines(alle, vak=vak, dagen=dagen)
    return komend, ics_parser.enkel_lopende_maand(alle)
