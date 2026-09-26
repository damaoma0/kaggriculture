"""Planner-on-day-11 and sector tests in the day-11 exact-start worlds (thread "search dispatch", 2026-09-25).

Uses scripts/xfix_run.py READ-ONLY (the day-11 agent owns it): its trace / full modes are called with this module's arms
injected into xfix_run.ARMS in memory and its output directory redirected to results/fresh/sector_20260925 (the 42-world
list is still read from results/fresh/xfix_20260925/worlds42.json).

  trace  day 11 from the leader's exact morning state (leader actions through step 263, then the arm), per-unit per-step
         records + opponent cash at the day-11 / day-12 mornings -> OUT/trace/<arm>/<ep>.json (42 worlds)
  full   full games, the arm from step 0, --worlds g1 | sem4 | all (all = the 52 G1 + sem4 worlds) -> OUT/full/<arm>/<ep>.json

Arms (agents/mgt_lead_search2.py = mgt_lead.py at git f8b48ef, the current T, + the planner block; agents/mgt_lead_sector.py
= the same + the sector term):
  N0    planner off (= the current T)
  N11   planner days 11-23, the shipping settings (v1 + survival fallback, deterministic budgets)
  N12   planner days 12-23, the shipping settings (= the deploy candidate's window)
  S0 / S11  the sector copy with the sector term off (must equal N0 / N11)
  S11f  the day-11 planner + the seed fix (sd_seed_fix); the S11w.. arms all include it
  (arm names must differ case-insensitively: Windows merges result folders)
  S11w / S11h / S11wh / S11wh2  day-11 planner + sectors (sd_sector_w 40) / contiguity (sd_hop_w 20) / both / both x2
Offline measurement: the wall-clock caps are raised (2 / 1 / 3 s) so the deterministic evaluation budgets decide even
under the harness's instrumentation (on Kaggle's runner the shipping caps 0.75 / 0.6 / 0.8 s essentially never fire).

  both   trace (42 worlds) + stream: the viewer's days-11-12 streams of the 12 G1 worlds -> results/fresh/day12_viz/<arm>_streams/
usage: sector_run.py trace|both|full <arm,...> [--worlds all] [--games ep,...] [--workers 4]
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import xfix_run as X  # noqa: E402

OUT = ROOT / 'results/fresh/sector_20260925'
SHIP = dict(sd_surv_fb=20, sd_evals0=24000, sd_evals=8000, sd_budget0=2.0, sd_budget=1.0, sd_step_cap=3.0)
S2, SEC = 'agents/mgt_lead_search2.py', 'agents/mgt_lead_sector.py'
DVC_M = {'MELON': [[0, 0.0], [6, 53.8], [12, 3.1], [18, 8.6], [24, 0.5]],
         'WOOL': [[0, 0.0], [6, 26.4], [12, 9.3], [18, 7.1], [24, 5.8]],
         'MILK': [[0, 0.0], [6, 13.4], [12, 7.2], [18, 0.8], [24, 0.0]],
         'STRAWBERRY': [[0, 0.0], [6, 0.0], [12, 2.9], [18, 4.8], [24, 0.0]]}
HVM = {'decay': {'bonus': 500.0}, 'MELON': {'bonus': 80.0, 'full': 1, 'by_hour': 8, 'hour_w': 20.0}}
HVM_MEL = {'MELON': HVM['MELON']}          # M: the melon part only (audit items 1-3; the decay item 8 stays off)
MDEC = dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0, sd_dv_coins=DVC_M,
            sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1, sd_hv_pref=HVM, sd_hp_parity=1, **SHIP)   # = M_decay
ARMS_C3F80 = dict(MDEC, sd_fert_sell=1, sd_retire=1, sd_hard_late_w=10.0, sd_hard_safe=16, sd_water_tomorrow=10.0,
                  sd_fert_ret=1, sd_fert_first=1, sd_fert_first_crops=['WHEAT', 'CARROT'], sd_fert_frac=1.0,
                  sd_collect_floor=80.0, sd_finish_collect=1)     # = C3f80
# B1 (user, 2026-09-28): every fix so far on M_decay -- explicit recipe
ARMS_B1 = dict(MDEC,
               sd_fert_sell=1, sell_now=['MELON'],                                   # leader fertilizer policy; melons sold on arrival
               sd_retire=1, sd_hard_late_w=10.0, sd_hard_safe=16,                    # survival water late weight 10 after h16, retired exempt
               sd_water_tomorrow=10.0,                                               # idle waters worth 10
               sd_fert_ret=1, sd_collect_floor=80.0, sd_finish_collect=1,            # cycle: fertilizer back with goods, collect >= 80, collect before leaving
               sd_fert_first=1, sd_fert_first_crops=['WHEAT', 'CARROT'], sd_fert_frac=1.0,
               sd_fert_ages={'WHEAT': [1, 2], 'CARROT': [1, 2]},                     # wheat / carrot fertilized at age 1-2
               hp_crops=['MELON', 'WHEAT'], hp_wheat_min_units=5,                    # fertilized wheat harvested at age 3 (5 units)
               cut_mode='leader_harvest',                                            # late plantings the leader harvests are kept
               sd_feed_bonus=20.0)                                                   # +20 on every feed / care
ARMS = {
    'N0': (S2, dict(dispatch_search='off')),
    'N11': (S2, dict(dispatch_search='active', sd_days=[11, 23], **SHIP)),
    'N12': (S2, dict(dispatch_search='active', sd_days=[12, 23], **SHIP)),
    'S0': (SEC, dict(dispatch_search='off')),                                        # must equal N0
    'S11': (SEC, dict(dispatch_search='active', sd_days=[11, 23], **SHIP)),          # must equal N11 (sector off)
    'S11f': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, **SHIP)),          # seed fix only
    'S11w': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, **SHIP)),       # + sectors
    'S11h': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_hop_w=20.0, **SHIP)),          # + contiguity
    'S11wh': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0, **SHIP)),
    # the measured same-day credit (coordinator table: melon 53.8 a unit on days 6-11, wool 26.4, milk 13.4, ...) + the
    # final delivery trip: v1 carried the day-11 melons to midnight (17.2 melons in the shed next morning vs 5.7)
    'S11c': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1, **SHIP)),
    'S11ca': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                        sd_early_animal=1, **SHIP)),
    'S11caw': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                         sd_early_animal=1, sd_sector_w=40.0, sd_hop_w=20.0, **SHIP)),
    # round 3 (base = S11ca + the water-before-harvest fix): spawn steering / hires by demand / both
    'S11cf': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                        sd_early_animal=1, sd_water_first=1, **SHIP)),
    'S11cfs': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                         sd_early_animal=1, sd_water_first=1, sd_spawn_steer=1, **SHIP)),
    'S11cfd': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                         sd_early_animal=1, sd_water_first=1, sd_hire_demand=1, **SHIP)),
    'S11cfsd': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                          sd_early_animal=1, sd_water_first=1, sd_spawn_steer=1, sd_hire_demand=1, **SHIP)),
    # round 3b (parity audit): base S11cf + the melon harvest tendency in the planner (sd_hv_pref melon + decay), the
    # executor's harvest_policy values (sd_hp_parity), the coop build split from the goose placement (sd_split_place)
    'S11cg': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                        sd_early_animal=1, sd_water_first=1, sd_hv_pref=HVM, sd_hp_parity=1, sd_split_place=1, **SHIP)),
    'S11cgs': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                         sd_early_animal=1, sd_water_first=1, sd_hv_pref=HVM, sd_hp_parity=1, sd_split_place=1,
                         sd_spawn_steer=1, **SHIP)),
    'S11cgd': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                         sd_early_animal=1, sd_water_first=1, sd_hv_pref=HVM, sd_hp_parity=1, sd_split_place=1,
                         sd_hire_demand=1, **SHIP)),
    'S11cgsd': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                          sd_early_animal=1, sd_water_first=1, sd_hv_pref=HVM, sd_hp_parity=1, sd_split_place=1,
                          sd_spawn_steer=1, sd_hire_demand=1, **SHIP)),
    # round 4 (user design): the BUILD + animal bundle, one hand, the animal bought at hour 0, instead of the split
    'S11cb': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                        sd_early_animal=1, sd_water_first=1, sd_hv_pref=HVM, sd_hp_parity=1, sd_bundle_build=1, **SHIP)),
    'S11cbs': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                         sd_early_animal=1, sd_water_first=1, sd_hv_pref=HVM, sd_hp_parity=1, sd_bundle_build=1,
                         sd_spawn_steer=1, **SHIP)),
    'S11cbd': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                         sd_early_animal=1, sd_water_first=1, sd_hv_pref=HVM, sd_hp_parity=1, sd_bundle_build=1,
                         sd_hire_demand=1, **SHIP)),
    'S11cbsd': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                          sd_early_animal=1, sd_water_first=1, sd_hv_pref=HVM, sd_hp_parity=1, sd_bundle_build=1,
                          sd_spawn_steer=1, sd_hire_demand=1, **SHIP)),
    # round 5: the bundle base + idle fill (waters worth tomorrow's labour, idle fertilizer delivered) + radial corridors
    'S11ci': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                        sd_early_animal=1, sd_water_first=1, sd_hv_pref=HVM, sd_hp_parity=1, sd_bundle_build=1,
                        sd_water_tomorrow=40.0, sd_idle_fert=1, **SHIP)),
    'S11cr': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                        sd_early_animal=1, sd_water_first=1, sd_hv_pref=HVM, sd_hp_parity=1, sd_bundle_build=1,
                        sd_water_tomorrow=40.0, sd_idle_fert=1, sd_corr_w=40.0, sd_rad_in=20.0, sd_rad_side=10.0, **SHIP)),
    'S11cr2': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                         sd_early_animal=1, sd_water_first=1, sd_hv_pref=HVM, sd_hp_parity=1, sd_bundle_build=1,
                         sd_water_tomorrow=40.0, sd_idle_fert=1, sd_corr_w=80.0, sd_rad_in=40.0, sd_rad_side=20.0, **SHIP)),
    'S11crr': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_dv_coins=DVC_M, sd_final_trip=1,
                         sd_early_animal=1, sd_water_first=1, sd_hv_pref=HVM, sd_hp_parity=1, sd_bundle_build=1,
                         sd_water_tomorrow=40.0, sd_idle_fert=1, sd_rad_in=20.0, sd_rad_side=10.0, **SHIP)),
    # main branch M (user, 2026-09-26): S11wh (sector homes 40 + patch contiguity 20) + melon prioritization (sd_hv_pref
    # melon full-yield bonus by hour 8, no decay item, sd_hp_parity: melon harvest in the leaders' window and window water) + the
    # melon sale fix (measured credit + final trip) + water before harvest + the coop / goose pair job (goose bought at h0,
    # must land by the day end, any hour); M_idle = M + idle fill. Streams carry "plan" (each hand's job tiles).
    'M': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                    sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                    sd_hv_pref=HVM_MEL, sd_hp_parity=1, **SHIP)),
    'M_idle': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                         sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                         sd_hv_pref=HVM_MEL, sd_hp_parity=1,
                         sd_water_tomorrow=40.0, sd_idle_fert=1, **SHIP)),
    # M2 (fix after the M run): M + the place-now rule in hook 3 (every unit, survival-fallback ones too) + the pair's
    # PLACE hard deadline at h19 (slack before the survival fallback; the day end once h19 has passed); M2a: rule only
    'M2': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                     sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                     sd_hv_pref=HVM_MEL, sd_hp_parity=1, sd_coop_place=1, sd_coop_by=19, **SHIP)),
    'M2a': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                      sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                      sd_hv_pref=HVM_MEL, sd_hp_parity=1, sd_coop_place=1, **SHIP)),
    # M2i: M2 + idle fill v2 (empty-route hands only, no values: same-day delivery, then the nearest dry plant at home)
    'M2i': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                      sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                      sd_hv_pref=HVM_MEL, sd_hp_parity=1, sd_coop_place=1, sd_coop_by=19, sd_idle_v2=1, **SHIP)),
    # M_decay (user, one world): M + the decay item of sd_hv_pref exactly as in S11cg (HVM = decay 500 + M's melon entry)
    'M_decay': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                          sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                          sd_hv_pref=HVM, sd_hp_parity=1, **SHIP)),
    # M_once (user, one world): M_decay + plan once in the morning, frozen routes, local repairs on breakage only
    'M_once': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                         sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                         sd_hv_pref=HVM, sd_hp_parity=1, sd_plan_once=1, sd_once_evals=48000, **SHIP)),
    # M_once2 (user, one world): M_once + repair (c) as a limited reassignment
    'M_once2': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                          sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                          sd_hv_pref=HVM, sd_hp_parity=1, sd_plan_once=1, sd_once_evals=48000, sd_once_steal=1, **SHIP)),
    # days 11-14 (mode multi): M_decay14 = M_decay; F1 = M_decay + mj_fertilize True (fertilizer charged at 0)
    'M_decay14': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                            sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                            sd_hv_pref=HVM, sd_hp_parity=1, **SHIP)),
    'F1': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                     sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                     sd_hv_pref=HVM, sd_hp_parity=1, mj_fertilize=True, **SHIP)),
    # F3 (user, days 11-14): F1 + FERTILIZE on the first day it adds units; H1 (user, day 11, world 112673479): M_decay +
    # hard ops cost 30 an hour after h16 + a hard job nobody can take ejects the least-value non-hard jobs
    'F3': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                     sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                     sd_hv_pref=HVM, sd_hp_parity=1, mj_fertilize=True, sd_fert_first=1, **SHIP)),
    'H1': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                     sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                     sd_hv_pref=HVM, sd_hp_parity=1, sd_hard_late_w=30.0, sd_hard_safe=16, sd_hard_eject=1, **SHIP)),
    # sweeps (user, single worlds)
    **{f'fv{int(f * 100):02d}': (SEC, dict(MDEC, sd_fert_first=1, sd_fert_frac=f)) for f in (0.0, 0.25, 0.5, 0.75)},
    **{f'hw{w:02d}e{e}': (SEC, dict(MDEC, sd_retire=1, sd_hard_late_w=float(w), sd_hard_safe=16, sd_hard_eject=e))
       for w in (5, 10, 20, 40) for e in (0, 1)},
    **{f'if{w:02d}': (SEC, dict(MDEC, sd_water_tomorrow=float(w), sd_idle_fert=1)) for w in (5, 10, 20)},
    'iv2': (SEC, dict(MDEC, sd_idle_v2=1)),
    'rt0': (SEC, dict(MDEC, sd_retire=1)),        # reference: the retirement exemption alone
    # fertilizer policy (user + leader tapes, 2026-09-27): sell the whole shed stock, never pick fertilizer up from the
    # shed, keep collected fertilizer in hand for fertilizing (midnight dump -> sold next morning); on top, fertilize on
    # the first useful day with fertilizer charged at a fraction of its price
    'G0': (SEC, dict(MDEC, sd_fert_sell=1)),
    # new main branch candidate (user, 2026-09-28): G0 + survival water late weight 10 after h16 (retired plants exempt)
    # + idle waters worth 10 (idle hands do NOT deliver fertilizer: the fertilizer policy keeps it in hand)
    'C1': (SEC, dict(MDEC, sd_fert_sell=1, sd_retire=1, sd_hard_late_w=10.0, sd_hard_safe=16, sd_water_tomorrow=10.0)),
    # the user's cycle (2026-09-28): wheat out, feed / care / collect on the way, missions + fertilize, back with
    # fertilizer and goods (dropped together at the shed), unused fertilizer sold; on top of C1
    **{f'C2f{f}': (SEC, dict(MDEC, sd_fert_sell=1, sd_retire=1, sd_hard_late_w=10.0, sd_hard_safe=16, sd_water_tomorrow=10.0,
                            sd_fert_ret=1, sd_fert_first=1, sd_fert_first_crops=['WHEAT', 'CARROT'], sd_fert_frac=1.0,
                            sd_collect_floor=float(f))) for f in (20, 40, 80)},
    **{f'C3f{f}': (SEC, dict(MDEC, sd_fert_sell=1, sd_retire=1, sd_hard_late_w=10.0, sd_hard_safe=16, sd_water_tomorrow=10.0,
                            sd_fert_ret=1, sd_fert_first=1, sd_fert_first_crops=['WHEAT', 'CARROT'], sd_fert_frac=1.0,
                            sd_collect_floor=float(f), sd_finish_collect=1)) for f in (20, 80)},   # C2 + finish the tile (collect before leaving)
    'C3n': (SEC, dict(MDEC, sd_fert_sell=1, sd_retire=1, sd_hard_late_w=10.0, sd_hard_safe=16, sd_water_tomorrow=10.0,
                      sd_fert_ret=1, sd_collect_floor=40.0, sd_finish_collect=1)),
    # the wheat cycle on top of C3f80 (user, 2026-09-28): fertilized wheat harvested from age 3 (5 units after today's water)
    # and replanted on the leader's tile; strength sweep: W3b = every wheat from age 3, W3c = W3a + an age-3 bonus of 40
    'W3a': (SEC, dict(ARMS_C3F80, hp_crops=['MELON', 'WHEAT'], hp_wheat_min_units=5)),
    'W3b': (SEC, dict(ARMS_C3F80, hp_crops=['MELON', 'WHEAT'])),
    # fertilize wheat / carrots at age 1-2 (or 2 only) and harvest fertilized wheat at age 3 (user, 2026-09-28)
    'W4a': (SEC, dict(ARMS_C3F80, hp_crops=['MELON', 'WHEAT'], hp_wheat_min_units=5, sd_fert_ages={'WHEAT': [1, 2], 'CARROT': [1, 2]})),
    # collect on the way out (user cycle) on top of W4a: threshold sweep 1 / 3 / 6 fertilizer carried
    **{f'X1t{k}': (SEC, dict(ARMS_C3F80, hp_crops=['MELON', 'WHEAT'], hp_wheat_min_units=5,
                            sd_fert_ages={'WHEAT': [1, 2], 'CARROT': [1, 2]}, sd_path_collect=k)) for k in (1, 3, 6)},
    # X1t6 with a smaller charged fertilizer price for the wheat / carrot fertilize jobs (user: smaller value): sweep
    **{f'X2f{int(f * 100):02d}': (SEC, dict(ARMS_C3F80, hp_crops=['MELON', 'WHEAT'], hp_wheat_min_units=5,
                            sd_fert_ages={'WHEAT': [1, 2], 'CARROT': [1, 2]}, sd_path_collect=6, sd_fert_frac=f))
       for f in (0.5, 0.25, 0.0)},
    # each hand carries what its trip needs: the shed keeps today's fertilize need at the morning sale (sd_fert_sell 2)
    **{f'X3f{int(f * 100):02d}': (SEC, dict(ARMS_C3F80, sd_fert_sell=2, hp_crops=['MELON', 'WHEAT'], hp_wheat_min_units=5,
                            sd_fert_ages={'WHEAT': [1, 2], 'CARROT': [1, 2]}, sd_path_collect=6, sd_fert_frac=f))
       for f in (1.0, 0.5)},
    # radial (user): animal feed / care / collect spread over every hand's way out: cap sweep 1 / 2 / 3 on C3f80
    **{f'R1c{k}': (SEC, dict(ARMS_C3F80, sd_animal_cap=k)) for k in (1, 2, 3)},
    # late-season plantings (the leader plants 25-37 wheat on days 26-27): cutoff off / cutoff only where the leader never harvests
    'P1': (SEC, dict(ARMS_C3F80, plant_cutoff={})),
    'P2': (SEC, dict(ARMS_C3F80, cut_mode='leader_harvest')),
    # day-11 isolation of C1's parts (user: fix day 11 first): G0 = fert policy; D1 = G0 + retire + survival late 10;
    # D2 = G0 + idle waters 10; C1 = all three
    'D1': (SEC, dict(MDEC, sd_fert_sell=1, sd_retire=1, sd_hard_late_w=10.0, sd_hard_safe=16)),
    'D2': (SEC, dict(MDEC, sd_fert_sell=1, sd_water_tomorrow=10.0)),
    'D3': (SEC, dict(MDEC, sd_retire=1, sd_hard_late_w=10.0, sd_hard_safe=16, sd_water_tomorrow=10.0)),
    # melons sold as soon as they reach the shed (user: no melon demand builds up), day-11 tests
    'G0s': (SEC, dict(MDEC, sd_fert_sell=1, sell_now=['MELON'])),
    'D1s': (SEC, dict(MDEC, sd_fert_sell=1, sd_retire=1, sd_hard_late_w=10.0, sd_hard_safe=16, sell_now=['MELON'])),
    'C1s': (SEC, dict(MDEC, sd_fert_sell=1, sd_retire=1, sd_hard_late_w=10.0, sd_hard_safe=16, sd_water_tomorrow=10.0, sell_now=['MELON'])),
    # animals (user): feeding charged a fraction of the wheat price / a bonus on fed + cared animals; base G0s, day 11
    **{f'Aw{int(f * 100):02d}': (SEC, dict(MDEC, sd_fert_sell=1, sell_now=['MELON'], sd_wheat_frac=f)) for f in (0.5, 0.25)},
    **{f'Ab{b}': (SEC, dict(MDEC, sd_fert_sell=1, sell_now=['MELON'], sd_feed_bonus=float(b))) for b in (20, 50)},
    'Awb': (SEC, dict(MDEC, sd_fert_sell=1, sell_now=['MELON'], sd_wheat_frac=0.5, sd_feed_bonus=20.0)),
    'B1': (SEC, dict(ARMS_B1)),
    # leave-one-out of B1 on day 11 (which fix costs melon timing / radial routes)
    'B1-fp': (SEC, dict(ARMS_B1, sd_fert_sell=0)),
    'B1-sn': (SEC, dict(ARMS_B1, sell_now=[])),
    'B1-sv': (SEC, dict(ARMS_B1, sd_retire=0, sd_hard_late_w=0.0, sd_hard_safe=20)),
    'B1-cy': (SEC, dict(ARMS_B1, sd_fert_ret=0, sd_collect_floor=0.0, sd_finish_collect=0)),
    'B1-wf': (SEC, dict(ARMS_B1, sd_fert_first=0)),
    'B1-a3': (SEC, dict(ARMS_B1, hp_crops=['MELON'], hp_wheat_min_units=0)),
    'B1-ct': (SEC, dict(ARMS_B1, cut_mode='all')),
    'B1-fb': (SEC, dict(ARMS_B1, sd_feed_bonus=0.0)),
    'B1ni': (SEC, dict(ARMS_B1, sd_water_tomorrow=0.0)),        # B1 without the idle waters
    'B1p': (SEC, dict(ARMS_B1, sd_path_collect=6)),             # B1 + collect on the way out
    # hard-coded melon rule (user): by 8 +10 / unit / hour early, 8-12 -10 / unit / hour late, never after 12
    'B1pM': (SEC, dict(ARMS_B1, sd_path_collect=6, sd_melon_rule=1)),
    # K0 (user design 2026-09-28): B1 recipe + the tiered plan fixed at hour 0 (sd_tier; its own melon rule, sectors by
    # heuristic search, extras, animal work from the melon hands' leftover); the hourly route search is not used
    'K0': (SEC, dict(ARMS_B1, sd_tier=1)),
    'K0a': (SEC, dict(ARMS_B1, sd_tier=1, hire_extra=1, sd_tier_animal_hand=1)),   # + one animal hand
    'G0sM': (SEC, dict(MDEC, sd_fert_sell=1, sell_now=['MELON'], sd_melon_rule=1)),
    # melon morning push vs the new animal values (user: B1p's farmer collects instead of harvesting melons)
    **{f'B1pm{w}': (SEC, dict(ARMS_B1, sd_path_collect=6, sd_hv_pref=dict(HVM, MELON=dict(HVM['MELON'], hour_w=float(w)))))
       for w in (60, 150)},
    **{f'B1pc{c}': (SEC, dict(ARMS_B1, sd_path_collect=6, sd_collect_floor=float(c))) for c in (20, 40)},
    'B1pmc': (SEC, dict(ARMS_B1, sd_path_collect=6, sd_collect_floor=20.0,
                        sd_hv_pref=dict(HVM, MELON=dict(HVM['MELON'], hour_w=150.0)))),
    'W4b': (SEC, dict(ARMS_C3F80, hp_crops=['MELON', 'WHEAT'], hp_wheat_min_units=5, sd_fert_ages={'WHEAT': [2, 2], 'CARROT': [1, 2]})),
    'W3c': (SEC, dict(ARMS_C3F80, hp_crops=['MELON', 'WHEAT'], hp_wheat_min_units=5,
                      sd_hv_pref=dict(HVM, WHEAT={'ages': [[12, 29, 3, 3]], 'bonus': 40.0}))),
    'C2n': (SEC, dict(MDEC, sd_fert_sell=1, sd_retire=1, sd_hard_late_w=10.0, sd_hard_safe=16, sd_water_tomorrow=10.0,
                      sd_fert_ret=1, sd_collect_floor=40.0)),     # the cycle without the wheat / carrot fertilize rule
    'M_decay30': (SEC, dict(MDEC)),               # = M_decay, run to the season end (multi, 19 days)
    'N0_30': (S2, dict(dispatch_search='off')),   # = N0 (the current T), run to the season end
    **{f'G{int(f * 100):03d}': (SEC, dict(MDEC, sd_fert_sell=1, sd_fert_first=1, sd_fert_frac=f)) for f in (1.0, 0.75, 0.5, 0.25)},
    # the same two arms under the shipping build's wall-clock caps (0.75 / 0.6 / 0.8 s; evaluation budgets unchanged)
    'Mship': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                        sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                        sd_hv_pref=HVM_MEL, sd_hp_parity=1, **dict(SHIP, sd_budget0=0.75, sd_budget=0.6, sd_step_cap=0.8))),
    'M_idleship': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=40.0, sd_hop_w=20.0,
                             sd_dv_coins=DVC_M, sd_final_trip=1, sd_water_first=1, sd_coop_pair=2, sd_plan_log=1,
                             sd_hv_pref=HVM_MEL, sd_hp_parity=1, sd_water_tomorrow=40.0, sd_idle_fert=1,
                             **dict(SHIP, sd_budget0=0.75, sd_budget=0.6, sd_step_cap=0.8))),
    'S11a': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_early_animal=1, **SHIP)),      # + early animal
    'S11wh2': (SEC, dict(dispatch_search='active', sd_days=[11, 23], sd_seed_fix=1, sd_sector_w=80.0, sd_hop_w=40.0, **SHIP)),
}


LABEL = {
    'N0': 'N0: current T (mgt_lead.py f8b48ef: melon 8 AM + replant_leader), greedy dispatcher',
    'N11': 'N11: route-search planner on days 11-23 (v1 + survival fallback, deterministic budgets)',
    'N12': 'N12: route-search planner on days 12-23 (the deploy candidate window)',
    'S11f': 'S11f: N11 + seed over-commit repair',
    'S11w': 'S11w: S11f + sectors (home quadrant = spawn quadrant, 40 coins an op outside home, rebalanced at 1/8/14h)',
    'S11h': 'S11h: S11f + contiguity (20 coins per extra step of a hop between job tiles)',
    'S11wh': 'S11wh: S11f + sectors 40 + contiguity 20',
    'S11wh2': 'S11wh2: S11f + sectors 80 + contiguity 40',
    'S11a': 'S11a: S11f + the goose bought before the melon harvest on its coop tile (sd_early_animal)',
    'S11c': 'S11c: S11f + the measured same-day delivery credit (melon 53.8 a unit on days 6-11) + final delivery trip',
    'S11ca': 'S11ca: S11c + sd_early_animal',
    'S11caw': 'S11caw: S11ca + sectors 40 + contiguity 20',
    'S11cf': 'S11cf: S11ca + water before harvesting a one-time crop in its window (the coop-tile melon fix)',
    'S11cfs': 'S11cfs: S11cf + spawn steering (farmer hour-0 stand, hour-0 / hour-1 hire split)',
    'S11cfd': 'S11cfd: S11cf + hires by demand (planned value vs fib wage at hour 0)',
    'S11cfsd': 'S11cfsd: S11cf + spawn steering + hires by demand',
    'S11cg': 'S11cg: S11cf + melon harvest tendency in the planner (early, full) + executor harvest values + coop split from goose',
    'S11cgs': 'S11cgs: S11cg + spawn steering',
    'S11cgd': 'S11cgd: S11cg + hires by demand',
    'S11cgsd': 'S11cgsd: S11cg + spawn steering + hires by demand',
    'S11cb': 'S11cb: S11cf + melon tendency + executor harvest values + the BUILD+animal bundle (one hand: water, harvest, coop, goose, feed, care)',
    'S11cbs': 'S11cbs: S11cb + spawn steering',
    'S11cbd': 'S11cbd: S11cb + hires by demand',
    'S11cbsd': 'S11cbsd: S11cb + spawn steering + hires by demand',
    'M': 'M: sectors 40 + contiguity 20 + melon priority (full yield by 8h, leader window) + same-day melon credit + final trip + water before harvest + coop/goose 2-hour job (goose bought h0, must land by day end)',
    'M_idle': 'M_idle: M + idle fill (a water on a dry plant worth 40, idle hands deliver fertilizer)',
    'M2': 'M2: M + any hand on its empty coop with the goose places it + the coop/goose job due by h19 (then by day end)',
    'M2a': 'M2a: M + any hand on its empty coop with the goose places it',
    **{f'fv{int(f * 100):02d}': f'fv{int(f * 100):02d}: M_decay + fertilize on the first useful day, fertilizer charged at {f:.2f} x its price, days 11-14' for f in (0.0, 0.25, 0.5, 0.75)},
    **{f'hw{w:02d}e{e}': f'hw{w:02d}e{e}: M_decay + retired plants exempt + survival ops cost {w} an hour after h16' + (' + hard jobs eject others' if e else '') for w in (5, 10, 20, 40) for e in (0, 1)},
    **{f'if{w:02d}': f'if{w:02d}: M_decay + idle fill (a water on a dry plant worth {w}, idle hands deliver fertilizer)' for w in (5, 10, 20)},
    'iv2': 'iv2: M_decay + idle fill v2 (idle hands only: same-day delivery, then the nearest dry plant at home)',
    'rt0': 'rt0: M_decay + retired plants get no hard water (reference for the hw sweep)',
    'G0': 'G0: M_decay + leader fertilizer policy (shed stock all sold, no shed pickups, collected fertilizer kept in hand)',
    'C1': 'C1: G0 + survival water late weight 10 after h16 (retired plants exempt) + idle waters worth 10',
    **{f'C2f{f}': f'C2f{f}: C1 + cycle (fertilizer back with the goods, sold) + wheat/carrot fertilize on the first useful day + collect worth >= {f}' for f in (20, 40, 80)},
    **{f'C3f{f}': f'C3f{f}: C2f{f} + collect before leaving an animal tile' for f in (20, 80)},
    'C3n': 'C3n: C2n + collect before leaving an animal tile',
    'W3a': 'W3a: C3f80 + fertilized wheat harvested from age 3 (5 units) and replanted',
    'W3b': 'W3b: C3f80 + every wheat harvested from age 3 (tendency)',
    **{f'X1t{k}': f'X1t{k}: W4a + collect on the way out while carrying < {k} fertilizer' for k in (1, 3, 6)},
    **{f'X2f{int(f * 100):02d}': f'X2f{int(f * 100):02d}: X1t6 + wheat/carrot fertilize charged at {f:.2f} x the fertilizer price' for f in (0.5, 0.25, 0.0)},
    **{f'X3f{int(f * 100):02d}': f'X3f{int(f * 100):02d}: X2 at {f:.2f} + the shed keeps the day fertilize need (trip-start pickups)' for f in (1.0, 0.5)},
    **{f'R1c{k}': f'R1c{k}: C3f80 + radial animals (at most {k} animal jobs a hand, on the way out)' for k in (1, 2, 3)},
    'P1': 'P1: C3f80 + no late-season planting cutoff',
    'P2': 'P2: C3f80 + cutoff only for plantings the leader never harvests',
    'D1': 'D1: M_decay + fertilizer policy + survival late weight 10 (retire exempt)',
    'D2': 'D2: M_decay + fertilizer policy + idle waters 10',
    'D3': 'D3: M_decay + survival late weight 10 + idle waters 10 (no fertilizer policy)',
    'G0s': 'G0s: G0 + melons sold as soon as they reach the shed',
    'D1s': 'D1s: D1 + melons sold as soon as they reach the shed',
    'C1s': 'C1s: C1 + melons sold as soon as they reach the shed',
    **{f'Aw{int(f * 100):02d}': f'Aw{int(f * 100):02d}: G0s + feeding charged {f:.2f} x the wheat price' for f in (0.5, 0.25)},
    **{f'Ab{b}': f'Ab{b}: G0s + {b} coins on every feed / care' for b in (20, 50)},
    'Awb': 'Awb: G0s + feeding at 0.5 x wheat + 20 on every feed / care',
    'B1': 'B1: all fixes (fert policy, melons on arrival, survival water, idle waters, cycle, wheat fert age 1-2 + age-3 harvest, late plantings, feed bonus)',
    'B1ni': 'B1ni: B1 without idle waters',
    'B1-fp': 'B1 without the fertilizer policy',
    'B1-sn': 'B1 without melons sold on arrival',
    'B1-sv': 'B1 without the survival-water weight',
    'B1-cy': 'B1 without the cycle (fert back, collect floor, collect before leaving)',
    'B1-wf': 'B1 without wheat/carrot fertilizing at age 1-2',
    'B1-a3': 'B1 without the age-3 wheat harvest',
    'B1-ct': 'B1 without late plantings',
    'B1-fb': 'B1 without the feed bonus',
    'B1p': 'B1p: B1 + collect on the way out',
    'B1pM': 'B1pM: B1p + hard-coded melon rule (by 8, else by 12 with penalty)',
    'K0': 'K0: B1 + tiered plan fixed at hour 0 (melon hands, sectors by search, extras, animal work)',
    'K0a': 'K0a: K0 + one animal hand',
    'G0sM': 'G0sM: G0s + hard-coded melon rule',
    **{f'B1pm{w}': f'B1pm{w}: B1p + melon later than 8 AM costs {w} an hour' for w in (60, 150)},
    **{f'B1pc{c}': f'B1pc{c}: B1p + collect worth at least {c} (not 80)' for c in (20, 40)},
    'B1pmc': 'B1pmc: B1p + melon 150 an hour after 8 AM + collect floor 20',
    'W4a': 'W4a: W3a + wheat / carrots fertilized at age 1-2 only',
    'W4b': 'W4b: W3a + wheat fertilized at age 2 only (carrots 1-2)',
    'W3c': 'W3c: W3a + age-3 wheat harvest bonus 40',
    'C2n': 'C2n: C1 + cycle (fertilizer back with the goods, sold) + collect worth >= 40, no extra fertilizing',
    'M_decay30': 'M_decay (season end)',
    'N0_30': 'current T (season end)',
    **{f'G{int(f * 100):03d}': f'G{int(f * 100):03d}: G0 + fertilize on the first useful day, fertilizer charged at {f:.2f} x its price' for f in (1.0, 0.75, 0.5, 0.25)},
    'F3': 'F3: F1 + fertilize on the first day it adds units (fertilizer in hand or shed), days 11-14',
    'H1': 'H1: M_decay + survival ops cost 30 an hour after h16 + hard jobs eject the least-value others',
    'M_once2': 'M_once2: M_once + an idle hand takes the nearest job it can start before its holder (limited reassignment)',
    'M_decay14': 'M_decay14: M_decay played days 11-14 (for the fertilizer comparison)',
    'F1': 'F1: M_decay + fertilizer charged at 0 in the maintenance module (fertilize by the extra units), days 11-14',
    'M_once': 'M_once: M_decay + each hand planned once in the morning (48k evals), then only local repairs (job gone, new must-do or job, empty route)',
    'M_decay': 'M_decay: M + the harvest decay bonus 500 (a one-time crop decaying from tomorrow is harvested today), as in S11cg',
    'M2i': 'M2i: M2 + idle fill v2 (idle hands only: same-day delivery, then the nearest dry plant in the home quadrant)',
    'Mship': 'Mship: M under the shipping wall-clock caps 0.75 / 0.6 / 0.8 s',
    'M_idleship': 'M_idleship: M_idle under the shipping wall-clock caps 0.75 / 0.6 / 0.8 s',
    'S11ci': 'S11ci: S11cb + idle fill (a water on a dry plant worth 40, tomorrow labour saved; idle hands deliver fertilizer)',
    'S11cr': 'S11cr: S11ci + radial corridors (40 an op outside the corridor; 20 an inward, 10 a sideways step between job tiles)',
    'S11cr2': 'S11cr2: S11ci + radial corridors x2 (80 / 40 / 20)',
    'S11crr': 'S11crr: S11ci + radial steps only (20 inward, 10 sideways; no corridors)',
}


_MODS = []


def _load_module_rec(path, tag):
    m = _ORIG_LM(path, tag)
    _MODS.append(m)
    return m


_ORIG_LM = X.load_module


def stream_job(args):
    """the viewer's stream of one G1 world: leader tape for t < 264, the arm for 264..311, {} after (xfix_run's stream
    format) -> results/fresh/day12_viz/<arm>_streams/<ep>.json with a one-line label in "arm"."""
    import traceback
    _, game, arm = args
    try:
        del _MODS[:]
        r = X.ledger_play(game, arm, 'stream')
        r['arm'] = LABEL.get(arm, arm)
        cfg = ARMS.get(arm, (None, {}))[1]
        if cfg.get('sd_corr_w') and _MODS:       # the viewer's corridor overlay: each hand's corridor tiles by day
            L_ = (getattr(_MODS[-1], '_S', None) or {}).get('sd') or {}
            r['corridors'] = {d: v for d, v in (L_.get('corridor_log') or {}).items() if d in ('11', '12')}
        if cfg.get('sd_sector_w') and _MODS:     # the viewer's sector overlay: homes by day, rebalancing changes
            L_ = (getattr(_MODS[-1], '_S', None) or {}).get('sd') or {}
            r['sectors'] = {d: v for d, v in (L_.get('sector_log') or {}).items() if d in ('11', '12')}
            r['sector_changes'] = [c for c in (L_.get('sector_changes') or []) if 264 <= c[0] < 312]
        if cfg.get('sd_plan_once') and _MODS:    # plan once: the morning plan steps and every repair [step, unit, reason, tile, key]
            L_ = (getattr(_MODS[-1], '_S', None) or {}).get('sd') or {}
            r['once_steps'] = L_.get('once_steps') or []
            r['repairs'] = [x for x in (L_.get('repairs') or []) if 264 <= x[0] < 312]
        if cfg.get('sd_retire') and _MODS:       # retired plants (tile indices) by day
            L_ = (getattr(_MODS[-1], '_S', None) or {}).get('sd') or {}
            r['retired'] = {d: sorted(v) for d, v in (L_.get('retired_log') or {}).items() if d in ('11', '12')}
        if cfg.get('sd_plan_log') and _MODS:     # the viewer's plan overlay: each hand's planned job tiles on every change
            L_ = (getattr(_MODS[-1], '_S', None) or {}).get('sd') or {}
            r['plan'] = {s_: v for s_, v in (L_.get('plan_log') or {}).items() if 264 <= int(s_) < 312}
        d = ROOT / 'results/fresh/day12_viz' / (arm.lower() + '_streams')
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{game.split(':')[1]}.json").write_text(json.dumps(r, default=str), encoding='utf-8')
        return 'stream', game, arm, (r.get('cash') or [None])[-1], None
    except Exception as exc:
        return 'stream', game, arm, None, f'{type(exc).__name__}: {exc} ' + traceback.format_exc()[-2000:]


def multi_job(args):
    """days 11..11+nd-1 from the leader's exact day-11 morning (LEADER: the tape): both farms' money at every morning
    264..(11+nd)*24, our fertilizer ops by crop, fertilizer sold / held per day, passes; the stream for 264..(11+nd)*24-1
    -> OUT/multi/<arm>/<ep>.json and results/fresh/day12_viz/<arm>_streams/<ep>.json."""
    import copy
    import traceback
    import kaggle_environments as KE
    import lead_g1
    import lead_ledger
    _, game, arm, nd = args
    try:
        D = X.D
        tape = X.tape_of(game)
        seat = tape['seat']
        envbox, box = {}, {}
        orig_make = KE.make

        def mk(*a, **k):
            e = orig_make(*a, **k)
            envbox['env'] = e
            return e
        KE.make = mk
        try:
            if arm == 'LEADER':
                r = lead_ledger.play(game, 'leader')
            else:
                path, cfg = ARMS[arm]

                def loader(_cfg):
                    del _MODS[:]
                    mod = X.load_module(path, 'xfix_' + arm)
                    h = X.Handoff(mod, dict(X.BASE, **cfg), tape, hand=D, stop=(D + nd) * 24)
                    h.record = {}
                    box['h'] = h
                    return h
                lead_g1._load_agent = loader
                r = lead_ledger.play(game, 'ours')
        finally:
            KE.make = orig_make
        env = envbox['env']
        money = {}
        for d in range(D, D + nd + 1):
            fs = env.steps[min(d * 24, len(env.steps) - 1)][0].observation.farms   # day-30 'morning' = the final state
            money[d] = [float(fs[seat]['money']), float(fs[1 - seat]['money'])]
        days = r['days']
        out = dict(game=game, episode=int(game.split(':')[1]), arm=arm, seat=seat, ndays=nd, money=money,
                   fert_ops={d: {k.split(':', 1)[1]: v for k, v in (days[d].get('opk') or {}).items() if k.startswith('FERTILIZE:')}
                             for d in range(D, D + nd)},
                   fert_sold={d: (days[d].get('sold') or {}).get('FERTILIZER', 0) for d in range(D, D + nd)},
                   fert_held={d: (days[d].get('shed_after') or {}).get('FERTILIZER', 0)
                              + (days[d].get('carried_mid') or {}).get('FERTILIZER', 0) for d in range(D, D + nd)},
                   passes={d: days[d].get('passes', 0) for d in range(D, D + nd)},
                   died={d: days[d].get('died', {}) for d in range(D, D + nd)})
        (OUT / 'multi' / arm).mkdir(parents=True, exist_ok=True)
        (OUT / 'multi' / arm / f"{game.split(':')[1]}.json").write_text(json.dumps(out, default=str), encoding='utf-8')
        if arm != 'LEADER':
            cfg = ARMS[arm][1]
            acts = [copy.deepcopy(a) if isinstance(a, dict) and a else {} for a in tape['actions']]
            for t_, a_ in box['h'].record.items():
                if D * 24 <= t_ < (D + nd) * 24:
                    acts[t_] = a_
            for t_ in range((D + nd) * 24, len(acts)):
                acts[t_] = {}
            st_ = dict(game=game, episode=out['episode'], seat=seat, seed=tape['seed'], arm=LABEL.get(arm, arm),
                       cfg=dict(X.BASE, **cfg), agent_path=ARMS[arm][0], first_step=D * 24, last_step=(D + nd) * 24 - 1,
                       actions=acts, mode='multi',
                       note='actions[t] = the leader tape for t < 264, the arm for 264..%d, {} after' % ((D + nd) * 24 - 1),
                       cash=[0.0] * D + [money[d][0] for d in range(D, D + nd + 1)])   # morning cash by day (the viewer's oracle; days < D unchecked)
            L_ = (getattr(box['h'].mod, '_S', None) or {}).get('sd') or {}
            lo, hi = D * 24, (D + nd) * 24
            if cfg.get('sd_sector_w'):
                st_['sectors'] = {d: v for d, v in (L_.get('sector_log') or {}).items() if D <= int(d) < D + nd}
                st_['sector_changes'] = [c for c in (L_.get('sector_changes') or []) if lo <= c[0] < hi]
            if cfg.get('sd_plan_log'):
                st_['plan'] = {s_: v for s_, v in (L_.get('plan_log') or {}).items() if lo <= int(s_) < hi}
            if cfg.get('sd_plan_once'):
                st_['once_steps'] = L_.get('once_steps') or []
                st_['repairs'] = [x for x in (L_.get('repairs') or []) if lo <= x[0] < hi]
            d_ = ROOT / 'results/fresh/day12_viz' / (arm.lower() + '_streams')
            d_.mkdir(parents=True, exist_ok=True)
            (d_ / f"{game.split(':')[1]}.json").write_text(json.dumps(st_, default=str), encoding='utf-8')
        return 'multi', game, arm, money[D + nd][0], None
    except Exception as exc:
        return 'multi', game, arm, None, f'{type(exc).__name__}: {exc} ' + traceback.format_exc()[-2000:]


def run_one(j):
    if j[0] == 'stream':
        return stream_job(j)
    if j[0] == 'multi':
        return multi_job(j)
    del _MODS[:]
    res = X.job(j)
    if j[0] == 'trace' and res[4] is None and _MODS:   # the planner's own counters: time caps, evals, plan ms per step
        try:
            st_ = ((getattr(_MODS[-1], '_S', None) or {}).get('sd') or {}).get('st') or {}
            f = X.OUT / 'trace' / j[2] / f"{j[1].split(':')[1]}.json"
            r = json.loads(f.read_text(encoding='utf-8'))
            r['sd_st'] = {k: st_.get(k) for k in ('steps', 'time_capped', 'evals', 'plan_ms', 'plan_ms_first', 'step_ms',
                                                   'coop_pair', 'coop_wait', 'pair_buy', 'pair_place_now', 'water_first',
                                                   'errors', 'last_error', 'planned_hard_unplanned')}
            r['sd_cfg'] = {k: getattr(_MODS[-1], 'CFG', {}).get(k) for k in ('sd_evals0', 'sd_evals', 'sd_budget0',
                                                                              'sd_budget', 'sd_step_cap')}
            f.write_text(json.dumps(r, default=str), encoding='utf-8')
        except Exception:
            pass
    return res


def setup():
    X.OUT = OUT
    wl = json.loads((ROOT / 'results/fresh/xfix_20260925/worlds42.json').read_text(encoding='utf-8'))
    X.load_worlds = lambda: wl
    X.ARMS.update(ARMS)
    X.load_module = _load_module_rec


def main():
    argv = sys.argv[1:]
    mode, arms = argv[0], argv[1].split(',')
    sel, spec, workers = None, 'all', int(os.environ.get('LP_WORKERS', 4))
    extra_streams = []
    i = 2
    while i < len(argv):
        if argv[i] == '--games':
            sel = argv[i + 1].split(','); i += 2
        elif argv[i] == '--worlds':
            spec = argv[i + 1]; i += 2
        elif argv[i] == '--streams':
            extra_streams = argv[i + 1].split(','); i += 2
        elif argv[i] == '--workers':
            workers = int(argv[i + 1]); i += 2
        else:
            i += 1
    setup()
    import lead_g1
    if mode == 'full':
        games = list(lead_g1.GAMES) if spec in ('g1', 'all') else []
        if spec in ('sem4', 'all'):
            w = json.loads((ROOT / 'results/fresh/lead_sem4_20260925/worlds.json').read_text(encoding='utf-8'))['worlds']
            games += [x['game'] for x in w if x['game'] not in games]
    else:
        games = [w['game'] for w in X.load_worlds()['worlds']]
    if sel:
        games = [g for g in games if g.split(':')[1] in sel]
    if mode == 'stream':
        jobs = [('stream', g, a) for a in arms if a != 'LEADER' for g in lead_g1.GAMES]
    elif mode == 'both':                                 # day-11 traces (42 worlds) + the viewer streams (12 G1 worlds)
        jobs = [('trace', g, a) for a in arms for g in games]
        jobs += [('stream', g, a) for a in arms if a != 'LEADER' for g in lead_g1.GAMES]
    else:
        jobs = [(mode, g, a) for a in arms for g in games]
    jobs += [('stream', g, a) for a in extra_streams for g in lead_g1.GAMES]    # streams only (e.g. sector overlays)
    print(len(jobs), 'jobs', flush=True)
    t0 = time.time()
    errs = 0
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for f in as_completed([pool.submit(run_one, j) for j in jobs]):
            m, g, a, fin, err = f.result()
            errs += bool(err)
            print(time.strftime('%H:%M:%S'), m, a, g, ('FAILED ' + err) if err else f'{fin}', flush=True)
    print(f'completed {len(jobs)} games in {time.time() - t0:.0f}s, errors (FAILED) {errs}', flush=True)


if __name__ == '__main__':
    main()
