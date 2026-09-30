"""Stage 0 of the Mother-Goose-tape base: do her recorded action tapes survive OFF their own world?

Every tape gets the equilibrium opening (her turn-0/1 wheat orders replaced by one BUY of her net feed wheat on
turn 0), plays its recorded seat against a LIVE opponent (default v50_public), and is scored in four arms:
  own_rec    her own shops, her recorded weed spawns (upper bound; old tapes only - needs the spawn cache)
  own_nat    her own shops, natural weeds
  class_nat  the shops of ANOTHER of her games whose first two shops fall in the same demand class
             (strawberry-demanding count, Yarn present, milk-demanding count), natural weeds, that game's seed
  rand_nat   the shops of a random other game (any class), natural weeds
Recorded per game: margin, final cash, commands that had no effect or addressed a missing hand, and DIG
commands issued on a live plant (her recorded weed digs landing on our crops).

Output: results/fresh/mg_tape/offworld/<arm>-<tape_eid>-<world_eid>.json
Usage:  python mg_tape_offworld.py [rival] [arms=own_rec,own_nat,class_nat,rand_nat] [sets=old,new]
"""
import json, random, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from market_corpus import ROOT
import tape_vs_bench as TV

OUT = ROOT / 'results/fresh/mg_tape/offworld'
NEW_DIR = ROOT / 'data/leaders_20260919'
MG_TEAM = 16730612
STRAW = {'BRUNCH_SPOT', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP', 'FARMERS_MARKET'}
MILK = {'PIZZA_SHOP', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP'}


def games():
    """[(set, path, eid, seat)] for her old (56266758) and new (56331731/56331777) replays."""
    out = [('old', p, e, s) for p, e, s in TV.mg_games()]
    sample = json.loads((ROOT / 'results/fresh/leader_segments/sample_20260919.json').read_text(encoding='utf-8'))['sample']
    for row in sample:
        seat = next(i for i, a in enumerate(row['agents']) if a['team'] == MG_TEAM)
        out.append((f"new{row['agents'][seat]['sub']}", str(NEW_DIR / f"episode-{row['id']}-replay.json"), row['id'], seat))
    return out


def shops_of(replay):
    return [replay['steps'][min(719, d * 24)][0]['observation']['town']['unlocked_shops'] for d in range(31)]


def klass(shops):
    two = shops[:2]
    return (sum(s in STRAW for s in two), int('YARN_STORE' in two), min(2, sum(s in MILK for s in two)))


def fix_opening(tape):
    """Replace her turn-0/1 wheat orders with a single BUY of her net feed wheat at index 0 of turn 0."""
    net = 0
    for t in (0, 1):
        keep = []
        for o in (tape[t].get('market') or []):
            if len(o) >= 3 and o[1] == 'WHEAT' and o[0] in ('BUY_PRODUCT', 'SELL'):
                net += int(o[2]) if o[0] == 'BUY_PRODUCT' else -int(o[2])
            else:
                keep.append(o)
        tape[t] = dict(tape[t], market=keep)
    if net > 0:
        tape[0] = dict(tape[0], market=[['BUY_PRODUCT', 'WHEAT', net]] + tape[0]['market'])
    return net


def run(job):
    arm, rival, tape_path, tape_eid, seat, world_path, world_eid = job
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    tape_replay = json.loads(open(tape_path, encoding='utf-8').read())
    tape = [deepcopy(tape_replay['steps'][t + 1][seat]['action'] or {}) for t in range(719)]
    net = fix_opening(tape)
    world = tape_replay if world_eid == tape_eid else json.loads(open(world_path, encoding='utf-8').read())
    config, seed, shops = world['configuration'], world['info']['seed'], shops_of(world)
    del tape_replay
    spawns = None
    if arm == 'own_rec':
        cache = json.loads((TV.OUT / 'cache' / f'orig-{tape_eid}-{seat}.json').read_text(encoding='utf-8'))
        spawns = cache['logged_spawns'][seat]
    rp = ROOT / 'agents' / f'{rival}.py'
    opp = get_last_callable(rp.read_text(encoding='utf-8'), path=str(rp))
    stats = dict(dig_on_plant=0, dig_on_live=0)

    def play_tape(obs, t):
        a = deepcopy(tape[t]) if t < len(tape) else {'farmer': ['PASS'], 'hands': [], 'market': []}
        farm = obs['farms'][seat]
        pos = [farm['farmer']] + list(farm['hands'])
        cmds = [a.get('farmer')] + list(a.get('hands') or [])
        for i, c in enumerate(cmds[:len(pos)]):
            if c and c[0] == 'DIG':
                x, y = pos[i]
                tile = farm['tiles'][y][x]
                if isinstance(tile, dict) and tile.get('kind') == 'PLANT':
                    stats['dig_on_plant'] += 1
                    if tile.get('max_lifespan_step', -1) < 0 or t < tile['max_lifespan_step']:
                        stats['dig_on_live'] += 1
        return a

    players = [None, None]
    players[seat] = play_tape
    players[1 - seat] = lambda obs, t: opp(obs)
    env = make('kaggriculture', configuration=config, info={'seed': seed})
    res = TV._play(E, env, players, seat, shops, spawns, seat, seat)
    phys = res['daily'][seat][-1]['physical']
    out = dict(arm=arm, rival=rival, tape=tape_eid, world=world_eid, seat=seat, net_wheat=net,
               tape_class=None, shops=shops[30],
               final=res['final'][seat], rival_final=res['final'][1 - seat], margin=res['final'][seat] - res['final'][1 - seat],
               commands=phys.get('commands', 0), no_effect=phys.get('no_effect', 0),
               missing_worker=phys.get('missing_worker_commands', 0), effective=phys.get('effective', 0),
               revenue=res['daily'][seat][-1]['revenue'], spend=res['daily'][seat][-1]['spend'],
               cash_daily=[d['money'] for d in res['daily'][seat]], **stats)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{arm}-{rival}-{tape_eid}-{world_eid}.json').write_text(json.dumps(out), encoding='utf-8')
    return out


def main():
    rival = sys.argv[1] if len(sys.argv) > 1 else 'v50_public'
    arms = (sys.argv[2] if len(sys.argv) > 2 else 'own_rec,own_nat,class_nat,rand_nat').split(',')
    sets = (sys.argv[3] if len(sys.argv) > 3 else 'old,new').split(',')
    gs = [g for g in games() if any(g[0].startswith(s) for s in sets)]
    # first-two-shop class of every game (day-6 shops), from the events files or the replay itself
    classes = {}
    for st, path, eid, seat in gs:
        ev = ROOT / f'results/fresh/mg_policy/events-{eid}.json'
        if ev.exists():
            shops6 = json.loads(ev.read_text(encoding='utf-8'))['days'][6]['shops']
        else:
            r = json.loads(open(path, encoding='utf-8').read())
            shops6 = r['steps'][144][0]['observation']['town']['unlocked_shops']
            del r
        classes[eid] = klass(shops6)
    rng = random.Random(20260919)
    jobs = []
    for st, path, eid, seat in gs:
        same_set = [g for g in gs if g[0] == st and g[2] != eid]
        same_class = [g for g in same_set if classes[g[2]] == classes[eid]]
        for arm in arms:
            if arm == 'own_rec':
                if st != 'old':
                    continue
                w = (path, eid)
            elif arm == 'own_nat':
                w = (path, eid)
            elif arm == 'class_nat':
                if not same_class:
                    continue
                g = rng.choice(same_class); w = (g[1], g[2])
            else:
                g = rng.choice(same_set); w = (g[1], g[2])
            job = (arm, rival, path, eid, seat, w[0], w[1])
            if not (OUT / f'{arm}-{rival}-{eid}-{w[1]}.json').exists():
                jobs.append(job)
    print(f'{len(jobs)} games; classes: { {k: sum(1 for v in classes.values() if v == k) for k in sorted(set(classes.values()))} }', flush=True)
    with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
        futures = {pool.submit(run, j): j for j in jobs}
        for f in as_completed(futures):
            try:
                r = f.result()
                print(f"{r['arm']:9s} tape {r['tape']} world {r['world']}: margin {r['margin']:+9.0f} no-effect {r['no_effect']:4d} "
                      f"missing {r['missing_worker']:4d} dig-on-live {r['dig_on_live']}", flush=True)
            except Exception as exc:
                print(f'FAILED {futures[f][0]} {futures[f][3]}: {type(exc).__name__}: {exc}', flush=True)


if __name__ == '__main__':
    main()
