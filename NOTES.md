# NOTES – Trends in AI, labo 3

Korte wrap-up van de drie POC's en de start van de gecombineerde MCP-server.
Per onderdeel: wat werkte, wat niet, en wat we nodig hebben om samen te voegen.

## Omgeving (geldt voor alles)
- Geen systeem-Python; we gebruiken **`uv`**. Elke map is een **los uv-project met
  eigen `.venv`**.
- **Valkuil:** `uv init` in een submap voegt die toe als *workspace member* aan
  `02_labo/pyproject.toml`; een `uv sync` wist dan de gedeelde ML-omgeving
  (torch/datasets/transformers). Daarom: `pyproject.toml` **met de hand** maken en
  `uv add`/`uv sync` gebruiken. (Dit is één keer misgegaan en hersteld.)
- Draaien kan altijd met `uv run --directory <map> python <script>`.

## POC 1 – WebUntis (`poc1_webuntis/`)
**Werkt.** Toont de vakken van een klas met per vak het eerstvolgende lesmoment + lokaal.
- Twee loginroutes: wachtwoord (library `webuntis`) en geheime sleutel/TOTP (zelf
  nagebouwd zoals npm `webuntis`/WebUntisSecretAuth: `getUserData2017` + JSESSIONID +
  personId/personType via `/api/app/config`).
- **Wat niet werkte:** de klassieke `getTimetable`-RPC geeft bij AP Hogeschool
  `-8509 "no right for timetable"` voor studenten — óók voor het klasrooster. De
  officiële Platform API (developer.untis.com) is enkel voor partners.
- **Oplossing:** rooster via de **REST-API**
  `/WebUntis/api/public/timetable/weekly/data` met de JSESSIONID van de login.
- **Voor samenvoegen:** gedeelde login in `.env`; klas-ID's in `config.py`
  (`3itai: 10247`); herbruik `untis_login.py` + `rooster.py`. Login is relatief traag
  → later eventueel de sessie cachen i.p.v. per tool-call opnieuw inloggen.

## POC 2 – Digitap/Moodle deadlines (`poc2_deadlines/`)
**Werkt.** Toont komende deadlines (vak, titel, vervaldatum) in Europe/Brussels.
- `icalendar` 7.x: `SUMMARY`=titel, `CATEGORIES.cats[0]`=vak, `DTSTART`=vervaldatum
  (datetime in UTC óf kale datum). Filters `--vak` en `--dagen`.
- **Wat opviel:** `preset_time=monthnow` in de export-URL beperkt de feed tot de
  lopende maand → het script **waarschuwt** daarvoor (tip: `recentupcoming`).
- **Voor samenvoegen:** de ICS-URL is **persoonlijk** → per gebruiker opslaan (niet
  in `.env`). Herbruik `ics_parser.py`.

## POC 3 – Context per gebruiker (`poc3_context/`)
**Werkt.** Minimale MCP-server die context per gebruiker onthoudt; de demo bewijst
isolatie tussen twee gebruikers.
- **Belangrijk:** MCP geeft **geen** identiteit van de Claude-gebruiker door. We
  identificeren zelf met een **persoonlijke sleutel** (in `?key=` of
  `Authorization: Bearer`). De server mapt sleutel → gebruiker.
- **SDK-verrassing:** de MCP Python SDK is **2.x**; `FastMCP` heet nu `MCPServer`
  (`from mcp.server.mcpserver import MCPServer, Context`). Headers via `ctx.headers`,
  query via `ctx.request_context.request.query_params`. Client:
  `streamable_http_client(url)` levert `(read, write)`.
- Opslag: SQLite; nieuwe verbinding per call (thread-safe t.o.v. de server-threads).

## Gecombineerde server (`mcp_server/`) – stap 1 klaar
Fundering: MCP-basis + gebruikersidentificatie (sleutel) + contexttools
(`onthoud`, `haal_context_op`, `wis_geheugen`, `begroet`). Gebruikers beheer je met
`beheer.py`. Datamodel al klaar voor de rest:
- **WebUntis**: gedeelde login uit `.env` (stap 2, nog te doen).
- **Digitap**: per-gebruiker ICS-URL op het gebruikersrecord in SQLite (stap 3, nog
  te doen).

**Nog te doen:** stap 2 (WebUntis-tools met `rooster.py`), stap 3 (Digitap-tools met
`ics_parser.py` en de per-gebruiker URL).
