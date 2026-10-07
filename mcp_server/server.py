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

from dotenv import load_dotenv
from mcp.server.mcpserver import Context, MCPServer

import database
import untis

server = MCPServer(
    "trends-ai",
    instructions=(
        "Je bent een persoonlijke schoolassistent. Roep aan het BEGIN van een gesprek "
        "haal_context_op() aan om te weten wie de gebruiker is (naam, klas, studiejaar, "
        "voorkeuren). Telkens de gebruiker iets over zichzelf vertelt, roep je "
        "onthoud(sleutel, waarde) aan om dat te bewaren. Later kun je ook het rooster "
        "en de deadlines van de gebruiker opvragen."
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
        "Geef het lesrooster van de gebruiker voor de komende `dagen` dagen (standaard 7): "
        "een lijst lessen met vak, tijdstip en lokaal, gesorteerd op tijd. Welke klas we "
        "lezen volgt uit het onthouden feit 'klas' van de gebruiker (anders de standaard "
        "uit de serverinstelling). Gebruik dit als de gebruiker vraagt naar zijn rooster, "
        "lessen, of wanneer/waar een bepaald vak is."
    )
)
def haal_rooster(ctx: Context, dagen: int = 7) -> dict:
    gebruiker_id, _ = _identificeer(ctx)
    klas = _onthouden_klas(gebruiker_id)
    lessen = untis.haal_lessen(dagen, klas_naam=klas)
    lessen.sort(key=lambda les: les["start"])
    return {
        "klas": klas or "(standaard uit .env of persoonlijk rooster)",
        "dagen": dagen,
        "aantal": len(lessen),
        "lessen": [_toon_les(les) for les in lessen],
    }


@server.tool(
    description=(
        "Geef de vakken van de gebruiker, afgeleid uit het rooster van de komende 4 weken, "
        "met per vak het eerstvolgende lesmoment en lokaal. Welke klas we lezen volgt uit "
        "het onthouden feit 'klas' (anders de standaard uit de serverinstelling). Gebruik "
        "dit als de gebruiker vraagt welke vakken hij heeft."
    )
)
def haal_vakken(ctx: Context) -> dict:
    gebruiker_id, _ = _identificeer(ctx)
    klas = _onthouden_klas(gebruiker_id)
    lessen = untis.haal_lessen(28, klas_naam=klas)  # 4 weken
    vakken = untis.eerstvolgende_per_vak(lessen)
    return {
        "klas": klas or "(standaard uit .env of persoonlijk rooster)",
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
