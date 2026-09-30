"""Per-step market / cash / order-fill panel of DSM's 108 recorded episodes (109 DSM farm-games), for the
price-awareness study (scripts/analyze_price_awareness.py).

Each step t of a replay is re-resolved with the engine's own functions (data/kaggriculture.py, engine 1.32.7):
unit actions of both players, then the interleaved market, then town consumption, from the recorded state steps[t]
and the recorded actions steps[t+1]. Every commit is logged, so we know exactly which orders filled, how many
units, at what price, for BOTH players. The simulated money and market inventory are checked against the recorded
steps[t+1] (mismatch counts are stored; they should be 0).

One replay at a time (32 MB each), gated on psutil free memory >= 2.5 GB, del + gc after each. Output: one small
gzip JSON per episode under results/fresh/newphase_20260923/price_awareness/replay_extract/<episode>.json.gz with
  episode, names, dsm_seats, seed, final_money,
  prices[t] (9 products at obs t, PRODUCTS order), inventory_day[d] (market inventory at day start),
  money[p][t], hands[p][t], day_state[p][d] (counts, empty structures, weeds, quadrants, seeds, shed at day start),
  orders[p] = [[t, op, item, requested_units, filled_units, coins], ...] (op HIRE / BUY_LAND use units=1 per order),
  dropped[p] = [[t, n_orders_past_10], ...], plant[p] = [[t, crop, n]], place[p] = [[t, animal, n]],
  check = {money_mismatch, inventory_mismatch, steps}
"""
import copy, gc, gzip, json, sys, time, types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/newphase_20260923/price_awareness/replay_extract'
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]
CROPS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]
ANIMALS = ["SHEEP", "COW", "GOOSE"]


def load_engine():
    if 'kaggle_environments.utils' not in sys.modules:       # the engine copy only needs resolve_episode_seed
        pkg = types.ModuleType('kaggle_environments'); ut = types.ModuleType('kaggle_environments.utils')
        ut.resolve_episode_seed = lambda *a, **k: 0
        pkg.utils = ut
        sys.modules['kaggle_environments'] = pkg; sys.modules['kaggle_environments.utils'] = ut
    src = (ROOT / 'data/kaggriculture.py').read_text(encoding='utf-8')
    src = src.split('json_path = path.abspath')[0]              # skip the spec / renderer tail (needs the package json)
    K = types.ModuleType('kagg_engine'); K.__file__ = str(ROOT / 'data/kaggriculture.py')
    exec(compile(src, K.__file__, 'exec'), K.__dict__)
    return K


class NS:
    def __init__(self, **kw): self.__dict__.update(kw)


def tile_sig(t):
    if not isinstance(t, dict):
        return t
    if t.get('kind') == 'PLANT':
        return ('P', t['crop'], t.get('planted_day'))
    return (t.get('kind'), t.get('animal'))


def day_state(farm, private):
    c = {}
    for row in farm['tiles']:
        for t in row:
            if t == 'LOCKED' or t is None:
                continue
            k = t.get('kind')
            if k == 'PLANT':
                c[t['crop']] = c.get(t['crop'], 0) + 1
            elif k == 'WEED':
                c['WEED'] = c.get('WEED', 0) + 1
            elif k in ('COOP', 'PASTURE'):
                key = t['animal'] if t.get('animal') else 'EMPTY_' + k
                c[key] = c.get(key, 0) + 1
    return dict(counts=c, quadrants=len(farm['unlocked_quadrants']), money=farm['money'],
                seeds={k: v for k, v in (private.get('seeds') or {}).items() if v},
                shed={k: v for k, v in (private.get('shed') or {}).items() if v})


def run_replay(K, path):
    r = json.loads(path.read_text(encoding='utf-8'))
    steps = r['steps']
    names = r['info'].get('TeamNames') or []
    out = dict(episode=int(path.name.split('-')[1]), names=names, seed=r['info'].get('seed'),
               dsm_seats=[i for i, n in enumerate(names) if 'DSM' in (n or '')], n_steps=len(steps),
               rewards=r.get('rewards'))
    del r
    if len(steps) < 720:
        return out
    obs = lambda t, p: steps[t][p]['observation']
    out['prices'] = [[obs(t, 0)['market']['prices'][x] for x in PRODUCTS] for t in range(720)]
    out['inventory_day'] = [[obs(d * 24, 0)['market']['inventory'][x] for x in PRODUCTS] for d in range(30)]
    out['shops_day'] = [list(obs(d * 24, 0)['town']['unlocked_shops']) for d in range(30)]
    out['money'] = [[obs(t, 0)['farms'][p]['money'] for t in range(720)] for p in (0, 1)]
    out['hands'] = [[len(obs(t, 0)['farms'][p]['hands']) for t in range(720)] for p in (0, 1)]
    out['day_state'] = [[day_state(obs(d * 24, 0)['farms'][p], obs(d * 24, p)['private']) for d in range(30)]
                        + [day_state(obs(719, 0)['farms'][p], obs(719, p)['private'])] for p in (0, 1)]
    out['final_money'] = [obs(719, 0)['farms'][p]['money'] for p in (0, 1)]

    log = []
    pid = {}
    orig_commit, orig_hire, orig_land = K._commit_unit, K._do_hire, K._do_buy_land

    def commit(op, item, price, farm, private, market, shed_capacity=100):
        ok = orig_commit(op, item, price, farm, private, market, shed_capacity)
        log.append((pid[id(farm)], op, item, price if ok else 0, ok))
        return ok

    def hire(farm, private, board_size, mult=1):
        m0, n0 = farm['money'], farm['hires_today']
        orig_hire(farm, private, board_size, mult)
        log.append((pid[id(farm)], 'HIRE', '', m0 - farm['money'], farm['hires_today'] > n0))

    def land(farm, board_size):
        m0, n0 = farm['money'], len(farm['unlocked_quadrants'])
        orig_land(farm, board_size)
        log.append((pid[id(farm)], 'BUY_LAND', '', m0 - farm['money'], len(farm['unlocked_quadrants']) > n0))

    K._commit_unit, K._do_hire, K._do_buy_land = commit, hire, land
    env = NS(configuration={})
    orders = [[], []]; dropped = [[], []]; plant = [[], []]; place = [[], []]
    mm = im = 0
    try:
        for t in range(719):
            o0 = obs(t, 0)
            farms = copy.deepcopy(o0['farms']); market = copy.deepcopy(o0['market']); town = copy.deepcopy(o0['town'])
            privs = [copy.deepcopy(obs(t, p)['private']) for p in (0, 1)]
            acts = [steps[t + 1][p].get('action') if isinstance(steps[t + 1][p].get('action'), dict) else {} for p in (0, 1)]
            day = t // 24
            for p in (0, 1):
                pid[id(farms[p])] = p
                before = [[tile_sig(x) for x in row] for row in farms[p]['tiles']]
                a = acts[p]
                fa = a.get('farmer', ['PASS']); ha = a.get('hands', [])
                ha = ha if isinstance(ha, list) else []
                dem = {}
                for u in [fa, *ha]:
                    if isinstance(u, list) and len(u) >= 2 and u[0] == 'PLANT':
                        dem[u[1]] = dem.get(u[1], 0) + 1
                seeds = privs[p].get('seeds', {})
                blocked = {c for c, n in dem.items() if n > seeds.get(c, 0)}
                allow = lambda u: ['PASS'] if isinstance(u, list) and len(u) >= 2 and u[0] == 'PLANT' and u[1] in blocked else u
                K._apply_unit_action(farms[p], privs[p], 0, allow(fa), 10, day, 24, 100)
                for hi, u in enumerate(ha):
                    K._apply_unit_action(farms[p], privs[p], hi + 1, allow(u), 10, day, 24, 100)
                pc, ac = {}, {}
                for y, row in enumerate(farms[p]['tiles']):
                    for x, tl in enumerate(row):
                        s = tile_sig(tl)
                        if s != before[y][x] and isinstance(tl, dict):
                            if tl.get('kind') == 'PLANT':
                                pc[tl['crop']] = pc.get(tl['crop'], 0) + 1
                            elif tl.get('animal') and before[y][x] != s:
                                ac[tl['animal']] = ac.get(tl['animal'], 0) + 1
                plant[p] += [[t, c, n] for c, n in pc.items()]
                place[p] += [[t, c, n] for c, n in ac.items()]
                m = a.get('market') or []
                m = m if isinstance(m, list) else []
                if len(m) > 10:
                    dropped[p].append([t, len(m) - 10])
            state = [NS(observation=NS(market=market, farms=farms, private=privs[p], town=town), action=acts[p]) for p in (0, 1)]
            log.clear()
            K._process_market(state, env)
            K._town_consume(env, state, t)
            # aggregate: requested units from the (first 10) orders, filled units / coins from the commit log
            for p in (0, 1):
                m = acts[p].get('market') or []
                m = m[:10] if isinstance(m, list) else []
                agg = {}
                for od in m:
                    if not isinstance(od, list) or not od:
                        continue
                    op = od[0]
                    if op in ('HIRE', 'BUY_LAND'):
                        key, n = (op, ''), 1
                    elif op in ('BUY_SEED', 'BUY_PRODUCT', 'BUY_ANIMAL', 'SELL') and len(od) >= 3:
                        try:
                            n = int(od[2])
                        except (TypeError, ValueError):
                            continue
                        key = (op, od[1])
                    else:
                        continue
                    agg.setdefault(key, [0, 0, 0])[0] += n
                for q, op, item, price, ok in log:
                    if q == p and ok:
                        a_ = agg.setdefault((op, item or ''), [0, 0, 0])
                        a_[1] += 1; a_[2] += price
                orders[p] += [[t, k[0], k[1], v[0], v[1], v[2]] for k, v in agg.items()]
            nxt = obs(t + 1, 0)
            for p in (0, 1):
                if abs(farms[p]['money'] - nxt['farms'][p]['money']) > 1e-6:
                    mm += 1
            if any(market['inventory'][x] != nxt['market']['inventory'][x] for x in PRODUCTS):
                im += 1
    finally:
        K._commit_unit, K._do_hire, K._do_buy_land = orig_commit, orig_hire, orig_land
    out.update(orders=orders, dropped=dropped, plant=plant, place=place,
               check=dict(money_mismatch=mm, inventory_mismatch=im, steps=719))
    del steps
    return out


def main():
    import psutil
    sys.stdout.reconfigure(encoding='utf-8')
    OUT.mkdir(parents=True, exist_ok=True)
    K = load_engine()
    paths = sorted((ROOT / 'data/dsm_replays').glob('episode-*-replay.json'))
    if len(sys.argv) > 1:
        paths = paths[:int(sys.argv[1])]
    for i, path in enumerate(paths):
        eid = path.name.split('-')[1]
        dst = OUT / f'{eid}.json.gz'
        if dst.exists():
            continue
        while psutil.virtual_memory().available / 1e9 < 2.5:
            print('waiting for memory', psutil.virtual_memory().available / 1e9, flush=True)
            time.sleep(30)
        t0 = time.time()
        rec = run_replay(K, path)
        with gzip.open(dst, 'wt', encoding='utf-8') as f:
            json.dump(rec, f, separators=(',', ':'))
        print(i, eid, rec.get('names'), rec.get('check'), f'{time.time() - t0:.1f}s', flush=True)
        del rec
        gc.collect()


if __name__ == '__main__':
    main()
