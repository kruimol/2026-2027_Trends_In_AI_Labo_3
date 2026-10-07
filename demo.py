"""Demo zonder Claude Desktop.

Dit script gebruikt ``ContextMemory`` rechtstreeks en speelt drie momenten na.
Zo tonen we dat dezelfde vraag ("Wat moet ik nu doen?") een andere context
oplevert naargelang het tijdstip en wat er intussen gebeurde.

We overschrijven het "huidige" tijdstip via de omgevingsvariabele
STUDIECOACH_NU, en we gebruiken een apart geheugenbestand zodat de demo het
echte ``geheugen.json`` niet aanraakt.

Starten:  uv run demo.py
"""

from __future__ import annotations

import os
from pathlib import Path

from context_memory import NU_OMGEVINGSVARIABELE, ContextMemory

# Apart bestand voor de demo, zodat we het echte geheugen niet vervuilen.
DEMO_PAD = Path(__file__).parent / "demo_geheugen.json"


def zet_tijd(tijdstip: str) -> None:
    """Stel het gesimuleerde 'nu' in via de omgevingsvariabele."""
    os.environ[NU_OMGEVINGSVARIABELE] = tijdstip


def toon_moment(titel: str, geheugen: ContextMemory) -> None:
    """Druk een kopje en de huidige context af, zodat verschillen zichtbaar zijn."""
    print("\n" + "=" * 60)
    print(titel)
    print("=" * 60)
    print(geheugen.context_tekst())


def main() -> None:
    """Speel de drie momenten na."""
    # Schone start: eventueel oud demobestand weggooien.
    DEMO_PAD.unlink(missing_ok=True)

    # --- Moment 1: maandag 10u -------------------------------------------
    # Nieuwe sessie: we leren de vakken en één deadline kennen.
    zet_tijd("2026-03-02T10:00:00")  # maandag
    geheugen = ContextMemory(pad=DEMO_PAD, seed_pad=None)
    geheugen.voeg_vak_toe("Wiskunde", "3ITAI")
    geheugen.voeg_vak_toe("Geschiedenis", "3ITAI")
    geheugen.voeg_deadline_toe("Wiskunde", "2026-03-06", "examen", "3ITAI")  # vrijdag
    geheugen.markeer_zwak_punt("Wiskunde", "integralen")
    toon_moment("MOMENT 1 - maandag 10u (vakken + deadline toegevoegd)", geheugen)

    # --- Moment 2: donderdag 22u -----------------------------------------
    # Nieuwe sessie (nieuwe ContextMemory): de sessielaag is weer leeg, maar de
    # geschiedenis is uit het bestand geladen. Eén dag voor de deadline.
    zet_tijd("2026-03-05T22:00:00")  # donderdag
    geheugen = ContextMemory(pad=DEMO_PAD, seed_pad=None)
    geheugen.log_studiesessie("Wiskunde", 90)
    toon_moment("MOMENT 2 - donderdag 22u (nieuwe sessie, 1 dag voor deadline)", geheugen)

    # --- Moment 3: zaterdag 14u ------------------------------------------
    # Opnieuw een nieuwe sessie: de deadline is nu voorbij.
    zet_tijd("2026-03-07T14:00:00")  # zaterdag
    geheugen = ContextMemory(pad=DEMO_PAD, seed_pad=None)
    toon_moment("MOMENT 3 - zaterdag 14u (deadline voorbij)", geheugen)

    # Opruimen: demobestand weer verwijderen.
    DEMO_PAD.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
