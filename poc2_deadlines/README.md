# POC 2 – Digitap: deadlines uit de ICS-kalender

Deze proof of concept haalt je **Moodle/Digitap-kalenderexport** (een ICS-feed) op
en toont je komende deadlines, gesorteerd op datum, in de tijdzone
**Europe/Brussels**. Per deadline zie je het vak, de titel en de vervaldatum.

In een Moodle-export staat per deadline een `VEVENT` met:
- `SUMMARY` = naam van de opdracht,
- `CATEGORIES` = korte naam van het vak,
- `DTSTART` = vervaldatum (soms met tijd in UTC, soms enkel een datum).

We parsen de feed met de library **`icalendar`**.

## Installeren

Dit mapje is een los `uv`-project met een eigen virtuele omgeving:

```bash
uv sync
```

## Testen zonder netwerk (offline)

Er zit een voorbeeldbestand `voorbeeld.ics` bij. De tests bewijzen dat het parsen,
sorteren, filteren en de waarschuwing kloppen – zonder internet:

```bash
uv run python test_deadlines.py
```

## Echt draaien

1. Kopieer `.env.example` naar `.env`:

   ```bash
   cp .env.example .env
   ```

2. Vul `DIGITAP_ICS_URL` in met je eigen export-URL (zie hieronder).

3. Draai:

   ```bash
   uv run python deadlines.py                 # alle komende deadlines
   uv run python deadlines.py --vak "Trends"  # enkel dat vak (deel van de naam volstaat)
   uv run python deadlines.py --dagen 14      # enkel binnen 14 dagen
   ```

Lukt het ophalen niet, dan toont het script de **exacte foutmelding** en stopt het.

## Waar vind ik de ICS-URL?

In Moodle/Digitap: **Kalender → Exporteren** (of "Kalender exporteren"). Kies wat je
wil exporteren en het tijdsbereik, en klik op **"URL ophalen"** / **"Get calendar
URL"**. Kopieer die URL; ze ziet er ongeveer zo uit:

```
https://learning.ap.be/calendar/export_execute.php?userid=...&authtoken=...&preset_what=all&preset_time=monthnow
```

> De `authtoken` in die URL is een **persoonlijk geheim**. Zet de volledige URL
> enkel in `.env` (die staat in `.gitignore`), nooit in de code of in dit bestand.

## De parameter `preset_time`

`preset_time` in de URL bepaalt welke periode Moodle teruggeeft:

- `weeknow` – deze week,
- `monthnow` – **deze maand** (standaard bij veel exports),
- `recentupcoming` – recent + de volgende 60 dagen,
- `custom` – eigen bereik.

Staat er `preset_time=monthnow`, dan krijg je enkel deadlines van de lopende maand.
Het script **waarschuwt** je als de feed daar op lijkt. Wil je verder vooruitkijken,
verander dan `monthnow` naar bijvoorbeeld `recentupcoming` in je URL.

## Geheimen

`.env` staat in `.gitignore` en wordt nooit ingeleverd. De ICS-URL met authtoken is
een geheim: hou hem uit code, README en logs.
