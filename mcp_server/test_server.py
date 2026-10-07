"""Offline tests voor de databanklaag (geen netwerk/server nodig).

Bewijst dat:
- de per-gebruiker Digitap-URL opgeslagen en gelezen wordt;
- feiten van twee gebruikers strikt gescheiden blijven.

Draaien: `uv run python test_server.py`
"""

import tempfile
from pathlib import Path

import database


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


if __name__ == "__main__":
    test_digitap_url_per_gebruiker()
    test_feiten_gescheiden_per_gebruiker()
    print("\nAlle tests geslaagd.")
