#!/usr/bin/env python3
"""
andah_data.py - one loader for every real Andah dataset the trade model uses.

Kept separate from the model so the model file is only economics, and so the
provenance of every number is in one readable place. Nothing here invents
anything: each function returns what DJ's own files actually contain.

SOURCES
  geojson     Desktop/Andah games/andah_games/data/andah-countries.geojson
              172 country polygons in lon/lat, with areaKm2 and a neighbours
              list carrying SHARED BORDER LENGTH IN KM. This is the single best
              geographic source in the project: exact, complete, and its
              adjacency graph is 100% reciprocated.
  history     .../data/gdp-history.json     population 1700-1765 (66 years)
              .../data/gdp-growth.json      annual growth rates, same span
  flights     .../data/flight-network.json  591 airports, 10,445 routes with
              distance and demand. An INDEPENDENT bilateral linkage network,
              used to calibrate and validate the gravity model rather than
              assuming its coefficients.
  janus       data/Andah_Janus Statistics.xlsx  Geoscheme sheet: continent,
              subregion, population, area, GDP nominal and per capita, 1765.
  ports       data/Top 60 Container Ports.xlsx
  production  data/Production Statistics.xlsx + data/Oil_Gas Statistics.xlsx

THE LAHN WAS REDENOMINATED, AND THIS FILE RESOLVES IT
  The Janus 'ALL' sheet and the games data carry a per-capita figure exactly 8x
  the one implied by the Geoscheme sheet. That is not an error: the lahn was
  revalued 8x, the wiki was converted page by page, and Geoscheme is simply the
  one file still holding OLD lahn. So load_janus takes GDP and GDP per capita
  from the games folder's countries.json (NEW lahn) and everything non-monetary
  from Geoscheme, and refuses to run if the two ever differ by anything other
  than exactly 1x or 8x. Every lahn figure this project emits is new lahn.
"""

import collections
import json
import math
import os

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
GAMES = r"C:\Users\danny\Desktop\Andah games\andah_games\data"

JANUS = os.path.join(DATA, "Andah_Janus Statistics.xlsx")
PORTS = os.path.join(DATA, "Top 60 Container Ports.xlsx")
PRODUCTION = os.path.join(DATA, "Production Statistics.xlsx")
OILGAS = os.path.join(DATA, "Oil_Gas Statistics.xlsx")

SUMMARY_SHEETS = {"Fossil fuels", "Nuclear fuel", "Gemstones", "Metals", "Mineral"}
EARTH_YEAR_OFFSET = 250          # 1765 AFA == 2015 Earth, confirmed by the population series

R_EARTH_KM = 6371.0


# ---------------------------------------------------------------------------
# core country table
# ---------------------------------------------------------------------------

def load_janus():
    """
    Continent, subregion, area, population, GDP nominal and per capita, x172.

    THE LAHN WAS REDENOMINATED. The Geoscheme sheet carries the OLD lahn; the
    games folder's countries.json carries the NEW one, exactly 8.0000x higher for
    every one of the 172 countries (checked: min, median and max ratio all 8.0000).
    The wiki was converted page by page (.lahn_scaled.json lists them) and the
    Janus 'ALL' sheet's Per (NOM) column already shows the new figure, which is
    why that column looked "8x too high" against Geoscheme's own GDP/population.

    So GDP and GDP per capita are taken from countries.json, and everything
    non-monetary (continent, subregion, area, population) from Geoscheme, which
    is still the authoritative roster. The guard below refuses to run if the two
    sources ever disagree by anything other than exactly 1x or 8x: if the
    Geoscheme sheet is later converted to new lahn, that is the moment a silent
    double-scaling would otherwise begin.
    """
    wb = openpyxl.load_workbook(JANUS, read_only=True, data_only=True)
    ws = wb["Geoscheme"]
    out = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or not r[2] or not isinstance(r[7], (int, float)):
            continue
        name = str(r[2]).strip()
        out[name] = dict(
            name=name,
            continent=str(r[0]).strip(),
            subregion=str(r[1]).strip(),
            area_janus=float(r[3] or 0),
            population=float(r[4] or 0),
            gdp_ppp=float(r[6] or 0),
            gdp_geoscheme=float(r[7]),
            gdp=float(r[7]),
            gdp_pc=float(r[8]) if isinstance(r[8], (int, float)) else 0.0,
        )
    wb.close()

    path = os.path.join(GAMES, "countries.json")
    with open(path, encoding="utf-8") as fh:
        games = {c["name"]: c.get("metrics", {})
                 for c in json.load(fh).get("countries", [])}
    lower = {k.lower(): k for k in games}
    ratios = []
    for name, c in out.items():
        g = games.get(name) or games.get(lower.get(name.lower(), ""))
        if not g:
            continue
        new_gdp = g.get("GDP (Nominal)")
        new_pc = g.get("Per (NOM)")
        if not isinstance(new_gdp, (int, float)) or new_gdp <= 0:
            continue
        ratio = new_gdp / c["gdp_geoscheme"] if c["gdp_geoscheme"] else 0.0
        ratios.append(ratio)
        c["gdp"] = float(new_gdp)
        c["gdp_pc"] = float(new_pc) if isinstance(new_pc, (int, float)) else (
            c["gdp"] / c["population"] if c["population"] else 0.0)
        c["lahn_ratio"] = ratio
    if ratios:
        lo, hi = min(ratios), max(ratios)
        ok = (abs(lo - 8.0) < 0.01 and abs(hi - 8.0) < 0.01) or (abs(lo - 1.0) < 0.01 and abs(hi - 1.0) < 0.01)
        if not ok:
            raise SystemExit(
                f"countries.json and the Geoscheme sheet disagree on GDP by a factor "
                f"between {lo:.3f} and {hi:.3f}. Expected exactly 8x (Geoscheme in old "
                f"lahn) or exactly 1x (Geoscheme converted). Anything else means one of "
                f"them was partly edited; sort that out before trusting a lahn figure.")
        LAHN_STATE["ratio"] = ratios[0]
    return out


# What load_janus found: 8.0 means Geoscheme is still in old lahn and GDP came
# from countries.json; 1.0 means the two agree. Surfaced in the workbook.
LAHN_STATE = {"ratio": None}


# ---------------------------------------------------------------------------
# geography
# ---------------------------------------------------------------------------

def _ring_area_centroid(ring):
    """Planar signed area and centroid of a lon/lat ring. Sign gives winding."""
    a = cx = cy = 0.0
    n = len(ring)
    for i in range(n - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    a *= 0.5
    if abs(a) < 1e-12:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return 0.0, (sum(xs) / len(xs), sum(ys) / len(ys))
    return a, (cx / (6 * a), cy / (6 * a))


def _ring_perimeter_km(ring):
    total = 0.0
    for i in range(len(ring) - 1):
        total += haversine_km(ring[i][0], ring[i][1], ring[i + 1][0], ring[i + 1][1])
    return total


def haversine_km(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH_KM * math.asin(min(1.0, math.sqrt(h)))


def load_geography():
    """
    Centroid, area, land perimeter, shared-border lengths and coastline per country.

    Landlocked is DERIVED, not asserted: a country is landlocked when essentially
    all of its outline is shared with land neighbours, so no stretch of boundary
    faces water. That is a measurement off DJ's own polygons rather than a guess
    from prose, and it is why this replaces the earlier wiki-text extraction.
    """
    path = os.path.join(GAMES, "andah-countries.geojson")
    with open(path, encoding="utf-8") as fh:
        gj = json.load(fh)

    geo = {}
    for feat in gj["features"]:
        p = feat["properties"]
        name = p["name"]
        polys = feat["geometry"]["coordinates"]

        # ANTIMERIDIAN. One country (Ashain) has territory on both sides of the
        # 180th meridian, spanning -179.78 to +177.70. Averaging those longitudes
        # as plain numbers puts its centroid at +78, roughly 8,500 km from where
        # it actually is, which would corrupt its distance to every other country
        # and so its openness, its gravity flows and its trade partners.
        # Its own airports give the true value (circular mean +158.9), which is
        # what this reproduces: shift the western lobe east by 360 degrees,
        # average in that continuous frame, then wrap the answer back.
        all_lons = [pt[0] for poly in polys for ring in poly for pt in ring]
        wrap = (max(all_lons) - min(all_lons)) > 180.0

        def unwrap(x):
            return x + 360.0 if (wrap and x < 0) else x

        tot_w = 0.0
        sx = sy = 0.0
        perim = 0.0
        for poly in polys:
            outer = [(unwrap(x), y) for x, y in poly[0]]
            a, (cx, cy) = _ring_area_centroid(outer)
            w = abs(a)
            tot_w += w
            sx += cx * w
            sy += cy * w
            # perimeter uses haversine on the ORIGINAL coordinates: it already
            # handles the wrap correctly through the sine of the difference
            perim += _ring_perimeter_km(poly[0])
        if tot_w > 0:
            lon, lat = sx / tot_w, sy / tot_w
            if lon > 180.0:
                lon -= 360.0
        else:
            lon, lat = p.get("label", [0, 0])

        borders = {n["name"]: float(n["km"]) for n in p.get("neighbours", [])}
        shared = sum(borders.values())
        # Shared borders are counted once per side; the polygon perimeter counts
        # that same stretch once for this country. Coastline is what is left.
        coast = max(0.0, perim - shared)

        geo[name] = dict(
            name=name,
            lon=lon, lat=lat,
            area_km2=float(p.get("areaKm2") or 0),
            polygons=int(p.get("polygons") or len(polys)),
            perimeter_km=perim,
            borders=borders,
            shared_border_km=shared,
            coast_km=coast,
            coast_share=coast / perim if perim > 0 else 0.0,
            label_span_km=float(p.get("labelSpanKm") or 0),
        )

    # landlocked: no meaningful coastline. 2% of outline is the tolerance for
    # polygon noise along a shared border.
    for g in geo.values():
        g["landlocked"] = g["coast_share"] < 0.02
        g["is_island"] = len(g["borders"]) == 0
    return geo


def distance_matrix(geo, names):
    """Great-circle km between every pair of country centroids."""
    d = {}
    for a in names:
        ga = geo.get(a)
        if not ga:
            continue
        for b in names:
            if a == b:
                continue
            gb = geo.get(b)
            if not gb:
                continue
            d[(a, b)] = haversine_km(ga["lon"], ga["lat"], gb["lon"], gb["lat"])
    return d


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------

def load_population_history():
    """{country: {afa_year: population}} for 1700-1765."""
    path = os.path.join(GAMES, "gdp-history.json")
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = {}
    for rec in raw["countries"]:
        series = {}
        for row in rec.get("rows", []):
            if len(row) >= 3 and isinstance(row[1], (int, float)):
                series[int(row[1])] = float(row[2])
        if series:
            out[rec["name"]] = series
    return out


def load_growth_history():
    """{country: {afa_year: real growth rate}} for 1700-1765."""
    path = os.path.join(GAMES, "gdp-growth.json")
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = {}
    for name, rec in raw.get("countries", {}).items():
        g = rec.get("growth") or {}
        series = {}
        for k, v in g.items():
            try:
                series[int(k) - EARTH_YEAR_OFFSET] = float(v)
            except (TypeError, ValueError):
                continue
        if series:
            out[name] = series
    return out


def backcast_gdp(countries, pophist, growth, years):
    """
    GDP per capita and GDP for earlier benchmark years.

    Anchored on the known 1765 per-capita figure and walked backwards through
    DJ's own annual growth series, so the earlier years are implied by data he
    already authored rather than invented here. GDP is then per-capita times his
    population series for that year.
    """
    out = {}
    for name, c in countries.items():
        g = growth.get(name, {})
        pops = pophist.get(name, {})
        pc = {1765: c["gdp_pc"]}
        for y in range(1764, 1699, -1):
            rate = g.get(y + 1, 0.0)          # growth INTO year y+1
            pc[y] = pc[y + 1] / (1.0 + rate) if rate > -0.95 else pc[y + 1]
        rec = {}
        for y in years:
            pop = pops.get(y)
            if pop is None or y not in pc:
                continue
            rec[y] = dict(population=pop, gdp_pc=pc[y], gdp=pop * pc[y])
        out[name] = rec
    return out


# ---------------------------------------------------------------------------
# flight network - the independent linkage check
# ---------------------------------------------------------------------------

def load_flight_linkage(valid_names):
    """
    Observed bilateral connectivity: {(a,b): {routes, demand, mean_km}}.

    This is the model's one piece of genuine bilateral evidence. It was built by
    DJ for a different purpose entirely, which is exactly what makes it useful:
    the gravity model can be fitted to reproduce it, instead of its coefficients
    being asserted and never tested.
    """
    path = os.path.join(GAMES, "flight-network.json")
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    ap = {a["id"]: a for a in raw["airports"]}
    pairs = {}
    for e in raw.get("routes", []):
        a, b = ap.get(e.get("from")), ap.get(e.get("to"))
        if not a or not b:
            continue
        ca, cb = a.get("country"), b.get("country")
        if ca == cb or ca not in valid_names or cb not in valid_names:
            continue
        key = tuple(sorted((ca, cb)))
        rec = pairs.setdefault(key, dict(routes=0, demand=0.0, km=0.0))
        rec["routes"] += 1
        rec["demand"] += float(e.get("demand") or 0)
        rec["km"] += float(e.get("distanceKm") or 0)
    for rec in pairs.values():
        rec["mean_km"] = rec["km"] / rec["routes"] if rec["routes"] else 0.0
    return pairs


# ---------------------------------------------------------------------------
# ports and production (unchanged sources, tidied loaders)
# ---------------------------------------------------------------------------

def load_ports():
    wb = openpyxl.load_workbook(PORTS, read_only=True, data_only=True)
    cargo, rows = {}, []
    for r in wb["Sheet1"].iter_rows(min_row=2, values_only=True):
        if not r or not r[1] or not isinstance(r[5], (int, float)):
            continue
        country = str(r[2]).strip()
        cargo[country] = cargo.get(country, 0.0) + float(r[5])
        rows.append(dict(port=str(r[1]).strip(), country=country,
                         region=str(r[3] or "").strip(),
                         location=str(r[4] or "").strip(), cargo=float(r[5])))
    wb.close()
    return cargo, rows


def _country_col(header, rows):
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
    """{commodity: {country: share of world output}} across all parseable sheets."""
    wb = openpyxl.load_workbook(PRODUCTION, read_only=True, data_only=True)
    shares, skipped = {}, []
    for sheet in wb.sheetnames:
        label = sheet.strip()
        if label in SUMMARY_SHEETS:
            continue
        rows = [r for r in wb[sheet].iter_rows(values_only=True)
                if r and any(x is not None for x in r)]
        if len(rows) < 3:
            skipped.append((label, "empty")); continue
        header = [str(x).strip() if x else "" for x in rows[0]]
        ci = _country_col(header, rows)
        if ci is None:
            skipped.append((label, "no country column")); continue
        pi = None
        for j in range(ci + 1, len(header)):
            if sum(1 for r in rows[1:] if j < len(r) and isinstance(r[j], (int, float))) >= 3:
                pi = j; break
        if pi is None:
            skipped.append((label, "no numeric column")); continue
        per, world = {}, None
        for r in rows[1:]:
            if ci >= len(r) or not r[ci] or pi >= len(r):
                continue
            nm = str(r[ci]).strip()
            v = r[pi]
            if not isinstance(v, (int, float)) or v <= 0:
                continue
            low = nm.lower()
            # World-total rows are spelled three different ways across these
            # sheets ("World", "World total", "World Total"). Matching only the
            # bare word let the other two through AS COUNTRIES, carrying shares
            # of 107% and 58%, which corrupted the denominator wherever a sheet
            # had no exact "World" row.
            if low.startswith("world"):
                world = max(world or 0.0, float(v))
            elif low.startswith("other") or low in ("country", "total", "rank"):
                continue
            else:
                per[nm] = per.get(nm, 0.0) + float(v)
        if not per:
            skipped.append((label, "no country rows")); continue
        total = world if world and world > 0 else sum(per.values())
        shares[label] = {k: v / total for k, v in per.items()}
    wb.close()
    return shares, skipped


# Producer names in Production Statistics.xlsx that are misspellings of a
# canonical country. Curated deliberately rather than fuzzy-matched at run time:
# a blind matcher would happily bind a genuinely unknown producer to whatever
# looked closest and hide the problem. Each of these was confirmed by eye against
# the canonical list. "Ecuador" is an Earth country left in the sheet by accident
# and is intentionally NOT mapped.
PRODUCER_ALIASES = {
    "Oscaira": "Oscairia",
    "Palugrotoa": "Pelugrotoa",
    "Etreres": "Etretes",
    "Ethirha": "Etirha",
    "Areoix Luie": "Areoix Lie",
    "Rijan Bu": "Rijan bu",
    "Yaxuro": "Yaxuto",
    "Ralesria": "Raledria",
    "Mestijan Hyaa": "Mesjan Hyaa",
    "Andasudare": "Andsaudare",
    "Nheyea Si": "Nheyes Si",
    "Heylen": "Hyelen",
    "Ianoa": "Iainoa",
    "Yihnurga": "Yihnurda",
    "Saremeh (Easuhura)": "Easuhura",
}


def canonicalise_production(shares, valid):
    """
    Fold misspelled producer names into their canonical country, renormalise each
    commodity to sum to 1, and report everything that had to be corrected.

    RENORMALISATION IS NOT COSMETIC. Twelve of these sheets do not sum to 100%
    of world output as loaded. Palladium reaches 237% because the sheet stacks
    three decade tables one under another and every row is accumulated into the
    same producer; Bismuth is 135% and Bentonite 123%. Others fall short (Gold
    75%) because a chunk of output sits in an "other countries" row that is
    deliberately skipped. Either way the raw numbers are not shares of anything,
    so a country's resource score would be scaled by an arbitrary per-commodity
    factor of between 0.75 and 2.4. Rescaling each commodity to sum to 1 makes
    every one a true share; the relative standing of producers within a commodity,
    which is what the model actually uses, is untouched.
    """
    fixed, unmatched = {}, collections.Counter()
    rescaled, shortfall = {}, {}
    for commodity, per in shares.items():
        out = {}
        for name, share in per.items():
            canon = PRODUCER_ALIASES.get(name, name)
            if canon in valid:
                out[canon] = out.get(canon, 0.0) + share
            else:
                unmatched[name] += share
        total = sum(out.values())
        if total > 1.02:
            # OVER 100%: the sheet stacks several year tables under one header
            # and every row accumulates into the same producer (Palladium 237%,
            # Bismuth 135%, Bentonite 123%). These are not shares of anything
            # and must be rescaled.
            rescaled[commodity] = total
            out = {k: v / total for k, v in out.items()}
        elif total < 0.98 and total > 0:
            # UNDER 100%: the sheet has an explicit "Other countries" row that
            # the loader skips on purpose, so the shortfall is real output by
            # producers the sheet does not name. Rescaling here would be wrong:
            # it silently hands that residual to the listed producers.
            #
            # The Gold sheet proves it. It carries World 3300 AND
            # "Other countries 780" (23.6%), and prints its own percentages -
            # Gaeiya 11.5%, Iareva 9.4%. An earlier version of this function
            # rescaled every commodity that missed 100% in either direction,
            # which restated Gaeiya as holding 15.4% of world gold, contradicting
            # the spreadsheet's own column, and flipped Arbiya's leading export
            # from silver to gold because gold was scaled by 1.34 and silver by
            # only 1.02. Shares are left alone here and reported instead.
            shortfall[commodity] = total
        fixed[commodity] = out
    return fixed, unmatched, rescaled, shortfall


def load_oil_gas():
    out = {}
    try:
        wb = openpyxl.load_workbook(OILGAS, read_only=True, data_only=True)
    except Exception:
        return out
    for sheet, key in (("Oil", "Oil"), ("Gas", "Natural Gas")):
        if sheet not in wb.sheetnames:
            continue
        per, world = {}, None
        for r in wb[sheet].iter_rows(min_row=2, values_only=True):
            if not r or not r[0] or len(r) < 5:
                continue
            # names carry a source suffix such as "Sunsokua (MPU)"
            nm = str(r[0]).split("(")[0].strip()
            v = r[4]
            if not isinstance(v, (int, float)) or v <= 0:
                continue
            # These sheets carry a world-total row too, and it was previously
            # counted as a producer. Because that row equals the sum of the
            # countries, including it doubled the denominator and HALVED every
            # country's oil and gas share. Oil alone is 40% of the commodity
            # weighting, so this quietly suppressed every petro economy.
            if nm.lower().startswith("world") or nm.lower() in ("total", "country"):
                world = max(world or 0.0, float(v))
                continue
            per[nm] = per.get(nm, 0.0) + float(v)
        if per:
            total = world if world and world > 0 else sum(per.values())
            out[key] = {k: v / total for k, v in per.items()}
    wb.close()
    return out


# ---------------------------------------------------------------------------

def load_all():
    """Everything, keyed on the 172 Janus country names, with a reconciliation report."""
    countries = load_janus()
    geo = load_geography()

    # the geojson carries one lowercase name; match case-insensitively rather
    # than hand-patching, so any future casing drift also resolves itself
    lower = {k.lower(): k for k in geo}
    fixed = {}
    for name in countries:
        if name in geo:
            fixed[name] = geo[name]
        elif name.lower() in lower:
            fixed[name] = geo[lower[name.lower()]]
    # rewrite border keys onto Janus spelling too
    canon = {k.lower(): k for k in countries}
    for g in fixed.values():
        g["borders"] = {canon.get(k.lower(), k): v for k, v in g["borders"].items()}

    production, skipped = load_production()
    production.update(load_oil_gas())
    production, unmatched_producers, rescaled, shortfall = canonicalise_production(
        production, set(countries))

    # THE WIKI PRODUCTION TABLES ARE THE PRIMARY SOURCE.
    #
    # DJ: "use all pages in the Category:Statistics page, this is all the data to
    # do with production i have." Those pages and Production Statistics.xlsx are
    # the same data for 24 of the 29 commodities that appear in both, agreeing to
    # the last percent. Where they disagree the wiki wins, because the wiki page
    # is what a reader sees and what an article would cite; a model that
    # contradicted the published table would be wrong on its face.
    #
    # The workbook still fills the gaps: Oil, Natural Gas, Motor vehicle and
    # Paper have no wiki page, and Niobium's page is transposed (years down the
    # side, countries across the top) so it cannot be read the same way.
    wiki_conflicts = []
    try:
        import wiki_production
        wiki_prod, wiki_report = wiki_production.load_wiki_production()
    except Exception as exc:                     # never let a parse fault stop a build
        wiki_prod, wiki_report = {}, [("wiki_production", f"failed: {exc}", "")]
    for commodity, per in wiki_prod.items():
        old = production.get(commodity)
        if old:
            sa = sum(old.values()) or 1.0
            sb = sum(per.values()) or 1.0
            diff = sum(abs(per.get(k, 0) / sb - old.get(k, 0) / sa)
                       for k in set(per) | set(old)) / 2
            if diff > 0.02:
                top_w = max(per.items(), key=lambda kv: kv[1])[0]
                top_x = max(old.items(), key=lambda kv: kv[1])[0]
                wiki_conflicts.append((commodity, 1 - diff, top_w, top_x,
                                       len(per), len(old)))
        production[commodity] = per
    cargo, port_rows = load_ports()

    # The history files carry one lowercase key ('lasri'), which silently cost a
    # country in every benchmark year. Resolve the same way as the geojson.
    pophist = load_population_history()
    growth = load_growth_history()
    for series in (pophist, growth):
        low = {k.lower(): k for k in series}
        for name in countries:
            if name not in series and name.lower() in low:
                series[name] = series.pop(low[name.lower()])

    wiki_evidence = {}
    ev_path = os.path.join(DATA, "wiki_economy_evidence.json")
    if os.path.exists(ev_path):
        with open(ev_path, encoding="utf-8") as fh:
            wiki_evidence = json.load(fh).get("evidence", {})

    try:
        import wiki_canon
        financial_centres, gfci_report = wiki_canon.load_financial_centres()
        blocs = wiki_canon.load_blocs()
    except Exception as exc:
        financial_centres, gfci_report, blocs = {}, [("wiki_canon", str(exc))], {}

    return dict(
        countries=countries,
        geo=fixed,
        wiki_evidence=wiki_evidence,
        financial_centres=financial_centres,
        gfci_report=gfci_report,
        blocs=blocs,
        production=production,
        production_skipped=skipped,
        cargo=cargo,
        port_rows=port_rows,
        pophist=pophist,
        growth=growth,
        unmatched_producers=unmatched_producers,
        rescaled_commodities=rescaled,
        wiki_conflicts=wiki_conflicts,
        wiki_report=wiki_report,
        wiki_commodities=sorted(wiki_prod),
        shortfall_commodities=shortfall,
        flights=load_flight_linkage(set(countries)),
    )


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    d = load_all()
    c, g = d["countries"], d["geo"]
    print(f"countries        {len(c)}")
    print(f"geography        {len(g)}/{len(c)} matched")
    ll = [n for n, x in g.items() if x["landlocked"]]
    isl = [n for n, x in g.items() if x["is_island"]]
    print(f"landlocked       {len(ll)}  {sorted(ll)[:8]}")
    print(f"islands          {len(isl)}  {sorted(isl)[:8]}")
    print(f"commodities      {len(d['production'])} (skipped {len(d['production_skipped'])})")
    if d['rescaled_commodities']:
        print(f"rescaled         {len(d['rescaled_commodities'])} commodities did not sum to 100%:")
        for _cm, _t in sorted(d['rescaled_commodities'].items(), key=lambda kv: -kv[1])[:6]:
            print(f"                   {_cm:<16}{_t:8.1%}")
    if d['shortfall_commodities']:
        print(f"shortfall        {len(d['shortfall_commodities'])} commodities list under 100% "
              f"(an 'other countries' row); left as-is:")
        for _cm, _t in sorted(d['shortfall_commodities'].items(), key=lambda kv: kv[1])[:5]:
            print(f"                   {_cm:<16}{_t:8.1%}")
    print(f"wiki production   {len(d['wiki_commodities'])} commodities read from Category:Statistics pages")
    if d['wiki_conflicts']:
        print(f"  {len(d['wiki_conflicts'])} disagree with the workbook (wiki wins):")
        for _c, agree, tw, tx, nw, nx in sorted(d['wiki_conflicts'], key=lambda x: x[1]):
            note = f"top: wiki {tw}, xlsx {tx}" if tw != tx else f"same leader, {nw} vs {nx} producers"
            print(f"     {_c:<14}{agree:6.0%} agreement   {note}")
    if d['unmatched_producers']:
        print(f"unmatched names  {dict(d['unmatched_producers'])}")
    print(f"port countries   {len(d['cargo'])} over {len(d['port_rows'])} ports")
    print(f"population hist  {len(d['pophist'])} countries")
    print(f"growth hist      {len(d['growth'])} countries")
    print(f"flight pairs     {len(d['flights'])} international country-pairs")
    tot_area_gj = sum(x["area_km2"] for x in g.values())
    tot_area_jn = sum(x["area_janus"] for x in c.values())
    print(f"area cross-check geojson {tot_area_gj:,.0f} km2 vs Janus {tot_area_jn:,.0f} km2 "
          f"({tot_area_gj/tot_area_jn:.1%})")
