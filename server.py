"""MCP-server 'studiecoach'.

Deze server geeft Claude Desktop toegang tot ons contextgeheugen via een set
MCP-tools. Claude Desktop is het chatvenster en het taalmodel; deze server
onthoudt de context en biedt die aan.

Belangrijk voor een MCP-server over stdio: stdout is gereserveerd voor het
protocol. We gebruiken daarom nooit ``print()`` maar enkel de logging-module
(die naar stderr schrijft).

API gecontroleerd tegen de geïnstalleerde SDK (mcp 2.x): in deze versie heet de
server-klasse ``MCPServer`` (voorheen ``FastMCP``).
"""

from __future__ import annotations

import logging
import os

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from context_memory import ContextMemory

# Logging naar stderr (niet stdout!), zodat het MCP-protocol ongestoord blijft.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("studiecoach")

# De server en één gedeeld contextgeheugen. Het geheugen leeft zolang de server
# draait; de sessielaag is dus leeg bij elke start.
mcp = MCPServer("studiecoach")
geheugen = ContextMemory()


@mcp.tool()
def haal_context_op() -> str:
    """Roep dit ALTIJD EERST aan bij elke studievraag.

    Geeft de volledige context terug (omgeving = nu, geschiedenis = bewaard,
    sessie = deze ronde) als leesbare tekst. Zonder deze context weet je niet
    welke dag het is, welke deadlines er zijn of waar de student mee worstelt,
    en kan je de vraag 'Wat moet ik nu doen?' niet goed beantwoorden.
    """
    return geheugen.context_tekst()


@mcp.tool()
def voeg_vak_toe(naam: str) -> str:
    """Sla een vak op. Roep dit aan zodra een nieuw vak in het gesprek opduikt."""
    geheugen.voeg_vak_toe(naam)
    return f"Vak '{naam}' opgeslagen."


@mcp.tool()
def voeg_deadline_toe(vak: str, datum: str, type: str) -> str:
    """Sla een deadline op zodra de student er een noemt.

    Args:
        vak: naam van het vak.
        datum: de vervaldag in formaat JJJJ-MM-DD.
        type: soort deadline, bijvoorbeeld 'examen', 'taak' of 'project'.
    """
    geheugen.voeg_deadline_toe(vak, datum, type)
    return f"Deadline voor '{vak}' ({type}) op {datum} opgeslagen."


@mcp.tool()
def markeer_zwak_punt(vak: str, onderwerp: str) -> str:
    """Noteer een onderwerp dat nog niet lukt.

    Roep dit aan zodra de student aangeeft iets moeilijk te vinden of niet te
    begrijpen, zodat de coach er later rekening mee houdt.
    """
    geheugen.markeer_zwak_punt(vak, onderwerp)
    return f"Zwak punt opgeslagen: {vak} - {onderwerp}."


@mcp.tool()
def markeer_beheerst(onderwerp: str) -> str:
    """Verwijder een onderwerp uit de zwakke punten.

    Roep dit aan zodra de student aangeeft dat iets nu wél lukt.
    """
    geheugen.markeer_beheerst(onderwerp)
    return f"'{onderwerp}' is nu beheerst en uit de zwakke punten verwijderd."


@mcp.tool()
def log_studiesessie(vak: str, minuten: int) -> str:
    """Log hoeveel minuten er aan een vak gestudeerd is.

    Roep dit aan zodra de student vertelt dat hij of zij gestudeerd heeft.
    """
    geheugen.log_studiesessie(vak, minuten)
    return f"Studiesessie gelogd: {minuten} minuten voor '{vak}'."


@mcp.tool()
def wis_geheugen() -> str:
    """Wis de volledige bewaarde geschiedenis (vakken, deadlines, zwakke punten, studielog)."""
    geheugen.wis_geheugen()
    return "Het geheugen is gewist."


if __name__ == "__main__":
    logger.info("Studiecoach MCP-server start (stdio-transport).")
    mcp.run(transport="stdio")
