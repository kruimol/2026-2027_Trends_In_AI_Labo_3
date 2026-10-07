"""SQLite-opslag voor de gecombineerde MCP-server.

Twee tabellen:
- gebruikers: koppelt een persoonlijke toegangssleutel aan een gebruiker (naam),
  en bewaart diens eigen Digitap ICS-URL (per gebruiker);
- feiten:     sleutel/waarde-feiten per gebruiker (de context, bv. 'klas'->'3itai').

WebUntis is een GEDEELDE login en staat niet hier maar in .env. De Digitap-URL is
WEL persoonlijk en staat daarom op het gebruikersrecord.

We openen een nieuwe verbinding per bewerking: simpel en veilig omdat de MCP-server
tools in werk-threads uitvoert (SQLite-verbindingen zijn niet thread-overschrijdend).
"""

import os
import secrets
import sqlite3
from pathlib import Path


def _standaard_db():
    """Pad naar de databank; overschrijfbaar via MCP_DB_PATH (handig voor de demo)."""
    uit_env = os.environ.get("MCP_DB_PATH")
    return Path(uit_env) if uit_env else Path(__file__).with_name("trends_ai.sqlite")


def verbind(db_pad=None):
    conn = sqlite3.connect(db_pad or _standaard_db())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS gebruikers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            toegangssleutel TEXT NOT NULL UNIQUE,
            naam TEXT NOT NULL,
            digitap_ics_url TEXT
        );
        CREATE TABLE IF NOT EXISTS feiten (
            gebruiker_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
            sleutel TEXT NOT NULL,
            waarde TEXT NOT NULL,
            PRIMARY KEY (gebruiker_id, sleutel)
        );
        """
    )
    conn.commit()


def maak_gebruiker(conn, naam, toegangssleutel=None, digitap_ics_url=None):
    """Maak een gebruiker aan; genereert een sleutel als je er geen opgeeft."""
    if toegangssleutel is None:
        toegangssleutel = secrets.token_urlsafe(24)
    conn.execute(
        "INSERT INTO gebruikers (toegangssleutel, naam, digitap_ics_url) VALUES (?, ?, ?)",
        (toegangssleutel, naam, digitap_ics_url),
    )
    conn.commit()
    return toegangssleutel


def gebruiker_via_sleutel(conn, toegangssleutel):
    """Geef de rij (id, naam, digitap_ics_url) voor deze sleutel, of None."""
    return conn.execute(
        "SELECT id, naam, digitap_ics_url FROM gebruikers WHERE toegangssleutel = ?",
        (toegangssleutel,),
    ).fetchone()


def zet_digitap_url(conn, gebruiker_id, url):
    """Stel de persoonlijke Digitap ICS-URL van een gebruiker in (of actualiseer ze)."""
    conn.execute(
        "UPDATE gebruikers SET digitap_ics_url = ? WHERE id = ?",
        (url, gebruiker_id),
    )
    conn.commit()


def haal_digitap_url(conn, gebruiker_id):
    rij = conn.execute(
        "SELECT digitap_ics_url FROM gebruikers WHERE id = ?", (gebruiker_id,)
    ).fetchone()
    return rij["digitap_ics_url"] if rij else None


def onthoud_feit(conn, gebruiker_id, sleutel, waarde):
    """Bewaar of overschrijf één feit."""
    conn.execute(
        """
        INSERT INTO feiten (gebruiker_id, sleutel, waarde) VALUES (?, ?, ?)
        ON CONFLICT(gebruiker_id, sleutel) DO UPDATE SET waarde = excluded.waarde
        """,
        (gebruiker_id, sleutel, waarde),
    )
    conn.commit()


def haal_feiten(conn, gebruiker_id):
    """Geef alle feiten van een gebruiker als dict {sleutel: waarde}."""
    rijen = conn.execute(
        "SELECT sleutel, waarde FROM feiten WHERE gebruiker_id = ? ORDER BY sleutel",
        (gebruiker_id,),
    ).fetchall()
    return {rij["sleutel"]: rij["waarde"] for rij in rijen}


def wis_feiten(conn, gebruiker_id):
    conn.execute("DELETE FROM feiten WHERE gebruiker_id = ?", (gebruiker_id,))
    conn.commit()
