---
type: note
---
# How the Workshop works

This folder is your safe drafting space. The export (`to_obsidian.py`) only ever writes
to `Articles/` and `Categories/`, so nothing here is ever overwritten.

## Drafting a new note

1. Capture the idea in [[3 Workshop/Inbox|Inbox]].
2. Create a note in this folder and insert a template (the core **Templates** command,
   pointed at `4 Templates/`): [[4 Templates/Country|Country]], [[4 Templates/City|City]],
   [[4 Templates/Person|Person]], [[4 Templates/World Cup edition|World Cup edition]],
   [[4 Templates/Religion|Religion]].
3. Fill in the properties and prose.

Drafts carry `status: draft`. They use the real `type:` (e.g. `country`), so a work-in-
progress will also appear in the matching dashboard until you promote it. That is intentional.

## Promoting a draft to the wiki

Obsidian is the thinking and drafting layer; the wiki is the canonical publish layer, and
the link is **one-directional** (editing `Articles/` directly is pointless, the next export
overwrites it). To publish:

1. Hand-translate the draft into MediaWiki wikitext as `pages/Main/<Title>.wiki` in the repo.
2. Create the page: `python _publish_new.py pages/Main/<Title>.wiki`
   (or, to edit an existing page, `python push.py -m "summary" pages/Main/<Title>.wiki`).
3. Re-run `python to_obsidian.py` to pull the now-canonical version back into `Articles/`,
   then delete the Workshop draft.

## Canon rules (apply before publishing)

These are hard project rules; breaking them has forced rewrites and deletions.

- **Never invent proper nouns.** Cities, countries, hosts, players and currencies almost
  always already exist. Check `data/*.xlsx` first (sheet name = canonical country; use
  `Largest Cities by Population.xlsx` for prominence; `List of FLLA World Cup Host
  Nations.xlsx` for hosts and winners). Ask before inventing.
- **British spelling** throughout (centre, programme, organised, colour, defence).
- **No em-dashes.** Use commas, semicolons or parentheses; en-dash `–` only for scores and
  date ranges.
- **Currency:** the `{{lahn}}` template, `&nbsp;` before scale words.
- **Dates:** DD Month YYYY. Current in-universe data is ~1763–1765.
- Reuse established citation bodies (GTU, World Data Union / Census, Krali, FLLA). Any page
  with `<ref>` tags needs `== References ==` + `{{reflist}}`.
- Consult the project memory notes (religion taxonomy, FLLA award/trophy names) before
  writing domain lore.
