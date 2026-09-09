#!/usr/bin/env python3
"""
wiki_trade_pages.py - write the trade list pages from the model output.

Generated, never hand-edited: the model is re-run often enough that a hand-typed
table would be stale within a session. Run this after export_trade_json.py and
the pages follow whatever the model currently says.

House style is taken from List of countries by GDP (nominal), which is the
closest existing page: values in millions of LND, {{flag|X}} in the first
column, a sortable sticky header, Global Trade Union as the source, and
[[Category:Statistics]] at the foot. British spelling, no em-dashes.

WRITES FILES ONLY. Publishing is a separate, deliberate step:
    python _publish_new.py pages/Main/<page>.wiki
"""

import io
import json
import os

import andah_data as ad
import trade_baskets as tb

OUT = os.path.join(ad.HERE, "pages", "Main")
JSON = os.path.join(ad.HERE, "andah_trade_atlas.json")

# One dataset-level citation reused across each table. The GDP page gives every
# row its own reference, which is right when three institutions disagree per
# country; here every figure comes from one GTU release, so a single named
# reference is both honest and far less to read.
REF = ('<ref name="gtu-trade">{{Cite web '
       '|url=https://www.globaltradeunion.org/database/trade-outlook/1765/world '
       '|title=Trade Outlook 1765: Merchandise and Services Trade by Country '
       '|website=globaltradeunion.org |publisher=[[Global Trade Union]] '
       '|date=1765 }} Retrieved 1765.</ref>')
REF_USE = '<ref name="gtu-trade" />'

FOOT = """
== See also ==
* [[List of countries by GDP (nominal)]]
* [[Global Trade Union]]

== References ==
{{reflist}}

[[Category:Statistics]]
"""


def m(v):
    """Millions of LND, the unit the GDP tables use."""
    return f"{round(v / 1e6):,}"


def pct(v):
    return f"{v * 100:.2f}%" if v * 100 < 10 else f"{v * 100:.1f}%"


def head(caption, cols):
    return ('{| class="wikitable sortable sticky-header-multi static-row-numbers" {{left}}\n'
            f"|+{caption}\n"
            '|- class="static-row-header" style="text-align:center;vertical-align:bottom;"\n'
            + "".join(f"! {c}\n" for c in cols))


def world_row(cells):
    return ('|- class="static-row-header " style="font-weight:bold;"\n'
            '| style="text-align:left" |{{noflag|World}} || ' + " || ".join(cells) + "\n")


def build(data):
    C = data["countries"]
    L = data["lists"]
    year = data["year"]
    wx = data["world"]["exports"]
    label = {k: l for k, l, _ in tb.CATEGORIES}
    pages = {}

    # ---- exports -----------------------------------------------------------
    by_x = sorted(C.values(), key=lambda c: -c["x"])
    t = head(f"Exports of goods and services (million LND) by country, {year}",
             ["Rank", "Country", "Exports", "Share of world", "Year", "Largest export category"])
    t += world_row([m(wx) + REF, "100%", str(year), "&mdash;"]).replace("&mdash;", "")
    for i, c in enumerate(by_x, 1):
        t += ("|-\n| " + str(i) + " || {{flag|" + c["name"] + "}} || " + m(c["x"])
              + " || " + pct(c["x"] / wx) + " || " + str(year)
              + " || " + label.get(c["lead_cat"], "") + "\n")
    t += "|}\n"
    pages["List_of_countries_by_exports"] = (
        "'''This is a list of countries by exports''' of goods and services, measured in "
        "millions of [[Lahn|LND]]. Figures are Global Trade Union estimates for " + str(year)
        + ". World exports balance world imports by construction, so the two lists share a "
        "total.\n\n"
        "The largest export category is the single biggest line of each country's export "
        "basket, of fifteen categories covering twelve classes of goods and three of "
        "services.\n\n"
        "==Table==\n" + t + FOOT)

    # ---- imports -----------------------------------------------------------
    by_m = sorted(C.values(), key=lambda c: -c["m"])
    t = head(f"Imports of goods and services (million LND) by country, {year}",
             ["Rank", "Country", "Imports", "Share of world", "Merchandise", "Services",
              "Trade balance"])
    t += world_row([m(wx) + REF, "100%", "", "", "0"])
    for i, c in enumerate(by_m, 1):
        svc = c["m"] * (c.get("svc_share") or 0.0)
        goods = c["m"] - svc
        bal = c["bal"]
        sign = "&minus;" if bal < 0 else ""
        t += ("|-\n| " + str(i) + " || {{flag|" + c["name"] + "}} || " + m(c["m"])
              + " || " + pct(c["m"] / wx) + " || " + m(goods) + " || " + m(svc)
              + " || " + sign + m(abs(bal)) + "\n")
    t += "|}\n"
    pages["List_of_countries_by_imports"] = (
        "'''This is a list of countries by imports''' of goods and services, measured in "
        "millions of [[Lahn|LND]]. Figures are Global Trade Union estimates for " + str(year)
        + ".\n\nThe trade balance is a country's exports less its imports; a negative "
        "figure is a deficit. World imports balance world exports, so the world trade "
        "balance is zero.\n\n"
        "==Table==\n" + t + FOOT)

    # ---- by category -------------------------------------------------------
    body = ("'''This is a list of the leading exporters in each category of traded goods "
            "and services''', measured in millions of [[Lahn|LND]]. Figures are Global "
            "Trade Union estimates for " + str(year) + ".\n\nTrade is divided into fifteen "
            "categories, twelve of goods and three of services. The share shown is each "
            "country's share of world exports in that category, not of its own exports.\n\n")
    for key, lab, kind in tb.CATEGORIES:
        rows = L["by_category"].get(key) or []
        if not rows:
            continue
        tot = sum(v for _, v in rows) or 1.0
        world_cat = sum(C[n]["basket"].get(key, 0.0)
                        * (C[n]["goods_x"] + C[n]["svc_x"] - C[n]["reexports"])
                        for n in C) or 1.0
        body += "=== " + lab + " ===\n"
        body += head(lab + " exports (million LND), " + str(year),
                     ["Rank", "Country", "Exports", "Share of world " + lab.lower()])
        for i, (name, v) in enumerate(rows, 1):
            body += ("|-\n| " + str(i) + " || {{flag|" + name + "}} || " + m(v)
                     + " || " + pct(v / world_cat) + "\n")
        body += "|}\n\n"
    pages["List_of_top_exporting_countries_by_category"] = body + FOOT

    # ---- high tech ---------------------------------------------------------
    ht = L["high_tech"]
    t = head("High-technology exports (million LND) by country, " + str(year),
             ["Rank", "Country", "High-technology exports",
              "Share of the country's manufactured exports"])
    for i, (name, v, share) in enumerate(ht[:60], 1):
        t += ("|-\n| " + str(i) + " || {{flag|" + name + "}} || " + m(v)
              + " || " + pct(share) + "\n")
    t += "|}\n"
    pages["List_of_countries_by_high-tech_exports"] = (
        "'''This is a list of countries by high-technology exports''', measured in millions "
        "of [[Lahn|LND]]. Figures are Global Trade Union estimates for " + str(year) + REF
        + ".\n\nHigh-technology exports are products of high research and development "
        "intensity: electronics and electrical equipment, machinery and industrial "
        "equipment, chemicals and pharmaceuticals, and aerospace. The share is of each "
        "country's manufactured exports rather than of its exports as a whole, so "
        "commodity exporters are not flattered by a small manufacturing base.\n\n"
        "The sixty largest exporters are listed.\n\n"
        "==Table==\n" + t + FOOT)

    # ---- leading trade partners --------------------------------------------
    lp = sorted(L["leading_partners"], key=lambda r: -C[r[0]]["x"])
    t = head("Largest trading partners by country, " + str(year),
             ["Country", "Largest export market", "Share of exports",
              "Largest source of imports", "Share of imports"])
    for name, xp, xs, mp, ms in lp:
        t += ("|-\n| {{flag|" + name + "}} || {{flag|" + xp + "}} || " + pct(xs)
              + " || {{flag|" + mp + "}} || " + pct(ms) + "\n")
    t += "|}\n"
    pages["List_of_countries_by_leading_trade_partners"] = (
        "'''This is a list of countries by their largest trading partners''', showing the "
        "single largest destination for each country's exports and the single largest "
        "source of its imports. Figures are Global Trade Union estimates for " + str(year)
        + REF + ".\n\nThe two are frequently different: a country's biggest customer need "
        "not be its biggest supplier, because what a country sells and what it buys are "
        "rarely made in the same places.\n\n"
        "Countries are listed in order of the size of their exports.\n\n"
        "==Table==\n" + t + FOOT)
    return pages


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    with io.open(JSON, encoding="utf-8") as fh:
        data = json.load(fh)
    pages = build(data)
    for name, text in pages.items():
        if "—" in text:
            raise SystemExit(f"{name}: em-dash found; house style forbids it")
        path = os.path.join(OUT, name + ".wiki")
        existed = os.path.exists(path)
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"  {'updated' if existed else 'wrote  '} {name}.wiki  "
              f"({len(text):,} bytes, {text.count(chr(10)) + 1} lines)")
    print("\nNothing has been published. To create these on the wiki:")
    for name in pages:
        print(f"  python _publish_new.py pages/Main/{name}.wiki")


if __name__ == "__main__":
    main()
