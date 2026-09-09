#!/usr/bin/env python3
"""
sea_lanes.py - where the ships actually go.

Takes the reconciled flow matrix and routes every coastal pair's trade along
its shortest sea path on the same grid sea_distance.py used, accumulating the
value that passes through each cell. Two things come out:

  LANES   the actual path, as a polyline, for the heaviest flows - round the
          cape, through the canal - so the map can draw a shipping route rather
          than a great-circle arc.
  TRAFFIC value per sea cell. Summed over all pairs this is a heat map of the
          world's sea lanes, and the cells with the most traffic are the
          chokepoints: the straits and the canal.

Landlocked countries' trade rides the gateway neighbour's coast, so their
flows appear on the water from that neighbour onward and on no land.

Writes data/sea_lanes.json. Re-run after the model changes.
"""

import collections
import heapq
import io
import json
import math
import os
import sys
import time

import andah_data as ad
import build_trade_model as M
import sea_distance as SD

OUT = os.path.join(ad.HERE, "data", "sea_lanes.json")
LANES = 260            # heaviest flows drawn as routes
TRAFFIC_CELLS = 9000   # busiest cells kept for the heat layer


def dijkstra_with_prev(sources, ocean):
    dist = {s: 0.0 for s in sources}
    prev = {}
    q = [(0.0, s) for s in sources]
    heapq.heapify(q)
    while q:
        d, (x, y) = heapq.heappop(q)
        if d > dist.get((x, y), 1e18):
            continue
        for dx, dy in SD.DIRS8:
            nx, ny = (x + dx) % SD.W, y + dy
            if 0 <= ny < SD.H and (nx, ny) in ocean:
                nd = d + SD.step_km(y, dx, dy)
                if nd < dist.get((nx, ny), 1e18):
                    dist[(nx, ny)] = nd
                    prev[(nx, ny)] = (x, y)
                    heapq.heappush(q, (nd, (nx, ny)))
    return dist, prev


def walk(prev, end):
    path = [end]
    while path[-1] in prev:
        path.append(prev[path[-1]])
    path.reverse()
    return path


def lonlat(x, y):
    return round((x + 0.5) / SD.W * 360.0 - 180.0, 2), round(SD.cell_lat(y), 2)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    data = ad.load_all()
    rows, flows, meta = M.run(data)
    geo = data["geo"]
    canon = {k.lower(): k for k in data["countries"]}
    with open(os.path.join(ad.GAMES, "andah-countries.geojson"), encoding="utf-8") as fh:
        gj = json.load(fh)
    px, idx, names = SD.rasterise(gj, canon)
    ocean, _, _ = SD.ocean_mask(px)
    for name, lat, lon in SD.CANALS:
        SD.dig_canal(px, ocean, lon, lat)
    coast = SD.coast_cells(px, idx, ocean)
    with open(SD.OUT, encoding="utf-8") as fh:
        via = json.load(fh).get("via_gateway") or {}
    print(f"grid ready ({time.time()-t0:.0f}s)")

    # who sails from which coast: a landlocked country's flow leaves from its
    # gateway, recorded by sea_distance.py
    def coast_of(a, b):
        r = via.get(f"{a}|{b}")
        return (r[0], r[1]) if r else (a, b)

    by_src = collections.defaultdict(list)
    for (a, b), v in flows.items():
        pa, pb = coast_of(a, b)
        if pa in coast and pb in coast and pa != pb:
            by_src[pa].append((pb, v, a, b))

    traffic = collections.Counter()
    heavy = sorted(flows.items(), key=lambda kv: -kv[1])[:LANES]
    want = {(a, b) for (a, b), _ in heavy}
    lanes = {}
    done = 0
    for pa, targets in by_src.items():
        dist, prev = dijkstra_with_prev(coast[pa], ocean)
        for pb, v, a, b in targets:
            end = min(coast[pb], key=lambda c: dist.get(c, 1e18))
            if dist.get(end, 1e18) >= 1e18:
                continue
            path = walk(prev, end)
            for c in path:
                traffic[c] += v
            if (a, b) in want:
                # thin the polyline: keep every 3rd cell plus the ends
                pts = [lonlat(*c) for i, c in enumerate(path) if i % 3 == 0 or i == len(path) - 1]
                lanes[f"{a}|{b}"] = dict(v=round(v), pts=pts)
        done += 1
        if done % 20 == 0:
            print(f"   {done}/{len(by_src)} coasts routed ({time.time()-t0:.0f}s)")

    # chokepoints: the busiest cells anywhere, and the canal's own traffic
    busiest = traffic.most_common(TRAFFIC_CELLS)
    top = traffic.most_common(1)[0][1] if traffic else 1.0
    cells = [[*lonlat(x, y), round(v / top, 4)] for (x, y), v in busiest]
    canal_traffic = {}
    for name, lat, lon in SD.CANALS:
        cx, cy = SD.cell(lon, lat)
        near = [traffic[(x % SD.W, y)] for x in range(cx - 4, cx + 5) for y in range(cy - 4, cy + 5)]
        canal_traffic[name] = round(max(near)) if near else 0
    print(f"routed {sum(len(t) for t in by_src.values()):,} flows; {len(lanes)} lanes drawn; "
          f"peak cell carries {top/1e12:.2f}T; canal {canal_traffic}  ({time.time()-t0:.0f}s)")
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(dict(cells=cells, lanes=lanes, peak=round(top), canals=canal_traffic), fh)
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
