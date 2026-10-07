# Studiecoach — MCP-server als contextgeheugen

Een klein schoolprototype voor een opdracht over **contextgebruik in AI**.
Claude Desktop is het chatvenster en het taalmodel; onze Python-server houdt de
**context** bij en biedt die aan via MCP-tools. Zo kunnen we aantonen dat
dezelfde vraag — *"Wat moet ik nu doen?"* — een ander antwoord geeft naargelang
de context.

Gemaakt door twee studenten. Bewust klein en leesbaar gehouden.

## Hoe het werkt: drie contextlagen

Alles draait rond één klasse, `ContextMemory` (in `context_memory.py`), met drie lagen:

1. **Sessie** — acties van de huidige draaironde van de server. Leeft alleen in
   het geheugen en is dus **leeg na elke herstart**.
2. **Geschiedenis** — vakken, deadlines, zwakke punten en een studielog. Wordt
   bewaard in `geheugen.json` en blijft dus **over sessies heen** bestaan.
3. **Omgeving** — wordt bij **elke aanvraag opnieuw berekend**: datum, weekdag,
   uur, dagdeel, dagen tot elke deadline en welke deadlines voorbij zijn.

Het "huidige" tijdstip is overschrijfbaar via de omgevingsvariabele
`STUDIECOACH_NU` (ISO-formaat), zodat we in een demo een ander moment kunnen
simuleren.

## Installatie

Vereist: Python 3.10+ en [uv](https://docs.astral.sh/uv/).

```bash
# In de projectmap:
uv sync
```

Dit installeert de enige dependency, de officiële MCP Python SDK (`mcp[cli]`),
plus `pytest` voor de tests.

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

1. *"Ik volg Wiskunde en Geschiedenis. Voor Wiskunde heb ik op 6 maart een
   examen. Integralen snap ik nog niet goed."*
   → Claude roept `voeg_vak_toe`, `voeg_deadline_toe` en `markeer_zwak_punt` aan.
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

## Bestandsoverzicht

| Bestand | Rol |
|---|---|
| `context_memory.py` | De klasse `ContextMemory` met de drie lagen en JSON-opslag. |
| `server.py` | De MCP-server met zeven tools rond `ContextMemory`. |
| `demo.py` | Speelt drie momenten na zonder Claude Desktop. |
| `test_context_memory.py` | Pytest-tests voor `ContextMemory`. |
| `geheugen.json` | Wordt automatisch aangemaakt; de persistente geschiedenis. |
| `reflectie.md` | Reflectievragen (inhoud schrijven we zelf). |
