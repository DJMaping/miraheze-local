"""
push.py — Upload local file changes back to the wiki.

Usage:
    python push.py                       # Push all changed pages
    python push.py --dry-run             # Show what would be pushed, don't send
    python push.py pages/Main/Foo.wiki   # Push only this specific file
    python push.py -m "Fixed typos"      # Custom edit summary

Detects changes by comparing each file's current content to what was on the
wiki when we last pulled (stored in .state.json). Only changed files are sent.
"""

import os
import sys
import json
import argparse
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

API = os.environ["WIKI_API"]
USER = os.environ["WIKI_USER"]
PASS = os.environ["WIKI_PASS"]
DEFAULT_SUMMARY = os.environ.get("EDIT_SUMMARY", "Edited locally via script")

PAGES_DIR = Path("pages")
STATE_FILE = Path(".state.json")


def session_login():
    s = requests.Session()
    s.headers.update({"User-Agent": "miraheze-local/1.0"})

    r = s.get(API, params={
        "action": "query", "meta": "tokens", "type": "login", "format": "json"
    }).json()
    token = r["query"]["tokens"]["logintoken"]

    r = s.post(API, data={
        "action": "login",
        "lgname": USER,
        "lgpassword": PASS,
        "lgtoken": token,
        "format": "json",
    }).json()
    if r.get("login", {}).get("result") != "Success":
        raise SystemExit(f"Login failed: {r}")
    print(f"Logged in as {r['login']['lgusername']}")
    return s


def get_csrf_token(s) -> str:
    r = s.get(API, params={
        "action": "query", "meta": "tokens", "format": "json"
    }).json()
    return r["query"]["tokens"]["csrftoken"]


def fetch_remote(s, title: str):
    r = s.get(API, params={
        "action": "query",
        "prop": "revisions",
        "titles": title,
        "rvprop": "content|ids",
        "rvslots": "main",
        "formatversion": "2",
        "format": "json",
    }).json()
    page = r["query"]["pages"][0]
    if page.get("missing"):
        return None, None
    rev = page["revisions"][0]
    return rev["slots"]["main"]["content"], rev["revid"]


def edit_page(s, title: str, content: str, base_revid: int, token: str, summary: str):
    """Edit a page. base_revid prevents overwriting changes made on the wiki since pull."""
    data = {
        "action": "edit",
        "title": title,
        "text": content,
        "summary": summary,
        "token": token,
        "format": "json",
        "bot": "1",
    }
    if base_revid:
        data["baserevid"] = base_revid
        data["nocreate"] = "1"  # don't accidentally create new pages
    r = s.post(API, data=data).json()
    if "error" in r:
        raise RuntimeError(f"Edit failed for {title}: {r['error']}")
    return r["edit"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", help="Specific files to push (default: all changed)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-m", "--message", default=DEFAULT_SUMMARY, help="Edit summary")
    args = parser.parse_args()

    if not STATE_FILE.exists():
        raise SystemExit("No .state.json found. Run pull.py first.")
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))

    # Build {filepath -> title} reverse lookup
    file_to_title = {info["path"]: title for title, info in state.items()}

    # Decide which files to consider
    if args.files:
        candidates = [Path(f) for f in args.files]
    else:
        candidates = [Path(info["path"]) for info in state.values()]

    s = session_login() if not args.dry_run else None
    token = get_csrf_token(s) if s else None

    changed = 0
    skipped = 0
    for filepath in candidates:
        if not filepath.exists():
            print(f"  missing: {filepath}")
            continue
        key = str(filepath).replace("\\", "/")
        # Match either the stored path or normalised path
        title = None
        for stored_path, stored_title in {v["path"]: k for k, v in state.items()}.items():
            if stored_path.replace("\\", "/") == key:
                title = stored_title
                break
        if not title:
            print(f"  not tracked (run pull first): {filepath}")
            continue

        local = filepath.read_text(encoding="utf-8")
        base_revid = state[title]["revid"]

        # Compare against the version we pulled, to avoid spurious edits
        if not args.dry_run:
            remote_content, remote_revid = fetch_remote(s, title)
            if local == remote_content:
                skipped += 1
                continue
            if remote_revid != base_revid:
                print(f"  WARN: {title} changed on wiki since last pull (local {base_revid} vs remote {remote_revid}). Skipping. Pull again to reconcile.")
                continue

        if args.dry_run:
            print(f"  would push: {title}")
            changed += 1
            continue

        result = edit_page(s, title, local, base_revid, token, args.message)
        new_rev = result.get("newrevid", base_revid)
        state[title]["revid"] = new_rev
        print(f"  pushed {title}  (new rev {new_rev})")
        changed += 1

    if not args.dry_run:
        STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{changed} changed, {skipped} unchanged.")


if __name__ == "__main__":
    main()
