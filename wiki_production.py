#!/usr/bin/env python3
"""
wiki_production.py - read the production tables out of the Category:Statistics pages.

DJ: "use all pages in the Category:Statistics page, this is all the data to do
with production i have."

The wiki tables and data/Production Statistics.xlsx overlap but are not the same
set: some commodities are only on the wiki, some only in the workbook, and where
both exist the wiki is the page a reader actually sees, so it is the one the
model should agree with. This module parses the wiki tables, reconciles them
against the workbook, and reports every disagreement rather than silently
preferring one.

TABLE SHAPES HANDLED
  Country cell   {{flaglist|X}} | {{flagicon|X}} [[X]] | [[X]] | plain text,
                 optionally wrapped in ''' ''' or '' ''
  Values         on the same row after || , or on their own lines starting with |
  Header rows    World / World total / Other countries are captured separately
  Missing        an en-dash, a hyphen or N/A becomes None, not zero

WHICH COLUMN IS "PRODUCTION"
  The caption and header decide. A table with Total / Mine / Refinery / Smelter
  columns means the first is the one to use; a table whose first numeric column
  is Reserves must not be read as output. The header row is parsed for this
  rather than assuming column order.
"""

import collections
import os
import re

import andah_data as ad

PAGES = os.path.join(ad.HERE, "pages", "Main")

# page title stem -> commodity key used by the model (matches the xlsx sheet names
# where one exists, so the two sources can be compared directly)
PAGE_COMMODITY = {
    "aluminium": "Aluminium", "bentonite": "Bentonite", "bismuth": "Bismuth",
    "chromium": "Chromium", "coal": "Coal", "cobalt": "Cobalt", "copper": "Copper",
    "diamond": "Diamond", "feldspar": "Feldspar", "fluorite": "Fluorite",
    "gold": "Gold", "iridium": "Iridium", "iron_ore": "Iron", "lead": "Lead",
    "lithium": "Lithium", "magnesium": "Magnesium", "manganese": "Manganese",
    "mercury": "Mercury", "nickel": "Nickel", "niobium": "Niobium",
    "palladium": "Palladium", "platinum": "Platinum", "salt": "Salt",
    "silicon": "Silicon", "silver": "Silver",
    # The "thoruim production" page is captioned "Thoruim Reserves by country":
    # it is a stock, not a flow, so it must not be read as output.
    "thoruim": "__reserves_thorium",
    "tin": "Tin", "titanium": "Titanium", "uranium": "Uranium",
    "vanadium": "Vanadium", "zinc": "Zinc",
    # reserves pages: stock, not flow. Kept separate and never mixed into output.
    "natural_gas_proven_reserves": "__reserves_gas",
    "proven_oil_reserves": "__reserves_oil",
}

AGGREGATE_ROWS = ("world", "other countries", "other", "total", "rest of world")
MISSING = {"", "-", "–", "—", "n/a", "na", "nil", "none", "?"}


# Every flag template these tables use. The first parameter is the country, and
# it is the most reliable name in the cell: a wiki link may point at a topic
# rather than a country ("[[Gold mining in Gaeiya|Gaeiya]]"), but the flag
# template always names the country itself.
FLAG_TEMPLATE = re.compile(
    r"\{\{\s*(?:flag|flaglist|flagdeco|flagicon|flagcountry|noflag|flag\+link)\s*\|\s*([^}|]+)",
    re.I)


def _clean_country(cell):
    """
    Pull a country name out of a wiki table cell.

    Order matters. Reading the wiki link first looked right until the gold table,
    where "{{flagdeco|Gaeiya}} [[Gold mining in Gaeiya|Gaeiya]]" would have
    yielded the article title rather than the country. Flag templates first,
    then a link's LABEL (the half after the pipe, which is what a reader sees),
    then the link target, then whatever plain text is left.
    """
    s = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", cell, flags=re.S).strip()
    s = re.sub(r"'{2,}", "", s)                          # bold/italic markup
    m = FLAG_TEMPLATE.search(s)
    if m:
        return m.group(1).strip()
    m = re.search(r"\[\[[^\]|]+\|([^\]]+)\]\]", s)       # [[target|label]]
    if m:
        return m.group(1).strip()
    m = re.search(r"\[\[([^\]|]+)\]\]", s)               # [[target]]
    if m:
        return m.group(1).strip()
    s = re.sub(r"\{\{[^}]*\}\}", "", s)                  # a bare {{noflag}} etc
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip(" |")


def _number(cell):
    s = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", cell, flags=re.S)
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    s = re.sub(r"'{2,}", "", s).strip()
    if s.lower() in MISSING:
        return None
    m = re.search(r"-?[\d][\d,\. ]*", s)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "").replace(" ", ""))
    except ValueError:
        return None


# Attributes sit before a single pipe: rowspan="2" |Country. The test is that
# the prefix carries an "=" and no bracket, so a pipe inside a {{cite}} or a
# [[link]] stays where it is instead of being read as an attribute divider.
_HDR_ATTR = re.compile(r"^([^|\[{]*?=[^|\[{]*?)\|(?!\|)(.*)$", re.S)


def _header_cells(table):
    """
    The header cells of a wikitable, in column order.

    A row of headers may be written one per line or joined on one line with
    "!!", and the platinum, vanadium, bismuth and manganese tables use the
    joined form:

        ! Country !! Production (kg)
        !Year

    Read a line at a time that yields two headers rather than three, so "Year"
    sat at index 1 and the ban list in _production_column knocked out the
    column before it, which was Production. The picker then fell through to
    the year itself, and every country dated 1762 was recorded as producing
    1762/1764 = 99.9% of the world's platinum. Splitting on "!!" is what keeps
    header index aligned with column index.
    """
    cells = []
    for line in re.findall(r"^\s*!(.*)$", table, re.M):
        for raw in line.split("!!"):
            m = _HDR_ATTR.match(raw.strip())
            raw = m.group(2) if m else raw
            raw = re.sub(r"\{\{[^{}]*\}\}|<[^>]+>|'{2,}", "", raw)
            cells.append(raw.strip())
    return cells


def parse_table(text):
    """
    Return (rows, aggregates, headers) from the first wikitable in `text`.
    rows: [(country, [values...])], aggregates: {'world': [...], ...}
    """
    start = text.find("{|")
    if start < 0:
        return [], {}, []
    depth, i = 0, start
    while i < len(text) - 1:
        if text[i:i + 2] == "{|":
            depth += 1
            i += 2
            continue
        if text[i:i + 2] == "|}":
            depth -= 1
            i += 2
            if depth == 0:
                break
            continue
        i += 1
    table = text[start:i]

    headers = _header_cells(table)

    # A leading Rank column pushes the country into the second cell. Detected
    # from the header rather than guessed per row: the uranium table is the one
    # that needs it, and without this every row's "country" was the rank digit.
    hl0 = [h.lower().strip() for h in headers[:2]]
    rank_first = bool(hl0) and hl0[0] in ("rank", "no", "no.", "#", "num")

    rows, aggregates = [], {}
    for block in re.split(r"\n\|-", table)[1:]:
        block = block.strip()
        if not block or block.startswith("!"):
            continue
        cells = []
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("!"):
                continue
            if not line.startswith("|"):
                if cells:
                    cells[-1] += " " + line
                continue
            for part in line[1:].split("||"):
                cells.append(part)
        if not cells:
            continue
        # Some tables lead with a rank column, so the country sits in cell 1.
        # Detect it from the header rather than guessing per row.
        first = 1 if rank_first and len(cells) > 1 else 0
        name = _clean_country(cells[first])
        vals = [_number(c) for c in cells[first + 1:]]
        if not name:
            continue
        low = name.lower().strip("' ")
        if any(low.startswith(a) for a in AGGREGATE_ROWS):
            aggregates[low.split()[0]] = vals
        else:
            rows.append((name, vals))
    return rows, aggregates, headers


def _production_column(headers, rows):
    """
    Which value column is output? Prefer a header naming production or the total;
    never a reserves column. Falls back to the first column with real numbers.
    """
    hl = [h.lower() for h in headers]

    # Columns that are never output, whatever else the header says. "Year" is
    # here because a value like 1762 parses as a perfectly good number and would
    # otherwise be read as tonnes; "% of total" and "rank" likewise.
    def banned(h):
        return ("reserve" in h or "year" in h or "%" in h or "percent" in h
                or "rank" in h or h.strip() in ("no", "no.", "#"))

    # THE FIRST NON-BANNED COLUMN IS THE HEADLINE OUTPUT, in every table here:
    # copper's Total, gold's Gold production, cobalt's Production, zinc's Mine,
    # aluminium's Primary aluminium. An earlier version instead hunted for a
    # header containing "production", which on the aluminium page matched
    # "Bauxite -> Production" four columns along and read bauxite reserves as
    # aluminium output, putting Vayvele top of a table Dahe leads by 7x.
    # rowspan and colspan make header-to-column mapping unreliable, so position
    # is the safer signal and the ban list does the discriminating.
    width = max((len(v) for _, v in rows), default=0)
    banned_cols = {i - 1 for i, h in enumerate(hl) if banned(h)}
    for j in range(width):
        if j in banned_cols:
            continue
        if sum(1 for _, v in rows if len(v) > j and v[j] is not None) >= 3:
            return j
    return 0


def load_wiki_production():
    """
    {commodity: {country: share of world output}} from the wiki pages, plus a
    report of everything that needed a decision.
    """
    out, report = {}, []
    canon = set(ad.load_janus())
    lower = {c.lower(): c for c in canon}

    for fn in sorted(os.listdir(PAGES)):
        m = re.match(r"List_of_countries_by_(.+)_production\.wiki$", fn)
        stem = None
        if m:
            stem = m.group(1).lower()
        elif fn in ("List_of_countries_by_natural_gas_proven_reserves.wiki",
                    "List_of_countries_by_proven_oil_reserves.wiki"):
            stem = fn[len("List_of_countries_by_"):-len(".wiki")].lower()
        if not stem:
            continue
        commodity = PAGE_COMMODITY.get(stem)
        if not commodity:
            report.append((fn, "no commodity mapping", ""))
            continue
        if commodity.startswith("__"):
            continue                                   # reserves: stock, not flow

        text = open(os.path.join(PAGES, fn), encoding="utf-8", errors="ignore").read()
        rows, aggregates, headers = parse_table(text)
        if not rows:
            report.append((fn, "no rows parsed (table may be transposed)", ""))
            continue
        col = _production_column(headers, rows)

        per, dupes, unknown = {}, [], []
        for name, vals in rows:
            v = vals[col] if len(vals) > col else None
            if v is None or v <= 0:
                continue
            cn = name if name in canon else lower.get(name.lower())
            if not cn:
                unknown.append(name)
                continue
            if cn in per:
                dupes.append((cn, per[cn], v))
                per[cn] += v          # same country listed twice: sum the rows
            else:
                per[cn] = v
        if not per:
            report.append((fn, "no usable country values", f"col={col}"))
            continue

        world = None
        wagg = aggregates.get("world")
        if wagg and len(wagg) > col and wagg[col]:
            world = wagg[col]
        other = aggregates.get("other")
        listed = sum(per.values()) + (
            other[col] if other and len(other) > col and other[col] else 0)
        # A World row larger than the countries listed under it is the normal
        # case: the remainder is the producers the page leaves out, and the
        # shares should fall short of 100% by exactly that much. A World row
        # SMALLER than its own rows cannot be the denominator, because the
        # countries named on the page would then hold more than all of world
        # output: bismuth states 9,000 tonnes over rows that sum to 12,138, and
        # every producer's share was inflated by 35%. Where the page contradicts
        # itself the rows win over the summary, and the conflict is reported.
        total = max(world, listed) if world else listed
        if world and listed > world * 1.001:
            report.append((fn, "World row is below the sum of its own rows",
                           f"world {world:,.0f} vs rows {listed:,.0f} "
                           f"({listed / world - 1:+.0%}); rows used"))

        out[commodity] = {k: v / total for k, v in per.items()}
        if dupes:
            report.append((fn, f"{len(dupes)} duplicate country rows summed",
                           ", ".join(f"{c} ({a:,.0f}+{b:,.0f})" for c, a, b in dupes[:3])))
        if unknown:
            report.append((fn, f"{len(unknown)} unrecognised names dropped",
                           ", ".join(sorted(set(unknown))[:6])))
        if not world:
            report.append((fn, "no World row; total summed from the countries", ""))
    return out, report


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    wiki, report = load_wiki_production()
    xlsx, _ = ad.load_production()
    xlsx.update(ad.load_oil_gas())
    canon = set(ad.load_janus())
    xlsx, _unm, _res, _short = ad.canonicalise_production(xlsx, canon)

    print(f"wiki commodities parsed: {len(wiki)}   xlsx commodities: {len(xlsx)}")
    print(f"only on the wiki : {sorted(set(wiki) - set(xlsx))}")
    print(f"only in the xlsx : {sorted(set(xlsx) - set(wiki))}")
    print()
    print(f"{'COMMODITY':<16}{'wiki n':>7}{'xlsx n':>7}{'top wiki':>16}{'top xlsx':>16}{'  agreement'}")
    print("-" * 82)
    for c in sorted(set(wiki) & set(xlsx)):
        w, x = wiki[c], xlsx[c]
        tw = max(w.items(), key=lambda kv: kv[1])
        tx = max(x.items(), key=lambda kv: kv[1])
        # Normalise BOTH sides before comparing. The workbook deliberately leaves
        # shortfall commodities summing to under 1 (their "other countries" mass
        # is real), so a raw comparison against the wiki's 1.0 reported a
        # difference that was mostly the missing tail, not disagreement.
        sw, sx = sum(w.values()) or 1, sum(x.values()) or 1
        wn = {k: v / sw for k, v in w.items()}
        xn = {k: v / sx for k, v in x.items()}
        diff = sum(abs(wn.get(k, 0) - xn.get(k, 0)) for k in set(wn) | set(xn)) / 2
        agree = f"{max(0.0, 1 - diff):.0%}"
        print(f"{c:<16}{len(w):>7}{len(x):>7}{tw[0][:13]:>16}{tx[0][:13]:>16}{agree:>12}")
    print()
    print("PARSER REPORT")
    for fn, what, detail in report:
        print(f"  {fn[:52]:<54}{what}{('  ' + detail) if detail else ''}")
