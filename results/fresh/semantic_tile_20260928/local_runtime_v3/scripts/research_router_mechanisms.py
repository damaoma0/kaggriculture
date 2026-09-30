"""Research-only V45 mechanism ablations; never alters frozen agent sources."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
from statistics import mean
import json, random, time
from market_corpus import ROOT, load
from evaluate_boards import Ledger
from compare_router_refresh import PATHS

OUT = ROOT / 'results/fresh/router_mechanisms'
VARIANTS = ('full', 'no_tomatoes', 'no_reservations', 'no_terminal', 'no_flip', 'combined_off')

def jobs():
    return [(seed, seat, opponent, variant) for seed in range(135000, 135008)
            for seat in (0, 1) for opponent in ('selected', 'twocoins') for variant in VARIANTS]

def run(job):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    seed, seat, opponent, variant = job
    own = load('mechanism_own', PATHS['v45'])
    rival = load('mechanism_rival', PATHS[opponent])
    audit = {'eligible_tomato_calls': 0, 'blocked_terminal_calls': 0, 'blocked_reservation_calls': 0}
    qualifies = own._v219_qualifies
    def qualified(obs, native):
        result = qualifies(obs, native)
        audit['eligible_tomato_calls'] += int(result)
        return False if variant in ('no_tomatoes', 'combined_off') else result
    own._v219_qualifies = qualified
    if variant in ('no_reservations', 'combined_off'):
        def reserve(obs, action):
            audit['blocked_reservation_calls'] += 1
            return action
        own._r36_reserve = reserve
    if variant in ('no_terminal', 'combined_off'):
        def shadow(obs, config):
            audit['blocked_terminal_calls'] += 1
            return None
        own._shadow_terminal = shadow
    if variant in ('no_flip', 'combined_off'):
        own.agent = own._OPEN_PARENT
    env = make('kaggriculture', configuration={'seed': seed, 'episodeSteps': 720})
    schedule = random.Random(seed ^ 0xA171).choices(sorted(E.SHOPS), k=8)
    original = E._end_of_day
    def end(state, environment, day):
        original(state, environment, day)
        shops = state[0].observation.town.unlocked_shops
        shops[:] = schedule[:len(shops)]
    E._end_of_day = end
    times = []
    def call(obs):
        start = time.perf_counter()
        action = own.agent(obs)
        times.append(time.perf_counter() - start)
        return action
    players = [None, None]
    players[seat], players[1-seat] = call, rival.agent
    try:
        with Ledger(E) as ledger:
            env.run(players)
    finally:
        E._end_of_day = original
    assert len(env.steps) == 720 and all(s.status in ('ACTIVE', 'DONE') for ss in env.steps for s in ss), (job, env.logs[-2:])
    for i in (0, 1):
        assert 3000 + sum(ledger.data[i]['revenue'].values()) - sum(ledger.data[i]['spend'].values()) == env.state[i].reward
    row = dict(zip(('seed', 'seat', 'opponent', 'variant'), job))
    row.update(cash=env.state[seat].reward, opponent_cash=env.state[1-seat].reward,
               margin=env.state[seat].reward-env.state[1-seat].reward, shops=schedule,
               ledger=ledger.data, audit=audit, max_seconds=max(times),
               telemetry=getattr(own.agent, 'telemetry', {}),
               tomato_stats=own._V219_REPORT, terminal_stats=own._UPGRADE_STATS,
               reservation_stats=own._R36_SALE_REPORT)
    (OUT / 'games' / ('-'.join(map(str, job))+'.json')).write_text(json.dumps(row, indent=2), encoding='utf-8')
    return {k: row[k] for k in ('seed', 'seat', 'opponent', 'variant', 'margin')}

def main():
    from importlib.metadata import version
    (OUT/'games').mkdir(parents=True, exist_ok=True)
    paths = [PATHS['v45'], PATHS['selected'], *PATHS['twocoins'].parent.glob('*.py'),
             PATHS['twocoins'].parent/'actions.json', PATHS['twocoins'].parent/'settings.json',
             ROOT/'scripts/research_router_mechanisms.py']
    manifest = dict(engine=version('kaggle-environments'), jobs=jobs(),
        design='Eight fresh seeds, both seats, two reactive opponents; uniform common hidden shop draws with replacement. No tuning or promotion.',
        interventions={'no_tomatoes':'Decline _v219_qualifies', 'no_reservations':'Identity _r36_reserve; preserve scheduled sales and quote ordering',
        'no_terminal':'Decline seven-turn _shadow_terminal only', 'no_flip':'Use _OPEN_PARENT, preserving prior opening',
        'combined_off':'All four interventions; not a recreation of our old parent'},
        sources={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths})
    dest=OUT/'manifest.json'
    if dest.exists(): assert json.loads(dest.read_text(encoding='utf-8')) == json.loads(json.dumps(manifest))
    else: dest.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    pending=[j for j in jobs() if not (OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=8, max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]): print(f.result(), flush=True)
    rows=[json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text(encoding='utf-8')) for j in jobs()]
    summary={}
    for opponent in ('selected','twocoins'):
        baseline={(r['seed'],r['seat']):r for r in rows if r['opponent']==opponent and r['variant']=='full'}
        for variant in VARIANTS:
            rs=[r for r in rows if r['opponent']==opponent and r['variant']==variant]
            deltas=[baseline[r['seed'],r['seat']]['margin']-r['margin'] for r in rs]
            cash=[baseline[r['seed'],r['seat']]['cash']-r['cash'] for r in rs]
            summary[opponent+'/'+variant]=dict(games=len(rs),wins=sum(r['margin']>0 for r in rs),
                mean_margin=mean(r['margin'] for r in rs), mean_cash=mean(r['cash'] for r in rs),
                full_margin_gain=mean(deltas),full_cash_gain=mean(cash),
                paired_positive=sum(d>0 for d in deltas),paired_negative=sum(d<0 for d in deltas),
                worst_full_gain=min(deltas),best_full_gain=max(deltas),
                tomato_games=sum(r['tomato_stats']['commitments']>0 for r in rs),
                terminal_stats=[r['terminal_stats'] for r in rs])
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__': main()
