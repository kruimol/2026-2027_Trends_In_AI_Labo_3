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

## Gecombineerde server (`mcp_server/`) – alle stappen klaar
Fundering: MCP-basis + gebruikersidentificatie (sleutel) + contexttools
(`onthoud`, `haal_context_op`, `wis_geheugen`, `begroet`). Gebruikers beheer je met
`beheer.py`. Logins:
- **WebUntis**: gedeelde login uit `.env`.
- **Digitap**: per-gebruiker ICS-URL op het gebruikersrecord in SQLite, met terugval
  op een gedeelde `DIGITAP_ICS_URL` uit `.env`.

**Stap 2 (WebUntis) – klaar.** POC 1-code herbruikt (`untis_login.py`, `rooster.py`,
`config.py`) en samengebonden in `untis.py`. Twee tools: `haal_rooster(dagen=7, klas)`
en `haal_vakken(klas)`.
- **Vaste + dynamische parameters:** `klas` is een gesloten keuzelijst (Literal/enum
  afgeleid uit `config.KLASSEN`) zodat de LLM geen ongeldige klas kan doorgeven;
  `dagen` is begrensd tot 1–28. Beide optioneel.
- **Context beïnvloedt het antwoord:** klas-keuze = meegegeven `klas` > onthouden feit
  `klas` > `UNTIS_KLAS` uit `.env` > persoonlijk studentenrooster. Zo hangt het rooster
  van de opgeslagen context af wanneer er geen klas wordt meegegeven.
- **Keuze:** login per tool-call (eenvoudig/veilig), telkens netjes uitloggen. Login
  is traag → sessie cachen kan later een optimalisatie zijn.
- Offline bewijs: `test_server.py` test nu óók de REST-parser met dezelfde fixture
  als POC 1.

**Stap 3 (Digitap) – klaar.** POC 2-code herbruikt (`ics_parser.py` + `voorbeeld.ics`),
ophalen in `digitap.py`. Eén tool: `haal_deadlines(vak=None, dagen=None)`.
- **Per gebruiker én gedeeld:** de ICS-URL komt per gebruiker uit de databank; is die
  er niet, dan valt de server terug op de gedeelde `DIGITAP_ICS_URL` uit `.env`. Zo
  werkt zowel "één kalender" als "een kalender per gebruiker".
- `dagen` begrensd tot 1–365; `vak` is een vrije substring-filter (vakken komen uit de
  feed, dus geen vaste lijst mogelijk zoals bij de klas).
- Waarschuwt (in het antwoord) als de feed enkel de lopende maand lijkt te bevatten.
- Offline bewijs in `test_server.py` (parser + filters met `voorbeeld.ics`); end-to-end
  getest tegen een lokale HTTP-feed → tool haalt, parset en filtert correct.

**Status per deadline (per gebruiker).** Tweede tool `markeer_deadline(uid, status)` met
een vaste statuslijst (`nog te doen` / `mee bezig` / `klaar`, als enum in het schema).
- Status hangt aan de stabiele ICS-`uid`, opgeslagen in tabel `deadline_status` (per
  gebruiker). `haal_deadlines` toont per deadline de status (default `nog te doen`) + uid.
- Zo kan iemand in een nieuw gesprek vragen wat nog openstaat en een deadline als klaar
  (laten) markeren; de status blijft bewaard. Getest offline (scheiding per gebruiker) en
  end-to-end (markeren blijft bewaard over aanroepen heen).
