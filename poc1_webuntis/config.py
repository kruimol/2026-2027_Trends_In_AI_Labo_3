"""Klassen die we kunnen opvragen in WebUntis: naam -> klas-ID.

Zet in .env `UNTIS_KLAS` op een van de namen hieronder. We lezen het rooster van
die klas (niet het persoonlijke studentenrooster), want veel scholen blokkeren
dat laatste met de fout -8509 "no right for timetable".

Een klas-ID is geen geheim (het staat ook gewoon in de WebUntis-URL als je het
rooster van die klas opent), dus deze lijst mag in de code staan en wordt mee
ingeleverd. Voeg hier gerust extra klassen toe.
"""

KLASSEN = {
    "3itai": 10247,
    "1itVTAI": 10361,
}
