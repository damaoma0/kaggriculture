"""Paired comparisons; uncertainty is clustered by seed, never by seat."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import statistics as S

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/fresh/rotation_experiments'


def interval(values):
    if not values:
        return None
    rng = random.Random(20260922)
    means = sorted(S.mean(rng.choices(values, k=len(values))) for _ in range(12000))
    return [means[299], means[11699]]


def summarize(stage):
    directory = OUT/stage
    manifest = json.loads((directory/'manifest.json').read_text())
    games = [json.loads(p.read_text(encoding='utf-8')) for p in (directory/'games').glob('*.json')]
    base = {(g['seed'],g['seat']):g for g in games if g['agent']=='mgt_m1' and g.get('completed')}
    result = {'stage':stage, 'expected':manifest['expected_games'], 'present':len(games),
              'completed':sum(bool(g.get('completed')) for g in games), 'arms':{}}
    for name in manifest['agents']:
        rows = [g for g in games if g['agent']==name]
        valid = [g for g in rows if g.get('completed')]
        deltas = defaultdict(list); cash = []; unchanged=0; shops_same=0
        ledger_delta = {'revenue':Counter(), 'spend':Counter(), 'sold_units':Counter(), 'physical':Counter()}
        events=Counter(); units=Counter(); runtime_errors=0
        for g in valid:
            b=base.get((g['seed'],g['seat']))
            if b:
                deltas[g['seed']].append(g['margin']-b['margin'])
                cash.append(g['cash']-b['cash'])
                unchanged+=g['action_sha256']==b['action_sha256']
                shops_same+=g['shops']==b['shops']
                final=g['daily'][g['seat']][-1]; baseline=b['daily'][b['seat']][-1]
                for kind, totals in ledger_delta.items():
                    for k in set(final[kind]) | set(baseline[kind]):
                        totals[k]+=final[kind].get(k,0)-baseline[kind].get(k,0)
            report=g.get('agent_reports',{}).get('own',{}).get('_ROT_REPORT',{})
            runtime_errors+=int(report.get('errors',0))
            for k,v in report.items():
                if isinstance(v,(int,float)):
                    events[k]+=v
            for e in report.get('events',[]):
                units[e['kind']]+=e.get('units',0)
        seed_deltas=[S.mean(x) for x in deltas.values()]
        margin_by_seed=defaultdict(list)
        for g in valid: margin_by_seed[g['seed']].append(g['margin'])
        stats={'games':len(rows),'completed':len(valid),
               'wins':sum(g['margin']>0 for g in valid),'ties':sum(g['margin']==0 for g in valid),
               'losses':sum(g['margin']<0 for g in valid),
               'mean_margin':S.mean([g['margin'] for g in valid]) if valid else None,
               'mean_cash':S.mean([g['cash'] for g in valid]) if valid else None,
               'max_action_seconds':max((g['timing']['own']['max_seconds'] for g in valid),default=0),
               'actions_over_1s':sum(g['timing']['own']['over_1s'] for g in valid),
               'runtime_errors':runtime_errors, 'events':dict(events),'event_units':dict(units)}
        if name!='mgt_m1' and seed_deltas:
            stats.update(paired_seeds=len(seed_deltas),mean_paired_margin_delta=S.mean(seed_deltas),
                         margin_delta_seed_bootstrap_95=interval(seed_deltas), mean_paired_cash_delta=S.mean(cash),
                         better_seeds=sum(x>0 for x in seed_deltas),worse_seeds=sum(x<0 for x in seed_deltas),
                         equal_seeds=sum(x==0 for x in seed_deltas), unchanged_action_games=unchanged,
                         same_shop_games=shops_same,
                         mean_ledger_delta={kind:{k:v/len(cash) for k,v in totals.items() if v} for kind,totals in ledger_delta.items()},
                         per_seed_margin_deltas={str(k):S.mean(v) for k,v in deltas.items()})
        if stage=='direct' and valid:
            stats['mean_margin_seed_bootstrap_95']=interval([S.mean(v) for v in margin_by_seed.values()])
        result['arms'][name]=stats
    if 'mgt_exp_rotate' in result['arms'] and 'mgt_exp_hold' in result['arms']:
        hold={(g['seed'],g['seat']):g for g in games if g['agent']=='mgt_exp_hold' and g.get('completed')}
        delta=defaultdict(list)
        for g in games:
            b=hold.get((g['seed'],g['seat']))
            if g['agent']=='mgt_exp_rotate' and g.get('completed') and b:
                delta[g['seed']].append(g['margin']-b['margin'])
        if delta:
            values=[S.mean(x) for x in delta.values()]
            result['rotation_vs_hold']={'mean_margin_delta':S.mean(values),'seed_bootstrap_95':interval(values)}
    (directory/'summary.json').write_text(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage');args=p.parse_args()
    print(json.dumps(summarize(args.stage),indent=2))
