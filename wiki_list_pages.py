#!/usr/bin/env python3
"""
wiki_list_pages.py - the three trade list pages, in the shape of their
Wikipedia namesakes with Andah's figures in place of Earth's.

    List of countries by exports
    List of countries by exports per capita
    List of countries by imports

Structure follows en.wikipedia (lead, sections, column headers, a World row
and a union row in italics without a rank); the source is the Global Trade
Union, the population source the World Data Union, currency the lahn. Figures
come from andah_trade_atlas.json, so the pages regenerate after every model
run. Writes pages/Main/<title>.wiki. Nothing is pushed: new pages go up with
_publish_new.py, updates with push.py, when DJ says so.
"""
import json
import os
import sys

import trade_subcategories as tsub

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "andah_trade_atlas.json"), encoding="utf-8"))
C = D["countries"]
YEAR = D["year"]
PAGES = os.path.join(HERE, "pages", "Main")

GTU = ('<ref name="gtu">{{Cite web |url=https://www.globaltradeunion.org/database/trade-outlook/%d/countries '
       '|title=International trade statistics by country, %d |website=globaltradeunion.org '
       '|publisher=[[Global Trade Union]] |date=%d}} Retrieved %d.</ref>' % (YEAR, YEAR, YEAR, YEAR))
GTU2 = '<ref name="gtu" />'
WDU = ('<ref name="wdu">{{Cite web |url=https://www.worlddataunion.org/population/%d '
       '|title=World population estimates, %d |publisher=[[World Data Union]] |date=%d}} Retrieved %d.</ref>'
       % (YEAR, YEAR, YEAR, YEAR))
UNION_NOTE = ('<ref group="note">The [[Quian Union]] is a customs union of thirteen member states. It is shown for '
              'comparison with its members\' trade with countries outside the union only; trade between members is '
              'excluded. It is not ranked.</ref>')
SERVICES = {"transport", "tourism", "finance_business"}


def m(v):
    """
    A currency cell: {{lahn}}17,490,723 million. Every amount starts with the
    lahn template and carries its scale word, because the wiki's conversion
    tooltip (MediaWiki:Common.js) reads the number and scale that follow the
    symbol; a bare number under a "million" header would be read as units.
    A minus sign goes before the template so the number still starts with a
    digit.
    """
    sign = "−" if v < 0 else ""
    return f"{sign}{{{{lahn}}}}{abs(v) / 1e6:,.0f} million"


def cur(v):
    """A per-capita currency cell: {{lahn}}613,471."""
    sign = "−" if v < 0 else ""
    return f"{sign}{{{{lahn}}}}{abs(v):,.0f}"


def n0(v):
    return f"{v:,.0f}"


def flag(name):
    """{{flag|X}}: flag and linked name from Template:Country data X, the wiki's own mechanism."""
    return f"{{{{flag|{name}}}}}"


def union_cell(u):
    """The union row's name cell: flagged only if the wiki has country data for it."""
    has = os.path.exists(os.path.join(HERE, "pages", "Template", f"Country_data_{u['name'].replace(' ', '_')}.wiki"))
    return (f"''{{{{flag|{u['name']}}}}}''" if has else f"''[[{u['name']}]]''") + UNION_NOTE


def top_goods(c):
    subs = c.get("sub") or {}
    goods = [(k, v) for k, v in subs.items() if tsub.PARENT[k] not in SERVICES]
    if not goods:
        return ""
    k = max(goods, key=lambda kv: kv[1])[0]
    return tsub.LABEL[k]


def rows(sort_key):
    return sorted(C.values(), key=lambda c: -sort_key(c))


def table_head(caption, cols):
    return ['{| class="wikitable sortable" style="text-align:right"', f"|+ {caption}",
            "! " + " !! ".join(cols)]


def world_row(cells):
    return ["|- style=\"font-style:italic; background:#f2f2f2\"", "| " + " || ".join(cells)]


def union_row(cells):
    return ["|- style=\"font-style:italic\"", "| " + " || ".join(cells)]


def exports_page():
    world = D["world"]
    wx = sum(c["x"] for c in C.values())
    wg = sum(c["goods_x"] for c in C.values())
    ws = sum(c["svc_x"] for c in C.values())
    U = D.get("unions") or {}
    L = []
    L.append(f"This is a '''list of countries by exports''', including both merchandise exports and service exports, "
             f"based on figures published by the [[Global Trade Union]] for {YEAR}.{GTU} Merchandise exports are goods "
             f"produced in one country and sold to another; service exports are services supplied across borders between "
             f"residents of different countries. The figures are in {{{{lahn}}}} millions at current prices.")
    L.append("")
    hubs = [c["name"] for c in rows(lambda c: c["reexports"] / max(c["x"], 1)) if c["reexports"] > 0.3 * c["x"]][:3]
    if hubs:
        L.append(f"Some countries, such as {', '.join(f'[[{h}]]' for h in hubs[:-1])} and [[{hubs[-1]}]], have export "
                 f"figures that are large relative to the size of their economies because of re-exports: goods that pass "
                 f"through their ports and are sold on without substantial processing.{GTU2}")
        L.append("")
    L.append("== By total exports ==")
    L += table_head(f"Exports of goods and services, {YEAR}", ["Rank", "Country", "Exports", "Year", "Top goods export"])
    L += world_row(["", "''World''", m(wx), str(YEAR), ""])
    unions = sorted(U.values(), key=lambda u: -u["x"])
    for i, c in enumerate(rows(lambda c: c["x"]), 1):
        # a union sits at its value position, unranked, as Wikipedia places the EU
        while unions and unions[0]["x"] >= c["x"]:
            u = unions.pop(0)
            L += union_row(["", f"style=\"text-align:left\" | {union_cell(u)}", m(u["x"]), str(YEAR), ""])
        L += ["|-", f"| {i} || style=\"text-align:left\" | {flag(c['name'])} || {m(c['x'])} || {YEAR} || style=\"text-align:left\" | {top_goods(c)}"]
    for u in unions:
        L += union_row(["", f"style=\"text-align:left\" | {union_cell(u)}", m(u["x"]), str(YEAR), ""])
    L.append("|}")
    L.append("")
    L.append("== By merchandise exports ==")
    L.append(f"Merchandise exports include re-exports. Figures are in {{{{lahn}}}} millions.{GTU2}")
    L += table_head(f"Merchandise exports, {YEAR}", ["Rank", "Country", "Merchandise exports", "Year"])
    L += world_row(["", "''World''", m(wg), str(YEAR)])
    for i, c in enumerate(rows(lambda c: c["goods_x"]), 1):
        L += ["|-", f"| {i} || style=\"text-align:left\" | {flag(c['name'])} || {m(c['goods_x'])} || {YEAR}"]
    L.append("|}")
    L.append("")
    L.append("== By service exports ==")
    L.append(f"Service exports cover transport, travel, and financial, business and information services. Figures are in {{{{lahn}}}} millions.{GTU2}")
    L += table_head(f"Service exports, {YEAR}", ["Rank", "Country", "Service exports", "Year"])
    L += world_row(["", "''World''", m(ws), str(YEAR)])
    for i, c in enumerate(rows(lambda c: c["svc_x"]), 1):
        L += ["|-", f"| {i} || style=\"text-align:left\" | {flag(c['name'])} || {m(c['svc_x'])} || {YEAR}"]
    L.append("|}")
    L += ["", "== See also ==",
          "* [[List of countries by imports]]",
          "* [[List of countries by exports per capita]]",
          "* [[Global Trade Union]]",
          "", "== Notes ==", '{{reflist|group="note"}}',
          "", "== References ==", "{{reflist}}",
          "", "[[Category:Economy]]", "[[Category:Countries]]"]
    return "\n".join(L) + "\n"


def imports_page():
    wm = sum(c["m"] for c in C.values())
    wsvc = sum(c["m"] * (c.get("svc_share") or 0.0) for c in C.values())
    wgm = wm - wsvc
    U = D.get("unions") or {}
    L = []
    L.append(f"This is a '''list of countries by imports''', including both merchandise imports and service imports, "
             f"based on figures published by the [[Global Trade Union]] for {YEAR}.{GTU} Merchandise imports are goods "
             f"produced in one country and purchased by another; service imports are services procured across borders "
             f"between residents of different countries. The figures are in {{{{lahn}}}} millions at current prices, and the "
             f"trade balance is exports of goods and services less imports.")
    L.append("")
    L.append("== By total and merchandise imports ==")
    L += table_head(f"Imports of goods and services, {YEAR}",
                    ["Rank", "Country", "Total imports", "Merchandise imports", "Trade balance", "Year"])
    L += world_row(["", "''World''", m(wm), m(wgm), m(0), str(YEAR)])
    unions = sorted(U.values(), key=lambda u: -u["m"])
    for i, c in enumerate(rows(lambda c: c["m"]), 1):
        while unions and unions[0]["m"] >= c["m"]:
            u = unions.pop(0)
            L += union_row(["", f"style=\"text-align:left\" | {union_cell(u)}", m(u["m"]), "", m(u["bal"]), str(YEAR)])
        gm = c["m"] * (1.0 - (c.get("svc_share") or 0.0))
        L += ["|-", f"| {i} || style=\"text-align:left\" | {flag(c['name'])} || {m(c['m'])} || {m(gm)} || {m(c['bal'])} || {YEAR}"]
    for u in unions:
        L += union_row(["", f"style=\"text-align:left\" | {union_cell(u)}", m(u["m"]), "", m(u["bal"]), str(YEAR)])
    L.append("|}")
    L.append("")
    L.append("== By service imports ==")
    L.append(f"Service imports cover transport, travel abroad, and financial, business and information services bought from "
             f"other countries. Figures are in {{{{lahn}}}} millions.{GTU2}")
    L += table_head(f"Service imports, {YEAR}", ["Rank", "Country", "Service imports", "Year"])
    L += world_row(["", "''World''", m(wsvc), str(YEAR)])
    for i, c in enumerate(rows(lambda c: c["m"] * (c.get("svc_share") or 0.0)), 1):
        L += ["|-", f"| {i} || style=\"text-align:left\" | {flag(c['name'])} || {m(c['m'] * (c.get('svc_share') or 0.0))} || {YEAR}"]
    L.append("|}")
    L += ["", "== See also ==",
          "* [[List of countries by exports]]",
          "* [[List of countries by exports per capita]]",
          "* [[Global Trade Union]]",
          "", "== Notes ==", '{{reflist|group="note"}}',
          "", "== References ==", "{{reflist}}",
          "", "[[Category:Economy]]", "[[Category:Countries]]"]
    return "\n".join(L) + "\n"


def per_capita_page():
    wx = sum(c["x"] for c in C.values())
    wg = sum(c["goods_x"] for c in C.values())
    ws = sum(c["svc_x"] for c in C.values())
    wp = sum(c["population"] for c in C.values())
    L = []
    L.append(f"This is a '''list of countries by exports per capita''': the value of a country's exports of goods and "
             f"services in {YEAR} divided by its population. Export figures are from the [[Global Trade Union]]{GTU} and "
             f"population estimates from the [[World Data Union]].{WDU} Values are in {{{{lahn}}}} at current prices. Merchandise "
             f"exports include re-exports, which is why several small trading states with large ports rank near the top.")
    L.append("")
    L.append(f"== Exports per capita, {YEAR} ==")
    L += ['{| class="wikitable sortable" style="text-align:right"', f"|+ Exports per capita by country, {YEAR}",
          "! Rank !! Country !! Population (thousands) !! Merchandise exports !! Merchandise exports per capita "
          "!! Service exports !! Service exports per capita !! Total exports !! Total exports per capita"]
    L += world_row(["", "''World''", n0(wp / 1e3), m(wg), cur(wg / wp), m(ws), cur(ws / wp), m(wx), cur(wx / wp)])
    for i, c in enumerate(rows(lambda c: c["x"] / max(c["population"], 1)), 1):
        p = max(c["population"], 1)
        L += ["|-", f"| {i} || style=\"text-align:left\" | {flag(c['name'])} || {n0(p / 1e3)} || {m(c['goods_x'])} || {cur(c['goods_x'] / p)} "
                    f"|| {m(c['svc_x'])} || {cur(c['svc_x'] / p)} || {m(c['x'])} || {cur(c['x'] / p)}"]
    L.append("|}")
    L += ["", "== See also ==",
          "* [[List of countries by exports]]",
          "* [[List of countries by imports]]",
          "* [[Global Trade Union]]",
          "", "== References ==", "{{reflist}}",
          "", "[[Category:Economy]]", "[[Category:Countries]]"]
    return "\n".join(L) + "\n"


PAGES_OUT = {
    "List of countries by exports": exports_page,
    "List of countries by exports per capita": per_capita_page,
    "List of countries by imports": imports_page,
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    for title, fn in PAGES_OUT.items():
        path = os.path.join(PAGES, title.replace(" ", "_") + ".wiki")
        text = fn()
        assert "—" not in text, title
        open(path, "w", encoding="utf-8").write(text)
        print(f"wrote {path}  ({text.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
