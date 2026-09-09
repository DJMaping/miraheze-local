#!/usr/bin/env python3
"""
generate_trade_sections.py - write a country's trade figures into its wiki page.

Builds a "=== Trade ===" block of prose from andah_trade_atlas.json (the
model's output), in the shape of a country page on Wikipedia, and puts it
inside the page's existing == Economy == section, between
<!-- TRADE-AUTO START --> and <!-- TRADE-AUTO END --> markers, so it can be
regenerated after every model run without touching anything hand-written
around it. Same contract as generate_cities.py.

    python generate_trade_sections.py dry Emara          # print the block
    python generate_trade_sections.py apply Emara Dahe   # write it into the pages
    python generate_trade_sections.py apply --all        # every country page that exists

Nothing here pushes to the wiki; push.py does that, on request.
"""
import json
import os
import re
import sys

import trade_baskets as tb
import trade_subcategories as tsub

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.join(HERE, "andah_trade_atlas.json")
PAGES = os.path.join(HERE, "pages", "Main")
START, END = "<!-- TRADE-AUTO START -->", "<!-- TRADE-AUTO END -->"
CATLABEL = {k: l for k, l, _ in tb.CATEGORIES}
# how the categories read in a sentence
PROSE = {
    "crude_oil_gas": "crude oil and natural gas", "refined_fuels": "refined fuels and coal",
    "ores_metals": "ores and metals", "precious": "precious metals and gems",
    "agri_food": "food and agricultural products", "forestry_paper": "forest products and paper",
    "textiles": "textiles and clothing", "chemicals": "chemicals and pharmaceuticals",
    "machinery": "machinery and industrial equipment", "electronics": "electronics and electrical equipment",
    "vehicles": "vehicles, ships and aircraft", "other_manuf": "other manufactured goods",
    "transport": "transport and logistics services", "tourism": "travel and tourism",
    "finance_business": "financial and business services",
}
ORDINAL = {1: "largest", 2: "second largest", 3: "third largest", 4: "fourth largest",
           5: "fifth largest", 6: "sixth largest", 7: "seventh largest", 8: "eighth largest",
           9: "ninth largest", 10: "tenth largest"}


def lahn(v):
    """{{lahn}}5.94&nbsp;trillion, British house style."""
    a = abs(v)
    if a >= 1e12:
        return f"{{{{lahn}}}}{a / 1e12:.2f}&nbsp;trillion"
    if a >= 1e9:
        return f"{{{{lahn}}}}{a / 1e9:.0f}&nbsp;billion"
    return f"{{{{lahn}}}}{a / 1e6:.0f}&nbsp;million"


def pct(x, d=0):
    return f"{x * 100:.{d}f}%"


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def ordinal(n):
    return ORDINAL.get(n, f"{n}th largest")


def product_ranks(name, D):
    """[(label, rank, share_of_world)] for products where the country is top three."""
    C = D["countries"]
    dom = {n: c["goods_x"] + c["svc_x"] - c["reexports"] for n, c in C.items()}
    out = []
    for key, label, parent, *_ in D["products"]:
        col = {n: c.get("sub", {}).get(key, 0.0) * dom[n] for n, c in C.items() if c.get("sub", {}).get(key, 0.0) > 0}
        if name not in col:
            continue
        tot = sum(col.values()) or 1.0
        rank = 1 + sum(1 for v in col.values() if v > col[name])
        if rank <= 3 and col[name] / tot >= 0.08:
            out.append((label, rank, col[name] / tot, col[name]))
    out.sort(key=lambda t: (t[1], -t[3]))
    return out


def joinlist(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def block(name, D):
    """
    The Economy prose, in the shape of a country page on Wikipedia: a few
    paragraphs that say how big the trade is, what the country sells and to
    whom, and the two or three things it is known for. No tables; those
    belong in a separate "Economy of X" article if one is ever wanted.
    """
    C = D["countries"]
    c = C[name]
    year = D["year"]
    dom = c["goods_x"] + c["svc_x"] - c["reexports"]
    world_x = sum(v["x"] for v in C.values())
    ref = (f'<ref name="gtu-trade">{{{{Cite web |url=https://www.globaltradeunion.org/database/{year}/trade/{slug(name)} '
           f'|title=International trade statistics {year}: {name} |website=globaltradeunion.org '
           f'|publisher=[[Global Trade Union]] |date={year}}}}} Retrieved {year}.</ref>')
    ref2 = '<ref name="gtu-trade" />'
    bal = c["bal"]
    x_gdp = c["x"] / c["gdp"] if c["gdp"] else 0.0
    cats = sorted(((k, v * dom) for k, v in c["basket"].items() if v > 0), key=lambda kv: -kv[1])
    subs = dict(c.get("sub") or {})
    def lead_products(cat, n=2):
        ps = sorted(((k, v) for k, v in subs.items() if tsub.PARENT[k] == cat), key=lambda kv: -kv[1])[:n]
        return [tsub.LABEL[k].lower() for k, _ in ps]
    goods_share = 1.0 - c["svc_x"] / c["x"] if c["x"] else 1.0
    svc_cats = [(k, v) for k, v in cats if k in tb.SERVICES]

    # 1. size
    p1 = (f"{name} has an open, trade-dependent economy. In {year} its exports of goods and services were valued at "
          f"{lahn(c['x'])}, the {ordinal(c['rank'])} in the world and {pct(c['x'] / world_x, 1)} of the world total, "
          f"equivalent to {pct(x_gdp)} of GDP.{ref} Imports were {lahn(c['m'])}, leaving a trade "
          f"{'surplus' if bal >= 0 else 'deficit'} of {lahn(bal)}"
          f"{', among the largest in the world' if abs(bal) > 0.5e12 else ''}.{ref2}")
    # 2. what it sells
    k1, v1 = cats[0]
    k2, v2 = cats[1]
    k3, v3 = cats[2]
    sent = []
    if k1 in tb.SERVICES:
        sent.append(f"Services dominate {name}'s exports: {PROSE[k1]} alone account for {pct(v1 / dom)}, "
                    f"led by {joinlist(lead_products(k1))}.")
    else:
        sent.append(f"Manufactured goods make up most of what {name} sells abroad. {PROSE[k1][0].upper() + PROSE[k1][1:]} "
                    f"account for {pct(v1 / dom)} of exports, led by {joinlist(lead_products(k1))}, followed by "
                    f"{PROSE[k2]} ({pct(v2 / dom)}), chiefly {joinlist(lead_products(k2))}, and {PROSE[k3]} ({pct(v3 / dom)}).")
    ranks = product_ranks(name, D)
    if ranks:
        firsts = [l for l, r, sh, _ in ranks if r == 1][:3]
        seconds = [l for l, r, sh, _ in ranks if r == 2][:3]
        thirds = [l for l, r, sh, _ in ranks if r == 3][:2]
        bits = []
        if firsts:
            bits.append("the world's largest exporter of " + joinlist(l.lower() for l in firsts))
        if seconds:
            bits.append(("the second largest of " if firsts else "the world's second largest exporter of ")
                        + joinlist(l.lower() for l in seconds))
        if thirds and len(bits) < 2:
            bits.append("the third largest of " + joinlist(l.lower() for l in thirds))
        sent.append(f"{name} is {joinlist(bits)}.{ref2}")
    if svc_cats and k1 not in tb.SERVICES:
        sk, sv = svc_cats[0]
        sent.append(f"Services provide {pct(1 - goods_share)} of export earnings, the largest part of them "
                    f"{PROSE[sk]} ({pct(sv / dom)}).{ref2}")
    p2 = " ".join(sent)
    # 3. with whom
    out_p = c["partners"][:5]
    in_p = c["buyers"][:5]
    two = out_p[:2]
    p3 = (f"{name}'s largest trading partners are [[{two[0][0]}]] and [[{two[1][0]}]], which between them take "
          f"{pct((two[0][1] + two[1][1]) / c['x'])} of its exports, followed by "
          f"{joinlist(f'[[{q}]] ({pct(v / c[chr(120)])})' for q, v in out_p[2:5])}.{ref2} "
          f"Its imports come chiefly from {joinlist(f'[[{q}]] ({pct(v / c[chr(109)])})' for q, v in in_p[:3])}.{ref2}")
    # 4. the things only this country has
    extras = []
    canal = [t for t in D.get("transit", []) if t["hub"] == name and t["kind"] == "canal"]
    if canal and D.get("lanes"):
        import build_trade_model as M
        for cname, traffic in (D["lanes"].get("canals") or {}).items():
            extras.append(f"{name} owns and operates the {cname}, through which {lahn(traffic)} of cargo passed in {year}; "
                          f"tolls earned it {lahn(traffic * M.CANAL_TOLL_RATE)}.{ref2}")
    if c.get("reexports", 0) > 0.1 * c["x"]:
        extras.append(f"Its ports are among the busiest in the world, and {pct(c['reexports'] / c['x'])} of its exports "
                      f"by value were goods in transit rather than its own produce.{ref2}")
    tour = c["basket"].get("tourism", 0.0) * dom
    if tour > 0.05 * dom:
        extras.append(f"Tourism is a significant earner: visitors spent {lahn(tour)} in {year}, "
                      f"{pct(tour / dom)} of export earnings.{ref2}")
    if c["dva"] < 0.6:
        extras.append(f"Only {pct(c['dva'])} of the value of its exports is added domestically, a mark of how much "
                      f"of what it ships is assembled from imported parts or passes straight through.{ref2}")
    paras = [p1, p2, p3] + ([" ".join(extras)] if extras else [])
    body = "\n\n".join(paras)
    return START + "\n=== Trade ===\n" + body + "\n" + END


def insert(text, blk):
    if START in text and END in text:
        a, b = text.index(START), text.index(END) + len(END)
        return text[:a] + blk + text[b:]
    m = re.search(r"^== *Economy *==[^\n]*\n", text, flags=re.M)
    if m:
        nxt = re.search(r"^== ", text[m.end():], flags=re.M)
        cut = m.end() + nxt.start() if nxt else len(text)
        body = text[m.end():cut].rstrip("\n")
        return text[:m.end()] + (body + "\n\n" if body else "") + blk + "\n\n" + text[cut:]
    m = re.search(r"^== *(Demographics|References) *==", text, flags=re.M)
    cut = m.start() if m else len(text)
    return text[:cut] + "== Economy ==\n" + blk + "\n\n" + text[cut:]


def ensure_reflist(text):
    if "<ref" in text and "{{reflist}}" not in text.lower():
        m = re.search(r"^== *References *==[^\n]*\n", text, flags=re.M)
        if m:
            return text[:m.end()] + "{{reflist}}\n" + text[m.end():]
        cat = re.search(r"^\[\[Category:", text, flags=re.M)
        cut = cat.start() if cat else len(text)
        return text[:cut] + "== References ==\n{{reflist}}\n\n" + text[cut:]
    return text


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 3:
        print(__doc__)
        return
    mode, names = sys.argv[1], sys.argv[2:]
    D = json.load(open(ATLAS, encoding="utf-8"))
    if names == ["--all"]:
        names = [n for n in D["countries"] if os.path.exists(os.path.join(PAGES, n.replace(" ", "_") + ".wiki"))]
    for name in names:
        if name not in D["countries"]:
            print(f"!! {name}: not in the model")
            continue
        blk = block(name, D)
        if mode == "dry":
            print(blk)
            continue
        path = os.path.join(PAGES, name.replace(" ", "_") + ".wiki")
        if not os.path.exists(path):
            print(f"!! {name}: no page at {path}")
            continue
        text = open(path, encoding="utf-8").read()
        new = ensure_reflist(insert(text, blk))
        if new != text:
            open(path, "w", encoding="utf-8").write(new)
            print(f"wrote trade section into {path}")
        else:
            print(f"unchanged: {path}")


if __name__ == "__main__":
    main()
