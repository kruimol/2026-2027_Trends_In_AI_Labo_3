"""Klassen die we kunnen opvragen in WebUntis: naam -> klas-ID.

De gebruiker kiest zijn klas door ze te laten onthouden (bv. onthoud('klas', '3itai')).
Is er geen onthouden klas, dan valt de server terug op UNTIS_KLAS uit .env. In beide
gevallen zoeken we de naam hieronder op om het klas-ID te vinden.

Een klas-ID is geen geheim (het staat ook gewoon in de WebUntis-URL als je het
rooster van die klas opent), dus deze lijst mag in de code staan en wordt mee
ingeleverd. Voeg hier gerust extra klassen toe.
"""

KLASSEN = {
    "3itai": 10247,
    "1itVTAI": 10361,
}
