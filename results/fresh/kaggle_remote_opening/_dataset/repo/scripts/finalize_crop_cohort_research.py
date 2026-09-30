"""Validate retained panels and summarize independent-seed holdout uncertainty."""
from pathlib import Path
from collections import defaultdict
from hashlib import sha256
from itertools import product
from statistics import mean
import json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/crop_cohorts'

def summarize(panel):
    manifest=json.loads((OUT/panel/'manifest.json').read_text(encoding='utf-8'))
    rows=[json.loads(p.read_text(encoding='utf-8')) for p in (OUT/panel/'games').glob('*.json')]
    hashes={p['hash'] for p in manifest['policies']}
    rows=[r for r in rows if r['job']['policy_hash'] in hashes]
    assert len(rows)==manifest['games'],(panel,len(rows),manifest['games'])
    assert all(r['status']=='ok' and r['action_counts']==[719,719] for r in rows)
    for p in manifest['policies']:assert sha256(Path(p['path']).read_bytes()).hexdigest()==p['hash']
    bases={(r['job']['seed'],r['job']['seat'],r['job']['opponent']):r for r in rows if r['job']['policy_kind']=='baseline'}
    groups=defaultdict(list)
    for r in rows:
        j=r['job']
        if j['policy_kind']=='baseline':continue
        b=bases[j['seed'],j['seat'],j['opponent']];s=r['candidate_stats'] or {}
        if panel!='discovery':assert s.get('contract_errors',0)==0 and s.get('expired_unharvested_yield',0)==0
        groups[Path(j['policy_path']).stem].append(dict(seed=j['seed'],seat=j['seat'],opponent=j['opponent'],
            cash=r['final']['policy_cash']-b['final']['policy_cash'],margin=r['final']['margin']-b['final']['margin'],
            actual_margin=r['final']['margin'],baseline_margin=b['final']['margin'],
            same_shops=r['shops']['realized']==b['shops']['realized'],
            commitments=s.get('commitments',0),seed_purchases=s.get('seedpurchases',s.get('seed_orders',0)),
            max_seconds=r['timing']['policy']['max_seconds']))
    result={}
    for name,pairs in groups.items():
        opponents={o:dict(cash=mean(x['cash'] for x in pairs if x['opponent']==o),margin=mean(x['margin'] for x in pairs if x['opponent']==o)) for o in sorted({x['opponent'] for x in pairs})}
        clusters=[dict(seed=seed,cash=mean(x['cash'] for x in pairs if x['seed']==seed),margin=mean(x['margin'] for x in pairs if x['seed']==seed)) for seed in sorted({x['seed'] for x in pairs})]
        result[name]=dict(pairs=len(pairs),cash=mean(x['cash'] for x in pairs),margin=mean(x['margin'] for x in pairs),
             opponents=opponents,seeds=clusters,better=sum(x['margin']>0 for x in pairs),equal=sum(x['margin']==0 for x in pairs),worse=sum(x['margin']<0 for x in pairs),
             actual_wins=sum(x['actual_margin']>0 for x in pairs),baseline_wins=sum(x['baseline_margin']>0 for x in pairs),
             same_shop_pairs=sum(x['same_shops'] for x in pairs),active_games=sum(bool(x['commitments']) for x in pairs),
             max_seconds=max(x['max_seconds'] for x in pairs),worst=min(pairs,key=lambda x:x['margin']))
        if panel=='natural_holdout':
            values=[x['margin'] for x in clusters];n=len(values)
            bootstrap=sorted(sum(v)/n for v in product(values,repeat=n))
            result[name]['seed_cluster_bootstrap_95_percentile']=[bootstrap[int(.025*(len(bootstrap)-1))],bootstrap[int(.975*(len(bootstrap)-1))]]
            result[name]['bootstrap_note']='Exact resampling of six seed clusters, pooling all opponents and seats inside each seed; exploratory and small-sample.'
    identities={(r['job']['seed'],r['job']['seat'],r['job']['opponent'],r['job']['shops'],r['job']['policy_hash']) for r in rows}
    return result,identities

if __name__=='__main__':
    final={};unique=set()
    for panel in ('discovery','native_panel','value_panel','natural_holdout'):
        result,identities=summarize(panel);final[panel]=result;unique|=identities
    final['distinct_benchmark_games']=len(unique)
    final['export_check']=json.loads((OUT/'export_check.json').read_text(encoding='utf-8'))
    final['decision']='Retain corrected baseline. Reject unconditional replacements; value gate remains inconclusive because of small active-seed coverage and regressions against Two Coins and Pasture 2700. No upload.'
    (OUT/'final_summary.json').write_text(json.dumps(final,indent=2),encoding='utf-8')
    print(json.dumps(dict(distinct_games=len(unique),holdout=final['natural_holdout']),indent=2))
