"""Prices and sales by product, the leader's game vs our season games (same world, same frozen opponent), for
viz/sales_prices.html. Each game is replayed with the official engine; every step records the market price, the market's
extra stock (inventory - 10,000, what sets the price), both players' holdings (shed + carried) and every SELL commit.

usage: build_sales_viz.py [arm,...] [team:ep,...] [output name]   (defaults: k4f,k4nt, the three season worlds, sales_prices.html)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
PRODUCTS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER']
I0 = 10000
_orig = E._commit_unit
REC = {'w': None, 'seat': 0, 't': 0, 'sales': None}


def _hook(op, item, price, farm, private, market, shed_capacity=100):
    r = _orig(op, item, price, farm, private, market, shed_capacity)
    w = REC['w']
    if r and w is not None and op == 'SELL' and item in PRODUCTS:
        side = 0 if farm is w.farms[REC['seat']] else 1
        key = (REC['t'], side, item)
        u, v = REC['sales'].get(key, (0, 0.0))
        REC['sales'][key] = (u + 1, v + float(price))
    return r


E._commit_unit = _hook


def holdings(priv):
    h = {p: int(priv['shed'].get(p, 0) or 0) for p in PRODUCTS}
    for inv in priv.get('inventories') or []:
        for p in PRODUCTS:
            h[p] += int((inv or {}).get(p, 0) or 0)
    return h


def replay(tape, stream_actions):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    REC.update(w=w, seat=seat, sales={})
    price = {p: [] for p in PRODUCTS}
    stock = {p: [] for p in PRODUCTS}
    hold = [{p: [] for p in PRODUCTS}, {p: [] for p in PRODUCTS}]
    while w.t < 720:
        t = w.t
        REC['t'] = t
        m = w.market
        h0, h1 = holdings(w.private(seat)), holdings(w.private(1 - seat))
        for p in PRODUCTS:
            price[p].append(int(m['prices'][p]))
            stock[p].append(int(m['inventory'][p]) - I0)
            hold[0][p].append(h0[p])
            hold[1][p].append(h1[p])
        if stream_actions is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream_actions[t] if t < len(stream_actions) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    fin = [float(w.farms[seat]['money']), float(w.farms[1 - seat]['money'])]
    sales = {p: [[], []] for p in PRODUCTS}
    for (t, side, item), (u, v) in sorted(REC['sales'].items()):
        sales[item][side].append([t, u, round(v, 1)])
    REC['w'] = None
    return dict(final=fin, price=price, stock=stock, hold=hold, sales=sales)


def main():
    arms = (sys.argv[1] if len(sys.argv) > 1 else 'k4f,k4nt').split(',')
    games = (sys.argv[2] if len(sys.argv) > 2 else
             '16730612:112444381,16732748:112661570,16732748:112673479').split(',')
    labels = {}
    try:
        import sector_run as SR
        for k, v in SR.LABEL.items():
            labels[k.lower()] = v
    except Exception:
        pass
    out = {'products': PRODUCTS, 'worlds': []}
    for g in games:
        team, ep = g.split(':')
        tape = UE.load_tape(int(team), int(ep))
        wd = {'episode': ep, 'games': {}}
        wd['games']['leader'] = dict(replay(tape, None), label="Leader's game (the recorded episode)")
        for a in arms:
            f = ROOT / 'results/fresh/day12_viz' / f'{a}_streams' / f'{ep}.json'
            if not f.exists():
                continue
            s = json.loads(f.read_text(encoding='utf-8'))
            if s.get('mode') != 'multi':
                continue                               # only full-season streams
            r = replay(tape, s['actions'])
            mf = ROOT / 'results/fresh/sector_20260925/multi' / a.upper() / f'{ep}.json'
            chk = None
            if not mf.exists():
                mf = next((p for p in (ROOT / 'results/fresh/sector_20260925/multi').glob('*/' + f'{ep}.json')
                           if p.parent.name.lower() == a), None)
            if mf and mf.exists():
                mm = json.loads(mf.read_text())['money']['30']
                chk = abs(mm[0] - r['final'][0]) < 0.5 and abs(mm[1] - r['final'][1]) < 0.5
            wd['games'][a] = dict(r, label=labels.get(a, a), check=chk)
            print(ep, a, 'final', r['final'], 'matches season run' if chk else 'CHECK %s' % chk, flush=True)
        out['worlds'].append(wd)
    tpl = (ROOT / 'viz' / 'sales_prices_template.html').read_text(encoding='utf-8')
    html = tpl.replace('/*__DATA__*/null', json.dumps(out, separators=(',', ':')))
    dst = ROOT / 'viz' / (sys.argv[3] if len(sys.argv) > 3 else 'sales_prices.html')
    dst.write_text(html, encoding='utf-8')
    print('wrote', dst, '%.2f MB' % (len(html) / 1e6))


if __name__ == '__main__':
    main()
