# Vacuula voor Home Assistant

Custom integratie om een Neato-robot (D8/D9/D10 = "Gen4") aan te sturen via je eigen
[Vacuula](https://github.com/vacuula/vacuula)-server. Alles blijft lokaal: de integratie praat
met de Vacuula-server (`/api`), niet met de Neato-cloud.

## Wat je krijgt (per robot)

| Entiteit | |
|---|---|
| `vacuum.<naam>` | start / pauze / hervat / stop / terug naar dock / zoek robot, status (cleaning, docked, returning, paused, error) |
| `sensor.<naam>_battery` | accu in % |
| `sensor.<naam>_action`, `sensor.<naam>_error` | diagnose: wat doet de robot, welke foutcode(s) |
| `binary_sensor.<naam>_charging`, `_docked`, `_connected` | laden, op dock, verbonden met de Vacuula-server |
| `select.<naam>_cleaning_mode` | eco / turbo / auto / max (gebruikt bij elke start) |
| `select.<naam>_navigation_mode` | normal / gentle |
| `sensor.<naam>_last_run_area`, `_last_run_duration`, `_last_run_battery_used`, `_last_run_end`, `_last_run_started_by` | statistieken van de laatste schoonmaakronde (uit de rondes die Vacuula bewaart) |
| `sensor.<naam>_total_area`, `_run_count` | totaal schoongemaakt oppervlak en aantal rondes |
| `binary_sensor.<naam>_last_run_complete` | of de laatste ronde alles heeft gedaan |
| `image.<naam>_map` | de actieve plattegrond |
| `image.<naam>_last_run` | plattegrond met het gereden pad van de laatste ronde |
| `select.<naam>_zone` + `button.<naam>_clean_selected_zone` | kies een zone van de actieve kaart en maak die schoon |
| `button.<naam>_refresh_runs_and_maps` | rondes, kaarten en zones direct opnieuw laden |
| `switch.<naam>_force_floor_plan`, `select.<naam>_robot_language` | instellingen van de robot zelf |

Rondes, kaarten, zones en instellingen worden elke 10 minuten ververst en direct nadat een ronde klaar is
(de robot meldt zijn ronde pas even later; daarom wordt er nog twee keer nagekeken).

Updates komen live binnen via de event-stream van Vacuula (met een poll elke 60 s als vangnet).
Nieuwe robots verschijnen vanzelf als ze zich bij de server aanmelden.

### Services

* `vacuula.clean_zones` — maak benoemde zones schoon, bv. keuken en hal:
  ```yaml
  action: vacuula.clean_zones
  target:
    entity_id: vacuum.neato
  data:
    zones: ["Keuken", "Hal"]
    mode: turbo          # optioneel, anders de select
  ```
  De zones zijn de namen (of id's) uit de Vacuula-app. De kaart moet *actief* (gepromoot) zijn op
  de robot; no-go-lijnen worden standaard gerespecteerd (`nogo_enabled`).
* `vacuula.get_zones` — geeft kaarten met hun zones en no-go-lijnen terug (handig om de namen op
  te zoeken: Ontwikkelaarstools → Acties, met "Respons weergeven").
* `vacuula.get_runs` — geeft de laatste rondes terug (oppervlak, duur, accuverbruik, start/eind, …).
* `vacuula.get_schedule`, `vacuula.set_schedule_event`, `vacuula.delete_schedule_event` — het schema van
  de robot, in het ruwe formaat dat de robot zelf gebruikt. Haal eerst het schema op om te zien hoe een
  item eruitziet; ongeldige items weigert de robot.
* `vacuum.send_command` — rauw commando naar de robot, bv. `command: cleaning.pause`.

Een gewone `vacuum.start` gebruikt de actieve kaart (met no-go-lijnen) als die er is, anders een
volledige schoonmaakronde zonder kaart.

## Installeren

1. Kopieer de map `custom_components/vacuula` naar `/config/custom_components/vacuula` op je
   Home Assistant (bv. via de Samba-share `\\homeassistant\config`, of Terminal & SSH).
2. Herstart Home Assistant.
3. Instellingen → Apparaten & services → Integratie toevoegen → **Vacuula**.
4. Host invullen. Draait Vacuula als HA-app, probeer dan de standaard `6a057cb4-vacuula`; lukt dat
   niet, gebruik het IP-adres van je HA-machine (de app draait op het host-netwerk, poort 80).

Via HACS kan het ook als je deze map in een eigen GitHub-repo zet (de `hacs.json` staat erbij):
HACS → Aangepaste repository → categorie *Integratie*.

## Beperkingen / nog niet gedaan

* Alleen **Gen4** (D8, D9, D10, D800). Gen3 (D3–D7) gebruikt een ander protocol en wordt overgeslagen.
* Cleaning mode / navigation mode worden door de robot niet teruggemeld; Home Assistant onthoudt
  de laatst gekozen waarde.
* Er is **geen afgelegde afstand**: Vacuula en de robot bewaren die niet. Wel het oppervlak, de duur en het pad.
* De zones en no-go-lijnen staan niet op de kaartafbeelding getekend (de coördinaten zijn niet geverifieerd).
* Het schema is alleen ruw (services); er is nog geen mooie schema-entiteit.
* De velden van een ronde worden door de robot geleverd en zijn defensief uitgelezen: ontbreekt iets, dan
  blijft die sensor leeg (`unknown`). Gebruik `vacuula.get_runs` om te zien wat er binnenkomt.
* Vacuula zelf is nog bezig met een eigen Home Assistant-koppeling (🚧 in hun README); dit is een
  onafhankelijke integratie op hun publieke API en kan breken als die API verandert.

## Licentie

MIT, zie [LICENSE](LICENSE).
