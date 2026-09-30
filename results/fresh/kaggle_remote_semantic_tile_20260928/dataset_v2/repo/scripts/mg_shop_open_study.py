"""Event study of Mother-Goose (MG) behaviour around new-shop openings.

Tests the hypothesis: "she banks inventory before a new shop opens and dumps it at
hour 0 into the fresh demand." Offline analysis only, over the recorded 72-game
hourly trace in results/fresh/mg_watch/hourly.json (30 old-era + 42 new-era games,
720 steps/game, both farms). Nothing is simulated here; every number below is read
directly off the recorded price/glut/shed/carried/sells arrays.

A new shop (index i, 0..7) opens at hour 0 of day D = 3*(i+1), i.e. D in
{3,6,...,24}; its type is drawn independently each game and is not knowable before
it opens. For a product p, an opening is RELEVANT if that shop type buys p, else
IRRELEVANT (same event, so it is a same-day control for the two players and for
other products).

Q1 (sale volume around an opening): for each (event, product) with any sales in the
7-day window D-3..D+3, normalise her daily sold units by her own window mean
(controls for game-to-game and product-to-product scale), and separately normalise
hour-0/1 sold units by the *uniform-across-the-day* share of that same window mean
(2/24 of it) -- a value above 1 means hour 0-1 sells more than its even share of the
day. Both are reported for relevant vs irrelevant events, per era, with the
opponent's sells (rsells) as a reference population classified by the same events.

Q2 (price/glut response): daily-mean and hour-0/hour-23 price and glut, expressed as
a level change from day D-1, for relevant vs irrelevant openings (same-day openings
are the control for the seasonal/inventory trend -> difference-in-differences).
Reports the lift at D+1/D+2/D+3/D+6 and the instantaneous jump from hour 23 of D-1 to
hour 0 of D. Also splits relevant events by the shop's per-product consumption rate
(12/day for the two single-product shops YARN_STORE/PET_CAFE vs 6/day for the
multi-product shops) for WOOL and CARROT.

Q3 (pre-opening stock and day-mod-3 periodicity): her sellable stock (shed+carried)
at hour 23 of each day, compared locally as stock[D-1] - mean(stock[D-2], stock[D])
per opening event (a local trend control), per product and era, plus for shed_total.
Separately, her and the opponent's total daily sold units (all products) are
detrended by the era's per-calendar-day mean across games and averaged by
day-mod-3, to check for a period-3 pattern in sales volume unconditional on which
product a given opening will favour.

All group statistics are bootstrap means with a 95% percentile interval (resampled
over events, or over games for the day-mod-3 check). Standard library only.

Writes results/fresh/mg_watch/shop_open_study.json.
"""
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'results/fresh/mg_watch/hourly.json'
OUT_PATH = ROOT / 'results/fresh/mg_watch/shop_open_study.json'

PRODUCTS = ['WOOL', 'MILK', 'EGG', 'STRAWBERRY', 'TOMATO', 'CARROT', 'WHEAT', 'MELON', 'FERTILIZER']
PIDX = {name: i for i, name in enumerate(PRODUCTS)}
N_DAYS = 30

BUYS = {
    'BAKERY': ['EGG', 'WHEAT'],
    'PIZZA_SHOP': ['MILK', 'TOMATO', 'WHEAT'],
    'BRUNCH_SPOT': ['EGG', 'WHEAT', 'STRAWBERRY'],
    'YARN_STORE': ['WOOL'],
    'ICE_CREAM_SHOP': ['STRAWBERRY', 'MILK', 'WHEAT'],
    'PET_CAFE': ['CARROT'],
    'SMOOTHIE_SHOP': ['STRAWBERRY', 'MILK'],
    'FARMERS_MARKET': ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY'],
}
SINGLE_PRODUCT_SHOPS = {'YARN_STORE', 'PET_CAFE'}  # 12 units/day vs 6 units/day for multi-product shops

STUDY_PRODUCTS = ['WOOL', 'MILK', 'EGG', 'STRAWBERRY', 'TOMATO', 'CARROT', 'WHEAT']
OPEN_DAYS = [3 * (i + 1) for i in range(8)]  # [3,6,...,24]

N_BOOT = 3000
SEED = 20260919
ERAS = ('old', 'new', 'both')


def relevant(shop_type, product):
    return product in BUYS.get(shop_type, ())


def rate_for(shop_type, product):
    if not relevant(shop_type, product):
        return 0
    return 12 if shop_type in SINGLE_PRODUCT_SHOPS else 6


def bootstrap_ci(values, rng, n_boot=N_BOOT):
    values = [v for v in values if v is not None]
    n = len(values)
    if n == 0:
        return {'n': 0, 'mean': None, 'lo': None, 'hi': None}
    mean = sum(values) / n
    if n == 1:
        return {'n': 1, 'mean': mean, 'lo': mean, 'hi': mean}
    choices = rng.choices
    means = sorted(sum(choices(values, k=n)) / n for _ in range(n_boot))
    lo_i = int(0.025 * n_boot)
    hi_i = min(int(0.975 * n_boot), n_boot - 1)
    return {'n': n, 'mean': mean, 'lo': means[lo_i], 'hi': means[hi_i]}


def diff_bootstrap(a, b, rng, n_boot=N_BOOT):
    a = [v for v in a if v is not None]
    b = [v for v in b if v is not None]
    na, nb = len(a), len(b)
    if na == 0 or nb == 0:
        return {'n_a': na, 'n_b': nb, 'mean_diff': None, 'lo': None, 'hi': None}
    choices = rng.choices
    diffs = sorted(
        sum(choices(a, k=na)) / na - sum(choices(b, k=nb)) / nb
        for _ in range(n_boot)
    )
    lo_i = int(0.025 * n_boot)
    hi_i = min(int(0.975 * n_boot), n_boot - 1)
    return {'n_a': na, 'n_b': nb, 'mean_diff': sum(a) / na - sum(b) / nb,
            'lo': diffs[lo_i], 'hi': diffs[hi_i]}


def build_game_index(game):
    """Precompute per-product per-day arrays used by every question, for one game."""
    price, glut = game['price'], game['glut']
    shed, carried = game['shed'], game['carried']
    rshed, rcarried = game['rshed'], game['rcarried']
    shed_total, rshed_total = game['shed_total'], game['rshed_total']
    np_ = len(PRODUCTS)

    def sold_arrays(sells):
        units_day = [[0] * N_DAYS for _ in range(np_)]
        units_h01 = [[0] * N_DAYS for _ in range(np_)]
        for step, p, units, _price_before, _avg_price in sells:
            d, h = step // 24, step % 24
            units_day[p][d] += units
            if h < 2:
                units_h01[p][d] += units
        return units_day, units_h01

    sold_day, sold_h01 = sold_arrays(game['sells'])
    rsold_day, rsold_h01 = sold_arrays(game['rsells'])

    day_mean_price = [[0.0] * N_DAYS for _ in range(np_)]
    day_mean_glut = [[0.0] * N_DAYS for _ in range(np_)]
    hour0_price = [[0.0] * N_DAYS for _ in range(np_)]
    hour23_price = [[0.0] * N_DAYS for _ in range(np_)]
    stock_end = [[0.0] * N_DAYS for _ in range(np_)]
    for p in range(np_):
        pp, gg = price[p], glut[p]
        sp, cp = shed[p], carried[p]
        for d in range(N_DAYS):
            lo = d * 24
            day_mean_price[p][d] = sum(pp[lo:lo + 24]) / 24.0
            day_mean_glut[p][d] = sum(gg[lo:lo + 24]) / 24.0
            hour0_price[p][d] = pp[lo]
            hour23_price[p][d] = pp[lo + 23]
            stock_end[p][d] = sp[lo + 23] + cp[lo + 23]

    return {
        'sold_day': sold_day, 'sold_h01': sold_h01,
        'rsold_day': rsold_day, 'rsold_h01': rsold_h01,
        'day_mean_price': day_mean_price, 'day_mean_glut': day_mean_glut,
        'hour0_price': hour0_price, 'hour23_price': hour23_price,
        'stock_end': stock_end,
        'shedtotal_end': [shed_total[d * 24 + 23] for d in range(N_DAYS)],
    }


def build_events(games):
    events = []
    for gi, game in enumerate(games):
        for i, D in enumerate(OPEN_DAYS):
            events.append({'gi': gi, 'era': game['era'], 'D': D, 'shop_type': game['shops'][i]})
    return events


def q1_sales_around_openings(events, game_idxs, rng):
    reldays = list(range(-2, 4))  # D-2..D+3
    result = {}
    for product in STUDY_PRODUCTS:
        p = PIDX[product]
        result[product] = {}
        for era_key in ERAS:
            groups = defaultdict(lambda: defaultdict(list))
            n_rel = n_irr = 0
            for ev in events:
                if era_key != 'both' and ev['era'] != era_key:
                    continue
                idx = game_idxs[ev['gi']]
                D = ev['D']
                window = range(D - 3, D + 4)
                her_base = sum(idx['sold_day'][p][d] for d in window) / 7.0
                opp_base = sum(idx['rsold_day'][p][d] for d in window) / 7.0
                is_rel = relevant(ev['shop_type'], product)
                n_rel += is_rel
                n_irr += not is_rel
                tag = 'relevant' if is_rel else 'irrelevant'
                her_h01_expect = her_base * (2.0 / 24.0)
                opp_h01_expect = opp_base * (2.0 / 24.0)
                for rd in reldays:
                    d = D + rd
                    if her_base > 0:
                        groups['her_' + tag]['day_%+d' % rd].append(idx['sold_day'][p][d] / her_base)
                    if opp_base > 0:
                        groups['opp_' + tag]['day_%+d' % rd].append(idx['rsold_day'][p][d] / opp_base)
                    if her_h01_expect > 0:
                        groups['her_' + tag]['h01_%+d' % rd].append(idx['sold_h01'][p][d] / her_h01_expect)
                    if opp_h01_expect > 0:
                        groups['opp_' + tag]['h01_%+d' % rd].append(idx['rsold_h01'][p][d] / opp_h01_expect)
            era_out = {'n_relevant_events': n_rel, 'n_irrelevant_events': n_irr, 'series': {}}
            for gname, gdata in groups.items():
                era_out['series'][gname] = {k: bootstrap_ci(v, rng) for k, v in gdata.items()}
            # direct significance test on the opening day itself (her sells only)
            era_out['her_relevant_vs_irrelevant_day0'] = diff_bootstrap(
                groups['her_relevant']['day_+0'], groups['her_irrelevant']['day_+0'], rng)
            era_out['her_relevant_vs_irrelevant_h01_day0'] = diff_bootstrap(
                groups['her_relevant']['h01_+0'], groups['her_irrelevant']['h01_+0'], rng)
            result[product][era_key] = era_out
    return result


def q2_price_response(events, game_idxs, rng):
    horizons = list(range(-3, 7))  # D-3..D+6
    result = {}
    for product in STUDY_PRODUCTS:
        p = PIDX[product]
        result[product] = {}
        for era_key in ERAS:
            gp = defaultdict(lambda: defaultdict(list))   # price lift, by tag then horizon
            gg = defaultdict(lambda: defaultdict(list))   # glut lift
            jump = defaultdict(list)
            rate_lift = defaultdict(lambda: defaultdict(list))  # rate -> horizon -> lift (relevant only)
            n_rel = n_irr = 0
            for ev in events:
                if era_key != 'both' and ev['era'] != era_key:
                    continue
                idx = game_idxs[ev['gi']]
                D = ev['D']
                base_price = idx['day_mean_price'][p][D - 1]
                base_glut = idx['day_mean_glut'][p][D - 1]
                is_rel = relevant(ev['shop_type'], product)
                n_rel += is_rel
                n_irr += not is_rel
                tag = 'relevant' if is_rel else 'irrelevant'
                for rd in horizons:
                    d = D + rd
                    if 0 <= d < N_DAYS:
                        pl = idx['day_mean_price'][p][d] - base_price
                        gl = idx['day_mean_glut'][p][d] - base_glut
                        gp[tag][rd].append(pl)
                        gg[tag][rd].append(gl)
                        if is_rel:
                            rate_lift[rate_for(ev['shop_type'], product)][rd].append(pl)
                jump[tag].append(idx['hour0_price'][p][D] - idx['hour23_price'][p][D - 1])
            era_out = {'n_relevant_events': n_rel, 'n_irrelevant_events': n_irr,
                       'price_lift': {}, 'glut_lift': {}, 'diff_in_diff_price': {},
                       'diff_in_diff_glut': {}, 'by_rate_price_lift': {}}
            for rd in horizons:
                key = 'D%+d' % rd
                era_out['price_lift'][key] = {
                    'relevant': bootstrap_ci(gp['relevant'][rd], rng),
                    'irrelevant': bootstrap_ci(gp['irrelevant'][rd], rng),
                }
                era_out['glut_lift'][key] = {
                    'relevant': bootstrap_ci(gg['relevant'][rd], rng),
                    'irrelevant': bootstrap_ci(gg['irrelevant'][rd], rng),
                }
                era_out['diff_in_diff_price'][key] = diff_bootstrap(gp['relevant'][rd], gp['irrelevant'][rd], rng)
                era_out['diff_in_diff_glut'][key] = diff_bootstrap(gg['relevant'][rd], gg['irrelevant'][rd], rng)
            era_out['jump_at_open'] = {
                'relevant': bootstrap_ci(jump['relevant'], rng),
                'irrelevant': bootstrap_ci(jump['irrelevant'], rng),
                'diff': diff_bootstrap(jump['relevant'], jump['irrelevant'], rng),
            }
            for rate, hdata in rate_lift.items():
                era_out['by_rate_price_lift'][str(rate)] = {
                    'D+1': bootstrap_ci(hdata.get(1, []), rng),
                    'D+3': bootstrap_ci(hdata.get(3, []), rng),
                    'D+6': bootstrap_ci(hdata.get(6, []), rng),
                }
            result[product][era_key] = era_out
    return result


def q3_pre_opening_stock(events, game_idxs, rng):
    labels = ['WOOL', 'MILK', 'STRAWBERRY', 'EGG', 'WHEAT', 'TOTAL']
    result = {}
    for label in labels:
        result[label] = {}
        for era_key in ERAS:
            deltas = []
            for ev in events:
                if era_key != 'both' and ev['era'] != era_key:
                    continue
                idx = game_idxs[ev['gi']]
                D = ev['D']
                if label == 'TOTAL':
                    s2, s1, s0 = idx['shedtotal_end'][D - 2], idx['shedtotal_end'][D - 1], idx['shedtotal_end'][D]
                else:
                    p = PIDX[label]
                    se = idx['stock_end'][p]
                    s2, s1, s0 = se[D - 2], se[D - 1], se[D]
                deltas.append(s1 - (s2 + s0) / 2.0)
            result[label][era_key] = bootstrap_ci(deltas, rng)
    return result


def _moving_average(series, radius=4):
    """Centered moving average with a window (2*radius+1 = 9 days, a multiple of 3):
    long enough to cancel a period-3 oscillation almost completely (9 consecutive
    days span exactly 3 full 3-day cycles) while still tracking slower drift. This
    is what makes it safe to subtract as a trend without erasing the very
    day-mod-3 signal being tested (unlike an exact per-calendar-day mean, which is
    fully saturated and would zero out any such signal by construction)."""
    n = len(series)
    out = [0.0] * n
    for d in range(n):
        lo, hi = max(0, d - radius), min(n, d + radius + 1)
        window = series[lo:hi]
        out[d] = sum(window) / len(window)
    return out


def q3_day_mod3_periodicity(games, game_idxs, rng):
    result = {}
    for era_key in ERAS:
        gidxs = [gi for gi, g in enumerate(games) if era_key == 'both' or g['era'] == era_key]
        her_tot = {}  # (gi, d) -> total units
        opp_tot = {}
        her_day_totals = defaultdict(list)
        opp_day_totals = defaultdict(list)
        for gi in gidxs:
            idx = game_idxs[gi]
            for d in range(N_DAYS):
                h = sum(idx['sold_day'][p][d] for p in range(len(PRODUCTS)))
                o = sum(idx['rsold_day'][p][d] for p in range(len(PRODUCTS)))
                her_tot[(gi, d)] = h
                opp_tot[(gi, d)] = o
                her_day_totals[d].append(h)
                opp_day_totals[d].append(o)
        her_avg_by_day = [sum(her_day_totals[d]) / len(her_day_totals[d]) for d in range(N_DAYS)]
        opp_avg_by_day = [sum(opp_day_totals[d]) / len(opp_day_totals[d]) for d in range(N_DAYS)]
        her_smooth = _moving_average(her_avg_by_day)
        opp_smooth = _moving_average(opp_avg_by_day)
        her_by_mod = defaultdict(list)
        opp_by_mod = defaultdict(list)
        for gi in gidxs:
            for d in range(N_DAYS):
                her_by_mod[d % 3].append(her_tot[(gi, d)] - her_smooth[d])
                opp_by_mod[d % 3].append(opp_tot[(gi, d)] - opp_smooth[d])
        result[era_key] = {
            'day_mod3_meaning': {
                '0': 'opening day itself (3,6,...,24) plus days 0,27',
                '1': 'day after an opening (4,7,...,25) plus days 1,28',
                '2': 'day before an opening (2,5,...,23) plus days 26,29',
            },
            'her_residual_by_day_mod3': {str(m): bootstrap_ci(her_by_mod[m], rng) for m in (0, 1, 2)},
            'opp_residual_by_day_mod3': {str(m): bootstrap_ci(opp_by_mod[m], rng) for m in (0, 1, 2)},
        }
    return result


def main():
    with open(DATA_PATH, encoding='utf-8') as f:
        data = json.load(f)
    games = data['games']
    assert data['products'] == PRODUCTS, 'product order mismatch with docstring assumptions'
    print('games:', len(games), 'old:', sum(g['era'] == 'old' for g in games),
          'new:', sum(g['era'] == 'new' for g in games))

    game_idxs = [build_game_index(g) for g in games]
    events = build_events(games)
    print('opening events:', len(events))

    rng = random.Random(SEED)
    out = {
        'meta': {
            'n_games': len(games), 'n_old': sum(g['era'] == 'old' for g in games),
            'n_new': sum(g['era'] == 'new' for g in games), 'n_events': len(events),
            'open_days': OPEN_DAYS, 'buys': BUYS, 'n_boot': N_BOOT, 'seed': SEED,
        },
        'q1_sales_around_openings': q1_sales_around_openings(events, game_idxs, rng),
        'q2_price_response': q2_price_response(events, game_idxs, rng),
        'q3_pre_opening_stock': q3_pre_opening_stock(events, game_idxs, rng),
        'q3_day_mod3_periodicity': q3_day_mod3_periodicity(games, game_idxs, rng),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
    print('wrote', OUT_PATH)


if __name__ == '__main__':
    main()
