# Trends in AI – gecombineerde MCP-server

Deze MCP-server brengt de drie POC's samen. Hij onthoudt **context per gebruiker**,
kan je **WebUntis-rooster** opvragen en toont je **Digitap-deadlines**.

> **Stand van zaken:** alle drie de stappen zijn klaar — basis +
> gebruikersidentificatie + context (stap 1), WebUntis-rooster (stap 2) en
> Digitap-deadlines (stap 3).

## Hoe wordt een gebruiker herkend?

MCP geeft **geen** identiteit van de Claude-gebruiker door. We identificeren de
gebruiker zelf met een **persoonlijke toegangssleutel** die bij de verbinding
meekomt, ofwel:

- als query-parameter in de URL: `http://127.0.0.1:8000/mcp?key=<sleutel>`
- of als header: `Authorization: Bearer <sleutel>`

## Waar leven de logins?

- **WebUntis**: één **gedeelde** login (uit `.env`) — het rooster is "jouw rooster".
  Wélke klas we lezen hangt af van de gebruiker (zie hieronder).
- **Digitap**: **per gebruiker** een eigen ICS-URL, bewaard in de databank op het
  gebruikersrecord (stel je in met `beheer.py`). Heeft een gebruiker er geen, dan
  valt de server terug op één **gedeelde** `DIGITAP_ICS_URL` uit `.env`.

## Onderdelen

- `server.py` – de MCP-server (officiële MCP Python SDK, HTTP-transport).
- `database.py` – SQLite-opslag (tabellen `gebruikers`, `feiten` en `deadline_status`).
- `untis.py` – WebUntis-laag: inloggen, rooster ophalen, vakken afleiden.
- `untis_login.py`, `rooster.py`, `config.py` – uit POC 1 overgenomen WebUntis-code
  (twee loginroutes, REST-rooster, en de klas → klas-ID-lijst).
- `digitap.py` – Digitap-laag: de juiste ICS-URL kiezen en de feed ophalen.
- `ics_parser.py` – uit POC 2 overgenomen ICS-parser (deadlines lezen en filteren).
- `beheer.py` – admin-CLI: gebruikers aanmaken en hun Digitap-URL instellen.
- `demo.py` – start de server en bewijst dat elke sleutel enkel zijn eigen context ziet.

## Tools

**Context (stap 1)**

- `onthoud(sleutel, waarde)` – bewaar een feit over de gebruiker (bv. `klas`, `3itai`).
- `haal_context_op()` – geef alles terug wat we over deze gebruiker weten.
- `wis_geheugen()` – wis alle feiten van deze gebruiker.
- `begroet()` – begroeting die **verschilt** naargelang de opgeslagen context.

**WebUntis (stap 2)**

- `haal_rooster(dagen=7, klas=None)` – de lessen van de komende `dagen` dagen (1–28)
  met vak, tijd en lokaal.
- `haal_vakken(klas=None)` – de vakken van de komende 4 weken, met per vak het
  eerstvolgende lesmoment en lokaal.

De `klas`-parameter is **optioneel** en kan enkel een waarde uit een **vaste lijst**
zijn (de sleutels van `config.py`, bv. `3itai`). Dat staat zo in het tool-schema als
een `enum`, zodat de LLM geen ongeldige klas kan doorgeven. `dagen` is begrensd tot
1–28. Geef je geen `klas` mee, dan valt de server terug op de context (zie hieronder).

**Digitap (stap 3)**

- `haal_deadlines(vak=None, dagen=None)` – de komende deadlines (vak, titel,
  vervaldatum, **status** en een **uid**), gesorteerd op datum. `vak` filtert op (een
  deel van) de vaknaam; `dagen` (1–365) beperkt het venster. De server leest de
  **persoonlijke** ICS-URL van de gebruiker uit de databank, of anders de **gedeelde**
  `DIGITAP_ICS_URL` uit `.env`. Lijkt de feed enkel de lopende maand te bevatten, dan
  voegt het antwoord een waarschuwing toe (pas `preset_time` in de URL aan, bv.
  `monthnow` → `recentupcoming`).
- `markeer_deadline(uid, status)` – zet de **persoonlijke status** van één deadline.
  `status` is een vaste keuze (`enum`): `nog te doen`, `mee bezig` of `klaar`. De `uid`
  krijg je uit `haal_deadlines`.

### Status per deadline (per gebruiker)

Elke gebruiker heeft per deadline een eigen status, bewaard in de databank
(tabel `deadline_status`, gekoppeld aan de stabiele ICS-`uid`). Wie niets heeft gezet,
staat op `nog te doen`. Zo kan je in een nieuw gesprek vragen *"welke deadlines heb ik
nog?"* (alles wat niet `klaar` is) en vervolgens *"markeer deze als klaar"* — de status
blijft bewaard over gesprekken heen.

### Welke klas wordt gelezen?

De WebUntis-**login** is gedeeld, maar het **rooster** verschilt per gebruiker. De
server kiest de klas in deze volgorde:

1. de `klas`-parameter als die bij de tool-call wordt meegegeven (uit de vaste lijst);
2. anders het onthouden feit `klas` (bv. nadat je `onthoud('klas', '3itai')` aanriep);
3. anders `UNTIS_KLAS` uit `.env`;
4. anders het persoonlijke studentenrooster.

De klasnaam → klas-ID-lijst staat in `config.py`. Zo beïnvloedt de **opgeslagen
context** het rooster-antwoord, terwijl de LLM dankzij de vaste keuzelijst nooit een
ongeldige klas kan doorgeven.

## Installeren

```bash
uv sync
```

## Testen (offline) en demo

```bash
uv run python test_server.py   # databanklaag + WebUntis REST-parser + ICS-parser
uv run python demo.py          # end-to-end isolatie via de echte server
```

## Zelf gebruiken

1. Maak jezelf aan als gebruiker (en geef meteen je Digitap-URL mee):

   ```bash
   uv run python beheer.py nieuw "Aron" --digitap-url "https://learning.ap.be/calendar/export_execute.php?..."
   ```

   Noteer de **toegangssleutel** die wordt getoond. (Later kun je ze aanpassen met
   `uv run python beheer.py digitap <sleutel> "<URL>"`.)

2. Kopieer `.env.example` naar `.env` en vul de **gedeelde** WebUntis-login in
   (`UNTIS_SERVER`, `UNTIS_SCHOOL`, `UNTIS_USER` en ofwel `UNTIS_PASSWORD` ofwel
   `UNTIS_SECRET`). `UNTIS_KLAS` is de standaardklas als een gebruiker er zelf geen
   heeft laten onthouden. Waar je server, schoolnaam en geheime sleutel vindt, staat
   in de README van POC 1 (`poc1_webuntis/`). `DIGITAP_ICS_URL` (optioneel) is de
   gedeelde deadline-kalender voor gebruikers zonder eigen URL; waar je die URL vindt,
   staat in de README van POC 2 (`poc2_deadlines/`).

   ```bash
   cp .env.example .env
   ```

3. Start de server:

   ```bash
   uv run python server.py
   ```

   De server luistert op `http://127.0.0.1:8000/mcp`.

### Toevoegen aan Claude Code

```bash
claude mcp add --transport http trends-ai "http://127.0.0.1:8000/mcp?key=<sleutel>"
```

of met een header:

```bash
claude mcp add --transport http trends-ai http://127.0.0.1:8000/mcp \
  --header "Authorization: Bearer <sleutel>"
```

### Toevoegen aan de MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

Kies **Transport Type: Streamable HTTP**, URL `http://127.0.0.1:8000/mcp?key=<sleutel>`
(of voeg een header `Authorization: Bearer <sleutel>` toe), en klik **Connect**.

## Draaien met Docker

Bouwen en starten op poort 8000:

```bash
docker build -t trends-ai-mcp .
docker run --rm -p 8000:8000 -v trends_ai_data:/data trends-ai-mcp
```

De server luistert dan op `http://localhost:8000/mcp`. In de container bindt hij op
`0.0.0.0` (ingesteld via `MCP_HOST`), en de SQLite-databank staat op het volume
`/data` zodat ze blijft bestaan tussen herstarts.

Een gebruiker aanmaken in de draaiende container (schrijft naar hetzelfde volume):

```bash
docker exec -it <container> uv run --no-sync python beheer.py nieuw "Aron" \
  --digitap-url "<jouw-ICS-URL>"
```

De (gedeelde) WebUntis-instellingen voor stap 2 geef je later mee met
`--env-file .env` of losse `-e`-vlaggen bij `docker run`.

## Geheimen

`.env` en `*.sqlite` staan in `.gitignore`. Toegangssleutels en Digitap-URL's leven
in de databank; zet ze nooit in code, README of logs.
