"""Demo: bewijst dat elke gebruiker enkel zijn eigen context ziet.

Het script:
  1. gebruikt een tijdelijke databank (de echte blijft ongemoeid);
  2. maakt twee gebruikers aan met elk een eigen sleutel;
  3. start de MCP-server als apart proces;
  4. roept de server aan met sleutel A en met sleutel B, slaat per gebruiker iets
     anders op, en controleert dat A de feiten van B niet ziet (en omgekeerd).

Draaien: `uv run python demo.py`
"""

import contextlib
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

import database

POORT = 8765
BASIS_URL = f"http://127.0.0.1:{POORT}/mcp"


def _wacht_op_poort(poort, timeout=15):
    """Wacht tot de server luistert op de poort."""
    einde = time.time() + timeout
    while time.time() < einde:
        with contextlib.suppress(OSError):
            with socket.create_connection(("127.0.0.1", poort), timeout=0.5):
                return True
        time.sleep(0.2)
    return False


async def _roep_tool(sleutel, naam, argumenten=None):
    """Verbind met de server (sleutel in de URL) en roep één tool aan."""
    url = f"{BASIS_URL}?key={sleutel}"
    async with streamable_http_client(url) as (lees, schrijf):
        async with ClientSession(lees, schrijf) as sessie:
            await sessie.initialize()
            return await sessie.call_tool(naam, argumenten or {})


def _tekst(resultaat):
    """Maak van een tool-resultaat een leesbare string (voor controle/print)."""
    stukken = []
    for blok in resultaat.content:
        tekst = getattr(blok, "text", None)
        if tekst:
            stukken.append(tekst)
    gestructureerd = getattr(resultaat, "structuredContent", None)
    if gestructureerd is not None:
        stukken.append(str(gestructureerd))
    return " ".join(stukken)


async def _demo(sleutel_aron, sleutel_lotte):
    # Elke gebruiker slaat iets anders op.
    await _roep_tool(sleutel_aron, "onthoud", {"sleutel": "klas", "waarde": "3itai"})
    await _roep_tool(sleutel_lotte, "onthoud", {"sleutel": "klas", "waarde": "1itVTAI"})

    context_aron = _tekst(await _roep_tool(sleutel_aron, "haal_context_op"))
    context_lotte = _tekst(await _roep_tool(sleutel_lotte, "haal_context_op"))
    begroeting_aron = _tekst(await _roep_tool(sleutel_aron, "begroet"))
    begroeting_lotte = _tekst(await _roep_tool(sleutel_lotte, "begroet"))

    print("Context van Aron :", context_aron)
    print("Context van Lotte:", context_lotte)
    print("Begroeting Aron  :", begroeting_aron)
    print("Begroeting Lotte :", begroeting_lotte)

    # Isolatie: elk ziet enkel de eigen klas.
    assert "3itai" in context_aron and "1itVTAI" not in context_aron, context_aron
    assert "1itVTAI" in context_lotte and "3itai" not in context_lotte, context_lotte
    # De begroeting verschilt naargelang de opgeslagen context.
    assert "Aron" in begroeting_aron and "3itai" in begroeting_aron
    assert "Lotte" in begroeting_lotte and "1itVTAI" in begroeting_lotte
    print("\nOK: elke gebruiker ziet enkel zijn eigen context.")


def main():
    # 1. Tijdelijke databank + twee gebruikers.
    tijdelijke_db = Path(tempfile.mkdtemp()) / "demo.sqlite"
    conn = database.verbind(tijdelijke_db)
    try:
        database.init_db(conn)
        sleutel_aron = database.maak_gebruiker(conn, "Aron")
        sleutel_lotte = database.maak_gebruiker(conn, "Lotte")
    finally:
        conn.close()

    # 2. Server starten als apart proces, met dezelfde tijdelijke databank.
    omgeving = dict(os.environ, MCP_DB_PATH=str(tijdelijke_db), MCP_PORT=str(POORT))
    server = subprocess.Popen(
        [sys.executable, "server.py"],
        env=omgeving,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        if not _wacht_op_poort(POORT):
            fout = server.stderr.read().decode(errors="replace") if server.stderr else ""
            raise SystemExit("Server startte niet op tijd.\n" + fout)
        anyio.run(_demo, sleutel_aron, sleutel_lotte)
    finally:
        server.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            server.wait(timeout=5)


if __name__ == "__main__":
    main()
