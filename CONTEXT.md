# CONTEXT.md

The domain model for **miraheze-local**: the shared vocabulary, the core entities
and how they relate, and the decisions behind them.

This is the *why* and *what-things-mean* companion to [CLAUDE.md](CLAUDE.md), which
covers the *how* (commands, scripts, conventions). When the two overlap, CLAUDE.md
is authoritative on procedure; this file is authoritative on meaning. Canon lore
lives in the session memory under `~/.claude/projects/.../memory/` (indexed by
`MEMORY.md`); this file points at it rather than restating it.

---

## Two domains in one repo

The project sits at the seam of two unrelated domains, and most confusion comes
from conflating them:

1. **The sync layer** — a thin, conservative client over the MediaWiki `action`
   API that moves wiki pages between `andah.miraheze.org` and local `.wiki` files.
   This is *plumbing*: Python scripts, `.state.json`, revisions, conflict checks.
2. **The world of Andah** — the fictional setting the wiki documents: countries,
   cities, the FLLA World Cup, religions, currencies. This is *content*, governed
   by canon, and the canon lives in spreadsheets and lore, not in the code.

A change is usually in one domain or the other. "Push didn't send my edit" is a
sync question. "Who hosted the 1744 World Cup" is a canon question. Keep them apart.

---

## Ubiquitous language

### Sync / tooling

| Term | Meaning |
| --- | --- |
| **Tracked page** | A wiki page that has a local `.wiki` file and an entry in `.state.json`. |
| **`.state.json`** | The single source of truth for the local↔remote mapping: title → `{ revid, path }`. Gitignored, so it exists only on this machine. Without it, push has nothing to act on. |
| **revid** | The remote revision number recorded at last pull. The *baseline* push checks against. |
| **baserevid** | The revid sent with an edit so the wiki rejects the write if the page moved on since pull (lost-update protection). |
| **Conflict / drift** | Remote revid no longer matches the `.state.json` baseline → the page changed on the wiki since your last pull. Push skips it with a WARN; you pull again to reconcile. |
| **Namespace folder** | `pages/<NamespaceFolder>/` — `Main`, `Template`, `Category`, `Module`, etc., defined by `NS_NAMES` in `pull.py`. The folder *encodes the namespace*, so non-Main filenames drop the `Template:`-style prefix. |
| **Title ↔ filename mapping** | Spaces→`_`, subpage `/`→`__`, prefix stripped for non-Main. `safe_filename` (pull) does title→path; `_publish_new.py` reverses path→title. Filename ≠ title — always convert, never assume. |
| **`nocreate` / `createonly`** | Push uses `nocreate=1` (never creates a page). Creation is a separate, deliberate act via `_publish_new.py` / `_create_new.py` with `createonly=1`. |

### The world (canon)

| Term | Meaning |
| --- | --- |
| **Andah** | The fictional world the whole wiki documents. In-universe "now" is ~1763–1765. |
| **Continents (7)** | Ayuma, Atirha, Acrola, Mahea, Massir, Quia, New Ayre. Each has one football confederation and a `data/<Continent> Cities.xlsx` roster (one sheet per country, sheet name = canonical country name). |
| **FLLA** | The world football governing body. Runs the **FLLA World Cup** (a.k.a. Andah World Cup), held every 4 years; editions are numbered (1700 = 8th edition, so the 1st was 1672). |
| **Confederations (7)** | One per continent, each running its own qualification format (mirroring a real-world confederation). See the table below. |
| **lahn** | The FLLA reserve currency. Always rendered with the `{{lahn}}` template, `&nbsp;` before scale words: `{{lahn}}1.98&nbsp;billion`. |
| **FLLA seed (`#N`)** | A nation's world ranking, shown in sim outputs as `(FLLA #5)`. |
| **The lahn / GTU / Census / Krali** | Canonical citation bodies by domain — reuse, never invent competitors. See the `citation_sources` memory. |

#### Confederation map

| Continent | Confederation | Qual. format (real-world analogue) |
| --- | --- | --- |
| Ayuma | AFLA | Europe (UEFA) |
| Atirha | NFLA | North America (CONCACAF) |
| New Ayre | NAFLA | South America (CONMEBOL) |
| Mahea | EFLA | Europe (UEFA) |
| Quia | QFLA | Asia (AFC) |
| Massir | MFLA | Asia (AFC) |
| Acrola | CFLA | Africa (CAF) |

> **Known terminology drift:** simulation outputs and most pages use the `*FLA`
> abbreviations above, but CLAUDE.md's citation section names the same seven bodies
> as `AYFVL / ATFVL / NAFVL / MAFVL / QUFVL / MSFVL / ACFVL`. Two schemes for one
> set of entities. Treat `*FLA` (from the sim files and the graph) as the working
> standard; reconcile before relying on the other.

---

## Core entities & relationships

### The sync pipeline (pull → edit → push)

```
MediaWiki API  ──pull.py──▶  pages/**/*.wiki   ──(you / Claude edit)──▶  changed files
      ▲                           │                                          │
      │                      .state.json  ◀──records revid──────────────────┘
      └──────────────push.py◀────┘  (re-fetches remote, skips if equal or drifted,
                                      sends edit with baserevid + nocreate)
```

- **`.state.json` is the hub.** Pull writes it, push reads it, `push_recent.py`
  and the creation helpers update it. Every other component connects through it
  (it has the highest cross-component centrality in the graph). Lose it and the
  local tree is just orphaned text files.
- **Push is conservative by design.** It compares against *live remote content*,
  not file mtime, so editing a file and reverting it produces zero edits, and a
  page changed on the wiki since pull is protected, not clobbered.
- **Creation is opt-in.** The everyday loop can never create pages; new pages are
  a separate, explicit step.

### The Andah World Cup model

The richest content cluster. The recurring entity is **FLLA World Cup
(tournament series)**, with one page per edition (`<YEAR>_FLLA_World_Cup.wiki`,
plus `_qualification` and `_squads` subpages for some years). Each edition links to:

- **Nations / football teams** — the same ~25 top sides recur as competitors
  (Raledria, Lycroa, Verusa, Emara, Easuhura, Finae, Sanagara, Seytinemas, …).
- **Per-edition lore** that the wiki treats as canon and must stay consistent
  across pages:
  - 1716 — Estijan PED ban
  - 1724 — "groups of three" format controversy
  - 1736 — floodlight incident in the final
  - 1740 — two-trophy system begins (rotating **Andah Cup** + bespoke permanent
    trophy per edition; see the `flla_trophy_system` memory)
  - 1742 — confederation rotation policy
  - 1748 — "greatest World Cup in history"
  - 1764 — "Miracle of Rovik" (Easuhura's QF upset of Raledria)

---

## Source-of-truth hierarchy

When facts conflict, trust in this order:

1. **`data/*.xlsx`** — canonical names and locked outcomes. City rosters per
   continent; `Largest Cities by Population.xlsx` for size/prominence picks;
   `List of FLLA World Cup Host Nations.xlsx` for locked hosts/winners/scores.
   See the `data_canon_files` and `cities_data_structure` memories.
2. **`Simulation results/*.txt`** — generated match/standings data for each World
   Cup edition, the raw material for the edition pages (see workstream below).
3. **The wiki pages themselves** — existing canon to preserve and extend.
4. **`graphify-out/`** — a derived map of how it all interrelates; useful for
   navigation, not authority. Regenerate after large content changes.

> **Never invent proper nouns.** Cities, countries, hosts, players, currencies
> almost always already exist in `data/`. If nothing fits, ask before inventing.

---

## Decisions worth knowing

- **`.state.json` is gitignored on purpose** — large and machine-specific. The
  repo is portable; the local mapping is not.
- **Compare-against-remote, not mtime** — the reason push is safe to run broadly
  and idempotent.
- **British spelling, no em-dashes (`—`)** — project rule, not preference;
  violating it has forced rewrites. `–` for scorelines/ranges, `-` for compounds.
  Sweep for `—` before any push. See the `wiki_conventions` memory.
- **Canon award names** — sim outputs say "Golden Boot"; canon renames the awards
  to **Vairan Ball** (best player), **Marskval** (top scorer), **Bastion** (best
  goalkeeper). Canonicalise on transcription. See the `flla_award_names` memory.
- **Refs require a tail** — any page with `<ref>` needs `== References ==` +
  `{{reflist}}` before the category block or refs won't render.

---

## Active workstream (as of 2026-06-15)

Transcribing the **`Simulation results/*.txt`** files into the FLLA World Cup
edition pages. The sim files come in two shapes:

- **Full bracket** (e.g. `1764-world-cup.txt`) — champion, podium, top scorer,
  upsets, continental qualifiers with standings, group stage, knockout rounds.
- **Bare ranked list** (e.g. `1656-`, `1676-world-cup.txt`) — just final
  placements, for the earlier/lighter editions.

The currently-modified pages (`git status`) are the World Cup editions 1656→1768
plus a few `_qualification` / `_squads` subpages and the cross-edition summary
pages (`List_of_FLLA_World_Cup_finals`, `..._hosts`,
`National_team_appearances_...`). When transcribing: apply the canon award names,
keep nation names exactly as the canon spells them, honour locked hosts/winners
from `data/`, and run `python push.py --dry-run` before sending.

---

## Where to look next

- **Procedure / commands** → [CLAUDE.md](CLAUDE.md)
- **Onboarding / bot setup** → [README.md](README.md)
- **Script contracts** → module docstrings in [pull.py](pull.py), [push.py](push.py),
  [push_recent.py](push_recent.py), [_publish_new.py](_publish_new.py)
- **Canon data** → the `data/` spreadsheets (sheet names + rows are authoritative)
- **Corpus map** → [graphify-out/GRAPH_REPORT.md](graphify-out/GRAPH_REPORT.md)
- **Deep lore** → session memory files indexed by `MEMORY.md`
