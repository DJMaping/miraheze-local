# Andah Wiki — Content Audit & Prioritised Backlog

*Generated 2026-07-24. Read-only audit — nothing was edited. Method: deterministic scan of all 562 `pages/Main/*.wiki` files, cross-referenced against the canon spreadsheets in `data/` (Cities per continent, Largest Cities by Population, FLLA World Cup Host Nations), plus three focused deep-read passes (country depth, World Cup cluster, thematic breadth).*

**Corpus at a glance:** 562 Main pages = 530 articles + 32 redirects. Of the articles, **172 are country pages (the full canonical set — 172/172, none missing)**, ~130–140 are other content, and the rest is MediaWiki/template infrastructure. Country pages are **structurally uniform** (all share the same 8 sections + infobox) — so the country problem is *depth and hygiene*, not missing scaffolding.

> ⚠️ **Note on the graph:** `graphify-out/` is stale — it was built from only 31 files (the Python scripts + simulation text dumps), **not** the 530 articles. Its "god nodes" and communities describe the *codebase*, not the wiki content. Don't trust it for content questions until regenerated against a real page snapshot. (Added as backlog item T-4.)

---

## Top 5 next actions

1. **Strip the pasted Wikipedia template-category block from ~177 country articles** (§A1). Every country page carries ~20 junk categories copied from Wikipedia's `{{Infobox country}}` docs — including `[[Category:Country data templates of Germany]]`, `Wikipedia metatemplates`, `Pages with script errors`, and `Pages with template loops`. This is why a third of the wiki shows up under "script errors" and why **real-world Germany appears on 178 pages**. One mechanical bulk edit, enormous hygiene win. **(large but purely mechanical)**
2. **Create the missing citation-source pages and the top-level `Andah` page** (§A2). Six targets account for **>1,100 red-links**: Global Trade Union (467), Andah Factbook (201), Krali Development Report (179), BBC News Andah (173), World Data Union, and `Andah` itself (92). Every sourced claim on the wiki currently links into a void. All names already exist — no invention needed. **(medium)**
3. **Fix the hard consistency/canon bugs** (§E). A handful of cheap edits protect canon integrity: the 1768 "Massir since 1740" factual error, Trevilla's broken capital link, Rethern's `[[Xxvii]]` placeholder capital, New Kizura's swapped GDP figures, and stray author to-do notes shipped live in *Economy of Ashain*. (The 1760 runner-up conflict is a *decision* — see §NEEDS-DECISION.) **(quick)**
4. **Run the style sweep** (§C): currency not using `{{lahn}}` (Ikzen, Laselteh, Mesjan Hyaa, Vesozata, Economy of Virauzau, Vurahi, Economy of Ashain), ~20 American spellings, and 11 em-dashes across 7 pages. All quick, all enforce documented house rules. **(quick)**
5. **Fill the highest-value red-links** (§B): the top ~25 missing large cities — starting with **Fekhalai**, the single largest city in the world (42.5M) with no page. Every name is in the spreadsheets. **(large, but incremental)** *(The country set is complete — 172/172 — see §A3.)*

---

## A. Missing pages — most-linked & structural gaps

### A1. Systematic mis-categorisation of country articles — *the biggest single issue*
- **Affected:** ~177 country articles (Acetoa, Ashain, Areoix Lie, … essentially every `{{Infobox country}}` page). See lines ~115–135 of `Acetoa.wiki` / ~187–207 of `Ashain.wiki` for the pattern.
- **What's wrong:** each page ends with a ~20-line block of categories copy-pasted from Wikipedia's Infobox-country documentation, none of which belong on an Andah country article:
  `Country data templates of Germany`, `All country data templates`, `Country infobox templates`, `Wikipedia metatemplates`, `Templates using TemplateData`, `Lua-based templates`, `Template documentation pages`, `Pages with script errors`, `Pages with template loops`, `Pages using duplicate arguments in template calls`, `Sidebars with styles needing conversion`, etc. Only `[[Category:Countries]]` (and occasionally a real one) should remain.
- **Why it matters:** (1) real-world **Germany** now appears on 178 pages; (2) 181 pages show under `Pages with script errors` and 173 under `Pages with template loops`, so the maintenance categories are meaningless noise; (3) the category system — the reader's main navigation — is polluted wiki-wide.
- **Effort:** **large but mechanical.** A single scripted find-and-remove of the known junk category lines across all country pages, then `push.py --dry-run` to review. High reward per unit effort.

### A2. Missing citation-source pages + the world page (>1,100 red-links)
- **Affected / red-link counts:** `Global Trade Union` (467), `The Andah Factbook` (201), `Krali Development Report` (179), `BBC News Andah` (173), `Andah` (92), plus `World Data Union`, `GTU Geological Survey` (33), `Council on Vertical Urbanism`. **None exist.**
- **Why it matters:** these are the wiki's most-linked targets by a wide margin. Every `<ref>` on the site points at a red-link, and the top-level `Andah` page (the natural front door for continents/oceans/religions) is absent. Creating even short stub pages for each turns thousands of dead links live.
- **Effort:** **medium.** Names and remits already exist (see the "Citations" table in CLAUDE.md); each is a short institutional stub. Safe — no invention.

### A3. Missing country pages — NONE. The country set is complete (172/172).
- **Correction:** an earlier draft of this audit claimed 6 missing countries. That was **wrong** — an artefact of matching the *sheet-tab names* inside `data/*Cities*.xlsx` against page titles. All six exist on-wiki; the **spreadsheet sheet names are simply misspelled** relative to the canonical page titles:

  | Cities-sheet tab | Actual page | Continent |
  |---|---|---|
  | Eteretes | **Etretes** | Massir |
  | Isubul | **Isuibul** | New Ayre |
  | Oryreain | **Oyreain** | Massir |
  | Syliaduun | **Slyiaduun** | Atirha |
  | Praesy | **Praesyu** | Ayuma |
  | Yihnurga | **Yihnurda** | Quia |

- **The real finding (data hygiene, not content):** the Cities spreadsheets — which CLAUDE.md treats as canonical for country names — contain **at least 6 mis-spelled sheet tabs**. Anything that trusts those tab names (this audit's first pass, `generate_cities.py`'s `ALIAS` map, future tooling) can silently mis-key. Worth a pass to correct the tab names to match the wiki, or extend `generate_cities.py`'s `ALIAS` to cover them.
- **Effort:** **quick** (rename 6 spreadsheet tabs / add 6 aliases). No wiki pages needed.

### A4. Missing city pages — large gap
- **Coverage:** of the population-ranked cities, **14 of the top 25, 34 of the top 50, and 81 of the top 100 have no page.** *(Verified: the top-14 "missing" cities have no near-spelling page either — unlike the country case in §A3, these are genuine gaps. The deeper counts should still be treated as an upper bound, since city names in the spreadsheet may occasionally diverge from page titles the way the sheet tabs did.)*
- **Flagship omission:** `Fekhalai` (Dahe) — the **largest city in the world at 42.5M** — has no article, yet the much smaller Vurahi has a nine-page cluster.
- **Other top-25 gaps:** Havok, Bhaliloi, Kejira, Tirna-Rovik, Tiraqsi, Mihkose, Nakahiki, Xuqilin, Shurqan, Shinlotha, Zunle, Kaisri, Vrandig.
- **Why it matters:** cities are heavily red-linked from country "Largest cities" tables and World Cup host/venue prose; they're the natural next tier of geography content.
- **Effort:** **large (incremental).** Every name + population + country is in `data/Largest Cities by Population.xlsx`; work top-down. Safe to expand.

---

## B. Stubs & thin pages

### B1. Infobox-only "shell" country pages (~30+)
- **Affected (thinnest):** Letan, Trevilla, Rethern, Stinebar, New Kizura, Tonder, Yoprioq, Peka, Niul Spijan, Koruch, Viussi, Umendel (~4.8–5.6 KB each).
- **What's wrong:** a complete infobox followed by **all eight standard section headers left empty** — no prose at all. The only body content is the auto-generated `== Largest cities ==` line ("population figures not yet available"). Contrast the flagships **Easuhura (63 KB)** and **Dahe (53 KB)**, which have deep multi-paragraph leads, `===`/`====` sub-sections, densely sourced stats, images, `{{Main|…}}` sub-articles, and named people/institutions.
- **Why it matters:** ~30 nations are effectively blank behind a data card; this is the single largest volume of "world-building not yet written."
- **Effort:** **medium–large per page**, and partly blocked on canon — leader names, extra cities, parties and landmarks would have to be invented (see §NEEDS-DECISION). The *sourced infobox scaffolding already exists*, so prose can attach to real refs once written.

### B2. The seven confederations are one-line stubs
- **Affected:** `AYFVL`, `ATFVL`, `NAFVL`, `MAFVL`, `QUFVL`, `MSFVL`, `ACFVL` (~280–295 B each, all tagged `{{stub}}`).
- **What's wrong:** each is a single sentence naming its 1764 berths. These are core hub entities (the WC pages cite all seven constantly) yet carry no history, member list, format, or honours.
- **Why it matters:** high link-centrality, low content — cheap to make a real difference. Old names `AFLA`/`NFLA`/`NAFLA`/`EFLA`/`QFLA`/`MFLA`/`CFLA` already redirect here correctly (good).
- **Effort:** **medium.** Member nations and berth data are derivable from the country set + WC pages.

### B3. Religion — full scaffold, zero depth
- **Affected:** 7 religions (Imarel, Kelhari, Passanu, Srivandha, Kallimethra, Thessovai, Tzinalli) + ~22 denomination pages — **all 29 are <440 B near-identical stubs**; the hub `Religion in Andah` is a red-link.
- **Why it matters:** an entire belief-system domain is named but unwritten — a conspicuous world-building hole.
- **Effort:** **large.** Religion/denomination *names* exist (safe to structure), but deities, scripture, clergy and history would be net-new invention (§NEEDS-DECISION).

### B4. Bodies of water — boilerplate stubs
- **Affected:** ~16 seas + ~6 oceans, almost all 140–250 B ("The X Sea is a sea of Andah."): Dursio, Eashor, Josnon, Sheilia, Ashanian, Keisashi, Adrad, Praosia, Nasuanian, Pagnim, Kera, Ubrana, Uscea, Diairesi, Rianian, Trayd Cren; oceans Haanian, Srandan, Vihsanna, Rianian, Eanif, Hinsakian.
- **Why it matters:** low individual importance, but they're cheap wins and improve geography connectivity.
- **Effort:** **quick each** — a couple of sentences on location/adjacency (partly implied by region pages).

### B5. Other notable stubs / placeholders
- `Zirhu` — **0 bytes** (delete or write). `sandbox` — leftover.
- `List of ongoing armed conflicts` (18 B "under construction"), `List of language families` (one line), `Science and Technology in Ashain` (66 B holder), `Alzurian Union` (33 B, "too much lore to do rn"), `Premier of Virauzau` (18 B "TBC"), `Member of Provincial Parliament (MPP)` (placeholder).
- **Effort:** quick each; several are populatable from existing pages (e.g. ongoing-conflicts from the war/empire articles).

---

## C. Style & house-rule sweeps *(all quick, all documented rules)*

### C1. Currency not using `{{lahn}}`
- **Bare `$`:** `Ikzen` (`$19.845 billion`, `$6,395` …), `Laselteh` (`$183.882 billion`, `$28,183` …), `Mesjan Hyaa` (`$61.985 billion` …).
- **Redundant `{{lahn}}$`:** `Vesozata` (`{{lahn}}$3,099`), and the continent infoboxes on `Atirha` / `Mahea` (`{{lahn}}$13.715 trillion` …).
- **Hardcoded `₳` glyph + `$` conversions:** `Economy of Virauzau` (`₳1 billion ($185,1 million)` …), `Vurahi` (`₳60,000`, `₳1.77 trillion` …).
- **The word "dollars":** `Economy of Ashain` ("…X dollars worth of machinery goods").
- **Effort:** quick — normalise to `{{lahn}}` with `&nbsp;` before scale words.

### C2. American spellings (~20 content pages, markup-stripped)
- `Dahe` (center → centre; program, realize), `Economy of Ashain` (defense, organization, organized, program), `Sanagara` / `Ztesh` (neighbor), `Verste` (honor), `Moksha Mountains` / `Red Desert` / `Siita Desert` (meters), `Easuhura`/`Grazail`/`Vera Namqic`/`Moaneill`/`Raledria`/`Vurahi`/`Ilicuhe`/`Eldjo` (organization/organizations), `Hyelen` (favor), `Great Imperial War` (defense, harbor), `Zirohu` (harbor), `Hiemuekan Desert` (program), `Province of Rusiguii` (organized). (Several GDP/credit-rating list pages use `color=` — check whether prose vs. template arg before changing.)
- **Effort:** quick sweep.

### C3. Em-dashes (11 total, 7 pages)
- `List of tallest buildings` (4), `1752 FLLA World Cup qualification` (2), `Blockquote`, `Lists of countries by mineral production`, `List of languages by number of native speakers`, `List of languages by total number of speakers`, `Vurahi` (1 each).
- **Effort:** quick — replace with comma/semicolon/parentheses (en-dash `–` only for scores/ranges).

---

## D. Connectivity — orphans & uncategorised pages

### D1. Substantial orphan articles (no inbound links) — 37 of note
- **Biggest:** `National team appearances in the FLLA World Cup` (**108 KB!**), `List of countries by credit rating` (44 KB), `List of tallest buildings` (42 KB), `Economy of Easuhura` (30 KB), `Rovik Global University Rankings` (27 KB), `List of busiest container ports`, `List of countries by number of billionaires`, `Geography of Easuhura`, `Demographics of the Easuhura`, plus geography pages `Ryska River`, `Koaissa Desert`, `Lake Keetsuc`, `Emaran Peninsula`, several deserts.
- **Why it matters:** major content nobody can reach by clicking — link them from the relevant country pages, `List of…` hubs, and (once created) the `Andah` page.
- **Effort:** quick–medium (add inbound links; no new content).

### D2. Uncategorised content pages (~90)
- **Notable:** `Economy of Easuhura` (30 KB), `Geography of Easuhura`, `Government of Ashain`, `Arten cuisine`, and the whole Vurahi cluster (`The City of Vurahi`, `Mayor of Vurahi`, `Deputy Mayor of Vurahi`, `Legend of Vurahin`, `Catacombs of Vurahi`, `Corporation of Vurahi`), plus `Empire of Areoix Lie`, `Cratavian Empire`, `Almaglean Empire`.
- **Why it matters:** invisible to category navigation despite being well-developed.
- **Effort:** quick — add appropriate categories.

---

## E. Consistency / canon-integrity bugs *(quick fixes, high value)*

| Page(s) | Problem | Fix |
|---|---|---|
| `1768 FLLA World Cup` | Says "first held in **Massir** since the **1740 edition in Seytinemas**" — but 1740/Seytinemas was in **Mahea**, and the last Massir edition was **1732 (Dahe)**. Self-contradicts the 1732 & 1740 pages. | Correct to "since 1732 (Dahe)". **quick** |
| `1768 FLLA World Cup` | Has `== References ==` + `{{reflist}}` but **0 `<ref>`** — host-award/reseeding claims uncited; also references `File:1768 …qualification.png` with no qualification subpage. | Add refs or trim the reflist. **quick** |
| `1756`, `1760 FLLA World Cup` | Infoboxes **omit the Continent field** that every other developed edition has (should be Quia, Ayuma). | Add field. **quick** |
| `Trevilla` | Capital link mismatch: infobox `[[City Tirnsch]]` vs Largest-cities list `[[City Trinsch]]` — one is a broken link. | Reconcile spelling. **quick** |
| `New Kizura` | GDP figures look **transposed**: `GDP_nominal {{lahn}}5.438 bn > GDP_PPP {{lahn}}4.361 bn`, and nominal-per-capita > PPP-per-capita (reverse of every other page). | Verify/swap. **quick** |
| `Rethern` | Capital is a literal placeholder `[[Xxvii]]` (in `capital`, `largest_city`, and the cities list). | Needs a real city name (§NEEDS-DECISION). **quick once named** |
| `Dahe` | Naming drift in one clause: "coup in Fekhalai\|coup in **Fekunzai**" while the capital is **Fekunza**. | Pick one spelling. **quick** |
| `Dahe`, `Easuhura` | Unresolved placeholder blanks shipped in live prose: "divided into **___** province-level divisions", "**____**-largest exporter". | Fill or remove. **quick** |
| `Economy of Ashain` | Author to-do notes **live in the article body**: "produced …**X dollars** worth…", "(Lahn symbol)", HTML comment "Steal from that government report… steal the finnish model." | Remove/replace. **quick** |

---

## F. Coverage imbalance (where the world is thin)

| Domain | State | Verdict |
|---|---|---|
| Football / World Cup | 25 WC editions + Ayuman Cup + finals/hosts/appearances, all richly sourced, all seven confederations cited | **Over-developed** (the wiki's spine) |
| Countries (structure) | 166/172 present, uniform 8-section template | Complete scaffolding |
| Countries (depth) | 2 flagships at 53–63 KB, ~30 empty shells, long tail ~6.6 KB median | **Very uneven** |
| Economy / finance | Best non-football domain — 31 mineral lists, GDP/ports/ratings, two 30–42 KB economy pages | Strong |
| Indices / lists | Democracy Index (39 KB), tallest buildings (43 KB), nuclear states (54 KB), university rankings (28 KB) | Strong |
| Geography | Regions/continents OK; deserts/mountains/rivers fine; **seas/oceans/lakes mostly stubs** | Mixed |
| **Religion** | 7 religions + 22 denominations, **all stubs**; hub missing | **Thin** |
| **People / biographies** | **Only 2 in-world bios** (both Vurahi officials); footballers exist only in squad tables | **Nearly absent** |
| **Languages** | **Zero articles**; Emaran/Lastnu/Arten referenced only | **Absent** |
| **Science & technology** | 1 holder page + a rankings list | **Absent** |
| Non-sport organisations / offices | A few (Alzurian Union, Corporation of Vurahi, DAEL) mostly thin | Thin |

**Takeaway:** the world is a football encyclopaedia bolted onto a uniform-but-shallow atlas. The cheapest breadth wins are religion depth, languages, and biographies — but those are the domains that most need canon input (below).

---

## NEEDS-DECISION — items blocked on your canon call (no invented names proposed)

1. **1760 World Cup runner-up: `Darewa` (spreadsheet) vs `Raledria` (every wiki page).** The host-nations sheet lists Darewa; `1760 FLLA World Cup`, `List of FLLA World Cup finals`, and its Raledria summary row all say Raledria. Genuine source-vs-wiki divergence — pick the canonical answer; if Darewa, it cascades to the finals list and needs Darewa football content.
2. **Spreadsheet tab names vs. canonical page spellings (6 nations).** The Cities-sheet tabs `Eteretes / Isubul / Oryreain / Syliaduun / Praesy / Yihnurga` correspond to on-wiki pages `Etretes / Isuibul / Oyreain / Slyiaduun / Praesyu / Yihnurda`. The pages are canonical; the **spreadsheet tabs are the misspelled side**. Decide whether to fix the spreadsheet (rename tabs) so `data/` stays authoritative — no wiki changes needed. (This is really a data-hygiene fix, not a lore decision; see §A3.)
3. **Cancelled "War" editions 1664 / 1688 / 1692 / 1696** — currently red-links. Do you want stub pages recording the cancellation, or should they stay red?
4. **Empty-shell country pages (§B1)** — writing Government/Culture/History prose needs **invented leader names, extra city names + populations, parties, and landmarks**. Which nations do you want fleshed out, and will you supply the proper nouns or authorise invention?
5. **`Rethern` capital name** — currently the placeholder `[[Xxvii]]`; needs a real name.
6. **Religion depth (§B3)** — expanding the 7 religions needs deity, scripture, and clergy names that don't exist anywhere. Authorise invention or supply them?
7. **Language articles** — only names hinted (Emaran, Lastnu, Arten, Krali); grammar/script/family would be invented.
8. **Biographies** — beyond Orin Valorion and Vera Namqic, no personal names exist for heads of state, athletes, or cultural figures.
9. **Future WC editions 1772 (Pelugrotoa) & 1776 (Ahokini+Ashain)** — sheet gives only host + continent; anything beyond a bare stub requires invented venues/qualification.
10. **Real-world leakage** — besides the Germany categories (§A1), `Central Intelligence Agency` is red-linked 172× and there are real-world redirect imports (`Bonnie Parker`, `Clyde Barrow`, `Richard Burton (actor)`). Replace with in-universe equivalents, or intentional?

---

## T. Technical / housekeeping

- **T-1.** Delete or write `Zirhu.wiki` (0 bytes); clear the `sandbox` page.
- **T-2.** `pages/Main/.orig_early_scores/` holds backup copies of the early Ayuman/WC pages, and `data/` has duplicate spreadsheets (`Largest Cities by Population(1).xlsx`, `List of FLLA World Cup Host Nations(1).xlsx`, `Top 25 Unis-1.xlsx`). Tidy up to avoid editing the wrong copy.
- **T-3.** 69 pages sit under `Pages with broken file links` — infobox flag/globe PNGs (e.g. `Acetoa Flag.png`, `Ashain Globe.png`) that don't exist in the File namespace, so infoboxes render broken images. Worth an inventory of missing flag/map files (partly overlaps §A1 once the bogus categories are removed).
- **T-4.** Regenerate `graphify-out/` against a real snapshot of `pages/Main/` (currently built from 31 code/sim files) so the knowledge graph actually reflects the wiki content.

---

*End of audit. Suggested working order: A1 → A2 → E → C → A3/A4 → B2/B4/D → then the NEEDS-DECISION items as you rule on canon.*
