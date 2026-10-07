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
from rooster import Les, Rooster

# Logging naar stderr (niet stdout!), zodat het MCP-protocol ongestoord blijft.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("studiecoach")

# De server, één gedeeld contextgeheugen (schrijfbaar) en het lessenrooster
# (read-only). Het geheugen leeft zolang de server draait; de sessielaag is dus
# leeg bij elke start. Het rooster wordt één keer uit de JSON-bestanden geladen.
mcp = MCPServer("studiecoach")
geheugen = ContextMemory()
rooster = Rooster()


# ---------------------------------------------------------------------- #
# Leesbare opmaak-helpers (tools geven tekst terug, niet rauwe objecten)  #
# ---------------------------------------------------------------------- #
def _toon_lessen(lessen: list[Les], leeg: str) -> str:
    """Zet een lijst lessen om naar leesbare regels, of geef ``leeg`` terug."""
    if not lessen:
        return leeg
    return "\n".join(f"- {les.beschrijf()}" for les in lessen)


def _toon_deadlines(deadlines: list[dict], leeg: str) -> str:
    """Zet verrijkte deadline-records (met dagen_tot/voorbij) om naar tekst."""
    if not deadlines:
        return leeg
    regels = []
    for d in deadlines:
        if d["voorbij"]:
            status = f"VOORBIJ ({-d['dagen_tot']} dag(en) geleden)"
        elif d["dagen_tot"] == 0:
            status = "VANDAAG"
        else:
            status = f"over {d['dagen_tot']} dag(en)"
        regels.append(f"- {d['vak']} ({d['klas']}, {d['type']}) op {d['datum']}: {status}")
    return "\n".join(regels)


@mcp.tool()
def haal_context_op() -> str:
    """Roep dit ALTIJD EERST aan bij elke studievraag.

    Geeft de volledige context terug (omgeving = nu, rooster = les nu/straks,
    geschiedenis = bewaard, sessie = deze ronde) als leesbare tekst. Zonder deze
    context weet je niet welke dag het is, welke les nu loopt, welke deadlines er
    zijn of waar de student mee worstelt, en kan je de vraag 'Wat moet ik nu
    doen?' niet goed beantwoorden.
    """
    regels = [geheugen.context_tekst(), "", "=== ROOSTER (nu) ==="]
    nu_lessen = rooster.les_nu()
    if nu_lessen:
        regels.append("Les nu:")
        regels.append(_toon_lessen(nu_lessen, ""))
    else:
        regels.append("Les nu: geen les bezig")
    volgende = rooster.volgende_les()
    regels.append(f"Volgende les: {volgende.beschrijf() if volgende else 'geen meer deze week'}")
    regels.append("Lessen vandaag:")
    regels.append(_toon_lessen(rooster.lessen_vandaag(), "- geen lessen vandaag"))
    return "\n".join(regels)


@mcp.tool()
def voeg_vak_toe(naam: str, klas: str) -> str:
    """Sla een vak op voor een klas (bijvoorbeeld '3ITAI' of '4VTAI').

    Roep dit aan zodra een nieuw vak in het gesprek opduikt. Zit het vak in
    beide klassen (een gedeeld vak), roep het dan twee keer aan, één keer per
    klas.

    Args:
        naam: naam van het vak.
        klas: de klas waarin dit vak gegeven wordt.
    """
    geheugen.voeg_vak_toe(naam, klas)
    return f"Vak '{naam}' opgeslagen voor klas {klas}."


@mcp.tool()
def voeg_deadline_toe(vak: str, datum: str, type: str, klas: str) -> str:
    """Sla een deadline op zodra de student er een noemt.

    Een gedeeld vak kan per klas een andere deadline hebben, daarom hoort de
    klas er altijd bij.

    Args:
        vak: naam van het vak.
        datum: de vervaldag in formaat JJJJ-MM-DD.
        type: soort deadline, bijvoorbeeld 'examen', 'taak' of 'project'.
        klas: de klas waarvoor deze deadline geldt (bijvoorbeeld '3ITAI').
    """
    geheugen.voeg_deadline_toe(vak, datum, type, klas)
    return f"Deadline voor '{vak}' ({klas}, {type}) op {datum} opgeslagen."


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


# ---------------------------------------------------------------------- #
# Rooster-tools (read-only: bevragen het lessenrooster van beide klassen) #
# ---------------------------------------------------------------------- #
@mcp.tool()
def les_nu(klas: str | None = None) -> str:
    """Welke les loopt er op dit moment? Optioneel filteren op klas ('3ITAI'/'4VTAI')."""
    return _toon_lessen(rooster.les_nu(klas), "Er is nu geen les bezig.")


@mcp.tool()
def volgende_les(klas: str | None = None) -> str:
    """Wat is de eerstvolgende les die nog moet beginnen? Optioneel per klas."""
    les = rooster.volgende_les(klas)
    return les.beschrijf() if les else "Geen volgende les meer deze roosterweek."


@mcp.tool()
def lessen_vandaag(klas: str | None = None) -> str:
    """Geef alle lessen van vandaag, gesorteerd op uur. Optioneel per klas."""
    return _toon_lessen(rooster.lessen_vandaag(klas), "Vandaag staan er geen lessen gepland.")


@mcp.tool()
def lessen_op_dag(datum: str, klas: str | None = None) -> str:
    """Geef de lessen op een bepaalde dag.

    Args:
        datum: de dag in formaat JJJJ-MM-DD.
        klas: optioneel filter op klas ('3ITAI' of '4VTAI').
    """
    return _toon_lessen(rooster.lessen_op_dag(datum, klas), f"Geen lessen gevonden op {datum}.")


@mcp.tool()
def lessen_binnen_uren(uren: float, klas: str | None = None) -> str:
    """Welke lessen starten er binnen de komende X uur? Optioneel per klas.

    Args:
        uren: aantal uren vooruit kijken (bv. 3 voor 'de komende 3 uur').
        klas: optioneel filter op klas.
    """
    lessen = rooster.lessen_binnen_uren(uren, klas)
    return _toon_lessen(lessen, f"Geen lessen in de komende {uren} uur.")


@mcp.tool()
def rooster_week(klas: str | None = None) -> str:
    """Geef het volledige rooster van de ingelezen week. Optioneel per klas."""
    return _toon_lessen(rooster.rooster_week(klas), "Er is geen rooster ingeladen.")


@mcp.tool()
def wanneer_vak(vak: str) -> str:
    """Wanneer wordt een bepaald vak gegeven (over beide klassen heen)?

    Args:
        vak: naam of code van het vak (bv. 'Trends in AI' of 'MDI_IT_TRAI').
    """
    return _toon_lessen(rooster.wanneer_vak(vak), f"'{vak}' staat niet in het rooster.")


@mcp.tool()
def vakken_in_rooster(klas: str | None = None) -> str:
    """Geef de vakkenlijst zoals die uit het rooster blijkt. Optioneel per klas.

    Gedeelde vakken (in beide klassen) worden als zodanig gemarkeerd.
    """
    vakken = rooster.vakken(klas)
    if not vakken:
        return "Geen vakken gevonden."
    regels = []
    for v in vakken:
        gedeeld = " (gedeeld)" if v["gedeeld"] else ""
        regels.append(f"- {v['vak']}{gedeeld} [{', '.join(v['klassen'])}]")
    return "\n".join(regels)


# ---------------------------------------------------------------------- #
# Deadline-leestools (read-only: bevragen de bewaarde deadlines)          #
# ---------------------------------------------------------------------- #
@mcp.tool()
def komende_deadlines(dagen: int | None = None) -> str:
    """Geef de deadlines die nog moeten komen, vroegste eerst.

    Args:
        dagen: optionele horizon; bv. 7 geeft enkel de deadlines binnen een week.
    """
    return _toon_deadlines(geheugen.komende_deadlines(dagen), "Geen komende deadlines.")


@mcp.tool()
def deadlines_vandaag() -> str:
    """Geef de deadlines die vandaag vervallen."""
    return _toon_deadlines(geheugen.deadlines_vandaag(), "Vandaag zijn er geen deadlines.")


@mcp.tool()
def verlopen_deadlines() -> str:
    """Geef de deadlines die al voorbij zijn."""
    return _toon_deadlines(geheugen.verlopen_deadlines(), "Geen verlopen deadlines.")


@mcp.tool()
def deadlines_voor_vak(vak: str) -> str:
    """Geef alle deadlines van één vak (over beide klassen heen).

    Args:
        vak: naam van het vak (bv. 'Trends in AI').
    """
    return _toon_deadlines(geheugen.deadlines_voor_vak(vak), f"Geen deadlines voor '{vak}'.")


@mcp.tool()
def deadlines_voor_klas(klas: str) -> str:
    """Geef alle deadlines van één klas.

    Args:
        klas: de klas ('3ITAI' of '4VTAI').
    """
    return _toon_deadlines(geheugen.deadlines_voor_klas(klas), f"Geen deadlines voor klas {klas}.")


# ---------------------------------------------------------------------- #
# Combinatietool                                                          #
# ---------------------------------------------------------------------- #
@mcp.tool()
def wat_nu() -> str:
    """Bundel 'wat moet ik nu doen?' tot één advies.

    Combineert de les die nu loopt (of de volgende les), de eerstvolgende
    deadline en een eventueel zwak punt dat daarbij hoort. Handig als snel
    overzicht zonder eerst alle losse tools te hoeven aanroepen.
    """
    regels: list[str] = []

    nu_lessen = rooster.les_nu()
    if nu_lessen:
        regels.append("Nu bezig: " + "; ".join(les.beschrijf() for les in nu_lessen))
    else:
        volgende = rooster.volgende_les()
        regels.append(
            "Geen les bezig. Volgende les: "
            + (volgende.beschrijf() if volgende else "geen meer deze week.")
        )

    komend = geheugen.komende_deadlines()
    if komend:
        eerste = komend[0]
        wanneer = "vandaag" if eerste["dagen_tot"] == 0 else f"over {eerste['dagen_tot']} dag(en)"
        regels.append(
            f"Dichtstbijzijnde deadline: {eerste['vak']} ({eerste['klas']}, "
            f"{eerste['type']}) op {eerste['datum']} — {wanneer}."
        )
        zwak = [
            z for z in geheugen.geschiedenis["zwakke_punten"]
            if z["vak"].casefold() == eerste["vak"].casefold()
        ]
        if zwak:
            onderwerpen = ", ".join(z["onderwerp"] for z in zwak)
            regels.append(f"Let op — zwak punt bij dit vak: {onderwerpen}.")
    else:
        regels.append("Geen komende deadlines.")

    return "\n".join(regels)


def _start() -> None:
    """Start de server in de juiste modus.

    Standaard draaien we op stdio: zo start Claude Desktop de server lokaal als
    los proces. Zetten we STUDIECOACH_TRANSPORT=http, dan serveren we over
    streamable-HTTP op een poort, zodat de server achter een domein te deployen
    valt (bv. in Docker met een reverse proxy ervoor).
    """
    transport = os.environ.get("STUDIECOACH_TRANSPORT", "stdio").lower()

    if transport == "http":
        host = os.environ.get("STUDIECOACH_HOST", "127.0.0.1")
        poort = int(os.environ.get("STUDIECOACH_PORT", "8000"))

        # DNS-rebinding-bescherming controleert de Host-header. Achter een
        # vertrouwde reverse proxy wil je ofwel je domein toelaten via
        # STUDIECOACH_ALLOWED_HOSTS (komma-gescheiden), ofwel de controle
        # uitschakelen als je toch alleen via de proxy bereikbaar bent.
        rauwe_hosts = os.environ.get("STUDIECOACH_ALLOWED_HOSTS", "").strip()
        if rauwe_hosts:
            beveiliging = TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=[h.strip() for h in rauwe_hosts.split(",") if h.strip()],
            )
        else:
            beveiliging = TransportSecuritySettings(enable_dns_rebinding_protection=False)

        logger.info("Studiecoach MCP-server start (streamable-http) op %s:%s/mcp", host, poort)
        mcp.run(transport="streamable-http", host=host, port=poort, transport_security=beveiliging)
    else:
        logger.info("Studiecoach MCP-server start (stdio-transport).")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    _start()
