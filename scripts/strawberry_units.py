"""Item-by-item strawberry lives, the leader's game vs arms, one world (days 11-29): every strawberry harvested by our
farm is followed first-in-first-out through the hand that carries it and the shed - harvest step and tile, arrival in the
shed (a daytime delivery or the midnight dump) or deletion, sale step and price. DSM's k-th sold strawberry is paired
with each arm's k-th; the delay splits into harvested later / carried longer / waited longer in the shed. Writes JSON and
an HTML table; prints a summary.
usage: strawberry_units.py <team:ep> <ARM>[,<ARM>...] <out.html>"""
import html
import json
import sys
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
P = 'STRAWBERRY'
R = {'w': None, 'seat': 0, 't': 0}
_ua, _drop, _commit = E._apply_unit_action, E._drop_inventories_to_shed, E._commit_unit


class Life:
    def __init__(self):
        self.hands = {}                                # unit -> deque of [harvest step, tile]
        self.shed = deque()                            # [harvest step, tile, arrival step, how]
        self.sold = []                                 # dicts
        self.deleted = []

    def hand(self, u):
        return self.hands.setdefault(u, deque())


LF = {'cur': None}


def ua(farm, private, idx, action, *a, **k):
    w = R['w']
    if w is None or farm is not w.farms[R['seat']] or R['t'] < 264:
        return _ua(farm, private, idx, action, *a, **k)
    L = LF['cur']
    inv0 = int(((private['inventories'][idx] if idx < len(private['inventories']) else {}) or {}).get(P, 0) or 0)
    sh0 = int(private['shed'].get(P, 0) or 0)
    pos = tuple(farm['farmer'] if idx == 0 else farm['hands'][idx - 1])
    r = _ua(farm, private, idx, action, *a, **k)
    inv1 = int(((private['inventories'][idx] if idx < len(private['inventories']) else {}) or {}).get(P, 0) or 0)
    sh1 = int(private['shed'].get(P, 0) or 0)
    H = L.hand(idx)
    if inv1 > inv0 and sh1 == sh0:                     # harvest
        for _ in range(inv1 - inv0):
            H.append([R['t'], pos[1] * 10 + pos[0]])
    elif inv1 < inv0 and sh1 > sh0:                    # into the shed during the day
        for _ in range(min(inv0 - inv1, sh1 - sh0)):
            if H:
                hs, tile = H.popleft()
                L.shed.append([hs, tile, R['t'], 'day'])
    return r


def drop(private, cap):
    w = R['w']
    if w is None or private is not w.private(R['seat']) or R['t'] < 264:
        return _drop(private, cap)
    L = LF['cur']
    sh0 = int(private['shed'].get(P, 0) or 0)
    carried = [(u, int((inv or {}).get(P, 0) or 0)) for u, inv in enumerate(private['inventories'])]
    r = _drop(private, cap)
    moved = int(private['shed'].get(P, 0) or 0) - sh0
    for u, n in carried:                               # engine order: farmer first, then the hands by index
        H = L.hand(u)
        for _ in range(n):
            if not H:
                break
            hs, tile = H.popleft()
            if moved > 0:
                L.shed.append([hs, tile, R['t'], 'night'])
                moved -= 1
            else:
                L.deleted.append([hs, tile, R['t']])
    return r


def commit(op, item, price, farm, private, market, cap=100):
    r = _commit(op, item, price, farm, private, market, cap)
    w = R['w']
    if r and w is not None and op == 'SELL' and item == P and farm is w.farms[R['seat']] and R['t'] >= 264:
        L = LF['cur']
        if L.shed:
            hs, tile, ar, how = L.shed.popleft()
        else:
            hs, tile, ar, how = None, None, None, 'pre-day-11'
        L.sold.append({'h': hs, 'tile': tile, 'a': ar, 'how': how, 's': R['t'], 'p': price})
    return r


E._apply_unit_action, E._drop_inventories_to_shed, E._commit_unit = ua, drop, commit


def play(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    L = Life()
    LF['cur'] = L
    R.update(w=w, seat=seat)
    shed0 = None
    while w.t < 719:
        t = w.t
        R['t'] = t
        if t == 264:                                   # strawberries already in the shed on the day-11 morning
            for _ in range(int(w.private(seat)['shed'].get(P, 0) or 0)):
                L.shed.append([None, None, None, 'pre-day-11'])
            for u, inv in enumerate(w.private(seat)['inventories']):
                for _ in range(int((inv or {}).get(P, 0) or 0)):
                    L.hand(u).append([None, None])
        own = UE.tape_action(tape['actions'], t) if (stream is None or t < 264) else (stream[t] if isinstance(stream[t], dict) and stream[t] else dict(UE.PASS))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    R['w'] = None
    return L


def fmt(t):
    return '' if t is None else f'd{t // 24} h{t % 24}'


if __name__ == '__main__':
    g, arms, out = sys.argv[1], sys.argv[2].split(','), sys.argv[3]
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    lives = {'DSM': play(tape, None)}
    for a in arms:
        s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{a.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
        lives[a] = play(tape, s)
    D = lives['DSM'].sold
    summary = {}
    rows = {}
    for a in arms:
        A = lives[a].sold
        c = Counter()
        rr = []
        for k in range(max(len(D), len(A))):
            d = D[k] if k < len(D) else None
            x = A[k] if k < len(A) else None
            row = {'k': k + 1, 'd': d, 'x': x}
            if d and x:
                c['pairs'] += 1
                c['dp'] += x['p'] - d['p']
                ds = x['s'] - d['s']
                c['later' if ds > 0 else ('same' if ds == 0 else 'earlier')] += 1
                if d['h'] is not None and x['h'] is not None and d['a'] is not None and x['a'] is not None:
                    row['dh'] = x['h'] - d['h']
                    row['dc'] = (x['a'] - x['h']) - (d['a'] - d['h'])
                    row['dw'] = (x['s'] - x['a']) - (d['s'] - d['a'])
                    c['sum_dh'] += row['dh']
                    c['sum_dc'] += row['dc']
                    c['sum_dw'] += row['dw']
                    c['n_split'] += 1
                    c['night_' + x['how']] += 1
                    c['dsm_' + d['how']] += 1
            elif d:
                c['dsm_only'] += 1
                c['dsm_only_$'] += d['p']
            else:
                c['ours_only'] += 1
                c['ours_only_$'] += x['p']
            rr.append(row)
        rows[a] = rr
        summary[a] = dict(c, deleted=len(lives[a].deleted))
    summary['DSM'] = {'sold': len(D), 'deleted': len(lives['DSM'].deleted), 'day_arrivals': sum(1 for x in D if x['how'] == 'day')}
    for a in arms:
        c = summary[a]
        n = max(1, c.get('n_split', 0))
        print(f'{a} vs DSM on {g}: {c.get("pairs", 0)} paired units, our price - DSM {c.get("dp", 0):+.0f} total; sold same step {c.get("same", 0)}, later '
              f'{c.get("later", 0)}, earlier {c.get("earlier", 0)} | DSM-only {c.get("dsm_only", 0)} ({c.get("dsm_only_$", 0):.0f}), ours-only '
              f'{c.get("ours_only", 0)} ({c.get("ours_only_$", 0):.0f}) | deleted {c["deleted"]} (DSM {summary["DSM"]["deleted"]})')
        print(f'   per paired unit (ours - DSM, hours): harvested later {c.get("sum_dh", 0) / n:+.1f}, carried longer {c.get("sum_dc", 0) / n:+.1f}, '
              f'waited longer in the shed {c.get("sum_dw", 0) / n:+.1f} | our units arrived by day {c.get("night_day", 0)} / at midnight '
              f'{c.get("night_night", 0)}; DSM\'s by day {c.get("dsm_day", 0)} / midnight {c.get("dsm_night", 0)}')
    Path(out).with_suffix('.json').write_text(json.dumps({'summary': summary, 'rows': rows}, default=str), encoding='utf-8')
    # HTML
    head = ''.join(f'<th colspan="5">{html.escape(a)}</th><th colspan="4">{html.escape(a)} - DSM</th>' for a in arms)
    sub = ''.join('<th>harvest</th><th>tile</th><th>arrived</th><th>sold</th><th>price</th><th>harv</th><th>carry</th><th>shed</th><th>price</th>' for _ in arms)
    body = []
    for k in range(max(len(rows[a]) for a in arms)):
        d = D[k] if k < len(D) else None
        cells = [f'<td>{k + 1}</td>']
        if d:
            cells += [f'<td>{fmt(d["h"])}</td><td>{d["tile"] if d["tile"] is not None else ""}</td><td>{fmt(d["a"])} {d["how"] if d["how"] != "night" else "(night)"}</td><td>{fmt(d["s"])}</td><td>{d["p"]:.0f}</td>']
        else:
            cells += ['<td colspan="5">-</td>']
        for a in arms:
            r = rows[a][k] if k < len(rows[a]) else {}
            x = r.get('x')
            if x:
                cells.append(f'<td>{fmt(x["h"])}</td><td>{x["tile"] if x["tile"] is not None else ""}</td><td>{fmt(x["a"])} {x["how"] if x["how"] != "night" else "(night)"}</td><td>{fmt(x["s"])}</td><td>{x["p"]:.0f}</td>')
            else:
                cells.append('<td colspan="5">-</td>')
            if x and d:
                dp = x['p'] - d['p']
                cls = 'neg' if dp < -5 else ('pos' if dp > 5 else '')
                cells.append(f'<td>{r.get("dh", "")}</td><td>{r.get("dc", "")}</td><td>{r.get("dw", "")}</td><td class="{cls}">{dp:+.0f}</td>')
            else:
                cells.append('<td colspan="4"></td>')
        body.append('<tr>' + ''.join(cells) + '</tr>')
    summ = '<br>'.join(html.escape(f'{a}: {json.dumps(summary[a])}') for a in arms + ['DSM'])
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Strawberry item trace</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a65;--grid:#e6e3dc;--neg:#c0553a;--pos:#2f6f5e}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#16171a;--fg:#ecebe6;--muted:#a09e97;--grid:#2c2e33;--neg:#e07a5f;--pos:#5fb39b}}}}
:root[data-theme="dark"]{{--bg:#16171a;--fg:#ecebe6;--muted:#a09e97;--grid:#2c2e33;--neg:#e07a5f;--pos:#5fb39b}}
body{{background:var(--bg);color:var(--fg);font:13px/1.4 system-ui,sans-serif;margin:0;padding:16px}}
h1{{font-size:20px;margin:0 0 6px}} p{{color:var(--muted);margin:4px 0 12px}}
.wrap{{overflow-x:auto}} table{{border-collapse:collapse;white-space:nowrap}} th,td{{border-bottom:1px solid var(--grid);padding:3px 6px;text-align:right}}
th{{position:sticky;top:0;background:var(--bg)}} .neg{{color:var(--neg);font-weight:600}} .pos{{color:var(--pos);font-weight:600}}
</style></head><body><h1>Strawberry item trace</h1>
<p>World {html.escape(g)}. Row k = DSM's k-th strawberry sold (days 11-29) next to each arm's k-th. Harvest / arrival in the shed ((night) = the midnight
dump) / sale step and price; the difference columns split the extra time into harvested later, carried longer and waited longer in the shed (hours), and
the price difference. Units are followed first-in-first-out through the hand that harvested them and the shed.</p>
<p>{summ}</p>
<div class="wrap"><table><thead><tr><th>k</th><th colspan="5">DSM</th>{head}</tr><tr><th></th><th>harvest</th><th>tile</th><th>arrived</th><th>sold</th><th>price</th>{sub}</tr></thead>
<tbody>{"".join(body)}</tbody></table></div></body></html>'''
    Path(out).write_text(page, encoding='utf-8')
    print('written', out)
