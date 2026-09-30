"""Audit identity, split independence and hashes without printing held-out labels."""
import gzip
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/cumulative_planning'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    m=read(OUT/'data_manifest.json'); sample=read(ROOT/'results/fresh/leader_segments/sample.json')['sample']
    identity={x['id']:x['agents'] for x in sample}
    seeds={'train':set(),'test':set()};episodes={'train':set(),'test':set()};keys={'train':set(),'test':set()};counts={}
    checked=0
    for g in m['games']:
        ledger=read(Path(g['ledger_path']));seat=g['seat'];eid=g['episode']
        assert ledger['episode']==eid
        assert sha256(Path(g['raw_path']).read_bytes()).hexdigest()==ledger['replay_sha256']
        if eid in identity:
            assert identity[eid][seat]['sub']==g['submission']
        else:
            with gzip.open(ROOT/f"data/mg_tapes/{g['submission']}/{eid}.json.gz",'rt',encoding='utf-8') as f:t=json.load(f)
            assert t['seat']==seat and t['seed']==ledger['seed'] and t['episode']==eid
            assert t['rewards']==ledger['rewards']
            assert t['shops'][30]==ledger['shops_by_segment']['8']
        counts[str(g['submission'])]=counts.get(str(g['submission']),0)+1
        if g['split'] in seeds:
            seeds[g['split']].add(ledger['seed']);episodes[g['split']].add(eid);keys[g['split']].add(tuple(g['count_key']))
        checked+=1
    assert not(seeds['train']&seeds['test'])
    assert not(episodes['train']&episodes['test'])
    assert not(keys['train']&keys['test'])
    result=dict(games_checked=checked,versions=counts,
        train_unique_seeds=len(seeds['train']),test_unique_seeds=len(seeds['test']),
        train_unique_first4_compositions=len(keys['train']),test_unique_first4_compositions=len(keys['test']),
        overlaps=dict(seed=0,episode=0,first4_composition=0),
        identity_checks='Original source submission metadata; expansion known-version compact seat/seed/shop/reward agreement; all raw SHA256 match verified state ledgers.',
        baseline_sha256=sha256((ROOT/'agents/mgt_m1.py').read_bytes()).hexdigest(),
        manifest_sha256=sha256((OUT/'data_manifest.json').read_bytes()).hexdigest())
    (OUT/'corpus_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
