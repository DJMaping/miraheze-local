---
type: home
---
# Andah, a second brain

Welcome desk for the Andah world. This vault has two zones:

- **Generated, read-only** (`Articles/`, `Categories/`) is rebuilt from the wiki by
  `to_obsidian.py` and **overwritten on every export**. Never hand-edit it.
- **Hand-authored** (this note, `1 Maps/`, `2 Dashboards/`, `3 Workshop/`, `4 Templates/`)
  is yours. The export never touches it.

## Maps of content

- [[1 Maps/Geography|🗺 Geography]] – continents, countries, cities
- [[1 Maps/World Cups|🏆 World Cups]] – the FLLA World Cup editions
- [[1 Maps/Confederations|🛡 Confederations]] – the seven football confederations
- [[1 Maps/Religions|🕊 Religions]] – the religion families of Andah
- [[1 Maps/Economy|💰 Economy]] – the lahn, trade and development data

## Dashboards (live tables)

These read the `type:` and properties on every article and update themselves.

- [[2 Dashboards/Countries.base|Countries]] – 175, sortable by population, GDP, HDI
- [[2 Dashboards/Continents.base|Continents]] – 31
- [[2 Dashboards/Cities.base|Cities]] – 22
- [[2 Dashboards/World Cups.base|World Cups]] – 25 editions
- [[2 Dashboards/Confederations.base|Confederations]] – 7
- [[2 Dashboards/Religions.base|Religions]] – 7

## Workshop

Draft new canon here, then promote it to the wiki.

- [[3 Workshop/Inbox|📥 Inbox]] – quick capture
- [[3 Workshop/README|How the Workshop works]] – templates, the promotion path, canon rules

## Refresh

Run `python to_obsidian.py` from the repo root after pulling wiki changes to rebuild
`Articles/` and `Categories/`.
