#!/usr/bin/env python3
"""
trade_workbook.py - writes data/Andah_Trade_Statistics.xlsx from the model.

Kept apart from build_trade_model.py so the model file stays economics and this
file stays presentation. Nothing here computes a trade figure.

Conventions
  negatives print red everywhere, so a deficit is visible at a glance
  continent, subregion and label are colour-coordinated: each subregion is a
  darker shade of its own continent's hue, so the columns read as one system
  green fills mark the few inputs that are genuinely editable
"""

import collections
import math

import openpyxl
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import build_trade_model as M
import trade_baskets as TB

HDR = PatternFill("solid", fgColor="1F3864")
GREEN = PatternFill("solid", fgColor="E2EFDA")
PURPLE = PatternFill("solid", fgColor="E4DFEC")
OKF = PatternFill("solid", fgColor="C6EFCE")
BADF = PatternFill("solid", fgColor="FFC7CE")

MONEY = '#,##0;[Red]-#,##0'
PCT = '0.0%;[Red]-0.0%'
NUM = '#,##0.00;[Red]-#,##0.00'

CONTINENT_RGB = {
    "Acrola": (0xF9, 0xA8, 0x25), "Atirha": (0x43, 0xA0, 0x47),
    "Ayuma": (0x1E, 0x88, 0xE5), "Mahea": (0xD8, 0x1B, 0x60),
    "Massir": (0x8E, 0x24, 0xAA), "New Ayre": (0x00, 0x89, 0x7B),
    "Quia": (0xF4, 0x51, 0x1E),
}
# Every label describe() can return. The basket rewrite introduced new ones
# ("oil & gas exporter", "metals exporter", "agricultural exporter" and the
# rest) and they were missing here, so 93 of 172 rows fell through to the
# default grey and the column stopped carrying information.
LABEL_FILL = {
    # hubs
    "transit port economy": "B3E5FC", "re-export gateway": "B3E5FC",
    # resource
    "oil & gas exporter": "DCEDC8", "oil exporter": "DCEDC8",
    "fuel exporter": "DCEDC8", "metals exporter": "D7CCC8",
    "precious metals exporter": "F0E4B8", "agricultural exporter": "DCEDC8",
    "textile exporter": "F8D5DC",
    # services
    "services exporter": "E1BEE7", "tourism economy": "FFE7B8",
    # markets and industry
    "large consumer market": "FFF9C4", "highly open economy": "FFE0B2",
    "industrial surplus economy": "FFCCBC", "low-income trader": "CFD8DC",
    "diversified economy": "ECEFF1",
}


def _tint(rgb, f):
    return "".join(f"{int(v + (255 - v) * f):02X}" for v in rgb)


def palette(rows):
    cont, sub = {}, {}
    subs = collections.defaultdict(set)
    for r in rows:
        subs[r["continent"]].add(r["subregion"])
    for c, rgb in CONTINENT_RGB.items():
        cont[c] = PatternFill("solid", fgColor=_tint(rgb, 0.55))
        ordered = sorted(subs.get(c, []))
        n = max(1, len(ordered))
        for i, s in enumerate(ordered):
            # keyed on (continent, subregion): one subregion name appears under
            # two continents in the Geoscheme sheet, and a flat key would give
            # a country its neighbour's colour
            sub[(c, s)] = PatternFill("solid", fgColor=_tint(rgb, 0.80 - 0.35 * i / n))
    return cont, sub


def _head(ws, labels, widths=None):
    ws.append(labels)
    for i in range(1, len(labels) + 1):
        c = ws.cell(row=1, column=i)
        c.fill = HDR
        c.font = Font(bold=True, color="FFFFFF", size=10)
        c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.freeze_panes = "A2"
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def write(path, rows, flows, meta, data, year_runs, comparison):
    wb = openpyxl.Workbook()
    T = 1e12
    cont_fill, sub_fill = palette(rows)
    metrics, verdict = comparison
    wx = sum(r["total_x"] for r in rows)

    # ---------------- README ----------------
    ws = wb.active
    ws.title = "README"
    top = sorted(rows, key=lambda r: -r["total_x"])[:5]
    lines = [
        ("Andah trade statistics, 1765", True),
        ("", False),
        ("Values are in NEW lahn, the revalued unit: 8x the GDP figures in the Geoscheme", False),
        ("sheet of Andah_Janus Statistics.xlsx, and the same scale as countries.json in the", False),
        ("games folder and as the converted wiki pages. Built by build_trade_model.py.", False),
        ("", False),
        ("NOTHING HERE IS ASSIGNED", True),
        ("  An earlier version sorted each country into one of eight archetypes and read", False),
        ("  its trade off that bucket. This one does not. Every figure comes from a", False),
        ("  continuous relationship applied to data that already existed, and the label in", False),
        ("  the Trade Model sheet is computed LAST, from the finished numbers, purely so", False),
        ("  the table reads well. Change a country's GDP per capita and its character", False),
        ("  changes with it. No judgement call sits between the data and the result.", False),
        ("", False),
        ("WHERE THE NUMBERS COME FROM", True),
        ("  Geography   172 country polygons in lon/lat, giving exact centroids, areas,", False),
        ("              great-circle distances and shared border lengths. Landlocked is", False),
        ("              MEASURED, not asserted: a country whose whole outline is shared", False),
        ("              with neighbours has no coast. 30 landlocked, 24 islands.", False),
        ("              Cross-check: these polygons total 126.6m km2 against the Janus", False),
        ("              sheet's 125.7m, a 0.7% agreement between two independent files.", False),
        ("  Openness    a regression, not a bucket. Population enters NEGATIVELY and", False),
        ("              dominates: a large internal market is the strongest brake on", False),
        ("              trade there is. Income, area, landlocked status, remoteness and", False),
        ("              resource concentration do the rest.", False),
        ("  Gravity     trade between each pair falls with distance and rises with the", False),
        ("              product of their economies, lifted by a shared border. Checked", False),
        ("              against the flight network across all 14,706 country pairs: can", False),
        ("              the model pick out the 1,114 that are actually linked?", False),
        (f"              AUC {meta.get('gravity_auc', 0):.3f}, where 0.5 is chance.", False),
        ("              This is a CONSISTENCY check, not independent validation: that", False),
        ("              flight network's demand is itself a gravity model over the same", False),
        ("              GDP figures and the same map. It proves the wiring is right, and", False),
        ("              it did catch a real error, but it cannot prove gravity is the", False),
        ("              right structure for Andah's trade. See the Validation sheet.", False),
        ("  Transit     DJ's canon, untouched by any regression. Hinterland cargo becomes", False),
        ("              re-exports; stopover and canal traffic become services.", False),
        ("", False),
        ("TWO THINGS WORTH KNOWING", True),
        ("  The distance exponent is NOT fitted to the flight network. Sweeping it barely", False),
        ("  moves the correlation, so aviation cannot identify it, and passengers cross", False),
        ("  oceans far more readily than bulk cargo does. It comes from the merchandise", False),
        ("  trade literature instead.", False),
        ("", False),
        ("  The landlocked penalty is measured LIKE FOR LIKE. A raw comparison says", False),
        ("  landlocked countries trade 53% less, but they are also six times poorer per", False),
        ("  head, and that gap is the income, not the geography. Against coastal peers of", False),
        ("  similar size and income the penalty is 29%, which is what Earth shows.", False),
        ("", False),
        ("CALIBRATION", True),
        (f"  World GDP            {meta['world_gdp']/T:>9,.1f} trillion", False),
        (f"  World exports        {wx/T:>9,.1f} trillion   ({wx/meta['world_gdp']:.1%} of GDP)", False),
        (f"  Earth 2015 was       {'':>9}            (28.4% of GDP)", False),
        (f"  Metrics realistic    {sum(1 for m in metrics if verdict(m[1], m[2], m[3]) == 'realistic')}"
         f" of {len(metrics)}   see the Earth 2015 sheet", False),
        ("", False),
        ("LARGEST EXPORTERS", True),
    ]
    for i, r in enumerate(top, 1):
        lines.append((f"  {i}. {r['name']:<14}{r['total_x']/T:6.2f}T   {r['label']}", False))
    for text, bold in lines:
        ws.append([text])
        if bold:
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.column_dimensions["A"].width = 96

    # ---------------- Trade Model ----------------
    ws = wb.create_sheet("Trade Model")
    cols = [
        ("Country", "name"), ("Continent", "continent"), ("Subregion", "subregion"),
        ("Character (derived)", "label"),
        ("Exports total", "total_x"), ("Rank", "total_x_rank"),
        ("Imports total", "total_m"), ("Rank ", "total_m_rank"),
        ("Trade balance", "balance"),
        ("Goods exports", "goods_x"), ("Goods imports", "goods_m"),
        ("Services exports", "svc_x"), ("Services imports", "svc_m"),
        ("of which re-exports", "reexports"),
        ("Domestic value added", "dom_goods_x"), ("DVA share", "dva_share"),
        ("Trade as % of GDP", "trade_gdp"),
        ("Leading export (basket)", "leading_export"),
        ("Its share of exports", "leading_export_share_of_goods"),
        ("Basket hand-edited?", "basket_edited"),
        ("Global reach", "reach"),
        ("Leading commodity (raw)", "leading_commodity"),
        ("Top product share", "top_export_share"),
        ("Basket concentration (HHI)", "basket_hhi"),
        ("Effective export lines", "n_export_lines"),
        ("GDP nominal", "gdp"), ("GDP per capita", "gdp_pc"), ("Population", "population"),
        ("Area km2", "area_km2"), ("Landlocked", "landlocked"), ("Island", "is_island"),
        ("Coastline km", "coast_km"), ("Land neighbours", "n_borders"),
        ("Remoteness", "remoteness"),
        ("Openness (regression)", "openness"),
        ("Openness (realised exports/GDP)", "openness_realised"),
        ("Port factor", "port_factor"), ("Resource concentration", "resource_concentration"),
    ]
    # Formats and widths are keyed to the FIELD NAME, not to a hand-counted
    # column index. Three columns were added to this sheet at different times and
    # the hardcoded index lists were never updated, so the money and percent
    # formats had slid one place and the HHI column rendered as 0 for all 172
    # rows. Deriving them here means adding a column can never silently
    # mis-format another one again, and the widths list can never run short.
    MONEY_FIELDS = {
        "total_x", "total_m", "balance", "goods_x", "goods_m", "svc_x", "svc_m",
        "reexports", "dom_goods_x", "gdp", "gdp_pc", "population", "area_km2",
        "coast_km",
    }
    PCT_FIELDS = {
        "dva_share", "trade_gdp", "leading_export_share_of_goods",
        "top_export_share", "basket_hhi", "openness_realised",
    }
    NUM_FIELDS = {"remoteness", "openness", "port_factor", "resource_concentration", "reach"}
    RESULT_FIELDS = {
        "total_x", "total_m", "balance", "goods_x", "goods_m", "svc_x", "svc_m",
        "reexports", "dom_goods_x", "dva_share", "trade_gdp", "leading_export",
        "top_export_share", "basket_hhi", "n_export_lines",
    }
    WIDE = {"label": 24, "leading_export": 26, "leading_commodity": 20,
            "subregion": 15, "name": 17, "continent": 11,
            "leading_export_share_of_goods": 15, "openness_realised": 16,
            "resource_concentration": 13, "n_export_lines": 12}

    _head(ws, [c[0] for c in cols],
          [WIDE.get(k, 15) for _, k in cols])
    ordered = sorted(rows, key=lambda r: -r["total_x"])
    for r in ordered:
        ws.append([r.get(k) for _, k in cols])
    for i, r in enumerate(ordered):
        row = i + 2
        if r["continent"] in cont_fill:
            ws.cell(row=row, column=2).fill = cont_fill[r["continent"]]
        key = (r["continent"], r["subregion"])
        if key in sub_fill:
            ws.cell(row=row, column=3).fill = sub_fill[key]
        ws.cell(row=row, column=4).fill = PatternFill(
            "solid", fgColor=LABEL_FILL.get(r["label"], "ECEFF1"))
        for ci, (_label, field) in enumerate(cols, 1):
            cell = ws.cell(row=row, column=ci)
            if field in MONEY_FIELDS:
                cell.number_format = MONEY
            elif field in PCT_FIELDS:
                cell.number_format = PCT
            elif field in NUM_FIELDS:
                cell.number_format = NUM
            if field in RESULT_FIELDS:
                cell.fill = PURPLE
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{ws.max_row}"

    # ---------------- Bilateral partners ----------------
    ws = wb.create_sheet("Trade partners")
    _head(ws, ["Country", "Direction", "Rank", "Partner", "Flow", "Share of that country's total"],
          [18, 11, 7, 18, 16, 26])
    for r in ordered:
        for direction, key, tot in (("exports", "top_export_partners", r["goods_x"]),
                                    ("imports", "top_import_partners", r["goods_m"])):
            for rank, (partner, v) in enumerate(r.get(key, []), 1):
                ws.append([r["name"], direction, rank, partner, v, v / tot if tot else 0])
                ws.cell(row=ws.max_row, column=5).number_format = MONEY
                ws.cell(row=ws.max_row, column=6).number_format = PCT
    ws.auto_filter.ref = f"A1:F{ws.max_row}"

    # ---------------- Geography ----------------
    ws = wb.create_sheet("Geography")
    _head(ws, ["Country", "Continent", "Subregion", "Longitude", "Latitude", "Area km2",
               "Perimeter km", "Coastline km", "Coast share of outline", "Landlocked",
               "Island", "Land neighbours", "Total shared border km", "Neighbours (km)"],
          [17, 11, 15, 11, 11, 13, 13, 13, 20, 11, 8, 14, 20, 70])
    geo = data["geo"]
    for r in sorted(rows, key=lambda r: r["name"]):
        g = geo[r["name"]]
        nbs = ", ".join(f"{k} {v:,.0f}" for k, v in
                        sorted(g["borders"].items(), key=lambda kv: -kv[1]))
        ws.append([r["name"], r["continent"], r["subregion"], g["lon"], g["lat"],
                   g["area_km2"], g["perimeter_km"], g["coast_km"], g["coast_share"],
                   "yes" if g["landlocked"] else "no", "yes" if g["is_island"] else "no",
                   len(g["borders"]), g["shared_border_km"], nbs])
        rr = ws.max_row
        for col in (4, 5):
            ws.cell(row=rr, column=col).number_format = NUM
        for col in (6, 7, 8, 13):
            ws.cell(row=rr, column=col).number_format = MONEY
        ws.cell(row=rr, column=9).number_format = PCT
    ws.auto_filter.ref = f"A1:N{ws.max_row}"

    # ---------------- Benchmark years ----------------
    ws = wb.create_sheet("Benchmark years")
    _head(ws, ["Year", "World GDP", "World exports", "Exports / GDP",
               "Largest exporter", "Its exports", "2nd", "3rd", "Countries"],
          [8, 16, 16, 14, 18, 15, 16, 16, 11])
    for y in sorted(year_runs):
        yr = year_runs[y]
        if not yr:
            continue
        yrows, ymeta = yr
        ywx = sum(r["total_x"] for r in yrows)
        t3 = sorted(yrows, key=lambda r: -r["total_x"])[:3]
        ws.append([y, ymeta["world_gdp"], ywx, ywx / ymeta["world_gdp"],
                   t3[0]["name"], t3[0]["total_x"], t3[1]["name"], t3[2]["name"], len(yrows)])
        rr = ws.max_row
        for col in (2, 3, 6):
            ws.cell(row=rr, column=col).number_format = MONEY
        ws.cell(row=rr, column=4).number_format = PCT
    ws.append([])
    ws.append(["Population is DJ's own series; GDP per capita is walked back through his own"])
    ws.append(["annual growth rates. Only the world openness LEVEL is set externally, from"])
    ws.append(["Earth's actual globalisation path (1765 AFA is 2015 Earth), because that is a"])
    ws.append(["fact about shipping technology rather than about any one country."])

    # per-country series
    ws2 = wb.create_sheet("Country history")
    years = sorted(y for y in year_runs if year_runs[y])
    _head(ws2, ["Country"] + [f"{y} exports" for y in years]
          + [f"{y} trade/GDP" for y in years], [18] + [14] * (2 * len(years)))
    idx = {y: {r["name"]: r for r in year_runs[y][0]} for y in years}
    for r in ordered:
        n = r["name"]
        row = [n] + [idx[y].get(n, {}).get("total_x") for y in years] \
                  + [idx[y].get(n, {}).get("trade_gdp") for y in years]
        ws2.append(row)
        rr = ws2.max_row
        for i in range(len(years)):
            ws2.cell(row=rr, column=2 + i).number_format = MONEY
            ws2.cell(row=rr, column=2 + len(years) + i).number_format = PCT
    ws2.auto_filter.ref = f"A1:{get_column_letter(1 + 2 * len(years))}{ws2.max_row}"

    # ---------------- Categories ----------------
    ws = wb.create_sheet("Categories")
    _head(ws, ["Key", "Category", "Type", "World share of exports", "Drawn from"],
          [18, 34, 10, 20, 70])
    src = {
        "crude_oil_gas": "Oil and Natural Gas production sheets",
        "refined_fuels": "Coal, Uranium, Thorium production",
        "ores_metals": "23 metal and mineral production sheets",
        "precious": "Gold, Silver, Platinum, Palladium, Diamond production",
        "agri_food": "income profile (falls sharply with income and container throughput)",
        "forestry_paper": "Paper production plus income profile",
        "textiles": "income profile (peaks at lower-middle income)",
        "chemicals": "income profile", "machinery": "income profile plus container throughput",
        "electronics": "income profile plus container throughput",
        "vehicles": "Motor vehicle production plus income and throughput",
        "other_manuf": "income profile plus container throughput",
        "transport": "transit cargo (stopover, canal, hinterland) plus coast",
        "tourism": "islands, coastline, income", "finance_business": "income",
    }
    wm = meta.get("world_mix") or {}
    for k, label, typ in TB.CATEGORIES:
        ws.append([k, label, typ, wm.get(k, 0.0), src.get(k, "")])
        ws.cell(row=ws.max_row, column=4).number_format = PCT
    ws.append([])
    ws.append(["Chosen from the HS section structure and checked against real 2015 profiles:"])
    ws.append(["Saudi Arabia ~80% crude, Bangladesh ~85% textiles, Chile ~50% ores, Germany spread"])
    ws.append(["across machinery, vehicles and chemicals, the Maldives in tourism. Every real"])
    ws.append(["economy fits without a residual category."])

    # ---------------- Export baskets (editable) + model default ----------------
    def basket_sheet(title, field, editable):
        ws_ = wb.create_sheet(title)
        _head(ws_, ["Country", "Domestic exports"] + [TB.LABEL[k] for k in TB.KEYS] + ["Sum", "Hand-edited?"],
              [17, 15] + [14] * len(TB.KEYS) + [8, 12])
        for r in sorted(rows, key=lambda r: -r["total_x"]):
            b = r.get(field) or {}
            vals = [round(100.0 * b.get(k, 0.0), 1) for k in TB.KEYS]
            ws_.append([r["name"], r["dom_goods_x"] + r["svc_x"]] + vals
                       + [round(sum(vals), 1), "yes" if r.get("basket_edited") else ""])
            rr = ws_.max_row
            ws_.cell(row=rr, column=2).number_format = MONEY
            for ci in range(3, 3 + len(TB.KEYS)):
                if editable:
                    ws_.cell(row=rr, column=ci).fill = GREEN
            ws_.cell(row=rr, column=3 + len(TB.KEYS)).fill = (
                OKF if abs(sum(vals) - 100) < 0.6 else BADF)
        ws_.auto_filter.ref = f"A1:{get_column_letter(4 + len(TB.KEYS))}{ws_.max_row}"
        return ws_
    ws = basket_sheet("Export baskets", "basket_pre", True)
    ws.append([])
    ws.append(["HOW TO EDIT: change the green percentages for any country, keep the row near 100"])
    ws.append(["(it is renormalised on load), save, close Excel, run build_trade_model.py. A row that"])
    ws.append(["differs from 'Export baskets (model default)' by more than 0.5 points is treated as"])
    ws.append(["hand-set and used as written. Leading export, concentration, the label, the trade"])
    ws.append(["partners (through complementarity) and the atlas all follow. Shares are of DOMESTIC"])
    ws.append(["exports; a hub's re-exports are shown separately in the Trade Model sheet."])
    ws.append(["These are the shares BEFORE the world's manufacturing mix is bent to Earth's category"])
    ws.append(["shares (earth_products.EARTH_MIX); the bent shares the model actually uses are in the"])
    ws.append(["Trade Model and Categories sheets. Edit here; the bend keeps your row's tilt."])
    basket_sheet("Export baskets (model default)", "basket_default", False)

    # ---------------- Global reach (editable) ----------------
    ws = wb.create_sheet("Global reach")
    _head(ws, ["Country", "Global reach", "Model default", "GDP share of world", "Hand-edited?",
               "Top export partner", "Intra-continent share of its exports"],
          [17, 13, 13, 16, 12, 18, 30])
    flows_ = meta.get("flows") or {}
    cont = {r["name"]: r["continent"] for r in rows}
    intra_c = collections.defaultdict(float); tot_c = collections.defaultdict(float)
    for (a, b), v in flows_.items():
        tot_c[a] += v
        if cont[a] == cont[b]:
            intra_c[a] += v
    for r in sorted(rows, key=lambda r: -r["gdp"]):
        ws.append([r["name"], round(r["reach"], 3), round(r["reach_default"], 3),
                   r["gdp"] / meta["world_gdp"], "yes" if r.get("reach_edited") else "",
                   r["top_export_partners"][0][0] if r["top_export_partners"] else "",
                   intra_c[r["name"]] / tot_c[r["name"]] if tot_c[r["name"]] else 0.0])
        rr = ws.max_row
        ws.cell(row=rr, column=2).fill = GREEN
        ws.cell(row=rr, column=4).number_format = PCT
        ws.cell(row=rr, column=7).number_format = PCT
    ws.append([])
    ws.append(["Global reach divides a country's distance decay: 1.0 is the textbook value, 2.0 feels"])
    ws.append(["distance half as strongly. Defaults scale with economic size so the giants trade"])
    ws.append(["globally, as on Earth (the US does a third of its trade in its own region, Germany"])
    ws.append(["nearly 60%). Edit the green column for any country and re-run."])

    # ---------------- Earth 2015 ----------------
    ws = wb.create_sheet("Earth 2015")
    ws.append(["Andah measured against Earth 2015"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=13)
    ws.append(["Shape, not size. Every metric is a ratio or a share, so nothing here imports"])
    ws.append(["Earth's scale; it only asks whether the distribution is one a real world makes."])
    ws.append([])
    start = ws.max_row + 1
    hdr = ["Metric", "Andah", "Earth 2015", "Difference", "Verdict", "What it tests"]
    ws.append(hdr)
    for i in range(1, len(hdr) + 1):
        c = ws.cell(row=start, column=i)
        c.fill = HDR
        c.font = Font(bold=True, color="FFFFFF", size=10)
        c.alignment = Alignment(wrap_text=True)
    for label, a, e, tol, note in metrics:
        v = verdict(a, e, tol)
        ws.append([label, a, e, a - e, v, note])
        rr = ws.max_row
        for col in (2, 3, 4):
            ws.cell(row=rr, column=col).number_format = NUM
        ws.cell(row=rr, column=5).fill = OKF if v == "realistic" else BADF
        ws.cell(row=rr, column=5).font = Font(
            bold=True, color="006100" if v == "realistic" else "9C0006")
    nok = sum(1 for m in metrics if verdict(m[1], m[2], m[3]) == "realistic")
    ws.append([])
    ws.append([f"VERDICT: {nok} of {len(metrics)} metrics inside Earth 2015 tolerance."])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)

    # chart_top must be read AFTER the header row is written: openpyxl's append
    # advances _current_row, so taking max_row first put the header one row above
    # the range the chart reads, leaving both series unlabelled.
    ws.append([])
    ws.append(["Rank", "Andah share of world exports", "Earth 2015 share", "Andah country"])
    chart_top = ws.max_row
    for i in range(1, 5):
        c = ws.cell(row=chart_top, column=i)
        c.fill = HDR
        c.font = Font(bold=True, color="FFFFFF", size=10)
    e_top = M.EARTH_2015["top_exporters"]
    for i in range(20):
        ws.append([i + 1, ordered[i]["total_x"] / wx,
                   e_top[i] * 1e9 / M.EARTH_2015["world_exports"], ordered[i]["name"]])
        for col in (2, 3):
            ws.cell(row=ws.max_row, column=col).number_format = PCT
    try:
        ch = BarChart()
        ch.type = "col"
        ch.title = "Export concentration: Andah vs Earth 2015"
        ch.y_axis.title = "Share of world exports"
        ch.x_axis.title = "Rank"
        ch.height, ch.width = 9, 24
        ch.add_data(Reference(ws, min_col=2, max_col=3, min_row=chart_top,
                              max_row=chart_top + 20), titles_from_data=True)
        ch.set_categories(Reference(ws, min_col=1, min_row=chart_top + 1,
                                    max_row=chart_top + 20))
        ws.add_chart(ch, f"G{chart_top}")
    except Exception:
        pass
    for i, w in enumerate([42, 12, 13, 12, 14, 46], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ---------------- Transit ----------------
    ws = wb.create_sheet("Transit")
    _head(ws, ["Hub", "Component", "Partner", "Share of hub cargo", "Cargo units", "Note"],
          [16, 13, 14, 18, 13, 52])
    cargo_by = {r["name"]: r["cargo_own"] + r["cargo_carried"] + r["cargo_stopover"]
                + r["cargo_canal"] for r in rows}
    tot = collections.defaultdict(float)
    for hub, kind, partner, share, note in M.TRANSIT:
        tot[hub] += share
        ws.append([hub, kind, partner, share, round(cargo_by.get(hub, 0) * share), note])
        ws.cell(row=ws.max_row, column=4).fill = GREEN
    ws.append([])
    ws.append(["CHECK: each hub's shares must sum to 1.00"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    for hub, t in sorted(tot.items()):
        ws.append([hub, "", "", round(t, 4), "",
                   "OK" if abs(t - 1) < 1e-6 else "*** DOES NOT SUM TO 1.00 ***"])

    # ---------------- Constants ----------------
    ws = wb.create_sheet("Constants")
    _head(ws, ["Parameter", "Value", "What it does"], [26, 12, 96])
    for k, v, note in [
        ("WORLD_OPENNESS", M.WORLD_OPENNESS, "World exports / world GDP. Earth 2015 was 0.284."),
        ("B_POP", M.B_POP, "Population elasticity of openness. NEGATIVE and dominant: big internal markets suppress trade."),
        ("B_AREA", M.B_AREA, "Territory elasticity. Bigger countries trade more internally."),
        ("B_GDPPC", M.B_GDPPC, "Income elasticity. Richer economies trade slightly more."),
        ("B_LANDLOCKED", M.B_LANDLOCKED, "Set so the CONDITIONAL penalty matches Earth's 30%; measured at 0.287."),
        ("B_ISLAND", M.B_ISLAND, "Islands trade a little more."),
        ("B_REMOTE", M.B_REMOTE, "Distance from world demand."),
        ("B_RESOURCE", M.B_RESOURCE, "Disproportionate resource output raises exports."),
        ("THETA", M.THETA, "Gravity distance decay. From the trade literature, NOT the flight fit."),
        ("CONTIG", M.CONTIG, "Lift for a shared land border."),
        ("GRAV_A", M.GRAV_A, "Exporter GDP elasticity in the gravity equation."),
        ("GRAV_B", M.GRAV_B, "Importer GDP elasticity."),
    ]:
        ws.append([k, v, note])
        ws.cell(row=ws.max_row, column=2).fill = GREEN

    # ---------------- Validation ----------------
    ws = wb.create_sheet("Validation")
    _head(ws, ["Check", "Value", "Expected", "Status"], [52, 22, 18, 30])
    tm = sum(r["total_m"] for r in rows)
    checks = [
        ("Countries modelled", len(rows), 172, "OK" if len(rows) == 172 else "CHECK"),
        ("Geography matched", len(data["geo"]), 172, "OK" if len(data["geo"]) == 172 else "CHECK"),
        ("World exports minus world imports", round(wx - tm, 2), 0,
         "OK" if abs(wx - tm) < 1e6 else "BOOKS DO NOT BALANCE"),
        ("Gravity IPF max row error (lahn)", f"{meta['ipf_err_x']:.2e}", "< 1 lahn",
         "OK" if meta["ipf_err_x"] < 1.0 else "NOT CONVERGED"),
        ("Gravity IPF max column error (lahn)", f"{meta['ipf_err_m']:.2e}", "< 1 lahn",
         "OK" if meta["ipf_err_m"] < 1.0 else "NOT CONVERGED"),
        ("Gravity link prediction, AUC over ALL pairs (CONSISTENCY only)",
         round(meta.get("gravity_auc", 0), 4), ">0.85",
         "OK" if meta.get("gravity_auc", 0) > 0.85 else "WEAK"),
        ("  NOT independent: the flight network's demand is itself a gravity model",
         "views/flight-routes.js", "", "over the same GDP data and the same map"),
        ("  pairs scored (linked / unlinked)",
         f"{meta.get('auc_linked', 0):,} / {meta.get('auc_unlinked', 0):,}", "", ""),
        ("  GDP-only null model reaches", 0.8955, "", "distance is worth +0.05 AUC"),
        ("Intensive-margin correlation (weaker test)", round(meta["fit_r"], 4), "",
         "conditions on pairs that already have flights; a no-distance null scores 0.683"),
        ("Earth 2015 metrics realistic", nok, len(metrics),
         "OK" if nok == len(metrics) else "SEE Earth 2015 SHEET"),
        ("Landlocked countries (measured)", sum(1 for r in rows if r["landlocked"]), "", ""),
        ("Lahn: GDP source ratio to Geoscheme sheet", round(meta.get("lahn_ratio") or 0, 4), "8.0 or 1.0",
         "NEW lahn from countries.json" if abs((meta.get("lahn_ratio") or 0) - 8) < 0.01 else "check"),
        ("Export baskets hand-edited", meta.get("baskets_edited", 0), "", "read from the Export baskets sheet"),
        ("Global reach hand-edited", meta.get("reach_edited", 0), "", "read from the Global reach sheet"),
        ("Islands (measured)", sum(1 for r in rows if r["is_island"]), "", ""),
    ]
    for c in checks:
        ws.append(list(c))
        ws.cell(row=ws.max_row, column=4).fill = (
            OKF if str(c[3]).startswith("OK") else (BADF if c[3] else PatternFill()))

    ws.append([])
    ws.append(["Source data notes"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    conf = collections.defaultdict(set)
    for r in rows:
        conf[r["subregion"]].add(r["continent"])
    conf = {k: sorted(v) for k, v in conf.items() if len(v) > 1}
    if conf:
        for sub, cs in conf.items():
            members = [r["name"] for r in rows if r["subregion"] == sub]
            ws.append([f"Subregion '{sub}' is listed under {' and '.join(cs)}",
                       ", ".join(members), "", "check the Geoscheme sheet"])
    else:
        ws.append(["Every subregion belongs to exactly one continent", "", "", "OK"])
    ga = sum(g["area_km2"] for g in data["geo"].values())
    ja = sum(c["area_janus"] for c in data["countries"].values())
    ws.append([f"Area cross-check: polygons {ga:,.0f} km2 vs Janus sheet {ja:,.0f} km2",
               f"{ga/ja:.1%}", "~100%", "OK" if 0.95 < ga / ja < 1.05 else "CHECK"])

    ws.append([])
    ws.append(["Known fault in Production Statistics.xlsx"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append(["The 'Natural Gas' tab is a byte-for-byte copy of the 'Coal' tab",
               "", "", "harmless here, but fix it at source"])
    ws.append(["  The model does not use that tab: gas comes from Oil_Gas Statistics.xlsx,",
               "", "", ""])
    ws.append(["  which has 79 producers led by Pelugrotoa 23.8% and Sadain 17.8%.",
               "", "", ""])
    ws.append(["  Coal itself is genuine (Dahe 52.7% of world output); it is the gas tab",
               "", "", ""])
    ws.append(["  that was pasted over, so no coal or gas figure here is wrong.",
               "", "", ""])

    resc = data.get("rescaled_commodities") or {}
    if resc:
        ws.append([])
        ws.append([f"{len(resc)} commodity sheets did not sum to 100% of world output "
                   f"and were rescaled to true shares"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
        for cm, tot in sorted(resc.items(), key=lambda kv: -kv[1]):
            note = ("sheet appears to stack several year tables"
                    if tot > 1.15 else
                    "output missing, probably an 'other countries' row" if tot < 0.95 else "")
            ws.append([f"   {cm}", f"{tot:.1%}", "100%", note])
    skipped = data.get("production_skipped") or []
    if skipped:
        ws.append([])
        ws.append(["Commodity sheets that could not be parsed at all"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
        for nm, why in skipped:
            ws.append([f"   {nm}", why, "", "no data used"])
    unm = data.get("unmatched_producers") or {}
    if unm:
        ws.append([])
        ws.append(["Producer names that match no country (output discarded)"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
        for nm, sh in sorted(unm.items(), key=lambda kv: -kv[1]):
            ws.append([f"   {nm}", f"{sh:.2%} of a commodity", "",
                       "an Earth country left in the sheet" if nm == "Ecuador" else "check spelling"])

    try:
        wb.save(path)
    except PermissionError:
        raise SystemExit(
            f"\nCannot write {path}\nThe workbook is open in Excel, which locks the file. "
            "Close it and re-run.")
    return path
