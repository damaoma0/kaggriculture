"""One reproducible detailed game from the frozen comparison panel."""
import json,random
from collections import Counter
from compare_router_refresh import ROOT,OUT,PATHS,load,Ledger

def main():
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    seed=133000
    own=load('trace_selected',PATHS['selected']);other=load('trace_v45',PATHS['v45'])
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    schedule=random.Random(seed^0xA171).choices(sorted(E.SHOPS),k=8);original=E._end_of_day
    def end(state,environment,day):
        original(state,environment,day);shops=state[0].observation.town.unlocked_shops;shops[:]=schedule[:len(shops)]
    E._end_of_day=end
    def a(o):return own.agent(o)
    def b(o):return other.agent(o)
    try:
        with Ledger(E) as ledger:env.run([a,b])
    finally:E._end_of_day=original
    expected=json.loads((OUT/'games/randomshops-133000-0-selected-v45.json').read_text())
    assert env.state[0].reward==expected['cash'] and env.state[1].reward==expected['opponent_cash']
    rows=[]
    for t in (24,72,144,216,288,432,576,696,719):
        farms=[]
        for f in env.steps[t][0].observation.farms:
            tiles=[tile for row in f['tiles'] for tile in row if isinstance(tile,dict)]
            farms.append({'cash':f.money,'animals':Counter(x['animal'] for x in tiles if x.get('animal')),'crops':Counter(x['crop'] for x in tiles if x.get('crop')),'land':len(f.unlocked_quadrants)})
        rows.append({'step':t,'farms':farms})
    result={'seed':seed,'shops':schedule,'ledger':ledger.data,'checkpoints':rows,'first_actions':[s.action for s in env.steps[1]],'telemetry':getattr(other.agent,'telemetry',{})}
    (OUT/'trace_v45.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
