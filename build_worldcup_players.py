#!/usr/bin/env python3
"""Build a database of FLLA World Cup players from the wiki pages.

One-off data script (stdlib only, no network). It reads the local World Cup
edition pages under ``pages/Main/`` and aggregates every player our sources
name into a single per-player table, recording:

  * the team(s) they played for,
  * which World Cups they appear in,
  * their goals (total + per edition), and
  * any individual awards won.

Sources, in order of reliability:
  1. "Top individual goalscorers" tables (editions 1712-1764) - authoritative goals.
  2. Match goal events inside ``{{Football box}}`` templates - recovers every
     other scorer (surname only) and goals for older editions.
  3. Award rows (infobox + "Tournament awards" table, 1700-1764) - top scorer
     (Marskval), best player (Vairan Ball), best young player, best goalkeeper.
  4. The full 1704 squad page - the only edition with complete rosters; gives
     team + playing position for 288 players.

Output: ``data/FLLA_World_Cup_Players.csv`` (one row per player), which is then
uploaded to Google Drive as a Sheet.

Limitations are inherent to the source data and flagged in the Notes column:
goals only exist where recorded; "World Cups" means editions where the player is
named (squads aren't recorded except 1704); name matching is string-based.

Usage:  python build_worldcup_players.py
"""

import csv
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, "pages", "Main")
# Wiki-only base. The career-enriched primary file (FLLA_World_Cup_Players.csv)
# is produced from this by generate_player_careers.py.
OUT_CSV = os.path.join(HERE, "data", "FLLA_World_Cup_Players_wiki.csv")
SQUADS_1704 = os.path.join(PAGES, "1704_FLLA_World_Cup_squads.wiki")

# --- wikitext helpers --------------------------------------------------------

LINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]")
FLAG_RE = re.compile(r"\{\{\s*[Ff]lag(?:icon|country)?\s*\|\s*([^|}]+?)\s*(?:\|[^}]*)?\}\}")
REF_RE = re.compile(r"<ref[^>]*?/>|<ref[^>]*?>.*?</ref>", re.DOTALL)
GOAL_RE = re.compile(r"\{\{\s*[Gg]oal\b([^}]*)\}\}")
GOALS_COUNT_RE = re.compile(r"\((\d+)\s*goals?\)", re.IGNORECASE)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def strip_refs(s):
    return REF_RE.sub("", s)


def first_link(s):
    m = LINK_RE.search(s)
    return m.group(1).strip() if m else ""


def team_from_cell(s):
    """Team is the explicit [[link]] if present, else the {{Flagicon|..}} arg."""
    link = first_link(s)
    if link:
        return link.strip()
    m = FLAG_RE.search(s)
    return m.group(1).strip() if m else ""


def player_name(value):
    """Extract a clean player name from an infobox/table/award cell value."""
    v = strip_refs(value)
    v = FLAG_RE.sub("", v)
    v = GOALS_COUNT_RE.sub("", v)            # drop "(7 goals)"
    v = re.sub(r"\(\s*\[\[[^\]]*\]\]\s*\)", "", v)   # drop "([[Team]])"
    v = re.sub(r"\([^)]*\)", "", v)          # drop "(c)" / other parentheticals
    v = LINK_RE.sub("", v)                    # drop any remaining links
    v = re.sub(r"align\s*=\s*\"[^\"]*\"", "", v, flags=re.IGNORECASE)
    v = re.sub(r"^\s*[A-Za-z]+\d?\s*=\s*", "", v)   # leaked "goals2 = " prefix
    v = re.sub(r"'''?", "", v)               # bold/italic markers
    v = v.replace("|", " ")
    v = re.sub(r"\s+", " ", v).strip()
    return v


def award_goals(value):
    m = GOALS_COUNT_RE.search(value)
    return int(m.group(1)) if m else None


def field(block, name):
    """Return the single-line value of ``| name = ...`` in a template block."""
    m = re.search(r"\|\s*" + name + r"\s*=\s*(.*)", block)
    return m.group(1).strip() if m else ""


# Field tokens that should never appear inside a goals value (mark a leak from
# a neighbouring Football box field whose leading "|" was omitted).
FIELD_BREAK_RE = re.compile(
    r"\b(?:team[12]|score|stadium|attendance|referee|date|time|report|location)\s*=")


def classify_award(label):
    l = label.lower()
    if "marskval" in l or "top scorer" in l:
        return "Top scorer (Marskval)"
    if "vairan" in l or "best player" in l:
        return "Best player (Vairan Ball)"
    if "young" in l:
        return "Best young player"
    if "bastion" in l or "goalkeeper" in l:
        return "Best goalkeeper (Bastion)"
    return None


def find_template(text, start):
    """Given an index of '{{', return the balanced template text (or None)."""
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


# --- per-edition assembly ----------------------------------------------------

def _key(name, team):
    return (name.lower(), team.lower())


def build_edition(year, text):
    """Return {(name_lower, team_lower): entry} for one edition.

    entry = {name, team, goals, position, surname_only(bool), awards(set)}
    """
    entries = {}

    def get_or_create(name, team, surname_only=False):
        k = _key(name, team)
        e = entries.get(k)
        if e is None:
            e = {"name": name, "team": team, "goals": 0,
                 "position": "", "surname_only": surname_only, "awards": set()}
            entries[k] = e
        return e

    def rekey(old_entry, new_name):
        """Promote a surname-only entry to a full name (changes the dict key)."""
        del entries[_key(old_entry["name"], old_entry["team"])]
        old_entry["name"] = new_name
        old_entry["surname_only"] = False
        entries[_key(new_name, old_entry["team"])] = old_entry

    def fullname_by_surname(surname, team):
        for e in entries.values():
            if e["team"].lower() != team.lower():
                continue
            toks = e["name"].split()
            if len(toks) > 1 and toks[-1].lower() == surname.lower():
                return e
        return None

    def surnameonly_by_lasttoken(fullname, team):
        last = fullname.split()[-1].lower()
        for e in entries.values():
            if e["surname_only"] and e["team"].lower() == team.lower() \
                    and e["name"].lower() == last:
                return e
        return None

    # 1) Top individual goalscorers table (authoritative goals) ---------------
    gi = text.find("Top individual goalscorers")
    if gi != -1:
        end = text.find("|}", gi)
        block = text[gi:end if end != -1 else len(text)]
        for line in block.splitlines():
            line = line.strip()
            if not line.startswith("|") or line.startswith(("|+", "|-")):
                continue
            if "||" not in line:
                continue
            parts = line.split("||")
            if len(parts) < 4:
                continue
            rank = parts[0].lstrip("|").strip()
            if not re.match(r"^\d+$", rank):
                continue
            name = player_name(parts[1])
            team = team_from_cell(parts[2])
            gm = re.search(r"\d+", strip_refs(parts[-1]))
            goals = int(gm.group()) if gm else 0
            if not name or not team:
                continue
            e = get_or_create(name, team)
            e["goals"] = max(e["goals"], goals)

    # 2) Match goal events (every scorer, surname only) -----------------------
    matchcounts = defaultdict(int)   # (surname_lower, team) -> goals
    matchnames = {}                   # surname_lower -> display surname
    idx = 0
    while True:
        idx = text.find("{{Football box", idx)
        if idx == -1:
            break
        block = find_template(text, idx)
        idx += 2
        if not block:
            continue
        team1 = first_link(field(block, "team1"))
        team2 = first_link(field(block, "team2"))
        g1 = field(block, "goals1")
        g2 = field(block, "goals2")
        # Repair a source quirk: some boxes omit the leading "|" before
        # "goals2 =", leaking the away scorers into the goals1 value.
        lm = re.search(r"goals2\s*=\s*", g1)
        if lm:
            leaked = g1[lm.end():]
            g1 = g1[:lm.start()]
            g2 = (g2 + "<br/>" + leaked) if g2.strip() else leaked
        for team, gstr in ((team1, g1), (team2, g2)):
            if not team:
                continue
            for surname, count in parse_goal_events(gstr):
                matchcounts[(surname.lower(), team)] += count
                matchnames[surname.lower()] = surname

    for (surname_l, team), count in matchcounts.items():
        surname = matchnames[surname_l]
        if fullname_by_surname(surname, team):
            continue   # already a named (table) player; that goal tally is authoritative
        e = get_or_create(surname, team, surname_only=True)
        e["goals"] = max(e["goals"], count)

    # 3) Awards (infobox rows + Tournament awards table) ----------------------
    award_rows = []
    for m in re.finditer(
            r"^\|\s*(Top scorer|Best player|Best young player|Best goalkeeper)\s*\|\|\s*(.*)$",
            text, re.MULTILINE):
        award_rows.append((m.group(1), m.group(2)))
    ai = text.find("Tournament awards")
    if ai != -1:
        end = text.find("|}", ai)
        block = text[ai:end if end != -1 else len(text)]
        for line in block.splitlines():
            line = line.strip()
            if not line.startswith("|") or line.startswith(("|+", "|-", "!")):
                continue
            if "||" not in line:
                continue
            parts = line.split("||")
            award_rows.append((parts[0].lstrip("|").strip(), parts[1]))

    for label, value in award_rows:
        award = classify_award(label)
        if not award:
            continue
        name = player_name(value)
        team = team_from_cell(value)
        if not name or not team or name.lower() == team.lower():
            continue   # team-only award (fair play / leading nation)
        e = entries.get(_key(name, team))
        if e is None:
            su = surnameonly_by_lasttoken(name, team)
            if su is not None:
                rekey(su, name)
                e = su
            else:
                e = get_or_create(name, team)
        e["awards"].add(award)
        g = award_goals(value)
        if g:
            e["goals"] = max(e["goals"], g)

    return entries


def parse_goal_events(goals_str):
    """Yield (surname, goal_count) for one ``goals1=/goals2=`` field value."""
    out = []
    if not goals_str.strip():
        return out
    # Drop anything after a leaked neighbouring field (e.g. "stadium = ...").
    fb = FIELD_BREAK_RE.search(goals_str)
    if fb:
        goals_str = goals_str[:fb.start()]
    for seg in re.split(r"<br\s*/?>", goals_str):
        calls = GOAL_RE.findall(seg)
        if not calls:
            continue
        name = player_name(seg.split("{{")[0])
        if not name or "=" in name:
            continue
        count = 0
        for args in calls:
            for a in args.split("|"):
                if re.match(r"^\d+(?:\+\d+)?$", a.strip()):
                    count += 1
        out.append((name, count or len(calls)))
    return out


def parse_1704_squads(text):
    """Yield (player, team, position) from the 1704 squads page."""
    out = []
    team = None
    in_table = False
    for line in text.splitlines():
        s = line.strip()
        h = re.match(r"^===\s*([^=].*?)\s*===$", s)
        if h:
            team = h.group(1).strip()
            in_table = False
            continue
        if s.startswith("{|"):
            in_table = True
            continue
        if s.startswith("|}"):
            in_table = False
            continue
        if not (in_table and team):
            continue
        if not s.startswith("|") or s.startswith(("|+", "|-")) or s.startswith("!"):
            continue
        if "||" not in s:
            continue
        parts = s.split("||")
        if len(parts) < 3:
            continue
        pos = parts[1].strip()
        name = player_name(parts[2])
        if name and re.match(r"^[A-Za-z]{2,3}$", pos):
            out.append((name, team, pos))
    return out


# --- global aggregation ------------------------------------------------------

def main():
    edition_files = []
    for fn in sorted(os.listdir(PAGES)):
        m = re.match(r"^(\d{4})_FLLA_World_Cup\.wiki$", fn)
        if m:
            edition_files.append((int(m.group(1)), os.path.join(PAGES, fn)))

    glob = {}   # (name_lower, team_lower[, year]) -> record

    def record(name, team, key=None):
        k = key if key is not None else _key(name, team)
        r = glob.get(k)
        if r is None:
            r = {"name": name, "teams": set(), "positions": set(),
                 "years": set(), "goals_by_year": {}, "awards": set(),
                 "notes": set()}
            glob[k] = r
        r["teams"].add(team)
        return r

    editions_parsed = 0
    for year, path in edition_files:
        entries = build_edition(year, read(path))
        if not entries:
            continue
        editions_parsed += 1
        for e in entries.values():
            # A bare surname is not a stable identity across editions, so keep
            # surname-only scorers as a distinct record per edition; full names
            # aggregate across editions as before.
            if e["surname_only"]:
                key = (e["name"].lower(), e["team"].lower(), year)
                r = record(e["name"], e["team"], key=key)
            else:
                r = record(e["name"], e["team"])
            r["years"].add(year)
            r["goals_by_year"][year] = e["goals"]
            if e["position"]:
                r["positions"].add(e["position"])
            for a in e["awards"]:
                r["awards"].add((year, a))
            if e["surname_only"]:
                r["notes"].add("name from match data (surname only)")

    # 1704 squad: team + position, reconciled with scorers/awards
    squad_players = parse_1704_squads(read(SQUADS_1704))
    squad_count = len(squad_players)
    for name, team, pos in squad_players:
        # try exact, else fold a surname-only 1704 scorer into this full name
        r = glob.get(_key(name, team))
        if r is None:
            last = name.split()[-1].lower()
            folded = None
            for k, rr in list(glob.items()):
                if team in rr["teams"] and rr["name"].lower() == last \
                        and 1704 in rr["years"] \
                        and any("surname only" in n for n in rr["notes"]):
                    folded = (k, rr)
                    break
            if folded:
                k, rr = folded
                del glob[k]
                rr["name"] = name
                rr["notes"].discard("name from match data (surname only)")
                glob[_key(name, team)] = rr
                r = rr
            else:
                r = record(name, team)
                r["years"].add(1704)
                r["goals_by_year"].setdefault(1704, 0)
        r["positions"].add(pos)

    # Conservative cross-edition consolidation of surname-only records into a
    # unique full-name record on the same team -- but only when it stays a
    # plausible career: the merged appearances must span <= MAX_CAREER_SPAN
    # years. Surname appearances outside that window (e.g. the same surname
    # decades apart) are left as separate single-edition records.
    MAX_CAREER_SPAN = 12   # ~4 editions; matches the career generator's ceiling
    consolidated = 0
    sn_keys = [k for k, r in glob.items()
               if len(r["name"].split()) == 1
               and any("surname only" in n for n in r["notes"])]
    sn_keys.sort(key=lambda k: k[2] if len(k) > 2 else 0)   # oldest first
    for k in sn_keys:
        r = glob.get(k)
        if r is None:
            continue
        sn = r["name"].lower()
        cands = [kk for kk, rr in glob.items()
                 if kk != k and (r["teams"] & rr["teams"])
                 and len(rr["name"].split()) > 1
                 and rr["name"].split()[-1].lower() == sn]
        if len(cands) != 1:
            continue
        tgt = glob[cands[0]]
        merged_years = tgt["years"] | r["years"]
        if max(merged_years) - min(merged_years) > MAX_CAREER_SPAN:
            continue   # would be an implausibly long career: leave separate
        tgt["years"] |= r["years"]
        tgt["positions"] |= r["positions"]
        tgt["awards"] |= r["awards"]
        tgt["teams"] |= r["teams"]
        for y, g in r["goals_by_year"].items():
            tgt["goals_by_year"][y] = max(tgt["goals_by_year"].get(y, 0), g)
        tgt["notes"].add("includes surname-only match data")
        del glob[k]
        consolidated += 1

    rows = []
    split_records = 0
    for r in glob.values():
        # If a record's appearances span more than a plausible career, the same
        # name is being shared across eras (a name reused by the wiki, or a
        # surname collision). Split it into separate people, one per cluster of
        # years that fits inside MAX_CAREER_SPAN.
        clusters = []
        for y in sorted(r["years"]):
            if clusters and y - clusters[-1][0] <= MAX_CAREER_SPAN:
                clusters[-1].append(y)
            else:
                clusters.append([y])
        multi = len(clusters) > 1
        if multi:
            split_records += 1
        for cyears in clusters:
            cyset = set(cyears)
            gb = {y: g for y, g in r["goals_by_year"].items() if y in cyset}
            gby = "; ".join(f"{y}: {g}" for y, g in sorted(gb.items()) if g)
            awards = "; ".join(f"{y} {a}" for y, a in sorted(r["awards"]) if y in cyset)
            positions = sorted(r["positions"]) if (not multi or 1704 in cyset) else []
            notes = set(r["notes"])
            if multi:
                notes.add("name shared across eras (split)")
            rows.append({
                "Player": r["name"],
                "Team(s)": "; ".join(sorted(r["teams"])),
                "Position": "; ".join(positions),
                "World Cups": ", ".join(str(y) for y in cyears),
                "Total goals": sum(gb.values()),
                "Goals by World Cup": gby,
                "Awards": awards,
                "Notes": "; ".join(sorted(notes)),
            })

    rows.sort(key=lambda x: (-x["Total goals"], x["Player"].lower()))

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    cols = ["Player", "Team(s)", "Position", "World Cups",
            "Total goals", "Goals by World Cup", "Awards", "Notes"]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    scorers = sum(1 for r in rows if r["Total goals"] > 0)
    print(f"Editions parsed:         {editions_parsed}")
    print(f"1704 squad players:      {squad_count}")
    print(f"Cross-edition merges:    {consolidated}")
    print(f"Shared-name splits:      {split_records}")
    print(f"Total players (rows):    {len(rows)}")
    print(f"  with recorded goals:   {scorers}")
    print(f"Wrote {OUT_CSV}")


if __name__ == "__main__":
    sys.exit(main())
