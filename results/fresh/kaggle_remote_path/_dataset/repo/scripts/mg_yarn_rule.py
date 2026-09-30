"""ANALYSIS ONLY. How does Mother-Goose (old policy, teams 56266758/56266899 tape libraries)
respond to Yarn Store reveals with sheep purchases?

Reads the 584 compact tapes in data/mg_tapes/{56266758,56266899}/*.json.gz (gzip JSON; fields:
episode, seat, seed, rewards, opponent, shops[31], boards[30], cash[30], actions[719] -- all
already for HER seat, see fetch_mg_tapes.py:compact()). No simulation, no writes except the
single output JSON below.

Output: results/fresh/mg_tape/yarn_rule.json
"""
import gzip
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent.parent
TAPE_DIRS = [ROOT / 'data/mg_tapes/56266758', ROOT / 'data/mg_tapes/56266899']
OUT = ROOT / 'results/fresh/mg_tape/yarn_rule.json'

DAY_BUCKETS = [(0, 5), (6, 8), (9, 11), (12, 14), (15, 17), (18, 20), (21, 29)]


def bucket_of(day):
    for lo, hi in DAY_BUCKETS:
        if lo <= day <= hi:
            return f'{lo}-{hi}'
    return '21+'


def load_games():
    games = []
    for d in TAPE_DIRS:
        for fp in sorted(d.glob('*.json.gz')):
            with gzip.open(fp, 'rt', encoding='utf-8') as f:
                games.append(json.load(f))
    return games


def yarn_slots(game):
    """0-based shop-slot indices (0..7) where the fully-revealed shop list has YARN_STORE.
    Slot i is revealed on day 3*(i+1)."""
    full = game['shops'][30]
    return [i for i, n in enumerate(full) if n == 'YARN_STORE']


def yarn_days(game):
    return tuple(sorted(3 * (i + 1) for i in yarn_slots(game)))


def market_events(game, op, item=None):
    """[(day, hour, qty), ...] for market orders matching op (and item if given)."""
    out = []
    for t, a in enumerate(game['actions']):
        for m in (a.get('market') or []):
            if not (isinstance(m, list) and m):
                continue
            if m[0] != op:
                continue
            if item is not None and not (len(m) > 1 and m[1] == item):
                continue
            qty = int(m[2]) if len(m) > 2 else 1
            out.append((t // 24, t % 24, qty))
    return out


def unit_events(game, op, item=None):
    """[(day, hour, unit, arg), ...] for farmer/hand unit orders matching op (and first arg)."""
    out = []
    for t, a in enumerate(game['actions']):
        units = [('farmer', a.get('farmer'))] + [(f'hand{i+1}', h) for i, h in enumerate(a.get('hands') or [])]
        for who, unit in units:
            if not (isinstance(unit, list) and unit) or unit[0] != op:
                continue
            if item is not None and not (len(unit) > 1 and unit[1] == item):
                continue
            out.append((t // 24, t % 24, who, unit[1] if len(unit) > 1 else None))
    return out


def sheep_bought_total(game):
    return sum(q for _, _, q in market_events(game, 'BUY_ANIMAL', 'SHEEP'))


def tile_at(row_string, col):
    return row_string[col * 2:col * 2 + 2].strip()


def board_tile(board_day, row, col):
    return tile_at(board_day[row], col)


def count_label(board_day, label):
    return sum(1 for row_string in board_day for col in range(10) if tile_at(row_string, col) == label)


def quadrant(row, col):
    ns = 'N' if row < 5 else 'S'
    ew = 'W' if col < 5 else 'E'
    return ns + ew


# ---------------------------------------------------------------------------
# Q1: sheep purchases / board sheep / final cash, grouped by yarn reveal-day tuple
# ---------------------------------------------------------------------------

def q1_groups(games):
    tuples = Counter(yarn_days(g) for g in games)
    # Keep tuples with n>=8 as their own group; pool the rest by size (len of tuple).
    keep = {t for t, n in tuples.items() if n >= 8}

    def group_key(g):
        yd = yarn_days(g)
        if yd in keep:
            return yd
        return ('other', len(yd))

    groups = {}
    for g in games:
        groups.setdefault(group_key(g), []).append(g)

    def label(key):
        if key == ():
            return 'none'
        if isinstance(key, tuple) and key and key[0] == 'other':
            n = key[1]
            return f'{n} yarn stores, other combos' if n else 'none'
        return 'yarn days ' + '+'.join(str(d) for d in key)

    def sort_key(kv):
        key = kv[0]
        is_other = bool(key) and isinstance(key, tuple) and key[0] == 'other'
        return (is_other, str(key))

    out = []
    for key, grp in sorted(groups.items(), key=sort_key):
        n = len(grp)
        by_bucket = {}
        for lo, hi in DAY_BUCKETS:
            bname = f'{lo}-{hi}' if hi != 29 else '21+'
            vals = []
            for g in grp:
                vals.append(sum(q for d, h, q in market_events(g, 'BUY_ANIMAL', 'SHEEP') if lo <= d <= hi))
            by_bucket[bname] = round(mean(vals), 2)
        total = round(mean(sheep_bought_total(g) for g in grp), 2)
        sh_at = {}
        for day in (12, 18, 24):
            sh_at[str(day)] = round(mean(count_label(g['boards'][day], 'sh') for g in grp), 2)
        cash = round(mean(g['rewards'][g['seat']] for g in grp), 0)
        out.append(dict(group=label(key), yarn_days=key if not (isinstance(key, tuple) and key and key[0] == 'other')
                         else None, n=n, mean_total_sheep=total, sheep_by_day_bucket=by_bucket,
                         sheep_on_board=sh_at, mean_final_cash=cash))
    return out


# ---------------------------------------------------------------------------
# Q2: the trigger rule
# ---------------------------------------------------------------------------

SINGLE_DAYS = [3, 6, 9, 12, 15, 18, 21, 24]


def q2_profiles(games):
    zero = [g for g in games if yarn_days(g) == ()]
    baseline_mean = mean(sheep_bought_total(g) for g in zero)
    baseline_by_dayhour = Counter()
    for g in zero:
        for d, h, q in market_events(g, 'BUY_ANIMAL', 'SHEEP'):
            baseline_by_dayhour[(d, h)] += q
    baseline_by_dayhour = {f'day{d}_hr{h}': round(q / len(zero), 3) for (d, h), q in baseline_by_dayhour.items()}

    profiles = {}
    extra_by_D = {}
    for D in SINGLE_DAYS:
        grp = [g for g in games if yarn_days(g) == (D,)]
        if not grp:
            continue
        qty = Counter()
        presence = Counter()
        for g in grp:
            keys = set()
            for d, h, q in market_events(g, 'BUY_ANIMAL', 'SHEEP'):
                qty[(d, h)] += q
                keys.add((d, h))
            for k in keys:
                presence[k] += 1
        rows = []
        for (d, h) in sorted(set(qty) | set(presence)):
            rows.append(dict(day=d, hour=h, day_offset_from_D=d - D, mean_qty=round(qty[(d, h)] / len(grp), 3),
                              presence=f'{presence[(d, h)]}/{len(grp)}'))
        total = mean(sheep_bought_total(g) for g in grp)
        cash_at_D = mean(g['cash'][D] for g in grp)
        profiles[str(D)] = dict(n=len(grp), mean_total_sheep=round(total, 2), mean_cash_at_reveal=round(cash_at_D, 0),
                                 extra_vs_baseline=round(total - baseline_mean, 2), events=rows)
        extra_by_D[D] = round(total - baseline_mean)
        if extra_by_D[D] < 0:
            extra_by_D[D] = 0

    # Additivity check: for a few multi-yarn tuples with n>=6, compare actual mean total sheep to the
    # sum of each component D's singleton mean_total (baseline counted once).
    additivity = []
    for tup, n in Counter(yarn_days(g) for g in games).items():
        if len(tup) < 2 or n < 6:
            continue
        if not all(d in extra_by_D for d in tup):
            continue
        grp = [g for g in games if yarn_days(g) == tup]
        actual = mean(sheep_bought_total(g) for g in grp)
        predicted_additive = baseline_mean + sum(extra_by_D[d] for d in tup)
        additivity.append(dict(yarn_days=tup, n=n, actual_mean_total=round(actual, 2),
                                predicted_additive_total=round(predicted_additive, 2)))

    # Fit + accuracy: predicted_total(game) = baseline (rounded) + sum(extra_by_D[d] for d in yarn_days(game))
    baseline_round = round(baseline_mean)
    hits = 0
    for g in games:
        pred = baseline_round + sum(extra_by_D.get(d, 0) for d in yarn_days(g))
        actual = sheep_bought_total(g)
        if abs(pred - actual) <= 1:
            hits += 1
    accuracy = hits / len(games)

    return dict(baseline_mean_total_sheep_no_yarn=round(baseline_mean, 2),
                baseline_purchase_pattern=baseline_by_dayhour,
                per_reveal_day_profile=profiles,
                extra_sheep_lookup_by_reveal_day=extra_by_D,
                additivity_check_multi_yarn_games=sorted(additivity, key=lambda r: r['yarn_days']),
                rule_baseline_plus_lookup_accuracy_within_1=round(accuracy, 3),
                rule_description=(
                    'predicted_total_season_sheep(game) = 4 + sum(extra_sheep_lookup_by_reveal_day[D] '
                    'for each Yarn Store reveal day D in the game), applied independently/additively per '
                    'reveal regardless of how many Yarn Stores are already visible or her cash on hand.'))


# ---------------------------------------------------------------------------
# Q3: where the post-day-8 sheep go
# ---------------------------------------------------------------------------

def q3_placement(games):
    before_labels = Counter()
    quadrants = Counter()
    land_nearby = Counter()
    examples_by_before = Counter()
    n_new_pastures = 0
    n_games_with_new = 0
    for g in games:
        land_days = [d for d, h, q in market_events(g, 'BUY_LAND')]
        found_any = False
        for d in range(8, 29):
            before_row_set = g['boards'][d]
            after_row_set = g['boards'][d + 1]
            for row in range(10):
                for col in range(10):
                    before = board_tile(before_row_set, row, col)
                    after = board_tile(after_row_set, row, col)
                    if after == 'sh' and before != 'sh':
                        n_new_pastures += 1
                        found_any = True
                        before_labels[before] += 1
                        quadrants[quadrant(row, col)] += 1
                        near = any(abs(ld - (d + 1)) <= 3 for ld in land_days)
                        land_nearby['near_buy_land' if near else 'no_buy_land_nearby'] += 1
        if found_any:
            n_games_with_new += 1
    return dict(n_new_sheep_tiles_after_day8=n_new_pastures, n_games_with_new_sheep_tile_after_day8=n_games_with_new,
                before_label_counts=dict(before_labels.most_common()),
                quadrant_counts=dict(quadrants.most_common()),
                buy_land_within_3_days=dict(land_nearby),
                note=("before label 'co' is ambiguous: an empty COOP and a cow-occupied PASTURE are both "
                      "labelled 'co' (tile_label truncates kind/animal to 2 lowercase chars); 'pa' is an "
                      "empty (animal-less) pasture already built. An OCCUPIED pasture cannot be DIGged "
                      "(engine no-ops DIG on occupied coop/pasture), so a true cow/goose -> sheep species "
                      "swap on an existing occupied structure is not mechanically possible; 'co'/'go' before "
                      "labels here most likely reflect an empty coop or an unrelated cow tile adjacent, not "
                      "a swap."))


# ---------------------------------------------------------------------------
# Q4: what she gives up (hires, wheat) after a late yarn response
# ---------------------------------------------------------------------------

def q4_tradeoffs(games):
    zero = [g for g in games if yarn_days(g) == ()]

    def per_day_rate(grp, op, item, day_lo, day_hi):
        vals = []
        for g in grp:
            evs = market_events(g, op, item)
            total = sum(q for d, h, q in evs if day_lo <= d <= day_hi)
            vals.append(total / (day_hi - day_lo + 1))
        return round(mean(vals), 3)

    def wheat_plantings_rate(grp, day_lo, day_hi):
        vals = []
        for g in grp:
            evs = unit_events(g, 'PLANT', 'WHEAT')
            total = sum(1 for d, h, who, arg in evs if day_lo <= d <= day_hi)
            vals.append(total / (day_hi - day_lo + 1))
        return round(mean(vals), 3)

    windows = []
    for D in (12, 15, 18):
        grp = [g for g in games if yarn_days(g) == (D,)]
        if not grp:
            continue
        lo, hi = D, D + 3
        windows.append(dict(
            reveal_day=D, n=len(grp),
            hires_per_day=per_day_rate(grp, 'HIRE', None, lo, hi),
            hires_per_day_baseline=per_day_rate(zero, 'HIRE', None, lo, hi),
            wheat_bought_per_day=per_day_rate(grp, 'BUY_PRODUCT', 'WHEAT', lo, hi),
            wheat_bought_per_day_baseline=per_day_rate(zero, 'BUY_PRODUCT', 'WHEAT', lo, hi),
            wheat_plantings_per_day=wheat_plantings_rate(grp, lo, hi),
            wheat_plantings_per_day_baseline=wheat_plantings_rate(zero, lo, hi),
        ))
    return windows


# ---------------------------------------------------------------------------
# Q5: wool selling
# ---------------------------------------------------------------------------

def q5_wool(games):
    with_yarn = [g for g in games if yarn_days(g) != ()]
    zero = [g for g in games if yarn_days(g) == ()]
    sell_by_dayhour = Counter()
    n_with_sells = 0
    qty_hist = Counter()
    for g in with_yarn:
        evs = market_events(g, 'SELL', 'WOOL')
        if evs:
            n_with_sells += 1
        for d, h, q in evs:
            sell_by_dayhour[bucket_of(d)] += q
            qty_hist[q] += 1
    sell_by_dayhour_zero = Counter()
    n_with_sells_zero = 0
    for g in zero:
        evs = market_events(g, 'SELL', 'WOOL')
        if evs:
            n_with_sells_zero += 1
        for d, h, q in evs:
            sell_by_dayhour_zero[bucket_of(d)] += q
    return dict(
        games_with_yarn=len(with_yarn), games_with_yarn_and_any_wool_sell=n_with_sells,
        wool_sold_by_day_bucket_yarn_games=dict(sorted(sell_by_dayhour.items())),
        qty_per_sell_order_histogram=dict(qty_hist.most_common()),
        zero_yarn_games=len(zero), zero_yarn_games_with_any_wool_sell=n_with_sells_zero,
        wool_sold_by_day_bucket_zero_yarn_games=dict(sorted(sell_by_dayhour_zero.items())),
    )


# ---------------------------------------------------------------------------
# Q6: payoff
# ---------------------------------------------------------------------------

def q6_payoff(games):
    def n_yarn(g):
        n = len(yarn_days(g))
        return n if n < 3 else '3+'

    by_count = {}
    for key in (0, 1, 2, '3+'):
        grp = [g for g in games if n_yarn(g) == key]
        if grp:
            by_count[str(key)] = dict(n=len(grp), mean_final_cash=round(mean(g['rewards'][g['seat']] for g in grp), 0))

    early_late = {}
    for key in (1, 2):
        grp = [g for g in games if n_yarn(g) == key]
        early = [g for g in grp if min(yarn_days(g)) <= 9]
        late = [g for g in grp if min(yarn_days(g)) >= 15]
        entry = {}
        if early:
            entry['early_first_reveal_le_9'] = dict(n=len(early), mean_final_cash=round(mean(g['rewards'][g['seat']] for g in early), 0))
        if late:
            entry['late_first_reveal_ge_15'] = dict(n=len(late), mean_final_cash=round(mean(g['rewards'][g['seat']] for g in late), 0))
        early_late[str(key)] = entry
    return dict(by_yarn_count=by_count, early_vs_late_within_count=early_late,
                note='opponent differs per game (rating and policy both vary), so cash differences are suggestive only, not causal.')


def main():
    games = load_games()
    assert len(games) == 584, f'expected 584 tapes, found {len(games)}'
    result = dict(
        n_games=len(games),
        q1_sheep_by_reveal_group=q1_groups(games),
        q2_trigger_rule=q2_profiles(games),
        q3_placement=q3_placement(games),
        q4_tradeoffs=q4_tradeoffs(games),
        q5_wool_selling=q5_wool(games),
        q6_payoff=q6_payoff(games),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('wrote', OUT)


if __name__ == '__main__':
    main()
