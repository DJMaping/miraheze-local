#!/usr/bin/env python3
"""
trade_baskets.py - what each country exports, by category, and what it imports.

THE CATEGORIES
  Fifteen, chosen from the HS section structure and checked against real 2015
  country profiles so that every real economy fits without a residual: Saudi
  Arabia lands ~80% in crude oil & gas, Bangladesh ~85% in textiles, Chile ~50%
  in ores, Germany spread across machinery, vehicles and chemicals, the
  Maldives in tourism. Twelve goods categories, three services.

HOW A DEFAULT BASKET IS BUILT, "data first, then wiki canon flavour"
  1. Resource categories take their value straight from the production sheets:
     each commodity's share of world output times its trade weight, mapped to a
     category. A country with a fifth of the world's oil gets a basket that is
     mostly crude, and it is the same figure the openness regression used.
  2. What is left of goods exports is split across agriculture and the
     manufacturing categories by INCOME, interpolated between four real-world
     profiles (low income is farm produce and textiles, high income is
     machinery, vehicles, chemicals and electronics). This is the structural
     transformation every real economy follows.
  3. Services split by income and geography: transit hubs earn transport, islands
     and coasts earn tourism, rich economies earn finance.
  4. The wiki flavour: every country page was scanned for economy vocabulary
     (wiki_economy_evidence.py). Where DJ has already written that a country has
     an oil industry or a financial centre, that category is nudged up. It is a
     nudge, bounded, and never creates a category from nothing.
  5. Concentration is then sharpened to the Earth-realistic target the model
     already computes: a poor petrostate ends up 80-90% in one line, a rich
     diversified economy has no line above a quarter.

EDITING
  The workbook's 'Export baskets' sheet is the editable copy; 'Export baskets
  (model default)' is what the model generated. On re-run, any country whose
  editable row differs from its stored default is treated as hand-set and used
  as written, renormalised to 100%. Nothing else about the model needs to know
  the difference: leading export, concentration, the label, the trade partners
  and the atlas all read the basket.

IMPORT DEMAND
  Derived, never edited: a country buys what it does not make, scaled by the
  world's mix. A country exporting 40% oil has a small oil import need; an
  industrialising economy with no machinery of its own has a large one. This
  is what makes trade COMPLEMENTARY in the gravity layer.
"""

import math
import os

import openpyxl

# (key, label, goods|services)
CATEGORIES = [
    ("crude_oil_gas",    "Crude oil & natural gas",          "goods"),
    ("refined_fuels",    "Refined fuels & coal",             "goods"),
    ("ores_metals",      "Ores & base metals",               "goods"),
    ("precious",         "Precious metals & gems",           "goods"),
    ("agri_food",        "Food, crops & livestock",          "goods"),
    ("forestry_paper",   "Forestry, paper & fibres",         "goods"),
    ("textiles",         "Textiles & apparel",               "goods"),
    ("chemicals",        "Chemicals & pharmaceuticals",      "goods"),
    ("machinery",        "Machinery & industrial equipment", "goods"),
    ("electronics",      "Electronics & electrical",         "goods"),
    ("vehicles",         "Vehicles, ships & aircraft",       "goods"),
    ("other_manuf",      "Other manufactures",               "goods"),
    ("transport",        "Transport & logistics services",   "services"),
    ("tourism",          "Travel & tourism",                 "services"),
    ("finance_business", "Finance, business & IT services",  "services"),
]
KEYS = [k for k, _, _ in CATEGORIES]
LABEL = {k: l for k, l, _ in CATEGORIES}
GOODS = [k for k, _, t in CATEGORIES if t == "goods"]
SERVICES = [k for k, _, t in CATEGORIES if t == "services"]
RESOURCE = ["crude_oil_gas", "refined_fuels", "ores_metals", "precious"]
MANUF = ["agri_food", "forestry_paper", "textiles", "chemicals", "machinery",
         "electronics", "vehicles", "other_manuf"]

# production sheet -> category
COMMODITY_CATEGORY = {
    "Petrol": "refined_fuels", "Diesel": "refined_fuels", "Jet fuel": "refined_fuels",
    "Fuel oil": "refined_fuels",          # modelled tables, build_trade_model.refinery_tables
    "Oil": "crude_oil_gas", "Natural Gas": "crude_oil_gas",
    "Coal": "refined_fuels", "Uranium": "refined_fuels", "Thorium": "refined_fuels",
    "Iron": "ores_metals", "Copper": "ores_metals", "Aluminium": "ores_metals",
    "Nickel": "ores_metals", "Zinc": "ores_metals", "Tin": "ores_metals",
    "Lead": "ores_metals", "Lithium": "ores_metals", "Manganese": "ores_metals",
    "Titanium": "ores_metals", "Cobalt": "ores_metals", "Chromium": "ores_metals",
    "Magnesium": "ores_metals", "Vanadium": "ores_metals", "Niobium": "ores_metals",
    "Silicon": "ores_metals", "Bismuth": "ores_metals", "Mercury": "ores_metals",
    "Iridium": "ores_metals", "Salt": "ores_metals", "Bentonite": "ores_metals",
    "Feldspar": "ores_metals", "Fluorite": "ores_metals",
    "Gold": "precious", "Silver": "precious", "Platinum": "precious",
    "Palladium": "precious", "Diamond": "precious",
    "Paper": "forestry_paper",
    "Motor vehicle": "vehicles",
}

# Non-resource goods split by income band. Shares of the NON-resource remainder.
# Anchored on real 2015 profiles: low income looks like Ethiopia or Cambodia,
# lower-middle like Vietnam or India, upper-middle like Mexico or Turkey, high
# like Germany or Japan. Interpolated on log income between the anchors.
INCOME_PROFILES = [
    # (gdp per capita new lahn, {category: share of non-resource goods})
    (12_000,  dict(agri_food=.44, forestry_paper=.08, textiles=.21, other_manuf=.12,
                   chemicals=.03, machinery=.07, electronics=.03, vehicles=.02)),
    (45_000,  dict(agri_food=.24, forestry_paper=.06, textiles=.22, other_manuf=.14,
                   chemicals=.07, machinery=.12, electronics=.10, vehicles=.05)),
    (120_000, dict(agri_food=.12, forestry_paper=.04, textiles=.10, other_manuf=.13,
                   chemicals=.12, machinery=.18, electronics=.17, vehicles=.14)),
    (280_000, dict(agri_food=.07, forestry_paper=.03, textiles=.04, other_manuf=.11,
                   chemicals=.17, machinery=.22, electronics=.16, vehicles=.20)),
]
SERVICE_PROFILES = [
    # transport lowered and finance raised (Sep 1765 review): the world was
    # shipping 5.3% of its trade as transport services (Earth 4.2%) and only
    # 9.5% as finance and business (Earth 12.1%). Tourism is booked in money
    # by the receipts model; its profile share only matters for backcasts.
    (12_000,  dict(transport=.27, tourism=.42, finance_business=.31)),
    (120_000, dict(transport=.23, tourism=.30, finance_business=.47)),
    (280_000, dict(transport=.18, tourism=.22, finance_business=.60)),
]

FLAVOUR = 0.22          # strength of the wiki-vocabulary nudge
FLAVOUR_CAP = 2.0       # no category is more than doubled by flavour alone
# Resource dominance ceiling, as a FUNCTION of how concentrated a country
# genuinely is rather than one hard number. A flat 0.92 put 25 countries on
# exactly 90%, which is the ceiling binding rather than economics: real
# resource economies spread out (Angola 93% oil, Nigeria 87%, Kuwait 85%,
# Botswana 85% diamonds) and never cluster on an identical value. The curve
# below reaches 0.93 only for the truly extreme and holds a country producing
# 3x its GDP share of some commodity nearer 50%.
RESOURCE_CEILING_MIN = 0.45
RESOURCE_CEILING_MAX = 0.93
RESOURCE_CEILING_SCALE = 25.0


def resource_ceiling(concentration):
    return RESOURCE_CEILING_MIN + (RESOURCE_CEILING_MAX - RESOURCE_CEILING_MIN) * (
        1.0 - math.exp(-max(concentration, 0.0) / RESOURCE_CEILING_SCALE))


# Small island states. Earth's are tourism economies, because an island with no
# land and no factories sells the one thing it has: Maldives 75% tourism,
# Bahamas 68%, Seychelles 58%, Jamaica 52%, Fiji 48%. The model was giving
# Andah's 19 small islands a median 11%, and food as their leading export.
# DJ asked for the Fiji shape rather than the Maldives one: strongly touristic
# but with agriculture still material.
ISLAND_MAX_POP = 3_000_000
ISLAND_SERVICES_FLOOR = 0.52     # services as a share of exports
ISLAND_TOURISM_LIFT = 3.2        # within services, before renormalising

# DJ'S CANON. Statements about what a country makes that override the
# data-driven default. These are pinned shares for the named categories; every
# other category keeps its default weight and is scaled to fill the remainder.
# Kept in code rather than only in the workbook so a rebuild cannot lose them.
# Sharpening is skipped for these rows: the canon IS the concentration.
#
#   "Pelugrotoa and Areoix Lie are both large manufacturing hubs now, rivalling
#    Dahe and Raledria" - manufacturing overtakes oil as Pelugrotoa's first
#    line, oil stays a large second line (it still holds a fifth of world crude).
CANON_BASKETS = {
    # DJ: "Pelugrotoa and Areoix Lie are both large manufacturing hubs now,
    # rivalling Dahe and Raledria." Both baskets were first written to that
    # brief and came out nearly identical - 0.879 similarity, where Earth's
    # China and United States sit at 0.55. The production tables separate them
    # and were not being used: Pelugrotoa builds 27% of the world's motor
    # vehicles, 68.6% of its silicon and 24.9% of its paper, against Areoix
    # Lie's 5% of vehicles. So Pelugrotoa is the heavy-industry hub, cars and
    # materials on top of its oil and gas, and Areoix Lie the lighter one,
    # electronics and machinery. Letting the model derive them instead was
    # tried and rejected: it makes Areoix Lie 36% farm produce and Pelugrotoa a
    # 49% petrostate, which is not what the canon says either of them is.
    # DJ: "make Pelugrotoa way less of a vehicles and aircraft manufacturer".
    # This overrides his own motor-vehicle table, which has it building 27% of
    # the world's cars; the cars-over-ships tilt inside the smaller share still
    # follows that table. Vehicles 25% -> 9%, the rest to machinery, electronics,
    # chemicals and other manufactures.
    # Forestry was pinned at 5% when the vehicles share was cut, which made
    # Pelugrotoa 53% of the world's forest products (Earth's Canada: 12%); at
    # 1.5% it is the leader at about a fifth, as its paper table says.
    # NOTE: every pin here is an ABSOLUTE share of the country's exports, and
    # holds through the world-mix bend in build_trade_model (pinned cells are
    # fixed; only the unpinned cells of the row and column move). The values
    # were re-read against Earth once the world's mix was Earth's: Germany
    # ships 15% machinery, Japan 20%, Taiwan 45% electronics, Korea 30%.
    "Pelugrotoa": dict(vehicles=0.09, crude_oil_gas=0.19, machinery=0.15,
                       electronics=0.15, forestry_paper=0.015, chemicals=0.14,
                       other_manuf=0.06),   # chemicals 10 -> 14: petrochemicals on its oil; the mid-size rich were carrying the world's chemicals
    # DJ: "make Areoix Lie make less chemicals and pharmaceuticals" - held
    # well under the world's 13% while it leads with electronics and machinery.
    "Areoix Lie": dict(electronics=0.30, machinery=0.17, chemicals=0.05,
                       vehicles=0.09, other_manuf=0.07,
                       forestry_paper=0.008),   # not on DJ's forest lists, yet held a quarter of the world's forest products
    # DJ: "Easuhura is more bank and service like London". Its page carries more
    # finance vocabulary than any other in the corpus and it hosts a top-ten
    # centre, so the shape follows the UK's: finance dominant, a real industrial
    # base underneath, tourism material.
    # DJ: "make Easuhura more ship stuff". Vehicles 8% -> 14%, and the product
    # layer tilts that share hard toward ships (CANON_PRODUCT in
    # trade_subcategories), the way Korea's vehicle exports lean to hulls.
    "Easuhura": dict(finance_business=0.31, machinery=0.06, chemicals=0.08,
                     vehicles=0.14, tourism=0.08, electronics=0.05, transport=0.05,
                     forestry_paper=0.005),   # the bend kept handing an island finance centre a tenth of the world's wood
    # DJ: "Chaenia and Trian are electronics manufacturers, like Taiwan and
    # South Korea". Taiwan's electronics are ~45% of exports, Korea's ~30%; the
    # product layer sends theirs to chips.
    "Chaenia": dict(electronics=0.42, machinery=0.08, chemicals=0.09,
                    other_manuf=0.04, vehicles=0.03, transport=0.10),
    "Trian": dict(electronics=0.36, machinery=0.10, vehicles=0.08,
                  chemicals=0.10, other_manuf=0.05),
    # DJ: "Estijan should have more industry". It was 44% ores with 5% of
    # anything made; a rich mining economy with a real industrial base (a
    # Canada, not an Australia) sends about a third of its exports as
    # manufactures. The ores keep their production-table value: Estijan's
    # exports are lifted by CANON_OPENNESS so the industry comes on top of
    # the mining rather than out of it.
    # Ores are pinned at the share that keeps their production-table value
    # (1.39T) once the exports are lifted; without the pin the rest of the
    # basket was scaled down with everything else and the mining shrank.
    "Estijan": dict(ores_metals=0.33, machinery=0.09, vehicles=0.06, chemicals=0.08,
                    electronics=0.05, other_manuf=0.03),
    # Dahe's profile gave the largest economy 0.4% chemicals and no forest
    # products. DJ: "add some chemicals, but do China's forestry, because a
    # lot of their forests were taken away a long time ago; they're still big
    # enough to have a forest". China's forest exports are about 1% of its
    # trade and are processed goods, panels and paper, on imported logs; the
    # product tilt (trade_subcategories.CANON_PRODUCT) does that part.
    "Dahe": dict(chemicals=0.09, forestry_paper=0.010,    # 6 -> 9: still under the US's 12%
                 textiles=0.03),                          # DJ: the clothing goes to Ztesh, Quidic, Erkizil, Wundry
    # DJ: "Yaxuto makes a lot of watches". Switzerland's watches are 7% of its
    # exports; other manufactures pinned so the product tilt has room.
    "Yaxuto": dict(other_manuf=0.08),
    # DJ's forest list says Ucrua is heavily forested; the bend took it to 55%
    # of exports, which is a monoculture. Held at 30%.
    "Ucrua": dict(forestry_paper=0.30),
    # DJ: "spread the excess clothing in Ztesh, Quidic, Erkizil and Wundry".
    # Dahe had a Chinese 27% of the world's textiles on a US-shaped economy;
    # its textiles are held at 3% and the four become the clothing makers.
    # The product ranks follow in trade_subcategories.CANON_RANK.
    "Ztesh":   dict(textiles=0.18),
    "Quidic":  dict(textiles=0.38),
    "Erkizil": dict(textiles=0.18),
    "Wundry":  dict(textiles=0.30),
}

# DJ: countries with large forests ("doesn't mean they are cutting it,
# just for calibration"). A forest is an endowment, so these get a lift on
# the forestry category and, in trade_subcategories, on the products a forest
# of that kind yields: softwood logs, sawn timber and pulp from the boreal
# belt, hardwood logs, sawn timber and panels from the tropics.
FOREST_CANON = {}
for _n in ("Inania", "Deschon", "Reerica", "Pelines", "Fire Coast", "Eldavpir", "Umendel",
           "Pruim Fijan", "Saa", "Ruylku", "Oscairia", "Ucrua", "Mendereide", "Maalle", "Isari",
           "Nia", "Veelmit", "Ashain"):
    FOREST_CANON[_n] = "tropical"
for _n in ("Etirha", "Grazail", "Danocia", "Laselteh", "Arbiya", "Gaeiya", "Estijan", "Genaire",
           "Koruch", "Kusierna", "Volver", "Hyelen", "Mesjan Hyaa", "Iareva", "Nheyes Si", "Desaki"):
    FOREST_CANON[_n] = "boreal"
FOREST_LIFT = {"tropical": 2.2, "boreal": 2.6}
FOREST_MAX = 0.30      # forestry share of goods after the lift, at most

# Trade balances pinned by canon, as a share of GDP. DJ asked for Dahe to run a
# larger deficit; on Earth the biggest consumer market runs about -2.8% of GDP,
# so -2.5% puts it in that company without touching the cap.
CANON_BALANCE = {"Dahe": -0.025}

# HIGH-TECH, derived from the basket rather than a separate column. The OECD
# definition is aerospace, pharmaceuticals, computers and electronics, and
# scientific instruments. Electronics & electrical is almost entirely high-tech;
# the pharma share of chemicals and the aerospace share of vehicles rise with
# income (a poor country's chemicals are fertiliser, a rich one's are drugs).
HIGH_TECH_ELECTRONICS = 0.85


def _income_frac(gdp_pc, lo, hi, lo_pc=12_000, hi_pc=280_000):
    x = math.log(max(gdp_pc, 1.0))
    t = (x - math.log(lo_pc)) / (math.log(hi_pc) - math.log(lo_pc))
    t = max(0.0, min(1.0, t))
    return lo + (hi - lo) * t


def high_tech(basket, gdp_pc):
    """Share of DOMESTIC exports that count as high-tech, and of manufactured exports."""
    pharma = _income_frac(gdp_pc, 0.15, 0.60)
    aero = _income_frac(gdp_pc, 0.03, 0.35)
    ht = (basket.get("electronics", 0.0) * HIGH_TECH_ELECTRONICS
          + basket.get("chemicals", 0.0) * pharma
          + basket.get("vehicles", 0.0) * aero)
    manuf = sum(basket.get(k, 0.0) for k in ("textiles", "chemicals", "machinery",
                                             "electronics", "vehicles", "other_manuf"))
    return ht, (ht / manuf if manuf > 0 else 0.0)


def apply_canon(basket, canon):
    """Pin the named categories and scale the rest to fill what is left."""
    pinned = sum(canon.values())
    if pinned >= 0.999:
        out = {k: 0.0 for k in KEYS}
        out.update({k: v / pinned for k, v in canon.items()})
        return out
    rest_keys = [k for k in KEYS if k not in canon]
    rest_total = sum(basket.get(k, 0.0) for k in rest_keys)
    out = {}
    for k in KEYS:
        if k in canon:
            out[k] = canon[k]
        else:
            out[k] = (basket.get(k, 0.0) / rest_total * (1.0 - pinned)) if rest_total > 0 else 0.0
    return out


def _interp(profiles, gdp_pc):
    x = math.log(max(gdp_pc, 1.0))
    pts = [(math.log(g), p) for g, p in profiles]
    if x <= pts[0][0]:
        return dict(pts[0][1])
    if x >= pts[-1][0]:
        return dict(pts[-1][1])
    for (x0, p0), (x1, p1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return {k: p0[k] + (p1[k] - p0[k]) * t for k in p0}
    return dict(pts[-1][1])


def _norm(d, keys):
    s = sum(max(d.get(k, 0.0), 0.0) for k in keys)
    return {k: (max(d.get(k, 0.0), 0.0) / s if s > 0 else 0.0) for k in keys}


def _sharpen_to_top(shares, target_top):
    """
    Raise every share to a power p and renormalise until the largest share hits
    the target. Sharpening raises concentration; p < 1 flattens it. Bisection.
    """
    keys = [k for k, v in shares.items() if v > 0]
    if len(keys) < 2:
        return shares
    def top_at(p):
        raw = {k: shares[k] ** p for k in keys}
        s = sum(raw.values())
        return max(raw.values()) / s, {k: v / s for k, v in raw.items()}
    lo, hi = 0.25, 6.0
    cur, _ = top_at(1.0)
    if abs(cur - target_top) < 0.01:
        return shares
    for _ in range(40):
        mid = (lo + hi) / 2
        t, _ = top_at(mid)
        if t < target_top:
            lo = mid
        else:
            hi = mid
    _, out = top_at((lo + hi) / 2)
    for k in shares:
        out.setdefault(k, 0.0)
    return out


# A country hosting a leading financial centre earns from finance far beyond
# what its income implies. Scaled so the top centre's host gains roughly the
# lift the GFCI page's ranking implies, and countries with no centre are
# untouched.
GFCI_LIFT = 2.6


def default_basket(r, commodity_value, world_commodity_trade, evidence,
                   finance_weight=0.0):
    """
    r: a model row after run() has set dom_goods_x, svc_x, gdp_pc, cargo_*,
       top_export_share, coast_km, is_island, resource_concentration.
    commodity_value: {commodity: weighted share} for this country.
    Returns {category: share of DOMESTIC exports (goods DVA + services)}, sum 1.
    """
    goods_total = max(r["dom_goods_x"], 0.0)
    svc_total = max(r["svc_x"], 0.0)
    total = goods_total + svc_total
    if total <= 0:
        return {k: 0.0 for k in KEYS}

    # ---- goods: resource categories from production ----------------------
    res = {k: 0.0 for k in RESOURCE}
    manuf_from_production = {}
    for commodity, w in commodity_value.items():
        cat = COMMODITY_CATEGORY.get(commodity)
        if not cat:
            continue
        value = w * world_commodity_trade
        if cat in res:
            res[cat] += value
        else:
            manuf_from_production[cat] = manuf_from_production.get(cat, 0.0) + value
    res_value = sum(res.values())
    res_frac = (min(resource_ceiling(r.get("resource_concentration", 0.0)),
                    res_value / goods_total) if goods_total else 0.0)
    res_share = _norm(res, RESOURCE) if res_value > 0 else {k: 0.0 for k in RESOURCE}

    # ---- goods: everything else by income ----------------------------------
    manuf = _interp(INCOME_PROFILES, r["gdp_pc"])
    # CONTAINER THROUGHPUT IS A MANUFACTURING SIGNAL. Income alone cannot tell a
    # manufacturing giant from a rich farming economy: at Dahe's income the
    # profile hands it 17% food, when a country running the world's largest
    # container port and half its coal ships machinery and electronics, not
    # crops (China at the same income: 26% electronics, 17% machinery, 3% food).
    # cargo_concentration is share of world throughput over share of world GDP,
    # so above 1.0 weight moves from farm produce and textiles into the
    # container-borne categories, with diminishing returns.
    # A big port only implies factories when the cargo is the country's OWN.
    # cargo_concentration counts everything crossing the quay, so a transit hub
    # or a transshipment island scored as a manufacturing power on freight that
    # never enters its economy. Scaling by the domestic share of throughput
    # leaves Dahe's signal intact and removes it from the gateways, and the
    # TRANSIT hubs named in canon are protected explicitly.
    cc = r.get("cargo_concentration", 0.0)
    _own = r.get("cargo_own", 0.0)
    _all = _own + r.get("cargo_carried", 0.0) + r.get("cargo_stopover", 0.0) + r.get("cargo_canal", 0.0)
    domestic_share = (_own / _all) if _all > 0 else 1.0
    cc *= domestic_share
    if cc > 1.0:
        shift = min(0.70, 0.42 * math.log(cc))
        moved = 0.0
        for k in ("agri_food", "forestry_paper", "textiles"):
            take = manuf.get(k, 0.0) * shift
            manuf[k] = manuf.get(k, 0.0) - take
            moved += take
        for k, w in (("machinery", .30), ("electronics", .32), ("vehicles", .22), ("other_manuf", .16)):
            manuf[k] = manuf.get(k, 0.0) + moved * w
    manuf = _norm(manuf, MANUF)

    # PRODUCTION-BACKED MANUFACTURING IS RESERVED, NOT AVERAGED IN.
    #
    # What a country actually builds used to be added to its income profile and
    # then normalised across every category, which diluted the one number that
    # had been measured. Pelugrotoa builds 27% of the world's motor vehicles and
    # came out at 13% vehicles - below Areoix Lie, which builds 5% and came out
    # at 16%. Resource output has always had its value reserved before the
    # profile fills the rest; the manufactured commodities in the production
    # tables, motor vehicles and paper, now get the same treatment.
    avail = max(0.0, 1.0 - res_frac)
    prod_frac, prod_share = 0.0, {}
    if manuf_from_production and goods_total > 0:
        pv = sum(v for k, v in manuf_from_production.items() if k in MANUF)
        if pv > 0:
            prod_frac = min(pv / goods_total, avail * 0.80)
            prod_share = {k: v / pv for k, v in manuf_from_production.items() if k in MANUF}

    goods = {}
    for k in RESOURCE:
        goods[k] = res_frac * res_share[k]
    for k in MANUF:
        goods[k] = (avail - prod_frac) * manuf[k] + prod_frac * prod_share.get(k, 0.0)

    # ---- services -----------------------------------------------------------
    svc = _interp(SERVICE_PROFILES, r["gdp_pc"])
    # Two service lines are computed in money before the profile is asked:
    # transit earnings (stopover fees, canal tolls) are transport by
    # construction, and tourism receipts come from the receipts model in
    # build_trade_model (sun, coast, islands, nearness to rich markets). Both
    # are booked first, and the income profile fills only what is left.
    booked = {}
    if svc_total:
        passing = r.get("cargo_stopover", 0.0) + r.get("cargo_canal", 0.0) + r.get("cargo_carried", 0.0)
        if r.get("cargo_own", 0.0) + passing > 0 and r.get("svc_transit", 0.0) > 0:
            booked["transport"] = min(0.95, r.get("svc_transit", 0.0) / svc_total)
        if r.get("tourism_x", 0.0) > 0:
            booked["tourism"] = min(0.90, r["tourism_x"] / svc_total)
        tot_b = sum(booked.values())
        if tot_b > 0.95:
            booked = {k: v * 0.95 / tot_b for k, v in booked.items()}
    small_island = r.get("is_island") and (r.get("population") or 0) < ISLAND_MAX_POP
    if "tourism" not in booked:
        # no receipts model output (a backcast year): the old geography lifts
        if small_island:
            svc["tourism"] *= ISLAND_TOURISM_LIFT
        elif r.get("is_island"):
            svc["tourism"] *= 1.6
        elif r.get("coast_km", 0) > 1500:
            svc["tourism"] *= 1.2
        elif r.get("landlocked"):
            svc["tourism"] *= 0.7
    if r.get("landlocked"):
        svc["transport"] *= 0.75

    def _fill(svc_):
        """
        Booked money first, the profile fills the rest. Tourism, when booked,
        is exact. Transit is booked ON TOP of the profile's transport share,
        not instead of it: a country with ports but no transit income still
        ships and flies its own goods. (A first version booked transport at
        zero for exactly those countries, and Dahe lost its transport line.)
        """
        free = 1.0 - sum(booked.values())
        rest = [k for k in SERVICES if not (k == "tourism" and "tourism" in booked)]
        rt = sum(svc_[k] for k in rest) or 1.0
        out = {k: svc_[k] / rt * free if k in rest else 0.0 for k in SERVICES}
        for k, v in booked.items():
            out[k] = out.get(k, 0.0) + v if k != "tourism" else v
        return out
    if finance_weight > 0:
        svc["finance_business"] *= 1.0 + GFCI_LIFT * finance_weight
    svc = _fill(svc)

    # ---- forests (FOREST_CANON) ----------------------------------------------
    fc = FOREST_CANON.get(r["name"])
    if fc and goods.get("forestry_paper", 0.0) > 0:
        # a forest is an endowment, not a monoculture: never lift forestry
        # past FOREST_MAX of goods (Ucrua went to 60% of exports on 2.2x)
        cur = goods["forestry_paper"] / (sum(goods.values()) or 1.0)
        lift = min(FOREST_LIFT[fc], max(1.0, FOREST_MAX / max(cur, 1e-9)))
        goods["forestry_paper"] *= lift
        goods = _norm(goods, GOODS)

    # ---- wiki flavour, bounded ----------------------------------------------
    ev = evidence or {}
    if ev:
        for k in KEYS:
            h = ev.get(k, 0)
            if h:
                lift = min(FLAVOUR_CAP, 1.0 + FLAVOUR * math.log1p(h))
                if k in goods:
                    goods[k] *= lift
                elif k not in booked:
                    svc[k] *= lift
        goods = _norm(goods, GOODS)
        svc = _fill(svc)

    # ---- concentration to the Earth-realistic target -----------------------
    gs = goods_total / total
    if small_island:
        gs = min(gs, 1.0 - ISLAND_SERVICES_FLOOR)
    basket = {}
    for k in GOODS:
        basket[k] = goods[k] * gs
    for k in SERVICES:
        basket[k] = svc[k] * (1 - gs)
    canon = CANON_BASKETS.get(r["name"])
    if canon:
        return _norm(apply_canon(_norm(basket, KEYS), canon), KEYS)

    # SHARPEN WITHIN THE GOODS BLOCK ONLY, then reassemble.
    #
    # Sharpening is a power transform, and a power transform does not preserve a
    # partition: applied to all fifteen categories at once it silently moved mass
    # between goods and services, overwriting the services share the model had
    # just computed from income, resource concentration and port throughput.
    # It contradicted the model's own published svc_x column for 75 of 172
    # countries and mislabelled 5.6T lahn of world services as goods; three
    # countries came out with a basket that was ~100% goods beside a non-zero
    # services export figure. It also cut straight through the small-island
    # services floor set moments earlier, dropping 9 of 24 islands below it.
    #
    # Concentration is a statement about a country's PRODUCTS, so it belongs
    # inside the goods block. The target is expressed relative to that block,
    # because a top share of 0.45 of all exports is 0.45/gs of the goods alone.
    target = max(0.08, min(0.90, r.get("top_export_share", 0.3)))
    target = min(target, resource_ceiling(r.get("resource_concentration", 0.0)))
    if gs > 1e-9:
        goods_only = _norm({k: basket[k] for k in GOODS}, GOODS)
        tgt = max(0.08, min(0.97, target / gs))
        top_key = max(goods_only, key=goods_only.get)
        if top_key in RESOURCE:
            # a petrostate or a mining economy: the ceiling logic is exactly
            # what this sharpen encodes, so the whole goods basket takes it
            goods_only = _sharpen_to_top(goods_only, tgt)
        else:
            # RESOURCE SHARES ARE DATA AND ARE NOT SHARPENED AWAY. The sharpen
            # raises every share to a power, which crushes a small one far
            # more than proportionally: Dahe's resources were set at 18.4% of
            # goods from its 47% of world aluminium, 50% of lead and 53% of
            # coal, then came out at 2.8% with its gold and platinum zeroed,
            # because electronics was being pushed to 35% over them. Only the
            # manufactured block is sharpened now; the resource block keeps the
            # share the production tables gave it.
            res_sum = sum(goods_only[k] for k in RESOURCE)
            manuf_only = _norm({k: goods_only[k] for k in MANUF}, MANUF)
            manuf_only = _sharpen_to_top(
                manuf_only, max(0.08, min(0.97, tgt / max(1e-9, 1.0 - res_sum))))
            for k in MANUF:
                goods_only[k] = manuf_only[k] * (1.0 - res_sum)
        for k in GOODS:
            basket[k] = goods_only[k] * gs
    return _norm(basket, KEYS)


# How far a category's demand can be suppressed by exporting it.
#
# Manufactures and farm produce hold thousands of distinguishable products, so
# exporting them heavily never removes the need to buy them: a car-maker still
# buys cars, a wheat exporter still buys food. The 0.15 floor is what keeps
# those importable.
#
# Extracted commodities do not behave that way. A country shipping half its
# exports as crude has no use for anyone else's crude, and on Earth the large
# producers - Saudi Arabia, Russia, Iraq, Kuwait, Nigeria - import essentially
# none. Holding them to the same floor left 16% of the world's crude landing in
# countries that were themselves over 40% oil exporters, and made Ahokini and
# Verste, 50% and 51% oil and 1,111 km apart, each other's largest partner.
#
# REFINED FUELS ARE DELIBERATELY ABSENT from this set. Exporting crude while
# importing petrol is exactly what a producer without refineries does, and that
# trade is real; it is crude-for-crude that is not.
EXTRACTIVE_FLOOR = {"crude_oil_gas": 0.02, "ores_metals": 0.07, "precious": 0.07}
EXTRACTIVE_SLOPE = 4.5


def import_demand(basket, world_mix):
    """
    What a country buys, as shares. You import less of what you export heavily,
    and the rest follows the world's mix. How much less depends on whether the
    category is something a country can be self-sufficient in: see the floors
    above. The steeper slope puts the turn at about 22% of exports, so a country
    whose oil is a minority of what it sells still buys crude the way the United
    States does, while one above that line stops, as Saudi Arabia does.
    """
    d = {}
    for k in KEYS:
        share = basket.get(k, 0.0)
        floor = EXTRACTIVE_FLOOR.get(k)
        if floor is None:
            need = max(0.15, 1.0 - 2.2 * share)
        else:
            need = max(floor, 1.0 - EXTRACTIVE_SLOPE * share)
        d[k] = world_mix.get(k, 0.0) * need
    return _norm(d, KEYS)


# ---------------------------------------------------------------------------
# intermediate goods: what a country has to buy in order to sell
# ---------------------------------------------------------------------------
#
# Until this layer existed, 167 of the 172 countries had a domestic value added
# of exactly 100%: every export was treated as if the country had made it out of
# nothing. Nobody on Earth is at 100%. Roughly 70% of world trade is intermediate
# goods, and the OECD's value-added figures put China at 83%, Germany 73%, Korea
# 63%, Mexico 55% and Singapore 42%.
#
# FOREIGN_CONTENT is the share of a category's gross output that is imported
# inputs, for a mid-size economy. It is low where the value comes out of the
# ground and high where the work is assembly: refined fuels sit at the top
# because a refinery's main input is somebody else's crude, which is the one
# processing chain the category list already implies but the model never linked.
FOREIGN_CONTENT = {
    "crude_oil_gas":    0.05,
    "ores_metals":      0.09,
    "precious":         0.10,
    "agri_food":        0.13,
    "forestry_paper":   0.16,
    "refined_fuels":    0.55,
    "textiles":         0.34,
    "chemicals":        0.30,
    "machinery":        0.28,
    "electronics":      0.42,
    "vehicles":         0.38,
    "other_manuf":      0.30,
    "transport":        0.22,
    "tourism":          0.14,
    "finance_business": 0.09,
}

# What each category consumes, as shares of its imported inputs. This is a
# deliberately coarse input-output table: enough to say that a car plant buys
# steel, chips and plastics while a refinery buys crude, which is what decides
# whether a country's suppliers differ from its customers.
INPUT_MIX = {
    "crude_oil_gas":    {"machinery": .60, "refined_fuels": .40},
    "ores_metals":      {"refined_fuels": .40, "machinery": .35, "chemicals": .25},
    "precious":         {"machinery": .50, "chemicals": .30, "refined_fuels": .20},
    "agri_food":        {"agri_food": .50, "chemicals": .30, "refined_fuels": .20},
    "forestry_paper":   {"forestry_paper": .60, "chemicals": .40},
    "refined_fuels":    {"crude_oil_gas": .85, "chemicals": .15},
    "textiles":         {"agri_food": .35, "textiles": .35, "chemicals": .30},
    "chemicals":        {"crude_oil_gas": .45, "chemicals": .40, "ores_metals": .15},
    "machinery":        {"ores_metals": .30, "machinery": .25, "other_manuf": .20,
                         "electronics": .15, "chemicals": .10},
    "electronics":      {"electronics": .45, "other_manuf": .15, "ores_metals": .15,
                         "chemicals": .15, "machinery": .10},
    "vehicles":         {"machinery": .25, "other_manuf": .20, "ores_metals": .20,
                         "electronics": .20, "chemicals": .15},
    "other_manuf":      {"other_manuf": .40, "ores_metals": .25, "chemicals": .20,
                         "forestry_paper": .15},
    "transport":        {"refined_fuels": .70, "machinery": .30},
    "tourism":          {"agri_food": .50, "refined_fuels": .30, "other_manuf": .20},
    "finance_business": {"electronics": .50, "other_manuf": .30, "finance_business": .20},
}


def size_factor(gdp, median_gdp):
    """
    Small economies buy more of their inputs abroad, because they cannot make
    everything themselves: Singapore's exports are 58% foreign value, the United
    States' about 12%. Gentle exponent, hard clips, so the effect is a tilt and
    never a cliff.
    """
    if gdp <= 0 or median_gdp <= 0:
        return 1.0
    return max(0.65, min(1.5, (median_gdp / gdp) ** 0.055))


def foreign_content(basket, mult=1.0):
    """Share of a country's gross exports that is imported inputs."""
    fc = sum(basket.get(k, 0.0) * FOREIGN_CONTENT.get(k, 0.2) for k in KEYS)
    return max(0.0, min(0.75, fc * mult))


def intermediate_mix(basket, mult=1.0):
    """
    The categories a country must import BECAUSE OF WHAT IT EXPORTS, as shares.

    This is the half of import demand that consumption cannot explain. A country
    that assembles electronics buys components, metals and plastics whoever its
    shoppers are, and that is why its suppliers are not the same countries as its
    customers.
    """
    need = {k: 0.0 for k in KEYS}
    for k in KEYS:
        v = basket.get(k, 0.0) * FOREIGN_CONTENT.get(k, 0.2) * mult
        if v <= 0:
            continue
        for j, w in INPUT_MIX.get(k, {}).items():
            need[j] += v * w
    return _norm(need, KEYS)


def blended_demand(basket, world_mix, domestic_x, total_m, mult=1.0):
    """
    Import demand as the sum of two different appetites: intermediates, set by
    what the country makes, and final goods, set by what it consumes.
    """
    fc = foreign_content(basket, mult)
    inter_value = min(max(domestic_x, 0.0) * fc, max(total_m, 0.0) * 0.85)
    final_value = max(total_m - inter_value, 0.0)
    if inter_value <= 0 or total_m <= 0:
        return import_demand(basket, world_mix), fc
    inter = intermediate_mix(basket, mult)
    final = import_demand(basket, world_mix)
    tot = inter_value + final_value
    out = {k: (inter.get(k, 0.0) * inter_value + final.get(k, 0.0) * final_value) / tot
           for k in KEYS}
    return _norm(out, KEYS), fc


def complementarity(basket_i, demand_j, world_mix):
    """
    How well i's exports match j's imports, relative to a generic exporter with
    the world's own basket. 1.0 = no better than average; 2.0 = twice as well
    matched. This is what lets oil cross an ocean to reach an industrial buyer.
    """
    num = sum(basket_i.get(k, 0.0) * demand_j.get(k, 0.0) for k in KEYS)
    den = sum(world_mix.get(k, 0.0) * demand_j.get(k, 0.0) for k in KEYS)
    return num / den if den > 0 else 1.0


# ---------------------------------------------------------------------------
# read-back of hand edits
# ---------------------------------------------------------------------------

def _cell_number(v):
    """
    A green cell's value, or None if it is blank, or the string itself if it is
    something that cannot be a percentage.

    Excel does not always hand back a float. A percentage typed as text, pasted
    with a thousands separator or a stray %, or a formula in a file saved with
    calculation set to manual, all arrive as strings or None. Coercing those to
    0.0 was silent data loss of the worst kind: the zero differed from the
    default, so the row was committed as a deliberate edit with that category at
    nothing, and the next build wrote the zero back over the cell DJ had typed.
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("%", "").replace(",", "").replace(" ", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return str(v)


def read_edited_baskets(path):
    """
    Return {country: basket} for rows the user has changed, by comparing the
    editable sheet against the stored model-default sheet. A row counts as edited
    when any category differs by more than half a percentage point.

    A blank cell means "use the model's default for this category", not zero,
    so a row can be partly hand-set. Anything that is neither blank nor a number
    stops the build by name rather than being guessed at.
    """
    if not os.path.exists(path):
        return {}, {}
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        # NEVER swallow this. The build that follows rewrites the workbook, so a
        # silent empty return here would discard every hand edit and then
        # overwrite the only copy of them.
        raise SystemExit(
            f"Could not read {os.path.basename(path)} to recover your edits: {exc}\n"
            f"The build would overwrite the workbook, so it has stopped instead. "
            f"Close the file in Excel, or fix it, and re-run.")
    if "Export baskets" not in wb.sheetnames or "Export baskets (model default)" not in wb.sheetnames:
        wb.close()
        return {}, {}

    def sheet_rows(ws):
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return {}
        hdr = [str(x).strip() if x else "" for x in rows[0]]
        col = {}
        for i, h in enumerate(hdr):
            for k in KEYS:
                if h == LABEL[k] or h == k:
                    col[k] = i
        out, bad = {}, []
        for r in rows[1:]:
            if not r or not r[0]:
                continue
            name = str(r[0]).strip()
            vals = {}
            for k, i in col.items():
                v = _cell_number(r[i] if i < len(r) else None)
                if isinstance(v, str):
                    bad.append((name, LABEL[k], v))
                    continue
                vals[k] = v          # float, or None meaning "use the default"
            if vals:
                out[name] = vals
        return out, bad

    edited_sheet, bad_cells = sheet_rows(wb["Export baskets"])
    default_sheet, _ = sheet_rows(wb["Export baskets (model default)"])
    wb.close()

    if bad_cells:
        lines = "\n".join(f"    {c:<18}{col:<34}{v!r}" for c, col, v in bad_cells[:12])
        raise SystemExit(
            f"{len(bad_cells)} cell(s) in the Export baskets sheet are not numbers:\n{lines}\n"
            f"Enter a plain number (45, not '45%' or text), or clear the cell to take "
            f"the model's default. The build has stopped rather than read them as zero.")

    edited, reasons = {}, {}
    for name, vals in edited_sheet.items():
        base = default_sheet.get(name)
        if not base:
            continue
        # A blank cell inherits the default rather than meaning zero, so a row
        # can be part hand-set: change one category and the rest hold.
        merged = {k: (vals.get(k) if vals.get(k) is not None else base.get(k) or 0.0)
                  for k in KEYS}
        diff = {k: abs(merged[k] - (base.get(k) or 0.0)) for k in KEYS}
        worst = max(diff.values()) if diff else 0.0
        if worst > 0.5:
            total = sum(max(merged[k], 0.0) for k in KEYS)
            if total > 0:
                edited[name] = {k: max(merged[k], 0.0) / total for k in KEYS}
                reasons[name] = f"{sum(1 for v in diff.values() if v > 0.5)} categories changed, largest {worst:.1f}pp"
    return edited, reasons


def read_reach(path):
    """
    {country: global reach} for rows the user has CHANGED, from the Global reach
    sheet. The sheet stores the editable value in column B and the model's own
    default in column C, and only a row where the two differ counts as hand-set.
    Returning every row would flag all 172 countries as edited on every re-run,
    which is exactly what the first version did.
    """
    if not os.path.exists(path):
        return {}
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return {}
    out = {}
    if "Global reach" in wb.sheetnames:
        for r in wb["Global reach"].iter_rows(min_row=2, values_only=True):
            if not r or not r[0] or len(r) < 3:
                continue
            val, default = r[1], r[2]
            if (isinstance(val, (int, float)) and val > 0
                    and isinstance(default, (int, float))
                    and abs(float(val) - float(default)) > 1e-6):
                out[str(r[0]).strip()] = float(val)
    wb.close()
    return out
