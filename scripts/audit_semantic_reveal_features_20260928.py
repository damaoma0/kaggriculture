"""Independent static/pure-feature checks of the optional reveal model."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'results/fresh/semantic_strategy_20260928'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    sys.path.insert(0,str(ROOT/'scripts'))
    from semantic_strategy_blocks_reveal_20260928 import reveal_features
    path=STUDY/'block_model_reveal_modern100.json';bundle=json.loads(path.read_text())
    frozen=STUDY/'candidates/strategy_v8_kb115lt2_readiness/project/results/fresh/semantic_strategy_20260928/block_model_modern100.json'
    base=bundle['baseline_model'];rev=bundle['reveal_model'];types=bundle['reveal_shop_types']
    checks=dict(default_off=bundle['default_enabled'] is False,
        baseline_hash_link=sha(frozen)==bundle['baseline_model_sha256'],
        baseline_dictionary_equal=base==json.loads(frozen.read_text()),
        selected_columns_exact=set(bundle['selected_outputs'])=={'SHEEP','STRAWBERRY'},
        source_sha_preserved=base['source_sha256']==rev['source_sha256']==bundle['training_source_sha256'])
    dimensions=[]
    for block,old in base['blocks'].items():
        new=rev['blocks'][block];n=len(old['coef']);unchanged=True
        for j,species in enumerate(base['outputs']):
            if species in bundle['selected_outputs']:continue
            unchanged &= [r[j] for r in old['coef']]==[r[j] for r in new['coef'][:n]]
            unchanged &= all(row[j]==0 for row in new['coef'][n:])
        checks['unchanged_nonselected_coefficients_'+block]=unchanged
        checks['unchanged_schedule_caps_'+block]=all(old[k]==new[k] for k in ('shares','max_counts','hands','land','opening_examples'))
        checks['original_scaling_'+block]=old['mean']==new['mean'][:-len(types)] and old['scale']==new['scale'][:-len(types)]
        dimensions.append(dict(block=int(block),old_features=len(old['mean']),new_features=len(new['mean'])))
    probes=0
    for day in range(6,30):
        count=min(8,day//3);prefix=types[:count]
        got=reveal_features(day,prefix,types)
        expected=([float(s==prefix[day//3-1]) for s in types] if day<27 else [0.]*len(types))
        assert got==expected
        assert got==reveal_features(day,prefix+list(reversed(types)),types)
        if day<27:
            assert reveal_features(day,prefix[:-1],types,True)==[1/len(types)]*len(types)
            try:reveal_features(day,prefix[:-1],types,False)
            except ValueError:pass
            else:raise AssertionError('Missing current reveal did not reject')
        probes+=1
    checks['24_day_visible_index_and_future_expectation_probes']=probes==24
    checks['same_composition_different_latest_feature']=(reveal_features(9,['BAKERY','YARN_STORE','PIZZA_SHOP'],types)
        !=reveal_features(9,['BAKERY','PIZZA_SHOP','YARN_STORE'],types))
    assert all(checks.values()),checks
    out=dict(scope='INDEPENDENT_STATIC_AND_PURE_FEATURE_CHECK_NO_GAMES',result='PASS',checks=checks,dimensions=dimensions,
        model_sha256=sha(path),source_sha256=sha(ROOT/'scripts/semantic_strategy_blocks_reveal_20260928.py'),
        script_sha256=sha(Path(__file__)),frozen_baseline_sha256=sha(frozen),
        limitations=['Exploratory fit selected on development diagnostics, not independent performance evidence.',
            'Feature changes current shop identity only. It does not add rival state or market data to block generation.',
            'Admission may change other accepted species when the selected SHEEP/STRAWBERRY budgets compete for capacity.',
            'D6 opening retrieval bypasses regression features; future unknown reveal uses uniform expectation.'])
    dest=STUDY/'reveal_feature_independent_audit.json';dest.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(result=out['result'],checks=len(checks),model_sha256=out['model_sha256'])));print(dest)

if __name__=='__main__':main()
