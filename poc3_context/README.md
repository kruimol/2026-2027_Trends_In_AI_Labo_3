# POC 3 – Context per gebruiker in een MCP-server

Deze proof of concept is een minimale **MCP-server** die bewijst dat hij per
gebruiker context kan **onthouden**, en dat die context het antwoord **beïnvloedt**.

## Hoe identificeren we de gebruiker?

Belangrijk: MCP geeft **geen** gebruikers-ID van Claude door aan de server. We
identificeren de gebruiker daarom zelf met een **persoonlijke toegangssleutel** die
bij de verbinding wordt meegegeven. Dat kan op twee manieren (allebei ondersteund):

- als query-parameter in de URL: `http://127.0.0.1:8000/mcp?key=<sleutel>`
- of als header: `Authorization: Bearer <sleutel>`

De server zoekt bij die sleutel de juiste gebruiker op in de databank.

## Onderdelen

- `server.py` – de MCP-server (officiële MCP Python SDK, HTTP-transport).
- `database.py` – SQLite-opslag (tabellen `gebruikers` en `feiten`).
- `maak_gebruiker.py` – maakt een gebruiker aan en toont zijn sleutel.
- `demo.py` – start de server en toont dat twee sleutels elk hun eigen context zien.

## Tools

- `onthoud(sleutel, waarde)` – bewaar een feit over de gebruiker (bv. `klas`, `3itai`).
- `haal_context_op()` – geef alles terug wat we over deze gebruiker weten.
- `wis_geheugen()` – wis alle feiten van deze gebruiker.
- `begroet()` – een begroeting die **verschilt** naargelang de opgeslagen context.

De toolbeschrijvingen zijn zo geschreven dat Claude uit zichzelf `haal_context_op`
aanroept aan het begin van een gesprek, en `onthoud` wanneer je iets over jezelf
vertelt.

## Installeren

```bash
uv sync
```

## Demo (bewijst isolatie, zonder externe client)

```bash
uv run python demo.py
```

Dit start de server, maakt twee gebruikers (Aron en Lotte) aan met elk een eigen
sleutel, en toont dat Aron enkel zijn eigen klas ziet en Lotte de hare.

## Zelf gebruiken

1. Maak een gebruiker aan en noteer de sleutel:

   ```bash
   uv run python maak_gebruiker.py "Aron"
   ```

2. Start de server:

   ```bash
   uv run python server.py
   ```

   De server luistert op `http://127.0.0.1:8000/mcp`.

### Toevoegen aan Claude Code

Met de sleutel in de URL:

```bash
claude mcp add --transport http trends-ai-context "http://127.0.0.1:8000/mcp?key=<sleutel>"
```

Of met een header in plaats van de URL-sleutel:

```bash
claude mcp add --transport http trends-ai-context http://127.0.0.1:8000/mcp \
  --header "Authorization: Bearer <sleutel>"
```

Vraag daarna in Claude Code bijvoorbeeld *"begroet me"* of vertel *"ik zit in klas
3itai"* – Claude roept dan `begroet` / `onthoud` aan.

### Toevoegen aan de MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

Kies **Transport Type: Streamable HTTP**, en als URL
`http://127.0.0.1:8000/mcp?key=<sleutel>` (of voeg onder *Authentication* een header
`Authorization: Bearer <sleutel>` toe). Klik **Connect** en test de tools.

## Geheimen

`.env` staat in `.gitignore` en bevat geen sleutels. De toegangssleutels zelf staan
in de SQLite-databank (`*.sqlite`, ook in `.gitignore`); deel ze niet.
