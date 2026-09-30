"""Explain a small-change regression with successful physical work and cash."""
import gzip
import json
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
from research_labour_profit import Simulator, engine, economic


def run(episode,arm):
    E=engine()
    from kaggle_environments.agent import get_last_callable
    with gzip.open(ROOT/f'data/ladder_panel/56395605/{episode}.json.gz','rt',encoding='utf8') as f:
        g=json.load(f)
    source=ROOT/f'results/fresh/m1_minimal_20260922/sources/{arm}.py'
    entry=get_last_callable(source.read_text(encoding='utf8'),path=str(source))
    seat=g['seat'];actions=[None,None]
    actions[seat],actions[1-seat]=g['our_actions'],g['opp_actions']
    produced=Counter(); escaped_stock=Counter()
    with Simulator(g) as sim:
        old=E.interpreter;refresh=E._daily_refresh_animals
        def live(state,env):
            state[seat].action=entry(deepcopy(state[seat].observation),None)
            return old(state,env)
        def settle(farm,day):
            before=[(x,y,deepcopy(c)) for y,row in enumerate(farm['tiles']) for x,c in enumerate(row)
                    if isinstance(c,dict) and c.get('animal')=='SHEEP'] if sim.seats[id(farm)]==seat else []
            result=refresh(farm,day)
            for x,y,c in before:
                a=farm['tiles'][y][x]
                if a.get('animal')=='SHEEP':
                    produced[day]+=a['yield_units']-c['yield_units']
                else:
                    escaped_stock[day]+=c['yield_units']
            return result
        E.interpreter=live;E._daily_refresh_animals=settle
        try:
            r=sim.run(sim.initial,0,719,actions,capture=True)
        finally:
            E.interpreter=old;E._daily_refresh_animals=refresh
        econ=economic(r['events'],seat)
        assert 3000+sum(econ['revenue'].values())-sum(econ['spend'].values())==r['money'][seat]
        work=[x for x in r['work'] if x['seat']==seat]
        daily=defaultdict(Counter)
        for w in work:
            day=w['t']//24
            daily[day][w['cmd'][0]]+=1
            if w['cmd'][0]=='HARVEST':
                daily[day]['wool_harvested']+=w['delta'].get('WOOL',0)
            if w['cmd'][0]=='FEED':
                daily[day]['wheat_fed']-=w['delta'].get('WHEAT',0)
        private=r['state'][seat].observation.private
        harvested=sum(w['delta'].get('WOOL',0) for w in work if w['cmd'][0]=='HARVEST')
        sold=econ['units'].get('WOOL',0)
        stock=sum(inv.get('WOOL',0) for inv in [private.shed,*private.inventories])
        out=dict(episode=episode,arm=arm,cash=r['money'][seat],economy=econ,daily=daily,
                 wool_generated=sum(produced.values()),wool_harvested=harvested,wool_sold=sold,
                 wool_inventory_discarded=harvested-sold-stock,wool_inventory_remaining=stock,
                 wool_unharvested_at_escape=sum(escaped_stock.values()),work=work)
        destination=ROOT/f'results/fresh/m1_minimal_20260922/case_traces/{episode}-{arm}.json'
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(out),encoding='utf8')
        return {k:v for k,v in out.items() if k not in ('work','daily','economy')}, {d:daily[d] for d in range(25,30)}


if __name__=='__main__':
    episode=int(sys.argv[1]) if len(sys.argv)>1 else 111261836
    for arm in ('mgt_m1','mgt_micro_wool_upturn'):
        print(json.dumps(run(episode,arm)),flush=True)
