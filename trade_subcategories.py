#!/usr/bin/env python3
"""
trade_subcategories.py - the 15 categories split into ~150 traded products.

WHERE THE NUMBERS COME FROM, and where they do not.

  The 15-category basket is derived: production tables, an income profile, wiki
  vocabulary and DJ's canon all feed it. Below that level his data mostly stops.
  There is nothing in Andah that says whether a country's electronics are
  semiconductors or wiring looms, so inventing a per-country answer would be
  exactly the guessing he has told me I am bad at.

  Instead each parent category carries a LOW-INCOME and a HIGH-INCOME profile of
  its products, taken from real 2015 trade structure, and a country sits between
  them on GDP per capita. A poor country's electronics come out as assembly and
  cable; a rich one's as chips and instruments. This is the same mechanism the
  15-category basket already uses one level up, so it introduces no new kind of
  assumption - only more of an existing one.

  ONE CATEGORY IS REAL DATA RATHER THAN A PROFILE. Crude oil and natural gas
  splits on DJ's own Oil and Natural Gas production tables, per country, so a
  gas producer reads as a gas producer instead of inheriting an average.

  NO BILATERAL FLOWS. Sub-categories divide what a country sells, not who buys
  it: partners stay answered at the 15-category level, where the model actually
  solves a matrix. A sub-category share is a share of its parent, and the parent
  is what carries the trade.
"""

import trade_baskets as tb

# (key, label, (share when poor, share when rich)) within the parent.
# Shares are relative weights; they are normalised, so they need not sum to 1.
SUBS = {
    "crude_oil_gas": [
        ("crude_petroleum",   "Crude petroleum",              (.72, .60)),
        ("natural_gas",       "Natural gas",                  (.14, .22)),
        ("lng",               "Liquefied natural gas",        (.06, .11)),
        ("petroleum_gases",   "Petroleum gases and LPG",      (.06, .05)),
        ("condensates",       "Gas condensates",              (.02, .02)),
    ],
    "refined_fuels": [
        ("motor_spirit",      "Motor spirit and petrol",      (.20, .22)),
        ("diesel",            "Diesel and gas oils",          (.24, .24)),
        ("jet_fuel",          "Aviation fuel",                (.07, .11)),
        ("fuel_oil",          "Heavy fuel oil",               (.14, .09)),
        ("coal",              "Coal and briquettes",          (.24, .13)),
        ("coke",              "Coke and semi-coke",           (.07, .07)),
        ("nuclear_fuel",      "Uranium and nuclear fuel",     (.04, .14)),
    ],
    "ores_metals": [
        ("iron_ore",          "Iron ore",                     (.17, .11)),
        ("copper_ore",        "Copper ore",                   (.12, .08)),
        ("refined_copper",    "Refined copper",               (.07, .10)),
        ("bauxite_alumina",   "Bauxite and alumina",          (.07, .04)),
        ("aluminium",         "Aluminium",                    (.06, .11)),
        ("nickel",            "Nickel",                       (.05, .05)),
        ("zinc",              "Zinc",                         (.04, .04)),
        ("lead",              "Lead",                         (.03, .02)),
        ("tin",               "Tin",                          (.02, .02)),
        ("lithium",           "Lithium",                      (.02, .03)),
        ("manganese",         "Manganese",                    (.03, .02)),
        ("chromium",          "Chromium and ferroalloys",     (.04, .04)),
        ("titanium_ore",      "Titanium minerals",            (.02, .02)),
        ("cobalt",            "Cobalt",                       (.02, .02)),
        ("rare_earths",       "Rare earth elements",          (.01, .03)),
        ("iron_steel",        "Iron and steel",               (.13, .18)),
        ("steel_products",    "Steel bars, sheet and tube",   (.06, .07)),
        ("industrial_mineral", "Salt, bentonite and industrial minerals", (.04, .02)),
    ],
    "precious": [
        ("gold",              "Gold",                         (.44, .38)),
        ("silver",            "Silver",                       (.10, .09)),
        ("platinum",          "Platinum",                     (.11, .10)),
        ("palladium",         "Palladium",                    (.06, .07)),
        ("rough_diamond",     "Rough diamonds",               (.16, .08)),
        ("cut_gems",          "Cut diamonds and gemstones",   (.08, .16)),
        ("jewellery",         "Jewellery and goldsmiths' wares", (.05, .12)),
    ],
    "agri_food": [
        ("wheat",             "Wheat",                        (.045, .03)),
        ("maize",             "Maize",                        (.08, .06)),
        ("rice",              "Rice",                         (.07, .03)),
        ("soya",              "Soya beans",                   (.07, .05)),
        ("other_cereals",     "Other cereals",                (.03, .02)),
        ("beef",              "Beef",                         (.05, .07)),
        ("pork",              "Pork",                         (.03, .05)),
        ("poultry",           "Poultry",                      (.04, .04)),
        ("dairy",             "Milk, cheese and butter",      (.04, .09)),
        ("fish",              "Fish",                         (.07, .06)),
        ("crustaceans",       "Crustaceans and molluscs",     (.05, .04)),
        ("fruit",             "Fruit",                        (.08, .06)),
        ("vegetables",        "Vegetables",                   (.05, .04)),
        ("coffee",            "Coffee",                       (.05, .02)),
        ("tea_spices",        "Tea and spices",               (.03, .01)),
        ("cocoa",             "Cocoa",                        (.04, .01)),
        ("sugar",             "Sugar and confectionery",      (.04, .03)),
        ("oils_fats",         "Vegetable oils and fats",      (.05, .04)),
        ("animal_feed",       "Animal feed",                  (.03, .05)),
        ("beverages",         "Beverages and spirits",        (.03, .12)),
        ("tobacco",           "Tobacco",                      (.03, .03)),
    ],
    "forestry_paper": [
        ("logs",              "Logs and rough wood",          (.22, .10)),
        ("sawn_timber",       "Sawn timber",                  (.20, .16)),
        ("wood_panels",       "Plywood and wood panels",      (.15, .13)),
        ("pulp",              "Wood pulp",                    (.16, .17)),
        ("paper",             "Paper and paperboard",         (.15, .28)),
        ("packaging",         "Paper packaging",              (.07, .11)),
        ("natural_fibres",    "Cork and natural fibres",      (.05, .05)),
    ],
    "textiles": [
        ("cotton",            "Raw cotton",                   (.10, .03)),
        ("wool",              "Wool and animal hair",         (.04, .02)),
        ("synthetic_fibre",   "Synthetic fibres",             (.08, .09)),
        ("yarn",              "Yarn and thread",              (.10, .07)),
        ("woven_fabric",      "Woven fabric",                 (.13, .10)),
        ("knit_fabric",       "Knitted fabric",               (.07, .06)),
        ("knitwear",          "Knitted garments",             (.16, .14)),
        ("outerwear",         "Woven garments and outerwear", (.15, .16)),
        ("footwear",          "Footwear",                     (.09, .13)),
        ("leather",           "Leather and hides",            (.04, .06)),
        ("home_textiles",     "Carpets and home textiles",    (.04, .14)),
    ],
    "chemicals": [
        ("pharmaceuticals",   "Pharmaceuticals",              (.14, .42)),
        ("medical_supplies",  "Vaccines, blood and reagents", (.03, .07)),
        ("organic_chem",      "Organic chemicals",            (.17, .14)),
        ("inorganic_chem",    "Inorganic chemicals",          (.10, .05)),
        ("fertiliser",        "Fertilisers",                  (.15, .05)),
        ("plastics_primary",  "Plastics in primary form",     (.16, .13)),
        ("plastic_articles",  "Plastic articles",             (.10, .09)),
        ("rubber",            "Rubber and rubber articles",   (.07, .05)),
        ("paints",            "Paints, inks and dyes",        (.04, .04)),
        ("cosmetics",         "Cosmetics and perfumes",       (.04, .06)),
        ("soaps",             "Soaps and detergents",         (.03, .02)),
        ("industrial_gases",  "Industrial gases",             (.02, .02)),
    ],
    "machinery": [
        ("engines",           "Engines and motors",           (.09, .10)),
        ("turbines",          "Turbines and generating sets", (.05, .07)),
        ("pumps",             "Pumps and compressors",        (.08, .08)),
        ("valves_bearings",   "Valves, bearings and gearing", (.07, .09)),
        ("agri_machinery",    "Agricultural machinery",       (.07, .05)),
        ("construction_mach", "Construction and earthmoving", (.09, .08)),
        ("mining_mach",       "Mining and drilling machinery", (.06, .05)),
        ("machine_tools",     "Machine tools",                (.07, .09)),
        ("textile_mach",      "Textile machinery",            (.04, .03)),
        ("food_mach",         "Food processing machinery",    (.04, .03)),
        ("printing_mach",     "Printing and paper machinery", (.03, .03)),
        ("hvac",              "Heating, cooling and refrigeration", (.09, .08)),
        ("lifting",           "Cranes and lifting equipment", (.06, .05)),
        ("robots",            "Industrial robots and automation", (.02, .06)),
        ("moulds",            "Moulds and tooling",           (.05, .05)),
        ("other_machinery",   "Other industrial machinery",   (.09, .06)),
    ],
    "electronics": [
        ("semiconductors",    "Semiconductors",               (.02, .05)),
        ("integrated_circuits", "Integrated circuits",        (.10, .22)),
        ("computers",         "Computers",                    (.14, .12)),
        ("computer_parts",    "Computer parts and storage",   (.09, .08)),
        ("telephones",        "Telephones and handsets",      (.18, .15)),
        ("telecom_equip",     "Telecommunications equipment", (.08, .07)),
        ("broadcasting",      "Broadcasting and video equipment", (.07, .04)),
        ("displays",          "Displays and panels",          (.06, .05)),
        ("consumer_av",       "Consumer audio and video",     (.07, .03)),
        ("batteries",         "Batteries and accumulators",   (.04, .04)),
        ("insulated_wire",    "Insulated wire and cable",     (.07, .04)),
        ("transformers",      "Transformers and switchgear",  (.05, .05)),
        ("electric_motors",   "Electric motors",              (.03, .03)),
        ("lighting_electric", "Electric lighting",            (.03, .02)),
        ("measuring",         "Measuring and testing instruments", (.03, .08)),
        ("optical",           "Optical instruments and lenses", (.02, .04)),
        ("medical_devices",   "Medical and surgical devices", (.03, .09)),
    ],
    "vehicles": [
        ("cars",              "Cars",                         (.30, .34)),
        ("commercial_veh",    "Vans and lorries",             (.12, .10)),
        ("buses",             "Buses and coaches",            (.04, .03)),
        ("vehicle_parts",     "Vehicle parts",                (.20, .21)),
        ("motorcycles",       "Motorcycles",                  (.05, .03)),
        ("bicycles",          "Bicycles",                     (.03, .02)),
        ("trailers",          "Trailers and semi-trailers",   (.03, .03)),
        ("ships",             "Ships and tankers",            (.10, .07)),
        ("boats",             "Boats and yachts",             (.02, .03)),
        ("aircraft",          "Aircraft",                     (.05, .09)),
        ("aircraft_parts",    "Aircraft parts",               (.03, .04)),
        ("rail_stock",        "Railway rolling stock",        (.03, .02)),
    ],
    "other_manuf": [
        ("furniture",         "Furniture",                    (.16, .15)),
        ("toys_games",        "Toys and games",               (.09, .07)),
        ("sports_goods",      "Sporting goods",               (.05, .05)),
        ("glass",             "Glass and glassware",          (.08, .08)),
        ("ceramics",          "Ceramics and tableware",       (.08, .06)),
        ("cement_stone",      "Cement, stone and abrasives",  (.10, .06)),
        ("hand_tools",        "Hand tools and cutlery",       (.07, .07)),
        ("hardware",          "Builders' hardware",           (.06, .06)),
        ("lighting_fixtures", "Lamps and lighting fixtures",  (.06, .05)),
        ("prefab",            "Prefabricated buildings",      (.03, .03)),
        ("printed_matter",    "Books and printed matter",     (.05, .06)),
        ("instruments_music", "Musical instruments",          (.01, .01)),
        ("watches",           "Watches and clocks",           (.02, .06)),
        ("arms",              "Arms and ammunition",          (.03, .05)),
        ("misc_manuf",        "Other manufactured articles",  (.11, .14)),
    ],
    "transport": [
        ("sea_freight",       "Sea freight",                  (.34, .26)),
        ("air_freight",       "Air freight",                  (.12, .16)),
        ("road_freight",      "Road freight",                 (.16, .15)),
        ("rail_freight",      "Rail freight",                 (.06, .05)),
        ("pipeline",          "Pipeline transport",           (.04, .03)),
        ("port_services",     "Port and terminal services",   (.13, .13)),
        ("warehousing",       "Warehousing and logistics",    (.09, .14)),
        ("postal_courier",    "Postal and courier services",  (.06, .08)),
    ],
    "tourism": [
        ("leisure_travel",    "Leisure travel",               (.62, .55)),
        ("business_travel",   "Business travel",              (.15, .22)),
        ("border_trips",      "Day trips and border shopping", (.08, .07)),
        ("education_travel",  "Education travel",             (.05, .08)),
        ("health_travel",     "Health travel",                (.05, .03)),
        ("cruise",            "Cruise and marine tourism",    (.05, .05)),
    ],
    "finance_business": [
        ("banking",           "Banking services",             (.18, .17)),
        ("insurance",         "Insurance",                    (.11, .11)),
        ("reinsurance",       "Reinsurance",                  (.04, .05)),
        ("asset_management",  "Investment and asset management", (.06, .12)),
        ("legal",             "Legal services",               (.06, .07)),
        ("accounting",        "Accounting and audit",         (.05, .05)),
        ("consulting",        "Management consulting",        (.06, .08)),
        ("advertising",       "Advertising and market research", (.05, .05)),
        ("it_services",       "IT services",                  (.13, .10)),
        ("software",          "Software and licensing",       (.07, .09)),
        ("randd",             "Research and development",     (.04, .06)),
        ("telecom_services",  "Telecommunications services",  (.09, .05)),
        ("construction_svc",  "Construction and engineering services", (.06, .04)),
    ],
}

KEYS = [(parent, key) for parent, subs in SUBS.items() for key, _, _ in subs]
LABEL = {key: label for subs in SUBS.values() for key, label, _ in subs}
PARENT = {key: parent for parent, subs in SUBS.items() for key, _, _ in subs}

LOW_INCOME = 12_000.0
HIGH_INCOME = 280_000.0

# WHY COUNTRIES DO NOT ALL TOP THE SAME PRODUCT. The income profile alone gave
# every country on Andah cars as its leading vehicle, engines as its leading
# machine and banking as its leading service - 100% of them, in seven of the
# fifteen categories. Real economies specialise: Japan in cars, Korea in ships,
# France in aircraft. Three things below pull the mix apart, none of them a
# guess about any particular country.
#
#  1. PRODUCTION. Every table DJ has that reaches a product tilts toward it,
#     scaled by how concentrated the country is in that commodity relative to
#     its size. Silicon reaches into electronics: Pelugrotoa makes 68.6% of the
#     world's silicon, so its electronics lean to semiconductors.
#  2. ENDOWMENTS. Cold coasts fish and cut timber, the tropics grow coffee and
#     cocoa, the landlocked ship by rail and build no ships, islands sell
#     cruises, oil states make petrochemicals, financial centres manage assets,
#     miners build mining machinery, big countries grow grain, populous ones
#     make consumer goods. All read off data the model already carries.
#  3. SIZE. Small economies concentrate and large ones diversify, so a small
#     country's mix is sharpened toward its few strongest products and a giant's
#     is left broad.
COMMODITY_PRODUCT = {
    "Oil": "crude_petroleum", "Natural Gas": "natural_gas",
    "Coal": "coal", "Uranium": "nuclear_fuel", "Thorium": "nuclear_fuel",
    "Iron": "iron_ore", "Copper": "copper_ore", "Aluminium": "aluminium",
    "Nickel": "nickel", "Zinc": "zinc", "Tin": "tin", "Lead": "lead",
    "Lithium": "lithium", "Manganese": "manganese", "Titanium": "titanium_ore",
    "Cobalt": "cobalt", "Chromium": "chromium", "Vanadium": "chromium",
    "Magnesium": "aluminium", "Niobium": "rare_earths", "Iridium": "rare_earths",
    "Silicon": "inorganic_chem",
    "Petrol": "motor_spirit", "Diesel": "diesel", "Jet fuel": "jet_fuel", "Fuel oil": "fuel_oil",
    "Salt": "industrial_mineral", "Bentonite": "industrial_mineral",
    "Feldspar": "industrial_mineral", "Fluorite": "industrial_mineral",
    "Bismuth": "industrial_mineral", "Mercury": "industrial_mineral",
    "Gold": "gold", "Silver": "silver", "Platinum": "platinum",
    "Palladium": "palladium", "Diamond": "rough_diamond",
    "Paper": "paper", "Motor vehicle": "cars",
}
PROD_K = 2.5          # strength of the production tilt
SIZE_K = 0.30         # sharpening per e-fold below the median economy
SIZE_MAX = 1.0

GAS_SPLIT = {"Oil": "crude_petroleum", "Natural Gas": "natural_gas"}


def endowment_tilts(ctx):
    """Multipliers on product weights from what the model knows about a country."""
    import collections
    import math
    t = collections.defaultdict(lambda: 1.0)

    def lift(keys, f):
        for k in keys:
            t[k] *= f
    lat = abs(ctx.get("lat", 0.0))
    if lat >= 45:
        lift(("fish", "crustaceans", "logs", "sawn_timber", "pulp", "wood_panels"), 1.7)
    if lat <= 22:
        lift(("coffee", "cocoa", "tea_spices", "sugar", "fruit", "oils_fats", "rice"), 2.4)
    if lat > 28:
        lift(("coffee", "cocoa", "tea_spices"), 0.12)
    if lat < 15:
        lift(("wheat", "other_cereals"), 0.4)
    elif lat <= 35:
        lift(("fruit", "vegetables", "beverages"), 1.3)
    if ctx.get("landlocked"):
        lift(("ships", "boats", "sea_freight", "port_services", "cruise", "fish", "crustaceans"), 0.12)
        lift(("rail_freight", "road_freight", "pipeline"), 1.8)
    else:
        cs = ctx.get("coast_share", 0.0)
        lift(("ships", "boats", "sea_freight", "port_services", "fish", "crustaceans"), 1.0 + 1.6 * cs)
    if ctx.get("is_island"):
        lift(("cruise", "leisure_travel", "fish", "boats"), 1.5)
    oil = ctx.get("oil_share", 0.0)
    if oil > 0.05:
        lift(("organic_chem", "plastics_primary", "fertiliser", "pipeline",
              "diesel", "motor_spirit", "fuel_oil"), 1.0 + 3.0 * oil)
    fw = ctx.get("finance_weight", 0.0)
    if fw > 0:
        lift(("asset_management", "reinsurance", "banking", "insurance"), 1.0 + 4.0 * fw)
    mine = ctx.get("mining_share", 0.0)
    if mine > 0.08:
        lift(("mining_mach", "iron_steel", "construction_mach"), 1.0 + 2.5 * mine)
    if ctx.get("area_km2", 0.0) > 1_500_000:
        lift(("wheat", "maize", "beef", "soya", "animal_feed", "other_cereals"), 1.6)
    pop = ctx.get("population", 0.0)
    if pop > 60e6:
        # Earth's consumer manufactures are made by its most populous
        # industrial economy, and by a wide margin: China holds 40% of world
        # telephone exports, 45% of computers, 70% of toys. A flat 1.35x could
        # never produce that; the lift now grows with population, so a
        # country of 900 million manufactures like one.
        import math as _m
        f = 1.0 + 0.75 * _m.log(pop / 60e6)
        lift(("telephones", "computers", "consumer_av", "knitwear", "outerwear",
              "furniture", "toys_games", "footwear", "sports_goods"), f)
    # The four categories no production table reaches - vehicles, other
    # manufactures, tourism, finance - came out with every country topping the
    # same product. These are the endowment signals that separate them on
    # Earth: shipyards on long coasts, aircraft in rich large economies, parts
    # plants at middle incomes, motorcycles in poor populous ones, cement where
    # there is mining, watches and arms in rich small states, IT services in
    # populous middle-income ones, cruises on islands, business travel where the
    # finance is.
    gpc = ctx.get("gdp_pc", 0.0)
    rich, mid, poor = gpc >= 120e3, 25e3 <= gpc < 120e3, gpc < 25e3
    big = ctx.get("gdp_share", 0.0) >= 0.02
    cs = ctx.get("coast_share", 0.0)
    if not ctx.get("landlocked"):
        lift(("boats", "cruise"), 1.0 + 2.0 * cs)
        yard = (min(1.0, ctx.get("ports", 0) / 2.0)
                * min(1.0, ctx.get("industry", 0.0) / 0.35)
                * min(1.0, ctx.get("gdp_share", 0.0) / 0.008))
        lift(("ships",), 0.10 + 9.0 * yard)
    else:
        lift(("ships",), 0.02)
    if rich and big:
        lift(("aircraft", "aircraft_parts"), 5.0)
    else:
        lift(("aircraft",), 0.15)
    if rich and not big:
        lift(("aircraft_parts", "watches", "arms", "printed_matter", "machine_tools", "robots"), 2.0)
    if mid:
        lift(("vehicle_parts", "glass", "ceramics", "construction_svc", "textile_mach"), 1.9)
        if pop > 40e6:
            lift(("it_services", "software"), 2.6)
    if poor:
        lift(("motorcycles", "bicycles", "telecom_services", "hand_tools"), 2.4)
        if pop > 40e6:
            lift(("it_services",), 1.6)
    if ctx.get("landlocked") or ctx.get("area_km2", 0.0) > 2_000_000:
        lift(("rail_stock", "rail_freight", "agri_machinery"), 1.9)
    mine = ctx.get("mining_share", 0.0)
    if mine > 0.08:
        lift(("cement_stone",), 1.0 + 3.0 * mine)
    if fw > 0:
        lift(("business_travel", "air_freight"), 1.0 + 3.0 * fw)
    if ctx.get("is_island"):
        lift(("cruise",), 1.4)     # was 2.2: small islands became cruise monocultures (Baluyde 30% of exports)
    # Travel. Sun and coast sell holidays; land borders sell day trips and
    # shopping runs (none for an island); universities sell degrees, so
    # education travel goes to the rich and the large; operations go to the
    # middle-income countries with good hospitals and low prices, and to the
    # very richest.
    a = abs(ctx.get("lat", 0.0))
    clim = 1.0 if 18 <= a <= 42 else (0.85 if a < 18 else max(0.3, 1.0 - (a - 42) / 25.0))
    lift(("leisure_travel",), 0.5 + 0.9 * clim * (0.5 + 0.5 * min(1.0, cs * 4.0)))
    nb = ctx.get("n_borders", 0)
    lift(("border_trips",), 0.15 + 0.45 * min(nb, 5))
    pcr = ctx.get("pc_rel", 1.0)
    lift(("education_travel",), min(3.0, max(0.3, pcr ** 0.6)) * (1.0 + 0.3 * max(0.0, math.log(max(pop, 1e6) / 20e6))))
    lift(("health_travel",), 1.7 if 0.25 <= pcr <= 0.9 else (1.3 if pcr > 2.0 else 0.6))
    # DJ: education travel follows the top-university list (Rovik Global
    # University Rankings); uni_points is the country's share of the top-25
    # points, 0 for a country with none
    up = ctx.get("uni_points", 0.0)
    lift(("education_travel",), 0.25 + 6.0 * up)
    return t


def _mix(subs, gdp_pc):
    """Interpolate each product between the poor and rich profile on log income."""
    import math
    lo, hi = math.log(LOW_INCOME), math.log(HIGH_INCOME)
    t = (math.log(max(gdp_pc, 1.0)) - lo) / (hi - lo)
    t = max(0.0, min(1.0, t))
    out = {k: a + (b - a) * t for k, _, (a, b) in subs}
    tot = sum(out.values()) or 1.0
    return {k: v / tot for k, v in out.items()}


# Within the four resource categories the product mix is DATA, not a profile.
# Each country's value in a commodity is its share of world output from the
# production tables times the model's commodity weight - the same numbers that
# built the category share one level up - mapped onto the product. Processed
# products no table reaches (steel, refined copper, cut gems, motor spirit) keep
# a profile slice beside the raw ones, so a country can still export steel it
# smelts from imported ore. Without this, Dahe's 47% of world aluminium lost to
# a sliver of Estijan's far larger ores category, and 9 of 20 wiki table
# leaders were not the atlas leaders.
RESOURCE_PARENTS = {"crude_oil_gas", "refined_fuels", "ores_metals", "precious"}

# Product specialisms DJ has stated directly. Multipliers on the product's
# weight within its category; the category share itself is set in
# trade_baskets.CANON_BASKETS.
CANON_PRODUCT = {
    "Easuhura": {"ships": 9.0, "boats": 0.6},                      # "more ship stuff": hulls, not yachts
    "Chaenia":  {"integrated_circuits": 5.0, "semiconductors": 4.0,  # Taiwan
                 "displays": 2.0},
    "Trian":    {"integrated_circuits": 4.0, "semiconductors": 3.0,  # South Korea
                 "displays": 3.0, "telephones": 2.0},
    # DJ: Dahe's forests were largely cleared long ago; what it sells is
    # processed - panels, paper, packaging - on imported logs, as China does.
    "Dahe":     {"logs": 0.15, "sawn_timber": 0.4, "pulp": 0.5,
                 "wood_panels": 2.2, "paper": 1.6, "packaging": 1.6,
                 "aircraft": 6.0, "aircraft_parts": 2.0,      # DJ: swap Emara and Dahe in aircraft
                 "air_freight": 14.0,                        # DJ: swap Dahe and Lycroa in air freight
                 "arms": 8.0,                                # DJ: Dahe, Raledria, Pelugrotoa on top
                 "watches": 0.35},                           # so Yaxuto, not Dahe, leads watches
    "Emara":    {"aircraft": 0.18, "aircraft_parts": 0.5,
                 "insurance": 9.0, "reinsurance": 6.0},       # DJ: Etirha and Emara are the big insurers, Raledria kept in the top three
    "Lycroa":   {"air_freight": 0.5},
    "Etirha":   {"insurance": 4.0, "reinsurance": 4.0},
    "Raledria": {"arms": 4.0, "insurance": 0.2, "reinsurance": 0.35},
    "Pelugrotoa": {"arms": 1.5, "watches": 0.3, "printed_matter": 0.4,
                   "ships": 3.0, "cement_stone": 4.0},       # DJ: ships swapped with Areoix Lie; building a lot   # an oil-and-steel state does not lead watches and publishing
    "Areoix Lie": {"printed_matter": 0.0,                    # DJ: remove from books and printed matter
                   "watches": 0.0,                           # DJ: remove from watches
                   "ships": 0.25,                            # DJ: swap with Pelugrotoa in ships (rank pinned below)
                   "cement_stone": 4.0,                      # DJ: building a lot
                   "logs": 0.25, "sawn_timber": 0.3, "pulp": 0.4, "wood_panels": 0.6,   # not on the forest lists; held half the world's logs
                   "cars": 0.4,                              # DJ: less cars
                   "semiconductors": 0.3, "integrated_circuits": 0.3, "measuring": 0.3,
                   "optical": 0.3, "medical_devices": 0.3, "robots": 0.3,   # DJ: less high-end electrical
                   "arms": 0.3},
    "Yaxuto":   {"watches": 30.0},                           # DJ: a lot of watches
    "Gaeiya":   {"border_trips": 9.0},                       # DJ: more day trips and border shopping
    "Oyreain":  {"cruise": 6.0},                             # DJ: Oyreain, North Ayre, Sanagara each 7-10% of cruise                             # DJ: more cruise, with Sanagara and North Ayre
    "Sanagara": {"cruise": 8.0},
    "North Ayre": {"cruise": 0.12},                          # was 92% of its own travel; DJ wants ~7-10% of the world, not a monoculture
}
# Easuhura's finance tilts sit beside its ships (above): DJ: "higher on
# banking, it has a lot of large banks", "a bit" of the insurance.
CANON_PRODUCT["Easuhura"].update({"banking": 3.0, "insurance": 1.5, "reinsurance": 1.5,
                                  "logs": 0.3, "sawn_timber": 0.4, "pulp": 0.4})   # an island finance centre held 13% of the world's logs

# Product tilts for the forest lists in trade_baskets.FOREST_CANON.
FOREST_PRODUCT = {
    "boreal":   {"logs": 1.5, "sawn_timber": 2.0, "pulp": 2.2, "paper": 1.2},
    "tropical": {"logs": 1.8, "sawn_timber": 1.6, "wood_panels": 1.6},
}


def canon_for(name):
    """CANON_PRODUCT merged with the forest tilts, or None."""
    from trade_baskets import FOREST_CANON
    out = dict(CANON_PRODUCT.get(name) or {})
    fc = FOREST_CANON.get(name)
    if fc:
        for k, v in FOREST_PRODUCT[fc].items():
            out[k] = out.get(k, 1.0) * v
    return out or None
PROCESSED_SLICE = 0.28   # of a resource category, reserved for products no table reaches

# Ranks DJ has stated directly. The Earth-shape fit in export_trade_json hands
# out Earth's rank shares by a size-and-strength ordering; these countries are
# placed at the head of that ordering, in this order, and everyone else
# follows. A multiplier cannot do this: the fit is a cliff between third and
# first, and a tilt of 11 left Dahe sixth in aircraft while 14 made it first.
CANON_RANK = {
    "aircraft":    ["Raledria", "Verusa", "Dahe"],        # "swap Emara and Dahe": Dahe takes Emara's third
    "cruise":      ["Oyreain", "Sanagara", "North Ayre"],  # "each like 7-10%"
    "insurance":   ["Etirha", "Emara", "Raledria"],        # "the big insurers", Raledria kept in the top three
    "reinsurance": ["Etirha", "Emara", "Raledria"],
    "arms":        ["Dahe", "Raledria", "Pelugrotoa"],     # "on the top"
    "watches":     ["Yaxuto"],                             # "a lot of watches": the Switzerland of the world
    "ships":       ["Easuhura", "Raledria", "Pelugrotoa"],  # "swap Areoix Lie and Pelugrotoa"
    "cement_stone": ["Areoix Lie", "Pelugrotoa"],          # "should dominate since they are building a lot"
    # DJ: the clothing makers, "spread the excess clothing in Ztesh, Quidic, Erkizil and Wundry"
    "knitwear":      ["Quidic", "Ztesh", "Wundry", "Erkizil"],
    "outerwear":     ["Quidic", "Ztesh", "Wundry", "Erkizil"],
    "footwear":      ["Quidic", "Ztesh", "Wundry", "Erkizil"],
    "knit_fabric":   ["Quidic", "Ztesh", "Wundry", "Erkizil"],
    "woven_fabric":  ["Ztesh", "Quidic", "Wundry", "Erkizil"],
    "home_textiles": ["Quidic", "Wundry", "Ztesh", "Erkizil"],
    "yarn":          ["Ztesh", "Quidic", "Erkizil", "Wundry"],
}

# Shares of the world's trade in a product that DJ set outright. These cells
# are held fixed through the Earth-shape fit; the country's other products
# absorb the difference. Used where a rank alone could not deliver: North
# Ayre's cruise was 92% of its own travel, so no rank could bring it down.
CANON_FIXED_SHARE = {
    "cruise":      {"Oyreain": 0.09, "Sanagara": 0.09, "North Ayre": 0.09,   # "each like 7-10%"
                    "Easuhura": 0.03, "Lycroa": 0.015, "Emara": 0.015, "Ilicuhe": 0.015, "Praesyu": 0.015,
                    "Acrana": 0.015, "Zenashan": 0.015, "Ukhdari": 0.015},    # "a little" cruise and maritime
    "insurance":   {"Etirha": 0.18, "Emara": 0.16, "Raledria": 0.15},         # "the big insurers", Raledria kept third
    "reinsurance": {"Etirha": 0.26, "Emara": 0.19, "Raledria": 0.17},
    "border_trips": {"Gaeiya": 0.06},                                          # "increase Gaeiya": from 2.4%
}



def split(basket, gdp_pc, oil_share=None, ctx=None, prod_conc=None, prod_values=None, canon=None):
    """
    {sub_key: share of the country's whole export basket}.

    oil_share: the country's own crude-versus-gas split from the production
      tables; reweights only those two products.
    ctx: endowments (lat, coast_share, landlocked, is_island, oil_share,
      finance_weight, mining_share, area_km2, population, size_ratio).
    prod_conc: {commodity: concentration}, the country's share of world output
      of each commodity over its share of world exports.
    """
    import math
    tilt = endowment_tilts(ctx or {})
    sharpen = 1.0
    if ctx and ctx.get("size_ratio"):
        sharpen = 1.0 + max(0.0, min(SIZE_MAX, SIZE_K * math.log(ctx["size_ratio"])))
    prod_tilt = {}
    for com, conc in (prod_conc or {}).items():
        k = COMMODITY_PRODUCT.get(com)
        if k and conc > 0:
            prod_tilt[k] = prod_tilt.get(k, 1.0) * (1.0 + PROD_K * math.log1p(conc))
    out = {}
    for parent, subs in SUBS.items():
        parent_share = basket.get(parent, 0.0)
        if parent_share <= 0:
            continue
        mix = _mix(subs, gdp_pc)
        if parent == "crude_oil_gas" and oil_share is not None:
            named = mix["crude_petroleum"] + mix["natural_gas"]
            mix["crude_petroleum"] = named * oil_share
            mix["natural_gas"] = named * (1.0 - oil_share)
        if parent in RESOURCE_PARENTS and prod_values:
            raw = {}
            for com, val in prod_values.items():
                k = COMMODITY_PRODUCT.get(com)
                if k and PARENT.get(k) == parent and val > 0:
                    raw[k] = raw.get(k, 0.0) + val
            if raw:
                rtot = sum(raw.values())
                tabled = {COMMODITY_PRODUCT[c] for c in COMMODITY_PRODUCT}
                proc = {k: v * tilt[k] for k, v in mix.items() if k not in tabled}
                ptot = sum(proc.values()) or 1.0
                w = {k: (1.0 - PROCESSED_SLICE) * raw.get(k, 0.0) / rtot for k in raw}
                for k, v in proc.items():
                    w[k] = w.get(k, 0.0) + PROCESSED_SLICE * v / ptot
                tot = sum(w.values()) or 1.0
                for k, v in w.items():
                    out[k] = v / tot * parent_share
                continue
        cp = canon or {}
        w = {k: (v * tilt[k] * prod_tilt.get(k, 1.0) * cp.get(k, 1.0)) ** sharpen for k, v in mix.items()}
        tot = sum(w.values()) or 1.0
        for k, v in w.items():
            out[k] = v / tot * parent_share
    # business travel is booked on GDP in build_trade_model; hold the
    # country's business share of its travel to that figure
    bf = (ctx or {}).get("business_frac")
    if bf is not None and 0.0 < bf < 1.0:
        tk = [k for k, _, _ in SUBS["tourism"]]
        tot_t = sum(out.get(k, 0.0) for k in tk)
        rest = sum(out.get(k, 0.0) for k in tk if k != "business_travel")
        if tot_t > 0 and rest > 0:
            out["business_travel"] = bf * tot_t
            f = (1.0 - bf) * tot_t / rest
            for k in tk:
                if k != "business_travel" and k in out:
                    out[k] *= f
    return out


def oil_gas_share(production, country):
    """
    A country's crude share of its own oil-and-gas output, from DJ's tables.
    Returns None where it produces neither, so the profile is used instead.
    Gas is worth roughly a third of oil per unit in the model's commodity
    weights (40 against 12), and that ratio is what converts output to value.
    """
    oil = (production.get("Oil") or {}).get(country, 0.0) * 40.0
    gas = (production.get("Natural Gas") or {}).get(country, 0.0) * 12.0
    if oil + gas <= 0:
        return None
    return oil / (oil + gas)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{len(SUBS)} categories -> {len(KEYS)} products")
    for parent, subs in SUBS.items():
        print(f"   {tb.LABEL[parent]:<34} {len(subs):>3}")
