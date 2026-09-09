"""Rescale every lahn-denominated figure on the wiki by x8.

Covers four layers:
  1. {{lahn}}-prefixed figures in prose and infoboxes (incl. the stray
     "{{lahn}}$" doubled markers and the bare "$" GDP infobox values).
  2. The four List of countries by GDP tables (column values only, never
     the Year columns and never anything inside a <ref>).
  3. data/Andah_Janus Statistics.xlsx - the literal GDP inputs, plus the
     lahn->USD factor in the military columns (1.5 -> 0.1875) so the USD
     figures stay at their present real-world value.

Charts (<timeline>) and map legends ({{legend}}) are deliberately left
alone, as are Vurahi.wiki and Economy_of_Virauzau.wiki, which use the raw
lahn symbol and appear to already sit on the new scale.

THIS TRANSFORM IS NOT IDEMPOTENT. Running it twice over the same file
multiplies by 64. Every file it scales is recorded in .lahn_scaled.json and
skipped on later runs; --force overrides that, and should only be used on a
file that has been freshly re-pulled from the wiki.

Usage:
    python scale_lahn.py --dry-run     # report only, writes nothing
    python scale_lahn.py --apply       # rewrite files in place
    python scale_lahn.py --apply --files pages/Main/Dahe.wiki --force
                                       # re-scale specific re-pulled pages
"""

import argparse
import io
import pathlib
import re
import sys
from decimal import Decimal, ROUND_HALF_UP

FACTOR = Decimal(8)
MAIN = pathlib.Path("pages/Main")
XLSX = pathlib.Path("data/Andah_Janus Statistics.xlsx")
STAMP = pathlib.Path(".lahn_scaled.json")

# Pages that already sit on the new scale (raw lahn symbol, not {{lahn}}).
SKIP_PAGES = {"Vurahi.wiki", "Economy_of_Virauzau.wiki"}

LIST_PAGES = {
    "List_of_countries_by_GDP_(nominal).wiki",
    "List_of_countries_by_GDP_(PPP).wiki",
    "List_of_countries_by_GDP_(nominal)_per_capita.wiki",
    "List_of_countries_by_GDP_(PPP)_per_capita.wiki",
}

UNIT_CHAIN = ["thousand", "million", "billion", "trillion"]

NUM = r"[0-9](?:[0-9,]*[0-9])?(?:\.[0-9]+)?"
REF = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.S)

# {{lahn}}[$]1,234.5[&nbsp;| ]billion
LAHN_FIG = re.compile(
    r"(\{\{lahn\}\})(\$?)(" + NUM + r")((?:&nbsp;|[ ])?)"
    r"(trillion|billion|million|thousand)?"
)
# {{increase}}$19.845 billion  ->  {{increase}} {{lahn}}158.76 billion
DOLLAR_FIG = re.compile(
    r"(\{\{(?:increase|decrease|steady)\}\})[ ]?\$(" + NUM + r")((?:&nbsp;|[ ])?)"
    r"(trillion|billion|million|thousand)?"
)


def fmt(d):
    """Render a Decimal in wiki house style.

    At most three decimal places (promotion divides by 1000, which would
    otherwise leave figures like 1.471056 trillion), trailing zeros trimmed,
    and thousands separators once the integer part passes three digits.
    """
    d = d.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    ip, fp = format(d, "f").split(".")
    fp = fp.rstrip("0")
    if len(ip) > 3:
        ip = "{:,}".format(int(ip))
    return ip + ("." + fp if fp else "")


def scale(num_str, unit):
    """Multiply by 8, promoting the unit word once the value passes 1000.

    Promotion stops at 'trillion' so the wiki never has to say quadrillion.
    An unrecognised or misspelled unit is left untouched and the bare number
    is scaled in place.
    """
    d = Decimal(num_str.replace(",", "")) * FACTOR
    if unit and unit.lower() in UNIT_CHAIN:
        i = UNIT_CHAIN.index(unit.lower())
        while d >= 1000 and i < len(UNIT_CHAIN) - 1:
            d = d / 1000
            i += 1
        unit = UNIT_CHAIN[i]
    return fmt(d), unit


def do_lahn_figures(text, log, page):
    """Layer 1: every {{lahn}}-anchored figure, plus the {{increase}}$ ones."""

    def rebuild(prefix, num, sep, unit):
        """Keep the original separator even when no unit word was matched.

        The regex swallows the space after the figure whether or not the word
        that follows is a recognised unit, so dropping sep here would weld the
        number onto ordinary prose ("{{lahn}}3,840,000to") or onto a misspelled
        unit ("...904milion").
        """
        new_num, new_unit = scale(num, unit)
        if new_unit:
            return prefix + new_num + (sep or " ") + new_unit
        return prefix + new_num + sep

    def repl_lahn(m):
        marker, dollar, num, sep, unit = m.groups()
        out = rebuild(marker, num, sep, unit)
        log.append((page, m.group(0), out, "lahn$" if dollar else "lahn"))
        return out

    def repl_dollar(m):
        arrow, num, sep, unit = m.groups()
        out = rebuild(arrow + " {{lahn}}", num, sep, unit)
        log.append((page, m.group(0), out, "bare$"))
        return out

    text = LAHN_FIG.sub(repl_lahn, text)
    text = DOLLAR_FIG.sub(repl_dollar, text)
    return text


ROW_START = re.compile(r'^\|\s*(?:style="[^"]*"\s*\|\s*)?\{\{(?:flag|noflag)\|')
# A number that forms an entire table cell. The trailing group has to tolerate
# a masked <ref> placeholder, otherwise every cited value (the World row, and
# the first value of each source column) is silently skipped.
CELL_NUM = re.compile(
    r"(?<=\|)([ \t]*)(" + NUM + r")((?:[ \t]|\x01\d+\x01)*)(?=\||\x00|$)"
)
YEAR = re.compile(r"^1[67][0-9]{2}$")


def do_list_table(text, log, page):
    """Layer 2: value cells in the GDP tables.

    Rows are collected as logical blocks because ~7 rows per page put their
    first value on the country line, separated by a single pipe. Refs are
    masked first so ref years and URLs are never touched. Year cells
    (16xx/17xx) are skipped; no real value cell is a bare 4-digit number.
    """
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        if not ROW_START.match(lines[i]):
            out.append(lines[i])
            i += 1
            continue
        block = [lines[i]]
        j = i + 1
        while (
            j < len(lines)
            and lines[j].strip()
            and not lines[j].startswith("|-")
            and not lines[j].startswith("|}")
            and not ROW_START.match(lines[j])
        ):
            block.append(lines[j])
            j += 1

        joined = "\x00".join(block)
        refs = []

        def stash(m):
            refs.append(m.group(0))
            return "\x01%d\x01" % (len(refs) - 1)

        masked = REF.sub(stash, joined)

        def repl(m):
            lead, num, trail = m.group(1), m.group(2), m.group(3)
            if YEAR.match(num):
                return m.group(0)
            new_num, _ = scale(num, None)
            log.append((page, num, new_num, "table"))
            return lead + new_num + trail

        masked = CELL_NUM.sub(repl, masked)
        restored = re.sub(r"\x01(\d+)\x01", lambda m: refs[int(m.group(1))], masked)
        out.extend(restored.split("\x00"))
        i = j
    return "\n".join(out)


def load_stamp():
    import json
    if STAMP.exists():
        return set(json.loads(STAMP.read_text(encoding="utf-8")))
    return set()


def save_stamp(done):
    import json
    STAMP.write_text(json.dumps(sorted(done), indent=1), encoding="utf-8")


def run_wiki(apply, report, only=None, force=False):
    log = []
    touched = {}
    done = load_stamp()
    already = 0
    for f in sorted(MAIN.glob("*.wiki")):
        if f.name in SKIP_PAGES:
            continue
        if only and str(f).replace("\\", "/") not in only:
            continue
        if f.name in done and not force:
            already += 1
            continue
        original = f.read_text(encoding="utf-8")
        text = original
        if f.name in LIST_PAGES:
            text = do_list_table(text, log, f.name)
        text = do_lahn_figures(text, log, f.name)
        if text != original:
            touched[f] = text

    kinds = {}
    for entry in log:
        kinds[entry[3]] = kinds.get(entry[3], 0) + 1
    report.write("=== LAYER 1+2: WIKI ===\n")
    report.write("files changed: %d\n" % len(touched))
    for k, v in sorted(kinds.items()):
        report.write("  %-8s %d edits\n" % (k, v))
    report.write("\n--- every non-table edit ---\n")
    for page, before, after, kind in log:
        if kind != "table":
            report.write("  %-44s %-34s -> %s\n" % (page, before, after))
    report.write("\n--- table edits, first 40 ---\n")
    n = 0
    for page, before, after, kind in log:
        if kind == "table" and n < 40:
            report.write("  %-46s %14s -> %s\n" % (page, before, after))
            n += 1

    report.write("\nskipped (already scaled, see .lahn_scaled.json): %d\n" % already)
    if apply:
        for f, text in touched.items():
            f.write_text(text, encoding="utf-8")
            done.add(f.name)
        save_stamp(done)
    return touched, kinds


def run_xlsx(apply, report):
    import openpyxl

    wb = openpyxl.load_workbook(XLSX)
    ws = wb["ALL"]
    hdr = [c.value for c in ws[1]]
    cols = {name: idx + 1 for idx, name in enumerate(hdr) if name}
    money = ["GDP (Nominal)", "Per (NOM)", "GDP (PPP)", "Per (PPP)"]
    scaled = 0
    report.write("\n\n=== LAYER 3: SPREADSHEET ===\n")
    for name in money:
        ci = cols[name]
        n = 0
        for r in range(2, ws.max_row + 1):
            v = ws.cell(r, ci).value
            if v is None or isinstance(v, str):
                continue  # blank, or a formula that will cascade on its own
            ws.cell(r, ci).value = float(Decimal(str(v)) * FACTOR)
            n += 1
        scaled += n
        report.write("  %-16s scaled %d literal cells\n" % (name, n))

    fixed = 0
    for name in ["Military NOM USD ", "Military PPP USD"]:
        ci = cols[name]
        for r in range(2, ws.max_row + 1):
            v = ws.cell(r, ci).value
            if isinstance(v, str) and "1.5" in v:
                ws.cell(r, ci).value = v.replace("*1.5", "*0.1875")
                fixed += 1
    report.write("  USD factor 1.5 -> 0.1875 in %d formula cells\n" % fixed)
    if apply:
        wb.save(XLSX)
    return scaled, fixed


def leftovers(report):
    report.write("\n\n=== LEFTOVER '$' AND RAW SYMBOL (post-check) ===\n")
    for f in sorted(MAIN.glob("*.wiki")):
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\$|₳", t):
            ctx = t[max(0, m.start() - 55): m.start() + 45].replace("\n", "\\n")
            report.write("  %-36s ...%s...\n" % (f.name, ctx))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--files", nargs="*", default=None,
                    help="restrict to these paths (use after a re-pull)")
    ap.add_argument("--force", action="store_true",
                    help="re-scale even if already recorded in .lahn_scaled.json")
    a = ap.parse_args()
    if not (a.apply or a.dry_run):
        ap.error("pass --dry-run or --apply")

    report = io.open("scale_report.txt", "w", encoding="utf-8")
    report.write("MODE: %s\n\n" % ("APPLY" if a.apply else "DRY RUN"))
    only = set(x.replace("\\", "/") for x in a.files) if a.files else None
    touched, kinds = run_wiki(a.apply, report, only=only, force=a.force)
    if a.files:
        scaled = fixed = 0
        report.write("\n\n=== LAYER 3 SKIPPED (--files run) ===\n")
    elif "__xlsx__" in load_stamp() and not a.force:
        scaled = fixed = 0
        report.write("\n\n=== LAYER 3 SKIPPED (spreadsheet already rescaled) ===\n")
    else:
        scaled, fixed = run_xlsx(a.apply, report)
        if a.apply:
            done = load_stamp()
            done.add("__xlsx__")
            save_stamp(done)
    leftovers(report)
    report.close()

    print("mode:          %s" % ("APPLY" if a.apply else "DRY RUN"))
    print("wiki files:    %d" % len(touched))
    for k, v in sorted(kinds.items()):
        print("  %-8s %d" % (k, v))
    print("xlsx cells:    %d scaled, %d USD formulas" % (scaled, fixed))
    print("report:        scale_report.txt")


if __name__ == "__main__":
    main()
