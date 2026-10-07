"""Offline tests (geen netwerk/server/login nodig).

Bewijst dat:
- de per-gebruiker Digitap-URL opgeslagen en gelezen wordt;
- feiten van twee gebruikers strikt gescheiden blijven;
- de WebUntis REST-parser een weekantwoord correct verwerkt en per vak het
  eerstvolgende lesmoment afleidt.

Draaien: `uv run python test_server.py`
"""

import datetime
import tempfile
from pathlib import Path

import database
import rooster
import untis


def _verse_db():
    pad = Path(tempfile.mkdtemp()) / "test.sqlite"
    conn = database.verbind(pad)
    database.init_db(conn)
    return conn


def test_digitap_url_per_gebruiker():
    conn = _verse_db()
    try:
        sleutel = database.maak_gebruiker(conn, "Aron", digitap_ics_url="https://x/ics?token=a")
        gebruiker = database.gebruiker_via_sleutel(conn, sleutel)
        assert gebruiker["digitap_ics_url"] == "https://x/ics?token=a"
        # Actualiseren werkt ook.
        database.zet_digitap_url(conn, gebruiker["id"], "https://x/ics?token=b")
        assert database.haal_digitap_url(conn, gebruiker["id"]) == "https://x/ics?token=b"
    finally:
        conn.close()
    print("OK: Digitap-URL wordt per gebruiker bewaard en geactualiseerd.")


def test_feiten_gescheiden_per_gebruiker():
    conn = _verse_db()
    try:
        s_aron = database.maak_gebruiker(conn, "Aron")
        s_lotte = database.maak_gebruiker(conn, "Lotte")
        aron = database.gebruiker_via_sleutel(conn, s_aron)
        lotte = database.gebruiker_via_sleutel(conn, s_lotte)

        database.onthoud_feit(conn, aron["id"], "klas", "3itai")
        database.onthoud_feit(conn, lotte["id"], "klas", "1itVTAI")

        assert database.haal_feiten(conn, aron["id"]) == {"klas": "3itai"}
        assert database.haal_feiten(conn, lotte["id"]) == {"klas": "1itVTAI"}

        # Wissen bij de een laat de ander ongemoeid.
        database.wis_feiten(conn, aron["id"])
        assert database.haal_feiten(conn, aron["id"]) == {}
        assert database.haal_feiten(conn, lotte["id"]) == {"klas": "1itVTAI"}
    finally:
        conn.close()
    print("OK: feiten blijven gescheiden per gebruiker.")


# --- WebUntis: mini REST-antwoord met twee vakken, één ervan geannuleerd. ---
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
    vakken = untis.eerstvolgende_per_vak(lessen)

    assert set(vakken) == {"WIS"}, vakken  # NED is voorbij
    assert vakken["WIS"]["lokaal"] == "A102"  # de vroegste les
    assert vakken["WIS"]["long"] == "Wiskunde"
    print("OK: eerstvolgende les per vak correct afgeleid.")


if __name__ == "__main__":
    test_digitap_url_per_gebruiker()
    test_feiten_gescheiden_per_gebruiker()
    test_rest_parser()
    test_eerstvolgende_les_per_vak()
    print("\nAlle tests geslaagd.")
