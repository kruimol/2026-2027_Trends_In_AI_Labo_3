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

# Startdata ("seed"): wordt ingeladen als er nog geen echt geheugenbestand is.
# Zo heeft de coach bij een verse start meteen realistische vakken en deadlines.
# Dit bestand wordt zelf nooit overschreven; schrijfacties gaan naar STANDAARD_PAD.
SEED_PAD = Path(__file__).parent / "seed_geheugen.json"

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


def huidig_tijdstip() -> datetime:
    """Geef het "huidige" tijdstip terug (de klok, of een gesimuleerd moment).

    Normaal is dat de echte klok, maar via de omgevingsvariabele
    ``STUDIECOACH_NU`` (ISO-formaat, bv. ``2026-10-07T10:30``) kunnen we een
    ander moment simuleren. Dat maakt een reproduceerbare demo en reproduceerbare
    tests mogelijk. Deze functie staat op moduleniveau zodat zowel het geheugen
    als het rooster (``rooster.py``) exact dezelfde "nu" gebruiken.
    """
    rauw = os.environ.get(NU_OMGEVINGSVARIABELE)
    if rauw:
        try:
            return datetime.fromisoformat(rauw)
        except ValueError:
            logger.warning("Ongeldige %s=%r; gebruik de echte klok.", NU_OMGEVINGSVARIABELE, rauw)
    return datetime.now()


def _leeg_geheugen() -> dict[str, list]:
    """Geef de structuur van een leeg geschiedenis-geheugen terug.

    We centraliseren dit zodat laden, wissen en initialiseren altijd dezelfde
    vorm gebruiken.
    """
    return {
        # Een vak hoort bij één of meerdere klassen. Een "gedeeld" vak (dat in
        # beide klassen gegeven wordt) heeft meerdere klassen in zijn lijst.
        "vakken": [],  # lijst van {"naam", "klassen": [str, ...]}
        "deadlines": [],  # lijst van {"vak", "klas", "type", "datum"}
        "zwakke_punten": [],  # lijst van {"vak", "onderwerp"}
        "studielog": [],  # lijst van {"vak", "minuten", "datum"}
    }


class ContextMemory:
    """Houdt de drie contextlagen bij en bewaart de geschiedenis in JSON."""

    def __init__(self, pad: Path | str = STANDAARD_PAD, seed_pad: Path | str | None = SEED_PAD) -> None:
        """Maak een nieuw geheugen aan.

        De sessielaag start altijd leeg (dit is per definitie een nieuwe
        sessie). De geschiedenis wordt uit ``pad`` geladen als dat bestand
        bestaat, zodat eerdere kennis bewaard blijft. Bestaat ``pad`` nog niet,
        dan vallen we terug op ``seed_pad`` (de startdata). Geef ``seed_pad=None``
        mee als je bewust leeg wil starten (bv. in de demo of de tests).
        """
        self.pad = Path(pad)
        self.seed_pad = Path(seed_pad) if seed_pad is not None else None
        self.sessie: list[str] = []  # acties van deze sessie, enkel in geheugen
        self.geschiedenis: dict[str, list] = self._laad_geschiedenis()

    # ------------------------------------------------------------------ #
    # Opslag: geschiedenis laden en bewaren                              #
    # ------------------------------------------------------------------ #
    def _laad_geschiedenis(self) -> dict[str, list]:
        """Lees de geschiedenis uit het JSON-bestand, de seed, of begin leeg.

        Volgorde: bestaat het echte bestand (``pad``), dan lezen we dat.
        Bestaat het nog niet maar is er een seed, dan laden we de startdata.
        Een ontbrekend of beschadigd bestand mag de server nooit laten
        crashen; in dat geval starten we met een leeg geheugen.
        """
        bronbestand = self.pad
        if not self.pad.exists():
            if self.seed_pad is not None and self.seed_pad.exists():
                bronbestand = self.seed_pad  # verse start: gebruik de startdata
            else:
                return _leeg_geheugen()
        try:
            data = json.loads(bronbestand.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as fout:
            logger.warning("Kon %s niet lezen (%s); start met leeg geheugen.", bronbestand, fout)
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
        """Geef het "huidige" tijdstip terug (zie ``huidig_tijdstip``)."""
        return huidig_tijdstip()

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

    @staticmethod
    def _deadline_info(deadline: dict, vandaag: date) -> dict[str, Any]:
        """Verrijk één opgeslagen deadline met afgeleide velden.

        Voegt ``dagen_tot`` (negatief = al voorbij) en ``voorbij`` toe. Deze ene
        plek wordt door alle deadline-leesfuncties hergebruikt, zodat de telling
        overal identiek is.
        """
        vervaldag = date.fromisoformat(deadline["datum"])
        dagen = (vervaldag - vandaag).days
        return {
            "vak": deadline["vak"],
            "klas": deadline.get("klas", "?"),
            "type": deadline["type"],
            "datum": deadline["datum"],
            "dagen_tot": dagen,  # negatief = al voorbij
            "voorbij": dagen < 0,
        }

    def _alle_deadlines(self) -> list[dict[str, Any]]:
        """Geef alle deadlines verrijkt en gesorteerd op datum (vroegste eerst)."""
        vandaag = self._nu().date()
        verrijkt = [self._deadline_info(d, vandaag) for d in self.geschiedenis["deadlines"]]
        return sorted(verrijkt, key=lambda d: d["datum"])

    def omgeving(self) -> dict[str, Any]:
        """Bereken de omgevingslaag op basis van het huidige tijdstip.

        Deze laag wordt bewust niet opgeslagen: ze wordt elke keer opnieuw
        afgeleid, zodat "dagen tot deadline" en "verlopen" altijd kloppen.
        """
        nu = self._nu()
        vandaag = nu.date()
        return {
            "datum": vandaag.isoformat(),
            "weekdag": WEEKDAGEN[vandaag.weekday()],
            "uur": nu.hour,
            "dagdeel": self._dagdeel(nu.hour),
            "deadlines": self._alle_deadlines(),
        }

    # ------------------------------------------------------------------ #
    # Deadlines bevragen (read-only, afgeleid)                           #
    # ------------------------------------------------------------------ #
    def komende_deadlines(self, dagen: int | None = None) -> list[dict[str, Any]]:
        """Geef de deadlines die nog moeten komen (vandaag of later).

        Met ``dagen`` beperk je tot een horizon: bv. ``dagen=7`` geeft enkel de
        deadlines binnen de komende week. Gesorteerd op datum.
        """
        komend = [d for d in self._alle_deadlines() if not d["voorbij"]]
        if dagen is not None:
            komend = [d for d in komend if d["dagen_tot"] <= dagen]
        return komend

    def verlopen_deadlines(self) -> list[dict[str, Any]]:
        """Geef de deadlines die al voorbij zijn (gesorteerd op datum)."""
        return [d for d in self._alle_deadlines() if d["voorbij"]]

    def deadlines_vandaag(self) -> list[dict[str, Any]]:
        """Geef de deadlines die vandaag vervallen."""
        return [d for d in self._alle_deadlines() if d["dagen_tot"] == 0]

    def deadlines_voor_vak(self, vak: str) -> list[dict[str, Any]]:
        """Geef alle deadlines van één vak (over beide klassen heen)."""
        naam = vak.casefold()
        return [d for d in self._alle_deadlines() if d["vak"].casefold() == naam]

    def deadlines_voor_klas(self, klas: str) -> list[dict[str, Any]]:
        """Geef alle deadlines van één klas."""
        naam = klas.casefold()
        return [d for d in self._alle_deadlines() if d["klas"].casefold() == naam]

    # ------------------------------------------------------------------ #
    # Acties die de geschiedenis aanpassen                               #
    # ------------------------------------------------------------------ #
    def _zoek_vak(self, naam: str) -> dict | None:
        """Geef het vak-record met deze naam terug, of None."""
        for vak in self.geschiedenis["vakken"]:
            if vak["naam"] == naam:
                return vak
        return None

    def _klassen(self) -> list[str]:
        """Geef de klassen die in het geheugen voorkomen, alfabetisch gesorteerd."""
        namen = {klas for vak in self.geschiedenis["vakken"] for klas in vak["klassen"]}
        namen.update(deadline.get("klas", "?") for deadline in self.geschiedenis["deadlines"])
        return sorted(namen)

    def voeg_vak_toe(self, naam: str, klas: str) -> None:
        """Voeg een vak toe voor een klas (bv. '3ITAI' of '4VTAI').

        Bestaat het vak al, dan voegen we enkel de klas eraan toe. Zo ontstaat
        een "gedeeld" vak vanzelf: roep dit twee keer aan, één keer per klas.
        """
        vak = self._zoek_vak(naam)
        if vak is None:
            self.geschiedenis["vakken"].append({"naam": naam, "klassen": [klas]})
            self._bewaar_geschiedenis()
        elif klas not in vak["klassen"]:
            vak["klassen"].append(klas)
            self._bewaar_geschiedenis()
        self._noteer_in_sessie(f"vak toegevoegd: {naam} ({klas})")

    def voeg_deadline_toe(self, vak: str, datum: str, type: str, klas: str) -> None:
        """Bewaar een deadline voor een vak binnen een klas.

        ``datum`` is in formaat JJJJ-MM-DD; ``type`` is bv. 'examen' of 'taak'.
        De klas hoort erbij omdat een gedeeld vak per klas een andere deadline
        kan hebben.
        """
        # Valideer de datum meteen, zodat we geen onleesbare waarde opslaan.
        date.fromisoformat(datum)
        self.geschiedenis["deadlines"].append({"vak": vak, "klas": klas, "type": type, "datum": datum})
        self._bewaar_geschiedenis()
        self._noteer_in_sessie(f"deadline toegevoegd: {vak} ({klas}, {type}) op {datum}")

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
        klassen = self._klassen()
        if omgeving["deadlines"]:
            # Per klas groeperen, zodat de twee klassen niet door elkaar lopen.
            for klas in klassen:
                klas_deadlines = [d for d in omgeving["deadlines"] if d["klas"] == klas]
                if not klas_deadlines:
                    continue
                regels.append(f"Deadlines {klas}:")
                for info in klas_deadlines:
                    if info["voorbij"]:
                        status = f"VOORBIJ ({-info['dagen_tot']} dagen geleden)"
                    elif info["dagen_tot"] == 0:
                        status = "VANDAAG"
                    else:
                        status = f"over {info['dagen_tot']} dag(en)"
                    regels.append(f"  - {info['vak']} ({info['type']}) op {info['datum']}: {status}")
        else:
            regels.append("- geen deadlines bekend")

        regels.append("")
        regels.append("=== GESCHIEDENIS (bewaard) ===")
        # De vakkenlijst komt uit het rooster (zie rooster.py); hier tonen we
        # enkel de bewaarde geheugenlaag: zwakke punten en het studielog.
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
