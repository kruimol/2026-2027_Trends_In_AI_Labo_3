"""Pytest-tests voor het lessenrooster (``Rooster``).

We pinnen het "nu" met ``STUDIECOACH_NU`` binnen de ingelezen roosterweek
(2026-10-05 t/m 2026-10-09), zodat 'les nu', 'volgende les' en 'vandaag'
reproduceerbaar zijn en niet van de echte klok afhangen.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from context_memory import NU_OMGEVINGSVARIABELE
from rooster import Rooster

# Woensdag 7 oktober 2026, 10u30: midden in de les van 09:00-11:00.
WOENSDAG_1030 = "2026-10-07T10:30:00"


@pytest.fixture
def rooster() -> Rooster:
    """Laad het echte rooster uit de projectmap."""
    return Rooster()


def test_beide_klassen_geladen(rooster: Rooster) -> None:
    """Allebei de klassen moeten ingelezen zijn, met lessen."""
    assert rooster.klassen() == ["3ITAI", "4VTAI"]
    assert len(rooster.lessen) > 0


def test_les_nu(rooster: Rooster, monkeypatch: pytest.MonkeyPatch) -> None:
    """Om 10u30 loopt de les van 09:00-11:00; start inbegrepen, eind niet."""
    monkeypatch.setenv(NU_OMGEVINGSVARIABELE, WOENSDAG_1030)
    moment = datetime.fromisoformat(WOENSDAG_1030)
    nu = rooster.les_nu()
    assert nu, "er zou een les bezig moeten zijn"
    for les in nu:
        assert les.start <= moment < les.eind


def test_volgende_les_start_in_de_toekomst(rooster: Rooster, monkeypatch: pytest.MonkeyPatch) -> None:
    """De volgende les moet na het huidige moment beginnen."""
    monkeypatch.setenv(NU_OMGEVINGSVARIABELE, WOENSDAG_1030)
    volgende = rooster.volgende_les()
    assert volgende is not None
    assert volgende.start > datetime.fromisoformat(WOENSDAG_1030)


def test_lessen_vandaag(rooster: Rooster, monkeypatch: pytest.MonkeyPatch) -> None:
    """'Vandaag' bevat enkel lessen van die dag, gesorteerd op starttijd."""
    monkeypatch.setenv(NU_OMGEVINGSVARIABELE, WOENSDAG_1030)
    vandaag = rooster.lessen_vandaag()
    assert vandaag
    assert all(les.datum.isoformat() == "2026-10-07" for les in vandaag)
    assert vandaag == sorted(vandaag, key=lambda les: les.start)


def test_lessen_binnen_uren(rooster: Rooster, monkeypatch: pytest.MonkeyPatch) -> None:
    """Binnen X uur bevat enkel lessen die in dat venster starten."""
    monkeypatch.setenv(NU_OMGEVINGSVARIABELE, WOENSDAG_1030)
    nu = datetime.fromisoformat(WOENSDAG_1030)
    binnen = rooster.lessen_binnen_uren(3)
    assert binnen
    for les in binnen:
        assert nu <= les.start <= nu + timedelta(hours=3)


def test_wanneer_vak_vindt_gedeeld_vak_in_beide_klassen(rooster: Rooster) -> None:
    """Een gedeeld vak komt in beide klassen voor in het rooster."""
    momenten = rooster.wanneer_vak("Trends in AI")
    assert {les.klas for les in momenten} == {"3ITAI", "4VTAI"}


def test_wanneer_vak_matcht_op_code(rooster: Rooster) -> None:
    """Zoeken op de korte vakcode werkt ook."""
    momenten = rooster.wanneer_vak("MDI_IT_TRAI")
    assert all(les.vak_kort == "MDI_IT_TRAI" for les in momenten)
    assert momenten


def test_vakken_markeert_gedeeld(rooster: Rooster) -> None:
    """De vakcatalogus markeert vakken die in beide klassen voorkomen."""
    gedeeld = {v["vak"] for v in rooster.vakken() if v["gedeeld"]}
    assert "Trends in AI" in gedeeld
    assert "AI for Business" in gedeeld
    # Een vak dat maar in één klas zit, is niet gedeeld.
    niet_gedeeld = {v["vak"] for v in rooster.vakken() if not v["gedeeld"]}
    assert "ML algorithms" in niet_gedeeld


def test_vakken_filtert_op_klas(rooster: Rooster) -> None:
    """Filteren op klas geeft enkel vakken van die klas."""
    vakken_3itai = rooster.vakken("3ITAI")
    assert vakken_3itai
    assert all("3ITAI" in v["klassen"] for v in vakken_3itai)
