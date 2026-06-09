# miraheze-local

A local editing environment for a Miraheze-hosted MediaWiki. The workflow is: pull wiki pages to disk, edit them (with VS Code or Claude Code), then push changes back via the MediaWiki API.

## Project structure

- `pages/<Namespace>/<Title>.wiki` — local copies of wiki pages. Edit these.
- `.state.json` — tracks the last-pulled revision ID for each page so push can detect conflicts and local changes.
- `pull.py` — downloads pages from the wiki API to `pages/`.
- `push.py` — uploads changed pages back to the wiki. Compares local content to `.state.json` baseline; only sends pages that actually changed.
- `_publish_new.py` — creates brand-new wiki pages (pages not yet in `.state.json`).
- `_create_new.py` — helper for scaffolding new page files locally before publishing.
- `generate_cities.py` / `to_obsidian.py` — one-off data and conversion scripts.
- `data/` — source data files used by the generation scripts.
- `.env` — credentials (gitignored, never commit).

## Environment

Requires a `.env` file with:
```
WIKI_API=https://YOURWIKI.miraheze.org/w/api.php
WIKI_USER=BotUsername@BotName
WIKI_PASS=bot-password-here
EDIT_SUMMARY=Optional default edit summary
```

Python deps: `requests`, `python-dotenv`. Install with `pip install requests python-dotenv` (use the venv in `venv/`).

## Common commands

```bash
python pull.py                        # Pull all main-namespace pages
python pull.py "Page Title"           # Pull one specific page
python pull.py --ns 10                # Pull templates (namespace 10)
python pull.py --all-ns               # Pull every namespace

python push.py --dry-run              # Preview what would be sent
python push.py -m "Edit summary"      # Push all changed pages
python push.py pages/Main/Foo.wiki    # Push one specific file

python _publish_new.py pages/Main/NewPage.wiki   # Create a page that doesn't exist yet
```

## Key behaviours

- `push.py` refuses to push if the remote page changed since your last pull (conflict protection).
- `push.py` uses `nocreate=1` by default — it will not create new pages. Use `_publish_new.py` for that.
- Edits are flagged as bot edits (`bot=1`) if the account has the bot flag, keeping Recent Changes clean.
- Page filenames use underscores instead of spaces (matching MediaWiki URL conventions).

## Editing wiki pages with Claude Code

Pages are plain MediaWiki wikitext. When editing:
- Preserve existing templates, categories, and infobox syntax unless explicitly asked to change them.
- Treat `[[links]]`, `{{templates}}`, and `<ref>` tags as structured markup — don't reformat them as prose.
- After bulk edits, always run `python push.py --dry-run` first to review the diff before pushing.

Useful task patterns:
- "Read `pages/Main/Foo.wiki` and rewrite the lead paragraph to be more concise."
- "Find every page under `pages/Main/` that mentions 'Old Kingdom' and replace it with 'First Kingdom'."
- "Add `{{stub}}` to the bottom of any page in `pages/Main/` shorter than 500 characters."
