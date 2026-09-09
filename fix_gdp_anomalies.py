"""Repair infobox GDP figures that disagree with the authoritative list tables.

Only touches figures whose error is a clean power of ten (a comma used as a
decimal point, a full stop used as a thousands separator, or a missing or
misspelled unit word). Those are unambiguous formatting faults, and the correct
value is taken from the four List of countries by GDP pages, never invented.

Figures that merely disagree with the tables by an untidy ratio are left alone
and reported: those are two different numbers, not a typo, and choosing between
them is a content decision.

Usage:
    python fix_gdp_anomalies.py --dry-run
    python fix_gdp_anomalies.py --apply
"""

import argparse
import io
import pathlib
import re
from decimal import Decimal, ROUND_HALF_UP

MAIN = pathlib.Path("pages/Main")
REF = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.S)
ROW = re.compile(r'^\|\s*(?:style="[^"]*"\s*\|\s*)?\{\{(?:flag|noflag)\|([^}|]+)')
NUM = r"[0-9](?:[0-9,]*[0-9])?(?:\.[0-9]+)?"
UNIT = {"thousand": Decimal(10) ** 3, "million": Decimal(10) ** 6,
        "billion": Decimal(10) ** 9, "trillion": Decimal(10) ** 12}

# ratios that mean "formatting fault", not "different number"
CLEAN = [Decimal(10) ** e for e in (-9, -6, -3, 3, 6, 9)]
TOL = Decimal("0.02")


def parse_list(name):
    t = (MAIN / name).read_text(encoding="utf-8")
    lines = t.split("\n")
    out, i = {}, 0
    while i < len(lines):
        m = ROW.match(lines[i])
        if not m:
            i += 1
            continue
        block, j = [lines[i]], i + 1
        while (j < len(lines) and lines[j].strip()
               and not lines[j].startswith(("|-", "|}")) and not ROW.match(lines[j])):
            block.append(lines[j]); j += 1
        joined = REF.sub("", "\x00".join(block))
        cells = [c.strip() for c in re.split(r"\|\||\x00\s*\||^\|", joined)]
        vals = [c for c in cells
                if re.fullmatch(NUM, c) and not re.fullmatch(r"1[67][0-9]{2}", c)]
        if vals:
            out[m.group(1).strip()] = Decimal(vals[0].replace(",", ""))
        i = j
    return out


SOURCES = {
    "GDP_nominal": (parse_list("List_of_countries_by_GDP_(nominal).wiki"), True),
    "GDP_PPP": (parse_list("List_of_countries_by_GDP_(PPP).wiki"), True),
    "GDP_nominal_per_capita": (parse_list("List_of_countries_by_GDP_(nominal)_per_capita.wiki"), False),
    "GDP_PPP_per_capita": (parse_list("List_of_countries_by_GDP_(PPP)_per_capita.wiki"), False),
}


def house(amount, per_capita):
    """Render an absolute lahn amount the way the infoboxes do."""
    if per_capita:
        return "{:,}".format(int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))), ""
    for word in ("trillion", "billion", "million"):
        if amount >= UNIT[word]:
            d = (amount / UNIT[word]).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            ip, fp = format(d, "f").split(".")
            fp = fp.rstrip("0")
            if len(ip) > 3:
                ip = "{:,}".format(int(ip))
            return ip + ("." + fp if fp else ""), word
    return "{:,}".format(int(amount)), ""


FIELD = re.compile(
    r"(^\|\s*(GDP_nominal|GDP_PPP|GDP_nominal_per_capita|GDP_PPP_per_capita)\s*=\s*"
    r"(?:\{\{(?:increase|decrease|steady)[A-Za-z]*\}\}\s*)?)"
    r"(\{\{lahn\}\})(" + NUM + r")((?:&nbsp;|\s)?)([A-Za-z]+)?", re.M)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not (a.apply or a.dry_run):
        ap.error("pass --dry-run or --apply")

    out = io.open("fix_report.txt", "w", encoding="utf-8")
    fixed, skipped, touched = [], [], {}

    for f in sorted(MAIN.glob("*.wiki")):
        text = f.read_text(encoding="utf-8")
        country = f.stem.replace("_", " ")
        changed = text

        def repl(m):
            head, field, marker, numtxt, sep, unit = m.groups()
            table, is_agg = SOURCES[field]
            if country not in table:
                return m.group(0)
            want = table[country] * (UNIT["million"] if is_agg else Decimal(1))
            got = Decimal(numtxt.replace(",", ""))
            if unit and unit.lower() in UNIT:
                got *= UNIT[unit.lower()]
            if want == 0:
                return m.group(0)
            ratio = got / want
            if abs(ratio - 1) <= Decimal("0.03"):
                return m.group(0)
            if not any(abs(ratio / c - 1) <= TOL for c in CLEAN):
                skipped.append((country, field, m.group(0).split("=")[-1].strip(),
                                house(want, not is_agg), f"{ratio:.4g}"))
                return m.group(0)
            newnum, newunit = house(want, not is_agg)
            rebuilt = head + marker + newnum + ((" " + newunit) if newunit else "")
            fixed.append((country, field, m.group(0).split("=")[-1].strip(),
                          rebuilt.split("=")[-1].strip(), f"{ratio:.4g}"))
            return rebuilt

        changed = FIELD.sub(repl, changed)
        if changed != text:
            touched[f] = changed

    out.write("=== REPAIRED (clean power-of-ten fault, value from list tables) ===\n")
    for c, fld, before, after, r in fixed:
        out.write("  %-16s %-24s %-28s -> %-24s (was off %sx)\n" % (c, fld, before, after, r))
    out.write("\n=== LEFT ALONE (genuine disagreement, needs a human) ===\n")
    for c, fld, before, want, r in skipped:
        out.write("  %-16s %-24s %-28s  list says %s  (off %sx)\n"
                  % (c, fld, before, " ".join(x for x in want if x), r))
    out.close()

    if a.apply:
        for f, t in touched.items():
            f.write_text(t, encoding="utf-8")

    print("mode:    ", "APPLY" if a.apply else "DRY RUN")
    print("repaired:", len(fixed), "figures in", len(touched), "pages")
    print("left:    ", len(skipped), "genuine disagreements")
    print("report:   fix_report.txt")


if __name__ == "__main__":
    main()
