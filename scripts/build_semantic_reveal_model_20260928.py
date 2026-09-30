"""Fit isolated, development-selected reveal features without altering old files."""
from collections import defaultdict
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import build_semantic_block_model_20260928 as B
import semantic_strategy_policy_20260928 as P
from semantic_strategy_blocks_reveal_20260928 import reveal_features

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/fresh/semantic_strategy_20260928'
SELECTED=('SHEEP','STRAWBERRY')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source,baseline_path):
    baseline=json.loads(baseline_path.read_text())
    assert baseline['source_sha256']==sha(source)
    rows=json.loads(source.read_text())['rows'];games=defaultdict(dict)
    for row in rows:games[(int(row['meta']['episode']),int(row['meta']['seat']))][row['day']]=row
    revised=deepcopy(baseline);shops=list(P.SHOPS)
    selected=[baseline['outputs'].index(s) for s in SELECTED]
    for day in range(6,30,3):
        xx=[];yy=[]
        for _,game in sorted(games.items()):
            first=game[day];chunk=[game[d] for d in range(day,day+3)]
            assert all(r['features']['shops_prefix']==first['features']['shops_prefix'] for r in chunk)
            xx.append(B.features(first)+reveal_features(day,first['features']['shops_prefix'],shops))
            counts=np.array([B.quantities(r) for r in chunk],float).sum(axis=0)
            for c in first['features']['own_crop_cohorts']:
                if c['crop'] in ('WHEAT','CARROT') and c['birth']+P.DEFAULT_CONFIG['release_age'][c['crop']]<=day+2:
                    counts[baseline['outputs'].index(c['crop'])]-=c['count']
            yy.append(counts)
        xx=np.array(xx,float);yy=np.array(yy,float)
        mean=xx.mean(axis=0);scale=np.maximum(xx.std(axis=0),1.)
        design=np.column_stack([np.ones(len(xx)),(xx-mean)/scale]);penalty=np.eye(design.shape[1])*3.;penalty[0,0]=0
        fit=np.linalg.solve(design.T@design+penalty,design.T@yy)
        old=baseline['blocks'][str(day)];new=revised['blocks'][str(day)]
        n=len(old['mean']);assert mean[:n].tolist()==old['mean'] and scale[:n].tolist()==old['scale']
        coef=np.zeros_like(fit);coef[:n+1,:]=np.array(old['coef'])
        # Do not alter retirements, annual crop counts, cows or geese.
        for i in selected:coef[:,i]=fit[:,i]
        new['coef']=coef.tolist();new['mean']=mean.tolist();new['scale']=scale.tolist()
    bundle=dict(schema=1,kind='optional_reveal_identity',default_enabled=False,
        selected_outputs=list(SELECTED),reveal_shop_types=shops,
        selection_provenance='Exploratory development selection after full modern100 leave-episode-out diagnostics; not an independent test.',
        future_reveal_assumption='Uniform one-hot expectation only when the modeled reveal is not yet observed; no reveal atD27.',
        baseline_model_sha256=sha(baseline_path),training_source_sha256=sha(source),
        baseline_model=baseline,reveal_model=revised)
    manifest=dict(source=str(source.relative_to(ROOT)),source_sha256=sha(source),baseline=str(baseline_path.relative_to(ROOT)),
        baseline_sha256=sha(baseline_path),episodes=sorted({e for e,s in games}),
        seats=[dict(episode=e,seat=s) for e,s in sorted(games)],
        provenance='Same authorized modern100 stage2 training as baseline. PriorDSM40 is training, not an independent stage2 test. Protocol183 excluded by source audit.')
    return bundle,manifest


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',default=str(BASE/'causal_daily_rows_modern100.json'))
    ap.add_argument('--baseline',default=str(BASE/'block_model_modern100.json'))
    ap.add_argument('--out',default=str(BASE/'block_model_reveal_modern100.json'));args=ap.parse_args()
    source=Path(args.source);baseline=Path(args.baseline);out=Path(args.out)
    bundle,manifest=build(source,baseline);out.write_text(json.dumps(bundle,separators=(',',':'))+'\n')
    mp=out.with_name(out.stem+'_training_manifest.json');mp.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(path=str(out),sha256=sha(out),training_episodes=len(manifest['episodes']))))


if __name__=='__main__':main()
