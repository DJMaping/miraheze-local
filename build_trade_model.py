#!/usr/bin/env python3
"""
build_trade_model.py - Andah trade, derived rather than assigned.

WHAT CHANGED, AND WHY
  The previous model asked which of N buckets a country belonged to and then
  read its trade off that bucket. That put the burden on a judgement call the
  data can make better. This version never assigns anything. Every figure comes
  from a continuous relationship estimated on Earth 2015 and applied to DJ's own
  numbers, and the descriptive label is computed LAST, from the output, purely
  so the spreadsheet reads well. Change a country's GDP per capita and its
  character changes with it, which is the behaviour a worldbuilding tool wants.

THE FOUR LAYERS

  1. GEOGRAPHY, measured not guessed.
     172 polygons in lon/lat give exact centroids, areas, great-circle distances
     and shared border lengths. Landlocked is measured: a country whose entire
     outline is shared with neighbours has no coast. 30 land-locked, 24 islands.

  2. OPENNESS, a regression not a bucket.
     ln(trade/GDP) = c + b1 ln(pop) + b2 ln(area) + b3 ln(GDPpc)
                       + b4 landlocked + b5 island + b6 ln(remoteness)
                       + b7 resource concentration
     Population is the dominant term and it is NEGATIVE: a large internal market
     is the strongest brake on trade there is. This one equation reproduces, with
     no special-casing, the fact that giants trade at 25-35% of GDP while
     mid-size open economies reach 90%.

  3. GRAVITY, checked for consistency, NOT independently validated.
     X_ij = Y_i^a Y_j^b / D_ij^theta, lifted by contiguity, shared border length
     and common region. Scored against DJ's flight network over all 14,706
     country pairs: can the model tell which 1,114 are actually linked?
     AUC 0.953, where 0.5 is chance.

     READ THAT NUMBER CAREFULLY. Two earlier versions of this file oversold it,
     and both claims are withdrawn:

       - The first reported r = +0.70 correlation against flight demand as the
         validation. That conditions on pairs that already have flights, and a
         null model with no distance and no geography at all scores 0.683 on it.
         It was evidence that big economies trade more, close to a tautology.

       - The second called the AUC independent evidence, on the grounds that the
         flight network was built for an unrelated purpose. It was not built for
         an unrelated purpose in the sense that matters. That network's demand
         field is itself a gravity model: views/flight-routes.js computes
         base = (mass_A * mass_B)^alpha / dist^beta over the SAME countries.json
         GDP vector and the SAME map this model uses. Testing a gravity model
         against another gravity model over identical inputs cannot confirm that
         gravity is the right structure for Andah's trade; it can only confirm
         the two implementations agree.

     So the AUC is a CONSISTENCY check. It is still worth having - it caught the
     Ashain antimeridian error and it proves the geography, distance and GDP
     wiring are sound - but it is not evidence for the gravity assumption, and
     nothing in this project currently is. The genuinely external checks are the
     Earth 2015 metric suite and the polygon-versus-Janus area agreement.
     The distance exponent itself is NOT taken from that fit. Sweeping it from
     0.1 to 1.0 moves the correlation only 0.717 to 0.700, so aviation cannot
     identify the parameter, and aviation decays with distance far more gently
     than bulk cargo does anyway. THETA therefore comes from the merchandise
     trade literature; see validate_gravity(). Row and column sums are then
     forced onto the layer-2 totals by iterative proportional fitting, so the
     bilateral matrix and the country totals agree to machine precision.

  4. TRANSIT, which is canon and stays.
     Hinterland cargo becomes re-exports, stopover and canal traffic become
     services. That structure came from DJ directly and no regression should
     overrule it.

  Export baskets use Earth-realistic concentration: an economy's product spread
  widens with income, so a poor petrostate really can be 90% oil while a rich
  economy exports across hundreds of lines.

Usage
  python build_trade_model.py                  build for 1765
  python build_trade_model.py --fit            report the gravity validation and exit
  python build_trade_model.py --compare        Earth 2015 comparison and exit
  python build_trade_model.py --years 1725 1745 1765
"""

import argparse
import collections
import math
import os
import sys

import andah_data as ad
import trade_baskets as tb
import wiki_canon as wc

OUT = os.path.join(ad.DATA, "Andah_Trade_Statistics.xlsx")

YEAR = 1765
BENCHMARK_YEARS = [1725, 1745, 1765]

# ---------------------------------------------------------------------------
# Calibration constants, all from Earth 2015. Everything here is a ratio or an
# elasticity, so none of it imports Earth's absolute size into Andah.
# ---------------------------------------------------------------------------

WORLD_OPENNESS = 0.285      # world exports / world GDP

# TOURISM IS EARNED, NOT ASSIGNED. Until now a country's tourism was a slice of
# its services by income, times a flat island or coast factor, so the biggest
# rich economies earned the most whatever their weather: Raledria, at 49
# degrees, led the world. Earth's receipts follow sun, sea and nearness to
# rich markets: Spain, Thailand, Turkey, Greece and Mexico earn far more than
# their size, Germany, Canada and Russia far less. Receipts here are
#   attractiveness x market access ^ TOURISM_MA_EXP, scaled to Earth's share
#   of world trade (5.9%),
# where attractiveness is GDP ^ TOURISM_GDP_EXP x population ^ TOURISM_POP_EXP
# (a country has more to see, more beds and more airports the bigger and
# richer it is, with diminishing returns: Earth's elasticities are about 0.7
# on GDP and 0.3 on population), a climate factor peaking between 18 and 42
# degrees, a coastline factor, an island bonus, a landlocked penalty, and
# whatever DJ's pages already say about resorts and beaches; market access is the distance-discounted GDP of everyone else,
# discounted hard because most tourism is short-haul. Capped at
# TOURISM_MAX_SHARE of a country's exports, the Maldives' share.
TOURISM_SHARE_OF_TRADE = 0.059
TOURISM_MAX_SHARE = 0.75
TOURISM_ISLAND_FLOOR = 0.42   # small islands (under ISLAND_MAX_POP): the Fiji shape
TOURISM_GDP_EXP = 0.60      # receipts rise with the destination's economy...
TOURISM_POP_EXP = 0.25      # ...and a little more with its population (Earth's elasticities ~0.7 and ~0.3)
TOURISM_MA_EXP = 0.85
TOURISM_MA_KM = 1500.0
TOURISM_MA_THETA = 1.5
# Business travel is not sun: it follows the size of the economy and its
# financial centres (Earth: about $200bn of $1,250bn travel). It is booked on
# GDP and added to the leisure receipts; the product layer then holds each
# country's business share of its travel to this figure.
BUSINESS_SHARE_OF_TRADE = 0.0095
BUSINESS_FINANCE_LIFT = 2.0
# DJ's adjustments to leisure travel (multipliers on attractiveness). "Decrease
# massively" also lifts the small-island floor, "increase" raises it.
TOURISM_CANON = {}
for _n in ("Areoix Lie", "Inania", "Ealdorii", "Ztesh", "Vayvele", "Dual Cenryia", "Wundry",
           "Erkizil", "Galca", "Pelan"):
    TOURISM_CANON[_n] = 0.60
for _n in ("Ocaun", "Welenu Fana", "Migoku", "Western Migoku"):
    TOURISM_CANON[_n] = 0.20
for _n in ("Sanagara", "Easuhura", "Suenan", "Taval", "Oyreain", "Siana", "Merela Sta", "Trian",
           "Stinebar", "North Ayre", "Ahokini", "Tomscilus", "United Delet", "Isari", "Mendereide",
           "Jshain", "Disal Nila", "Walporein", "Peka", "Ilicuhe", "Prstreula", "Myla", "Fire Coast",
           "Rkmepuia", "Aplasia", "Guise", "Rijan bu", "Rethern", "Fermori", "Metndria", "Kaastini",
           "Desaki", "Koruch", "Sivoso", "Iainoa", "Taing", "Hiwush", "Yihnurda", "Jau", "Feio Lie",
           "Deschon", "Cloja"):
    TOURISM_CANON[_n] = 1.60


def tourism_climate(lat):
    a = abs(lat)
    if a <= 18:
        return 0.85
    if a <= 42:
        return 1.0
    if a <= 55:
        return 1.0 - (a - 42) / 13.0 * 0.55
    return max(0.20, 0.45 - (a - 55) / 15.0 * 0.25)
GOODS_SHARE = 0.78          # merchandise share of world exports
COMMODITY_SHARE_OF_GOODS = 0.235   # 0.25 for the wiki commodities plus refined petroleum (below)

# Openness elasticities. Signs and rough magnitudes are the standard findings of
# the empirical trade literature; the intercept is solved so the world total
# lands on WORLD_OPENNESS, so only the RELATIVE values matter here.
# Larger population -> much less open. Retuned after the resource term was fixed
# to use concentration: the old -0.280 was partly compensating for that bug.
# A marginally better fit was available at -0.14 (deviation 4.06 against 4.70),
# but that is below the empirical range for this elasticity, and 0.05 per metric
# on a suite of my own design is not worth an indefensible coefficient.
B_POP = -0.180
B_AREA = -0.075     # bigger territory -> more internal trade, less external
B_GDPPC = +0.055    # richer economies trade slightly more
# Landlocked penalty. Set so the CONDITIONAL measurement in earth_comparison()
# lands on Earth's ~30%: at -0.30 it comes out at 0.287. An earlier pass briefly
# set this to 0 because a raw landlocked-vs-coastal mean showed a 53% penalty
# and looked far too harsh. That was a confound: Andah's landlocked countries
# are six times poorer per head, and once size and income are held fixed the
# model was actually penalising them by only 3%, not 53%.
B_LANDLOCKED = -0.30
B_ISLAND = +0.10
B_REMOTE = -0.20    # far from markets -> less trade
# Resource term. Uses CONCENTRATION (share of world output divided by share of
# world GDP), not the raw output share. The raw share is a size variable: it gave
# Dahe, which produces LESS resource output than its GDP share, the second-largest
# resource boost in the world, while Far Lands at 1,318x concentration got +1.9%.
# log1p handles a measure that spans 0.06 to 1,318 without saturating a cap.
B_RESOURCE = +0.24

# Hard ceiling on exports as a multiple of GDP. Hong Kong and Singapore, the two
# most trade-dependent economies on Earth, export roughly twice their GDP. This
# binds only on microstates whose concentration ratios are built on a near-zero
# denominator; the world total is re-solved after it applies.
OPENNESS_CEILING = 2.20

# Services share of a country's exports. Rises with income (structural
# transformation) and falls where a big commodity export dominates the basket.
# The intercept is the share for a median-income country with no resource
# concentration; the world total is renormalised afterwards regardless.
SVC_INTERCEPT = 0.260
SVC_GDPPC_SLOPE = 0.075
SVC_RESOURCE_DRAG = 0.070
SVC_PORT_DRAG = 0.90     # per unit of ln(cargo concentration); floor keeps some services

# Trade balance. Resource exporters run surpluses; rich consumer markets run
# deficits. Continuous, so nothing is bucketed.
# Tuned jointly with BAL_TO_GDP after the balance was re-anchored to GDP rather
# than to export volume. The petrostate runs the surplus and the large consumer
# market runs the deficit, which the model was never told to do.
BAL_RESOURCE = -0.90
BAL_GDPPC = +0.055
BAL_INTERCEPT = -0.02

# Ceilings on the trade balance as a share of GDP. Earth's extremes are roughly
# +25% (Gulf petrostates at peak oil) and -15% on the deficit side, which is
# tighter because a deficit has to be financed by somebody.
BAL_CAP_SURPLUS = 0.25
BAL_CAP_DEFICIT = 0.15
HUB_EXPORT_CEILING = 2.2    # exports including transit fees, as a multiple of GDP
BAL_POOR_DEFICIT = 0.10     # tilt per e-fold of income below the median: a positive tilt is a deficit
BAL_CAP_OF_EXPORTS = 0.60    # surplus at most this share of exports (Kuwait's 2015 figure is ~0.45)
# Converts the dimensionless balance tilt into a share of GDP. Set so the spread
# of balances across countries matches Earth's without the caps having to bind.
BAL_TO_GDP = 0.50
# Margin an entrepot keeps on the goods it clears: financing, insurance,
# storage, breaking bulk, re-labelling. Real gateway ports book this spread,
# which is why the Netherlands and Singapore run surpluses on huge re-export
# volumes. Earth's effective margin is a few per cent of re-export value.
REEXPORT_MARGIN = 0.05

# Gravity.
# GDP elasticities. THESE DO NOT AFFECT THE RECONCILED MATRIX, and the comment
# is here so nobody tunes them expecting otherwise.
#
# The gravity term is gdp_a**A * gdp_b**B * d**-theta * exp(lift). The first
# factor is constant across a row, the second across a column, and IPF scales
# every row and column onto its target - which cancels them exactly. Swept over
# A/B from 0.95/0.85 to 1.10/0.68 and all twenty-one Earth metrics were
# identical to three decimals. They still shape the UNRECONCILED base that
# validate_gravity() and gravity_auc() score, so they are kept at the values
# the literature gives.
#
# The same argument applies to anything else row- or column-separable: only
# terms that vary by PAIR survive reconciliation. Every pair term the model has
# - distance, contiguity, shared continent, shared subregion, bloc membership,
# the geometric mean of reach - is SYMMETRIC in a and b, so after IPF the only
# asymmetry left is what the margins carry. That is why bilateral balances come
# out flatter than Earth's, and no amount of tuning these will change it.
GRAV_A = 0.95       # exporter GDP elasticity
GRAV_B = 0.85       # importer GDP elasticity
# Distance decay for MERCHANDISE trade. Taken from the empirical trade
# literature (estimates cluster near 1.0), NOT fitted to the flight network:
# see validate_gravity() for why aviation cannot identify this parameter.
THETA = 1.00

# SHIPS SAIL ROUND; CROWS FLY STRAIGHT. With this on, the distance the gravity
# layer and the remoteness term see is the sea route between two countries'
# coasts (sea_distance.py, cached in data/sea_distances.json), with a land leg
# for anyone landlocked. Great-circle distance puts Dahe and Areoix Lie 7,465 km
# apart; by sea they are 19,411 km, on opposite sides of a landmass. This is
# what lets two countries share a mountain border and trade almost nothing
# without anyone having to draw the mountains.
#
# Two things deliberately stay on the straight line: the flight-network check,
# because aircraft do fly straight, and the Earth distance metric, because its
# 4,900 km benchmark is a great-circle figure and must stay comparable.
SEA_ROUTING = True

# Who owns each canal, and what a canal earns per unit of value it carries.
CANAL_OWNER = {"Tiesa Canal": "Emara"}
CANAL_TOLL_RATE = 0.003   # DJ: two thirds of Suez. Suez took $5.2bn in 2015 on roughly $1.1T of cargo, about 0.45% of value


def canal_traffic():
    """{canal: value transiting per year} from the last sea_lanes.py run."""
    import json
    path = os.path.join(ad.HERE, "data", "sea_lanes.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return {k: float(v) for k, v in (json.load(fh).get("canals") or {}).items()}


def sea_or_straight(names, straight):
    """The sea matrix where it exists, the straight-line one where it does not."""
    import json
    path = os.path.join(ad.HERE, "data", "sea_distances.json")
    if not SEA_ROUTING or not os.path.exists(path):
        return straight, False
    with open(path, encoding="utf-8") as fh:
        km = json.load(fh).get("km") or {}
    out = {}
    for (a, b), d in straight.items():
        v = km.get(a, {}).get(b)
        out[(a, b)] = float(v) if v else d
    return out, True

# HOW FAR EACH KIND OF TRADE TRAVELS, relative to THETA.
#
# A single decay for all trade is the model's oldest simplification and its most
# expensive one: crude oil crosses oceans by tanker while a holiday is usually
# taken next door, and averaging the two puts oil in the wrong countries. These
# are relative weights, rescaled at runtime so the world-mix-weighted mean is
# exactly 1.0 and the aggregate calibration that THETA was fitted for survives.
#
# Low = travels far. Bulk commodities and anything with a high value-to-weight
# ratio ship anywhere; heavy low-value goods and face-to-face services do not.
CATEGORY_THETA = {
    "crude_oil_gas":    0.55,   # tankers; the global commodity par excellence
    "refined_fuels":    0.80,
    "ores_metals":      0.65,   # bulk carriers
    "precious":         0.35,   # value per kilo makes distance nearly free
    "agri_food":        0.95,
    "forestry_paper":   1.10,   # heavy and cheap: the classic regional good
    "textiles":         0.85,
    "chemicals":        0.95,
    "machinery":        0.95,
    "electronics":      0.75,   # small, valuable, often air-freighted
    "vehicles":         1.00,
    "other_manuf":      1.05,
    "transport":        0.85,   # shipping and logistics follow the cargo
    "tourism":          1.45,   # most tourism is short-haul and regional
    "finance_business": 0.45,   # the least physical thing a country sells
}
CONTIG = 0.45       # shared land border lift
# Continent lift cut and subregion lift raised, with REGIONAL_MULT eased from
# 2.8, so that crossing a continent boundary costs 2.05x rather than 2.66x.
SAME_CONTINENT = 0.30
SAME_SUBREGION = 0.45

# PROXIMITY, WHICH DOES NOT KNOW WHERE THE BOUNDARIES ARE.
#
# The continent and subregion lifts are dummies: a pair either shares one or it
# does not, so crossing a line costs a fixed multiple however far apart the two
# countries actually sit. At the values above that multiple was 2.66x, meaning
# two neighbours 500 km apart traded as if they were 1,330 km apart purely
# because a boundary ran between them, which is not a fact about shipping.
#
# The fix is not to weaken the dummies alone: the intra-continent share is
# MEASURED by continent, so weakening them drops it straight through the Earth
# check. This term instead rewards being close to anybody. Most short-range
# pairs are on the same continent, so the regional total holds up, while a pair
# either side of a line keeps whatever its distance earns.
NEAR_LIFT = 0.5
NEAR_SCALE = 1800.0
# Multiplies both regional lifts. Raised above 1.0 to keep small and mid-size
# economies regional (the Europe effect, 68% intra-region) while the reach dial
# sends the giants global; without it, globalising the giants drags the whole
# world's intra-continent share below Earth's.
#
# EASED FROM 2.6. At 2.6 the giants became continental monopolists: Areoix Lie
# was the largest partner of 24 of the 25 countries in Acrola, Pelugrotoa 24 of
# 25 in Mahea, Dahe 25 of 26 in Massir, and only a fifth of the world had a top
# partner on another continent. Splitting the lift between continent and
# subregion was tried first, on the theory that Earth is regional at the
# subregion level; it did open the world up but cost more intra-continent share
# than it was worth and left Acrola concentrated anyway.
REGIONAL_MULT = 2.4

# Complementarity exponent: how strongly a pair's basket match pulls trade.
# 1.0 means a pair matched twice as well as average trades twice as much,
# before distance and size.
#
# THE THREE DIALS BELOW WERE SWEPT TOGETHER (18 combinations). The finding: no
# setting makes the giants US-like (33% regional) while holding the world at
# Earth's 57%, because the giants ARE most of world trade. Earth manages it only
# because Europe's mid-size economies sit at 68% and counterbalance the US.
# Any single giant can be made US-like by raising its reach to 2.5-3.0 in the
# Global reach sheet.
#
# RAISED FROM 0.6 WITH REGIONAL_MULT (1.6 -> 2.6) after the import_demand fix.
# Once an oil state's appetite for crude was correctly near zero, the basket
# match said the right thing - Disal Nila to Dahe scored 1.30 against Disal Nila
# to Etirha at 0.47 - but at K_COMP 0.6 that 2.8x signal became 1.85x, and lost
# to a 16x distance ratio (615 km to Etirha against 10,004 km to Dahe). So the
# oil kept going to the oil states. Raising K_COMP lets the basket argue with
# distance; raising REGIONAL_MULT alongside it puts back the regional trade that
# a stronger complementarity term would otherwise disperse. Swept over 5 pairs:
# this one moves intra-continent share from 0.496 to 0.547 (Earth 0.570, so
# closer than before), leaves the other 15 Earth checks untouched, and cuts the
# crude landing in countries that are themselves over 40% oil exporters from
# 16.0% to 11.1%. Concentration stays Earth-like: median top-partner share
# 25.1%, and 14 of 172 countries send over 60% to one partner, where Earth has
# somewhere near a dozen (Canada, Mexico, Mongolia, Bhutan, Nepal, Lesotho).
K_COMP = 2.4
# Global reach: how weakly a country feels distance.
#
#   reach = 1 + REACH_SIZE * (export_share ** REACH_EXP)
#                + REACH_FINANCE * sqrt(centre_weight)
#
# SCALED ON EXPORTS, NOT GDP. Reach is about how far a country's trade travels,
# and a large home economy does not make it travel: Areoix Lie and Pelugrotoa
# export within 12% of Dahe on half its GDP, yet the GDP basis scored them 1.53
# and 1.45 against Dahe's 2.60. Big enough to dominate a continent and too
# short-range to leave it, each ended up the largest partner of 24 of the 25
# countries beside it, while only 20% of the world had a top partner on another
# continent. Earth runs at roughly half, because China is top partner across
# four continents at once.
#
# The finance term sends a leading financial centre out past its region whatever
# its size, since services cross distance in a way bulk freight cannot. It is
# what gives Easuhura, sixth in the GFCI table and a mid-size economy, a global
# reach rather than a regional one.
#
# Every country's value is still editable in the Global reach sheet.
# Swept with REGIONAL_MULT over 9 pairs against the share of countries whose
# largest partner sits on another continent: 20% before, 33% here, Earth
# around half. DJ asked for a moderate 35%.
REACH_SIZE = 5.4
REACH_EXP = 1.5
REACH_FINANCE = 1.4

# Openness multipliers for countries whose canon says they are export-oriented
# manufacturing hubs. This is the Germany-versus-China distinction and it is a
# real one: a continental giant with a vast home market trades at 35% of GDP
# while an export platform of similar sophistication reaches 85%. DJ: Pelugrotoa
# and Areoix Lie "are both large manufacturing hubs now, rivalling Dahe and
# Raledria", and rivalling means in the export totals, not only in the basket.
# Areoix Lie is the third largest economy yet was trading at 35% of GDP, exactly
# like Dahe, which is what kept it fifth by exports.
# DJ asked for the four giants to trade 30% MORE, multiplicatively: Dahe from
# 39% of GDP to about 51%, not to 69%. The existing hub multipliers are
# scaled by 1.55, not 1.30, because world exports are pinned at a fixed share
# of world GDP: lifting four countries scales all 168 others down, and a 1.30
# multiplier delivered only +18%. 1.55 lands +29% to +30%.
CANON_OPENNESS = {"Areoix Lie": 3.02, "Pelugrotoa": 1.94,
                  "Dahe": 1.55, "Raledria": 1.55,
                  "Estijan": 1.35}   # "more industry": added on top of its ores, not out of them

# How much a shared alliance bloc lifts trade between two members. The Earth
# comparison is the EU, where intra-bloc trade exceeds any member's trade with
# any outside partner. Only the countries in the Great Importance sheet carry
# membership, so this touches the largest economies and nobody else.
# Trade blocs. RAISED FROM 0.45 after finding this is the strongest lever the
# model has on whether a country's biggest customer differs from its biggest
# supplier - it took that metric from 0.15 to 0.26, where basket differences and
# GDP elasticities had done nothing. That fits the economics: an agreement is a
# pair-specific commitment, which is exactly the structure IPF cannot wash out,
# where every other pair term the model has is pure geography.
#
# WHAT THE BLOC DATA CANNOT YET SUPPORT, all reported rather than guessed at:
#   - Only 26 of the 172 countries carry any bloc code at all, from the Great
#     Importance sheet's alliance column. The other 146 get no lift, which is
#     the right default but is thin coverage for a dial this strong.
#   - Five of the fourteen codes have a single member (ADT, RRO, AFTZ, SHDA,
#     SACC) and are therefore inert: a lift needs two countries to share it.
#   - The codes are not typed. A free trade area and a mutual defence pact move
#     trade very differently, and MPU expands on the wiki to Mahea Petroleum
#     Union - a producers' body whose two members are both oil exporters, where
#     a trade lift is probably backwards. Typing them needs canon that does not
#     exist yet: only one organisation page exists in the whole corpus.
K_BLOC = 1.2

# ECONOMIC LINKS DJ HAS STATED DIRECTLY.
#
# These are not in the alliance column and not derivable from geography or
# production, so they get their own term rather than being smuggled into the
# bloc lift, where they would be indistinguishable from parsed data. Each entry
# is his wording and the weight reads off its strength.
#
# The Estijan group is hub-and-spoke, not a bloc: he said the eight are linked
# TO Estijan, so Fermori and Uularin get no lift with each other.
QUIAN_UNION = ["Ahokini", "Anymna", "Baluyde", "Desaki", "Erkizil", "Finae",
               "Myla", "Onphello", "Quidic", "Verste", "Wundry", "Yihnurda", "Ztesh"]

CANON_LINK_PAIRS = [
    (["Easuhura", "Ilicuhe"], 1.00),        # "closely economically linked"
    (["Eldjo", "Praesyu"], 0.80),           # "linked economicly more"
    (["Arbiya", "Raledria"], 1.00),         # "very close"
    (["Taval", "Hkuqo", "Ucrua", "Jshain"], 1.00),   # "more trade between" all four
    # A customs union raises trade between every pair of members, so this is an
    # all-pairs lift rather than hub-and-spoke. It does NOT put the members' oil
    # into each other's hands: crude only flows to a country whose import demand
    # wants crude, and an oil exporter's demand for crude is near zero, so the
    # per-category matrices keep Ahokini's and Verste's oil pointed at the big
    # consumers outside the bloc whatever this lift does.
    (QUIAN_UNION, 1.80),
]
CANON_LINK_HUBS = [
    ("Estijan", ["Fermori", "Uularin", "Lydroa", "Danocia", "Darewa",
                 "Urbiqu", "Ikzen", "Heiso"], 0.40),   # "slighly more"
]


def _canon_links():
    out = {}
    for names, w in CANON_LINK_PAIRS:
        for a in names:
            for b in names:
                if a != b:
                    out[(a, b)] = w
    for hub, spokes, w in CANON_LINK_HUBS:
        for sp in spokes:
            out[(hub, sp)] = w
            out[(sp, hub)] = w
    return out


CANON_LINK = _canon_links()

COMMODITY_WEIGHTS = {
    # Refined petroleum: not a wiki table. Earth exports $600bn of it against
    # $1,050bn of crude and gas, and the four products are the modelled
    # tables built by refinery_tables() below.
    "Petrol": 4.7, "Diesel": 6.1, "Jet fuel": 2.1, "Fuel oil": 2.9,   # refined fuels had reached 4.5% of trade against Earth's 3.5%
    # Weights are relative trade values. Oil and gas halved and the precious
    # metals raised in Sep 1765 review: crude and gas had come out at 10% of
    # world trade (Earth 5%) and precious metals at 1.1% (Earth 2.8%).
    "Oil": 14.0, "Natural Gas": 4.5, "Coal": 7.0, "Iron": 7.0, "Copper": 7.0,
    "Gold": 14.0, "Aluminium": 4.0, "Motor vehicle": 3.5, "Nickel": 2.0,
    "Silver": 3.5, "Zinc": 1.5, "Paper": 1.4, "Platinum": 2.6, "Diamond": 3.2,
    "Lead": 1.0, "Tin": 0.9, "Uranium": 0.8, "Lithium": 0.8, "Palladium": 1.5,
    "Manganese": 0.6, "Titanium": 0.6, "Cobalt": 0.6, "Chromium": 0.5,
    "Magnesium": 0.4, "Salt": 0.4, "Silicon": 0.4, "Niobium": 0.3,
    "Vanadium": 0.25, "Bentonite": 0.2, "Feldspar": 0.2, "Fluorite": 0.2,
    "Thorium": 0.15, "Iridium": 0.15, "Bismuth": 0.1, "Mercury": 0.1,
}

# DJ's transit canon. Shares of each hub's throughput; these are his, not fitted.
TRANSIT = [
    # DJ: "Emara isn't really a re-export hub, it barely counts": its ports
    # ship its own goods, a sliver of Lycroa's, and the canal is a toll.
    ("Emara",      "own",        "",           0.76, "Puzhu and Chishanov"),
    ("Emara",      "hinterland", "Lycroa",     0.04, "a little Lycroan cargo"),
    ("Emara",      "canal",      "",           0.20, "Alubri City, Tiesa Canal Territory"),
    ("Merela Sta", "own",        "",           0.30, ""),
    ("Merela Sta", "hinterland", "Verusa",     0.46, "some Verusan"),
    ("Merela Sta", "hinterland", "Yaxuto",     0.17, "some Yaxutan"),
    ("Merela Sta", "hinterland", "Palina",     0.07, "all Palinan"),
    # DJ: both should carry more domestic value added. Raising the own share is
    # the honest way to do it: what changes is how much of the cargo on their
    # quays is theirs rather than Dahe's passing through, which is exactly what
    # domestic value added measures.
    ("Sanagara",   "own",        "",           0.74, ""),
    ("Sanagara",   "hinterland", "Dahe",       0.16, ""),
    ("Sanagara",   "stopover",   "",           0.10, "Sanagara Strait"),
    ("Oyreain",    "own",        "",           0.64, ""),
    ("Oyreain",    "hinterland", "Dahe",       0.21, ""),
    ("Oyreain",    "stopover",   "",           0.15, "Batikolo on the Sanagara Strait"),
    ("Pha Hii",    "own",        "",           0.20, ""),
    ("Pha Hii",    "hinterland", "Dahe",       0.75, "89 km border with Dahe"),
    ("Pha Hii",    "hinterland", "Prystr Hii", 0.05, "Prystr Hii has no top-60 port"),
    ("Chaenia",    "own",        "",           0.45, ""),
    ("Chaenia",    "stopover",   "",           0.55, "Singapore-style stopover"),
    ("Taval",      "own",        "",           0.25, ""),
    ("Taval",      "stopover",   "",           0.75, "refuelling and bunkering"),
    ("Guise",      "own",        "",           0.05, ""),
    ("Guise",      "stopover",   "",           0.95, "pure transshipment"),
    ("Canldives",  "own",        "",           0.03, ""),
    ("Canldives",  "stopover",   "",           0.97, "Ayuma-Dahe lane, Vishanna Ocean"),
]
BUNKERING = {"Taval"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def ln(x, floor=1e-9):
    return math.log(max(x, floor))


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


# ---------------------------------------------------------------------------
# layer 1-2: fundamentals
# ---------------------------------------------------------------------------

REFINE_PRODUCERS, REFINE_HUBS, REFINE_IMPORTERS = 0.55, 0.25, 0.20

# CHAMPION CATEGORIES. Earth's rich countries each lead with a different
# industry - cars in Germany and Japan, machinery in Sweden and Austria,
# electronics in Korea, pharmaceuticals in Switzerland and Ireland - and that
# comes from history, not income. The income profile has no history, so once
# the world's mix was bent to Earth's, half the rich countries led with
# chemicals and none with cars or machinery. The rule below hands each
# eligible country one champion manufacturing category, spread across the
# band in Earth's proportions, chosen by a score from what the model knows:
# population and ports for vehicles; being landlocked, small and rich for
# machinery; coasts, islands, density and ports for electronics; being very
# rich and small, or an oil producer, for chemicals; being populous and poorer
# for textiles. The champion is set to CHAMPION_LEAD times the country's next
# manufacturing line, capped at CHAMPION_CAP of exports, the mass taken from
# its other manufacturing lines, and the world's mix is then re-bent to
# Earth's with the champions held fixed. Countries with DJ's own pins, and
# resource- or services-led countries, are left alone. DJ: "by rule".
CHAMPION_BANDS = [
    ("rich", 80_000, {"vehicles": .25, "machinery": .25, "electronics": .20, "chemicals": .20}),
    ("upper-middle", 25_000, {"vehicles": .25, "electronics": .25, "machinery": .15,
                              "textiles": .10, "chemicals": .05}),
]
CHAMPION_LEAD = 1.15         # champion = this times the country's next manufacturing line
CHAMPION_CAP = 0.30          # ...but never more than this share of its exports (Korea's electronics: 30%)
CHAMPION_WORLD_CAP = 0.18    # ...nor more than this share of the world's trade in the category (Germany's cars: 22%)
CHAMPION_COLUMN_FILL = 0.85  # pins plus champions may hold at most this much of a category's world total
CHAMPION_RESOURCE_LED = 0.35
CHAMPION_SERVICES_LED = 0.45


def champion_scores(r, g, nports, med_pc):
    pop = max(r["population"], 1e5)
    area = g.get("area_km2") or 1.0
    coastal = not r["landlocked"]
    island = bool(r["is_island"])
    dens = pop / area
    lnpop = math.log(pop / 1e7)
    rich = math.log(max(r["gdp_pc"], 1.0) / med_pc)
    oil = (r.get("commodity_mix") or {}).get("Oil", 0.0) > 0
    return {
        "vehicles":    0.6 * lnpop + (0.8 if nports > 0 else 0.0) + (0.5 if r["n_borders"] >= 3 else 0.0)
                       - (0.6 if island and pop < 20e6 else 0.0),
        "machinery":   (1.0 if r["landlocked"] else 0.0) + (0.6 if pop < 30e6 else 0.0) + 0.5 * rich
                       + (0.4 if r["n_borders"] >= 2 else 0.0),
        "electronics": (1.0 if coastal else 0.0) + (0.8 if island else 0.0) + (0.6 if dens > 150 else 0.0)
                       + (0.4 if nports >= 2 else 0.0) + (0.3 if 5e6 <= pop <= 120e6 else 0.0),
        "chemicals":   0.8 * rich + (0.8 if pop < 15e6 else 0.0) + (0.5 if r.get("finance_weight", 0) > 0 else 0.0)
                       + (0.4 if oil else 0.0) + (0.3 if coastal else 0.0),
        "textiles":    0.8 * lnpop + (0.8 if r["gdp_pc"] < 45e3 else 0.0) + (0.3 if coastal else 0.0),
    }


def assign_champions(rows, data, basket_of, pinned_names):
    """{country: category} by band, Earth's spread, best relative score first."""
    geo = data["geo"]
    nports = collections.Counter(pr["country"] for pr in (data.get("port_rows") or []))
    med_pc = sorted(r["gdp_pc"] for r in rows)[len(rows) // 2]
    out = {}
    zscore = data.setdefault("champion_score", {})
    for band, floor, freq in CHAMPION_BANDS:
        ceil = next((f for b, f, _ in CHAMPION_BANDS if f > floor), float("inf"))
        elig = []
        for r in rows:
            if r["name"] in pinned_names or not (floor <= r["gdp_pc"] < ceil):
                continue
            b = basket_of[r["name"]]
            if sum(b.get(k, 0.0) for k in tb.RESOURCE) >= CHAMPION_RESOURCE_LED:
                continue
            if r.get("svc_share", 0.0) >= CHAMPION_SERVICES_LED:
                continue
            elig.append(r)
        if not elig:
            continue
        scores = {r["name"]: champion_scores(r, geo[r["name"]], nports[r["name"]], med_pc) for r in elig}
        slots = {k: int(round(f * len(elig))) for k, f in freq.items()}
        cands = []
        for k in freq:
            vals = [scores[r["name"]][k] for r in elig]
            mu = sum(vals) / len(vals)
            sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1.0
            for r in elig:
                cands.append(((scores[r["name"]][k] - mu) / sd, r["name"], k))
        cands.sort(key=lambda t: (-t[0], t[1], t[2]))
        for z, nm, k in cands:
            if nm in out or slots.get(k, 0) <= 0:
                continue
            out[nm] = k
            zscore[nm] = z
            slots[k] -= 1
    return out


REFINED_TABLES = ("Petrol", "Diesel", "Jet fuel", "Fuel oil")


def refinery_tables(data):
    """
    WHO REFINES OIL. The wiki has no refining table, and without one refined
    fuels were 0.7% of world trade against Earth's 3.5%. Earth's refined
    exports come from three kinds of place, and the modelled table follows
    them (DJ chose this rule over naming hubs):
      producers   an oil state refines part of what it pumps (Russia, Saudi
                  Arabia, Kuwait, the United States): REFINE_PRODUCERS of the
                  world's refined exports, in proportion to oil output;
      hubs        entrepots refine what passes through (Singapore, Rotterdam,
                  Antwerp): REFINE_HUBS, in proportion to port cargo weighted
                  by how far that cargo exceeds the country's own economy;
      importers   big industrial economies with major ports re-export
                  products from imported crude (Korea, India, Japan):
                  REFINE_IMPORTERS, in proportion to GDP times ports, for
                  economies above 1% of world GDP.
    Adds four synthetic production tables, one per product, with the same
    country shares; the split between them is Earth's product mix.
    """
    prod = data["production"]
    if all(t in prod for t in REFINED_TABLES):
        return
    countries = data["countries"]
    names = set(countries)
    oil = prod.get("Oil") or {}
    cargo = collections.defaultdict(float)
    nports = collections.defaultdict(int)
    for pr in data.get("port_rows") or []:
        if pr["country"] in names:
            cargo[pr["country"]] += pr.get("cargo") or 0.0
            nports[pr["country"]] += 1
    wgdp = sum(c["gdp"] for c in countries.values())
    ratios = sorted(cargo[n] / countries[n]["gdp"] for n in cargo if countries[n]["gdp"] > 0)
    med_ratio = ratios[len(ratios) // 2] if ratios else 1.0
    prod_term = {n: oil.get(n, 0.0) for n in names}
    hub_term = {n: cargo[n] * min(4.0, (cargo[n] / countries[n]["gdp"]) / med_ratio)
                for n in cargo if countries[n]["gdp"] > 0}
    imp_term = {n: countries[n]["gdp"] * (1.0 + math.log1p(nports[n]))
                for n in names if countries[n]["gdp"] / wgdp >= 0.01 and nports[n] > 0}
    share = collections.defaultdict(float)
    for term, w in ((prod_term, REFINE_PRODUCERS), (hub_term, REFINE_HUBS), (imp_term, REFINE_IMPORTERS)):
        tot = sum(term.values())
        if tot > 0:
            for n, v in term.items():
                share[n] += w * v / tot
    for t in REFINED_TABLES:
        prod[t] = {n: v for n, v in share.items() if v > 1e-6}
    data["refinery_shares"] = dict(share)


def resource_scores(production, names):
    wsum = sum(COMMODITY_WEIGHTS.values())
    weights = {k: v / wsum for k, v in COMMODITY_WEIGHTS.items()}
    score = collections.defaultdict(float)
    per_commodity = collections.defaultdict(dict)
    for commodity, per in production.items():
        w = weights.get(commodity, 0.1 / wsum)
        for country, share in per.items():
            if country in names:
                score[country] += share * w
                per_commodity[country][commodity] = share * w
    return score, per_commodity


def market_access(countries, dist, names):
    """
    Sum of every other economy's GDP discounted by distance.

    Remoteness is its inverse. This is what makes a country far from the world's
    demand trade less, without anyone deciding it is 'peripheral'.
    """
    ma = {}
    for a in names:
        tot = 0.0
        for b in names:
            if a == b:
                continue
            d = dist.get((a, b))
            if d and d > 0:
                tot += countries[b]["gdp"] / d
        ma[a] = tot
    return ma


def compute_fundamentals(data, dist):
    refinery_tables(data)
    countries = data["countries"]
    geo = data["geo"]
    names = list(countries)
    rscore, rper = resource_scores(data["production"], set(names))
    ma = market_access(countries, dist, names)
    med_ma = sorted(ma.values())[len(ma) // 2]
    world_gdp = sum(c["gdp"] for c in countries.values())

    rows = []
    for name in sorted(names):
        c = countries[name]
        g = geo[name]
        gdp_share = c["gdp"] / world_gdp
        rs = rscore.get(name, 0.0)
        concentration = rs / gdp_share if gdp_share > 0 else 0.0

        lnop = (B_POP * ln(c["population"])
                + B_AREA * ln(g["area_km2"])
                + B_GDPPC * ln(max(c["gdp_pc"], 1.0))
                + B_LANDLOCKED * (1.0 if g["landlocked"] else 0.0)
                + B_ISLAND * (1.0 if g["is_island"] else 0.0)
                + B_REMOTE * ln(med_ma / max(ma[name], 1e-9))
                + B_RESOURCE * math.log1p(min(concentration, 40.0))
                + ln(CANON_OPENNESS.get(name, 1.0)))

        rows.append(dict(
            name=name, continent=c["continent"], subregion=c["subregion"],
            gdp=c["gdp"], gdp_pc=c["gdp_pc"], population=c["population"],
            area_km2=g["area_km2"], landlocked=g["landlocked"], is_island=g["is_island"],
            coast_km=g["coast_km"], n_borders=len(g["borders"]),
            market_access=ma[name], remoteness=med_ma / max(ma[name], 1e-9),
            resource_score=rs, resource_concentration=concentration,
            commodity_mix=rper.get(name, {}),
            ln_openness_raw=lnop,
        ))

    # Solve the intercept so world exports land on the calibrated share of GDP,
    # then apply a ceiling and re-solve.
    #
    # THE CEILING IS AN EMPIRICAL FACT, not a fudge. No real economy sustains
    # exports much beyond twice its GDP: Hong Kong and Singapore, the most
    # extreme entrepots on Earth, run about 2x exports and 4x total trade, and
    # that is the ceiling of what a pure transit economy can reach. Without it
    # the regression happily produced 6.9x for Tvecoca, a country of 5,165 people
    # whose resource CONCENTRATION reads 285 only because dividing by its
    # vanishing share of world GDP explodes the ratio; its actual oil output
    # weight is 0.0002. Ratios built on near-zero denominators need a bound.
    target = world_gdp * WORLD_OPENNESS
    if OPENNESS_CEILING <= WORLD_OPENNESS * 1.2:
        raise SystemExit(
            f"OPENNESS_CEILING ({OPENNESS_CEILING}) is at or below the world average "
            f"openness ({WORLD_OPENNESS}). Every country cannot be below the mean, so "
            f"the world total can never be reached and exports would come out "
            f"silently short. Raise the ceiling.")
    for r in rows:
        r["openness_uncapped"] = math.exp(r["ln_openness_raw"])
        r["openness"] = r["openness_uncapped"]
    # Cap, re-solve, repeat. Converges quickly at any sensible ceiling: at the
    # shipped 2.20 only two countries bind and the world target is hit exactly.
    for _ in range(24):
        scale = target / sum(r["openness"] * r["gdp"] for r in rows)
        capped = False
        for r in rows:
            v = r["openness"] * scale
            if v > OPENNESS_CEILING:
                v = OPENNESS_CEILING
                capped = True
            r["openness"] = v
        if not capped:
            break
    for r in rows:
        r["exports_pre"] = r["gdp"] * r["openness"]

        # Services share of exports. This previously ran through an
        # undocumented +0.18 literal with a slope so shallow that every country
        # in the world came out between 15% and 27% - the income story it
        # claimed to tell was inert. On Earth the spread is enormous: a
        # petrostate ships 5% services, a finance or tourism economy over 60%.
        # Two forces set it, and they pull opposite ways: services rise with
        # income, and collapse as a share when a country has a large commodity
        # export to dominate the denominator.
        pc_rel = r["gdp_pc"] / max(1.0, sorted(x["gdp_pc"] for x in rows)[len(rows) // 2])
        r["svc_share"] = min(0.72, max(0.05,
                                       SVC_INTERCEPT
                                       + SVC_GDPPC_SLOPE * ln(max(pc_rel, 0.05))
                                       - SVC_RESOURCE_DRAG * math.log1p(min(r["resource_concentration"], 40.0))))

        # balance: resource exporters surplus, rich consumer markets deficit
        # Income pulls both ways: rich consumer markets run deficits, and so
        # do poor countries (aid, remittances, capital inflows: Earth's
        # low-income group averages about -6% of GDP). Only the resource term
        # earns a surplus. The old single slope gave every poor country a
        # surplus, 19 of 21 above 5% of GDP.
        inc = (BAL_GDPPC * ln(pc_rel) if pc_rel >= 1.0
               else BAL_POOR_DEFICIT * (-ln(max(pc_rel, 0.05))))
        r["bal_tilt"] = (BAL_INTERCEPT
                         + BAL_RESOURCE * min(r["resource_concentration"], 3.0) * 0.1
                         + inc)
    return rows, world_gdp


# ---------------------------------------------------------------------------
# layer 3: gravity, fitted against the flight network
# ---------------------------------------------------------------------------

def gravity_matrix(rows, dist, geo, theta, contig, same_cont, same_sub,
                   comp=None, reach=None, blocs=None):
    """
    Bilateral flows before reconciliation.

    Two terms beyond the textbook equation:

    comp   COMPLEMENTARITY. How well i's export basket matches j's import
           demand, relative to a generic exporter (1.0 = average). Raised to
           K_COMP. This is what sends oil across an ocean to an industrial buyer
           and machinery to an industrialising one: trade follows need, not only
           proximity. Editing a country's basket therefore changes its partners.

    reach  GLOBAL REACH, per country. Divides the distance exponent, so a
           country with reach 1.8 feels distance about half as strongly as one
           with reach 1.0. The geometric mean of the pair's reach is used so
           both ends count. Defaults scale with economic size (the giants trade
           globally because everything they do is large) and DJ overrides any
           country in the workbook's Global reach sheet.
    """
    by = {r["name"]: r for r in rows}
    names = [r["name"] for r in rows]
    flows = {}
    for a in names:
        ra = by[a]
        for b in names:
            if a == b:
                continue
            rb = by[b]
            d = dist.get((a, b)) or 1.0
            border = geo[a]["borders"].get(b, 0.0)
            lift = 0.0
            if border > 0:
                # a longer shared border is a stronger link, with diminishing returns
                lift += contig + 0.06 * ln(1 + border / 500.0)
            lift += NEAR_LIFT * math.exp(-d / NEAR_SCALE)
            if ra["continent"] == rb["continent"]:
                lift += same_cont
            if ra["subregion"] == rb["subregion"]:
                lift += same_sub
            th = theta
            if reach:
                th = theta / math.sqrt(reach.get(a, 1.0) * reach.get(b, 1.0))
            if comp:
                lift += K_COMP * ln(max(comp.get((a, b), 1.0), 1e-6))
            if blocs:
                shared = len(blocs.get(a, set()) & blocs.get(b, set()))
                if shared:
                    lift += K_BLOC * math.log1p(shared)
            lift += CANON_LINK.get((a, b), 0.0)
            flows[(a, b)] = (math.exp(GRAV_A * ln(ra["gdp"]) + GRAV_B * ln(rb["gdp"])
                                      - th * ln(d) + lift))
    return flows


def validate_gravity(rows, dist, geo, flights, theta=None, contig=None, verbose=False):
    """
    Score the gravity structure against DJ's flight network.

    The flight network was built for an unrelated purpose, which is what makes it
    usable as evidence: nothing in it was chosen to make this model look good.
    We correlate predicted bilateral flows, in logs, with observed route demand
    across the ~1,106 country pairs that actually have flights.

    WHY THIS VALIDATES BUT DOES NOT FIT THE DISTANCE EXPONENT
      Sweeping theta from 0.1 to 1.0 moves the correlation only from 0.717 to
      0.700. The surface is essentially flat, so the flight data cannot identify
      distance decay; virtually all of the r=0.72 comes from the GDP and
      geography terms. Worse, fitting goods-trade decay to AVIATION would be the
      wrong target even if it were sharp: passengers cross oceans routinely,
      bulk cargo does not, so aviation decays far more gently than merchandise.
      Adopting the flight optimum (theta=0.4) would have quietly made Andah's
      trade far too indifferent to distance.

      So THETA stays at the standard merchandise-trade estimate of about 1.0 from
      the empirical literature, and the flight network does the job it is
      actually good for: confirming the structure is sound. The cost is 0.025 of
      correlation on a metric that was not measuring the right thing anyway.
    """
    obs = [(a, b, math.log(rec["demand"]))
           for (a, b), rec in flights.items() if rec["demand"] > 0]
    if len(obs) < 50:
        return THETA, CONTIG, 0.0, 0

    def score(th, cg):
        flows = gravity_matrix(rows, dist, geo, th, cg, SAME_CONTINENT, SAME_SUBREGION)
        xs, ys = [], []
        for a, b, lo in obs:
            f = flows.get((a, b), 0.0) + flows.get((b, a), 0.0)
            if f > 0:
                xs.append(math.log(f)); ys.append(lo)
        return pearson(xs, ys), len(xs)

    if verbose:
        print(f"   {'theta':>6}{'contig':>8}{'r':>10}")
        for th in [0.2, 0.4, 0.6, 0.8, 1.0, 1.2]:
            for cg in [0.0, 0.2, 0.45, 0.8]:
                r, n = score(th, cg)
                print(f"   {th:>6.1f}{cg:>8.2f}{r:>10.4f}")

    th = THETA if theta is None else theta
    cg = CONTIG if contig is None else contig
    r, n = score(th, cg)
    return th, cg, r, n


def gravity_auc(rows, dist, geo, flights):
    """
    The gravity check that actually carries weight: can the model pick out WHICH
    country pairs are linked, across every pair in the world?

    WHY THE CORRELATION TEST WAS NOT ENOUGH. Correlating predicted flow against
    flight demand among pairs that HAVE flights conditions on the outcome, and it
    turns out almost all of that r=0.70 is the GDP terms doing the work: a null
    model of Y_i^a * Y_j^b with no distance and no geography at all scores 0.683,
    so the entire gravity structure was adding 0.012. On that evidence the r was
    close to a tautology - big economies trade more - and it should not have been
    reported as validating the structure.

    This test does not condition on anything. Every unordered pair of the 172
    countries is scored, 14,706 of them, and we ask whether the model ranks the
    1,114 genuinely linked pairs above the 13,592 unlinked ones. Here the
    structure earns its place: GDP alone reaches AUC 0.896, adding distance takes
    it to 0.946, and the full model with contiguity and regional lifts reaches
    0.953. Distance is worth +0.05 AUC, which the correlation test could not see.
    """
    linked = set(flights)
    names = [r["name"] for r in rows]
    flows = gravity_matrix(rows, dist, geo, THETA, CONTIG, SAME_CONTINENT, SAME_SUBREGION)
    scored = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            key = tuple(sorted((a, b)))
            v = flows.get((a, b), 0.0) + flows.get((b, a), 0.0)
            scored.append((v, 1 if key in linked else 0))
    scored.sort(key=lambda x: x[0])
    n1 = sum(s[1] for s in scored)
    n0 = len(scored) - n1
    if not n1 or not n0:
        return 0.5, 0, 0
    rank_sum, i = 0.0, 0
    while i < len(scored):
        j = i
        while j < len(scored) and scored[j][0] == scored[i][0]:
            j += 1
        avg = (i + j - 1) / 2 + 1
        rank_sum += avg * sum(scored[k][1] for k in range(i, j))
        i = j
    return (rank_sum - n1 * (n1 + 1) / 2) / (n1 * n0), n1, n0


def ipf(flows, rows, iters=60):
    """
    Force the bilateral matrix onto the country totals.

    Iterative proportional fitting: scale rows to hit each country's exports,
    then columns to hit its imports, and repeat. It converges on the matrix
    closest to the gravity prediction that still reproduces both margins exactly,
    so the partner detail and the headline totals can never disagree.
    """
    names = [r["name"] for r in rows]
    want_x = {r["name"]: r["exports_goods_target"] for r in rows}
    want_m = {r["name"]: r["imports_goods_target"] for r in rows}
    f = dict(flows)
    for _ in range(iters):
        cur = collections.defaultdict(float)
        for (a, b), v in f.items():
            cur[a] += v
        for (a, b) in list(f):
            if cur[a] > 0:
                f[(a, b)] *= want_x[a] / cur[a]
        cur = collections.defaultdict(float)
        for (a, b), v in f.items():
            cur[b] += v
        for (a, b) in list(f):
            if cur[b] > 0:
                f[(a, b)] *= want_m[b] / cur[b]
    err_x = max(abs(sum(v for (a, b), v in f.items() if a == n) - want_x[n]) / max(want_x[n], 1)
                for n in names)
    err_m = max(abs(sum(v for (a, b), v in f.items() if b == n) - want_m[n]) / max(want_m[n], 1)
                for n in names)
    return f, err_x, err_m


def reconcile_demand(rows, world_mix):
    """
    Each country's imports split across the fifteen categories, consistent both
    ways: every country's rows add to its own import bill, and every category's
    column adds to what the world actually produces of it.

    import_demand() gives a plausible shape per country, but nothing makes the
    world's appetite for a category equal the world's output of it. Fitting the
    172 x 15 matrix to both margins is the same trick the bilateral IPF uses,
    one dimension down, and without it the per-category flows would be asked to
    hit targets that cannot all be met at once.
    """
    names = [r["name"] for r in rows]
    supply = {k: 0.0 for k in tb.KEYS}
    for r in rows:
        for k in tb.KEYS:
            supply[k] += r["basket"].get(k, 0.0) * r["domestic_x"]
    tot_supply = sum(supply.values()) or 1.0
    want_row = {}
    for r in rows:
        want_row[r["name"]] = max(r["total_m"], 1.0)
    scale = sum(want_row.values()) / tot_supply
    want_col = {k: v * scale for k, v in supply.items()}

    d = {}
    for r in rows:
        dem = r.get("import_demand") or tb.import_demand(r["basket"], world_mix)
        for k in tb.KEYS:
            d[(r["name"], k)] = max(dem.get(k, 0.0), 1e-9) * want_row[r["name"]]
    for _ in range(40):
        cur = collections.defaultdict(float)
        for (a, k), v in d.items():
            cur[a] += v
        for key in d:
            if cur[key[0]] > 0:
                d[key] *= want_row[key[0]] / cur[key[0]]
        cur = collections.defaultdict(float)
        for (a, k), v in d.items():
            cur[k] += v
        for key in d:
            if cur[key[1]] > 0:
                d[key] *= want_col[key[1]] / cur[key[1]]
    return d, want_col


def category_flows(rows, dist, geo, theta, contig, same_cont, same_sub,
                   reach, blocs, world_mix, verbose=False):
    """
    One bilateral matrix per category, each with its own distance decay, summed
    into the total.

    This replaces the single matrix the model used to build. That matrix could
    only ever say how much a pair traded, never what they traded, so oil moved
    at the same speed over distance as machinery and services had no geography
    at all - their targets were goods-only, so a financial centre's customers
    were inferred from the freight it happened to ship.

    Complementarity is NOT applied here. It existed to make baskets matter in a
    matrix that could not see them; now that a country only ships a category it
    produces, and only receives one it needs, the matching is structural.
    """
    # rescale so the mix-weighted mean decay is still THETA
    wm = {k: world_mix.get(k, 0.0) for k in tb.KEYS}
    wsum = sum(wm.values()) or 1.0
    mean_rel = sum(CATEGORY_THETA.get(k, 1.0) * wm[k] for k in tb.KEYS) / wsum
    th_of = {k: theta * CATEGORY_THETA.get(k, 1.0) / (mean_rel or 1.0) for k in tb.KEYS}

    goods_mix = {k: world_mix.get(k, 0.0) for k in tb.GOODS}
    gm_sum = sum(goods_mix.values()) or 1.0
    goods_mix = {k: v / gm_sum for k, v in goods_mix.items()}

    demand, _ = reconcile_demand(rows, world_mix)
    total = collections.defaultdict(float)
    per_cat = {}
    for k in tb.KEYS:
        want_x = {r["name"]: max(r["basket"].get(k, 0.0) * r["domestic_x"]
                                 + goods_mix.get(k, 0.0) * r["reexports"], 1e-6)
                  for r in rows}
        want_m = {r["name"]: max(demand.get((r["name"], k), 0.0), 1e-6) for r in rows}
        sx, sm = sum(want_x.values()), sum(want_m.values())
        if sx <= 0 or sm <= 0:
            continue
        want_m = {a: v * sx / sm for a, v in want_m.items()}   # balance the category
        f = gravity_matrix(rows, dist, geo, th_of[k], contig, same_cont, same_sub,
                           comp=None, reach=reach, blocs=blocs)
        f = ipf_to(f, want_x, want_m, iters=35)
        per_cat[k] = f
        for key, v in f.items():
            total[key] += v
        if verbose:
            print(f"   {k:<18} theta {th_of[k]:.2f}  {sx/1e12:8.2f}T")
    return dict(total), per_cat


def ipf_to(flows, want_x, want_m, iters=60):
    """IPF onto explicit row and column targets."""
    f = dict(flows)
    for _ in range(iters):
        cur = collections.defaultdict(float)
        for (a, b), v in f.items():
            cur[a] += v
        for key in f:
            if cur[key[0]] > 0:
                f[key] *= want_x[key[0]] / cur[key[0]]
        cur = collections.defaultdict(float)
        for (a, b), v in f.items():
            cur[b] += v
        for key in f:
            if cur[key[1]] > 0:
                f[key] *= want_m[key[1]] / cur[key[1]]
    return f


# ---------------------------------------------------------------------------
# layer 4: transit
# ---------------------------------------------------------------------------

def apply_transit(rows, cargo):
    by = {r["name"]: r for r in rows}
    for r in rows:
        r.update(cargo_own=0.0, cargo_carried=0.0, cargo_stopover=0.0,
                 cargo_canal=0.0, cargo_routed=0.0)
    hubs = {h for h, *_ in TRANSIT}
    for country, total in cargo.items():
        if country not in by:
            continue
        if country not in hubs:
            by[country]["cargo_own"] += total
            continue
        for hub, kind, partner, share, _n in TRANSIT:
            if hub != country:
                continue
            vol = total * share
            if kind == "own":
                by[country]["cargo_own"] += vol
            elif kind == "stopover":
                by[country]["cargo_stopover"] += vol
            elif kind == "canal":
                by[country]["cargo_canal"] += vol
            elif kind == "hinterland":
                by[country]["cargo_carried"] += vol
                if partner in by:
                    by[partner]["cargo_routed"] += vol
    for r in rows:
        r["effective_cargo"] = r["cargo_own"] + r["cargo_routed"]


# ---------------------------------------------------------------------------
# layer 5: export baskets, Earth-realistic concentration
# ---------------------------------------------------------------------------

def build_baskets(rows):
    """
    How concentrated is each country's export basket?

    On Earth the spread of a country's exports widens sharply with income: a poor
    petrostate really is ~90% one product, while a rich economy exports across
    hundreds of lines and no single one dominates. Modelled as a target share for
    the leading product that falls with income and rises with resource
    concentration, then the actual commodity mix is fitted under it.
    """
    med_pc = sorted(r["gdp_pc"] for r in rows)[len(rows) // 2]
    for r in rows:
        pc_rel = r["gdp_pc"] / max(med_pc, 1.0)
        # rich -> diversified; resource-heavy -> concentrated
        top_share = 0.30 - 0.11 * ln(max(pc_rel, 0.05)) + 0.16 * min(r["resource_concentration"], 4.0)
        r["top_export_share"] = max(0.06, min(0.90, top_share))
        # Herfindahl of the basket, consistent with that leading share
        r["basket_hhi"] = max(0.02, min(0.85, r["top_export_share"] ** 1.35))
        r["n_export_lines"] = max(1, int(round(1.0 / max(r["basket_hhi"], 0.012))))

        mix = r.get("commodity_mix") or {}
        if mix:
            lead, val = max(mix.items(), key=lambda kv: kv[1])
            r["leading_commodity"] = lead
            r["leading_commodity_weight"] = val
        else:
            r["leading_commodity"] = ""
            r["leading_commodity_weight"] = 0.0


def name_leading_exports(rows, world_commodity_trade):
    """Leading export is the basket's largest category; the raw commodity is kept alongside."""
    for r in rows:
        b = r.get("basket") or {}
        if b:
            top = max(b.items(), key=lambda kv: kv[1])
            r["leading_category"] = top[0]
            r["leading_export"] = tb.LABEL[top[0]]
            r["leading_export_share_of_goods"] = top[1]
            r["basket_hhi"] = sum(v * v for v in b.values())
            r["top_export_share"] = top[1]
            r["n_export_lines"] = sum(1 for v in b.values() if v >= 0.01)
    if all(r.get("basket") for r in rows):
        return
    _name_leading_exports_legacy(rows, world_commodity_trade)


def _name_leading_exports_legacy(rows, world_commodity_trade):
    """
    Decide what each country's leading export should actually be CALLED.

    Leading the world in a small market is not the same as living off it. Without
    a materiality test, 29 countries came out labelled by a commodity worth under
    2% of their own exports: Merela Sta as a motor-vehicle exporter on 0.13%,
    Ukhdari as a feldspar economy on 1.5%. Below the threshold the honest answer
    is a category, and the category itself is read off the computed figures
    rather than assigned.
    """
    for r in rows:
        value = r["leading_commodity_weight"] * world_commodity_trade
        share = value / r["goods_x"] if r["goods_x"] else 0.0
        r["leading_export_share_of_goods"] = share
        if r["leading_commodity"] and share >= 0.08:
            r["leading_export"] = r["leading_commodity"]
        elif r["dva_share"] < 0.70:
            r["leading_export"] = "Re-exports"
        elif r["svc_x"] / max(r["total_x"], 1.0) >= 0.45:
            r["leading_export"] = "Transit and port services"
        elif r["gdp_pc"] < 32_000:
            r["leading_export"] = "Agricultural produce"
        elif r["gdp_pc"] < 112_000:
            r["leading_export"] = "Light manufactures"
        else:
            r["leading_export"] = "Manufactures"


# ---------------------------------------------------------------------------
# derived label - computed from outputs, never an input
# ---------------------------------------------------------------------------

def describe(r):
    """
    A reading aid, produced AFTER the numbers and never feeding back into them.

    This is the inversion DJ asked for: the model no longer needs to know what
    kind of country this is in order to compute its trade. The label is just a
    sentence about what the figures turned out to be.
    """
    tot = r["cargo_own"] + r["cargo_carried"] + r["cargo_stopover"] + r["cargo_canal"]
    passing = r["cargo_stopover"] + r["cargo_canal"]
    if tot > 0 and passing / tot >= 0.55:
        return "transit port economy"
    if r["dva_share"] < 0.70:
        return "re-export gateway"
    # only call it an X exporter when X actually dominates the basket
    b = r.get("basket") or {}
    if b:
        top_k, top_v = max(b.items(), key=lambda kv: kv[1])
        if top_v >= 0.40 and top_k in ("crude_oil_gas", "refined_fuels", "ores_metals",
                                       "precious", "agri_food", "textiles", "tourism"):
            short = {"crude_oil_gas": "oil & gas", "refined_fuels": "fuel", "ores_metals": "metals",
                     "precious": "precious metals", "agri_food": "agricultural",
                     "textiles": "textile", "tourism": "tourism"}[top_k]
            return f"{short} exporter" if top_k != "tourism" else "tourism economy"
    elif r["resource_concentration"] >= 2.0 and r.get("leading_export_share_of_goods", 0) >= 0.08:
        return f"{r['leading_commodity'].lower()} exporter"
    if r["trade_gdp"] >= 1.4:
        return "highly open economy"
    if r["balance"] < 0 and r["trade_gdp"] < 0.55:
        return "large consumer market"
    if r["svc_x"] / max(r["total_x"], 1) >= 0.45:
        return "services exporter"
    # income thresholds are in NEW lahn (8x the old figures)
    if r["balance"] > 0 and r["gdp_pc"] >= 96_000:
        return "industrial surplus economy"
    if r["gdp_pc"] < 32_000:
        return "low-income trader"
    return "diversified economy"


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------

def run(data, year=YEAR, fit_verbose=False):
    countries = data["countries"]
    names = list(countries)
    straight = ad.distance_matrix(data["geo"], names)
    dist, sea_on = sea_or_straight(names, straight)

    rows, world_gdp = compute_fundamentals(data, dist)
    apply_transit(rows, data["cargo"])

    # port throughput lifts a country's openness, using EFFECTIVE cargo so a
    # hinterland economy is not punished for shipping through a neighbour
    # Median over countries that actually SHIP something. 131 of 172 have no
    # top-60 port, so the median across all countries is exactly 0.0 and the old
    # `or 1.0` fallback quietly replaced the normaliser with an arbitrary
    # constant, leaving port_factor measured against nothing meaningful.
    _int = sorted(r["effective_cargo"] / (r["gdp"] / 1e9)
                  for r in rows if r["gdp"] > 0 and r["effective_cargo"] > 0)
    med_int = _int[len(_int) // 2] if _int else 1.0
    world_cargo = sum(r["effective_cargo"] for r in rows)
    for r in rows:
        inten = r["effective_cargo"] / (r["gdp"] / 1e9) if r["gdp"] > 0 else 0.0
        r["port_factor"] = max(0.65, min(2.2, (inten / med_int) ** 0.22)) if inten > 0 else 0.72
        r["exports_pre"] *= r["port_factor"]
        # A big container port means a goods-dominated basket. Earth: China's
        # services are ~10% of exports and Germany's ~17%, against the UK's 45%,
        # and the difference is manufacturing throughput, not income.
        #
        # The signal is CARGO CONCENTRATION: share of world container throughput
        # divided by share of world GDP, the container analogue of resource
        # concentration. Throughput-per-GDP against the median port country
        # cannot see a giant: Dahe runs the world's largest port, yet per unit of
        # its enormous GDP it sits below the median, so the first version of this
        # never fired for it and it came out 27% services. Relative to the world
        # Dahe ships 1.4x its GDP share, which is a manufacturing exporter.
        r["cargo_concentration"] = ((r["effective_cargo"] / world_cargo) / (r["gdp"] / world_gdp)
                                    if world_cargo and r["gdp"] else 0.0)
        # A small island has no land and no factories, so services ARE the
        # economy: Earth's run 60-85% services against the model's 23%.
        if r["is_island"] and r["population"] < tb.ISLAND_MAX_POP:
            r["svc_share"] = max(r["svc_share"], tb.ISLAND_SERVICES_FLOOR)
        if r["cargo_concentration"] > 1.0:
            r["svc_share"] *= max(0.40, 1.0 - SVC_PORT_DRAG * math.log(r["cargo_concentration"]))

    # renormalise after the port lift so the world target still holds
    target = world_gdp * WORLD_OPENNESS
    s = target / sum(r["exports_pre"] for r in rows)
    for r in rows:
        r["exports_pre"] *= s
        r["total_x_target"] = r["exports_pre"]
        r["svc_x"] = r["exports_pre"] * r["svc_share"]
        r["dom_goods_x"] = r["exports_pre"] - r["svc_x"]

    # tourism receipts (see TOURISM_SHARE_OF_TRADE); booked into services
    # first by the basket, ahead of the income profile
    geo_ = data["geo"]
    med_pc = sorted(x["gdp_pc"] for x in rows)[len(rows) // 2]
    evid = data.get("wiki_evidence") or {}
    attr, ma = {}, {}
    for r in rows:
        nm = r["name"]
        pop = max(r["population"], 1e4)
        a = ((r["gdp"] / 1e12) ** TOURISM_GDP_EXP * (pop / 1e6) ** TOURISM_POP_EXP
             * tourism_climate(geo_[nm]["lat"]))
        a *= 0.55 + 0.45 * min(1.0, r["coast_km"] / 2500.0)
        if r["is_island"]:
            a *= 4.0 if pop < 8e6 else 1.5     # the Fiji shape DJ asked for: strongly touristic, not Maldives
        elif r["landlocked"]:
            a *= 0.65
        h = (evid.get(nm) or {}).get("tourism", 0)
        if h:
            a *= min(1.6, 1.0 + 0.35 * math.log1p(h))
        a *= TOURISM_CANON.get(nm, 1.0)
        attr[nm] = a
        ma[nm] = sum(q["gdp"] * (1.0 + straight[(nm, q["name"])] / TOURISM_MA_KM) ** -TOURISM_MA_THETA
                     for q in rows if q is not r)
    raw = {r["name"]: attr[r["name"]] * ma[r["name"]] ** TOURISM_MA_EXP for r in rows}
    world_x_pre = sum(r["exports_pre"] for r in rows)
    fin_c = data.get("financial_centres") or {}
    bus_raw = {r["name"]: r["gdp"] * (1.0 + BUSINESS_FINANCE_LIFT * fin_c.get(r["name"], 0.0)) for r in rows}
    bus_k = BUSINESS_SHARE_OF_TRADE * world_x_pre / (sum(bus_raw.values()) or 1.0)
    world_tour = (TOURISM_SHARE_OF_TRADE - BUSINESS_SHARE_OF_TRADE) * world_x_pre
    k = world_tour / sum(raw.values())
    # the cap is soft: receipts approach TOURISM_MAX_SHARE of exports
    # asymptotically, so a dozen small countries do not all sit on one line
    def capped(r, k):
        cap = TOURISM_MAX_SHARE * r["exports_pre"]
        return cap * (1.0 - math.exp(-raw[r["name"]] * k / cap)) if cap > 0 else 0.0
    for _ in range(6):      # re-solve the scale after the cap bites
        k *= world_tour / sum(capped(r, k) for r in rows)
    for r in rows:
        t = capped(r, k)
        # A small island is a tourism economy whatever the gravity says: Earth's
        # run 45-75% (Fiji 48%, Jamaica 52%, Bahamas 68%), and DJ asked for
        # the Fiji shape. The receipts model alone gave them 16%, because a
        # tiny GDP and a remote sea both score low; the floor is the canon.
        cf = TOURISM_CANON.get(r["name"], 1.0)
        if r["is_island"] and r["population"] < tb.ISLAND_MAX_POP and cf >= 0.5:
            # the floor varies with the island's own attractiveness relative
            # to its peers, so five islands do not all print the same figure
            peers = [attr[q["name"]] for q in rows if q["is_island"] and q["population"] < tb.ISLAND_MAX_POP]
            med = sorted(peers)[len(peers) // 2] if peers else attr[r["name"]]
            wobble = max(0.80, min(1.20, (attr[r["name"]] / max(med, 1e-12)) ** 0.25))
            floor = min(0.72, TOURISM_ISLAND_FLOOR * (cf ** 0.6) * wobble)
            t = max(t, floor * r["exports_pre"])
        bus = min(bus_raw[r["name"]] * bus_k, 0.25 * r["exports_pre"], 1.5 * t)
        r["business_x"] = bus
        t = t + bus
        r["tourism_x"] = t
        r["tourism_attr"] = attr[r["name"]]
        # services must be able to hold the tourism; the total is kept
        need = t / 0.85
        if need > r["svc_x"]:
            r["svc_x"] = need
            r["dom_goods_x"] = r["exports_pre"] - r["svc_x"]
            r["svc_share"] = r["svc_x"] / r["exports_pre"]

    # transit earnings: stopover fees and canal tolls are services, not goods
    passing = sum(r["cargo_stopover"] + 1.8 * r["cargo_canal"] for r in rows)
    # Stopover fees, bunkering and canal tolls. This was 0.18, i.e. 18% of world
    # services exports, which handed eight small hubs 0.64T between them and put
    # Canldives at 1,756% of GDP. That figure was mistakenly taken from transport
    # services' share of world services trade, but that line is overwhelmingly
    # freight earned by every shipping nation, not transit fees earned by
    # chokepoint states. On Earth the entire Suez and Panama toll take is about
    # 0.07% of world exports; 2% of services trade is generous for fees plus
    # bunkering and still leaves these economies visibly rich from shipping.
    transit_pool = target * (1 - GOODS_SHARE) * 0.02
    # CANAL TOLLS ARE NOW MEASURED, NOT SHARED OUT. sea_lanes.py routes every
    # flow along its sea path and sums what passes each cell, so the value
    # transiting a canal is known: 6.09T through the Tiesa Canal on the last
    # run. Suez earns about 0.56% of the cargo value it carries and Panama
    # about 0.96%, so the owner's toll income is that value at CANAL_TOLL_RATE,
    # and its canal cargo leaves the shared pool. The traffic comes from the
    # previous run's flows, one iteration behind; the toll is a fraction of a
    # percent of Emara's services, so the lag cannot move anything visible.
    canal_income = {}
    for canal, owner in CANAL_OWNER.items():
        v = canal_traffic().get(canal, 0.0)
        if v > 0:
            canal_income[owner] = canal_income.get(owner, 0.0) + v * CANAL_TOLL_RATE
    def pool_weight(r):
        canal = 0.0 if r["name"] in canal_income else 1.8 * r["cargo_canal"]
        return r["cargo_stopover"] + canal
    passing = sum(pool_weight(r) for r in rows)
    for r in rows:
        r["svc_transit"] = (transit_pool * pool_weight(r) / passing if passing else 0.0)
        r["svc_canal"] = canal_income.get(r["name"], 0.0)
        r["svc_transit"] += r["svc_canal"]
        r["svc_x"] += r["svc_transit"]
        # An entrepot's stopover fees are added after the export ceiling was
        # applied, so Guise came out at 3.2x GDP in exports and 6.7x in trade
        # (Hong Kong: about 2x and 4x). The fees are cut back to the ceiling.
        cap = HUB_EXPORT_CEILING * r["gdp"]
        over = r["dom_goods_x"] + r["svc_x"] - cap
        if over > 0 and r["svc_transit"] > 0:
            cut = min(over, r["svc_transit"])
            r["svc_transit"] -= cut
            r["svc_x"] -= cut

    # re-exports: carried cargo valued at the world average per unit of own cargo
    shippers = [r for r in rows if r["cargo_own"] > 0]
    own_total = sum(r["cargo_own"] for r in shippers)
    per_unit = (sum(r["dom_goods_x"] for r in shippers) / own_total) if own_total else 0.0
    for r in rows:
        r["reexports"] = r["cargo_carried"] * per_unit
        r["goods_x"] = r["dom_goods_x"] + r["reexports"]
        if r["name"] in BUNKERING:
            bump = r["svc_transit"] * 0.45
            r["goods_x"] += bump
            r["dom_goods_x"] += bump

    # Final normalisation. Transit services, re-exports and the bunkering bump
    # are all added AFTER the openness layer, so without this the world total
    # drifts above the calibrated share of GDP (it reached 31.3% before this
    # was added). Scale every component uniformly so the target holds exactly
    # and no country's composition changes.
    world_x = sum(r["goods_x"] + r["svc_x"] for r in rows)
    k = target / world_x
    for r in rows:
        for key in ("goods_x", "svc_x", "dom_goods_x", "reexports", "svc_transit"):
            r[key] *= k

    # imports from the continuous balance tilt, then forced to balance globally
    svc_scale = sum(r["svc_x"] for r in rows) / sum(r["gdp"] for r in rows)
    for r in rows:
        r["goods_m_raw"] = r["dom_goods_x"] * (1 + r["bal_tilt"]) + r["reexports"]
        # Demand for shipping, insurance and travel scales with the economy, not
        # with whether that economy happens to SELL those services. Indexing
        # imports to a country's own services exports made transit hubs buy back
        # everything they sold and left their hinterland customers buying nothing.
        r["svc_m_raw"] = (0.35 * r["svc_x"] + 0.65 * svc_scale * r["gdp"]) * (1 + r["bal_tilt"] * 0.6)
    # RE-EXPORTS MUST PASS THROUGH UNTAXED. A re-export is the same crate leaving
    # as arrived: it lifts gross exports and gross imports by the identical
    # amount and must leave the balance alone. Previously it was folded into
    # goods_m_raw and then scaled by a factor that differs from the export side,
    # which quietly taxed the pass-through at about 19% and gave every hub a
    # fictitious deficit - Merela Sta netted -71bn on 247bn of re-exports.
    # So the rescale is applied only to the DOMESTIC part, and re-exports are
    # added back to both sides afterwards, untouched.
    dom_x = sum(r["goods_x"] - r["reexports"] for r in rows)
    dom_m_raw = sum(r["goods_m_raw"] - r["reexports"] for r in rows)
    gs = dom_x / dom_m_raw if dom_m_raw else 1.0
    ss = sum(r["svc_x"] for r in rows) / sum(r["svc_m_raw"] for r in rows)
    for r in rows:
        r["goods_m"] = (r["goods_m_raw"] - r["reexports"]) * gs + r["reexports"]
        r["svc_m"] = r["svc_m_raw"] * ss
        r["total_x"] = r["goods_x"] + r["svc_x"]

    # CAP THE IMBALANCE. No economy sustains a surplus much beyond a quarter of
    # its GDP; the Gulf petrostates at peak oil are the ceiling, and the deficit
    # side is tighter still because someone has to lend you the difference.
    # Uncapped, a transshipment state earned fees worth several times its tiny
    # GDP and bought almost nothing back: Guise came out at +155% of GDP, which
    # is not a trade balance, it is an accounting artefact of a large fee income
    # divided by a very small economy. Excess is returned as imports, which is
    # what such a place actually does with the money.
    # THE BALANCE IS SCALED TO GDP, NOT TO TRADE VOLUME.
    #
    # A trade balance is a macroeconomic quantity - what a country saves less
    # what it invests - so it belongs in proportion to the economy, not to gross
    # trade. Deriving it from exports instead meant a transit hub trading at 400%
    # of GDP turned a modest tilt into an enormous balance: Guise reached +155%
    # of GDP. Capping that merely moved the problem, bunching two dozen countries
    # exactly on the ceiling. Anchoring the target to GDP removes the artefact at
    # source, and the cap goes back to being a rarely-touched backstop.
    # Every country's target balance is set from its own tilt, then the whole set
    # is CENTRED so the targets sum to zero before anything is applied. Setting a
    # target for all 172 and correcting afterwards over-determines the system:
    # the targets do not naturally sum to zero, and forcing the residual through
    # whichever countries were left uncapped threw individual balances as far as
    # -344% of GDP. Centring first means the world's books balance by
    # construction and each country keeps its intended position in the spread.
    # Entrepots keep a MARGIN on everything they clear. A gateway port does not
    # simply pass crates through at cost: it finances, insures, stores, breaks
    # bulk and re-labels, and books the spread. That is why the Netherlands,
    # Belgium and Singapore run trade SURPLUSES on enormous re-export volumes.
    # Without this the model gave them the opposite, a mild deficit, purely
    # because they have no resource endowment to earn a surplus tilt from.
    want = {}
    for r in rows:
        base = (-r["bal_tilt"] * BAL_TO_GDP) * r["gdp"] if r["gdp"] else 0.0
        want[r["name"]] = base + REEXPORT_MARGIN * r["reexports"]
        pin = tb.CANON_BALANCE.get(r["name"])
        if pin is not None and r["gdp"]:
            want[r["name"]] = pin * r["gdp"]
    total_gdp = sum(r["gdp"] for r in rows)
    drift = sum(want.values()) / total_gdp
    for _ in range(8):
        for r in rows:
            v = want[r["name"]] / r["gdp"] - drift if r["gdp"] else 0.0
            # a surplus is also capped against EXPORTS: a poor, resource-heavy
            # country with exports of 17% of GDP was handed a 20%-of-GDP
            # surplus, i.e. negative imports (Jau, Taniduna). No economy keeps
            # more than about BAL_CAP_OF_EXPORTS of what it earns abroad.
            cap_s = min(BAL_CAP_SURPLUS, BAL_CAP_OF_EXPORTS * r["total_x"] / r["gdp"]) if r["gdp"] else 0.0
            want[r["name"]] = max(-BAL_CAP_DEFICIT, min(cap_s, v)) * r["gdp"]
        residual = sum(want.values())
        if abs(residual) < 1e-3:
            break
        drift = residual / total_gdp
    for r in rows:
        bal = r["total_x"] - r["goods_m"] - r["svc_m"]
        r["goods_m"] += bal - want[r["name"]]
        r["balance_capped"] = r["gdp"] > 0 and abs(
            want[r["name"]] / r["gdp"]) >= min(BAL_CAP_SURPLUS, BAL_CAP_DEFICIT) - 1e-9

    for r in rows:
        r["total_m"] = r["goods_m"] + r["svc_m"]
        r["balance"] = r["total_x"] - r["total_m"]
        r["trade_gdp"] = (r["total_x"] + r["total_m"]) / r["gdp"] if r["gdp"] else 0.0
        # Domestic value added now nets off the imported inputs embodied in
        # exports as well as the re-exports passing straight through. Before, the
        # only thing that could pull a country below 100% was being a transit
        # hub.
        fc = r.get("foreign_content", 0.0)
        r["dva_share"] = (r["dom_goods_x"] * (1.0 - fc) / r["goods_x"]) if r["goods_x"] else 1.0
        # what the finished model implies, as opposed to the raw regression
        # value before the port lift, the ceiling and the normalisations
        r["openness_realised"] = r["total_x"] / r["gdp"] if r["gdp"] else 0.0
        # IPF scales rows and columns by target/current, so a NEGATIVE target
        # flips the sign of every flow in that row or column and the bilateral
        # matrix stops meaning anything. goods_m can go negative when the
        # balance cap pushes a large surplus down past a country's whole import
        # bill. Clamping to a floor keeps the matrix well formed; the floor is
        # tiny relative to any real economy, so it binds only in that pathology.
        r["exports_goods_target"] = max(r["goods_x"], 1.0)
        r["imports_goods_target"] = max(r["goods_m"], 1.0)
        if r["goods_m"] < 0 or r["goods_x"] < 0:
            r["negative_target"] = True

    # ---- export baskets, BEFORE gravity: complementarity is built from them ----
    build_baskets(rows)                       # concentration targets
    world_commodity_trade = target * GOODS_SHARE * COMMODITY_SHARE_OF_GOODS
    # Hand edits belong to 1765. Applying them to a backcast year would assert a
    # country made the same things in 1725, which is the opposite of what
    # backcasting is for: at 1725 incomes the profile should show far more
    # agriculture and textiles and far less electronics, as every real economy's
    # history does.
    edited, edit_notes = (tb.read_edited_baskets(OUT) if year == YEAR else ({}, {}))
    evidence = data.get("wiki_evidence") or {}
    finance = data.get("financial_centres") or {}
    for r in rows:
        r["finance_weight"] = finance.get(r["name"], 0.0)
        r["basket_default"] = tb.default_basket(
            r, r.get("commodity_mix") or {}, world_commodity_trade,
            evidence.get(r["name"]), finance_weight=r["finance_weight"])
        r["basket"] = edited.get(r["name"], r["basket_default"])
        r["basket_edited"] = r["name"] in edited
        r["basket_edit_note"] = edit_notes.get(r["name"], "")
    # the world's own mix, value-weighted over domestic exports
    dom = {r["name"]: r["dom_goods_x"] + r["svc_x"] for r in rows}
    tot_dom = sum(dom.values()) or 1.0
    world_mix = {k: sum(r["basket"][k] * dom[r["name"]] for r in rows) / tot_dom for k in tb.KEYS}
    # THE WORLD'S MANUFACTURING MIX IS EARTH'S. The income profiles gave every
    # rich country a German machinery share and a thin chemicals one, and the
    # sum came out as a world that shipped 16% of its trade as machinery
    # (Earth: 8%) and 4% as chemicals (Earth: 12%), so no product's share of
    # world trade could be compared with Earth's. The eight manufacturing
    # columns are rescaled to Earth's relative shares (earth_products.EARTH_MIX)
    # with every country's manufacturing total held fixed, by iterative
    # proportional fitting: a country's mix keeps its own tilt (a chip-maker
    # stays a chip-maker, twice as much so as the world), only the level of
    # each category moves with the world's. Resource categories come from the
    # production tables and services from their own calibration; neither is
    # touched. Canon pins in trade_baskets.CANON_BASKETS are pre-bend values.
    import earth_products as _EP
    manuf = list(tb.MANUF)
    esum = sum(_EP.EARTH_MIX[k] for k in manuf)
    mw = sum(r["basket"][k] * dom[r["name"]] for r in rows for k in manuf)
    tgt = {k: mw * _EP.EARTH_MIX[k] / esum for k in manuf}
    Xm = {r["name"]: {k: r["basket"][k] * dom[r["name"]] for k in manuf} for r in rows}
    Rm = {nm: sum(v.values()) for nm, v in Xm.items()}
    # Canon pins (trade_baskets.CANON_BASKETS) are statements about what a
    # country's exports look like, so they hold through the bend: a pinned
    # cell is fixed and only the unpinned cells of its row and column move.
    # A hand-edited row is treated as unpinned and bent like the rest.
    pinned = {(r["name"], k) for r in rows if not r.get("basket_edited")
              for k in (tb.CANON_BASKETS.get(r["name"]) or {}) if k in manuf}
    pin_col = {k: sum(Xm[nm][k] for nm in Xm if (nm, k) in pinned) for k in manuf}
    pin_row = {nm: sum(Xm[nm][k] for k in manuf if (nm, k) in pinned) for nm in Xm}
    for k in manuf:
        if pin_col[k] > 0.9 * tgt[k]:
            print(f"  WARNING: canon pins hold {pin_col[k] / tgt[k]:.0%} of the world's {k}; "
                  f"the bend cannot reach Earth's share")
    for _ in range(80):
        for k in manuf:
            col = sum(Xm[nm][k] for nm in Xm if (nm, k) not in pinned)
            want = tgt[k] - pin_col[k]
            if col > 0 and want > 0:
                f = want / col
                for nm in Xm:
                    if (nm, k) not in pinned:
                        Xm[nm][k] *= f
        for nm in Xm:
            sm = sum(Xm[nm][k] for k in manuf if (nm, k) not in pinned)
            want = Rm[nm] - pin_row[nm]
            if sm > 0 and want > 0:
                f = want / sm
                for k in manuf:
                    if (nm, k) not in pinned:
                        Xm[nm][k] *= f
    # champions (see CHAMPION_BANDS): set on the bent baskets, then held fixed
    # while the mix is bent again so the world total stays Earth's
    bent = {nm: {k: (Xm[nm][k] / dom[nm] if dom[nm] > 0 else 0.0) for k in manuf} for nm in Xm}
    for r in rows:
        for k in tb.KEYS:
            if k not in manuf:
                bent[r["name"]][k] = r["basket"][k]
    # the assignment is made once, in the base year, and reused for the
    # backcast years: a country's industrial identity does not flip between
    # 1725 and 1765
    if data.get("champions") is None:
        data["champions"] = assign_champions(rows, data, bent,
                                             {r["name"] for r in rows if tb.CANON_BASKETS.get(r["name"])})
    champions = {nm: k for nm, k in data["champions"].items() if nm in Xm}
    want_cell = {}
    for nm, k in champions.items():
        v = Xm[nm]
        others = max((v[j] for j in manuf if j != k), default=0.0)
        # the cap varies with how strongly the country scored for its
        # champion, so seven countries do not all print exactly 30%
        z = (data.get("champion_score") or {}).get(nm, 0.0)
        cap = CHAMPION_CAP * max(0.80, min(1.18, 0.95 + 0.10 * z))
        target = min(cap * dom[nm], CHAMPION_WORLD_CAP * tgt[k], max(v[k], CHAMPION_LEAD * others))
        if target > v[k]:
            want_cell[(nm, k)] = target
    # if a category's pins plus champions would exceed the fill line, scale the
    # champions of that category down together so the rest of the world keeps
    # a share of it (nobody's cars go to zero)
    for k in manuf:
        fixed = sum(Xm[nm][k] for nm in Xm if (nm, k) in pinned)
        asked = sum(t for (nm, kk), t in want_cell.items() if kk == k)
        room = CHAMPION_COLUMN_FILL * tgt[k] - fixed
        if asked > room > 0:
            f = room / asked
            for key in list(want_cell):
                if key[1] == k:
                    want_cell[key] = max(Xm[key[0]][k], want_cell[key] * f)
    for (nm, k), target in want_cell.items():
        v = Xm[nm]
        delta = target - v[k]
        rest = sum(v[j] for j in manuf if j != k)
        if delta <= 0 or rest <= delta:
            continue
        for j in manuf:
            if j != k:
                v[j] *= (rest - delta) / rest
        v[k] = target
        pinned.add((nm, k))
    for r in rows:
        r["champion"] = champions.get(r["name"], "")
    pin_col = {k: sum(Xm[nm][k] for nm in Xm if (nm, k) in pinned) for k in manuf}
    pin_row = {nm: sum(Xm[nm][k] for k in manuf if (nm, k) in pinned) for nm in Xm}
    for k in manuf:
        if pin_col[k] > 0.9 * tgt[k]:
            print(f"  WARNING: pins and champions hold {pin_col[k] / tgt[k]:.0%} of the world's {k}")
    for _ in range(80):
        for k in manuf:
            col = sum(Xm[nm][k] for nm in Xm if (nm, k) not in pinned)
            want = tgt[k] - pin_col[k]
            if col > 0 and want > 0:
                f = want / col
                for nm in Xm:
                    if (nm, k) not in pinned:
                        Xm[nm][k] *= f
        for nm in Xm:
            sm = sum(Xm[nm][k] for k in manuf if (nm, k) not in pinned)
            want = Rm[nm] - pin_row[nm]
            if sm > 0 and want > 0:
                f = want / sm
                for k in manuf:
                    if (nm, k) not in pinned:
                        Xm[nm][k] *= f
    print(f"  champions: {len(champions)} countries; "
          + ", ".join(f"{k} {sum(1 for v in champions.values() if v == k)}"
                      for k in ("vehicles", "machinery", "electronics", "chemicals", "textiles")))
    # Category-level shaping toward Earth's concentration curves was tried
    # here and removed: Andah's four giants are 48% of world trade where
    # Earth's top four are 34%, so they must hold more of every category than
    # Earth's leaders, and bending the categories only shoved their mass into
    # whichever categories were not bent. Product shapes inside a category are
    # fitted in export_trade_json instead.
    world_mix_before = dict(world_mix)
    for r in rows:
        nm = r["name"]
        # the basket as it stood before the bend: this is what the editable
        # sheet stores, so a hand edit is compared against the same thing it
        # was written over and the bend is never applied to its own output
        r["basket_pre"] = dict(r["basket"])
        if dom[nm] > 0 and Rm[nm] > 0:
            b = dict(r["basket"])          # never mutate basket_default in place
            for k in manuf:
                b[k] = Xm[nm][k] / dom[nm]
            r["basket"] = b
    world_mix = {k: sum(r["basket"][k] * dom[r["name"]] for r in rows) / tot_dom for k in tb.KEYS}
    # IMPORT DEMAND IS TWO APPETITES, NOT ONE. What a country consumes, and what
    # it must buy in order to make what it sells. Without the second, every
    # export was treated as made from nothing: 167 of 172 countries came out at
    # exactly 100% domestic value added, which no real economy achieves.
    gdps = sorted(r["gdp"] for r in rows)
    median_gdp = gdps[len(gdps) // 2]
    for r in rows:
        r["domestic_x"] = max(r["dom_goods_x"] + r["svc_x"], 0.0)
        mult = tb.size_factor(r["gdp"], median_gdp)
        r["size_factor"] = mult
        r["import_demand"], r["foreign_content"] = tb.blended_demand(
            r["basket"], world_mix, r["domestic_x"], r["total_m"], mult)
        r["intermediate_m"] = r["domestic_x"] * r["foreign_content"]
        # dva_share was set upstream, before the foreign content existed; restate
        # it now that it does, so the workbook and the atlas agree
        r["dva_share"] = ((r["dom_goods_x"] * (1.0 - r["foreign_content"]) / r["goods_x"])
                          if r["goods_x"] else 1.0)
    by_name = {r["name"]: r for r in rows}
    comp = {}
    for a in by_name:
        for b in by_name:
            if a != b:
                comp[(a, b)] = tb.complementarity(by_name[a]["basket"],
                                                  by_name[b]["import_demand"], world_mix)

    # ---- global reach: size-scaled defaults, overridden per country in the workbook
    reach_sheet = tb.read_reach(OUT)
    max_x = max(r["total_x"] for r in rows) or 1.0
    max_fin = max((r["finance_weight"] for r in rows), default=0.0) or 1.0
    for r in rows:
        # the exponent keeps the dial biting on the large exporters and leaves
        # the rest of the world at effectively 1.0
        share = r["total_x"] / max_x
        base = 1.0 + REACH_SIZE * share ** REACH_EXP
        base += REACH_FINANCE * math.sqrt(r["finance_weight"] / max_fin)
        r["reach_default"] = base
        r["reach"] = reach_sheet.get(r["name"], r["reach_default"])
        r["reach_edited"] = r["name"] in reach_sheet
    reach = {r["name"]: r["reach"] for r in rows}

    # gravity, reconciled
    theta, contig, fitr, fitn = validate_gravity(rows, straight, data["geo"],
                                                 data["flights"], verbose=fit_verbose)
    blocs = data.get("blocs") or {}
    flows, flows_by_cat = category_flows(
        rows, dist, data["geo"], theta, contig,
        SAME_CONTINENT * REGIONAL_MULT, SAME_SUBREGION * REGIONAL_MULT,
        reach=reach, blocs=blocs, world_mix=world_mix, verbose=fit_verbose)
    # the matrix now covers services as well as goods, so it answers to the
    # TOTAL margins rather than the goods-only ones it used to
    got_x = collections.defaultdict(float)
    got_m = collections.defaultdict(float)
    for (a, b), v in flows.items():
        got_x[a] += v
        got_m[b] += v
    err_x = max(abs(got_x[r["name"]] - r["total_x"]) / max(r["total_x"], 1.0) for r in rows)
    err_m = max(abs(got_m[r["name"]] - r["total_m"]) / max(r["total_m"], 1.0) for r in rows)
    # the AUC deliberately scores the BASE structure, without complementarity or
    # reach, so it keeps measuring the same thing it always did
    auc, n_linked, n_unlinked = gravity_auc(rows, straight, data["geo"], data["flights"])

    name_leading_exports(rows, world_commodity_trade)
    for r in rows:
        r["label"] = describe(r)
    world_mix_out = world_mix

    # top partners straight off the reconciled matrix
    out_by = collections.defaultdict(list)
    in_by = collections.defaultdict(list)
    for (a, b), v in flows.items():
        out_by[a].append((b, v))
        in_by[b].append((a, v))
    for r in rows:
        n = r["name"]
        r["top_export_partners"] = sorted(out_by[n], key=lambda x: -x[1])[:5]
        r["top_import_partners"] = sorted(in_by[n], key=lambda x: -x[1])[:5]

    for key in ("total_x", "total_m", "goods_x"):
        for rank, r in enumerate(sorted(rows, key=lambda x: -x[key]), 1):
            r[key + "_rank"] = rank

    meta = dict(flows_by_cat=flows_by_cat,
                world_gdp=world_gdp, theta=theta, contig=contig, fit_r=fitr,
                fit_n=fitn, gravity_auc=auc, auc_linked=n_linked,
                auc_unlinked=n_unlinked, ipf_err_x=err_x, ipf_err_m=err_m,
                year=year, dist=straight, sea_dist=dist, sea_routing=sea_on,
                flows=flows, world_mix=world_mix_out, world_mix_before=world_mix_before,
                baskets_edited=sum(1 for r in rows if r.get("basket_edited")),
                reach_edited=sum(1 for r in rows if r.get("reach_edited")),
                lahn_ratio=ad.LAHN_STATE.get("ratio"))
    return rows, flows, meta


# ---------------------------------------------------------------------------
# validation against Earth 2015
# ---------------------------------------------------------------------------

EARTH_2015 = dict(
    world_gdp=75.0e12, world_exports=21.3e12, services_share=0.225,
    median_trade_gdp=0.80, share_over_100pct=0.33,
    top_exporters=[2560, 2259, 1600, 802, 783, 746, 729, 625, 615, 559,
                   504, 491, 490, 423, 411, 406, 404, 393, 360, 326],
    giant_ratio=0.82,      # China: export share / GDP share
    second_ratio=0.44,     # United States
    landlocked_penalty=0.30,
)


def earth_comparison(rows, meta):
    """
    Measure Andah's SHAPE against Earth 2015. Every metric is a ratio or a share,
    so nothing here imports Earth's size; it only asks whether the distribution
    is the sort a real world produces.
    """
    E = EARTH_2015
    wx = sum(r["total_x"] for r in rows)
    wg = meta["world_gdp"]
    ranked = sorted(rows, key=lambda r: -r["total_x"])
    by_gdp = sorted(rows, key=lambda r: -r["gdp"])

    def a_share(n):
        return sum(r["total_x"] for r in ranked[:n]) / wx

    def e_share(n):
        return sum(E["top_exporters"][:n]) * 1e9 / E["world_exports"]

    tg = sorted(r["trade_gdp"] for r in rows)
    med_tg = tg[len(tg) // 2]
    over100 = sum(1 for v in tg if v > 1.0) / len(tg)
    g0, g1 = by_gdp[0], by_gdp[1]
    # Landlocked penalty, measured CONDITIONALLY.
    #
    # A raw landlocked-vs-coastal mean is worthless here: Andah's landlocked
    # countries have a median GDP per capita of about 1,200 against 7,400 for
    # coastal ones, so a naive comparison reports a ~53% penalty that is almost
    # entirely the income gap. Earth's ~30% figure is a regression coefficient
    # holding size and income fixed, so the like-for-like comparison is the only
    # one that can be set beside it: each landlocked country against coastal
    # peers of similar population AND similar income.
    ll = [r for r in rows if r["landlocked"]]
    cs = [r for r in rows if not r["landlocked"]]
    ratios = []
    for r in ll:
        peers = [c["trade_gdp"] for c in cs
                 if 0.5 <= c["population"] / max(r["population"], 1) <= 2.0
                 and 0.5 <= c["gdp_pc"] / max(r["gdp_pc"], 1) <= 2.0]
        if len(peers) >= 3:
            peers.sort()
            med_peer = peers[len(peers) // 2]
            if med_peer > 0:
                ratios.append(r["trade_gdp"] / med_peer)
    if ratios:
        ratios.sort()
        ll_pen = 1 - ratios[len(ratios) // 2]
    else:
        ll_pen = 0.0

    dvas = sorted(r.get("dva_share", 1.0) for r in rows)
    med_dva = dvas[len(dvas) // 2]

    flows_ = meta.get("flows") or {}
    dist_ = meta.get("dist") or {}
    if flows_:
        cont = {r["name"]: r["continent"] for r in rows}
        tot_f = sum(flows_.values()) or 1.0
        intra = sum(v for (a, b), v in flows_.items() if cont[a] == cont[b]) / tot_f
    else:
        intra = 0.57

    # ---- STRUCTURE OF THE FLOW MATRIX ------------------------------------
    #
    # Everything above this point tests totals: how much each country trades and
    # how concentrated the league table is. Only the intra-continent share tests
    # WHO TRADES WITH WHOM, and that is a single number covering 29,000 pairs.
    #
    # That blind spot is not hypothetical. The giants were once the largest
    # partner of 24 of the 25 countries on their own continent and of almost
    # nobody beyond it, and all sixteen checks passed while it was true. It was
    # caught by eye, not by the model. These four measure the matrix itself.
    trade_km = off_cont = xm_split = bal_disp = None
    if flows_:
        def d_of(a, b):
            return dist_.get((a, b)) or dist_.get((b, a)) or 0.0

        # 1. HOW FAR TRADE TRAVELS. A world whose distance decay is too steep
        #    still balances to the right totals; it just trades with the wrong
        #    people. Earth 2015 averages roughly 4,900 km per unit of exports.
        num = sum(v * d_of(a, b) for (a, b), v in flows_.items())
        trade_km = num / tot_f

        sells, buys = collections.defaultdict(dict), collections.defaultdict(dict)
        for (a, b), v in flows_.items():
            sells[a][b] = sells[a].get(b, 0.0) + v
            buys[b][a] = buys[b].get(a, 0.0) + v

        def top(dd):
            return max(dd, key=dd.get) if dd else None

        names_ = [r["name"] for r in rows]
        # 2. DO HUBS CROSS CONTINENTS? On Earth about half of all countries have
        #    a largest partner on another continent, because China is top partner
        #    across four at once. A world of continental spheres scores near zero.
        both = {a: {k: sells[a].get(k, 0.0) + buys[a].get(k, 0.0)
                    for k in set(sells[a]) | set(buys[a])} for a in names_}
        lead_t = {a: top(both[a]) for a in names_}
        off_cont = (sum(1 for a in names_ if lead_t[a] and cont[lead_t[a]] != cont[a])
                    / max(len(names_), 1))

        # 3. IS THE BIGGEST CUSTOMER ALSO THE BIGGEST SUPPLIER? Usually not:
        #    Japan sells to the United States and buys from China, and so do
        #    Germany, the UK, India, Vietnam, Russia and Turkey. When this sits
        #    near zero the exporters are interchangeable and only distance is
        #    deciding, which is what identical export baskets produce.
        xm_split = (sum(1 for a in names_ if top(sells[a]) != top(buys[a]))
                    / max(len(names_), 1))

        # 4. ARE PAIRS LOPSIDED? Trade between two countries rarely balances:
        #    the US-China gap is 0.65 of the pair's total, and a typical Earth
        #    pair runs 0.25-0.40. Reconciling to each country's totals does not
        #    by itself produce that, and a matrix that is too symmetric says no
        #    one runs a deficit with anyone in particular.
        gaps = []
        for a in names_:
            for b, x in sells[a].items():
                if a < b:
                    mm = sells.get(b, {}).get(a, 0.0)
                    if x + mm > 0:
                        gaps.append(abs(x - mm) / (x + mm))
        gaps.sort()
        bal_disp = gaps[len(gaps) // 2] if gaps else 0.0

    m = [
        ("World exports / world GDP", wx / wg, E["world_exports"] / E["world_gdp"], 0.04,
         "overall globalisation"),
        ("Services share of exports", sum(r["svc_x"] for r in rows) / wx, E["services_share"], 0.06,
         "invisibles vs merchandise"),
        ("Top exporter share", a_share(1), e_share(1), 0.05, "concentration at the very top"),
        ("Top 5 share", a_share(5), e_share(5), 0.09, "dominance by a few giants"),
        ("Top 10 share", a_share(10), e_share(10), 0.10, "same test one tier down"),
        ("Top 20 share", a_share(20), e_share(20), 0.10, "across the leading group"),
        ("Largest economy: export/GDP share", (g0["total_x"] / wx) / (g0["gdp"] / wg),
         E["giant_ratio"], 0.30, "KEY: giants export BELOW their weight"),
        ("Second economy: export/GDP share", (g1["total_x"] / wx) / (g1["gdp"] / wg),
         E["second_ratio"], 0.55, "the least trade-dependent giant"),
        ("Median trade / GDP", med_tg, E["median_trade_gdp"], 0.30, "the typical country"),
        ("Countries trading >100% of GDP", over100, E["share_over_100pct"], 0.18,
         "how common extreme openness is"),
        ("Landlocked trade penalty", ll_pen, E["landlocked_penalty"], 0.22,
         "landlocked states trade ~30% less on Earth"),
        ("99th percentile trade / GDP", tg[int(0.99 * (len(tg) - 1))], 4.00, 1.60,
         "constrains the TAIL. Earth's most open economies (Hong Kong, Singapore, "
         "Luxembourg) reach 3-4x GDP; nothing previously stopped a country at 17x"),
        ("Most open economy, trade / GDP", tg[-1], 4.40, 3.00,
         "the single most extreme country in the world"),
        ("Intra-continent share of world trade", intra, 0.57, 0.12,
         "Earth 2015 ~57% (Europe 68%, Asia 58%, Africa 18%). Tracks whether partners are too regional"),
        ("Mean distance per unit of exports (km)", trade_km if trade_km is not None else 4900.0,
         4900.0, 1800.0,
         "Earth 2015 ~4,900 km. Too low means distance decay is overwhelming the basket match"),
        ("Top partner on another continent", off_cont if off_cont is not None else 0.50,
         0.50, 0.22,
         "Earth ~50%: China is largest partner across four continents. Near zero means "
         "each continent has collapsed onto its own resident giant"),
        ("Biggest customer is not biggest supplier", xm_split if xm_split is not None else 0.45,
         0.45, 0.22,
         "Earth ~45%: Japan sells to the US and buys from China. Near zero means the big "
         "exporters are interchangeable and only distance is choosing between them"),
        ("Bilateral imbalance, median pair", bal_disp if bal_disp is not None else 0.32,
         0.32, 0.18,
         "Earth: US-China 0.65, a typical pair 0.25-0.40. Low means no pair runs a "
         "structural surplus with another, only each country against the world"),
        ("Median domestic value added in exports", med_dva, 0.78, 0.12,
         "Earth: Singapore 42%, Mexico 55%, Korea 63%, Germany 73%, China 83%, US 88%. "
         "Nobody reaches 100%: every country buys inputs. 167 of 172 sat at exactly "
         "100% before the intermediate-goods layer existed"),
        ("Largest surplus / world GDP", max(r["balance"] for r in rows) / wg, 0.0045, 0.004,
         "Earth: China, ~0.45%"),
        ("Largest deficit / world GDP", min(r["balance"] for r in rows) / wg, -0.0061, 0.005,
         "Earth: the United States, ~-0.6%"),
    ]

    def verdict(a, e, tol):
        return "realistic" if abs(a - e) <= tol else ("TOO HIGH" if a > e else "TOO LOW")
    return m, verdict


# ---------------------------------------------------------------------------
# benchmark years
# ---------------------------------------------------------------------------

# World trade as a share of world GDP, by year. Andah's 1765 is Earth's 2015
# (confirmed by DJ's own population series carrying both year columns), so the
# earlier benchmarks take Earth's actual globalisation path: trade was about 17%
# of world output in 1975 and 21% in 1995. Without this the model would imply
# 1725 was as globalised as 1765, which no shipping technology supports.
OPENNESS_BY_YEAR = {1725: 0.170, 1745: 0.210, 1765: 0.285}


def run_year(data, year):
    """
    Re-run the whole model for an earlier benchmark year.

    Population comes from DJ's series and GDP per capita is walked back through
    his own annual growth rates, so the earlier world is his history rather than
    invented here. Only the world openness level is externally set, because that
    is a fact about shipping technology rather than about any one country.
    """
    global WORLD_OPENNESS
    hist = ad.backcast_gdp(data["countries"], data["pophist"], data["growth"], [year])
    scaled = {}
    for name, c in data["countries"].items():
        rec = hist.get(name, {}).get(year)
        if not rec or rec["gdp"] <= 0:
            continue
        d = dict(c)
        d.update(population=rec["population"], gdp=rec["gdp"], gdp_pc=rec["gdp_pc"])
        scaled[name] = d
    if len(scaled) < 100:
        return None, None, None
    sub = dict(data)
    sub["countries"] = scaled
    saved = WORLD_OPENNESS
    try:
        if year not in OPENNESS_BY_YEAR:
            raise SystemExit(
                f"No globalisation level defined for {year}. Add it to "
                f"OPENNESS_BY_YEAR; running it at 1765's level would silently "
                f"imply that year was as globalised as the present.")
        WORLD_OPENNESS = OPENNESS_BY_YEAR[year]
        rows, flows, meta = run(sub, year=year)
    finally:
        WORLD_OPENNESS = saved
    return rows, flows, meta


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--years", nargs="*", type=int, default=BENCHMARK_YEARS)
    args = ap.parse_args()

    data = ad.load_all()
    rows, flows, meta = run(data, fit_verbose=args.fit)
    T = 1e12

    if args.fit:
        print(f"\nBEST FIT: theta={meta['theta']}  contiguity={meta['contig']}  r={meta['fit_r']:+.4f}")
        print(f"IPF convergence: max row error {meta['ipf_err_x']:.2e}, col {meta['ipf_err_m']:.2e}")
        return

    if args.compare:
        m, verdict = earth_comparison(rows, meta)
        print(f"{'METRIC':<38}{'ANDAH':>9}{'EARTH 2015':>12}   VERDICT")
        print("-" * 82)
        for label, a, e, tol, _n in m:
            print(f"{label:<38}{a:>9.3f}{e:>12.3f}   {verdict(a, e, tol)}")
        bad = [x[0] for x in m if verdict(x[1], x[2], x[3]) != "realistic"]
        print(f"\n{len(m)-len(bad)}/{len(m)} realistic" + (f"; off: {bad}" if bad else ""))
        return

    year_runs = {}
    for y in args.years:
        if y == YEAR:
            year_runs[y] = (rows, meta)
        else:
            yr, yf, ym = run_year(data, y)
            year_runs[y] = (yr, ym) if yr else None

    import trade_workbook
    path = trade_workbook.write(OUT, rows, flows, meta, data, year_runs,
                                earth_comparison(rows, meta))

    wx = sum(r["total_x"] for r in rows)
    print(f"World GDP {meta['world_gdp']/T:,.1f}T  exports {wx/T:,.1f}T "
          f"({wx/meta['world_gdp']:.1%} of GDP)  imports {sum(r['total_m'] for r in rows)/T:,.1f}T")
    print(f"gravity theta={meta['theta']} (literature). Link prediction over "
          f"{meta['auc_linked'] + meta['auc_unlinked']:,} pairs: AUC={meta['gravity_auc']:.3f} "
          f"(chance 0.5); intensive-margin r={meta['fit_r']:+.3f}")
    print()
    print(f"{'#':>3} {'COUNTRY':<15}{'EXPORTS':>9}{'IMPORTS':>9}{'BAL':>8}{'TR/GDP':>8}"
          f"{'DVA':>5}{'TOP%':>6}  {'LABEL':<26}TOP PARTNER")
    print("-" * 118)
    for i, r in enumerate(sorted(rows, key=lambda x: -x["total_x"])[:25], 1):
        tp = r["top_export_partners"][0][0] if r["top_export_partners"] else ""
        print(f"{i:>3} {r['name']:<15}{r['total_x']/T:>8.2f}T{r['total_m']/T:>8.2f}T"
              f"{r['balance']/T:>7.2f}T{r['trade_gdp']:>7.0%}{r['dva_share']:>5.0%}"
              f"{r['top_export_share']:>6.0%}  {r['label']:<26}{tp}")
    print()
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
