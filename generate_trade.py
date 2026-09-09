#!/usr/bin/env python3
"""
generate_trade.py - builds data/Andah_Trade_Statistics.xlsx

A seeded, reproducible model of Andah's merchandise and services trade for 1765,
built the same way as Andah_KTDI_Model.xlsx: real inputs from the other data/
spreadsheets, a home-made seeded LCG for character, and editable override columns
so nothing the model decides is final.

WHAT IT READS
  data/Andah_Janus Statistics.xlsx   Geoscheme sheet: continent, subregion,
                                     population, area, GDP nominal, GDP per capita
                                     for all 172 countries (100% coverage).
  data/Top 60 Container Ports.xlsx   port, country, region, location, cargo.
  data/Production Statistics.xlsx    34 commodity sheets, per-country output.
  data/Oil_Gas Statistics.xlsx       oil and gas production.

WHAT IT WRITES
  data/Andah_Trade_Statistics.xlsx   README / Config / Archetypes / Transit /
                                     Commodities / Trade Model / Validation

THE CENTRAL IDEA
  Container throughput is not one signal, it is four, and they do not all become
  goods exports:

    own trade          -> the country's own goods exports
    hinterland transit -> re-exports (inflate gross exports AND imports, so the
                          balance is untouched and domestic value added is low).
                          This is the Rotterdam effect: Merela Sta carries
                          Verusan, Palinan and Yaxutan cargo.
    stopover           -> services exports (port fees, bunkering). Boxes change
                          ship and never enter the economy, so Guise and
                          Canldives earn hard currency without gatecrashing the
                          merchandise table.
    canal toll         -> services exports. Alubri City on the Tiesa Canal.

  A hinterland country is not punished for having no port of its own: the cargo
  it routes through a hub is credited back to its effective throughput. That is
  why Lycroa, the 8th largest economy with nothing in the top 60, still reads as
  a serious trading nation.

Usage:
  python generate_trade.py                 build with the default seed
  python generate_trade.py --seed 4242     re-roll the whole world
  python generate_trade.py --summary       print the top 25 and exit
"""

import argparse
import collections
import os
import sys

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(DATA, "Andah_Trade_Statistics.xlsx")

JANUS = os.path.join(DATA, "Andah_Janus Statistics.xlsx")
PORTS = os.path.join(DATA, "Top 60 Container Ports.xlsx")
PRODUCTION = os.path.join(DATA, "Production Statistics.xlsx")
OILGAS = os.path.join(DATA, "Oil_Gas Statistics.xlsx")

YEAR = 1765
DEFAULT_SEED = 1765
DICE_STRENGTH = 0.15          # +/- 15% of character on top of the structural model
# Exponent on relative GDP: more negative means giants trade proportionally less.
# Not guessed. Swept against the twelve Earth 2015 shape metrics in the Earth 2015
# sheet, minimising total deviation; -0.30 is a clean minimum (3.15 against 4.78
# at -0.22 and 3.93 at -0.34). It is what makes the largest economy export
# slightly BELOW its GDP share, as every real giant does.
SIZE_DAMPING = -0.30
WORLD_OPENNESS = 0.285        # world exports as a share of world GDP (2015 Earth)
GOODS_SHARE = 0.78            # of that, the merchandise portion (2015 Earth)
COMMODITY_SHARE_OF_GOODS = 0.25   # how much of world merchandise trade is raw commodities

# Summary sheets in Production Statistics.xlsx that hold no per-country output.
SUMMARY_SHEETS = {"Fossil fuels", "Nuclear fuel", "Gemstones", "Metals", "Mineral"}

# Each commodity's share of world commodity trade by value. Unit-free on purpose:
# the production sheets record inconsistent units (gold in tonnes, aluminium and
# iron ore look like thousand tonnes), so absolute prices would be a trap. These
# are shares and are normalised, so only their relative size matters. Editable in
# the Commodities sheet.
COMMODITY_WEIGHTS = {
    "Oil": 40.0, "Natural Gas": 12.0, "Coal": 7.0, "Iron": 7.0, "Copper": 7.0,
    "Gold": 6.0, "Aluminium": 4.0, "Motor vehicle": 3.5, "Nickel": 2.0,
    "Silver": 1.6, "Zinc": 1.5, "Paper": 1.4, "Platinum": 1.2, "Diamond": 1.2,
    "Lead": 1.0, "Tin": 0.9, "Uranium": 0.8, "Lithium": 0.8, "Palladium": 0.7,
    "Manganese": 0.6, "Titanium": 0.6, "Cobalt": 0.6, "Chromium": 0.5,
    "Magnesium": 0.4, "Salt": 0.4, "Silicon": 0.4, "Niobium": 0.3,
    "Vanadium": 0.25, "Bentonite": 0.2, "Feldspar": 0.2, "Fluorite": 0.2,
    "Thorium": 0.15, "Iridium": 0.15, "Bismuth": 0.1, "Mercury": 0.1,
}

# The eight trade archetypes. openness is the mid-point of the trade-to-GDP band
# before size damping; svc_ratio is services exports as a share of GDP;
# bal_tilt is imports relative to exports (positive = structural deficit).
ARCHETYPES = {
    # -- Hub family: earns from other people's cargo --------------------------
    "entrepot": dict(
        family="Hub", openness=0.62, svc_ratio=0.070, bal_tilt=+0.02,
        desc="Gateway port clearing a larger neighbour's goods. Huge gross trade, thin domestic value added."),
    "transshipment": dict(
        family="Hub", openness=0.20, svc_ratio=0.320, bal_tilt=+0.05,
        desc="Boxes change ship and never enter the economy. Enormous throughput, tiny merchandise trade, lives on fees."),
    "bunkering": dict(
        family="Hub", openness=0.34, svc_ratio=0.190, bal_tilt=-0.02,
        desc="Refuelling and ship supply on a major lane. Sells the fuel as well as the service."),
    "canal_state": dict(
        family="Hub", openness=0.30, svc_ratio=0.240, bal_tilt=+0.02,
        desc="Owns a chokepoint and charges for passage. Toll income dwarfs its own cargo."),

    # -- Industry family: makes and sells things ------------------------------
    "manufacturing_advanced": dict(
        family="Industry", openness=0.40, svc_ratio=0.045, bal_tilt=-0.12,
        desc="Machinery, vehicles, precision goods. Deep supply chains, structural surplus, heavy container use."),
    "manufacturing_light": dict(
        family="Industry", openness=0.36, svc_ratio=0.025, bal_tilt=-0.08,
        desc="Textiles, assembly, consumer goods. Low-wage export platform importing components."),
    "industrialising": dict(
        family="Industry", openness=0.30, svc_ratio=0.030, bal_tilt=+0.04,
        desc="Climbing the value chain. Imports capital goods faster than it exports finished ones."),

    # -- Resource family: sells what is in the ground or the soil -------------
    "petro": dict(
        family="Resource", openness=0.44, svc_ratio=0.020, bal_tilt=-0.18,
        desc="Oil and gas dominate the basket. Large surplus, hostage to prices, thin non-energy base."),
    "mining": dict(
        family="Resource", openness=0.38, svc_ratio=0.022, bal_tilt=-0.12,
        desc="Metals and ores. Bulk tonnage, moderate value, exposed to a handful of buyers."),
    "plantation": dict(
        family="Resource", openness=0.30, svc_ratio=0.030, bal_tilt=-0.02,
        desc="Cash crops grown for export. Modest values, seasonal, imports its manufactures."),
    "subsistence": dict(
        family="Resource", openness=0.17, svc_ratio=0.018, bal_tilt=+0.10,
        desc="Farms mostly to feed itself. Trades little, and what it does buy it struggles to pay for."),

    # -- Services family: earns without shipping goods ------------------------
    "financial": dict(
        family="Services", openness=0.26, svc_ratio=0.200, bal_tilt=+0.02,
        desc="Banking, insurance and offshore business. Exports invisibles, imports nearly every physical good."),
    "tourism": dict(
        family="Services", openness=0.22, svc_ratio=0.150, bal_tilt=+0.06,
        desc="Visitors are the export. Strong services surplus offsetting a permanent goods deficit."),

    # -- Market family: big enough to mostly trade with itself ----------------
    "consumer": dict(
        family="Market", openness=0.22, svc_ratio=0.045, bal_tilt=+0.14,
        desc="Large wealthy internal market. Imports more than it exports; low trade-to-GDP because home demand is vast."),
    "diversified": dict(
        family="Market", openness=0.26, svc_ratio=0.050, bal_tilt=+0.02,
        desc="Broad balanced economy with no single dominant export mode. Trades roughly in line with its size."),

    # -- Constrained family: trades less than geography would predict ---------
    "sanctioned": dict(
        family="Constrained", openness=0.10, svc_ratio=0.008, bal_tilt=+0.01,
        desc="Cut off by others. Trade suppressed well below what its size and resources imply. Assign by hand."),
    "autarkic": dict(
        family="Constrained", openness=0.09, svc_ratio=0.010, bal_tilt=-0.02,
        desc="Self-sufficient by choice and policy. Very low trade-to-GDP. Assign by hand."),
    "war_economy": dict(
        family="Constrained", openness=0.13, svc_ratio=0.010, bal_tilt=+0.16,
        desc="Conflict has wrecked routes and capacity. Imports what it can, exports little. Assign by hand."),
    "microstate": dict(
        family="Constrained", openness=0.85, svc_ratio=0.150, bal_tilt=+0.08,
        desc="Tiny economy, extreme trade-to-GDP ratio, imports nearly everything it consumes."),
}

# Family fills for the Archetype column, and the palette for continents. Each
# subregion takes a progressively darker shade of its continent's colour, so the
# three coordinated columns read as one system.
FAMILY_FILL = {
    "Hub": "B3E5FC", "Industry": "FFCCBC", "Resource": "DCEDC8",
    "Services": "E1BEE7", "Market": "FFF9C4", "Constrained": "CFD8DC",
}
CONTINENT_RGB = {
    "Acrola": (0xF9, 0xA8, 0x25), "Atirha": (0x43, 0xA0, 0x47),
    "Ayuma": (0x1E, 0x88, 0xE5), "Mahea": (0xD8, 0x1B, 0x60),
    "Massir": (0x8E, 0x24, 0xAA), "New Ayre": (0x00, 0x89, 0x7B),
    "Quia": (0xF4, 0x51, 0x1E),
}

# Earth 2015, the calibration mirror. Exports are goods plus services in USD
# billions; the world figures are the denominators everything is measured
# against. Andah is judged realistic when its SHAPE matches these, not its size.
EARTH_2015 = dict(
    world_gdp=75.0e12,
    world_exports=21.3e12,
    services_share=0.225,
    median_trade_gdp=0.80,
    share_over_100pct=0.33,
    max_trade_gdp=4.00,
    top_exporters=[
        ("China", 2560), ("United States", 2259), ("Germany", 1600),
        ("United Kingdom", 802), ("Japan", 783), ("France", 746),
        ("Netherlands", 729), ("South Korea", 625), ("Hong Kong", 615),
        ("Italy", 559), ("Belgium", 504), ("Singapore", 491),
        ("Canada", 490), ("India", 423), ("Spain", 411), ("Mexico", 406),
        ("Switzerland", 404), ("Russia", 393), ("UAE", 360), ("Taiwan", 326),
    ],
    # exports as a share of world exports, divided by share of world GDP.
    # The lesson Andah has to reproduce: giants export LESS than proportionally.
    export_to_gdp_ratio={
        "China": 0.82, "United States": 0.44, "Germany": 1.67,
        "Japan": 0.25, "Netherlands": 3.40, "Singapore": 5.75, "India": 0.96,
    },
)

# Share of each hub's container throughput by component. Shares per hub must sum
# to 1.0; Validation checks this. Derived from DJ's canon:
#   Pha Hii and Prystr Hii are Dahe's outlets
#   Emara carries a lot of Lycroan trade, and Alubri City sits on the Tiesa Canal
#   Merela Sta is some Verusan, all Palinan and some Yaxutan
#   Guise and Canldives are pure transshipment (Canldives on the Ayuma-Dahe lane)
#   Chaenia and Oyreain are part stopover, Singapore-style
#   Taval's ports are largely refuelling stopovers
# Edit these in the Transit sheet and re-run; nothing here is load-bearing canon.
TRANSIT = [
    # hub,          component,     partner,       share, note
    ("Emara",       "own",         "",            0.55, "Puzhu and Chishanov, Emaran trade"),
    ("Emara",       "hinterland",  "Lycroa",      0.20, "Lycroa is port-poor and borders Emara"),
    ("Emara",       "canal",       "",            0.25, "Alubri City, Tiesa Canal Territory"),
    ("Merela Sta",  "own",         "",            0.30, ""),
    ("Merela Sta",  "hinterland",  "Verusa",      0.46, "some Verusan"),
    ("Merela Sta",  "hinterland",  "Yaxuto",      0.17, "some Yaxutan"),
    ("Merela Sta",  "hinterland",  "Palina",      0.07, "all Palinan"),
    ("Sanagara",    "own",         "",            0.35, ""),
    ("Sanagara",    "hinterland",  "Dahe",        0.40, ""),
    ("Sanagara",    "stopover",    "",            0.25, "Sanagara Strait"),
    ("Oyreain",     "own",         "",            0.20, ""),
    ("Oyreain",     "hinterland",  "Dahe",        0.40, ""),
    ("Oyreain",     "stopover",    "",            0.40, "Batikolo on the Sanagara Strait"),
    ("Pha Hii",     "own",         "",            0.20, ""),
    ("Pha Hii",     "hinterland",  "Dahe",        0.75, ""),
    ("Pha Hii",     "hinterland",  "Prystr Hii",  0.05, "Prystr Hii has no top-60 port"),
    ("Chaenia",     "own",         "",            0.45, ""),
    ("Chaenia",     "stopover",    "",            0.55, "Singapore-style stopover"),
    ("Taval",       "own",         "",            0.25, ""),
    ("Taval",       "stopover",    "",            0.75, "refuelling and bunkering"),
    ("Guise",       "own",         "",            0.05, ""),
    ("Guise",       "stopover",    "",            0.95, "pure transshipment"),
    ("Canldives",   "own",         "",            0.03, ""),
    ("Canldives",   "stopover",    "",            0.97, "Ayuma-Dahe lane, Vishanna Ocean"),
]

# Countries whose trade is bunkering-led: stopover fuel is also a real goods export.
BUNKERING = {"Taval"}


# --------------------------------------------------------------------------
# seeded dice - same contract as the KTDI model: keyed to a stable Dice ID that
# travels with the row, never to the row number, so sorting is safe.
# --------------------------------------------------------------------------

def lcg(seed, dice_id, stream=0):
    """Deterministic uniform in [0,1) from (seed, dice id, stream)."""
    x = (seed * 2654435761) ^ (dice_id * 40503) ^ (stream * 2246822519)
    x &= 0xFFFFFFFF
    for _ in range(3):
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
    return x / 0x80000000


def dice_mult(seed, dice_id, stream, strength):
    """A multiplier centred on 1.0, spread +/- strength."""
    return 1.0 + strength * (2.0 * lcg(seed, dice_id, stream) - 1.0)


# --------------------------------------------------------------------------
# loaders
# --------------------------------------------------------------------------

def load_countries():
    """Continent, subregion, area, population, GDP nominal and per capita for 172."""
    wb = openpyxl.load_workbook(JANUS, read_only=True, data_only=True)
    ws = wb["Geoscheme"]
    out = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or not r[2] or not isinstance(r[7], (int, float)):
            continue
        name = str(r[2]).strip()
        out[name] = dict(
            name=name, continent=str(r[0]).strip(), subregion=str(r[1]).strip(),
            area=r[3] or 0, population=r[4] or 0,
            gdp_ppp=r[6] or 0, gdp=float(r[7]),
            gdp_pc=float(r[8]) if isinstance(r[8], (int, float)) else 0.0,
        )
    wb.close()
    return out


def load_ports():
    """cargo by country, and the raw port rows for the Validation sheet."""
    wb = openpyxl.load_workbook(PORTS, read_only=True, data_only=True)
    ws = wb["Sheet1"]
    cargo = collections.Counter()
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or not r[1] or not isinstance(r[5], (int, float)):
            continue
        country = str(r[2]).strip()
        cargo[country] += r[5]
        rows.append((str(r[1]).strip(), country, str(r[3] or "").strip(),
                     str(r[4] or "").strip(), float(r[5])))
    wb.close()
    return cargo, rows


def _find_country_col(header, rows):
    """Locate the country column; fall back to the most text-heavy column."""
    for i, h in enumerate(header):
        if h and str(h).strip().lower().startswith("country"):
            return i
    best, best_n = None, 0
    for i in range(min(4, max((len(r) for r in rows), default=0))):
        n = sum(1 for r in rows[1:] if i < len(r) and isinstance(r[i], str) and len(r[i]) > 2)
        if n > best_n:
            best, best_n = i, n
    return best


def load_production():
    """
    {commodity: {country: share of world output}} across every parseable sheet.

    Tolerates the three layouts present: a World row, no World row (sum the
    countries instead), and a missing Country header (infer the column).
    """
    wb = openpyxl.load_workbook(PRODUCTION, read_only=True, data_only=True)
    shares, skipped = {}, []
    for sheet in wb.sheetnames:
        label = sheet.strip()
        if label in SUMMARY_SHEETS:
            continue
        ws = wb[sheet]
        rows = [r for r in ws.iter_rows(values_only=True)
                if r and any(x is not None for x in r)]
        if len(rows) < 3:
            skipped.append((label, "empty"))
            continue
        header = [str(x).strip() if x else "" for x in rows[0]]
        ci = _find_country_col(header, rows)
        if ci is None:
            skipped.append((label, "no country column"))
            continue

        # first numeric column after the country column is the production figure
        pi = None
        for j in range(ci + 1, len(header)):
            n = sum(1 for r in rows[1:] if j < len(r) and isinstance(r[j], (int, float)))
            if n >= 3:
                pi = j
                break
        if pi is None:
            skipped.append((label, "no numeric production column"))
            continue

        per, world = {}, None
        for r in rows[1:]:
            if ci >= len(r) or not r[ci] or pi >= len(r):
                continue
            country = str(r[ci]).strip()
            val = r[pi]
            if not isinstance(val, (int, float)) or val <= 0:
                continue
            if country.lower() == "world":
                world = float(val)
            elif country.lower().startswith("other"):
                continue
            else:
                per[country] = per.get(country, 0.0) + float(val)
        if not per:
            skipped.append((label, "no country rows"))
            continue
        total = world if world and world > 0 else sum(per.values())
        shares[label] = {k: v / total for k, v in per.items()}
    wb.close()
    return shares, skipped


def load_oil_gas():
    """Oil and gas production shares, which live in their own workbook."""
    out = {}
    try:
        wb = openpyxl.load_workbook(OILGAS, read_only=True, data_only=True)
    except Exception:
        return out
    for sheet, col in (("Oil", 4), ("Gas", 4)):
        if sheet not in wb.sheetnames:
            continue
        ws = wb[sheet]
        per = {}
        for r in ws.iter_rows(min_row=2, values_only=True):
            if not r or not r[0] or col >= len(r):
                continue
            name = str(r[0]).strip()
            # names carry a source suffix such as "Sunsokua (MPU)"
            if "(" in name:
                name = name.split("(")[0].strip()
            val = r[col]
            if isinstance(val, (int, float)) and val > 0:
                per[name] = per.get(name, 0.0) + float(val)
        if per:
            total = sum(per.values())
            key = "Oil" if sheet == "Oil" else "Natural Gas"
            out[key] = {k: v / total for k, v in per.items()}
    wb.close()
    return out


# --------------------------------------------------------------------------
# the model
# --------------------------------------------------------------------------

def build_transit(countries, cargo):
    """
    Decompose each hub's throughput and credit hinterland cargo back to its owner.

    Returns per-country: own / hinterland-carried / stopover / canal cargo, plus
    'routed' - cargo that belongs to this country but physically moves through
    somebody else's port, which is what stops port-poor economies like Lycroa
    from being scored as closed.
    """
    comp = {c: dict(own=0.0, carried=0.0, stopover=0.0, canal=0.0, routed=0.0)
            for c in countries}
    pairs = []
    hubs = {h for h, *_ in TRANSIT}

    for country, total in cargo.items():
        if country not in comp:
            continue
        if country not in hubs:
            comp[country]["own"] += total       # no transit story, all its own
            continue
        for hub, kind, partner, share, _note in TRANSIT:
            if hub != country:
                continue
            vol = total * share
            if kind == "own":
                comp[country]["own"] += vol
            elif kind == "stopover":
                comp[country]["stopover"] += vol
            elif kind == "canal":
                comp[country]["canal"] += vol
            elif kind == "hinterland":
                comp[country]["carried"] += vol
                if partner in comp:
                    comp[partner]["routed"] += vol
                    pairs.append((hub, partner, vol))
    return comp, pairs


def assign_archetype(c, comp, resource_score, gdp_share, med_gdp_pc, med_intensity,
                     leading_commodity=""):
    """
    Auto-tag from the data. Every call is overridable in the workbook, and
    'closed' is deliberately never assigned automatically: war and sanctions are
    canon decisions, not something to infer from a GDP column.

    The commodity test is deliberately RELATIVE. An absolute threshold tags the
    biggest economies as commodity states purely because everything they do is
    large: Dahe mines more than anyone and is still not a commodity economy,
    because its share of world output is smaller than its share of world GDP.
    What marks a commodity exporter is producing disproportionately, not a lot.
    """
    name = c["name"]
    k = comp.get(name, {})
    total = sum(k.get(x, 0.0) for x in ("own", "carried", "stopover", "canal"))
    gdp_bn = c["gdp"] / 1e9
    intensity = (total + k.get("routed", 0.0)) / gdp_bn if gdp_bn > 0 else 0.0
    carried = k.get("carried", 0.0)
    passing = k.get("stopover", 0.0) + k.get("canal", 0.0)
    concentration = resource_score / gdp_share if gdp_share > 0 else 0.0

    # -- Hub family ----------------------------------------------------------
    if name in BUNKERING:
        return "bunkering", "ports are refuelling and ship-supply stops on a major lane"
    if total > 0 and k.get("canal", 0.0) / total >= 0.30:
        return "canal_state", "a third or more of throughput is chokepoint transit"
    if total > 0 and passing / total >= 0.60:
        return "transshipment", f"{passing/total:.0%} of throughput is stopover traffic that never lands"
    if total > 0 and carried / total >= 0.30:
        return "entrepot", f"{carried/total:.0%} of throughput is a neighbour's cargo"

    # -- Constrained ---------------------------------------------------------
    if c["population"] and c["population"] < 1_500_000:
        return "microstate", "population under 1.5 million"

    # -- Resource ------------------------------------------------------------
    if concentration >= 1.5 and resource_score >= 0.002:
        energy = leading_commodity in ("Oil", "Natural Gas", "Coal")
        tag = "petro" if energy else "mining"
        return tag, f"produces {concentration:.1f}x its GDP share of world output, led by {leading_commodity.lower()}"

    # -- Industry and Market -------------------------------------------------
    rich = c["gdp_pc"] >= med_gdp_pc * 1.3
    middling = c["gdp_pc"] >= med_gdp_pc * 0.75
    busy = intensity >= med_intensity * 0.8

    pop = c["population"] or 0
    if rich and busy:
        return "manufacturing_advanced", "high income with heavy container throughput"
    if rich and gdp_share >= 0.01:
        return "consumer", "high income, modest throughput, large internal market"
    # Offshore finance is a genuinely rare thing. Requiring both very high income
    # AND a small population keeps it to a handful, rather than tagging every
    # well-off country that happens not to run a big port.
    if c["gdp_pc"] >= med_gdp_pc * 2.2 and pop < 12_000_000:
        return "financial", "very high income on a small population with little cargo"
    if rich and pop < 25_000_000:
        return "tourism", "comfortable income, small population, little freight"
    if rich:
        return "diversified", "high income, broad economy, no dominant export mode"
    if middling and busy:
        return "manufacturing_light", "middle income with above-median throughput"
    if middling and gdp_share >= 0.008:
        return "diversified", "middle income, broad economy, no dominant export mode"
    if middling:
        return "industrialising", "middle income, still importing more capital goods than it ships out"

    # -- Poorer economies ----------------------------------------------------
    # The world median throughput is set by countries with real ports, so a poor
    # economy can be a serious crop exporter and still never approach it. Judged
    # against the world bar, every one of them reads as subsistence, which is
    # wrong: the split that matters here is whether it ships anything at all.
    if intensity >= med_intensity * 0.25 or c["gdp_pc"] >= med_gdp_pc * 0.45:
        return "plantation", "low income but genuinely shipping, so cash crops rather than subsistence"
    return "subsistence", "little income and almost no freight"


def load_overrides():
    """
    Read back the hand edits from a previous build so re-running never wipes
    them. This is the whole point of the Overrides sheet: the auto-tagger gets
    you 172 defensible starting tags, and you overrule it wherever it is wrong.
    """
    if not os.path.exists(OUT):
        return {}
    try:
        wb = openpyxl.load_workbook(OUT, read_only=True, data_only=True)
    except Exception:
        return {}
    out = {}
    if "Overrides" in wb.sheetnames:
        for r in wb["Overrides"].iter_rows(min_row=2, values_only=True):
            if not r or not r[0] or len(r) < 2 or not r[1]:
                continue
            tag = str(r[1]).strip()
            if tag in ARCHETYPES:
                out[str(r[0]).strip()] = tag
            else:
                print(f"note: ignoring unknown archetype '{tag}' for {r[0]}", file=sys.stderr)
    wb.close()
    return out


def run_model(countries, cargo, production, seed, overrides=None):
    overrides = overrides or {}
    comp, pairs = build_transit(countries, cargo)

    # ---- resource score: share of world commodity output, weighted by value ----
    wsum = sum(COMMODITY_WEIGHTS.values())
    weights = {k: v / wsum for k, v in COMMODITY_WEIGHTS.items()}
    resource = collections.defaultdict(float)
    leading = {}
    for commodity, per in production.items():
        w = weights.get(commodity)
        if w is None:                     # unweighted commodity, give it a small floor
            w = 0.1 / wsum
        for country, share in per.items():
            if country not in countries:
                continue
            contribution = share * w
            resource[country] += contribution
            if contribution > leading.get(country, (None, 0.0))[1]:
                leading[country] = (commodity, contribution)

    world_gdp = sum(c["gdp"] for c in countries.values())
    gdps = sorted(c["gdp"] for c in countries.values())
    med_gdp = gdps[len(gdps) // 2]
    pcs = sorted(c["gdp_pc"] for c in countries.values() if c["gdp_pc"] > 0)
    med_gdp_pc = pcs[len(pcs) // 2]
    intensities = []
    for n, c in countries.items():
        k = comp[n]
        tot = k["own"] + k["carried"] + k["stopover"] + k["canal"] + k["routed"]
        if tot > 0 and c["gdp"] > 0:
            intensities.append(tot / (c["gdp"] / 1e9))
    intensities.sort()
    med_intensity = intensities[len(intensities) // 2] if intensities else 1.0

    dice_ids = {n: i + 1 for i, n in enumerate(sorted(countries))}

    rows = []
    for name in sorted(countries):
        c = countries[name]
        k = comp[name]
        did = dice_ids[name]
        rscore = resource.get(name, 0.0)
        gdp_share = c["gdp"] / world_gdp
        lead_c = leading.get(name, ("", 0.0))[0]
        arch, why = assign_archetype(c, comp, rscore, gdp_share, med_gdp_pc,
                                     med_intensity, lead_c)
        if name in overrides:
            arch, why = overrides[name], "set by hand in the Overrides sheet"
        a = ARCHETYPES[arch]

        # effective throughput: own cargo plus what this country routes elsewhere.
        effective = k["own"] + k["routed"]
        gdp_bn = c["gdp"] / 1e9
        intensity = effective / gdp_bn if gdp_bn > 0 else 0.0

        # Structural openness, damped hard for size. A large internal market is
        # the single strongest brake on trade-to-GDP: on Earth the two biggest
        # economies trade at 25-35% of GDP while mid-size ones reach 80-90%.
        openness = a["openness"] * (c["gdp"] / med_gdp) ** SIZE_DAMPING
        port_factor = ((intensity / med_intensity) ** 0.30) if intensity > 0 else 0.65
        port_factor = max(0.60, min(2.50, port_factor))
        # A commodity boost on top of a huge diversified economy double-counts,
        # so taper it by how concentrated the country actually is.
        concentration = rscore / gdp_share if gdp_share > 0 else 0.0
        resource_factor = 1.0 + 9.0 * rscore * min(1.0, concentration / 1.5)
        d = dice_mult(seed, did, 1, DICE_STRENGTH)

        raw_goods = c["gdp"] * openness * port_factor * resource_factor * d
        rows.append(dict(
            name=name, dice_id=did, archetype=arch, why=why,
            continent=c["continent"], subregion=c["subregion"],
            gdp=c["gdp"], gdp_pc=c["gdp_pc"], population=c["population"],
            cargo_own=k["own"], cargo_carried=k["carried"],
            cargo_stopover=k["stopover"], cargo_canal=k["canal"],
            cargo_routed=k["routed"], effective_cargo=effective,
            resource_score=rscore,
            leading_commodity=leading.get(name, ("", 0.0))[0],
            leading_score=leading.get(name, ("", 0.0))[1],
            leading="",
            openness=openness, port_factor=port_factor,
            resource_factor=resource_factor, dice=d,
            raw_goods=raw_goods,
        ))

    # ---- normalise merchandise to the world target ----
    target_goods = world_gdp * WORLD_OPENNESS * GOODS_SHARE
    target_services = world_gdp * WORLD_OPENNESS * (1 - GOODS_SHARE)
    scale = target_goods / sum(r["raw_goods"] for r in rows)
    for r in rows:
        r["dom_goods_x"] = r["raw_goods"] * scale       # domestic value added

    # ---- re-exports: value the carried cargo at the world average per unit ----
    total_own = sum(r["cargo_own"] for r in rows)
    value_per_unit = (sum(r["dom_goods_x"] for r in rows) / total_own) if total_own else 0.0
    for r in rows:
        r["reexports"] = r["cargo_carried"] * value_per_unit
        r["goods_x"] = r["dom_goods_x"] + r["reexports"]

    # ---- services: archetype base, plus stopover fees and canal tolls ----
    for r in rows:
        a = ARCHETYPES[r["archetype"]]
        r["svc_base"] = r["gdp"] * a["svc_ratio"] * dice_mult(seed, r["dice_id"], 2, DICE_STRENGTH)
        r["passing_cargo"] = r["cargo_stopover"] + r["cargo_canal"] * 1.8   # tolls beat fees
    passing_total = sum(r["passing_cargo"] for r in rows)
    base_total = sum(r["svc_base"] for r in rows)
    # split the world services target between ordinary services and transit earnings
    transit_pool = target_services * 0.18
    ordinary_pool = target_services - transit_pool
    for r in rows:
        r["svc_transit"] = (transit_pool * r["passing_cargo"] / passing_total) if passing_total else 0.0
        r["svc_x"] = r["svc_base"] * (ordinary_pool / base_total) + r["svc_transit"]

    # ---- bunkering states also sell the fuel itself ----
    for r in rows:
        if r["name"] in BUNKERING:
            r["goods_x"] += r["svc_transit"] * 0.45
            r["dom_goods_x"] += r["svc_transit"] * 0.45

    # ---- imports: archetype tilt, then forced to balance the world's books ----
    for r in rows:
        a = ARCHETYPES[r["archetype"]]
        tilt = a["bal_tilt"] * dice_mult(seed, r["dice_id"], 3, 0.5)
        r["goods_m_raw"] = r["dom_goods_x"] * (1 + tilt) + r["reexports"]
        r["svc_m_raw"] = r["svc_x"] * (1 + tilt * 0.6)
    gscale = sum(r["goods_x"] for r in rows) / sum(r["goods_m_raw"] for r in rows)
    sscale = sum(r["svc_x"] for r in rows) / sum(r["svc_m_raw"] for r in rows)
    for r in rows:
        r["goods_m"] = r["goods_m_raw"] * gscale
        r["svc_m"] = r["svc_m_raw"] * sscale
        r["total_x"] = r["goods_x"] + r["svc_x"]
        r["total_m"] = r["goods_m"] + r["svc_m"]
        r["balance"] = r["total_x"] - r["total_m"]
        r["trade_gdp"] = (r["total_x"] + r["total_m"]) / r["gdp"] if r["gdp"] else 0.0
        r["dva_share"] = r["dom_goods_x"] / r["goods_x"] if r["goods_x"] else 1.0

    # ---- leading export, but only when the commodity is actually material ----
    # Dominating a small market is not the same as living off it: Ukhdari leads
    # the world in feldspar, which is 0.2% of world commodity trade and no basis
    # for calling it a feldspar economy.
    world_commodity_trade = target_goods * COMMODITY_SHARE_OF_GOODS
    for r in rows:
        value = r["leading_score"] * world_commodity_trade
        if r["name"] in BUNKERING:
            r["leading"] = "Bunker fuel and port services"
        elif r["goods_x"] > 0 and value / r["goods_x"] >= 0.08:
            r["leading"] = r["leading_commodity"]
        else:
            r["leading"] = {
                "entrepot": "Re-exports", "transshipment": "Port and transit services",
                "canal_state": "Transit tolls", "bunkering": "Bunker fuel and port services",
                "financial": "Financial services", "tourism": "Travel and tourism",
                "plantation": "Cash crops", "subsistence": "Agricultural produce",
                "industrialising": "Light manufactures", "manufacturing_light": "Consumer goods",
                "sanctioned": "Restricted", "war_economy": "Restricted",
                "autarkic": "Minimal external trade",
            }.get(r["archetype"], "Manufactures")

    for key in ("total_x", "total_m", "goods_x", "goods_m"):
        for rank, r in enumerate(sorted(rows, key=lambda x: -x[key]), 1):
            r[key + "_rank"] = rank
    return rows, pairs, dict(world_gdp=world_gdp, target_goods=target_goods,
                             target_services=target_services,
                             value_per_unit=value_per_unit, seed=seed)


# --------------------------------------------------------------------------
# workbook
# --------------------------------------------------------------------------

HDR = PatternFill("solid", fgColor="1F3864")
GREEN = PatternFill("solid", fgColor="E2EFDA")   # editable
ORANGE = PatternFill("solid", fgColor="FCE4D6")  # dice
PURPLE = PatternFill("solid", fgColor="E4DFEC")  # derived

# Negative values print red everywhere, so a deficit is visible at a glance.
MONEY = '#,##0;[Red]-#,##0'
PCT = '0.0%;[Red]-0.0%'
RATIO = '0.00;[Red]-0.00'


def _tint(rgb, factor):
    """Lighten an RGB triple towards white. factor 0 = original, 1 = white."""
    return "".join(f"{int(v + (255 - v) * factor):02X}" for v in rgb)


def build_palette(rows):
    """
    Colour-coordinate continent, subregion and archetype.

    Continents get a base hue; each subregion within a continent takes a
    progressively darker shade of that same hue, so the two columns read as one
    system rather than two unrelated legends. Archetypes are coloured by family.
    """
    continent_fill, subregion_fill = {}, {}
    subs = collections.defaultdict(set)
    for r in rows:
        subs[r["continent"]].add(r["subregion"])
    for cont, rgb in CONTINENT_RGB.items():
        continent_fill[cont] = PatternFill("solid", fgColor=_tint(rgb, 0.55))
        ordered = sorted(subs.get(cont, []))
        n = max(1, len(ordered))
        for i, sub in enumerate(ordered):
            # Keyed by (continent, subregion), not by subregion alone. One
            # subregion name currently appears under two continents in the
            # Geoscheme sheet, and a flat key silently gives a country its
            # neighbour's colour. Validation reports any such case.
            # 0.80 (palest) down to 0.45, so subregions stay legible under black text
            subregion_fill[(cont, sub)] = PatternFill("solid", fgColor=_tint(rgb, 0.80 - 0.35 * i / n))
    archetype_fill = {tag: PatternFill("solid", fgColor=FAMILY_FILL[a["family"]])
                      for tag, a in ARCHETYPES.items()}
    return continent_fill, subregion_fill, archetype_fill


def earth_comparison(rows, meta):
    """
    Measure Andah against Earth 2015 on SHAPE, not size.

    Absolute totals are meaningless across two different worlds, so every metric
    here is a ratio or a share. The one that matters most is the giant's export
    ratio: on Earth the largest economies export LESS than proportionally
    (China 0.82, the United States 0.44), because a vast internal market is the
    strongest brake on trade there is. If Andah's biggest economy comes out above
    1.0 the model is treating size as an accelerator instead of a brake.
    """
    E = EARTH_2015
    world_x = sum(r["total_x"] for r in rows)
    wg = meta["world_gdp"]
    ranked = sorted(rows, key=lambda r: -r["total_x"])
    e_ranked = sorted(E["top_exporters"], key=lambda x: -x[1])

    def a_share(n):
        return sum(r["total_x"] for r in ranked[:n]) / world_x

    def e_share(n):
        return sum(v for _, v in e_ranked[:n]) * 1e9 / E["world_exports"]

    tg = sorted(r["trade_gdp"] for r in rows)
    med_tg = tg[len(tg) // 2]
    over100 = sum(1 for v in tg if v > 1.0) / len(tg)
    # Ranked by GDP, not by exports. Ranking by exports puts a petrostate second
    # and compares it against the United States, which tests nothing: a petrostate
    # is supposed to export above its weight. The question is what a country with
    # a very large internal market does.
    by_gdp = sorted(rows, key=lambda r: -r["gdp"])
    top = by_gdp[0]
    top_ratio = (top["total_x"] / world_x) / (top["gdp"] / wg)
    second = by_gdp[1]
    second_ratio = (second["total_x"] / world_x) / (second["gdp"] / wg)
    svc = sum(r["svc_x"] for r in rows) / world_x
    surplus = max(r["balance"] for r in rows) / wg
    deficit = min(r["balance"] for r in rows) / wg

    # tolerance is deliberately generous: Andah is a different world, we are
    # checking it is not structurally absurd, not forcing it to be Earth.
    def verdict(a, e, tol):
        return "realistic" if abs(a - e) <= tol else ("TOO HIGH" if a > e else "TOO LOW")

    return [
        ("World exports / world GDP", world_x / wg, E["world_exports"] / E["world_gdp"], 0.05,
         "How globalised the world is overall"),
        ("Services share of exports", svc, E["services_share"], 0.06,
         "Invisibles versus merchandise"),
        ("Top exporter's share of world exports", a_share(1), e_share(1), 0.05,
         "Concentration at the very top"),
        ("Top 5 share of world exports", a_share(5), e_share(5), 0.09,
         "Whether trade is dominated by a handful of giants"),
        ("Top 10 share of world exports", a_share(10), e_share(10), 0.10,
         "The same test one tier down"),
        ("Top 20 share of world exports", a_share(20), e_share(20), 0.10,
         "And across the whole leading group"),
        ("Largest economy: export share / GDP share", top_ratio,
         E["export_to_gdp_ratio"]["China"], 0.30,
         "THE KEY TEST. Below 1.0 on Earth: a huge internal market suppresses trade"),
        ("Second economy: export share / GDP share", second_ratio,
         E["export_to_gdp_ratio"]["United States"], 0.55,
         "Earth's second economy is the least trade-dependent of all the giants"),
        ("Median trade / GDP", med_tg, E["median_trade_gdp"], 0.30,
         "The typical country, not the headline ones"),
        ("Share of countries trading over 100% of GDP", over100, E["share_over_100pct"], 0.18,
         "How common extreme openness is"),
        ("Largest surplus / world GDP", surplus, 0.0045, 0.004,
         "Earth 2015: China, roughly 0.45% of world GDP"),
        ("Largest deficit / world GDP", deficit, -0.0061, 0.005,
         "Earth 2015: the United States, roughly -0.6% of world GDP"),
    ], verdict


def _header(ws, labels, fills=None):
    ws.append(labels)
    for i, _ in enumerate(labels, 1):
        cell = ws.cell(row=1, column=i)
        cell.fill = HDR
        cell.font = Font(bold=True, color="FFFFFF", size=10)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.freeze_panes = "A2"
    if fills:
        for col, fill in fills.items():
            for row in range(2, ws.max_row + 1):
                ws.cell(row=row, column=col).fill = fill


def _widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def write_workbook(rows, pairs, meta, production, skipped, port_rows):
    wb = openpyxl.Workbook()

    # ---------------- README ----------------
    ws = wb.active
    ws.title = "README"
    T = 1e12
    top_x = sorted(rows, key=lambda r: -r["total_x"])[:5]
    lines = [
        ("Andah trade statistics, seed-driven", True),
        ("", False),
        (f"Year {YEAR}. All values in lahn, same magnitude convention as the GDP columns", False),
        ("in Andah_Janus Statistics.xlsx. Generated by generate_trade.py; do not hand-edit", False),
        ("the Trade Model sheet, edit the inputs below and re-run.", False),
        ("", False),
        ("THE SEED", True),
        ("  Config!B2. Change it and every random element re-rolls across all 172 countries", False),
        ("  at once. The same seed always rebuilds the same world. Config!B3 is the dice", False),
        ("  strength; set it to 0 to switch character off and keep only the structural model.", False),
        ("  The dice are keyed to the Dice ID column, which travels with its row, NOT to the", False),
        ("  row number, so sorting the table is safe.", False),
        ("", False),
        ("WHY THROUGHPUT IS NOT ONE NUMBER", True),
        ("  A container crossing a quay can mean four different things, and only two of them", False),
        ("  are the port country's own exports:", False),
        ("", False),
        ("    own        the country's own goods. Becomes merchandise exports.", False),
        ("    hinterland somebody else's goods moving through. Becomes RE-EXPORTS, which lift", False),
        ("               gross exports and imports equally, leave the balance alone, and show", False),
        ("               up as a low domestic value added share. Merela Sta carries Verusan,", False),
        ("               Palinan and Yaxutan cargo; Emara carries Lycroan; Dahe ships through", False),
        ("               Sanagara, Oyreain and Pha Hii.", False),
        ("    stopover   boxes change ship and never enter the economy. Becomes SERVICES", False),
        ("               exports, not goods. This is why Guise and Canldives run world-class", False),
        ("               ports on tiny economies without gatecrashing the merchandise table.", False),
        ("    canal      transit tolls. Alubri City on the Tiesa Canal. Also services.", False),
        ("", False),
        ("  A hinterland country is never punished for having no port. The cargo it routes", False),
        ("  through a hub is credited back to its own effective throughput, which is why", False),
        (f"  Lycroa, the 8th largest economy with nothing in the top 60, still reads as a", False),
        ("  serious trading nation.", False),
        ("", False),
        ("WHAT YOU CAN EDIT", True),
        ("  Green sheets and columns are inputs. Config sets the seed and the world totals.", False),
        ("  Archetypes sets each tag's trade-to-GDP band, services ratio and deficit tilt.", False),
        ("  Transit is the decomposition table: shares per hub must sum to 1.00, and", False),
        ("  Validation will tell you if they do not. Commodities holds the value weights.", False),
        ("  Orange columns are what the dice produced, purple columns are derived.", False),
        ("", False),
        ("HOW A COUNTRY GETS ITS NUMBERS", True),
        ("  exports = GDP x openness(archetype, damped for size) x port factor x resource", False),
        ("  factor x dice, normalised so world exports equal the Config target. Imports come", False),
        ("  from the archetype's deficit tilt and are then forced so that world imports equal", False),
        ("  world exports exactly. The books balance by construction.", False),
        ("", False),
        ("  'closed' is never assigned automatically. War and sanctions are canon decisions,", False),
        ("  not something to infer from a GDP column, so set that tag by hand.", False),
        ("", False),
        ("CALIBRATION", True),
        (f"  World GDP (nominal)      {meta['world_gdp']/T:>10,.1f} trillion", False),
        (f"  World exports target     {(meta['target_goods']+meta['target_services'])/T:>10,.1f} trillion"
         f"  ({WORLD_OPENNESS:.1%} of GDP, 2015 Earth)", False),
        (f"    merchandise            {meta['target_goods']/T:>10,.1f} trillion  ({GOODS_SHARE:.0%})", False),
        (f"    services               {meta['target_services']/T:>10,.1f} trillion  ({1-GOODS_SHARE:.0%})", False),
        (f"  Seed                     {meta['seed']:>10}", False),
        ("", False),
        ("LARGEST EXPORTERS ON THIS SEED", True),
    ]
    for i, r in enumerate(top_x, 1):
        lines.append((f"  {i}. {r['name']:<14} {r['total_x']/T:6.2f}T   {r['archetype']}", False))
    for text, bold in lines:
        ws.append([text])
        if bold:
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    _widths(ws, [110])

    # ---------------- Config ----------------
    ws = wb.create_sheet("Config")
    _header(ws, ["Setting", "Value", "Notes"])
    for k, v, note in [
        ("SEED", meta["seed"], "Change this to re-roll every random element at once"),
        ("DICE_STRENGTH", DICE_STRENGTH, "0 switches character off, keeping only the structural model"),
        ("WORLD_OPENNESS", WORLD_OPENNESS, "World exports as a share of world GDP. 2015 Earth was about 0.285"),
        ("GOODS_SHARE", GOODS_SHARE, "Merchandise share of world exports; the rest is services"),
        ("COMMODITY_SHARE_OF_GOODS", COMMODITY_SHARE_OF_GOODS, "How much of world merchandise trade is raw commodities"),
        ("YEAR", YEAR, "In-universe year of the estimates"),
    ]:
        ws.append([k, v, note])
    for row in range(2, ws.max_row + 1):
        ws.cell(row=row, column=2).fill = GREEN
    _widths(ws, [26, 14, 78])

    # ---------------- Archetypes ----------------
    ws = wb.create_sheet("Archetypes")
    _header(ws, ["Archetype", "Trade/GDP openness", "Services exports / GDP",
                 "Balance tilt (+ = deficit)", "Countries", "What it means"])
    counts = collections.Counter(r["archetype"] for r in rows)
    for tag, a in ARCHETYPES.items():
        ws.append([tag, a["openness"], a["svc_ratio"], a["bal_tilt"], counts.get(tag, 0), a["desc"]])
    for row in range(2, ws.max_row + 1):
        for col in (2, 3, 4):
            ws.cell(row=row, column=col).fill = GREEN
    _widths(ws, [16, 18, 20, 20, 11, 96])

    # ---------------- Transit ----------------
    ws = wb.create_sheet("Transit")
    _header(ws, ["Hub", "Component", "Partner", "Share of hub cargo",
                 "Cargo units", "Implied % of partner's own trade", "Note"])
    by_hub = collections.defaultdict(float)
    cargo_by = {r["name"]: r["cargo_own"] + r["cargo_carried"] + r["cargo_stopover"] + r["cargo_canal"]
                for r in rows}
    eff = {r["name"]: r["effective_cargo"] for r in rows}
    for hub, kind, partner, share, note in TRANSIT:
        by_hub[hub] += share
        vol = cargo_by.get(hub, 0.0) * share
        implied = ""
        if kind == "hinterland" and partner and eff.get(partner):
            implied = f"{vol / eff[partner]:.0%}"
        ws.append([hub, kind, partner, share, round(vol), implied, note])
    for row in range(2, ws.max_row + 1):
        ws.cell(row=row, column=4).fill = GREEN
        ws.cell(row=row, column=6).fill = PURPLE
    ws.append([])
    ws.append(["CHECK: every hub's shares must sum to 1.00"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    for hub, tot in sorted(by_hub.items()):
        ws.append([hub, "", "", round(tot, 4), "", "", "OK" if abs(tot - 1.0) < 1e-6 else "*** DOES NOT SUM TO 1.00 ***"])
    _widths(ws, [15, 13, 14, 18, 12, 28, 46])

    # ---------------- Commodities ----------------
    ws = wb.create_sheet("Commodities")
    _header(ws, ["Commodity", "Value weight", "Normalised share of commodity trade",
                 "Countries with output", "Top producer", "Its share"])
    wsum = sum(COMMODITY_WEIGHTS.values())
    for commodity in sorted(production, key=lambda c: -COMMODITY_WEIGHTS.get(c, 0)):
        per = production[commodity]
        top = max(per.items(), key=lambda x: x[1]) if per else ("", 0)
        w = COMMODITY_WEIGHTS.get(commodity)
        ws.append([commodity, w if w else "", (w / wsum) if w else "",
                   len(per), top[0], top[1]])
    for row in range(2, ws.max_row + 1):
        ws.cell(row=row, column=2).fill = GREEN
    _widths(ws, [18, 14, 30, 20, 18, 12])
    if skipped:
        ws.append([])
        ws.append(["Sheets that could not be parsed:"])
        for name, why in skipped:
            ws.append([name, why])

    # ---------------- Trade Model ----------------
    ws = wb.create_sheet("Trade Model")
    cols = [
        ("Country", "name"), ("Continent", "continent"), ("Subregion", "subregion"),
        ("Archetype", "archetype"), ("Why tagged", "why"),
        ("GDP nominal", "gdp"), ("GDP per capita", "gdp_pc"),
        ("Exports, total", "total_x"), ("Export rank", "total_x_rank"),
        ("Imports, total", "total_m"), ("Import rank", "total_m_rank"),
        ("Trade balance", "balance"),
        ("Goods exports", "goods_x"), ("Goods export rank", "goods_x_rank"),
        ("Goods imports", "goods_m"),
        ("Services exports", "svc_x"), ("Services imports", "svc_m"),
        ("of which re-exports", "reexports"),
        ("Domestic value added exports", "dom_goods_x"),
        ("DVA share of goods exports", "dva_share"),
        ("Trade as % of GDP", "trade_gdp"),
        ("Leading export", "leading"),
        ("Cargo, own", "cargo_own"), ("Cargo, carried for others", "cargo_carried"),
        ("Cargo, stopover", "cargo_stopover"), ("Cargo, canal", "cargo_canal"),
        ("Cargo routed via others", "cargo_routed"), ("Effective cargo", "effective_cargo"),
        ("Resource score", "resource_score"),
        ("Openness used", "openness"), ("Port factor", "port_factor"),
        ("Resource factor", "resource_factor"), ("Dice", "dice"),
        ("Dice ID", "dice_id"),
    ]
    _header(ws, [c[0] for c in cols])
    ordered = sorted(rows, key=lambda x: -x["total_x"])
    for r in ordered:
        ws.append([r[k] for _, k in cols])
    cont_fill, sub_fill, arch_fill = build_palette(rows)
    for i, r in enumerate(ordered):
        row = i + 2
        # the three coordinated columns
        if r["continent"] in cont_fill:
            ws.cell(row=row, column=2).fill = cont_fill[r["continent"]]
        if (r["continent"], r["subregion"]) in sub_fill:
            ws.cell(row=row, column=3).fill = sub_fill[(r["continent"], r["subregion"])]
        ws.cell(row=row, column=4).fill = arch_fill[r["archetype"]]
        for col in (33,):                      # dice
            ws.cell(row=row, column=col).fill = ORANGE
        for col in range(8, 23):               # results
            ws.cell(row=row, column=col).fill = PURPLE
        for col in (6, 7) + tuple(range(8, 20)):
            ws.cell(row=row, column=col).number_format = MONEY
        for col in (20, 21):
            ws.cell(row=row, column=col).number_format = PCT
        for col in (30, 31, 32, 33):
            ws.cell(row=row, column=col).number_format = RATIO
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{ws.max_row}"
    _widths(ws, [17, 11, 15, 14, 40, 16, 14, 16, 8, 16, 8, 16, 16, 9, 16, 16, 16,
                 16, 18, 12, 12, 15, 11, 13, 12, 11, 13, 13, 12, 11, 10, 11, 9, 8])

    # ---------------- Overrides ----------------
    # Written LAST in terms of intent but placed here so it sits beside the model.
    # Anything typed into column B wins over the auto-tagger on the next run.
    ws = wb.create_sheet("Overrides")
    _header(ws, ["Country", "Archetype override", "Auto-assigned", "Why the model chose it"])
    ws.append([])
    ws.cell(row=2, column=1, value="Type an archetype in column B to overrule the model. "
                                   "Blank means accept the auto tag. Re-run generate_trade.py to apply.")
    ws.cell(row=2, column=1).font = Font(italic=True, size=9)
    _cont, _sub, arch_fill = build_palette(rows)
    for r in sorted(rows, key=lambda x: -x["total_x"]):
        ws.append([r["name"], "" if r["why"] != "set by hand in the Overrides sheet" else r["archetype"],
                   r["archetype"], r["why"]])
        ws.cell(row=ws.max_row, column=2).fill = GREEN
        ws.cell(row=ws.max_row, column=3).fill = arch_fill[r["archetype"]]
    _widths(ws, [18, 24, 24, 62])
    ws.freeze_panes = "A3"

    # a legend of the valid tags, so the column is self-documenting
    ws2 = wb.create_sheet("Archetype legend")
    _header(ws2, ["Family", "Archetype", "Trade/GDP", "Services/GDP", "Balance tilt", "Countries", "Meaning"])
    counts2 = collections.Counter(r["archetype"] for r in rows)
    for tag, a in sorted(ARCHETYPES.items(), key=lambda x: (x[1]["family"], x[0])):
        ws2.append([a["family"], tag, a["openness"], a["svc_ratio"], a["bal_tilt"],
                    counts2.get(tag, 0), a["desc"]])
        ws2.cell(row=ws2.max_row, column=2).fill = arch_fill[tag]
        ws2.cell(row=ws2.max_row, column=5).number_format = RATIO
    _widths(ws2, [13, 24, 11, 13, 12, 11, 104])

    # ---------------- Earth 2015 ----------------
    ws = wb.create_sheet("Earth 2015")
    metrics, verdict = earth_comparison(rows, meta)
    ws.append(["Andah measured against Earth 2015"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=13)
    ws.append(["Shape, not size. Absolute totals mean nothing across two different worlds, so every"])
    ws.append(["metric below is a ratio or a share. Andah is realistic when its distribution matches."])
    ws.append([])
    start = ws.max_row + 1
    _hrow = ["Metric", "Andah", "Earth 2015", "Difference", "Verdict", "What it tests"]
    ws.append(_hrow)
    for i in range(1, len(_hrow) + 1):
        c = ws.cell(row=start, column=i)
        c.fill = HDR
        c.font = Font(bold=True, color="FFFFFF", size=10)
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for label, a, e, tol, note in metrics:
        v = verdict(a, e, tol)
        ws.append([label, a, e, a - e, v, note])
        row = ws.max_row
        for col in (2, 3, 4):
            ws.cell(row=row, column=col).number_format = RATIO
        ws.cell(row=row, column=5).fill = PatternFill(
            "solid", fgColor="C6EFCE" if v == "realistic" else "FFC7CE")
        ws.cell(row=row, column=5).font = Font(
            color="006100" if v == "realistic" else "9C0006", bold=True)
    n_ok = sum(1 for m in metrics if verdict(m[1], m[2], m[3]) == "realistic")
    ws.append([])
    ws.append([f"VERDICT: {n_ok} of {len(metrics)} metrics fall inside Earth 2015 tolerance."])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append([f"Size damping is set to {SIZE_DAMPING}, chosen by sweeping this table and minimising"])
    ws.append(["total deviation. It is the single lever that controls how much giants trade."])

    # top-20 exporter share curve, Andah against Earth
    ws.append([])
    chart_top = ws.max_row + 1
    ws.append(["Rank", "Andah share of world exports", "Earth 2015 share of world exports",
               "Andah country", "Earth country"])
    for i in range(1, len(_hrow) + 1):
        c = ws.cell(row=chart_top, column=i)
        c.fill = HDR
        c.font = Font(bold=True, color="FFFFFF", size=10)
    a_ranked = sorted(rows, key=lambda r: -r["total_x"])[:20]
    e_ranked = sorted(EARTH_2015["top_exporters"], key=lambda x: -x[1])[:20]
    world_x = sum(r["total_x"] for r in rows)
    for i in range(20):
        ws.append([i + 1,
                   a_ranked[i]["total_x"] / world_x,
                   e_ranked[i][1] * 1e9 / EARTH_2015["world_exports"],
                   a_ranked[i]["name"], e_ranked[i][0]])
        for col in (2, 3):
            ws.cell(row=ws.max_row, column=col).number_format = PCT
    try:
        from openpyxl.chart import BarChart, Reference
        ch = BarChart()
        ch.type = "col"
        ch.title = "Export concentration: Andah vs Earth 2015 (share of world exports by rank)"
        ch.y_axis.title = "Share of world exports"
        ch.x_axis.title = "Rank"
        ch.height, ch.width = 9, 26
        data = Reference(ws, min_col=2, max_col=3, min_row=chart_top, max_row=chart_top + 20)
        cats = Reference(ws, min_col=1, min_row=chart_top + 1, max_row=chart_top + 20)
        ch.add_data(data, titles_from_data=True)
        ch.set_categories(cats)
        ws.add_chart(ch, f"H{chart_top}")
    except Exception as exc:                       # chart is a nicety, never fatal
        print(f"note: could not add the comparison chart ({exc})", file=sys.stderr)
    _widths(ws, [46, 12, 13, 12, 14, 60])

    # ---------------- Validation ----------------
    ws = wb.create_sheet("Validation")
    _header(ws, ["Check", "Value", "Expected", "Status"])
    tx = sum(r["total_x"] for r in rows)
    tm = sum(r["total_m"] for r in rows)
    gx = sum(r["goods_x"] for r in rows)
    sx = sum(r["svc_x"] for r in rows)
    dom = sum(r["dom_goods_x"] for r in rows)
    checks = [
        ("Countries modelled", len(rows), 172, "OK" if len(rows) == 172 else "MISMATCH"),
        ("World exports / world GDP", round(tx / meta["world_gdp"], 4), WORLD_OPENNESS,
         "OK" if abs(tx / meta["world_gdp"] - WORLD_OPENNESS) < 0.02 else "CHECK"),
        ("World exports minus world imports", round(tx - tm, 2), 0,
         "OK" if abs(tx - tm) < 1e6 else "BOOKS DO NOT BALANCE"),
        ("Merchandise share of exports", round(gx / tx, 4), GOODS_SHARE,
         "OK" if abs(gx / tx - GOODS_SHARE) < 0.03 else "CHECK"),
        ("Services exports", round(sx, 0), round(meta["target_services"], 0), ""),
        ("Re-exports as share of merchandise", round(1 - dom / gx, 4), "", "informational"),
        ("Commodity sheets parsed", len(production), 34, ""),
        ("Ports decomposed", len(port_rows), 60, ""),
    ]
    for c in checks:
        ws.append(list(c))

    # Source-data problems worth knowing about, reported rather than patched:
    # the Geoscheme sheet is DJ's canon and this script does not get to edit it.
    conflicts = collections.defaultdict(set)
    for r in rows:
        conflicts[r["subregion"]].add(r["continent"])
    conflicts = {k: sorted(v) for k, v in conflicts.items() if len(v) > 1}
    ws.append([])
    ws.append(["Source data notes"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    if conflicts:
        for sub, conts in conflicts.items():
            members = [r["name"] for r in rows if r["subregion"] == sub]
            ws.append([f"Subregion '{sub}' is listed under {' and '.join(conts)}",
                       ", ".join(members), "", "check the Geoscheme sheet"])
    else:
        ws.append(["Every subregion belongs to exactly one continent", "", "", "OK"])
    ws.append([])
    ws.append(["Hinterland pairs and the cargo they move"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append(["Hub", "Partner", "Cargo units", ""])
    for hub, partner, vol in pairs:
        ws.append([hub, partner, round(vol), ""])
    _widths(ws, [40, 20, 20, 26])

    try:
        wb.save(OUT)
    except PermissionError:
        raise SystemExit(
            f"\nCannot write {OUT}\n"
            "The workbook is open in Excel, which locks the file. Close it and re-run.\n"
            "Nothing was changed, and any edits you made in the Overrides or Transit\n"
            "sheets are safe: save them in Excel first, then close it, then re-run."
        )
    return OUT


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--summary", action="store_true", help="print the top 25 and exit")
    ap.add_argument("--compare", action="store_true",
                    help="print the Earth 2015 comparison and exit")
    ap.add_argument("--fresh", action="store_true",
                    help="ignore the Overrides sheet from a previous build")
    args = ap.parse_args()

    countries = load_countries()
    cargo, port_rows = load_ports()
    production, skipped = load_production()
    production.update(load_oil_gas())

    unknown = sorted(set(cargo) - set(countries))
    if unknown:
        print(f"note: port countries not in the Geoscheme sheet: {unknown}", file=sys.stderr)

    overrides = {} if args.fresh else load_overrides()
    if overrides:
        print(f"honouring {len(overrides)} hand-set archetypes from the Overrides sheet")
    rows, pairs, meta = run_model(countries, cargo, production, args.seed, overrides)

    if args.compare:
        metrics, verdict = earth_comparison(rows, meta)
        print(f"{'METRIC':<46}{'ANDAH':>9}{'EARTH 2015':>12}   VERDICT")
        print("-" * 88)
        for label, a, e, tol, _note in metrics:
            print(f"{label:<46}{a:>9.3f}{e:>12.3f}   {verdict(a, e, tol)}")
        bad = [m[0] for m in metrics if verdict(m[1], m[2], m[3]) != "realistic"]
        print()
        print(f"{len(metrics)-len(bad)}/{len(metrics)} metrics realistic"
              + (f"; off: {bad}" if bad else ""))
        return

    T = 1e12
    print(f"World GDP {meta['world_gdp']/T:,.1f}T   "
          f"exports {sum(r['total_x'] for r in rows)/T:,.1f}T   "
          f"imports {sum(r['total_m'] for r in rows)/T:,.1f}T   seed {args.seed}")
    print()
    print(f"{'#':>3} {'COUNTRY':<15}{'EXPORTS':>10}{'IMPORTS':>10}{'BALANCE':>10}"
          f"{'TRADE/GDP':>10}  {'DVA':>5}  {'ARCHETYPE':<24}LEADING EXPORT")
    print("-" * 118)
    for i, r in enumerate(sorted(rows, key=lambda x: -x["total_x"])[:25], 1):
        print(f"{i:>3} {r['name']:<15}{r['total_x']/T:>9.2f}T{r['total_m']/T:>9.2f}T"
              f"{r['balance']/T:>9.2f}T{r['trade_gdp']:>9.0%}  {r['dva_share']:>4.0%}  "
              f"{r['archetype']:<24}{r['leading']}")

    if args.summary:
        return
    path = write_workbook(rows, pairs, meta, production, skipped, port_rows)
    print()
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
