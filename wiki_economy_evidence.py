#!/usr/bin/env python3
"""
wiki_economy_evidence.py - what the wiki already says each country makes.

The export baskets are authored "data first, then wiki canon flavour". This is
the flavour half, done mechanically so it is reproducible: every country page is
scanned for economy vocabulary, each hit is credited to one of the fifteen
export categories, and the Great Importance sheet's 'Economic' column is folded
in. Nothing here decides a basket on its own; it nudges the data-driven default
toward what DJ has already written.

Writes data/wiki_economy_evidence.json: {country: {category: hits}}.
"""
import collections, json, os, re, sys

import openpyxl
import andah_data as ad

PAGES = os.path.join(ad.HERE, "pages", "Main")
OUT = os.path.join(ad.DATA, "wiki_economy_evidence.json")

# category -> vocabulary. Word-boundary, case-insensitive. Keep these concrete:
# a word like "industry" says nothing about WHICH industry and is left out.
VOCAB = {
    "crude_oil_gas":   ["crude oil", "oil field", "oilfield", "petroleum", "natural gas", "gas field",
                        "oil reserves", "oil production", "oil industry", "oil exports?", "gas exports?"],
    "refined_fuels":   ["refiner(?:y|ies)", "refined", "coal", "colliery", "uranium", "nuclear fuel", "bunker(?:ing)?"],
    "ores_metals":     ["iron ore", "copper", "aluminium", "bauxite", "nickel", "zinc", "steel", "smelt(?:er|ing)",
                        "tin mine", "lead mine", "mining", r"\bmines?\b", "lithium", "manganese", "chromium", "cobalt"],
    "precious":        ["gold", "silver", "diamonds?", "platinum", "gemstones?", "jewell?ery"],
    "agri_food":       ["agricultur(?:e|al)", "farming", r"\bfarms?\b", "wheat", "rice", "cattle", "livestock",
                        "fisher(?:y|ies)", "fishing", "dairy", "sugar", "coffee", "tea plantation", "cocoa",
                        "fruit", "wine", "vineyards?", "grain", "maize", "olives?"],
    "forestry_paper":  ["timber", "forestry", "logging", "paper", "pulp", "cotton", "wool", "rubber"],
    "textiles":        ["textiles?", "garments?", "apparel", "clothing", "weaving", "silk"],
    "chemicals":       ["chemicals?", "pharmaceutical", "fertili[sz]er", "plastics", "petrochemical"],
    "machinery":       ["machinery", "heavy industry", "engineering", "industrial equipment", "machine tools?",
                        "manufacturing"],
    "electronics":     ["electronics", "semiconductor", "microchip", "computers?", "telecommunications?",
                        "high[- ]tech", "technology sector", "technological"],
    "vehicles":        ["automotive", "automobile", "car manufactur", "vehicles?", "shipbuilding", "shipyards?",
                        "aircraft", "aerospace", "aviation industry", "railway manufactur", "locomotives?"],
    "other_manuf":     ["furniture", "consumer goods", "ceramics", "glassware", "toys"],
    "transport":       [r"\bports?\b", "shipping", "canal", "harbou?rs?", "container", "logistics", "transit",
                        "transshipment", "entrep[oô]t", "merchant fleet", "stopover"],
    "tourism":         ["tourism", "tourists?", "resorts?", "beaches", "holiday"],
    "finance_business":["bank(?:ing|s)?", "financial (?:centre|center|services|sector)", "insurance", "offshore",
                        "stock exchange", "software", "IT services", "business services"],
}
RX = {cat: re.compile("|".join(f"(?:{w})" for w in words), re.I) for cat, words in VOCAB.items()}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    countries = ad.load_janus()
    evidence = {}
    missing = []
    for name in countries:
        path = os.path.join(PAGES, name.replace(" ", "_") + ".wiki")
        if not os.path.exists(path):
            missing.append(name)
            continue
        text = open(path, encoding="utf-8", errors="ignore").read()
        # strip infobox parameters and refs so a citation URL cannot count as evidence
        text = re.sub(r"<ref[^>]*>.*?</ref>", " ", text, flags=re.S)
        text = re.sub(r"\{\{[^{}]*\}\}", " ", text)
        hits = {cat: len(rx.findall(text)) for cat, rx in RX.items()}
        evidence[name] = {k: v for k, v in hits.items() if v}

    # Great Importance sheet: a free-text 'Economic' column for 26 major countries
    wb = openpyxl.load_workbook(ad.JANUS, read_only=True, data_only=True)
    gi = {}
    if "Great Importance" in wb.sheetnames:
        ws = wb["Great Importance"]
        hdr = None
        for r in ws.iter_rows(values_only=True):
            if hdr is None:
                hdr = [str(x).strip() if x else "" for x in r]
                continue
            if not r or not r[1]:
                continue
            row = dict(zip(hdr, r))
            econ = str(row.get("Economic") or "").strip()
            interests = str(row.get(" Strategic Interests") or row.get("Strategic Interests") or "").strip()
            blob = (econ + " " + interests).strip()
            if blob and blob != "None":
                gi[str(r[1]).strip()] = blob
                for cat, rx in RX.items():
                    n = len(rx.findall(blob))
                    if n:
                        evidence.setdefault(str(r[1]).strip(), {})
                        evidence[str(r[1]).strip()][cat] = evidence[str(r[1]).strip()].get(cat, 0) + 3 * n
    wb.close()

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(dict(evidence=evidence, great_importance=gi), fh, indent=1)
    covered = sum(1 for v in evidence.values() if v)
    print(f"wrote {OUT}")
    print(f"  pages scanned: {len(countries) - len(missing)}   missing pages: {len(missing)} {missing[:6]}")
    print(f"  countries with any economy evidence: {covered}/172")
    top = collections.Counter()
    for v in evidence.values():
        for k, n in v.items():
            top[k] += n
    print("  hits by category:", dict(top.most_common()))
    for n in ["Easuhura", "Raledria", "Dahe", "Emara", "Pelugrotoa", "Merela Sta"]:
        print(f"  {n:<12} {evidence.get(n)}")


if __name__ == "__main__":
    main()
