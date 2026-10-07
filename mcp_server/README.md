# Trends in AI – gecombineerde MCP-server

Deze MCP-server brengt de drie POC's samen. Hij onthoudt **context per gebruiker**
en zal (in volgende stappen) ook je **WebUntis-rooster** en je **Digitap-deadlines**
kunnen opvragen.

> **Stand van zaken:** stap 1 (basis + gebruikersidentificatie + context) is klaar.
> Stap 2 (WebUntis) en stap 3 (Digitap) volgen.

## Hoe wordt een gebruiker herkend?

MCP geeft **geen** identiteit van de Claude-gebruiker door. We identificeren de
gebruiker zelf met een **persoonlijke toegangssleutel** die bij de verbinding
meekomt, ofwel:

- als query-parameter in de URL: `http://127.0.0.1:8000/mcp?key=<sleutel>`
- of als header: `Authorization: Bearer <sleutel>`

## Waar leven de logins?

- **WebUntis**: één **gedeelde** login (uit `.env`) — het rooster is "jouw rooster".
  (Wordt in stap 2 gebruikt.)
- **Digitap**: **per gebruiker** een eigen ICS-URL, bewaard in de databank op het
  gebruikersrecord (stel je in met `beheer.py`). (Wordt in stap 3 gebruikt.)

## Onderdelen

- `server.py` – de MCP-server (officiële MCP Python SDK, HTTP-transport).
- `database.py` – SQLite-opslag (tabellen `gebruikers` en `feiten`).
- `beheer.py` – admin-CLI: gebruikers aanmaken en hun Digitap-URL instellen.
- `demo.py` – start de server en bewijst dat elke sleutel enkel zijn eigen context ziet.

## Tools (stap 1)

- `onthoud(sleutel, waarde)` – bewaar een feit over de gebruiker (bv. `klas`, `3itai`).
- `haal_context_op()` – geef alles terug wat we over deze gebruiker weten.
- `wis_geheugen()` – wis alle feiten van deze gebruiker.
- `begroet()` – begroeting die **verschilt** naargelang de opgeslagen context.

## Installeren

```bash
uv sync
```

## Testen (offline) en demo

```bash
uv run python test_server.py   # databanklaag (scheiding + Digitap-URL)
uv run python demo.py          # end-to-end isolatie via de echte server
```

## Zelf gebruiken

1. Maak jezelf aan als gebruiker (en geef meteen je Digitap-URL mee):

   ```bash
   uv run python beheer.py nieuw "Aron" --digitap-url "https://learning.ap.be/calendar/export_execute.php?..."
   ```

   Noteer de **toegangssleutel** die wordt getoond. (Later kun je ze aanpassen met
   `uv run python beheer.py digitap <sleutel> "<URL>"`.)

2. Kopieer `.env.example` naar `.env` (de WebUntis-velden mag je nu nog leeg laten;
   die zijn voor stap 2):

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
