"""Admin-CLI om gebruikers te beheren (de "registratie").

Dit draai je lokaal, los van Claude. Secrets (sleutel, Digitap-URL) blijven zo uit
de MCP-tools en dus uit het zicht van Claude.

Voorbeelden:
    uv run python beheer.py nieuw "Aron"
    uv run python beheer.py nieuw "Aron" --digitap-url "https://learning.ap.be/calendar/export_execute.php?..."
    uv run python beheer.py digitap <sleutel> "https://learning.ap.be/calendar/export_execute.php?..."
"""

import argparse

import database


def _nieuw(args):
    conn = database.verbind()
    try:
        database.init_db(conn)
        sleutel = database.maak_gebruiker(conn, args.naam, digitap_ics_url=args.digitap_url)
    finally:
        conn.close()
    print(f"Gebruiker '{args.naam}' aangemaakt.")
    print(f"Toegangssleutel: {sleutel}")
    if args.digitap_url:
        print("Digitap-URL opgeslagen.")
    print("Geef de sleutel mee als '?key=<sleutel>' in de URL, of als header "
          "'Authorization: Bearer <sleutel>'.")


def _digitap(args):
    conn = database.verbind()
    try:
        database.init_db(conn)
        gebruiker = database.gebruiker_via_sleutel(conn, args.sleutel)
        if gebruiker is None:
            raise SystemExit("Onbekende sleutel.")
        database.zet_digitap_url(conn, gebruiker["id"], args.url)
    finally:
        conn.close()
    print(f"Digitap-URL ingesteld voor gebruiker '{gebruiker['naam']}'.")


def main():
    parser = argparse.ArgumentParser(description="Beheer gebruikers van de MCP-server.")
    sub = parser.add_subparsers(dest="commando", required=True)

    p_nieuw = sub.add_parser("nieuw", help="Maak een nieuwe gebruiker aan.")
    p_nieuw.add_argument("naam", help="Naam van de gebruiker.")
    p_nieuw.add_argument("--digitap-url", help="Persoonlijke Digitap ICS-URL (optioneel).")
    p_nieuw.set_defaults(func=_nieuw)

    p_digitap = sub.add_parser("digitap", help="Stel de Digitap-URL van een gebruiker in.")
    p_digitap.add_argument("sleutel", help="De toegangssleutel van de gebruiker.")
    p_digitap.add_argument("url", help="De Digitap ICS-URL.")
    p_digitap.set_defaults(func=_digitap)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
