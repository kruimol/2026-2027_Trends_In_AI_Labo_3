"""Offline tests (geen netwerk/server/login nodig).

Bewijst dat:
- de per-gebruiker Digitap-URL opgeslagen en gelezen wordt;
- feiten van twee gebruikers strikt gescheiden blijven;
- de WebUntis REST-parser een weekantwoord correct verwerkt en per vak het
  eerstvolgende lesmoment afleidt;
- de Digitap/Moodle ICS-parser deadlines correct leest en filtert (met voorbeeld.ics).

Draaien: `uv run python test_server.py`
"""

import datetime
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

import database
import ics_parser
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


# --- Digitap/Moodle: parsen en filteren van de ICS-kalender (voorbeeld.ics). ---
BRUSSEL = ZoneInfo("Europe/Brussels")
VANAF = datetime.datetime(2026, 10, 7, 9, 0, tzinfo=BRUSSEL)


def _laad_deadlines():
    pad = Path(__file__).with_name("voorbeeld.ics")
    return ics_parser.parse_deadlines(pad.read_bytes())


def test_ics_parsen_en_tijdzone():
    deadlines = _laad_deadlines()
    assert len(deadlines) == 4, deadlines
    # Gesorteerd op datum; vak komt uit CATEGORIES.
    assert deadlines[1]["vak"] == "Trends in AI"
    # 13:00 UTC wordt 15:00 Brusselse tijd (zomertijd in oktober).
    assert deadlines[1]["wanneer"].hour == 15 and deadlines[1]["heeft_tijd"] is True
    # All-day event (VALUE=DATE) heeft geen tijd.
    robot = next(d for d in deadlines if d["vak"] == "Robotics")
    assert robot["heeft_tijd"] is False
    print("OK: ICS geparset (vak uit CATEGORIES, tijdzone, all-day).")


def test_ics_filteren():
    deadlines = _laad_deadlines()
    # Voorbije deadline (01/10) valt weg t.o.v. de vaste 'vanaf'-datum.
    assert len(ics_parser.filter_deadlines(deadlines, vanaf=VANAF)) == 3
    # Filter op vak (hoofdletterongevoelig).
    trends = ics_parser.filter_deadlines(deadlines, vanaf=VANAF, vak="trends")
    assert len(trends) == 1 and trends[0]["titel"].startswith("Labo 3")
    # Venster van 14 dagen: 15/10 en 20/10 wel, 05/11 niet.
    assert len(ics_parser.filter_deadlines(deadlines, vanaf=VANAF, dagen=14)) == 2
    print("OK: filteren op toekomst, vak en venster werkt.")


if __name__ == "__main__":
    test_digitap_url_per_gebruiker()
    test_feiten_gescheiden_per_gebruiker()
    test_rest_parser()
    test_eerstvolgende_les_per_vak()
    test_ics_parsen_en_tijdzone()
    test_ics_filteren()
    print("\nAlle tests geslaagd.")
