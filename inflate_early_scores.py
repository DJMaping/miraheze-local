#!/usr/bin/env python3
"""Inflate pre-1700 (Ayuman Cup) scoring to early-football blowout levels.

One-off content script (stdlib only, no network). Real football before the
professional era produced wild, lopsided scores; the seven pre-1700 editions of
the competition (the Ayuman Cup, 1656-1684) currently score like modern
tournaments (~2.1-2.9 goals/match). This rewrites their match scores onto a
"bold early -> moderate later" arc that eases back to modern levels by 1700,
keeping every derived table internally consistent.

What it changes, per page (pages/Main/<year>_Ayuman_Cup.wiki):
  * group match scorelines (an edition-specific inflation, winners widened);
  * group standings GF/GA/GD (recomputed from the new results; W/D/L/Pts are
    deliberately preserved so qualification never changes);
  * the derived runner-up / third-placed ranking tables (1668, 1680);
  * knockout {{Football box}} scores + goal-scorer minute lists;
  * the bracket numbers (synced to the boxes);
  * the Goalscorers tier list, infobox totals + top scorer, and the Goalscorers
    prose sentence;
  * the four "ordinary" finals (1656/1668/1672/1684) get a modest lift with a
    rewritten narration. Three landmark finals are kept verbatim: 1660 (6-1, the
    most emphatic final), 1676 (3-0, won without conceding) and 1680 (0-0, the
    coin-toss final).

Design guarantees / invariants (asserted before any file is written):
  * every match keeps its result (winner stays winner; draws stay draws; 0-0
    stays 0-0), so points and standings order are untouched;
  * group GF == sum of that team's goals in the new results, GA likewise;
  * each {{Football box}} goal-event count == the new score on each side;
  * infobox "Goals scored" == sum of every new match; average to 2 dp;
  * tier-list leader == infobox top scorer == prose top scorer;
  * no em-dash (U+2014) is introduced; scorelines use the en-dash U+2013 and GD
    uses U+2212, matching the existing style.

Generation is deterministic (added goal minutes are seeded per match), so the
script is idempotent: it backs up each pristine page to
``pages/Main/.orig_early_scores/`` on first run and always re-derives from that
backup, so re-running produces the same output and ``--restore`` undoes it.

Usage:
  python inflate_early_scores.py dry       # preview + run all invariant checks
  python inflate_early_scores.py apply      # write the pages
  python inflate_early_scores.py verify     # re-check the live pages on disk
  python inflate_early_scores.py --restore  # restore originals from backup
"""

import os
import re
import sys
import hashlib
import random

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, "pages", "Main")
BACKUP = os.path.join(PAGES, ".orig_early_scores")

YEARS = [1656, 1660, 1668, 1672, 1676, 1680, 1684]

EN = "–"   # en dash, used in scorelines
MIN = "−"  # minus sign, used in GD column
EM = "—"   # em dash, must never appear

FLAG_RE = re.compile(r"\{\{\s*[Ff]lag(?:icon|country)?\s*\|\s*([^|}]+?)\s*(?:\|[^}]*)?\}\}")
SCORE_RE = re.compile(r"(\d+)\s*" + EN + r"\s*(\d+)")
GOAL_RE = re.compile(r"\{\{\s*[Gg]oal\s*\|([^}]*)\}\}")

# Per-edition inflation factors:
#   GW/GL  group winner / loser multipliers (winners widened for blowouts)
#   GDF    group draw multiplier (applied symmetrically)
#   KW/KL  non-final knockout winner / loser multipliers (gentler)
#   TIER   tier-list / top-scorer multiplier
FACT = {
    1656: dict(GW=2.5, GL=1.5, GDF=2.0, KW=1.6, KL=1.2, TIER=2.5),
    1660: dict(GW=2.4, GL=1.5, GDF=2.0, KW=1.6, KL=1.2, TIER=2.0),
    1668: dict(GW=2.3, GL=1.4, GDF=1.9, KW=1.5, KL=1.2, TIER=2.0),
    1672: dict(GW=1.9, GL=1.3, GDF=1.6, KW=1.4, KL=1.2, TIER=1.7),
    1676: dict(GW=1.6, GL=1.25, GDF=1.4, KW=1.3, KL=1.1, TIER=1.5),
    1680: dict(GW=1.6, GL=1.25, GDF=1.45, KW=1.3, KL=1.1, TIER=1.35),
    1684: dict(GW=1.2, GL=1.1, GDF=1.15, KW=1.15, KL=1.05, TIER=1.15),
}

# Ordinary finals that get a modest lift. The three landmark finals
# (1660, 1676, 1680) are intentionally absent and left verbatim.
FINALS = {
    1656: dict(
        score=(6, 3),
        goals1="Brody {{Goal|14|44|67}}<br/>Sael {{Goal|39}}<br/>Verd {{Goal|58|81}}",
        goals2="Renn {{Goal|28|62}}<br/>Molde {{Goal|73}}",
        ts_final=3,
        lead_old="4" + EN + "2 in the [[#Final|final]]",
        lead_new="6" + EN + "3 in the [[#Final|final]]",
        narration=(
            "The final was held at the Bagusil Grand Stadium on 2 July 1656 before an "
            "estimated crowd of 13,000, the largest of the tournament. [[Estijan]] took "
            "the lead through Tomas Brody, the tournament's leading scorer, and although "
            "Halvard Renn levelled for [[Eldjo]], Emeric Sael and a second from Brody "
            "carried the side to a 3" + EN + "1 advantage by the interval. Brody completed "
            "his hat-trick after the break and Lukan Verd struck twice, with a second from "
            "Renn and a late goal from Sigur Molde offering Eldjo only consolation in a "
            "6" + EN + "3 win. The victory secured the first title in the competition's "
            "history, and the [[FLLA World Cup#The Ayuma Cup|Ayuma Cup]] was presented to "
            "the Estijani captain at the close of the match, the first time the trophy was "
            "awarded.<ref name=\"heritage-final\">{{cite web|url=https://www.flla.org/"
            "heritage/world-cup/1656/final|title=The 1656 Ayuman Cup final: Estijan "
            "6" + EN + "3 Eldjo|publisher=[[FLLA]]|date=14 March 1763}}</ref>"),
    ),
    1668: dict(
        score=(3, 1),
        goals1="Calier {{Goal|41|58}}<br/>Voral {{Goal|73}}",
        goals2="Halson {{Goal|26}}",
        ts_final=2,
        lead_old="2" + EN + "1 in the [[#Final|final]]",
        lead_new="3" + EN + "1 in the [[#Final|final]]",
        narration=(
            "The final was held at the Jioquin Grand Stadium on 2 July 1668 before an "
            "estimated crowd of 18,000. [[Estijan]] led at the interval through Brod "
            "Halson, but [[Lycroa]] turned the match after the break: Tomas Calier, the "
            "tournament's leading scorer, levelled and then struck again to put his side "
            "ahead, before Ferid Voral added a third late on for a 3" + EN + "1 victory. "
            "The win secured Lycroa's second title, and the original [[FLLA World Cup#The "
            "Andah Cup|Andah Cup]] was presented to the Lycroan captain at the close of "
            "the match.<ref name=\"heritage-final\">{{cite web|url=https://www.flla.org/"
            "heritage/world-cup/1668/final|title=The 1668 Ayuman Cup final: Lycroa "
            "3" + EN + "1 Estijan|publisher=[[FLLA]]|date=14 May 1763}}</ref>"),
    ),
    1672: dict(
        score=(6, 3),
        goals1="Volzhen {{Goal|8|52|75}}<br/>Kazhan {{Goal|33}}<br/>Tschev {{Goal|58|82}}",
        goals2="Calmar {{Goal|45|66}}<br/>Veldt {{Goal|70}}",
        ts_final=3,
        lead_old="4" + EN + "2 in the [[#Final|final]]",
        lead_new="6" + EN + "3 in the [[#Final|final]]",
        narration=(
            "The final was held at the Rivostan Grand Stadium on 2 July 1672 before an "
            "estimated crowd of 20,000. [[Emara]] took the lead early through Dragomir "
            "Volzhen, the tournament's leading scorer, and led 3" + EN + "1 by the hour "
            "through Ivor Kazhan and Milorad Tschev, with [[Lycroa]] replying through "
            "Tomas Calmar. Volzhen completed his hat-trick and Tschev added a second, and "
            "although Calmar struck again and Andrej Veldt pulled one back, Emara ran out "
            "6" + EN + "3 winners. The victory secured Emara's first title, won on home "
            "soil, and the original [[FLLA World Cup#The Andah Cup|Andah Cup]] was "
            "presented to the Emaran captain at the close of the match.<ref name="
            "\"heritage-final\">{{cite web|url=https://www.flla.org/heritage/world-cup/"
            "1672/final|title=The 1672 Ayuman Cup final: Emara 6" + EN + "3 Lycroa|"
            "publisher=[[FLLA]]|date=14 March 1763}}</ref>"),
    ),
    1684: dict(
        score=(5, 3),
        goals1="Veitz {{Goal|9|55}}<br/>Marold {{Goal|38|70}}<br/>Halden {{Goal|84}}",
        goals2="Feronti {{Goal|44|78}}<br/>Mazzo {{Goal|61}}",
        ts_final=2,
        lead_old="4" + EN + "2 in the [[#Final|final]]",
        lead_new="5" + EN + "3 in the [[#Final|final]]",
        narration=(
            "The final was held at the Shurqan Grand Stadium on 4 July 1684 before an "
            "estimated crowd of 30,000. [[Alzurian Union|Alzuria]] took the lead early "
            "through Konrad Veitz, the tournament's leading scorer, and led through "
            "Heinric Marold before [[Siana]] drew level with goals from Aldo Feronti and "
            "Renso Mazzo. Marold restored the lead with his second, Veitz struck again and "
            "Anders Halden added a fifth late on, with a second from Feronti giving Siana "
            "the last word in a 5" + EN + "3 win. The victory secured Alzuria's first "
            "title, won on home soil, and the original [[FLLA World Cup#The Andah Cup|"
            "Andah Cup]] was presented to the Alzurian captain at the close of the match."
            "<ref name=\"heritage-final\">{{cite web|url=https://www.flla.org/heritage/"
            "world-cup/1684/final|title=The 1684 Ayuman Cup final: Alzuria 5" + EN + "3 "
            "Siana|publisher=[[FLLA]]|date=11 June 1763}}</ref>"),
    ),
}

WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight",
         "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
         "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]

# goal-minute pools for added scorer events
NORMAL_MINS = [9, 17, 23, 31, 38, 44, 52, 58, 66, 74, 81, 88, 13, 27, 41, 63, 77, 85]
AET_MINS = [95, 103, 111, 119, 99, 107, 115]


def word(n):
    return WORDS[n] if 0 <= n < len(WORDS) else str(n)


def rhu(x):
    """Round half up to nearest int (avoids banker's rounding surprises)."""
    return int(x + 0.5)


def flag_of(cell):
    m = FLAG_RE.search(cell)
    return m.group(1).strip() if m else None


def fmt_gd(gd):
    if gd > 0:
        return "+%d" % gd
    if gd < 0:
        return MIN + str(-gd)
    return "0"


def seeded_rng(*parts):
    h = hashlib.md5("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return random.Random(int(h, 16))


# --- balanced-template helper ------------------------------------------------

def find_template(text, start):
    depth, i, n = 0, start, len(text)
    while i < n - 1:
        two = text[i:i + 2]
        if two == "{{":
            depth += 1
            i += 2
            continue
        if two == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return text[start:i]
            continue
        i += 1
    return None


# --- inflation of a single scoreline -----------------------------------------

def inflate_pair(gh, ga, f):
    """Return new (home, away) goals preserving the result (winner/draw)."""
    if gh == ga:                       # draw stays a draw, symmetric
        v = rhu(gh * f["GDF"])
        return v, v
    home_win = gh > ga
    w, l = (gh, ga) if home_win else (ga, gh)
    nw = max(rhu(w * f["GW"]), 1)
    nl = rhu(l * f["GL"])
    if nl >= nw:
        nl = nw - 1
    if nl < 0:
        nl = 0
    return (nw, nl) if home_win else (nl, nw)


def inflate_knockout(gh, ga, f):
    home_win = gh > ga
    w, l = (gh, ga) if home_win else (ga, gh)
    nw = max(rhu(w * f["KW"]), 1)
    nl = rhu(l * f["KL"])
    if nl >= nw:
        nl = nw - 1
    if nl < 0:
        nl = 0
    return (nw, nl) if home_win else (nl, nw)


# --- scorer-list redistribution ----------------------------------------------

def parse_scorers(goals_str):
    """[(surname, [minute,...]), ...] for a goals1/goals2 field value."""
    out = []
    s = goals_str.strip()
    if not s:
        return out
    for seg in re.split(r"<br\s*/?>", s):
        seg = seg.strip()
        if not seg:
            continue
        calls = GOAL_RE.findall(seg)
        name = seg.split("{{")[0].strip()
        mins = []
        for args in calls:
            for a in args.split("|"):
                a = a.strip()
                if a.isdigit():
                    mins.append(int(a))
        out.append((name, mins))
    return out


def render_scorers(scorers):
    parts = []
    for name, mins in scorers:
        if not mins:
            continue
        joined = "|".join(str(m) for m in sorted(mins))
        parts.append("%s {{Goal|%s}}" % (name, joined))
    return "<br/>".join(parts)


def redistribute(goals_str, new_total, aet, seedparts):
    scorers = [[n, list(m)] for n, m in parse_scorers(goals_str)]
    cur = sum(len(m) for _, m in scorers)
    if new_total == cur:
        return goals_str.strip(), scorers
    if new_total < cur:
        rem = cur - new_total
        for s in reversed(scorers):
            while rem > 0 and s[1]:
                s[1].pop()
                rem -= 1
        scorers = [s for s in scorers if s[1]]
        return render_scorers(scorers), scorers
    # need to add goals
    if not scorers:
        # no named scorers to attribute to; cannot grow this side
        return goals_str.strip(), scorers
    used = set(m for _, ms in scorers for m in ms)
    rng = seeded_rng(*seedparts)
    pool = [m for m in NORMAL_MINS if m not in used]
    if aet:
        pool += [m for m in AET_MINS if m not in used]
    rng.shuffle(pool)
    fallback = 50
    for i in range(new_total - cur):
        if pool:
            m = pool.pop()
        else:
            while fallback in used:
                fallback += 1
            m = fallback
        used.add(m)
        scorers[i % len(scorers)][1].append(m)
    return render_scorers(scorers), scorers


# --- table block helpers -----------------------------------------------------

def iter_table_blocks(lines):
    """Yield (start, end_inclusive, caption) for each {| ... |} table."""
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].lstrip().startswith("{|"):
            start = i
            cap = ""
            j = i + 1
            while j < n and not lines[j].lstrip().startswith("|}"):
                if lines[j].lstrip().startswith("|+"):
                    cap = lines[j].split("|+", 1)[1].strip()
                j += 1
            yield start, j, cap
            i = j + 1
        else:
            i += 1


def header_cols(line):
    """Column names for a '! a !! b !! c' header line."""
    return [c.strip().lstrip("!").strip() for c in line.split("!!")]


# --- per-page transform ------------------------------------------------------

class Problem(Exception):
    pass


def transform(year, text):
    f = FACT[year]
    lines = text.split("\r\n")
    repl = []           # (old_str, new_str) applied to full text, each unique
    issues = []

    # ---- 1) group matches: parse + new scores ------------------------------
    # group_letter -> list of dicts(home, away, ngh, nga)
    groups = {}
    for start, end, cap in iter_table_blocks(lines):
        m = re.match(r"Group\s+([A-Z])\s+matches", cap)
        if not m:
            continue
        gl = m.group(1)
        groups.setdefault(gl, [])
        for li in range(start, end):
            line = lines[li]
            s = line.strip()
            if not s.startswith("|") or s.startswith(("|+", "|-", "|}", "!")):
                continue
            if "||" not in line:
                continue
            cells = line.split("||")
            if len(cells) < 5:
                continue
            sm = SCORE_RE.search(cells[2])
            if not sm:
                continue
            home = flag_of(cells[1])
            away = flag_of(cells[3])
            gh, ga = int(sm.group(1)), int(sm.group(2))
            ngh, nga = inflate_pair(gh, ga, f)
            groups[gl].append(dict(home=home, away=away, ngh=ngh, nga=nga,
                                   ogh=gh, oga=ga))
            newcells = list(cells)
            newcells[2] = " %d%s%d " % (ngh, EN, nga)
            repl.append((line, "||".join(newcells)))

    # per-team group stats from NEW results, keyed by group then team
    def team_stats(matches, exclude_pair=None):
        st = {}

        def slot(t):
            return st.setdefault(t, dict(pld=0, w=0, d=0, l=0, gf=0, ga=0))
        for mt in matches:
            if exclude_pair and {mt["home"], mt["away"]} == exclude_pair:
                continue
            h, a = slot(mt["home"]), slot(mt["away"])
            gh, ga = mt["ngh"], mt["nga"]
            h["pld"] += 1
            a["pld"] += 1
            h["gf"] += gh
            h["ga"] += ga
            a["gf"] += ga
            a["ga"] += gh
            if gh > ga:
                h["w"] += 1
                a["l"] += 1
            elif gh < ga:
                a["w"] += 1
                h["l"] += 1
            else:
                h["d"] += 1
                a["d"] += 1
        for t, v in st.items():
            v["gd"] = v["gf"] - v["ga"]
            v["pts"] = 2 * v["w"] + v["d"]
        return st

    gstats = {gl: team_stats(ms) for gl, ms in groups.items()}

    # ---- 2) rewrite standings + derived ranking tables ---------------------
    def rewrite_standings(start, end, stats, assert_wdl):
        hi = None
        for li in range(start, end):
            s = lines[li].strip()
            if s.startswith("!") and "Team" in s and "GF" in s:
                hi = li
                break
        if hi is None:
            raise Problem("no header in standings table at %d (%d)" % (start, year))
        cols = header_cols(lines[hi])
        ix = {c: cols.index(c) for c in ("Team", "Pld", "W", "D", "L", "GF", "GA", "GD", "Pts")}
        for li in range(hi + 1, end):
            line = lines[li]
            s = line.strip()
            if not s.startswith("|") or s.startswith(("|+", "|-", "|}", "!")):
                continue
            if "||" not in line:
                continue
            cells = line.split("||")
            if len(cells) <= ix["GD"]:
                continue
            team = flag_of(cells[ix["Team"]])
            if team not in stats:
                issues.append("%d: standings team %r not in stats" % (year, team))
                continue
            v = stats[team]
            if assert_wdl:
                for col, key in (("Pld", "pld"), ("W", "w"), ("D", "d"),
                                 ("L", "l"), ("Pts", "pts")):
                    have = cells[ix[col]].strip()
                    if have != str(v[key]):
                        issues.append("%d: %s %s mismatch table=%s recomputed=%s"
                                      % (year, team, col, have, v[key]))
            newcells = list(cells)
            newcells[ix["GF"]] = " %d " % v["gf"]
            newcells[ix["GA"]] = " %d " % v["ga"]
            newcells[ix["GD"]] = " %s " % fmt_gd(v["gd"])
            repl.append((line, "||".join(newcells)))

    standings_spans = {}    # group letter -> (start,end)
    runnerup_span = None
    thirdplace_span = None
    for start, end, cap in iter_table_blocks(lines):
        m = re.match(r"Group\s+([A-Z])\s+standings", cap)
        if m:
            standings_spans[m.group(1)] = (start, end)
        elif "second-placed" in cap.lower():
            runnerup_span = (start, end)
        elif "third-placed" in cap.lower():
            thirdplace_span = (start, end)

    for gl, (start, end) in standings_spans.items():
        rewrite_standings(start, end, gstats[gl], assert_wdl=True)

    # bottom team of each group (last standings data row), for the 1680 rule
    def group_bottom(gl):
        start, end = standings_spans[gl]
        last = None
        for li in range(start, end):
            s = lines[li].strip()
            if s.startswith("|") and not s.startswith(("|+", "|-", "|}", "!")) and "||" in lines[li]:
                cells = lines[li].split("||")
                t = flag_of(cells[1])
                if t:
                    last = t
        return last

    # find which group a team belongs to
    team_group = {}
    for gl, st in gstats.items():
        for t in st:
            team_group[t] = gl

    if runnerup_span:
        # runner-up ranking: stats are the team's full group record
        flat = {t: v for gl in gstats for t, v in gstats[gl].items()}
        rewrite_standings(runnerup_span[0], runnerup_span[1], flat, assert_wdl=False)

    if thirdplace_span:
        adj = {}
        # rows are the three third-placed teams; for a 5-team group drop the
        # row team's match against that group's bottom side.
        start, end = thirdplace_span
        hi = next(li for li in range(start, end)
                  if lines[li].strip().startswith("!") and "Team" in lines[li])
        cols = header_cols(lines[hi])
        tix = cols.index("Team")
        for li in range(hi + 1, end):
            s = lines[li].strip()
            if not s.startswith("|") or s.startswith(("|+", "|-", "|}", "!")):
                continue
            if "||" not in lines[li]:
                continue
            t = flag_of(lines[li].split("||")[tix])
            if not t:
                continue
            gl = team_group[t]
            ms = groups[gl]
            n_teams = len(gstats[gl])
            if n_teams > 4:
                excl = {t, group_bottom(gl)}
                st = team_stats(ms, exclude_pair=excl)
            else:
                st = team_stats(ms)
            adj[t] = st[t]
        rewrite_standings(start, end, adj, assert_wdl=False)

    # ---- 3) football boxes (knockout) --------------------------------------
    # collect boxes in document order; last is the final
    boxes = []
    idx = 0
    while True:
        bi = text.find("{{Football box", idx)
        if bi == -1:
            break
        block = find_template(text, bi)
        idx = bi + 2
        if not block:
            continue
        boxes.append(block)

    box_results = {}     # frozenset(team1,team2) -> {team: goals}
    total_goals = 0

    def field_val(block, name):
        # [ \t]* (not \s*) so an empty field never swallows the next line
        m = re.search(r"\|[ \t]*" + name + r"[ \t]*=[ \t]*([^\r\n]*)", block)
        return m.group(1).strip() if m else ""

    for bn, block in enumerate(boxes):
        is_final = (bn == len(boxes) - 1)
        t1 = flag_of(field_val(block, "team1"))
        t2 = flag_of(field_val(block, "team2"))
        score_val = field_val(block, "score")
        sm = SCORE_RE.search(score_val)
        if not sm:
            raise Problem("%d: unparsable box score %r" % (year, score_val))
        g1, g2 = int(sm.group(1)), int(sm.group(2))
        aet = "{{Aet}}" in block or "{{aet}}" in block.lower()
        g1s = field_val(block, "goals1")
        g2s = field_val(block, "goals2")

        if is_final and year in FINALS:
            cfg = FINALS[year]
            n1, n2 = cfg["score"]
            new_g1s, new_g2s = cfg["goals1"], cfg["goals2"]
        elif is_final:
            # landmark final kept verbatim
            n1, n2, new_g1s, new_g2s = g1, g2, g1s, g2s
        else:
            n1, n2 = inflate_knockout(g1, g2, f)
            new_g1s, sc1 = redistribute(g1s, n1, aet, (year, t1, t2, "1", bn))
            new_g2s, sc2 = redistribute(g2s, n2, aet, (year, t1, t2, "2", bn))

        # verify scorer counts match the new score (skip 0 sides w/ no names)
        def count_goals(gs):
            return sum(len(m) for _, m in parse_scorers(gs))
        if new_g1s and count_goals(new_g1s) != n1:
            issues.append("%d: box %d goals1 count %d != %d" % (year, bn, count_goals(new_g1s), n1))
        if new_g2s and count_goals(new_g2s) != n2:
            issues.append("%d: box %d goals2 count %d != %d" % (year, bn, count_goals(new_g2s), n2))
        if n1 > 0 and not new_g1s:
            issues.append("%d: box %d scored %d but no goals1 scorers" % (year, bn, n1))
        if n2 > 0 and not new_g2s:
            issues.append("%d: box %d scored %d but no goals2 scorers" % (year, bn, n2))

        box_results[frozenset((t1, t2))] = {t1: n1, t2: n2}
        total_goals += n1 + n2

        # build replacement block
        nb = block
        new_score = "%d%s%d" % (n1, EN, n2) + (" {{Aet}}" if aet else "")
        nb = re.sub(r"(\|[ \t]*score[ \t]*=[ \t]*)[^\r\n]*", lambda mm: mm.group(1) + new_score, nb, count=1)
        nb = re.sub(r"(\|[ \t]*goals1[ \t]*=[ \t]*)[^\r\n]*", lambda mm: mm.group(1) + new_g1s, nb, count=1)
        nb = re.sub(r"(\|[ \t]*goals2[ \t]*=[ \t]*)[^\r\n]*", lambda mm: mm.group(1) + new_g2s, nb, count=1)
        if nb != block:
            repl.append((block, nb))

    total_goals += sum(mt["ngh"] + mt["nga"] for ms in groups.values() for mt in ms)

    # ---- 4) bracket numbers ------------------------------------------------
    bi = text.find("{{#invoke:RoundN")
    if bi != -1:
        bracket = find_template(text, bi)
        new_bracket_lines = []
        for bl in bracket.split("\r\n"):
            mm = re.match(
                r"^(\| \| \{\{Flagicon\|)([^}]+)(\}\}[^|]*\| )(\d+)( \| \{\{Flagicon\|)([^}]+)(\}\}[^|]*\| )(\d+)\s*$",
                bl)
            if not mm:
                new_bracket_lines.append(bl)
                continue
            lk, rk = mm.group(2).strip(), mm.group(6).strip()
            res = box_results.get(frozenset((lk, rk)))
            if not res:
                issues.append("%d: bracket pair %s/%s has no box" % (year, lk, rk))
                new_bracket_lines.append(bl)
                continue
            nl, nr = res[lk], res[rk]
            new_bracket_lines.append(
                "%s%s%s%d%s%s%s%d" % (mm.group(1), mm.group(2), mm.group(3), nl,
                                      mm.group(5), mm.group(6), mm.group(7), nr))
        new_bracket = "\r\n".join(new_bracket_lines)
        if new_bracket != bracket:
            repl.append((bracket, new_bracket))

    # ---- 5) tier list, infobox, prose --------------------------------------
    # parse tier list: between '===Goalscorers===' and next '==='
    gi = text.find("===Goalscorers===")
    ge = text.find("===", gi + 3)
    # the heading itself is '===Goalscorers===' so search beyond it
    ge = text.find("\r\n===", gi + 3)
    tier_region = text[gi:ge]
    tiers = []   # (count, [bullet_line, ...]) preserving order
    cur_count = None
    cur_bullets = []
    for line in tier_region.split("\r\n"):
        hm = re.match(r"^'''(\d+) goals?'''$", line.strip())
        if hm:
            if cur_count is not None:
                tiers.append((cur_count, cur_bullets))
            cur_count = int(hm.group(1))
            cur_bullets = []
        elif line.strip().startswith("*") and cur_count is not None:
            cur_bullets.append(line)
    if cur_count is not None:
        tiers.append((cur_count, cur_bullets))

    # knockout goals per player surname (to keep tier totals >= attested)
    ko_goals = {}
    for block in boxes:
        for fld in ("goals1", "goals2"):
            for name, mins in parse_scorers(field_val(block, fld)):
                ko_goals[name] = ko_goals.get(name, 0) + len(mins)
    # final goals already inside boxes (final box updated above uses cfg names)
    if year in FINALS:
        cfg = FINALS[year]
        for fld in ("goals1", "goals2"):
            for name, mins in parse_scorers(cfg[fld]):
                # cfg names already counted via boxes[-1]'s original; recount cleanly
                pass

    # scale tier counts; bullets carry full names whose surname is the last token
    scaled = []      # (new_count, bullets)
    for count, bullets in tiers:
        nc = max(1, rhu(count * f["TIER"]))
        # ensure not below any listed player's knockout tally
        for b in bullets:
            nm = re.sub(r"\{\{[^}]*\}\}", "", b)
            nm = re.sub(r"\(\[\[[^\]]*\]\]\)", "", nm)
            nm = nm.replace("*", "").strip()
            surname = nm.split()[-1] if nm.split() else ""
            nc = max(nc, ko_goals.get(surname, 0))
        scaled.append([nc, bullets])
    # keep strictly descending so the tiers stay ordered after scaling
    for i in range(1, len(scaled)):
        if scaled[i][0] >= scaled[i - 1][0]:
            scaled[i][0] = scaled[i - 1][0] - 1
        if scaled[i][0] < 1:
            scaled[i][0] = 1
    top_count = scaled[0][0] if scaled else 0

    # render new tier region
    out = ["===Goalscorers===", ""]
    # keep the prose paragraph (first non-empty, non-bullet, non-header block)
    prose = ""
    for line in tier_region.split("\r\n"):
        st = line.strip()
        if st.startswith("A total of"):
            prose = line
            break
    # update prose numbers
    matches_played = sum(len(ms) for ms in groups.values()) + len(boxes)
    avg = total_goals / matches_played if matches_played else 0
    ts_final = None
    if year in FINALS:
        ts_final = FINALS[year]["ts_final"]
    new_prose = prose
    new_prose = re.sub(
        r"A total of \d+ goals were scored in (\d+) matches, an average of [\d.]+ per match",
        "A total of %d goals were scored in \\1 matches, an average of %.2f per match" % (total_goals, avg),
        new_prose, count=1)
    new_prose = re.sub(r"who scored \w+ goals across the tournament",
                       "who scored %s goals across the tournament" % word(top_count),
                       new_prose, count=1)
    if ts_final is not None:
        new_prose = re.sub(r"including \w+ in the final",
                           "including %s in the final" % word(ts_final),
                           new_prose, count=1)
    out.append(new_prose)
    out.append("")
    for nc, bullets in scaled:
        out.append("'''%d goals'''" % nc)
        out.extend(bullets)
        out.append("")
    new_tier_region = "\r\n".join(out).rstrip("\r\n")
    repl.append((tier_region.rstrip("\r\n"), new_tier_region))

    # infobox: Matches played stays; Goals scored + Top scorer updated
    repl_infobox = []
    for line in lines:
        gm = re.match(r"^\| Goals scored \|\| \d+ \([\d.]+ per match\)$", line)
        if gm:
            repl_infobox.append((line, "| Goals scored || %d (%.2f per match)" % (total_goals, avg)))
        tm = re.match(r"^(\| Top scorer \|\| .*?)\(\d+ goals?\)$", line)
        if tm:
            repl_infobox.append((line, "%s(%d goals)" % (tm.group(1), top_count)))
    repl.extend(repl_infobox)

    # ---- 6) finals: lead sentence + narration ------------------------------
    if year in FINALS:
        cfg = FINALS[year]
        # lead score
        lead_done = False
        for i, line in enumerate(lines):
            if cfg["lead_old"] in line:
                repl.append((line, line.replace(cfg["lead_old"], cfg["lead_new"], 1)))
                lead_done = True
                break
        if not lead_done:
            issues.append("%d: lead final score phrase not found" % year)
        # narration paragraph
        narr_done = False
        for line in lines:
            if line.startswith("The final was held at"):
                repl.append((line, cfg["narration"]))
                narr_done = True
                break
        if not narr_done:
            issues.append("%d: narration line not found" % year)

    # ---- apply replacements -------------------------------------------------
    new_text = text
    for old, new in repl:
        if old == new:
            continue
        c = new_text.count(old)
        if c != 1:
            issues.append("%d: replacement not unique (%d) for %r..." % (year, c, old[:60]))
            continue
        new_text = new_text.replace(old, new, 1)

    if EM in new_text and EM not in text:
        issues.append("%d: introduced an em-dash" % year)

    # structural integrity: these markers must survive unchanged in count
    for marker in ("{{Football box", "| stadium =", "| referee =",
                   "| attendance =", "| date =", "| team1 =", "| team2 =",
                   "| score =", "{| class", "|+ Group", "{{Flagicon"):
        if new_text.count(marker) != text.count(marker):
            issues.append("%d: marker count changed for %r (%d -> %d)"
                          % (year, marker, text.count(marker), new_text.count(marker)))

    stats = dict(matches=matches_played, goals=total_goals, avg=avg,
                 top=top_count,
                 maxline=max(("%d%s%d" % (mt["ngh"], EN, mt["nga"])
                              for ms in groups.values() for mt in ms),
                             key=lambda s: max(int(x) for x in s.split(EN)),
                             default=""))
    return new_text, issues, stats


# --- driver ------------------------------------------------------------------

def page_path(year):
    return os.path.join(PAGES, "%d_Ayuman_Cup.wiki" % year)


def backup_path(year):
    return os.path.join(BACKUP, "%d_Ayuman_Cup.wiki" % year)


def read_raw(path):
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8")


def write_raw(path, text):
    with open(path, "wb") as fh:
        fh.write(text.encode("utf-8"))


def ensure_backup(year):
    if not os.path.isdir(BACKUP):
        os.makedirs(BACKUP)
    bp = backup_path(year)
    if not os.path.exists(bp):
        write_raw(bp, read_raw(page_path(year)))


def source_text(year):
    """Pristine text: the backup if present, else the live page."""
    bp = backup_path(year)
    return read_raw(bp) if os.path.exists(bp) else read_raw(page_path(year))


def restore():
    if not os.path.isdir(BACKUP):
        print("no backups to restore")
        return 0
    n = 0
    for year in YEARS:
        bp = backup_path(year)
        if os.path.exists(bp):
            write_raw(page_path(year), read_raw(bp))
            n += 1
    print("restored %d page(s) from backup" % n)
    return 0


def run(mode):
    all_issues = []
    for year in YEARS:
        src = source_text(year)
        old_goals = re.search(r"\| Goals scored \|\| (\d+) \(([\d.]+) per match\)", src)
        new_text, issues, st = transform(year, src)
        all_issues += issues
        og = old_goals.group(1) if old_goals else "?"
        oa = old_goals.group(2) if old_goals else "?"
        flag = "  !! %d issue(s)" % len(issues) if issues else ""
        print("%d: goals %s->%d  avg %s->%.2f  top->%d  biggest group win %s%s"
              % (year, og, st["goals"], oa, st["avg"], st["top"], st["maxline"], flag))
        for it in issues:
            print("      - " + it)
        if mode == "apply" and not issues:
            ensure_backup(year)
            write_raw(page_path(year), new_text)
        if mode == "verify":
            live = read_raw(page_path(year))
            if live != new_text:
                print("      - VERIFY: live page differs from re-derived output")

    if all_issues:
        print("\n%d issue(s) total -- not safe to apply" % len(all_issues))
        return 1
    if mode == "apply":
        print("\napplied to %d pages (backups in %s)" % (len(YEARS), BACKUP))
    elif mode == "dry":
        print("\ndry run clean -- rerun with 'apply' to write")
    else:
        print("\nverify clean")
    return 0


def main(argv):
    if "--restore" in argv:
        return restore()
    mode = "dry"
    for a in argv:
        if a in ("dry", "apply", "verify"):
            mode = a
    return run(mode)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
