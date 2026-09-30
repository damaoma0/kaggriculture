"""Read-only, serial audit of recent public Kaggriculture openings.

Uses an isolated output directory. Verifies recorded actions in the engine;
does not edit playing policies, submit agents, or simulate counterfactual policies.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import statistics
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/leader_opening_review_20260924_01a0'


def write(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def api_client():
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    return api


def snapshot():
    from kagglesdk.competitions.types.competition_api_service import ApiGetLeaderboardRequest
    api = api_client()
    captured = datetime.now(timezone.utc).isoformat()
    with api.build_kaggle_client() as client:
        req = ApiGetLeaderboardRequest()
        req.competition_name = 'kaggriculture'
        api._set_paging(req, 10, None)
        response = client.competitions.competition_api_client.get_leaderboard(req)
    rows = [dict(rank=i+1, team_id=r.team_id, team=r.team_name, score=str(r.score),
                 submission_date=str(r.submission_date))
            for i, r in enumerate(response.submissions)]
    result = dict(captured_utc=captured, leaderboard=rows, inventory=[])
    write('snapshot.json', result)
    print(json.dumps(dict(captured_utc=captured, leaderboard=rows), ensure_ascii=False), flush=True)
    for row in rows[:6]:
        subs = api.competition_team_submissions(int(row['team_id']))
        values = [dict(id=int(s.id), submitted=str(s.date_submitted), score=str(s.public_score)) for s in subs]
        def score(s):
            try:
                return float(s['score'])
            except (ValueError, TypeError):
                return -1e9
        values.sort(key=lambda s: s['submitted'], reverse=True)
        best = max(values, key=score)
        latest = values[0]
        # Include the current highest-scoring submission and the latest one when distinct.
        chosen = [best] + ([latest] if latest['id'] != best['id'] else [])
        item = dict(**row, submissions=values, selected=chosen, episodes={})
        for sub in chosen:
            eps = api.competition_list_episodes(sub['id'])
            complete = [e for e in eps if 'COMPLETED' in str(e.state)]
            complete.sort(key=lambda e: str(e.create_time), reverse=True)
            item['episodes'][str(sub['id'])] = [dict(
                id=int(e.id), created=str(e.create_time),
                agents=[dict(submission_id=a.submission_id, seat=a.index,
                             team_id=a.team_id, team=a.team_name, reward=a.reward)
                        for a in e.agents]) for e in complete]
        result['inventory'].append(item)
        write('snapshot.json', result)
        print(json.dumps(dict(team=row['team'], selected=chosen,
                              completed={k: len(v) for k,v in item['episodes'].items()}), ensure_ascii=False), flush=True)


def parse_replay(path, metadata):
    from analyze_openings_2026 import count_engine_tiles, extract_orders
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    r = json.loads(raw)
    del raw
    steps = r['steps']
    record = dict(episode=int(r['info']['EpisodeId']), seed=r['info'].get('seed'),
                  teams=r['info']['TeamNames'], statuses=r['statuses'], rewards=r['rewards'],
                  module_version=r['module_version'], replay_sha256=digest,
                  metadata=metadata, steps=len(steps), per_seat={})
    for seat in (0, 1):
        actions = [s[seat]['action'] for s in steps[1:]]
        daily = []
        for day in range(19):
            t = day*24
            if t >= len(steps):
                break
            obs = steps[t][0]['observation']
            f = obs['farms'][seat]
            private = steps[t][seat]['observation'].get('private', {})
            cohorts = Counter()
            board = []
            for y, row in enumerate(f['tiles']):
                for x, tile in enumerate(row):
                    if not isinstance(tile, dict):
                        continue
                    species = tile.get('crop') or tile.get('animal')
                    if species:
                        born = tile.get('planted_day', tile.get('placed_day'))
                        cohorts[f'{species}:{born}'] += 1
                        board.append(dict(x=x, y=y, **tile))
            mid = steps[min(t+12, len(steps)-1)][0]['observation']['farms'][seat]
            daily.append(dict(day=day, counts=dict(count_engine_tiles(f['tiles'])), cash=f['money'],
                              quadrants=f['unlocked_quadrants'], hands_midday=len(mid['hands']),
                              shops=obs['town']['unlocked_shops'], prices=obs['market']['prices'],
                              seeds=private.get('seeds'), shed=private.get('shed'),
                              carried=private.get('inventories'), cohorts=dict(cohorts), board=board))
        first_plant = {}
        for t, states in enumerate(steps[:216]):
            for row in states[0]['observation']['farms'][seat]['tiles']:
                for tile in row:
                    if isinstance(tile, dict) and tile.get('crop'):
                        first_plant.setdefault(tile['crop'], max(0, t-1))
        record['per_seat'][str(seat)] = dict(daily=daily, first_plant_action_step=first_plant,
                                            orders=extract_orders(actions, max_day=8))
    del r, steps
    gc.collect()
    return record


def replays():
    import psutil
    api = api_client()
    snap = json.loads((OUT/'snapshot.json').read_text(encoding='utf-8'))
    profiles_path = OUT/'profiles.json'
    profiles = json.loads(profiles_path.read_text(encoding='utf-8')) if profiles_path.exists() else {}
    jobs = {}
    for team in snap['inventory']:
        for j, sub in enumerate(team['selected']):
            eps = team['episodes'][str(sub['id'])]
            for e in eps[:3 if j == 0 else 1]:
                jobs.setdefault(str(e['id']), e)
    # Existing exact profiles identify our established opening; refresh three of
    # their full records to obtain ages and private inventory on the same schema.
    old = json.loads((ROOT/'results/fresh/newphase_20260923/openings/our_full_cache.json').read_text(encoding='utf-8'))
    for eid in list(old)[:3]:
        jobs.setdefault(eid, dict(id=int(eid), source='previous own-agent sample',
                                 agents=[dict(seat=i, team=t) for i,t in enumerate(old[eid]['team_names'])]))
    write('replay_selection.json', list(jobs.values()))
    scratch = OUT/'replays'
    scratch.mkdir(exist_ok=True)
    for eid, metadata in jobs.items():
        if eid in profiles:
            continue
        deadline = time.monotonic()+120
        while psutil.virtual_memory().available < 2.6e9:
            if time.monotonic() > deadline:
                raise RuntimeError('Insufficient spare memory for one replay parse; resume later.')
            print('Waiting for 2.6 GB available memory before serial parse.', flush=True)
            time.sleep(5)
        path = scratch/f'episode-{eid}-replay.json'
        if not path.exists():
            api.competition_episode_replay(int(eid), str(scratch), quiet=True)
        record = parse_replay(path, metadata)
        profiles[eid] = record
        write('profiles.json', profiles)
        # Retain these bounded source files for the subsequent verified ledger audit.
        print(json.dumps(dict(episode=eid, teams=record['teams'], statuses=record['statuses'],
                              day6={s: v['daily'][6]['counts'] if len(v['daily']) > 6 else None
                                    for s,v in record['per_seat'].items()}), ensure_ascii=False), flush=True)


def audit_ledgers():
    """Re-execute both recorded streams through D18; verify every physical state.

    This verifies historical transactions, not counterfactual opening value.
    """
    import psutil
    from kaggle_environments.envs.kaggriculture import kaggriculture as engine
    from kaggle_environments.utils import structify
    from evaluate_boards import Ledger
    profiles = json.loads((OUT/'profiles.json').read_text(encoding='utf-8'))
    target = OUT/'ledger_audit.json'
    audits = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    engine_path = Path(engine.__file__)
    for eid, profile in profiles.items():
        if eid in audits and audits[eid]['verified_transitions'] >= 432:
            continue
        deadline = time.monotonic()+120
        while psutil.virtual_memory().available < 2.6e9:
            if time.monotonic() > deadline:
                raise RuntimeError('Insufficient memory for serial ledger audit; resume later.')
            print('Waiting for spare memory before ledger audit.', flush=True)
            time.sleep(5)
        path = OUT/'replays'/f'episode-{eid}-replay.json'
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == profile['replay_sha256']
        r = json.loads(data)
        del data
        state = structify(deepcopy(r['steps'][0]))
        env = SimpleNamespace(done=False, configuration=structify(r['configuration']), info=r['info'])
        daily, sales = [], [[], []]
        with Ledger(engine) as ledger:
            daily.append(dict(day=0, seats=deepcopy(ledger.data)))
            for t in range(min(432, len(r['steps'])-1)):
                before = deepcopy(ledger.data)
                for seat in (0, 1):
                    state[seat].action = deepcopy(r['steps'][t+1][seat]['action'])
                    state[seat].observation.step = t
                state = engine.interpreter(state, env)
                for seat in (0, 1):
                    for key in ('farms', 'market', 'town', 'private'):
                        assert state[seat].observation[key] == r['steps'][t+1][seat]['observation'][key], (eid,t,seat,key)
                    row = ledger.data[seat]
                    cash = state[0].observation.farms[seat]['money']
                    assert 3000+sum(row['revenue'].values())-sum(row['spend'].values()) == cash, (eid,t,seat,'cash')
                    for product, units in row['sold_units'].items():
                        delta = units-before[seat]['sold_units'][product]
                        if delta:
                            sales[seat].append(dict(step=t, day=t//24, hour=t%24, product=product, units=delta,
                                                    revenue=row['revenue'][product]-before[seat]['revenue'][product]))
                if (t+1)%24 == 0:
                    daily.append(dict(day=(t+1)//24, seats=deepcopy(ledger.data)))
        audits[eid] = dict(verified_transitions=min(432,len(r['steps'])-1),
                           verified_fields=['farms','market','town','private'],
                           engine_source=str(engine_path), engine_sha256=hashlib.sha256(engine_path.read_bytes()).hexdigest(),
                           daily=daily, sales=sales)
        write('ledger_audit.json', audits)
        print(json.dumps(dict(episode=eid, transitions=audits[eid]['verified_transitions'],
                              day6=[v['revenue'] for v in daily[6]['seats']])), flush=True)
        del r, state
        gc.collect()


def summaries():
    snap = json.loads((OUT/'snapshot.json').read_text(encoding='utf-8'))
    profiles = json.loads((OUT/'profiles.json').read_text(encoding='utf-8'))
    ledgers = json.loads((OUT/'ledger_audit.json').read_text(encoding='utf-8'))
    groups = []
    for team in snap['inventory']:
        for j, sub in enumerate(team['selected']):
            ids = [str(e['id']) for e in team['episodes'][str(sub['id'])][:3 if j == 0 else 1]]
            members = []
            for eid in ids:
                meta = profiles[eid]['metadata']
                seat = next(a['seat'] for a in meta['agents'] if int(a['submission_id']) == sub['id'])
                members.append((eid,seat))
            groups.append(dict(team=team['team'], rank=team['rank'], submission=sub,
                               role='best-rated' if j == 0 else 'latest, not best-rated', members=members))
    ours = [(eid, p['teams'].index('Ghost Rule')) for eid,p in profiles.items() if 'Ghost Rule' in p['teams']]
    groups.append(dict(team='Ghost Rule established opening', role='historical own baseline', members=ours))
    for group in groups:
        group['n'] = len(group['members'])
        group['daily'] = []
        for day in (1,3,6,9,12,15,18):
            members = [(profiles[e]['per_seat'][str(s)]['daily'][day],ledgers[e]['daily'][day]['seats'][s])
                       for e,s in group['members']]
            def stats(values):
                return dict(mean=statistics.mean(values), min=min(values), max=max(values))
            row = dict(day=day, cash=stats([p['cash'] for p,l in members]),
                       counts={k:stats([p['counts'].get(k,0) for p,l in members])
                               for k in ('COW','SHEEP','GOOSE','STRAWBERRY','WHEAT','MELON','TOMATO','CARROT')},
                       seeds={k:stats([p['seeds'].get(k,0) for p,l in members])
                              for k in ('WHEAT','STRAWBERRY','CARROT')},
                       shed_wheat=stats([p['shed'].get('WHEAT',0) for p,l in members]))
            for ledger_key in ('revenue','sold_units','spend'):
                keys=sorted({k for p,l in members for k in l[ledger_key]})
                row[ledger_key]={k:stats([l[ledger_key].get(k,0) for p,l in members]) for k in keys}
            group['daily'].append(row)
        group['episodes'] = []
        for eid, seat in group['members']:
            p=profiles[eid]['per_seat'][str(seat)]
            sales=ledgers[eid]['sales'][seat]
            first_sales={}
            for sale in sales:
                first_sales.setdefault(sale['product'],sale)
            group['episodes'].append(dict(episode=eid,seat=seat,shops=p['daily'][6]['shops'],
                                           first_plant=p['first_plant_action_step'],first_sales=first_sales,
                                           day6_cohorts=p['daily'][6]['cohorts']))
    result=dict(captured_utc=snap['captured_utc'], unique_replays=len(profiles),
                verified_transitions=sum(a['verified_transitions'] for a in ledgers.values()), groups=groups)
    write('summary.json',result)
    for g in groups:
        d=g['daily'][2]
        print(json.dumps(dict(team=g['team'],role=g['role'],n=g['n'],
                              day6_counts={k:v['mean'] for k,v in d['counts'].items()},cash=d['cash'],
                              first_strawberry_sales=[e['first_sales'].get('STRAWBERRY') for e in g['episodes']]),ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['snapshot', 'replays', 'profiles', 'ledgers', 'summary'])
    args = parser.parse_args()
    if args.stage == 'snapshot':
        snapshot()
    elif args.stage == 'replays':
        replays()
    elif args.stage == 'profiles':
        profiles=json.loads((OUT/'profiles.json').read_text(encoding='utf-8'))
        for eid, old in list(profiles.items()):
            profiles[eid]=parse_replay(OUT/'replays'/f'episode-{eid}-replay.json', old['metadata'])
        write('profiles.json',profiles)
    elif args.stage == 'ledgers':
        audit_ledgers()
    elif args.stage == 'summary':
        summaries()


if __name__ == '__main__':
    main()
