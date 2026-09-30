"""Price-impact screen for every mgt_m1 losing-game store mismatch.

Artificially add a product to the shed, or discard it after production, before
the recorded market order. This tests *market headroom only*: it supplies no
planting, animal, feed, care, transport, or cost of production. It must never be
called a feasible or optimal production policy. Both players' market prices,
cash constraints and unchanged action streams run in the official engine.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/store_mismatch_shift_20260923/headroom_active'
PRIOR = ROOT / 'results/fresh/store_mismatch_shift_20260923/headroom'
QUANTITIES = (0, 1, 2, 4, 6, 8, 12)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def screen_episode(episode, events):
    from research_labour_profit import Simulator, engine

    target = OUT/f'{episode}.json.gz'
    if target.exists():
        with gzip.open(target,'rt',encoding='utf8') as f:
            payload=json.load(f)
        assert payload['episode']==episode and len(payload['events'])==len(events)
        corrected=False
        for actual,expected in zip(payload['events'],events):
            assert actual['slot']==expected['slot']
            assert actual['source_store']==expected['source_store']
            assert actual['actual_store']==expected['actual_store']
            assert set(actual['products'])==set(expected['shop_drains_per_day'])
            for p,d in actual['products'].items():
                val=expected['shop_drains_per_day'][p]
                if d['demand_delta_per_day']!=val:
                    d['demand_delta_per_day']=val
                    corrected=True
        if corrected:
            with gzip.open(target,'wt',encoding='utf8') as f:json.dump(payload,f,separators=(',',':'))
        return {'episode':episode,'events':len(events),'cached':True}
    reusable={}
    prior=PRIOR/f'{episode}.json.gz'
    if prior.exists():
        with gzip.open(prior,'rt',encoding='utf8') as f:old=json.load(f)
        for e in old['events']:
            for p,d in e['products'].items():
                reusable[(e['slot'],p,d['mode'])]=d
    with gzip.open(ROOT/f'data/ladder_panel/56395605/{episode}.json.gz','rt',encoding='utf8') as f:
        game=json.load(f)
    seat=game['seat'];actions=[None,None]
    actions[seat],actions[1-seat]=game['our_actions'],game['opp_actions']
    by_day=defaultdict(list)
    for e in events:by_day[e['reveal_day']].append(e)
    rows=[]
    with Simulator(game) as sim:
        E=engine()
        initial=sim.initial
        cursor=0
        for day in sorted(by_day):
            start=day*24
            if start>cursor:
                prior=sim.run(initial,cursor,start,actions)
                initial=prior['state'];cursor=start
            for event in by_day[day]:
                product_curves={}
                for product,delta in event['shop_drains_per_day'].items():
                    mode='add' if delta>0 else 'discard'
                    cached=reusable.get((event['slot'],product,mode))
                    if cached is not None:
                        product_curves[product]=dict(cached,demand_delta_per_day=delta)
                        continue
                    curve=[]
                    for q in QUANTITIES:
                        changed=Counter()
                        consumed=Counter()
                        market_fn=E._process_market

                        def altered(state,env):
                            t=sim.t;d=t//24;h=t%24
                            action=state[seat].action
                            shed=state[seat].observation.private['shed']
                            if mode=='add' and d>=day and h in (1,5,9,13,17,21):
                                cycle=(h-1)//4
                                n=q//6+(1 if cycle<q%6 else 0)
                                n=min(n,max(0,100-sum(shed.values())))
                                orders=action.get('market') or []
                                same=next((o for o in orders if o and o[0]=='SELL' and o[1]==product),None)
                                if n and (same is not None or len(orders)<10):
                                    shed[product]=shed.get(product,0)+n
                                    if same is not None:same[2]+=n
                                    else:
                                        orders.append(['SELL',product,n])
                                        action['market']=orders
                                    changed[product]+=n
                            elif mode=='discard' and d>=day and q:
                                remaining=max(0,q-consumed[d])
                                if remaining and any(o and o[0]=='SELL' and o[1]==product for o in (action.get('market') or [])):
                                    n=min(remaining,shed.get(product,0))
                                    if n:
                                        shed[product]-=n
                                        changed[product]+=n
                                        consumed[d]+=n
                            return market_fn(state,env)

                        E._process_market=altered
                        try:
                            result=sim.run(initial,start,719,actions)
                        finally:
                            E._process_market=market_fn
                        if q==0:
                            assert result['money']==game['rewards'],(episode,day,product,result['money'],game['rewards'])
                        sold=Counter(item for _,s,op,item,_ in result['events'] if s==seat and op=='SELL')
                        curve.append(dict(requested_per_day=q,changed_units=changed[product],
                                          cash=result['money'][seat],opponent_cash=result['money'][1-seat],
                                          margin=result['money'][seat]-result['money'][1-seat],
                                          sold_post_reveal=sold[product]))
                    base=curve[0]
                    for x in curve:
                        x['gross_margin_delta']=x['margin']-base['margin']
                        x['gross_cash_delta']=x['cash']-base['cash']
                        x['opponent_cash_delta']=x['opponent_cash']-base['opponent_cash']
                        x['gross_margin_per_changed_unit']=(x['gross_margin_delta']/x['changed_units'] if x['changed_units'] else None)
                    product_curves[product]=dict(mode=mode,demand_delta_per_day=delta,curve=curve,
                                                 best_no_cost_grid_q=max(curve,key=lambda x:x['margin'])['requested_per_day'])
                rows.append(dict(slot=event['slot'],reveal_day=day,
                                 source_store=event['source_store'],actual_store=event['actual_store'],
                                 under2500=event['under2500'],products=product_curves))
    payload=dict(episode=episode,seed=game['seed'],seat=seat,baseline_cash=game['rewards'],
                 events=rows,validated=True,
                 interpretation='Gross market response to free delivered or discarded units. No physical production, input cost, feasible action schedule, or online policy. Event curves share the same game and can be correlated.')
    OUT.mkdir(parents=True,exist_ok=True)
    with gzip.open(target,'wt',encoding='utf8') as f:json.dump(payload,f,separators=(',',':'))
    return {'episode':episode,'events':len(events),'cached':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--limit-episodes',type=int,default=0)
    parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    audit=read(ROOT/'results/fresh/store_mismatch_shift_20260923/active_store_pairs.json')
    grouped=defaultdict(list)
    for e in audit['events']:grouped[e['episode']].append(e)
    episodes=sorted(grouped)
    if args.limit_episodes:episodes=episodes[:args.limit_episodes]
    OUT.mkdir(parents=True,exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        jobs=[pool.submit(screen_episode,e,grouped[e]) for e in episodes]
        done=0
        for f in as_completed(jobs):
            row=f.result();done+=1
            if done%5==0 or done==len(jobs):print(json.dumps({'done':done,'total':len(jobs),'latest':row}),flush=True)
    if args.limit_episodes:return
    samples=[]
    for episode in episodes:
        with gzip.open(OUT/f'{episode}.json.gz','rt',encoding='utf8') as f:r=json.load(f)
        for e in r['events']:
            for p,d in e['products'].items():
                samples.append(dict(episode=episode,slot=e['slot'],source_store=e['source_store'],
                                    actual_store=e['actual_store'],product=p,under2500=e['under2500'],**d))
    from statistics import median
    groups=defaultdict(list)
    for x in samples:groups[(x['source_store'],x['actual_store'],x['product'])].append(x)
    summary=[]
    for (source,target,p),rr in sorted(groups.items()):
        qstats={}
        for q in QUANTITIES:
            vals=[next(x for x in r['curve'] if x['requested_per_day']==q) for r in rr]
            qstats[str(q)]=dict(median_gross_margin_delta=median(x['gross_margin_delta'] for x in vals),
                                positive_margin_cases=sum(x['gross_margin_delta']>0 for x in vals),
                                median_changed_units=median(x['changed_units'] for x in vals),
                                median_gross_margin_per_changed_unit=median(x['gross_margin_per_changed_unit'] for x in vals if x['gross_margin_per_changed_unit'] is not None) if any(x['changed_units'] for x in vals) else None)
        best=max(QUANTITIES,key=lambda q:qstats[str(q)]['median_gross_margin_delta'])
        summary.append(dict(source_store=source,actual_store=target,product=p,events=len(rr),
                            mode=rr[0]['mode'],demand_delta_per_day=rr[0]['demand_delta_per_day'],
                            best_no_cost_median_grid_q=best,curve=qstats))
    result=dict(created_utc=datetime.now(timezone.utc).isoformat(),losses=len(episodes),
                mismatch_events=sum(len(grouped[e]) for e in episodes),product_event_curves=len(samples),
                quantities=list(QUANTITIES),pairs=summary,
                method='Official engine replays all recorded actions and actual shops. Before each market step, add free product to shed and sale order at six evenly spaced daily opportunities, or discard product from shed just before a planned sale. Both players receive changed market quotes. Exact base arms reproduce recorded cash.',
                caveat='This is a market-only sensitivity analysis, not an executable production shift or its optimum. Added goods cost nothing and need no land, labor, care or lead time; discarded goods save none of those costs. Multiple slot events in one game are correlated.')
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:result[k] for k in ('losses','mismatch_events','product_event_curves','quantities')}))


if __name__=='__main__':main()
