# Graph Report - .  (2026-06-09)

## Corpus Check
- 31 files · ~57,860 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 159 nodes · 247 edges · 17 communities (15 shown, 2 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 5 edges (avg confidence: 0.75)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Obsidian Export Pipeline|Obsidian Export Pipeline]]
- [[_COMMUNITY_FLLA Confederations & World Cup|FLLA Confederations & World Cup]]
- [[_COMMUNITY_City Data Generation|City Data Generation]]
- [[_COMMUNITY_Wiki Pull & State Sync|Wiki Pull & State Sync]]
- [[_COMMUNITY_Wiki Page Creation|Wiki Page Creation]]
- [[_COMMUNITY_Push & Edit Sync|Push & Edit Sync]]
- [[_COMMUNITY_Country Concepts & Simulation Data|Country Concepts & Simulation Data]]
- [[_COMMUNITY_Recent Push Tracking|Recent Push Tracking]]
- [[_COMMUNITY_FLLA WC Results - Etirha Era|FLLA WC Results - Etirha Era]]
- [[_COMMUNITY_Gstack Setup Scripts|Gstack Setup Scripts]]
- [[_COMMUNITY_WC Results - Emara & Finae Era|WC Results - Emara & Finae Era]]
- [[_COMMUNITY_WC Results - Quidic & Sattle Era|WC Results - Quidic & Sattle Era]]
- [[_COMMUNITY_WC Format Controversy 1724-1760|WC Format Controversy 1724-1760]]
- [[_COMMUNITY_WC 1716 & Estijan Ban|WC 1716 & Estijan Ban]]
- [[_COMMUNITY_Claude Permissions Settings|Claude Permissions Settings]]
- [[_COMMUNITY_1736 Floodlight Incident|1736 Floodlight Incident]]
- [[_COMMUNITY_Settings Local Config|Settings Local Config]]

## God Nodes (most connected - your core abstractions)
1. `FLLA World Cup (Tournament Series)` - 18 edges
2. `convert()` - 15 edges
3. `1700 FLLA World Cup (8th Edition)` - 12 edges
4. `main()` - 7 edges
5. `main()` - 7 edges
6. `_render_infobox()` - 7 edges
7. `1716 FLLA World Cup (12th Edition)` - 7 edges
8. `.state.json (Page revision state file)` - 6 edges
9. `1704 FLLA World Cup (9th Edition)` - 6 edges
10. `1708 FLLA World Cup (10th Edition)` - 6 edges

## Surprising Connections (you probably didn't know these)
- `1764 Andah World Cup Simulation Result (data copy)` --references--> `FLLA World Cup (Tournament Series)`  [EXTRACTED]
  data/simulation-result.txt → Simulation results/1716-world-cup.txt
- `Sattle (Nation/Football Team)` --semantically_similar_to--> `Raledria (Nation/Football Team)`  [INFERRED] [semantically similar]
  Simulation results/1740-world-cup.txt → Simulation results/1716-world-cup.txt
- `Skyscraper Rankings by Country (Andah)` --references--> `Raledria (Nation/Football Team)`  [EXTRACTED]
  skyscrapers_dump.txt → Simulation results/1716-world-cup.txt
- `Skyscraper Rankings by Country (Andah)` --references--> `Emara (Nation/Football Team)`  [EXTRACTED]
  skyscrapers_dump.txt → Simulation results/1716-world-cup.txt
- `Skyscraper Rankings by Country (Andah)` --references--> `Dahe (Nation/Football Team)`  [EXTRACTED]
  skyscrapers_dump.txt → Simulation results/1732-world-cup.txt

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Wiki Sync Pipeline (pull → edit → push)** — pull, push, push_recent, state_json [EXTRACTED 1.00]
- **Wiki Page Creation Tools** — create_new, publish_new, mediawiki_api [EXTRACTED 1.00]
- **FLLA World Cup Simulation Results Series (1700-1712)** — wc_1700, wc_1704, wc_1708, wc_1712 [EXTRACTED 1.00]
- **FLLA World Cup Champions Across Editions (Raledria, Lycroa, Verusa Dominate)** — concept_raledria, concept_lycroa, concept_verusa, concept_flla_world_cup [EXTRACTED 1.00]
- **Cinderella Nations in FLLA World Cup (Terressin, Areoix Lie, Sattle)** — concept_terressin, concept_areoix_lie, concept_sattle, concept_flla_world_cup [EXTRACTED 0.95]
- **FLLA World Cup Simulation Result Documents (1716-1764)** — simulation_results_1716_world_cup, simulation_results_1720_world_cup, simulation_results_1724_world_cup, simulation_results_1728_world_cup, simulation_results_1732_world_cup, simulation_results_1736_world_cup, simulation_results_1740_world_cup, simulation_results_1744_world_cup, simulation_results_1748_world_cup, simulation_results_1752_world_cup, simulation_results_1756_world_cup, simulation_results_1760_world_cup, simulation_results_1764_world_cup [EXTRACTED 1.00]

## Communities (17 total, 2 thin omitted)

### Community 0 - "Obsidian Export Pipeline"
Cohesion: 0.13
Nodes (27): Obsidian Vault (Andah-Wiki), clean_cell(), collapse_blanks(), convert(), convert_external_links(), convert_headings(), convert_infoboxes(), convert_inline() (+19 more)

### Community 1 - "FLLA Confederations & World Cup"
Cohesion: 0.18
Nodes (17): AFLA (Ayuma confederation), CFLA (Acrola confederation), EFLA (Mahea confederation), MFLA (Massir confederation), NAFLA (New Ayre confederation), NFLA (Atirha confederation), QFLA (Quia confederation), FLLA World Cup (tournament series) (+9 more)

### Community 2 - "City Data Generation"
Cohesion: 0.22
Nodes (14): Largest Cities by Population.xlsx, *Cities*.xlsx (per-region roster files), build_section(), clean_name(), insert_section(), load_data(), main(), merge_country() (+6 more)

### Community 3 - "Wiki Pull & State Sync"
Cohesion: 0.20
Nodes (14): fetch_page(), list_pages(), load_state(), main(), pull.py — Download wiki pages to local files.  Usage:     python pull.py, Return (content, revid) for a page, or (None, None) if missing., Write a page to disk and record its revid in state., Log in using a bot password and return an authenticated session. (+6 more)

### Community 4 - "Wiki Page Creation"
Cohesion: 0.29
Nodes (9): One-off helper: create new local files on the wiki and register them in .state.j, MediaWiki API, csrf(), filepath_to_title(), login(), main(), Path, One-shot helper to create new wiki pages that aren't yet in .state.json.  Usage: (+1 more)

### Community 5 - "Push & Edit Sync"
Cohesion: 0.29
Nodes (9): Pull-Edit-Push Wiki Workflow, edit_page(), fetch_remote(), get_csrf_token(), main(), push.py — Upload local file changes back to the wiki.  Usage:     python push.py, Edit a page. base_revid prevents overwriting changes made on the wiki since pull, session_login() (+1 more)

### Community 6 - "Country Concepts & Simulation Data"
Cohesion: 0.28
Nodes (9): Dahe (Nation/Football Team), Easuhura (Nation/Football Team), Lycroa (Nation/Football Team), Miracle of Rovik (1764 QF Upset), Skyscraper Rankings by Country (Andah), 1764 Andah World Cup Simulation Result (data copy), 1732 FLLA World Cup (16th Edition), 1764 Andah World Cup Simulation (+1 more)

### Community 7 - "Recent Push Tracking"
Cohesion: 0.31
Nodes (7): iso, timestamp, fmt(), load_last_push(), main(), push_recent.py — Push only files modified since the last time you ran this.  Tra, save_last_push()

### Community 8 - "FLLA WC Results - Etirha Era"
Cohesion: 0.36
Nodes (8): FLLA Confederation Rotation Policy (1742), Etirha (Nation/Football Team), FLLA World Cup (Tournament Series), Praesyu (Nation/Football Team), Sanagara (Nation/Football Team), 1720 FLLA World Cup (13th Edition), 1744 FLLA World Cup (19th Edition), 1752 FLLA World Cup (21st Edition)

### Community 9 - "Gstack Setup Scripts"
Cohesion: 0.33
Nodes (5): gstack-retry-setup.sh script, gstack-run-setup.sh script, launch_test(), PATH, PATH

### Community 10 - "WC Results - Emara & Finae Era"
Cohesion: 0.29
Nodes (7): 1748 Known as Greatest World Cup in History, Emara (Nation/Football Team), Finae (Nation/Football Team), Halric Ostley (Emara, 1748 Golden Boot), New Misos (Nation/Football Team), 1728 FLLA World Cup (15th Edition), 1748 FLLA World Cup (20th Edition)

### Community 11 - "WC Results - Quidic & Sattle Era"
Cohesion: 0.33
Nodes (6): FLLA Confederations (NFLA/AFLA/NAFLA/EFLA/QFLA/MFLA/CFLA), Quidic (Nation/Football Team), Sattle (Nation/Football Team), Seytinemas (Nation/Football Team), 1740 FLLA World Cup (18th Edition), 1756 FLLA World Cup (22nd Edition)

### Community 12 - "WC Format Controversy 1724-1760"
Cohesion: 0.40
Nodes (5): 1724 Groups-of-Three Format Controversy, Areoix Lie (Nation/Football Team), Verusa (Nation/Football Team), 1724 FLLA World Cup (14th Edition), 1760 Andah World Cup Simulation

### Community 13 - "WC 1716 & Estijan Ban"
Cohesion: 0.50
Nodes (4): Estijan PED Ban (1716 WC), Taval (Nation/Football Team), Terressin (Nation/Football Team), 1716 FLLA World Cup (12th Edition)

### Community 15 - "1736 Floodlight Incident"
Cohesion: 1.00
Nodes (3): 1736 Floodlight Incident in Final, Raledria (Nation/Football Team), 1736 FLLA World Cup (17th Edition)

## Knowledge Gaps
- **25 isolated node(s):** `allow`, `timestamp`, `iso`, `PATH`, `gstack-run-setup.sh script` (+20 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `.state.json (Page revision state file)` connect `Wiki Page Creation` to `Obsidian Export Pipeline`, `Wiki Pull & State Sync`, `Push & Edit Sync`, `Recent Push Tracking`?**
  _High betweenness centrality (0.133) - this node is a cross-community bridge._
- **Why does `FLLA World Cup (Tournament Series)` connect `FLLA WC Results - Etirha Era` to `Country Concepts & Simulation Data`, `WC Results - Emara & Finae Era`, `WC Results - Quidic & Sattle Era`, `WC Format Controversy 1724-1760`, `WC 1716 & Estijan Ban`, `1736 Floodlight Incident`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `MediaWiki API` connect `Wiki Page Creation` to `Wiki Pull & State Sync`, `Push & Edit Sync`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **What connects `allow`, `timestamp`, `iso` to the rest of the system?**
  _42 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Obsidian Export Pipeline` be split into smaller, more focused modules?**
  _Cohesion score 0.1330049261083744 - nodes in this community are weakly interconnected._