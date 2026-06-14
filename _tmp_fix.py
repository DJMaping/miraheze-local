import json, os, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
API = os.environ["WIKI_API"]; USER = os.environ["WIKI_USER"]; PASS = os.environ["WIKI_PASS"]
s = requests.Session(); s.headers.update({"User-Agent": "miraheze-local/1.0"})
tok = s.get(API, params={"action": "query", "meta": "tokens", "type": "login", "format": "json"}).json()["query"]["tokens"]["logintoken"]
s.post(API, data={"action": "login", "lgname": USER, "lgpassword": PASS, "lgtoken": tok, "format": "json"})
csrf = s.get(API, params={"action": "query", "meta": "tokens", "format": "json"}).json()["query"]["tokens"]["csrftoken"]

BAD = "Template:FLLA World Cup doc"
GOOD = "Template:FLLA World Cup/doc"
r = s.post(API, data={"action": "move", "from": BAD, "to": GOOD, "reason": "Fix subpage title (should be /doc)",
                      "noredirect": "1", "movetalk": "1", "token": csrf, "format": "json"}).json()
print("move result:", json.dumps(r.get("move", r.get("error", r)), ensure_ascii=False))

# new current revid of the moved page
info = s.get(API, params={"action": "query", "titles": GOOD, "prop": "info", "format": "json"}).json()
revid = next(iter(info["query"]["pages"].values())).get("lastrevid")
print("new revid:", revid)

# fix .state.json: drop any bad-spaced key, register the correct title
state = json.loads(Path(".state.json").read_text(encoding="utf-8"))
for k in [k for k in state if k.replace(" ", "").lower() == "template:fllaworldcupdoc"]:
    print("removing stale state key:", repr(k))
    state.pop(k)
state[GOOD] = {"revid": revid, "path": "pages/Template/FLLA_World_Cup__doc.wiki"}
Path(".state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
print("state.json updated; GOOD registered as", GOOD)
