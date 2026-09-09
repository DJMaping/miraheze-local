#!/usr/bin/env python3
"""
sea_distance.py - how far apart two countries are for a ship, not a crow.

WHY. The gravity layer used great-circle distance, which puts Dahe and Areoix
Lie 7,465 km apart. They sit on opposite sides of a landmass; a tanker sails
19,411 km. Two countries can share a border of mountains or desert and trade
almost nothing, while two across a strait trade constantly, and the model could
not see either. DJ has no terrain data to give and should not have to: if the
sea route goes round, the land between was never much use for trade.

HOW. The country polygons are drawn onto a 0.25-degree grid, sea is everything
that is not land, and a shortest path is run over sea cells from every coastal
country to every other, with step costs in real kilometres (a longitude step
shrinks with latitude). The Tiesa Canal is cut through its isthmus at Alubri
City so ships take it rather than rounding the continent.

  - The ocean is ONE connected body on this grid. The two coastal countries
    that cannot be reached, Tomscilus and Welenu Fana, sit on lakes: their
    "coast" is a lakeshore, and they are landlocked for shipping. That is the
    right answer, not a blocked strait.
  - A landlocked country reaches the sea through a bordering coastal country:
    its distance to anywhere is the straight-line leg to that neighbour plus
    the neighbour's sea leg, minimised over its neighbours.
  - Each country also carries an inland leg, centroid to its own nearest coast,
    so a large country whose capital sits far from the sea is not treated as if
    its ports were at its geographic centre.

Writes data/sea_distances.json once; build_trade_model reads it. Re-run after
the geojson changes.
"""

import collections
import heapq
import io
import json
import math
import os
import sys
import time

from PIL import Image, ImageDraw

import andah_data as ad

OUT = os.path.join(ad.HERE, "data", "sea_distances.json")
W, H = 1440, 720                       # 0.25 degree
KM_PER_CELL = 40075.0 / W              # at the equator

# The Tiesa Canal. Emara's overseas territory at Alubri City, bordering Trian and
# Etretes, per Emara's own page. Dug as a one-cell channel between the two
# nearest stretches of open sea that are far apart BY SEA and close by land.
CANALS = [("Tiesa Canal", -27.2755, 81.432)]

# Sea cells touching a country's land; for lake shores this finds the lake, and
# the ocean test below throws it out.
DIRS4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIRS8 = DIRS4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))


def cell(lon, lat):
    return int((lon + 180.0) / 360.0 * W) % W, min(H - 1, max(0, int((90.0 - lat) / 180.0 * H)))


def cell_lat(y):
    return 90.0 - (y + 0.5) / H * 180.0


def step_km(y, dx, dy):
    """Kilometres for one grid step at row y."""
    kx = KM_PER_CELL * max(0.05, math.cos(math.radians(cell_lat(y))))
    ky = KM_PER_CELL
    return math.hypot(kx * abs(dx), ky * abs(dy))


def rasterise(geo_json, canon):
    img = Image.new("I", (W, H), 0)
    dr = ImageDraw.Draw(img)
    idx, names = {}, []
    for f in geo_json["features"]:
        nm = canon.get(f["properties"]["name"].lower())
        if not nm:
            continue
        if nm not in idx:
            idx[nm] = len(names) + 1
            names.append(nm)
        for poly in f["geometry"]["coordinates"]:
            pts = [((x + 180.0) / 360.0 * W, (90.0 - y) / 180.0 * H) for x, y in poly[0]]
            dr.polygon(pts, fill=idx[nm])
    return img.load(), idx, names


def ocean_mask(px):
    """Cells of the single largest connected water body."""
    comp = {}
    sizes = collections.Counter()
    cid = 0
    for y in range(H):
        for x in range(W):
            if px[x, y] or (x, y) in comp:
                continue
            cid += 1
            stack = [(x, y)]
            comp[(x, y)] = cid
            while stack:
                cx, cy = stack.pop()
                sizes[cid] += 1
                for dx, dy in DIRS4:
                    nx, ny = (cx + dx) % W, cy + dy
                    if 0 <= ny < H and not px[nx, ny] and (nx, ny) not in comp:
                        comp[(nx, ny)] = cid
                        stack.append((nx, ny))
    big = sizes.most_common(1)[0][0]
    return {c for c, k in comp.items() if k == big}, cid, sizes[big]


def dig_canal(px, ocean, lon, lat, radius=8):
    """
    Open a one-cell channel at a canal. Among sea cells within `radius` of the
    site, take the pair that is farthest apart by sea for how close it is by
    land - that pair straddles the isthmus - and turn the land between them
    into sea. Returns the cells dug.
    """
    cx, cy = cell(lon, lat)
    near = [(x % W, y) for x in range(cx - radius, cx + radius + 1)
            for y in range(cy - radius, cy + radius + 1)
            if 0 <= y < H and ((x % W), y) in ocean]
    if len(near) < 2:
        return []
    # sea distance from one arbitrary near cell to the others, bounded search
    src = near[0]
    dist = {src: 0.0}
    q = [(0.0, src)]
    limit = radius * 40
    while q:
        d, (x, y) = heapq.heappop(q)
        if d > dist.get((x, y), 1e18) or d > limit:
            continue
        for dx, dy in DIRS8:
            nx, ny = (x + dx) % W, y + dy
            if 0 <= ny < H and (nx, ny) in ocean:
                nd = d + math.hypot(dx, dy)
                if nd < dist.get((nx, ny), 1e18):
                    dist[(nx, ny)] = nd
                    heapq.heappush(q, (nd, (nx, ny)))
    # the far side is whatever near cell the bounded search could not reach,
    # or failing that the one with the worst sea/land ratio
    far = [c for c in near if c not in dist]
    if far:
        a = min(near, key=lambda c: math.hypot(c[0] - cx, c[1] - cy))
        b = min(far, key=lambda c: math.hypot(c[0] - cx, c[1] - cy))
    else:
        best, a, b = 0.0, None, None
        for c1 in near:
            for c2 in near:
                land = math.hypot(c1[0] - c2[0], c1[1] - c2[1]) or 1.0
                r = dist.get(c2, 1e9) / land
                if r > best and land >= 2:
                    best, a, b = r, c1, c2
        if a is None:
            return []
    dug = []
    x0, y0 = a
    x1, y1 = b
    n = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(n + 1):
        x = round(x0 + (x1 - x0) * i / n) % W
        y = round(y0 + (y1 - y0) * i / n)
        if px[x, y]:
            px[x, y] = 0
            dug.append((x, y))
        ocean.add((x, y))
    return dug


def coast_cells(px, idx, ocean):
    """{country: set of ocean cells adjacent to its land}."""
    coast = collections.defaultdict(set)
    inv = {v: k for k, v in idx.items()}
    for (x, y) in ocean:
        for dx, dy in DIRS4:
            nx, ny = (x + dx) % W, y + dy
            if 0 <= ny < H and px[nx, ny]:
                coast[inv[px[nx, ny]]].add((x, y))
    return coast


def sea_dijkstra(sources, ocean):
    """Kilometres from the nearest of `sources` to every reachable ocean cell."""
    dist = {s: 0.0 for s in sources}
    q = [(0.0, s) for s in sources]
    heapq.heapify(q)
    while q:
        d, (x, y) = heapq.heappop(q)
        if d > dist.get((x, y), 1e18):
            continue
        for dx, dy in DIRS8:
            nx, ny = (x + dx) % W, y + dy
            if 0 <= ny < H and (nx, ny) in ocean:
                nd = d + step_km(y, dx, dy)
                if nd < dist.get((nx, ny), 1e18):
                    dist[(nx, ny)] = nd
                    heapq.heappush(q, (nd, (nx, ny)))
    return dist


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    data = ad.load_all()
    geo = data["geo"]
    canon = {k.lower(): k for k in data["countries"]}
    with open(os.path.join(ad.GAMES, "andah-countries.geojson"), encoding="utf-8") as fh:
        gj = json.load(fh)
    px, idx, names = rasterise(gj, canon)
    ocean, ncomp, nocean = ocean_mask(px)
    print(f"grid {W}x{H}: ocean is {nocean:,} cells, {ncomp - 1} enclosed lakes  ({time.time()-t0:.1f}s)")

    canal_cells = {}
    for name, lat, lon in CANALS:
        dug = dig_canal(px, ocean, lon, lat)
        canal_cells[name] = dug
        print(f"{name}: dug {len(dug)} cells at {lat:.2f}, {lon:.2f}")

    coast = coast_cells(px, idx, ocean)
    coastal = [n for n in names if coast[n]]
    lakebound = [n for n in names if not geo[n]["landlocked"] and not coast[n]]
    print(f"coastal on the ocean: {len(coastal)}; lake-shore only: {lakebound}")

    # inland leg: centroid to nearest own coast cell
    inland = {}
    for n in coastal:
        g = geo[n]
        best = 1e18
        for (x, y) in coast[n]:
            lon = (x + 0.5) / W * 360.0 - 180.0
            lat = cell_lat(y)
            best = min(best, ad.haversine_km(g["lon"], g["lat"], lon, lat))
        inland[n] = best

    # sea legs, coast to coast
    sea = {}
    for i, n in enumerate(coastal):
        d = sea_dijkstra(coast[n], ocean)
        row = {}
        for m in coastal:
            if m == n:
                continue
            best = min((d.get(c, 1e18) for c in coast[m]), default=1e18)
            if best < 1e18:
                row[m] = best
        sea[n] = row
        if (i + 1) % 20 == 0:
            print(f"   {i + 1}/{len(coastal)} coasts routed  ({time.time()-t0:.0f}s)")

    # full matrix with inland legs and landlocked routing
    def straight(a, b):
        return ad.haversine_km(geo[a]["lon"], geo[a]["lat"], geo[b]["lon"], geo[b]["lat"])

    def gateways(n):
        """Coastal countries a landlocked one can reach the sea through."""
        out = []
        for nb in geo[n]["borders"]:
            if nb in sea:
                out.append(nb)
        return out

    matrix = {}
    via = {}
    for a in names:
        matrix[a] = {}
        ga = [a] if a in sea else gateways(a)
        for b in names:
            if a == b:
                continue
            gb = [b] if b in sea else gateways(b)
            best, route = 1e18, None
            for pa in ga:
                for pb in gb:
                    if pa == pb:
                        leg = 0.0
                    else:
                        leg = sea.get(pa, {}).get(pb, 1e18)
                    if leg >= 1e18:
                        continue
                    total = leg + inland.get(pa, 0.0) + inland.get(pb, 0.0)
                    if pa != a:
                        total += straight(a, pa)
                    if pb != b:
                        total += straight(b, pb)
                    if total < best:
                        best, route = total, (pa, pb)
            if best < 1e18:
                matrix[a][b] = round(best)
                if route != (a, b):
                    via[f"{a}|{b}"] = route
    missing = sum(1 for a in names for b in names if a != b and b not in matrix[a])
    pairs = sum(len(v) for v in matrix.values())
    print(f"routed {pairs:,} pairs; {missing} with no sea route at all (straight-line will be used)")

    out = dict(grid=[W, H], ocean_cells=nocean, canals={k: len(v) for k, v in canal_cells.items()},
               coastal=coastal, lakebound=lakebound, inland_km={k: round(v) for k, v in inland.items()},
               km=matrix, via_gateway=via)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print(f"wrote {OUT}  ({os.path.getsize(OUT)/1e6:.2f} MB, {time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
