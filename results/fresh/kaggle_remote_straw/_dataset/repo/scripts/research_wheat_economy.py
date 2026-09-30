"""Research-only wheat conservation audit and frozen V45 policy ablations."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter
from hashlib import sha256
import argparse, json, random
from market_corpus import ROOT, load
from evaluate_boards import Ledger
from compare_router_refresh import PATHS

OUT=ROOT/'results/fresh/wheat_economy'
VARIANTS=('full','no_feed','no_trim','no_feed_or_trim','old_expert','fixed_route')

def stock(private):
    return private['shed'].get('WHEAT',0)+sum(inv.get('WHEAT',0) for inv in private['inventories'])

class WheatAudit:
    """Hooks only real interpreter execution, excluding policy projections."""
    def __init__(self, engine, env):
        self.E,self.env=engine,env
        self.active=False;self.seats={};self.step=0
        self.total=[Counter(),Counter()];self.rows=[{},{}]
        self.initial=None
    def add(self,seat,key,value):
        if not value:return
        self.total[seat][key]+=value
        self.rows[seat].setdefault(self.step,Counter())[key]+=value
    def __enter__(self):
        e=self.E
        self.original={key:getattr(e,key) for key in ('_apply_unit_action','_commit_unit','_end_of_day')}
        self.interpreter=self.env.interpreter
        def interpreter(state,env):
            if not state[0].observation.get('farms'):return self.interpreter(state,env)
            self.active=True;self.step=int(state[0].observation.step)
            self.seats={id(f):i for i,f in enumerate(state[0].observation.farms)}
            if self.initial is None:self.initial=[stock(s.observation.private) for s in state]
            try:
                result=self.interpreter(state,env)
                for seat,s in enumerate(result):
                    t=self.total[seat]
                    expected=self.initial[seat]+t['harvest']+t['bought']-t['sold']-t['fed']-t['discarded']
                    assert expected==stock(s.observation.private),(self.step,seat,expected,stock(s.observation.private),t)
                return result
            finally:self.active=False
        def unit(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity=100):
            if not self.active or id(farm) not in self.seats:
                return self.original['_apply_unit_action'](farm,private,idx,action,board_size,day,turns_per_day,shed_capacity)
            seat=self.seats[id(farm)];before=stock(private)
            inv_before=private['inventories'][idx].get('WHEAT',0) if idx<len(private['inventories']) else 0
            seed_before=private['seeds'].get('WHEAT',0)
            result=self.original['_apply_unit_action'](farm,private,idx,action,board_size,day,turns_per_day,shed_capacity)
            delta=stock(private)-before
            op=action[0] if action else ''
            if op=='HARVEST':self.add(seat,'harvest',delta)
            elif op=='FEED':self.add(seat,'fed',-delta)
            elif op=='DROP':self.add(seat,'discarded',-delta);self.add(seat,'manual_discard',-delta)
            else:assert delta==0,(op,delta)
            self.add(seat,'planted',seed_before-private['seeds'].get('WHEAT',0))
            if op=='PICKUP' and len(action)>1 and action[1]=='WHEAT' and idx<len(private['inventories']):
                self.add(seat,'pickup',private['inventories'][idx].get('WHEAT',0)-inv_before)
            return result
        def commit(op,item,price,farm,private,market,shed_capacity=100):
            result=self.original['_commit_unit'](op,item,price,farm,private,market,shed_capacity)
            if self.active and result and item=='WHEAT':
                seat=self.seats[id(farm)]
                if op=='BUY_PRODUCT':self.add(seat,'bought',1);self.add(seat,'purchase_cost',price)
                elif op=='SELL':self.add(seat,'sold',1);self.add(seat,'sale_revenue',price)
                elif op=='BUY_SEED':self.add(seat,'seeds_bought',1);self.add(seat,'seed_cost',price)
            return result
        def end(state,env,day):
            before=[stock(s.observation.private) for s in state]
            result=self.original['_end_of_day'](state,env,day)
            for seat,s in enumerate(state):
                loss=before[seat]-stock(s.observation.private)
                self.add(seat,'discarded',loss);self.add(seat,'night_discard',loss)
            return result
        self.env.interpreter=interpreter
        e._apply_unit_action,e._commit_unit,e._end_of_day=unit,commit,end
        return self
    def __exit__(self,*exc):
        self.env.interpreter=self.interpreter
        for key,value in self.original.items():setattr(self.E,key,value)

def configure(module,variant):
    if variant in ('no_feed','no_feed_or_trim'):module._R85_FEED=False
    if variant in ('no_trim','no_feed_or_trim'):module._r95_replenish=lambda obs,action:action
    if variant in ('old_expert','fixed_route'):
        def router(obs,step,state):
            if step>=144 and not state.get('day6'):
                shops=tuple(obs['town']['unlocked_shops'][:2])
                state['expert']='ablation_'+variant
                state['route']=module._R110_OLD_SHOPS.get(shops,0) if variant=='old_expert' else 0
                state['day6']=True
            if step>=648 and not state.get('day27'):
                state['route']=2;state['day27']=True
            return state.get('route',0)
        module._IMPL.chassis.router=router

def jobs():
    return [(s,i,o,v) for s in range(136000,136008) for i in (0,1)
            for o in ('selected','twocoins') for v in VARIANTS]

def run(job,out=OUT,parity=False):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    seed,seat,opponent,variant=job
    own=load('wheat_own',PATHS['v45']);rival=load('wheat_rival',PATHS[opponent])
    configure(own,variant)
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    schedule=random.Random(seed^0xA171).choices(sorted(E.SHOPS),k=8)
    original=E._end_of_day
    def end(state,environment,day):
        original(state,environment,day)
        shops=state[0].observation.town.unlocked_shops;shops[:]=schedule[:len(shops)]
    E._end_of_day=end
    routes=[]
    def call(obs):
        action=own.agent(obs)
        if int(obs['step']) in (144,432,648):routes.append(dict(step=int(obs['step']),**own._IMPL.chassis.players[seat]['router_state']))
        return action
    players=[None,None];players[seat]=call;players[1-seat]=rival.agent
    try:
        with Ledger(E) as ledger:
            with WheatAudit(E,env) as audit:env.run(players)
    finally:E._end_of_day=original
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss),(job,len(env.steps),env.logs[-2:])
    for i in (0,1):
        assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
        t=audit.total[i];l=ledger.data[i]
        assert t['sold']==l['sold_units'].get('WHEAT',0)
        assert t['sale_revenue']==l['revenue'].get('WHEAT',0)
        assert t['purchase_cost']==l['spend'].get('BUY_PRODUCT:WHEAT',0)
        t['initial']=audit.initial[i];t['remaining']=stock(env.state[i].observation.private)
    row=dict(zip(('seed','seat','opponent','variant'),job))
    row.update(cash=env.state[seat].reward,opponent_cash=env.state[1-seat].reward,
        margin=env.state[seat].reward-env.state[1-seat].reward,shops=schedule,routes=routes,
        ledger=ledger.data,wheat=audit.total,wheat_steps=audit.rows,telemetry=getattr(own.agent,'telemetry',{}))
    if parity:
        previous=json.loads((ROOT/'results/fresh/router_mechanisms/games'/('-'.join(map(str,job))+'.json')).read_text(encoding='utf-8'))
        for key in ('cash','opponent_cash','margin','ledger','shops'):assert row[key]==previous[key],key
        row['prior_run_parity']=True
    out.mkdir(parents=True,exist_ok=True)
    (out/('-'.join(map(str,job))+'.json')).write_text(json.dumps(row,indent=2),encoding='utf-8')
    return {k:row[k] for k in ('seed','seat','opponent','variant','margin')}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
    if args.smoke:
        print(run((135000,0,'selected','full'),OUT/'checks',parity=True));return
    from importlib.metadata import version
    (OUT/'games').mkdir(parents=True,exist_ok=True)
    paths=[PATHS['v45'],PATHS['selected'],*PATHS['twocoins'].parent.glob('*.py'),PATHS['twocoins'].parent/'actions.json',PATHS['twocoins'].parent/'settings.json',
           ROOT/'scripts/research_wheat_economy.py',ROOT/'scripts/evaluate_boards.py',ROOT/'.venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py']
    manifest=dict(engine=version('kaggle-environments'),jobs=jobs(),
        design='Eight fresh seeds, both seats, two reactive rivals, identical hidden uniform shop draws with replacement. Each-turn wheat conservation and exact cash ledgers. No tuning or promotion.',
        interventions={'no_feed':'Disable discretionary economic feed skipping only; retain native feeding',
          'no_trim':'Disable day10/11 wheat replenishment trimming only; retain supply guards and input workers',
          'no_feed_or_trim':'Both input changes disabled',
          'old_expert':'Use V39 shop-pair route lookup for all first-two-shop pairs, preserving all later overlays',
          'fixed_route':'Keep route0 through turn647 then normal terminal route2; preserve later reactive overlays'},
        sources={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths})
    dest=OUT/'manifest.json'
    if dest.exists():assert json.loads(dest.read_text(encoding='utf-8'))==json.loads(json.dumps(manifest))
    else:dest.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    pending=[j for j in jobs() if not (OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=8,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j,OUT/'games') for j in pending]):print(f.result(),flush=True)

if __name__=='__main__':main()
