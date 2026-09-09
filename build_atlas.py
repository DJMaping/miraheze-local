#!/usr/bin/env python3
"""
build_atlas.py - fill atlas_template.html with andah_trade_atlas.json.

Run after export_trade_json.py. Writes andah_trade_atlas.html beside the
template and .preview/atlas.html for the local preview server. The published
artifact is the same file; publish it from a Claude session with the artifact's
URL so the link stays the same.

Order of the whole pipeline:
  python sea_distance.py      (only after the geojson changes; 9 minutes)
  python build_trade_model.py (model + data/Andah_Trade_Statistics.xlsx)
  python sea_lanes.py         (routes every flow; 10 minutes; feeds the canal toll)
  python build_trade_model.py (again, so the toll income is the routed one)
  python export_trade_json.py (products, complexity, Earth products sheet, JSON)
  python build_atlas.py
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(HERE, "atlas_template.html"), encoding="utf-8").read()
data = open(os.path.join(HERE, "andah_trade_atlas.json"), encoding="utf-8").read()
assert "/*__DATA__*/{}" in tpl, "template has no data slot"
html = tpl.replace("/*__DATA__*/{}", data, 1)
os.makedirs(os.path.join(HERE, ".preview"), exist_ok=True)
for p in (os.path.join(HERE, "andah_trade_atlas.html"), os.path.join(HERE, ".preview", "atlas.html")):
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(html)
print(f"atlas built: {len(html) // 1000} KB")
