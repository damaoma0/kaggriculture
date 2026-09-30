"""Internal consistency checks for store-pair and exact-engine screen artifacts."""
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/fresh/store_mismatch_shift_20260923'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))


def main():
 audit=read(BASE/'active_store_pairs.json')
 report=read(BASE/'pair_shift_summary.json')
 summary=read(BASE/'conversion/summary.json')
 care=read(BASE/'care_grid/summary.json')
 assert audit['counts']==dict(losses=89,store_substitution_events=383,
                              directed_store_pairs=56,under2500_events=247)
 assert len(report['pairs'])==56 and len(summary['conversions'])==128
 assert summary['conversion_event_curves']==837
 assert len({(r['source_store'],r['actual_store']) for r in report['pairs']})==56
 assert sum(r['events'] for r in report['pairs'])==383
 assert len({e['episode'] for e in audit['events']})==89
 assert min(Counter(e['episode'] for e in audit['events']).values())>=2
 by_key={(e['episode'],e['slot']):e for e in audit['events']}
 curves=0
 for path in sorted((BASE/'conversion').glob('*.json.gz')):
  with gzip.open(path,'rt',encoding='utf8') as f:g=json.load(f)
  assert g['validated']
  seat=g['seat'];base=g['baseline_cash'][seat]-g['baseline_cash'][1-seat]
  for e in g['events']:
   source=by_key[(g['episode'],e['slot'])]
   assert (e['source_store'],e['actual_store'])==(source['source_store'],source['actual_store'])
   for c in e['conversions']:
    assert source['shop_drains_per_day'][c['source']]<0
    assert source['shop_drains_per_day'][c['target']]>0
    assert [x['requested_per_day'] for x in c['curve']]==[0,1,2,4,6,8,12]
    assert c['curve'][0]['margin']==base and c['curve'][0]['converted_units']==0
    for x in c['curve']:
     assert x['margin_delta']==x['margin']-base
     assert 0<=x['converted_units']<=x['requested_per_day']*(30-e['reveal_day'])
    curves+=1
 assert curves==837
 registry=read(ROOT/'data/tape_variants/109740300-milk-care-to-wool-d17-diagnostic.json')
 source=ROOT/registry['source']
 assert sha256(source.read_bytes()).hexdigest()==registry['source_sha256']
 assert care['best_tested_arm']=='17' and care['best_tested_margin_delta']==237
 assert (sha256((ROOT/'agents/mgt_m1.py').read_bytes()).hexdigest()==
         '1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470')
 doc=(ROOT/'docs/store_mismatch_production_shift.md').read_text(encoding='utf8')
 assert doc.count('| '+ 'Pizza → Yarn' + ' |')==1
 print(json.dumps(dict(losses=89,mismatches=383,pairs=56,conversion_curves=curves,
                       best_care_arm=care['best_tested_arm'],source_unchanged=True)))


if __name__=='__main__':main()
