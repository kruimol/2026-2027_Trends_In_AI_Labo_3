"""Offline tests voor het parsen en filteren van de ICS-kalender.

Gebruikt het voorbeeldbestand voorbeeld.ics, dus geen netwerk nodig.
We prikken een vaste "vanaf"-datum (7 okt 2026) zodat de tests stabiel zijn.

Draaien: `uv run python test_deadlines.py`
"""

import datetime
from zoneinfo import ZoneInfo

import ics_parser

BRUSSEL = ZoneInfo("Europe/Brussels")
VANAF = datetime.datetime(2026, 10, 7, 9, 0, tzinfo=BRUSSEL)


def _laad():
    with open("voorbeeld.ics", "rb") as bestand:
        return ics_parser.parse_deadlines(bestand.read())


def test_parsen_en_sorteren():
    deadlines = _laad()
    assert len(deadlines) == 4, deadlines
    # Gesorteerd op datum: 01/10, 15/10, 20/10, 05/11.
    titels = [d["titel"] for d in deadlines]
    assert titels[0].startswith("Oud labo")
    assert titels[-1].startswith("Paper AI and Society")
    # Vak komt uit CATEGORIES.
    assert deadlines[1]["vak"] == "Trends in AI"
    # 13:00 UTC wordt 15:00 Brusselse tijd (zomertijd in oktober).
    assert deadlines[1]["wanneer"].hour == 15
    assert deadlines[1]["heeft_tijd"] is True
    # All-day event (VALUE=DATE) heeft geen tijd.
    robot = next(d for d in deadlines if d["vak"] == "Robotics")
    assert robot["heeft_tijd"] is False
    print("OK: parsen, sorteren, vak uit CATEGORIES en tijdzone kloppen.")


def test_filter_toekomst():
    deadlines = _laad()
    komend = ics_parser.filter_deadlines(deadlines, vanaf=VANAF)
    # Het oude labo (01/10) valt weg.
    assert len(komend) == 3, komend
    assert all(d["wanneer"] >= VANAF for d in komend)
    print("OK: voorbije deadlines worden weggefilterd.")


def test_filter_op_vak():
    deadlines = _laad()
    komend = ics_parser.filter_deadlines(deadlines, vanaf=VANAF, vak="trends")
    # Enkel de komende Trends-in-AI-deadline (het oude labo is voorbij).
    assert len(komend) == 1, komend
    assert komend[0]["titel"].startswith("Labo 3")
    print("OK: filteren op vak werkt (hoofdletterongevoelig).")


def test_filter_op_dagen():
    deadlines = _laad()
    komend = ics_parser.filter_deadlines(deadlines, vanaf=VANAF, dagen=14)
    # Binnen 14 dagen na 07/10: 15/10 en 20/10 wel, 05/11 niet.
    titels = {d["titel"].split(" inleveren")[0] for d in komend}
    assert len(komend) == 2, komend
    assert "Paper AI and Society" not in " ".join(d["titel"] for d in komend)
    print("OK: venster van N dagen werkt.")


def test_waarschuwing_lopende_maand():
    deadlines = _laad()
    # Met een november-deadline erbij: geen waarschuwing.
    assert ics_parser.enkel_lopende_maand(deadlines, vandaag=VANAF) is False
    # Alleen oktober-deadlines: wel waarschuwing.
    enkel_oktober = [d for d in deadlines if d["wanneer"].month == 10]
    assert ics_parser.enkel_lopende_maand(enkel_oktober, vandaag=VANAF) is True
    print("OK: waarschuwing 'enkel lopende maand' klopt.")


if __name__ == "__main__":
    test_parsen_en_sorteren()
    test_filter_toekomst()
    test_filter_op_vak()
    test_filter_op_dagen()
    test_waarschuwing_lopende_maand()
    print("\nAlle tests geslaagd.")
