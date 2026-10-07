"""Lessenrooster-laag voor de studiecoach.

Dit bestand bevat de klasse ``Rooster``. Zij leest de WebUntis-exports van de
twee klassen (``3ITAI.json`` en ``4VTAI.json``) in en zet elke les om naar één
genormaliseerd ``Les``-record. Daarmee kan de coach vragen beantwoorden als
"welke les heb ik nu?", "wat is mijn volgende les?", "welke lessen heb ik
vandaag / binnen X uur?" en "wanneer krijg ik vak Y?".

Deze laag is bewust **read-only**: het rooster is een vast gegeven dat we enkel
bevragen. De schrijfbare context (deadlines, zwakke punten, studielog) zit in
``context_memory.py``. Beide lagen delen hetzelfde "nu" via
``huidig_tijdstip()``, zodat een gesimuleerd tijdstip (``STUDIECOACH_NU``) overal
consistent doorwerkt.

Bewust geen database en geen extra dependencies: we lezen rechtstreeks de JSON.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from context_memory import WEEKDAGEN, huidig_tijdstip

logger = logging.getLogger(__name__)

# Welke bronbestanden horen bij welk klaslabel. We vertrouwen bewust NIET op de
# ``resource.shortName`` in het bestand (die is voor 4VTAI intern "1ITVTAI_TI"),
# maar leggen het label hier expliciet vast. De map is overschrijfbaar via de
# omgevingsvariabele STUDIECOACH_ROOSTER_MAP (handig in een container).
ROOSTER_BESTANDEN = {
    "3ITAI": "3ITAI.json",
    "4VTAI": "4VTAI.json",
}

STANDAARD_MAP = Path(os.environ.get("STUDIECOACH_ROOSTER_MAP", Path(__file__).parent))

# Alleen echte lesblokken meenemen (geen pauzes/holtes die WebUntis soms exporteert).
LES_TYPE = "NORMAL_TEACHING_PERIOD"


@dataclass
class Les:
    """Eén genormaliseerd lesblok uit het rooster."""

    klas: str
    vak: str  # longName, bv. "Trends in AI"
    vak_kort: str  # shortName, bv. "MDI_IT_TRAI"
    start: datetime
    eind: datetime
    lokalen: list[str] = field(default_factory=list)
    docenten: list[str] = field(default_factory=list)
    lesvorm: str = ""  # bv. "Labo", "Theorie", "Groepsleren"
    medeklassen: list[str] = field(default_factory=list)

    @property
    def datum(self) -> date:
        return self.start.date()

    @property
    def weekdag(self) -> str:
        return WEEKDAGEN[self.start.weekday()]

    def bezig_op(self, moment: datetime) -> bool:
        """Loopt deze les op ``moment`` (start inbegrepen, eind niet)?"""
        return self.start <= moment < self.eind

    def beschrijf(self) -> str:
        """Geef een korte, leesbare regel voor deze les."""
        klok = f"{self.start:%H:%M}-{self.eind:%H:%M}"
        vorm = f" ({self.lesvorm})" if self.lesvorm else ""
        lok = " · lok " + "/".join(self.lokalen) if self.lokalen else ""
        doc = " · " + "/".join(self.docenten) if self.docenten else ""
        return f"{self.weekdag} {self.start:%d/%m} {klok}  {self.vak}{vorm}{lok}{doc} [{self.klas}]"


def _namen(posities: list | None) -> list[str]:
    """Haal de ``shortName``s uit een position-lijst (ROOM/TEACHER/CLASS/...).

    Defensief: lege of ontbrekende posities en ``removed`` items leveren niets op.
    """
    namen: list[str] = []
    for item in posities or []:
        huidig = item.get("current") or {}
        naam = huidig.get("shortName")
        if naam:
            namen.append(naam)
    return namen


class Rooster:
    """Leest de lessenroosters van beide klassen in en biedt bevragingen aan."""

    def __init__(self, map_pad: Path | str = STANDAARD_MAP, bestanden: dict[str, str] | None = None) -> None:
        """Laad het rooster uit de JSON-bestanden.

        ``map_pad`` is de map waarin de bestanden staan; ``bestanden`` mapt een
        klaslabel op een bestandsnaam (default ``ROOSTER_BESTANDEN``).
        """
        self.map_pad = Path(map_pad)
        self.bestanden = bestanden or ROOSTER_BESTANDEN
        self.lessen: list[Les] = self._laad()

    # ------------------------------------------------------------------ #
    # Inladen                                                            #
    # ------------------------------------------------------------------ #
    def _laad(self) -> list[Les]:
        """Lees alle bestanden in en zet ze om naar een platte lijst lessen."""
        lessen: list[Les] = []
        for klas, bestandsnaam in self.bestanden.items():
            pad = self.map_pad / bestandsnaam
            if not pad.exists():
                logger.warning("Roosterbestand %s ontbreekt; klas %s wordt overgeslagen.", pad, klas)
                continue
            try:
                data = json.loads(pad.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as fout:
                logger.warning("Kon %s niet lezen (%s); klas %s overgeslagen.", pad, fout, klas)
                continue
            for dag in data.get("days", []):
                for grid in dag.get("gridEntries", []):
                    les = self._maak_les(klas, grid)
                    if les is not None:
                        lessen.append(les)
        lessen.sort(key=lambda les: les.start)
        logger.info("Rooster geladen: %d lessen over %d klassen.", len(lessen), len(self.bestanden))
        return lessen

    @staticmethod
    def _maak_les(klas: str, grid: dict) -> Les | None:
        """Zet één WebUntis-gridEntry om naar een ``Les``, of ``None`` als het geen les is."""
        if grid.get("type") != LES_TYPE:
            return None
        duur = grid.get("duration") or {}
        try:
            start = datetime.fromisoformat(duur["start"])
            eind = datetime.fromisoformat(duur["end"])
        except (KeyError, ValueError):
            return None

        vakken = grid.get("position1") or []
        if not vakken:
            return None
        vak_huidig = (vakken[0].get("current") or {})
        vak = vak_huidig.get("longName") or vak_huidig.get("displayName") or vak_huidig.get("shortName", "")
        vak_kort = vak_huidig.get("shortName", "")

        lesvorm_namen = _namen(grid.get("position4"))
        return Les(
            klas=klas,
            vak=vak,
            vak_kort=vak_kort,
            start=start,
            eind=eind,
            lokalen=_namen(grid.get("position2")),
            docenten=_namen(grid.get("position3")),
            lesvorm=lesvorm_namen[0] if lesvorm_namen else "",
            medeklassen=_namen(grid.get("position5")),
        )

    # ------------------------------------------------------------------ #
    # Hulp                                                               #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _nu() -> datetime:
        return huidig_tijdstip()

    def _filter_klas(self, lessen: list[Les], klas: str | None) -> list[Les]:
        """Filter op klas (hoofdletterongevoelig); ``None`` = alle klassen."""
        if klas is None:
            return lessen
        naam = klas.casefold()
        return [les for les in lessen if les.klas.casefold() == naam]

    def klassen(self) -> list[str]:
        """Geef de geladen klaslabels, alfabetisch."""
        return sorted({les.klas for les in self.lessen})

    def dekking(self) -> tuple[date, date] | None:
        """Geef de eerste en laatste dag die het rooster dekt, of ``None`` als leeg."""
        if not self.lessen:
            return None
        return self.lessen[0].datum, self.lessen[-1].datum

    # ------------------------------------------------------------------ #
    # Bevragingen                                                        #
    # ------------------------------------------------------------------ #
    def lessen_op_dag(self, datum: date | str, klas: str | None = None) -> list[Les]:
        """Geef alle lessen op een bepaalde dag (gesorteerd op starttijd)."""
        if isinstance(datum, str):
            datum = date.fromisoformat(datum)
        lessen = [les for les in self.lessen if les.datum == datum]
        return self._filter_klas(lessen, klas)

    def lessen_vandaag(self, klas: str | None = None) -> list[Les]:
        """Geef de lessen van vandaag (volgens het huidige/gesimuleerde moment)."""
        return self.lessen_op_dag(self._nu().date(), klas)

    def les_nu(self, klas: str | None = None) -> list[Les]:
        """Geef de les(sen) die op dit moment bezig zijn (kan leeg zijn)."""
        nu = self._nu()
        lessen = [les for les in self.lessen if les.bezig_op(nu)]
        return self._filter_klas(lessen, klas)

    def volgende_les(self, klas: str | None = None) -> Les | None:
        """Geef de eerstvolgende les die nog moet starten, of ``None``."""
        nu = self._nu()
        kandidaten = [les for les in self.lessen if les.start > nu]
        kandidaten = self._filter_klas(kandidaten, klas)
        return kandidaten[0] if kandidaten else None  # lessen zijn op start gesorteerd

    def lessen_binnen_uren(self, uren: float, klas: str | None = None) -> list[Les]:
        """Geef de lessen die binnen de komende ``uren`` uur starten."""
        nu = self._nu()
        grens = nu + timedelta(hours=uren)
        lessen = [les for les in self.lessen if nu <= les.start <= grens]
        return self._filter_klas(lessen, klas)

    def rooster_week(self, klas: str | None = None) -> list[Les]:
        """Geef alle ingelezen lessen (de volledige roosterweek), gesorteerd."""
        return self._filter_klas(list(self.lessen), klas)

    def wanneer_vak(self, vak: str) -> list[Les]:
        """Geef alle momenten waarop een vak gegeven wordt (over beide klassen).

        Matcht hoofdletterongevoelig op zowel de volledige naam (longName) als de
        korte code (shortName), zodat "Trends in AI" en "MDI_IT_TRAI" allebei werken.
        """
        naam = vak.casefold()
        return [
            les for les in self.lessen
            if naam in les.vak.casefold() or naam == les.vak_kort.casefold()
        ]

    def vakken(self, klas: str | None = None) -> list[dict]:
        """Geef de vakcatalogus afgeleid uit het rooster.

        Elk record: ``{"vak", "vak_kort", "klassen": [...], "gedeeld": bool}``.
        Een vak dat in beide klassen voorkomt is "gedeeld". Met ``klas`` beperk je
        tot de vakken van één klas. Gesorteerd op vaknaam.
        """
        per_vak: dict[str, dict] = {}
        for les in self.lessen:
            rec = per_vak.setdefault(
                les.vak, {"vak": les.vak, "vak_kort": les.vak_kort, "klassen": set()}
            )
            rec["klassen"].add(les.klas)
        resultaat = []
        for rec in per_vak.values():
            if klas is not None and klas.casefold() not in {k.casefold() for k in rec["klassen"]}:
                continue
            resultaat.append(
                {
                    "vak": rec["vak"],
                    "vak_kort": rec["vak_kort"],
                    "klassen": sorted(rec["klassen"]),
                    "gedeeld": len(rec["klassen"]) > 1,
                }
            )
        return sorted(resultaat, key=lambda r: r["vak"])
