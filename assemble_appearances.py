# -*- coding: utf-8 -*-
matrix=open("frag_matrix.txt",encoding="utf-8").read().rstrip()
ranking=open("frag_ranking.txt",encoding="utf-8").read().rstrip()
conf=open("frag_conf.txt",encoding="utf-8").read().rstrip()

LEAD = r"""{{Short description|Record of national team participation in the FLLA World Cup}}

[[File:Map_of_FLLA_World_Cup_participating_nations.png|thumb|upright=1.8|A map showing all nations to have competed at an FLLA World Cup final tournament]]
[[File:Map_of_FLLA_World_Cup_best_performances.png|thumb|upright=1.8|A map showing the best performance of each nation to have competed at an FLLA World Cup]]
[[File:Map_of_FLLA_World_Cup_host_nations.png|thumb|upright=1.8|A map showing all nations that have hosted an FLLA World Cup and how many times they have done so]]

This article records the appearances of national teams at the final tournaments of the '''[[FLLA World Cup]]''', the international [[Arraby]] competition contested by the senior men's national teams of the member associations of the [[FLLA]]. The competition has been held in twenty-four completed editions between the [[1656 FLLA World Cup|1656 edition]], staged as the Ayuman Continental Tournament, and the [[1764 FLLA World Cup|1764 edition]].<ref name="fllaheritage">{{cite web|url=https://www.flla.org/heritage/world-cup/roll-of-honour|title=FLLA World Cup roll of honour|publisher=[[FLLA]]|date=20 August 1764}}</ref>

As of the [[1764 FLLA World Cup|1764 edition]], '''79''' national teams have competed at an FLLA World Cup final tournament. [[Emara]] have made the most appearances, having taken part on twenty-two occasions, ahead of [[Praesyu]] with twenty-one and [[Verusa]] with twenty. Twelve different teams have been crowned champions; [[Lycroa]] are the most successful, with five titles and a record eight final appearances.<ref name="fllarecords">{{cite web|url=https://www.flla.org/heritage/world-cup/records|title=FLLA World Cup final records and milestones|publisher=[[FLLA]]|date=22 August 1764}}</ref> Three teams have reached a final without ever winning the tournament: [[Siana]], [[Seytinemas]] and [[Taval]].

The figures below count appearances at the final tournament only; the four editions awarded but never contested because of intercontinental conflict (the [[1664 FLLA World Cup|1664]], [[1688 FLLA World Cup|1688]], [[1692 FLLA World Cup|1692]] and [[1696 FLLA World Cup|1696]] editions) are excluded, as is the qualifying competition.

==Ranking of teams by number of appearances==

The following table ranks every nation to have appeared at an FLLA World Cup by the number of final tournaments attended. Teams level on appearances are ordered by best result and then alphabetically.<ref name="fllaheritage" />

"""

LEGEND = r"""==Comprehensive team results by tournament==

The result of each team at each edition is shown using the following key:

{{col-begin}}
{{col-2}}
* '''1st''' &ndash; Champions
* '''2nd''' &ndash; Runners-up
* '''3rd''' &ndash; Third place
* '''4th''' &ndash; Fourth place
{{col-2}}
* '''QF''' &ndash; Quarter-finals
* '''R16''' &ndash; Round of 16 (last 16)
* '''GS''' &ndash; Group stage (first round)
* Blank &ndash; Did not qualify or did not enter
{{col-end}}

Host nations are shown in '''bold'''. For each team, "Apps" gives the total number of final tournaments attended.

"""

HOSTS = r"""==Hosts==

The tournament has been hosted as follows; co-hosting countries are listed together. For a fuller breakdown, including the cancelled editions and the confederation rotation policy, see [[List of FLLA World Cup hosts]].

{| class="wikitable" style="text-align:center; font-size:95%;"
|+ FLLA World Cup hosts
! Year !! Host(s) !! Continent
|-
| [[1656 FLLA World Cup|1656]] || align="left" | {{Flagicon|Siana}} [[Siana]] || align="left" | [[Ayuma]]
|-
| [[1660 FLLA World Cup|1660]] || align="left" | {{Flagicon|Easuhura}} [[Easuhura]] || align="left" | [[Ayuma]]
|-
| [[1668 FLLA World Cup|1668]] || align="left" | {{Flagicon|Eldjo}} [[Eldjo]] || align="left" | [[Ayuma]]
|-
| [[1672 FLLA World Cup|1672]] || align="left" | {{Flagicon|Emara}} [[Emara]] || align="left" | [[Ayuma]]
|-
| [[1676 FLLA World Cup|1676]] || align="left" | {{Flagicon|Praesyu}} [[Praesyu]] || align="left" | [[Ayuma]]
|-
| [[1680 FLLA World Cup|1680]] || align="left" | {{Flagicon|Lycroa}} [[Lycroa]] || align="left" | [[Ayuma]]
|-
| [[1684 FLLA World Cup|1684]] || align="left" | {{Flagicon|Alzurian Union}} [[Alzurian Union|Alzuria]] || align="left" | [[Ayuma]]
|-
| [[1700 FLLA World Cup|1700]] || align="left" | {{Flagicon|Raledria}} [[Raledria]] || align="left" | [[Atirha]]
|-
| [[1704 FLLA World Cup|1704]] || align="left" | {{Flagicon|Emara}} [[Emara]] || align="left" | [[Ayuma]]
|-
| [[1708 FLLA World Cup|1708]] || align="left" | {{Flagicon|United Delet}} [[United Delet]] || align="left" | [[New Ayre]]
|-
| [[1712 FLLA World Cup|1712]] || align="left" | {{Flagicon|Praesyu}} [[Praesyu]] || align="left" | [[Ayuma]]
|-
| [[1716 FLLA World Cup|1716]] || align="left" | {{Flagicon|Easuhura}} [[Easuhura]] || align="left" | [[Ayuma]]
|-
| [[1720 FLLA World Cup|1720]] || align="left" | {{Flagicon|Etirha}} [[Etirha]] || align="left" | [[Atirha]]
|-
| [[1724 FLLA World Cup|1724]] || align="left" | {{Flagicon|Areoix Lie}} [[Areoix Lie]] || align="left" | [[Acrola]]
|-
| [[1728 FLLA World Cup|1728]] || align="left" | {{Flagicon|Emara}} [[Emara]] || align="left" | [[Ayuma]]
|-
| [[1732 FLLA World Cup|1732]] || align="left" | {{Flagicon|Dahe}} [[Dahe]] || align="left" | [[Massir]]
|-
| [[1736 FLLA World Cup|1736]] || align="left" | {{Flagicon|Verusa}} [[Verusa]] || align="left" | [[Ayuma]]
|-
| [[1740 FLLA World Cup|1740]] || align="left" | {{Flagicon|Seytinemas}} [[Seytinemas]] || align="left" | [[Mahea]]
|-
| [[1744 FLLA World Cup|1744]] || align="left" | {{Flagicon|Lycroa}} [[Lycroa]] || align="left" | [[Ayuma]]
|-
| [[1748 FLLA World Cup|1748]] || align="left" | {{Flagicon|New Misos}} [[New Misos]] || align="left" | [[Atirha]]
|-
| [[1752 FLLA World Cup|1752]] || align="left" | {{Flagicon|United Delet}} [[United Delet]] || align="left" | [[New Ayre]]
|-
| [[1756 FLLA World Cup|1756]] || align="left" | {{Flagicon|Erkizil}} [[Erkizil]], {{Flagicon|Quidic}} [[Quidic]], {{Flagicon|Wundry}} [[Wundry]], {{Flagicon|Ztesh}} [[Ztesh]] || align="left" | [[Quia]]
|-
| [[1760 FLLA World Cup|1760]] || align="left" | {{Flagicon|Ukhdari}} [[Ukhdari]] || align="left" | [[Ayuma]]
|-
| [[1764 FLLA World Cup|1764]] || align="left" | {{Flagicon|Raledria}} [[Raledria]] || align="left" | [[Atirha]]
|}

"""

CONF_INTRO = r"""==Participation by confederation==

The table below summarises participation at the final tournament by [[FLLA]] confederation. "Teams" counts the distinct national teams from each confederation to have appeared; "Total appearances" sums those teams' individual appearances across all editions.<ref name="fllaheritage" />

"""

TAIL = r"""

==Notes==

* The first seven editions, from [[1656 FLLA World Cup|1656]] to [[1684 FLLA World Cup|1684]], were contested while the competition was staged as the Ayuman Continental Tournament and were open only to [[AYFVL]] member associations; the tournament was rebranded the FLLA World Cup and opened to all confederations from the [[1700 FLLA World Cup|1700 edition]].
* The size of the final tournament has varied over its history: from eight to thirteen teams in the Ayuman Continental Tournament era, sixteen from the [[1684 FLLA World Cup|1684 edition]], twenty-four at some later editions from [[1724 FLLA World Cup|1724]], and a fixed thirty-two since the [[1740 FLLA World Cup|1740 edition]].
* The round of 16 exists only at editions with twenty-four or more teams; at smaller editions the first knockout round was the quarter-finals.

==See also==

* [[FLLA World Cup]]
* [[FLLA]]
* [[Arraby]]
* [[List of FLLA World Cup finals]]
* [[List of FLLA World Cup hosts]]
* [[List of FLLA World Cup champions]]
* [[AYFVL]]
* [[ATFVL]]
* [[NAFVL]]
* [[MAFVL]]
* [[QUFVL]]
* [[MSFVL]]
* [[ACFVL]]

==References==
{{reflist}}

[[Category:FLLA World Cup]]
[[Category:National team appearances in the FLLA World Cup| ]]
[[Category:International Arraby competitions]]
[[Category:Lists of FLLA World Cup]]
"""

page = LEAD + ranking + "\n\n" + LEGEND + matrix + "\n\n" + HOSTS + CONF_INTRO + conf + TAIL
open("pages/Main/National_team_appearances_in_the_FLLA_World_Cup.wiki","w",encoding="utf-8").write(page)
print("written, total chars:", len(page))
print("em-dashes:", page.count("—"))
