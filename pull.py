"""
pull.py — Download wiki pages to local files.

Usage:
    python pull.py                  # Pull all pages in main namespace
    python pull.py "Page Title"     # Pull a single specific page
    python pull.py --ns 10          # Pull a specific namespace (10 = Template)
    python pull.py --all-ns         # Pull every namespace

Pages are saved under pages/<Namespace>/<Page_Title>.wiki
File names use underscores instead of spaces, like MediaWiki URLs.
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

PAGES_DIR = Path("pages")
STATE_FILE = Path(".state.json")

# Namespace IDs -> folder names. Main is namespace 0.
NS_NAMES = {
    0: "Main",
    1: "Talk",
    2: "User",
    3: "User_talk",
    4: "Project",
    6: "File",
    8: "MediaWiki",
    10: "Template",
    12: "Help",
    14: "Category",
    828: "Module",
}


def session_login():
    """Log in using a bot password and return an authenticated session."""
    s = requests.Session()
    s.headers.update({"User-Agent": "miraheze-local/1.0"})

    # Get a login token
    r = s.get(API, params={
        "action": "query", "meta": "tokens", "type": "login", "format": "json"
    }).json()
    token = r["query"]["tokens"]["logintoken"]

    # Log in
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


def safe_filename(title: str) -> str:
    """Convert a page title to a safe-ish filename."""
    # MediaWiki already disallows most bad characters; we just swap spaces and
    # slashes which appear in subpages.
    return title.replace(" ", "_").replace("/", "__")


def list_pages(s, namespace: int):
    """Yield all page titles in a namespace via the API (paginated)."""
    apcontinue = None
    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "apnamespace": namespace,
            "aplimit": "max",
            "format": "json",
        }
        if apcontinue:
            params["apcontinue"] = apcontinue
        r = s.get(API, params=params).json()
        for page in r["query"]["allpages"]:
            yield page["title"]
        if "continue" in r:
            apcontinue = r["continue"]["apcontinue"]
        else:
            return


def fetch_page(s, title: str):
    """Return (content, revid) for a page, or (None, None) if missing."""
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


def write_page(title: str, namespace: int, content: str, revid: int, state: dict):
    """Write a page to disk and record its revid in state."""
    ns_folder = NS_NAMES.get(namespace, f"NS_{namespace}")
    folder = PAGES_DIR / ns_folder
    folder.mkdir(parents=True, exist_ok=True)

    # For non-main namespaces, the title includes the prefix ("Template:Foo");
    # strip it for the filename since the folder already encodes the namespace.
    bare_title = title.split(":", 1)[1] if namespace != 0 and ":" in title else title
    filepath = folder / f"{safe_filename(bare_title)}.wiki"
    filepath.write_text(content, encoding="utf-8")

    state[title] = {"revid": revid, "path": str(filepath)}
    print(f"  pulled {title}  (rev {revid})")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("title", nargs="?", help="Single page title to pull")
    parser.add_argument("--ns", type=int, default=0, help="Namespace ID (default 0 = Main)")
    parser.add_argument("--all-ns", action="store_true", help="Pull all known namespaces")
    args = parser.parse_args()

    s = session_login()
    state = load_state()

    if args.title:
        content, revid = fetch_page(s, args.title)
        if content is None:
            print(f"Page does not exist: {args.title}")
            return
        # Determine namespace from the title prefix if any
        ns = 0
        if ":" in args.title:
            prefix = args.title.split(":", 1)[0]
            for nid, nname in NS_NAMES.items():
                if nname.replace("_", " ") == prefix:
                    ns = nid
                    break
        write_page(args.title, ns, content, revid, state)
    else:
        namespaces = list(NS_NAMES.keys()) if args.all_ns else [args.ns]
        for ns in namespaces:
            print(f"Listing namespace {ns} ({NS_NAMES.get(ns, '?')})...")
            for title in list_pages(s, ns):
                content, revid = fetch_page(s, title)
                if content is not None:
                    write_page(title, ns, content, revid, state)

    save_state(state)
    print("Done. State saved to .state.json")


if __name__ == "__main__":
    main()
