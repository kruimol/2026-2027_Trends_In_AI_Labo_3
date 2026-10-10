# Reflectienota – Context is King

**Vak:** Trends in AI (labo 3) · **Opdracht:** *Context is King* (Hassan Haddouchi)
**Werkvorm:** Optie B – prototype · **Team:** 2 studenten

Deze nota bevat onze **bevindingen**: wat we gebouwd hebben, wat we onderweg
vaststelden over de rol van context, hoe we MCP in de praktijk ervaarden, en een
reflectie — technisch én ethisch — over hoe MCP of een geavanceerder contextprotocol
ons systeem zou verbeteren. Het volledige projectoverzicht en de afvinking van de
opdracht staan in [`OVERVIEUW.md`](OVERVIEUW.md); het technische logboek per deelstap
in [`NOTES.md`](NOTES.md).

## Opzet in één alinea

We bouwden een persoonlijke schoolassistent, niet als losse chatbot, maar als een
échte **MCP-server** (`trends-ai`) die Claude koppelt aan het schoolleven. De server
onthoudt context per gebruiker in een SQLite-databank (naam, klas, studiejaar,
voorkeuren, deadline-status) en biedt acht tools aan: om context te **onthouden** en
**op te halen**, om het **rooster** uit WebUntis te lezen, en om **deadlines** uit de
Digitap/Moodle-kalender te tonen en af te vinken. We kozen er bewust voor om context
niet te *simuleren* maar het Model Context Protocol zelf te implementeren — zo zijn
onze bevindingen gebaseerd op echte ervaring in plaats van op een gedachte-experiment.

## Bevinding 1 — Context stuurt het gedrag van de assistent

De kernvraag van de opdracht is of context het gedrag van de toepassing beïnvloedt.
Dat zagen we op meerdere plaatsen, en het is reproduceerbaar:

- **De begroeting hangt van het geheugen af.** `begroet()` geeft een andere tekst
  naargelang wat bekend is: een lege gebruiker krijgt een uitnodiging om iets te
  vertellen, een gekende gebruiker wordt met naam, klas en studiejaar begroet.
- **Hetzelfde verzoek levert een ander rooster op, afhankelijk van de context.**
  `haal_rooster()` kiest de klas volgens een duidelijke prioriteit: *expliciet
  meegegeven klas* > *onthouden feit `klas`* > *standaard uit `.env`*. Vraag je "wat
  is mijn rooster?" zonder klas mee te geven, dan bepaalt het geheugen het antwoord.
  Wie eerder `onthoud('klas', '3itai')` deed, krijgt een ander rooster dan wie niets
  liet onthouden.
- **Status blijft bewaard over sessies.** Markeer je een deadline als "klaar", dan is
  dat in een volgend, volledig nieuw gesprek nog steeds zo. De assistent kan dus in de
  tijd meegroeien met de gebruiker.
- **Context is strikt per gebruiker.** Twee gebruikers delen dezelfde server maar niet
  elkaars geheugen. Dat bewijzen we end-to-end in `demo.py` (twee gebruikers met
  verschillende klassen) en in de offline tests `test_server.py`.

Onze bevinding: context maakt het verschil tussen een generieke chatbot en een
assistent die *jouw* situatie kent. De waarde zit niet in meer rekenkracht maar in de
juiste context op het juiste moment.

## Bevinding 2 — MCP in de praktijk

Door MCP écht te bouwen, leerden we waar de kracht én de grenzen van het protocol
liggen:

- **Context als tools werkt beter dan prompt-plakwerk.** In plaats van alle informatie
  vooraf in een systeem-prompt te proppen, *beslist het model zelf* wanneer het
  `haal_context_op()` aanroept of iets `onthoud()`t. De context blijft daardoor
  actueel en relevant, en de aanpak schaalt beter dan een steeds groeiende prompt.
- **Eén keer schrijven, overal bruikbaar.** Dezelfde server werkt met elke MCP-client
  (Claude Desktop, Claude Code, de MCP Inspector) zonder aanpassing.
- **MCP geeft geen identiteit door.** Het protocol vertelt de server niet wíé de
  gebruiker achter Claude is. We moesten daarom zelf een **toegangssleutel**-mechanisme
  bouwen (via `?key=` of een `Authorization: Bearer`-header) om gebruikers te
  onderscheiden en hun context gescheiden te houden.
- **Een jonge, bewegende SDK.** De Python-SDK is intussen 2.x: `FastMCP` heet nu
  `MCPServer`, headers lees je via `ctx.headers`, enz. Dat kostte uitzoekwerk omdat
  oudere voorbeelden niet meer kloppen.
- **De echte wereld is weerbarstig.** WebUntis blokkeert de klassieke
  `getTimetable`-RPC voor studenten (`-8509 "no right for timetable"`); we moesten
  uitwijken naar de REST-API. De login is bovendien traag omdat we per tool-call
  opnieuw inloggen — een bewuste keuze voor eenvoud, met caching als bekende
  verbetering.

## Reflectie — Hoe MCP of een geavanceerder contextprotocol ons systeem zou verbeteren

MCP maakte het haalbaar om context een *eersterangs, herbruikbaar* onderdeel van de
assistent te maken. De randen die we nu zelf moesten invullen, zijn precies waar een
rijker contextprotocol winst zou boeken:

- **Ingebouwde authenticatie en identiteit.** Als het protocol de gebruiker
  betrouwbaar zou doorgeven, verdween onze zelfgebouwde sleutel-laag en zou context
  automatisch aan de juiste persoon hangen — veiliger en eenvoudiger.
- **Gestandaardiseerd geheugen en "resources".** Nu bewaren we feiten via ad-hoc
  tools (`onthoud`/`haal_context_op`). Een protocol met een afgesproken geheugenmodel
  zou context uniform laten delen, doorzoeken en versioneren tussen toepassingen.
- **Sessie- en consentbeheer.** Expliciete protocol-afspraken over *welke* context
  bewaard mag worden en *hoe lang* zouden privacy afdwingbaar maken in plaats van een
  keuze van de ontwikkelaar (zie ethiek hieronder).
- **Caching en sessies in het protocol.** Dit zou meteen onze trage WebUntis-login
  oplossen zonder dat we zelf een houdbaarheidslogica moeten schrijven.

## Technische aspecten

Enkele architectuurkeuzes en hun afwegingen:

- **Login per tool-call vs. caching.** We loggen per aanroep opnieuw in bij WebUntis.
  Voordeel: eenvoudig en veilig (geen sessie-toestand die kan verlopen of lekken).
  Nadeel: traag. De sessie cachen is een duidelijke, geïsoleerde optimalisatie voor
  later.
- **Nieuwe SQLite-verbinding per aanroep.** Dat houdt de opslag thread-safe t.o.v. de
  werk-threads van de server, zonder gedeelde connectie-toestand.
- **Gesloten keuzelijsten (enums) in het tool-schema.** `klas` (afgeleid uit één bron
  van waarheid, `config.KLASSEN`) en `status` zijn `Literal`-types. Zo kan het model
  geen ongeldige waarde "verzinnen" — belangrijk bij een LLM dat vrije tekst
  produceert. Numerieke parameters zoals `dagen` zijn begrensd (1–28 / 1–365).
- **Per-gebruiker configuratie met terugval.** De Digitap-ICS-URL staat per gebruiker
  in de databank, met terugval op een gedeelde `DIGITAP_ICS_URL` uit `.env`. Zo werkt
  zowel "één gedeelde kalender" als "een kalender per student".
- **Geheimen buiten de code.** Credentials en URL's leven in `.env`, niet in de
  broncode die we inleveren; klas-ID's (geen geheim) staan wél gewoon in `config.py`.

## Ethische aspecten

Omdat de assistent **persoonlijke schoolgegevens** opslaat, zijn de ethische vragen
niet theoretisch.

- **Transparantie en uitlegbaarheid.** Elke tool heeft een duidelijke, Nederlandstalige
  beschrijving die meteen de instructie aan het model is, dus het gedrag is te volgen.
  De antwoorden vermelden bovendien hun **bron** ("persoonlijke kalender" vs. "gedeelde
  kalender (.env)") en geven een **waarschuwing** wanneer de feed verdacht beperkt is
  (enkel de lopende maand). De gebruiker weet zo waar informatie vandaan komt. Een
  aandachtspunt blijft dat een LLM resultaten vrij herformuleert; de tools geven daarom
  gestructureerde velden terug i.p.v. vrije tekst, zodat de brongegevens exact blijven.
- **Privacy van contextuele gegevens.** Alle context staat in een **lokale** SQLite en
  is **per gebruiker geïsoleerd** via de toegangssleutel — niemand ziet andermans
  geheugen. We bewaren bewust het minimum (feiten die de gebruiker zelf deelt) en geen
  wachtwoorden in de databank. Risico's die we onderkennen: de toegangssleutel is
  gevoelig (wie hem heeft, heeft de context) en een gedeelde kalender-URL kan meer
  tonen dan bedoeld. Een productieversie zou de databank versleutelen en de sleutels
  roteerbaar maken.
- **Beheer van langetermijngeheugen.** De gebruiker houdt controle: `onthoud` voegt toe,
  `wis_geheugen` verwijdert alles — een concrete invulling van het "recht om vergeten te
  worden". Toch zagen we grenzen: er is nu geen *vervaldatum* op feiten en geen expliciet
  moment van *toestemming* per bewaarde gegeven. Een volwassen systeem zou per feit een
  houdbaarheid en een consent-status bijhouden, en de gebruiker periodiek tonen wat er
  over hem bewaard wordt.

## Conclusie — Geleerde lessen

Context is inderdaad "king": dezelfde assistent voelt generiek of persoonlijk, puur
afhankelijk van wat hij onthoudt. MCP bleek de juiste bouwsteen om dat netjes te doen —
context als tools, door het model zelf aangestuurd — maar het protocol lost (nog) niet
alles op: identiteit, consent, gestandaardiseerd geheugen en caching moesten we zelf
invullen. Juist dáár zou een geavanceerder contextprotocol het grootste verschil maken.
De belangrijkste les: een goede AI-assistent bouwen gaat minder over het model en meer
over het zorgvuldig, transparant en privacybewust beheren van de context eromheen.
