"""POC 3 - minimale MCP-server die context per gebruiker onthoudt.

Belangrijk: MCP geeft GEEN gebruikers-ID van Claude door aan de server. We
identificeren de gebruiker daarom zelf met een persoonlijke toegangssleutel die
bij de verbinding wordt meegegeven, ofwel:
  - in een Authorization-header:  Authorization: Bearer <sleutel>
  - of als query-parameter in de URL:  http://.../mcp?key=<sleutel>

Opslag: SQLite (zie database.py). Starten: `uv run python server.py`.
"""

import os

from mcp.server.mcpserver import Context, MCPServer

import database

server = MCPServer(
    "trends-ai-context",
    instructions=(
        "Deze server onthoudt feiten per gebruiker (naam, klas, studiejaar, "
        "voorkeuren, ...). Roep aan het BEGIN van een gesprek haal_context_op() aan "
        "om te weten wie de gebruiker is en wat je al over hem weet. Telkens de "
        "gebruiker iets over zichzelf vertelt, roep je onthoud(sleutel, waarde) aan "
        "om dat te bewaren."
    ),
)


def _identificeer(ctx):
    """Zoek de gebruiker op via de toegangssleutel (header of ?key=)."""
    sleutel = None

    # 1. Authorization-header ('Bearer <sleutel>' of de kale sleutel).
    headers = ctx.headers or {}
    autorisatie = headers.get("authorization")
    if autorisatie:
        if autorisatie.lower().startswith("bearer "):
            sleutel = autorisatie[7:].strip()
        else:
            sleutel = autorisatie.strip()

    # 2. Anders de query-parameter ?key=... uit de URL.
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
    finally:
        conn.close()
    if gebruiker is None:
        raise ValueError("Onbekende toegangssleutel. Maak eerst een gebruiker aan.")
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


if __name__ == "__main__":
    # Zorg dat de tabellen bestaan voor we starten.
    conn = database.verbind()
    try:
        database.init_db(conn)
    finally:
        conn.close()

    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8000"))
    print(f"MCP-server luistert op http://{host}:{port}/mcp")
    server.run(transport="streamable-http", host=host, port=port)
