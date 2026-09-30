"""UMG output ranges and configurations at the literal pre-reveal ticks.

Replays the 30 full old-UMG games exactly. Primary bins end at states
71,143,...,719; conventional 72-action bins are independently checked against
the saved, previously field-validated segment ledgers.
"""
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/production_continuation/three_day_periods'
SOURCE = ROOT / 'results/fresh/leader_segments'
PRODUCTS = ('WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','EGG','MILK','WOOL','FERTILIZER')
FARM = ('WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','COW','SHEEP','GOOSE')
ENDPOINTS = tuple(72*(i+1)-1 for i in range(10))


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def run(job):
    eid, seat = job
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    from analyze_leader_segments import board
    path = ROOT / f'data/leaders_20260917/episode-{eid}-replay.json'
    source = read(SOURCE / f'segments-{eid}.json')
    raw = path.read_bytes()
    assert sha256(raw).hexdigest() == source['replay_sha256']
    r = json.loads(raw)
    env = make('kaggriculture', configuration=r['configuration'], info={'seed':r['info']['seed']})
    original_unit, original_interpreter = E._apply_unit_action, env.interpreter
    active, current_step, own_farm = [False], [0], [None]
    aligned = [Counter() for _ in range(10)]
    conventional = [Counter() for _ in range(10)]
    def interpreter(state, environment):
        current_step[0] = int(state[0].observation.step)
        farms = getattr(state[0].observation, 'farms', []) or []
        own_farm[0] = farms[seat] if seat < len(farms) else None
        active[0] = True
        try:
            return original_interpreter(state, environment)
        finally:
            active[0] = False
    def unit(farm, private, idx, action, *args, **kwargs):
        track = (active[0] and farm is own_farm[0] and idx < len(private['inventories'])
                 and action and action[0] in ('HARVEST','COLLECT_FERTILIZER'))
        before = dict(private['inventories'][idx]) if track else {}
        result = original_unit(farm, private, idx, action, *args, **kwargs)
        if track:
            after = private['inventories'][idx]
            for product in PRODUCTS:
                q = after.get(product,0)-before.get(product,0)
                if q > 0:
                    t = current_step[0]
                    aligned[min(9,(t+1)//72)][product] += q
                    conventional[min(9,t//72)][product] += q
        return result
    def player(i):
        return lambda obs: deepcopy(r['steps'][int(obs['step'])+1][i]['action'])
    E._apply_unit_action, env.interpreter = unit, interpreter
    try:
        env.run([player(0),player(1)])
    finally:
        E._apply_unit_action, env.interpreter = original_unit, original_interpreter
    assert len(env.steps)==720 and all(s.status=='DONE' for s in env.state)
    assert [s.reward for s in env.state] == r['rewards']
    for i in range(10):
        expected = source['seats'][seat]['segments'][i]['physical']
        assert all(conventional[i][p] == expected.get('produced:'+p,0) for p in PRODUCTS), (eid,i)
    assert sum(aligned, Counter()) == sum(conventional, Counter())
    segments = []
    for i,t in enumerate(ENDPOINTS):
        obs = r['steps'][t][seat]['observation']
        live = env.steps[t][seat].observation
        assert all(live[field]==obs[field] for field in ('farms','private','market','town')), (eid,t)
        farm = obs['farms'][seat]
        c = board(farm)
        assert sum(c.values())==100
        cohorts, held_yield = Counter(), Counter()
        for row in farm['tiles']:
            for tile in row:
                if not isinstance(tile,dict):
                    continue
                if tile.get('crop'):
                    cohorts[tile['crop']+':age'+str(t//24-tile['planted_day'])] += 1
                    held_yield[tile['crop']] += tile.get('yield_units',0)
                elif tile.get('animal'):
                    cohorts[tile['animal']+':age'+str(t//24-tile['placed_day'])] += 1
                    held_yield[E.ANIMALS[tile['animal']]['product']] += tile.get('yield_units',0)
        expected_shops = min(8,(t//24)//3)
        assert len(obs['town']['unlocked_shops']) == expected_shops
        segments.append(dict(segment=i, nominal_days=[i*3,i*3+2], end_tick=t,
            output=dict(aligned[i]), conventional_three_day_output=dict(conventional[i]),
            configuration=c, crop_and_animal_ages=dict(cohorts), unharvested_yield=dict(held_yield),
            cash=farm['money'], hands=len(farm['hands']), quadrants=len(farm['unlocked_quadrants']),
            shed=obs['private']['shed'], seeds=obs['private']['seeds'],
            shops=obs['town']['unlocked_shops'], prices=obs['market']['prices'], tiles=farm['tiles']))
    out = dict(episode=eid, submission=56266758, seat=seat, opponent=r['info']['TeamNames'][1-seat],
               replay_sha256=source['replay_sha256'], segments=segments,
               validation='Final scores, 10 full snapshots, all 90 conventional product totals, season output totals checked')
    (OUT / f'game-{eid}.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    return out


def stats(values):
    return dict(min=min(values),max=max(values),mean=mean(values),median=median(values))


def interval(s):
    return str(s['min']) if s['min']==s['max'] else f"{s['min']}–{s['max']}"


def report(games):
    result = dict(games=len(games), submission=56266758, scope='30 full UMG replays, not all 584 compact tapes',
        output_definition='Successful harvest/collection into worker inventory; excludes bought goods, sales and unharvested biological yield',
        boundary_definition='Pre-reveal observations 71,143,...,719. Production accumulated between those snapshots; first interval has71 actions, later intervals72.',
        segments=[])
    for i in range(10):
        rs=[g['segments'][i] for g in games]
        hist=Counter(json.dumps({k:r['configuration'].get(k,0) for k in FARM},sort_keys=True) for r in rs)
        result['segments'].append(dict(segment=i,nominal_days=[i*3,i*3+2],end_tick=ENDPOINTS[i],
            output={p:stats([r['output'].get(p,0) for r in rs]) for p in PRODUCTS},
            conventional_output={p:stats([r['conventional_three_day_output'].get(p,0) for r in rs]) for p in PRODUCTS},
            configuration={p:stats([r['configuration'].get(p,0) for r in rs]) for p in (*FARM,'EMPTY','WEED','LOCKED','EMPTY_PASTURE','EMPTY_COOP')},
            resources={p:stats([r[p] for r in rs]) for p in ('cash','hands','quadrants')},
            distinct_crop_herd_count_configurations=len(hist),
            most_common_observed_configuration=json.loads(hist.most_common(1)[0][0]),
            most_common_configuration_frequency=hist.most_common(1)[0][1]))
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# UMG: production ranges and pre-reveal farm configurations','',
        'Thirty full replays of submission **56266758**. Values are observed **minimum–maximum**, including zero; a single number means every game agrees. These are sample ranges, not guarantees or confidence intervals.','',
        '## Exact timing','',
        'Snapshots are ticks **71, 143, 215, 287, 359, 431, 503, 575, 647, 719**, immediately before the next three-day boundary. New shops reveal at ticks 72 through 576 in steps of 72; the eight-shop cap prevents further reveals at days 27 and 30. Tick 719 is the final recorded state.','',
        'Production is aligned to these exact snapshots: action outcomes 1–71, 72–143, …, 648–719. The first bin has 71 executed actions and the remaining bins have 72. The period labels below are calendar labels; strict conventional three-day totals are also retained in the JSON. This avoids mixing a post-reveal output total with a pre-reveal configuration.','',
        '**Output means successfully harvested/collected goods**, before subsequent use, sales or overflow loss. Purchased wheat is excluded. Product still held on plants/animals is recorded separately in each game file.','',
        '## Harvested/collected output per period','']
    def table(fields,source):
        lines.append('| Days | '+' | '.join(fields)+' |')
        lines.append('|---|'+'---:|'*len(fields))
        for row in result['segments']:
            lo,hi=row['nominal_days']
            lines.append(f'| {lo}–{hi} | '+' | '.join(interval(row[source][p]) for p in fields)+' |')
        lines.append('')
    table(PRODUCTS,'output')
    lines.extend(['## Standing crops and animals at the pre-reveal tick','',
        'Crop values count occupied crop tiles, including immature plants; animal values count living animals. Ranges are marginal: combining all maxima does **not** describe a feasible farm. Ages and actual tile grids are retained in the per-game records.',''])
    table(FARM,'configuration')
    lines.extend(['## Remaining capacity and resources',''])
    table(('EMPTY','WEED','LOCKED','EMPTY_PASTURE','EMPTY_COOP'),'configuration')
    table(('cash','hands','quadrants'),'resources')
    lines.extend(['## Variation in farm composition','', '| Days | Distinct crop/herd count configurations | Most frequent configuration: games |','|---|---:|---:|'])
    for row in result['segments']:
        lo,hi=row['nominal_days']
        lines.append(f"| {lo}–{hi} | {row['distinct_crop_herd_count_configurations']} | {row['most_common_configuration_frequency']}/30 |")
    lines.extend(['','## Validation and scope','',
        'Each game was rerun with its original recorded actions in the official engine. Final scores and all ten complete checkpoint observations reproduced; conventional production totals matched all saved segment-ledger product counts. Total production agrees under both boundary conventions. Harvest counting happens inside the engine before midnight inventory resets.','',
        'The 584 compact tapes retain day-start boards but lack these exact pre-reveal observations. Both tables therefore use the same 30 full replays rather than mixing sample populations or shifting the configuration by one tick.','',
        'Artifacts: `results/fresh/production_continuation/three_day_periods/summary.json` and `game-<episode>.json`. Script: `scripts/summarize_umg_three_day_periods.py`.'])
    (ROOT/'docs/umg_three_day_periods.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(games=len(games),report='docs/umg_three_day_periods.md')))


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    sample=read(SOURCE/'sample.json')
    jobs=[(e['id'],seat) for e in sample['sample'] for seat,a in enumerate(e['agents']) if a['sub']==56266758]
    assert len(jobs)==30 and len({e for e,s in jobs})==30
    games=[]
    with ProcessPoolExecutor(max_workers=3,max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(run,j) for j in jobs]):
            row=future.result();games.append(row);print('validated',row['episode'],flush=True)
    report(sorted(games,key=lambda g:g['episode']))
