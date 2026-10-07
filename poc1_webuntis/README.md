# POC 1 – WebUntis: mijn vakken ophalen

Deze proof of concept logt in op WebUntis met **jouw eigen studentenaccount** en
toont de lijst van je vakken, afgeleid uit je rooster van de **komende 4 weken**.
Per vak zie je het eerstvolgende lesmoment met lokaal.

We gebruiken bewust de **oudere, niet-officiële API** (niet de Untis Platform API
van developer.untis.com, want die is enkel voor integratiepartners). Inloggen
gebeurt via JSON-RPC; het rooster zelf halen we via de REST-API (zie hieronder).

## Twee loginroutes

Je school gebruikt mogelijk Microsoft-SSO; dan werkt een gewoon wachtwoord niet.
Daarom zijn er twee routes, gekozen via `.env`:

1. **Gebruikersnaam + wachtwoord** – via de Python-library `webuntis`.
2. **Gebruikersnaam + geheime sleutel** – de sleutel achter de QR-code in je
   WebUntis-profiel. Per login wordt daaruit een eenmalige code (TOTP) berekend.
   Dit is nagebouwd zoals het npm-pakket `webuntis` (WebUntisSecretAuth) en het
   project toughIQ/webuntis-mcp het doen.

Staat `UNTIS_SECRET` ingevuld, dan wordt route 2 gebruikt; anders route 1.

## Welk rooster lezen we, en hoe?

We lezen standaard het **klasrooster** (bv. van `3itai`). Het toont álle lessen
van de klas; bij gesplitste keuzegroepen is dat iets ruimer dan je eigen pakket —
voor deze POC is dat prima. Je kiest de klas met `UNTIS_KLAS` in `.env`; de
bijhorende klas-ID staat in `config.py`. Laat `UNTIS_KLAS` leeg om je persoonlijke
rooster te proberen (student-ID, werkt enkel als de school dat toestaat).

**Belangrijk – waarom de REST-API?** De klassieke `getTimetable` (JSON-RPC) geeft
bij veel scholen de fout `-8509 "no right for timetable"` voor studenten – ook
voor het klasrooster. Daarom halen we het rooster via de REST-API
`/WebUntis/api/public/timetable/weekly/data` (`rooster.py`). Die gebruikt dezelfde
rechten als de WebUntis-website en werkt daardoor meestal wél, met dezelfde
JSESSIONID-cookie die we bij het inloggen al kregen.

> Zie je je rooster wél op <https://webuntis.com> in de browser, dan werkt deze
> REST-aanpak ook. Zie je het daar óók niet, dan is het puur een rechtenkwestie en
> moet je schoolbeheerder je account de nodige rechten geven.

## Klas-ID's opzoeken

Weet je het klas-ID niet? Draai het hulpscript; het schrijft alle klassen met hun
ID naar `klassen.json`:

```bash
uv run python klassen_export.py
```

## Installeren

Dit mapje is een los `uv`-project met een eigen virtuele omgeving:

```bash
uv sync
```

## Testen zonder login (offline)

Bewijst dat het verwerken van het rooster klopt, zonder netwerk of gegevens:

```bash
uv run python test_vakken.py
```

## Echt draaien

1. Kopieer `.env.example` naar `.env` en vul je gegevens in:

   ```bash
   cp .env.example .env
   ```

2. Vul in `.env` in:
   - `UNTIS_SERVER` en `UNTIS_SCHOOL` (zie hieronder waar je die vindt),
   - `UNTIS_USER` (je studentengebruikersnaam),
   - **ofwel** `UNTIS_PASSWORD` **ofwel** `UNTIS_SECRET`,
   - `UNTIS_KLAS` (bv. `3itai`): welke klas-rooster we lezen.

3. Zorg dat je klas in `config.py` staat (naam → klas-ID), bv. `"3itai": 10247`.
   Pas die lijst gerust aan. Klas-ID's zijn geen geheim.

4. Draai:

   ```bash
   uv run python vakken.py
   ```

Lukt de login niet, dan toont het script de **exacte foutmelding** van WebUntis
en stopt het. Er wordt geen nepdata getoond.

## Waar vind ik server, schoolnaam en geheime sleutel?

- **Server + schoolnaam**: ga naar <https://webuntis.com>, zoek je school en log
  in. Kijk daarna naar de URL in je browser, bv.
  `https://mese.webuntis.com/WebUntis/?school=mijn-school#/basic/login`.
  - `UNTIS_SERVER` = het stuk vóór `/WebUntis` → hier `mese.webuntis.com`.
  - `UNTIS_SCHOOL` = de waarde van `?school=` → hier `mijn-school`.
- **Geheime sleutel** (voor route 2): log in op WebUntis in de browser en ga naar
  **Profiel → Toegangsgegevens / Freigaben**. Klik bij *Twee-factor-authenticatie*
  of *Untis Mobile* op **"QR-code weergeven"**. Naast de QR-code staat een
  **geheime sleutel** (een reeks letters/cijfers). Dat is de waarde voor
  `UNTIS_SECRET`. (De QR-code zelf bevat exact diezelfde sleutel.)

## Geheimen

`.env` staat in `.gitignore` en wordt nooit ingeleverd. Zet nooit een echt
wachtwoord of sleutel in de code, in `.env.example` of in de uitvoer/logs.
