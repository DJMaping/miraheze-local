import re, os, json
from collections import defaultdict, Counter
MAIN="pages/Main"
YEARS=[1700,1704,1708,1712,1716,1720,1724,1728,1732,1736,1740,1744,1748,1752,1756,1760,1764]
team_conf=defaultdict(Counter)
for y in YEARS:
    f=os.path.join(MAIN,f"{y}_FLLA_World_Cup.wiki")
    if not os.path.exists(f): continue
    txt=open(f,encoding="utf-8").read()
    m=re.search(r"==\s*Final standings\s*==",txt)
    if not m: continue
    sub=txt[m.end():]
    nxt=re.search(r"\n==[^=]",sub)
    if nxt: sub=sub[:nxt.start()]
    # rows: lines with Team link then conf link
    for row in re.split(r"\n\|-",sub):
        links=re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]",row)
        # find team (first non-conf non-file) and conf (one of the 7)
        confs={"AYFVL","ATFVL","NAFVL","MAFVL","QUFVL","MSFVL","ACFVL"}
        team=None;conf=None
        for l in links:
            l=l.strip()
            if l in confs and conf is None: conf=l
            elif not l.lower().startswith("file:") and l not in confs and team is None:
                team=l
        if team and conf:
            team_conf[team][conf]+=1
# print mapping, flag conflicts
for t in sorted(team_conf):
    c=team_conf[t]
    best=c.most_common(1)[0][0]
    flag=" <-- CONFLICT %s"%dict(c) if len(c)>1 else ""
    print(f"{t} = {best}{flag}")
