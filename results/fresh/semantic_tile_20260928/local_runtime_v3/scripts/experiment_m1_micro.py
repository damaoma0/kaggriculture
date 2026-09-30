"""Small, separately frozen m1 interventions and paired diagnostic/live panels."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
import difflib
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
OUT = ROOT / 'results/fresh/m1_minimal_20260922'
ARMS = ['mgt_m1', 'mgt_micro_single', 'mgt_micro_yarn18', 'mgt_micro_wool_upturn']


def read(p):
    return json.loads(p.read_text(encoding='utf8'))


def write(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding='utf8')


def digest(b):
    return sha256(b).hexdigest()


def freeze():
    if (OUT/'design.json').exists():
        return read(OUT/'design.json')
    source = (ROOT/'agents/mgt_m1.py').read_bytes()
    assert digest(source) == '1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470'
    replacements = {
        'mgt_micro_single': (b"'min_deficit': 2", b"'min_deficit': 1",
                             'Allow one-sheep additions; retain all profit, cash, routing and staffing gates.'),
        'mgt_micro_yarn18': (b'_SHP_LOOKUP = {3: 10, 6: 9, 9: 4, 12: 2, 15: 2}',
                             b'_SHP_LOOKUP = {3: 10, 6: 9, 9: 4, 12: 2, 15: 2, 18: 2}',
                             'A D18 Yarn Store raises the target by two, as D15 does; the profit gate and D19 cutoff remain.'),
        'mgt_micro_wool_upturn': (b'    return min(today, _shp_price(item, x))',
            b"    future = _shp_price(item, x)\n"
            b"    if item == 'WOOL' and 'YARN_STORE' in ((obs.get('town') or {}).get('unlocked_shops') or []):\n"
            b"        if future > today:\n"
            b"            _shp_count('wool_upturn_quotes')\n"
            b"        return future\n"
            b"    return min(today, future)",
            'For existing sheep servicing with an observed Yarn Store, allow the existing three-day wool forecast to rise above today. Retain the 20% value discount and 1.5x wage check. No new forecast model.'),
    }
    hashes, descriptions = {}, {}
    (OUT/'sources').mkdir(parents=True, exist_ok=True)
    for arm in ARMS:
        candidate = source
        if arm != 'mgt_m1':
            old, new, description = replacements[arm]
            assert source.count(old) == 1, arm
            if b'\r\n' in source:
                new = new.replace(b'\n', b'\r\n')
            candidate = source.replace(old, new)
            descriptions[arm] = description
            target = ROOT/'agents'/f'{arm}.py'
            if target.exists():
                assert target.read_bytes() == candidate, f'Preexisting different candidate: {target}'
            target.write_bytes(candidate)
            diff = ''.join(difflib.unified_diff(source.decode().splitlines(True), candidate.decode().splitlines(True),
                                              fromfile='mgt_m1.py', tofile=f'{arm}.py', n=2))
            (OUT/f'{arm}.diff').write_text(diff, encoding='utf8')
        (OUT/'sources'/f'{arm}.py').write_bytes(candidate)
        hashes[arm] = digest(candidate)
    rng = random.Random(2026092207)
    seeds = rng.sample(range(1_900_000_000, 2_000_000_000), 36)
    audit = read(ROOT/'results/fresh/all_umg_m1/summary.json')
    available = {int(p.name.split('.')[0]) for p in (ROOT/'data/ladder_panel/56395605').glob('*.json.gz')}
    wins = sorted(e['episode'] for e in audit['episodes'] if e['margin'] > 0 and e['episode'] in available)
    historical = [111743130, 111678108, 111261836, 111262874] + rng.sample(wins, 2)
    design = dict(created_utc=datetime.now(timezone.utc).isoformat(), arms=ARMS, source_hashes=hashes,
        descriptions=descriptions, historical_diagnostic=historical, development=seeds[:12], confirmation=seeds[12:],
        seats=[0, 1], live_opponent='v56',
        hypothesis='Test three independent minimal changes against unchanged mgt_m1; do not combine them before separate evidence.',
        selection='Choose the completed, error-free development arm with the highest positive mean paired margin and positive own-cash change. If none improves, diagnose its activation and cost before proposing another narrow change. Only one unchanged arm may use the 24 confirmation seeds.',
        confirmation_rule='Report paired margin, own cash, wins, lower tail and seed-bootstrap uncertainty on all 24 fresh seeds and both seats. This is a small-change experiment, not the reserved 3000-Elo qualification.',
        limitations='Historical diagnostics replay fixed opponent actions and forced shops. Live panels use responsive V56 and natural RNG; policy changes may alter shop draws through weeds.')
    write(OUT/'design.json', design)
    return design


def historical_job(job):
    arm, episode, design = job
    target = OUT/'historical'/f'{arm}-{episode}.json'
    if target.exists():
        old = read(target)
        assert old['source_sha256'] == design['source_hashes'][arm]
        return {k:old[k] for k in ('arm','episode','completed','margin','action_changes')}
    row = dict(arm=arm, episode=episode, completed=False, source_sha256=design['source_hashes'][arm])
    log = OUT/'historical_logs'/f'{arm}-{episode}.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w', encoding='utf8') as output:
        saved = os.dup(1), os.dup(2)
        try:
            os.dup2(output.fileno(),1); os.dup2(output.fileno(),2)
            from research_labour_profit import Simulator, engine, economic
            E = engine()
            from kaggle_environments.agent import get_last_callable
            with gzip.open(ROOT/f'data/ladder_panel/56395605/{episode}.json.gz','rt',encoding='utf8') as f:
                g = json.load(f)
            path = OUT/'sources'/f'{arm}.py'
            assert digest(path.read_bytes()) == design['source_hashes'][arm]
            entry = get_last_callable(path.read_text(encoding='utf8'), path=str(path))
            seat = g['seat']; actions=[None,None]
            actions[seat], actions[1-seat] = g['our_actions'],g['opp_actions']
            changes, elapsed = [], []
            with Simulator(g) as sim:
                interpreter = E.interpreter
                def live(state, env):
                    begin=time.perf_counter()
                    action=entry(deepcopy(state[seat].observation), None)
                    elapsed.append(time.perf_counter()-begin)
                    if action != g['our_actions'][sim.t]:
                        changes.append(sim.t)
                    state[seat].action=action
                    return interpreter(state,env)
                E.interpreter=live
                try:
                    r=sim.run(sim.initial,0,719,actions)
                finally:
                    E.interpreter=interpreter
                economics=[economic(r['events'],i) for i in (seat,1-seat)]
                for i,e in zip((seat,1-seat),economics):
                    assert 3000+sum(e['revenue'].values())-sum(e['spend'].values()) == r['money'][i]
                if arm == 'mgt_m1':
                    assert not changes and r['money']==g['rewards']
                G=entry.__globals__
                row.update(completed=True, seed=g['seed'], seat=seat, cash=r['money'][seat],
                    opponent_cash=r['money'][1-seat], margin=r['money'][seat]-r['money'][1-seat],
                    recorded=g['rewards'], action_changes=len(changes), first_change=changes[0] if changes else None,
                    economics=economics, overlay=G.get('_SHP_REPORT',{}), router=G.get('_MGT_REPORT',{}),
                    max_action_seconds=max(elapsed), actions_over_1s=sum(t>1 for t in elapsed),
                    ledger_verified=True)
        except Exception:
            row['error']=traceback.format_exc()
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            os.close(saved[0]);os.close(saved[1])
    write(target,row)
    return {k:row.get(k) for k in ('arm','episode','completed','margin','action_changes','error')}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['freeze','historical','development','confirmation'])
    parser.add_argument('--candidate')
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    design=freeze()
    if args.stage=='freeze':
        print(json.dumps(design,indent=2));return
    if args.stage=='historical':
        jobs=[(a,e,design) for a in ARMS for e in design['historical_diagnostic']]
        with ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:
            for future in as_completed([pool.submit(historical_job,j) for j in jobs]):
                print(json.dumps(future.result()),flush=True)
        return
    arms=ARMS
    if args.stage=='confirmation':
        selection=read(OUT/'selection.json')
        assert args.candidate==selection['candidate'] and args.candidate in ARMS[1:]
        arms=['mgt_m1',args.candidate]
    for a in arms:
        assert digest((ROOT/'agents'/f'{a}.py').read_bytes())==design['source_hashes'][a]
    command=[sys.executable,str(ROOT/'scripts/benchmark_segment_stitch.py'),'--agents',','.join(arms),
             '--opponents','v56','--seeds',','.join(map(str,design[args.stage])),
             '--workers',str(args.workers),'--out',str(OUT/args.stage)]
    env=dict(os.environ)
    env['PYTHONPATH']=str(ROOT/'.venv/Lib/site-packages')+os.pathsep+str(ROOT/'scripts')
    subprocess.run(command,check=True,cwd=ROOT,env=env)


if __name__=='__main__':
    main()
