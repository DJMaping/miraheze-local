# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# miraheze-local

A local editing environment for the Andah wiki (`andah.miraheze.org`), a Miraheze-hosted MediaWiki for a fictional world ("Andah"). The workflow is: pull wiki pages to disk, edit them (with VS Code or Claude Code), then push changes back via the MediaWiki API.

Scale: ~3,250 tracked pages — ~530 Main articles, ~1,580 Templates, ~340 Modules, ~510 Files, ~140 Categories. Most editing work is on `pages/Main/`.

## Architecture

The whole system is a thin sync layer over the MediaWiki `action` API, with `.state.json` as the single source of truth for what maps to what.

- `.state.json` — the index. Maps every tracked page title to `{ "revid": <last-pulled revision>, "path": "pages/.../X.wiki" }`. Both pull and push read/write it. It is **gitignored** (large, machine-specific), so it exists only locally — without it, push has nothing to do.
- **Pull** (`pull.py`) lists pages via `list=allpages`, fetches each one's content + revid, writes the file, and records the revid in `.state.json`.
- **Push** (`push.py`) is the inverse and is deliberately conservative. For each candidate file it: (1) re-fetches the *current* remote content, (2) skips if local == remote (no spurious edits), (3) skips with a WARN if the remote revid no longer matches the `.state.json` baseline — meaning the page changed on the wiki since your last pull (conflict protection; pull again to reconcile), then (4) sends the edit with `baserevid` + `nocreate=1`.

Because push compares against live remote content (not just mtime), editing a file and reverting it produces zero edits.

## Title ↔ filename mapping

Files live at `pages/<NamespaceFolder>/<Title>.wiki`. The namespace folder names are defined by `NS_NAMES` in `pull.py` (0→`Main`, 10→`Template`, 14→`Category`, 828→`Module`, etc.). Conversions, applied by `safe_filename` in `pull.py`:
- Spaces → underscores (MediaWiki convention).
- Subpage slashes (`/`) → `__` (keeps the path one level deep).
- For non-Main namespaces the title prefix (`Template:`) is stripped from the filename since the folder already encodes it.

`_publish_new.py` reverses this mapping path→title (namespace-aware). When working out a page's wiki title from a file path, mirror this logic — don't assume filename == title.

## Common commands

```bash
python pull.py                        # Pull all main-namespace pages
python pull.py "Page Title"           # Pull one specific page (namespace inferred from prefix)
python pull.py --ns 10                # Pull templates (namespace 10)
python pull.py --all-ns               # Pull every namespace in NS_NAMES

python push.py --dry-run              # Preview what would be sent (no login, no writes)
python push.py -m "Edit summary"      # Push all changed pages
python push.py pages/Main/Foo.wiki    # Push specific file(s)

python push_recent.py                 # Push only files changed since the last push_recent run
python _publish_new.py pages/Main/NewPage.wiki   # Create a page that doesn't exist yet
```

Always run `python push.py --dry-run` first after bulk edits to review what will be sent.

## Creating new pages

`push.py` uses `nocreate=1` and will **never** create a page. Two helpers do, both using `createonly=1`:
- `_publish_new.py <paths...>` — the one to use. Derives the title from the file path (namespace-aware), registers the new page in `.state.json` on success.
- `_create_new.py "<summary>" <paths...>` — older/simpler variant. Derives the title from the bare filename stem only (Main namespace), takes the edit summary as its first positional arg.

## Incremental push

`push_recent.py` (also `push_recent.bat`) pushes only files whose mtime is newer than the timestamp in `.last_push.json`. It batches files (50 per `push.py` invocation, to stay under the Windows ~32K command-line limit) and only advances the timestamp if every batch succeeds. Use this for "push whatever I've touched since last time" without re-scanning all tracked pages.

## One-off data / conversion scripts

These are not part of the pull/push loop and read from `data/`:
- `generate_cities.py` — regenerates the `== Largest cities ==` section on country pages from the `data/*Cities*.xlsx` spreadsheets, merged with `data/Largest Cities by Population.xlsx`. Run `python generate_cities.py dry [Country...]` to preview, `python generate_cities.py apply` to write. Idempotent: it replaces the block between `<!-- LARGEST-CITIES-AUTO START -->` / `END` markers. `ALIAS` maps spreadsheet sheet names to actual wiki page titles where they differ.
- `to_obsidian.py` — one-directional export of Main + Category pages to an Obsidian vault. The target vault is resolved by `resolve_vault`: `--vault` arg > `OBSIDIAN_VAULT` env var > the default `Andah-Wiki/` beside the script. Writes generated notes into `<vault>/Articles/` and `<vault>/Categories/` — both are **overwritten on every run**, so never hand-edit them (the two-zone rule: keep hand-authored notes in other folders). Converts wikitext → markdown, turns categories into frontmatter tags, and emits **typed frontmatter** — a `type:` (country / continent / city / worldcup / confederation / religion / person / article) plus per-type queryable properties (capital, population, gdp_ppp, hdi, host, champion, …) for Bases/Dataview; see `build_typed_frontmatter`. Expands a large set of canon data templates (see `_expand_one`). Never writes back to the wiki.

## Environment

Requires a gitignored `.env` (never commit it):
```
WIKI_API=https://andah.miraheze.org/w/api.php
WIKI_USER=BotUsername@BotName
WIKI_PASS=bot-password-here
EDIT_SUMMARY=Optional default edit summary
# Optional: override the Obsidian vault target for to_obsidian.py
# (defaults to Andah-Wiki/ beside the script if unset)
# OBSIDIAN_VAULT=C:\Users\danny\Documents\miraheze-local\Andah-Wiki
```
Bot password is created at `Special:BotPasswords`. Auth is a two-step login-token → login flow repeated in each script's `session_login()`. Python deps: `requests`, `python-dotenv` (plus `openpyxl` for `generate_cities.py`). Use the venv in `venv/`.

Edits are flagged `bot=1`, keeping Recent Changes clean if the account has the bot flag.

## Editing wiki pages

Pages are plain MediaWiki wikitext. When editing:
- Preserve existing templates, categories, and infobox syntax unless explicitly asked to change them.
- Treat `[[links]]`, `{{templates}}`, and `<ref>` tags as structured markup — don't reformat them as prose.
- Don't hand-edit inside `<!-- LARGEST-CITIES-AUTO ... -->` blocks; regenerate them with `generate_cities.py` instead.

## Canon and writing conventions

These are project rules, not preferences — violating them has repeatedly forced full rewrites and page deletions.

**Never invent proper nouns.** Cities, countries, regions, hosts, players, currencies, organisations — the canon name almost always already exists. Before writing any new proper noun, check `data/`:
- `data/<Continent> Cities.xlsx` (Ayuma, Atirha, Acrola, Mahea, Massir, Quia, New Ayre) — one **sheet per country**, and the sheet name IS the canonical country name. The rows are that country's canonical cities.
- `data/Largest Cities by Population.xlsx` — global pop-ranked cities; use this **first** when picking a city for any size- or prominence-related role.
- `data/List of FLLA World Cup Host Nations.xlsx` — locked-in hosts/winners/scores per World Cup year.

If no canon entry fits, **ask the user before inventing** — do not fabricate to fill a gap (e.g. an Nth qualifier in a confederation).

**Style:**
- **British spelling** throughout (centre, programme, organised, colour, defence, travelling).
- **No em-dashes (`—`).** Use commas, semicolons, or parentheses. En-dash `–` is fine for scorelines/date ranges; hyphen `-` for compounds. Sweep for `—` before pushing.
- **Currency:** the `{{lahn}}` template (the lahn is the FLLA reserve currency), with `&nbsp;` before scale words, e.g. `{{lahn}}1.98&nbsp;billion`.
- **Dates:** DD Month YYYY (e.g. `11 June 1760`). Current in-universe data is ~1763–1765.

**Citations:** reuse the established in-universe sources rather than inventing competing ones. By domain: **Global Trade Union** (GTU) for economy/GDP/trade/ports; **World Data Union** / `Census <Country>` for population/area; **Krali Development Report** for HDI; **FLLA** + the seven confederations (AYFVL, ATFVL, NAFVL, MAFVL, QUFVL, MSFVL, ACFVL) for football; **The Andah Factbook** / BBC News Andah for general facts; **Council on Vertical Urbanism** for tallest buildings. Any page with `<ref>` tags must also have `== References ==` + `{{reflist}}` before the category block, or the refs won't render.

## Knowledge graph (graphify)

`graphify-out/` is a generated knowledge graph of the wiki corpus (`graph.json`, `graph.html`, `GRAPH_REPORT.md`), built from the page snapshot in `graphify-wiki-corpus/`. Treat questions about the wiki's content, structure, or how articles interrelate as graphify queries — invoke the `/graphify` skill rather than grepping 530 articles by hand. Regenerate after large content changes if the graph is being relied on.

## Further context

When this file isn't enough, route to the deeper sources:

- **Setup / onboarding** — [README.md](README.md) (bot-password setup, daily workflow walkthrough).
- **Exact script behaviour** — each script has a module docstring explaining its contract: [pull.py](pull.py), [push.py](push.py), [push_recent.py](push_recent.py), [_publish_new.py](_publish_new.py), [generate_cities.py](generate_cities.py), [to_obsidian.py](to_obsidian.py). Read these before changing sync logic.
- **Canon names / data** — the [data/](data/) xlsx spreadsheets are the source of truth (see "Canon and writing conventions" above). Inspect with `openpyxl`; sheet names and rows are authoritative.
- **Corpus overview** — [graphify-out/GRAPH_REPORT.md](graphify-out/GRAPH_REPORT.md) summarises the wiki's main entities and clusters; the live graph lives in `graphify-out/graph.json`.
- **Deep in-universe lore** (religion families, FLLA award names, trophy system, Lycroan history, cities data structure, wiki skin/CSS) — captured as session memory under `C:\Users\danny\.claude\projects\c--Users-danny-Documents-miraheze-local\memory\`, indexed by `MEMORY.md`. These auto-load each session; consult them before writing domain-specific lore, and update them when canon changes.
