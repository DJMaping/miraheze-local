"""One-shot helper to create new wiki pages that aren't yet in .state.json.

Usage: python _publish_new.py path/to/file.wiki [more files...]

Uses the same auth as push.py. After successful creation, adds each page to
.state.json so subsequent push.py runs can update them normally.
"""

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Secrets live outside the repo (~/.miraheze-secrets/.env); local .env is a fallback.
load_dotenv(Path.home() / ".miraheze-secrets" / ".env")
load_dotenv()
API = os.environ["WIKI_API"]
USER = os.environ["WIKI_USER"]
PASS = os.environ["WIKI_PASS"]
SUMMARY = os.environ.get("EDIT_SUMMARY", "Created locally via script")

STATE_FILE = Path(".state.json")


def login():
    s = requests.Session()
    s.headers.update({"User-Agent": "miraheze-local/1.0"})
    tok = s.get(API, params={"action": "query", "meta": "tokens", "type": "login", "format": "json"}).json()["query"]["tokens"]["logintoken"]
    r = s.post(API, data={"action": "login", "lgname": USER, "lgpassword": PASS, "lgtoken": tok, "format": "json"}).json()
    if r.get("login", {}).get("result") != "Success":
        raise SystemExit(f"Login failed: {r}")
    print(f"Logged in as {r['login']['lgusername']}")
    return s


def csrf(s):
    return s.get(API, params={"action": "query", "meta": "tokens", "format": "json"}).json()["query"]["tokens"]["csrftoken"]


def filepath_to_title(p: Path) -> str:
    parts = p.parts
    if parts[0] != "pages":
        raise ValueError(f"Expected path under pages/: {p}")
    namespace = parts[1]
    page = "/".join(parts[2:])
    if page.endswith(".wiki"):
        page = page[:-5]
    page = page.replace("_", " ")
    return page if namespace == "Main" else f"{namespace}:{page}"


def main():
    files = [Path(a) for a in sys.argv[1:]]
    if not files:
        raise SystemExit("Provide one or more .wiki file paths.")

    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
    s = login()
    token = csrf(s)

    for fp in files:
        if not fp.exists():
            print(f"  missing: {fp}")
            continue
        title = filepath_to_title(fp)
        content = fp.read_text(encoding="utf-8")
        r = s.post(API, data={
            "action": "edit",
            "title": title,
            "text": content,
            "summary": SUMMARY,
            "token": token,
            "format": "json",
            "createonly": "1",
            "bot": "1",
        }).json()
        if "error" in r:
            print(f"  FAILED {title}: {r['error']}")
            continue
        rev = r["edit"].get("newrevid")
        print(f"  created {title}  (rev {rev})")
        state[title] = {"revid": rev, "path": str(fp)}

    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Done.")


if __name__ == "__main__":
    main()
