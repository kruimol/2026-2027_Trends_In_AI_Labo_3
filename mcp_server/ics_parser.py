"""Parsen en filteren van een Moodle/Digitap ICS-kalender.

Overgenomen uit POC 2 (poc2_deadlines/ics_parser.py). Deze module doet geen netwerk;
ze werkt op ruwe ICS-bytes. Zo kunnen we het parsen offline testen met een
voorbeeldbestand (zie test_server.py).

In een Moodle-export staat per deadline een VEVENT met:
- UID         = stabiele identificatie (gebruiken we om een status aan te hangen),
- SUMMARY     = naam van de opdracht,
- CATEGORIES  = korte naam van het vak,
- DTSTART     = vervaldatum (soms met tijd in UTC, soms enkel een datum).
"""

import datetime
from zoneinfo import ZoneInfo

from icalendar import Calendar

BRUSSEL = ZoneInfo("Europe/Brussels")


def _als_brussel(moment):
    """Geef (aware datetime in Brussel, heeft_tijd) voor een date of datetime.

    All-day events (VALUE=DATE) hebben geen tijd; die tonen we als datum alleen.
    """
    if isinstance(moment, datetime.datetime):
        if moment.tzinfo is None:  # naïef -> veronderstel lokale (Brusselse) tijd
            moment = moment.replace(tzinfo=BRUSSEL)
        return moment.astimezone(BRUSSEL), True
    # Een kale datum -> middernacht Brusselse tijd, zonder tijdsaanduiding.
    return datetime.datetime(moment.year, moment.month, moment.day, tzinfo=BRUSSEL), False


def parse_deadlines(ics_bytes):
    """Zet een ICS-feed om naar een lijst deadlines, gesorteerd op datum.

    Elke deadline is een dict: {uid, vak, titel, wanneer (aware datetime), heeft_tijd}.
    De uid is de stabiele VEVENT-UID; daarmee hangen we later een status aan.
    """
    kalender = Calendar.from_ical(ics_bytes)
    deadlines = []
    for event in kalender.walk("VEVENT"):
        start = event.get("DTSTART")
        if start is None:
            continue
        wanneer, heeft_tijd = _als_brussel(start.dt)

        categorie = event.get("CATEGORIES")
        vak = str(categorie.cats[0]) if categorie and categorie.cats else "?"
        titel = str(event.get("SUMMARY", "")).strip() or "(geen titel)"
        uid = str(event.get("UID", "")).strip()

        deadlines.append(
            {
                "uid": uid,
                "vak": vak,
                "titel": titel,
                "wanneer": wanneer,
                "heeft_tijd": heeft_tijd,
            }
        )

    deadlines.sort(key=lambda d: d["wanneer"])
    return deadlines


def filter_deadlines(deadlines, vanaf=None, vak=None, dagen=None):
    """Hou enkel komende deadlines (>= vanaf), optioneel per vak en binnen N dagen."""
    if vanaf is None:
        vanaf = datetime.datetime.now(tz=BRUSSEL)
    tot = vanaf + datetime.timedelta(days=dagen) if dagen is not None else None

    resultaat = []
    for deadline in deadlines:
        if deadline["wanneer"] < vanaf:
            continue
        if vak and vak.lower() not in deadline["vak"].lower():
            continue
        if tot and deadline["wanneer"] > tot:
            continue
        resultaat.append(deadline)
    return resultaat


def enkel_lopende_maand(deadlines, vandaag=None):
    """True als geen enkele deadline ná de lopende maand valt.

    Dan lijkt de feed beperkt tot deze maand (bv. preset_time=monthnow in de URL).
    """
    if not deadlines:
        return False
    if vandaag is None:
        vandaag = datetime.datetime.now(tz=BRUSSEL)

    # Eerste dag van de volgende maand (middernacht, Brusselse tijd).
    if vandaag.month == 12:
        volgende_maand = vandaag.replace(year=vandaag.year + 1, month=1, day=1)
    else:
        volgende_maand = vandaag.replace(month=vandaag.month + 1, day=1)
    volgende_maand = volgende_maand.replace(hour=0, minute=0, second=0, microsecond=0)

    return max(d["wanneer"] for d in deadlines) < volgende_maand
