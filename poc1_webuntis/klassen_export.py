"""Hulpscript: exporteer alle klassen met hun ID's naar klassen.json.

Handig om te controleren welk klas-ID je in config.py moet zetten.

Gebruik: `uv run python klassen_export.py`
Logt in met dezelfde route als vakken.py (zie .env) en schrijft de lijst weg.
"""

import json

import vakken  # hergebruik de loginroute uit vakken.py


def main():
    session = None
    try:
        session = vakken.kies_en_login()
        # getKlassen via de library; kan net als het rooster een rechtenfout geven.
        klassen = session.klassen()
        lijst = [
            {
                "id": k._data.get("id"),
                "name": k._data.get("name"),
                "long_name": k._data.get("longName"),
            }
            for k in klassen
        ]
    except Exception as fout:
        # Toon de exacte foutmelding en stop (geen nepdata).
        print(f"FOUT: {fout}")
        raise SystemExit(1)
    finally:
        if session is not None:
            session.logout(suppress_errors=True)

    with open("klassen.json", "w", encoding="utf-8") as bestand:
        json.dump(lijst, bestand, ensure_ascii=False, indent=2)

    print(f"{len(lijst)} klassen weggeschreven naar klassen.json")
    # Toon ook even de eerste paar in de terminal.
    for klas in lijst[:10]:
        print(f"  {klas['id']}: {klas['name']} ({klas['long_name']})")
    if len(lijst) > 10:
        print(f"  ... en nog {len(lijst) - 10} andere (zie klassen.json)")


if __name__ == "__main__":
    main()
