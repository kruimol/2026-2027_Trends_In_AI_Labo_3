"""Maak een nieuwe gebruiker aan met een persoonlijke toegangssleutel.

Gebruik:
    uv run python maak_gebruiker.py "Aron"

Print de sleutel die je in je MCP-client (Claude Code / MCP Inspector) meegeeft,
ofwel als '?key=<sleutel>' in de URL, ofwel als 'Authorization: Bearer <sleutel>'.
"""

import sys

import database


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        raise SystemExit('Gebruik: uv run python maak_gebruiker.py "<naam>"')
    naam = sys.argv[1].strip()

    conn = database.verbind()
    try:
        database.init_db(conn)
        sleutel = database.maak_gebruiker(conn, naam)
    finally:
        conn.close()

    print(f"Gebruiker '{naam}' aangemaakt.")
    print(f"Toegangssleutel: {sleutel}")
    print("Geef die mee als '?key=<sleutel>' in de URL, of als header "
          "'Authorization: Bearer <sleutel>'.")


if __name__ == "__main__":
    main()
