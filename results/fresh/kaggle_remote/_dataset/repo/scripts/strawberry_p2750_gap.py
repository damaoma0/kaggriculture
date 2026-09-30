"""Strawberry (and wool/milk context) revenue/unit gap on the 2750-3000 ladder panel, at today's
opponent level, for mgt_m1 and mgt_y3.

Uses scripts/ladder_panel.py's per-game output (rival_revenue/rival_sold/rival_spend and per-day
cumulative revenue_daily/rival_revenue_daily for both sides, already recorded by that harness).
This script only reads results/fresh/ladder_panel/<agent>/<episode>.json and
data/ladder_panel/p2750/<episode>.json.gz (for shop timing/world type); it runs no games itself.

World type: strawberry-buying shops (BRUNCH_SPOT, ICE_CREAM_SHOP, SMOOTHIE_SHOP, FARMERS_MARKET)
among the first 4 unlocked shop instances ("early", unlock days 3/6/9/12) vs the last 4
("late", unlock days 15/18/21/24).

When-in-season: per-day (non-cumulative) revenue from diffing consecutive revenue_daily snapshots
(index d+1 minus index d = revenue earned during day d; final game-end settlement folded into day 29),
summed over early(12-17)/mid(18-23)/late(24-29) day windows.

Output: results/fresh/newphase_20260923/strawberry/p2750_gap.json
"""
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Read directly from this thread's own remote-panel fetch output (results/fresh/kaggle_remote_straw/<run>/output/),
# never from the shared results/fresh/ladder_panel cache: every p2750 episode already has a STALE cached
# mgt_m1/mgt_y3 result there (pre-dating rival_revenue/rival_sold/revenue_daily), and other threads on this
# shared machine may be reading/writing that shared cache concurrently.
REMOTE_RUN_DIR = ROOT / 'results/fresh/kaggle_remote_straw/straw1/output'
GAMES = ROOT / 'data/ladder_panel/p2750'
OUT = ROOT / 'results/fresh/newphase_20260923/strawberry'
STRAW_SHOPS = {'BRUNCH_SPOT', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP', 'FARMERS_MARKET'}
MILK_SHOPS = {'PIZZA_SHOP', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP'}


def world_type(ep):
    g = json.load(gzip.open(GAMES / f'{ep}.json.gz', 'rt', encoding='utf-8'))
    shops = g['shops'][-1]                       # full 8 instances, unlock order
    first4, last4 = shops[:4], shops[4:8]
    return dict(early_straw=sum(1 for s in first4 if s in STRAW_SHOPS),
                late_straw=sum(1 for s in last4 if s in STRAW_SHOPS),
                early_wool=sum(1 for s in first4 if s == 'YARN_STORE'),
                late_wool=sum(1 for s in last4 if s == 'YARN_STORE'),
                early_milk=sum(1 for s in first4 if s in MILK_SHOPS),
                late_milk=sum(1 for s in last4 if s in MILK_SHOPS),
                shops=shops)


def day_window_revenue(revenue_daily, product, lo, hi):
    """Sum of per-day (non-cumulative) revenue for `product` over days [lo, hi] inclusive.
    revenue_daily[d] is cumulative through the START of day d (d=0..29); revenue_daily[30] is the
    final post-settlement cumulative total (through end of day 29)."""
    total = 0.0
    for d in range(lo, hi + 1):
        a = revenue_daily[d].get(product, 0) if d < len(revenue_daily) else 0
        nxt = d + 1
        b = revenue_daily[nxt].get(product, 0) if nxt < len(revenue_daily) else a
        total += b - a
    return total


def load_agent(agent):
    rows = {}
    if not REMOTE_RUN_DIR.exists():
        return rows
    for f in REMOTE_RUN_DIR.rglob('*.json'):
        if f.name == 'run_info.json':
            continue
        r = json.loads(f.read_text(encoding='utf-8'))
        if r.get('agent') != agent:
            continue
        rows[str(r['episode'])] = r
    return rows


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def summarize_product(rows, wt, product):
    per_game = []
    for ep, r in rows.items():
        own_rev = r['revenue'].get(product, 0)
        opp_rev = r['rival_revenue'].get(product, 0)
        own_u = r['sold'].get(product, 0)
        opp_u = r['rival_sold'].get(product, 0)
        w = wt[ep]
        per_game.append(dict(episode=ep, own_rev=own_rev, opp_rev=opp_rev, own_units=own_u,
                              opp_units=opp_u, rev_gap=own_rev - opp_rev, unit_gap=own_u - opp_u,
                              margin=r['margin'], win=r['margin'] > 0,
                              early_straw=w['early_straw'], late_straw=w['late_straw'],
                              early_wool=w['early_wool'], late_wool=w['late_wool'],
                              early_milk=w['early_milk'], late_milk=w['late_milk']))
    return per_game


def bucket_report(per_game, key):
    buckets = {}
    for row in per_game:
        b = row[key]
        buckets.setdefault(b, []).append(row)
    out = {}
    for b, grp in sorted(buckets.items()):
        out[str(b)] = dict(
            n=len(grp), wins=sum(r['win'] for r in grp), losses=sum(not r['win'] for r in grp),
            mean_own_rev=round(mean([r['own_rev'] for r in grp]), 1),
            mean_opp_rev=round(mean([r['opp_rev'] for r in grp]), 1),
            mean_rev_gap=round(mean([r['rev_gap'] for r in grp]), 1),
            mean_own_units=round(mean([r['own_units'] for r in grp]), 2),
            mean_opp_units=round(mean([r['opp_units'] for r in grp]), 2),
            mean_unit_gap=round(mean([r['unit_gap'] for r in grp]), 2),
            mean_margin=round(mean([r['margin'] for r in grp]), 1))
    return out


def when_in_season(rows, wt, product, agent_label):
    windows = dict(early=(12, 17), mid=(18, 23), late=(24, 29))
    out = {}
    for wname, (lo, hi) in windows.items():
        own_vals, opp_vals = [], []
        for ep, r in rows.items():
            own_vals.append(day_window_revenue(r['revenue_daily'], product, lo, hi))
            opp_vals.append(day_window_revenue(r['rival_revenue_daily'], product, lo, hi))
        out[wname] = dict(days=[lo, hi], n=len(own_vals),
                           mean_own=round(mean(own_vals), 1), mean_opp=round(mean(opp_vals), 1),
                           mean_gap=round(mean(own_vals) - mean(opp_vals), 1),
                           total_own=round(sum(own_vals), 1), total_opp=round(sum(opp_vals), 1))
    return out


def main():
    agents = ['mgt_m1', 'mgt_y3']
    result = {}
    for agent in agents:
        rows = load_agent(agent)
        if not rows:
            print(f'{agent}: no local results found under {PANEL / agent} (fetch/merge the remote run first)')
            continue
        wt = {ep: world_type(ep) for ep in rows}
        agent_out = dict(n_games=len(rows), wins=sum(r['margin'] > 0 for r in rows.values()),
                          losses=sum(r['margin'] <= 0 for r in rows.values()),
                          mean_margin=round(mean([r['margin'] for r in rows.values()]), 1))
        for product in ('STRAWBERRY', 'WOOL', 'MILK'):
            per_game = summarize_product(rows, wt, product)
            agent_out[product] = dict(
                overall=dict(mean_own_rev=round(mean([r['own_rev'] for r in per_game]), 1),
                             mean_opp_rev=round(mean([r['opp_rev'] for r in per_game]), 1),
                             mean_rev_gap=round(mean([r['rev_gap'] for r in per_game]), 1),
                             mean_own_units=round(mean([r['own_units'] for r in per_game]), 2),
                             mean_opp_units=round(mean([r['opp_units'] for r in per_game]), 2),
                             mean_unit_gap=round(mean([r['unit_gap'] for r in per_game]), 2)),
                by_early_shops=bucket_report(per_game, 'early_straw' if product == 'STRAWBERRY'
                                              else ('early_wool' if product == 'WOOL' else 'early_milk')),
                by_late_shops=bucket_report(per_game, 'late_straw' if product == 'STRAWBERRY'
                                             else ('late_wool' if product == 'WOOL' else 'late_milk')),
                when_in_season=when_in_season(rows, wt, product, agent))
        # margin vs strawberry rev_gap correlation (simple: mean margin in games where we're strawberry-net-negative vs net-positive)
        straw_pg = summarize_product(rows, wt, 'STRAWBERRY')
        neg = [r for r in straw_pg if r['rev_gap'] < -500]
        pos = [r for r in straw_pg if r['rev_gap'] > 500]
        agent_out['margin_vs_straw_gap'] = dict(
            straw_deficit_n=len(neg), straw_deficit_mean_margin=round(mean([r['margin'] for r in neg]), 1) if neg else None,
            straw_deficit_win_rate=round(mean([r['win'] for r in neg]), 3) if neg else None,
            straw_surplus_n=len(pos), straw_surplus_mean_margin=round(mean([r['margin'] for r in pos]), 1) if pos else None,
            straw_surplus_win_rate=round(mean([r['win'] for r in pos]), 3) if pos else None)
        result[agent] = agent_out

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'p2750_gap.json').write_text(json.dumps(result, indent=1), encoding='utf-8')

    for agent, a in result.items():
        print(f'\n=== {agent}: n={a["n_games"]} W-L {a["wins"]}-{a["losses"]}, mean margin {a["mean_margin"]:+,.0f} ===')
        for product in ('STRAWBERRY', 'WOOL', 'MILK'):
            o = a[product]['overall']
            print(f'  {product}: own_rev {o["mean_own_rev"]:,.0f} vs opp {o["mean_opp_rev"]:,.0f} '
                  f'(gap {o["mean_rev_gap"]:+,.0f}); own_units {o["mean_own_units"]:.1f} vs opp {o["mean_opp_units"]:.1f} '
                  f'(gap {o["mean_unit_gap"]:+.1f})')
            print(f'    by early shops: {a[product]["by_early_shops"]}')
            print(f'    by late shops:  {a[product]["by_late_shops"]}')
            w = a[product]['when_in_season']
            print(f'    when: early(12-17) gap {w["early"]["mean_gap"]:+,.0f}, mid(18-23) gap {w["mid"]["mean_gap"]:+,.0f}, '
                  f'late(24-29) gap {w["late"]["mean_gap"]:+,.0f}')
        m = a['margin_vs_straw_gap']
        print(f'  margin vs strawberry gap: deficit games n={m["straw_deficit_n"]} mean margin {m["straw_deficit_mean_margin"]} '
              f'win_rate {m["straw_deficit_win_rate"]}; surplus games n={m["straw_surplus_n"]} mean margin {m["straw_surplus_mean_margin"]} '
              f'win_rate {m["straw_surplus_win_rate"]}')


if __name__ == '__main__':
    main()
