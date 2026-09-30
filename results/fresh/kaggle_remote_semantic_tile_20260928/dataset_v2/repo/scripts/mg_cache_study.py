"""The shed as a price cache: what holding stock returns, measured on Mother-Goose's 72 replays (offline).

Input: results/fresh/mg_watch/hourly.json (scripts/mg_cache_extract.py). Output: results/fresh/mg_watch/cache_study.json
  1. intraday price profile: price at hour h over that day's mean price, days 10-28, by product
  2. who sells when: units by hour of day, her and her opponents
  3. her realised carry: every unit is matched first-in-first-out from the step it reached her SHED to the step it was
     sold (a unit delivered and sold in the same step holds 0 hours); gain = price when sold - price when it arrived
  4. counterfactual timing on her own arrival stream (own price impact and the 100-item cap ignored, so these are
     ceilings): sell on arrival / hold to hour 0 of the next day / hold to the best hour of the next morning (0-6) /
     perfect hindsight within 24 hours; plus the risk - how often the price next morning is below the arrival price
  5. capacity: how full her shed runs, and how close the midnight auto-drop comes to the 100 cap
"""
import json
import random
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = json.loads((ROOT / 'results/fresh/mg_watch/hourly.json').read_text())
P = D['products']
STORABLE = ['WOOL', 'MILK', 'EGG', 'STRAWBERRY', 'TOMATO', 'CARROT', 'MELON']   # never picked back up from the shed


def boot(xs, n=2000, seed=3):
    if len(xs) < 3:
        return (None, None)
    rng = random.Random(seed)
    m = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(n))
    return round(m[int(0.025 * n)], 2), round(m[int(0.975 * n)], 2)


def intraday(games, pi, lo=10, hi=28):
    rel = [[] for _ in range(24)]
    for g in games:
        pr = g['price'][pi]
        for d in range(lo, hi + 1):
            day = pr[d * 24:(d + 1) * 24]
            mean = sum(day) / 24.0
            if mean < 5:
                continue
            for h in range(24):
                rel[h].append(day[h] / mean)
    return [round(sum(x) / max(1, len(x)), 3) for x in rel]


def by_hour(games, pi, key):
    out = [0.0] * 24
    for g in games:
        for s in g[key]:
            if s[1] == pi:
                out[s[0] % 24] += s[2]
    return [round(v / max(1, len(games)), 1) for v in out]


def fifo(g, pi):
    """[(arrival_step, sale_step, price_at_arrival, price_at_sale)] per unit she sold."""
    shed, price = g['shed'][pi], g['price'][pi]
    sold = defaultdict(int)
    lots = defaultdict(list)
    for s in g['sells']:
        if s[1] == pi:
            sold[s[0]] += s[2]
            lots[s[0]].append(s)
    queue, out = [], []
    for u in range(shed[0]):
        queue.append(0)
    for t in range(len(shed) - 1):
        arrivals = shed[t + 1] - shed[t] + sold.get(t, 0)       # net deposits during step t (before the market)
        for _ in range(max(0, arrivals)):
            queue.append(t)
        for s in lots.get(t, []):
            for _ in range(s[2]):
                a = queue.pop(0) if queue else t
                out.append((a, t, price[a], s[3]))
    return out


def counterfactual(g, pi):
    """Per arriving unit: price on arrival, at hour 0 next day, best of next morning 0-6, best within 24 h."""
    shed, price = g['shed'][pi], g['price'][pi]
    sold = defaultdict(int)
    for s in g['sells']:
        if s[1] == pi:
            sold[s[0]] += s[2]
    rows = []
    for t in range(len(shed) - 1):
        n = shed[t + 1] - shed[t] + sold.get(t, 0)
        if n <= 0 or t // 24 >= 28:
            continue
        nd = (t // 24 + 1) * 24
        morning = price[nd:nd + 7]
        rows.append((n, t % 24, price[t], price[nd], max(morning), sum(morning) / len(morning), max(price[t:t + 25])))
    return rows


def main():
    out = {}
    for era in ('old', 'new', 'all'):
        games = [g for g in D['games'] if era == 'all' or g['era'] == era]
        print(f'\n=================== era {era}: {len(games)} games')
        res = out.setdefault(era, {})
        for p in STORABLE:
            pi = P.index(p)
            prof = intraday(games, pi)
            hers, theirs = by_hour(games, pi, 'sells'), by_hour(games, pi, 'rsells')
            units = [x for g in games for x in fifo(g, pi)]
            if not units:
                continue
            hold = [s - a for a, s, _, _ in units]
            gain = [ps - pa for _, _, pa, ps in units]
            per_game = [sum(ps - pa for _, _, pa, ps in fifo(g, pi)) for g in games]
            cf = [r for g in games for r in counterfactual(g, pi)]
            n = sum(r[0] for r in cf)
            w = lambda k: sum(r[0] * r[k] for r in cf) / max(1, n)
            worse = sum(r[0] for r in cf if r[5] < r[2]) / max(1, n)
            res[p] = dict(intraday=prof, her_units_by_hour=hers, opp_units_by_hour=theirs, units=len(units),
                          hold_same_step=round(sum(1 for h in hold if h == 0) / len(hold), 3),
                          hold_median_h=st.median(hold), hold_mean_h=round(sum(hold) / len(hold), 1),
                          share_held_over_6h=round(sum(1 for h in hold if h > 6) / len(hold), 3),
                          gain_per_unit=round(sum(gain) / len(gain), 2), gain_per_game=round(sum(per_game) / len(games)),
                          gain_per_game_ci=boot(per_game), cf_arrival=round(w(2), 1), cf_next_h0=round(w(3), 1),
                          cf_next_morning_best=round(w(4), 1), cf_next_morning_mean=round(w(5), 1), cf_best_24h=round(w(6), 1),
                          share_next_morning_below_arrival=round(worse, 3))
            r = res[p]
            print(f'\n{p}: {r["units"] / len(games):.0f} units/game')
            print('  intraday price/day-mean by hour :', ' '.join(f'{v:.2f}' for v in prof))
            print('  her units/game by hour          :', ' '.join(f'{v:4.1f}' for v in hers))
            print('  opponents units/game by hour    :', ' '.join(f'{v:4.1f}' for v in theirs))
            print(f'  her hold: same step {r["hold_same_step"]:.0%}, median {r["hold_median_h"]} h, mean {r["hold_mean_h"]} h, '
                  f'held >6 h {r["share_held_over_6h"]:.0%}; realised gain vs price on arrival {r["gain_per_unit"]:+.1f}/unit, '
                  f'{r["gain_per_game"]:+,} per game {r["gain_per_game_ci"]}')
            print(f'  ceilings on her arrival stream (no own impact): on arrival {r["cf_arrival"]}, next day hour 0 {r["cf_next_h0"]}, '
                  f'next morning mean {r["cf_next_morning_mean"]} / best {r["cf_next_morning_best"]}, best within 24 h {r["cf_best_24h"]}; '
                  f'next morning below arrival for {r["share_next_morning_below_arrival"]:.0%} of units')
        full = [max(g['shed_total'][d * 24:(d + 1) * 24]) for g in games for d in range(10, 29)]
        night = [g['shed_total'][d * 24 + 23] + sum(g['carried'][i][d * 24 + 23] for i in range(len(P))) for g in games for d in range(10, 29)]
        res['capacity'] = dict(daily_max_shed_mean=round(sum(full) / len(full), 1), share_days_shed_over_90=round(sum(1 for x in full if x >= 90) / len(full), 3),
                               night_load_mean=round(sum(night) / len(night), 1), share_nights_over_100=round(sum(1 for x in night if x > 100) / len(night), 3),
                               share_nights_over_90=round(sum(1 for x in night if x > 90) / len(night), 3))
        print('\n  capacity (days 10-28):', res['capacity'])
    (ROOT / 'results/fresh/mg_watch/cache_study.json').write_text(json.dumps(out, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
