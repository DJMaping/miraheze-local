"""One-off helper: create new local files on the wiki and register them in .state.json.

Usage: python _create_new.py "<summary>" path1 path2 ...
"""
import os
import sys
import json
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()
API = os.environ["WIKI_API"]
USER = os.environ["WIKI_USER"]
PASS = os.environ["WIKI_PASS"]

summary = sys.argv[1]
files = sys.argv[2:]

s = requests.Session()
s.headers.update({"User-Agent": "miraheze-local/1.0"})
r = s.get(API, params={"action": "query", "meta": "tokens", "type": "login", "format": "json"}).json()
r = s.post(API, data={
    "action": "login", "lgname": USER, "lgpassword": PASS,
    "lgtoken": r["query"]["tokens"]["logintoken"], "format": "json",
}).json()
assert r["login"]["result"] == "Success", r
print(f"Logged in as {r['login']['lgusername']}")
token = s.get(API, params={"action": "query", "meta": "tokens", "format": "json"}).json()["query"]["tokens"]["csrftoken"]

state = json.loads(Path(".state.json").read_text(encoding="utf-8"))

for filepath_str in files:
    filepath = Path(filepath_str)
    # Title is the filename without .wiki, with underscores → spaces
    title = filepath.stem.replace("_", " ")
    content = filepath.read_text(encoding="utf-8")
    r = s.post(API, data={
        "action": "edit", "title": title, "text": content,
        "summary": summary, "token": token, "format": "json",
        "bot": "1", "createonly": "1",
    }).json()
    if "error" in r:
        print(f"  ERROR {title}: {r['error']}")
    else:
        rev = r["edit"]["newrevid"]
        state[title] = {"revid": rev, "path": str(filepath)}
        print(f"  created {title} (rev {rev})")

Path(".state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
print("Done.")
