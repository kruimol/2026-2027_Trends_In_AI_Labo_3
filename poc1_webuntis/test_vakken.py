"""Offline tests (geen netwerk/login nodig).

Twee dingen worden bewezen:
1. rooster._lessen_uit_week() parset een REST-antwoord correct (met een fixture
   die de vorm van /WebUntis/api/public/timetable/weekly/data nabootst);
2. vakken.haal_vakken() leidt per vak het eerstvolgende lesmoment correct af.

Draaien: `uv run python test_vakken.py`
"""

import datetime

import rooster
import vakken

# --- Fixture: een mini REST-antwoord met twee vakken, één ervan geannuleerd. ---
NEP_REST = {
    "result": {
        "data": {
            "elements": [
                {"type": 1, "id": 10247, "name": "3itai", "longName": "3 ITAI"},
                {"type": 3, "id": 501, "name": "WIS", "longName": "Wiskunde"},
                {"type": 3, "id": 502, "name": "GES", "longName": "Geschiedenis"},
                {"type": 4, "id": 900, "name": "A102", "longName": "Lokaal A102"},
            ],
            "elementPeriods": {
                "10247": [
                    {
                        "id": 1,
                        "date": 20261012,
                        "startTime": 835,
                        "endTime": 925,
                        "cellState": "STANDARD",
                        "elements": [
                            {"type": 1, "id": 10247},
                            {"type": 3, "id": 501},
                            {"type": 4, "id": 900},
                        ],
                    },
                    {
                        "id": 2,
                        "date": 20261012,
                        "startTime": 1030,
                        "endTime": 1120,
                        "cellState": "CANCEL",  # geannuleerd -> moet wegvallen
                        "elements": [{"type": 3, "id": 502}],
                    },
                ]
            },
        }
    }
}


def test_rest_parser():
    lessen = rooster._lessen_uit_week(NEP_REST, 10247)
    assert len(lessen) == 1, lessen  # de geannuleerde les is weg
    les = lessen[0]
    assert les["vak"] == "WIS"
    assert les["long"] == "Wiskunde"
    assert les["lokaal"] == "A102"
    assert les["start"] == datetime.datetime(2026, 10, 12, 8, 35)
    print("OK: REST-antwoord correct geparset (geannuleerde les genegeerd).")


def test_eerstvolgende_les_per_vak():
    morgen = datetime.datetime.now() + datetime.timedelta(days=1)
    overmorgen = morgen + datetime.timedelta(days=1)
    gisteren = datetime.datetime.now() - datetime.timedelta(days=1)

    lessen = [
        {"vak": "WIS", "long": "Wiskunde", "start": overmorgen, "lokaal": "A101"},
        {"vak": "WIS", "long": "Wiskunde", "start": morgen, "lokaal": "A102"},
        {"vak": "NED", "long": "Nederlands", "start": gisteren, "lokaal": "C301"},
    ]
    vakken_dict = vakken.haal_vakken(lessen)

    assert set(vakken_dict) == {"WIS"}, vakken_dict  # NED is voorbij
    assert vakken_dict["WIS"]["lokaal"] == "A102"  # de vroegste les
    assert vakken_dict["WIS"]["long"] == "Wiskunde"
    print("OK: eerstvolgende les per vak correct afgeleid.")


if __name__ == "__main__":
    test_rest_parser()
    test_eerstvolgende_les_per_vak()
