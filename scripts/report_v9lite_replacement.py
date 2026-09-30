"""Paired accounting for the frozen replacement / wool-upturn experiment."""
from collections import Counter
import json
from pathlib import Path
import random
from statistics import mean

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/v9lite_replacement_20260925'


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def interval(values):
    if len(values)<2:return None
    rng=random.Random(250926)
    b=sorted(mean(rng.choices(values,k=len(values))) for _ in range(10000))
    return [b[250],b[9750]]


def summarize(rows,seeds):
    baseline={(r['number'],r['seat']):r for r in rows if r.get('completed') and r['arm']=='baseline'}
    result={}
    for arm in ('guard','upturn','combined'):
        pairs=[]
        for r in rows:
            if r.get('arm')!=arm or not r.get('completed') or r['number'] not in seeds:continue
            b=baseline.get((r['number'],r['seat']))
            if not b:continue
            own,bown=r['economics'][0],b['economics'][0]
            changed=r['action_sha256']!=b['action_sha256']
            pairs.append(dict(number=r['number'],seat=r['seat'],margin_delta=r['margin']-b['margin'],
                own_delta=r['cash']-b['cash'],rival_delta=r['rival_cash']-b['rival_cash'],changed=changed,
                wage_delta=own['spend'].get('HIRE',0)-bown['spend'].get('HIRE',0),
                wool_delta=own['units'].get('WOOL',0)-bown['units'].get('WOOL',0),
                wheat_delta=own['units'].get('WHEAT',0)-bown['units'].get('WHEAT',0),
                late_plant_delta=len(r['successful_plantings'])-len(b['successful_plantings']),
                wins_before=int(b['margin']>0),wins_after=int(r['margin']>0),
                same_shops=r.get('shops')==b.get('shops'),
                guard_fires=(r['telemetry'].get('sheep') or {}).get('replacement_service_suppressed',0)))
        if not pairs:continue
        clusters=[mean(p['margin_delta'] for p in pairs if p['number']==s) for s in seeds
                  if {p['seat'] for p in pairs if p['number']==s}=={0,1}]
        result[arm]=dict(games=len(pairs),mean_margin=mean(p['margin_delta'] for p in pairs),
            mean_own_cash=mean(p['own_delta'] for p in pairs),mean_rival_cash=mean(p['rival_delta'] for p in pairs),
            better=sum(p['margin_delta']>0 for p in pairs),worse=sum(p['margin_delta']<0 for p in pairs),
            unchanged=sum(p['margin_delta']==0 for p in pairs),worst=min(p['margin_delta'] for p in pairs),
            seed_bootstrap_95ci=interval(clusters),independent_seed_pairs=len(clusters),
            wins_before=sum(p['wins_before'] for p in pairs),wins_after=sum(p['wins_after'] for p in pairs),pairs=pairs)
    return result


def main():
    design=read(OUT/'design.json')
    historical=[read(p) for p in (OUT/'historical').glob('*.json')]
    live=[read(p) for p in (OUT/'live').glob('*.json')]
    result=dict(historical=summarize(historical,design['historical']),
        pilot=summarize(live,design['pilot_seeds']),confirmation=summarize(live,design['confirmation_seeds']),
        completed=sum(bool(r.get('completed')) for r in historical+live),
        errors=[r for r in historical+live if not r.get('completed')],
        caveat='Historical worlds replay fixed opponents and forced shops. Live seed pairs are independent worlds; '
        'bootstrap intervals with two/four worlds are very imprecise. Do not infer Elo or current 3000+ strength.')
    result['official_runtime'] = dict(
        verified_live_ledgers=sum(bool(r.get('ledger_verified')) for r in live),
        minimum_own_bank=min((r['min_bank'][r['seat']] for r in live if r.get('completed')),default=None),
        search_errors=sum((r.get('telemetry',{}).get('search') or {}).get('errors',0) for r in historical+live))
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    compact={stage:{a:{k:v for k,v in r.items() if k!='pairs'} for a,r in result[stage].items()}
             for stage in ('historical','pilot','confirmation')}
    print(json.dumps(dict(compact,completed=result['completed'],errors=result['errors']),indent=2))
    lines=['# V9-lite replacement / wool-upturn experiment — 2026-09-25','',
        'Four frozen arms differ only in packaged agents/mgt_y3.py: baseline, explicit crop-replacement guard, '
        'wool-price upturn, and both. Current submissions and the original V9-lite package are unchanged.','',
        '| Arm | Historical mean margin change (2 diagnostic worlds) | Fresh pilot mean margin change | Pilot better / worse / same |',
        '|---|---:|---:|---|']
    for a in ('guard','upturn','combined'):
        h=result['historical'].get(a,{});p=result['pilot'].get(a,{})
        lines.append(f"| {a} | {h.get('mean_margin','pending')} | {p.get('mean_margin','pending')} | "
                     f"{p.get('better',0)} / {p.get('worse',0)} / {p.get('unchanged',0)} |")
    lines+=['','Historical results use fixed recorded shops and opponent actions. Pilot uses two newly generated '
        'seeds, both seats, a responsive V56, natural RNG and the official engine time bank. '
        'These are two independent pilot worlds, not four independent worlds. Confirmation seeds remain separate.',
        '',f"Completed full games: {result['completed']}. Recorded failures: {len(result['errors'])}. "
        f"Verified live ledgers: {result['official_runtime']['verified_live_ledgers']}. "
        f"Minimum own live time bank: {result['official_runtime']['minimum_own_bank']}. "
        f"Internal search errors: {result['official_runtime']['search_errors']}.",'',
        '## Mechanism and rejection evidence','',
        'The guard scans the selected route for DIG then PLANT on the same tile over today and the next two days, '
        'abstains when native FEED precedes the conversion, removes optional FEED/CARE and retains an already-requested '
        'HARVEST when product is present. It changes no shops or external opponent behavior. Contract checks cover '
        'conversion recognition, native-feed veto, final-stock harvesting and removal of obsolete rescue commitments.','',
        'In episode 111261836 it restores the D26 wheat planting at (3,4), which later yields five wheat. '
        'But total wool sold falls 80 to 58, wage spending falls 953, and final competitive margin falls 2,034. '
        'The second diagnostic loses 4,322. Thus treating the donor conversion as mandatory is not a validated fix '
        'for current y3: keeping an animal can be the profitable demand response. The old m1 failure does not '
        'transfer directly to V9-lite.','',
        'The isolated wool-upturn patch changes the current diagnostics by -20 and 0. Its older m1 validation '
        'cannot be reused as current-package evidence.','',
        'No promotion is justified by restoring a planting or increasing a forecast alone. Any successor needs '
        'a comparison of feasible remaining animal income and crop replacement income, including labor and rival '
        'price effects, rather than an unconditional retirement priority.','',
        'Reproduce: experiment_v9lite_replacement.py freeze / historical / pilot; '
        'report_v9lite_replacement.py; test_mgt_replacement_guard.py. Exact source hashes, predeclared '
        'seeds, raw results, work traces and ledgers are stored beside this report.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':main()
