# OVERVIEUW – Context is King (Trends in AI, labo 3)

**Opdracht:** *Context is King – analyse/prototype rond MCP en contextgebruik in AI*
(Hassan Haddouchi)
**Gekozen werkvorm:** **Optie B – prototype** (groepje van 2 studenten)
**Wat het is:** een persoonlijke schoolassistent, gebouwd als een échte
**MCP-server** (`trends-ai`) die Claude koppelt aan je schoolleven — rooster,
deadlines en een persoonlijk geheugen, per gebruiker gescheiden.

> Dit document is het overkoepelende inleverdocument. Het technische logboek per
> deelstap staat in [`NOTES.md`](NOTES.md); de setup- en draai-instructies in
> [`mcp_server/README.md`](mcp_server/README.md).

---

## 1. Wat we gebouwd hebben

In plaats van context te *simuleren* (bv. een lijstje hardcoden in een prompt) hebben
we het **Model Context Protocol zelf geïmplementeerd**. De assistent is een
MCP-server die acht tools aanbiedt aan Claude. Claude roept die tools aan om:

- te **onthouden** wie de gebruiker is (naam, klas, studiejaar, voorkeuren);
- het **lesrooster** op te halen uit WebUntis;
- de **deadlines** op te halen uit de Digitap/Moodle-kalender en hun status bij te
  houden.

De context (het geheugen) wordt **per gebruiker** bewaard in een SQLite-databank en
beïnvloedt rechtstreeks wat de tools teruggeven — precies wat de opdracht vraagt.

---

## 2. Hoe we het aangepakt hebben: 3 POC's → één server

We bouwden eerst drie losse proof-of-concepts en voegden die daarna samen. Het detail
(wat werkte, wat niet) staat in [`NOTES.md`](NOTES.md).

| Stap | Map | Resultaat |
|------|-----|-----------|
| POC 1 | [`poc1_webuntis/`](poc1_webuntis/) | Rooster + vakken ophalen uit WebUntis |
| POC 2 | [`poc2_deadlines/`](poc2_deadlines/) | Deadlines parsen uit een ICS-kalender |
| POC 3 | [`poc3_context/`](poc3_context/) | Per-gebruiker contextgeheugen via MCP |
| Samen | [`mcp_server/`](mcp_server/) | Alle drie gecombineerd in één MCP-server |

**Omgeving:** Python 3.12, beheerd met `uv`. Elke map is een los `uv`-project met een
eigen `.venv`.

---

## 3. Architectuur

```
        ┌─────────────────────────────────────┐
        │              Claude                 │   MCP-client
        └───────────────────┬─────────────────┘
                            │  toegangssleutel
                            │  (?key=<…>  of  Authorization: Bearer <…>)
        ┌───────────────────▼─────────────────┐
        │     MCP-server  (server.py)         │   transport: streamable-http
        │     "trends-ai", SDK mcp>=2         │   http://127.0.0.1:8000/mcp
        └───────┬───────────────┬─────────────┘
                │               │               │
      ┌─────────▼────┐  ┌───────▼──────┐  ┌─────▼────────────┐
      │ database.py  │  │  untis.py    │  │  digitap.py      │
      │ SQLite       │  │  WebUntis    │  │  ICS-kalender    │
      │ (3 tabellen) │  │  REST-API    │  │  (Moodle/Digitap)│
      └──────────────┘  └──────────────┘  └──────────────────┘
```

**Gebruikersidentificatie.** MCP geeft géén identiteit van de Claude-gebruiker door.
We lossen dat op met een **persoonlijke toegangssleutel** die bij de verbinding
meekomt (als `?key=` in de URL of als `Authorization: Bearer`). De server mapt sleutel
→ gebruiker ([`server.py:49`](mcp_server/server.py)). Een onbekende sleutel maakt
automatisch een nieuwe gebruiker aan.

**Kernbestanden** (in [`mcp_server/`](mcp_server/)):

| Bestand | Rol |
|---------|-----|
| `server.py` | De MCP-server + de 8 tools |
| `database.py` | SQLite-opslag (gebruikers, feiten, deadline-status) |
| `config.py` | Klas → WebUntis-ID (gesloten keuzelijst) |
| `untis.py` + `untis_login.py` + `rooster.py` | WebUntis-integratie |
| `digitap.py` + `ics_parser.py` | Deadline-integratie |
| `beheer.py` | Admin-CLI om gebruikers te beheren |
| `demo.py` | End-to-end demo die isolatie tussen gebruikers bewijst |
| `test_server.py` | Offline unit-tests |

---

## 4. De 8 MCP-tools

**Context / geheugen**

| Tool | Parameters | Doel |
|------|------------|------|
| `onthoud` | `sleutel`, `waarde` | Bewaar één feit over de gebruiker (bv. `onthoud('klas','3itai')`). |
| `haal_context_op` | – | Geef alle bewaarde feiten terug (aan het begin van een gesprek). |
| `wis_geheugen` | – | Wis alle feiten van de gebruiker. |
| `begroet` | – | Begroet de gebruiker; het antwoord verschilt naargelang wat bekend is. |

**Rooster (WebUntis)**

| Tool | Parameters | Doel |
|------|------------|------|
| `haal_rooster` | `dagen` (1–28, std. 7), `klas` (optioneel) | Lessen voor de komende dagen: vak, tijd, lokaal. |
| `haal_vakken` | `klas` (optioneel) | Vakken van de komende 4 weken, met het eerstvolgende lesmoment. |

**Deadlines (Digitap/Moodle)**

| Tool | Parameters | Doel |
|------|------------|------|
| `haal_deadlines` | `vak` (filter), `dagen` (1–365) | Komende deadlines met vak, titel, vervaldatum, status + uid. |
| `markeer_deadline` | `uid`, `status` | Zet de persoonlijke status van één deadline. |

De tool-beschrijvingen staan in het Nederlands in [`server.py`](mcp_server/server.py)
en zijn meteen de instructies die Claude krijgt.

---

## 5. Het contextgeheugen

Opgeslagen in SQLite ([`database.py`](mcp_server/database.py)), drie tabellen:

| Tabel | Inhoud |
|-------|--------|
| `gebruikers` | toegangssleutel, naam, (optioneel) persoonlijke Digitap-ICS-URL |
| `feiten` | vrije sleutel→waarde-feiten per gebruiker (naam, klas, studiejaar, voorkeuren…) |
| `deadline_status` | status per deadline (gekoppeld aan de stabiele ICS-`uid`) |

- **Gebruikersgeschiedenis:** de `feiten`-tabel is het geheugen dat over gesprekken
  heen bewaard blijft; de deadline-status onthoudt wat je al af hebt.
- **Tijd:** alle tijden worden omgezet naar **Europe/Brussels**; rooster en deadlines
  werken relatief t.o.v. *nu* ("komende N dagen").
- **Sessie-/gebruikersgegevens:** elke gebruiker wordt geïdentificeerd via zijn
  toegangssleutel, en alle context is **strikt per gebruiker gescheiden**. Nieuwe
  SQLite-verbinding per tool-call → thread-safe.

---

## 6. Context beïnvloedt het gedrag (bewijs)

Dit is de kern van de opdracht — en het is op meerdere plaatsen aantoonbaar:

1. **`begroet()`** past zijn antwoord aan op basis van de opgeslagen naam, klas en
   studiejaar ([`server.py:137`](mcp_server/server.py)). Leeg geheugen → andere
   begroeting.
2. **`haal_rooster()` / `haal_vakken()`** kiezen de klas volgens de prioriteit:
   *meegegeven `klas`* > *onthouden feit `klas`* > *`UNTIS_KLAS` uit `.env`*. Zonder
   argument hangt het rooster dus volledig af van wat de gebruiker eerder liet
   onthouden ([`server.py:195`](mcp_server/server.py)).
3. **`markeer_deadline()`** → de status blijft bewaard, ook in een volgend gesprek, en
   kleurt wat `haal_deadlines()` toont.
4. **Isolatie** tussen gebruikers is bewezen in [`demo.py`](mcp_server/demo.py)
   (Aron vs. Lotte) en in [`test_server.py`](mcp_server/test_server.py).

---

## 7. Opdracht-checklist (Optie B)

| Vereiste uit de opdracht | Status | Waar |
|--------------------------|:------:|------|
| Simpele AI-toepassing met zelf toegevoegde context (assistent) | ✅ | hele `mcp_server/` |
| Eigen contextgeheugen: **gebruikersgeschiedenis** | ✅ | `feiten` + `deadline_status` in `database.py` |
| Eigen contextgeheugen: **tijd / locatie** | ✅ | Europe/Brussels + "komende N dagen" (`ics_parser.py`, `rooster.py`) |
| Eigen contextgeheugen: **sessie-/gebruikersgegevens** | ✅ | toegangssleutel + per-gebruiker isolatie (`server.py`) |
| Aantonen dat context het gedrag beïnvloedt | ✅ | sectie 6 + `demo.py` |
| Reflectiestuk over MCP / geavanceerder contextprotocol | ✅ | sectie 9 |
| Broncode met commentaar | ✅ | alle modules + docstrings |
| Inleveren op Digitap | ⬜ | nog te doen |

---

## 8. Verbeteringen & ontwerpkeuzes

Onderweg verbeterden we het prototype met een aantal bewuste keuzes:

- **WebUntis via REST-API i.p.v. de klassieke RPC.** De `getTimetable`-RPC geeft bij
  AP Hogeschool `-8509 "no right for timetable"` voor studenten. We halen het rooster
  daarom via `/WebUntis/api/public/timetable/weekly/data` met dezelfde sessie.
- **Twee login-routes** naar WebUntis: wachtwoord én geheime sleutel/TOTP (zelf
  nagebouwd met `getUserData2017` + JSESSIONID).
- **Gesloten keuzelijsten (enums) in het tool-schema.** `klas` (afgeleid uit
  `config.KLASSEN`) en `status` zijn `Literal`-types, zodat de LLM geen ongeldige
  waarde kan "verzinnen". `dagen` is begrensd (1–28 / 1–365).
- **Per-gebruiker Digitap-URL met terugval** op een gedeelde `DIGITAP_ICS_URL` uit
  `.env` → werkt zowel voor "één gedeelde kalender" als "een kalender per gebruiker".
- **Automatische aanmaak** van een gebruiker bij een eerste, onbekende sleutel — geen
  voorafgaande registratie nodig.
- **Waarschuwing** wanneer de ICS-feed enkel de lopende maand lijkt te bevatten
  (`preset_time=monthnow` → tip `recentupcoming`).
- **Bewijslast:** offline unit-tests ([`test_server.py`](mcp_server/test_server.py))
  met vaste fixtures + een end-to-end demo, en een **Dockerfile** voor deployment.
- **Bekende beperking / toekomst:** de WebUntis-login gebeurt per tool-call en is
  relatief traag — de sessie cachen is een logische volgende optimalisatie.

---

## 9. Reflectie: MCP & een geavanceerder contextprotocol

De opdracht vraagt een reflectie over hoe MCP ons systeem zou verbeteren. Omdat we MCP
*zelf* gebouwd hebben, is onze reflectie geen "wat-als" maar gebaseerd op ervaring.

**Wat MCP ons concreet opleverde**
- **Eén protocol, overal bruikbaar.** We schreven de tools één keer; elke MCP-client
  (Claude Desktop, Claude Code, de MCP Inspector) kan ze meteen gebruiken.
- **Context als tools i.p.v. prompt-plakwerk.** In plaats van alle context vooraf in
  een prompt te proppen, *beslist het model zelf* wanneer het `haal_context_op()`
  roept of iets `onthoud()`t. Dat houdt de context actueel en relevant, en schaalt
  veel beter dan een groeiende system-prompt.
- **Scheiding van zorgen.** De data (rooster, deadlines, geheugen) leeft in onze
  server; het model hoeft enkel te weten *dat* de tools bestaan, niet *hoe* ze werken.

**Wat MCP (nog) niet voor ons oploste**
- **Geen ingebouwde identiteit.** MCP geeft niet door wie de Claude-gebruiker is. We
  moesten zelf een toegangssleutel-mechanisme bouwen om gebruikers te onderscheiden.
- **Jonge, bewegende SDK.** De Python-SDK is intussen 2.x: `FastMCP` heet nu
  `MCPServer`, headers via `ctx.headers`, enz. Dat kostte uitzoekwerk.

**Hoe een geavanceerder contextprotocol het systeem zou verbeteren**
- **Ingebouwde authenticatie/identiteit**, zodat we geen eigen sleutels hoeven te
  beheren en de context automatisch aan de juiste persoon hangt.
- **Gestandaardiseerd geheugen en "resources"**, zodat context (feiten, documenten)
  op een uniforme manier gedeeld en opgehaald wordt i.p.v. via ad-hoc tools.
- **Sessie- en consent-beheer**: expliciete afspraken over welke context bewaard mag
  worden en hoe lang — belangrijk nu we persoonlijke schoolgegevens opslaan.
- **Caching / sessies in het protocol**, wat meteen onze trage WebUntis-login zou
  oplossen.

Kortom: MCP maakte het haalbaar om context tot een *eersterangs, herbruikbaar*
onderdeel van de assistent te maken. Een rijker contextprotocol zou vooral de randen —
identiteit, consent, gestandaardiseerd geheugen en caching — wegwerken die we nu nog
zelf hebben moeten invullen.

---

## 10. Project draaien

Volledige instructies staan in [`mcp_server/README.md`](mcp_server/README.md). In het kort:

```sh
# 1. Maak een gebruiker (geeft een toegangssleutel terug)
uv run --directory mcp_server python beheer.py nieuw "Aron"

# 2. Start de server
uv run --directory mcp_server python server.py
#    → http://127.0.0.1:8000/mcp   (koppel in Claude met ?key=<sleutel>)

# Bewijs zonder netwerk / zonder echte accounts:
uv run --directory mcp_server python test_server.py   # offline unit-tests
uv run --directory mcp_server python demo.py          # end-to-end isolatie-demo
```

**In te leveren op Digitap:** deze repository (broncode met commentaar) + dit
`OVERVIEUW.md` als overzicht en reflectienota.
