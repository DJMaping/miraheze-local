#!/usr/bin/env python3
"""
export_trade_json.py - packs the trade model into one JSON for the atlas artifact.

The polygons are the point of the map, so they need to survive simplification
with their silhouettes intact. Douglas-Peucker on each ring keeps the corners
that define a coastline and drops the vertices between them, which is what a
printed chart does when it changes scale.
"""

import io
import json
import math
import os
import sys

import andah_data as ad
import build_trade_model as M
import trade_baskets as tb
import trade_subcategories as tsub
import earth_products as EP

OUT = os.path.join(ad.HERE, "andah_trade_atlas.json")
EPSILON = 0.14        # degrees; ~15 km at the equator
MIN_RING_AREA = 0.30  # drop islands smaller than this, in square degrees


def perpendicular_distance(pt, a, b):
    (x, y), (x1, y1), (x2, y2) = pt, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def simplify(points, eps):
    """Douglas-Peucker, iterative so a long coastline cannot blow the stack."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        lo, hi = stack.pop()
        worst, idx = 0.0, -1
        for i in range(lo + 1, hi):
            d = perpendicular_distance(points[i], points[lo], points[hi])
            if d > worst:
                worst, idx = d, i
        if worst > eps and idx > 0:
            keep[idx] = True
            stack.append((lo, idx))
            stack.append((idx, hi))
    return [p for p, k in zip(points, keep) if k]


def ring_area(ring):
    a = 0.0
    for i in range(len(ring) - 1):
        a += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    return abs(a) / 2.0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    data = ad.load_all()
    rows, flows, meta = M.run(data)
    metrics, verdict = M.earth_comparison(rows, meta)

    # THE EARLIER BENCHMARKS. The model has always been able to run 1725 and
    # 1745 - population from DJ's series, income walked back through his own
    # growth rates, world openness set to the era's shipping technology - but
    # only three summary numbers ever left the building. Carrying the per-country
    # figures through is what lets a country page say how its trade grew and what
    # it used to sell.
    history, hist_world = {}, {}
    for y in M.BENCHMARK_YEARS:
        if y == meta["year"]:
            continue
        yrows, _yflows, ymeta = M.run_year(data, y)
        if not yrows:
            continue
        hist_world[y] = dict(gdp=round(ymeta["world_gdp"]),
                             exports=round(sum(r["total_x"] for r in yrows)))
        for r in yrows:
            history.setdefault(r["name"], {})[y] = dict(
                x=round(r["total_x"]), gdp=round(r["gdp"]),
                lead=r["basket"] and max(r["basket"], key=r["basket"].get),
                trade_gdp=round(r["trade_gdp"], 3))
        print(f"  {y}: {len(yrows)} countries, "
              f"{sum(r['total_x'] for r in yrows)/1e12:.1f}T exports")

    with open(os.path.join(ad.GAMES, "andah-countries.geojson"), encoding="utf-8") as fh:
        gj = json.load(fh)

    canon = {k.lower(): k for k in data["countries"]}
    shapes, kept_pts, raw_pts = {}, 0, 0
    for feat in gj["features"]:
        name = canon.get(feat["properties"]["name"].lower())
        if not name:
            continue
        rings = []
        for poly in feat["geometry"]["coordinates"]:
            ring = [(round(x, 3), round(y, 3)) for x, y in poly[0]]
            raw_pts += len(ring)
            rings.append((ring_area(ring), ring))
        rings.sort(key=lambda t: -t[0])
        parts = []
        for i, (area, ring) in enumerate(rings):
            # Always keep a country's LARGEST landmass, however small it is in
            # world terms. Filtering purely on area silently erased 18 island
            # states from the map entirely, which is the one thing an atlas
            # cannot do: a country with no shape reads as a country that is not
            # there. Smaller islands beyond the first still get dropped.
            if i > 0 and area < MIN_RING_AREA:
                continue
            eps = EPSILON if i == 0 else EPSILON * 1.6
            simp = simplify(ring, eps)
            if len(simp) < 4 and i == 0:
                simp = ring[:: max(1, len(ring) // 8)] + [ring[-1]]
            if len(simp) >= 4:
                parts.append([[q[0], q[1]] for q in simp])
                kept_pts += len(simp)
        if parts:
            shapes[name] = parts

    by = {r["name"]: r for r in rows}
    world_x = sum(r["total_x"] for r in rows)
    hubs = {h for h, *_ in M.TRANSIT}

    # Every partner, not just the top five: the treemaps need the whole
    # distribution. Anything under 0.2% of a country's flow is folded into
    # "Other" so the file stays small and the treemap stays legible.
    out_flows, in_flows = {}, {}
    for (a, b), v in flows.items():
        out_flows.setdefault(a, []).append((b, v))
        in_flows.setdefault(b, []).append((a, v))

    def distribution(items):
        tot = sum(v for _, v in items) or 1.0
        items = sorted(items, key=lambda x: -x[1])
        keep = [[n, round(v)] for n, v in items if v / tot >= 0.002]
        rest = sum(v for n, v in items if v / tot < 0.002)
        if rest > 0:
            keep.append(["Other", round(rest)])
        return keep

    # WHO BUYS WHAT. The model now solves a separate bilateral matrix per
    # category, so this is a real answer rather than a country's basket
    # multiplied by its partner list: the buyers of a country's oil and the
    # buyers of its electronics are genuinely different sets of countries.
    # Trimmed to the five largest per category, which is what a page shows.
    by_cat = meta.get("flows_by_cat") or {}
    cat_out, cat_in, cat_in_val = {}, {}, {}
    for k, f in by_cat.items():
        o, i = {}, {}
        for (a, b), v in f.items():
            o.setdefault(a, []).append((b, v))
            i.setdefault(b, []).append((a, v))
        for name, items in o.items():
            items.sort(key=lambda t: -t[1])
            tot = sum(v for _, v in items) or 1.0
            cat_out.setdefault(name, {})[k] = [[q, round(v / tot, 4)] for q, v in items[:14]]
        for name, items in i.items():
            items.sort(key=lambda t: -t[1])
            tot = sum(v for _, v in items) or 1.0
            cat_in.setdefault(name, {})[k] = [[q, round(v / tot, 4)] for q, v in items[:14]]
            # the country's own import bill for this category, so the treemap can
            # state a real total instead of inferring one from the world's mix
            cat_in_val.setdefault(name, {})[k] = round(tot)

    # PORTS. The cargo tables name 60 quays across 37 countries and their
    # throughput sums exactly to each country's total, so a country's seaborne
    # goods can be split across its own ports without inventing anything.
    #
    # The own/transit split is inherited from the country and applied to every
    # port in it in proportion. That IS an assumption - the data does not say
    # which quay carries the hinterland cargo and which loads the country's own
    # exports - and it is why the atlas labels the split as the country's rather
    # than the port's.
    by_name = {r["name"]: r for r in rows}
    port_rows = sorted(data.get("port_rows") or [], key=lambda r: -r["cargo"])
    world_rank = {r["port"]: i + 1 for i, r in enumerate(port_rows)}
    by_country = {}
    for r in port_rows:
        by_country.setdefault(r["country"], []).append(r)
    ports = {}
    for name, rs in by_country.items():
        row = by_name.get(name)
        if not row:
            continue
        tot = sum(x["cargo"] for x in rs) or 1.0
        seaborne = max(row["goods_x"], 0.0) + max(row["goods_m"], 0.0)
        ports[name] = [[x["port"], round(x["cargo"]), round(x["cargo"] / tot, 4),
                        x.get("location") or "", world_rank[x["port"]],
                        round(seaborne * x["cargo"] / tot)] for x in rs]

    # THE QUIAN UNION, counted the way Eurostat counts the EU: only trade that
    # crosses the union's outer border. Trade between members is internal and is
    # left out of the union's exports entirely, which is the whole point of
    # looking at a bloc this way - it answers what the union sells to the world
    # rather than what its members sell each other.
    UNIONS = {
        "Quian Union": ["Ahokini", "Anymna", "Baluyde", "Desaki", "Erkizil",
                        "Finae", "Myla", "Onphello", "Quidic", "Verste",
                        "Wundry", "Yihnurda", "Ztesh"],
    }
    unions = {}
    for uname, members in UNIONS.items():
        members = [x for x in members if x in by_name]
        mset = set(members)
        ux = um = intra = 0.0
        dest, src = {}, {}
        for (a, b), v in flows.items():
            if a in mset and b in mset:
                intra += v
            elif a in mset:
                ux += v
                dest[b] = dest.get(b, 0.0) + v
            elif b in mset:
                um += v
                src[a] = src.get(a, 0.0) + v
        cats_x, cats_m = {}, {}
        cat_dest, cat_src = {}, {}
        for k, f in (meta.get("flows_by_cat") or {}).items():
            for (a, b), v in f.items():
                if a in mset and b not in mset:
                    cats_x[k] = cats_x.get(k, 0.0) + v
                    cat_dest.setdefault(k, {})[b] = cat_dest.setdefault(k, {}).get(b, 0.0) + v
                elif b in mset and a not in mset:
                    cats_m[k] = cats_m.get(k, 0.0) + v
                    cat_src.setdefault(k, {})[a] = cat_src.setdefault(k, {}).get(a, 0.0) + v
        tot_cx = sum(cats_x.values()) or 1.0

        def top(dd, cap=14):
            items = sorted(dd.items(), key=lambda t: -t[1])
            tot = sum(v for _, v in items) or 1.0
            return [[q, round(v / tot, 4)] for q, v in items[:cap]]

        unions[uname] = dict(
            name=uname, members=members,
            gdp=round(sum(by_name[x]["gdp"] for x in members)),
            population=round(sum(by_name[x]["population"] for x in members)),
            x=round(ux), m=round(um), bal=round(ux - um), intra=round(intra),
            intra_share=round(intra / (intra + ux), 4) if (intra + ux) else 0.0,
            basket={k: round(v / tot_cx, 4) for k, v in cats_x.items()},
            partners=distribution([(q, v) for q, v in dest.items()]),
            buyers=distribution([(q, v) for q, v in src.items()]),
            cat_buyers={k: top(v) for k, v in cat_dest.items()},
            cat_sellers={k: top(v) for k, v in cat_src.items()},
            cat_m={k: round(v) for k, v in cats_m.items()},
        )

    # PRODUCTS BELOW THE CATEGORY. A breakdown of what each country sells, not
    # of who buys it: the 175 products divide the basket, and the 15 categories
    # still carry the flows. Crude against gas is real per-country data; the
    # rest interpolates a poor and a rich profile on income.
    production = data.get("production") or {}
    geo = data["geo"]
    world_x = sum(r["total_x"] for r in rows) or 1.0
    gdps = sorted(r["gdp"] for r in rows)
    median_gdp = gdps[len(gdps) // 2]
    median_pc = sorted(r["gdp_pc"] for r in rows)[len(rows) // 2]
    # the top-25 of DJ's Rovik Global University Rankings page: 25 points for
    # first place down to 1 for 25th, summed by country, as a share of the total
    uni_points = {}
    up = os.path.join(ad.HERE, "pages", "Main", "Rovik_Global_University_Rankings.wiki")
    if os.path.exists(up):
        import re
        txt = open(up, encoding="utf-8").read()
        first = txt.split("{| class=\"wikitable sortable\"")[0] if "{| class=\"wikitable sortable\"" in txt else txt
        rows_ = re.findall(r"\{\{flagicon\|([^}|]+)\}\}[^\n]*\n\|\s*(\d+)", first)
        for cname, rank in rows_:
            rk = int(rank)
            if 1 <= rk <= 25:
                uni_points[cname.strip()] = uni_points.get(cname.strip(), 0.0) + (26 - rk)
        tot = sum(uni_points.values()) or 1.0
        uni_points = {k: v / tot for k, v in uni_points.items()}
        print(f"  universities: {len(rows_)} ranked rows, points for {len(uni_points)} countries: "
              + ", ".join(f"{k} {v:.0%}" for k, v in sorted(uni_points.items(), key=lambda kv: -kv[1])[:5]))
    subs = {}
    for r in rows:
        nm = r["name"]
        g = geo.get(nm, {})
        og = tsub.oil_gas_share(production, nm)
        xshare = r["total_x"] / world_x
        # concentration in each commodity: share of world output over share of
        # world exports, the same measure the resource ceiling already uses
        conc = {}
        for com, per in production.items():
            v = per.get(nm, 0.0)
            if v > 0 and xshare > 0:
                conc[com] = v / xshare
        ctx = dict(lat=g.get("lat", 0.0), coast_share=g.get("coast_share", 0.0),
                   landlocked=g.get("landlocked", False), is_island=g.get("is_island", False),
                   area_km2=g.get("area_km2", 0.0), population=r.get("population", 0.0),
                   oil_share=r["basket"].get("crude_oil_gas", 0.0),
                   finance_weight=r.get("finance_weight", 0.0),
                   mining_share=r["basket"].get("ores_metals", 0.0) + r["basket"].get("precious", 0.0),
                   size_ratio=median_gdp / max(r["gdp"], 1.0),
                   n_borders=len(g.get("borders", [])), pc_rel=r["gdp_pc"] / max(1.0, median_pc),
                   uni_points=uni_points.get(nm, 0.0),
                   business_frac=(r.get("business_x", 0.0) / r["tourism_x"]) if r.get("tourism_x") else None,
                   gdp_pc=r["gdp_pc"], gdp_share=r["gdp"] / (meta["world_gdp"] or 1.0),
                   ports=sum(1 for pr in (data.get("port_rows") or []) if pr["country"] == nm),
                   industry=r["basket"].get("machinery", 0.0) + r["basket"].get("ores_metals", 0.0)
                            + r["basket"].get("vehicles", 0.0))
        # the country's value in each commodity: world-output share x the
        # model's commodity weight, exactly what built its resource categories
        pvals = {com: per.get(nm, 0.0) * M.COMMODITY_WEIGHTS.get(com, 0.1)
                 for com, per in production.items() if per.get(nm, 0.0) > 0}
        sp = tsub.split(r["basket"], r["gdp_pc"], og, ctx=ctx, prod_conc=conc, prod_values=pvals,
                        canon=tsub.canon_for(nm))
        subs[nm] = {k: v for k, v in sp.items() if v > 0.00005}
    # Products outside the resource categories are bent to EARTH'S SHAPE below
    # (earth_products.py): each product's world total is its Earth share of
    # the category, and its spread over countries is matched on Earth's top-1,
    # top-3 and top-10 exporter shares. Resource products are production data
    # and are left alone.
    FIT_ROUNDS, FIT_RESEED, FIT_LAMBDA, FIT_RANK_RCA, FIT_RANK_SIZE = 12, 0.15, (0.6, 0.25), 0.45, 0.90
    FIT_FIXED = {"business_travel"}     # booked on GDP in the model: held as a fixed cell through the fit
    keep = {"crude_oil_gas", "ores_metals", "precious", "refined_fuels"}
    dom_of = {r["name"]: r["domestic_x"] for r in rows}
    # SMALL ECONOMIES DO NOT EXPORT EVERYTHING. A real small economy has
    # meaningful exports in 20-40 products; the median country here had 140 of
    # 175, a long tail of slivers that made every product look shared by half
    # the world (53 countries above 0.5% of world footwear, against Earth's
    # 18). Each country keeps its largest products, the count growing with the
    # size of its economy - about 50 at the median, 18 for the smallest, all of
    # them for a giant - and the pruned weight goes to the survivors within the
    # same category, so the fifteen-category basket is untouched. Resource
    # products are exempt: those are production data.
    gdp_of = {r["name"]: r["gdp"] for r in rows}
    pre_prune = {nm: dict(sp) for nm, sp in subs.items()}
    for nm, sp in subs.items():
        K = int(max(18, min(175, 50.0 * (gdp_of[nm] / median_gdp) ** 0.25)))
        if len(sp) <= K:
            continue
        ranked = sorted(sp.items(), key=lambda kv: -kv[1])
        survivors = {k for k, _ in ranked[:K]}
        # never delete a category's last product, or the basket would change
        for k, v in ranked[K:]:
            if tsub.PARENT[k] in keep or not any(tsub.PARENT[j] == tsub.PARENT[k] for j in survivors):
                survivors.add(k)
        lost = {}
        for k, v in sp.items():
            if k not in survivors:
                lost[tsub.PARENT[k]] = lost.get(tsub.PARENT[k], 0.0) + v
        kept_by_parent = {}
        for k in survivors:
            kept_by_parent[tsub.PARENT[k]] = kept_by_parent.get(tsub.PARENT[k], 0.0) + sp[k]
        subs[nm] = {k: sp[k] * (1.0 + lost.get(tsub.PARENT[k], 0.0) / kept_by_parent[tsub.PARENT[k]])
                    for k in survivors if kept_by_parent.get(tsub.PARENT[k])}
    # EARTH-SHAPED PRODUCTS. For every category that is not a resource:
    #   rows    each country's exports of the category, fixed (the basket);
    #   columns each product's world total, set to Earth's share of that
    #           category (earth_products.EARTH, exports 2015);
    #   shape   each product's column is blended part-way toward Earth's
    #           rank-share curve for that product (leader's share, top three,
    #           top ten, and how many countries hold 1%), then rows and
    #           columns are rescaled, and the whole thing repeated. The
    #           ranking of countries inside a product is the model's own
    #           (canon, endowments, production, population); the blend never
    #           reorders it, only the row rescaling can, and that is where the
    #           specialising happens: a giant held down to Earth's second
    #           place in computers has its electronics total pushed into the
    #           products it leads.
    # The result: toys look like toys (one maker with most of the world and a
    # thin tail), pumps look like pumps (twenty makers, the first with a sixth),
    # and no country's category total moves by a lahn.
    fit_shape = {}
    for par in tsub.SUBS:
        if par in keep:
            continue
        prods = [k for k, _, _ in tsub.SUBS[par]]
        bench = [k for k in prods if k in EP.EARTH]
        if not bench:
            continue
        R = {}
        for nm, sp in subs.items():
            v = sum(sp.get(k, 0.0) for k in prods) * dom_of[nm]
            if v > 0:
                R[nm] = v
        cat_world = sum(R.values())
        if not cat_world:
            continue
        X = {nm: {k: subs[nm].get(k, 0.0) * dom_of[nm] for k in bench} for nm in R}
        fixed_k = [k for k in bench if k in FIT_FIXED]
        free_k = [k for k in bench if k not in FIT_FIXED]
        fixed_tot = sum(X[nm][k] for nm in R for k in fixed_k)
        esum = sum(EP.EARTH[k][0] for k in free_k) or 1.0
        T = {k: (cat_world - fixed_tot) * EP.EARTH[k][0] / esum for k in free_k}
        for k in fixed_k:
            T[k] = sum(X[nm][k] for nm in R)
        # cells held fixed: whole products booked in money by the model
        # (business travel), and shares DJ set outright (CANON_FIXED_SHARE)
        fixed_cells = {(nm, k) for k in fixed_k for nm in R}
        for k in free_k:
            for nm, sh in (tsub.CANON_FIXED_SHARE.get(k) or {}).items():
                if nm in R:
                    X[nm][k] = sh * T[k]
                    fixed_cells.add((nm, k))
        # DJ: education travel follows the top-university list. Booked
        # outright from the Rovik points (85% of the product to the ranked
        # countries in proportion, the rest to everyone by profile), capped at
        # half a country's travel. Left to the fit, the row constraint had
        # handed Raledria two thirds of the world's students.
        if par == "tourism" and uni_points and "education_travel" in free_k:
            ke = "education_travel"
            for nm, upt in uni_points.items():
                if nm in R:
                    X[nm][ke] = min(0.85 * upt * T[ke], 0.5 * R[nm])
                    fixed_cells.add((nm, ke))
        n_fixed_col = {k: sum(1 for nm in R if (nm, k) in fixed_cells) for k in bench}

        def fixed_in_col(k):
            return sum(X[nm][k] for nm in R if (nm, k) in fixed_cells)

        def fixed_in_row(nm):
            return sum(X[nm][k] for k in bench if (nm, k) in fixed_cells)

        def scale_rows():
            for nm in R:
                sm = sum(X[nm][k] for k in bench if (nm, k) not in fixed_cells)
                want = R[nm] - fixed_in_row(nm)
                if sm > 0 and want > 0:
                    f = want / sm
                    for k in bench:
                        if (nm, k) not in fixed_cells:
                            X[nm][k] *= f

        def scale_cols():
            for k in free_k:
                sm = sum(X[nm][k] for nm in R if (nm, k) not in fixed_cells)
                want = T[k] - fixed_in_col(k)
                if sm > 0 and want > 0:
                    f = want / sm
                    for nm in R:
                        if (nm, k) not in fixed_cells:
                            X[nm][k] *= f
        # A product the size pruning removed from a country is seeded back at
        # a fraction of its pre-pruning weight, so Earth's tail (28 countries
        # above 1% of soaps) can be reached where the shape asks for it; the
        # fit thins it again where it does not. Cells the endowments zeroed
        # (ships for the landlocked) stay zero.
        for nm in R:
            for k in free_k:
                if (nm, k) not in fixed_cells and X[nm][k] <= 0 and pre_prune[nm].get(k, 0.0) > 0:
                    X[nm][k] = pre_prune[nm][k] * dom_of[nm] * FIT_RESEED
        for k in free_k:
            if not any(X[nm][k] > 0 for nm in R):
                for nm in R:
                    X[nm][k] = R[nm] * 1e-3
        for rnd in range(FIT_ROUNDS):
            # a big step toward Earth's curve early, a small one late, so the
            # last rounds settle rather than swing
            lam = FIT_LAMBDA[0] if rnd < FIT_ROUNDS // 2 else FIT_LAMBDA[1]
            for k in free_k:
                col = {nm: X[nm][k] for nm in R if X[nm][k] > 0 and (nm, k) not in fixed_cells}
                if len(col) < 2:
                    continue
                # rank by size (sub-linear, so a giant does not lead everything)
                # times relative strength, so the leader in sugar need not be
                # the leader in wheat
                order = {nm: (v ** FIT_RANK_SIZE) * ((v / R[nm]) / (T[k] / cat_world)) ** FIT_RANK_RCA
                         for nm, v in col.items()}
                # DJ's stated ranks go to the head of the order (CANON_RANK)
                canon_rank = tsub.CANON_RANK.get(k)
                if canon_rank:
                    top = max(order.values()) or 1.0
                    for i, nm in enumerate(canon_rank):
                        if nm in order:
                            order[nm] = top * (20.0 - i)
                new = EP.blend(col, EP.EARTH[k], lam, order=order, skip=n_fixed_col[k])
                want = T[k] - fixed_in_col(k)
                sc = want / sum(new.values()) if want > 0 else 0.0
                for nm, v in new.items():
                    X[nm][k] = v * sc
            scale_rows()
        for _ in range(60):
            scale_cols()
            scale_rows()
        for nm in R:
            for k in bench:
                subs[nm][k] = X[nm][k] / dom_of[nm]
    subs = {nm: {k: round(v, 5) for k, v in sp.items() if v > 0.00005} for nm, sp in subs.items()}
    dom_world = sum(dom_of.values()) or 1.0
    product_shape = {}
    for par, k in tsub.KEYS:
        col = {nm: sp.get(k, 0.0) * dom_of[nm] for nm, sp in subs.items() if sp.get(k, 0.0) > 0}
        t1, t3, t10, n1 = EP.shape(col)
        lead = max(col, key=col.get) if col else ""
        product_shape[k] = dict(share=round(sum(col.values()) / dom_world, 5), top1=round(t1, 4),
                                top3=round(t3, 4), top10=round(t10, 4), n=n1, leader=lead,
                                makers=len(col))
    e_shape = {k: dict(share=round(v[0] / EP.EARTH_WORLD_TRADE, 5), top1=v[1], top3=v[2],
                       top10=v[3], n=v[4], leader=v[5]) for k, v in EP.EARTH.items()}
    def _verdict(k):
        e, a = e_shape.get(k), product_shape[k]
        if not e:
            return "resource (production data)"
        r1, r3 = a["top1"] / e["top1"], a["top3"] / e["top3"]
        if 0.75 <= r1 <= 1.33 and 0.8 <= r3 <= 1.25:
            return "Earth-like"
        # for the leader's size: its share of the product over its share of
        # world trade, Earth against Andah
        es = EP.EARTH_TRADE_SHARE.get(e["leader"])
        a_s = dom_of.get(a["leader"], 0.0) / dom_world
        if es and a_s > 0:
            ratio = (a["top1"] / a_s) / (e["top1"] / es)
            if 0.7 <= ratio <= 1.45 and 0.7 <= a["top10"] / e["top10"] <= 1.3:
                return "Earth-like for the leader's size"
        return "flatter than Earth" if r1 < 0.75 or r3 < 0.8 else "sharper than Earth"
    verd = {k: _verdict(k) for k in product_shape}
    vc = {}
    for v in verd.values():
        vc[v] = vc.get(v, 0) + 1
    print("  product shapes vs Earth 2015:", vc)
    worst = sorted((k for k in product_shape if k in e_shape),
                   key=lambda k: -abs(math.log(max(product_shape[k]["top1"], 1e-4) / e_shape[k]["top1"])))[:8]
    for k in worst:
        a, e = product_shape[k], e_shape[k]
        print(f"     {k:<20} top1 {a['top1']:.0%} ({a['leader']}) vs Earth {e['top1']:.0%} ({e['leader']}); "
              f"top3 {a['top3']:.0%}/{e['top3']:.0%}; n {a['n']}/{e['n']}; share {a['share']:.2%}/{e['share']:.2%}")
    # the benchmark, as a CSV beside the data and a sheet in the workbook
    import csv
    bp = os.path.join(ad.HERE, "data", "product_benchmark.csv")
    hdr = ["product", "category", "Earth 2015 US$ bn", "Earth % of world trade", "Andah % of world trade",
           "Earth top-1", "Earth leader", "Andah top-1", "Andah leader", "Earth top-3", "Andah top-3",
           "Earth top-10", "Andah top-10", "Earth exporters >=1%", "Andah exporters >=1%", "Andah makers", "verdict"]
    brows = []
    for par, k in tsub.KEYS:
        a, e = product_shape[k], e_shape.get(k)
        brows.append([tsub.LABEL[k], tb.CATLABEL.get(par, par) if hasattr(tb, "CATLABEL") else par,
                      EP.EARTH[k][0] if e else "", e["share"] if e else "", a["share"],
                      e["top1"] if e else "", e["leader"] if e else "", a["top1"], a["leader"],
                      e["top3"] if e else "", a["top3"], e["top10"] if e else "", a["top10"],
                      e["n"] if e else "", a["n"], a["makers"], verd[k]])
    with open(bp, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(hdr)
        w.writerows(brows)
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill
        xp = os.path.join(ad.HERE, "data", "Andah_Trade_Statistics.xlsx")
        wb = openpyxl.load_workbook(xp)
        if "Earth products" in wb.sheetnames:
            del wb["Earth products"]
        ws = wb.create_sheet("Earth products")
        ws.append(["Every product against Earth's 2015 exports (OEC / UN Comtrade, WTO services). "
                   "Resource products are production data and are not fitted."])
        ws.cell(row=1, column=1).font = Font(bold=True)
        ws.append(hdr)
        for c in range(1, len(hdr) + 1):
            ws.cell(row=2, column=c).font = Font(bold=True)
        ok = PatternFill("solid", fgColor="E2F0D9")
        bad = PatternFill("solid", fgColor="FCE4D6")
        for r in brows:
            ws.append(r)
            v = r[-1]
            ws.cell(row=ws.max_row, column=len(hdr)).fill = ok if v.startswith("Earth-like") else (bad if "Earth" in v else PatternFill())
        for col, wdt in zip("ABCDEFGHIJKLMNOPQ", [26, 26, 12, 12, 12, 10, 16, 10, 16, 10, 10, 10, 10, 10, 10, 10, 22]):
            ws.column_dimensions[col].width = wdt
        ws.freeze_panes = "A3"
        wb.save(xp)
        print(f"  wrote Earth products sheet -> {xp}")
    except Exception as ex:
        print("  could not add Earth products sheet:", ex)

    # ECONOMIC COMPLEXITY, the OEC's headline number, from the 172 x 175
    # product matrix. Revealed comparative advantage marks which products a
    # country makes more of than the world does; diversity is how many, ubiquity
    # is how many countries make each. Complexity is the second eigenvector of
    # the country-country matrix those define: high for economies that make many
    # things few others can, low for ones that make few things everyone can. It
    # is about WHAT a country sells rather than how much, which the export rank
    # already says.
    plist = [k for _, k in tsub.KEYS]
    # As the OEC does, micro-economies are left out of the complexity
    # calculation: a country with three products, all of them rare, comes out
    # "more complex" than any industrial economy. Below 1.2 million people or
    # a hundredth of a percent of world exports a country gets no ranking.
    dom_world_all = sum(dom_of.values()) or 1.0
    # ...and so are entrepots: a hub's product table is other people's
    # products passing through, so Pha Hii came out the second most complex
    # economy in the world
    cl = [r["name"] for r in rows if subs.get(r["name"])
          and r.get("population", 0) >= 1.2e6 and dom_of[r["name"]] >= 1e-4 * dom_world_all
          and r["reexports"] < 0.4 * max(r["total_x"], 1.0)]
    X = {c: {p: subs[c].get(p, 0.0) * by_name[c]["domestic_x"] for p in plist} for c in cl}
    tot = sum(v for c in cl for v in X[c].values()) or 1.0
    ptot = {p: sum(X[c][p] for c in cl) for p in plist}
    ctot = {c: sum(X[c].values()) or 1.0 for c in cl}
    Mcp = {c: {p: 1 if (X[c][p] / ctot[c]) / ((ptot[p] / tot) or 1e-12) >= 1.0 else 0
               for p in plist} for c in cl}
    kc = {c: sum(Mcp[c].values()) for c in cl}
    kp = {p: sum(Mcp[c][p] for c in cl) for p in plist}
    # country-country matrix, then power iteration with the trivial vector removed
    Mt = {}
    for c in cl:
        Mt[c] = {}
        for c2 in cl:
            acc = 0.0
            for p in plist:
                if Mcp[c][p] and Mcp[c2][p] and kp[p]:
                    acc += 1.0 / kp[p]
            Mt[c][c2] = acc / (kc[c] or 1)
    vec = {c: (i % 7) - 3.0 for i, c in enumerate(cl)}   # any non-constant start
    for _ in range(300):
        mean = sum(vec.values()) / len(cl)
        for c in cl:
            vec[c] -= mean                              # deflate the all-ones eigenvector
        new = {c: sum(Mt[c][c2] * vec[c2] for c2 in cl) for c in cl}
        norm = math.sqrt(sum(v * v for v in new.values())) or 1.0
        vec = {c: v / norm for c, v in new.items()}
    mean = sum(vec.values()) / len(cl)
    sd = math.sqrt(sum((v - mean) ** 2 for v in vec.values()) / len(cl)) or 1.0
    eci = {c: (v - mean) / sd for c, v in vec.items()}
    # sign convention: complexity should rise with income
    rich = sorted(cl, key=lambda c: -by_name[c]["gdp_pc"])[:20]
    if sum(eci[c] for c in rich) < 0:
        eci = {c: -v for c, v in eci.items()}
    # product complexity: the first reflection of ECI onto products
    pci = {}
    for p in plist:
        makers = [c for c in cl if Mcp[c][p]]
        pci[p] = sum(eci[c] for c in makers) / len(makers) if makers else 0.0
    pm = sum(pci.values()) / len(plist)
    psd = math.sqrt(sum((v - pm) ** 2 for v in pci.values()) / len(plist)) or 1.0
    pci = {p: round((v - pm) / psd, 3) for p, v in pci.items()}
    print(f"  complexity: {len(cl)} countries; top {sorted(cl, key=lambda c: -eci[c])[:3]}")

    # the five list pages, computed once here so the atlas just renders them
    cats = {k: [] for k in tb.KEYS}
    for r in rows:
        dom = r["dom_goods_x"] + r["svc_x"]
        for k, share in (r.get("basket") or {}).items():
            if share > 0:
                cats[k].append([r["name"], round(dom * share)])
    for k in cats:
        cats[k].sort(key=lambda x: -x[1])
        cats[k] = cats[k][:25]

    hightech = []
    for r in rows:
        ht_share, ht_of_manuf = tb.high_tech(r.get("basket") or {}, r["gdp_pc"])
        dom = r["dom_goods_x"] + r["svc_x"]
        hightech.append([r["name"], round(dom * ht_share), round(ht_of_manuf, 4)])
    hightech.sort(key=lambda x: -x[1])

    leading = []
    for r in sorted(rows, key=lambda x: x["name"]):
        o = sorted(out_flows.get(r["name"], []), key=lambda x: -x[1])
        i = sorted(in_flows.get(r["name"], []), key=lambda x: -x[1])
        ot = sum(v for _, v in o) or 1.0
        it = sum(v for _, v in i) or 1.0
        leading.append([r["name"],
                        o[0][0] if o else "", round(o[0][1] / ot, 4) if o else 0,
                        i[0][0] if i else "", round(i[0][1] / it, 4) if i else 0])

    countries = {}
    for r in rows:
        countries[r["name"]] = dict(
            name=r["name"], continent=r["continent"], subregion=r["subregion"],
            label=r["label"], gdp=round(r["gdp"]), gdp_pc=round(r["gdp_pc"]),
            population=round(r["population"]),
            x=round(r["total_x"]), m=round(r["total_m"]), bal=round(r["balance"]),
            goods_x=round(r["goods_x"]), svc_x=round(r["svc_x"]),
            reexports=round(r["reexports"]), dva=round(r["dva_share"], 4),
            trade_gdp=round(r["trade_gdp"], 4), rank=r["total_x_rank"],
            m_rank=r["total_m_rank"], share=round(r["total_x"] / world_x, 6),
            lead=r["leading_export"], top_share=round(r["top_export_share"], 3),
            landlocked=bool(r["landlocked"]), island=bool(r["is_island"]),
            neighbours=len(data["geo"][r["name"]]["borders"]),
            coast=round(data["geo"][r["name"]]["coast_km"]),
            lon=round(data["geo"][r["name"]]["lon"], 2),
            lat=round(data["geo"][r["name"]]["lat"], 2),
            hub=r["name"] in hubs,
            partners=distribution(out_flows.get(r["name"], [])),
            buyers=distribution(in_flows.get(r["name"], [])),
            cat_buyers=cat_out.get(r["name"], {}),
            cat_sellers=cat_in.get(r["name"], {}),
            cat_m=cat_in_val.get(r["name"], {}),
            history=history.get(r["name"], {}),
            ports=ports.get(r["name"], []),
            sub=subs.get(r["name"], {}),
            eci=round(eci.get(r["name"], 0.0), 3),
            diversity=kc.get(r["name"], 0),
            high_tech=round(tb.high_tech(r.get("basket") or {}, r["gdp_pc"])[0], 4),
            basket={k: round(v, 4) for k, v in (r.get("basket") or {}).items()},
            basket_edited=bool(r.get("basket_edited")),
            lead_cat=r.get("leading_category", ""),
            champion=r.get("champion", ""),
            reach=round(r.get("reach", 1.0), 3),
            svc_share=round(r["svc_x"] / r["total_x"], 4) if r["total_x"] else 0.0,
        )

    _merged = {}
    for (a, b), v in flows.items():
        key = (a, b) if a < b else (b, a)
        _merged[key] = _merged.get(key, 0.0) + v

    transit = [dict(hub=h, kind=k, partner=p, share=s, note=n) for h, k, p, s, n in M.TRANSIT]

    payload = dict(
        year=M.YEAR,
        world=dict(
            gdp=round(meta["world_gdp"]), exports=round(world_x),
            openness=round(world_x / meta["world_gdp"], 4),
            countries=len(rows),
            landlocked=sum(1 for r in rows if r["landlocked"]),
            islands=sum(1 for r in rows if r["is_island"]),
            auc=round(meta["gravity_auc"], 3),
        ),
        countries=countries,
        shapes=shapes,
        transit=transit,
        categories=[[k, l, t] for k, l, t in tb.CATEGORIES],
        # The heaviest bilateral flows, for the map's flow layer. Directed pairs
        # are merged: a line on a map shows a relationship, not a direction.
        top_flows=(lambda: [
            [a, b, round(v)] for (a, b), v in sorted(
                ((k, v) for k, v in _merged.items()), key=lambda kv: -kv[1])[:220]
        ])(),
        lists=dict(by_category=cats, high_tech=hightech, leading_partners=leading),
        unions=unions,
        lanes=(json.load(io.open(os.path.join(ad.HERE, "data", "sea_lanes.json"), encoding="utf-8"))
               if os.path.exists(os.path.join(ad.HERE, "data", "sea_lanes.json")) else None),
        sea_routing=bool(meta.get("sea_routing")),
        products=[[k, tsub.LABEL[k], parent, pci.get(k, 0.0), e_shape.get(k), product_shape[k], verd[k],
                   [w[0], w[1]]]
                  for parent, k in tsub.KEYS for w in [next(ww for kk, _, ww in tsub.SUBS[parent] if kk == k)]],
        income_span=[tsub.LOW_INCOME, tsub.HIGH_INCOME],
        refinery=(lambda s: [[n, round(v, 4)] for n, v in sorted(s.items(), key=lambda kv: -kv[1])[:12]])(
            data.get("refinery_shares") or {}),
        flags=json.load(io.open(os.path.join(ad.HERE, "data", "flags_embedded.json"),
                                encoding="utf-8"))
        if os.path.exists(os.path.join(ad.HERE, "data", "flags_embedded.json")) else {},
        history_world=hist_world,
        continents={r["name"]: r["continent"] for r in rows},
        world_mix={k: round(v, 4) for k, v in (meta.get("world_mix") or {}).items()},
        lahn_ratio=meta.get("lahn_ratio"),
        edited=dict(baskets=meta.get("baskets_edited", 0), reach=meta.get("reach_edited", 0)),
        metrics=[dict(name=l, andah=round(a, 4), earth=round(e, 4),
                      ok=verdict(a, e, t) == "realistic", note=n)
                 for l, a, e, t, n in metrics],
    )

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    size = os.path.getsize(OUT)
    print(f"wrote {OUT}")
    print(f"  {len(countries)} countries, {len(shapes)} with shapes")
    print(f"  polygon vertices {raw_pts:,} -> {kept_pts:,} ({kept_pts/raw_pts:.1%})")
    print(f"  {size/1e6:.2f} MB")


if __name__ == "__main__":
    main()
