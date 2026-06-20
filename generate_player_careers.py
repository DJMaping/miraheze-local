#!/usr/bin/env python3
"""Give named FLLA World Cup players realistic multi-edition careers.

The wiki names most players in only one edition, so the base database
(``data/FLLA_World_Cup_Players_wiki.csv``, produced by build_worldcup_players.py)
has almost everyone in a single World Cup. This script generates a persistent,
hand-editable *careers layer* (``data/player_careers.csv``) and merges it onto
the base to produce the enriched primary file
``data/FLLA_World_Cup_Players.csv``.

Design (database-only; the wiki is never touched):
  * Eligible = full-name players (>= 2 tokens) that are NOT surname-only.
  * Career length drawn from a realistic spread: ~45% 1 WC, 30% 2, 18% 3, 7% 4+.
  * A career is a window of consecutive editions for the player's own nation,
    covering their attested year(s).
  * Attested years keep their real goals. Added years get modest goals on a
    career arc, capped below both the player's own peak and that edition's real
    top scorer, so no goalscorer table is ever contradicted.
  * Generation is deterministic (RNG seeded from a stable hash of name+team).
    If data/player_careers.csv already exists it is loaded, not regenerated, so
    it is a stable curated artifact you can edit by hand.

Usage:  python generate_player_careers.py
"""

import csv
import hashlib
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_CSV = os.path.join(HERE, "data", "FLLA_World_Cup_Players_wiki.csv")
CAREERS_CSV = os.path.join(HERE, "data", "player_careers.csv")
OUT_CSV = os.path.join(HERE, "data", "FLLA_World_Cup_Players.csv")

COLS = ["Player", "Team(s)", "Position", "World Cups",
        "Total goals", "Goals by World Cup", "Awards", "Notes"]

# Career-length distribution (cumulative thresholds) and a realistic ceiling.
LENGTH_CDF = [(0.45, 1), (0.75, 2), (0.93, 3), (1.01, 4)]
MAX_LEN = 4   # at most 4 editions (~16 years); longer is unrealistic


def seeded_rng(*parts):
    h = hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()
    return random.Random(int(h, 16))


def parse_years(s):
    return [int(y) for y in re.findall(r"\d{4}", s or "")]


def parse_goals_by_year(s):
    return {int(y): int(g) for y, g in re.findall(r"(\d{4})\s*:\s*(\d+)", s or "")}


def is_surname_only(notes):
    return "surname only" in (notes or "")


def draw_length(rng):
    r = rng.random()
    for thresh, length in LENGTH_CDF:
        if r < thresh:
            return length
    return 4


def main():
    with open(BASE_CSV, encoding="utf-8", newline="") as fh:
        base = list(csv.DictReader(fh))

    # Edition timeline and each edition's top attested goal tally.
    edition_top = {}
    all_years = set()
    for row in base:
        for y, g in parse_goals_by_year(row["Goals by World Cup"]).items():
            edition_top[y] = max(edition_top.get(y, 0), g)
        all_years.update(parse_years(row["World Cups"]))
    timeline = sorted(all_years)
    idx_of = {y: i for i, y in enumerate(timeline)}

    # --- careers layer: load if present, else generate ----------------------
    if os.path.exists(CAREERS_CSV):
        careers = {}
        with open(CAREERS_CSV, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                career = parse_goals_by_year(row["Career"])
                careers[(row["Player"], row["Team"])] = career
        generated = False
    else:
        careers = {}
        for row in base:
            name, team = row["Player"], row["Team(s)"]
            if len(name.split()) < 2 or is_surname_only(row["Notes"]):
                continue
            attested = parse_years(row["World Cups"])
            if not attested:
                continue
            goals_by_year = parse_goals_by_year(row["Goals by World Cup"])
            rng = seeded_rng(name, team)

            min_i, max_i = idx_of[min(attested)], idx_of[max(attested)]
            existing_span = max_i - min_i + 1
            if existing_span > MAX_LEN:
                continue   # anomalous wide span (e.g. bad surname merge): leave as-is
            length = min(max(draw_length(rng), existing_span), MAX_LEN)

            slack = length - existing_span
            offset = rng.randint(0, slack) if slack > 0 else 0
            start = min_i - offset
            start = max(0, min(start, len(timeline) - length))
            window = [timeline[i] for i in range(start, start + length)]

            if len(window) <= len(set(attested)):
                continue   # no extra editions -> stays single

            # Career arc: peak = best attested year.
            peak_year = max(attested, key=lambda y: goals_by_year.get(y, 0))
            peak_goals = goals_by_year.get(peak_year, 0)
            peak_i = idx_of[peak_year]

            career = {}
            for y in window:
                if y in goals_by_year or y in attested:
                    career[y] = goals_by_year.get(y, 0)
                    continue
                d = abs(idx_of[y] - peak_i)
                if peak_goals == 0:
                    g = 1 if rng.random() < 0.08 else 0
                else:
                    g = int(peak_goals * (0.5 ** d) + rng.random())
                hard_cap = max(edition_top.get(y, 1) - 1, 0)
                own_cap = peak_goals if peak_goals > 0 else 1
                career[y] = max(0, min(g, own_cap, hard_cap))
            careers[(name, team)] = career

        with open(CAREERS_CSV, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Player", "Team", "Position", "Career"])
            for row in base:
                key = (row["Player"], row["Team(s)"])
                if key in careers:
                    career = careers[key]
                    spec = "; ".join(f"{y}:{career[y]}" for y in sorted(career))
                    w.writerow([row["Player"], row["Team(s)"], row["Position"], spec])
        generated = True

    # --- merge careers onto base -> enriched primary file -------------------
    enriched = []
    for row in base:
        key = (row["Player"], row["Team(s)"])
        gby = parse_goals_by_year(row["Goals by World Cup"])
        years = set(parse_years(row["World Cups"]))
        notes = row["Notes"]

        career = careers.get(key)
        if career:
            added = False
            for y, g in career.items():
                if y not in years:
                    years.add(y)
                    added = True
                if y not in gby and g:
                    gby[y] = g
            if added:
                notes = (notes + "; " if notes else "") + "career spans generated"

        total = sum(gby.values())
        out = dict(row)
        out["World Cups"] = ", ".join(str(y) for y in sorted(years))
        out["Total goals"] = total
        out["Goals by World Cup"] = "; ".join(
            f"{y}: {gby[y]}" for y in sorted(gby) if gby[y])
        out["Notes"] = notes
        enriched.append(out)

    enriched.sort(key=lambda x: (-int(x["Total goals"]), x["Player"].lower()))

    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(enriched)

    # --- report -------------------------------------------------------------
    def bucket(n):
        return "4+" if n >= 4 else str(n)
    dist = {"1": 0, "2": 0, "3": 0, "4+": 0}
    extended = 0
    for row in enriched:
        n = len(parse_years(row["World Cups"]))
        dist[bucket(n)] += 1
        if "career spans generated" in row["Notes"]:
            extended += 1

    print(f"{'generated' if generated else 'loaded'} careers for "
          f"{len(careers)} players; {extended} rows extended")
    print(f"World Cups per player: "
          f"1={dist['1']}  2={dist['2']}  3={dist['3']}  4+={dist['4+']}  "
          f"(of {len(enriched)} total)")
    print(f"Wrote {CAREERS_CSV}")
    print(f"Wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
