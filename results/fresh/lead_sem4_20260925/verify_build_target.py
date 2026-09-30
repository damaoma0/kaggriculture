"""Skeptic check of arms S / S0 (no games, one process): Target counts vs the semantics on 4 worlds the builder did not
use, an independent tile-leak test (own permutation + mirror, all tile-indexed fields moved) on the Target AND on the
full agent() (synthetic observations), with a negative control (arm T must change under the same permutation), the
one-day market shift checked against the tape's SELL orders, and planting-cutoff losses over all 48 worlds.
"""
import gzip
import json
import random
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import lead_sem4 as L  # noqa: E402

WORLDS = ['16770421:112612443', '16732748:112655730', '16623559:112910261', '16730612:112449129']
QUADS = ('NW', 'NE', 'SW', 'SE')


def quad(i):
    x, y = i % 10, i // 10
    return ('N' if y < 5 else 'S') + ('W' if x < 5 else 'E')


def load_tape(tid, ep):
    return json.load(gzip.open(sorted(L.lead_g1.TAPES.glob(f'{tid}_*/{ep}.json.gz'))[0], 'rt', encoding='utf-8'))


def move_tiles(sem, perm):
    """apply tile map perm (index -> index) to EVERY tile-indexed field of the semantics (recursive over lists of ints
    under known tile keys, boards as 100-lists)."""
    s = deepcopy(sem)
    for day in s['days']:
        b = day['board']
        nb = [None] * 100
        for i in range(100):
            nb[perm[i]] = b[i]
        day['board'] = nb
        for key in ('planted', 'built', 'maintenance'):
            day[key] = {k: [perm[t] for t in ts] for k, ts in day[key].items()}
        day['dug'] = [perm[t] for t in day['dug']]
        for key in ('harvested', 'animals', 'eligible'):
            v = day.get(key)
            if isinstance(v, dict):
                for k2, v2 in list(v.items()):
                    if isinstance(v2, list) and v2 and all(isinstance(x, int) and 0 <= x < 100 for x in v2) \
                            and k2 in ('tiles', 'placed', 'culled', 'lost', 'escaped', 'died'):
                        v[k2] = [perm[t] for t in v2]
    return s


def rand_perm(seed):
    rng = random.Random(seed)
    perm = {}
    for q in QUADS:
        idx = [i for i in range(100) if quad(i) == q]
        sh = idx[:]
        rng.shuffle(sh)
        perm.update(zip(idx, sh))
    return perm


def mirror_perm():
    perm = {}
    for i in range(100):
        x, y = i % 10, i // 10
        x0 = 0 if x < 5 else 5
        y0 = 0 if y < 5 else 5
        perm[i] = (y0 + (4 - (y - y0))) * 10 + (x0 + (4 - (x - x0)))     # point reflection inside the quadrant
    return perm


def tdump(T):
    def norm(v):
        if isinstance(v, Counter):
            return sorted((repr(k), n) for k, n in v.items() if n)
        if isinstance(v, dict):
            return sorted((repr(k), norm(x)) for k, x in v.items())
        if isinstance(v, (list, tuple)):
            return [norm(x) for x in v]
        return v
    return {k: norm(v) for k, v in vars(T).items()}


def agent_trace(mod, sem, cfg, lab_board, seat):
    """full agent() on a fixed synthetic observation sequence (identical for every call of this function)."""
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    mod.configure(sem, **cfg)
    farms = [E._new_farm(10, 3000), E._new_farm(10, 3000)]
    privs = [E._new_private(), E._new_private()]
    market = E._new_market()
    town = {'unlocked_shops': []}
    out = []

    def call(step):
        obs = {'step': step, 'player': seat, 'farms': farms, 'private': privs[seat], 'market': market,
               'town': town, 'day': step // 24, 'hour': step % 24, 'remainingOverageTime': 60}
        a = mod.agent(deepcopy(obs))
        out.append(json.dumps(a, sort_keys=True, default=str))
    for step in range(0, 24):
        call(step)
    # day 6: NE unlocked, NW partly planted with young wheat, 3 hands, seeds in stock
    f = farms[seat]
    f['unlocked_quadrants'] = ['NW', 'NE']
    for i in range(100):
        x, y = i % 10, i // 10
        if quad(i) == 'NE':
            f['tiles'][y][x] = None
        elif quad(i) == 'NW':
            f['tiles'][y][x] = E._new_plant('WHEAT', 4 + (i % 3), 24) if i % 4 else None
    f['money'] = 4000.0
    f['hands'] = [[4, 4] for _ in range(3)]
    privs[seat]['inventories'] = [{} for _ in range(4)]
    privs[seat]['seeds'].update({'STRAWBERRY': 8, 'WHEAT': 10, 'MELON': 4, 'TOMATO': 4, 'CARROT': 4})
    privs[seat]['shed'].update({'WHEAT': 20, 'SHEEP': 2, 'GOOSE': 2, 'COW': 1})
    for step in range(6 * 24, 6 * 24 + 24):
        call(step)
    # day 12: every quadrant, the leader's day-12 labels (same synthetic board for both runs), 10 hands
    lab_crop = {'WH': 'WHEAT', 'CA': 'CARROT', 'TO': 'TOMATO', 'ST': 'STRAWBERRY', 'ME': 'MELON'}
    f['unlocked_quadrants'] = ['NW', 'NE', 'SW', 'SE']
    for i, l in enumerate(lab_board):
        x, y = i % 10, i // 10
        if l in lab_crop:
            f['tiles'][y][x] = E._new_plant(lab_crop[l], 9 if l in ('WH', 'CA') else 4, 24)
        elif l in ('sh', 'go', 'co'):
            f['tiles'][y][x] = E._new_animal({'sh': 'SHEEP', 'go': 'GOOSE', 'co': 'COW'}[l], 3)
        elif l == 'pa':
            f['tiles'][y][x] = {'kind': 'PASTURE'}
        else:
            f['tiles'][y][x] = None
    f['money'] = 6000.0
    f['hands'] = [[4, 4] for _ in range(10)]
    privs[seat]['inventories'] = [{} for _ in range(11)]
    privs[seat]['shed'].update({'WHEAT': 30, 'FERTILIZER': 10})
    for step in range(12 * 24, 12 * 24 + 24):
        call(step)
    return out, dict(getattr(mod, '_S', {}).get('log', {}))


def main():
    errs = []
    S = L._load_module('agents/mgt_lead_sem.py', 'v_s')
    S0 = L._load_module('agents/mgt_lead_sem0.py', 'v_s0')
    TT = L._load_module('agents/mgt_lead_semT.py', 'v_t')
    print('S place_rule', S.CFG['place_rule'], '| S0', S0.CFG['place_rule'])
    for g in WORLDS:
        tid, ep = g.split(':')
        sem = L._load_sem(tid, ep)
        tape = load_tape(tid, ep)
        days = sem['days']
        n = len(days)
        T = S.Target(sem)
        e = []
        if set(vars(T)) != set(S.TARGET_FIELDS):
            e.append(f'fields {set(vars(T)) ^ set(S.TARGET_FIELDS)}')
        for d in range(n):
            if T.plant_n[d] != Counter({c: len(ts) for c, ts in days[d]['planted'].items() if ts}):
                e.append(f'plant_n d{d}')
            if Counter(c for (pd, c, k) in T.events if pd == d) != T.plant_n[d]:
                e.append(f'events d{d}')
            if T.hands[d] != days[d]['labour']['hands_present']:
                e.append(f'hands d{d}')
            if T.fert_n[d] != len(set(days[d]['maintenance'].get('FERTILIZE', []))):
                e.append(f'fert_n d{d}')
            if d < n - 1:
                lab = Counter(days[d + 1]['board'])
                if sum(T.struct_n[d].values()) != lab['co'] + lab['pa'] + lab['sh'] + lab['go']:
                    e.append(f'struct total d{d}: {dict(T.struct_n[d])} vs labels co{lab["co"]} pa{lab["pa"]} sh{lab["sh"]} go{lab["go"]}')
                if T.anim_n[d]['GOOSE'] != lab['go'] or T.anim_n[d]['SHEEP'] != lab['sh']:
                    e.append(f'anim d{d}')
                if T.struct_n[d]['COOP'] - T.anim_n[d]['GOOSE'] + T.anim_n[d]['COW'] != lab['co']:
                    e.append(f'co d{d}')
                # alive: cohort members whose tile shows the crop at the start of day d+1 (independent recount)
                for pd in range(d + 1):
                    for c, ts in days[pd]['planted'].items():
                        k = sum(1 for t in ts if days[d + 1]['board'][t] == c[:2])
                        if T.alive[d + 1].get((pd, c), 0) != k:
                            e.append(f'alive d{d + 1} {pd} {c}')
        # land: board-derived vs tape BUY_LAND order days
        bl = sorted({step // 24 for step, a in enumerate(tape['actions'])
                     for o in ((a or {}).get('market') or [])[:10] if o and o[0] == 'BUY_LAND'})
        if [T.land_day.get(q) for q in ('NE', 'SW', 'SE')] != bl[:3]:
            e.append(f'land {T.land_day} vs tape order days {bl}')
        # market shift: semantics sold_units[i] vs tape SELL order quantities on day i and day i+1 (requested)
        req = [Counter() for _ in range(31)]
        for step, a in enumerate(tape['actions']):
            for o in ((a or {}).get('market') or [])[:10]:
                if o and o[0] == 'SELL' and len(o) >= 3:
                    req[step // 24][o[1]] += int(o[2])
        dev_same = dev_next = 0
        for i, day in enumerate(days[:29]):
            su = Counter(day['market']['sold_units'])
            for p in set(su) | set(req[i]) | set(req[i + 1]):
                dev_same += abs(su[p] - req[i][p])
                dev_next += abs(su[p] - (req[i + 1][p] + (req[0][p] if i == 0 else 0)))
        # cum_sold: index i -> actual day i+1 (index 0 -> days 0 and 1); cum through day d
        for d in range(n):
            run = Counter()
            for i, day in enumerate(days):
                if max(1, i + 1) <= d:
                    run.update(day['market']['sold_units'])
            if +T.cum_sold[d] != +run:
                e.append(f'cum_sold d{d}')
        # leak: Target invariant under a random within-quadrant permutation and a within-quadrant point reflection
        for nm, perm in (('rand', rand_perm(int(ep) % 9973 + 11)), ('mirror', mirror_perm())):
            ps = move_tiles(sem, perm)
            if tdump(S.Target(ps)) != tdump(T) or tdump(S0.Target(ps)) != tdump(S0.Target(sem)):
                e.append(f'Target changes under {nm} permutation')
            # the permuted semantics really moved the leader's plan (sanity)
            moved = sum(1 for d in range(n) for c, ts in days[d]['planted'].items() for t in ts if perm[t] != t)
            if nm == 'rand' and moved == 0:
                e.append('permutation moved nothing')
        # full agent(): S and S0 identical under the permutation, T (negative control) must differ
        perm = rand_perm(int(ep) % 9973 + 11)
        ps = move_tiles(sem, perm)
        lab12 = days[12]['board']
        seat = sem['meta']['seat']
        res = {}
        for nm, mod in (('S', S), ('S0', S0), ('T', TT)):
            a1, lg1 = agent_trace(mod, sem, L.EXEC_CFG, lab12, seat)
            a2, lg2 = agent_trace(mod, ps, L.EXEC_CFG, lab12, seat)
            ndiff = sum(1 for x, y in zip(a1, a2) if x != y)
            res[nm] = (ndiff, len(a1), {k: v for k, v in lg1.items() if k.startswith(('place_', 'plant_un', 'struct_un', 'replace', 'sbuild'))})
        if res['S'][0] or res['S0'][0]:
            e.append(f"agent actions change under the permutation: S {res['S'][0]}, S0 {res['S0'][0]}")
        # paper execution (planner only, from lead_sem4._paper) days matching the leader's counts after cutoffs
        pap = {}
        for nm, mod in (('S', S), ('S0', S0)):
            p1 = L._paper(mod, sem, L.EXEC_CFG)
            p2 = L._paper(mod, ps, L.EXEC_CFG)
            same = all(a['jobs'] == b['jobs'] for a, b in zip(p1, p2))
            cut = mod.CFG['plant_cutoff']
            pl = sum(1 for d in range(30) if Counter(p1[d]['planted']) == Counter({c: k for c, k in T.plant_n[d].items() if d <= cut.get(c, 99)}))
            st = sum(1 for d in range(30) if Counter(p1[d]['struct']) == +T.struct_n[d])
            an = sum(1 for d in range(30) if Counter(p1[d]['anim']) == +T.anim_n[d])
            tot_want = sum(k for d in range(30) for c, k in T.plant_n[d].items() if d <= cut.get(c, 99))
            tot_got = sum(sum(p1[d]['planted'].values()) for d in range(30))
            pap[nm] = dict(jobs_same_under_perm=same, plant_days=pl, struct_days=st, anim_days=an,
                           plantings_paper=tot_got, plantings_leader_after_cutoff=tot_want)
            if not same:
                e.append(f'{nm} paper jobs change under permutation')
        print(f"\n{g}: {'OK' if not e else 'ERRORS ' + '; '.join(e[:8])}")
        print(f"   land {T.land_day}, tape BUY_LAND days {bl}; market shift |sold_units[i]-SELL orders day i| {dev_same} vs day i+1 {dev_next}")
        print(f"   agent() actions differing under permutation: " + ', '.join(f'{k} {v[0]}/{v[1]}' for k, v in res.items())
              + f"; S planner log {res['S'][2]}")
        for nm, v in pap.items():
            print(f'   paper {nm}: {v}')
        errs += [f'{g}: {x}' for x in e]
        if res['T'][0] == 0:
            print('   WARNING: negative control T unchanged under permutation (test has no power here)')
    # cutoff losses over all 48 worlds
    cut = S.CFG['plant_cutoff']
    tot, lost = Counter(), Counter()
    for w in L.load_worlds():
        sem = L._load_sem(w['team_id'], w['episode'])
        for d, day in enumerate(sem['days']):
            for c, ts in day['planted'].items():
                tot[c] += len(ts)
                if d > cut.get(c, 99):
                    lost[c] += len(ts)
    print('\nleader plantings over 48 worlds (all / after the executor plant_cutoff days, skipped by T, S and S0):')
    print('  ', {c: (tot[c], lost[c], f'{100 * lost[c] / max(1, tot[c]):.0f}%') for c in tot})
    print('\nVERIFY TARGET', 'PASS' if not errs else 'FAIL', errs[:10])
    return 0 if not errs else 1


if __name__ == '__main__':
    sys.exit(main())
