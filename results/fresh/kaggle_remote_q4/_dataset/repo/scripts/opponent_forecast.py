"""General forecast of a deterministic, shop-conditioned opponent from its recorded games.

Question: given only the shops revealed so far, how precisely can we predict what the opponent's farm
and sales will be on day N, and does the error compound or stay bounded?

The component is opponent-agnostic. It needs a library of the opponent's recorded games (days, board,
market orders — the format written by extract_mg_events.py) and predicts by nearest neighbours in a
shop-feature space built only from shops visible at the forecast origin. Mother-Goose is the first
instance; any opponent with a replay library can be plugged in.

Evaluation is leave-one-out over her 30 games. For each game, origin day o and horizon day d >= o, the
forecast uses only the shops visible at day o and the other 29 games. Baseline: the mean of all other
games (no shop information). Floor: pairs of games whose shops were identical through day d, which
bounds the error from her execution noise alone.
"""
import glob, json, statistics as st
from collections import Counter
from market_corpus import ROOT

SRC = ROOT / 'results/fresh/mg_policy'
OUT = ROOT / 'results/fresh/opponent_forecast'
DEMAND = {
    'BAKERY': ('EGG', 'WHEAT'), 'PIZZA_SHOP': ('MILK', 'TOMATO', 'WHEAT'),
    'BRUNCH_SPOT': ('EGG', 'WHEAT', 'STRAWBERRY'), 'YARN_STORE': ('WOOL', 'WOOL'),
    'ICE_CREAM_SHOP': ('STRAWBERRY', 'MILK', 'WHEAT'), 'PET_CAFE': ('CARROT', 'CARROT'),
    'SMOOTHIE_SHOP': ('STRAWBERRY', 'MILK'), 'FARMERS_MARKET': ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY')}
PRODUCTS = ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'EGG', 'MILK', 'WOOL')
BOARD = {'WH': 'WHEAT', 'ST': 'STRAWBERRY', 'TO': 'TOMATO', 'CA': 'CARROT', 'ME': 'MELON',
         'co': 'COW', 'sh': 'SHEEP', 'go': 'GOOSE'}
SELLABLE = ('STRAWBERRY', 'TOMATO', 'CARROT', 'MELON', 'MILK', 'WOOL', 'EGG', 'WHEAT', 'FERTILIZER')


def features(shops):
    """Shop-demand features: per-product demand units, plus the ordered first two shops (the route key
    V45-lineage policies read at day 6)."""
    f = Counter()
    for s in shops:
        for p in DEMAND.get(s, ()):
            f[p] += 1
    return f, tuple(shops[:2])


def distance(a, b):
    fa, ka = a
    fb, kb = b
    return sum(abs(fa[p] - fb[p]) for p in PRODUCTS) + (0 if ka == kb else 1.5)


def board_counts(day):
    c = Counter()
    for row in day['board']:
        for code in row:
            if code in BOARD:
                c[BOARD[code]] += 1
    return c


def sales_by_day(game):
    """Requested sale units per product per day, and the hour of each sale order."""
    out = [Counter() for _ in range(30)]
    hours = {p: Counter() for p in SELLABLE}
    for e in game['events']:
        if e['kind'] == 'market' and e['op'] == 'SELL' and e['item'] in SELLABLE:
            d = e['step'] // 24
            out[d][e['item']] += min(int(e['qty']), 1000)
            hours[e['item']][e['step'] % 24] += 1
    return out, hours


def load():
    games = []
    for path in sorted(glob.glob(str(SRC / 'events-*.json'))):
        g = json.loads(open(path, encoding='utf-8').read())
        g['boards'] = [board_counts(d) for d in g['days']]
        g['sales'], g['sale_hours'] = sales_by_day(g)
        games.append(g)
    return games


def forecast(target, library, origin, day, k=3):
    """Predict the target's board and sales on `day` from shops visible at `origin`."""
    ft = features(target['days'][origin]['shops'])
    ranked = sorted(library, key=lambda g: distance(ft, features(g['days'][origin]['shops'])))
    near = ranked[:k]
    board = Counter()
    sales = Counter()
    for g in near:
        for key, v in g['boards'][day].items():
            board[key] += v / len(near)
        for key, v in g['sales'][day].items():
            sales[key] += v / len(near)
    return board, sales


def err(pred, actual, keys):
    return sum(abs(pred.get(k, 0) - actual.get(k, 0)) for k in keys)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    games = load()
    keys = sorted(set(BOARD.values()))
    print('## 1. Board forecast error (sum of |predicted - actual| plant/animal counts over all types)')
    print('   origin = forecast made at that day; horizon = the day being predicted; 30-game leave-one-out')
    summary = {}
    print(f"{'origin':>6s} {'horizon':>7s} {'kNN(shops)':>11s} {'no-shop mean':>13s} {'noise floor':>12s} {'productive tiles':>17s}")
    for origin, horizons in ((0, (5, 12, 18, 24)), (6, (8, 12, 18, 24)), (12, (12, 15, 18, 21, 24, 27)),
                             (18, (18, 21, 24, 27))):
        for day in horizons:
            e_knn, e_mean, floor = [], [], []
            for i, g in enumerate(games):
                lib = games[:i] + games[i + 1:]
                pb, _ = forecast(g, lib, origin, day)
                e_knn.append(err(pb, g['boards'][day], keys))
                mean = Counter()
                for h in lib:
                    for kk, v in h['boards'][day].items():
                        mean[kk] += v / len(lib)
                e_mean.append(err(mean, g['boards'][day], keys))
                for h in lib:
                    if h['days'][day]['shops'] == g['days'][day]['shops'] and h['episode'] > g['episode']:
                        floor.append(err(h['boards'][day], g['boards'][day], keys))
            tiles = st.mean(sum(g['boards'][day].values()) for g in games)
            fl = f"{st.mean(floor):6.1f} (n={len(floor)})" if floor else '      -'
            print(f"{origin:6d} {day:7d} {st.mean(e_knn):11.1f} {st.mean(e_mean):13.1f} {fl:>12s} {tiles:17.1f}")
            summary[f'{origin}->{day}'] = dict(knn=st.mean(e_knn), mean=st.mean(e_mean), floor=floor, tiles=tiles)

    print('\n## 2. Sale forecast: requested sale units per product per day, forecast from shops visible at day 12')
    print(f"{'product':>11s} {'units/day (actual)':>19s} {'MAE kNN':>8s} {'MAE mean':>9s} {'peak-day hit (kNN)':>19s} {'peak-day hit (mean)':>20s}")
    for p in ('STRAWBERRY', 'TOMATO', 'CARROT', 'MILK', 'WOOL', 'EGG', 'MELON', 'WHEAT'):
        mae_k, mae_m, hit_k, hit_m, level = [], [], 0, 0, []
        for i, g in enumerate(games):
            lib = games[:i] + games[i + 1:]
            pk, pm, act = [], [], []
            for day in range(12, 30):
                _, s = forecast(g, lib, 12, day)
                pk.append(s.get(p, 0))
                pm.append(st.mean(h['sales'][day].get(p, 0) for h in lib))
                act.append(g['sales'][day].get(p, 0))
            mae_k.append(st.mean(abs(a - b) for a, b in zip(pk, act)))
            mae_m.append(st.mean(abs(a - b) for a, b in zip(pm, act)))
            level.append(st.mean(act))
            if max(act) > 0:
                peak = act.index(max(act))
                hit_k += abs(pk.index(max(pk)) - peak) <= 1
                hit_m += abs(pm.index(max(pm)) - peak) <= 1
        print(f"{p:>11s} {st.mean(level):19.1f} {st.mean(mae_k):8.1f} {st.mean(mae_m):9.1f} {f'{hit_k}/30':>19s} {f'{hit_m}/30':>20s}")

    print('\n## 3. Hour of day at which she places sale orders (all 30 games pooled)')
    for p in ('STRAWBERRY', 'TOMATO', 'MILK', 'WOOL', 'EGG', 'MELON', 'CARROT'):
        h = Counter()
        for g in games:
            h.update(g['sale_hours'][p])
        tot = sum(h.values())
        if not tot:
            continue
        top = ', '.join(f'h{hr}:{100 * n / tot:.0f}%' for hr, n in h.most_common(4))
        print(f'   {p:11s} {tot:5d} orders | most common hours {top}')
    (OUT / 'mg_forecast_summary.json').write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')


if __name__ == '__main__':
    main()
