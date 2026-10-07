"""Gecombineerde MCP-server voor "Trends in AI" - stap 1: basis + context.

Deze server onthoudt context per gebruiker. In latere stappen komen er tools bij
voor je WebUntis-rooster (stap 2) en je Digitap-deadlines (stap 3).

Gebruiker identificeren: MCP geeft geen identiteit van Claude door, dus we gebruiken
een persoonlijke toegangssleutel die bij de verbinding meekomt:
  - in een Authorization-header:  Authorization: Bearer <sleutel>
  - of als query-parameter:        http://.../mcp?key=<sleutel>

Starten: `uv run python server.py`  (maak eerst een gebruiker met beheer.py).
"""

import os
from typing import Annotated, Literal

from dotenv import load_dotenv
from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

import config
import database
import digitap
import untis

# Gesloten keuzelijst voor de klas, afgeleid uit de ene bron van waarheid (config.py).
# Door dit als Literal te typeren wordt het in het tool-schema een 'enum': de LLM kan
# enkel een bestaande klas doorgeven en dus geen ongeldige waarde "verzinnen".
KlasKeuze = Literal[tuple(config.KLASSEN.keys())]

# Gesloten keuzelijst voor de status van een deadline (idem: enum in het schema).
StatusKeuze = Literal["nog te doen", "mee bezig", "klaar"]
STANDAARD_STATUS = "nog te doen"

server = MCPServer(
    "trends-ai",
    instructions=(
        "Je bent een persoonlijke schoolassistent. Roep aan het BEGIN van een gesprek "
        "haal_context_op() aan om te weten wie de gebruiker is (naam, klas, studiejaar, "
        "voorkeuren). Telkens de gebruiker iets over zichzelf vertelt, roep je "
        "onthoud(sleutel, waarde) aan om dat te bewaren. Je kunt ook het rooster en de "
        "deadlines van de gebruiker opvragen. Elke deadline heeft een persoonlijke status "
        "('nog te doen', 'mee bezig', 'klaar'); zegt de gebruiker dat hij ergens mee bezig "
        "is of iets af heeft, zet dan de status met markeer_deadline."
    ),
)


def _identificeer(ctx):
    """Zoek de gebruiker op via de toegangssleutel (Authorization-header of ?key=)."""
    sleutel = None

    headers = ctx.headers or {}
    autorisatie = headers.get("authorization")
    if autorisatie:
        if autorisatie.lower().startswith("bearer "):
            sleutel = autorisatie[7:].strip()
        else:
            sleutel = autorisatie.strip()

    if not sleutel:
        request = getattr(ctx.request_context, "request", None)
        query = getattr(request, "query_params", None)
        if query:
            sleutel = query.get("key")

    if not sleutel:
        raise ValueError(
            "Geen toegangssleutel meegegeven (Authorization-header of ?key= in de URL)."
        )

    conn = database.verbind()
    try:
        gebruiker = database.gebruiker_via_sleutel(conn, sleutel)
        if gebruiker is None:
            # Onbekende sleutel? Maak meteen een nieuwe gebruiker aan met deze sleutel.
            # De naam is voorlopig de sleutel zelf; de gebruiker kan 'm later met
            # onthoud('naam', ...) bijstellen.
            database.maak_gebruiker(conn, sleutel, toegangssleutel=sleutel)
            gebruiker = database.gebruiker_via_sleutel(conn, sleutel)
    finally:
        conn.close()
    return gebruiker["id"], gebruiker["naam"]


@server.tool(
    description=(
        "Bewaar EEN feit over de huidige gebruiker, bv. onthoud('klas', '3itai') of "
        "onthoud('naam', 'Aron'). Roep dit aan zodra de gebruiker iets over zichzelf "
        "vertelt (naam, klas, studiejaar, voorkeuren). Een bestaande sleutel wordt "
        "overschreven."
    )
)
def onthoud(sleutel: str, waarde: str, ctx: Context) -> str:
    gebruiker_id, _ = _identificeer(ctx)
    conn = database.verbind()
    try:
        database.onthoud_feit(conn, gebruiker_id, sleutel, waarde)
    finally:
        conn.close()
    return f"Onthouden: {sleutel} = {waarde}"


@server.tool(
    description=(
        "Geef alle bewaarde feiten over de huidige gebruiker terug. Roep dit aan aan "
        "het begin van een gesprek om te weten wie de gebruiker is en wat je al weet."
    )
)
def haal_context_op(ctx: Context) -> dict:
    gebruiker_id, naam = _identificeer(ctx)
    conn = database.verbind()
    try:
        feiten = database.haal_feiten(conn, gebruiker_id)
    finally:
        conn.close()
    return {"naam": naam, "feiten": feiten}


@server.tool(description="Wis alle bewaarde feiten over de huidige gebruiker.")
def wis_geheugen(ctx: Context) -> str:
    gebruiker_id, _ = _identificeer(ctx)
    conn = database.verbind()
    try:
        database.wis_feiten(conn, gebruiker_id)
    finally:
        conn.close()
    return "Geheugen gewist."


@server.tool(
    description=(
        "Begroet de huidige gebruiker. Het antwoord verschilt naargelang wat er al "
        "over de gebruiker bekend is (naam, klas, studiejaar)."
    )
)
def begroet(ctx: Context) -> str:
    gebruiker_id, naam = _identificeer(ctx)
    conn = database.verbind()
    try:
        feiten = database.haal_feiten(conn, gebruiker_id)
    finally:
        conn.close()

    delen = [f"Hallo {naam}!"]
    if "klas" in feiten:
        delen.append(f"Jij zit in klas {feiten['klas']}.")
    if "studiejaar" in feiten:
        delen.append(f"Studiejaar: {feiten['studiejaar']}.")
    if not feiten:
        delen.append("Ik weet nog niets over jou - vertel gerust iets, dan onthoud ik het.")
    return " ".join(delen)


def _onthouden_klas(gebruiker_id):
    """Geef het onthouden feit 'klas' van de gebruiker, of None.

    Zo bepaalt de opgeslagen context welk klasrooster we lezen. Is er geen onthouden
    klas, dan valt de WebUntis-laag terug op UNTIS_KLAS uit .env.
    """
    conn = database.verbind()
    try:
        feiten = database.haal_feiten(conn, gebruiker_id)
    finally:
        conn.close()
    return feiten.get("klas")


def _toon_les(les):
    """Zet één les om naar leesbare velden (datetime -> tekst) voor het antwoord."""
    return {
        "vak": les["vak"],
        "volledige_naam": les["long"],
        "wanneer": les["start"].strftime("%a %d/%m om %H:%M"),
        "lokaal": les["lokaal"],
    }


@server.tool(
    description=(
        "Geef het lesrooster voor de komende `dagen` dagen (1-28, standaard 7): een lijst "
        "lessen met vak, tijdstip en lokaal, gesorteerd op tijd. `klas` is optioneel en "
        "mag enkel een waarde uit de vaste lijst zijn; laat je het leeg, dan gebruiken we "
        "de onthouden klas van de gebruiker (of de standaard uit de serverinstelling). "
        "Gebruik dit als de gebruiker vraagt naar zijn rooster, lessen, of wanneer/waar "
        "een bepaald vak is."
    )
)
def haal_rooster(
    ctx: Context,
    dagen: Annotated[int, Field(ge=1, le=28)] = 7,
    klas: KlasKeuze | None = None,
) -> dict:
    gebruiker_id, _ = _identificeer(ctx)
    gekozen = klas or _onthouden_klas(gebruiker_id)
    lessen = untis.haal_lessen(dagen, klas_naam=gekozen)
    lessen.sort(key=lambda les: les["start"])
    return {
        "klas": gekozen or "(standaard uit .env of persoonlijk rooster)",
        "dagen": dagen,
        "aantal": len(lessen),
        "lessen": [_toon_les(les) for les in lessen],
    }


@server.tool(
    description=(
        "Geef de vakken van de gebruiker, afgeleid uit het rooster van de komende 4 weken, "
        "met per vak het eerstvolgende lesmoment en lokaal. `klas` is optioneel en mag enkel "
        "een waarde uit de vaste lijst zijn; laat je het leeg, dan gebruiken we de onthouden "
        "klas van de gebruiker (of de standaard uit de serverinstelling). Gebruik dit als de "
        "gebruiker vraagt welke vakken hij heeft."
    )
)
def haal_vakken(ctx: Context, klas: KlasKeuze | None = None) -> dict:
    gebruiker_id, _ = _identificeer(ctx)
    gekozen = klas or _onthouden_klas(gebruiker_id)
    lessen = untis.haal_lessen(28, klas_naam=gekozen)  # 4 weken
    vakken = untis.eerstvolgende_per_vak(lessen)
    return {
        "klas": gekozen or "(standaard uit .env of persoonlijk rooster)",
        "aantal": len(vakken),
        "vakken": [
            {
                "vak": naam,
                "volledige_naam": vak["long"],
                "eerstvolgende_les": vak["start"].strftime("%a %d/%m om %H:%M"),
                "lokaal": vak["lokaal"],
            }
            for naam, vak in sorted(vakken.items())
        ],
    }


def _toon_deadline(deadline, status):
    """Zet één deadline om naar leesbare velden (datetime -> tekst) voor het antwoord.

    `uid` geven we mee zodat de gebruiker (via markeer_deadline) een status kan zetten.
    """
    if deadline["heeft_tijd"]:
        wanneer = deadline["wanneer"].strftime("%a %d/%m/%Y om %H:%M")
    else:
        wanneer = deadline["wanneer"].strftime("%a %d/%m/%Y")
    return {
        "uid": deadline["uid"],
        "vak": deadline["vak"],
        "titel": deadline["titel"],
        "vervalt": wanneer,
        "status": status,
    }


@server.tool(
    description=(
        "Geef de komende deadlines van de gebruiker uit zijn Digitap/Moodle-kalender, "
        "gesorteerd op datum (met vak, titel, vervaldatum, status en een uid). Met `vak` "
        "filter je op (een deel van) de vaknaam; met `dagen` (1-365) toon je enkel "
        "deadlines binnen dat aantal dagen. Elke deadline heeft een persoonlijke status "
        "('nog te doen', 'mee bezig' of 'klaar'); wil de gebruiker weten wat nog openstaat, "
        "toon dan de deadlines die niet 'klaar' zijn. Gebruik de meegegeven uid om met "
        "markeer_deadline een status te zetten."
    )
)
def haal_deadlines(
    ctx: Context,
    vak: str | None = None,
    dagen: Annotated[int, Field(ge=1, le=365)] | None = None,
) -> dict:
    gebruiker_id, _ = _identificeer(ctx)
    conn = database.verbind()
    try:
        persoonlijke_url = database.haal_digitap_url(conn, gebruiker_id)
        statussen = database.haal_deadline_statussen(conn, gebruiker_id)
    finally:
        conn.close()
    bron = "persoonlijke kalender" if persoonlijke_url else "gedeelde kalender (.env)"

    komend, enkel_maand = digitap.haal_deadlines(persoonlijke_url, vak=vak, dagen=dagen)
    antwoord = {
        "bron": bron,
        "aantal": len(komend),
        "deadlines": [
            _toon_deadline(d, statussen.get(d["uid"], STANDAARD_STATUS)) for d in komend
        ],
    }
    if enkel_maand:
        antwoord["waarschuwing"] = (
            "De feed lijkt enkel de lopende maand te bevatten. Pas 'preset_time' in de "
            "ICS-URL aan (bv. monthnow -> recentupcoming) als je meer deadlines verwacht."
        )
    return antwoord


@server.tool(
    description=(
        "Zet de persoonlijke status van één deadline. `uid` is de identificatie die je bij "
        "haal_deadlines kreeg; `status` moet 'nog te doen', 'mee bezig' of 'klaar' zijn. "
        "Gebruik dit als de gebruiker zegt dat hij met een deadline bezig is of ze af heeft. "
        "De status blijft bewaard, ook in een nieuw gesprek."
    )
)
def markeer_deadline(ctx: Context, uid: str, status: StatusKeuze) -> str:
    gebruiker_id, _ = _identificeer(ctx)
    conn = database.verbind()
    try:
        database.zet_deadline_status(conn, gebruiker_id, uid, status)
    finally:
        conn.close()
    return f"Status van deadline bijgewerkt naar '{status}'."


if __name__ == "__main__":
    load_dotenv()
    conn = database.verbind()
    try:
        database.init_db(conn)
    finally:
        conn.close()

    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8000"))
    print(f"MCP-server 'trends-ai' luistert op http://{host}:{port}/mcp")
    server.run(transport="streamable-http", host=host, port=port)
