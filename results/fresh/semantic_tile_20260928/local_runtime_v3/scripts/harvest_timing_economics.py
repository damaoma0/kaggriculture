"""Harvest timing, deliverable 1: ECONOMICS of harvesting a plant earlier vs later, per crop x period, from
results/fresh/harvest_timing_20260925/leaders/ (written by harvest_timing_extract.py, 540 leader games). Stored
data only; no games, no engine runs. This is about the HARVEST decision (when to press HARVEST on a tile), distinct
from deliverable 2 (harvest_timing_market.py: once harvested, sell now vs next morning).

Four ingredients, all keyed by crop x HARVEST period (0-5, 6-11, 12-17, 18-23, 24-29):
  1. units gained/lost from the engine's growth rules.
     - loss1 = units actually lost had this exact harvest happened 1 day earlier: observed directly from the
       corpus-derived per-plant `yend` (held/yield units at the end of each day; extracted for every plant, every
       crop, unconditionally) as units_at_harvest - yend[day-1]. Real data, not a model.
     - gain1 = units gained had the leader waited 1 more day before this harvest.
         one-time crops (wheat/carrot/melon): the plant is REMOVED from the corpus's per-day tracking at harvest
         (the tile is empty from then on), so "if not harvested" on day+1 is not observed and must be modeled from
         the engine's own growth-window rule (harvest_timing_report.one_more_day_gain: +1/+2 if day+1 is still
         inside the window, else the decay rule -1 unit/2 hours).
         ongoing crops (tomato/strawberry): harvesting does NOT remove the plant (it keeps producing up to the
         held cap of 4), so yend[day+1] is real observed data too: gain1 = yend[day+1] - units_at_harvest.
  2. price: the leaders' own realised sold_revenue / sold_units per crop per day (days.jsonl.gz, corpus ground
     truth), pooled across all 540 games for volume, giving a period price-per-unit and a within-period coins/day
     trend (weighted least squares of price on day, weight = that day's pooled units sold -- "realised daily
     trend", as opposed to a modeled inventory curve).
  3. tile-turnover value: one-time crops only (harvesting empties the tile; an ongoing crop keeps the tile
     regardless of when you harvest it). Per plant: total harvested revenue (each harvest's units at that day's
     price) / tile-days occupied (harvest day - planted day, so a same-day replant is tile-days>=1). Pooled
     coins/tile-day by PLANTING period, applied to the same-numbered HARVEST period (leaders replant the same day
     in the large majority of cases per harvest_timing_report.sec_ages, so this is a same-bucket proxy, not a
     lagged one; the replant-same-day rate is reported alongside so the assumption's coverage is visible).
  4. decay risk: already folded into gain1's sign for one-time crops (waiting past the window IS decay). Reported
     separately too: the fraction of harvests already past the safe window (age > max_yield_day) and their
     observed decay_loss in coins, i.e. money already lost to the leaders who waited too long, at the point they
     finally harvested. For ongoing crops the timing risk is cap waste (units cut by the 4-held cap), from
     harvest_timing_report.sec_ongo's wasted_since, priced the same way.

Bottom line per crop x period (coins per harvest event):
  1 day EARLIER = -loss1*price - trend/day + tile_rate/day   (tile_rate/day = 0 for ongoing crops)
  1 day LATER   = +gain1*price + trend/day - tile_rate/day
(trend/day > 0 means price is rising over the period: harvesting/selling a day earlier forfeits that rise, a day
later captures it. tile_rate/day > 0 means freeing the tile a day earlier is worth that much if replanted, so it
ADDS to the earlier case and SUBTRACTS from the later case.) These two are not mirror images of each other: loss1
and gain1 come from different observed/modeled bases (see above), and trend/tile terms are added with the sign
appropriate to each direction.

"A few hours earlier/later" is not a smooth per-hour rate for units (watering is a once-a-day event; decay ticks
every 2 hours) so it is reported separately, per crop, as: (a) the coin value of missing today's watering bonus
by harvesting before the day's WATER action, (b) the per-2-hour decay tick cost once past the window, (c) a
pointer to harvest_timing_market.py's hour-of-day price tables for the continuous intraday price effect.

usage: .venv/Scripts/python.exe scripts/harvest_timing_economics.py
Writes results/fresh/harvest_timing_20260925/economics/{report.md,tables.json}.
"""
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from harvest_timing_extract import CROP, OUT  # noqa: E402
from harvest_timing_report import iter_games, period, PERIODS, PNAME, q, one_more_day_gain  # noqa: E402

ECOUT = OUT / 'economics'
CROPS = ('WHEAT', 'CARROT', 'MELON', 'TOMATO', 'STRAWBERRY')
ONE_TIME = ('WHEAT', 'CARROT', 'MELON')
ONGOING = ('TOMATO', 'STRAWBERRY')


def wls_slope(pts):
    """weighted least-squares slope of y on x; pts = [(x, y, w), ...]. None if <2 distinct x or singular."""
    pts = [(x, y, w) for x, y, w in pts if w > 0]
    if len({x for x, _, _ in pts}) < 2:
        return None
    sw = sum(w for _, _, w in pts)
    swx = sum(w * x for x, _, w in pts)
    swy = sum(w * y for _, y, w in pts)
    swxx = sum(w * x * x for x, _, w in pts)
    swxy = sum(w * x * y for x, y, w in pts)
    denom = sw * swxx - swx * swx
    if abs(denom) < 1e-6:
        return None
    return (sw * swxy - swx * swy) / denom


def main():
    ECOUT.mkdir(parents=True, exist_ok=True)
    # ---- pass 1: pooled realised price per crop per day (leaders' own sold_revenue / sold_units), plus raw rows
    day_rev = {c: Counter() for c in CROPS}
    day_units = {c: Counter() for c in CROPS}
    H = []   # harvest rows: crop, per(harvest day), d, age, units, loss1, gain1, hour, fert, wt_before
    T = defaultdict(list)  # crop -> [(planted_period, tile_days, [(day, units), ...])] one-time crops only
    n_games = 0
    for ep, team, plants, hv, days in iter_games('leaders'):
        n_games += 1
        pl = {p['id']: p for p in plants}
        for D, dd in enumerate(days):
            for c in CROPS:
                u = (dd.get('sold_units') or {}).get(c, 0)
                if u:
                    day_units[c][D] += u
                    day_rev[c][D] += (dd.get('sold_revenue') or {}).get(c, 0)
        for r in hv:
            crop = r['crop']
            c = CROP[crop]
            p = pl[r['plant']]
            loss1 = None
            if r['d'] > 0 and str(r['d'] - 1) in p['yend']:
                loss1 = r['units'] - p['yend'][str(r['d'] - 1)]
            if crop in ONE_TIME:
                gain1 = one_more_day_gain(c, r)
            else:
                gain1 = None
                if str(r['d'] + 1) in p['yend']:
                    gain1 = p['yend'][str(r['d'] + 1)] - r['units']
            fert = any(fd <= r['d'] for fd, fh in p['ferts'])
            # "past window" = further waiting is now in decay territory: age > M for one-time crops (a fixed growth
            # window); for ongoing crops decay only starts the day after the 4th production, unrelated to age, so
            # use prod_no (productions banked before this harvest; this harvest may itself be the 4th).
            if crop in ONE_TIME:
                past_window = r['age'] > c['M']
            else:
                past_window = r.get('prod_no', 0) + 1 >= 4
            H.append(dict(crop=crop, per=period(r['d']), d=r['d'], age=r['age'], units=r['units'],
                          loss1=loss1, gain1=gain1, hour=r['h'], fert=fert, wt_before=r['wt_before'],
                          decay_loss=r['decay_loss'], past_window=past_window))
        for p in plants:
            if p['crop'] not in ONE_TIME or not p['harv']:
                continue
            last_d = max(d for d, h, u in p['harv'])
            tile_days = max(1, last_d - p['pd'])
            T[p['crop']].append((period(p['pd']), tile_days, [(d, u) for d, h, u in p['harv']]))

    # ---- price lookups: per-day, per-period (pooled ratio), per-crop overall (pooled ratio) ----
    price_day, price_period, price_crop = {}, {}, {}
    for c in CROPS:
        price_day[c] = {D: day_rev[c][D] / day_units[c][D] for D in day_units[c] if day_units[c][D] > 0}
        price_period[c] = {}
        for pi, (lo, hi) in enumerate(PERIODS):
            u = sum(day_units[c][D] for D in range(lo, hi + 1))
            price_period[c][pi] = (sum(day_rev[c][D] for D in range(lo, hi + 1)) / u) if u > 0 else None
        tot_u = sum(day_units[c].values())
        price_crop[c] = (sum(day_rev[c].values()) / tot_u) if tot_u > 0 else None

    def price_at(c, d, pi):
        if d in price_day[c]:
            return price_day[c][d]
        if price_period[c].get(pi) is not None:
            return price_period[c][pi]
        return price_crop[c]

    # price trend (coins/day) within each period, weighted by that day's pooled units
    trend = {c: {} for c in CROPS}
    for c in CROPS:
        for pi, (lo, hi) in enumerate(PERIODS):
            pts = [(D, price_day[c][D], day_units[c][D]) for D in range(lo, hi + 1) if D in price_day[c]]
            trend[c][pi] = wls_slope(pts)

    # tile coins/day by crop x PLANTING period (one-time crops only)
    tile_rate = {c: {} for c in ONE_TIME}
    tile_replant_n = {c: {} for c in ONE_TIME}
    for c in ONE_TIME:
        by_pi = defaultdict(lambda: [0.0, 0])
        for pi, tdays, harv_list in T[c]:
            rev = sum(u * price_at(c, d, period(d)) for d, u in harv_list)
            by_pi[pi][0] += rev
            by_pi[pi][1] += tdays
        for pi, (rev, tdays) in by_pi.items():
            tile_rate[c][pi] = rev / tdays if tdays > 0 else None
        tile_replant_n[c] = Counter(pi for pi, _, _ in T[c])

    # ---- aggregate harvest rows by crop x period ----
    A = defaultdict(lambda: defaultdict(list))
    for r in H:
        A[(r['crop'], r['per'])]['loss1'].append(r['loss1'] if r['loss1'] is not None else float('nan'))
        A[(r['crop'], r['per'])]['gain1'].append(r['gain1'] if r['gain1'] is not None else float('nan'))
        A[(r['crop'], r['per'])]['age'].append(r['age'])
        A[(r['crop'], r['per'])]['units'].append(r['units'])
        A[(r['crop'], r['per'])]['past_window'].append(int(r['past_window']))
        A[(r['crop'], r['per'])]['decay_loss'].append(r['decay_loss'])
        A[(r['crop'], r['per'])]['wt_before'].append(int(r['wt_before']))
        A[(r['crop'], r['per'])]['fert'].append(int(r['fert']))
        A[(r['crop'], r['per'])]['n'].append(1)

    def mean(xs):
        xs = [x for x in xs if x == x]  # drop NaN
        return sum(xs) / len(xs) if xs else None

    def fmt(v, nd=1):
        return '-' if v is None else f'{v:+.{nd}f}'

    out_lines = []
    tables = {'games': n_games, 'price_period': price_period, 'price_crop': price_crop, 'trend': trend,
              'tile_rate': tile_rate, 'rows': {}}

    def p(s=''):
        print(s)
        out_lines.append(s)

    p(f'# Harvest-timing economics ({n_games} leader games, {len(H)} harvest events)\n')
    p('Coins per harvest event for shifting the HARVEST 1 day earlier / later. earlier = -loss1*price - trend '
      '+ tile_rate; later = +gain1*price + trend - tile_rate (trend, tile_rate in coins/day; tile_rate = 0 for '
      'ongoing crops, which keep the tile regardless of harvest timing). loss1/decay from the corpus; gain1 '
      'modeled (one-time crops) or observed (ongoing crops, see module docstring).\n')
    p('Reading notes:')
    p('- For crops harvested right at the earliest legal age (melon age 10 = first_yield_day; strawberry/tomato\'s '
      'first production), the "1 day earlier" column is a counterfactual (HARVEST is illegal one day sooner) -- it '
      'measures the value of that last pre-harvest watering, not an available action. The "1 day later" column is '
      'the real, available lever for those crops.')
    p('- A negative "units gained by 1d later" is the growth-window rule turning into the decay rule: once the '
      'observed harvest is already at the window\'s last day (wheat age 4, carrot age 3), the model\'s next day is '
      'past the window, so decay ticks (-1 unit/2h) apply instead of a growth bonus -- this is why late-game wheat '
      '/ carrot show large negative "1 day later" values even at "0% past window" (they are AT the edge, not past '
      'it; one_more_day_gain is forward-looking).')
    p('- tile $/day is pooled revenue / pooled tile-days for one-time-crop plantings that were harvested at least '
      'once, bucketed by PLANTING period, applied to the same-numbered HARVEST period (leaders replant the same '
      'tile the same day 39-96% of the time depending on crop/period -- see harvest_timing_report.py\'s '
      '"replanted same day" column; this is a same-bucket proxy, not a lagged one).\n')
    for crop in CROPS:
        c = CROP[crop]
        window_desc = f'window end {c["M"]}' if crop in ONE_TIME else 'decay starts the day after the 4th production'
        p(f'\n## {crop} (harvest-allowed age {c["F"]}, {window_desc}, held cap {c["cap"]}'
          f'{", one-time (frees the tile)" if crop in ONE_TIME else ", ongoing (tile stays occupied)"})')
        p('| period | n | mean age | price/unit | trend $/day | tile $/day | units lost, 1d earlier | units '
          f'gained, 1d later | {"past window" if crop in ONE_TIME else "4th+ prod. banked"} | decay units so far '
          '| **1 day earlier** | **1 day later** |')
        p('|---|---|---|---|---|---|---|---|---|---|---|---|')
        any_fallback = False
        for pi in range(5):
            a = A.get((crop, pi))
            if not a:
                continue
            n = len(a['n'])
            price_u = price_period[crop].get(pi)
            price_fallback = price_u is None
            any_fallback = any_fallback or price_fallback
            if price_u is None:
                price_u = price_crop[crop]
            tr = trend[crop][pi]
            tl = tile_rate.get(crop, {}).get(pi) if crop in ONE_TIME else None
            l1, g1 = mean(a['loss1']), mean(a['gain1'])
            earlier = later = None
            if price_u is not None and l1 is not None:
                earlier = -l1 * price_u - (tr or 0) + (tl or 0)
            if price_u is not None and g1 is not None:
                later = g1 * price_u + (tr or 0) - (tl or 0)
            row = [PNAME[pi], str(n), f"{mean(a['age']):.2f}",
                   ('-' if price_u is None else f'{price_u:.1f}' + ('*' if price_fallback else '')),
                   ('-' if tr is None else f'{tr:+.2f}'), ('-' if tl is None else f'{tl:+.1f}'),
                   f'{l1:.2f}' if l1 is not None else '-', f'{g1:+.2f}' if g1 is not None else '-',
                   f"{100 * mean(a['past_window']):.0f}%", f"{mean(a['decay_loss']):.2f}",
                   fmt(earlier), fmt(later)]
            p('| ' + ' | '.join(row) + ' |')
            tables['rows'][f'{crop}|{pi}'] = {
                'n': n, 'mean_age': mean(a['age']), 'price_unit': price_u, 'price_is_crop_fallback': price_fallback,
                'trend_per_day': tr,
                'tile_rate_per_day': tl, 'loss1_units': l1, 'gain1_units': g1,
                'past_window_share': mean(a['past_window']), 'decay_units_so_far': mean(a['decay_loss']),
                'coins_1day_earlier': earlier, 'coins_1day_later': later}
        if crop in ONE_TIME:
            rep = ', '.join(f'{PNAME[pi]} n={tile_replant_n[crop].get(pi, 0)}' for pi in range(5)
                             if tile_replant_n[crop].get(pi, 0))
            p(f'  tile $/day sample (plantings with >=1 harvest, by PLANTING period): {rep}')
        if any_fallback:
            p("  * = no sales of this crop recorded in this period's days (pooled); price/unit falls back to the "
              "crop's whole-corpus average, and the period's own trend ('-') is genuinely unavailable.")

    # ---- "a few hours" section ----
    p('\n## A few hours earlier / later (not a smooth per-hour rate; reported as discrete effects)\n')
    p('One-time crops (wheat/carrot/melon) have a real within-day lever: harvesting before vs after the day\'s '
      'WATER changes the units in THIS harvest (the growth-window bonus is credited the moment you water). Ongoing '
      'crops (tomato/strawberry) do not: their daily +1/+2 is decided by yesterday\'s watering and paid out at the '
      'automatic end-of-day refresh regardless of when during the day you press HARVEST, so the harvest hour only '
      'affects which SALE price you catch (see the intraday price pointer below), never the unit count.\n')
    p('| crop | harvesting before today\'s WATER costs (coins, when in growth window & unwatered) | share of '
      'harvests unwatered-before, in window | decay tick (coins / 2h, once decay has started) |')
    p('|---|---|---|---|')
    for crop in CROPS:
        c = CROP[crop]
        price_u = price_crop[crop]
        dtick = price_u  # 1 unit / 2h once decay has started = price_u coins/2h, same rule for both crop types
        if crop in ONE_TIME:
            inwin = [r for r in H if r['crop'] == crop and (c['M'] + 1) // 2 <= r['age'] <= c['M']]
            share_unwatered = mean([int(not r['wt_before']) for r in inwin]) if inwin else None
            fert_share = mean([int(r['fert']) for r in inwin]) if inwin else 0.0
            bonus = 1 + (fert_share or 0)   # +2 if fertilized else +1, blended by observed fertilizer share
            wcost = bonus * price_u if price_u is not None else None
            share_str = '-' if share_unwatered is None else f'{100 * share_unwatered:.0f}%'
        else:
            wcost, share_str = 'n/a (production fixed by yesterday\'s watering)', 'n/a'
        p(f'| {crop} | {fmt(wcost) if isinstance(wcost, (int, float)) or wcost is None else wcost} | {share_str} | '
          f'{fmt(dtick)} |')
    p('\ndecay tick eligibility: one-time crops once age > the window end (wheat 4, carrot 3, melon 12); ongoing '
      'crops once 4 productions have banked (decay starts the day after the 4th, independent of age).')
    p('\nIntraday price trend (continuous, by hour of the ready hour): see harvest_timing_market.py\'s '
      '"By hour bin" tables (results/fresh/harvest_timing_20260925/market/credit_report.md) -- built from the '
      'same replays, already broken out by hour bin per product.')

    Path(ECOUT / 'report.md').write_text('\n'.join(out_lines) + '\n', encoding='utf-8')
    json.dump(tables, open(ECOUT / 'tables.json', 'w'), indent=1)
    p(f'\n[{n_games} games; wrote {ECOUT / "report.md"}]')


if __name__ == '__main__':
    main()
