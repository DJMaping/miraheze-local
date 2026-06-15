# AGENTS.md

Guidance for AI coding agents working in **miraheze-local**. This is the tool-agnostic
companion to [CLAUDE.md](CLAUDE.md); CLAUDE.md is the authoritative, fuller source — read it
when this file isn't enough.

## What this repo is

A local editing environment for the **Andah wiki** (`andah.miraheze.org`), a Miraheze-hosted
MediaWiki for a fictional world. The workflow: pull wiki pages to disk → edit the `.wiki` files →
push changes back via the MediaWiki `action` API. Most editing happens in `pages/Main/`.

Scale: ~3,250 tracked pages (~530 Main articles, ~1,580 Templates, ~340 Modules, ~510 Files,
~140 Categories).

## Setup

- Python project. Use the venv in `venv/`. Deps: `requests`, `python-dotenv` (plus `openpyxl`
  for the data scripts).
- Requires a gitignored `.env` (never commit it):
  ```
  WIKI_API=https://andah.miraheze.org/w/api.php
  WIKI_USER=BotUsername@BotName
  WIKI_PASS=bot-password-here
  EDIT_SUMMARY=Optional default edit summary
  # OBSIDIAN_VAULT=optional vault path for to_obsidian.py (default: Andah-Wiki/ beside the script)
  ```
  Bot password is created at `Special:BotPasswords`.
- `.state.json` is the local index (gitignored). It maps each page title to
  `{ revid, path }` and is the single source of truth for what maps to what. Without it, push
  has nothing to do.

## Commands

```bash
python pull.py                        # Pull all main-namespace pages
python pull.py "Page Title"           # Pull one page (namespace inferred from prefix)
python pull.py --ns 10                # Pull templates (namespace 10)
python pull.py --all-ns               # Pull every namespace

python push.py --dry-run              # Preview what would be sent (no login, no writes)
python push.py -m "Edit summary"      # Push all changed pages
python push.py pages/Main/Foo.wiki    # Push specific file(s)

python push_recent.py                 # Push only files changed since the last push_recent run
python _publish_new.py pages/Main/NewPage.wiki   # Create a page that doesn't exist yet
```

**Always run `python push.py --dry-run` first after bulk edits** to review what will be sent.

## How sync works (and why it's safe)

- **Pull** lists pages, fetches content + revid, writes the file, records the revid in `.state.json`.
- **Push** is deliberately conservative. Per file it: (1) re-fetches the *current* remote content,
  (2) skips if local == remote, (3) skips with a WARN if the remote revid no longer matches the
  `.state.json` baseline (the page changed on the wiki since your last pull — pull again to
  reconcile), then (4) sends the edit with `baserevid` + `nocreate=1`.
- Because push compares against live remote content, editing a file and reverting it produces
  zero edits.
- `push.py` uses `nocreate=1` and will **never** create a page. To create new pages use
  `_publish_new.py` (derives title from path, registers in `.state.json`).

## Title ↔ filename mapping

Files live at `pages/<NamespaceFolder>/<Title>.wiki` (`0→Main`, `10→Template`, `14→Category`,
`828→Module`, …). Conversions (`safe_filename` in `pull.py`): spaces → underscores, subpage `/` →
`__`, and for non-Main namespaces the `Template:`-style prefix is stripped from the filename.
`_publish_new.py` reverses this. **Don't assume filename == title** — mirror this logic.

## Editing rules (these are hard project rules, not preferences)

Violating the canon rules below has repeatedly forced full rewrites and page deletions.

- **Never invent proper nouns.** Cities, countries, regions, hosts, players, currencies, orgs —
  the canon name almost always already exists. Check `data/` first:
  - `data/<Continent> Cities.xlsx` — one **sheet per country**; the sheet name IS the canonical
    country name, and its rows are that country's canonical cities.
  - `data/Largest Cities by Population.xlsx` — global pop-ranked cities; use this **first** when
    picking a city for any size/prominence role.
  - `data/List of FLLA World Cup Host Nations.xlsx` — locked-in hosts/winners/scores per year.
  - If no canon entry fits, **ask the user before inventing.** Do not fabricate to fill a gap.
- **British spelling** throughout (centre, programme, organised, colour, defence, travelling).
- **No em-dashes (`—`).** Use commas, semicolons, or parentheses. En-dash `–` is fine for
  scorelines/date ranges; hyphen `-` for compounds. Sweep for `—` before pushing.
- **Currency:** the `{{lahn}}` template with `&nbsp;` before scale words, e.g.
  `{{lahn}}1.98&nbsp;billion`.
- **Dates:** DD Month YYYY (e.g. `11 June 1760`). Current in-universe data is ~1763–1765.
- **Citations:** reuse established in-universe sources, don't invent competing ones — GTU
  (economy/trade), World Data Union / `Census <Country>` (population/area), Krali Development
  Report (HDI), FLLA + the seven confederations (football), The Andah Factbook / BBC News Andah
  (general), Council on Vertical Urbanism (tallest buildings). Any page with `<ref>` tags needs
  `== References ==` + `{{reflist}}` before the category block or refs won't render.
- **Preserve markup:** treat `[[links]]`, `{{templates}}`, `<ref>` tags, categories, and infobox
  syntax as structured markup — don't reformat as prose or change them unless asked.
- **Don't hand-edit inside `<!-- LARGEST-CITIES-AUTO ... -->` blocks** — regenerate with
  `generate_cities.py`.

## One-off data / conversion scripts (not part of pull/push)

- `generate_cities.py` — regenerates `== Largest cities ==` sections from the `data/*Cities*.xlsx`
  spreadsheets. `python generate_cities.py dry [Country...]` to preview, `apply` to write.
  Idempotent (replaces the `LARGEST-CITIES-AUTO` block).
- `to_obsidian.py` — one-directional export of Main + Category pages to an Obsidian vault (target
  resolved by `resolve_vault`: `--vault` > `OBSIDIAN_VAULT` env > default `Andah-Wiki/` beside the
  script). Writes `<vault>/Articles/` + `<vault>/Categories/`, both **overwritten every run** (never
  hand-edit; keep hand-authored notes elsewhere), with typed, queryable frontmatter (`type:` +
  per-type fields). Never writes back to the wiki.

## Conventions for changes to this repo

- Read each script's module docstring before changing sync logic ([pull.py](pull.py),
  [push.py](push.py), [push_recent.py](push_recent.py), [_publish_new.py](_publish_new.py)).
- Inspect `data/` spreadsheets with `openpyxl`; sheet names and rows are authoritative.
- Edits are flagged `bot=1` to keep Recent Changes clean.
