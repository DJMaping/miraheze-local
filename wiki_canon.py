#!/usr/bin/env python3
"""
wiki_canon.py - canon that already exists on the wiki and should drive the model.

Two sources, both DJ's, both previously ignored by the trade model:

  FINANCIAL CENTRES  pages/Main/Global_Financial_Centres_Index.wiki ranks the
    world's financial centres. Tirna (Raledria) leads at 766, Pha Hii second,
    Rivostan (Emara) third. A country hosting a top centre earns far more from
    finance than its income alone implies, which is the whole point of the page.
    Without this the model set every country's finance share from GDP per
    capita, so a published ranking and the trade figures could disagree.

  ALLIANCE BLOCS  the Janus 'Great Importance' sheet's Allineces column, for the
    26 countries it covers: ADT, BDT, DAC, RSDA, RRO, SHI, APA, MPU, NMCC,
    AANS, AFTZ. Members of the same bloc trade more with each other, as they do
    on Earth: intra-EU trade exceeds any member's trade with any outside partner.
    Coverage is partial by nature, and countries outside the sheet simply get no
    bloc lift rather than a guessed one.
"""

import os
import re

import openpyxl

import andah_data as ad

PAGES = os.path.join(ad.HERE, "pages", "Main")
GFCI_PAGE = os.path.join(PAGES, "Global_Financial_Centres_Index.wiki")


def load_financial_centres():
    """
    {country: strength}, where strength is a country's share of the world's
    top-centre weight.

    A centre's weight falls steeply with rank, because financial activity is far
    more concentrated than a linear reading of the ratings would suggest: London
    and New York dominate Earth's league table even though the numeric ratings of
    the top twenty are close together. Rank, not the raw rating, carries that.
    """
    if not os.path.exists(GFCI_PAGE):
        return {}, []
    text = open(GFCI_PAGE, encoding="utf-8", errors="ignore").read()
    centres, seen = [], set()
    # rows look like:  | 1 || align=left| {{flagicon|Raledria}} [[Tirna]] | 766<ref .../>
    for block in re.split(r"\n\|-", text):
        m_rank = re.search(r"^\s*\|\s*(\d{1,3})\s*\|\|", block)
        if not m_rank:
            continue
        countries = re.findall(r"\{\{\s*flagicon\s*\|\s*([^}|]+)\s*\}\}", block)
        if not countries:
            continue
        m_city = re.search(r"\[\[([^\]|]+)", block)
        m_rating = re.search(r"\|\s*(\d{3})\s*(?:<ref|\|)", block)
        rank = int(m_rank.group(1))
        if rank in seen:
            continue
        seen.add(rank)
        centres.append(dict(rank=rank, city=(m_city.group(1) if m_city else ""),
                            rating=int(m_rating.group(1)) if m_rating else None,
                            countries=[c.strip() for c in countries]))

    canon = set(ad.load_janus())
    weight, report = {}, []
    for c in centres:
        # a centre listed under two flags (Pha Hii / Dahe) is shared between them
        valid = [x for x in c["countries"] if x in canon]
        if not valid:
            report.append((c["city"], f"rank {c['rank']}: no recognised country"))
            continue
        w = 1.0 / (c["rank"] ** 0.75)
        for name in valid:
            weight[name] = weight.get(name, 0.0) + w / len(valid)
    total = sum(weight.values()) or 1.0
    return {k: v / total for k, v in weight.items()}, report


BLOC_SPLIT = re.compile(r"[,/;]+")


def load_blocs():
    """{country: {bloc codes}} from the Great Importance sheet."""
    wb = openpyxl.load_workbook(ad.JANUS, read_only=True, data_only=True)
    out = {}
    if "Great Importance" in wb.sheetnames:
        ws = wb["Great Importance"]
        rows = list(ws.iter_rows(values_only=True))
        if rows:
            hdr = [str(x).strip() if x else "" for x in rows[0]]
            try:
                ci = hdr.index("Name")
            except ValueError:
                ci = 1
            ai = next((i for i, h in enumerate(hdr)
                       if h.lower().startswith("allinec") or h.lower() == "alliances"), None)
            canon = set(ad.load_janus())
            for r in rows[1:]:
                if ai is None or ci >= len(r) or not r[ci]:
                    continue
                name = str(r[ci]).strip()
                if name not in canon:
                    continue
                raw = str(r[ai] or "").strip()
                if not raw or raw.lower() == "none":
                    continue
                codes = {c.strip().upper() for c in BLOC_SPLIT.split(raw) if c.strip()}
                # the sheet truncates some cells mid-code ("RSD" for RSDA); a code
                # is kept only if it looks like one, and near-duplicates are merged
                # "DAC" and "DAC+" are the same bloc in an ordinary and an
                # extended form; members of either trade as partners, so the
                # trailing marker is dropped rather than splitting them in two.
                codes = {c.rstrip("+") for c in codes if 2 <= len(c) <= 6}
                if codes:
                    out[name] = codes
    wb.close()
    return out


def bloc_lift(blocs, a, b):
    """How many blocs a pair shares. 0 when either is outside the sheet."""
    return len(blocs.get(a, set()) & blocs.get(b, set()))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    fc, rep = load_financial_centres()
    print(f"financial centres: {len(fc)} countries carry weight")
    for k, v in sorted(fc.items(), key=lambda kv: -kv[1])[:10]:
        print(f"   {k:<16}{v:6.1%} of world centre weight")
    if rep:
        print("   unresolved:", rep[:4])
    print()
    b = load_blocs()
    codes = {}
    for c, s in b.items():
        for x in s:
            codes[x] = codes.get(x, 0) + 1
    print(f"blocs: {len(b)} countries, {len(codes)} distinct codes")
    print("   ", dict(sorted(codes.items(), key=lambda kv: -kv[1])))
    pairs = sum(1 for a in b for x in b if a < x and b[a] & b[x])
    print(f"   country pairs sharing at least one bloc: {pairs}")
