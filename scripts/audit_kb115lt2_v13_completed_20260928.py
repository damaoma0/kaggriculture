"""Read completed natural V13/V12 games; no engine, agents or forecasts."""
from collections import Counter,defaultdict
from pathlib import Path
import argparse
import hashlib
import json

from diagnose_v8_daily_product_flow_20260928 import animal_action_trace,flat,stocks

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path(r'C:\Users\xyygl\Documents\kaggriculture')
STUDY=MAIN/'results/fresh/semantic_strategy_20260928'
VERSIONS=('strategy_v12_kb115lt2_runtime_fast','strategy_v13_kb115lt2_harvest_exchange')
PRODUCT={'SHEEP':'WOOL','COW':'MILK','GOOSE':'EGG'}
SHED={44,45,54,55}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def difference(a,b):return {k:b.get(k,0)-a.get(k,0) for k in sorted(set(a)|set(b)) if a.get(k,0)!=b.get(k,0)}
def interval(g,s,d,key):return difference(g['daily'][s][d].get(key,{}),g['daily'][s][d+1].get(key,{}))

def all_stock_losses(g,day,trace=None):
    seat=g['case']['seat'];before=g['diagnostics'][seat][day]['current_observation'];after=g['diagnostics'][seat][day+1]['current_observation']
    opening,closing=stocks(before),stocks(after);physical=interval(g,seat,day,'physical')
    spend,sold=interval(g,seat,day,'spend'),interval(g,seat,day,'sold_units');residuals={};unknown=[];balances={}
    for p in ('WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','EGG','MILK','WOOL','FERTILIZER'):
        used=physical.get('op:FEED',0)-physical.get('no_effect:FEED',0) if p=='WHEAT' else physical.get('op:FERTILIZE',0)-physical.get('no_effect:FERTILIZE',0) if p=='FERTILIZER' else 0
        n=opening.get(p,0)+physical.get('produced:'+p,0)-sold.get(p,0)-used-closing.get(p,0)
        bought=bool(spend.get('BUY_PRODUCT:'+p,0))
        request_cap=sum(x['order'][2] for x in trace['market_requests'] if x['order'][:2]==['BUY_PRODUCT',p]) if trace is not None else None
        # Requests only bound successful purchases; they are never treated as fills.
        low=max(0,n);high=n+(request_cap if bought else 0) if not bought or request_cap is not None else None
        assert high is None or high>=low,(day,p,n,request_cap)
        exact=low if low==high else None
        balances[p]=dict(opening=opening.get(p,0),collected=physical.get('produced:'+p,0),sold=sold.get(p,0),
            consumed=used,closing=closing.get(p,0),constant_excluding_buys=n,purchase_spend=spend.get('BUY_PRODUCT:'+p,0),
            requested_buy_units_upper_bound=request_cap,discard_lower_bound=low,discard_upper_bound=high,exact_discard=exact,
            actual_buys_implied_by_conservation=exact-n if exact is not None else None)
        if not bought:
            assert n>=0;residuals[p]=n
        elif exact is None:unknown.append(p)
    # Animals also occupy the shed. These cases have no stock or purchases;
    # if that changes, refuse a total-stock claim without placement accounting.
    animals={p:dict(opening=opening.get(p,0),closing=closing.get(p,0),purchase_spend=spend.get('BUY_ANIMAL:'+p,0)) for p in PRODUCT}
    animal_zero=all(not any(r.values()) for r in animals.values())
    exacts=[r['exact_discard'] for r in balances.values()]
    return dict(discard_residuals_without_purchase=residuals,unresolved_due_to_purchase_units_not_logged=unknown,
        product_balances=balances,animal_stock_audit=animals,animal_zero_inflow_and_stock=animal_zero,
        exact_total_discard=sum(exacts) if animal_zero and all(x is not None for x in exacts) else None,
        seeds_excluded='Official engine stores seeds separately; they never enter shed or worker inventories.')

def product_flow(g,trace,day,product):
    """Full daily balance certifies no discard; hours only if sales all fill."""
    seat=g['case']['seat'];obs=g['diagnostics'][seat][day]['current_observation'];nxt=g['diagnostics'][seat][day+1]['current_observation']
    sold=interval(g,seat,day,'sold_units').get(product,0);harvested=interval(g,seat,day,'physical').get('produced:'+product,0)
    purchased=interval(g,seat,day,'spend').get('BUY_PRODUCT:'+product,0)
    assert purchased==0
    lost=stocks(obs).get(product,0)+harvested-sold-stocks(nxt).get(product,0);assert lost>=0
    requests=[r for r in trace['market_requests'] if r['order'][:2]==['SELL',product]]
    requested=sum(r['order'][2] for r in requests)
    result=dict(collected=harvested,sold=sold,revenue=interval(g,seat,day,'revenue').get(product,0),
        realized_average_price=interval(g,seat,day,'revenue').get(product,0)/sold if sold else None,
        dawn_shed=obs['private']['shed'].get(product,0),next_dawn_shed=nxt['private']['shed'].get(product,0),
        actual_discard_residual=lost,sale_request_units=requested,all_sales_filled=requested==sold,
        exact_hourly_certified=lost==0 and requested==sold)
    if not result['exact_hourly_certified']:return result
    inv=Counter({i:x.get(product,0) for i,x in enumerate(obs['private']['inventories'])});shed=obs['private']['shed'].get(product,0)
    held={x['tile']:x['dawn_yield'] for x in trace['animal_tiles'] if PRODUCT[x['species']]==product}
    byhour=defaultdict(list)
    for row in trace['commands']:byhour[row['hour']].append(row)
    sales=Counter()
    for row in requests:sales[row['hour']]+=row['order'][2]
    result['hours']=[]
    for hour in range(24):
        deliveries=[];harvests=[]
        for row in byhour[hour]:
            u,t,c=row['unit'],row['tile'],row['command'];op=c[0]
            if op=='HARVEST' and held.get(t,0):
                n=held.pop(t);inv[u]+=n;harvests.append(dict(unit=u,tile=t,units=n))
            if t in SHED:
                if c[:2]==['PICKUP',product]:
                    n=min(shed,c[2] if len(c)>2 else 1);shed-=n;inv[u]+=n
                n=inv[u] if op=='DROP' else min(inv[u],c[2] if len(c)>2 else 1) if c[:2]==['PLACE',product] else 0
                if n:inv[u]-=n;shed+=n;deliveries.append(dict(unit=u,units=n))
        before=shed;shed-=sales[hour];assert shed>=0
        result['hours'].append(dict(hour=hour,harvests=harvests,deliveries=deliveries,available_before_market=before,
            sold=sales[hour],ending_shed=shed,carried=sum(inv.values())))
    assert shed+sum(inv.values())==stocks(nxt).get(product,0)
    result['midnight_carried_units']=sum(inv.values())
    return result

def audit(case):
    paths=[STUDY/'runs'/v/'development/live'/(case+'.json') for v in VERSIONS]
    games=[json.loads(p.read_text()) for p in paths]
    assert all(g['completed'] and g['eligible'] for g in games)
    actions=[json.loads(p.with_suffix('.actions.json').read_text()) for p in paths]
    seat=games[0]['case']['seat'];assert games[0]['case']==games[1]['case']
    traces=[animal_action_trace(g,a,seat) for g,a in zip(games,actions)]
    accepted=[]
    for diag in games[1]['final_diagnostics'][str(seat)]:
        event=diag.get('harvest_exchange',{})
        if not event.get('accepted'):continue
        day=diag['day'];t=event['tile'];removed=event['removed_tile'];trace=traces[1]['days'][day]
        target=next(x for x in trace['animal_tiles'] if x['tile']==t)
        hits=[x for x in trace['commands'] if x['tile']==t and x['command']==['HARVEST']]
        assert hits and target['dawn_yield']==event['held']
        assert target['harvest_hour']==hits[0]['hour']
        removed_executions=[x for x in trace['commands'] if x['tile']==removed and x['command']==event['removed_command']]
        p=event['product'];before=games[1]['diagnostics'][seat][day]['current_observation'];after=games[1]['diagnostics'][seat][day+1]['current_observation']
        # Later dispatch may remap a route. Preserve the mismatch rather than
        # equating a planned worker id with successful execution evidence.
        row=dict(day=day,decision=event,executed_harvest=hits[0],actual_collected_units=target['dawn_yield'],
            removed_command_still_executed=removed_executions,removed_tile_before=flat(before)[removed],removed_tile_next_dawn=flat(after)[removed],
            target_next_dawn=flat(after)[t],physical_day_delta_vs_v12=difference(interval(games[0],seat,day,'physical'),interval(games[1],seat,day,'physical')),
            planned_unit_matches_actual=hits[0]['unit']==event['unit'],
            collection_day_all_stock_loss_audits={v:all_stock_losses(g,day,traces[i]['days'][day]) for i,(v,g) in enumerate(zip(VERSIONS,games))},
            collection_day_flows={v:product_flow(g,traces[i]['days'][day],day,p) for i,(v,g) in enumerate(zip(VERSIONS,games))},
            next_day_flows={v:product_flow(g,traces[i]['days'][day+1],day+1,p) for i,(v,g) in enumerate(zip(VERSIONS,games))} if day<28 else None)
        accepted.append(row)
    financial={}
    for role,s in (('own',seat),('rival',1-seat)):
        a,b=[g['daily'][s][-1] for g in games]
        goods=sorted(set(a['revenue'])|set(b['revenue']))
        financial[role]=dict(cash_delta=b['money']-a['money'],revenue_delta=difference(a['revenue'],b['revenue']),
            spend_delta=difference(a['spend'],b['spend']),products={p:dict(
            collected=[r['physical'].get('produced:'+p,0) for r in (a,b)],sold=[r['sold_units'].get(p,0) for r in (a,b)],
            revenue=[r['revenue'].get(p,0) for r in (a,b)]) for p in goods})
    first={}
    for role,s in (('own',seat),('rival',1-seat)):
        first[role]=next((dict(step=i,day=i//24,hour=i%24,v12=a,v13=b) for i,(a,b) in enumerate(zip(actions[0][s],actions[1][s])) if a!=b),None)
    return dict(case=case,source_hashes={str(p):sha(p) for p in paths+[p.with_suffix('.actions.json') for p in paths]},
        margins=[g['margin'] for g in games],margin_delta=games[1]['margin']-games[0]['margin'],
        first_action_changes=first,shop_sequences=[g['shops'] for g in games],
        shop_changes=[dict(day=(i+1)*3,v12=a,v13=b) for i,(a,b) in enumerate(zip(games[0]['shops'],games[1]['shops'])) if a!=b],
        traces_verified=[dict(early_positions=t['early_position_snapshots_verified'],daily_species_harvest_balances=t['daily_species_harvest_balances_verified']) for t in traces],
        accepted_exchanges=accepted,finances=financial,
        limitation='Accepted target collection is certified against reconstructed positions and complete daily animal-product harvest ledgers. Future sale timestamps are exact only where all daily sale requests fill and inventory balance proves zero discard. Natural shops differ, so total outcomes are not isolated feature profit.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--cases',default='live-00,live-01');p.add_argument('--output',type=Path,
        default=ROOT/'results/fresh/semantic_kb115lt2_recovery/v13_first_completed_audit.json');args=p.parse_args()
    rows=[audit(case) for case in args.cases.split(',')]
    result=dict(scope='READ_ONLY_COMPLETED_V13_NATURAL_GAME_AUDIT',new_games=0,rows=rows,
        script_sha256=sha(Path(__file__)),position_trace_source_sha256=sha(ROOT/'scripts/diagnose_v8_daily_product_flow_20260928.py'),
        engine_source_sha256=sha(MAIN/'.venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py'),
        stock_identity='discard = opening shed+carried + collected + actual buys - sold - successful FEED/FERTILIZE consumption - closing shed+carried',
        purchase_bound='Actual buys never exceed executed market request quantities (first 10 orders only). Nonnegative discard and this upper bound can certify exact buys/discard; orders are not otherwise treated as fills.')
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(args.output),sha256=sha(args.output),summary=[dict(case=r['case'],margin_delta=r['margin_delta'],
        own_cash_delta=r['finances']['own']['cash_delta'],rival_cash_delta=r['finances']['rival']['cash_delta'],
        exchanges=[dict(day=x['day'],units=x['actual_collected_units'],product=x['decision']['product'],hour=x['executed_harvest']['hour'],
            removed=x['decision']['removed_command'],removed_done=bool(x['removed_command_still_executed']),
            discard=x['collection_day_flows'][VERSIONS[1]]['actual_discard_residual']) for x in r['accepted_exchanges']]) for r in rows]),indent=2))

if __name__=='__main__':main()
