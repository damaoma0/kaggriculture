"""Abandonment research (2026-09-26): one row per animal of ours (and of the rival) from the replays of
scripts/abandon_replay.py, with the moment feeding stopped, the productions it forfeited, the market at that moment and
the maintenance module's own hour-0 verdict reconstructed from the recorded dawn state and dawn quotes.

Row fields: side, ep, who (0 ours / 1 rival), kind, x, y, placed, last_fed, stop (first unfed day of the final unfed
run), escape (night; None = alive at the end), made (units produced), prods (production nights with a yield),
lost_nights (production nights on nights >= escape that would still fall on nights <= 28), lost_units_min (1 a
night = fed only), lost_units_full (1 + interval a night = fed and cared), bank_lost_stop (the bank wiped on the stop
night if that was a production night), cls: never (placed too late to ever produce) | end_of_life (no production
lost) | mid (at least one production lost) | alive,
q_prod / q_wheat / q_fert = dawn quotes on the stop day, real_prev = our realised sale price of the product on the
2 days before the stop day, real_rest = our realised price from the stop day to the end, herd = our live animals of
that kind at dawn of the stop day, shops = shop instances buying the product that day,
mod_feed = the module's hour-0 plan fed on the stop day / the day before (1 / 0; ours only; collect=True as in KS1).
usage: abandon_animals.py <side,...> <panel> -> results/fresh/abandon_20260926/animals.json + printed summary
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
AN = E.ANIMALS
P = E.PRODUCTS
PI = {p: i for i, p in enumerate(P)}
PROD = {'COW': 'MILK', 'SHEEP': 'WOOL', 'GOOSE': 'EGG'}
RDIR = ROOT / 'results/fresh/abandon_20260926/replay'
OUT = ROOT / 'results/fresh/abandon_20260926'
_NS = {}


def sm():
    if not _NS:
        exec(compile((ROOT / 'scripts/fragments/sem_maintenance.py').read_text(encoding='utf-8'), 'sm', 'exec'), _NS)
    return _NS


def quote(R, item, t):
    return E.market_price(item, R['inv'][min(t, 719)][PI[item]])


def prod_nights(kind, placed):
    a = AN[kind]
    return [n for n in range(placed, 29) if (n + 1 - placed - a['first_yield_day']) >= 0
            and (n + 1 - placed - a['first_yield_day']) % a['interval'] == 0]


def shops_on(tape, day, item):
    sh = list(tape['shops'][:min(8, day // 3)])
    return sum(1 for s in sh if item in E.SHOPS[s])


def module_feed(kind, placed, dawn_row, R, h=0):
    d, cu, bank, yu, fa = dawn_row
    t = d * 24 + h
    pr, wp, fp = quote(R, PROD[kind], t), quote(R, 'WHEAT', t), quote(R, 'FERTILIZER', t)
    p = sm()['sm_tile_plan'](kind, (placed, cu, bank, yu, False, False), d, h, pr, wp, False, 8, 0.0,
                             collect_price=fp, avail=bool(fa))
    return None if p['combo'] is None else int(p['combo'][0])


def rows_for(side, ep, tape):
    R = json.loads((RDIR / side / f'{ep}.json').read_text(encoding='utf-8'))
    sales = defaultdict(list)          # (who, item, day) -> prices
    for st, who, op, item, price, inv0 in R['trades']:
        if op == 'SELL':
            sales[(who, item, st // 24)].append(price)
    herd = Counter()
    for k, a in R['animals'].items():
        who, x, y, pd, kind = k.split(',')
        for dw in a['dawn']:
            herd[(int(who), kind, dw[0])] += 1
    out = []
    for k, a in R['animals'].items():
        who, x, y, pd, kind = k.split(',')
        who, x, y, pd = int(who), int(x), int(y), int(pd)
        nights = a['nights']
        fed_days = [n[0] for n in nights if n[1]]
        esc = [n[0] for n in nights if n[7]]
        escape = esc[0] if esc else None
        last_fed = max(fed_days) if fed_days else None
        stop = (escape - 1) if escape is not None else None
        pn = prod_nights(kind, pd)
        made = sum(n[6] for n in nights)
        prods = sum(1 for n in nights if n[5] and n[6] > 0)
        lost = [n for n in pn if escape is not None and n >= escape]
        iv = AN[kind]['interval']
        bank_lost_stop = 0
        if stop is not None:
            ns_ = [n for n in nights if n[0] == stop]
            if ns_ and ns_[0][5] and not ns_[0][1]:
                bank_lost_stop = ns_[0][3]
        if not pn:
            cls = 'never'
        elif escape is None:
            cls = 'alive'
        elif lost:
            cls = 'mid'
        else:
            cls = 'end_of_life'
        row = dict(side=side, ep=ep, who=who, kind=kind, x=x, y=y, placed=pd, last_fed=last_fed, stop=stop,
                   escape=escape, made=made, prods=prods, lost_nights=len(lost), lost_units_min=len(lost),
                   lost_units_full=len(lost) * (1 + iv), bank_lost_stop=bank_lost_stop, cls=cls)
        if stop is not None and stop >= 0:
            item = PROD[kind]
            t = stop * 24
            row.update(q_prod=quote(R, item, t), q_wheat=quote(R, 'WHEAT', t), q_fert=quote(R, 'FERTILIZER', t),
                       herd=herd.get((who, kind, stop), 0), shops=shops_on(tape, stop, item))
            prev = sales.get((who, item, stop - 1), []) + sales.get((who, item, stop - 2), [])
            rest = [p for d in range(stop, 30) for p in sales.get((who, item, d), [])]
            row['real_prev'] = round(sum(prev) / len(prev), 1) if prev else None
            row['real_rest'] = round(sum(rest) / len(rest), 1) if rest else None
            row['n_rest'] = len(rest)
            rprev = sales.get((1 - who, item, stop - 1), []) + sales.get((1 - who, item, stop - 2), [])
            row['rival_prev'] = round(sum(rprev) / len(rprev), 1) if rprev else None
            if who == 0 and cls == 'mid':
                dm = {dw[0]: dw for dw in a['dawn']}
                row['mod_feed'] = [module_feed(kind, pd, dm[d], R) if d in dm else None for d in (stop - 1, stop)]
                row['mod_feed_h12'] = [module_feed(kind, pd, dm[d], R, 12) if d in dm else None for d in (stop - 1, stop)]
        out.append(row)
    return out, R


def main():
    sides = sys.argv[1].split(',')
    games = Path(sys.argv[2]).read_text().replace(',', ' ').split()
    rows = []
    for g in games:
        team, ep = g.split(':')
        tape = UE.load_tape(int(team), int(ep))
        for side in sides:
            r, _ = rows_for(side, ep, tape)
            rows += r
    (OUT / 'animals.json').write_text(json.dumps(rows), encoding='utf-8')
    n = len(games)
    print(f'{n} worlds; per world counts of OUR animals by class and kind (escapes on nights >= 11 only for "mid")')
    for side in sides:
        C = Counter()
        L = Counter()
        for r in rows:
            if r['side'] != side or r['who'] != 0:
                continue
            if r['cls'] == 'mid' and r['escape'] < 11:
                continue
            C[(r['kind'], r['cls'])] += 1
            if r['cls'] == 'mid':
                L[r['kind']] += r['lost_units_full']
        s = ' | '.join(f"{kd}: " + ' '.join(f"{c} {C[(kd, c)] / n:.2f}" for c in ('mid', 'end_of_life', 'never', 'alive'))
                       + f" lostU {L[kd] / n:.1f}" for kd in ('COW', 'SHEEP', 'GOOSE'))
        print(f'{side:6s} {s}')


if __name__ == '__main__':
    main()
