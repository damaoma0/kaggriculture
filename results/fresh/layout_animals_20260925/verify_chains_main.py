"""Independent skeptic re-derivation of the fertilizer-chain report (chains.txt), stored replays only.

usage: .venv/Scripts/python.exe results/fresh/layout_animals_20260925/verify_chains_main.py ep1 ep2 ...

Does NOT reuse fert_chains.py. Differences in method:
  * effectiveness of COLLECT / PICKUP / FERTILIZE / DROP / PLACE is read from the RECORDED inventory delta of the
    unit (post - pre) on every non-boundary step; only the 30 hour-23 steps are inferred from the pre-state tile.
  * two token stacks per unit (true LIFO and true FIFO), each with its own deposit handling.
  * two definitions of "shed visit between collect and fertilize":
      THEIRS  = the unit's pre-state position is a shed tile at any step s with t_collect < s <= t_fert
                (a unit that collects from an animal standing ON a shed tile is always 'after shed' under this);
      ENTERED = the unit moves onto a shed tile from a non-shed tile, or does PICKUP/DROP/shed-PLACE, after the
                collect (standing still on the shed-tile animal does not count).
  * outbound tests: STRAIGHT = moves since last shed presence == dshed(animal) at the collect;
                    PURE = moves from last shed presence to the crop == dshed(crop) (zero detour for the whole leg).
Seat = index of 'DSM' in info.TeamNames, cross-checked with observation.player and info.Agents[].Name.
Writes verify_chains_main.json (per seat-game numbers) next to this script. One file in memory at a time.
"""
import gc
import json
import os
import sys
import statistics as stt

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SHED = ((4, 4), (5, 4), (4, 5), (5, 5))
MV = {'NORTH': (0, -1), 'SOUTH': (0, 1), 'EAST': (1, 0), 'WEST': (-1, 0)}


def dsh(p):
    return min(abs(p[0] - a) + abs(p[1] - b) for a, b in SHED)


def mh(p, q):
    return abs(p[0] - q[0]) + abs(p[1] - q[1])


def quad(p):
    return ('N' if p[1] < 5 else 'S') + ('W' if p[0] < 5 else 'E')


def seat_game(steps, seat):
    R = {'collect': 0, 'pick_units': 0, 'applied': 0, 'deposit_units': 0, 'dump': 0, 'anomaly': 0,
         'moves': 0, 'bnd_inferred': 0}
    ferts = []           # one record per effective FERTILIZE
    collects = []        # one record per effective COLLECT
    lay = {'animal': [], 'crop': []}
    for t in range(1, len(steps)):
        day, hour = (t - 1) // 24, (t - 1) % 24
        bnd = hour == 23
        pf = steps[t - 1][0]['observation']['farms'][seat]
        pp = steps[t - 1][seat]['observation']['private']
        qp = steps[t][seat]['observation']['private']
        qf = steps[t][0]['observation']['farms'][seat]
        act = steps[t][seat].get('action') or {}
        if not isinstance(act, dict):
            act = {}
        if hour == 0:
            U = {}
            for y in range(10):
                for x in range(10):
                    tl = pf['tiles'][y][x]
                    if isinstance(tl, dict):
                        if tl.get('animal'):
                            lay['animal'].append((x, y))
                        elif tl.get('kind') == 'PLANT':
                            lay['crop'].append((x, y))
        shed_f = int(pp['shed'].get('FERTILIZER', 0))
        acts = [act.get('farmer') or ['PASS']] + list(act.get('hands') or [])
        pos_list = [tuple(pf['farmer'])] + [tuple(h) for h in pf['hands']]
        taken = set()
        for u, pos in enumerate(pos_list):
            a = acts[u] if u < len(acts) and isinstance(acts[u], list) and acts[u] else ['PASS']
            op = a[0]
            if u not in U:
                U[u] = {'lifo': [], 'fifo': [], 'cm': 0, 'last_shed_s': -1, 'last_shed_cm': None,
                        'entries': 0, 'prev_on_shed': pos in SHED}
            S = U[u]
            on_shed = pos in SHED
            if on_shed:
                S['last_shed_s'] = t
                S['last_shed_cm'] = S['cm']
            fpre = int((pp['inventories'][u] if u < len(pp['inventories']) else {}).get('FERTILIZER', 0))
            assert fpre == len(S['lifo']) == len(S['fifo']), (t, u, fpre, len(S['lifo']))
            tile = pf['tiles'][pos[1]][pos[0]]
            if not bnd:
                fpost = int((qp['inventories'][u] if u < len(qp['inventories']) else {}).get('FERTILIZER', 0))
                d = fpost - fpre
            else:
                R['bnd_inferred'] += 1
                d = 0
                if op == 'COLLECT_FERTILIZER' and isinstance(tile, dict) and tile.get('animal') \
                        and tile.get('fertilizer_available') and pos not in taken:
                    d = 1
                elif op == 'FERTILIZE' and isinstance(tile, dict) and tile.get('kind') == 'PLANT' and fpre >= 1:
                    d = -1
                elif op == 'PICKUP' and on_shed and len(a) >= 2 and a[1] == 'FERTILIZER':
                    n = int(a[2]) if len(a) >= 3 else 1
                    d = max(0, min(n, shed_f))
                elif op == 'DROP' and on_shed:
                    d = -fpre
                elif op == 'PLACE' and on_shed and len(a) >= 2 and a[1] == 'FERTILIZER':
                    n = int(a[2]) if len(a) >= 3 else 1
                    d = -max(0, min(n, fpre))
            if op == 'COLLECT_FERTILIZER' and d == 1:
                taken.add(pos)
                R['collect'] += 1
                since = S['cm'] - S['last_shed_cm'] if S['last_shed_cm'] is not None else None
                tok = {'src': 'field', 't': t, 'A': pos, 'cm': S['cm'], 'entries': S['entries'],
                       'last_shed_s': S['last_shed_s'], 'last_shed_cm': S['last_shed_cm'],
                       'since_shed': since, 'shed_stock_at_last_shed': None}
                collects.append({'A': pos, 'since': since, 'animal': tile.get('animal'), 't': t, 'u': u})
                S['lifo'].append(tok)
                S['fifo'].append(tok)
            elif op == 'PICKUP' and d > 0:
                R['pick_units'] += d
                shed_f -= d
                for _ in range(d):
                    tok = {'src': 'shed', 't': t, 'A': pos, 'cm': S['cm'], 'entries': S['entries'],
                           'last_shed_s': t, 'last_shed_cm': S['cm'], 'since_shed': 0}
                    S['lifo'].append(tok)
                    S['fifo'].append(tok)
                S['entries'] += 1
            elif op == 'FERTILIZE' and d == -1:
                R['applied'] += 1
                L = S['lifo'].pop()
                F = S['fifo'].pop(0)
                homog = len({x['src'] for x in S['lifo'] + [L]}) == 1
                rec = {'t': t, 'day': day, 'u': u, 'C': pos, 'src_lifo': L['src'], 'src_fifo': F['src'],
                       'homog': homog, 'A': L['A'], 'tA': L['t'],
                       'theirs_between': S['last_shed_s'] > L['t'],
                       'entered_between': S['entries'] > L['entries'],
                       'straight': (L['since_shed'] == dsh(L['A'])) if L['since_shed'] is not None else None,
                       'walk_shed_to_C': (S['cm'] - L['last_shed_cm']) if L['last_shed_cm'] is not None else None,
                       'last_shed_s': L['last_shed_s']}
                ferts.append(rec)
            elif op in ('DROP', 'PLACE') and d < 0 and on_shed:
                k = -d
                R['deposit_units'] += k
                for _ in range(k):
                    S['lifo'].pop()
                    S['fifo'].pop(0)
                S['entries'] += 1
            elif d != 0:
                R['anomaly'] += 1
                # resync
                while len(S['lifo']) > fpre + d:
                    S['lifo'].pop()
                    S['fifo'].pop(0)
                while len(S['lifo']) < fpre + d:
                    tok = {'src': 'unknown', 't': t, 'A': pos, 'cm': S['cm'], 'entries': S['entries'],
                           'last_shed_s': S['last_shed_s'], 'last_shed_cm': S['last_shed_cm'], 'since_shed': None}
                    S['lifo'].append(tok)
                    S['fifo'].append(tok)
            if op in ('PICKUP', 'DROP') and on_shed and d == 0:
                pass
            if op in MV:
                dx, dy = MV[op]
                nx, ny = pos[0] + dx, pos[1] + dy
                if 0 <= nx < 10 and 0 <= ny < 10:
                    S['cm'] += 1
                    R['moves'] += 1
                    if (nx, ny) in SHED and not on_shed:
                        S['entries'] += 1
        if bnd:
            for S in U.values():
                R['dump'] += len(S['lifo'])
                S['lifo'] = []
                S['fifo'] = []
        # shed stock bookkeeping for trip starts: store pre-state stock per step
        R.setdefault('_stock', {})[t] = int(pp['shed'].get('FERTILIZER', 0))
    return R, ferts, collects, lay


def summarise(R, ferts, collects, lay):
    n = len(ferts)
    out = {k: v for k, v in R.items() if not k.startswith('_')}
    out['n_fert'] = n
    out['field_lifo'] = sum(f['src_lifo'] == 'field' for f in ferts)
    out['field_fifo'] = sum(f['src_fifo'] == 'field' for f in ferts)
    out['homog'] = sum(f['homog'] for f in ferts)
    fl = [f for f in ferts if f['src_lifo'] == 'field']
    ch_t = [f for f in fl if not f['theirs_between']]
    ch_e = [f for f in fl if not f['entered_between']]
    out['direct_theirs'] = len(ch_t)
    out['direct_entered'] = len(ch_e)
    out['field_after_shed_theirs'] = len(fl) - len(ch_t)
    out['after_theirs_but_not_entered'] = sum(1 for f in fl if f['theirs_between'] and not f['entered_between'])
    out['after_theirs_animal_dshed0'] = sum(1 for f in fl if f['theirs_between'] and dsh(f['A']) == 0)
    for tag, ch in (('theirs', ch_t), ('entered', ch_e)):
        if not ch:
            continue
        dA = [dsh(f['A']) for f in ch]
        dC = [dsh(f['C']) for f in ch]
        out[f'{tag}_mean_dA'] = sum(dA) / len(ch)
        out[f'{tag}_mean_dC'] = sum(dC) / len(ch)
        out[f'{tag}_closer'] = sum(a < c for a, c in zip(dA, dC)) / len(ch)
        out[f'{tag}_onpath'] = sum(dsh(f['A']) + mh(f['A'], f['C']) == dsh(f['C']) for f in ch) / len(ch)
        out[f'{tag}_samequad'] = sum(quad(f['A']) == quad(f['C']) for f in ch) / len(ch)
        st = [f['straight'] for f in ch if f['straight'] is not None]
        out[f'{tag}_straight_to_animal'] = sum(st) / len(st) if st else None
        pw = [f for f in ch if f['walk_shed_to_C'] is not None]
        out[f'{tag}_pure_outbound_leg'] = sum(f['walk_shed_to_C'] == dsh(f['C']) for f in pw) / len(pw) if pw else None
        out[f'{tag}_dA_dist'] = {str(k): dA.count(k) for k in sorted(set(dA))}
        lag = [f['t'] - f['tA'] for f in ch]
        out[f'{tag}_lag_mean'] = sum(lag) / len(lag)
        out[f'{tag}_lag_median'] = stt.median(lag)
        # trips: (day,u,last_shed_s); stock at the step the unit last stood on the shed
        trips = {}
        for f in ch:
            trips.setdefault((f['day'], f['u'], f['last_shed_s']), []).append(f)
        stock = R['_stock']
        k1 = sum(1 for (dd, uu, s) in trips if s > 0 and stock.get(s, 0) >= 1)
        kv = sum(1 for (dd, uu, s) in trips if s > 0)
        out[f'{tag}_trips'] = len(trips)
        out[f'{tag}_trips_valid_shed'] = kv
        out[f'{tag}_trip_stock_ge1'] = k1 / kv if kv else None
    cs = collects
    out['collect_mean_dA'] = sum(dsh(c['A']) for c in cs) / len(cs) if cs else None
    out['collect_dshed0'] = sum(dsh(c['A']) == 0 for c in cs)
    out['collect_straight'] = sum(1 for c in cs if c['since'] is not None and c['since'] == dsh(c['A'])) / len(cs)
    for g in ('animal', 'crop'):
        L = lay[g]
        out[f'lay_{g}_n'] = len(L)
        out[f'lay_{g}_mean_dshed'] = sum(dsh(p) for p in L) / len(L) if L else None
        out[f'lay_{g}_dshed0'] = sum(dsh(p) == 0 for p in L)
        out[f'lay_{g}_quad'] = {q: sum(quad(p) == q for p in L) for q in ('NW', 'NE', 'SW', 'SE')}
    return out


def main():
    eps = sys.argv[1:]
    res = {}
    outp = os.path.join(HERE, 'verify_chains_main.json')
    if os.path.exists(outp):
        res = json.load(open(outp, encoding='utf-8'))
    for ep in eps:
        if psutil.virtual_memory().available < 1024 ** 3:
            print('STOP: free memory under 1 GB before', ep)
            break
        fp = os.path.join(ROOT, 'data', 'dsm_replays', f'episode-{ep}-replay.json')
        with open(fp, encoding='utf-8') as f:
            d = json.load(f)
        teams = d['info']['TeamNames']
        agents = [a.get('Name') for a in d['info'].get('Agents', [])]
        steps = d['steps']
        seats = [i for i, nm in enumerate(teams) if nm == 'DSM']
        for seat in seats:
            player = steps[1][seat]['observation'].get('player')
            R, ferts, collects, lay = seat_game(steps, seat)
            o = summarise(R, ferts, collects, lay)
            o.update({'teams': teams, 'agents': agents, 'obs_player': player, 'rewards': d.get('rewards'),
                      'n_steps': len(steps)})
            res[f'{ep}:{seat}'] = o
            print(ep, seat, 'rss', psutil.Process().memory_info().rss // 2 ** 20, 'MB',
                  {k: o[k] for k in ('collect', 'pick_units', 'applied', 'anomaly', 'n_fert', 'field_lifo',
                                     'direct_theirs', 'direct_entered')}, flush=True)
        del d, steps
        gc.collect()
        json.dump(res, open(outp, 'w', encoding='utf-8'), indent=1, default=str)


if __name__ == '__main__':
    main()
