# -*- coding: utf-8 -*-
"""One-off generator for 'National team appearances in the FLLA World Cup'.
Builds the comprehensive results matrix + ranking + confederation tables from
the per-edition stage data extracted from the wiki edition pages.
Not part of the pull/push loop."""
import re, io, sys

# Raw per-edition data: list of "Team=CODE" lines, (H) marks the host that year.
RAW = {
1656: """Siana=3rd (H)
Estijan=W
Eldjo=RU
Verusa=GS
Easuhura=GS
Emara=GS
Merela Sta=GS
Yaxuto=GS
Praesyu=4th""",
1660: """Easuhura=3rd (H)
Eldjo=GS
Emara=RU
Estijan=4th
Lycroa=W
Praesyu=GS
Verusa=GS
Yaxuto=GS""",
1668: """Eldjo=3rd (H)
Darewa=GS
Easuhura=GS
Emara=GS
Estijan=RU
Lycroa=W
Merela Sta=GS
Palina=GS
Praesyu=GS
Siana=4th
Verusa=GS
Yaxuto=GS""",
1672: """Emara=W (H)
Easuhura=GS
Eldjo=GS
Estijan=4th
Lycroa=RU
Merela Sta=GS
Praesyu=3rd
Siana=GS
Verusa=GS
Yaxuto=GS""",
1676: """Praesyu=3rd (H)
Estijan=GS
Verusa=R16
Yaxuto=GS
Merela Sta=QF
Palina=QF
Darewa=GS
Siana=4th
Taval=GS
Emara=RU
Easuhura=GS
Eldjo=W""",
1680: """Lycroa=W (H)
Darewa=GS
Easuhura=GS
Eldjo=RU
Emara=GS
Estijan=QF
Merela Sta=QF
Palina=QF
Praesyu=4th
Siana=3rd
Taval=GS
Verusa=GS
Yaxuto=GS""",
1684: """Alzurian Union=W (H)
Darewa=GS
Easuhura=GS
Eldjo=GS
Emara=QF
Estijan=QF
Lycroa=QF
Merela Sta=GS
Palina=GS
Praesyu=4th
Raledria=3rd
Siana=RU
Taval=GS
Trian=GS
Verusa=GS
Yaxuto=GS""",
1700: """Raledria=W (H)
Etirha=GS
Genaire=GS
Emara=GS
Lycroa=3rd
Praesyu=GS
Estijan=R16
Eldjo=R16
Siana=4th
Taval=GS
Quidic=GS
Dahe=GS
Areoix Lie=GS
United Delet=RU
Astye=GS
Terressin=GS""",
1704: """Emara=W (H)
Siana=RU
Lycroa=3rd
Easuhura=4th
Raledria=QF
Etirha=QF
Estijan=QF
Praesyu=QF
Dahe=GS
Quidic=GS
Seytinemas=GS
Areoix Lie=GS
Verusa=GS
Eldjo=GS
United Delet=GS
Alzurian Union=GS""",
1708: """United Delet=W (H)
Raledria=RU
Emara=3rd
Lycroa=4th
Quidic=QF
Estijan=QF
Praesyu=QF
Areoix Lie=QF
Etirha=GS
Eldjo=GS
Siana=GS
Iainoa=GS
Taval=GS
Seytinemas=GS
New Misos=GS
Astye=GS""",
1712: """Raledria=W
Easuhura=RU
Praesyu=3rd (H)
Emara=4th
Dahe=QF
Lycroa=QF
Siana=QF
Eldjo=QF
Quidic=GS
Etirha=GS
Wundry=GS
Areoix Lie=GS
Taval=GS
United Delet=GS
Ohtina=GS
Otiiric=GS""",
1716: """Raledria=W
Emara=RU
Easuhura=3rd (H)
Lycroa=4th
Verusa=QF
Praesyu=QF
Taval=QF
United Delet=QF
Quidic=GS
Dahe=GS
Seytinemas=GS
Siana=GS
Eldjo=GS
Reerica=GS
Areoix Lie=GS
New Misos=GS""",
1720: """Praesyu=W
Lycroa=RU
Etirha=3rd (H)
Raledria=4th
Emara=QF
Easuhura=QF
Dahe=QF
Verusa=QF
Pelugrotoa=GS
Finae=GS
Areoix Lie=GS
Seytinemas=GS
Taval=GS
Sattle=GS
United Delet=GS
Quidic=GS""",
1724: """Verusa=W
Easuhura=RU
Lycroa=3rd
Areoix Lie=4th (H)
Raledria=QF
Emara=QF
Dahe=QF
Praesyu=QF
Seytinemas=R16
New Misos=R16
United Delet=R16
Quidic=R16
Etirha=R16
Taval=R16
Trian=R16
Siana=R16
Astye=GS
Ztesh=GS
Sattle=GS
Vesozata=GS
Reerica=GS
Candenat=GS
Volver=GS
Inania=GS""",
1728: """Emara=W (H)
Taval=RU
Verusa=3rd
Raledria=4th
Lycroa=QF
Praesyu=QF
New Misos=QF
Genaire=QF
Finae=GS
Darewa=GS
Sanagara=GS
Wundry=GS
Chaenia=GS
Terressin=GS
Dahe=GS
United Delet=GS""",
1732: """Lycroa=W
Emara=RU
Verusa=3rd
Dahe=4th (H)
Raledria=QF
Ukhdari=QF
Finae=QF
Genaire=QF
Etretes=R16
Praesyu=R16
Sanagara=R16
Wundry=R16
Darewa=R16
United Delet=R16
Oyreain=R16
Terressin=R16
New Misos=GS
Acrana=GS
Prstreula=GS
Trian=GS
Chaenia=GS
Pelines=GS
Reerica=GS
Ztesh=GS""",
1736: """Raledria=W
Verusa=RU (H)
Easuhura=3rd
Etirha=4th
Siana=QF
Anymna=QF
Ohtina=QF
Ealdorii=QF
Taval=R16
United Delet=R16
Quidic=R16
Wundry=R16
Praesyu=R16
Merela Sta=R16
Dahe=R16
Lycroa=R16
Deschon=GS
Otiiric=GS
Oyreain=GS
Areoix Lie=GS
Ilicuhe=GS
Sivoso=GS
North Ayre=GS
Pelines=GS""",
1740: """New Misos=W
Lycroa=RU
Dahe=3rd
Fermori=4th
Trian=QF
Emara=QF
United Delet=QF
Sattle=QF
Seytinemas=R16 (H)
Verusa=R16
Astye=R16
Acetoa=R16
Praesyu=R16
Genaire=R16
Ztesh=R16
Raledria=R16
Etirha=GS
Vesozata=GS
Isnti=GS
Volver=GS
Darewa=GS
Quidic=GS
Siana=GS
Erkizil=GS
Inania=GS
Reerica=GS
Sanagara=GS
Haiza=GS
Candenat=GS
Ruylku=GS
Chaenia=GS
Isari=GS""",
1744: """Lycroa=W (H)
Easuhura=RU
Sanagara=3rd
New Misos=4th
Ohtina=QF
Etirha=QF
Verusa=QF
Quidic=QF
Finae=R16
Ztesh=R16
Terressin=R16
Dahe=R16
Merela Sta=R16
Siana=R16
Umarcia=R16
Areoix Lie=R16
Oyreain=GS
Taval=GS
Inania=GS
Vesozata=GS
Chaenia=GS
United Delet=GS
Ukhdari=GS
Trian=GS
Otiiric=GS
Isari=GS
Eldavpir=GS
Arbiya=GS
Fire Coast=GS
Lydroa=GS
Myla=GS
Raledria=GS""",
1748: """New Misos=W (H)
Seytinemas=RU
Finae=3rd
Sanagara=4th
Raledria=QF
Dual Cenryia=QF
Dahe=QF
Quidic=QF
Etirha=R16
Easuhura=R16
Emara=R16
United Delet=R16
Trian=R16
Ohtina=R16
Haiza=R16
Pelines=R16
Inania=GS
Rijan bu=GS
Yaxuto=GS
Ruylku=GS
Astye=GS
Palina=GS
Myla=GS
Acetoa=GS
Fermori=GS
Oyreain=GS
Erkizil=GS
Eldavpir=GS
Praesyu=GS
Gaeiya=GS
Genaire=GS
Eldjo=GS""",
1752: """Praesyu=W
Verusa=RU
United Delet=3rd (H)
New Misos=4th
Quidic=QF
Raledria=QF
Wundry=QF
Erkizil=QF
Iainoa=R16
Andsaudare=R16
Ukhdari=R16
Walporein=R16
Merela Sta=R16
Sivoso=R16
Trian=R16
Ztesh=R16
Emara=GS
Easuhura=GS
Mendereide=GS
Astye=GS
Exilium=GS
Chaenia=GS
Myla=GS
Haiza=GS
Ucrua=GS
Taval=GS
Terressin=GS
Pelines=GS
Acetoa=GS
Etirha=GS
Laselteh=GS
Guise=GS""",
1756: """Quidic=W (H)
New Misos=RU
Wundry=3rd (H)
Raledria=4th
Ztesh=QF (H)
Verusa=QF
Ukhdari=QF
United Delet=QF
Erkizil=R16 (H)
Easuhura=R16
Etirha=R16
Taval=R16
Emara=R16
Myla=R16
Terressin=R16
Finae=R16
Praesyu=GS
Iainoa=GS
Walporein=GS
Mendereide=GS
Merela Sta=GS
Sivoso=GS
Trian=GS
Exilium=GS
Chaenia=GS
Anymna=GS
Haiza=GS
Ucrua=GS
Laselteh=GS
Guise=GS
Pelines=GS
Acetoa=GS""",
1760: """Verusa=W
Raledria=RU
United Delet=3rd
Easuhura=4th
Taval=QF
Acetoa=QF
Sivoso=QF
Myla=QF
Haiza=R16
Ukhdari=R16 (H)
Etirha=R16
Merela Sta=R16
Emara=R16
Pelines=R16
Terressin=R16
New Misos=R16
Iainoa=GS
Walporein=GS
Mendereide=GS
Trian=GS
Dual Cenryia=GS
Exilium=GS
Chaenia=GS
Quidic=GS
Finae=GS
Ztesh=GS
Ucrua=GS
Etretes=GS
Vesozata=GS
Areoix Lie=GS
Deschon=GS
Laselteh=GS""",
1764: """Easuhura=W
Emara=RU
Verusa=3rd
Seytinemas=4th
Siana=QF
Sanagara=QF
Raledria=QF (H)
Finae=QF
Lycroa=R16
Vesozata=R16
Taval=R16
Chaenia=R16
Terressin=R16
Jshain=R16
Genaire=R16
Isnti=R16
Grazail=GS
Gaeiya=GS
Astye=GS
Mendereide=GS
Iainoa=GS
Isari=GS
Trian=GS
Exilium=GS
Anymna=GS
Wundry=GS
Erkizil=GS
Haiza=GS
Dahe=GS
Pelines=GS
Acetoa=GS
Viussi=GS""",
}

YEARS = sorted(RAW)

# parse
data = {}      # year -> {team: code}
hosts = {}     # year -> set(team)
for y, block in RAW.items():
    data[y] = {}
    hosts[y] = set()
    for line in block.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        is_host = "(H)" in line
        line = line.replace("(H)", "").strip()
        team, code = line.rsplit("=", 1)
        team = team.strip()
        code = code.strip()
        data[y][team] = code
        if is_host:
            hosts[y].add(team)

# confederation map — extracted authoritatively from edition Final-standings tables
# and qualification-section confederation headings (see extract_conf2.py).
CONF = {
  "Acetoa": "ACFVL", "Acrana": "AYFVL", "Alzurian Union": "AYFVL", "Andsaudare": "NAFVL",
  "Anymna": "QUFVL", "Arbiya": "ATFVL", "Areoix Lie": "ACFVL", "Astye": "NAFVL",
  "Candenat": "ACFVL", "Chaenia": "MAFVL", "Dahe": "MSFVL", "Darewa": "AYFVL",
  "Deschon": "ACFVL", "Dual Cenryia": "MAFVL", "Ealdorii": "AYFVL", "Easuhura": "AYFVL",
  "Eldavpir": "ACFVL", "Eldjo": "AYFVL", "Emara": "AYFVL", "Erkizil": "QUFVL",
  "Estijan": "AYFVL", "Etirha": "ATFVL", "Etretes": "MSFVL", "Exilium": "MAFVL",
  "Fermori": "AYFVL", "Finae": "QUFVL", "Fire Coast": "ACFVL", "Gaeiya": "ATFVL",
  "Genaire": "ATFVL", "Grazail": "ATFVL", "Guise": "ATFVL", "Haiza": "MSFVL",
  "Iainoa": "NAFVL", "Ilicuhe": "AYFVL", "Inania": "MAFVL", "Isari": "NAFVL",
  "Isnti": "MAFVL", "Jshain": "ACFVL", "Laselteh": "ATFVL", "Lycroa": "AYFVL",
  "Lydroa": "AYFVL", "Mendereide": "NAFVL", "Merela Sta": "AYFVL", "Myla": "QUFVL",
  "New Misos": "ATFVL", "North Ayre": "MSFVL", "Ohtina": "NAFVL", "Otiiric": "MAFVL",
  "Oyreain": "MSFVL", "Palina": "AYFVL", "Pelines": "ACFVL", "Pelugrotoa": "MAFVL",
  "Praesyu": "AYFVL", "Prstreula": "NAFVL", "Quidic": "QUFVL", "Raledria": "ATFVL",
  "Reerica": "ACFVL", "Rijan bu": "ACFVL", "Ruylku": "MSFVL", "Sanagara": "MSFVL",
  "Sattle": "ACFVL", "Seytinemas": "MAFVL", "Siana": "AYFVL", "Sivoso": "MAFVL",
  "Taval": "MSFVL", "Terressin": "ACFVL", "Trian": "MAFVL", "Ucrua": "MSFVL",
  "Ukhdari": "AYFVL", "Umarcia": "NAFVL", "United Delet": "NAFVL", "Verusa": "AYFVL",
  "Vesozata": "MSFVL", "Viussi": "ACFVL", "Volver": "QUFVL", "Walporein": "NAFVL",
  "Wundry": "QUFVL", "Yaxuto": "AYFVL", "Ztesh": "QUFVL",
}

# all teams
teams = set()
for y in YEARS:
    teams |= set(data[y])

RANK = {"W":0,"RU":1,"3rd":2,"4th":3,"SF":4,"QF":5,"R16":6,"GS":7}
BEST_TEXT = {"W":"Champions","RU":"Runners-up","3rd":"Third place","4th":"Fourth place",
             "SF":"Semi-finals","QF":"Quarter-finals","R16":"Round of 16","GS":"Group stage"}
DISPLAY = {"W":"1st","RU":"2nd","3rd":"3rd","4th":"4th","SF":"SF","QF":"QF","R16":"R16","GS":"GS"}
COLOR = {  # background, text-color  (canon legend colours from edition result maps)
 "W":("#2b42a3","#ffffff"),"RU":("#34c0be","#000000"),"3rd":("#269c5a","#ffffff"),
 "4th":("#81c846","#000000"),"QF":("#e4e454","#000000"),"R16":("#ff9f40","#000000"),
 "GS":("#b94954","#ffffff"),
}

def best_of(team):
    codes = [data[y][team] for y in YEARS if team in data[y]]
    return min(codes, key=lambda c: RANK.get(c,9))

def appearances(team):
    return sum(1 for y in YEARS if team in data[y])

def debut(team):
    return min(y for y in YEARS if team in data[y])

def recent(team):
    return max(y for y in YEARS if team in data[y])

# sort: appearances desc, best asc, name
team_list = sorted(teams, key=lambda t: (-appearances(t), RANK.get(best_of(t),9), t))

out = io.StringIO()
W = out.write

# ---------- comprehensive results matrix ----------
W('{| class="wikitable sortable" style="text-align:center; font-size:85%;"\n')
W('|+ Comprehensive team results by tournament\n')
W('! rowspan="2" | Team !! colspan="%d" | Edition !! rowspan="2" | Apps\n' % len(YEARS))
W('|-\n')
for y in YEARS:
    W('! style="font-size:90%%;" | [[%d FLLA World Cup|%d]]\n' % (y, y))
for t in team_list:
    conf = CONF.get(t, "")
    W('|-\n')
    W('! style="text-align:left; font-weight:normal;" | {{Flagicon|%s}} [[%s]]\n' % (t, t))
    for y in YEARS:
        if t in data[y]:
            c = data[y][t]
            bg, fg = COLOR.get(c, ("#ffffff","#000000"))
            txt = DISPLAY.get(c, c)
            if t in hosts[y]:
                txt = "'''%s'''" % txt
            W('| style="background:%s; color:%s;" | %s\n' % (bg, fg, txt))
        else:
            W('| style="background:#ececec;" |\n')
    W('| %d\n' % appearances(t))
W('|}\n')

matrix = out.getvalue()

# ---------- ranking table ----------
out2 = io.StringIO(); W = out2.write
W('{| class="wikitable sortable" style="text-align:center;"\n')
W('|+ Teams ranked by number of appearances\n')
W('! Team !! Confederation !! Appearances !! Debut !! Most recent !! Best result\n')
for t in team_list:
    W('|-\n')
    W('| align="left" | {{Flagicon|%s}} [[%s]] || [[%s]] || %d || [[%d FLLA World Cup|%d]] || [[%d FLLA World Cup|%d]] || align="left" | %s\n'
      % (t, t, CONF.get(t,""), appearances(t), debut(t), debut(t), recent(t), recent(t), BEST_TEXT[best_of(t)]))
W('|}\n')
ranking = out2.getvalue()

# ---------- confederation totals ----------
confs = ["AYFVL","ATFVL","NAFVL","MAFVL","QUFVL","MSFVL","ACFVL"]
from collections import defaultdict
conf_teams = defaultdict(set); conf_apps = defaultdict(int); conf_best = defaultdict(lambda:"GS")
for t in teams:
    c = CONF.get(t,"")
    if c not in confs:
        sys.stderr.write("NO CONF: %s\n"%t); continue
    conf_teams[c].add(t)
    conf_apps[c]+=appearances(t)
    if RANK[best_of(t)] < RANK[conf_best[c]]:
        conf_best[c]=best_of(t)

out3 = io.StringIO(); W=out3.write
W('{| class="wikitable sortable" style="text-align:center;"\n')
W('|+ Participation by confederation\n')
W('! Confederation !! Continent !! Teams !! Total appearances !! Best result\n')
CONT={"AYFVL":"Ayuma","ATFVL":"Atirha","NAFVL":"New Ayre","MAFVL":"Mahea","QUFVL":"Quia","MSFVL":"Massir","ACFVL":"Acrola"}
for c in sorted(confs, key=lambda c:-conf_apps[c]):
    W('|-\n')
    W('| align="left" | [[%s]] || align="left" | [[%s]] || %d || %d || align="left" | %s\n'
      % (c, CONT[c], len(conf_teams[c]), conf_apps[c], BEST_TEXT[conf_best[c]]))
W('|}\n')
conf_table = out3.getvalue()

# write fragments
open("frag_matrix.txt","w",encoding="utf-8").write(matrix)
open("frag_ranking.txt","w",encoding="utf-8").write(ranking)
open("frag_conf.txt","w",encoding="utf-8").write(conf_table)

# summary stats to stderr
print("teams total:", len(teams))
print("most appearances:", [(t,appearances(t)) for t in team_list[:8]])
print("champions:", sorted({t for y in YEARS for t in [max(data[y],key=lambda k:0)] } ))
for t in team_list:
    if CONF.get(t,"") not in confs:
        print("MISSING CONF:", t)
