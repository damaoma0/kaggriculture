"""Read-only audit and paired episode bootstrap for local continuation transfer."""
import json, gzip
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/tape_gap_plans'
PRODUCTS=('WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','EGG','MILK','WOOL','FERTILIZER')

def vec(x): return np.array([x[p] for p in PRODUCTS],float)
def mae(row,key): return float(np.abs(vec(row[key])-vec(row['actual'])).mean())
def bootstrap(rows, baseline, draws=10000, seed=20260922):
    by=defaultdict(list)
    for row in rows: by[str(row['episode'])].append(row)
    episodes=sorted(by); rng=np.random.default_rng(seed); values=[]
    for _ in range(draws):
        chosen=rng.choice(episodes,len(episodes),replace=True)
        sample=[row for ep in chosen for row in by[ep]]
        values.append(float(np.mean([mae(r,baseline)-mae(r,'transferred_target') for r in sample])))
    point=float(np.mean([mae(r,baseline)-mae(r,'transferred_target') for r in rows]))
    return {'n_rows':len(rows),'n_episodes':len(episodes),'baseline':baseline,'transfer':'transferred_target',
            'mae_reduction':point,'bootstrap95':[float(x) for x in np.quantile(values,[.025,.975])],
            'bootstrap_draws':draws,'seed':seed}
def compact_empty_tokens():
    found=Counter()
    for sub in ('56266758','56266899'):
        for path in (ROOT/f'data/mg_tapes/{sub}').glob('*.json.gz'):
            with gzip.open(path,'rt',encoding='utf-8') as f:g=json.load(f)
            for board in g['boards'][12:25:3]:
                raw=''.join(board); assert len(raw)==200
                found.update(raw[i:i+2] for i in range(0,200,2))
    return {k:v for k,v in found.items() if k in (' .',' L')}
def main():
    analysis=json.loads((OUT/'local_transfer_analysis.json').read_text())
    primary=json.loads((OUT/'dataset_primary.json').read_text())
    candidates=json.loads((OUT/'primary_candidates.json').read_text())
    rows=analysis['rows']; missing=[r for r in rows if not r['ordered_prefix_available_584']]
    production=[]; identity=[]
    for game in primary['games']:
        compact=ROOT/f"data/ladder_panel/56395605/{game['episode']}.json.gz"
        with gzip.open(compact,'rt',encoding='utf-8') as f:raw=json.load(f)
        identity.append(game['compact_sha256']==__import__('hashlib').sha256(compact.read_bytes()).hexdigest() and raw['rewards']==game['rewards'])
        for day in (12,15,18,21,24):
            cp=game['checkpoints'][str(day)]; idx=day//3
            prior=game['segments'][idx-1]['output']; total={p:sum(s['output'][p] for s in game['segments'][:idx]) for p in PRODUCTS}
            production.append(cp['prior_output']==prior and cp['cumulative_output']==total and all(s['output'][p]==s['physical'].get('produced:'+p,0) for s in game['segments'] for p in PRODUCTS))
    residual_ok=all(np.allclose(vec(r['transferred_target']),np.maximum(0,vec(r['mechanical_own'])+vec(r['donor_output'])-vec(r['mechanical_donor']))) for r in rows)
    current_only=all(r['day'] in (12,15,18,21,24) and r['donor_episode']!=r['episode'] for r in rows)
    # Candidates use the compact ranker, whose own empty is '.'; compact UMG has '.' too.
    result={'scope':'Read-only audit; no ranking/replay/model artifact changed.',
       'rows':len(rows),'missing_ordered_prefix_rows':len(missing),'primary_games':len(primary['games']),
       'identity':{'all_compact_hash_and_reward_match':all(identity),'checked_games':len(identity)},
       'production':{'all_prior_cumulative_and_physical_output_consistent':all(production),'checked_checkpoint_rows':len(production)},
       'continuation_logic':{'residual_identity_exact':residual_ok,'current_checkpoint_donor_day_and_self_exclusion':current_only,
         'mechanical_profile_source_check':'research_nearest_continuation.tile_profile simulates to min(day+6,30) and sums day..day+2; no end=day+3 mechanical call.'},
       'ranking_labels':{'primary_candidate_count':len(candidates['candidates']),'compact_empty_tokens':compact_empty_tokens(),
         'finding':'Canonical compact encoding uses two-character tokens; empty is " ." and locked is " L", matching own_tiles. Productive comparison uses WH/CA/TO/ST/ME/co/go/sh.'},
       'paired_episode_bootstrap':{'missing_ordered_prefix': [bootstrap(missing,b) for b in ('donor_output','frozen_forecast')],
         'by_day':{str(day):[bootstrap([r for r in missing if r['day']==day],b) for b in ('donor_output','frozen_forecast')] for day in (12,15,18,21,24)}},
       'important_findings':['The reported transfer is a target diagnostic, not a continuation action; it uses donor next3 as a label after current-state ranking.',
         'The donor library includes UMG train and already-exposed test episodes. Its UMG diagnostic is therefore a falsification check, not a new blind result.',
         'Simulator explicitly forces each tape’s observed daily shop path; the equality assertion is a consistency check, not independent RNG/shop-path validation.']}
    (OUT/'independent_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result['paired_episode_bootstrap']['missing_ordered_prefix'],indent=2))
if __name__=='__main__':main()
