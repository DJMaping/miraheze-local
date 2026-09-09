import sys
import json, math, sys
sys.path.insert(0, r"C:UsersdannyDocumentsmiraheze-local")
sys.stdout.reconfigure(encoding="utf-8")
import earth_products as EP, trade_subcategories as t
D=json.load(open('andah_trade_atlas.json',encoding='utf-8'))
C=D['countries']; P=D['products']
dom={n:c['goods_x']+c['svc_x']-c['reexports'] for n,c in C.items()}
wm=D['world_mix']
print('category      Andah   Earth  | top1 Andah (who) top3 | Earth top1')
EC={'agri_food':(.10,'US'),'forestry_paper':(.12,'Canada'),'textiles':(.35,'China'),'chemicals':(.13,'Germany'),'machinery':(.16,'Germany'),'electronics':(.28,'China'),'vehicles':(.20,'Germany'),'other_manuf':(.30,'China'),'transport':(.10,'US'),'tourism':(.17,'US'),'finance_business':(.20,'US')}
for k in wm:
    col={n:c['basket'].get(k,0)*dom[n] for n,c in C.items()}
    tot=sum(col.values()) or 1; s=sorted(col.items(),key=lambda kv:-kv[1])
    e=EC.get(k)
    print(f"{k:<17} {wm[k]:6.1%} {EP.EARTH_MIX[k]:6.1%} | {s[0][1]/tot:5.0%} {s[0][0]:<12} {sum(v for _,v in s[:3])/tot:5.0%} | {e[0] if e else 0:.0%} {e[1] if e else ''}")
vc={}
for k,l,par,pci,e,a,v in P: vc[v]=vc.get(v,0)+1
print('\nverdicts',vc)
print('MISSES:')
for k,l,par,pci,e,a,v in P:
    if e and v!='Earth-like':
        print(f"{v[:7]:<8} {k:<20} top1 {a['top1']:.0%} {a['leader']:<12} vs {e['top1']:.0%} | top3 {a['top3']:.0%}/{e['top3']:.0%} | top10 {a['top10']:.0%}/{e['top10']:.0%} | n {a['n']:>2}/{e['n']:<2} | share {a['share']*100:.2f}/{e['share']*100:.2f}")
errs=[abs(math.log(a['share']/e['share'])) for k,l,par,pci,e,a,v in P if e and a['share']>0]
print('\nworld-share log error: median %.2f max %.2f'%(sorted(errs)[len(errs)//2],max(errs)))
nd=[(a['n']-e['n']) for k,l,par,pci,e,a,v in P if e]
print('exporters>=1%% diff (Andah-Earth): mean %.1f, median %d'%(sum(nd)/len(nd),sorted(nd)[len(nd)//2]))
cnt=sorted(len(c['sub']) for c in C.values()); print('products per country: min %d median %d max %d'%(cnt[0],cnt[len(cnt)//2],cnt[-1]))
print('metrics ok',sum(m['ok'] for m in D['metrics']),'/',len(D['metrics']), [m['name'] for m in D['metrics'] if not m['ok']])
for n in ['Pelugrotoa','Areoix Lie','Dahe','Raledria','Easuhura','Chaenia','Trian']:
    b=C[n]['basket']; print(f"{n:<12}", ' '.join(f"{k[:5]} {b[k]:.2f}" for k in ['machinery','electronics','chemicals','vehicles','forestry_paper','textiles','other_manuf','agri_food']))
