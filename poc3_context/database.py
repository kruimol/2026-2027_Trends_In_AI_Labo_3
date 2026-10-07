"""SQLite-opslag voor de context per gebruiker.

Twee tabellen:
- gebruikers: koppelt een persoonlijke toegangssleutel aan een gebruiker (naam);
- feiten:     sleutel/waarde-feiten per gebruiker (bv. 'klas' -> '3itai').

We openen een nieuwe verbinding per bewerking. Dat is simpel en vermijdt
problemen met SQLite-verbindingen die over threads gedeeld worden (de MCP-server
voert tools in werk-threads uit).
"""

import os
import secrets
import sqlite3
from pathlib import Path


def _standaard_db():
    """Pad naar de databank; overschrijfbaar via MCP_DB_PATH (handig voor de demo)."""
    uit_env = os.environ.get("MCP_DB_PATH")
    return Path(uit_env) if uit_env else Path(__file__).with_name("context.sqlite")


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
            naam TEXT NOT NULL
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


def maak_gebruiker(conn, naam, toegangssleutel=None):
    """Maak een gebruiker aan; genereert een sleutel als je er geen opgeeft."""
    if toegangssleutel is None:
        toegangssleutel = secrets.token_urlsafe(24)
    conn.execute(
        "INSERT INTO gebruikers (toegangssleutel, naam) VALUES (?, ?)",
        (toegangssleutel, naam),
    )
    conn.commit()
    return toegangssleutel


def gebruiker_via_sleutel(conn, toegangssleutel):
    """Geef de rij (id, naam) voor deze sleutel, of None."""
    return conn.execute(
        "SELECT id, naam FROM gebruikers WHERE toegangssleutel = ?",
        (toegangssleutel,),
    ).fetchone()


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
