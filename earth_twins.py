#!/usr/bin/env python3
"""
earth_twins.py - does each Andah country's export basket look like a real one?

DJ: "look at similar sized nations and economies, population sizes, and see the
earth data, see if yours looks realistic in comparison, or has a earth twin,
eg Ireland and most of its exports being pharmaceuticals."

The Earth 2015 suite already checks the world's SHAPE: concentration, openness,
the size of the tail. It says nothing about whether an individual country's
basket is a thing a real economy does. This does that, per country.

HOW A TWIN IS CHOSEN
  Nearest real economy in three dimensions at once: population, GDP per capita,
  and whether it is an island or landlocked. Distance is in logs, because the
  difference between 1m and 10m people matters as much as between 10m and 100m.
  A twin is only reported when it is genuinely close; a country with no near
  neighbour on Earth is said to have none rather than being forced onto one.

WHAT IT REPORTS
  For each Andah country: its twin, the twin's real export profile, and where
  the two disagree by more than a threshold. The point is not to force Andah to
  copy Earth. It is to surface the cases where the model has produced something
  no real economy of that size and income does, so DJ can judge.

THE EARTH FIGURES
  Approximate 2015 export structures, in the model's own fifteen categories,
  from published trade profiles. They are rounded and are meant to capture the
  SHAPE of each economy (Bangladesh is overwhelmingly garments, Botswana
  overwhelmingly diamonds, Ireland heavily pharmaceutical) rather than to be
  precise to the percentage point.
"""

import math

import trade_baskets as tb

# name, population (millions), GDP per capita USD 2015, island, landlocked,
# {category: share of exports}
EARTH = [
    # --- petrostates -------------------------------------------------------
    ("Saudi Arabia", 31.6, 20_600, 0, 0, dict(crude_oil_gas=.75, refined_fuels=.08, chemicals=.09, other_manuf=.03, transport=.02, tourism=.02)),
    ("Kuwait", 3.9, 29_300, 0, 0, dict(crude_oil_gas=.85, refined_fuels=.06, chemicals=.04, other_manuf=.02, transport=.02)),
    ("Qatar", 2.4, 65_000, 0, 0, dict(crude_oil_gas=.82, chemicals=.07, refined_fuels=.04, transport=.04, other_manuf=.02)),
    ("Angola", 27.9, 4_200, 0, 0, dict(crude_oil_gas=.93, precious=.03, agri_food=.02, other_manuf=.01)),
    ("Nigeria", 181.0, 2_700, 0, 0, dict(crude_oil_gas=.87, agri_food=.05, refined_fuels=.02, other_manuf=.03, transport=.02)),
    ("Azerbaijan", 9.6, 5_500, 0, 0, dict(crude_oil_gas=.87, agri_food=.05, ores_metals=.02, other_manuf=.03, transport=.02)),
    ("Kazakhstan", 17.5, 10_500, 0, 1, dict(crude_oil_gas=.62, ores_metals=.17, agri_food=.06, chemicals=.05, other_manuf=.06, transport=.03)),
    ("Norway", 5.2, 74_400, 0, 0, dict(crude_oil_gas=.55, agri_food=.12, ores_metals=.07, machinery=.07, transport=.08, other_manuf=.06, tourism=.03)),
    # --- mining ------------------------------------------------------------
    ("Chile", 17.9, 13_600, 0, 0, dict(ores_metals=.50, agri_food=.24, forestry_paper=.08, chemicals=.05, other_manuf=.06, tourism=.04, transport=.03)),
    ("Zambia", 16.2, 1_300, 0, 1, dict(ores_metals=.75, agri_food=.09, chemicals=.05, other_manuf=.06, tourism=.05)),
    ("Mongolia", 3.0, 3_900, 0, 1, dict(ores_metals=.62, crude_oil_gas=.13, precious=.09, textiles=.06, agri_food=.05, tourism=.05)),
    ("Botswana", 2.2, 6_500, 0, 1, dict(precious=.85, ores_metals=.04, agri_food=.03, other_manuf=.03, tourism=.05)),
    ("Peru", 31.4, 6_000, 0, 0, dict(ores_metals=.42, precious=.15, agri_food=.22, textiles=.05, forestry_paper=.03, other_manuf=.06, tourism=.07)),
    ("Guinea", 12.0, 700, 0, 0, dict(ores_metals=.70, precious=.18, agri_food=.07, other_manuf=.05)),
    # --- agriculture -------------------------------------------------------
    ("Ethiopia", 99.4, 640, 0, 1, dict(agri_food=.72, textiles=.06, precious=.05, forestry_paper=.04, other_manuf=.05, transport=.08)),
    ("Kenya", 46.1, 1_350, 0, 0, dict(agri_food=.55, chemicals=.07, textiles=.06, other_manuf=.09, tourism=.13, transport=.10)),
    ("Ghana", 27.6, 1_700, 0, 0, dict(precious=.42, crude_oil_gas=.20, agri_food=.27, other_manuf=.06, tourism=.05)),
    ("Paraguay", 6.6, 4_100, 0, 1, dict(agri_food=.68, forestry_paper=.05, textiles=.04, ores_metals=.03, other_manuf=.12, transport=.08)),
    ("Uruguay", 3.4, 15_500, 0, 0, dict(agri_food=.62, forestry_paper=.09, chemicals=.05, textiles=.03, other_manuf=.08, tourism=.09, finance_business=.04)),
    ("Argentina", 43.4, 13_800, 0, 0, dict(agri_food=.55, vehicles=.11, chemicals=.07, ores_metals=.04, machinery=.05, other_manuf=.10, tourism=.05, transport=.03)),
    ("New Zealand", 4.6, 38_600, 1, 0, dict(agri_food=.58, forestry_paper=.10, ores_metals=.03, machinery=.05, other_manuf=.07, tourism=.13, transport=.04)),
    # --- textiles / light manufacturing ------------------------------------
    ("Bangladesh", 161.0, 1_250, 0, 0, dict(textiles=.85, agri_food=.04, forestry_paper=.02, other_manuf=.05, transport=.02, finance_business=.02)),
    ("Cambodia", 15.5, 1_200, 0, 0, dict(textiles=.70, agri_food=.08, other_manuf=.07, tourism=.13, transport=.02)),
    ("Sri Lanka", 21.0, 3_900, 1, 0, dict(textiles=.44, agri_food=.20, other_manuf=.09, chemicals=.03, tourism=.16, transport=.08)),
    ("Vietnam", 91.7, 2_100, 0, 0, dict(electronics=.32, textiles=.24, agri_food=.14, other_manuf=.13, machinery=.06, tourism=.07, transport=.04)),
    ("Honduras", 8.9, 2_400, 0, 0, dict(textiles=.52, agri_food=.32, other_manuf=.07, tourism=.06, transport=.03)),
    # --- manufacturing -----------------------------------------------------
    ("Germany", 81.7, 41_300, 0, 0, dict(vehicles=.23, machinery=.20, chemicals=.16, electronics=.13, other_manuf=.11, agri_food=.05, finance_business=.06, transport=.04, tourism=.02)),
    ("Japan", 127.0, 34_500, 1, 0, dict(vehicles=.25, machinery=.22, electronics=.18, chemicals=.12, ores_metals=.06, other_manuf=.08, finance_business=.05, transport=.03, tourism=.01)),
    ("South Korea", 51.0, 27_200, 0, 0, dict(electronics=.30, vehicles=.16, machinery=.13, refined_fuels=.09, chemicals=.10, ores_metals=.06, other_manuf=.07, transport=.06, tourism=.03)),
    ("China", 1371.0, 8_100, 0, 0, dict(electronics=.30, machinery=.17, textiles=.13, other_manuf=.15, chemicals=.06, vehicles=.05, ores_metals=.05, agri_food=.03, transport=.03, tourism=.03)),
    ("Mexico", 121.9, 9_200, 0, 0, dict(vehicles=.27, electronics=.24, machinery=.13, agri_food=.07, crude_oil_gas=.06, chemicals=.05, other_manuf=.10, tourism=.06, transport=.02)),
    ("Czechia", 10.6, 17_800, 0, 1, dict(vehicles=.24, machinery=.22, electronics=.17, chemicals=.07, other_manuf=.13, agri_food=.04, finance_business=.05, transport=.05, tourism=.03)),
    ("Poland", 38.0, 12_600, 0, 0, dict(machinery=.19, vehicles=.16, electronics=.13, other_manuf=.15, agri_food=.11, chemicals=.07, forestry_paper=.05, transport=.09, tourism=.05)),
    ("Slovakia", 5.4, 16_100, 0, 1, dict(vehicles=.32, electronics=.20, machinery=.15, ores_metals=.07, chemicals=.05, other_manuf=.11, transport=.05, tourism=.03)),
    ("Thailand", 68.7, 5_800, 0, 0, dict(electronics=.22, machinery=.15, vehicles=.13, agri_food=.14, chemicals=.08, other_manuf=.09, tourism=.14, transport=.03)),
    ("Malaysia", 30.3, 9_600, 0, 0, dict(electronics=.33, refined_fuels=.11, crude_oil_gas=.08, chemicals=.08, machinery=.08, agri_food=.09, other_manuf=.11, tourism=.09, transport=.03)),
    ("Turkey", 78.5, 10_900, 0, 0, dict(vehicles=.15, machinery=.12, textiles=.17, ores_metals=.09, agri_food=.12, chemicals=.06, other_manuf=.13, tourism=.12, transport=.04)),
    # --- services / finance / tourism --------------------------------------
    ("Ireland", 4.7, 61_800, 1, 0, dict(chemicals=.55, electronics=.08, machinery=.05, agri_food=.09, other_manuf=.04, finance_business=.15, transport=.02, tourism=.02)),
    ("Switzerland", 8.3, 82_000, 0, 1, dict(chemicals=.38, precious=.17, machinery=.13, other_manuf=.12, electronics=.05, finance_business=.11, tourism=.03, transport=.01)),
    ("Singapore", 5.5, 55_600, 1, 0, dict(electronics=.28, chemicals=.13, refined_fuels=.14, machinery=.09, other_manuf=.07, finance_business=.15, transport=.11, tourism=.03)),
    ("Luxembourg", 0.57, 101_000, 0, 1, dict(finance_business=.62, ores_metals=.08, machinery=.07, other_manuf=.09, chemicals=.04, transport=.06, tourism=.04)),
    ("United Kingdom", 65.1, 44_300, 1, 0, dict(finance_business=.30, machinery=.12, vehicles=.10, chemicals=.11, precious=.06, electronics=.06, other_manuf=.09, tourism=.08, transport=.05, agri_food=.03)),
    ("Cyprus", 1.2, 23_300, 1, 0, dict(transport=.32, finance_business=.26, tourism=.20, agri_food=.08, chemicals=.06, other_manuf=.08)),
    ("Malta", 0.43, 24_800, 1, 0, dict(finance_business=.30, tourism=.24, electronics=.14, other_manuf=.10, transport=.14, chemicals=.05, agri_food=.03)),
    ("Panama", 3.9, 13_700, 0, 0, dict(transport=.48, finance_business=.16, tourism=.14, agri_food=.13, other_manuf=.06, precious=.03)),
    ("Iceland", 0.33, 51_000, 1, 0, dict(agri_food=.38, ores_metals=.22, tourism=.28, other_manuf=.05, transport=.04, finance_business=.03)),
    # --- island / tourism economies ----------------------------------------
    ("Maldives", 0.41, 8_600, 1, 0, dict(tourism=.75, agri_food=.13, transport=.07, other_manuf=.03, finance_business=.02)),
    ("Mauritius", 1.3, 9_300, 1, 0, dict(tourism=.30, textiles=.20, agri_food=.16, finance_business=.16, other_manuf=.10, transport=.08)),
    ("Fiji", 0.89, 5_000, 1, 0, dict(tourism=.48, agri_food=.24, forestry_paper=.05, other_manuf=.09, transport=.09, ores_metals=.05)),
    ("Jamaica", 2.9, 5_000, 1, 0, dict(tourism=.52, ores_metals=.16, agri_food=.14, chemicals=.05, other_manuf=.07, transport=.06)),
    ("Seychelles", 0.09, 15_400, 1, 0, dict(tourism=.58, agri_food=.28, transport=.07, other_manuf=.04, finance_business=.03)),
    ("Bahamas", 0.39, 22_800, 1, 0, dict(tourism=.68, transport=.11, finance_business=.10, chemicals=.05, agri_food=.04, other_manuf=.02)),
    # --- small, poor, landlocked -------------------------------------------
    ("Nepal", 28.5, 750, 0, 1, dict(textiles=.32, agri_food=.24, other_manuf=.16, ores_metals=.06, tourism=.18, transport=.04)),
    ("Rwanda", 11.6, 720, 0, 1, dict(ores_metals=.32, agri_food=.38, precious=.06, other_manuf=.06, tourism=.14, transport=.04)),
    ("Malawi", 17.2, 380, 0, 1, dict(agri_food=.82, textiles=.04, ores_metals=.04, other_manuf=.05, tourism=.05)),
    ("Moldova", 3.6, 1_800, 0, 1, dict(agri_food=.45, textiles=.19, machinery=.08, other_manuf=.12, transport=.08, tourism=.05, finance_business=.03)),
    ("Kyrgyzstan", 6.0, 1_100, 0, 1, dict(precious=.38, agri_food=.16, textiles=.13, ores_metals=.08, other_manuf=.11, transport=.09, tourism=.05)),
]

# When is a difference worth reporting? A category has to be materially large in
# one and materially small in the other; small wobbles are not findings.
GAP = 0.22
TWIN_MAX_DISTANCE = 1.5     # in the log-space metric below


def _twin_distance(pop_a, pc_a, isl_a, ll_a, pop_b, pc_b, isl_b, ll_b):
    d = (math.log(max(pop_a, 1e-4) / max(pop_b, 1e-4)) / 2.0) ** 2
    d += (math.log(max(pc_a, 1.0) / max(pc_b, 1.0)) / 1.1) ** 2
    d += 0.55 * (isl_a != isl_b) + 0.55 * (ll_a != ll_b)
    return math.sqrt(d)


def find_twin(pop_m, gdp_pc_usd, island, landlocked):
    best = None
    for name, pop, pc, isl, ll, basket in EARTH:
        d = _twin_distance(pop_m, gdp_pc_usd, island, landlocked, pop, pc, isl, ll)
        if best is None or d < best[0]:
            best = (d, name, basket, pop, pc)
    if not best or best[0] > TWIN_MAX_DISTANCE:
        return None
    return dict(distance=best[0], name=best[1], basket=best[2],
                population=best[3], gdp_pc=best[4])


def compare(rows, lahn_per_usd):
    """
    For every country: its twin and any category where the two disagree sharply.
    lahn_per_usd converts Andah per-capita income onto the Earth scale, taken
    from the two worlds' median incomes rather than assumed, so the match is on
    relative standing rather than on a currency the two do not share.
    """
    out = []
    for r in rows:
        pop_m = r["population"] / 1e6
        pc_usd = r["gdp_pc"] / lahn_per_usd
        twin = find_twin(pop_m, pc_usd, 1 if r["is_island"] else 0,
                         1 if r["landlocked"] else 0)
        basket = r.get("basket") or {}
        gaps = []
        if twin:
            for k in tb.KEYS:
                a, e = basket.get(k, 0.0), twin["basket"].get(k, 0.0)
                if abs(a - e) >= GAP:
                    gaps.append((k, a, e))
            gaps.sort(key=lambda g: -abs(g[1] - g[2]))
        out.append(dict(country=r["name"], pop_m=pop_m, pc_usd=pc_usd,
                        twin=twin, gaps=gaps, basket=basket,
                        island=bool(r["is_island"]), landlocked=bool(r["landlocked"]),
                        gdp=r["gdp"]))
    return out


def median_scale(rows):
    """
    Lahn per USD, from the two worlds' MEDIAN per-capita income. Anchoring on the
    median rather than the mean keeps a handful of very rich microstates from
    setting the exchange rate for everybody.
    """
    earth_pc = sorted(pc for _n, _p, pc, _i, _l, _b in EARTH)
    andah_pc = sorted(r["gdp_pc"] for r in rows if r["gdp_pc"] > 0)
    if not andah_pc or not earth_pc:
        return 1.0
    return andah_pc[len(andah_pc) // 2] / earth_pc[len(earth_pc) // 2]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    import andah_data as ad
    import build_trade_model as M

    data = ad.load_all()
    rows, flows, meta = M.run(data)
    scale = median_scale(rows)
    res = compare(rows, scale)

    print(f"lahn per USD, from the two medians: {scale:,.1f}")
    matched = [r for r in res if r["twin"]]
    print(f"countries with a close Earth twin: {len(matched)}/{len(res)}")
    flagged = [r for r in matched if r["gaps"]]
    print(f"of those, disagreeing sharply on at least one category: {len(flagged)}")
    print()

    print("SMALLEST 30 ECONOMIES, against their twins")
    print(f"{'COUNTRY':<15}{'pop m':>7}{'$/head':>9}  {'TWIN':<15}{'twin $/head':>12}   basket vs twin")
    print("-" * 108)
    for r in sorted(matched, key=lambda x: x["gdp"])[:30]:
        t = r["twin"]
        top = max(r["basket"].items(), key=lambda kv: kv[1]) if r["basket"] else ("", 0)
        ttop = max(t["basket"].items(), key=lambda kv: kv[1])
        mark = "  <-- " + ", ".join(f"{k} {a:.0%} vs {e:.0%}" for k, a, e in r["gaps"][:2]) if r["gaps"] else ""
        print(f"{r['country']:<15}{r['pop_m']:>7.1f}{r['pc_usd']:>9,.0f}  {t['name']:<15}{t['gdp_pc']:>12,.0f}   "
              f"{tb.LABEL[top[0]][:20] if top[0] else '':<22}{top[1]:>5.0%} | twin {tb.LABEL[ttop[0]][:18]} {ttop[1]:.0%}{mark}")

    print()
    print("BIGGEST DISAGREEMENTS ANYWHERE")
    for r in sorted(flagged, key=lambda x: -abs(x["gaps"][0][1] - x["gaps"][0][2]))[:18]:
        k, a, e = r["gaps"][0]
        print(f"  {r['country']:<15} {tb.LABEL[k]:<34} model {a:>5.0%}   {r['twin']['name']} {e:>5.0%}")
