"""Exact recorded-action audit of the newly fetched cohort, both submissions."""
import gzip
import json
from collections import Counter
from pathlib import Path
import audit_m1_cross_game_symptoms as A

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/fresh/records_refresh_20260923'

def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    A.EPISODES=OUT/'audits'
    rows=[]
    cohorts={}
    for sub, status in manifest['submissions'].items():
        all_games=[]
        for p in (ROOT/f'data/ladder_panel/{sub}').glob('*.json.gz'):
            with gzip.open(p,'rt',encoding='utf8') as f: g=json.load(f)
            s=g['seat']; m=g['rewards'][s]-g['rewards'][1-s]
            all_games.append(dict(episode=g['episode'],created=g['created'],margin=m,
                                  opponent=g['opponent']['team'],shops=g['shops'][29]))
        fresh=[g for g in all_games if g['episode'] in status['downloaded']]
        def stats(gs):
            return dict(n=len(gs),wins=sum(g['margin']>0 for g in gs),losses=sum(g['margin']<0 for g in gs),
                        ties=sum(g['margin']==0 for g in gs),mean_margin=sum(g['margin'] for g in gs)/max(1,len(gs)))
        cohorts[sub]=dict(all=stats(all_games),new=stats(fresh),games=fresh)
        for ep in status['downloaded']:
            r=A.audit_one(ROOT/f'data/ladder_panel/{sub}/{ep}.json.gz')
            r['submission']=sub
            rows.append(r)
            print('audit',sub,ep,r['margin'],flush=True)
    groups={}
    for label,rs in [('new_all',rows),('new_losses',[r for r in rows if r['margin']<0]),('new_wins',[r for r in rows if r['margin']>0])]:
        gaps=Counter()
        for r in rs:
            for product in set(r['sides'][0]['revenue'])|set(r['sides'][1]['revenue']):
                gaps[product]+=r['sides'][0]['revenue'].get(product,0)-r['sides'][1]['revenue'].get(product,0)
        groups[label]=dict(n=len(rs),mean_revenue_gap={k:v/max(1,len(rs)) for k,v in gaps.items()},
                          exact_cash_checks=len(rs),berry=A.summarize(rs) if rs else {})
    summary=dict(cohorts=cohorts,groups=groups)
    (OUT/'diagnosis.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps(groups),flush=True)

if __name__=='__main__':main()
