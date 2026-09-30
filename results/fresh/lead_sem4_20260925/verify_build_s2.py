"""Second skeptic check of the sem4 build (exact-removals round). No games, one process, own code.

  A  Target counts of S / S0 vs an independent recomputation from the semantics (plantings by crop per day,
     structures by kind / animals by species at the end of each day, land days vs the tape's BUY_LAND orders,
     hands, cumulative sold units, live / ended removals by crop per day) on 3 worlds the builder did not use.
  B  tile-leak: S / S0 Target identical under within-quadrant permutations (3 seeds, every tile field moved) and,
     apart from land_day, under a permutation of all 100 tiles; negative control: T's Target changes.
  C  S / S0 planner (own paper execution, jobs AND fertilize targets AND removal selections, all 30 days x 5 hours)
     identical under a within-quadrant permutation.
  D  S / S0 full agent() on fixed synthetic farms (the leader's own day boards, unpermuted) with the original vs the
     permuted semantics: identical actions; T as negative control.
  E  T (mgt_lead_exact): removals issued on the leader's own boards == the leader's removal tiles by day; ops per
     job kind (harvest first); relocated-cohort cases (our cohort plant on another tile).
  F  exact_removals False == mgt_lead.py (paper jobs + fert + boards, own defaults and EXEC_CFG; agent() calls).
  G  S / S0 removal counts per day and crop == the leader's live removals (leader boards, rm_late 0; own paper, rm_late 1).
  H  stored reproduction references and run-plan commands; I  leader removal statistics over the 48 worlds;
  J  planting-cutoff losses over the 48 worlds.
"""
import ast
import gzip
import importlib.util
import json
import random
import sys
import time
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'results/fresh/lead_sem4_20260925'
WORLDS = ['16770421:112750983', '16623559:112685100', '16730612:112585733']
T_EXTRA = ['16732748:112832436']
EXEC_CFG = {'p1_min_value': 30, 'release_stale_d': True, 'fert_hold': 1}
LAB = {'WH': 'WHEAT', 'CA': 'CARROT', 'TO': 'TOMATO', 'ST': 'STRAWBERRY', 'ME': 'MELON'}
PROD_AGES = {'STRAWBERRY': [10, 12, 14, 16], 'TOMATO': [8, 9, 10, 11]}
END = {'STRAWBERRY': 16, 'TOMATO': 11, 'WHEAT': 4, 'CARROT': 3, 'MELON': 12}
FIRST = {'STRAWBERRY': 10, 'TOMATO': 8, 'WHEAT': 2, 'CARROT': 2, 'MELON': 10}
QUADS = ('NW', 'NE', 'SW', 'SE')
ERR = []


def err(msg):
    ERR.append(msg)
    print('   ERROR', msg)


def quad(i):
    x, y = i % 10, i // 10
    return ('N' if y < 5 else 'S') + ('W' if x < 5 else 'E')


def load_mod(path, tag):
    spec = importlib.util.spec_from_file_location(f'v2_{tag}_{time.time_ns()}', ROOT / path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load_sem(game):
    tid, ep = game.split(':')
    return json.load(gzip.open(ROOT / 'data/leader_semantics' / tid / f'{ep}.json.gz', 'rt', encoding='utf-8'))


def load_tape(game):
    tid, ep = game.split(':')
    return json.load(gzip.open(sorted((ROOT / 'data/leader_tapes').glob(f'{tid}_*/{ep}.json.gz'))[0], 'rt', encoding='utf-8'))


def move(sem, perm):
    """every tile reference of the semantics moved by perm (index -> index)."""
    s = deepcopy(sem)
    for day in s['days']:
        nb = [None] * 100
        for i in range(100):
            nb[perm[i]] = day['board'][i]
        day['board'] = nb
        for key in ('planted', 'built', 'maintenance'):
            day[key] = {k: [perm[t] for t in ts] for k, ts in day[key].items()}
        day['dug'] = [perm[t] for t in day['dug']]
        day['harvested']['tiles'] = [perm[t] for t in day['harvested']['tiles']]
        for k in ('placed', 'culled'):
            day['animals'][k] = [perm[t] for t in day['animals'].get(k, [])]
    return s


def perm_within(seed):
    rng = random.Random(seed)
    perm = {}
    for q in QUADS:
        idx = [i for i in range(100) if quad(i) == q]
        sh = idx[:]
        rng.shuffle(sh)
        perm.update(zip(idx, sh))
    return perm


def perm_all(seed):
    rng = random.Random(seed)
    idx = list(range(100))
    sh = idx[:]
    rng.shuffle(sh)
    return dict(zip(idx, sh))


def norm(v):
    if isinstance(v, Counter):
        return sorted((str(k), n) for k, n in v.items() if n)
    if isinstance(v, dict):
        return sorted((str(k), norm(x)) for k, x in v.items())
    if isinstance(v, (list, tuple)):
        return [norm(x) for x in v]
    return v


def leader_removals(sem):
    """own recomputation: per day, list of (tile, crop, pd, age, live, harvested same day)."""
    out = []
    last = {}
    for d, day in enumerate(sem['days']):
        rows, seen = [], set()
        harv = set(day['harvested']['tiles'])
        for t in day['dug']:
            if t in seen:
                continue
            seen.add(t)
            crop = LAB.get(day['board'][t])
            if crop is None:
                continue
            pd, pc = last.get(t, (None, None))
            if pc != crop:
                rows.append((t, crop, None, None, None, None))
                continue
            rows.append((t, crop, pd, d - pd, d - pd <= END[crop], t in harv))
        out.append(rows)
        for c, ts in day['planted'].items():
            for t in ts:
                last[t] = (d, c)
    return out


def leader_tiles(sem, d):
    """the leader's day-d start board as engine-like tiles (own code): plant yield = productions visible since the
    tile's last harvest (ongoing) / 1 (one-time); structures from the built history; animals from labels."""
    days = sem['days']
    last_plant, last_harv, skind = {}, {}, {}
    for dd in range(d):
        for t in days[dd]['harvested']['tiles']:
            last_harv[t] = dd
        for c, ts in days[dd]['planted'].items():
            for t in ts:
                last_plant[t] = (dd, c)
        for op, ts in days[dd]['built'].items():
            for t in ts:
                skind[t] = 'COOP' if op == 'BUILD_COOP' else 'PASTURE'
    tiles = [[None] * 10 for _ in range(10)]
    for i, lab in enumerate(days[d]['board']):
        x, y = i % 10, i // 10
        if lab == ' L':
            tiles[y][x] = 'LOCKED'
        elif lab in LAB:
            crop = LAB[lab]
            pd = last_plant[i][0]
            if crop in PROD_AGES:
                h = last_harv.get(i, -1)
                yu = sum(1 for p in PROD_AGES[crop] if h < pd + p <= d)
            else:
                yu = 1
            tiles[y][x] = {'kind': 'PLANT', 'crop': crop, 'planted_day': pd, 'yield_units': yu, 'watered_today': False,
                           'consecutive_unwatered': 0, 'fertilized_until_day': -1, 'max_lifespan_step': -1}
        elif lab in ('go', 'sh', 'co', 'pa'):
            kind = skind.get(i, 'COOP' if lab == 'go' else 'PASTURE')
            t = {'kind': kind}
            if lab == 'go':
                t['animal'] = 'GOOSE'
            elif lab == 'sh':
                t['animal'] = 'SHEEP'
            elif lab == 'co' and kind == 'PASTURE':
                t['animal'] = 'COW'
            if 'animal' in t:
                t.update(placed_day=0, yield_units=0, consecutive_unfed=0, fed_today=False, cared_today=False,
                         fertilizer_available=False)
            tiles[y][x] = t
    return tiles, last_plant


# ============================================================================ A
def check_A(game, S, S0):
    sem = load_sem(game)
    days = sem['days']
    n = len(days)
    T = S.Target(sem)
    T0 = S0.Target(sem)
    if norm({f: getattr(T, f) for f in S.TARGET_FIELDS}) != norm({f: getattr(T0, f) for f in S0.TARGET_FIELDS}):
        err(f'{game}: S and S0 Targets differ')
    if set(vars(T)) != set(S.TARGET_FIELDS):
        err(f'{game}: Target attributes {set(vars(T)) ^ set(S.TARGET_FIELDS)} outside TARGET_FIELDS')
    bad = []
    # plantings
    for d in range(n):
        want = Counter({c: len(ts) for c, ts in days[d]['planted'].items() if ts})
        if +T.plant_n[d] != want:
            bad.append(f'plant d{d}')
        if Counter(c for (pd, c, k) in T.events if pd == d) != want:
            bad.append(f'events d{d}')
    # structures / animals at the end of day d, own derivation (built history; a structure stays until the tile shows
    # no structure label on a later board)
    skind = {}
    for d in range(n):
        for op, ts in days[d]['built'].items():
            for t in ts:
                skind[t] = 'COOP' if op == 'BUILD_COOP' else 'PASTURE'
        b = days[d + 1]['board'] if d + 1 < n else days[d]['board']
        for t in list(skind):
            if b[t] not in ('co', 'pa', 'sh', 'go'):
                skind.pop(t)
        st = Counter(skind.values())
        an = Counter()
        for t, k in skind.items():
            if k == 'COOP' and b[t] == 'go':
                an['GOOSE'] += 1
            elif k == 'PASTURE' and b[t] == 'sh':
                an['SHEEP'] += 1
            elif k == 'PASTURE' and b[t] == 'co':
                an['COW'] += 1
        if +T.struct_n[d] != +st:
            bad.append(f'struct d{d} {dict(T.struct_n[d])} vs {dict(st)}')
        if +T.anim_n[d] != +an:
            bad.append(f'anim d{d} {dict(T.anim_n[d])} vs {dict(an)}')
    # land days: board-derived (first day d whose day d+1 board shows the quadrant) and the tape's BUY_LAND orders
    tape = load_tape(game)
    buy_days = []
    for t, a in enumerate(tape['actions']):
        for o in (a.get('market') or [])[:10]:
            if o and o[0] == 'BUY_LAND':
                buy_days.append(t // 24)
    board_land = {}
    for q in ('NE', 'SW', 'SE'):
        for d in range(n):
            b = days[d + 1]['board'] if d + 1 < n else days[d]['board']
            if any(b[i] != ' L' for i in range(100) if quad(i) == q):
                board_land[q] = d
                break
    if T.land_day != board_land or len(T.land_day) != 3:
        bad.append(f'land {T.land_day} vs {board_land}')
    if sorted(set(buy_days))[:3] != sorted(board_land.values()):
        bad.append(f'land vs tape BUY_LAND days {sorted(set(buy_days))}')
    # hands
    if list(T.hands) != [int(days[d]['labour']['hands_present']) for d in range(n)]:
        bad.append('hands')
    # cumulative sold: index i of market.* belongs to actual day i+1 (index 0 = days 0 and 1, counted at day 1)
    run = Counter()
    for d in range(n):
        for i, day in enumerate(days):
            if (1 if i == 0 else i + 1) == d:
                run.update(day['market']['sold_units'])
        if +T.cum_sold[d] != +run:
            bad.append(f'cum_sold d{d}')
    # removals
    LR = leader_removals(sem)
    unmatched = sum(1 for rows in LR for r in rows if r[2] is None)
    for d in range(n):
        live = Counter(r[1] for r in LR[d] if r[4])
        ended = Counter(r[1] for r in LR[d] if r[4] is False)
        if +T.rm_n[d] != live or +T.rm_ended_n[d] != ended:
            bad.append(f'rm d{d} {dict(T.rm_n[d])}/{dict(T.rm_ended_n[d])} vs {dict(live)}/{dict(ended)}')
    tot_live = Counter(r[1] for rows in LR for r in rows if r[4])
    print(f'A {game}: Target counts vs own recomputation: {"OK" if not bad else bad[:5]}; land {T.land_day}; '
          f'tape BUY_LAND days {sorted(set(buy_days))}; plantings {len(T.events)}; live removals {dict(tot_live)}; '
          f'label/cohort mismatches {unmatched}')
    if bad:
        err(f'{game}: Target counts {bad[:5]}')
    return sem, T


# ============================================================================ B
def check_B(game, sem, S, X):
    T = S.Target(sem)
    ref = norm({f: getattr(T, f) for f in S.TARGET_FIELDS})
    xr = norm(X.Target(sem).removals)
    for seed in (1, 2, 3):
        p = perm_within(1000 * seed + int(game.split(':')[1]) % 997)
        ps = move(sem, p)
        Tp = S.Target(ps)
        if norm({f: getattr(Tp, f) for f in S.TARGET_FIELDS}) != ref:
            err(f'{game}: S Target changes under within-quadrant permutation seed {seed}')
        if seed == 1 and norm(X.Target(ps).removals) == xr:
            err(f'{game}: negative control failed (T removals unchanged by the permutation)')
    pa = perm_all(77 + int(game.split(':')[1]) % 991)
    Ta = S.Target(move(sem, pa))
    diff = [f for f in S.TARGET_FIELDS if norm(getattr(Ta, f)) != norm(getattr(T, f))]
    print(f'B {game}: S Target invariant under 3 within-quadrant permutations; all-tile permutation changes only {diff}')
    if set(diff) - {'land_day'}:
        err(f'{game}: all-tile permutation changes {diff}')


# ============================================================================ paper (own)
def paper(mod, sem, cfg, hours=(0, 1, 3, 8, 14)):
    """own planner-only execution: every job done at once; ongoing plants carry 1 yield on a production day (and 0
    after the same-day harvest the job does); plants past their life vanish; land on the Target's land day."""
    mod.configure(sem, **cfg)
    S = mod._new_state()
    mod._S = S
    T = mod._T
    tiles = [[None if quad(y * 10 + x) == 'NW' else 'LOCKED' for x in range(10)] for y in range(10)]
    land = {}
    ld = getattr(T, 'land_day')
    rec = []
    for day in range(30):
        for q in ('NE', 'SW', 'SE'):
            if ld.get(q, 99) <= day and q not in land:
                land[q] = day
                for i in range(100):
                    if quad(i) == q:
                        tiles[i // 10][i % 10] = None
        for i in range(100):
            t = tiles[i // 10][i % 10]
            if isinstance(t, dict) and t.get('kind') == 'PLANT':
                age = day - t['planted_day']
                if age > END[t['crop']]:
                    tiles[i // 10][i % 10] = None
                elif t['crop'] in PROD_AGES:
                    t['yield_units'] = 1 if age in PROD_AGES[t['crop']] else 0
                else:
                    t['yield_units'] = 1
                    if age >= END[t['crop']]:
                        tiles[i // 10][i % 10] = None      # harvested at its max-yield day
        out = []
        dug = Counter()
        for h in hours:
            jobs, fert = mod._plan(None, S, tiles, day)
            rmsel = sorted((k, v) for k, v in (S.get('rm') or {}).items())
            out.append((h, sorted((i, j[0], j[1]) for i, j in jobs.items()), sorted(fert), rmsel))
            for i, j in jobs.items():
                x, y = i % 10, i // 10
                prev = tiles[y][x]
                if isinstance(prev, dict) and prev.get('kind') == 'PLANT' and j[0] in ('REMOVE', 'PLANT', 'BUILD'):
                    c = prev['crop']
                    if j[0] == 'REMOVE' or c in PROD_AGES or day - prev['planted_day'] < FIRST[c]:
                        if day - prev['planted_day'] <= END[c]:
                            dug[c] += 1
                if j[0] == 'REMOVE':
                    tiles[y][x] = None
                elif j[0] == 'PLANT':
                    tiles[y][x] = {'kind': 'PLANT', 'crop': j[1], 'planted_day': day, 'yield_units': 0,
                                   'fertilized_until_day': -1, 'watered_today': True, 'consecutive_unwatered': 0,
                                   'max_lifespan_step': -1}
                elif j[0] == 'BUILD':
                    tiles[y][x] = {'kind': j[1]}
                    if len(j) > 2 and j[2]:
                        tiles[y][x] = {'kind': j[1], 'animal': j[2]}
                elif j[0] == 'PLACE':
                    tiles[y][x] = {'kind': tiles[y][x]['kind'], 'animal': j[1]}
        planted = Counter()
        for (h, jl, fl, rs) in out:
            for (i, k, v) in jl:
                if k == 'PLANT':
                    planted[v] += 1
        st = Counter(t['kind'] for row in tiles for t in row if isinstance(t, dict) and t.get('kind') in ('COOP', 'PASTURE'))
        an = Counter(t['animal'] for row in tiles for t in row if isinstance(t, dict) and t.get('animal'))
        rec.append(dict(out=out, planted=planted, dug=dug, st=st, an=an,
                        board=[json.dumps(t, sort_keys=True) for row in tiles for t in row]))
    return rec


def check_C_G(game, sem, S, S0):
    T = S.Target(sem)
    LR = leader_removals(sem)
    p = perm_within(4242 + int(game.split(':')[1]) % 983)
    ps = move(sem, p)
    for nm, mod in (('S', S), ('S0', S0)):
        a = paper(mod, sem, EXEC_CFG)
        b = paper(mod, ps, EXEC_CFG)
        same = all(x['out'] == y['out'] for x, y in zip(a, b))
        cut = mod.CFG['plant_cutoff']
        pl_ok = sum(1 for d in range(30) if a[d]['planted'] == Counter({c: k for c, k in T.plant_n[d].items() if d <= cut.get(c, 99)}))
        st_ok = sum(1 for d in range(30) if +a[d]['st'] == +T.struct_n[d])
        an_ok = sum(1 for d in range(30) if +a[d]['an'] == +T.anim_n[d])
        seen = set()
        for d in range(30):
            for (h, jl, fl, rs) in a[d]['out']:
                for idx, crop in rs:
                    seen.add((idx, crop, d))
        dig_ok = sum(1 for d in range(30) if +a[d]['dug'] == Counter(r[1] for r in LR[d] if r[4]))
        # selections opened on day d (a mature one-time crop picked for a removal is harvested, not dug: counted here)
        rm_ok = sum(1 for d in range(30) if Counter(c for (i, c, dd) in seen if dd == d) - Counter(c for (i, c, dd) in seen if dd == d - 1 and (i, c, d) in seen) == Counter(r[1] for r in LR[d] if r[4])
                    or Counter(c for (i, c, dd) in seen if dd == d) == Counter(r[1] for r in LR[d] if r[4]))
        rm_tot = sum((a[d]['dug'] for d in range(30)), Counter())
        lv_tot = Counter(r[1] for rows in LR for r in rows if r[4])
        fert_n = sum(len(x[2]) for d in range(30) for x in a[d]['out'][:1])
        print(f'C/G {game} {nm}: own paper jobs+fert+removal picks identical under permutation: {same}; days equal to the '
              f'leader: plantings (after cutoffs) {pl_ok}/30, structures {st_ok}/30, animals {an_ok}/30, removal picks {rm_ok}/30, physical live digs {dig_ok}/30 '
              f'(paper {dict(rm_tot)} vs leader live {dict(lv_tot)}); fert targets at hour 0 over 30 days {fert_n} '
              f'(leader FERTILIZE tiles {sum(T.fert_n)})')
        if not same:
            err(f'{game} {nm}: paper changes under permutation')
        if rm_ok != 30:
            err(f'{game} {nm}: paper removal picks differ from the leader on {30 - rm_ok} days')
        # G: leader boards, fresh state per day, rm_late 0
        mod.configure(sem, **dict(EXEC_CFG, rm_late=0))
        ok = 0
        for d in range(30):
            tiles, _ = leader_tiles(sem, d)
            St = mod._new_state()
            mod._S = St
            rm = mod._count_removals(St, tiles, d, d)
            ok += Counter(rm.values()) == Counter(r[1] for r in LR[d] if r[4])
        print(f'G {game} {nm}: removal counts on the leader\'s own boards equal the leader\'s live removals on {ok}/30 days')
        if ok != 30:
            err(f'{game} {nm}: count removals on leader boards {ok}/30')


# ============================================================================ D
def check_D(game, sem, S, S0, X, E):
    p = perm_within(9090 + int(game.split(':')[1]) % 977)
    ps = move(sem, p)
    seat = sem['meta']['seat']
    LR = leader_removals(sem)
    rm_day = max(range(8, 29), key=lambda d: (sum(1 for r in LR[d] if r[4]), -d))
    st_day = next((d for d in range(1, 29) if sem['days'][d]['built']), 6)
    res = {}
    for nm, mod, cfg in (('S', S, EXEC_CFG), ('S0', S0, EXEC_CFG), ('T', X, EXEC_CFG)):
        seqs = []
        for s_ in (sem, ps):
            mod.configure(s_, **cfg)
            mod._S = None
            seq = []
            for d in (st_day, 12, rm_day):
                tl, last_plant = leader_tiles(sem, d)          # our farm = the UNPERMUTED leader board (fixed)
                farm = E._new_farm(10, 3000)
                priv = E._new_private()
                farm['unlocked_quadrants'] = ['NW'] + [q for q in ('NE', 'SW', 'SE') if any(tl[i // 10][i % 10] != 'LOCKED' for i in range(100) if quad(i) == q)]
                for i in range(100):
                    t = tl[i // 10][i % 10]
                    if isinstance(t, dict) and t.get('animal'):
                        t = dict(E._new_animal(t['animal'], 0), kind=t['kind'])
                    farm['tiles'][i // 10][i % 10] = t
                nh = max(0, int(sem['days'][d]['labour']['hands_present']) - 1)
                farm['hands'] = [[4, 4] for _ in range(nh)]
                farm['money'] = 6000.0
                priv['inventories'] = [{} for _ in range(nh + 1)]
                priv['seeds'] = {c: 20 for c in LAB.values()}
                priv['shed'].update({'WHEAT': 20, 'FERTILIZER': 5, 'STRAWBERRY': 3, 'WOOL': 2})
                market = E._new_market()
                farms = [E._new_farm(10, 3000), E._new_farm(10, 3000)]
                farms[seat] = farm
                mod._S = None
                for h in range(0, 24, 2):
                    obs = {'step': d * 24 + h, 'player': seat, 'farms': farms, 'private': priv, 'market': market,
                           'town': {'unlocked_shops': []}, 'day': d, 'hour': h, 'remainingOverageTime': 60}
                    seq.append(json.dumps(mod.agent(obs), sort_keys=True))
            seqs.append(seq)
        res[nm] = sum(1 for x, y in zip(*seqs) if x != y), len(seqs[0])
    print(f'D {game}: full agent() on fixed farms (days {st_day}, 12, {rm_day}), original vs permuted semantics, calls '
          f'with different actions: ' + ', '.join(f'{k} {v[0]}/{v[1]}' for k, v in res.items()))
    if res['S'][0] or res['S0'][0]:
        err(f'{game}: S/S0 agent actions change under permutation {res}')
    if res['T'][0] == 0:
        err(f'{game}: negative control T unchanged under permutation')


# ============================================================================ E
def expected_ops(t, kind, day, X):
    c = X.CROPS[t['crop']]
    age = day - t['planted_day']
    harv = t.get('yield_units', 0) > 0 and age >= c['first']
    return harv


def check_E(game, X):
    sem = load_sem(game)
    X.configure(sem, **EXEC_CFG)
    T = X._T
    LR = leader_removals(sem)
    n_want = n_got = n_match = 0
    kinds, harv_ok, harv_bad, ops_bad, day_bad = Counter(), 0, [], [], []
    reloc = Counter()
    for d in range(30):
        tiles, last_plant = leader_tiles(sem, d)
        S = X._new_state()
        X._S = S
        for t, (pd, c) in last_plant.items():
            S['done'].add((pd, t))
            if isinstance(tiles[t // 10][t % 10], dict) and tiles[t // 10][t % 10].get('crop') == c:
                S['owner'][(pd, t)] = (t, pd)
                S['owned'].add((t, pd))
        jobs, fert = X._plan(None, S, tiles, d)
        want = {(r[0], r[1]) for r in LR[d] if r[2] is not None}
        got = set(S['rm'].items())
        n_want += len(want)
        n_got += len(got)
        n_match += len(want & got)
        if want != got:
            day_bad.append((d, sorted(want - got), sorted(got - want)))
        seeds = Counter({c: 99 for c in X.CROPS})
        cut = X.CFG['plant_cutoff']        # plantings after the executor's cutoff day are skipped by design (J)
        planted_today = {t: c for c, ts in sem['days'][d]['planted'].items() for t in ts if d <= cut.get(c, 99)}
        built_today = {t: op for op, ts in sem['days'][d]['built'].items() for t in ts}
        for idx, crop in S['rm'].items():
            t = tiles[idx // 10][idx % 10]
            job = jobs.get(idx)
            kinds[job[0] if job else 'none'] += 1
            ops = X._tile_ops(idx, t, job, fert, d, 29, seeds)[0]
            names = [o[0] for o in ops]
            c = X.CROPS[t['crop']]
            age = d - t['planted_day']
            harv = t.get('yield_units', 0) > 0 and age >= c['first']
            fin = X._plant_state(t, d)[2]
            # expected job: the leader's own planting / build on this tile today, else REMOVE
            exp_job = 'PLANT' if idx in planted_today else 'BUILD' if idx in built_today else 'REMOVE'
            if job is None or job[0] != exp_job:
                ops_bad.append((d, idx, 'job', job, exp_job))
            if job and job[0] == 'PLANT' and job[1] != planted_today.get(idx):
                ops_bad.append((d, idx, 'crop', job, planted_today.get(idx)))
            if job and job[0] == 'REMOVE':
                exp = (['HARVEST', 'DIG'] if c['ongoing'] else ['HARVEST']) if harv else ['DIG']
            elif job and job[0] == 'PLANT':
                if fin:
                    exp = ['DIG', 'PLANT', 'WATER']
                elif not c['ongoing'] and harv:
                    exp = None                                   # mgt_lead's own harvest-then-plant path
                else:
                    exp = (['HARVEST'] if harv else []) + ['DIG', 'PLANT', 'WATER']
            elif job and job[0] == 'BUILD':
                exp = None if (not c['ongoing'] and harv) else (['HARVEST'] if harv else []) + ['DIG', 'BUILD_' + job[1]]
            else:
                exp = None
            if exp is not None and names[:len(exp)] != exp:
                ops_bad.append((d, idx, job, names, exp))
            r = next((r for r in LR[d] if r[0] == idx), None)
            if r is not None and r[4]:
                hf = 'HARVEST' in names[:2]
                if hf == r[5]:
                    harv_ok += 1
                else:
                    harv_bad.append((d, idx, t['crop'], age, t.get('yield_units'), names, 'leader harvested' if r[5] else 'leader did not harvest'))
        # relocation cases: every live removal cohort plant moved to another empty tile (owner record there)
        for (tt, crop, pd, age, live, hv) in LR[d]:
            if not live:
                continue
            for mode in ('empty_tt', 'blocked_tt'):
                tl2, _ = leader_tiles(sem, d)
                free = [i for i in range(100) if tl2[i // 10][i % 10] is None and i not in planted_today and i != tt
                        and i not in built_today and i not in T.struct_by_day[d] and i not in T.plant[min(29, d + 1)]]
                if not free:
                    continue
                m = free[0]
                tl2[m // 10][m % 10] = tl2[tt // 10][tt % 10]
                tl2[tt // 10][tt % 10] = None
                if mode == 'blocked_tt':      # a young carrot of ours (planted yesterday) on the leader's tile
                    tl2[tt // 10][tt % 10] = {'kind': 'PLANT', 'crop': 'CARROT', 'planted_day': d - 1, 'yield_units': 1,
                                              'watered_today': False, 'consecutive_unwatered': 0,
                                              'fertilized_until_day': -1, 'max_lifespan_step': -1}
                S2 = X._new_state()
                X._S = S2
                for t, (pd2, c2) in last_plant.items():
                    S2['done'].add((pd2, t))
                S2['owner'][(pd, tt)] = (m, pd)
                S2['owned'].add((m, pd))
                j2, _ = X._plan(None, S2, tl2, d)
                ok = S2['rm'].get(m) == crop and tt not in S2['rm']
                if tt in planted_today:
                    if mode == 'empty_tt':
                        ok = ok and j2.get(tt, (None,))[0] == 'PLANT' and j2.get(m, (None,))[0] == 'REMOVE'
                    else:
                        ok = ok and j2.get(m, (None,))[0] == 'PLANT' and j2[m][1] == planted_today[tt]
                reloc[(mode, ok)] += 1
                if not ok and reloc[(mode, False)] <= 3:
                    print(f'      relocation {mode} d{d} tt {tt} -> m {m}: rm {S2["rm"]}, job tt {j2.get(tt)}, job m {j2.get(m)}, '
                          f'leader plants on tt: {planted_today.get(tt)}')
    ok = n_want == n_got == n_match
    print(f'E {game}: T on the leader\'s boards: leader removals {n_want}, issued {n_got}, same (tile, crop) {n_match} -> '
          f'{"MATCH" if ok else "MISMATCH"}; jobs {dict(kinds)}; op-sequence problems {len(ops_bad)}; harvest-first agrees '
          f'with the leader on live removals {harv_ok}, disagrees {len(harv_bad)}; relocation {dict(reloc)}')
    for x in day_bad[:4]:
        print('      day mismatch', x)
    for x in ops_bad[:6]:
        print('      ops', x)
    for x in harv_bad[:6]:
        print('      harvest', x)
    if not ok:
        err(f'{game}: T removals mismatch {day_bad[:3]}')
    if ops_bad:
        err(f'{game}: T ops {ops_bad[:3]}')
    if any(not k[1] for k in reloc):
        err(f'{game}: T relocation failures {dict(reloc)}')


# ============================================================================ F
def check_F(game, E):
    sem = load_sem(game)
    for cfg in ({}, EXEC_CFG):
        a = paper(load_mod('agents/mgt_lead.py', 'fa'), sem, cfg)
        b = paper(load_mod('agents/mgt_lead_exact.py', 'fb'), sem, dict(cfg, exact_removals=False))
        c = paper(load_mod('agents/mgt_lead_exact.py', 'fc'), sem, cfg)
        same = all(x['out'][i][:3] == y['out'][i][:3] and x['board'] == y['board'] for x, y in zip(a, b) for i in range(len(x['out'])))
        diff_on = sum(1 for x, y in zip(a, c) if x['out'] != y['out'])
        print(f'F {game} cfg {cfg or "own defaults"}: exact_removals False == mgt_lead.py (own paper jobs, fert, boards): '
              f'{same}; exact_removals True differs on {diff_on}/30 days')
        if not same:
            err(f'{game}: exact_removals False differs from mgt_lead.py ({cfg})')


# ============================================================================ H / I / J
def check_H():
    ref = ROOT / 'results/fresh/lead_agent_20260924'
    plan = json.loads((OUT / 'run_plan.json').read_text(encoding='utf-8'))
    exp = {'abl_Gbase2_remote': {'112655730': [79844, 106718], '112714050': [65932, 68277]},
           'abl_Gff1_remote': {'112655730': [78240, 107680], '112714050': [62859, 70009]},
           'abl_E2ff1_remote': {'112655730': [80595, 103951], '112714050': [64539, 75096]},
           'abl_E2dep8_remote': {'112655730': [82345, 105734], '112714050': [66013, 76080]}}
    for dname, v in exp.items():
        for ep, (f, o) in v.items():
            r = json.loads((ref / dname / f'{ep}.json').read_text(encoding='utf-8'))
            ok = round(r['final']) == f and round(r['opp_final']) == o
            print(f'H stored {dname}/{ep}: final {r["final"]:.0f} opp {r["opp_final"]:.0f} cfg {r.get("cfg")} -> {"as claimed" if ok else "DIFFERENT"}')
            if not ok:
                err(f'stored {dname}/{ep} differs from the run plan')
    for a, b in (('abl_Gbase2_remote', 'abl_Gcut_remote'), ('abl_Gbase2_remote', 'abl_Gtr_remote'),
                 ('abl_E2dep8_remote', 'abl_E2_tievalff')):
        for ep in ('112655730', '112714050'):
            ra = json.loads((ref / a / f'{ep}.json').read_text(encoding='utf-8'))
            rb = json.loads((ref / b / f'{ep}.json').read_text(encoding='utf-8'))
            print(f'H {a} vs {b} {ep}: day-start cash equal {sum(1 for x, y in zip(ra["days"], rb["days"]) if x["cash"] == y["cash"])}/30, '
                  f'final {ra["final"]:.0f}/{rb["final"]:.0f}')
    # run-plan commands: every remote_panel call carries both env vars; kernel counts
    cmds = []
    for s in plan['steps']:
        for k, v in s.items():
            if isinstance(v, str) and 'remote_panel.py' in v:
                cmds.append((s['name'][:2], k, v))
    miss = [(a, b) for a, b, v in cmds if 'KGR_DATASET=' + chr(39) * (b == 'poll_powershell') + 'yiyangxudmm/kaggriculture-panel-bundle-sem4' not in v
            or 'KGR_STAGE=' + chr(39) * (b == 'poll_powershell') + 'results/fresh/kaggle_remote_sem4' not in v]
    pushes = [(a, b) for a, b, v in cmds if ' pushcmd ' in v]
    ps = plan['steps'][2].get('poll_powershell', '')
    print(f'H run plan: {len(cmds)} remote_panel commands, missing env: {miss or "none"} (PowerShell poll sets both: '
          f'{"KGR_DATASET=" in ps.replace("$env:", "") or "$env:KGR_DATASET" in ps}); pushcmd per step {Counter(a for a, b in pushes)}')
    if miss:
        err(f'run plan commands without env {miss}')


def check_IJ(S):
    worlds = json.loads((OUT / 'worlds.json').read_text(encoding='utf-8'))['worlds']
    by_age = defaultdict(Counter)
    live, harv, after = Counter(), Counter(), Counter()
    tot_pl, cut_pl = Counter(), Counter()
    cut = S.CFG['plant_cutoff']
    per_team = defaultdict(Counter)
    for w in worlds:
        sem = load_sem(w['game'])
        for rows in leader_removals(sem):
            for (t, crop, pd, age, lv, hv) in rows:
                if pd is None:
                    continue
                by_age[crop][age] += 1
                per_team[w['team']][crop] += 1
                if lv:
                    live[crop] += 1
                    harv[crop] += hv
        for d, day in enumerate(sem['days']):
            for c, ts in day['planted'].items():
                tot_pl[c] += len(ts)
                if d > cut.get(c, 99):
                    cut_pl[c] += len(ts)
    print('I leader removals over the 48 worlds (DIG of a tile showing a crop, cohort = last planting of that crop):')
    for c in by_age:
        print(f'   {c}: all {sum(by_age[c].values())}, by age {dict(sorted(by_age[c].items()))}, live {live[c]} '
              f'(harvested the same day {harv[c]})')
    print('   per team per game: ' + '; '.join(f'{t} ' + ', '.join(f'{c[:2]} {v / 12:.1f}' for c, v in sorted(cn.items())) for t, cn in per_team.items()))
    print('J leader plantings over the 48 worlds: all / after the executor plant_cutoff day (skipped by T0, T, S, S0): '
          + ', '.join(f'{c} {tot_pl[c]} / {cut_pl[c]} ({100 * cut_pl[c] / max(1, tot_pl[c]):.1f}%)' for c in tot_pl)
          + f'; per game {sum(cut_pl.values()) / 48:.1f} of {sum(tot_pl.values()) / 48:.1f}')


def main():
    t0 = time.time()
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    S = load_mod('agents/mgt_lead_sem.py', 's')
    S0 = load_mod('agents/mgt_lead_sem0.py', 's0')
    X = load_mod('agents/mgt_lead_exact.py', 'x')
    assert S.CFG['place_rule'] == 'care' and S0.CFG['place_rule'] == 'centre'
    for g in WORLDS:
        sem, T = check_A(g, S, S0)
        check_B(g, sem, S, X)
        check_C_G(g, sem, S, S0)
        check_D(g, sem, S, S0, load_mod('agents/mgt_lead_exact.py', 'xd'), E)
    for g in WORLDS + T_EXTRA:
        check_E(g, load_mod('agents/mgt_lead_exact.py', 'xe'))
    for g in WORLDS:
        check_F(g, E)
    check_H()
    check_IJ(S)
    print(f'\nwall {time.time() - t0:.0f}s')
    print('VERIFY S2', 'PASS' if not ERR else 'FAIL', ERR[:12])


if __name__ == '__main__':
    main()
