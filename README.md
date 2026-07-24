# miraheze-local

Edit your Miraheze wiki from VS Code / Claude Code with a pull → edit → push workflow.

## Setup (one time)

1. **Install deps** (from this folder, with the venv activated):
   ```
   pip install requests python-dotenv
   ```
2. **Get a bot password** at `https://YOURWIKI.miraheze.org/wiki/Special:BotPasswords`.
   Grant: Basic rights, High-volume editing, Edit existing pages, Create/edit/move pages.
3. **Configure**: create `%USERPROFILE%\.miraheze-secrets\.env` (outside the repo)
   and fill in `WIKI_API`, `WIKI_USER`, `WIKI_PASS`. A `.env` in the repo root
   also works as a fallback, but keeping it outside means it can never be
   committed or bundled up with the folder.

## Daily workflow

```
# Pull the latest version of every page in the main namespace
python pull.py

# Or pull just one page
python pull.py "Atlantis"

# Or pull templates too
python pull.py --ns 10

# ...edit files under pages/ using VS Code or Claude Code...

# See what would change
python push.py --dry-run

# Send your edits to the wiki
python push.py -m "Reworded intros across geography pages"
```

## How it works

- `pull.py` lists pages via the MediaWiki API, downloads each one, and saves it
  to `pages/<Namespace>/<Title>.wiki`. It records each page's revision ID in
  `.state.json` so push knows what's been edited locally vs remotely.
- `push.py` reads each tracked file, compares it to the current remote content,
  and only sends pages whose local content has actually changed. It refuses to
  push if the page changed on the wiki since your last pull (so you don't
  clobber someone else's edit).

## Using Claude Code

From this folder, run `claude` to launch Claude Code. Then ask things like:

- "Read pages/Main/Atlantis.wiki and rewrite the lead to be more concise."
- "Find every page that mentions 'Old Kingdom' and replace it with 'First Kingdom'."
- "Add an infobox template call to the top of all pages in pages/Main/ that don't already have one."

After Claude Code finishes editing, run `python push.py --dry-run` to verify,
then `python push.py` to send the changes.

## Safety notes

- Credentials live in `%USERPROFILE%\.miraheze-secrets\.env`, outside the repo,
  so they can't end up on GitHub. (`.env` is also gitignored as a belt-and-braces
  measure in case one is ever created in the repo root.)
- `push.py` uses `nocreate=1` by default, so it won't accidentally create new
  pages. To create a new page, pull it once (it'll be empty), edit, then push.
- The bot flag is honoured (`bot=1`), so your edits won't flood Recent Changes
  if your account has it. If not, drop that line in `push.py`.
- Always `--dry-run` before a big push.
