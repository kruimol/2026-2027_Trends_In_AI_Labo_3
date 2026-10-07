"""Twee loginroutes voor WebUntis, allebei via de oudere JSON-RPC API.

Overgenomen uit POC 1 (poc1_webuntis/untis_login.py): bewezen werkend. Welke route
je ook kiest, je krijgt altijd dezelfde ingelogde ``webuntis.Session`` terug, zodat
de rest van de code (untis.py) niet hoeft te weten hoe er ingelogd werd.

Route 1: gebruikersnaam + wachtwoord -> met de library ``webuntis``.
Route 2: gebruikersnaam + geheime sleutel (TOTP) -> zelf nagebouwd, zoals
         het npm-pakket ``webuntis`` (WebUntisSecretAuth) en toughIQ/webuntis-mcp
         het doen. De library zelf kan dit niet, dus we loggen handmatig in
         en schuiven de sessie daarna in een ``webuntis.Session``.
"""

import base64
import time
from urllib.parse import urlparse

import pyotp
import requests
import webuntis


def host(server: str) -> str:
    """Maak van 'https://mese.webuntis.com' of 'mese.webuntis.com' de kale host."""
    server = server.strip()
    if server.startswith(("http://", "https://")):
        ontleed = urlparse(server)
        return ontleed.netloc or ontleed.path
    return server


def login_met_wachtwoord(server, school, user, password, useragent):
    """Route 1: standaard login met wachtwoord via de webuntis-library."""
    session = webuntis.Session(
        server=host(server),
        school=school,
        username=user,
        password=password,
        useragent=useragent,
    )
    session.login()  # roept de JSON-RPC-methode 'authenticate' aan
    return session


def login_met_secret(server, school, user, secret, useragent):
    """Route 2: login met de geheime sleutel uit het WebUntis-profiel (QR-code).

    Stappen (identiek aan het npm-pakket webuntis):
      1. Bereken een eenmalige code (TOTP) uit de geheime sleutel.
      2. POST die code naar getUserData2017; de server geeft een JSESSIONID terug.
      3. Haal personId/personType op via /WebUntis/api/app/config.
      4. Steek de JSESSIONID en persoonsgegevens in een webuntis.Session.
    """
    kale_host = host(server)
    basis = f"https://{kale_host}"
    http = requests.Session()

    # Dezelfde 'schoolname'-cookie die de officiële app meestuurt.
    schoolcookie = "_" + base64.b64encode(school.encode()).decode()
    http.cookies.set("schoolname", schoolcookie)

    # 1. Eenmalige code uit de sleutel. pyotp gebruikt dezelfde instellingen
    #    als otplib in het npm-pakket: SHA1, 6 cijfers, nieuw venster per 30s.
    otp = pyotp.TOTP(secret).now()
    client_time = int(time.time() * 1000)  # tijd in milliseconden

    # 2. Inloggen via de interne mobiele JSON-RPC (getUserData2017).
    payload = {
        "id": "trends-ai-server",
        "method": "getUserData2017",
        "params": [{"auth": {"clientTime": client_time, "user": user, "otp": otp}}],
        "jsonrpc": "2.0",
    }
    antwoord = http.post(
        f"{basis}/WebUntis/jsonrpc_intern.do",
        params={"m": "getUserData2017", "school": school, "v": "i2.2"},
        json=payload,
        headers={"User-Agent": useragent},
        timeout=30,
    )
    antwoord.raise_for_status()
    data = antwoord.json()
    if "error" in data:
        # Toon de exacte foutmelding van WebUntis en stop (geen nepdata).
        raise RuntimeError(f"WebUntis weigerde de secret-login: {data['error']}")

    jsessionid = http.cookies.get("JSESSIONID")
    if not jsessionid:
        raise RuntimeError("Geen JSESSIONID ontvangen; is de geheime sleutel juist?")

    # 3. personId/personType ophalen uit de app-config (zoals WebUntisSecretAuth).
    config = http.get(
        f"{basis}/WebUntis/api/app/config",
        headers={"User-Agent": useragent},
        timeout=30,
    )
    config.raise_for_status()
    gebruiker = config.json()["data"]["loginServiceConfig"]["user"]
    person_id = gebruiker["personId"]
    persoon = next((p for p in gebruiker["persons"] if p["id"] == person_id), None)
    if persoon is None:
        raise RuntimeError("Kon het persoonstype niet uit de app-config halen.")

    # 4. Sessie in de webuntis-library schuiven. Die stuurt de JSESSIONID als
    #    cookie mee bij elke verdere RPC, en my_timetable() gebruikt login_result.
    session = webuntis.Session(
        server=kale_host, school=school, username=user, useragent=useragent
    )
    session.config["jsessionid"] = jsessionid
    session.login_result = {"personId": person_id, "personType": persoon["type"]}
    return session
