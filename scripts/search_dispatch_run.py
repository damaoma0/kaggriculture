"""Runner for the search-dispatch tests in leader worlds (Kaggle side; games never run on the shared laptop).

It plays agents/mgt_lead_search.py through scripts/lead_sem4.py's play() (the lead_g1 world: recorded seed, forced shop
sequence, the opponent's recorded actions, our executor in the leader's seat following the leader's exact plan; sem4's
REPRO arms reproduce lead_g1 / lead_ablation results to the dollar) because it records the metrics wanted here
(effective maintenance ops by type, moves, deaths, rot units, discards, per quadrant / day). Arms are injected into
lead_sem4.ARMS in memory and its output directory is redirected (the file is not edited):

  SDoff  dispatch_search off      (= the source mgt_lead.py decisions)     + EXEC_CFG
  SDsh   dispatch_search shadow   (greedy acts; must equal SDoff to the dollar)
  SDa12  dispatch_search active, sd_days [12, 23]
  SDall  dispatch_search active, every day
  v2 (block v2 options, V2 below: in-day delivery credit tables DVF / DVC + final trip, hard ops late penalty, every
  unit a candidate for hard jobs, hard-job insertion with ejection):
  V2sh   shadow + V2 (greedy acts; must equal SDoff to the dollar)
  V2a12  active, sd_days [12, 23] + V2
  V2all  active, every day + V2
  V2a12x active, sd_days [12, 23] + V2 with the delivery credit doubled
  V3sh / V3a12 / V3all  V3 = V2 with the credit x2 + survival from 16h + overnight shed-cap term + harvest tendencies
         HV (sd_hv_pref, melon offer) + marginal-revenue values (sd_mr); V3a12m0 = V3a12 without sd_mr
  (EXEC_CFG = p1_min_value 30, release_stale_d True, fert_hold 1: the deploy's executor defaults, as the G1 / sem4 runs)

usage: search_dispatch_run.py --arms SDoff,SDsh (--g1 | --games team:ep,... | --worlds FILE [--shard i/n])
                              [--workers 4] [--cfg 'k=v;k=v'] [--suffix X]
Results: results/fresh/search_dispatch_20260925/lead_worlds/<arm><suffix>/<ep>.json (+ manifest)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import lead_g1  # noqa: E402
import lead_sem4 as L4  # noqa: E402

AGENT = 'agents/mgt_lead_search.py'
EXEC = dict(L4.EXEC_CFG)
ARMS = {
    'SDoff': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='off')),
    'SDsh': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='shadow')),
    'SDa12': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active', sd_days=[12, 23])),
    'SDall': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active')),
}
# v2 priors (coins per unit delivered by 22h = frac x the current price + coins; wheat / egg / fertilizer 0; only
# products whose leader sell quota of the day has room, sd_dv_quota): melon highest (town-center demand only, the
# first units sold take the price; leaders sell 87% of melons the day they pick them), wool / milk next (v1's largest
# price losses: wool ~20% of the price per unit sold a day late; rival revenue per unit withheld milk 88, wool 71),
# strawberry / tomato / carrot low (leaders sell them mostly the next morning). Swappable for the measured
# same-day-vs-next-morning margin table.
DVF = {'MELON': 0.2, 'WOOL': 0.15, 'MILK': 0.1, 'STRAWBERRY': 0.05, 'TOMATO': 0.03, 'CARROT': 0.01}
DVC = {'MELON': 20, 'WOOL': 12, 'MILK': 15, 'STRAWBERRY': 4, 'TOMATO': 2, 'CARROT': 1}
V2 = dict(sd_dv_frac=DVF, sd_dv_coins=DVC, sd_final_trip=1, sd_hard_late_w=30.0, sd_hard_all=1, sd_hard_eject=1)
V2X = dict(V2, sd_dv_frac={k: 2 * v for k, v in DVF.items()}, sd_dv_coins={k: 2 * v for k, v in DVC.items()})
ARMS.update({
    'V2sh': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='shadow', **V2)),
    'V2a12': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active', sd_days=[12, 23], **V2)),
    'V2all': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active', **V2)),
    'V2a12x': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active', sd_days=[12, 23], **V2X)),
})
# v3: the leaders' harvest timing as soft bonuses on HARVEST ops (user ruling 2026-09-25; the executor gets the same
# table later): a one-time crop on its last day before decay; wheat at age 2-3 on days 0-11 and 3-4 from day 12;
# carrots at age 3; melons once today's water brings them to 6, early in the morning (-hour_w a hour after by_hour;
# the delivery credit sells them the same day); tomatoes / strawberries at every production.
HV = {'decay': {'bonus': 500.0},
      'WHEAT': {'bonus': 30.0, 'ages': [[0, 11, 2, 3], [12, 29, 3, 4]]},
      'CARROT': {'bonus': 30.0, 'ages': [[0, 29, 3, 3]]},
      'MELON': {'bonus': 80.0, 'full': 1, 'by_hour': 8, 'hour_w': 20.0, 'offer': 1},
      'TOMATO': {'bonus': 20.0}, 'STRAWBERRY': {'bonus': 20.0}}
# V3 = V2 with the credit x2 (V2a12x beat V2a12: +1,036 9/3 vs +90 3/9, n.s.), survival pulled earlier (60 coins an hour
# after 16h; v2's 30 after 20h left dry-at-23h at 46), the shed-cap term over overnight shed items, and HV.
# + maintenance values at marginal revenue (sd_mr: coordinator, the glut curves answer extra volume)
V3 = dict(V2X, sd_hard_late_w=60.0, sd_hard_safe=16, sd_cap_all=1, sd_hv_pref=HV, sd_mr=1)
ARMS.update({
    'V3sh': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='shadow', **V3)),
    'V3a12': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active', sd_days=[12, 23], **V3)),
    'V3all': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active', **V3)),
    'V3a12m0': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active', sd_days=[12, 23], **dict(V3, sd_mr=0))),
})
# v4 = V3 with the MEASURED same-day credit (coordinator 2026-09-25, 230 replays with per-step market data,
# results/fresh/harvest_timing_20260925/market/credit_tables.json: margin credit = own gain - own cannibalization + rival
# loss, coins per unit sold now vs the next morning, by period d0-5 / d6-11 / d12-17 / d18-23 / d24-28; negatives -> 0;
# wheat / carrot / tomato / egg within +-1 -> 0; fertilizer none). Melon's by-hour pattern (h0-11 ~+50, afternoon ~+10)
# is carried by HV's early-morning soft target.
DVC_M = {'MELON': [[0, 0.0], [6, 53.8], [12, 3.1], [18, 8.6], [24, 0.5]],
         'WOOL': [[0, 0.0], [6, 26.4], [12, 9.3], [18, 7.1], [24, 5.8]],
         'MILK': [[0, 0.0], [6, 13.4], [12, 7.2], [18, 0.8], [24, 0.0]],
         'STRAWBERRY': [[0, 0.0], [6, 0.0], [12, 2.9], [18, 4.8], [24, 0.0]]}
V4 = dict(V3, sd_dv_frac={}, sd_dv_coins=DVC_M)
ARMS.update({
    'V4a12': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active', sd_days=[12, 23], **V4)),
    'V4all': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active', **V4)),
})
# v5 (coordinator: margin decides games) = V4 judged on margin: plain-price job values (margin MR = price - own slope x our
# remaining sales + slope x rival remaining sales = price when the rival sells alike) and the executor's survival routes
# guaranteed from 20h (sd_surv_fb).
V5 = dict(V4, sd_mr=0, sd_surv_fb=20)
ARMS.update({
    'V5a12': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active', sd_days=[12, 23], **V5)),
    'V5all': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active', **V5)),
    'V5sh': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='shadow', **V5)),
})


def main(argv):
    L4.ARMS.update(ARMS)
    L4.OUT = ROOT / 'results/fresh/search_dispatch_20260925/lead_worlds'
    out = []
    i = 0
    while i < len(argv):
        if argv[i] == '--g1':
            out += ['--games', ','.join(lead_g1.GAMES)]
            i += 1
        else:
            out.append(argv[i])
            i += 1
    L4.run(out)


if __name__ == '__main__':
    main(sys.argv[1:])
