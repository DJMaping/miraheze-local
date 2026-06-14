import os, requests
from dotenv import load_dotenv
load_dotenv()
API = os.environ["WIKI_API"]; USER = os.environ["WIKI_USER"]; PASS = os.environ["WIKI_PASS"]
s = requests.Session(); s.headers.update({"User-Agent": "miraheze-local/1.0"})
tok = s.get(API, params={"action": "query", "meta": "tokens", "type": "login", "format": "json"}).json()["query"]["tokens"]["logintoken"]
s.post(API, data={"action": "login", "lgname": USER, "lgpassword": PASS, "lgtoken": tok, "format": "json"})
ui = s.get(API, params={"action": "query", "meta": "userinfo", "uiprop": "rights", "format": "json"}).json()["query"]["userinfo"]
rights = set(ui.get("rights", []))
print("user:", ui.get("name"))
for r in ("move", "delete", "suppressredirect", "edit"):
    print("  right", r, "=", r in rights)
q = s.get(API, params={"action": "query", "titles": "Template:FLLA World Cup doc|Template:FLLA World Cup/doc", "prop": "info", "format": "json"}).json()
for pid, pg in q["query"]["pages"].items():
    print("title=", repr(pg["title"]), "| missing=", "missing" in pg)
