"""Contextgeheugen voor de studiecoach.

Dit bestand bevat de klasse ``ContextMemory``. Zij houdt drie lagen context
bij zodat de studiecoach op dezelfde vraag ("Wat moet ik nu doen?") een ander
antwoord kan geven naargelang de situatie:

1. Sessie     - wat er in deze draaironde van de server gebeurde (alleen in
                geheugen, leeg na herstart).
2. Geschiedenis - vakken, deadlines, zwakke punten en een studielog (bewaard
                in ``geheugen.json``, blijft bestaan over sessies heen).
3. Omgeving   - afgeleide feiten over het huidige moment (datum, weekdag, uur,
                dagdeel, dagen tot elke deadline, verlopen deadlines). Wordt bij
                elke aanvraag opnieuw berekend.

Bewust geen database en geen extra dependencies: alles zit in één JSON-bestand.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Standaardlocatie van het geheugenbestand: naast dit script, zodat het altijd
# teruggevonden wordt ongeacht vanwaar de server gestart wordt. Via de
# omgevingsvariabele STUDIECOACH_GEHEUGEN kan je een ander pad kiezen; dat is
# handig in een container, waar je het bestand op een volume wil bewaren.
STANDAARD_PAD = Path(os.environ.get("STUDIECOACH_GEHEUGEN", Path(__file__).parent / "geheugen.json"))

# Naam van de omgevingsvariabele waarmee we het "huidige" tijdstip kunnen
# overschrijven. Handig om in een demo een ander moment te simuleren.
NU_OMGEVINGSVARIABELE = "STUDIECOACH_NU"

# Nederlandse weekdagnamen, geïndexeerd zoals datetime.weekday() (maandag = 0).
WEEKDAGEN = [
    "maandag",
    "dinsdag",
    "woensdag",
    "donderdag",
    "vrijdag",
    "zaterdag",
    "zondag",
]


def _leeg_geheugen() -> dict[str, list]:
    """Geef de structuur van een leeg geschiedenis-geheugen terug.

    We centraliseren dit zodat laden, wissen en initialiseren altijd dezelfde
    vorm gebruiken.
    """
    return {
        "vakken": [],  # lijst van vaknamen (str)
        "deadlines": [],  # lijst van {"vak", "type", "datum"}
        "zwakke_punten": [],  # lijst van {"vak", "onderwerp"}
        "studielog": [],  # lijst van {"vak", "minuten", "datum"}
    }


class ContextMemory:
    """Houdt de drie contextlagen bij en bewaart de geschiedenis in JSON."""

    def __init__(self, pad: Path | str = STANDAARD_PAD) -> None:
        """Maak een nieuw geheugen aan.

        De sessielaag start altijd leeg (dit is per definitie een nieuwe
        sessie). De geschiedenis wordt uit ``pad`` geladen als dat bestand
        bestaat, zodat eerdere kennis bewaard blijft.
        """
        self.pad = Path(pad)
        self.sessie: list[str] = []  # acties van deze sessie, enkel in geheugen
        self.geschiedenis: dict[str, list] = self._laad_geschiedenis()

    # ------------------------------------------------------------------ #
    # Opslag: geschiedenis laden en bewaren                              #
    # ------------------------------------------------------------------ #
    def _laad_geschiedenis(self) -> dict[str, list]:
        """Lees de geschiedenis uit het JSON-bestand, of begin leeg.

        Een ontbrekend of beschadigd bestand mag de server niet laten
        crashen; in dat geval starten we met een leeg geheugen.
        """
        if not self.pad.exists():
            return _leeg_geheugen()
        try:
            data = json.loads(self.pad.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as fout:
            logger.warning("Kon %s niet lezen (%s); start met leeg geheugen.", self.pad, fout)
            return _leeg_geheugen()
        # Ontbrekende sleutels aanvullen, zodat oudere bestanden blijven werken.
        geheugen = _leeg_geheugen()
        geheugen.update({sleutel: data.get(sleutel, []) for sleutel in geheugen})
        return geheugen

    def _bewaar_geschiedenis(self) -> None:
        """Schrijf de geschiedenis naar het JSON-bestand (leesbaar ingesprongen)."""
        self.pad.write_text(
            json.dumps(self.geschiedenis, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _noteer_in_sessie(self, actie: str) -> None:
        """Voeg een leesbare actiebeschrijving toe aan de sessielaag."""
        self.sessie.append(actie)

    # ------------------------------------------------------------------ #
    # Omgeving: alles wat van het huidige tijdstip afhangt               #
    # ------------------------------------------------------------------ #
    def _nu(self) -> datetime:
        """Geef het "huidige" tijdstip terug.

        Normaal is dat de echte klok, maar via de omgevingsvariabele
        ``STUDIECOACH_NU`` (ISO-formaat) kunnen we een ander moment simuleren.
        Dat maakt een reproduceerbare demo mogelijk.
        """
        rauw = os.environ.get(NU_OMGEVINGSVARIABELE)
        if rauw:
            try:
                return datetime.fromisoformat(rauw)
            except ValueError:
                logger.warning("Ongeldige %s=%r; gebruik de echte klok.", NU_OMGEVINGSVARIABELE, rauw)
        return datetime.now()

    @staticmethod
    def _dagdeel(uur: int) -> str:
        """Vertaal een uur (0-23) naar een dagdeel in woorden."""
        if 6 <= uur < 12:
            return "ochtend"
        if 12 <= uur < 18:
            return "middag"
        if 18 <= uur < 23:
            return "avond"
        return "nacht"

    def omgeving(self) -> dict[str, Any]:
        """Bereken de omgevingslaag op basis van het huidige tijdstip.

        Deze laag wordt bewust niet opgeslagen: ze wordt elke keer opnieuw
        afgeleid, zodat "dagen tot deadline" en "verlopen" altijd kloppen.
        """
        nu = self._nu()
        vandaag = nu.date()

        deadlines_info: list[dict[str, Any]] = []
        for deadline in self.geschiedenis["deadlines"]:
            vervaldag = date.fromisoformat(deadline["datum"])
            dagen = (vervaldag - vandaag).days
            deadlines_info.append(
                {
                    "vak": deadline["vak"],
                    "type": deadline["type"],
                    "datum": deadline["datum"],
                    "dagen_tot": dagen,  # negatief = al voorbij
                    "voorbij": dagen < 0,
                }
            )

        return {
            "datum": vandaag.isoformat(),
            "weekdag": WEEKDAGEN[vandaag.weekday()],
            "uur": nu.hour,
            "dagdeel": self._dagdeel(nu.hour),
            "deadlines": deadlines_info,
        }

    # ------------------------------------------------------------------ #
    # Acties die de geschiedenis aanpassen                               #
    # ------------------------------------------------------------------ #
    def voeg_vak_toe(self, naam: str) -> None:
        """Voeg een vak toe (dubbels worden overgeslagen)."""
        if naam not in self.geschiedenis["vakken"]:
            self.geschiedenis["vakken"].append(naam)
            self._bewaar_geschiedenis()
        self._noteer_in_sessie(f"vak toegevoegd: {naam}")

    def voeg_deadline_toe(self, vak: str, datum: str, type: str) -> None:
        """Bewaar een deadline voor een vak.

        ``datum`` is in formaat JJJJ-MM-DD; ``type`` is bv. 'examen' of 'taak'.
        """
        # Valideer de datum meteen, zodat we geen onleesbare waarde opslaan.
        date.fromisoformat(datum)
        self.geschiedenis["deadlines"].append({"vak": vak, "type": type, "datum": datum})
        self._bewaar_geschiedenis()
        self._noteer_in_sessie(f"deadline toegevoegd: {vak} ({type}) op {datum}")

    def markeer_zwak_punt(self, vak: str, onderwerp: str) -> None:
        """Noteer dat een onderwerp binnen een vak nog niet lukt."""
        zwak = {"vak": vak, "onderwerp": onderwerp}
        if zwak not in self.geschiedenis["zwakke_punten"]:
            self.geschiedenis["zwakke_punten"].append(zwak)
            self._bewaar_geschiedenis()
        self._noteer_in_sessie(f"zwak punt gemarkeerd: {vak} - {onderwerp}")

    def markeer_beheerst(self, onderwerp: str) -> None:
        """Verwijder een onderwerp uit de zwakke punten (het lukt nu wel)."""
        self.geschiedenis["zwakke_punten"] = [
            zwak for zwak in self.geschiedenis["zwakke_punten"] if zwak["onderwerp"] != onderwerp
        ]
        self._bewaar_geschiedenis()
        self._noteer_in_sessie(f"beheerst: {onderwerp}")

    def log_studiesessie(self, vak: str, minuten: int) -> None:
        """Voeg een studiesessie toe aan het studielog, gedateerd op vandaag."""
        self.geschiedenis["studielog"].append(
            {"vak": vak, "minuten": minuten, "datum": self._nu().date().isoformat()}
        )
        self._bewaar_geschiedenis()
        self._noteer_in_sessie(f"studiesessie gelogd: {vak} ({minuten} min)")

    def wis_geheugen(self) -> None:
        """Wis de volledige geschiedenis (de sessielaag blijft ongemoeid)."""
        self.geschiedenis = _leeg_geheugen()
        self._bewaar_geschiedenis()
        self._noteer_in_sessie("geheugen gewist")

    # ------------------------------------------------------------------ #
    # Leesbare weergave van de drie lagen                                #
    # ------------------------------------------------------------------ #
    def context_tekst(self) -> str:
        """Geef de drie lagen terug als één leesbaar tekstblok.

        Dit is wat het taalmodel via ``haal_context_op`` te zien krijgt.
        """
        omgeving = self.omgeving()
        regels: list[str] = []

        regels.append("=== OMGEVING (nu) ===")
        regels.append(
            f"Het is {omgeving['weekdag']} {omgeving['datum']}, "
            f"{omgeving['uur']}u ({omgeving['dagdeel']})."
        )
        if omgeving["deadlines"]:
            for info in omgeving["deadlines"]:
                if info["voorbij"]:
                    status = f"VOORBIJ ({-info['dagen_tot']} dagen geleden)"
                elif info["dagen_tot"] == 0:
                    status = "VANDAAG"
                else:
                    status = f"over {info['dagen_tot']} dag(en)"
                regels.append(f"- {info['vak']} ({info['type']}) op {info['datum']}: {status}")
        else:
            regels.append("- geen deadlines bekend")

        regels.append("")
        regels.append("=== GESCHIEDENIS (bewaard) ===")
        regels.append("Vakken: " + (", ".join(self.geschiedenis["vakken"]) or "geen"))
        if self.geschiedenis["zwakke_punten"]:
            for zwak in self.geschiedenis["zwakke_punten"]:
                regels.append(f"Zwak punt: {zwak['vak']} - {zwak['onderwerp']}")
        else:
            regels.append("Zwakke punten: geen")
        totaal_minuten = sum(sessie["minuten"] for sessie in self.geschiedenis["studielog"])
        regels.append(
            f"Studielog: {len(self.geschiedenis['studielog'])} sessie(s), "
            f"{totaal_minuten} minuten in totaal"
        )

        regels.append("")
        regels.append("=== SESSIE (sinds server-start) ===")
        if self.sessie:
            regels.extend(f"- {actie}" for actie in self.sessie)
        else:
            regels.append("- nog geen acties deze sessie")

        return "\n".join(regels)
