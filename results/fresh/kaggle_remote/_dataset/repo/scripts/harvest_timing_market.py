"""Harvest timing, market part: coins per unit for selling at the harvest hour vs the next morning, own + rival = margin,
from STORED Kaggle replays with per-step observations (no games).

usage:
  .venv/Scripts/python.exe scripts/harvest_timing_market.py extract     # data/dsm_replays + data/replays -> compact file
  .venv/Scripts/python.exe scripts/harvest_timing_market.py report

extract: each replay is decoded one step at a time (json raw_decode; the files are ~30 MB). Kept per engine step s
(replay steps[s+1] = the state after step s, its `action` = the action applied at step s): the market inventory after
the step, each player's SELL / BUY_PRODUCT requests (first 10 orders, the engine cap) and whether it placed any other
order, each player's shed after the step and money after the step, and the unlocked shops before the step.
Self-play episodes (same team in both seats) are skipped.

report: total units sold at step s = inventory change + town / shop consumption at s (+ units bought back for wheat /
fertilizer; sales at the $1 floor do not move the inventory and are not seen). Split between the players by their SELL
requests: a player with stock left after the step sold its full request, the other the rest; both stock-limited ->
proportional (counted). Checked against money: on steps where a player placed only SELL orders, the engine's lockstep
market re-simulated with these per-player units must give that player's money change.
Credit for a unit X of product P ready at step s0 = day d0, hour h0 (the price quoted at a market phase is
price(inventory after the previous step)):
  own gain       = price(inv before s0) - price(inv before the next morning's first market phase, step 24(d0+1))
                   (the path in between = both players' sales + consumption, as recorded);
  own cannibal.  = sum over OUR other units sold in [s0, next morning) of price(inv) - price(inv + 1)  (X sold first
                   raises the inventory seen by every later sale until the morning);
  rival loss     = the same sum over the RIVAL's units sold in [s0, next morning);
  margin credit  = own gain - own cannibalization + rival loss.  (0 externalities when price(inv before s0) = 1.)
Day 29 has no next morning (unsold = lost) and is left out. Tables by product x period (d0) and by hour bin.
"""
import gzip
import json
import math
import re
import statistics as st
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/harvest_timing_20260925/market'
SRC = [ROOT / 'data/dsm_replays', ROOT / 'data/replays']
PRODUCTS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER']
MP = {  # engine MARKET_PARAMS (kaggriculture.py 1.32.7)
    'WHEAT': (25, 400, 'sqrt', 0.80, 'log', 0.20), 'CARROT': (35, 450, 'hinge', 1.00, 'sqrt', 0.70),
    'TOMATO': (60, 200, 'hinge', 0.40, 'sqrt', 0.60), 'STRAWBERRY': (120, 100, 'sqrt', 0.70, 'linear', 1.60),
    'MELON': (250, 300, 'log', 0.20, 'sq', 3.60), 'EGG': (50, 332, 'hinge', 0.40, 'log', 0.20),
    'MILK': (160, 122, 'sqrt', 0.60, 'linear', 1.60), 'WOOL': (200, 105, 'log', 0.20, 'sq', 3.20),
    'FERTILIZER': (100, 200, 'linear', 0.40, 'linear', 0.40)}
I0 = 10000
SHOPS = {'BAKERY': ['EGG', 'WHEAT'], 'PIZZA_SHOP': ['MILK', 'TOMATO', 'WHEAT'],
         'BRUNCH_SPOT': ['EGG', 'WHEAT', 'STRAWBERRY'], 'YARN_STORE': ['WOOL'],
         'ICE_CREAM_SHOP': ['STRAWBERRY', 'MILK', 'WHEAT'], 'PET_CAFE': ['CARROT'],
         'SMOOTHIE_SHOP': ['STRAWBERRY', 'MILK'], 'FARMERS_MARKET': ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY']}
PNAME = ['d0-5', 'd6-11', 'd12-17', 'd18-23', 'd24-28']
FIRST_YIELD = {'WHEAT': 2, 'CARROT': 2, 'TOMATO': 8, 'STRAWBERRY': 10, 'MELON': 10}
ANIMAL_PRODUCT = {'GOOSE': 'EGG', 'COW': 'MILK', 'SHEEP': 'WOOL'}


def _shape(f, x, T):
    x = max(0.0, x)
    if f == 'linear':
        return x
    if f == 'sq':
        return x * x
    if f == 'sqrt':
        return math.sqrt(x)
    if f == 'log':
        return math.log(1.0 + x)
    if f == 'hinge':
        u = x / T
        return u + 8.0 * max(0.0, u - 1.0) ** 2
    return x


_PC = {}


def price(item, inv):
    key = (item, inv)
    v = _PC.get(key)
    if v is None:
        base, T, bf, bt, af, at = MP[item]
        if inv < I0:
            p = base + bt * base / _shape(bf, T, T) * _shape(bf, I0 - inv, T)
        else:
            p = base - at * base / _shape(af, T, T) * _shape(af, inv - I0, T)
        v = max(1, int(round(p)))
        if len(_PC) < 2_000_000:
            _PC[key] = v
    return v


def consumption(s, shops):
    c = Counter()
    if s % 24 == 0:
        for p in PRODUCTS:
            if p != 'FERTILIZER':
                c[p] += 1
    if s % 4 == 0:
        for sh in shops:
            prods = SHOPS[sh]
            for p in prods:
                c[p] += 2 if len(prods) == 1 else 1
    return c


# ---------------------------------------------------------------------------------------------------------- extract
def steps_iter(path):
    txt = open(path, encoding='utf-8').read()
    i = txt.find('"steps"')
    j = txt.index('[', i) + 1
    dec = json.JSONDecoder()
    while True:
        while txt[j] in ' \n\r\t,':
            j += 1
        if txt[j] == ']':
            return
        obj, j = dec.raw_decode(txt, j)
        yield obj


def extract_one(path):
    head = open(path, encoding='utf-8').read(9000)
    tn = json.loads(re.search(r'"TeamNames": (\[[^\]]*\])', head).group(1))
    rw = json.loads(re.search(r'"rewards": (\[[^\]]*\])', head).group(1))
    ep = int(re.search(r'"EpisodeId": (\d+)', head).group(1))
    if tn[0] == tn[1]:
        return None
    rec = {'ep': ep, 'teams': tn, 'rewards': rw, 'inv': [], 'shops': [], 'sell': [], 'buy': [], 'other': [],
           'orders': [], 'shed': [], 'money': [], 'harv': []}
    prev_shops = []
    prev_farms = None
    for k, stp in enumerate(steps_iter(path)):
        ob0 = stp[0]['observation']
        if k == 0:
            prev_shops = list((ob0.get('town') or {}).get('unlocked_shops') or [])
            prev_farms = ob0['farms']
            continue
        # engine step s = k - 1
        s = k - 1
        rec['shops'].append(prev_shops)
        prev_shops = list((ob0.get('town') or {}).get('unlocked_shops') or [])
        # harvest events: a unit whose position (state before the step) holds a harvestable tile and whose action is
        # HARVEST takes the tile's units (the first such unit of the step; units act before the step's decay)
        hv = []
        for i in range(2):
            fp = prev_farms[i]
            posl = [fp['farmer']] + list(fp.get('hands') or [])
            a = stp[i].get('action') or {}
            acts = [a.get('farmer') or ['PASS']] + list(a.get('hands') or []) if isinstance(a, dict) else []
            got = Counter()
            taken = set()
            for u, act in enumerate(acts):
                if u >= len(posl) or not isinstance(act, list) or not act or act[0] != 'HARVEST':
                    continue
                x, y = posl[u]
                if (x, y) in taken:
                    continue
                tile = fp['tiles'][y][x]
                if not isinstance(tile, dict) or tile.get('yield_units', 0) <= 0:
                    continue
                if tile.get('kind') == 'PLANT':
                    if s // 24 - tile['planted_day'] < FIRST_YIELD[tile['crop']]:
                        continue
                    prod = tile['crop']
                elif tile.get('animal'):
                    prod = ANIMAL_PRODUCT[tile['animal']]
                else:
                    continue
                got[prod] += tile['yield_units']
                taken.add((x, y))
            hv.append(dict(got))
        rec['harv'].append(hv)
        prev_farms = ob0['farms']
        inv = ob0['market']['inventory']
        rec['inv'].append([inv[p] for p in PRODUCTS])
        sells, buys, others, ords, sheds, money = [], [], [], [], [], []
        for i in range(2):
            a = stp[i].get('action') or {}
            m = a.get('market') if isinstance(a, dict) else None
            m = (m if isinstance(m, list) else [])[:10]
            sc, bc, oth = Counter(), Counter(), 0
            clean = []
            for o in m:
                if not isinstance(o, list) or not o:
                    continue
                if o[0] in ('SELL', 'BUY_PRODUCT') and len(o) >= 3 and o[1] in PRODUCTS:
                    try:
                        n = int(o[2])
                    except (TypeError, ValueError):
                        continue
                    if n <= 0:
                        continue
                    (sc if o[0] == 'SELL' else bc)[o[1]] += n
                    clean.append([o[0], o[1], n])
                else:
                    oth += 1
                    clean.append([o[0]] + [x for x in o[1:3]])
            sells.append({p: v for p, v in sc.items()})
            buys.append({p: v for p, v in bc.items()})
            others.append(oth)
            ords.append(clean)
            shed = stp[i]['observation'].get('private', {}).get('shed', {})
            sheds.append({p: shed.get(p, 0) for p in PRODUCTS if shed.get(p, 0)})
            money.append(ob0['farms'][i]['money'])
        rec['sell'].append(sells)
        rec['buy'].append(buys)
        rec['other'].append(others)
        rec['orders'].append(ords)
        rec['shed'].append(sheds)
        rec['money'].append(money)
    return rec


def cmd_extract():
    OUT.mkdir(parents=True, exist_ok=True)
    files = [f for d in SRC for f in sorted(d.glob('episode-*-replay.json'))]
    t0 = time.time()
    n = skipped = 0
    with gzip.open(OUT / 'replays.jsonl.gz', 'wt', encoding='utf-8') as fo:
        for f in files:
            rec = extract_one(f)
            if rec is None:
                skipped += 1
                continue
            rec['src'] = f.parent.name
            fo.write(json.dumps(rec, separators=(',', ':')) + '\n')
            n += 1
            del rec
            if n % 20 == 0:
                print(f'  {n} games, {time.time() - t0:.0f}s', flush=True)
    print(f'extracted {n} games (skipped {skipped} self-play) in {time.time() - t0:.0f}s')


# ---------------------------------------------------------------------------------------------------------- report
def split_sales(g):
    """per step: {product: (x0, x1)} units sold by each player; plus counters."""
    val = Counter()
    out = []
    prev = [I0] * len(PRODUCTS)
    for s in range(len(g['inv'])):
        inv = g['inv'][s]
        cons = consumption(s, g['shops'][s])
        row = {}
        for pi, p in enumerate(PRODUCTS):
            r = [g['sell'][s][i].get(p, 0) for i in range(2)]
            b = [g['buy'][s][i].get(p, 0) for i in range(2)]
            d_inv = inv[pi] - prev[pi] + cons.get(p, 0)
            if not r[0] and not r[1]:
                if d_inv > 0:
                    val['unexplained_up'] += d_inv
                continue
            B = b[0] + b[1]
            S = d_inv + B if B else d_inv
            if S < 0:
                val['neg_sales'] += 1
                S = 0
            if S > r[0] + r[1]:
                val['over_request'] += 1
                S = r[0] + r[1]
            if S == 0:
                continue
            if not r[1]:
                x = (S, 0)
            elif not r[0]:
                x = (0, S)
            elif S >= r[0] + r[1]:
                x = (r[0], r[1])
            else:
                h = s % 24
                left = [g['shed'][s][i].get(p, 0) > 0 for i in range(2)]
                if h != 23 and left[0] and not left[1]:
                    x = (r[0], max(0, S - r[0]))
                elif h != 23 and left[1] and not left[0]:
                    x = (max(0, S - r[1]), r[1])
                else:
                    x0 = round(S * r[0] / (r[0] + r[1]))
                    x = (x0, S - x0)
                    val['proportional_split_units'] += S
            val['sold_units'] += S
            row[p] = x
        out.append(row)
        prev = inv
    return out, val


def lockstep_revenue(g, s, xs, prev_inv):
    """re-simulate the market phase of step s (both players' orders, per-player sell caps = xs) -> revenue per player."""
    inv = {p: prev_inv[i] for i, p in enumerate(PRODUCTS)}
    ords = g['orders'][s]
    cap = [{p: xs.get(p, (0, 0))[i] for p in PRODUCTS} for i in range(2)]
    sold = [Counter(), Counter()]
    rev = [0, 0]
    L = max(len(ords[0]), len(ords[1]))
    for idx in range(L):
        stt = []
        for i in range(2):
            o = ords[i][idx] if idx < len(ords[i]) else None
            if o and o[0] in ('SELL', 'BUY_PRODUCT'):
                stt.append({'op': o[0], 'item': o[1], 'rem': o[2]})
            else:
                stt.append(None)
        while True:
            quoted = [None, None]
            for i in range(2):
                q = stt[i]
                if q is None or q['rem'] <= 0:
                    continue
                if q['op'] == 'SELL':
                    quoted[i] = price(q['item'], inv[q['item']])
                else:
                    quoted[i] = price(q['item'], inv[q['item']] - 1)
            if all(v is None for v in quoted):
                break
            any_c = False
            for i in range(2):
                if quoted[i] is None:
                    continue
                q = stt[i]
                if q['op'] == 'SELL':
                    if sold[i][q['item']] < cap[i][q['item']]:
                        sold[i][q['item']] += 1
                        rev[i] += quoted[i]
                        if quoted[i] > 1:
                            inv[q['item']] += 1
                        q['rem'] -= 1
                        any_c = True
                    else:
                        stt[i] = None
                else:
                    inv[q['item']] -= 1      # buys assumed to succeed (only used on the other player's side)
                    q['rem'] -= 1
                    any_c = True
            if not any_c:
                break
    return rev


def refine_step(g, s, row, prev):
    """money is the ground truth for a player whose only orders at step s are SELLs: re-allocate its units per product
    (grid over 0..request, the other player keeping the rest of the observed total for contested products) until the
    re-simulated lockstep revenue equals its money change. Returns (row, status)."""
    from itertools import product as iprod
    sell_only = [bool(g['sell'][s][i]) and not g['buy'][s][i] and not g['other'][s][i] for i in range(2)]
    if not any(sell_only):
        return row, 'no_sell_only'
    dm = [g['money'][s][i] - (g['money'][s - 1][i] if s else 3000.0) for i in range(2)]
    rev = lockstep_revenue(g, s, row, prev)
    if all(abs(rev[i] - dm[i]) < 0.5 for i in range(2) if sell_only[i]):
        return row, 'ok'
    tot = {p: sum(row.get(p, (0, 0))) for p in PRODUCTS}
    for _ in range(2):
        changed = False
        for i in range(2):
            if not sell_only[i] or abs(rev[i] - dm[i]) < 0.5:
                continue
            prods = list(g['sell'][s][i])
            grids = [range(0, g['sell'][s][i][p] + 1) for p in prods]
            size = 1
            for gr in grids:
                size *= len(gr)
            if size > 3000:
                continue
            best = None
            for combo in iprod(*grids):
                trial = dict(row)
                for p, xi in zip(prods, combo):
                    xo = row.get(p, (0, 0))[1 - i]
                    if g['sell'][s][1 - i].get(p) and not sell_only[1 - i]:
                        xo = max(0, min(g['sell'][s][1 - i][p], tot[p] - xi))
                    trial[p] = (xi, xo) if i == 0 else (xo, xi)
                r = lockstep_revenue(g, s, trial, prev)
                e = abs(r[i] - dm[i])
                dist = sum(abs(xi - row.get(p, (0, 0))[i]) for p, xi in zip(prods, combo))
                if best is None or (e, dist) < best[0]:
                    best = ((e, dist), trial, r)
                    if e < 0.5 and dist == 0:
                        break
            if best is not None and best[0][0] < abs(rev[i] - dm[i]):
                row, rev = best[1], best[2]
                changed = True
        if not changed:
            break
    ok = all(abs(rev[i] - dm[i]) < 0.5 for i in range(2) if sell_only[i])
    return row, ('refined_ok' if ok else 'refined_fail')


def credits(g, sales):
    """per (seat, product, day, hour) -> (me, p, d0, h0, own_gain, own_cannibalization (our units sold after s0 until
    the morning; the units of step s0 itself excluded: a batch sold now or in the morning carries its own within-batch
    effect in both cases), rival_loss (rival units sold from s0 until the morning), units sold by me at s0, units
    harvested by me at s0, own units after s0, rival units from s0, price now, price next morning)."""
    n = len(g['inv'])
    inv_before = [[I0] * len(PRODUCTS)] + g['inv'][:-1]     # inventory at the market phase of step s
    rows = []
    for pi, p in enumerate(PRODUCTS):
        ext = [[0.0, 0.0] for _ in range(n)]
        for s in range(n):
            x = sales[s].get(p)
            if not x:
                continue
            inv = inv_before[s][pi]
            k0, k1 = x
            for k in range(max(k0, k1)):
                a = price(p, inv) - price(p, inv + 1)
                if k < k0:
                    ext[s][0] += a
                if k < k1:
                    ext[s][1] += a
                inv += (k < k0) + (k < k1)
        for d0 in range(29):
            sm = (d0 + 1) * 24
            if sm >= n:
                break
            p_m = price(p, g['inv'][sm - 1][pi])
            acc = [0.0, 0.0]
            units = [0, 0]
            for h0 in range(23, -1, -1):
                s0 = d0 * 24 + h0
                x = sales[s0].get(p) or (0, 0)
                p_now = price(p, inv_before[s0][pi])
                own_gain = p_now - p_m
                hv = g['harv'][s0]
                for me in range(2):
                    rv = 1 - me
                    if p_now <= 1:
                        can, rl = 0.0, 0.0
                    else:
                        can, rl = acc[me], acc[rv] + ext[s0][rv]
                    rows.append((me, p, d0, h0, own_gain, can, rl, x[me], hv[me].get(p, 0), units[me],
                                 units[rv] + x[rv], p_now, p_m))
                acc[0] += ext[s0][0]
                acc[1] += ext[s0][1]
                units[0] += x[0]
                units[1] += x[1]
    return rows


def cmd_report():
    src = OUT / 'replays.jsonl.gz'
    # key -> [sum own, sum cannibal, sum rival, sum own units after, sum rival units, sum weight]
    AG = {w: defaultdict(lambda: [0.0] * 6) for w in ('hour', 'harv', 'sold')}
    val_all = Counter()
    status = Counter()
    money_chk = Counter()
    games = 0
    t0 = time.time()
    with gzip.open(src, 'rt', encoding='utf-8') as f:
        for line in f:
            g = json.loads(line)
            sales, val = split_sales(g)
            val_all.update(val)
            prev = [I0] * len(PRODUCTS)
            for s in range(len(g['inv'])):
                if any(g['sell'][s][i] for i in range(2)):
                    row, stt = refine_step(g, s, sales[s], prev)
                    sales[s] = row
                    status[stt] += 1
                    if stt != 'no_sell_only':
                        rev = lockstep_revenue(g, s, row, prev)
                        for i in range(2):
                            if g['sell'][s][i] and not g['buy'][s][i] and not g['other'][s][i]:
                                dm = g['money'][s][i] - (g['money'][s - 1][i] if s else 3000.0)
                                money_chk['steps'] += 1
                                money_chk['exact'] += int(abs(dm - rev[i]) < 0.5)
                                money_chk['abs_err'] += abs(dm - rev[i])
                                money_chk['rev'] += abs(dm)
                prev = g['inv'][s]
            strong = [t == 'DSM' for t in g['teams']]
            for (me, p, d0, h0, og, can, rl, sold_here, harv_here, own_after, rv_units, p_now, p_m) in credits(g, sales):
                per = min(4, d0 // 6)
                hb = h0 // 6
                role = ('rivalDSM' if strong[1 - me] and not strong[me] else
                        ('meDSM' if strong[me] and not strong[1 - me] else 'other'))
                keys = ((p, per), (p, 'hb%d' % hb), (p, per, 'hb%d' % hb), (p, per, role))
                for w, wt in (('hour', 1), ('harv', harv_here), ('sold', sold_here)):
                    if not wt:
                        continue
                    for key in keys:
                        a = AG[w][key]
                        a[0] += og * wt
                        a[1] += can * wt
                        a[2] += rl * wt
                        a[3] += own_after * wt
                        a[4] += rv_units * wt
                        a[5] += wt
            games += 1
            del g, sales
    print(f'{games} games in {time.time() - t0:.0f}s')
    print('split:', dict(val_all))
    print('refine status (steps with sells):', dict(status))
    print(f"money check on sell-only steps after refinement: {money_chk['exact']}/{money_chk['steps']} exact; abs error "
          f"{money_chk['abs_err']:.0f} of {money_chk['rev']:.0f} revenue")
    res = {'games': games, 'split': dict(val_all), 'refine': dict(status), 'money_check': dict(money_chk), 'tables': {}}

    def cell(a):
        if not a or not a[5]:
            return None
        return [v / a[5] for v in a[:5]] + [a[5]]

    for w, title in (('harv', 'weighted by the units harvested at that hour (the planner case)'),
                     ('sold', 'weighted by the units the player actually sold at that hour (nd-like)'),
                     ('hour', 'every (day, hour) equally')):
        print(f'\nCoins per unit: sell at the ready hour vs the next morning, {title}.')
        print('Cell = own gain - own cannibalization + rival loss = **margin** [rival units sold until the morning; weight]')
        print('| product | ' + ' | '.join(PNAME) + ' |')
        print('|---|' + '---|' * 5)
        for p in PRODUCTS:
            cells = []
            for per in range(5):
                c = cell(AG[w].get((p, per)))
                if c is None:
                    cells.append('-')
                    continue
                og, can, rl, oa, ru, wt = c
                cells.append(f'{og:+.1f} - {can:.1f} + {rl:.1f} = **{og - can + rl:+.1f}** [{ru:.0f}; {wt:.0f}]')
                res['tables'][f'{w}|{p}|{per}'] = {'own': og, 'cannibal': can, 'rival': rl, 'margin': og - can + rl,
                                                   'own_units_after': oa, 'rival_units': ru, 'weight': wt}
            print(f'| {p} | ' + ' | '.join(cells) + ' |')
    for w in ('harv', 'hour'):
        print(f'\nBy hour bin of the ready hour, all periods ({w}): **margin** (own gain / cannibal. / rival loss)')
        print('| product | h0-5 | h6-11 | h12-17 | h18-23 |')
        print('|---|---|---|---|---|')
        for p in PRODUCTS:
            cells = []
            for hb in range(4):
                c = cell(AG[w].get((p, 'hb%d' % hb)))
                if c is None:
                    cells.append('-')
                    continue
                og, can, rl, oa, ru, wt = c
                cells.append(f'**{og - can + rl:+.1f}** ({og:+.1f} / {can:.1f} / {rl:.1f}; n {wt:.0f})')
                res['tables'][f'{w}_hour|{p}|{hb}'] = {'own': og, 'cannibal': can, 'rival': rl, 'margin': og - can + rl,
                                                       'weight': wt}
            print(f'| {p} | ' + ' | '.join(cells) + ' |')
        print(f'\nBy period x hour bin ({w}): margin h0-5 / h6-11 / h12-17 / h18-23')
        print('| product | ' + ' | '.join(PNAME) + ' |')
        print('|---|' + '---|' * 5)
        for p in PRODUCTS:
            cells = []
            for per in range(5):
                sub = []
                for hb in range(4):
                    c = cell(AG[w].get((p, per, 'hb%d' % hb)))
                    sub.append('-' if c is None else f'{c[0] - c[1] + c[2]:+.0f}')
                    if c is not None:
                        res['tables'][f'{w}_ph|{p}|{per}|{hb}'] = {'own': c[0], 'cannibal': c[1], 'rival': c[2],
                                                                   'margin': c[0] - c[1] + c[2], 'weight': c[5]}
                cells.append(' / '.join(sub))
            print(f'| {p} | ' + ' | '.join(cells) + ' |')
    print('\nRole split (harvest-weighted): margin (rival loss) with the rival = DSM (me = the other team) | me = DSM')
    print('| product | ' + ' | '.join(PNAME) + ' |')
    print('|---|' + '---|' * 5)
    for p in PRODUCTS:
        cells = []
        for per in range(5):
            a = cell(AG['harv'].get((p, per, 'rivalDSM')))
            b = cell(AG['harv'].get((p, per, 'meDSM')))
            fa = '-' if a is None else f'{a[0] - a[1] + a[2]:+.1f} ({a[2]:.1f})'
            fb = '-' if b is None else f'{b[0] - b[1] + b[2]:+.1f} ({b[2]:.1f})'
            cells.append(f'{fa} / {fb}')
        print(f'| {p} | ' + ' | '.join(cells) + ' |')
    json.dump(res, open(OUT / 'credit_tables.json', 'w'), indent=1)


if __name__ == '__main__':
    {'extract': cmd_extract, 'report': cmd_report}[sys.argv[1]]()
