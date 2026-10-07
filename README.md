# Studiecoach — MCP-server als contextgeheugen

Een klein schoolprototype voor een opdracht over **contextgebruik in AI**.
Claude Desktop is het chatvenster en het taalmodel; onze Python-server houdt de
**context** bij en biedt die aan via MCP-tools. Zo kunnen we aantonen dat
dezelfde vraag — *"Wat moet ik nu doen?"* — een ander antwoord geeft naargelang
de context.

Gemaakt door twee studenten. Bewust klein en leesbaar gehouden.

## Hoe het werkt: geheugen + rooster

De server combineert twee lagen:

**1. Het contextgeheugen** — de klasse `ContextMemory` (in `context_memory.py`),
schrijfbaar, met drie sublagen:

1. **Sessie** — acties van de huidige draaironde van de server. Leeft alleen in
   het geheugen en is dus **leeg na elke herstart**.
2. **Geschiedenis** — deadlines, zwakke punten en een studielog. Wordt
   bewaard in `geheugen.json` en blijft dus **over sessies heen** bestaan.
3. **Omgeving** — wordt bij **elke aanvraag opnieuw berekend**: datum, weekdag,
   uur, dagdeel, dagen tot elke deadline en welke deadlines voorbij zijn.

**2. Het lessenrooster** — de klasse `Rooster` (in `rooster.py`), **read-only**.
Zij leest de WebUntis-exports van onze twee klassen in — `3ITAI.json` en
`4VTAI.json` (één week, 2026-10-05 t/m 2026-10-09) — en zet elke les om naar één
genormaliseerd record (vak, lokaal, docent, lesvorm, start/eind, medeklassen).
Daarmee beantwoordt de coach vragen als "welke les heb ik nu?", "wat is mijn
volgende les?", "welke lessen heb ik vandaag / binnen X uur?" en "wanneer krijg
ik vak Y?". De **vakkenlijst wordt hieruit afgeleid** (dus niet apart bijgehouden).

Beide lagen delen hetzelfde "huidige" tijdstip. Dat is overschrijfbaar via de
omgevingsvariabele `STUDIECOACH_NU` (ISO-formaat, bv. `2026-10-07T10:30`), zodat
we in een demo of test een vast moment binnen de roosterweek kunnen simuleren.

## Installatie

Vereist: Python 3.10+ en [uv](https://docs.astral.sh/uv/).

```bash
# In de projectmap:
uv sync
```

Dit installeert de enige dependency, de officiële MCP Python SDK (`mcp[cli]`),
plus `pytest` voor de tests.

## De vakken en de deadlines

De **vakken** van onze twee klassen (**3ITAI** en **4VTAI**) worden rechtstreeks
uit de lesroosters (`3ITAI.json` / `4VTAI.json`) afgeleid — er is dus geen aparte
vakkenlijst die uit sync kan lopen. Vraag ze op met `vakken_in_rooster`.

Elke klas heeft eigen vakken, maar sommige zijn **gedeeld** (ze zitten in beide
klassen): `Trends in AI`, `AI and Society` en `AI for Business`. Die worden als
"gedeeld" gemarkeerd.

De **deadlines** zitten in `seed_geheugen.json` (samen met enkele zwakke punten
en een studielog) — zelf gemaakte, realistische deadlines verspreid over beide
klassen, met het zwaartepunt rond de roosterweek. Een deadline hoort bij een
specifieke klas, want een gedeeld vak kan per klas een andere deadline hebben
(zie `Trends in AI` in de seed). `haal_context_op` toont alles netjes gegroepeerd
per klas, zodat de twee niet door elkaar lopen.

## Beschikbare tools

Alle tools geven leesbare Nederlandstalige tekst terug.

**Context**
- `haal_context_op` — roep dit altijd eerst aan: omgeving (nu), rooster (les
  nu/straks/vandaag), bewaarde geschiedenis en de sessie, in één blok.
- `wat_nu` — kort advies: wat loopt er nu (of wat is de volgende les), de
  dichtstbijzijnde deadline en een eventueel bijbehorend zwak punt.

**Rooster (read-only)**
- `les_nu` — welke les loopt er nu? (optioneel per klas)
- `volgende_les` — de eerstvolgende les.
- `lessen_vandaag` — alle lessen van vandaag.
- `lessen_op_dag(datum)` — lessen op een bepaalde dag (JJJJ-MM-DD).
- `lessen_binnen_uren(uren)` — lessen die binnen X uur starten.
- `rooster_week` — het volledige rooster van de week.
- `wanneer_vak(vak)` — alle momenten van een vak (over beide klassen).
- `vakken_in_rooster` — de vakkenlijst, met gedeelde vakken gemarkeerd.

**Deadlines bevragen (read-only)**
- `komende_deadlines(dagen?)` — wat komt er nog aan (optionele horizon in dagen).
- `deadlines_vandaag` — wat vervalt vandaag.
- `verlopen_deadlines` — wat is al voorbij.
- `deadlines_voor_vak(vak)` — deadlines van één vak.
- `deadlines_voor_klas(klas)` — deadlines van één klas.

**Geheugen bijwerken (schrijvend)**
- `voeg_deadline_toe`, `voeg_vak_toe`, `markeer_zwak_punt`, `markeer_beheerst`,
  `log_studiesessie`, `wis_geheugen`.

Een `klas`-argument is telkens optioneel en filtert op `3ITAI` of `4VTAI`.

## Default data (seed)

Hoe het werkt: zodra er nog geen `geheugen.json` bestaat, laadt `ContextMemory`
de inhoud van `seed_geheugen.json`. De eerste schrijfactie maakt dan het echte
`geheugen.json` aan (dat staat in `.gitignore`, zodat je live data niet in git
belandt). De seed zelf wordt nooit overschreven.

Wil je terug naar de default? Verwijder gewoon het live bestand:

```bash
rm geheugen.json        # lokaal (stdio)
rm data/geheugen.json   # Docker-volume
```

> In de demo en de tests wordt de seed bewust overgeslagen
> (`ContextMemory(..., seed_pad=None)`), zodat die een schone, voorspelbare
> start houden.

## De demo (zonder Claude Desktop)

```bash
uv run demo.py
```

Dit speelt drie momenten na en drukt na elk moment de context af:

- **maandag 10u** — vakken en een deadline toevoegen;
- **donderdag 22u** — nieuwe sessie, één dag vóór de deadline;
- **zaterdag 14u** — de deadline is voorbij.

Je ziet de omgevingslaag mee veranderen ("over 4 dagen" → "over 1 dag" →
"VOORBIJ") terwijl de geschiedenis bewaard blijft en de sessielaag bij elke
nieuwe sessie weer leeg start.

## De tests

```bash
uv run pytest
```

Test onder meer: opslaan en opnieuw laden, lege sessie na herstart, correcte
"dagen tot deadline" en herkenning van een verlopen deadline.

## Registreren in Claude Desktop

1. Zoek het configuratiebestand `claude_desktop_config.json`:
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

   (Makkelijkste weg: Claude Desktop → Settings → Developer → *Edit Config*.)

2. Voeg onze server toe. Gebruik een **absoluut pad** naar de projectmap en laat
   `uv` de server starten.

   **macOS / Linux:**

   ```json
   {
     "mcpServers": {
       "studiecoach": {
         "command": "uv",
         "args": [
           "--directory",
           "/home/kruimol/school/2026-2027/trents_in_AI/02_labo/labo_3",
           "run",
           "server.py"
         ]
       }
     }
   }
   ```

   **Windows:**

   ```json
   {
     "mcpServers": {
       "studiecoach": {
         "command": "uv",
         "args": [
           "--directory",
           "C:\\Users\\kruimol\\studiecoach",
           "run",
           "server.py"
         ]
       }
     }
   }
   ```

   > Pas het pad aan naar jouw projectmap. Als `uv` niet op het systeem-PATH
   > van Claude Desktop staat, gebruik dan het volledige pad naar `uv`
   > (bv. `C:\\Users\\<naam>\\.local\\bin\\uv.exe` of `/home/<naam>/.local/bin/uv`).

3. **Sluit Claude Desktop volledig af en herstart het** (op Windows: ook via het
   systeemvak, niet enkel het venster sluiten). De server verschijnt daarna bij
   de tools (het schuifje / hamerpictogram in het chatvenster).

## Demoscenario in Claude Desktop

Stel Claude deze vragen na elkaar (in deze volgorde):

1. *"Ik zit in 4VTAI. Voor AI programming heb ik volgende week een examen en
   async in Python snap ik nog niet goed."*
   → Claude roept `voeg_vak_toe` (met klas `4VTAI`), `voeg_deadline_toe` en
   `markeer_zwak_punt` aan.
2. *"Wat moet ik nu doen?"*
   → Claude roept eerst `haal_context_op` aan en antwoordt rekening houdend met
   de deadline en het zwakke punt.
3. *"Ik heb net 90 minuten aan integralen gewerkt en snap het nu."*
   → Claude roept `log_studiesessie` en `markeer_beheerst` aan.
4. *"En nu, wat moet ik doen?"*
   → Opnieuw `haal_context_op`; het antwoord is nu anders (integralen is weg uit
   de zwakke punten, er staat een studiesessie in het log).

Simuleer desnoods een ander moment door Claude Desktop te starten met
`STUDIECOACH_NU` gezet (bv. een dag ná de deadline), of pas de datum in de
vragen aan.

## "Context uit" tonen

Om te laten zien wat context toevoegt, schakel je de connector uit:
**Settings → Connectors / Developer → zet `studiecoach` uit** (of verwijder het
blok tijdelijk uit `claude_desktop_config.json` en herstart Claude Desktop).
Stel dan opnieuw de vraag *"Wat moet ik nu doen?"*. Zonder onze server heeft
Claude geen weet van je vakken, deadlines of zwakke punten en geeft het een
algemeen, context-loos antwoord. Zet de connector weer aan voor het verschil.

## Twee manieren van draaien: stdio vs. HTTP

De server kan op twee transporten draaien, gestuurd door de omgevingsvariabele
`STUDIECOACH_TRANSPORT`:

- **`stdio`** (standaard) — Claude Desktop start de server lokaal als los proces.
  Dit is wat hierboven beschreven staat.
- **`http`** — de server luistert op een poort via *streamable-HTTP*. Zo kan je
  hem in een container draaien en achter een domein deployen, en toevoegen als
  **remote connector** (via een URL) in plaats van een lokaal commando.

Relevante omgevingsvariabelen voor HTTP-modus:

| Variabele | Standaard | Betekenis |
|---|---|---|
| `STUDIECOACH_TRANSPORT` | `stdio` | Zet op `http` om over een poort te serveren. |
| `STUDIECOACH_HOST` | `127.0.0.1` | Interface om op te binden (in Docker `0.0.0.0`). |
| `STUDIECOACH_PORT` | `8000` | Poort. |
| `STUDIECOACH_ALLOWED_HOSTS` | *(leeg)* | Komma-gescheiden lijst van toegelaten `Host`-headers (bv. je domein). Leeg = DNS-rebinding-controle uit. |
| `STUDIECOACH_GEHEUGEN` | naast `server.py` | Pad naar `geheugen.json` (in Docker een volume). |

Het HTTP-eindpunt is altijd `/mcp` (dus bv. `http://localhost:8000/mcp`).

## Deployen met Docker

De `Dockerfile` bouwt de server en draait hem in HTTP-modus op poort 8000.

```bash
# Bouwen en starten (data komt in ./data dankzij het volume):
docker compose up --build
# → server luistert op http://localhost:8000/mcp
```

Of zonder compose:

```bash
docker build -t studiecoach .
docker run -p 8000:8000 -v "$(pwd)/data:/app/data" studiecoach
```

`geheugen.json` wordt in `/app/data` geschreven; door die map als volume te
koppelen blijft de data bewaard over herstarts heen.

### Op je eigen domein

Remote MCP-connectoren vereisen **HTTPS**. Zet daarom een reverse proxy met TLS
vóór de container (bv. Caddy, Nginx of Traefik) die `https://jouwdomein/mcp`
doorstuurt naar de container op poort 8000. Voorbeeld met Caddy (`Caddyfile`):

```
studiecoach.jouwdomein.be {
    reverse_proxy localhost:8000
}
```

Geef je domein dan mee zodat de `Host`-controle het aanvaardt:

```bash
STUDIECOACH_ALLOWED_HOSTS=studiecoach.jouwdomein.be docker compose up --build
```

(Of laat `STUDIECOACH_ALLOWED_HOSTS` leeg als de container enkel via de proxy
bereikbaar is; dan staat de DNS-rebinding-controle uit.)

### Toevoegen als remote connector

In Claude Desktop / claude.ai: **Settings → Connectors → Add custom connector**,
en geef de URL `https://studiecoach.jouwdomein.be/mcp` op. Daarna verschijnen
dezelfde tools, maar nu vanaf je server in plaats van lokaal.

> Let op: in HTTP-modus is er **één gedeeld `geheugen.json`** voor iedereen die
> verbindt. Voor dit schoolprototype is dat prima; het is geen gebruikersgescheiden
> opslag.

## Bestandsoverzicht

| Bestand | Rol |
|---|---|
| `context_memory.py` | De klasse `ContextMemory` met de drie lagen en JSON-opslag. |
| `rooster.py` | De klasse `Rooster`: leest de lesroosters read-only in en bevraagt ze. |
| `server.py` | De MCP-server met alle tools rond `ContextMemory` en `Rooster`. |
| `3ITAI.json`, `4VTAI.json` | De WebUntis-lesroosters van de twee klassen (één week). |
| `demo.py` | Speelt drie momenten na zonder Claude Desktop. |
| `test_context_memory.py` | Pytest-tests voor `ContextMemory`. |
| `test_rooster.py` | Pytest-tests voor `Rooster`. |
| `seed_geheugen.json` | Default startdata (deadlines + zwakke punten + studielog); wordt ingeladen bij een verse start. |
| `geheugen.json` | Wordt automatisch aangemaakt; de persistente geschiedenis (gitignored). |
| `reflectie.md` | Reflectievragen (inhoud schrijven we zelf). |
| `Dockerfile` | Bouwt de server en draait hem in HTTP-modus op poort 8000. |
| `docker-compose.yml` | Start de container met een volume voor de data. |
| `.dockerignore` | Houdt lokale rommel en data uit de image. |
