"""Pytest-tests voor ContextMemory.

We testen de kern van het contextgeheugen:
- opslaan en opnieuw laden (geschiedenis blijft over sessies heen);
- de sessielaag is leeg na een "herstart" (nieuwe instantie);
- "dagen tot deadline" klopt;
- een verlopen deadline wordt herkend.

We gebruiken de omgevingsvariabele STUDIECOACH_NU om een vast tijdstip te
simuleren, zodat de tests niet afhangen van de echte klok.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from context_memory import NU_OMGEVINGSVARIABELE, ContextMemory


@pytest.fixture
def pad(tmp_path: Path) -> Path:
    """Geef een tijdelijk pad voor het geheugenbestand (per test schoon)."""
    return tmp_path / "geheugen.json"


def test_opslaan_en_opnieuw_laden(pad: Path) -> None:
    """Wat we opslaan, moet een nieuwe instantie terug inlezen."""
    geheugen = ContextMemory(pad=pad)
    geheugen.voeg_vak_toe("Wiskunde")
    geheugen.voeg_deadline_toe("Wiskunde", "2026-03-06", "examen")

    opnieuw = ContextMemory(pad=pad)
    assert opnieuw.geschiedenis["vakken"] == ["Wiskunde"]
    assert opnieuw.geschiedenis["deadlines"][0]["vak"] == "Wiskunde"


def test_sessie_is_leeg_na_herstart(pad: Path) -> None:
    """De sessielaag mag niet meeverhuizen naar een nieuwe instantie."""
    geheugen = ContextMemory(pad=pad)
    geheugen.voeg_vak_toe("Wiskunde")
    assert geheugen.sessie  # in deze sessie staat wél een actie

    opnieuw = ContextMemory(pad=pad)
    assert opnieuw.sessie == []  # na "herstart" terug leeg


def test_dagen_tot_deadline_klopt(pad: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Op 4 maart moet een deadline op 6 maart 'over 2 dagen' zijn."""
    monkeypatch.setenv(NU_OMGEVINGSVARIABELE, "2026-03-04T09:00:00")
    geheugen = ContextMemory(pad=pad)
    geheugen.voeg_deadline_toe("Wiskunde", "2026-03-06", "examen")

    info = geheugen.omgeving()["deadlines"][0]
    assert info["dagen_tot"] == 2
    assert info["voorbij"] is False


def test_verlopen_deadline_wordt_herkend(pad: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Een deadline in het verleden moet als 'voorbij' gemarkeerd worden."""
    monkeypatch.setenv(NU_OMGEVINGSVARIABELE, "2026-03-10T09:00:00")
    geheugen = ContextMemory(pad=pad)
    geheugen.voeg_deadline_toe("Wiskunde", "2026-03-06", "examen")

    info = geheugen.omgeving()["deadlines"][0]
    assert info["voorbij"] is True
    assert info["dagen_tot"] < 0


def test_markeer_beheerst_verwijdert_zwak_punt(pad: Path) -> None:
    """Een beheerst onderwerp mag niet meer in de zwakke punten staan."""
    geheugen = ContextMemory(pad=pad)
    geheugen.markeer_zwak_punt("Wiskunde", "integralen")
    assert len(geheugen.geschiedenis["zwakke_punten"]) == 1

    geheugen.markeer_beheerst("integralen")
    assert geheugen.geschiedenis["zwakke_punten"] == []
