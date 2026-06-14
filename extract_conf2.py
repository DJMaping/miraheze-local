import re, os
from collections import defaultdict, Counter
MAIN="pages/Main"
ALLYEARS=[1700,1704,1708,1712,1716,1720,1724,1728,1732,1736,1740,1744,1748,1752,1756,1760,1764]
confs={"AYFVL","ATFVL","NAFVL","MAFVL","QUFVL","MSFVL","ACFVL"}
team_conf=defaultdict(Counter)

def pagetext(y):
    f=os.path.join(MAIN,f"{y}_FLLA_World_Cup.wiki")
    return open(f,encoding="utf-8").read() if os.path.exists(f) else ""

for y in ALLYEARS:
    txt=pagetext(y)
    # 1) standings table
    m=re.search(r"==\s*Final standings\s*==",txt)
    if m:
        sub=txt[m.end():]
        nxt=re.search(r"\n==[^=]",sub)
        if nxt: sub=sub[:nxt.start()]
        for row in re.split(r"\n\|-",sub):
            links=re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]",row)
            team=conf=None
            for l in links:
                l=l.strip()
                if l in confs and conf is None: conf=l
                elif not l.lower().startswith("file:") and l not in confs and team is None: team=l
            if team and conf: team_conf[team][conf]+=1
    # 2) qualification bullet lists under "==== [[CONF]] (...) ===="
    for cm in re.finditer(r"====\s*\[\[(AYFVL|ATFVL|NAFVL|MAFVL|QUFVL|MSFVL|ACFVL)\]\][^=]*====",txt):
        conf=cm.group(1)
        seg=txt[cm.end():]
        nxt=re.search(r"\n=",seg)
        if nxt: seg=seg[:nxt.start()]
        for bm in re.finditer(r"^\*\s*\{\{Flagicon\|[^}]+\}\}\s*\[\[([^\]|]+)",seg,re.M):
            team_conf[bm.group(1).strip()][conf]+=1

# manual: pre-1700 all-Ayuman teams
for t in ["Alzurian Union","Palina","Yaxuto","Merela Sta","Darewa","Siana","Estijan","Eldjo","Emara","Easuhura","Verusa","Lycroa","Praesyu"]:
    team_conf[t]["AYFVL"]+=0  # ensure present only if seen; don't override

final={}
for t,c in team_conf.items():
    final[t]=c.most_common(1)[0][0]
# force pre-1700 Ayuman if missing
for t in ["Alzurian Union","Palina","Yaxuto"]:
    final.setdefault(t,"AYFVL")

# print python dict
print("CONF = {")
for t in sorted(final):
    print(f'  "{t}": "{final[t]}",')
print("}")
