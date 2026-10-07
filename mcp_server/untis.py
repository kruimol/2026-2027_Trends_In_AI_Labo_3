"""WebUntis-laag voor de MCP-server: inloggen, rooster ophalen, vakken afleiden.

Deze module bindt de bewezen POC 1-code (untis_login.py + rooster.py) samen tot een
paar functies die de MCP-tools in server.py aanroepen. De WebUntis-login is GEDEELD
en komt uit .env; welke klas we lezen hangt af van de gebruiker (zie kies_klas_id).

De login is relatief traag en gebeurt per tool-call opnieuw (eenvoudig en veilig);
we loggen telkens netjes weer uit.
"""

import datetime
import os

import config
import rooster
import untis_login

# Vriendelijke naam die we aan WebUntis meegeven (verplicht door de API).
USERAGENT = "trends-ai-server (schoolopdracht)"


def _instellingen():
    """Lees de gedeelde WebUntis-instellingen uit .env en controleer de verplichte."""
    inst = {
        "server": os.getenv("UNTIS_SERVER", "").strip(),
        "school": os.getenv("UNTIS_SCHOOL", "").strip(),
        "user": os.getenv("UNTIS_USER", "").strip(),
        "password": os.getenv("UNTIS_PASSWORD", "").strip(),
        "secret": os.getenv("UNTIS_SECRET", "").strip(),
        "klas_env": os.getenv("UNTIS_KLAS", "").strip(),
    }
    ontbreekt = [n for n in ("server", "school", "user") if not inst[n]]
    if ontbreekt:
        velden = ", ".join("UNTIS_" + n.upper() for n in ontbreekt)
        raise RuntimeError(f"WebUntis is niet ingesteld in .env (ontbreekt: {velden}).")
    if not inst["secret"] and not inst["password"]:
        raise RuntimeError("Zet in .env ofwel UNTIS_PASSWORD ofwel UNTIS_SECRET.")
    return inst


def _login(inst):
    """Kies de loginroute (secret heeft voorrang) en geef een ingelogde sessie terug."""
    if inst["secret"]:
        return untis_login.login_met_secret(
            inst["server"], inst["school"], inst["user"], inst["secret"], USERAGENT
        )
    return untis_login.login_met_wachtwoord(
        inst["server"], inst["school"], inst["user"], inst["password"], USERAGENT
    )


def kies_klas_id(klas_naam):
    """Zoek het klas-ID op uit config.py op basis van een klasnaam.

    Geeft None terug als er geen klasnaam is (dan proberen we het persoonlijke
    studentenrooster). Staat de naam niet in config.py, dan stoppen we met een
    duidelijke melding.
    """
    if not klas_naam:
        return None
    if klas_naam not in config.KLASSEN:
        beschikbaar = ", ".join(sorted(config.KLASSEN))
        raise RuntimeError(
            f"Onbekende klas '{klas_naam}'. Voeg ze toe aan config.py of kies uit: "
            + beschikbaar
        )
    return config.KLASSEN[klas_naam]


def haal_lessen(dagen, klas_naam=None):
    """Haal de lessen van vandaag tot over `dagen` dagen.

    `klas_naam` komt meestal uit het onthouden feit 'klas' van de gebruiker; is die
    er niet, dan gebruiken we UNTIS_KLAS uit .env; is ook die leeg, dan proberen we
    het persoonlijke studentenrooster.
    """
    inst = _instellingen()
    gekozen_klas = klas_naam or inst["klas_env"]
    klas_id = kies_klas_id(gekozen_klas)

    session = _login(inst)
    try:
        if klas_id is not None:
            element_type, element_id = rooster.TYPE_KLAS, klas_id
        else:
            element_type = rooster.TYPE_STUDENT
            element_id = session.login_result["personId"]

        host = untis_login.host(inst["server"])
        jsessionid = session.config["jsessionid"]
        vandaag = datetime.date.today()
        einde = vandaag + datetime.timedelta(days=dagen)
        return rooster.haal_lessen(
            host, inst["school"], jsessionid, element_type, element_id, vandaag, einde
        )
    finally:
        session.logout(suppress_errors=True)


def eerstvolgende_per_vak(lessen):
    """Leid uit een lijst lessen per vak het eerstvolgende (nog niet voorbije) moment af.

    Geeft een dict terug: vaknaam -> {long, start, lokaal}.
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
