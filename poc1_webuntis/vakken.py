"""POC 1 - toon mijn vakken, afgeleid uit mijn WebUntis-rooster.

Gebruik: `uv run python vakken.py`

Leest de instellingen uit .env, kiest een loginroute (wachtwoord of geheime
sleutel), haalt het rooster van de komende 4 weken op en leidt daaruit de lijst
van vakken af. Per vak tonen we het eerstvolgende lesmoment met lokaal.
"""

import datetime
import os

from dotenv import load_dotenv

import config
import rooster
import untis_login

# Vriendelijke naam die we aan WebUntis meegeven (verplicht door de API).
USERAGENT = "trends-ai-poc1 (schoolopdracht)"


def kies_en_login():
    """Lees .env en log in via de juiste route (secret heeft voorrang)."""
    load_dotenv()
    server = os.getenv("UNTIS_SERVER", "").strip()
    school = os.getenv("UNTIS_SCHOOL", "").strip()
    user = os.getenv("UNTIS_USER", "").strip()
    password = os.getenv("UNTIS_PASSWORD", "").strip()
    secret = os.getenv("UNTIS_SECRET", "").strip()

    ontbreekt = [
        naam
        for naam, waarde in (
            ("UNTIS_SERVER", server),
            ("UNTIS_SCHOOL", school),
            ("UNTIS_USER", user),
        )
        if not waarde
    ]
    if ontbreekt:
        raise SystemExit("Vul eerst .env in. Ontbreekt nog: " + ", ".join(ontbreekt))

    if secret:
        print("Loginroute: geheime sleutel (TOTP)")
        return untis_login.login_met_secret(server, school, user, secret, USERAGENT)
    if password:
        print("Loginroute: gebruikersnaam + wachtwoord")
        return untis_login.login_met_wachtwoord(server, school, user, password, USERAGENT)
    raise SystemExit("Zet in .env ofwel UNTIS_PASSWORD ofwel UNTIS_SECRET.")


def haal_vakken(lessen):
    """Leid uit een lijst lessen (zie rooster.py) de vakken af.

    Geeft een dict terug: vaknaam -> {long, start, lokaal} van het eerstvolgende
    (nog niet voorbije) lesmoment van dat vak.
    """
    nu = datetime.datetime.now()
    vakken = {}
    for les in lessen:
        if les["start"] < nu:  # al voorbij
            continue
        bestaand = vakken.get(les["vak"])
        if bestaand is None or les["start"] < bestaand["start"]:
            vakken[les["vak"]] = {
                "long": les["long"],
                "start": les["start"],
                "lokaal": les["lokaal"],
            }
    return vakken


def bepaal_klasse_id():
    """Zoek het klas-ID op uit config.py op basis van UNTIS_KLAS in .env.

    Geeft None terug als UNTIS_KLAS leeg is (dan gebruiken we het persoonlijke
    rooster). Staat de naam niet in config.py, dan stoppen we met een duidelijke
    melding.
    """
    klas_naam = os.getenv("UNTIS_KLAS", "").strip()
    if not klas_naam:
        return None
    if klas_naam not in config.KLASSEN:
        beschikbaar = ", ".join(sorted(config.KLASSEN))
        raise SystemExit(
            f"Onbekende klas '{klas_naam}'. Voeg ze toe aan config.py of kies uit: "
            + beschikbaar
        )
    return config.KLASSEN[klas_naam]


def main():
    load_dotenv()
    session = None
    try:
        klasse_id = bepaal_klasse_id()
        session = kies_en_login()

        # Server en school opnieuw uit .env (voor de REST-call).
        server = untis_login._host(os.getenv("UNTIS_SERVER", ""))
        school = os.getenv("UNTIS_SCHOOL", "").strip()
        jsessionid = session.config["jsessionid"]

        # Welk element vragen we op: een klas, of (zonder klas) de student zelf.
        if klasse_id is not None:
            element_type, element_id = rooster.TYPE_KLAS, klasse_id
        else:
            element_type = rooster.TYPE_STUDENT
            element_id = session.login_result["personId"]

        vandaag = datetime.date.today()
        einde = vandaag + datetime.timedelta(weeks=4)
        lessen = rooster.haal_lessen(
            server, school, jsessionid, element_type, element_id, vandaag, einde
        )
        vakken = haal_vakken(lessen)
    except Exception as fout:
        # Toon de exacte foutmelding en stop (we verzinnen geen nepdata).
        print(f"FOUT: {fout}")
        raise SystemExit(1)
    finally:
        if session is not None:
            session.logout(suppress_errors=True)

    if not vakken:
        print("Geen vakken gevonden in de komende 4 weken.")
        return

    print(f"\nJouw vakken (komende 4 weken) - {len(vakken)} gevonden:\n")
    for naam in sorted(vakken):
        vak = vakken[naam]
        wanneer = vak["start"].strftime("%a %d/%m om %H:%M")
        print(f"- {naam} ({vak['long']})")
        print(f"    eerstvolgende les: {wanneer} in lokaal {vak['lokaal']}")


if __name__ == "__main__":
    main()
