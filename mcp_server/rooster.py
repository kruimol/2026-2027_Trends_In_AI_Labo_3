"""Rooster ophalen via de WebUntis REST-API.

Overgenomen uit POC 1 (poc1_webuntis/rooster.py). We gebruiken
/WebUntis/api/public/timetable/weekly/data in plaats van de klassieke
getTimetable-RPC. Reden: veel scholen blokkeren die RPC voor studenten met de fout
-8509 "no right for timetable". De REST-API gebruikt dezelfde rechten als de
WebUntis-website en werkt daardoor meestal wél, met dezelfde JSESSIONID-cookie die
we bij het inloggen al kregen.

De zware verwerking (JSON -> eenvoudige lessen) zit in _lessen_uit_week, die we
los kunnen testen met een fixture (zie test_server.py).
"""

import base64
import datetime

import requests

# Elementtypes in WebUntis.
TYPE_KLAS = 1
TYPE_VAK = 3
TYPE_LOKAAL = 4
TYPE_STUDENT = 5


def _parse_dt(datum_int, tijd_int):
    """Zet WebUntis-datum (20260908) en -tijd (835 of 1350) om naar datetime."""
    jaar, maand, dag = datum_int // 10000, (datum_int // 100) % 100, datum_int % 100
    uur, minuut = tijd_int // 100, tijd_int % 100
    return datetime.datetime(jaar, maand, dag, uur, minuut)


def _lessen_uit_week(data, element_id):
    """Haal uit één week-antwoord een lijst eenvoudige lessen.

    Elke les is een dict: {vak, long, start, lokaal}.
    """
    kern = data["result"]["data"]

    # id (per type) -> korte en lange naam, voor vakken en lokalen.
    kort, lang = {}, {}
    for el in kern.get("elements", []):
        sleutel = (el["type"], el["id"])
        kort[sleutel] = el.get("name") or el.get("longName") or "?"
        lang[sleutel] = el.get("longName") or el.get("name") or "?"

    lessen = []
    for periode in kern.get("elementPeriods", {}).get(str(element_id), []):
        # Geannuleerde lessen overslaan.
        if periode.get("cellState") == "CANCEL" or periode.get("is", {}).get("cancelled"):
            continue

        vak_id = lokaal_id = None
        for deel in periode.get("elements", []):
            if deel["type"] == TYPE_VAK and vak_id is None:
                vak_id = deel["id"]
            elif deel["type"] == TYPE_LOKAAL and lokaal_id is None:
                lokaal_id = deel["id"]
        if vak_id is None:
            continue

        lessen.append(
            {
                "vak": kort.get((TYPE_VAK, vak_id), "?"),
                "long": lang.get((TYPE_VAK, vak_id), "?"),
                "start": _parse_dt(periode["date"], periode["startTime"]),
                "lokaal": kort.get((TYPE_LOKAAL, lokaal_id), "?") if lokaal_id else "?",
            }
        )
    return lessen


def haal_lessen(server, school, jsessionid, element_type, element_id, start, einde):
    """Haal alle lessen (als eenvoudige dicts) tussen start en einde (datums).

    De REST-API geeft per week terug, dus we lopen week per week.
    """
    basis = f"https://{server}"
    http = requests.Session()
    http.cookies.set("JSESSIONID", jsessionid)
    http.cookies.set("schoolname", "_" + base64.b64encode(school.encode()).decode())

    lessen = []
    maandag = start - datetime.timedelta(days=start.weekday())
    while maandag <= einde:
        antwoord = http.get(
            f"{basis}/WebUntis/api/public/timetable/weekly/data",
            params={
                "elementType": element_type,
                "elementId": element_id,
                "date": maandag.isoformat(),  # yyyy-MM-dd
                "formatId": 1,
            },
            timeout=30,
        )
        antwoord.raise_for_status()
        body = antwoord.json()
        if "data" not in body or "result" not in body.get("data", {}):
            # Toon het exacte antwoord (bv. een rechtenfout) en stop.
            raise RuntimeError(f"Onverwacht REST-antwoord van WebUntis: {body}")
        lessen.extend(_lessen_uit_week(body["data"], element_id))
        maandag += datetime.timedelta(days=7)

    # Enkel lessen binnen het gevraagde venster behouden.
    return [les for les in lessen if start <= les["start"].date() <= einde]
