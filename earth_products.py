"""
earth_products.py - what Earth traded of each manufactured product in 2015, and
how concentrated the trade was.

One row per product outside the resource categories: world exports in US$
billions, the leading exporter's share, the top-three and top-ten shares, and
the number of countries holding at least 1% of world exports. Figures are
read off OEC / UN Comtrade (HS4, 2015) and the WTO services tables, grouped to
the atlas's product list; each is an approximation to within roughly a fifth,
which is finer than anything the model can resolve. The leader is named so a
reader can see what shape is being copied, not so Andah gets the same name.

These are EXPORTS, not output. China builds 28% of the world's cars and ships
3% of the traded ones; the atlas measures trade, so trade is the benchmark.

Used two ways by export_trade_json.py:
  - a product's world total is set to its Earth share OF ITS CATEGORY (the
    category totals are already Earth-calibrated one level up);
  - a product's spread across countries is bent toward Earth's rank-share
    curve, matched on top-1, top-3 and top-10, keeping every country's
    category total fixed. The ordering of countries is the model's own.
"""

EARTH_WORLD_TRADE = 21150.0   # US$ bn, goods 16,400 + commercial services 4,750

# The categories' shares of Earth's world trade in 2015, from the HS chapter
# totals (OEC) and the WTO services tables: HS84 less computers is machinery,
# HS85 + HS90 + computers is electronics, HS28-40 is chemicals with plastics
# and rubber, HS86-89 vehicles, HS50-64 with leather textiles, HS44-48
# forestry, HS01-24 food. Resource categories are listed for reference only;
# the model takes those from the production tables. build_trade_model bends
# the world's manufacturing mix to the manufacturing rows of this table, so
# that a product's share of world trade can be compared with Earth's at all:
# before that Andah shipped 16% of its trade as machinery to Earth's 8%, and
# 4% as chemicals to Earth's 12%.
EARTH_MIX = {
    "crude_oil_gas": 0.050, "refined_fuels": 0.035, "ores_metals": 0.045, "precious": 0.028,
    "agri_food": 0.064, "forestry_paper": 0.014, "textiles": 0.045, "chemicals": 0.118,
    "machinery": 0.077, "electronics": 0.142, "vehicles": 0.082, "other_manuf": 0.035,
    "transport": 0.042, "tourism": 0.059, "finance_business": 0.121,
}

# How concentrated each manufacturing CATEGORY is on Earth: the leader's share
# of world exports of the category, the top three, the top ten, and how many
# countries hold 1%. Same shape as an EARTH row, minus the value and name.
# build_trade_model bends the categories marked True toward these with every
# country's total fixed, which is what stops one giant leading every product
# of a category at once. Textiles and other manufactures are NOT bent: on
# Earth their leader is one populous middle-income country with a third of
# the world (China), and which Andah country plays that part is canon DJ has
# not given, so the model leaves them at the spread its baskets produce.
EARTH_CAT = {
    "agri_food":      (None, .10, .25, .55, 35, "United States", True),
    "forestry_paper": (None, .12, .30, .62, 30, "Canada", True),
    "textiles":       (None, .35, .47, .68, 28, "China", False),
    "chemicals":      (None, .13, .31, .65, 30, "Germany", True),
    "machinery":      (None, .16, .43, .76, 25, "Germany", True),
    "electronics":    (None, .28, .46, .76, 22, "China", True),
    "vehicles":       (None, .20, .42, .76, 25, "Germany", True),
    "other_manuf":    (None, .30, .47, .72, 25, "China", False),
}

# key: (usd_bn, top1, top3, top10, n_at_least_1pct, leader)
# Values are the HS4 lines grouped to the product, with the chapter's
# unlisted lines folded into the nearest product (miscellaneous chemical
# products into organic chemicals, switchgear into transformers, machines
# n.e.c. into other machinery), so that a category's products add up to
# within a fifth of its chapter total in EARTH_MIX. The remainder is spread in
# proportion when the world totals are set.
EARTH = {
    # ---- agriculture and food ----
    "wheat":          (39,  .15, .38, .85, 15, "United States"),
    "maize":          (28,  .34, .64, .92, 12, "United States"),
    "rice":           (22,  .30, .62, .92, 12, "India"),
    "soya":           (47,  .44, .90, .98,  5, "Brazil"),
    "other_cereals":  (15,  .22, .50, .85, 14, "Australia"),
    "beef":           (50,  .18, .45, .83, 15, "Australia"),
    "pork":           (32,  .16, .43, .88, 14, "Germany"),
    "poultry":        (28,  .27, .55, .85, 14, "Brazil"),
    "dairy":          (80,  .13, .37, .75, 20, "Germany"),
    "fish":           (65,  .15, .33, .65, 25, "Norway"),
    "crustaceans":    (35,  .12, .34, .70, 22, "India"),
    "fruit":          (95,  .12, .29, .62, 30, "United States"),
    "vegetables":     (65,  .13, .37, .72, 25, "Netherlands"),
    "coffee":         (30,  .19, .38, .72, 20, "Brazil"),
    "tea_spices":     (20,  .18, .42, .75, 18, "China"),
    "cocoa":          (45,  .12, .33, .68, 22, "Germany"),
    "sugar":          (40,  .30, .46, .70, 20, "Brazil"),
    "oils_fats":      (85,  .22, .44, .72, 20, "Indonesia"),
    "animal_feed":    (70,  .15, .36, .70, 20, "Argentina"),
    "beverages":      (100, .20, .39, .72, 25, "France"),
    "tobacco":        (35,  .12, .27, .60, 25, "Germany"),
    # ---- forestry and paper ----
    "logs":           (12,  .25, .58, .88, 12, "New Zealand"),
    "sawn_timber":    (35,  .22, .44, .80, 18, "Canada"),
    "wood_panels":    (40,  .25, .39, .68, 25, "China"),
    "pulp":           (40,  .20, .54, .88, 12, "Brazil"),
    "paper":          (100,  .13, .32, .68, 25, "Germany"),
    "packaging":      (60,  .15, .36, .68, 25, "China"),
    "natural_fibres": (3,   .25, .55, .85, 12, "China"),
    # ---- textiles, clothing, footwear ----
    "cotton":         (12,  .35, .58, .88, 12, "United States"),
    "wool":           (6,   .45, .63, .88, 10, "Australia"),
    "synthetic_fibre":(30,  .40, .54, .82, 18, "China"),
    "yarn":           (25,  .20, .45, .80, 18, "China"),
    "woven_fabric":   (60,  .40, .52, .74, 20, "China"),
    "knit_fabric":    (25,  .45, .60, .85, 16, "China"),
    "knitwear":       (210, .37, .52, .74, 22, "China"),
    "outerwear":      (220, .34, .47, .72, 25, "China"),
    "footwear":       (130, .40, .58, .78, 20, "China"),
    "leather":        (120,  .30, .53, .78, 22, "China"),
    "home_textiles":  (60,  .40, .60, .82, 18, "China"),
    # ---- chemicals and pharmaceuticals ----
    "pharmaceuticals":(320, .15, .40, .82, 18, "Germany"),
    "medical_supplies":(200, .20, .42, .80, 18, "United States"),
    "organic_chem":   (600, .12, .31, .70, 28, "United States"),
    "inorganic_chem": (130, .12, .33, .62, 30, "United States"),
    "fertiliser":     (65,  .15, .38, .72, 22, "Russia"),
    "plastics_primary":(320,.12, .31, .72, 25, "United States"),
    "plastic_articles":(260,.22, .44, .72, 28, "China"),
    "rubber":         (190, .18, .38, .68, 25, "China"),
    "paints":         (45,  .15, .36, .70, 25, "Germany"),
    "cosmetics":      (95,  .18, .39, .70, 25, "France"),
    "soaps":          (45,  .14, .32, .64, 28, "Germany"),
    "industrial_gases":(8,  .15, .35, .70, 22, "United States"),
    # ---- machinery ----
    "engines":        (130, .16, .41, .75, 22, "Germany"),
    "turbines":       (120, .25, .55, .88, 15, "United States"),
    "pumps":          (130, .17, .43, .76, 22, "Germany"),
    "valves_bearings":(140, .16, .40, .76, 22, "Germany"),
    "agri_machinery": (50,  .17, .41, .76, 20, "Germany"),
    "construction_mach":(75,.14, .40, .78, 20, "Japan"),
    "mining_mach":    (30,  .16, .44, .76, 20, "United States"),
    "machine_tools":  (55,  .20, .49, .82, 18, "Germany"),
    "textile_mach":   (20,  .22, .53, .85, 15, "Germany"),
    "food_mach":      (25,  .22, .44, .80, 18, "Germany"),
    "printing_mach":  (15,  .25, .52, .85, 15, "Germany"),
    "hvac":           (110,  .30, .45, .74, 22, "China"),
    "lifting":        (70,  .17, .42, .76, 22, "Germany"),
    "robots":         (8,   .40, .66, .92, 10, "Japan"),
    "moulds":         (12,  .18, .42, .78, 20, "China"),
    "other_machinery":(450, .20, .46, .76, 25, "China"),
    # ---- electronics and electrical ----
    "semiconductors": (95,  .25, .44, .78, 18, "China"),
    "integrated_circuits":(600,.18,.45, .88, 14, "Taiwan"),
    "computers":      (200, .45, .61, .82, 16, "China"),
    "computer_parts": (120, .30, .46, .80, 20, "China"),
    "telephones":     (250, .47, .65, .86, 15, "China"),
    "telecom_equip":  (130, .45, .59, .82, 18, "China"),
    "broadcasting":   (150, .40, .58, .82, 18, "China"),
    "displays":       (90,  .30, .67, .92, 12, "China"),
    "consumer_av":    (120,  .45, .60, .84, 16, "China"),
    "batteries":      (45,  .32, .56, .82, 18, "China"),
    "insulated_wire": (115, .20, .40, .70, 25, "China"),
    "transformers":   (250, .25, .44, .74, 25, "China"),
    "electric_motors":(50,  .20, .43, .76, 22, "China"),
    "lighting_electric":(40,.45, .58, .80, 20, "China"),
    "measuring":      (150,  .18, .46, .78, 22, "United States"),
    "optical":        (100,  .18, .46, .80, 20, "China"),
    "medical_devices":(180, .22, .43, .78, 22, "United States"),
    # ---- vehicles, ships, aircraft ----
    "cars":           (700, .22, .43, .77, 22, "Germany"),
    "commercial_veh": (110, .15, .40, .74, 22, "Mexico"),
    "buses":          (12,  .15, .38, .78, 18, "China"),
    "vehicle_parts":  (400, .18, .40, .74, 22, "Germany"),
    "motorcycles":    (22,  .22, .46, .82, 18, "China"),
    "bicycles":       (12,  .30, .60, .85, 15, "China"),
    "trailers":       (18,  .20, .40, .74, 22, "Germany"),
    "ships":          (110, .33, .68, .88, 10, "South Korea"),
    "boats":          (12,  .15, .40, .78, 18, "Italy"),
    "aircraft":       (150, .30, .77, .96,  8, "France"),
    "aircraft_parts": (80,  .25, .53, .88, 15, "United States"),
    "rail_stock":     (30,  .15, .42, .78, 20, "China"),
    # ---- other manufactures ----
    "furniture":      (150, .35, .50, .76, 22, "China"),
    "toys_games":     (60,  .60, .71, .86, 15, "China"),
    "sports_goods":   (22,  .40, .58, .80, 18, "China"),
    "glass":          (55,  .20, .41, .70, 25, "China"),
    "ceramics":       (40,  .40, .62, .82, 18, "China"),
    "cement_stone":   (40,  .22, .37, .68, 28, "China"),
    "hand_tools":     (40,  .30, .53, .80, 20, "China"),
    "hardware":       (100, .25, .45, .74, 25, "China"),
    "lighting_fixtures":(35,.55, .65, .82, 15, "China"),
    "prefab":         (60,  .25, .41, .70, 28, "China"),
    "printed_matter": (30,  .15, .40, .76, 22, "United States"),
    "instruments_music":(6, .30, .54, .84, 15, "China"),
    "watches":        (45,  .50, .77, .92, 10, "Switzerland"),
    "arms":           (12,  .30, .50, .82, 18, "United States"),
    "misc_manuf":     (60,  .45, .60, .80, 20, "China"),
    # ---- transport services ----
    "sea_freight":    (250, .15, .35, .70, 22, "Denmark"),
    "air_freight":    (300, .18, .34, .66, 25, "United States"),
    "road_freight":   (100, .12, .28, .60, 30, "Poland"),
    "rail_freight":   (25,  .12, .30, .68, 25, "Russia"),
    "pipeline":       (8,   .20, .43, .80, 15, "Russia"),
    "port_services":  (150, .12, .26, .60, 35, "United States"),
    "warehousing":    (40,  .12, .30, .65, 30, "United States"),
    "postal_courier": (35,  .15, .38, .70, 25, "United States"),
    # ---- travel ----
    "leisure_travel": (850, .17, .28, .55, 40, "United States"),
    "business_travel":(200, .15, .30, .58, 40, "United States"),
    "border_trips":   (80,  .15, .35, .65, 30, "United States"),
    "education_travel":(70, .35, .64, .88, 12, "United States"),
    "health_travel":  (15,  .25, .41, .75, 18, "United States"),
    "cruise":         (25,  .12, .32, .62, 20, "United States"),   # by destination, not by the cruise line's home port
    # ---- finance and business services ----
    "banking":        (420, .25, .55, .83, 18, "United States"),
    "insurance":      (80,  .15, .42, .78, 18, "United Kingdom"),
    "reinsurance":    (50,  .25, .60, .92, 10, "Germany"),
    "asset_management":(120,.30, .67, .92, 12, "United States"),
    "legal":          (40,  .30, .61, .85, 15, "United States"),
    "accounting":     (30,  .15, .40, .75, 20, "United Kingdom"),
    "consulting":     (400, .15, .35, .72, 25, "United States"),
    "advertising":    (60,  .15, .35, .70, 25, "United States"),
    "it_services":    (330, .25, .52, .82, 18, "India"),
    "software":       (300, .40, .62, .88, 15, "United States"),
    "randd":          (150, .20, .40, .78, 20, "United States"),
    "telecom_services":(110,.12, .30, .66, 30, "United States"),
    "construction_svc":(100,.25, .45, .76, 20, "China"),
}


def shape(col):
    """(top1, top3, top10, n_at_least_1pct) of a {country: value} column."""
    tot = sum(col.values())
    if tot <= 0:
        return 0.0, 0.0, 0.0, 0
    s = sorted((v / tot for v in col.values()), reverse=True)
    return s[0], sum(s[:3]), sum(s[:10]), sum(1 for v in s if v >= 0.01)


GAMMAS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.15, 1.3, 1.5, 1.75, 2.0, 2.3,
          2.7, 3.2, 3.8, 4.5, 5.5, 7.0, 9.0]


def _err(got, want):
    import math
    t1, t3, t10, _ = got
    e1, e3, e10 = want[1], want[2], want[3]
    f = lambda a, b: math.log(max(a, 1e-4) / max(b, 1e-4)) ** 2
    return f(t1, e1) + f(t3, e3) + 0.5 * f(t10, e10)


def reshape(col, target, glim=(0.6, 2.0), tlim=(0.35, 2.5)):
    """
    Bend a {country: value} column toward an EARTH row's shape, in two moves
    that never reorder the countries:
      slope  raise every value to the power that brings the top-1 and top-3
             shares closest to Earth's (a power above 1 concentrates);
      tail   scale everything below tenth place by the factor that puts the
             top-10 share at Earth's, so a product with a modest leader and a
             thin tail (pork: 16% top-1, 88% top-10) is reachable, which no
             single power can do.
    Both are limited per call so the fit approaches gradually. Returns the new
    column, unscaled, and the power used.
    """
    import math
    if len(col) < 2:
        return dict(col), 1.0
    e1, e3, e10 = target[1], target[2], target[3]
    f = lambda a, b: math.log(max(a, 1e-4) / max(b, 1e-4)) ** 2
    best, bestg = None, 1.0
    for g in GAMMAS:
        t1, t3, _, _ = shape({c: v ** g for c, v in col.items()})
        e = f(t1, e1) + f(t3, e3)
        if best is None or e < best:
            best, bestg = e, g
    g = max(glim[0], min(glim[1], bestg))
    new = {c: v ** g for c, v in col.items()}
    ranked = sorted(new.items(), key=lambda kv: -kv[1])
    head = sum(v for _, v in ranked[:10])
    tail = sum(v for _, v in ranked[10:])
    if tail > 0 and 0 < e10 < 1:
        tau = head * (1.0 - e10) / (e10 * tail)
        tau = max(tlim[0], min(tlim[1], tau))
        for c, _ in ranked[10:]:
            new[c] *= tau
    return new, g


def curve(target, m):
    """
    Earth's rank-share curve for a product, drawn for m exporters: rank 1 at
    the leader's share, ranks 2-3 sharing the rest of the top three, 4-10 the
    rest of the top ten, and a geometric tail beyond tenth place whose slope
    puts the right number of countries above 1% of world exports.
    """
    t1, t3, t10, n1 = target[1:5]
    if m <= 0:
        return []
    sh = [t1]
    r23 = max(0.0, (t3 - t1) / 2.0)
    sh += [min(t1, r23)] * 2
    r410 = max(0.0, (t10 - t3) / 7.0)
    sh += [min(sh[-1], r410)] * 7
    sh = sh[:m]
    rest = max(0.0, 1.0 - sum(sh))
    k = m - len(sh)
    if k > 0 and rest > 0:
        want = max(0, n1 - sum(1 for v in sh if v >= 0.01))
        best, bestq = None, 0.8
        for q in [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.93, 0.96, 0.98, 0.99]:
            a = rest * (1.0 - q) / (1.0 - q ** k) if q < 1 else rest / k
            tail = [a * q ** j for j in range(k)]
            got = sum(1 for v in tail if v >= 0.01)
            e = abs(got - want) + (0.01 if a > sh[-1] else 0.0)
            if best is None or e < best:
                best, bestq = e, q
        a = rest * (1.0 - bestq) / (1.0 - bestq ** k)
        sh += [min(sh[-1], a * bestq ** j) for j in range(k)]
    tot = sum(sh) or 1.0
    return [v / tot for v in sh]


def blend(col, target, lam, order=None, skip=0):
    """
    Move a {country: value} column part of the way (lam in 0..1) toward
    Earth's rank-share curve: each country's share becomes the geometric
    blend of its own and the share Earth gives its rank. Ranks follow the
    values unless `order` gives a score per country, which lets a country
    that is relatively strong in the product (a high revealed comparative
    advantage) rank above a bigger one that is not: on Earth the leader in
    sugar is not the leader in wheat, and with pure size ranking one giant
    would lead every product at once and none of them sharply. Returns the
    new column, unscaled.
    """
    if len(col) < 2 or lam <= 0:
        return dict(col)
    key = (lambda kv: -order.get(kv[0], kv[1])) if order else (lambda kv: -kv[1])
    ranked = sorted(col.items(), key=key)
    tot = sum(v for _, v in ranked) or 1.0
    # `skip` cells above this column are fixed by canon: these take the curve
    # from that rank down, renormalised
    earth = curve(target, len(ranked) + skip)[skip:]
    et = sum(earth) or 1.0
    earth = [e / et for e in earth]
    out = {}
    for (c, v), e in zip(ranked, earth):
        cur = max(v / tot, 1e-9)
        out[c] = (cur ** (1.0 - lam)) * (max(e, 1e-6) ** lam)
    return out


# Each Earth leader's share of world trade in 2015 (goods plus services), so a
# product's concentration can be read FOR THE LEADER'S SIZE: Germany ships 22%
# of the world's cars on 7.5% of its trade, a ratio of 2.9. Andah's giants are
# 12% of world trade each, so a Raledria with 31% of cars is Germany-shaped,
# not sharper; the verdict sheet says both.
EARTH_TRADE_SHARE = {
    "United States": .106, "China": .121, "Germany": .075, "Japan": .041, "United Kingdom": .038,
    "Netherlands": .036, "France": .035, "South Korea": .030, "Italy": .027, "Canada": .023,
    "India": .020, "Russia": .019, "Mexico": .019, "Switzerland": .018, "Taiwan": .015,
    "Australia": .011, "Poland": .010, "Brazil": .010, "Indonesia": .008, "Denmark": .007,
    "Norway": .0066, "Argentina": .003, "New Zealand": .002,
}
