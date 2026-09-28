"""mgt_lead: follow a leader's per-day BOARD plan with our own closed-loop execution.
mgt_lead_sector (2026-09-25, built by scripts/search_dispatch_build.py from agents/mgt_lead.py (git f8b48ef) as of 2026-09-25 f8b48ef, sha256 3707fa44efcf37e1, snapshot
results/fresh/search_dispatch_20260925/source/mgt_lead_3707fa44.py): the same agent plus a rolling-horizon route-search dispatcher behind CFG "dispatch_search" (default
"off" = the source's decisions: every hook is guarded). See the SEARCH DISPATCH BLOCK.


Research agent (2026-09-24). Not a replay of the leader's actions: every step reads the live
observation, derives the jobs still needed on each tile (structural diff toward the target's
boards + maintenance of our own live assets + harvests), and dispatches farmer/hands greedily
(nearest task, with shed pickups for wheat / fertilizer / animals). Market: sell following the
target's cumulative per-day sold units (capped by our stock), buy what today's jobs need when
cash allows (re-tried every hour), hire the target's day hand count.

Target: set with configure(semantics_dict) (a data/leader_semantics/<team>/<ep>.json.gz object).
NOTE (data quirk): in those files market.*, animals.bought and labour.hires_arrived of index d
belong to actual day d+1 (index 0 = days 0 and 1); boards, plantings, maintenance and
hands_present are correctly dated.

2026-09-25 port (E1): options merged from agents/mgt_lead_deploy.py (tie_value and hand_stock ON by default as in
the deploy; maint_goal, hire_demand, cap_fix, retire_visit, reach_guard / reach_first, commit, pick_plan OFF) and
from agents/mgt_lead_exact.py (thread sem4: exact_removals, OFF by default; 48 four-quadrant leader worlds T-T0
-289, CI -1,120..+542). With tie_value 0, hand_stock 0 every decision is the previous mgt_lead (sha256 a1cd70e6).

2026-09-25 xfix port (thread xfix; results/fresh/xfix_20260925, scripts/xfix_*.py): tile-exact fixes found by tracing
T's day 11 from the leader's exact morning state, each behind its own CFG key, all OFF by default except the confirmed pair
(harvest_policy leader_tendency on melons + replant_leader: default ON = the new T baseline; with both off the file
is the previous mgt_lead.py, sha256 e0849ddd, to the dollar). CONFIRMED in full games (52 leader worlds, own cash vs T, clean worlds):
harvest_policy "leader_tendency" with hp_crops ["MELON"] (+816, t-CI +94..+1,538) and, with replant_leader,
+2,264 (+1,063..+3,465; margin +4,145). Measured and REJECTED (kept off): the wheat / carrot tendency, fert_follow,
fert_gross, fert_shadow (flat), fert_release, idle_deliver, deliver_credit, upkeep_scale, busy_upkeep_pen,
lead_harvest_bonus, place_bonus_days 29. pf_log = planting-fate log (logging only).
"""
import time
from collections import Counter

CROPS = {
    "WHEAT":      {"seed": 10, "first": 2, "maxday": 4, "interval": 0, "max": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first": 2, "maxday": 3, "interval": 0, "max": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first": 8, "maxday": 8, "interval": 1, "max": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first": 10, "maxday": 10, "interval": 2, "max": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first": 10, "maxday": 12, "interval": 0, "max": 6, "ongoing": False},
}
ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP", "first": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW": {"cost": 400, "structure": "PASTURE", "first": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]
LAND_ORDER = ["NE", "SW", "SE"]
LAND_PRICES = [1000, 2000, 4000]
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
LABEL_CROP = {"WH": "WHEAT", "CA": "CARROT", "TO": "TOMATO", "ST": "STRAWBERRY", "ME": "MELON"}
CROP_LABEL = {v: k for k, v in LABEL_CROP.items()}
LATE = {"WHEAT": 1, "CARROT": 1, "MELON": 2, "TOMATO": 3, "STRAWBERRY": 3}
MOVES = {(0, -1): "NORTH", (0, 1): "SOUTH", (1, 0): "EAST", (-1, 0): "WEST"}

CFG = {
    "smart_water": True,     # engine-derived skips: water only when survival / yield needs it
    "hire_mode": "target",   # "target" = the target's hands that day
    "hire_extra": 0,
    "sell_mode": "cum",      # cumulative target sold units per product
    "zone_penalty": 0,
    "prio_mode": "new",
    "late_hour": 15,
    "sticky": False,
    "fert_ongoing": True,
    "deliver_value": 300,
    "window_urgent": ["MELON", "WHEAT", "CARROT"],
    "wheat_days": 1,
    "late": {"STRAWBERRY": 6, "TOMATO": 5, "MELON": 3},  # catch-up days for missed plantings
    "dispatch": "greedy",    # "greedy" (per-step matching) | "route" (sweep plan per day; 0.506, experimental)
    "two_opt": True,
    "travel_w": 1.4,
    "reach_w": 4.0,
    "insert_by_finish": True,
    "pick_k": 4,
    "prio3": True,
    "hires_first": True,
    "fert_prio": 1,
    "pick_cap": {"WHEAT": 3, "FERTILIZER": 4},
    "deliver_value_late": 1000,
    "hires_at_front": True,
    "place_bonus": 8,
    "place_bonus_days": 0,
    "window_p0": ["MELON"],
    "fert_reserve_soon": True,
    "lazy_fetch": False,
    "harvest_before_build": True,
    "mj_fertilize": "auto",   # sem_maintenance fertilize: "auto" (when the extra units pay at market price) | True | {crop: ...}
    "seed_fund": 0,           # 1: at hours 0-2 sell stock beyond the quota (most valuable first, above the reserves) in the same step to fund the seeds of today's plant jobs (the leader spends to the last coin)
    "harvest_source": "ours", # "leader" = a one-time crop (wheat / carrot) is also harvested on the day the leader harvests that cohort's tile (full value, before full yield if the leader does); our required harvests and survival net stay
    "early_onetime": False,   # optional harvest of wheat / carrot from one day before full yield (cycle research)
    "spawn_allot": False,
    "maint_source": "ours",   # ablation: "leader" = the leader's per-tile per-day WATER/FEED/CARE/FERTILIZE
    "sched_maint": True,      # (default on since 2026-09-24: S1f 0.862/0.854/0.833 vs A29 0.792/0.780/0.785) scheduler: maintenance jobs (value, deadline) from scripts/fragments/sem_maintenance.py
    "surv_reserve": True,     # (default on since R16: 0.874/0.866/0.844 vs 0.862/0.854/0.833) from surv_hour: survival jobs (dies / escapes tonight) get nearest-first routes, only their op
    "surv_hour": 16,
    "surv_harvest": False,
    "atrisk_bonus": 0,        # greedy cost bonus (steps) for a one-time crop at/after full yield with a harvest pending (decays tomorrow)
    "cut_mode": "all",        # "all" = plant_cutoff applies to every late planting; "leader_harvest" = only to plantings the leader itself never harvests before the end (T follows the leader's exact plan)
    "plant_cutoff": {"STRAWBERRY": 13, "TOMATO": 18, "MELON": 19, "WHEAT": 25, "CARROT": 26},   # last planting day with a full harvest before the end (min_maintenance); later plantings incl. catch-ups are skipped (2026-09-25: full panel +336, G1 +0.007)    # survival routes also take one-time crops at/after full-yield age (missed harvests decay)
    "sched_dispatch": False,  # scheduler: dispatch by value density among jobs finishable before their deadline
    "sched_hire": False,      # scheduler: hire the n-th hand while the value only it adds exceeds fib(n)
    "p1_min_value": 0.0,      # maintenance ops worth <= this (coins) count as priority 2 (deferred after late_hour)
    "deliver_units": 10,      # a unit carrying this many products walks them to the shed for same-day sale
    "release_stale_d": False, # drop a delivery assignment once nothing deliverable is carried (1 idle step per DROP)
    "cap_fix": 0,             # no-extra-trip shed-cap fix: hours cap_fix_hour..23 units on / next to a shed deposit everything deliverable (wheat above the next-day herd need included) and the same step sells what the midnight projection cannot hold; each morning the feed-wheat keep is capped to what tonight leaves room for
    "cap_fix_hour": 21,
    "cap_harvest_est": 40,    # expected units still to be harvested into hands during a day (morning wheat cap)
    "hire_demand": "off",     # "off" = target hands; "all" = smallest k (morning search, own greedy simulation) completing every production-affecting job reachable at k_max; "marginal" = add hands while the marginal completed value covers the k-th fib wage
    "dem_kmax": 14,
    "dem_rehire_value": 200,  # later hire only if new production-affecting jobs worth this appeared (re-searched)
    "reach_guard": 0,         # 1 = a task that cannot be finished today (hour + travel + ops > 24) is not assigned (no walking toward it)
    "reach_first": 0,         # 1 = reach_guard on the FIRST op only (hour + travel + 1 > 24): partial work on multi-op tasks (feed before care / harvest) stays allowed
    "commit": 0,              # 1 = the current target keeps a bonus = steps already walked toward it (<= commit_cap): no churn
    "commit_cap": 6,
    "pick_plan": 0,           # 1 = one pickup per item type sized to the current task + the open tasks this unit is nearest to (<= pick_plan_max); no opportunistic pickups
    "pick_plan_max": 6,
    "retire_visit": 0.0,      # labour charge (coins) per visit to an animal in the maintenance solve; an animal whose remaining production at today's price no longer covers feed + visits is retired (the leaders retire cows / sheep at ~0.2x base price with 2-4 productions left)
    "maint_goal": "value",    # "max_production" = every job that changes production is required (inputs free in the maintenance solve, fertilize whenever it raises units, priority by units not coins); only no-production jobs may be skipped
    "tie_value": 1,           # equal-cost tasks go to the tile worth most today (thread Q, 2026-09-25: deploy full panel +1,420 vs ff1, CI +513..+2,328; deploy G1 0.902)
    "hand_stock": 1,          # 1: wheat picked only for the unit's current task (+ hs_buffer), no opportunistic wheat pickups; from hs_drop_hour a unit AT the shed places wheat above its task need (no extra trips). default 1 (2026-09-25: deploy full panel +983 vs the tie_value default, CI +334..+1,559)
    "hs_buffer": 1,
    "hs_drop_hour": 18,
    "cap_deliver": 0,         # 1: on a projected midnight overflow (cap_hour.., same projection as cap_guard) the units carrying the most products (wheat / fertilizer included) deliver them; cap_guard then sells the excess
    "cap_guard": 0,           # 1: midnight shed-cap guard from cap_hour: shed + carried + cap_rate x hours left - sells <= 100 - cap_margin (wheat above the reserve first, then cheapest)
    "cap_hour": 16,
    "cap_rate": 2.5,          # expected items still coming into the units' hands per remaining hour
    "cap_margin": 3,
    "fert_hold": 0,           # 1: collected fertilizer is not delivered while fertilize jobs remain today (applied in the field); 2: never delivered mid-day
    "helper_split": False,    # a unit left free by the greedy joins a held animal tile and takes its last op
    "helper_crops": False,    # helper split also on ongoing crops (strawberry / tomato: HARVEST is independent of water)
    "idle_trace": None,       # research: directory for the idle-pass / dropped-job trace (one jsonl per game)
    "mj_every": 3,            # re-solve maintenance jobs at most every N hours when the asset set changed
    "mj_collect": True,       # value the daily fertilizer an animal yields (keeps old animals fed longer)
    "opt_harvest_frac": 0.15, # value of an optional (early) harvest = held units x price x this (cash now)
    "plan_value": 400.0,      # value of a plan job (plant / build / place pipeline) for the scheduler
    "travel_est": 2.0,
    "sched_cost": "skip",     # "skip" (value picks today's skips, distance routes) | "prize" | "density"
    "step_value": 40.0,       # coins one unit-step is worth (prize cost)
    "skip_slack": 1.0,        # skip dispatch: fraction of the remaining unit-hours the kept jobs may fill        # hiring model: travel steps per tile job
    "hire_idle": 0.0,         # hiring model: extra coins a hand must earn (idle risk)
    "maint_safety": False,    # ablation B2: with maint_source="leader", still save plants/animals that die tonight
    "hands_d29_fix": True,    # A29 (default on since 2026-09-24): hire the day-28 count on day 29 (the corpus records 0 hands on day 29 because the day-end hook never runs on the last day)
    "sell_source": "leader",  # ablation: "shed" = mgt_lead_deploy's sell-as-it-reaches-the-shed rule
    "hire_source": "ours",    # ablation: "leader_steps" = the leader's HIRE orders at the leader's steps
    "route_once": True,
    "add_radius": 3,
    "late_p1": 0,
    "steal_radius": 5,
    "keep_bonus": 1.5,
    "exact_removals": False,  # sem4: issue the leader's DIGs of live plants on our tile for that cohort (48 four-quadrant leader worlds: T-T0 -289, CI -1,120..+542; default off)
    "rm_late": 1,             # sem4: a removal stays open on the leader's removal day and this many days after
    # ---- SEARCH DISPATCH (mgt_lead_search / mgt_lpv_search only; scripts/search_dispatch_block.py) ---------
    "dispatch_search": "off", # "off" = the source's decisions | "shadow" = greedy acts, the planner runs and logs | "active" = planned units follow the plan
    "sd_days": None,          # [lo, hi] day window (inclusive) of the planner; None = every day
    "sd_budget0": 0.9,        # s: time cap of the day's first plan (hour 0; warm start of the day)
    "sd_budget": 0.3,         # s: time cap of a later step's re-plan
    "sd_evals0": 60000,       # route evaluations of the day's first plan (deterministic work budget)
    "sd_evals": 8000,         # route evaluations of a later step
    "sd_step_cap": 0.95,      # s: the planner stops when the whole step reaches this
    "sd_bank_stop": 20.0,     # s of the 60 s overage bank used -> planner off (greedy) for the rest of the game
    "sd_lambda": 0.5,         # coins per planned unit-step (tie-breaker toward short routes)
    "sd_late_frac": 0.5,      # share of an op's value kept when it is done after its deadline
    "sd_switch": 40.0,        # coins per step already walked toward a job the unit is taken off (the executor's step_value)
    "sd_vmin": 2.0,           # minimum value of an op (value-0 jobs save later visits)
    "sd_hard": 5000.0,        # bonus on survival ops (plant dies / animal escapes tonight): hard constraints
    "sd_cap": 100,            # midnight shed cap ...
    "sd_cap_margin": 0,       # ... minus this margin
    "sd_cap_w": 20.0,         # coins per projected midnight-load unit above the cap
    "sd_plan_jobs": 1,        # predicted jobs: plan plantings whose seeds are bought this step (release next hour)
    "sd_pairs": 1,            # predicted jobs: the deploy's same-day replant after a wheat / carrot harvest (order pair)
    "sd_replant_value": 400.0,
    "sd_k_units": 4,          # candidate routes per insertion (nearest) + the 2 nearest idle units
    "sd_rr_max": 8,           # ruin size (jobs)
    "sd_rr_noise": 30.0,      # regret noise of the recreate step (coins)
    "sd_rr_stall": 25,        # ruin-and-recreate attempts without improvement before the step's search stops
    "sd_seed": 7,
    "sd_hs_drop": 1,          # a planned unit at its pickup shed tile from hs_drop_hour places wheat above its route's need
    "sd_idle": "pass",        # a planned unit with an empty route: "pass" (deliver what it carries, else wait) | "greedy"
    "sd_deliv": 1,            # model the executor's delivery trigger inside the routes
    "sd_finish_tile": 1,      # active: a delivery started this step waits while a planned unit is on its current planned tile
    "sd_dv_frac": {},         # v2: product -> share of the current price credited per unit delivered by sd_dv_hour (sold the same day)
    "sd_dv_coins": {},        # v2: product -> coins per such unit (a number, or [[first_day, coins], ...])
    "sd_dv_hour": 22,         # v2: last DROP / PLACE hour that sells the same day (unit actions come before the market)
    "sd_dv_quota": 1,         # v2: with sell_source "leader" only products whose sell quota of the day has room get the credit
    "sd_hourly_profile": None,   # {product: [24 cumulative shares]} (user 2026-09-26: follow DSM's market PATTERN): the sell quota at hour h of day d = the target's sales before day d + share[h] x its sales on day d (not its whole day at hour 1); catch-up when behind, never ahead
    "sd_wheat_reserve_today": 0, # 1: the wheat reserve is today's remaining feeds only (not + n_animals x wheat_days): wheat sells on the target's pace, tomorrow's feed is bought at hour 0 (sd_tier_wheat)
    "sd_maint_floor": {},     # {product: floor} (abandonment research R2, docs/abandonment_research_20260926.md; KPT1 lost its sheep herd on day 24 when an evening wool sale left the dawn quote at 1): the maintenance module values these animal products at max(quote, floor) until sd_maint_floor_last, so one thin dawn quote cannot abandon a herd with productions left (R2: milk 60, wool 100, egg 45)
    "sd_maint_floor_last": 26,  # last day the floors apply (after it: the quote, the final cycle)
    "sd_books_sell": [],      # products (user 2026-09-26: "switch to DSM sell plans"): sold on the leader's own sell plan for this world (results/fresh/threads_20260928/dsm_sales/<ep>.json): at every step up to the leader's cumulative units through that step, capped by our shed, first in the order list (the leader's position); no sale on delivery; at hour 21 anything above the leader's sales of the next 12 steps is sold (our surplus does not fill the shed overnight)
    "sd_books_cap": 0,        # 1 (KBK2 overflow days: the plan's held goods took shed room, the midnight dump deleted wheat): from hour 21 on, when shed + everything carried + what the routes still harvest today would not fit the shed (100 - sd_tier_dump_buffer), the held sd_books_sell goods are sold, cheapest first, down to what fits
    "sd_maint_floor_trail": 0,  # KWE (2026-09-26, world 112604454: the wool floor 100 kept 10 sheep fully fed / cared on days 21-26 while our wool sold at 1-33 and every hourly quote was <= 98; sheep feeds 158 vs DSM 104 = 54 wheat, care 137 vs 100): H >= 1 = each floor is capped by the trailing statistic (sd_maint_floor_stat) of that product's hourly quotes over the last H hours, so one thin dawn quote after a high evening stays protected (R2) but a glut that lasts all day is priced as one
    "sd_glut_stop": {},       # {product: price} (DSM on 112604454: full sheep service days 11-17, then from the wool collapse on day 18 a trickle of 1-5 feeds / cares a day for the rest of the season; KC5's trailing floor followed the quotes back up and served all 10 sheep again on days 24-25): once the product's trailing sd_glut_hours mean quote falls below the price, it is glutted for the rest of the season and its animals get no optional CARE and no optional FEED on non-production days (keep-alive and production-day feeds stay)
    "sd_glut_hours": 48,
    "sd_maint_floor_stat": "mean",  # "mean" | "max" of the trailing quotes
    "sd_books_batch": 0,      # > 0 (DSM's wool glut on 112604454: never more than 8 units a step, never at $1; KC3 dumped surplus wool at h21 down to $1, where a sale earns 1 and adds no market stock, so the rival's price rises): the surplus / capacity sells of sd_books_sell products are at most this many units a step, and none while the quote is <= sd_books_minpx
    "sd_books_front": 0.0,    # X in (0, 1] (user 2026-09-28, KB115L decomposition: the learned pace alone costs -8.1k a world
    # vs DSM's books - it is a 40-game average that sells ~50% of wool by h8, DSM sells a production day's wool by h8 in
    # lots ahead of the rival's h3-h9 sales, and the rival then sells the same units into the price we lowered; KB115L wool
    # -7.4k / -4.8k, milk -1.4k / -2.6k, all on the rival's side): with sd_books_source "pace", a product the rival sold
    # on the previous 3 days (inferred from the market, mean >= sd_books_front_min units a day) sells our shed in even lots
    # from hour 1 so that it is gone by the hour the rival has usually sold X of its day's units (past that hour: by its
    # last usual selling hour; after it: the pace); never slower than the pace. 0 = off. PARKED (2026-09-28): KB115LF50
    # vs KB115L on 33 panel worlds paired -937 a world (95% -1,707..-147), 10 better / 23 worse, wins 27 -> 25; it helped
    # the two worlds it was built on (+0.5k / +3.1k) - mechanism: front-loading sells into our own price impact in most
    # worlds; beating the rival's sale needs the rival's per-day volume and our arrival timing, not an hour average
    "sd_books_front_min": 1.0,
    "sd_books_minpx": 5,
    "sd_books_walk": 0,       # 1 (KC4 still sold 14 wool at $1: near the floor a unit lowers the wool price by ~6, so a batch of 8 from quote 24 ends at 1; DSM never sold wool at $1): every sd_books_sell sell stops before the engine price of the next unit (market stock + units already sold this step) would be <= sd_books_minpx
    "sd_books_source": "dsm", # "pace" (DSM-free, user 2026-09-27: KB99 hazard -1,913 - a share of our shed each hour sells slower than DSM when our goods arrive late, rival windfall +1.4k): DSM's learned PACE (dsm_sell_pace.py: share of the day's goods - dawn stock + arrivals - sold by each hour, by product / phase / hour / rival habit), we sell up to pace x (our shed + our sales today) - our sales today; "dsm": the leader's recorded sell plan (dsm_sales); "hazard" (DSM-free, user 2026-09-27: we will not have DSM's plans): DSM's learned selling hazard x our shed stock, by product / season phase / hour / the rival's habit (its units at this hour and in the next 4 on the previous 3 days, inferred from the market: stock change - our sales + shop consumption); tables results/fresh/threads_20260928/dsm_sell_hazard2.json (fallback dsm_sell_hazard.json), 40 recordings
    "sd_books_cap_free": 0,   # 1 (KB0 on 40 worlds: on overflow nights the shed holds wool 7.0 / milk 4.7 the price floor keeps unsold, and the dump deletes the strawberries / wheat carried in; leaving glut goods on the animals cost -0.9k: less supply lets the rival sell dearer): the capacity sells of the plan (sd_books_cap, from hour 21 when tonight would overflow) ignore the batch cap and the price floor - room for carried goods worth more beats the price of a glut unit, and a sale above $1 still lowers the rival's price
    "sd_books_h0_slots": 0,   # N > 0 (KB4 on 112604454: every hour-0 list is 10 HIREs, so the 10-order cap drops the plan's hour-0 sells - DSM sells strawberry 11 at hour 0 on days 17/19/20 ahead of the rival's hour-0 dump, we sell an hour later behind it; DSM itself hires 8 at hour 0 and the rest at hour 1 and keeps its sells first): up to N of the plan's hour-0 sells keep their slots, the day plan moves as many hour-0 hires to hour 1 (they act from hour 2) and the hour-0 market trims the hires to the plan's count
    "sd_books_h0_lot": 0,   # 1 (KB7 on 112604454: the hour-0 slot flushed the whole backlog - strawberry 31 / 35 on days 22 / 23 where DSM sells 6-11, milk 17 on day 21 where DSM sells none - into the price before the hour-0 town tick): at hour 0 the plan sells at most DSM's own hour-0 lot of that step; the backlog waits for hour 1, after the tick
    "sd_books_even": [],      # products (user 2026-09-27: "dump strawberries in nearly equal lumps in tick 1,5,... if they arrive midnight"; item trace on 112604454: catch-up lumps of 21-31 strawberries at hour 1 walk our price down): when we are behind DSM's cumulative sales, the backlog is sold in equal lots over the day's remaining post-tick hours (1/5/9/13/17/21); other hours sell only DSM's own lot of that step
    "sd_books_sur_h": 12,     # the 21:00 surplus rule sells what exceeds DSM's sales over the next this-many steps (item trace: DSM holds day-26/27 strawberries to day 28 22:00 / day 29 05:00 at 97-110, we sold them at day 27 21:00 at 62 -> 22)
    "sd_books_cap_order": 0,  # 1 (item trace: the room-making sells on overflow nights picked strawberries - the cheapest books product - at glut prices; wheat / carrots / tomatoes are not books products and were never considered): room is made with every product in the shed, cheapest first; products in sd_books_cap_protect only when room is still short, in batches and above the price floor
    "sd_books_cap_protect": ["STRAWBERRY"],
    "sd_pattern_tick": [],    # products (user 2026-09-26: imitate DSM's selling; engine-isolated test +2.7k on world 112604454): sold only at hours 1 / 5 / 9 / 13 / 17 / 21 (the first market after a town consumption tick; the engine clears the market BEFORE the town consumes at hours 0 / 4 / 8 / 12 / 16 / 20) on the sd_hourly_profile quota; their deliveries are no longer sold on arrival and the overflow guards leave them alone at the tick hours themselves (hour 20). Needs sd_hourly_profile for these products
    "sd_wheat_pick_now": 0,   # 1 (2026-09-26, KQ plant deaths): the market's wheat reserve for the tiered plan's pickups also counts the WHEAT the executor picks up in this same step. Those pick items are marked done when the command is issued, but the wheat is still in the observed shed and the engine runs unit actions before the market, so without this the sale takes the wheat the later pickups (the hour-1 hires, acting from hour 2) need: they wait for a buy-back and their routes end an hour late (last WATER unfinished, plants die; FEED skipped)
    "sd_h0_front": [],        # (user 2026-09-26) products whose shed stock may be sold at hour 0 FIRST in the order list (the engine processes both players' orders position by position, so a sell behind the hires comes after the rival's hour-0 sales); the largest-value pile >= sd_h0_front_min, at most sd_h0_front_n orders; one hour-0 hire moves to hour 1 only when the 10 slots are full
    "sd_h0_front_min": 5,
    "sd_h0_front_n": 1,
    "sd_h0_front_pos": 0,
    "sd_h0_front_gain": 0.0,  # > 0 (user): instead of the largest pile, sell at hour 0 every listed product whose stock x edge >= this (the cost of one delayed hire, ~70 a day); free slots (fewer than 10 hour-0 orders) need only a positive gain. edge = price at the start of hour 0 minus at the start of hour 1, learned in the game on days the product was not sold at hour 0 (EMA 0.2), starting from sd_h0_front_edge0
    "sd_h0_front_edge0": {"MILK": 21.0, "STRAWBERRY": 7.5, "WOOL": 7.0},     # 0: first in the list; 1 (control): after the hires and the wheat buy
    "sd_evening_sell": [],    # products (e.g. ["WOOL", "MILK", "STRAWBERRY"]) of which a share of the morning shed stock is held back and sold at sd_evening_hour..23 (the rival sells at hour 0: supply that reaches the market the evening before lowers its price; leaders sell 36-68% of the night's carry after hour 11)
    "sd_evening_frac": 0.5,
    "sd_evening_hour": 20,
    "sd_final_sell_all": 0,   # 1 (user 2026-09-26): at the last executed step (718) sell every product for the shed stock PLUS everything carried (units act before the market, so goods dropped at 718 sell in the same step; over-ordering is harmless)
    "sd_final_trip": 0,       # v2: routes end with the walk of their products to the shed (credited when in time)
    "sd_hard_late_w": 0.0,    # v2: coins per hour a hard (survival) op is done after sd_hard_safe
    "sd_hard_safe": 20,
    "sd_hard_all": 0,         # v2: every unit is a candidate for a hard job
    "sd_hard_eject": 0,       # v2: a hard job nobody can take is inserted by dropping the least-value non-hard jobs
    "sd_cap_all": 0,          # v3: the midnight shed-load term also counts products staying in the shed overnight
    "sd_mr": 0,               # v3: maintenance job values at marginal revenue (price - slope x our units still to sell)
    "sd_mr_floor": 0.1,       # v3: ... floored at this share of the price
    "sd_surv_fb": None,       # v5: from this hour the executor's survival routes keep their units / tiles (None = off)
    "sd_sector_w": 0.0,       # sectors: coins per op outside the unit's home quadrant (0 = off)
    "sd_sector_hours": [1, 8, 14],   # sectors: hours of the home rebalancing
    "sd_sector_ratio": 2.0,
    "sd_water_first": 0,      # a one-time crop's harvest task waters first when the water still adds a unit today
    "sd_hire_demand": 0,      # hour 0: hire the k in [want - 6, want] with the best planned value net of the fib wages
    "sd_hire_evals": 3000,    # route evaluations per tried k
    "sd_spawn_steer": 0,      # hour 0: farmer stand + hour-0 / hour-1 hire split so the spawn quadrants match the work
    "sd_hp_parity": 0,        # the executor's harvest_policy values (melon harvest in window, melon window water) in the plan
    "sd_split_place": 0,      # a BUILD + PLACE plan part = structure job + placement job (successor)
    "sd_build_value": 150.0,  # value of the structure job when split
    "sd_bundle_build": 0,     # every plan BUILD + animal = one job: clear -> BUILD -> PLACE -> FEED -> CARE (never an empty structure)
    "sd_bundle_value": "auto",  # the bundle's value: "auto" = a day of the animal (2 x product price / interval + fertilizer)
    "sd_water_tomorrow": 0.0, # coins: a water on a dry plant is worth at least this (tomorrow's labour saved); 0 = off
    "sd_idle_fert": 0,        # an idle planned unit delivers its fertilizer too
    "sd_corr_w": 0.0,         # radial corridors: coins per op outside the unit's corridor (0 = off)
    "sd_rad_in": 0.0,         # radial: coins per inward step between job tiles
    "sd_rad_side": 0.0,       # radial: coins per sideways step between job tiles
    "sd_coop_pair": 0,        # a plan BUILD + animal = one job [DIG,] BUILD, PLACE (one hand, animal from the trip start); FEED / CARE upkeep; 2 = + must complete by the day end (hard, any hour)
    "sd_coop_by": 24,         # the coop pair's PLACE: hard deadline hour while ahead (24 = the day end)
    "sd_coop_place": 0,       # hook 3: any unit on its empty coop / pasture with the animal in hand places it
    "sd_idle_v2": 0,          # idle fill v2: empty-route units only, no values: same-day delivery, then nearest dry plant at home
    "sd_plan_once": 0,        # plan each unit's route once (first step from h1 with all hires on board), then local repairs only
    "sd_once_evals": 48000,   # evaluations for that one morning plan
    "sd_once_steal": 0,       # plan once, repair (c): an empty-route unit takes the nearest job it can start earlier than its holder
    "sd_fert_first": 0,       # the maintenance jobs gain FERTILIZE on the first day it adds units (fertilizer in hand / shed)
    "sd_fert_frac": None,     # applying fertilizer is charged at this fraction of its price (None = the module's own)
    "sd_animal_cap": 0,       # radial (user): at most this many animal jobs (feed / care / collect) in one hand's route (0 = off)
    "sd_animal_cap_w": 200.0, # coins per animal job above the cap
    "sd_animal_late_w": 20.0, # coins per animal job placed after the route's first patch job (animals on the way out)
    "sd_path_collect": 0,     # >0: a planned unit carrying less fertilizer than this steps onto an animal with fertilizer on a shortest path to its next job (collect on the way out)
    "sd_finish_collect": 0,   # 1: a unit about to walk off (or pass on) an animal tile whose fertilizer is still available collects it first (one visit per tile)
    "sd_fert_ret": 0,         # 1 (user cycle): a unit delivering goods at the shed DROPs everything (its unused fertilizer goes back and is sold) when its remaining route has no FERTILIZE (and no FEED while it carries wheat) and it carries no animal
    "sd_fert_ages": None,     # {crop: [age_lo, age_hi]}: the first-useful-day FERTILIZE rule only at these ages (e.g. wheat [1, 2])
    "sd_fert_first_crops": None,   # list of crops the first-useful-day FERTILIZE rule applies to (None = all)
    "sd_collect_floor": 0.0,  # a COLLECT_FERTILIZER op is worth at least this many coins (fertilizer is worth more on crops than its sale price late)
    "sd_collect_at_floor": 0,  # 1 (2026-09-28, KB160 day 27 on 112602061: the fertilizer quote hit $1 on day 26, the maintenance
    # module emits COLLECT_FERTILIZER only while the quote is > 1, so the day had no collect op at all, 16 fertilizes had no
    # supply and the hands idled 74 actions; KB115L: 2/40 worlds, days 24-27, 140 unplanned fertilizes): the tier plan
    # gets a collect op on every pen with fertilizer available that has none, worth max(quote, sd_collect_floor).
    # 2: only as many as the day's FERTILIZE ops (value > 0) lacking a collect, pens nearest them first (mode 1 on
    # 112592389 added 24 collects on day 28, when a fertilizer has almost no use left: -2,383; +8,640 / +6,678 where the
    # bug starved days 24-27)
    "sd_wheat_frac": None,    # feeding is charged this fraction of the wheat price in the maintenance values (None = full)
    "sd_feed_bonus": 0.0,     # coins added to every FEED / CARE op of a live animal (user: bonus on animals fed / cared)
    "sell_now": [],           # products sold as soon as they reach the shed, whatever the leader's quota (e.g. MELON)
    "sd_tier": 0,             # 1 (user, 2026-09-28): tiered plan fixed at hour 0 (melon hands / sectors by heuristic search / extras / animal work)
    "sd_tier_budget": 10.0,   # safety cap (seconds) of one sector search at hour 0
    "sd_tier_iters": 6000,    # sector search iterations (deterministic)
    "sd_tier_offsets": 8,     # sweep start: angular offsets tried (each routed once with the best rotation by proxy)
    "sd_tier_pair_top": 0,    # >0: collect pairing only for this many best bundle positions and 4 animals (speed)
    "sd_tier_hop_w": 1.0,     # sector cost: hours per extra step between consecutive stops of a patch (contiguity)
    "sd_tier_coll_w": 2.0,    # sector cost: hours credited per fertilizer collectable on the outbound leg (capped by the patch's fertilize tiles)
    "sd_tier_prio_w": 2.0,    # sector cost weight of an hour of mandatory work on a melon hand after its drop
    "sd_tier_t0": 2.0,        # annealing start temperature (hours)
    "sd_tier_rate": 1.0,      # extras: minimum coins per added hour
    "sd_tier_rate_c": 20.0,   # extras on the outbound hands (phase C): minimum coins per added hour
    "sd_tier_wait_max": 4,    # executor: hours a hand waits for a tile / seed / animal before skipping the op
    "sd_tier_animal_hand": 0, # the last k hires are animal hands (animal work only)
    "sd_tier_fert_supply": 0, # 1: at hour 0 the first-useful-day fertilize jobs count today's collections (one per animal), not only what hands carry
    "sd_tier_pair_own": 0,    # 1: a collect -> fertilize pair is scored on the fertilize's own value (the collect is worth its sale anyway)
    "sd_tier_fert_skip_harv": 0,  # 1: no fertilize on a tile whose one-time crop is harvested today or which is replanted / rebuilt today
    "sd_tier_fert_exact": 0,  # 1: fertilize value = the engine's units from one FERTILIZE today (first useful day only) x price - charge
    "sd_tier_relief": 0,      # 1: a hand with spare time takes a tile from a busier hand so that hand can do an unplanned extra
    "sd_tier_relief_passes": 2,
    "sd_tier_relief_minv": 0.0,
    "sd_tier_fill_near": 0,
    "sd_tier_rot_all": 0,     # 1: the sweep start routes every rotation of arcs to hands (no distance proxy; slower)
    "sd_tier_swap_oropt": 0,  # 1: a swap move re-optimizes both routes (slower)
    "sd_tier_spawn_passes": 2,  # plan / spawn-check passes at hour 0
    "sd_tier_farmer_hold": 0, # 1: a farmer on / next to the shed at hour 0 holds that hour (the hires' spawn is then known: one pass)   # >0: extras fill tries only this many hands nearest to each extra (speed)   # relief only for unplanned extras worth at least this (speed)
    "sd_tier_relief_slack": 2, # hours a hand must have free at the end of its day to take a tile
    "sd_tier_straw_water": None,  # value of an extra (not survival) WATER on a strawberry (None: the job list's own)
    "sd_tier_wheat": 0,       # 1: the day's feeds are bought at hour 0 when the shed lacks the wheat (first order); pickups wait for it
    "sd_tier_deliver": 0,     # 1: when the projected midnight dump will not fit the shed, the hands with the most valuable loads end their day at the shed (DROP, sold at once)
    "sd_tier_dump_buffer": 5,
    "sd_tier_access_keep": 0, # 1 (bug fix, 2026-09-26, KDF2 day 12 on 112604454): the PLACE after a HARVEST on a shed tile (sd_tier_access_drop) keeps the wheat this route still needs for its remaining FEEDs; it used to place ALL wheat in the hand (feed wheat included, sold at once), so the later FEEDs were skipped and a goose and a cow escaped
    "sd_tier_dump_defer": 0,  # 1 (KC2a on 112604454: hands carried 105-127 units into the midnight dump on days 20/24/26/28 while the planner projected 109-128 and found no delivery that fits; the excess was deleted): when the projected dump still exceeds 100 - sd_tier_dump_buffer after the deliveries, harvests whose tile can hold the units until tomorrow without losing production (animal: tonight's production fits max_held; ongoing crop: yield + tonight's production <= max_yield and not in its last day of life; one-time crop: not decaying by tomorrow; no melons, no replant on the tile) are left for tomorrow, cheapest units first
    "sd_tier_dump_defer_cap": 0,   # > 0: the deferral works down to this projected midnight load (default 100 - sd_tier_dump_buffer); lower leaves room for goods the seller holds in the shed
    "sd_tier_dump_refill": 0, # 1 (KC5 on 112604454: idle 200 unit-hours vs DSM 7, 167 of them at h20-23, freed when sd_tier_dump_defer took tail harvests out after the extras fill): after the deliveries / deferral, one more fill pass with the extras left over, without harvests (they would refill the dump)
    "sd_tier_dump_refill_rate": None,   # value per added hour the refill pass needs (None: sd_tier_rate); the hours it fills are idle otherwise (goose CARE ~73 with 2 h of walking scored 24 < 70 and was left out; DSM cares its geese 80 of 90 goose-days)
    "sd_tier_rebalance": 0,   # 1 (user 2026-09-27: "for waste of work post-20 o'clock could we reassign tiles from busy sectors to non-busy"): the refill pass (sd_tier_dump_refill) may give a leftover extra on a tile another hand owns to any hand with room (tile ownership and the nearest-hands filter off), so the hands that end at 20-23 take the busy sectors' undone waterings / fertilizing / care
    "sd_keep_alive_guard": 0,  # 1 (KS5a on 112604454: the maintenance module abandoned the whole sheep flock on days 23-24 when the trailing wool floor followed a glut down; R2 of docs/abandonment_research_20260926.md): an animal unfed yesterday with >= 2 production nights left (up to night 28) always gets a mandatory keep-alive FEED, whatever the module decided
    "sd_tier_dawn_learned_max": 4,   # sd_tier_dawn_shape "learned": at most this many dawn trips a day (DSM: 0-4, 1.8 on average)
    # sd_tier_dawn_shape "learned2" (user 2026-09-28, KB115L: the learned rule makes 2-3 trips / 8-12 units on 112602061's
    # synchronized wool mornings d21/24/27 where DSM makes 6-7 / 26-31, and DSM dawn trips were +4.2k there with DSM books):
    # "learned" plus, in any phase, sheep pens one tile off with 4 <= wool < max_held when >= sd_tier_dawn_sync_n sheep pens
    # within 2 tiles hold >= 4 wool at dawn (DSM days 18+: 1-off rate 1-4% with 0-3 such pens, 33% with 6-7, 68% with 8-9),
    # sheep pens two tiles off when >= sd_tier_dawn_sync_n2 (DSM 18%; paired into the trip of an adjacent 1-off pen, as DSM's
    # 2-pen trips; no trip of its own), and up to sd_tier_dawn_learned_max2 trips on those mornings (DSM 5.9 pens a day, max 8)
    "sd_tier_dawn_sync_n": 6,
    "sd_tier_dawn_sync_n2": 8,
    "sd_tier_dawn_learned_max2": 8,
    "sd_keep_alive_guard_min": 2,   # productions left (nights up to 28) from which the keep-alive guard holds; 1 = every animal that still produces once more (KH5 lost 1.2 animals a world before day 27 vs 0.3 with DSM's data: the module abandons flocks in their last cycles when the wool price path dips, and our wool keeps the rival's price down)
    "sd_tier_dayret_shape": None,   # "file" (user 2026-09-27: improve with DSM knowledge; the dawn SHAPE copy was worth +2.0k where copying only the COUNT of returns was worth nothing): DSM's daytime returns of this world (results/fresh/threads_20260928/dsm_dayret/<ep>.json: hand, drop hour, the tiles it harvested the goods on); each return goes to our outbound hand whose mandatory route holds the most of those tiles, as a shed stop (DELIVER) right after the last of them, kept when it adds no lateness; never skipped by the executor
    "sd_tier_dayret_relocate": 0,   # > 0: a DSM return that would make its hand late may move up to this many of the hand's tail stops (after the return) to the outbound hand where each fits cheapest without lateness (user: reassign tiles from busy sectors to non-busy)
    "sd_defer_shed": 0,       # > 0 (KB0 on 40 worlds: on 219 overflow nights the shed already held wool 7.0 / milk 4.7 units - our surplus over DSM's plan that the price floor keeps unsold - vs DSM's 0.9 / 1.3; DSM keeps its glut wool ON the sheep): at planning, a product whose shed stock is at least this many units has its animal harvests left on the animals when the tile can hold them without losing production (sd_tier_dump_defer's check)
    "sd_harvest_follow_dsm": [],   # crops or animals (SHEEP / COW / GOOSE: same rule on the pens; KB2: 46% of DSM's daytime returns found no match because 30% of our strawberry harvests fall on another day than DSM's, same 44 tiles): harvest a tile of these crops on the days DSM harvested it (the target's harvested tiles per day); on other days its harvest waits when the plant can hold the units without losing production
    "sd_wheat_d3": 0,  # 1 (user 2026-09-27: DSM harvests wheat at age 3 - PW . FW WH, 5 units - and at age 4 only when the
    # day-3 harvest + replant cannot fit - PW . FW W WH, 6 units; KB118 copying his age-4 days cost the extra waters' labour):
    # a wheat harvest before its last full day is not mandatory; where DSM plants wheat on the tile within
    # sd_wheat_d3_ahead days (same-type replant on our timing) the day-3 harvest + replant is an optional bundle worth
    # sd_wheat_d3_v wheat prices, merged into the stop of the (then mandatory) day-3 water; without a replant the
    # harvest waits for the last full day (mandatory then)
    "sd_wheat_d3_v": 1.0,
    "sd_evening_wheat_surplus": 0,  # 1 (user 2026-09-28: the day-17 hand plan overflowed with 15 wheat held in the shed while 25
    # came home in the hands - tomorrow needs ~23; KB155 (wheat_days 0) over-sold all day and rebought 40-52 wheat; an
    # evening round trip costs ~0 a unit: sold 38.0-40.0, rebought next morning 37.6-39.0): from sd_ews_hour, only when the
    # projected midnight load (shed + hands + the routes' remaining harvests / collects - fertilizes - this step's sales)
    # exceeds 100 - sd_tier_dump_buffer, sell shed wheat up to that excess and never below tomorrow's feeds (animals x
    # wheat_days) net of the wheat coming home. PARKED as a safe add-on (KB158 = KB115 + keep 0: 112604454 identical to KB115,
    # 112602061 -122 own, midnight deletions 3 -> 1; with the day-17 hand plan v1: deletions 18 -> 3, next morning ~+300,
    # days 17-19 sales ~+700; keep 1.0 sold only 5 of the 15 shed wheat - animals x 1 overstates the ~23-31 feeds a day)
    "sd_ews_hour": 21,
    "sd_ews_keep": 1.0,  # share of tomorrow's feeds (net of the wheat coming home) kept in the shed; 0 = when overflowing, sell
    # shed wheat up to the excess (the hour-0 wheat buy covers the morning at ~ the evening price)
    "sd_wheat_net": 0,  # 1 (user 2026-09-28, midnight audit of 112602061: DSM empties the shed every evening - 0-3 units before
    # the dump - and collects 29.5 fertilizer a day vs our 19.2; the planner's midnight room subtracted a whole day of feed
    # wheat (100 - animals - 5, ~65) while the hands' loads already carry the ~25 harvested wheat that feeds tomorrow):
    # _tier_deliver's room = 100 - max(0, animals x wheat_days - wheat the routes bring home) - sd_tier_dump_buffer
    "sd_collect_make_room": 0,  # 1 (KB146-148: freeing midnight room raised no collects - 90 of ~103 unplaced collects a world
    # sit on pens a route already visits, the route packed to 24 by earlier phases): after the fills, an unplaced collect
    # joins the visit of a route that stops at its pen, dropping that route's cheapest optional ops worth less than the
    # collect (supply and lateness kept); extra collects within the projected midnight room
    "sd_collect_market": 0,  # 1: a COLLECT_FERTILIZER op is worth the fertilizer's market price (not the module's shadow price,
    # which collapses late in the season, nor the 80 floor); sd_collect_floor is ignored
    "sd_pen_sweep": 0,  # 1 (user 2026-09-28, hand plans of days 17 / 22: one hand per pen doing its whole service, straight
    # sweeps from the spawn tiles, crops as route tails: +14 ops on 25 fewer steps in the engine): replaces the mandatory
    # search and the fills for the outbound / post segments by a constructive plan over TILE SERVICE UNITS (a tile's
    # mandatory ops + its optional ops worth >= sd_pen_sweep_vmin): equal-work angular sectors (several start angles),
    # hands matched to sectors by spawn tile, nearest-neighbour order, trimmed to the day (lateness / supply by _tier_eval),
    # leftover mandatory units inserted with room made by dropping the cheapest optional ops, then local search (relocate,
    # swap, 2-opt, insert). The delivery / midnight-load pass (_tier_deliver) runs after it as usual. PARKED (KB140-144, 2
    # worlds, vs KB115: margin -6.2k..-16.5k a world; vmin 16 / 60 / 150 all worse): no fertilizer supply planning - the
    # sector routes holding the outer crops pass few pens and are packed with (over-valued) cares / feeds, so the pairing
    # move finds no room: fertilizes 195 -> 34-100 on 112602061, none at all from day 23; a higher vmin also drops the
    # wheat fertilizes themselves. The hand plans worked because each route's pens supplied its own crop tails' fertilizes
    # (+ 3-5 shed fertilizers). A v2 must build collect -> fertilize chains first
    "sd_pen_sweep_vmin": 16.0,
    "sd_pen_sweep_iters": 3000,
    "sd_polish": 0,  # N > 0 (user 2026-09-28: "teach how you manually plan to the planner"; offline scripts/proc_planner.py
    # optimize on the KB115 / KB158 routes of two worlds, days 12-27, with the planner's drops / deliveries kept: +87 / +83
    # a day on the engine-true scorer, from collects, care and fertilize put into hours freed by fewer steps and dropped
    # zero-value waters; the day-17 engine check KB160 matched the scorer the next morning, +199): after every fill,
    # carry and delivery pass, N iterations of hill climbing over the finished routes (relocate / swap a whole stop, reverse
    # a run of stops, add an unplaced optional WATER / FERTILIZE / CARE / FEED / COLLECT_FERTILIZER, drop one), on
    # engine-true values: a window water bonus x price, a FERTILIZED ongoing crop's production-day water 1 unit, a water
    # whose skip makes tomorrow's survival water a must + sd_polish_water_c, fertilize = units gained x price - the
    # fertilizer quote, collect = the quote, care = 1 unit when the animal is fed today (fed already, a mandatory feed, or a
    # feed on the same route) and a later production is ahead, feed = bank x price on a production night (an unfed animal
    # still produces 1) + sd_polish_water_c when skipping it makes tomorrow's feed a must; lateness / supply as _tier_eval, minus sd_polish_step_w per route hour, and the
    # midnight load at most the delivery pass's headroom above the plan's. Stops with dawn legs, deliveries, drops,
    # in-place drops, placements, builds and copy returns stay where they are; harvests / plantings are never dropped
    "sd_polish_water_c": 10.0,
    "sd_polish_step_w": 0.2,
    "sd_polish_seed": 1,
    "sd_polish_xch": 0.0,  # > 0: share of iterations spent on the EXCHANGE move (an unplaced op into a stop the route already
    # makes, the best of up to 6 lower-value optional ops of that route out); ltp1: routes are full to 24, so a lone add is
    # late and a lone drop loses value - 1.8 collects / 4.4 cares added a world while DSM collects 79 / cares 33 more
    "sd_polish_final": 0,  # 1: the polish runs once a day on the plan the hour-0 passes keep (the core may run up to 5 times
    # for the spawn agreement; with the routes' first stops fixed the result is the same, the discarded passes are skipped)
    "sd_manual_plan": None,  # research (user 2026-09-28: validate hand plans in the engine): path of a JSON {episode: {day:
    # {"routes": [{"u", "fpick", "stops": [[x, y, [OP, ...]], ...]}]}}}; on that world and day each planned unit's route is
    # replaced by the hand route (ops taken from the day's catalogue with their values / mandatory flags; PICKUP = a
    # mid-route shed pickup of wheat for the feeds after it; DROP = drop at the shed tile); declared fertilizer pickups
    # are allowed and reserved that day. Every other day is the normal plan
    "sd_water_useless_zero": 0,  # 1 (user 2026-09-27: KB115 waters wheat at age 1 9.0 times a world vs DSM 2.5, from the 10-coin
    # water floor): an OPTIONAL water on a wheat / carrot plant before its window (age < (max_yield_day + 1) // 2) that is
    # not needed for survival (not dry yesterday) adds nothing and is dropped
    "sd_keepalive_wheat": 0,  # 1 (user 2026-09-27: a keep-alive water is worth the wheat it would waste plus one action to dig
    # the dead plant, not +5000): a wheat SURVIVAL water (dry yesterday, not watered, not harvested / replaced today) is
    # optional, worth (units the plant holds after today's water) x wheat price + sd_labor_price; the planting-day water
    # stays mandatory with its plant
    "sd_labor_price": 20.0,   # coins an action (user: wheat earns ~22 an action, ~16 an hour with one-hour visits)
    "sd_anim_value_exact": 0,  # 1 (user: then bring the animal prices down; KB115 plans value a sheep care 234 where wool sells
    # at 93, a cow care 144-209 against milk 86-92): optional CARE / FEED REPLACED by the engine rule of _tier_anim_value
    # (CARE = one product unit when a production night is ahead, else 0; optional FEED = bank x price on a production day
    # + half a unit when a production is ahead); keep-alive / survival feeds stay mandatory
    "sd_tier_fert_use": 0,  # 1 (user 2026-09-27: F optional but valued; KB115 on 112602061: 39 of 143 age-2 wheat fertilizes,
    # worth 42-78, unplaced - 11 on full routes whose earlier collect left a fertilizer in hand: fertilizes are offered in
    # phase C, collects arrive in D / E, the fertilize is not offered again and the fertilizer is dumped and sold): after the
    # fills, each route's carried fertilizer (fpick + collects - fertilizes so far) is spent on unplaced FERTILIZE ops of its
    # own later stops that already water the tile; a full route makes room by dropping its cheapest optional op worth less
    # than the fertilize (never on that tile, never a collect / fertilize), keeping lateness and supply
    "sd_fert_bonus": 0.0,  # coins added to a FERTILIZE's value (sd_tier_fert_exact) for the crops in sd_fert_bonus_crops
    "sd_fert_bonus_crops": ["WHEAT"],
    "sd_wheat_fert_mand": 0,  # 1 (user 2026-09-27: F matters more than harvest timing - a 13-day loop gives 20 units fertilized vs
    # 12 unfertilized on either cycle; unfertilized wheat is not worth growing): the age-2 FERTILIZE of every wheat plant
    # is mandatory (KB115 on 112602061: 39 of 143 were offered to the fills, values 42-78, and never placed); the route
    # evaluation supplies a mandatory fertilize its own collects do not cover by a shed pickup at the route start, the
    # finished routes carry those pickups (within the shed's hour-0 stock) and the market keeps today's and tomorrow's
    # wheat fertilizer in the shed
    "sd_wheat_h3_opt": 0,  # 1 (user 2026-09-27: stop the day-3 harvest being mandatory, more wiggle for the planner): a wheat
    # harvest before its last full day, on a tile with no replant / build of DSM's today, is optional (tier 3, worth
    # sd_wheat_h3_frac x units x wheat price) together with the water that precedes it (mandatory only for survival);
    # the last full day (age 4) and the last two days of the season stay mandatory; replants stay on DSM's days
    "sd_wheat_h3_frac": 0.5,
    "sd_wheat_h3_wv": 1.0,  # the optional day-3 water's value: this x its units x wheat price (KB123-125 at 1.0: the W+H bundle
    # ~166 coins outbid the day-2 fertilizes, 118 -> 102; a day-3 harvest gains nothing over a day-4 one, 5 units either way)
    "sd_wheat_d3_ahead": 2,
    "sd_follow_defer_exact": 0,   # 1: sd_harvest_follow_dsm holds a one-time crop until its last full day (KB116 on 112602061: the
    # default defer test never let an age-3 wheat wait for DSM's age-4 harvest: 52 cohorts harvested a day early, 5 units vs 6)
    "sd_harvest_follow_keep": 0,   # 1 (KB9, 40 worlds: we sell wool 9-15 units behind DSM at the rival's sales from day 18; sheep harvest days match DSM on 16.4 pen-days a world, 15.1 DSM-only / 16.5 ours-only; on 112604454 day 17 the dump deferral removed the 3 pens DSM harvested): harvests added or kept by sd_harvest_follow_dsm are exempt from the dump deferral
    "sd_maint_follow_dsm": [],   # ops (FEED / CARE / WATER / FERTILIZE; KB17 on 112604454: idle 182 -> 106 unit-hours changed nothing, the freed hours went to walking and low-value waters; DSM does +32 fertilizes, +38 cares, +32 collects and -38 feeds with the same hands, geese cared 85 vs our 43 a world): on the tiles DSM did the op today (semantics maintenance lists, tile-exact board) our optional op becomes mandatory; a missing FEED / CARE / WATER is added (FERTILIZE only promoted: it needs fertilizer in hand)
    "sd_maint_follow_drop": [],  # ops of sd_maint_follow_dsm whose optional instances are dropped on tiles DSM did not service today (frees the labor DSM does not spend; keep-alive and feed-bank feeds are added later and stay)
    "sd_maint_follow_kinds": [],  # animals / crops the maintenance follow applies to (empty: all; KB20 dropped sheep care on DSM's glut days: wool made -0.6k and the rival's wool windfall +0.7k)
    "sd_tier_dump_fix": 0,    # 1 (2026-09-26, case world 112604454: hands carried 124-159 units into the midnight dump while the shed was empty): the executor skips a planned end-of-day DROP only when the PROJECTED midnight load (shed + carried + the units the routes still harvest today) fits, not the load at that hour
    "sd_tier_copy_returns": 0,  # 1 (user 2026-09-26: copy how many hands go back to the shed to drop): the plan holds at least as many daytime shed deliveries as the leader made that day at hour >= 5 (results/fresh/threads_20260928/dsm_returns/<ep>.json), best load value per added hour, extras at a route end trimmed if needed
    "sd_tier_copy_returns_from": 11,   # first day it applies
    "sd_tier_copy_returns_end": 0,    # >0 (KDF2 trace: copied drops left the hour-1 hires no slack, their last waterings went unfinished): a copied delivery only where the route still ends by this hour, and the executor never skips a copied delivery (the drop check cancelled them after the plan had made room)
    "sd_tier_deliver_check": 0,   # 1: a planned delivery is skipped when shed + everything carried already fits at that hour
    "sd_tier_deliver_skip": 0,  # 1 (user 2026-09-27: "on these heavy nights dump waste thousands of coins while a trip back home only costs a few waterings... make a few hands skip their nonmandatory jobs and go home by 23 to make drops"; KB54 112592389 days 26 / 27: projected 121 / 136 carried, zero deliveries planned - every route ran to 24 and only trailing extras could be trimmed - 41 units deleted): when no delivery fits and the projected carried load exceeds 100 - sd_tier_dump_buffer, a hand drops its cheapest optional jobs anywhere in the route until a DROP at the shed fits the day; kept when the goods it saves from deletion (min(its load, the excess) x average price) exceed the jobs given up
    "sd_tier_deliver_skip_max": 12,  # optional jobs one hand may give up
    "sd_tier_deliver_skip_min": 10,  # go-home only when the excess still projected AFTER the harvest deferral is at least this many units (KB63 fired on 4.3 world-days a world before the deferral, KB54 loses goods on 2.3)
    "sd_tier_deliver_skip_trips": 2,  # drops a hand may make (end of day or mid-route, user: two trips instead of one)
    "sd_tier_deliver_skip_collects": 0,  # 1 (KB64 112592389 day 27: 47 optional jobs, 28 of them collects, were off limits, so only one hand could go home): optional collects may be given up too (the route check still rejects a trial that leaves a fertilize without fertilizer)
    "sd_tier_deliver_keep": None, # products a delivery does not sell at once (e.g. ["MILK"]: dearer the next morning) # units kept free in the shed at midnight beyond tomorrow's feed wheat (one per animal)
    "sd_tier_coll_cap": 0,    # >0: collects per hand; one more only when it is on the hand's way (no extra walking)
    # ---- animal thread (2026-09-28): all default OFF (= K5b)
    "sd_tier_log_v": 0,       # 1: the day summary logs every planned op as [op, mandatory, tier, value] (diagnosis only)
    "sd_tier_anim_c": 0,      # 1: the animal FEED / CARE bundles join the outbound extras pool (tier C, by value per hour)
    "sd_tier_anim_c_minv": 0.0,   # ... only bundles worth at least this (coins)
    "sd_tier_anim_c_mult": 1.0,   # ... their value multiplied by this in that pool
    "sd_tier_anim_mand_minv": None,  # FEED / CARE of a live animal become mandatory (tier B) when their joint value >= this
    "sd_tier_pen_bundle": 0,  # 1 (user 2026-09-26, learned from DSM: feed + care + collect in one visit on 36% of its pen visits vs our 7%): on every live animal the COLLECT (fertilizer waiting), the CARE (a later production in the season can realise it) and the FEED (care in the bundle, or tonight's production cashes a bank) join the keep-alive feed / due harvest as ONE mandatory stop, so the sector search gives the pen to one hand; the collected fertilizer then supplies that hand's fertilizes
    "sd_tier_pen_bundle_hmin": 0,   # > 0: the pen's harvest joins the stop when it holds >= this many units (else the cap rule)
    "sd_tier_pen_bundle_collect": 1,   # 0: the COLLECT stays out of the pen stop (free for the fertilize pairing; KB1 lost 4.3 fertilizes a day with it in)
    "sd_tier_prio_straw": 0,  # 1 (user 2026-09-26: strawberry "melon mode"): one hour-0 hire (not the farmer, no melon duty) first harvests the strawberry tiles holding >= sd_tier_prio_straw_min units (or due), watering them in the same visit, best units x price per added hour while its drop at the shed stays by sd_tier_prio_straw_by; then a normal post segment
    "sd_tier_prio_straw_min": 2,  # DSM's mean units per strawberry harvest (1.95)
    "sd_tier_prio_straw_by": 12,  # DSM delivers the same day 62% of strawberries harvested at hours 0-7, 13% at 12-15
    "sd_tier_srun": 0,        # 1 (user 2026-09-27: "bring back strawberry in close proximity. So one labor with following priorities: hard deadline 22, bring back as much as possible, then a bonus on getting back early and bonus on getting extra work done"; DSM brings 54 strawberries a world home by day vs our 8, its returns ~3 tiles each dropped at hour ~16): one hour-0 hire runs the strawberry harvests first and DELIVERs them at the shed - (1) its drop by sd_tier_srun_by and no op late, (2) most strawberry units (cheapest insertion, units per added hour incl. the walk back), (3) earliest drop for that set (reordering), (4) the tiles' WATER in the same visit, ties to visits carrying a mandatory op; then a normal post segment
    "sd_tier_srun_by": 22,    # the run's hard deadline: DELIVER at the shed by this hour
    "sd_tier_srun_min": 1,    # strawberry tiles holding >= this many units (or with a due harvest) are candidates
    "sd_tier_srun_radius": None,  # candidates within this many steps of the nearest shed tile (None: any)
    "sd_tier_srun_passes": 2,  # improvement passes (reorder for an earlier drop, swap for more units)
    "sd_tier_sclu": 0,        # 1 (user 2026-09-27: "we find a cluster of strawberries of at least 4 or 6, assign a hand and direct path to harvest and come back, doing extra work along the path"; "radius constraints applies ... mainly distance between the strawberry cluster"; KB28 whole-day runner -993: +121 moves crossing the map, the sectors lost collects / cares; DSM's returns ~3 tiles within 2 of each other): clusters of harvestable strawberry tiles all within sd_tier_sclu_r of each other holding >= sd_tier_sclu_min units; per cluster one hour-0 hire (not the farmer, not in DSM's dawn trips today) walks shed -> cluster (best order) -> shed and DELIVERs by sd_tier_sclu_by, doing the ops of tiles on its shortest-path legs (no detour); then its normal post segment
    "sd_tier_sclu_min": 4,    # units a cluster must hold
    "sd_tier_sclu_r": 2,      # max Manhattan distance between any two tiles of a cluster
    "sd_tier_sclu_max": 2,    # clusters (hands) a day at most
    "sd_tier_sclu_by": 22,    # hard deadline of the DELIVER
    "sd_tier_sclu_extra": 1,  # 1: ops on the legs' shortest-path tiles join the trip (water, care, feed, collect, harvest)
    "sd_tier_sclu_extra_h": 2,   # extra work may delay the drop by at most this many hours past the cluster-only drop (user: early return ranks above extra work)
    "sd_tier_sclu_fert": 0,   # 1 (8-world demo KB31: strawberry made -7.7 a world - the trip took the cluster tiles' HARVEST / WATER, their lone FERTILIZE stayed with the sectors and went unplanned: 29.4 unfertilized production nights vs 21.6): the trip picks up fertilizer at the shed and fertilizes its cluster tiles in the same visit
    "sd_tier_sclu_dmax": None,  # cluster tiles at most this many steps from the nearest shed tile (DSM: mean 3.9, farthest 4.7)
    "sd_tier_sclu_day_min": 0,  # a trip only when today's ready strawberry units reach this (DSM returns on batch days: 21.9 harvested vs 9.3)
    "sd_tier_sclu_sector_d": None,  # user: "if the distance is short enough we can also make the path to the cluster in the sector of this hand": clusters whose farthest tile is within this distance take all path work that fits by the deadline (no extra-hours cap)
    "sd_tier_sclu_outfert": 0,  # 1 (user): extra labor on the outbound and a safe shed stock: pick up more fertilizer and do the other hands' FERTILIZE jobs on the outbound leg's shortest-path tiles
    "sd_tier_sclu_outfert_h": 3,  # hours the outbound fertilizing may add to the drop
    "sd_tier_sclu_fert_keep": 0,  # fertilizer left in the shed (the pickups take at most the hour-0 stock minus this)
    "sd_tier_sclu_sell_cap": 0,  # 1 (KB34 lag at the rival's strawberry sales went NEGATIVE on days 24-27, -1.3..-6.1: selling the trip's strawberries on arrival ran us ahead of DSM's schedule into lower prices, own -363): the sale on arrival stops at DSM's cumulative sales through the end of the day
    "sd_tier_sclu_need_min": None,  # a trip only when DSM's cumulative strawberry sales through today's end minus ours and minus our shed stock is at least this many units (the trips then target the days we fall behind: 16-23)
    "sd_tier_fert_carry": 0,  # 1 (user 2026-09-27: "if shed has good headroom, normal hands could pick up more fertilizer during the outbound if they have free steps at the end, and also we can look back and apply more during their day. So that excess end up in shed during evening dump, and more wheat is fertilized"; DSM fertilizes 72.6 strawberries / 110.6 wheat a world vs our 59.3 / 106.0, fertilizer comes only from paired pen collects): after the fills, hands starting at the shed take a fertilizer pickup and the day's unplanned useful FERTILIZE extras are inserted into their routes (no added lateness); the pickups take at most the shed's hour-0 stock
    "sd_tier_fert_carry_spare": 0,  # spare fertilizer per carrying hand when the projected midnight dump has that much headroom (returns at the dump)
    "sd_tier_fert_carry_min": 0,  # hands whose planned route ends by hour 23 carry this many shed fertilizer even with no planned insertion (KB12 on 112604454: 150 of 170 idle unit-hours fall at hours 21-23, away from the shed, when the shed holds no fertilizer - it is sold during the day; the pickup at the outbound feeds sd_tier_idle_fert at the day's end)
    "sd_tier_idle_fert": 0,   # 1 (user: hands with free steps at the end pick up shed fertilizer and fertilize more, the excess returns at the evening dump; KB37 found the PLANNED routes full - 153 of 227 end at 24, the rest at 22-23 - the idle hours (182 unit-hours on 112604454) appear in execution): a hand whose plan is done fertilizes the nearest plant where one FERTILIZE still adds units (_tier_fert_gain), reachable before hour 23; without fertilizer it first picks up at the shed as many as the reachable targets, the shed stock and the midnight headroom allow
    "sd_tier_idle_fert_max": 4,  # fertilizer an idle hand picks up at most
    "sd_tier_idle_work": 0,   # 1 (2026-09-28, hand-plan lesson "fill the route tails"; hour budget on 10 worlds: a hand-day works
    # 12.24 h vs DSM's 13.09 and idles 0.78 h after its last job vs 0.03 - about 40 hand-hours a world, while DSM collects 79
    # more fertilizers, cares 33 more geese and waters wheat 26 more times): a hand whose plan is done walks to the best job on
    # the live board by value / (walk + 1) that it can finish by hour 23 and no other hand's remaining plan does: CARE on an
    # animal fed today with a production ahead (a unit), COLLECT_FERTILIZER (the quote, within the midnight room), WATER (a
    # window bonus x price, a fertilized ongoing crop's production-day unit, else sd_tier_idle_work_wc when skipping it makes
    # tomorrow's water a must); targets are claimed so idle hands do not collide
    "sd_tier_idle_work_wc": 10.0,
    "sd_tier_idle_work_minv": 5.0,
    "sd_tier_fert_opp": 0,    # 1 (KB40 on 112604454: 36 hands carried 67 shed fertilizer, 2 were used - the idle hours fall at hour 23 with no time to reach a target): a hand carrying fertilizer beyond its own remaining plan fertilizes the plant it stands on (stops and the tiles it walks across) when one FERTILIZE still adds units, no plan fertilizes it today, and its remaining plan still ends by hour 23 with the extra hour(s); then WATERs it when not watered and no plan waters it today
    "sd_tier_fert_shed": 0,   # 1 (user: "the rule to fertilize and pick up for regular hands"; KB37/40/41 added fertilizes after the fills, when the routes were already filled to hour 24 with low-value extras - 2 to 6 a season): a FERTILIZE extra a hand has no fertilizer for may be supplied by a shed pickup at the start of its route (besides the paired pen collect), inside the normal fill, competing on value; the pickups share a day budget = the shed's hour-0 fertilizer minus sd_tier_sclu_fert_keep and the trips' pickups
    "sd_tier_fert_merge": 0,  # 1 (user 2026-09-27: "getting fertilizer at turn beginning... pick up fertilizer from shed such that they use that extra spare hour to fertilize"; DSM picks up 28 fertilizer a world at the turn start, we 0; 68 of our hand-days end idle, 33.5 of them picked up nothing): after planning, a hand starting on a shed tile with a spare hour picks up shed fertilizer at the start and FERTILIZEs the plants it already stops at to WATER (not yet watered today; the fertilize goes first, so a one-time crop's water in its window gives +2, a strawberry's production night its second unit), when gain x price beats the fertilizer's own price; the pickups share the shed's hour-0 stock
    "sd_tier_early_deliver": [],  # products (STRAWBERRY / WOOL / MILK; user: bring them in early "drawn from the budget pool of spare hand-hours"; KB70 strawberry trips: strawberry margin +622 but other production -800 - a trip takes a hand's day): after planning, a hand that already harvests such products and has spare time inserts ONE delivery to the shed at the best point after those harvests (units per added hour), only when we are behind DSM's cumulative sales of the product through the day (net of the shed stock) and the route still ends by 24 with no added lateness; the books plan sells the goods on DSM's schedule
    "sd_tier_early_deliver_uval": 0.0,  # > 0 (KB72 fired 3.1 times a world: lag days exist - strawberry 9.0 / milk 7.1 / wool 5.9 a world - but spare hours rarely fit a delivery): when no spare-time delivery fits, the hand may give up its cheapest optional jobs while units x this value (the timing gain per unit delivered early; KB70 trips: rival strawberry windfall -711 for ~35 early units, ~20 a unit) exceeds the jobs given up
    "sd_tier_early_deliver_skip_max": 8,
    "sd_tier_pdrop": [],  # products (user 2026-09-27 "yes please try": DSM carries goods home mid-day and goes back out, 19.8 trips a world with 167 units - strawberry 38, milk 34, wool 25, melon 18 - we 5.8 with 32, strawberry 0.1; our routes stand on a shed access tile mid-day carrying goods on 12.5 hand-days a world, DSM 28): after planning, a route that passes a shed access tile after harvesting these products PLACEs them there (one op per product, named) when that costs <= sd_tier_pass_drop_cost extra hours, adds no lateness or supply failure, ends by 24 and the drop is by sd_tier_pass_drop_hmax; books products only while we are behind DSM's cumulative sales through the day (net of the shed stock), other products are sold on arrival. Differs from sd_tier_pass_drop (zero detour, planned before the fills, every product sold at once; KP4 vs KE7 margin -142 n.s.): planned after all fills, books products lag-gated and sold on DSM's schedule
    "sd_tier_pdrop_cost": 1,  # max extra route hours for one drop (1 = the path already crosses an access tile: only the PLACE hour)
    "sd_tier_pdrop_hmax": 20,  # latest drop hour (a post-tick sale hour 21 still follows)
    "sd_tier_pdrop_max": 1,  # drops per route
    "sd_tier_pdrop_ops": 2,  # products placed per drop (1 hour each)
    "sd_tier_pdrop_need": 1,  # 0: books products without the lag gate
    "sd_tier_pdrop_min": 2,  # min units per drop
    "sd_tier_pdrop_early": 0,  # 1 (case world: after all fills 140 of 179 routes end at 24, 1 drop a season): planned right after the mandatory search, before the fills pack the routes around it
    "sd_tier_feed_harvest": 0,  # 1 (DSM, 40 worlds: 31.1 feeding hand-days a world feed from wheat the hand harvested earlier on its route, no morning pickup; we 0 - every feeding hand loads wheat first, 41.9 hand-days a world load wheat for a single feed, DSM 6.4): a route's FEEDs are supplied first by the wheat of its earlier MANDATORY wheat harvests (today's yield on the tile), only the rest is picked up at the shed; the search, the fills and the executor's pickup all use this count. KB91 (mode 1) vs KB78 -460 (t -1.82): wheat loads 131 -> 120 a world but the search routes hands through the wheat field first: shed hours -11, moves +13, work -3 (no labor gained). 2: the supply is applied only after the mandatory search (the fills and the executor use it, the routes' order is the search's)
    "sd_tier_collect_c": 0,  # 1 (user: why is fertilizer lost? KB78 loses 97.5 pen-days of fertilizer a world, DSM 7.2; 82.5 of them on pens a hand WORKED that day without collecting, 18.3 by a hand that ended its day idle; in the plans 76 a world are listed extras worth 80 at a pen the route already visits, never placed: stand-alone collects are offered only in phases D / E, after phase C has filled the outbound routes with waterings ~10 and feed / care): the stand-alone collects join the phase C pool, merged only into a stop the route already has on that pen (no extra walking; 2 = any insertion); collects paired with a fertilize are unchanged. Case world: planned collects 363 -> 362 (1) / 353 (2), fertilizes 205 -> 190 / 160: the hands at those pens are full (84 of 89 such routes end at 24, mostly MANDATORY work), so a phase C collect only takes a fertilize pairing's collect. Parked with mechanism
    "sd_tier_collect_c_max": 0,  # > 0: at most this many phase C collects a day (the midnight shed room)
    "sd_tier_spawn_exact": 0,  # 1 (user 2026-09-27, spawn investigation panel_spawn.py: the hour-1 hires spawn by the engine rule on our units' positions after their hour-1 commands, which the plan predicts 100%, but the plan is self-consistent on only 49% of days - it assumes spawn tiles, re-routes the hour-0 hires around them, and their hour-1 positions then imply other tiles; the buffer plans those hires from hour 3 and they run ahead / idle): two-stage plan - inside each planning pass, after all routes are built, the farmer's and the hour-0 hires' routes stay fixed, their hour-1 positions give the exact spawn tiles, and the hour-1 hires' routes are reassigned to those tiles (best permutation by full route evaluation, from hour 2), optional tail ops trimmed while that makes a route late, freed time filled with the leftover extras (no harvests); the outer re-plan / buffer then sees a consistent plan; the executor remap is skipped when the hires stand where planned. KB96 (mode 1) vs KB78 -1,052: spawns 100% right but the first pass plans the hour-1 hires from an empty-shed guess (33 of 43 wrong), the reassignment leaves 1.0 late route and trims 15 optional ops a world (strawberry plant-days -2.0, weeds +2.5), and the fill's collects add midnight load (deleted +5 units a world). 2: re-plan up to twice with the exact tiles fed back into the search (keep the pass with the fewest mismatches), no collects in the fill. KB97 (mode 2) vs KB78 -414 (t -1.44): spawns 100% right, deaths back to 1.2, but work +0.02 a hand-day (idle -0.10 h turns into moves +0.08) and the hour-1 hires carry 16 more units into the midnight dump, where they come last (deleted 9.0 -> 11.9 a world; 7.8 of KB78's 9.0 are the hour-1 hires' goods). Parked with mechanism: the buffer hour is worth little because the planner does not turn it into work
    "sd_tier_farmer_h0pick": 0,  # 1 (user 2026-09-27, labor viewer: the farmer idles at hour 0; DSM's farmer PICKs UP wheat at hour 0 on 71% of days, ours PASSes on 73% and picks up at hour 1): with the hour-0 hold, the farmer's ordinary outbound route starts at hour 0 with the rule that his hour-0 command never moves him (a pickup at the shed or a job on his own tile, else he waits that hour) - the hires' spawn stays known and the search gets his hour 0; the executor turns any hour-0 move into PASS
    "sd_tier_route_swap": 0,  # 1 (user 2026-09-27, labor viewer day 17: hand 4 spawned on (4,4) with a route that starts next to (4,5), a step lost, while another hand could have taken it; the hour-0 hires spawn in a fixed order on known tiles and the sector search moves single stops, never whole routes - first planned stop 1.47 steps from the hand's spawn tile vs 1.20 from the nearest shed tile, 40-world mean): right after the mandatory search, whole routes are swapped between outbound hands with the same start hour (each re-ordered from its new start), best improvement first, while the pair's cost falls and no lateness is added; spawns do not change (they follow the hire order). KB102 (mode 1) on 2 worlds -1,541 / -3,756 and first stops FARTHER from the spawn (1.45 -> 1.63 steps): the fills change each route's start after the swap and the re-plan passes shuffle again. 2: on the FINISHED routes, just before they are built: the same-start outbound hands trade whole routes (order kept) so that the sum of their end hours falls - i.e. each route starts from the spawn tile nearest its first stop - kept only when no route gets later than 24 or later lateness
    "sd_path_planner": 0,  # 1 (user 2026-09-27, audit docs/tier_planner_audit.md: routes are already path-like, the gap is work per visit 1.75 vs DSM 2.06 ops a tile - required work routed first, optional pieces filled after, hours-only objective): one search over TILE SERVICES (all worthwhile ops of a tile together; a tile with required ops may also run required-only or without its fertilize), objective = value of the optional work done - sd_path_lambda x the route's hours - 1000 x lateness / supply failures; required tiles always placed, optional-only tiles may stay unvisited; starts from the mandatory search, upgrades / inserts greedily, then anneals (relocate, swap, reorder, mode toggle, pool insert / remove, whole-route swap between same-start hands); replaces the extras fills
    "sd_path_lambda": 0.0,  # coins an hour of a hand's time inside its day (user: the hand is bought - no cost <= 24 h, infinite beyond; KB104 at 30: idle 569 h a world on 2 worlds, -18k: jobs valued under 30 an hour left undone in free time)
    "sd_path_eps": 0.01,  # tie-break per route hour: the shorter of two equal-value routes
    "sd_path_eject": 1,  # 1 (KB108 day 17: optional sheep pens worth ~400 left out because every nearby route ended at 24 with waterings worth 10): inserts and upgrades make room by dropping the least valuable optional work of that route
    "sd_path_iters": 3000,  # annealing iterations per planning pass
    "sd_path_near": 4,  # tiles: a move only targets routes with a stop this close
    "sd_path_t0": 20.0,  # annealing start temperature (coins)
    # tile exactness (user 2026-09-27: type exact - retirements modelled exactly, a same-type replant may keep our timing).
    # KB78 on 112602061: 44 tiles of another type than DSM's by day 29 - DSM let 5 cows escape on days 16-19 that we
    # kept (his wheat / carrots there were moved), DSM's pastures / wheat went elsewhere because our tomatoes /
    # strawberries still stood on his tiles
    "sd_exact_retire": 0,  # 1: DSM's animal escapes copied: no FEED / CARE on our animal (same tile by smap) on a day
    # DSM's animal of that species is not alive at the next or the one-after morning (2 unfed days = the escape night; also
    # an animal of ours where DSM has another species or none); its HARVEST on the escape day is mandatory. 2: only
    # escapes before night 27 (DSM's end-of-season stop of feeding not copied)
    "sd_clean": 0,  # 1 (user 2026-09-28, KB115LT: "everything that goes to tile planner can be kept"): the LOWER layer reads
    # none of DSM's recorded game beyond the tile plan interface (TilePlanView) - off: DSM's daily sales quota in the
    # delivery values (sd_dv_quota) and in the dispatcher's open products (quota_open), the regular sell path's DSM quota
    # (every product it serves is sold by sell_now / sd_fert_sell / the books anyway), and DSM's tomorrow fertilize count in
    # the fertilizer reserve (T.fert). Inactive in the tier arms and not covered here (keep them off; sd_tp_iface counts
    # any read): fert_shadow, sd_mr, sd_cap_all, sd_hourly_profile, sd_h0_front, fert_follow, maint_source /
    # harvest_source "leader", the books "dsm" source, sd_harvest_follow_dsm, copy returns, dayret, dawn shape "file"
    "sd_clean_plan": 0,  # 1 (the user's first ruling, 2026-09-28, kept for a tile planner that supplies no cohort ends /
    # exits): the plan-side DSM timing off too - DSM's animal exits (sd_exact_retire + prefeed; see sd_own_retire), the
    # late-planting cutoff exemption for cohorts the plan harvests (cut_mode leader_harvest -> every late planting),
    # replant_leader (harvest-and-replant on the plan's harvest day) and the catch-up skip when the plan's own cohort is
    # gone from its board (T.board)
    "sd_tp_iface": 0,  # 1 (KB115LT): the plan is read only through TilePlanView (the tile planner -> lower layer interface,
    # fields listed on the class); other fields of the recorded game and the per-world DSM files (_dsm_data) return empty
    # and every such read is counted in _TP_LEAK, logged per day as the tier summary's "tp_leak"
    "sd_tp_file": None,  # with sd_tp_iface: a JSON tile plan {episode: TilePlanView.to_dict()} (or one plan) replaces the
    # recorded game's plan entirely - the input a trained tile planner writes (scripts/export_tile_plans.py writes DSM's)
    "sd_own_retire": 0,  # 1 (with sd_clean): our retirement rule - an animal with no production night left that can still
    # reach the market (nights day .. last - 1; a night-28 product is harvested and sold on day 29) gets no FEED / CARE
    # (the survival feed included) and its held yield is harvested on the day it escapes (the sd_exact_retire mechanics)
    "sd_exact_retire_prefeed": 0,  # 1: FEED mandatory on our animal two days before DSM's escape night (the two unfed days
    # then fall on DSM's: KB113 on 112604454 lost 4 sheep a night early where the module had skipped that feed)
    "sd_exact_site": 0,  # 1: DSM's planting / structure stays on DSM's tile when our asset of another type holds it: a live
    # plant of another crop (any age) is harvested (when it holds units) and dug, an empty structure dug, an animal of ours
    # that sd_exact_retire lets go is waited for; 2: also wait (no remap) where our plant is the same crop (our timing)
    "sd_tier_fert_merge_collect": 0,  # 1: a merged fertilize may use fertilizer the route already collects and does not spend (look-back pen collects) before asking for a shed pickup (one spare hour instead of two)
    "sd_tier_prio_ani": 0,    # 1 (user 2026-09-26: "melon mode" for important animal harvests): the farmer (no melon duty that day) first harvests the cow / sheep pens holding >= sd_tier_prio_ani_min units (or due), feed / care in the same visit, best units x price per added hour while his drop at the shed stays by sd_tier_prio_ani_by; then he is a normal hand (post segment in the sector search), as after a melon delivery
    "sd_tier_prio_ani_min": {"COW": 3, "SHEEP": 4},   # DSM's mean units per harvest at pens near the shed (cow 3.4-3.8, sheep 4.2-4.4); eggs left out (DSM delivers only 18% of eggs the same day)
    "sd_tier_prio_ani_by": 8,     # the melon rule's morning deadline
    "sd_tier_central_hand": 0,   # 1 (user 2026-09-26): the farmer (when he has no melon duty) is the CENTRAL hand: he serves the pens within sd_tier_central_radius of the shed (FEED, CARE when a later production realises it, the due HARVEST), chosen greedily by value per added hour (care = product price, feed cashing a bank = bank x price) while his day fits, and puts each harvest into the shed right after (DELIVER, sold at once; pens on access tiles use PLACE_HARVEST); the COLLECTs stay with the outbound hands; his pens leave the others' work; he is out of the sector search, fills and relief
    "sd_tier_central_radius": 2,
    "sd_tier_central_mode": "care",   # "deliver" (user: the central hand is for EARLY DELIVERY): first the central pens with product (due harvest or >= sd_tier_central_hmin), ranked by units x price per added hour, each with its feed / care in the same visit and a drop at the shed right after; then care of other central pens with the time left
    "sd_tier_central_hmin": None,  # e.g. {"COW": 3, "SHEEP": 4, "GOOSE": 3} (DSM's mean units per harvest at pens within 2 tiles: cow 3.4-3.8, sheep 4.2-4.4, goose 2.7-3.5): the central hand also harvests (and drops) a pen holding at least this many units   # DSM same-day milk delivery by distance from the access tiles: 95 / 61 / 42 / 27% at 0 / 1 / 2 / 3
    "sd_tier_spawn_buffer": 0, # 1 (2026-09-26): when the hour-1 hires' spawn prediction has still not settled after the re-plan passes, re-plan once from the spawn tiles the plan's own hour-1 positions imply, with the hour-1 hires planned from hour 3 (one hour of slack: a spawn one tile off then costs no tail work)
    "sd_tier_spawn_remap": 0,  # 1 (2026-09-26): at the first hour the hour-1 hires act, their routes are reassigned among them so each takes the route whose first stop is nearest its actual spawn tile (the spawn prediction does not always settle: 30% of them started late in KS1, all on a wrong spawn tile)
    "sd_tier_spawn_h2": 0,    # 1 (2026-09-26): the hour-1 hires spawn on the least occupied shed tile AFTER the hour-0 units' hour-1 commands; when that differs from the plan's assumption (empty shed tiles), re-plan once with the spawn tiles the plan's own hour-1 positions imply (KE7: 65% of hour-1 hires started ~0.9 h late and lost their route's tail ops)
    "sd_tier_water_exact": 0, # 1 (user 2026-09-26: shift the weights): a non-mandatory WATER is worth units x price by engine rules (one-time crop in its window: +1, +2 fertilized, to the cap; ongoing crop producing tonight and fertilized: +1 if under the cap; else 0) + sd_water_tomorrow   # > 0: the pen's harvest joins the stop when it holds >= this many units (else the cap rule)
    "sd_tier_pen_round": 0,   # 1 (user 2026-09-26, learned from DSM): a hand whose mandatory route holds animal harvests within sd_tier_pen_radius of the shed does them first and puts the product into the shed (DELIVER) before its other stops; planned right after the mandatory sector search, before the extras
    "sd_tier_pen_radius": 2,
    "sd_tier_pen_min": 0,     # > 0: a pen within the radius holding >= this many units keeps its harvest mandatory (joins the morning round) even when nothing overflows tonight
    "sd_tier_pass_drop": 0,   # 1 (user 2026-09-26): a hand whose planned path crosses a shed-access tile at no extra distance (or stops on one) while carrying goods drops them there (DELIVER, sold at once; the feed wheat / fertilizer its later stops need is kept); planned after the mandatory search, no added lateness
    "sd_tier_pass_min": 1,    # ... only when it carries at least this many units (fertilizer not counted)
    "sd_tier_turn_plan": 0,   # 1 (user, learned from DSM): right after the mandatory sector search each outbound hand gets one shed stop after its harvest leg (>= sd_tier_turn_min units, reached by sd_tier_turn_hour, detour <= sd_tier_turn_detour, no added lateness); the extras then fill around it
    "sd_tier_turnaround": 0,  # 1 (leader shed-flow analysis): when the projected midnight dump will not fit, a hand whose harvest leg ends by sd_tier_turn_hour passes the shed between two stops (detour <= sd_tier_turn_detour tiles) and PLACEs its harvested goods there, sold at once (keeping the wheat / fertilizer its later stops need); end-of-day deliveries handle the rest
    "sd_tier_turn_hour": 16,
    "sd_tier_turn_detour": 2,
    "sd_tier_turn_min": 4,    # ... only loads of at least this many units
    "sd_tier_access_drop": 0, # 1 (leader shed-flow analysis, 2026-09-26): a HARVEST on a shed-access tile is followed by a PLACE of the harvested product into the shed, sold at once (leaders deliver 89-97% of such milk / wool / eggs the same day, K5b 8-19%)
    "sd_tier_feed_bank": 0,   # N >= 1 (coordinator 2026-09-26): a FEED on the animal's production day is mandatory (tier B) when its banked care bonus is >= N (an unfed production day wipes the bank: K5b loses 23 eggs / 19 milk / 13 wool a world that way vs DSM 15 / 8 / 3)
    "sd_tier_goose_care": 0,  # KWE thread (2026-09-26, world 112604454: goose CARE 48 vs DSM 80 on the same 5 geese, 27 fed-not-cared goose-days vs 1 -> 21 fewer eggs; a CARE is a tier-4 extra that the packed days never take): 1 = a goose CARE is mandatory (same stop, +1 h) wherever the goose's FEED is mandatory today (keep-alive / sd_tier_feed_bank), which chains daily (a cared day banks +1, the next day's FEED is then mandatory by the bank); 2 = also FEED + CARE on a goose with any other mandatory op (a due HARVEST); 3 = FEED + CARE mandatory on every live goose every day (DSM: fed 81 / cared 80 of 90 goose-days). Only while the care can still be paid by a harvestable production (day <= last_day - 2)
    "sd_tier_goose_c_minv": None,  # KWE: goose FEED / CARE bundles join the tier-C pool (value per hour against the waterings / fertilizes) when worth >= this (None: the general sd_tier_anim_c_minv)
    "sd_tier_goose_c_mult": 1.0,   # KWE: ... their value multiplied by this in that pool
    "sd_tier_anim_harv": 0,   # 1: an animal HARVEST is mandatory only when tonight's production would overflow max_held
    "sd_tier_anim_harv_frac": 0.1,   # ... else an extra worth held x price x this
    "sd_tier_anim_harv_end": 27,     # ... from this day every animal harvest stays mandatory (season end)
    "sd_tier_anim_out": 0,    # 1 (user idea): in phase C, after the collect -> fertilize pairs, an outbound hand with spare time
                              # feeds / cares / collects the animals on its outbound leg (spawn -> first patch stop)
    "sd_tier_anim_out_detour": 0,    # ... animals at most this many tiles off a shortest path (0 = on it; 1 tile = 2 extra steps)
    "sd_tier_anim_out_spare": 1,     # ... a hand qualifies while its planned day ends by 24 - this (hours)
    "sd_tier_anim_out_collect_only": 0,  # 1 (user: "for outbound hands to collect more fertilizers"; KB43 on 8 worlds: collects +15, fertilizer margin +985, eggs +499, but its outbound FEED / CARE delayed the crop work: strawberry -1,042, wheat -395, wool -307): the outbound pass takes only the COLLECTs
    "sd_tier_out_collect_late": 0,  # 1 (user: collect "if they have free steps at the end"; KB47 collect-only in phase C -1,320 on 8 worlds - the pass reorders phase C and its collects take the hours of waterings worth more than their value): after all fills, a hand whose plan still has free hours collects fertilizer at animals on its shortest path out (detour sd_tier_anim_out_detour) when the route still ends by hour 24 and the midnight dump has room for the fertilizer
    "sd_tier_path_collect": 0,  # 1 (user 2026-09-27: "if after planning we have a hand with unspent hour, we can retroactively inspect animal pens along the path"): after all fills, a hand whose planned day ends before 24 collects the free fertilizer of pens it already stops at (merged, no walking) and of pens inside any leg's shortest-path box (no detour), cheapest first, while the route still ends by 24 with no added lateness and the midnight dump has room
    "sd_tier_path_collect_detour": 0,  # pens up to this many tiles off a leg's shortest path also qualify (1 tile = 2 extra steps)
    "sd_tier_collect_swap": 0,  # 1 (user: "retroactively swap out a collection from central hand to outbound hand when it turns out that it has 1 hr extra... central hand saves 1hr"): after planning, a COLLECT in a full hand's route (planned to hour 24, not supplying its own fertilize) moves to a hand with spare time that stops at the pen or passes it (sd_tier_path_collect_detour), and the full hand refills the freed hour from the day's leftover extras
    "sd_tier_straw_fert_mult": 1.0,  # strawberry FERTILIZE extras' value x this (user: "add value to strawberry fertilization"; KB54 leaves 14.3 watered production nights a world unfertilized vs DSM 4.5 - the missing ones are the cycle's first (+9) and third (+13) fertilizes)
    "sd_tier_straw_fert_days": [],  # user: strawberry fertilizes on these days since planting (9, 13: each covers two production nights, p+9/p+11 and p+13/p+15) get value x sd_tier_straw_fert_day_mult
    "sd_tier_straw_fert_day_mult": 10.0,
    "sd_tier_straw_odd_water": 0,  # 1 (user: "stagger the watering from the fertilization days"): strawberries are watered on odd days since planting (the production nights +9/+11/+13/+15 and the fertilize days are odd; every other day keeps them alive; blocks planted on even / odd days alternate): an optional strawberry WATER on an odd day gets value >= sd_tier_straw_odd_water_v (a production night of a fertilized plant: the strawberry price), one on an even day is dropped (mandatory keep-alive waters stay)
    "sd_tier_straw_odd_water_v": 40.0,
    # ---- dawn thread (2026-09-28, KDW): DSM's dawn deliveries of wool / milk, all default OFF (= KS1fl)
    "sd_tier_dawn": 0,        # 1 (user: "we want them early just like DSM did"; DSM makes short round trips at the start of the day):
                              # at hour 0, before the mandatory sector search, a unit that starts its day at the shed by hour
                              # sd_tier_dawn_t0max takes ONE near pen (within sd_tier_dawn_radius of a shed tile, holding >=
                              # sd_tier_dawn_min units): walk there, HARVEST, walk back to the nearest shed tile and PLACE the
                              # product (DELIVER, sold at once; a pen ON a shed tile: HARVEST + PLACE_HARVEST in place), all by
                              # hour sd_tier_dawn_by; then it picks up its wheat and is a normal outbound hand from that shed
                              # tile (DSM world 112604454: 8 trips / 38 units at hours 0-1, harvest h1-2, drop h3-4; we made 0)
    "sd_tier_dawn_radius": 1, # DSM's round trips: all 8 to pens 1 tile from a shed tile (its near-pen harvests <= 2 tiles: 70 of 86 dawn wool, all 129 dawn milk)
    "sd_tier_dawn_min": {"COW": 3, "SHEEP": 4},   # DSM's near-shed harvest sizes (cow 3.4-3.8, sheep 4.2-4.4: one production each, harvested the morning after it)
    "sd_tier_dawn_by": 4,     # DSM's dawn drops: hours 1-4 (leave h0-1, back within 3 h)
    "sd_tier_dawn_t0max": 1,  # units that act from hour 1 at the latest (farmer, hour-0 hires; DSM leaves at h0-1)
    "sd_tier_dawn_max": 0,    # > 0: at most this many dawn legs a day (0 = one per eligible pen)
                              # sd_tier_dawn 2: the same leg as an EXTRA (tier C pool, phase C) that competes with the other
                              # extras by value per added hour, put at the start of an outbound hand's route (its pickups after
                              # it); only pens whose harvest is deferred (sd_tier_anim_harv); legs no hand takes go back to plain
                              # deferred harvests
    "sd_tier_dawn_shape": None,  # sd_tier_dawn 3 (user: "imitate the exact shape of DSM's early morning trips: how many hands,
                              # how many tiles"): {day: [[dsm unit, first acting hour, start tile, [[pen tile, animal], ...],
                              # drop tile], ...]} from DSM's recorded game of this world (scripts/dsm_dawn_shape.py); each DSM
                              # trip is given to one of our units acting from the same hour (the farmer for DSM's farmer; a hire
                              # starting on DSM's start tile first, else the one nearest the pen), over the same pens where our
                              # board holds the same animal with product (HARVEST; a lone pen on a shed tile: PLACE_HARVEST in
                              # place, else DELIVER on DSM's drop tile), then its pickups and route; a DSM farmer trip at hour 0
                              # makes our farmer act at hour 0 that day (no hold)
    "sd_tier_dawn_service": 0,  # 1 (modes 1 / 3; DSM: after the trip's wheat pickup the unit feeds / cares / collects the pen it just
                                # harvested, e.g. d12 u2 HARVEST 54 h1, PLACE h2, PICKUP h3, FEED h4, CARE h5, COLLECT h6): the leg pen's
                                # FEED / CARE / COLLECT (mandatory, or extras worth > 0) become the first stop of that unit's route
                                # after its pickups (KDS1b traced: splitting the pen visit lost 5 cow CAREs = 5 milk a season)
    "sd_tier_dawn_cf": 0,     # diagnosis only: at hour 0 also plan the day with the dawn legs off, from the same state and the
                              # same units / spawn tiles, and log that plan in the day summary ("cf": per unit end hour and
                              # stops [tile, [[op, mandatory, tier, value], ...]], unplanned extras) -> the jobs the legs displaced
    "sd_tier_dawn_frac": 0.25,  # mode 2: a dawn-delivered unit is worth price x this (DSM: timing ~1.4k wool + 1.9k milk here for
                                # 49 + 68 units delivered within 2 h of a dawn harvest, ~28 a unit = 0.15-0.25 x price)
    "sd_melon_rule": 0,       # 1 (user): hard-coded melon trips (by 8 bonus / 8-12 penalty / never after 12), melon hands kept out of the planner
    "sd_mel_bonus": 10.0,     # coins per melon unit per hour delivered before 8
    "sd_mel_pen": 10.0,       # coins per melon unit per hour delivered after 8 (never after 12)
    "sd_fert_sell": 0,        # 3: as 1 (collected fertilizer stays in hand) but the shed keeps tomorrow's fertilize need for
                              # route pickups (KB134 / KB135 with sd_tier_fert_shed); 1 (user rule, leader tapes): the shed's fertilizer is all sold (no reserve), fertilizer is never picked up from the shed, collected fertilizer stays in hand for fertilizing (never delivered mid-day; the midnight dump brings the rest, sold next morning)
    "sd_retire": 0,           # plants the plan retires (abandoned / cleared before producing again) get no hard water job
    "sd_plan_log": 0,         # viewer: log each hand's planned job tiles (route order) on every change (L["plan_log"])
    "sd_early_animal": 0,     # a BUILD job's animal is bought while its tile still waits for the crop harvest
    "sd_seed_fix": 0,         # the warm start drops plantings the seeds held no longer cover (the plan never over-commits seeds)
    "sd_hop_central": 2,      # contiguity: tiles within this distance of the shed are en-route (no hop cost to / from them)
    "sd_hop_w": 0.0,          # contiguity: coins per step of a hop beyond one between consecutive job tiles (0 = off)   # sectors: rebalance while a quadrant's ops per home hand exceed this x another's
    "sd_hv_pref": {},         # v3: the leaders' harvest timing as soft bonuses on HARVEST ops (see the block header); {} = off
    "sd_keep": 0,             # research: keep the last plan object (static checks)
    "sd_log": None,           # research: directory for per-step jsonl records + the game summary
    # ---- xfix (2026-09-25), tile-exact fixes, all off by default
    "replant_leader": 1,      # (default ON since the xfix port) # 1: a leader planting stays on the leader's tile when our tile holds the same one-time crop the leader harvested there today / yesterday (harvest now at any harvestable age, then plant) instead of remapping the planting to a free tile (the leader harvests melons at age 10 and wheat at age 2 to replant)
    "fert_follow": 0,         # 1: the leader's per-tile FERTILIZE targets of the day (the plan's fert set) become FERTILIZE ops on our live plants under sched_maint (the maintenance module's own ops otherwise replace them)
    "fert_follow_prio": 1,    # priority of a followed fertilize (0 / 1)
    "fert_gross": 0,          # 1: a FERTILIZE job's priority is judged on its gross value (units x price), not net of the fertilizer at its market quote
    "fert_shadow": 0,         # 1: the maintenance module values fertilizer at price - 0.2 x forecast own remaining sales (the leader plan's remaining fertilizer sales); 2: + 0.2 x the rival's (not modelled: = 1)
    "idle_deliver": 0,        # 1: a unit left without a task carries its sellable stock (fertilizer included, beyond today's open fertilize need) to the shed while a same-day sale is still possible (arrival by hour 22) and the shed has room (DROP deletes overflow)
    "lead_harvest_bonus": 0,  # steps: cost bonus for a task that harvests a one-time crop (melon / wheat / carrot) with no yield left to gain, or a melon, on a tile the leader harvests today (melons: no shop demand, 250 - 0.01 x excess^2, the first units sold win; the leader harvests them at h4-7 and sells by h11)
    "harvest_policy": "leader_tendency",   # (default ON since the xfix port) # "leader_tendency" (user ruling, 2026-09-25; 540 leader tapes): SOFT value / priority bonuses toward the leaders' harvest windows, independent of the target: melons at the first allowed age (10) after watering to 6, early in the day (dispatch bonus before hp_melon_hour) and delivered for a same-day sale; wheat at age >= 2 on days 0-11 where a plan job replants the tile, at age >= 3 from day 12; carrots at age 3; tomatoes / strawberries at every production; water before a harvest that day; one-time crops at their last age join the survival routes (never decay)
    "hp_wheat_min_units": 0,  # wheat cycle: before the max-yield age, wheat enters the harvest window only once today's water brings it to this many units (5 = fertilized wheat at age 3)
    "hp_crops": ["MELON"],   # (xfix port default: melons only; the wheat / carrot / ongoing tendencies measured worse) # crops the harvest tendency applies to
    "hp_frac": 0.5,           # harvest value inside the tendency window = held units x price x this (prio 1 above p1_min_value)
    "hp_melon_bonus": 6,      # dispatch cost bonus (steps) for a melon harvest task before hp_melon_hour
    "hp_melon_hour": 8,       # the melon dispatch bonus applies before this hour (user ruling: before 8 AM; the leaders harvest melons at median h6, IQR 5-8; noon measured the same)
    "upkeep_scale": 1.0,      # x on the maintenance module's non-survival animal FEED / CARE job values (upkeep thread: the per-job losses overstate the pair's joint loss by ~35%; 0.65)
    "busy_upkeep_pen": 0,     # steps added to a non-survival animal-upkeep-only task (FEED / CARE / COLLECT) while the open tasks exceed busy_ratio x crew (upkeep thread: on busy days the leader skips upkeep for harvests / digs / plantings)
    "busy_ratio": 3.0,
    "deliver_credit": 0,      # 1: deliver when the carried units' same-day-sale credit exceeds the trip (dc_step_value x 2 x shed distance) instead of the flat deliver_units / deliver_value trigger (credit per unit: results/fresh/harvest_timing_20260925/market/credit_tables.json: melon ~54 before noon on days 6-11 else ~12, wool 26/9/7/6, milk 13/7/1/0, strawberry -1/3/5/-2 by day window 6-11/12-17/18-23/24-28, others 0)
    "dc_step_value": 12.0,    # coins of displaced work per unit-step
    "fert_release": 0,        # 1: fertilizer is kept in hand only while today's open fertilize need exceeds the stock in hands (the surplus is deliverable), and the market's fertilizer reserve counts our own ongoing plants due tomorrow, not the leader's tomorrow targets we do not follow (they held 18.4 vs the leader's 9.9 at midnight)
    "pf_log": 0,              # 1: planting-fate log (logging only): for every leader planting event (day, tile, crop) its fate in T and the code path; S["pf"]
}


def _dcredit(p, day, hour):
    """xfix deliver_credit: coins per unit of selling at the harvest hour instead of after the midnight dump."""
    w = 0 if day <= 11 else 1 if day <= 17 else 2 if day <= 23 else 3
    if p == "MELON":
        return 54.0 if (day <= 11 and hour < 12) else 12.0
    return {"WOOL": (26.0, 9.0, 7.0, 6.0), "MILK": (13.0, 7.0, 1.0, 0.0),
            "STRAWBERRY": (-1.0, 3.0, 5.0, -2.0)}.get(p, (0.0, 0.0, 0.0, 0.0))[w]

def _curve():
    order = []
    for qx, qy, rows in ((0, 0, range(4, -1, -1)), (5, 0, range(0, 5)), (5, 5, range(5, 10)), (0, 5, range(9, 4, -1))):
        for k, y in enumerate(rows):
            xs = range(qx, qx + 5) if k % 2 == 0 else range(qx + 4, qx - 1, -1)
            if qx == 0 and qy == 0:
                xs = range(4, -1, -1) if k % 2 == 0 else range(0, 5)
            for x in xs:
                order.append(y * 10 + x)
    return order


CURVE = _curve()
CURVE_POS = {idx: i for i, idx in enumerate(CURVE)}

_SMNS = None


def _sm():
    """scripts/fragments/sem_maintenance.py (stdlib-only; pasted into the single-file agent later)."""
    global _SMNS
    if _SMNS is None:
        import os
        here = globals().get("__file__")          # undefined under Kaggle's loader (exec of the source)
        cands = [os.path.join(os.path.dirname(os.path.abspath(here)), "..", "scripts", "fragments", "sem_maintenance.py")] if here else []
        cands.append(os.path.join(os.getcwd(), "scripts", "fragments", "sem_maintenance.py"))
        path = next((c for c in cands if os.path.isfile(c)), cands[-1])
        ns = {}
        with open(path, encoding="utf-8") as fh:
            exec(compile(fh.read(), "sem_maintenance", "exec"), ns)
        if CFG.get("retire_visit"):
            _orig_plan0 = ns["sm_tile_plan"]
            _animals = set(ns.get("SM_ANIMALS", {}))

            def _retire_plan(kind, state, day, hour, price=None, input_price=None, fert_ok=False, future_hour=8,
                             visit_cost=0.0, *a, **k):
                if kind in _animals:
                    visit_cost = max(visit_cost, float(CFG["retire_visit"]))
                return _orig_plan0(kind, state, day, hour, price, input_price, fert_ok, future_hour, visit_cost, *a, **k)
            ns["sm_tile_plan"] = _retire_plan
        if CFG.get("maint_goal") == "max_production":
            _orig_plan = ns["sm_tile_plan"]

            def _max_prod_plan(kind, state, day, hour, price=None, input_price=None, *a, **k):
                return _orig_plan(kind, state, day, hour, price, 0.0, *a, **k)   # inputs free: the max-units plan
            ns["sm_tile_plan"] = _max_prod_plan
        _SMNS = ns
    return _SMNS


def _mj_fert():
    return True if CFG.get("maint_goal") == "max_production" else CFG["mj_fertilize"]


_T = None      # Target
_S = None      # per-game state


def _quad(x, y):
    return ("N" if y < 5 else "S") + ("W" if x < 5 else "E")


def _fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


# =========================================================================== TARGET (interface)
# A target supplies, per day d: events [(plant_day, tile, crop)], plant[d] {tile: crop}, fert[d] set(tile),
# struct_by_day[d] {tile: 'COOP'|'PASTURE'}, animals_by_day[d] {tile: species}, hands[d], cum_sold[d]
# Counter(product -> cumulative units sold through day d), land_day {quadrant: day}, board[d] (labels), n.
# Deployment builds the same fields from other sources (replace Target / configure only).

class Target:
    def __init__(self, sem):
        days = sem["days"]
        self.n = len(days)
        self.board = [d["board"] for d in days]
        self.harv_tiles = [set((d.get("harvested") or {}).get("tiles", [])) for d in days]   # the leader's harvested tiles per day
        self.plant = []          # day -> {tile: crop}
        self.fert = []           # day -> set(tile)
        self.hands = [int(d["labour"].get("hands_present", 0)) for d in days]
        self.cash = [d.get("cash_start") for d in days]
        self.final = sem["meta"]["rewards"][sem["meta"]["seat"]]
        struct_kind = {}
        self.struct_by_day = []  # day -> {tile: kind} desired structures at END of day d
        for d, day in enumerate(days):
            self.plant.append({t: c for c, ts in day["planted"].items() for t in ts})
            self.fert.append(set(day["maintenance"].get("FERTILIZE", [])))
            for op, ts in day["built"].items():
                for t in ts:
                    struct_kind[t] = "COOP" if op == "BUILD_COOP" else "PASTURE"
            for t in day["dug"]:
                # a dug structure disappears
                if t in struct_kind and (d + 1 >= self.n or self.board[d + 1][t] not in ("co", "pa", "sh", "go")):
                    struct_kind.pop(t, None)
            self.struct_by_day.append(dict(struct_kind))
        # desired animals at end of day d: from board d+1 (last day: board of day 29)
        self.animals_by_day = []
        for d in range(self.n):
            b = self.board[d + 1] if d + 1 < self.n else self.board[d]
            want = {}
            for t, kind in self.struct_by_day[d].items():
                lab = b[t]
                if kind == "COOP" and lab == "go":
                    want[t] = "GOOSE"
                elif kind == "PASTURE" and lab == "sh":
                    want[t] = "SHEEP"
                elif kind == "PASTURE" and lab == "co":
                    want[t] = "COW"
            self.animals_by_day.append(want)
        # quadrant unlock day
        self.land_day = {}
        for q in LAND_ORDER:
            for d in range(self.n):
                b = self.board[d + 1] if d + 1 < self.n else self.board[d]
                if any(b[y * 10 + x] != " L" for y in range(10) for x in range(10) if _quad(x, y) == q):
                    self.land_day[q] = d
                    break
        # actual-day sold units (fix the one-day shift of the semantics' market block)
        sold = [Counter() for _ in range(self.n)]
        for i, day in enumerate(days):
            actual = 1 if i == 0 else i + 1
            if actual < self.n:
                sold[actual].update(day["market"]["sold_units"])
        self.cum_sold = []
        run = Counter()
        for d in range(self.n):
            run = run + sold[d]
            self.cum_sold.append(Counter(run))
        # plant events list (pd, tile, crop)
        self.events = [(d, t, c) for d in range(self.n) for t, c in self.plant[d].items()]
        # OPTIONAL fields (ablation only; deployment targets may omit them):
        # maint[d] = {'WATER'|'FEED'|'CARE'|'FERTILIZE': set(tile)} the leader's own maintenance that day
        self.maint = [{op: set(ts) for op, ts in day["maintenance"].items()} for day in days]
        self.hire_steps = {}      # step -> number of HIRE orders the leader issued (set by the ablation harness)
        # sem4 exact removals: removals[d] = [(leader tile, crop, cohort planting day)] for the leader's DIGs on day d
        # of a tile showing a crop label on the leader's board that day (plants only; structures stay with
        # struct_by_day, weeds are ignored); the cohort is the last planting of that crop on the tile before day d
        self.removals = [[] for _ in range(self.n)]
        last_plant = {}
        for d, day in enumerate(days):
            seen = set()
            for t in day["dug"]:
                crop = LABEL_CROP.get(self.board[d][t])
                if crop is not None and t not in seen and last_plant.get(t, (None, None))[1] == crop:
                    self.removals[d].append((t, crop, last_plant[t][0]))
                    seen.add(t)
            for c, ts in day["planted"].items():
                for t in ts:
                    last_plant[t] = (d, c)


_TP_LEAK = Counter()    # sd_tp_iface: reads of non-interface plan fields / per-world DSM files


class TilePlanView:
    """sd_tp_iface (KB115LT): the TILE PLANNER -> LOWER LAYER interface. The lower layer (maintenance, harvests, labour,
    routes, sales) reads only these fields of the plan; a trained tile planner must supply exactly them. Per day d of n:
      n                  season length in days
      plant[d]           {tile: crop} plantings the plan makes on day d
      events             [(planting day, tile, crop)] the same plantings as one list
      struct_by_day[d]   {tile: "COOP" | "PASTURE"} structures standing at the end of day d
      animals_by_day[d]  {tile: species} animals the plan keeps at the end of day d (a placement is the first day on a
                         tile, an exit / retirement the first day off it)
      board[d]           [100 labels] the plan's board at the start of day d (crop cohorts, structures, animals, locked)
      harv_tiles[d]      set(tile) crop cohorts that END on day d (one-time crop harvest) or have their FIRST harvest
                         (ongoing crop): cohort life, not pick timing; animal pens are left out (their harvests are ours)
      removals[d]        [(tile, crop, planting day)] live crop cohorts the plan digs out on day d
      land_day           {quadrant: day} land purchases
      hands[d]           hands present on day d
      cum_sold[d]        OPENING ONLY: cumulative units sold through day d for d <= 10 (the replayed opening's sales,
                         which are ours; the harness seeds our sold counter from day 10 at the handoff); d >= 11 is the
                         lower layer's business (empty, counted as "cum_sold>10")
    Days 0-10 are the recorded opening (the harness replays them). Everything else of the recorded game - fert
    (fertilize targets), maint (upkeep lists), cash, final, hire_steps - belongs to the lower layer: a read returns empty
    data and counts in _TP_LEAK; _dsm_data (per-world DSM files) returns None and counts too."""

    OPENING_LAST = 10

    class _Opening(list):
        def __getitem__(self, i):
            if isinstance(i, int) and (i if i >= 0 else len(self) + i) > TilePlanView.OPENING_LAST:
                _TP_LEAK["cum_sold>10"] += 1
                return Counter()
            return list.__getitem__(self, i)

    def __init__(self, T):
        self.cum_sold = TilePlanView._Opening(T.cum_sold)
        self.n = T.n
        self.plant = T.plant
        self.events = T.events
        self.struct_by_day = T.struct_by_day
        self.animals_by_day = T.animals_by_day
        self.board = T.board
        self.removals = T.removals
        self.land_day = T.land_day
        self.hands = T.hands
        ht, seen = [], set()
        for d in range(T.n):
            keep = set()
            for t in sorted(getattr(T, "harv_tiles", [set()] * T.n)[d]):
                crop = LABEL_CROP.get(T.board[d][t])
                if crop is None:
                    continue                           # a pen (or no crop): the lower layer's harvest
                if not CROPS[crop]["ongoing"]:
                    keep.add(t)                        # a one-time cohort ends
                elif t not in seen:
                    keep.add(t)                        # an ongoing cohort's first harvest
                    seen.add(t)
            for t in T.plant[d]:
                seen.discard(t)                        # a new cohort on the tile
            ht.append(keep)
        self.harv_tiles = ht

    _FIELDS = ("n", "plant", "events", "struct_by_day", "animals_by_day", "board", "harv_tiles", "removals", "land_day",
               "hands", "cum_sold")

    def to_dict(self):
        """the interface as plain JSON data (int tile keys become strings; cum_sold only for the opening days 0-10)"""
        return {"n": self.n,
                "plant": [{str(t): c for t, c in x.items()} for x in self.plant],
                "events": [list(e) for e in self.events],
                "struct_by_day": [{str(t): k for t, k in x.items()} for x in self.struct_by_day],
                "animals_by_day": [{str(t): a for t, a in x.items()} for x in self.animals_by_day],
                "board": [list(b) for b in self.board],
                "harv_tiles": [sorted(x) for x in self.harv_tiles],
                "removals": [[list(r) for r in x] for x in self.removals],
                "land_day": dict(self.land_day),
                "hands": list(self.hands),
                "cum_sold": [dict(list.__getitem__(self.cum_sold, d)) for d in range(min(self.n, TilePlanView.OPENING_LAST + 1))]}

    @classmethod
    def from_dict(cls, d):
        """sd_tp_file: a tile plan supplied as JSON data (the fields above, as to_dict writes them)"""
        v = cls.__new__(cls)
        n = int(d["n"])
        v.n = n
        v.plant = [{int(t): c for t, c in x.items()} for x in d["plant"]]
        v.events = [(int(e[0]), int(e[1]), e[2]) for e in d["events"]]
        v.struct_by_day = [{int(t): k for t, k in x.items()} for x in d["struct_by_day"]]
        v.animals_by_day = [{int(t): a for t, a in x.items()} for x in d["animals_by_day"]]
        v.board = [list(b) for b in d["board"]]
        v.harv_tiles = [set(int(t) for t in x) for x in d["harv_tiles"]]
        v.removals = [[(int(r[0]), r[1], int(r[2])) for r in x] for x in d["removals"]]
        v.land_day = {q: int(x) for q, x in d["land_day"].items()}
        v.hands = [int(h) for h in d["hands"]]
        cs = [Counter(x) for x in d.get("cum_sold", [])]
        v.cum_sold = TilePlanView._Opening(cs + [Counter() for _ in range(n - len(cs))])
        return v

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        _TP_LEAK[name] += 1
        n = self.__dict__.get("n", 30)
        if name == "fert":
            return [set() for _ in range(n)]
        if name == "maint":
            return [{} for _ in range(n)]
        if name == "cash":
            return [None] * n
        if name == "hire_steps":
            return {}
        return None


def configure(sem, **cfg):
    global _T, _S, _TGT_EP
    _T = Target(sem)
    _S = None
    _TGT_EP = (sem.get("meta") or {}).get("episode")
    _DSM_DATA.clear()
    CFG.update(cfg)
    _TP_LEAK.clear()
    if CFG.get("sd_tp_iface"):
        src_ = CFG.get("sd_tp_file")
        if src_:                                   # an external tile plan (a trained planner's output), JSON by episode
            import json as _j
            from pathlib import Path as _P
            pth_ = _P(src_) if _P(src_).is_absolute() else _P(__file__).resolve().parents[1] / src_
            plans_ = _j.loads(pth_.read_text(encoding="utf-8"))
            _T = TilePlanView.from_dict(plans_[str(_TGT_EP)] if str(_TGT_EP) in plans_ else plans_)
        else:
            _T = TilePlanView(_T)                  # KB115LT: the plan only through its interface


_TGT_EP = None
_DSM_DATA = {}
_FSHED = {"left": 0}                               # sd_tier_fert_shed: shed fertilizer the day's route pickups may still take


def _dawn_shape(day=None, tiles=None):
    """sd_tier_dawn_shape: the dict itself, "file" = results/fresh/threads_20260928/dsm_dawn/<ep>.json (build_dsm_dawn.py),
    or "learned" = today's trips from DSM's dawn rule (scripts/dsm_dawn_rule.py over 40 recordings) on our own board:
    pens ON a shed tile with cow >= 3 / sheep >= 4 / goose >= 4 units (DSM 75-98%), and in the early season (day <= 17)
    pens one tile off with sheep >= 4 / cow >= 6 (DSM 36-68%; later 2-20%); the farmer takes the first at hour 0, hires
    the rest from hour 1, at most sd_tier_dawn_learned_max a day"""
    v = CFG["sd_tier_dawn_shape"]
    if v == "file":
        return ((_dsm_data("dawn") or {}).get("days")) or {}
    if v in ("learned", "learned2"):
        if day is None or tiles is None:
            return {}
        l2_ = v == "learned2"
        ne_ = 0
        if l2_:                                   # the morning's eligible sheep pens (<= 2 tiles, >= 4 wool)
            for idx in range(100):
                t = _tile(tiles, idx)
                if _animal(t) and t["animal"] == "SHEEP" and int(t.get("yield_units", 0) or 0) >= 4 and \
                        min(abs(idx % 10 - a) + abs(idx // 10 - b) for a, b in SHED) <= 2:
                    ne_ += 1
        sync1_ = l2_ and ne_ >= int(CFG["sd_tier_dawn_sync_n"])
        sync2_ = l2_ and ne_ >= int(CFG["sd_tier_dawn_sync_n2"])
        cands, far_ = [], []
        for idx in range(100):
            t = _tile(tiles, idx)
            if not _animal(t):
                continue
            x, y = idx % 10, idx // 10
            d = min(abs(x - a) + abs(y - b) for a, b in SHED)
            u = int(t.get("yield_units", 0) or 0)
            an = t["animal"]
            mh_ = int(ANIMALS[an]["max_held"])
            if d == 0 and u >= {"COW": 3, "SHEEP": 4, "GOOSE": 4}[an]:
                cands.append((0, -u, idx, an))
            elif d == 1 and day <= 17 and u >= {"COW": 6, "SHEEP": 4}.get(an, 99):
                cands.append((1, -u, idx, an))
            elif d == 1 and sync1_ and an == "SHEEP" and 4 <= u < mh_:
                cands.append((1, -u, idx, an))
            elif d == 2 and sync2_ and an == "SHEEP" and 4 <= u < mh_:
                far_.append((2, -u, idx, an))
        cands.sort()
        cap_ = int(CFG["sd_tier_dawn_learned_max2"]) if sync2_ else int(CFG["sd_tier_dawn_learned_max"])
        trips = []
        for i, (d, _, idx, an) in enumerate(cands[:cap_]):
            sh = min(((a, b) for a, b in SHED), key=lambda q: abs(q[0] - idx % 10) + abs(q[1] - idx // 10))
            shi = sh[1] * 10 + sh[0]
            trips.append([0 if i == 0 else i, 0 if i == 0 else 1, shi, [[idx, an]], shi])
        for d, _, idx, an in sorted(far_):        # learned2: a 2-off pen joins the trip of an adjacent 1-off pen
            hit_ = next((tr for tr in trips if len(tr[3]) == 1 and abs(tr[3][0][0] % 10 - idx % 10)
                         + abs(tr[3][0][0] // 10 - idx // 10) == 1 and min(abs(tr[3][0][0] % 10 - a)
                         + abs(tr[3][0][0] // 10 - b) for a, b in SHED) == 1), None)
            if hit_ is not None:
                hit_[3].append([idx, an])
        return {str(day): trips}
    return v or {}


def _dsm_data(kind):
    """research copies only: per-episode leader data built by scripts/build_dsm_<kind>.py (None when missing)"""
    if CFG.get("sd_tp_iface"):                     # KB115LT: not part of the tile plan interface
        _TP_LEAK["dsm_data:" + kind] += 1
        return None
    if kind not in _DSM_DATA:
        _DSM_DATA[kind] = None
        try:
            import json as _j
            from pathlib import Path as _P
            f = _P(__file__).resolve().parents[1] / "results/fresh/threads_20260928" / ("dsm_" + kind) / ("%s.json" % _TGT_EP)
            _DSM_DATA[kind] = _j.loads(f.read_text(encoding="utf-8"))
        except Exception:
            _DSM_DATA[kind] = None
    return _DSM_DATA[kind]


def _books_cum(S):
    """sd_books_sell (leader source): the leader's cumulative sold units by step, from step 0 (S["_books_cum"])"""
    if S.get("_books_cum") is None:
        DS_ = _dsm_data("sales")
        if DS_ is None:
            return None
        cum_, run_ = {}, Counter()
        for t_ in range(0, 720):
            for p_, v_ in (DS_["steps"].get(str(t_)) or {}).items():
                run_[p_] += int(v_["n"])
            cum_[t_] = dict(run_)
        S["_books_cum"] = cum_
    return S["_books_cum"]


def _new_state():
    return {
        "pmap": {},        # (pd, T) -> our tile for a plant event
        "done": set(),     # fulfilled plant events (pd, T)
        "smap": {},        # target structure tile -> our tile
        "assign": {},      # unit -> tile idx
        "sold": Counter(),  # our cumulative sold units (issued)
        "day": -1,
        "log": Counter(),
        "tmax": 0.0,
        "owner": {},       # sem4 (exact_removals only): (pd, T) -> (our tile, planted_day) of the plant that fulfilled it
        "owned": set(),    # sem4: {(our tile, planted_day)} of those plants
        "rm": {},          # sem4: our tile -> crop, removals open now (empty unless exact_removals)
        "rm_prev": {},     # sem4: open removals at the previous call (log only)
        "rm_seen": set(),  # sem4: (key, dd) removals already counted as issued (log only)
    }


# --------------------------------------------------------------------------- helpers

def _g(o, k, default=None):
    try:
        v = o[k]
        return default if v is None else v
    except (KeyError, TypeError, IndexError):
        return getattr(o, k, default)


def _tile(tiles, idx):
    return tiles[idx // 10][idx % 10]


def _dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _near_shed(p):
    return min(SHED, key=lambda q: (_dist(p, q), q))


def _step_toward(p, q):
    dx, dy = q[0] - p[0], q[1] - p[1]
    if dx:
        return [MOVES[(1 if dx > 0 else -1, 0)]]
    if dy:
        return [MOVES[(0, 1 if dy > 0 else -1)]]
    return ["PASS"]


def _is_plant(t):
    return isinstance(t, dict) and t.get("kind") == "PLANT"


def _is_weed(t):
    return isinstance(t, dict) and t.get("kind") == "WEED"


def _animal(t):
    return t.get("animal") if isinstance(t, dict) else None


def _ongoing_last_age(crop):
    c = CROPS[crop]
    return c["first"] + c["interval"] * (c["max"] - 1)


def _plant_state(t, day):
    """returns (age, harvestable_now, finished)"""
    c = CROPS[t["crop"]]
    age = day - t["planted_day"]
    if c["ongoing"]:
        last = _ongoing_last_age(t["crop"])
        finished = (age >= last and t.get("yield_units", 0) <= 0) or age > last + 1
        return age, t.get("yield_units", 0) > 0 and age >= c["first"], finished
    return age, age >= c["first"], False


def _onetime_should_harvest(t, day):
    c = CROPS[t["crop"]]
    age = day - t["planted_day"]
    if age < c["first"]:
        return False
    if age >= c["maxday"]:
        return True
    y = t.get("yield_units", 0)
    if y >= c["max"]:
        return True
    # remaining possible gain
    fert = t.get("fertilized_until_day", -1) >= day
    return False if fert else (y >= _unfert_max(t["crop"]))


def _unfert_max(crop):
    c = CROPS[crop]
    ws = (c["maxday"] + 1) // 2
    return min(c["max"], 1 + (c["maxday"] - ws + 1))


def _water_needed(t, day, last_day):
    """(needed, urgent)"""
    if t.get("watered_today"):
        return False, False
    c = CROPS[t["crop"]]
    age = day - t["planted_day"]
    if day >= last_day:
        # final day: only yield-adding water on one-time crops matters
        if not c["ongoing"]:
            ws = (c["maxday"] + 1) // 2
            return ws <= age <= c["maxday"], False
        return False, False
    if t.get("consecutive_unwatered", 0) >= 1:
        return True, True
    if not CFG["smart_water"]:
        return True, False
    if not c["ongoing"]:
        ws = (c["maxday"] + 1) // 2
        return ws <= age <= c["maxday"], False
    # ongoing: water on a fertilized production day
    fert = t.get("fertilized_until_day", -1) >= day
    if fert:
        k = (day + 1) - t["planted_day"] - c["first"]
        if k >= 0 and k % c["interval"] == 0 and k // c["interval"] + 1 <= c["max"]:
            return True, False
    return False, False


# =========================================================================== PLANNER (target -> tile jobs)

def _free_tile(tiles, near, reserved):
    best = None
    for idx in range(100):
        if idx in reserved:
            continue
        t = _tile(tiles, idx)
        if t == "LOCKED":
            continue
        if t is None or _is_weed(t):
            key = (_dist((idx % 10, idx // 10), near) + (1 if t is not None else 0), idx)
            if best is None or key < best[0]:
                best = (key, idx)
    return None if best is None else best[1]


def _remaining_prods(t, day):
    """productions of our plant still to come after today's visible yield (ongoing: production ages > age;
    one-time: 1 before its first harvestable day, else 0 -- the harvest-first rule takes the current yield)."""
    c = CROPS[t["crop"]]
    age = day - t["planted_day"]
    if c["ongoing"]:
        return sum(1 for k in range(c["max"]) if c["first"] + c["interval"] * k > age)
    return 1 if age < c["first"] else 0


def _removals(S, tiles, d, day):
    """sem4 exact removals open now: {our tile: crop} and {leader tile: (our tile, removal day)}.
    The leader's DIG of cohort (pd, tt) on day dd (d - rm_late <= dd <= d) is issued on our tile for that cohort
    (the tile whose plant fulfilled the event; else pmap, default tt) while that tile still holds the plant: same
    crop, planted before dd, and (when known) the very plant that fulfilled the event; without an owner record
    only a plant planted on / after pd that no other event owns."""
    T = _T
    out, by_lt, lg = {}, {}, S["log"]
    for dd in range(max(0, d - CFG["rm_late"]), d + 1):
        for (tt, crop, pd) in T.removals[dd]:
            key = (pd, tt)
            own = S["owner"].get(key)
            m = own[0] if own else S["pmap"].get(key, tt)
            cur = _tile(tiles, m)
            if not (_is_plant(cur) and cur["crop"] == crop and cur["planted_day"] < dd):
                continue
            if own is not None:
                if cur["planted_day"] != own[1]:
                    continue
            elif cur["planted_day"] < pd or (m, cur["planted_day"]) in S["owned"]:
                continue
            out[m] = crop
            by_lt[tt] = (m, dd)
            if (key, dd) not in S["rm_seen"]:
                S["rm_seen"].add((key, dd))
                lg["rm_issued_" + crop] += 1
                lg["rm_forfeit_prods"] += _remaining_prods(cur, day)
                if dd < d:
                    lg["rm_issued_late"] += 1
    # removals no longer open: the plant is gone (dug by us, harvested, died) or the window closed
    for m, (crop, pday) in S["rm_prev"].items():
        if m not in out:
            cur = _tile(tiles, m)
            gone = not (_is_plant(cur) and cur["crop"] == crop and cur["planted_day"] == pday)
            lg[("rm_gone_" if gone else "rm_expired_") + crop] += 1
    S["rm_prev"] = {m: (c, _tile(tiles, m)["planted_day"]) for m, c in out.items()}
    return out, by_lt


def _exact_retire(S, tiles, d):
    """sd_exact_retire: our animals to let go today {our tile: escapes tonight (bool)}: our animal on a tile that maps to a
    tile of DSM's (identity or smap) where DSM's animal of the same species is not alive at the next morning or the one
    after (DSM left it unfed: the escape needs 2 unfed days)."""
    T = _T
    last = T.n - 1
    if int(CFG["sd_exact_retire"]) >= 2 and d >= 27:
        return {}
    inv = {}
    struct_tiles = set()
    for dd in range(T.n):
        struct_tiles.update(T.struct_by_day[dd])
    for tt in struct_tiles:
        if S["smap"].get(tt, tt) == tt:
            inv.setdefault(tt, tt)
    for tt, m in S["smap"].items():
        inv[m] = tt
    out = {}
    must = S["_xfeed"] = set()
    for m, tt in inv.items():
        t = _tile(tiles, m)
        if not _animal(t) or t.get("fed_today"):
            continue
        sp = t["animal"]
        a1 = T.animals_by_day[d].get(tt) == sp
        a2 = T.animals_by_day[min(d + 1, last)].get(tt) == sp
        if not (a1 and a2):
            out[m] = not a1
        elif (CFG["sd_exact_retire_prefeed"] and d + 2 <= last and T.animals_by_day[d + 2].get(tt) != sp
              and not (int(CFG["sd_exact_retire"]) >= 2 and d + 2 >= 27)):
            must.add(m)                          # DSM's escapes at night d + 2: fed today, unfed d + 1 and d + 2
    return out


def _own_retire(tiles, d):
    """sd_own_retire (see the flag): {our tile: escapes tonight} for our animals with no production night left that can
    still reach the market (production at the end of night n: n + 1 - placed - first >= 0 and divisible by the interval;
    useful nights d .. last - 1)."""
    last = _T.n - 1
    out = {}
    if d >= last:
        return out
    for m in range(100):
        t = _tile(tiles, m)
        if not _animal(t):
            continue
        a = ANIMALS[t["animal"]]
        pd_ = int(t.get("placed_day", d))
        if any(n + 1 - pd_ - a["first"] >= 0 and (n + 1 - pd_ - a["first"]) % a["interval"] == 0 for n in range(d, last)):
            continue
        out[m] = int(t.get("consecutive_unfed", 0) or 0) >= 1 and not t.get("fed_today")
    return out


def _plan(obs, S, tiles, day):
    """Structural jobs for today: {our_idx: job} where job = ('PLANT', crop, event) |
    ('BUILD', kind) | ('PLACE', species) (a BUILD may carry a place species) | ('REMOVE', crop) (sem4)."""
    T = _T
    jobs = {}
    last = T.n - 1
    d = min(day, last)
    rm, rm_lt = ({}, {})
    if CFG["exact_removals"]:
        rm, rm_lt = _removals(S, tiles, d, day)
    S["rm"] = rm
    if CFG["sd_exact_retire"] and not CFG["sd_clean_plan"]:
        S["_xretire"] = _exact_retire(S, tiles, d)
    elif CFG["sd_own_retire"]:
        S["_xretire"] = _own_retire(tiles, d)       # sd_own_retire: our rule, no DSM escapes
    else:
        S["_xretire"] = {}
    # reserve target tiles used for structural work in the next days (keep the layout free)
    reserved = set()
    for dd in range(d, min(last, d + 2) + 1):
        for t in T.plant[dd]:
            reserved.add(t)
    for t in T.struct_by_day[d]:
        reserved.add(S["smap"].get(t, t))
    # structures + animals
    want_struct = T.struct_by_day[d]
    want_animal = T.animals_by_day[d]
    for tt, kind in want_struct.items():
        m = S["smap"].get(tt, tt)
        cur = _tile(tiles, m)
        if cur == "LOCKED":
            continue
        if isinstance(cur, dict) and cur.get("kind") == kind:
            sp = want_animal.get(tt)
            if sp and not _animal(cur):
                jobs[m] = ("PLACE", sp)
            continue
        ok = cur is None or _is_weed(cur)
        if not ok and _is_plant(cur):
            age, harv, fin = _plant_state(cur, day)
            ok = fin or (not CROPS[cur["crop"]]["ongoing"] and harv)
            if not ok and m in rm:
                ok = True                    # sem4: the leader removes this plant today; build after the removal
        if not ok and tt in rm_lt and rm_lt[tt][0] not in jobs:
            m = rm_lt[tt][0]                 # sem4: our tile of the cohort the leader removed from tt
            S["smap"][tt] = m
            reserved.add(m)
            ok = True
        if not ok and CFG["sd_exact_site"] and isinstance(cur, dict):
            if _is_plant(cur) or ("animal" not in cur and cur.get("kind") in ("COOP", "PASTURE")):
                ok = True                    # sd_exact_site: harvest / dig ours, build on DSM's tile
                S["log"]["xsite_struct_" + str(cur.get("crop") or cur.get("kind"))] += 1
            elif _animal(cur) and m in S.get("_xretire", {}):
                S["log"]["xsite_struct_wait"] += 1
                continue                     # our animal escapes tonight / tomorrow night (DSM's did): wait
        if not ok:
            m2 = _free_tile(tiles, (tt % 10, tt // 10), reserved | set(jobs))
            if m2 is None:
                continue
            S["smap"][tt] = m2
            m = m2
            reserved.add(m2)
        jobs[m] = ("BUILD", kind, want_animal.get(tt))
    # plantings (today's events + recent catch-up)
    cut = CFG["plant_cutoff"]
    d3_ = bool(CFG["sd_wheat_d3"])
    d3a_ = int(CFG["sd_wheat_d3_ahead"]) if d3_ else 0
    wown_ = S.setdefault("_wown", set())            # sd_wheat_d3: (our tile, planting day) already credited to an event
    for (pd, tt, crop) in T.events:
        early_ = False
        if d3_ and crop == "WHEAT" and d < pd <= d + d3a_ and (pd, tt) not in S["done"]:
            m_e = S["pmap"].get((pd, tt), tt)
            t_e = _tile(tiles, m_e)
            if (m_e not in jobs and _is_plant(t_e) and t_e["crop"] == "WHEAT" and day - int(t_e["planted_day"]) >= 3
                    and int(t_e.get("yield_units", 0) or 0) > 0):
                early_ = True                    # our wheat can be harvested and the tile replanted ahead of DSM
        late_ = CFG["late"].get(crop, LATE[crop]) + (d3a_ if crop == "WHEAT" else 0)
        if not early_ and (pd > d or d - pd > late_):
            if (CFG["pf_log"] and pd <= d and d - pd == CFG["late"].get(crop, LATE[crop]) + 1
                    and (pd, tt) not in S["done"]):
                _pf_set(S, (pd, tt), crop, d, "window_expired")
            continue
        if cut and d > cut.get(crop, 99) and not (
                CFG["cut_mode"] == "leader_harvest" and not CFG["sd_clean_plan"]
                and any(tt in T.harv_tiles[d2] for d2 in range(pd + 1, T.n) if d2 < len(getattr(T, "harv_tiles", ())))):
            ck = ("cut", pd, tt)
            if ck not in S["done"]:
                S["done"].add(ck)
                S["log"]["cut_" + crop] += 1       # would-be planting skipped: no full harvest reachable
                if CFG["pf_log"]:
                    _pf_set(S, (pd, tt), crop, d, "plant_cutoff")
            continue
        key = (pd, tt)
        if key in S["done"]:
            continue
        if pd < d and not CFG["sd_clean_plan"] and T.board[d][tt] != CROP_LABEL[crop]:
            if CFG["pf_log"]:
                _pf_set(S, key, crop, d, "cohort_gone")
            continue  # the target's own cohort is gone; no catch-up
        m = S["pmap"].get(key, tt)
        cur = _tile(tiles, m)
        why_ = None
        if (d3_ and crop == "WHEAT" and _is_plant(cur) and cur["crop"] == crop
                and pd - d3a_ <= cur["planted_day"] < pd and (m, cur["planted_day"]) not in wown_
                and cur["planted_day"] > max((p_ for (p_, t2_, c2_) in T.events if t2_ == tt and p_ < pd), default=-1)):
            S["done"].add(key)                   # sd_wheat_d3: our replant ahead of DSM's fulfils his planting
            wown_.add((m, cur["planted_day"]))
            S["log"]["wheat_d3_credit"] += 1
            continue
        if early_:
            if m in jobs or m != S["pmap"].get(key, tt):
                continue
            jobs[m] = ("PLANT", crop, key, "d3")
            S["log"]["wheat_d3_offer"] += 1
            continue
        if _is_plant(cur) and cur["crop"] == crop and cur["planted_day"] >= pd:
            if d3_ and crop == "WHEAT":
                wown_.add((m, cur["planted_day"]))
            if CFG["pf_log"]:
                _pf_set(S, key, crop, d, "planted", tile=m, planted_day=cur["planted_day"], remapped=(m != tt))
            S["done"].add(key)
            if CFG["exact_removals"]:        # sem4 bookkeeping: which plant fulfilled this event
                S["owner"][key] = (m, cur["planted_day"])
                S["owned"].add((m, cur["planted_day"]))
            continue
        if m in jobs:
            m = None
            why_ = "tile_taken_by_another_job"
        if m is not None:
            if cur == "LOCKED":
                m = None
                why_ = "locked"
            elif cur is None or _is_weed(cur):
                pass
            elif _is_plant(cur):
                age, harv, fin = _plant_state(cur, day)
                c = CROPS[cur["crop"]]
                # xfix replant_leader: the leader harvested this very crop on this tile today / yesterday to replant it
                # (melons at age 10, wheat at age 2): harvest now and plant here instead of remapping the planting
                lead_rp = (CFG["replant_leader"] and not CFG["sd_clean_plan"] and m == tt and not c["ongoing"] and harv
                           and cur.get("yield_units", 0) > 0 and T.board[d][tt] == CROP_LABEL.get(cur["crop"])
                           and any(tt in hs for hs in getattr(T, "harv_tiles", [])[max(0, d - 1):d + 1]))
                if lead_rp and (pd, tt) not in S.setdefault("rp_seen", set()):
                    S["rp_seen"].add((pd, tt))
                    S["log"]["replant_leader_" + cur["crop"]] += 1
                if not (fin or (not c["ongoing"] and harv and age >= c["maxday"] - 1) or m in rm or lead_rp):
                    if CFG["sd_exact_site"] and cur["crop"] != crop:
                        S["log"]["xsite_plant_over_" + cur["crop"]] += 1   # harvest / dig ours, plant on DSM's tile
                    elif int(CFG["sd_exact_site"]) >= 2 and cur["crop"] == crop:
                        S["log"]["xsite_plant_wait_" + crop] += 1          # same crop: ours stands in (our timing)
                        continue
                    else:
                        m = None
                        why_ = "live_%s_age%d_%s" % (cur["crop"], age, "harvestable" if harv else "growing")
            elif CFG["sd_exact_site"] and isinstance(cur, dict) and "animal" not in cur and cur.get("kind") in ("COOP", "PASTURE"):
                S["log"]["xsite_plant_over_" + cur["kind"]] += 1           # dig our empty structure, plant on DSM's tile
            elif CFG["sd_exact_site"] and _animal(cur) and m in S.get("_xretire", {}):
                S["log"]["xsite_plant_wait_animal"] += 1
                continue                                                   # our animal escapes (as DSM's did): wait
            else:
                m = None
                why_ = "structure"
        if m is None and tt in rm_lt and pd >= rm_lt[tt][1] and rm_lt[tt][0] not in jobs:
            m = rm_lt[tt][0]                 # sem4: plant on our tile of the cohort the leader removed from tt
            S["pmap"][key] = m
        if m is None:
            if cur == "LOCKED" and _T.land_day.get(_quad(tt % 10, tt // 10), 99) <= day:
                if CFG["pf_log"]:
                    _pf_set(S, key, crop, d, "wait_land")
                continue  # land coming (we buy it today); wait rather than remap
            m2 = _free_tile(tiles, (tt % 10, tt // 10), reserved | set(jobs))
            if m2 is None:
                if CFG["pf_log"]:
                    _pf_set(S, key, crop, d, "no_free_tile", why=why_)
                continue
            S["pmap"][key] = m2
            m = m2
            if CFG["pf_log"]:
                _pf_set(S, key, crop, d, "job", tile=m, remap=why_)
        elif CFG["pf_log"]:
            _pf_set(S, key, crop, d, "job", tile=m)
        jobs[m] = ("PLANT", crop, key)
    for m, crop in rm.items():               # sem4: removals with no planting / structure on the tile today
        if m not in jobs:
            jobs[m] = ("REMOVE", crop)
    if CFG["harvest_source"] == "leader":
        lh = set()
        for tt in getattr(T, "harv_tiles", [set()] * T.n)[d] if d < T.n else ():
            last = max((pd for (pd, t2, c2) in T.events if t2 == tt and pd < d), default=None)
            lh.add(S["pmap"].get((last, tt), tt) if last is not None else tt)
        S["lead_harv"] = lh
    # fertilize targets (mapped)
    fert = set()
    for tt in (T.fert[d] if CFG["fert_follow"] else ()):
        m = tt
        for (pd, t2), mm in S["pmap"].items():
            if t2 == tt:
                m = mm
        fert.add(m)
    if CFG["maint_source"] == "leader":
        mp = {}
        for (pd, t2), mm in S["pmap"].items():
            mp[t2] = mm
        mp.update({k: v for k, v in S["smap"].items()})
        lm = getattr(T, "maint", None)
        S["lmaint"] = {op: {mp.get(tt, tt) for tt in ts} for op, ts in (lm[d] if lm else {}).items()}
    return jobs, fert


def _tile_ops(idx, t, job, fert, day, last_day, seeds):
    """ordered ops for our tile now; also the items the sequence needs and a priority."""
    ops, need, prio = [], Counter(), 3
    rm_here = _S is not None and idx in _S.get("rm", ()) and _is_plant(t)    # sem4 exact removal on this tile
    if job is not None:
        kind = job[0]
        if kind == "REMOVE" or (kind == "PLANT" and rm_here and seeds.get(job[1], 0) <= 0):
            # sem4: harvest first when there is harvestable yield (the leader harvests before digging), then DIG
            # (a one-time crop's harvest already clears the tile); a planting waiting for seeds still removes
            if rm_here:
                age, harv, fin = _plant_state(t, day)
                if harv and t.get("yield_units", 0) > 0:
                    ops.append(["HARVEST"])
                    if CROPS[t["crop"]]["ongoing"]:
                        ops.append(["DIG"])
                else:
                    ops.append(["DIG"])
                return ops, need, 0
        elif kind == "PLANT" and rm_here and not _plant_state(t, day)[2] \
                and not (not CROPS[t["crop"]]["ongoing"] and _plant_state(t, day)[1]):
            # sem4: a live plant the leader removes today, then the leader's planting on the tile
            crop = job[1]
            age, harv, fin = _plant_state(t, day)
            if harv and t.get("yield_units", 0) > 0:
                ops.append(["HARVEST"])
            ops += [["DIG"], ["PLANT", crop], ["WATER"]]
            return ops, need, 0
        if kind == "PLANT":
            crop = job[1]
            if seeds.get(crop, 0) <= 0:
                pass  # wait for seeds; still do maintenance below
            elif t is None:
                ops += [["PLANT", crop], ["WATER"]]
                prio = 0
            elif _is_weed(t):
                ops += [["DIG"], ["PLANT", crop], ["WATER"]]
                prio = 0
            elif _is_plant(t):
                age, harv, fin = _plant_state(t, day)
                c = CROPS[t["crop"]]
                if fin:
                    ops += [["DIG"], ["PLANT", crop], ["WATER"]]
                    prio = 0
                elif not c["ongoing"] and harv:
                    ws = (c["maxday"] + 1) // 2
                    if not t.get("watered_today") and ws <= age <= c["maxday"]:
                        ops += [["WATER"]]
                    ops += [["HARVEST"], ["PLANT", crop], ["WATER"]]
                    prio = 0
            if ops:
                return ops, need, prio
        elif kind == "BUILD":
            k, sp = job[1], job[2]
            if t is None:
                ops += [["BUILD_" + k]]
            elif _is_weed(t) or _is_plant(t):
                if _is_plant(t):
                    c = CROPS[t["crop"]]
                    if not c["ongoing"] and _plant_state(t, day)[1]:
                        if CFG["harvest_before_build"]:
                            return [["HARVEST"]], need, 0
                        ops += [["HARVEST"]]
                    else:
                        if rm_here and c["ongoing"] and _plant_state(t, day)[1]:
                            ops += [["HARVEST"]]     # sem4: the leader harvests before digging
                        ops += [["DIG"]]
                else:
                    ops += [["DIG"]]
                ops += [["BUILD_" + k]]
            if sp:
                ops += [["PLACE", sp], ["FEED"], ["CARE"]]
                need[sp] += 1
                need["WHEAT"] += 1
            return ops, need, 0
        elif kind == "PLACE":
            sp = job[1]
            if isinstance(t, dict) and not _animal(t):
                ops += [["PLACE", sp], ["FEED"], ["CARE"]]
                need[sp] += 1
                need["WHEAT"] += 1
                return ops, need, 0
    if CFG["sched_maint"] and _S is not None and (_is_plant(t) or _animal(t)):
        r = _sched_tile_ops(idx, t, day)
        if r is not None:
            if (CFG["fert_follow"] and _is_plant(t) and idx in fert and day < last_day
                    and t.get("fertilized_until_day", -1) < day and not any(o[0] == "FERTILIZE" for o in r[0])):
                # xfix fert_follow: the leader fertilizes this tile today (its plan's FERTILIZE list, mapped to our tile)
                need2 = Counter(r[1])
                need2["FERTILIZER"] += 1
                v0, dl0 = _S["tval"].get(idx, (0.0, 23))
                pr = (_S.get("prices") or {}).get(t["crop"], 0) or 0
                _S["tval"][idx] = (v0 + 2.0 * float(pr), dl0)
                return [["FERTILIZE"]] + list(r[0]), need2, min(r[2], CFG["fert_follow_prio"])
            return r
    if _is_plant(t):
        c = CROPS[t["crop"]]
        age = day - t["planted_day"]
        own_fert = False
        lm = _S.get("lmaint") if (CFG["maint_source"] == "leader" and _S) else None
        if CFG["fert_ongoing"] and c["ongoing"] and day < last_day - 1:
            # a production falls within the 3 fertilized days and the plant is not finished
            last = _ongoing_last_age(t["crop"])
            for k in range(3):
                a = age + k + 1  # production visible at age a happens at the end of day+k
                if c["first"] <= a <= last and (a - c["first"]) % c["interval"] == 0:
                    own_fert = True
                    break
        if lm is not None:
            own_fert = False
        if (idx in fert or own_fert) and t.get("fertilized_until_day", -1) < day and day < last_day:
            ops.append(["FERTILIZE"])
            need["FERTILIZER"] += 1
            prio = min(prio, CFG["fert_prio"])
        wn, urgent = _water_needed(t, day, last_day)
        if lm is not None:
            cu1 = t.get("consecutive_unwatered", 0) >= 1 and day < last_day
            wn = (idx in lm.get("WATER", ()) or (CFG["maint_safety"] and cu1)) and not t.get("watered_today")
            urgent = wn and cu1
        if wn:
            ops.append(["WATER"])
            # a window water on a one-time crop adds a unit (melon ~ $200): treat as urgent
            valuable = (not c["ongoing"]) and CFG["window_urgent"] and t["crop"] in CFG["window_urgent"]
            if CFG["prio3"]:
                hard = (not c["ongoing"]) and t["crop"] in CFG["window_p0"]
                prio = min(prio, 0 if (urgent or (valuable and hard)) else 1 if valuable else 2)
            else:
                prio = min(prio, 1 if (urgent or valuable) else 2)
        if c["ongoing"]:
            if t.get("yield_units", 0) > 0 and age >= c["first"]:
                ops.append(["HARVEST"])
                risk = age >= _ongoing_last_age(t["crop"]) or t.get("yield_units", 0) >= c["max"] - 1 or day >= last_day - 1
                prio = min(prio, 1 if (risk or not CFG["prio3"]) else 2)
        else:
            if age >= c["first"]:
                # harvest after today's water when nothing more can be gained
                y = t.get("yield_units", 0)
                ws = (c["maxday"] + 1) // 2
                will_water = wn and ws <= age <= c["maxday"]
                bonus = (2 if t.get("fertilized_until_day", -1) >= day else 1) if will_water else 0
                tt = dict(t)
                tt["yield_units"] = min(c["max"], y + bonus)
                if (_onetime_should_harvest(tt, day) or (day >= last_day)
                        or (CFG["harvest_source"] == "leader" and t["crop"] in ("WHEAT", "CARROT") and y > 0
                            and _S is not None and idx in _S.get("lead_harv", ()))):
                    ops.append(["HARVEST"])
                    prio = min(prio, 1)
    elif _animal(t):
        if day < last_day:
            lma = _S.get("lmaint") if (CFG["maint_source"] == "leader" and _S) else None
            if not t.get("fed_today") and (lma is None or idx in lma.get("FEED", ())
                                           or (CFG["maint_safety"] and t.get("consecutive_unfed", 0) >= 1)):
                ops.append(["FEED"])
                need["WHEAT"] += 1
                if CFG["prio3"]:
                    prio = min(prio, 0 if t.get("consecutive_unfed", 0) >= 1 else 1)
                else:
                    prio = min(prio, 1 if t.get("consecutive_unfed", 0) >= 1 else 2)
            if not t.get("cared_today") and (lma is None or idx in lma.get("CARE", ())):
                ops.append(["CARE"])
                prio = min(prio, 2)
        if t.get("fertilizer_available"):
            ops.append(["COLLECT_FERTILIZER"])
            prio = min(prio, 2)
        if t.get("yield_units", 0) > 0:
            ops.append(["HARVEST"])
            risk = t.get("yield_units", 0) >= ANIMALS[t["animal"]]["max_held"] - 2 or day >= last_day - 1
            prio = min(prio, 1 if (risk or not CFG["prio3"]) else 2)
    return ops, need, prio


def _pf_set(S, key, crop, d, st, **kw):
    """xfix pf_log (logging only): the leader planting event's status on day d (the day's last call wins; the first
    remap reason is kept)."""
    r = S.setdefault("pf", {}).setdefault(key, {"crop": crop, "pd": key[0], "tt": key[1], "days": {}})
    r["days"][d] = st
    for k, v in kw.items():
        if k == "remap" and r.get("remap"):
            continue
        r[k] = v


def _hp_window(t, day, idx):
    """xfix harvest_policy leader_tendency: is this plant inside the leaders' harvest window today?"""
    c = CROPS[t["crop"]]
    age = day - t["planted_day"]
    if age < c["first"] or t.get("yield_units", 0) <= 0 or t["crop"] not in CFG["hp_crops"]:
        return False
    if c["ongoing"]:
        return True                                   # every production (a next-morning sale is fine)
    if t["crop"] == "MELON":
        return True                                   # the first allowed day
    if t["crop"] == "WHEAT":
        if day <= 11:
            return age >= 2 and _S is not None and idx in _S.get("hp_jobs", ())   # early only where the plan replants
        mu = int(CFG.get("hp_wheat_min_units", 0) or 0)
        if mu and age < c["maxday"]:
            # hp_wheat_min_units (wheat cycle): before the max-yield age only once today's water brings it to mu units
            # (fertilized wheat: 5 at age 3); unfertilized wheat keeps growing to its age-4 harvest
            exp = int(t.get("yield_units", 0)) + (0 if t.get("watered_today") else
                                                 (2 if int(t.get("fertilized_until_day", -1)) >= day else 1))
            return age >= 3 and min(exp, c["max"]) >= mu
        return age >= 3
    if t["crop"] == "CARROT":
        return age >= 3
    return False


def _sched_done(cmd, t, day):
    if cmd == "WATER":
        return bool(t.get("watered_today"))
    if cmd == "FEED":
        return bool(t.get("fed_today"))
    if cmd == "CARE":
        return bool(t.get("cared_today"))
    if cmd == "FERTILIZE":
        return t.get("fertilized_until_day", -1) >= day + 2
    if cmd == "HARVEST":
        return t.get("yield_units", 0) <= 0
    if cmd == "COLLECT_FERTILIZER":
        return not t.get("fertilizer_available")
    return False


def _sched_tile_ops(idx, t, day):
    """maintenance ops of our live asset from the value/deadline job list (sem_maintenance)."""
    S = _S
    asset = t.get("crop") if _is_plant(t) else t.get("animal")
    start = t.get("planted_day") if _is_plant(t) else t.get("placed_day")
    if (idx, asset, start) not in S.get("mj_known", ()):
        return None          # planted / placed after the last solve: our own rules until the next refresh
    ops, need, prio, val, dl = [], Counter(), 3, 0.0, 23
    for j in sorted(S.get("mj", {}).get(idx, ()), key=lambda j: j.get("order", 0)):
        if j.get("asset") != asset:
            continue
        cmd = j["cmd"]
        if _sched_done(cmd, t, day):
            continue
        if j.get("optional"):
            # early harvest only where the yield keeps accruing anyway (animals, strawberry / tomato); a one-time
            # crop's harvest ends the plant, so it waits for the module's required harvest -- unless early_onetime
            # (y3-style: wheat / carrot from one day before full yield, replanted the same day by the target)
            lead_h = (CFG["harvest_source"] == "leader" and _is_plant(t) and t["crop"] in ("WHEAT", "CARROT")
                      and idx in S.get("lead_harv", ()))
            hpw = CFG["harvest_policy"] == "leader_tendency" and _is_plant(t) and _hp_window(t, day, idx)
            if _is_plant(t) and not CROPS[t["crop"]]["ongoing"] and not lead_h and not hpw:
                c_ = CROPS[t["crop"]]
                if not (CFG["early_onetime"] and t["crop"] in ("WHEAT", "CARROT")
                        and day - t["planted_day"] >= c_["maxday"] - 1):
                    continue
            frac = 1.0 if lead_h else (CFG["hp_frac"] if hpw else CFG["opt_harvest_frac"])
            v = float(j.get("held", 0)) * float(j.get("price", 0)) * frac
            if lead_h:
                S["log"]["lead_harvest_" + t["crop"]] += 1
            if hpw:
                S["log"]["hp_harvest_op_" + t["crop"]] += 1
        else:
            v = max(0.0, float(j.get("value", 0.0)))
            if (cmd == "HARVEST" and CFG["harvest_policy"] == "leader_tendency" and _is_plant(t)
                    and _hp_window(t, day, idx)):
                # xfix harvest_policy: a harvest the module keeps at ~0 (same units tomorrow at a constant price) is
                # worth its units now inside the leaders' window (melons race to the market; the tile is replanted)
                v = max(v, float(t.get("yield_units", 0)) * float(j.get("price", 0)) * CFG["hp_frac"])
            if cmd in ("FEED", "CARE") and CFG["upkeep_scale"] != 1.0 and j.get("kind") != "survival":
                v *= CFG["upkeep_scale"]      # xfix: the module's per-job FEED / CARE losses double-count the pair
            if cmd in ("FEED", "CARE") and CFG.get("sd_feed_bonus") and _animal(t):
                v += float(CFG["sd_feed_bonus"])
            if cmd == "COLLECT_FERTILIZER" and CFG["sd_collect_floor"]:
                v = max(v, float(CFG["sd_collect_floor"]))   # sd_collect_floor
        vp = v
        if CFG["fert_gross"] and cmd == "FERTILIZE":
            # xfix fert_gross: judge a fertilize on its gross value (the fertilizer in hand is sunk / depth-priced)
            vp = max(v, float(j.get("units", 0) or 0) * float(j.get("price", 0) or 0))
        ops.append([cmd])
        for k, n in (j.get("needs") or {}).items():
            need[k] += n
        val += v
        if v > 0:
            dl = min(dl, int(j.get("deadline", 23)))
        if CFG.get("maint_goal") == "max_production":
            prio = min(prio, 0 if j.get("kind") == "survival" else 1 if (j.get("units", 0) > 0 or vp > CFG["p1_min_value"]) else 2)
        else:
            prio = min(prio, 0 if j.get("kind") == "survival" else 1 if vp > CFG["p1_min_value"] else 2)
    if (CFG["harvest_policy"] == "leader_tendency" and _is_plant(t) and t["crop"] == "MELON" and "MELON" in CFG["hp_crops"]
            and 6 <= day - t["planted_day"] <= 10 and t.get("yield_units", 0) < CROPS["MELON"]["max"]
            and not t.get("watered_today") and day < 29):
        # xfix harvest_policy: every melon window water counts toward 6 units at age 10 (the leaders harvest at the first
        # allowed day and sell that morning; the module sees the cap reached by age 12 anyway and values it ~0)
        pm = float((S.get("prices") or {}).get("MELON", 0) or 0) or 200.0
        if not any(o[0] == "WATER" for o in ops):
            ops.append(["WATER"])
            S["log"]["hp_melon_water_added"] += 1
        val += pm
        prio = min(prio, 1)
    if _is_plant(t) and not CROPS[t["crop"]]["ongoing"] and t.get("yield_units", 0) > 0 \
            and day - t["planted_day"] >= CROPS[t["crop"]]["maxday"] and any(o[0] == "HARVEST" for o in ops):
        S.setdefault("atrisk", set()).add(idx)
    # CARE pays only when fed: keep FEED before CARE on the tile
    ops.sort(key=lambda o: {"FERTILIZE": 0, "FEED": 0, "WATER": 1, "CARE": 1, "HARVEST": 2, "COLLECT_FERTILIZER": 3}.get(o[0], 5))
    S["tval"][idx] = (val, dl)
    return ops, need, prio


def _first_need(ops, inv):
    """items the ops before (and including) the first item-consuming op need that inv lacks."""
    need = Counter()
    for op in ops:
        c = op[0]
        k = "WHEAT" if c == "FEED" else "FERTILIZER" if c == "FERTILIZE" else op[1] if c == "PLACE" else None
        if k is None:
            continue
        need[k] += 1
        return [k] if inv.get(k, 0) < need[k] else []
    return []


# =========================================================================== EXECUTOR + MARKET
# Target-agnostic except: _market reads _T.cum_sold / _T.hands / _T.land_day / _T.fert (sell quota, hires, land).


def agent(obs, config=None):
    global _S
    t0 = time.time()
    if CFG["dispatch_search"] != "off":   # SEARCH DISPATCH HOOK 4
        _SD_T[:] = [t0]
    step = int(_g(obs, "step", 0))
    if _S is None or step == 0 or step < _S.get("last_step", -1):
        _S = _new_state()
    S = _S
    S["last_step"] = step
    me = int(_g(obs, "player", 0))
    farm = _g(obs, "farms")[me]
    private = _g(obs, "private", {})
    day, hour = divmod(step, 24)
    last_day = 29
    tiles = farm["tiles"]
    money = float(farm["money"])
    shed = Counter({k: int(v) for k, v in dict(_g(private, "shed", {})).items() if v})
    seeds = Counter({k: int(v) for k, v in dict(_g(private, "seeds", {})).items() if v})
    invs = [Counter({k: int(v) for k, v in dict(i).items() if v}) for i in _g(private, "inventories", [])]
    pos = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
    while len(invs) < len(pos):
        invs.append(Counter())
    prices = dict(_g(_g(obs, "market", {}), "prices", {}))
    if CFG["sd_glut_stop"]:                         # sticky glut: trailing mean quote below the price once = glutted
        gh_ = S.setdefault("glut_hist", {})
        gl_ = S.setdefault("glut", {})
        for k_, px_ in CFG["sd_glut_stop"].items():
            h_ = gh_.setdefault(k_, [])
            if not h_ or h_[-1][0] != step:
                h_.append((step, float(prices.get(k_, 0) or 0)))
            while h_ and step - h_[0][0] > int(CFG["sd_glut_hours"]):
                h_.pop(0)
            if len(h_) >= int(CFG["sd_glut_hours"]) and k_ not in gl_ and sum(x[1] for x in h_) / len(h_) < float(px_):
                gl_[k_] = day
    if CFG["sd_maint_floor_trail"] and CFG["sd_maint_floor"]:   # KWE: hourly quote history of the floor products
        ph_ = S.setdefault("price_hist", {})
        for k_ in CFG["sd_maint_floor"]:
            h_ = ph_.setdefault(k_, [])
            if not h_ or h_[-1][0] != step:
                h_.append((step, float(prices.get(k_, 0) or 0)))
            while h_ and step - h_[0][0] > 96:
                h_.pop(0)
    if _T is None:
        return {"farmer": ["PASS"], "hands": [["PASS"]] * (len(pos) - 1), "market": []}
    if S["day"] != day:
        S["day"] = day
        S["assign"] = {}
        S["walk"] = {}
    if CFG["fert_follow"] or CFG["harvest_policy"] == "leader_tendency":
        S["prices"] = prices
    unlocked = list(farm.get("unlocked_quadrants", ["NW"]))

    jobs, fert = _plan(obs, S, tiles, day)
    if CFG["harvest_policy"] == "leader_tendency":
        S["hp_jobs"] = set(jobs)
        S["hp_melon"] = {i_ for i_ in range(100) if _is_plant(_tile(tiles, i_)) and _tile(tiles, i_)["crop"] == "MELON"
                         and day - _tile(tiles, i_)["planted_day"] >= CROPS["MELON"]["first"]
                         and _tile(tiles, i_).get("yield_units", 0) > 0}
    if CFG["sched_maint"]:
        sig = []
        for idx in range(100):
            t = _tile(tiles, idx)
            if _is_plant(t):
                sig.append((idx, t["crop"], t["planted_day"]))
            elif _animal(t):
                sig.append((idx, t["animal"], t.get("placed_day")))
        sig = tuple(sig)
        if S.get("mj_day") != day or (S.get("mj_sig") != sig and hour - S.get("mj_hour", -99) >= CFG["mj_every"]):
            mj_prices = None
            if CFG["fert_shadow"]:
                # xfix fert_shadow: no shop buys fertilizer; its price only falls by 0.2 per unit sold (both players), so a
                # unit we hold is worth the quote minus 0.2 x our own remaining sales (the plan's; else an animal-based forecast)
                d_s = min(day, _T.n - 1)
                rem = None
                try:
                    tot = float(_T.cum_sold[_T.n - 1].get("FERTILIZER", 0))
                    if tot < 1e5:
                        rem = max(0.0, tot - float(_T.cum_sold[d_s].get("FERTILIZER", 0)))
                except Exception:
                    rem = None
                if rem is None:
                    n_an = sum(1 for r_ in tiles for t_ in r_ if _animal(t_))
                    rem = 0.7 * n_an * max(0, 28 - day)
                p_f = float(prices.get("FERTILIZER", 100) or 100)
                mj_prices = {"FERTILIZER": max(1.0, p_f - 0.2 * rem)}
                S["log"]["fert_shadow_sum"] += int(mj_prices["FERTILIZER"])
            if CFG["sd_maint_floor"] and day <= int(CFG["sd_maint_floor_last"]):   # R2: no abandonment on one thin quote
                mj_prices = dict(mj_prices or {})
                for k_, fl_ in CFG["sd_maint_floor"].items():
                    fl2_ = float(fl_)
                    H_ = int(CFG["sd_maint_floor_trail"] or 0)
                    if H_ > 0:                     # KWE: a glut that lasts all day lowers the floor
                        hist_ = [p_ for s_, p_ in S.get("price_hist", {}).get(k_, ()) if step - s_ <= H_]
                        if hist_:
                            stat_ = max(hist_) if CFG["sd_maint_floor_stat"] == "max" else sum(hist_) / len(hist_)
                            fl2_ = min(fl2_, stat_)
                            S["log"]["floor_trail_%s" % k_] += int(round(fl2_))
                    mj_prices[k_] = max(float(prices.get(k_, 0) or 0), fl2_)
            try:
                jl = _sm()["maintenance_jobs"](obs, me, prices=mj_prices, fertilize=_mj_fert(), include_optional=True,
                                              collect=CFG["mj_collect"], log=S.setdefault("abandon", []))
            except Exception as exc:  # never crash: fall back to the previous list
                S["log"]["mj_error"] += 1
                jl = None
            if jl is not None:
                by = {}
                for j in jl:
                    by.setdefault(j["tile"][1] * 10 + j["tile"][0], []).append(j)
                S["mj"] = by
                S["mj_day"], S["mj_sig"], S["mj_hour"] = day, sig, hour
                S["mj_known"] = set(sig)
                S["log"]["mj_calls"] += 1
    S["tval"] = {}
    S["atrisk"] = set()

    # ---- tile tasks
    tasks = {}
    for idx in range(100):
        t = _tile(tiles, idx)
        if t == "LOCKED":
            continue
        ops, need, prio = _tile_ops(idx, t, jobs.get(idx), fert, day, last_day, seeds)
        if ops:
            tasks[idx] = (ops, need, prio)
            if idx not in S["tval"]:
                S["tval"][idx] = ((CFG["plan_value"] if jobs.get(idx) else 50.0 * len(ops)), 23)

    if CFG["lead_harvest_bonus"]:
        lhb = set()
        d_h = min(day, _T.n - 1)
        hs_ = getattr(_T, "harv_tiles", None)
        if hs_ and d_h < len(hs_):
            for tt in hs_[d_h]:
                t_ = _tile(tiles, tt)
                if (_is_plant(t_) and not CROPS[t_["crop"]]["ongoing"] and t_.get("yield_units", 0) > 0
                        and day - t_["planted_day"] >= CROPS[t_["crop"]]["first"]
                        and (t_["crop"] == "MELON" or _onetime_should_harvest(t_, day))):
                    lhb.add(tt)
        S["lh_bonus"] = lhb
    carried = Counter()
    for inv in invs:
        carried.update(inv)
    demand = Counter()
    for ops, need, prio in tasks.values():
        demand.update(need)

    # ---- dispatch
    S["capfix_drop"] = Counter()
    n = len(pos)
    actions = [["PASS"] for _ in range(n)]
    prev = S["assign"]
    for u in list(prev):
        if u >= n or (prev[u] != "D" and prev[u] not in tasks):
            prev.pop(u, None)
    if CFG["sticky"]:
        assign = prev
    else:
        # fresh matching every step; deliveries stay sticky, current tasks get a small bonus
        assign = {u: v for u, v in prev.items() if v == "D"}
        S["assign"] = assign
    taken = set(v for v in assign.values() if v != "D")
    shed_left = Counter(shed)
    seeds_left = Counter(seeds)
    d_ = min(day, _T.n - 1)
    quota_open = {p for p in PRODUCTS if p != "WHEAT"
                  and (CFG["sd_clean"] or _T.cum_sold[d_].get(p, 0) - S["sold"][p] - shed.get(p, 0) > 0)}
    fert_short = demand.get("FERTILIZER", 0) > shed.get("FERTILIZER", 0)

    fert_keep = fert_short or (CFG["fert_hold"] == 1 and demand.get("FERTILIZER", 0) > 0) or CFG["fert_hold"] == 2
    if CFG["sd_fert_sell"]:
        fert_keep = True                  # sd_fert_sell: collected fertilizer is applied, never walked back to the shed
        if CFG["sd_fert_sell"] == 1 and S.get("_manual_today") != day:
            shed_left["FERTILIZER"] = 0   # ... and never picked up from the shed (the shed's stock is sold)
    if CFG["fert_release"] and CFG["fert_hold"] == 1 and not fert_short:
        fert_keep = demand.get("FERTILIZER", 0) >= carried.get("FERTILIZER", 0)    # xfix: only the surplus is deliverable

    n_herd = sum(1 for r_ in tiles for t_ in r_ if _animal(t_))
    wheat_over = (CFG["cap_fix"] and hour >= CFG["cap_fix_hour"] and day < last_day
                  and shed.get("WHEAT", 0) + carried.get("WHEAT", 0) > n_herd)

    def deliverable(inv):
        return {k: v for k, v in inv.items() if v > 0 and k in PRODUCTS and (k != "WHEAT" or wheat_over)
                and not (k == "FERTILIZER" and fert_keep)}

    def usable_ops(u, ops, need):
        """ops this unit can run at the tile now (items carried or obtainable at the shed)."""
        inv = invs[u]
        lack = {k for k, v in need.items() if inv.get(k, 0) < v and shed_left.get(k, 0) <= 0}
        if not lack:
            return ops
        out = []
        placing_blocked = False
        for op in ops:
            c = op[0]
            if c == "PLACE" and op[1] in lack:
                placing_blocked = True
                continue
            if placing_blocked and c in ("FEED", "CARE"):
                continue
            if c in ("FEED", "CARE") and "WHEAT" in lack:
                continue
            if c == "FERTILIZE" and "FERTILIZER" in lack:
                continue
            out.append(op)
        return out

    skipped_now = set()
    if CFG["sched_dispatch"] and CFG["sched_cost"] == "skip":
        # temporary skips: keep the highest value-density jobs that fit the crew's remaining unit-hours
        cap = sum(max(0, 23 - hour) for _ in range(n)) * CFG["skip_slack"]
        items = []
        for i2, (o2, n2, p2) in tasks.items():
            v2, dl2 = S["tval"].get(i2, (0.0, 23))
            tt2 = len(o2) + CFG["travel_est"]
            items.append((-(v2 / tt2), i2, tt2))
        items.sort()
        acc = 0.0
        for _, i2, tt2 in items:
            acc += tt2
            if acc > cap:
                skipped_now.add(i2)
        if hour == 12:
            S["log"]["skip_jobs_h12"] += len(skipped_now)

    def cost(u, idx):
        ops, need, prio = tasks[idx]
        p = pos[u]
        tgt = (idx % 10, idx // 10)
        ok = usable_ops(u, ops, need)
        if not ok:
            return None
        if CFG["lazy_fetch"]:
            miss = [k for k in _first_need(ok, invs[u]) if shed_left.get(k, 0) > 0]
        else:
            miss = [k for k, v in need.items() if invs[u].get(k, 0) < v and shed_left.get(k, 0) > 0]
        if miss:
            s = _near_shed(p)
            c = _dist(p, s) + len(miss) + _dist(s, tgt)
        else:
            c = _dist(p, tgt)
        # a plant pipeline must be finished (watered) today
        if any(o[0] == "PLANT" for o in ok) and hour + c + len(ok) > 24:
            return None
        if CFG["reach_guard"] and hour + c + (1 if CFG["reach_first"] else len(ok)) > 24:
            return None                 # cannot be finished today: do not walk toward it
        if len(ok) < len(ops):
            c += 2
        if CFG["sched_dispatch"] and CFG["sched_cost"] == "skip":
            if idx in skipped_now:
                c += 30             # today's temporary skip: only when nothing else is left
        elif CFG["sched_dispatch"]:
            v, dl = S["tval"].get(idx, (0.0, 23))
            tt = c + len(ok)
            structural = any(o[0] in ("PLANT", "PLACE", "BUILD_COOP", "BUILD_PASTURE", "DIG") for o in ok)
            if hour + tt - 1 > dl and not structural:
                v *= 0.2            # past its deadline most of the value is gone
            if CFG["sched_cost"] == "prize":
                # prize-collecting: travel + ops minus the job's value in unit-steps
                c2 = tt - v / CFG["step_value"]
                if prev.get(u) == idx:
                    c2 -= CFG["keep_bonus"]
                return c2
            dens = (v + 1.0) / max(1.0, tt)
            if prev.get(u) == idx:
                dens *= 1.3
            return -dens
        if CFG["prio_mode"] == "old":
            return c + prio * (6 if hour >= 14 else 3)
        # urgency only matters when the day runs short: plant/place pipelines and
        # death-preventing work first late in the day
        if CFG["atrisk_bonus"] and idx in S.get("atrisk", ()):
            c -= CFG["atrisk_bonus"]  # the whole crop is lost if this harvest waits until tomorrow
        if CFG["place_bonus"] and day <= CFG["place_bonus_days"] and any(o[0] == "PLACE" for o in ops):
            c -= CFG["place_bonus"]  # animals first (the leaders place every animal early in the day)
        if CFG["lead_harvest_bonus"] and idx in S.get("lh_bonus", ()) and any(o[0] == "HARVEST" for o in ops):
            c -= CFG["lead_harvest_bonus"]   # xfix: the leader harvests (and sells) this crop today: first thing
        if (CFG["busy_upkeep_pen"] and prio >= 1 and len(tasks) > CFG["busy_ratio"] * n
                and all(o[0] in ("FEED", "CARE", "COLLECT_FERTILIZER") for o in ops)):
            c += CFG["busy_upkeep_pen"]      # xfix: busy day: harvests / plantings / digs before animal upkeep
        if (CFG["harvest_policy"] == "leader_tendency" and hour < CFG["hp_melon_hour"] and idx in S.get("hp_melon", ())
                and any(o[0] == "HARVEST" for o in ops)):
            c -= CFG["hp_melon_bonus"]       # xfix harvest_policy: melons early in the day (race to the market)
        if hour >= CFG["late_hour"] and prio >= 2:
            c += 10
        elif CFG["prio3"] and hour >= CFG["late_hour"] and prio == 1:
            c += CFG["late_p1"]
        return c

    # zones: contiguous chunks of the curve with balanced work, recomputed when the crew changes
    zkey = (day, n)
    if S.get("zkey") != zkey:
        S["zkey"] = zkey
        w = [0.0] * 100
        for idx, (ops, need, prio) in tasks.items():
            w[CURVE_POS[idx]] = len(ops) + 1.5
        tot = sum(w) or 1.0
        zone = {}
        acc = 0.0
        for i, idx in enumerate(CURVE):
            u = min(n - 1, int(acc / tot * n)) if n > 1 else 0
            zone[idx] = u
            acc += w[i]
        S["zone"] = zone
    zone = S["zone"]
    zneed = [Counter() for _ in range(n)]
    for idx, (ops, need, prio) in tasks.items():
        zu = zone.get(idx, 0)
        if zu < n:
            zneed[zu].update(need)

    def cost2(u, idx):
        c = cost(u, idx)
        if c is None:
            return None
        if not CFG["sticky"] and prev.get(u) == idx and not CFG["sched_dispatch"]:
            c -= CFG["keep_bonus"]
            if CFG["commit"]:
                w_ = S.get("walk", {}).get(u)
                if w_ and w_[0] == idx:
                    c -= min(CFG["commit_cap"], w_[1])   # switch cost = steps already walked toward it
        if not CFG["zone_penalty"]:
            return c
        return c + (0 if zone.get(idx, 0) == u else CFG["zone_penalty"])

    if CFG["dispatch"] == "route":
        actions, taken = _dispatch_route(S, day, hour, last_day, tiles, pos, invs, tasks, shed, seeds,
                                          demand, carried, prices, quota_open, fert_short)
    # delivery for same-day sale when cash binds (or a unit carries a lot)
    capd = S.setdefault("capd", set())
    if S.get("capd_day") != day:
        S["capd_day"] = day
        capd.clear()

    def deliv_u(u):
        if u in capd:           # cap delivery: everything sellable, wheat and fertilizer included
            return {k: v for k, v in invs[u].items() if v > 0 and k in PRODUCTS}
        return deliverable(invs[u])
    if CFG["release_stale_d"]:
        for u in [u for u, v in assign.items() if v == "D" and u < n and not deliv_u(u)]:
            assign.pop(u, None)
    for u in list(capd):
        if u >= n or assign.get(u) != "D":
            capd.discard(u)
    if CFG["cap_deliver"] and day < last_day and CFG["cap_hour"] <= hour < 22 and CFG["dispatch"] != "route":
        need = (sum(shed.values()) + sum(sum(i.values()) for i in invs) + CFG["cap_rate"] * (23 - hour)
                - (100 - CFG["cap_margin"]) - sum(sum(invs[u].values()) for u in capd))
        if need > 0:
            cand = sorted((u for u in range(n) if u not in assign),
                          key=lambda u: (-sum(v for k, v in invs[u].items() if k in PRODUCTS), _dist(pos[u], _near_shed(pos[u]))))
            for u in cand:
                if need <= 0:
                    break
                c = sum(v for k, v in invs[u].items() if k in PRODUCTS)
                if c <= 0 or _dist(pos[u], _near_shed(pos[u])) + 1 > 22 - hour:
                    continue
                assign[u] = "D"
                capd.add(u)
                need -= c
                S["log"]["capd_units"] += 1
    for u in range(n):
        if CFG["dispatch"] == "route":
            break
        if u in assign:
            continue
        dv = deliverable(invs[u])
        val = sum(prices.get(k, 0) * v for k, v in dv.items() if k in quota_open)
        late = CFG["prio3"] and hour >= CFG["late_hour"]
        hp_mel = (CFG["harvest_policy"] == "leader_tendency" and dv.get("MELON", 0) > 0 and "MELON" in quota_open
                  and hour + _dist(pos[u], _near_shed(pos[u])) <= 22)     # xfix: melons sold the same day
        credit_ok = False
        if CFG["deliver_credit"] and dv:
            cr = sum(v * _dcredit(k, day, hour) for k, v in dv.items() if k in quota_open)
            credit_ok = cr > CFG["dc_step_value"] * 2 * _dist(pos[u], _near_shed(pos[u]))
            if credit_ok:
                S["log"]["dc_deliveries"] += 1
        flat = (((sum(dv.values()) >= CFG["deliver_units"] or val >= CFG["deliver_value"]) and not late)
                or (val >= CFG["deliver_value_late"] and hour < 20)) if not CFG["deliver_credit"] else False
        if dv and hour < 22 and (flat or credit_ok or (S.get("short") and val > 0) or hp_mel):
            assign[u] = "D"
    surv_route = {}
    if CFG["surv_reserve"] and hour >= CFG["surv_hour"] and day < last_day and CFG["dispatch"] != "route":
        # every tile whose asset dies / escapes tonight unless served: nearest-arrival greedy routes
        surv = []
        for idx in tasks:
            t_ = _tile(tiles, idx)
            if ((CFG["surv_harvest"] or CFG["harvest_policy"] == "leader_tendency")
                    and _is_plant(t_) and not CROPS[t_["crop"]]["ongoing"] and t_.get("yield_units", 0) > 0
                    and day - t_["planted_day"] >= CROPS[t_["crop"]]["maxday"]
                    and any(o[0] == "HARVEST" for o in tasks[idx][0])):
                surv.append((idx, "HARVEST"))   # a one-time crop past full yield starts decaying tomorrow morning
            elif _is_plant(t_) and not t_.get("watered_today") and t_.get("consecutive_unwatered", 0) >= 1:
                surv.append((idx, "WATER"))
            elif _animal(t_) and not t_.get("fed_today") and t_.get("consecutive_unfed", 0) >= 1:
                if any(invs[v].get("WHEAT", 0) > 0 for v in range(n)) or shed_left.get("WHEAT", 0) > 0:
                    surv.append((idx, "FEED"))
        if surv:
            clock = {u: hour for u in range(n) if assign.get(u) != "D"}
            where = {u: pos[u] for u in clock}
            wheat = {u: invs[u].get("WHEAT", 0) for u in clock}
            left = list(surv)
            while left and clock:
                best = None
                for u in clock:
                    for idx, op in left:
                        q = (idx % 10, idx // 10)
                        if op == "FEED" and wheat[u] <= 0:
                            s0 = _near_shed(where[u])
                            arr = clock[u] + _dist(where[u], s0) + 1 + _dist(s0, q)
                        else:
                            arr = clock[u] + _dist(where[u], q)
                        if best is None or arr < best[0]:
                            best = (arr, u, idx, op)
                arr, u, idx, op = best
                if arr > 23:
                    break
                surv_route.setdefault(u, []).append((idx, op))
                clock[u], where[u] = arr + 1, (idx % 10, idx // 10)
                if op == "FEED":
                    wheat[u] = max(0, wheat[u] - 1) if wheat[u] > 0 else 0
                left.remove((idx, op))
            S["log"]["surv_routed"] += sum(len(r) for r in surv_route.values())
            S["log"]["surv_unroutable"] += len(left)
        for u, r in surv_route.items():
            assign[u] = r[0][0]
            taken.add(r[0][0])
    _sd_run = _sd_pre(S, obs, me, step, day, hour, last_day, tiles, pos, invs, tasks, jobs, shed, seeds, prices, assign, taken, surv_route, deliv_u, fert_keep, demand, prev) if CFG["dispatch_search"] != "off" else None   # SEARCH DISPATCH HOOK 1
    free = [u for u in range(n) if u not in assign] if CFG["dispatch"] != "route" else []
    while free:
        best = None
        for u in free:
            for idx in tasks:
                if idx in taken:
                    continue
                c = cost2(u, idx)
                if c is None:
                    continue
                if CFG["tie_value"]:
                    c = c + (-min(4000.0, S['tval'].get(idx, (0.0, 23))[0]) * 1e-4)   # value-aware tie-break: equal-cost tasks go to the tile worth most today (q4 thread, 2026-09-25)
                if best is None or c < best[0]:
                    best = (c, u, idx)
        if best is None:
            break
        _, u, idx = best
        assign[u] = idx
        taken.add(idx)
        free.remove(u)
    helper = {}
    if CFG["helper_split"] and free:
        # units the greedy left free (every open task held): join a held animal tile with >= 2 open ops and take its
        # last independent op (collect / harvest / care) if they get there before the owner could finish alone
        owners = {v: w for w, v in assign.items() if isinstance(v, int)}
        cand = []
        for idx, (ops, need, prio) in tasks.items():
            t_h = _tile(tiles, idx)
            if idx not in owners or len(ops) < 2:
                continue
            if _animal(t_h):
                if not any(o[0] in ("HARVEST", "COLLECT_FERTILIZER", "CARE") for o in ops):
                    continue
            elif not (CFG["helper_crops"] and _is_plant(t_h) and CROPS[t_h["crop"]]["ongoing"]
                      and any(o[0] == "HARVEST" for o in ops) and not any(o[0] in ("PLANT", "DIG") for o in ops)):
                continue
            tgt = (idx % 10, idx // 10)
            cand.append((idx, tgt, _dist(pos[owners[idx]], tgt) + len(ops)))
        for u in list(free):
            best = None
            for idx, tgt, fin in cand:
                if idx in helper.values():
                    continue
                arr = _dist(pos[u], tgt) + 1
                if arr >= fin or hour + arr > 23:
                    continue
                if best is None or arr < best[0]:
                    best = (arr, idx)
            if best is not None:
                helper[u] = best[1]
                free.remove(u)
        S["log"]["helper_steps"] += len(helper)

    assign0 = dict(assign)
    if CFG["pf_log"]:
        asg_ = set(v for v in assign0.values() if v != "D")
        for m_, j_ in jobs.items():
            if j_[0] == "PLANT" and j_[2] in S.get("pf", {}):
                r_ = S["pf"][j_[2]]
                r_["job_steps"] = r_.get("job_steps", 0) + 1
                r_["seed_steps"] = r_.get("seed_steps", 0) + (1 if seeds.get(j_[1], 0) > 0 else 0)
                r_["assign_steps"] = r_.get("assign_steps", 0) + (1 if m_ in asg_ else 0)
                if m_ in tasks and any(o[0] == "PLANT" for o in tasks[m_][0]):
                    r_["task_steps"] = r_.get("task_steps", 0) + 1
    shed_left0 = Counter(shed_left)
    plant_count = Counter()
    endgame = day >= last_day
    for u in range(n):
        if CFG["dispatch"] == "route":
            break
        p = pos[u]
        inv = invs[u]
        # final day delivery
        if endgame:
            sellable = sum(v for k, v in inv.items() if k in PRODUCTS)
            s = _near_shed(p)
            if sellable and (22 - hour) <= _dist(p, s) + 1:
                actions[u] = ["DROP"] if p == s else _step_toward(p, s)
                assign.pop(u, None)
                continue
        if _sd_run is not None and u in _sd_run["units"]:   # SEARCH DISPATCH HOOK 2
            _sd_a = _sd_act(S, _sd_run, u, p, inv, tasks, tiles, shed_left, seeds_left, plant_count, carried, hour, usable_ops, deliv_u)
            if _sd_a is not None:
                actions[u] = _sd_a
                continue
        idx = assign.get(u)
        if CFG["cap_fix"] and CFG["cap_fix_hour"] <= hour <= 23 and day < last_day and u not in surv_route:
            dvc = deliverable(inv)
            s_c = _near_shed(p)
            if dvc and _dist(p, s_c) <= 1:
                if p != s_c:
                    actions[u] = _step_toward(p, s_c)
                else:
                    if all(k in dvc for k in inv):
                        actions[u] = ["DROP"]
                        for k, v in dvc.items():
                            S.setdefault("capfix_drop", Counter())[k] += v
                    else:
                        k = max(dvc, key=lambda q: dvc[q])
                        actions[u] = ["PLACE", k, int(inv[k])]
                        S.setdefault("capfix_drop", Counter())[k] += int(inv[k])
                    S["log"]["capfix_deposits"] += 1
                assign.pop(u, None)
                continue
        if u in helper:
            hidx = helper[u]
            htgt = (hidx % 10, hidx // 10)
            if p != htgt:
                actions[u] = _step_toward(p, htgt)
            else:
                hop = None
                for op in reversed(tasks[hidx][0]):
                    if op[0] in ("HARVEST", "COLLECT_FERTILIZER", "CARE"):
                        hop = op
                        break
                actions[u] = list(hop) if hop else ["PASS"]
            continue
        if p in SHED and idx != "D" and hour < 22:
            if CFG["hand_stock"] and hour >= CFG["hs_drop_hour"] and inv.get("WHEAT", 0) > 0:
                keep_w = tasks[idx][1].get("WHEAT", 0) if (idx is not None and idx in tasks) else 0
                surplus = inv.get("WHEAT", 0) - keep_w - CFG["hs_buffer"]
                if surplus > 0:
                    actions[u] = ["PLACE", "WHEAT", int(surplus)]
                    S["log"]["hs_drop"] += int(surplus)
                    continue
            want = zneed[u] if CFG["zone_penalty"] else Counter(
                {k: min(CFG["pick_cap"].get(k, 3), max(0, demand[k] - carried[k])) for k in ("WHEAT", "FERTILIZER")})
            if CFG["hand_stock"]:
                want["WHEAT"] = 0
            if CFG["pick_plan"]:
                want["WHEAT"] = 0
                want["FERTILIZER"] = 0
            if CFG["spawn_allot"] and hour <= 2 and n > 1:
                # full-day allotment at spawn: this hand's share of the day's feeding
                share = -(-demand["WHEAT"] // n) + 1
                want["WHEAT"] = min(max(0, demand["WHEAT"] - carried["WHEAT"] + inv.get("WHEAT", 0)), share)
            got = None
            for k in ("WHEAT", "FERTILIZER"):
                gap = min(want.get(k, 0) - inv.get(k, 0), max(0, demand[k] - carried[k]), shed_left.get(k, 0))
                if gap > 0:
                    got = (k, gap)
                    break
            if got:
                shed_left[got[0]] -= got[1]
                carried[got[0]] += got[1]
                actions[u] = ["PICKUP", got[0], int(got[1])]
                continue
        if idx is None or idx == "D":
            dv = deliv_u(u)
            if (not dv and idx is None and CFG["idle_deliver"] and day < last_day
                    and hour + _dist(p, _near_shed(p)) <= 22):
                # xfix idle_deliver: no task left for this unit: carry its sellable stock (not wheat; fertilizer beyond the
                # open fertilize need) to the shed so it sells today instead of after the midnight dump
                f_open = max(0, demand.get("FERTILIZER", 0) - sum(invs[v].get("FERTILIZER", 0) for v in range(n) if v != u)
                             - shed_left.get("FERTILIZER", 0))
                dv = {k: v for k, v in inv.items() if v > 0 and k in PRODUCTS and k != "WHEAT"
                      and (k != "FERTILIZER" or v > f_open)}
                if dv and sum(shed.values()) + sum(inv.values()) > 95:
                    dv = {}                  # a DROP / PLACE at a full shed deletes what does not fit
                if dv:
                    S["log"]["idle_deliver"] += 1
            if dv and hour < 23:
                s = _near_shed(p)
                if p != s:
                    actions[u] = _step_toward(p, s)
                else:
                    if all(k in dv for k in inv):
                        actions[u] = ["DROP"]
                    else:
                        k = sorted(dv)[0]
                        actions[u] = ["PLACE", k, int(inv[k])]
                    if len(dv) <= 1:
                        assign.pop(u, None)
            else:
                assign.pop(u, None)
            continue
        ops, need, prio = tasks[idx]
        tgt = (idx % 10, idx // 10)
        if u in surv_route:
            sop = surv_route[u][0][1]
            if sop == "FEED" and inv.get("WHEAT", 0) <= 0 and shed_left.get("WHEAT", 0) > 0:
                s0 = _near_shed(p)
                if p != s0:
                    actions[u] = _step_toward(p, s0)
                else:
                    k = min(shed_left["WHEAT"], max(1, sum(1 for _, o in surv_route[u] if o == "FEED")))
                    shed_left["WHEAT"] -= k
                    actions[u] = ["PICKUP", "WHEAT", int(k)]
                continue
            if p != tgt:
                actions[u] = _step_toward(p, tgt)
                continue
            actions[u] = [sop]
            continue
        if CFG["lazy_fetch"]:
            miss = [k for k in _first_need(usable_ops(u, ops, need), inv) if shed_left.get(k, 0) > 0]
        else:
            miss = [k for k, v in need.items() if inv.get(k, 0) < v and shed_left.get(k, 0) > 0]
        if miss:
            s = _near_shed(p)
            if p != s:
                actions[u] = _step_toward(p, s)
                continue
            k = miss[0]
            cover = max(0, demand[k] - carried[k])
            amt = min(shed_left[k], max(need[k] - inv.get(k, 0), min(cover, zneed[u][k] - inv.get(k, 0))))
            if CFG["hand_stock"] and k == "WHEAT":
                amt = min(shed_left[k], max(0, need[k] - inv.get(k, 0)) + CFG["hs_buffer"])
            if CFG["pick_plan"] and k in ("WHEAT", "FERTILIZER"):
                # this unit's share: its task + the open tasks it is nearest to (not held by another unit)
                want_ = need.get(k, 0)
                for j_, (o_, n_, p_) in tasks.items():
                    if j_ == idx or n_.get(k, 0) <= 0 or (j_ in taken and assign.get(u) != j_):
                        continue
                    jt = (j_ % 10, j_ // 10)
                    du = _dist(tgt, jt)
                    if all(du <= _dist(pos[v], jt) for v in range(n) if v != u):
                        want_ += n_[k]
                amt = min(shed_left[k], max(1, min(CFG["pick_plan_max"], want_) - inv.get(k, 0)))
                S["log"]["pick_plan_" + k] += 1
            amt = max(1, amt)
            shed_left[k] -= amt
            carried[k] += amt
            actions[u] = ["PICKUP", k, int(amt)]
            continue
        if p != tgt:
            actions[u] = _step_toward(p, tgt)
            if CFG["commit"]:
                w_ = S.setdefault("walk", {}).get(u)
                S["walk"][u] = (idx, (w_[1] + 1) if (w_ and w_[0] == idx) else 1)
            continue
        # at tile: first executable op
        act = None
        t = _tile(tiles, idx)
        for op in usable_ops(u, ops, need):
            c = op[0]
            if c == "FEED" and inv.get("WHEAT", 0) <= 0:
                continue
            if c == "CARE" and isinstance(t, dict) and not t.get("fed_today") and any(o[0] == "FEED" for o in ops):
                continue
            if c == "FERTILIZE" and inv.get("FERTILIZER", 0) <= 0:
                continue
            if c == "PLACE" and inv.get(op[1], 0) <= 0:
                break
            if c == "PLANT":
                if seeds_left.get(op[1], 0) <= 0 or hour >= 23:
                    break
                seeds_left[op[1]] -= 1
                plant_count[op[1]] += 1
            act = op
            break
        if act is None:
            assign.pop(u, None)
            actions[u] = ["PASS"]
        else:
            actions[u] = list(act)

    # ---- diagnostics
    if CFG["pf_log"]:
        for u_ in range(n):
            a_ = actions[u_]
            if a_ and a_[0] == "HARVEST":
                t_ = _tile(tiles, pos[u_][1] * 10 + pos[u_][0])
                if _is_plant(t_) and t_["crop"] == "MELON" and t_.get("yield_units", 0) > 0                         and day - t_["planted_day"] >= CROPS["MELON"]["first"]:
                    S["log"]["melon_units_h%02d" % hour] += int(t_["yield_units"])    # xfix log: melon units by hour
    if hour in (1, 23) and day < last_day:
        lg = S["log"]
        nf = sum(1 for ops, need, prio in tasks.values() if any(o[0] == "FERTILIZE" for o in ops))
        lg["fert_tasks_h%02d" % hour] += nf
        lg["fert_stock_h%02d" % hour] += shed.get("FERTILIZER", 0) + carried.get("FERTILIZER", 0)
    if step >= 718 and not S.get("abandon_logged"):
        S["abandon_logged"] = True
        for e in S.get("abandon", []):
            S["log"]["abandon_%s_%s" % (e.get("verdict"), e.get("kind"))] += 1
    if hour == 23 and day < last_day and S.get("tval"):
        S["log"]["skipped_value"] += int(sum(v for i, (v, dl) in S["tval"].items() if i in tasks))
        S["log"]["skipped_jobs"] += len(tasks)
    if hour == 23 and day < last_day:
        lg = S["log"]
        for idx, (ops, need, prio) in tasks.items():
            t = _tile(tiles, idx)
            if _is_plant(t) and not t.get("watered_today") and t.get("consecutive_unwatered", 0) >= 1:
                lg["die_%s_%s" % (t["crop"], "assigned" if idx in taken else "unassigned")] += 1

            if _animal(t) and not t.get("fed_today"):
                lg["unfed_%s" % ("assigned" if idx in taken else "unassigned")] += 1
    if hour == 23 and day < last_day:
        for idx in range(100):
            t = _tile(tiles, idx)
            if _is_plant(t) and not t.get("watered_today") and t.get("consecutive_unwatered", 0) >= 1:
                if idx not in tasks:
                    S["log"]["dying_no_task"] += 1
                elif any(o[0] == "WATER" for o in tasks[idx][0]):
                    S["log"]["dying_water_task"] += 1
                else:
                    S["log"]["dying_task_without_water"] += 1
    if CFG["idle_trace"]:
        _sl_now = Counter(shed_left)
        shed_left.clear(); shed_left.update(shed_left0)      # judge the idle units as the dispatcher saw the shed
        try:
            _idle_trace(S, obs, me, tiles, day, hour, n, pos, invs, tasks, taken, assign0, actions, shed_left,
                        cost, usable_ops, surv_route)
        except Exception as exc:
            S["log"]["trace_error"] += 1
        shed_left.clear(); shed_left.update(_sl_now)
    lg = S["log"]
    for u in range(n):
        if actions[u] == ["PASS"]:
            lg["pass_h%02d" % (hour // 6 * 6)] += 1

    if _sd_run is not None:   # SEARCH DISPATCH HOOK 3
        _sd_post(S, _sd_run, obs, me, step, day, hour, last_day, tiles, pos, tasks, assign, actions)
    if CFG["sd_tier"] and CFG["dispatch_search"] != "off":   # tiered fixed plan: every planned unit follows its list
        try:
            _tier_override(S, obs, step, day, hour, tiles, pos, invs, actions, seeds, shed)
        except Exception as exc:
            try:
                import traceback as _tb
                L_ = _sd_state(S)
                L_["st"]["errors"] += 1
                L_["st"]["last_error"] = ("tier_exec %s: %s" % (type(exc).__name__, exc))[:300]
                L_["st"]["tier_tb"] = _tb.format_exc()[-1500:]
            except Exception:
                pass
    # ---- market
    orders = _market(S, obs, day, hour, money, shed, seeds, carried, invs, tasks, jobs, demand, prices,
                     unlocked, farm, pos, last_day)
    dt = time.time() - t0
    S["tmax"] = max(S["tmax"], dt)
    if CFG["dispatch_search"] != "off":   # SEARCH DISPATCH HOOK 5
        _sd_step_end(step, t0)
    return {"farmer": actions[0], "hands": actions[1:], "market": orders}


# ---- research: idle-pass / dropped-job trace (CFG idle_trace) -----------------------------

def _idle_trace(S, obs, me, tiles, day, hour, n, pos, invs, tasks, taken, assign0, actions, shed_left, cost, usable_ops,
                surv_route):
    """Buffer every PASS of the day with the open tasks and why that unit did not take each; at hour 23 value the
    jobs still open with a fresh sem_maintenance solve (minus what hour 23 itself does) and write one day record."""
    import json as _json
    import os as _os
    buf = S.setdefault("itr_buf", [])
    if S.get("itr_day") != day:
        S["itr_day"] = day
        buf.clear()
        S["itr_open"] = {}
    first_open = S["itr_open"]
    work = S.setdefault("itr_work", Counter())
    if hour == 0:
        work.clear()
    mjv = {}
    for idx_, jl_ in S.get("mj", {}).items():
        for j_ in jl_:
            if not j_.get("optional"):
                mjv[(idx_, j_["cmd"])] = float(j_.get("value", 0.0))
    for u in range(n):
        a = actions[u]
        c = a[0] if a else "PASS"
        if c in ("NORTH", "SOUTH", "EAST", "WEST"):
            work["move"] += 1
        elif c in ("WATER", "FEED", "CARE", "HARVEST", "FERTILIZE", "COLLECT_FERTILIZER"):
            idx_ = pos[u][1] * 10 + pos[u][0]
            v_ = mjv.get((idx_, c))
            work["op_" + c] += 1
            work["opv_" + ("none" if v_ is None else "0" if v_ <= 0 else "lt30" if v_ < 30 else "lt100" if v_ < 100 else "ge100")] += 1
            work["opval"] += v_ or 0.0
        elif c in ("PICKUP", "DROP", "PLACE"):
            work["shed_" + c] += 1
        elif c == "PASS":
            work["pass"] += 1
        else:
            work["plan_" + c] += 1
    for idx, (ops, need, prio) in tasks.items():
        for o in ops:
            first_open.setdefault((idx, o[0]), hour)
    for u in range(n):
        if actions[u] != ["PASS"]:
            continue
        a0 = assign0.get(u)
        if a0 is not None and a0 != "D":
            t = _tile(tiles, a0)
            buf.append({"h": hour, "u": u, "kind": "tile_noop", "idx": a0, "pos": list(pos[u]),
                        "ops": [o[0] if len(o) == 1 else o[0] + ":" + str(o[1]) for o in tasks.get(a0, ([], 0, 0))[0]],
                        "inv": dict(invs[u]), "fed": bool(isinstance(t, dict) and t.get("fed_today"))})
            continue
        why = {}
        for idx, (ops, need, prio) in tasks.items():
            tgt = (idx % 10, idx // 10)
            if idx in taken:
                owner = [v for v, w in assign0.items() if w == idx]
                ow = owner[0] if owner else -1
                why[idx] = ("taken", _dist(pos[u], tgt), ow, _dist(pos[ow], tgt) if ow >= 0 else None)
                continue
            ok = usable_ops(u, ops, need)
            if not ok:
                lack = sorted(k for k, v in need.items() if invs[u].get(k, 0) < v and shed_left.get(k, 0) <= 0)
                why[idx] = ("lack:" + ",".join(lack), None, None, None)
                continue
            c = cost(u, idx)
            why[idx] = ("plant_late" if c is None else "valid", _dist(pos[u], tgt), None, None)
        buf.append({"h": hour, "u": u, "kind": "no_task" if a0 is None else "deliver", "pos": list(pos[u]),
                    "inv": dict(invs[u]), "why": why,
                    "open": {idx: [o[0] for o in ops] for idx, (ops, need, prio) in tasks.items()}})
    if hour != 23:
        return
    # dropped = fresh solve's (non-optional, value > 0) jobs still open at hour 23, minus the ops executed at hour 23
    done23 = set()
    for u in range(n):
        a = actions[u]
        if a and a[0] in ("WATER", "FEED", "CARE", "HARVEST", "FERTILIZE", "COLLECT_FERTILIZER"):
            done23.add((pos[u][1] * 10 + pos[u][0], a[0]))
    try:
        jl = _sm()["maintenance_jobs"](obs, me, prices=None, fertilize=_mj_fert(), include_optional=False,
                                      collect=CFG["mj_collect"])
    except Exception:
        jl = []
    dropped = []
    for j in jl:
        idx = j["tile"][1] * 10 + j["tile"][0]
        v = float(j.get("value", 0.0))
        if v <= 0 or (idx, j["cmd"]) in done23:
            continue
        t = _tile(tiles, idx)
        in_task = idx in tasks and any(o[0] == j["cmd"] for o in tasks[idx][0])
        passes = []
        for b in buf:
            if b["kind"] == "tile_noop":
                continue
            if idx in b["why"] and j["cmd"] in b["open"].get(idx, ()):
                passes.append([b["h"], b["u"]] + list(b["why"][idx]))
        dropped.append({"idx": idx, "cmd": j["cmd"], "value": round(v, 1), "kind": j.get("kind"), "units": j.get("units", 0),
                        "asset": j.get("asset"), "deadline": j.get("deadline"), "in_task": in_task,
                        "first_open": first_open.get((idx, j["cmd"])), "idle": passes,
                        "cu": (t.get("consecutive_unwatered") if _is_plant(t) else t.get("consecutive_unfed")
                               if isinstance(t, dict) else None)})
    plan_open = {idx: [o[0] for o in ops] for idx, (ops, need, prio) in tasks.items()
                 if any(o[0] in ("PLANT", "PLACE", "BUILD_COOP", "BUILD_PASTURE") for o in ops)}
    passes_kind = {}
    for b in buf:
        k = b["kind"] + ("" if b["kind"] != "tile_noop" else ":" + ",".join(b["ops"]))
        passes_kind.setdefault(k, [0, 0])
        passes_kind[k][0] += 1
        passes_kind[k][1] += 1 if b["h"] >= 18 else 0
    noop = [{k: b[k] for k in ("h", "u", "idx", "ops", "inv", "fed")} for b in buf if b["kind"] == "tile_noop"]
    idle_detail = []
    for b in buf:
        if b["kind"] == "tile_noop":
            continue
        cnt = {}
        for idx, (r, _d, _o, _od) in b["why"].items():
            cnt[r] = cnt.get(r, 0) + 1
        idle_detail.append([b["h"], b["u"], b["pos"], b["inv"], cnt, len(b["open"])])
    rec = {"day": day, "n": n, "work": dict(work), "dropped": dropped, "plan_open23": plan_open, "passes": passes_kind,
           "noop": noop, "idle": idle_detail, "mj_hour": S.get("mj_hour")}
    path = S.get("itr_path")
    if path is None:
        _os.makedirs(CFG["idle_trace"], exist_ok=True)
        path = _os.path.join(CFG["idle_trace"], "%d_%d_%d.jsonl" % (_os.getpid(), int(time.time() * 1000), me))
        S["itr_path"] = path
    with open(path, "a", encoding="utf-8") as f:
        f.write(_json.dumps(rec) + "\n")
    buf.clear()


# ---- route dispatcher (sweep plan per day, executed closed loop) ---------------------------

import math as _math


def _job_items(ops):
    wheat = sum(1 for o in ops if o[0] == "FEED")
    fert = sum(1 for o in ops if o[0] == "FERTILIZE") - sum(1 for o in ops if o[0] == "COLLECT_FERTILIZER")
    animals = Counter(o[1] for o in ops if o[0] == "PLACE")
    return wheat, fert, animals


def _route_time(start_hour, p, route, tasks):
    t = start_hour
    for idx in route:
        q = (idx % 10, idx // 10)
        t += _dist(p, q) + len(tasks[idx][0])
        p = q
    return t


def _route_len(p, r):
    c, L = p, 0
    for i in r:
        q = (i % 10, i // 10)
        L += _dist(c, q)
        c = q
    return L


def _order_route(p, jobs, tasks):
    """nearest neighbour from p, then 2-opt on travel."""
    left = list(jobs)
    out = []
    cur = p
    while left:
        j = min(left, key=lambda i: (_dist(cur, (i % 10, i // 10)), i))
        out.append(j)
        left.remove(j)
        cur = (j % 10, j // 10)
    if CFG["two_opt"] and len(out) > 3:
        best = _route_len(p, out)
        improved = True
        loops = 0
        while improved and loops < 6:
            improved = False
            loops += 1
            for i in range(len(out) - 1):
                for k in range(i + 1, len(out)):
                    r = out[:i] + out[i:k + 1][::-1] + out[k + 1:]
                    L = _route_len(p, r)
                    if L < best:
                        out, best, improved = r, L, True
    return out


def _build_routes(S, hour, pos, tasks, n):
    """sweep: sort jobs by angle around the shed centre, cut into n balanced sectors, order each."""
    jobs = list(tasks)
    if not jobs:
        return {u: [] for u in range(n)}
    ang = {i: _math.atan2((i // 10) - 4.5, (i % 10) - 4.5) for i in jobs}
    jobs.sort(key=lambda i: (ang[i], _dist((4.5, 4.5), (i % 10, i // 10))))
    # start the sweep at the largest angular gap so no sector wraps across a cluster
    if len(jobs) > 2:
        gaps = [((ang[jobs[(k + 1) % len(jobs)]] - ang[jobs[k]]) % (2 * _math.pi), k) for k in range(len(jobs))]
        g, k = max(gaps)
        jobs = jobs[k + 1:] + jobs[:k + 1]
    home = (4, 4)

    def gtime(g):
        if not g:
            return 0
        need = set()
        for i in g:
            w_, f_, an = _job_items(tasks[i][0])
            if w_:
                need.add("W")
            if f_ > 0:
                need.add("F")
            need.update(an)
        # nearest-neighbour tour length from the shed
        left, cur, L = list(g), home, 0
        while left:
            j = min(left, key=lambda i: _dist(cur, (i % 10, i // 10)))
            L += _dist(cur, (j % 10, j // 10))
            cur = (j % 10, j // 10)
            left.remove(j)
        return len(need) + L + sum(len(tasks[i][0]) for i in g)

    def split(T):
        groups, cur = [], []
        for i in jobs:
            if cur and gtime(cur + [i]) > T:
                groups.append(cur)
                cur = []
            cur.append(i)
        groups.append(cur)
        return groups

    lo, hi = 1.0, 24.0 * 4
    best = split(hi)
    for _ in range(9):
        mid = (lo + hi) / 2
        g = split(mid)
        if len(g) <= n:
            best, hi = g, mid
        else:
            lo = mid
    groups = best
    while len(groups) < n:
        groups.append([])
    order = sorted(range(len(groups)), key=lambda g: -len(groups[g]))
    free = list(range(n))
    routes = {u: [] for u in range(n)}
    for g in order:
        if not free:
            break
        grp = groups[g]
        if grp:
            cx = sum(i % 10 for i in grp) / len(grp)
            cy = sum(i // 10 for i in grp) / len(grp)
            u = min(free, key=lambda v: (_dist(pos[v], (cx, cy)), v))
        else:
            u = free[-1]
        free.remove(u)
        routes[u] = _order_route(pos[u], grp, tasks)
    return routes


def _insert(routes, pos, hour, idx, tasks, limit=23.5):
    best = None
    q = (idx % 10, idx // 10)
    for u, r in routes.items():
        base = _route_time(hour, pos[u], r, tasks)
        prev = pos[u]
        for k in range(len(r) + 1):
            nxt = (r[k] % 10, r[k] // 10) if k < len(r) else None
            add = _dist(prev, q) + len(tasks[idx][0]) + (_dist(q, nxt) - _dist(prev, nxt) if nxt else 0)
            fin = base + add
            key = (fin > limit, fin if CFG["insert_by_finish"] else add, add)
            if best is None or key < best[0]:
                best = (key, u, k)
            if nxt:
                prev = nxt
    if best is None:
        return False
    _, u, k = best
    routes[u].insert(k, idx)
    return True


def _dispatch_route(S, day, hour, last_day, tiles, pos, invs, tasks, shed, seeds, demand, carried, prices,
                    quota_open, fert_short):
    n = len(pos)
    actions = [["PASS"] for _ in range(n)]
    lg = S["log"]
    key = (day, n)
    full = n >= _T.hands[min(day, _T.n - 1)] + 1 or hour >= 2
    if CFG["route_once"]:
        if S.get("rday") != day:
            S["rday"] = day
            S["rbuilt"] = False
            S["routes"] = _build_routes(S, hour, pos, tasks, n)
            S["deliver"] = set()
        elif not S["rbuilt"] and full:
            S["rbuilt"] = True
            S["routes"] = _build_routes(S, hour, pos, tasks, n)
    elif S.get("rkey") != key:
        S["rkey"] = key
        S["routes"] = _build_routes(S, hour, pos, tasks, n)
        S["deliver"] = set()
    routes = S["routes"]
    for u in list(routes):
        if u >= n:
            routes.pop(u)
    for u in range(n):
        routes.setdefault(u, [])
        routes[u] = [i for i in routes[u] if i in tasks]
    routed = set(i for r in routes.values() for i in r)
    for idx in sorted(tasks, key=lambda i: tasks[i][2]):
        if idx not in routed:
            if CFG["route_once"]:
                q = (idx % 10, idx // 10)
                near = min((_dist(q, (j % 10, j // 10)) for r in routes.values() for j in r), default=99)
                near = min(near, min(_dist(q, pos[v]) for v in range(n)))
                if near > CFG["add_radius"]:
                    continue
            _insert(routes, pos, hour, idx, tasks)
            routed.add(idx)
    # idle hands take the nearest task nobody has
    if CFG["route_once"]:
        for u in range(n):
            if routes[u]:
                continue
            free_t = [i for i in tasks if i not in routed]
            if free_t:
                i = min(free_t, key=lambda i: _dist(pos[u], (i % 10, i // 10)))
                routes[u] = [i]
                routed.add(i)
    shed_left = Counter(shed)
    seeds_left = Counter(seeds)
    endgame = day >= last_day

    def deliverable(inv):
        return {k: v for k, v in inv.items() if v > 0 and k in PRODUCTS and k != "WHEAT"
                and not (k == "FERTILIZER" and fert_short)}

    def route_need(u, k=None):
        need = Counter()
        bal = 0
        fneed = 0
        for i in (routes[u] if k is None else routes[u][:k]):
            w, f, an = _job_items(tasks[i][0])
            need["WHEAT"] += w
            bal -= f
            fneed = max(fneed, -bal)
            for a, c in an.items():
                need[a] += c
        need["FERTILIZER"] = fneed
        return need

    # idle units steal the job whose owner would reach it much later than they can
    for u in range(n):
        if routes[u] or hour >= 23:
            continue
        best = None
        for v, r in routes.items():
            if v == u or len(r) < 2:
                continue
            t = hour
            prev = pos[v]
            for k, i in enumerate(r):
                q = (i % 10, i // 10)
                t += _dist(prev, q) + len(tasks[i][0])
                prev = q
                if k == 0:
                    continue
                gain = t - (hour + _dist(pos[u], q))
                if _dist(pos[u], q) > CFG["steal_radius"]:
                    continue
                if gain > 2 and (best is None or gain > best[0]):
                    best = (gain, v, k, i)
        if best:
            _, v, k, i = best
            routes[v].pop(k)
            routes[u] = [i]

    # wheat rebalancing: FEED jobs of units without wheat (shed empty) go to units carrying surplus wheat
    if shed_left.get("WHEAT", 0) <= 0:
        surplus = {v: invs[v].get("WHEAT", 0) - route_need(v)["WHEAT"] for v in range(n)}
        for u in range(n):
            have = invs[u].get("WHEAT", 0)
            for i in list(routes[u]):
                if not any(o[0] == "FEED" for o in tasks[i][0]):
                    continue
                if have > 0:
                    have -= 1
                    continue
                donors = [v for v in range(n) if v != u and surplus[v] > 0]
                if not donors:
                    break
                q = (i % 10, i // 10)
                v = min(donors, key=lambda v: _dist(pos[v], q))
                routes[u].remove(i)
                r = routes[v]
                k = min(range(len(r) + 1), key=lambda k: (_dist((r[k - 1] % 10, r[k - 1] // 10) if k else pos[v], q)
                                                          + (_dist(q, (r[k] % 10, r[k] // 10)) if k < len(r) else 0)))
                r.insert(k, i)
                surplus[v] -= 1
                lg["feed_moved"] += 1

    for u in range(n):
        p = pos[u]
        inv = invs[u]
        if endgame:
            sellable = sum(v for k, v in inv.items() if k in PRODUCTS)
            s0 = _near_shed(p)
            if sellable and (22 - hour) <= _dist(p, s0) + 1:
                actions[u] = ["DROP"] if p == s0 else _step_toward(p, s0)
                continue
        rn = route_need(u, CFG["pick_k"] if n == 1 else None)
        dv = deliverable(inv)
        if "FERTILIZER" in dv:
            keep = rn.get("FERTILIZER", 0)
            if dv["FERTILIZER"] <= keep:
                dv.pop("FERTILIZER")
            else:
                dv["FERTILIZER"] -= keep
        if not endgame and (u in S["deliver"] or (dv and hour < 22)):
            val = sum(prices.get(k, 0) * v for k, v in dv.items() if k in quota_open)
            if dv and (u in S["deliver"] or sum(dv.values()) >= 10 or val >= CFG["deliver_value"]
                       or (S.get("short") and val > 0)):
                S["deliver"].add(u)
                s0 = _near_shed(p)
                if p != s0:
                    actions[u] = _step_toward(p, s0)
                elif all(k in dv for k in inv):
                    actions[u] = ["DROP"]
                    S["deliver"].discard(u)
                else:
                    k = sorted(dv)[0]
                    actions[u] = ["PLACE", k, int(dv[k])]
                    if len(dv) <= 1:
                        S["deliver"].discard(u)
                continue
            S["deliver"].discard(u)
        if p in SHED and hour < 23:
            got = None
            for k in ["WHEAT", "FERTILIZER"] + sorted(a for a in rn if a in ANIMALS):
                gap = min(rn.get(k, 0) - inv.get(k, 0), shed_left.get(k, 0))
                if gap > 0:
                    got = (k, gap)
                    break
            if got:
                shed_left[got[0]] -= got[1]
                actions[u] = ["PICKUP", got[0], int(got[1])]
                continue
        act = None
        for attempt in range(len(routes[u])):
            idx = routes[u][0]
            ops, need, prio = tasks[idx]
            tgt = (idx % 10, idx // 10)
            lack = [k for k, v in need.items() if inv.get(k, 0) < v]
            if lack and all(shed_left.get(k, 0) > 0 for k in lack):
                s0 = _near_shed(p)
                if p == s0:
                    k = lack[0]
                    amt = int(min(shed_left[k], max(need[k] - inv.get(k, 0), rn.get(k, 0) - inv.get(k, 0))))
                    shed_left[k] -= amt
                    act = ["PICKUP", k, amt]
                else:
                    act = _step_toward(p, s0)
                break
            usable = []
            has_feed = any(o[0] == "FEED" for o in ops)
            for op in ops:
                c = op[0]
                if c == "PLACE" and inv.get(op[1], 0) <= 0:
                    break
                if c in ("FEED", "CARE") and has_feed and inv.get("WHEAT", 0) <= 0:
                    continue
                if c == "FERTILIZE" and inv.get("FERTILIZER", 0) <= 0:
                    continue
                if c == "PLANT" and (seeds_left.get(op[1], 0) <= 0 or hour >= 23):
                    break
                usable.append(op)
            if not usable:
                routes[u].append(routes[u].pop(0))
                continue
            if p != tgt:
                act = _step_toward(p, tgt)
            else:
                op = usable[0]
                if op[0] == "PLANT":
                    seeds_left[op[1]] -= 1
                act = list(op)
            break
        if act is None:
            lg["route_idle"] += 1
            if dv and hour < 23:
                s0 = _near_shed(p)
                if p != s0:
                    act = _step_toward(p, s0)
                else:
                    k = sorted(dv)[0]
                    act = ["PLACE", k, int(dv[k])]
            else:
                act = ["PASS"]
        actions[u] = act
    taken = set(i for r in routes.values() for i in r)
    return actions, taken


def _sched_hands(S, day, hour, tasks, jobs=None):
    """hire the n-th hand while the value of the jobs only it adds (in value-density order, within the day's
    remaining unit-hours) exceeds fib(n-1); decided at hour 0 (re-used for later retries)."""
    key = ("hands", day)
    if key in S and hour > 0:
        return S[key]
    items = []
    for idx, (ops, need, prio) in tasks.items():
        v, dl = S.get("tval", {}).get(idx, (0.0, 23))
        tt = len(ops) + CFG["travel_est"] + (0.5 if need else 0.0)
        items.append((v / tt, v, tt))
    for idx, job in (jobs or {}).items():
        if idx in tasks:
            continue            # plan job whose seeds / animals are not in yet: it still needs a hand today
        tt = 3 + CFG["travel_est"]
        items.append((CFG["plan_value"] / tt, CFG["plan_value"], tt))
    items.sort(reverse=True)

    def done_value(k):
        cap = (24 - hour) + (23 - hour) * k
        tot = acc = 0.0
        for dens, v, tt in items:
            if acc + tt > cap:
                break
            acc += tt
            tot += v
        return tot
    k, prev_v = 0, done_value(0)
    cut = 0.0
    while k < 14:
        vk = done_value(k + 1)
        marginal = vk - prev_v
        if marginal <= _fib(k) + CFG["hire_idle"]:
            cut = marginal
            break
        k, prev_v = k + 1, vk
    S[key] = k
    lg = S["log"]
    lg["hire_hands"] += k
    lg["hire_cut_value"] += int(cut)
    return k


def _dem_jobs(S, tasks, plan_jobs=None):
    """(tile, n_ops, wheat, fert, prio, value, production-affecting) per open task; plan PLANT jobs whose seeds are not
    bought yet (no task before the hour-0 purchase) are added as plant + water."""
    out = []
    for idx, job in (plan_jobs or {}).items():
        if idx not in tasks and job and job[0] == "PLANT":
            out.append((idx, 2, 0, 0, 0, float(CFG["plan_value"]), True))
    mj = S.get("mj", {})
    for idx, (ops, need, prio) in tasks.items():
        v, dl = S.get("tval", {}).get(idx, (50.0 * len(ops), 23))
        plan = any(o[0] in ("PLANT", "PLACE", "BUILD_COOP", "BUILD_PASTURE", "DIG") for o in ops)
        mjs = [j for j in mj.get(idx, ()) if not j.get("optional")]
        prod = plan or (not mjs) or any(j.get("units", 0) > 0 or j.get("kind") == "survival" for j in mjs)
        out.append((idx, len(ops), int(need.get("WHEAT", 0)), int(need.get("FERTILIZER", 0)), prio, float(v), bool(prod)))
    return out


def _dem_sim(jobs, units, h0):
    """event simulation of our greedy: units = [(pos, first free hour)]; returns (value done, production jobs done)."""
    import heapq
    upos = [tuple(u[0]) for u in units]
    cw = [0] * len(units)
    cf = [0] * len(units)
    heap = [(u[1], i) for i, u in enumerate(units)]
    heapq.heapify(heap)
    rem = set(range(len(jobs)))
    val = 0.0
    nprod = 0
    while heap and rem:
        t, i = heapq.heappop(heap)
        if t >= 24:
            continue
        p = upos[i]
        best = None
        for j in rem:
            idx, nops, w, f, prio, v, prod = jobs[j]
            tgt = (idx % 10, idx // 10)
            pick = w > cw[i] or f > cf[i]
            if pick:
                sh = _near_shed(p)
                trav = abs(p[0] - sh[0]) + abs(p[1] - sh[1]) + 1 + abs(sh[0] - tgt[0]) + abs(sh[1] - tgt[1])
            else:
                trav = abs(p[0] - tgt[0]) + abs(p[1] - tgt[1])
            if t + trav + nops > 24:
                continue
            c = trav + (10 if (t >= CFG["late_hour"] and prio >= 2) else 0)
            if best is None or c < best[0]:
                best = (c, j, trav, pick)
        if best is None:
            continue                      # nothing this unit can still finish today
        c, j, trav, pick = best
        idx, nops, w, f, prio, v, prod = jobs[j]
        rem.discard(j)
        val += v
        nprod += 1 if prod else 0
        if pick:
            cw[i] = max(cw[i], w + 1)
            cf[i] = max(cf[i], f)
        cw[i] = max(0, cw[i] - w)
        cf[i] = max(0, cf[i] - f)
        upos[i] = (idx % 10, idx // 10)
        heapq.heappush(heap, (t + trav + nops, i))
    return val, nprod


def _dem_choose(S, jobs, base_units, h_spawn, hires_today, kmax):
    spawn_pts = [(4, 4), (5, 4), (4, 5), (5, 5)]
    cache = {}

    def run(k):
        if k not in cache:
            units = list(base_units) + [(spawn_pts[i % 4], h_spawn) for i in range(k)]
            cache[k] = _dem_sim(jobs, units, h_spawn)
        return cache[k]
    if CFG["hire_demand"] == "all":
        target = run(kmax)[1]
        lo, hi = 0, kmax
        while lo < hi:                    # smallest k reaching the production jobs done at k_max (bisection)
            mid = (lo + hi) // 2
            if run(mid)[1] >= target:
                hi = mid
            else:
                lo = mid + 1
        return lo, len(cache)
    k = 0
    while k < kmax:                       # marginal: the (k+1)-th hand must pay its fib wage in completed job value
        gain = run(k + 1)[0] - run(k)[0]
        if gain < _fib(hires_today + k):
            break
        k += 1
    return k, len(cache)


def _demand_hands(S, day, hour, tasks, pos, farm, obs_=None, plan_jobs=None):
    """hands wanted today (hires issued from hour 0; a later hire only when the job list grew unforeseeably)."""
    st = S.setdefault("dem", {})
    kmax = CFG["dem_kmax"]
    if st.get("day") != day:
        t0 = time.time()
        jobs = _dem_jobs(S, tasks, plan_jobs)
        # cash at hour 0: hires come first (as in the target-hands rule, which sells stock to fund them); k is capped by
        # cash + the sellable shed stock at 85% of today's price (2026-09-25: reserving the day's purchases first zeroed
        # the hands on cash-bound opening days and started a death spiral)
        money = float(farm.get("money", 0))
        prices_ = dict(_g(_g(obs_, "market", {}), "prices", {})) if obs_ is not None else {}
        shed_ = dict(_g(_g(obs_, "private", {}), "shed", {})) if obs_ is not None else {}
        fund = money + sum(float(prices_.get(k_, 0)) * 0.85 * float(v_) for k_, v_ in shed_.items() if k_ in PRODUCTS)
        hires_today = int(farm.get("hires_today", 0))
        kcash, spent = 0, 0.0
        while kcash < kmax and spent + _fib(hires_today + kcash) <= fund:
            spent += _fib(hires_today + kcash)
            kcash += 1
        k, nsim = _dem_choose(S, jobs, [(tuple(pos[0]), hour)], hour + 1, hires_today, max(0, kcash))
        if kcash < kmax:
            S["log"]["dem_cash_capped"] += 1
        st.update(day=day, k=k, seen=set(tasks))
        S["log"]["dem_ms"] += int(1000 * (time.time() - t0))
        S["log"]["dem_sims"] += nsim
        S["log"]["dem_k_sum"] += k
        return k
    if 0 < hour <= 12:
        new = [i for i in tasks if i not in st["seen"]]
        if new:
            st["seen"] |= set(new)
            jobs = _dem_jobs(S, {i: tasks[i] for i in new})
            if sum(j[5] for j in jobs if j[6]) >= CFG["dem_rehire_value"]:
                t0 = time.time()
                have = len(pos) - 1
                alljobs = _dem_jobs(S, tasks)
                units = [(tuple(q), hour) for q in pos]
                k2, nsim = _dem_choose(S, alljobs, units, hour + 1, int(farm.get("hires_today", 0)), max(0, kmax - have))
                S["log"]["dem_ms"] += int(1000 * (time.time() - t0))
                S["log"]["dem_sims"] += nsim
                if have + k2 > st["k"]:
                    S["log"]["dem_rehire"] += 1
                    st["k"] = have + k2
    return st["k"]


# ---- the engine's price curve (copied from kaggle_environments kaggriculture.py 1.32.7: MARKET_PARAMS, _shape,
# market_price) for sd_books_walk: the price a unit gets = f(market stock), the stock grows by one per unit sold
_MKT_I0, _MKT_FLOOR, _MKT_HINGE = 10000, 1, 8.0
_MKT_PARAMS = {
    "WHEAT":      {"base":  25, "T": 400, "below_func": "sqrt",   "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base":  35, "T": 450, "below_func": "hinge",  "below_target": 1.00, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base":  60, "T": 200, "below_func": "hinge",  "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "T": 100, "below_func": "sqrt",   "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "T": 300, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base":  50, "T": 332, "below_func": "hinge",  "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "T": 122, "below_func": "sqrt",   "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "T": 105, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
    "FERTILIZER": {"base": 100, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}


def _mkt_shape(func, x, T):
    x = max(0.0, x)
    if func == "sq":
        return x * x
    if func == "sqrt":
        return x ** 0.5
    if func == "log":
        return _math.log(1.0 + x)
    if func == "hinge":
        u = x / T
        return u + _MKT_HINGE * max(0.0, u - 1.0) ** 2
    return x


def _mkt_price(item, inventory):
    p = _MKT_PARAMS[item]
    base, T = p["base"], p["T"]
    if inventory < _MKT_I0:
        amp = p["below_target"] * base / _mkt_shape(p["below_func"], T, T)
        price = base + amp * _mkt_shape(p["below_func"], _MKT_I0 - inventory, T)
    else:
        amp = p["above_target"] * base / _mkt_shape(p["above_func"], T, T)
        price = base - amp * _mkt_shape(p["above_func"], inventory - _MKT_I0, T)
    return max(_MKT_FLOOR, int(round(price)))


def _walk_cap(item, inventory, minpx, cap=10000):
    """units that can be sold now, one at a time into the stock, before a unit's price would be <= minpx"""
    k = 0
    while k < cap and _mkt_price(item, inventory + k) > minpx:
        k += 1
    return k


_SHOPS_E = {   # kaggle_environments kaggriculture.py SHOPS (each unlocked instance consumes every 4th step after the market)
    "BAKERY": ["EGG", "WHEAT"], "PIZZA_SHOP": ["MILK", "TOMATO", "WHEAT"], "BRUNCH_SPOT": ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE": ["WOOL"], "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"], "PET_CAFE": ["CARROT"],
    "SMOOTHIE_SHOP": ["STRAWBERRY", "MILK"], "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"]}
_HAZ = {}


_PACE = {}


def _pace_tables():
    f_ = CFG.get("sd_books_pace_file") or "results/fresh/threads_20260928/dsm_sell_pace.json"
    if CFG.get("sd_books_pace_map"):               # {episode: table} (leave-fold-out tables: no world's own recording)
        try:
            import json as _j
            from pathlib import Path as _P
            mp_ = _j.loads((_P(__file__).resolve().parents[1] / CFG["sd_books_pace_map"]).read_text())
            f_ = mp_.get(str(_TGT_EP)) or f_
        except Exception:
            pass
    if _PACE.get("_file") != f_:                   # cached per table file (a worker process plays several worlds)
        _PACE.clear()
        _PACE["_file"] = f_
        try:
            import json as _j
            from pathlib import Path as _P
            d_ = _j.loads((_P(__file__).resolve().parents[1] / f_).read_text())
            _PACE["p2"], _PACE["p1"] = d_["p2"], d_["p1"]
        except Exception:
            _PACE["p2"], _PACE["p1"] = {}, {}
    return _PACE


def _haz_tables():
    if not _HAZ:
        try:
            import json as _j
            from pathlib import Path as _P
            base = _P(__file__).resolve().parents[1] / "results/fresh/threads_20260928"
            _HAZ["h2"] = _j.loads((base / "dsm_sell_hazard2.json").read_text())["hazard2"]
            _HAZ["h1"] = _j.loads((base / "dsm_sell_hazard.json").read_text())["hazard"]
        except Exception:
            _HAZ["h2"], _HAZ["h1"] = {}, {}
    return _HAZ


def _rival_infer(S, obs, step, products):
    """rival units sold per (step, product) from the market: stock(t) - stock(t-1) - our sells(t-1) + consumption(t-1)"""
    inv = dict(_g(_g(obs, "market", {}), "inventory", {}) or {})
    prev = S.get("_riv_prev")
    hist = S.setdefault("_riv_hist", {})
    if prev and prev[0] == step - 1 and inv:
        t1 = step - 1
        shops = list(((obs.get("town") or {}).get("unlocked_shops")) or []) if isinstance(obs, dict) else []
        for p in products:
            cons = 0
            if t1 % 4 == 0:
                cons += sum((2 if len(_SHOPS_E.get(sh, ())) == 1 else 1) for sh in shops if p in _SHOPS_E.get(sh, ()))
            if t1 % 24 == 0 and p != "FERTILIZER":
                cons += 1
            r = int(inv.get(p, 0)) - int(prev[1].get(p, 0)) - int(prev[2].get(p, 0)) + cons
            if r > 0:
                hist[(t1, p)] = r
    return inv


def _market(S, obs, day, hour, money, shed, seeds, carried, invs, tasks, jobs, demand, prices,
            unlocked, farm, pos, last_day):
    T = _T
    d = min(day, T.n - 1)
    sells, hires, buys = [], [], []
    endgame = day >= last_day
    # reserves: wheat for today's remaining feeding, fertilizer for pending fertilize
    reserve = Counter()
    n_anim = sum(1 for r in farm["tiles"] for t in r if _animal(t))
    reserve["WHEAT"] = max(0, demand.get("WHEAT", 0) - carried.get("WHEAT", 0)
                           + (n_anim * CFG["wheat_days"] if (day < last_day - 1 and not CFG["sd_wheat_reserve_today"]) else 0))
    n_plants = sum(1 for r in farm["tiles"] for t in r if _is_plant(t))
    tomorrow = 0 if CFG["sd_clean"] else min(len(T.fert[d + 1]) if d + 1 < T.n else 0, n_plants)
    if (CFG["fert_release"] and not CFG.get("fert_follow")) or CFG["sd_clean"]:
        tomorrow = 0                  # xfix: the leader's tomorrow targets are not ours (the module decides our fertilize)
    if CFG["fert_ongoing"]:
        if CFG["fert_reserve_soon"]:
            n_on = 0
            for r in farm["tiles"]:
                for t in r:
                    if _is_plant(t) and CROPS[t["crop"]]["ongoing"] and t.get("fertilized_until_day", -1) <= day:
                        c = CROPS[t["crop"]]
                        age = day - t["planted_day"]
                        last = _ongoing_last_age(t["crop"])
                        if any(c["first"] <= age + k + 1 <= last and (age + k + 1 - c["first"]) % c["interval"] == 0
                               for k in range(1, 4)):
                            n_on += 1
            tomorrow = max(tomorrow, n_on)
        else:
            n_on = sum(1 for r in farm["tiles"] for t in r if _is_plant(t) and CROPS[t["crop"]]["ongoing"])
            tomorrow = max(tomorrow, n_on // 2)
    if CFG["sd_wheat_fert_mand"]:                # tomorrow's mandatory wheat fertilizes (today's age-1 wheat)
        tomorrow = max(tomorrow, sum(1 for r in farm["tiles"] for t in r
                                     if _is_plant(t) and t.get("crop") == "WHEAT" and day - int(t.get("planted_day", day)) == 1))
    reserve["FERTILIZER"] = max(0, demand.get("FERTILIZER", 0) + tomorrow - carried.get("FERTILIZER", 0))
    if CFG["sd_fert_sell"]:
        reserve["FERTILIZER"] = 0         # sd_fert_sell: no fertilizer kept in the shed
        if CFG["sd_fert_sell"] == 2:     # 2: keep only what today's fertilize jobs still need (picked up at trip start)
            reserve["FERTILIZER"] = max(0, demand.get("FERTILIZER", 0) - carried.get("FERTILIZER", 0))
        if CFG["sd_fert_sell"] == 3:     # 3 (user 2026-09-27): the shed keeps tomorrow's fertilizer for route pickups
            need_ = 0                    # (not reduced by what hands carry; the midnight cap ignored for now)
            for r_ in farm["tiles"]:
                for t_ in r_:
                    if not _is_plant(t_) or int(t_.get("fertilized_until_day", -1)) >= day + 1:
                        continue
                    a_ = day - int(t_.get("planted_day", day))
                    cd_ = CROPS.get(t_.get("crop"), {})
                    if t_.get("crop") == "WHEAT" and a_ == 1:
                        need_ += 1
                    elif t_.get("crop") == "CARROT" and a_ in (0, 1):
                        need_ += 1
                    elif cd_.get("ongoing") and a_ + 2 - cd_["first"] >= 0 and (a_ + 2 - cd_["first"]) % max(1, cd_["interval"]) == 0:
                        need_ += 1               # an ongoing crop producing tomorrow night
            reserve["FERTILIZER"] = max(need_, demand.get("FERTILIZER", 0))
            S["log"]["fert_keep_next"] += need_
    TPw_ = S.get("tier") if CFG["sd_tier"] and CFG["sd_tier_wheat"] else None
    if TPw_ and TPw_.get("day") == day:
        left_ = sum(it_["n"] for R_ in TPw_["routes"].values() for it_ in R_["items"][R_["k"]:]
                    if it_["kind"] == "pick" and it_["item"] == "WHEAT")
        if CFG["sd_wheat_pick_now"]:              # + this step's pickups: still in the observed shed, gone before the sale
            pn_ = TPw_.get("_picked_now")
            if pn_ and pn_[0] == int(_g(obs, "step", 0)):
                left_ += int(pn_[1].get("WHEAT", 0))
        reserve["WHEAT"] = max(reserve["WHEAT"], left_)
    TPf_ = S.get("tier") if CFG["sd_tier"] and (CFG["sd_tier_sclu_fert"] or CFG["sd_tier_sclu_outfert"] or CFG["sd_tier_fert_carry"]
                                                 or CFG["sd_tier_fert_shed"] or CFG["sd_tier_fert_merge"] or CFG["sd_path_planner"]
                                                 or CFG["sd_wheat_fert_mand"] or S.get("_manual_today") == day) else None
    if TPf_ and TPf_.get("day") == day:            # sd_tier_sclu_fert: the trips' fertilizer stays in the shed until picked up
        left_f = sum(it_["n"] for R_ in TPf_["routes"].values() for it_ in R_["items"][R_["k"]:]
                     if it_["kind"] == "pick" and it_["item"] == "FERTILIZER")
        reserve["FERTILIZER"] = max(int(reserve.get("FERTILIZER", 0) or 0), left_f)
    if endgame:
        reserve = Counter()
    # sell following the target's cumulative sold units
    pt_ = set(CFG["sd_pattern_tick"] or ())
    bk_ = set(CFG["sd_books_sell"] or ())
    pt_ |= bk_
    for p in PRODUCTS:
        if p in bk_ and not endgame:
            continue                      # sd_books_sell: sold below on the leader's plan
        have = shed.get(p, 0) - reserve.get(p, 0)
        if have <= 0:
            continue
        if p in pt_ and not endgame and hour % 4 != 1:
            continue                      # sd_pattern_tick: sell only right after a consumption tick
        if endgame:
            n = have
        else:
            if CFG["sell_source"] == "shed":
                # mgt_lead_deploy rule: everything as soon as it is in the shed, except the wheat the herd eats
                if p == "WHEAT":
                    n_an = sum(1 for r_ in farm["tiles"] for t_ in r_ if _animal(t_))
                    quota = shed.get("WHEAT", 0) - (n_an * max(0, 28 - day) + 10)
                else:
                    quota = have
            elif CFG["sd_clean"]:
                quota = have                  # sd_clean: no DSM quota (sell_now / sd_fert_sell / the books serve these)
            else:
                quota = T.cum_sold[d].get(p, 0) - S["sold"][p]
                prof_ = CFG["sd_hourly_profile"]
                if prof_ and p in prof_:           # follow the target's hour-of-day pattern within the day
                    prev_ = T.cum_sold[d - 1].get(p, 0) if d >= 1 else 0
                    quota = prev_ + float(prof_[p][hour]) * (T.cum_sold[d].get(p, 0) - prev_) - S["sold"][p]
                    quota = int(quota)
            if p in (CFG.get("sell_now") or ()):
                quota = have                  # sell_now (user): sold as soon as it is in the shed (melons: no demand builds up)
            if CFG["sd_fert_sell"] and p == "FERTILIZER":
                quota = have                  # sd_fert_sell: everything in the shed (above the reserve), now
            n = min(have, quota)
        if n > 0:
            sells.append(["SELL", p, int(n)])
    if CFG["sd_evening_wheat_surplus"] and hour >= int(CFG["sd_ews_hour"]) and day < last_day:
        _evening_wheat_surplus(S, day, shed, invs, farm, sells)
    # shed overflow guard: midnight drop discards above 100
    total = sum(shed.values()) + sum(sum(i.values()) for i in invs)
    sold_now = sum(o[2] for o in sells)
    if CFG["cap_fix"] and not endgame:
        dropped = S.get("capfix_drop") or Counter()
        if hour >= CFG["cap_fix_hour"]:
            proj = total - sold_now
            extra = int(proj - 97 + 0.999)
            if extra > 0:
                order = ["WHEAT"] + sorted((q for q in PRODUCTS if q != "WHEAT"), key=lambda q: prices.get(q, 0))
                for p_ in order:
                    if extra <= 0:
                        break
                    if p_ in pt_ and hour % 4 == 0:
                        continue
                    already = sum(o[2] for o in sells if o[1] == p_)
                    can = shed.get(p_, 0) + dropped.get(p_, 0) - reserve.get(p_, 0) - already
                    k_ = min(can, extra)
                    if k_ > 0:
                        sells.append(["SELL", p_, int(k_)])
                        S["log"]["capfix_sold_" + p_] += int(k_)
                        extra -= k_
        elif hour <= 3:
            n_an = sum(1 for r_ in farm["tiles"] for t_ in r_ if _animal(t_))
            other = sum(v for k_, v in shed.items() if k_ != "WHEAT") + sum(v for k_, v in carried.items() if k_ != "WHEAT")
            keep_cap = max(2 * n_an, 100 - other - CFG["cap_harvest_est"])
            already = sum(o[2] for o in sells if o[1] == "WHEAT")
            k_ = min(shed.get("WHEAT", 0) - reserve.get("WHEAT", 0) - already,
                     shed.get("WHEAT", 0) + carried.get("WHEAT", 0) - already - keep_cap)
            if k_ > 0:
                sells.append(["SELL", "WHEAT", int(k_)])
                S["log"]["capfix_morning_wheat"] += int(k_)
    if CFG["cap_guard"] and not endgame and hour >= CFG["cap_hour"]:
        proj = total - sold_now + CFG["cap_rate"] * (23 - hour)
        extra = int(proj - (100 - CFG["cap_margin"]) + 0.999)
        if extra > 0:
            S["log"]["cap_need"] += extra
            order = ["WHEAT"] + sorted((q for q in PRODUCTS if q != "WHEAT"), key=lambda q: prices.get(q, 0))
            for p in order:
                if extra <= 0:
                    break
                if p in pt_ and hour % 4 == 0:
                    continue
                already = sum(o[2] for o in sells if o[1] == p)
                can = shed.get(p, 0) - reserve.get(p, 0) - already
                k = min(can, extra)
                if k > 0:
                    sells.append(["SELL", p, int(k)])
                    S["log"]["cap_sold_" + p] += int(k)
                    extra -= k
    elif not endgame and hour >= 20 and total - sold_now > 95:
        extra = total - sold_now - 90
        for p in sorted(PRODUCTS, key=lambda q: -(shed.get(q, 0))):
            if extra <= 0:
                break
            if p in pt_ and hour % 4 == 0:
                continue
            already = sum(o[2] for o in sells if o[1] == p)
            can = shed.get(p, 0) - reserve.get(p, 0) - already
            k = min(can, extra)
            if k > 0:
                sells.append(["SELL", p, int(k)])
                extra -= k
    # value estimate of sells (for budgeting this step)
    cash = money + sum(prices.get(o[1], 0) * o[2] * 0.85 for o in sells)
    # hires come first: without hands nothing is maintained (death spiral); sell beyond quota to fund them
    hires = []
    if (not endgame or CFG["hands_d29_fix"]) and hour <= 12 and CFG["hires_first"]:
        want = T.hands[d] + CFG["hire_extra"]
        if CFG["hire_demand"] in ("all", "marginal"):
            want = _demand_hands(S, day, hour, tasks, pos, farm, obs, jobs)
        elif CFG["sched_hire"]:
            want = _sched_hands(S, day, hour, tasks, jobs)
        elif CFG["hands_d29_fix"] and d == T.n - 1 and T.hands[d] == 0 and d > 0:
            # semantics artifact: hands_present of the last day is 0 (the end-of-day hook never runs on day 29)
            want = T.hands[d - 1] + CFG["hire_extra"]
        k = max(0, want - (len(pos) - 1))
        hires_today = int(farm.get("hires_today", 0))
        cost_all = sum(_fib(hires_today + i) for i in range(k))
        if cash < cost_all:
            gap = cost_all - cash
            for p in sorted(PRODUCTS, key=lambda q: -prices.get(q, 0)):
                if gap <= 0:
                    break
                already = sum(o[2] for o in sells if o[1] == p)
                can = shed.get(p, 0) - reserve.get(p, 0) - already
                if can <= 0 or prices.get(p, 0) <= 1:
                    continue
                q = min(can, int(gap // max(1, prices[p] * 0.85)) + 1)
                sells.append(["SELL", p, int(q)])
                gap -= q * prices[p] * 0.85
                cash += q * prices[p] * 0.85
        for i in range(k):
            c = _fib(hires_today + i)
            if cash - c < 0:
                break
            cash -= c
            hires.append(["HIRE"])
    # wheat for feed first (animals are the largest investment)
    wheat_buy = []
    short = False
    if not endgame:
        k = demand.get("WHEAT", 0) - carried.get("WHEAT", 0) - shed.get("WHEAT", 0)
        pw = max(1, prices.get("WHEAT", 25))
        short |= k > int(cash // (pw + 2))
        k = min(k, int(cash // (pw + 2)))
        if k > 0:
            wheat_buy.append(["BUY_PRODUCT", "WHEAT", int(k)])
            cash -= k * (pw + 1)
    # hires
    if not endgame and hour <= 12 and not CFG["hires_first"]:
        want = T.hands[d] + CFG["hire_extra"]
        have = len(pos) - 1
        k = max(0, want - have)
        hires_today = int(farm.get("hires_today", 0))
        for i in range(k):
            c = _fib(hires_today + i)
            if cash - c < 0:
                break
            cash -= c
            hires.append(["HIRE"])
    # land
    nq = len(unlocked) - 1
    if nq < 3:
        q = LAND_ORDER[nq]
        if T.land_day.get(q, 99) <= day:
            if cash >= LAND_PRICES[nq]:
                buys.append(["BUY_LAND"])
                cash -= LAND_PRICES[nq]
            else:
                short = True
    # animals for place jobs
    need_an = Counter()
    for ops, need, prio in tasks.values():
        for k, v in need.items():
            if k in ANIMALS:
                need_an[k] += v
    # also place jobs whose structure is not yet ready (tasks exist anyway via BUILD)
    if CFG["sd_tier"]:                             # tiered plan: the day's structures' animals are bought at once
        tl_ = farm["tiles"]
        for idx_, job_ in jobs.items():
            if job_ and job_[0] == "BUILD" and len(job_) > 2 and job_[2] in ANIMALS:
                t_ = tl_[idx_ // 10][idx_ % 10]
                if isinstance(t_, dict) and "animal" in t_:
                    continue
                if idx_ in tasks and any(k_ in ANIMALS for k_ in tasks[idx_][1]):
                    continue
                need_an[job_[2]] += 1
    for sp, v in need_an.items():
        k = v - shed.get(sp, 0) - carried.get(sp, 0)
        short |= k > int(cash // ANIMALS[sp]["cost"])
        k = min(k, int(cash // ANIMALS[sp]["cost"]))
        if k > 0:
            buys.append(["BUY_ANIMAL", sp, int(k)])
            cash -= k * ANIMALS[sp]["cost"]
    # seeds
    need_seed = Counter()
    for idx, job in jobs.items():
        if job[0] == "PLANT":
            need_seed[job[1]] += 1
    if CFG["seed_fund"] and hour <= 2 and not endgame:
        cost_seeds = sum(max(0, v - seeds.get(c_, 0)) * CROPS[c_]["seed"] for c_, v in need_seed.items())
        if cash < cost_seeds:
            gap = cost_seeds - cash
            for p in sorted(PRODUCTS, key=lambda q: -prices.get(q, 0)):
                if gap <= 0:
                    break
                already = sum(o[2] for o in sells if o[1] == p)
                can = shed.get(p, 0) - reserve.get(p, 0) - already
                if can <= 0 or prices.get(p, 0) <= 1:
                    continue
                q = min(can, int(gap // max(1, prices[p] * 0.85)) + 1)
                sells.append(["SELL", p, int(q)])
                gap -= q * prices[p] * 0.85
                cash += q * prices[p] * 0.85
                S["log"]["seed_fund_sold"] += int(q)
    for crop, v in need_seed.items():
        k = v - seeds.get(crop, 0)
        short |= k > int(cash // CROPS[crop]["seed"])
        k = min(k, int(cash // CROPS[crop]["seed"]))
        if k > 0:
            buys.append(["BUY_SEED", crop, int(k)])
            cash -= k * CROPS[crop]["seed"]
    # assemble within the 10-order cap: sells first (cash), then hires, then buys
    buys = wheat_buy + buys
    if CFG["hire_source"] == "leader_steps":
        # the leader's own HIRE orders, at the leader's steps (they fail on cash exactly as orders do)
        hires = [["HIRE"]] * int(getattr(T, "hire_steps", {}).get(int(_g(obs, "step", 0)), 0))
    orders = []
    hire_cost = sum(_fib(int(farm.get("hires_today", 0)) + i) for i in range(len(hires)))
    if CFG["hires_at_front"] and hires and money >= hire_cost:
        # hands hired at hour h act from h+1: every hour a hire waits costs a unit-hour
        orders += hires[:10]
        hires = hires[10:]
    elif CFG["hires_at_front"] and hires:
        # fund the hires with the fewest, most valuable sales first, then hire in the same step
        est = money
        for o in sorted(sells, key=lambda o: -prices.get(o[1], 0) * o[2]):
            if est >= hire_cost or len(orders) >= 4:
                break
            orders.append(o)
            est += prices.get(o[1], 0) * o[2] * 0.85
        room = 10 - len(orders)
        orders += hires[:room]
        hires = hires[room:]
        sells = [o for o in sells if o not in orders]
    for o in sells:
        if len(orders) >= 4 and hour == 0 and not CFG["hires_at_front"]:
            break
        if len(orders) >= 10:
            break
        orders.append(o)
    room = 10 - len(orders) - min(len(buys), 3)
    orders += hires[:max(0, room)]
    for o in buys + sells[len([x for x in orders if x[0] == "SELL"]):]:
        if len(orders) >= 10:
            break
        orders.append(o)
    TPd_ = S.get("tier") if CFG["sd_tier"] and CFG["sd_tier_deliver"] else None
    if TPd_ and TPd_.get("day") == day and TPd_.get("dsell"):
        ds_ = [["SELL", p_, int(n_)] for p_, n_ in TPd_["dsell"].items() if n_ > 0 and p_ not in pt_]
        dsp_ = {o_[1] for o_ in ds_}
        orders = ds_ + [o for o in orders if not (o[0] == "SELL" and o[1] in dsp_)][:max(0, 10 - len(ds_))]
        TPd_["dsell"] = Counter()
    if TPw_ and TPw_.get("day") == day and TPw_.get("wheat_buy") and not TPw_.get("wheat_bought") and hour <= 1:
        k_ = int(TPw_["wheat_buy"])
        pw_ = max(1, prices.get("WHEAT", 25))
        k_ = min(k_, int(money // (pw_ + 2)))
        if k_ > 0:                                 # first in the list: it lands before the hour-1 pickups
            orders = [["BUY_PRODUCT", "WHEAT", k_]] + [o for o in orders if not (o[0] == "BUY_PRODUCT" and o[1] == "WHEAT")][:9]
        TPw_["wheat_bought"] = True
    if float(CFG["sd_h0_front_gain"]) > 0 and hour == 1 and (S.get("h0q") or {}).get("day") == day:   # learn the edge
        q_ = S["h0q"]
        ed_ = S.setdefault("h0edge", dict(CFG["sd_h0_front_edge0"] or {}))
        for p_, q0_ in q_["q"].items():
            if p_ not in q_["sold"] and q0_ > 0 and float(prices.get(p_, 0) or 0) > 0:
                ed_[p_] = 0.8 * float(ed_.get(p_, 0.0)) + 0.2 * (q0_ - float(prices.get(p_, 0)))
        q_["day"] = -1
    TPq_ = S.get("tier") if CFG["sd_tier"] else None
    if CFG["sd_hourly_profile"] and hour == 23 and not endgame and TPq_ and TPq_.get("day") == day:
        for p_ in CFG["sd_hourly_profile"]:
            tot_ = T.cum_sold[d].get(p_, 0)
            today_ = tot_ - (T.cum_sold[d - 1].get(p_, 0) if d >= 1 else 0)
            TPq_["cnt"]["q_day|" + p_] += max(0, today_)
            TPq_["cnt"]["q_behind|" + p_] += max(0, int(tot_ - S["sold"][p_]))
            TPq_["cnt"]["q_ahead|" + p_] += max(0, int(S["sold"][p_] - tot_))
        sc_ = TPq_.setdefault("summary", {}).setdefault("cnt", {})   # the day's summary was written before this market
        for k_, v_ in TPq_["cnt"].items():
            if k_.startswith("q_"):
                sc_[k_] = v_
    TPh_ = S.get("tier") if CFG["sd_tier"] else None
    if CFG["sd_h0_front"] and hour == 0 and not endgame and TPh_ and TPh_.get("day") == day and TPh_.get("h0_front"):
        fr_ = [["SELL", p_, int(shed.get(p_, 0) or 0)] for p_ in TPh_["h0_front"] if int(shed.get(p_, 0) or 0) > 0]
        if CFG["sd_hourly_profile"]:               # only the pattern's hour-0 share
            prof_ = CFG["sd_hourly_profile"]
            fr2_ = []
            for o_ in fr_:
                p_ = o_[1]
                if p_ in prof_:
                    prev_ = T.cum_sold[d - 1].get(p_, 0) if d >= 1 else 0
                    q0_ = int(prev_ + float(prof_[p_][0]) * (T.cum_sold[d].get(p_, 0) - prev_) - S["sold"][p_])
                    if q0_ > 0:
                        fr2_.append(["SELL", p_, min(o_[2], q0_)])
                else:
                    fr2_.append(o_)
            fr_ = fr2_
        hires_ = [o for o in orders if o[0] == "HIRE"][:int(TPh_.get("k0", 10))]
        rest_ = [o for o in orders if o[0] != "HIRE" and not (o[0] == "SELL" and o[1] in TPh_["h0_front"])]
        if int(CFG["sd_h0_front_pos"]) == 0:
            orders = (fr_ + hires_ + rest_)[:10]
        else:                                      # control: behind the hires and the wheat buy
            orders = (hires_ + rest_[:max(0, 10 - len(hires_) - len(fr_))] + fr_)[:10]
        TPh_["cnt"]["h0_front_units"] += sum(o[2] for o in fr_)
        TPh_["cnt"]["h0_front_days"] += 1
    if CFG["sd_evening_sell"] and not endgame:
        E_ = S.setdefault("eve", {})
        if E_.get("day") != day and hour >= 1:     # the first market after the midnight dump: set the evening reserve
            E_.clear()
            E_["day"] = day
            E_["res"] = {p_: int(round(float(CFG["sd_evening_frac"]) * int(shed.get(p_, 0) or 0))) for p_ in CFG["sd_evening_sell"]}
        res_ = E_.get("res") if E_.get("day") == day else None
        if res_:
            h0_ = int(CFG["sd_evening_hour"])
            new_ = []
            rel_ = {}
            if hour >= h0_:                        # release the reserve evenly over the evening hours
                for p_ in res_:
                    rel_[p_] = res_[p_] if hour >= 23 else -(-res_[p_] // (24 - hour))
            for o in orders:
                if o[0] == "SELL" and o[1] in res_:
                    cap_ = int(shed.get(o[1], 0) or 0) - (res_[o[1]] - rel_.get(o[1], 0))
                    q_ = min(max(int(o[2]), rel_.get(o[1], 0)), cap_)
                    if q_ <= 0:
                        continue
                    o = ["SELL", o[1], q_]
                new_.append(o)
            for p_, k_ in rel_.items():            # evening releases with no regular sell order this hour
                k_ = min(k_, int(shed.get(p_, 0) or 0))
                if k_ > 0 and not any(o[0] == "SELL" and o[1] == p_ for o in new_):
                    new_.append(["SELL", p_, k_])
            for p_, k_ in rel_.items():
                res_[p_] = max(0, res_[p_] - k_)
            orders = new_[:10]
    hz_ = CFG["sd_books_source"] == "hazard"
    pc_ = CFG["sd_books_source"] == "pace"
    dfree_ = hz_ or pc_                            # DSM-free sellers: no recorded plan, the rival read from the market
    inv_riv_ = _rival_infer(S, obs, int(_g(obs, "step", 0)), bk_) if (bk_ and dfree_) else None
    if bk_ and not endgame:                        # sd_books_sell: the leader's sell plan, capped by our shed
        DS_ = None if dfree_ else _dsm_data("sales")
        if DS_ is not None or dfree_:
            if dfree_:
                S["_books_cum"] = {}
            if S.get("_sold_d0_day") != day:       # sd_books_source pace: our sales count at the start of the day
                S["_sold_d0"] = {q_: int(S["sold"][q_]) for q_ in PRODUCTS}
                S["_sold_d0_day"] = day
            elif S.get("_books_cum") is None:
                cum_, run_ = {}, Counter()
                for t_ in range(0, 720):          # from step 0: the harness starts S["sold"] with the leader's days 0-10
                    for p_, v_ in (DS_["steps"].get(str(t_)) or {}).items():
                        run_[p_] += int(v_["n"])
                    cum_[t_] = dict(run_)
                S["_books_cum"] = cum_
            step_ = int(_g(obs, "step", 0))
            cum_ = S["_books_cum"]
            orders = [o for o in orders if not (o[0] == "SELL" and o[1] in bk_)]
            front_ = []
            for p_ in sorted(bk_):
                have_ = int(shed.get(p_, 0) or 0)
                if hz_:                            # DSM-free: DSM's learned hazard x our shed stock
                    H_ = _haz_tables()
                    ph_ = "early" if day <= 17 else ("mid" if day <= 23 else "late")
                    rh_ = S.get("_riv_hist") or {}
                    dd_ = [day - k for k in (1, 2, 3) if day - k >= 11]
                    now_ = soon_ = 0
                    if dd_:
                        now_ = int(sum(rh_.get((d_ * 24 + hour, p_), 0) for d_ in dd_) / len(dd_) >= 1)
                        soon_ = int(sum(rh_.get((d_ * 24 + hh_, p_), 0) for d_ in dd_ for hh_ in range(hour + 1, min(24, hour + 5))) / len(dd_) >= 2)
                    hzv_ = H_["h2"].get("%s|%s|%d|%d|%d" % (p_, ph_, hour, now_, soon_), H_["h1"].get("%s|%s|%d" % (p_, ph_, hour), 0.0))
                    q_ = int(round(float(hzv_) * have_))
                    if q_ > 0:
                        front_.append((0, ["SELL", p_, min(have_, q_)]))
                    continue
                if pc_:                            # DSM-free: DSM's learned pace x our day's goods
                    P_ = _pace_tables()
                    ph_ = "early" if day <= 17 else ("mid" if day <= 23 else "late")
                    rh_ = S.get("_riv_hist") or {}
                    dd_ = [day - k for k in (1, 2, 3) if day - k >= 11]
                    now_ = soon_ = 0
                    if dd_:
                        now_ = int(sum(rh_.get((d_ * 24 + hour, p_), 0) for d_ in dd_) / len(dd_) >= 1)
                        soon_ = int(sum(rh_.get((d_ * 24 + hh_, p_), 0) for d_ in dd_ for hh_ in range(hour + 1, min(24, hour + 5))) / len(dd_) >= 2)
                    k1_ = "%s|%s|%d" % (p_, ph_, hour)
                    pv_ = float(P_["p2"].get("%s|%d|%d" % (k1_, now_, soon_), P_["p1"].get(k1_, 0.0)))
                    st_ = int(S["sold"][p_]) - int((S.get("_sold_d0") or {}).get(p_, 0))
                    q_ = int(round(pv_ * (have_ + st_))) - st_
                    fx_ = float(CFG["sd_books_front"] or 0)
                    if fx_ > 0 and dd_ and have_ > 0:      # sd_books_front: gone before the rival's usual selling hours
                        R_ = [sum(rh_.get((d_ * 24 + hh_, p_), 0) for d_ in dd_) / len(dd_) for hh_ in range(24)]
                        tot_ = sum(R_)
                        if tot_ >= float(CFG["sd_books_front_min"]):
                            hl_ = max(hh_ for hh_ in range(24) if R_[hh_] > 0)
                            cum_r_, hx_ = 0.0, hl_
                            for hh_ in range(24):
                                cum_r_ += R_[hh_]
                                if cum_r_ >= fx_ * tot_ - 1e-9:
                                    hx_ = hh_
                                    break
                            end_ = hx_ if hour <= hx_ else (hl_ if hour <= hl_ else None)
                            if end_ is not None and hour >= 1:
                                qf_ = -(-have_ // (end_ - hour + 1))
                                if qf_ > q_:
                                    S["log"]["books_front_" + p_] += min(have_, qf_) - max(0, q_)
                                    q_ = qf_
                    if q_ > 0:
                        front_.append((0, ["SELL", p_, min(have_, q_)]))
                    continue
                q_ = int((cum_.get(step_) or {}).get(p_, 0)) - int(S["sold"][p_])
                if int(CFG["sd_books_h0_lot"]) and hour == 0:   # hour 0: DSM's own lot only, the backlog waits for the tick
                    q_ = min(q_, int((cum_.get(step_) or {}).get(p_, 0)) - int((cum_.get(step_ - 1) or {}).get(p_, 0)))
                if p_ in (CFG["sd_books_even"] or ()):  # user: the backlog in equal lots over the remaining post-tick hours
                    lot_ = int((cum_.get(step_) or {}).get(p_, 0)) - int((cum_.get(step_ - 1) or {}).get(p_, 0))
                    back_ = q_ - lot_
                    if back_ > 0:
                        rem_ = [hh_ for hh_ in (1, 5, 9, 13, 17, 21) if hh_ >= hour]
                        if hour in (1, 5, 9, 13, 17, 21) and rem_:
                            q_ = lot_ + -(-back_ // len(rem_))
                        elif rem_:
                            q_ = lot_
                        S["log"]["books_even_" + p_] += 1
                if hour == 21:                     # our surplus over the leader's next sd_books_sur_h steps goes now
                    nxt_ = int((cum_.get(min(719, step_ + int(CFG["sd_books_sur_h"]))) or {}).get(p_, 0)) - int((cum_.get(step_) or {}).get(p_, 0))
                    sur_ = have_ - nxt_
                    if int(CFG["sd_books_batch"]):     # DSM: small lots, never at the floor
                        sur_ = 0 if float(prices.get(p_, 0) or 0) <= float(CFG["sd_books_minpx"]) else min(sur_, max(q_, 0) + int(CFG["sd_books_batch"]))
                    q_ = max(q_, sur_)
                n_ = min(have_, q_)
                TPb_ = S.get("tier")
                if TPb_ and TPb_.get("day") == day and hour in (1, 5, 13, 21):   # diagnostics: the plan vs our count
                    TPb_["cnt"]["books_h%02d_%s" % (hour, p_)] = "have %d sold %d plan %d q %d step %d" % (
                        have_, int(S["sold"][p_]), int((cum_.get(step_) or {}).get(p_, 0)), q_, step_)
                if n_ > 0:
                    pos_ = int(((DS_["steps"].get(str(step_)) or {}).get(p_) or {}).get("pos", 0))
                    front_.append((pos_, ["SELL", p_, n_]))
            if CFG["sd_books_cap"] and hour >= 21:     # shed capacity at midnight
                TPc_ = S.get("tier") or {}
                load_ = (sum(int(v or 0) for v in shed.values()) + sum(int(v or 0) for inv_ in invs for v in (inv_ or {}).values())
                         + int(TPc_.get("_harv_left", 0) or 0) if TPc_.get("day") == day else 0)
                load_ -= sum(int(o_[2]) for o_ in orders if o_[0] == "SELL") + sum(o_[2] for _, o_ in front_)
                excess_ = load_ - (100 - int(CFG["sd_tier_dump_buffer"]))
                if int(CFG["sd_books_cap_order"]):     # room from every product in the shed, cheapest first; protected ones last
                    prot_ = set(CFG["sd_books_cap_protect"] or ())
                    cf2_ = S.setdefault("_cap_free", set())
                    for p_ in sorted([q for q in PRODUCTS if q not in prot_ and int(shed.get(q, 0) or 0) > 0],
                                     key=lambda q: float(prices.get(q, 0) or 0)):
                        if excess_ <= 0:
                            break
                        done_ = sum(o_[2] for _, o_ in front_ if o_[1] == p_) + sum(int(o_[2]) for o_ in orders if o_[0] == "SELL" and o_[1] == p_)
                        k_ = min(int(shed.get(p_, 0) or 0) - done_, excess_)
                        if k_ > 0:
                            cf2_.add((int(_g(obs, "step", 0)), p_))
                            hit_ = next((x for x in front_ if x[1][1] == p_), None)
                            if hit_:
                                hit_[1][2] += k_
                            else:
                                front_.append((0, ["SELL", p_, k_]))
                            excess_ -= k_
                            S["log"]["books_cap2_" + p_] += k_
                for p_ in sorted(bk_, key=lambda q: float(prices.get(q, 0) or 0)):
                    if excess_ <= 0:
                        break
                    if int(CFG["sd_books_cap_order"]) and p_ not in set(CFG["sd_books_cap_protect"] or ()):
                        continue                   # already offered above
                    done_ = sum(o_[2] for _, o_ in front_ if o_[1] == p_)
                    k_ = min(int(shed.get(p_, 0) or 0) - done_, excess_)
                    prot2_ = int(CFG["sd_books_cap_order"]) and p_ in set(CFG["sd_books_cap_protect"] or ())
                    if int(CFG["sd_books_batch"]) and (not CFG["sd_books_cap_free"] or prot2_):     # DSM: small lots, never at the floor
                        k_ = 0 if float(prices.get(p_, 0) or 0) <= float(CFG["sd_books_minpx"]) else min(k_, max(0, int(CFG["sd_books_batch"]) - done_))
                    if k_ > 0 and CFG["sd_books_cap_free"] and not prot2_:
                        st_c_ = S.setdefault("_cap_free", set())
                        st_c_.add((int(_g(obs, "step", 0)), p_))   # exempt from the walk floor below (room beats price)
                    if k_ > 0:
                        hit_ = next((x for x in front_ if x[1][1] == p_), None)
                        if hit_:
                            hit_[1][2] += k_
                        else:
                            front_.append((0, ["SELL", p_, k_]))
                        excess_ -= k_
                        S["log"]["books_cap_" + p_] += k_
            if CFG["sd_books_walk"]:                  # never walk a sale down to the floor (DSM: no wool at $1)
                inv_m_ = dict(_g(_g(obs, "market", {}), "inventory", {}) or {})
                kept_ = []
                cf_ = S.get("_cap_free") or set()
                for pos_, o_ in front_:
                    if o_[1] in inv_m_ and (int(_g(obs, "step", 0)), o_[1]) not in cf_:
                        k_ = _walk_cap(o_[1], int(inv_m_[o_[1]]), float(CFG["sd_books_minpx"]), o_[2])
                        if k_ < o_[2]:
                            S["log"]["books_walk_cut_" + o_[1]] += o_[2] - k_
                        o_[2] = k_
                    if o_[2] > 0:
                        kept_.append((pos_, o_))
                front_ = kept_
            for pos_, o_ in sorted(front_, key=lambda x: x[0]):
                orders.insert(min(pos_, len(orders)), o_)
            TPk_ = S.get("tier") or {}
            if int(CFG["sd_books_h0_slots"]) and hour == 0 and TPk_.get("day") == day and TPk_.get("h0_books"):
                nh_, new_ = 0, []                  # sd_books_h0_slots: the hires past the plan's hour-0 count go at hour 1
                for o_ in orders:
                    if o_[0] == "HIRE":
                        nh_ += 1
                        if nh_ > int(TPk_.get("k0", 10)):
                            S["log"]["books_h0_hire_moved"] += 1
                            continue
                    new_.append(o_)
                orders = new_
            TPn_ = S.get("tier") or {}
            if TPn_.get("day") == day and TPn_.get("dsell_now"):   # sd_tier_sclu: the trip's delivery sold on arrival
                for p_, n_ in TPn_["dsell_now"].items():
                    if p_ in bk_ and n_ > 0 and int(CFG["sd_tier_sclu_sell_cap"]) and not dfree_:
                        cum_c_ = S.get("_books_cum") or {}
                        in_ = sum(int(o_[2]) for o_ in orders if o_[0] == "SELL" and o_[1] == p_)
                        n_ = max(0, min(int(n_), int((cum_c_.get(day * 24 + 23) or {}).get(p_, 0)) - int(S["sold"][p_]) - in_))
                        S["log"]["sclu_sell_capped_" + p_] += 1
                    if p_ in bk_ and n_ > 0:
                        hit_ = next((o_ for o_ in orders if o_[0] == "SELL" and o_[1] == p_), None)
                        if hit_:
                            hit_[2] = int(hit_[2]) + int(n_)
                        else:
                            orders.insert(0, ["SELL", p_, int(n_)])
                        S["log"]["sclu_sold_now_" + p_] += int(n_)
                TPn_["dsell_now"] = Counter()
            while len(orders) > 10:                # 10-order cap: never drop a hire or a buy (the hour-0 feed wheat buy:
                # dropping it left the hour-1 hires short of wheat, feeds skipped, KC1 day 19); ordinary sells go first,
                # then the plan's own sells
                drop_ = next((i_ for i_ in range(len(orders) - 1, -1, -1)
                              if orders[i_][0] == "SELL" and orders[i_][1] not in bk_), None)
                if drop_ is None:
                    drop_ = next((i_ for i_ in range(len(orders) - 1, -1, -1) if orders[i_][0] == "SELL"), None)
                if drop_ is None:
                    break
                orders.pop(drop_)
                S["log"]["books_dropped_order"] += 1
    if CFG["sd_final_sell_all"] and int(_g(obs, "step", 0)) >= 718:
        orders = [["SELL", p_, int(shed.get(p_, 0) or 0) + int(carried.get(p_, 0) or 0)] for p_ in PRODUCTS
                  if int(shed.get(p_, 0) or 0) + int(carried.get(p_, 0) or 0) > 0][:10]
    for o in orders:
        if o[0] == "SELL":
            S["sold"][o[1]] += o[2]
    if inv_riv_ is not None:                       # sd_books_source hazard: this step's stock and our sells, for the inference
        S["_riv_prev"] = (int(_g(obs, "step", 0)), inv_riv_, {o[1]: int(o[2]) for o in orders if o[0] == "SELL"})
    S["short"] = short
    return orders


# ============================================================================================
# ===== BEGIN SEARCH DISPATCH BLOCK (mgt_lpv_search only; inserted by scripts/search_dispatch_build.py) ======
# Source: scripts/search_dispatch_block.py. This text is inserted verbatim into the agent file (it is not a module):
# it uses the executor's globals CFG, SHED, ANIMALS, CROPS, PRODUCTS, _tile, _near_shed, _step_toward, _is_plant,
# _is_weed, _animal, _fib, _T, _S, _sm, _mj_fert and the deploy's _DEP, DEP_CFG, _MGT_REPORT. stdlib only.
#
# CFG["dispatch_search"]: "off" = nothing below runs (every hook is guarded; the executor is the source deploy's);
# "shadow" = the greedy acts; the planner runs every step and logs its time, its planned drops and its agreement with
# the greedy; "active" = inside CFG["sd_days"] ([lo, hi], None = all days) every non-delivering unit with a planned
# route follows the plan's next step, with a per-unit fallback to the greedy when that step is invalid (and for
# everyone when the planner fails, runs out of its time bank or the day is outside the window).
#
# Every step: the executor's tile tasks (+ predicted jobs: plan plantings whose seeds are bought this step, and the
# same-day replant after a wheat / carrot harvest as an order pair harvest -> plant + water) become jobs with per-op
# coin values and deadlines (the maintenance module's values as _sched_tile_ops reads them; plan jobs = plan_value on
# completion); survival ops (plant dies / animal escapes tonight) are hard. The previous step's routes are the warm
# start (gone jobs dropped, infeasible routes repaired), unplanned jobs are regret-inserted, then relocate / 2-opt /
# or-opt / ruin-and-recreate run inside a work budget (route evaluations: deterministic) and a time cap. Only each
# unit's next step is executed.
#
# Time model (the unit acts at hour t): Manhattan moves; one step per op; one PICKUP step per item type at the shed
# tile of least detour, placed before the first job the unit cannot supply (exact amounts = the route's lowest running
# balance; wheat harvested / fertilizer collected earlier in the route count; the shed stock is shared by the routes);
# the executor's delivery trigger (>= deliver_units or >= deliver_value before late_hour, >= deliver_value_late
# before 20, any value when cash is short) inserts the walk to the nearest shed tile + the DROP / PLACE steps (a pending
# pickup is merged into that visit); release hours; an op after its deadline keeps sd_late_frac of its value; a hard
# op must be on time; only the route's last job may be cut by the day end (maintenance only: plan jobs complete);
# day-29 routes must leave the walk back to the shed. Objective = coins of the ops done - sd_lambda x route time -
# sd_switch x steps already walked toward a job the unit is taken off - sd_cap_w x the projected midnight load (shed
# wheat / fertilizer / animals + everything carried + wheat / fertilizer gained - consumed) above sd_cap - sd_cap_margin.
#
# v2 (2026-09-25, all off by default = v1): v1 carried products to midnight (a delivery cost route time and earned
# nothing, and full routes never went idle), so they sold a day late into lower prices (12 G1 worlds: volume +5.2k /
# +6.9k, price -3.7k / -5.2k). The in-day delivery credit is paid for each deliverable
# unit that reaches the shed by a DROP / PLACE at or before sd_dv_hour (the market sells it the same day: unit actions
# come before the market, and the sell orders are computed from the shed seen at the start of the turn), glut goods
# (melon, milk, wool, strawberry) highest; per-product tables sd_dv_frac (x the current price) + sd_dv_coins (coins,
# optionally by day), swappable for the measured same-day-vs-next-morning margin table; sd_final_trip = after its last job a route walks what it carries to the
# nearest shed tile (the idle rule does that in execution) and gets the credit when the drop is in time. v1 left
# survival ops to hour 23 (thirsty plants still dry at 23h: 20 -> 54 / 66 a game): sd_hard_late_w = coins per hour a
# hard op is done after sd_hard_safe; sd_hard_all = every unit is a candidate for a hard job; sd_hard_eject = a hard
# job nobody can take is inserted where dropping the least value of non-hard jobs makes the route feasible.
#
# v3 (2026-09-25, user ruling: the leaders' harvest timing as tendencies, soft): sd_hv_pref = a small table (empty =
# off, the same table the executor gets later) of bonuses on a HARVEST op: a one-time crop on its last day before decay
# ("decay"), wheat / carrot at the leaders' ages by season part ("ages": [day_from, day_to, age_lo, age_hi]), melons
# once today's water brings them to full yield ("full") and early in the morning (a soft target: "by_hour" /
# "hour_w" = coins per hour later), tomatoes / strawberries at every production; WATER stays before HARVEST. MELON
# "offer": 1 = the planner adds the full-yield melon harvest the executor's tasks skip until the last day (job ("H",
# tile), after the tile's WATER task; value = the bonus, the same-day credit, the soft hour; a planned unit does it).
# sd_cap_all: the midnight shed-load term also counts the products that stay in the shed overnight (beyond the day's
# leader sell quota; with the deploy's sem rule, the held strawberries). sd_mr: a maintenance job's coin value is scaled
# by marginal revenue / price of its product: p(inv) - slope(inv) x our units still to sell this season (the leader's
# season total minus ours), slope = the engine price drop for one more unit at today's market inventory (a sold unit
# raises the inventory for good) x our share of the season's supply beyond the market's remaining consumption, floored
# at sd_mr_floor x p; glut goods lose most, wheat / carrot / egg little.
# sd_early_animal: a BUILD job's animal is bought while the tile still waits for its crop's harvest (the executor's
# market buys animals only for tasks that PLACE them; with harvest_before_build that task appears after the harvest).
# sd_water_first: a task that harvests a one-time crop in its growth window, unwatered today and below cap, waters first
# (the PLANT pipeline's rule; the BUILD / REMOVE harvest paths lacked it: the coop tile's melon was cut at 5 units).
# sd_hire_demand: at hour 0 the planner plans the day with k virtual hires for k in [want - 6, want] (sd_hire_evals
# route evaluations each) and hires the k with the best planned value net of the fib wages (the executor's market hires
# that many). sd_spawn_steer: the farmer's hour-0 stand (stay, a neighbouring shed tile or off the shed) and the split of
# the hires between hour 0 and hour 1 are chosen so the spawn quadrants (least-occupied shed tile, NW NE SW SE order)
# match the plan's work per quadrant. Both act through the market's hire count (CFG hire_extra for the day) and the
# farmer's hour-0 command. sd_hp_parity: the planner values the executor's harvest_policy jobs as the executor does
# (a melon harvest in the leaders' window = held units x price x hp_frac; a melon window water = the melon price);
# sd_split_place: a BUILD + PLACE plan part is split into the structure job (sd_build_value) and the placement job
# (plan_value, successor of the structure): the leader builds the coop at h13 and places the goose at h14.
# sd_bundle_build (user design, replaces the split): every plan BUILD with an animal is one job for one hand: clear the
# tile (WATER if due, HARVEST or DIG) -> BUILD -> PLACE -> FEED -> CARE, the animal and its feed wheat picked up at the
# trip start, valued at a day's delay (a day of the animal's product + fertilizer, sd_bundle_value "auto") on top of the
# clearing ops; never an empty structure (no animal: the structure waits whole). sd_water_tomorrow: a water on a dry
# plant is worth at least this (tomorrow's labour saved: a plant dry today is a must-do tomorrow), and plants without a
# sd_coop_pair (user, main branch M): the structure and its animal as ONE job ([DIG,] BUILD, PLACE: two hours, one hand,
# the animal from the trip start), FEED / CARE upkeep afterwards; a crop on the tile is harvested first and the pair is
# predicted after that harvest; the pair buys its animal from hour 0 (the clearing task carries the need); never an
# empty structure. sd_coop_pair 2: the pair must complete by the day end (hard op:
# sd_hard on the PLACE, deadline the day end, any hour; the clearing harvest is kept planned first).
# sd_idle_v2 (idle fill v2, user rules): only a unit with an empty planned route, outside route insertion, no values:
# its sellable stock + fertilizer to the shed while a same-day sale is possible, else the nearest dry unplanned plant
# in its home quadrant.
# sd_plan_once (user, M_once): one full-day plan per unit at the first step from h1 with all of the day's hires on the
# board (sd_once_evals evaluations); afterwards the routes are frozen: no search, no reassignment; repairs are local
# and logged (L["repairs"]): a job gone / infeasible, a new must-do or new job inserted, an empty route refilled.
# sd_fert_frac: applying fertilizer is charged at this fraction of its price in the maintenance module (collection keeps
# the full price; sd_fert_first then uses the same charged price). sd_retire: plants the plan retires (abandoned, or
# their tile cleared by the plan before they could produce again) get no hard water job.
# sd_coop_by: the PLACE's hard deadline hour while that hour is ahead (the day end once it has passed): slack before the
# survival fallback. sd_coop_place: in hook 3 any unit standing on its empty structure with the animal places it.
# (radial corridors, user design) sd_corr_w: each unit's angular corridor around the shed (equal work, by spawn angle,
# disjoint); an op outside it costs sd_corr_w; sd_rad_in / sd_rad_side: coins per inward / sideways step between job
# tiles (the trip works outward; deliveries and pickups are not job-to-job moves).
# task get a planner-only water job; sd_idle_fert: an idle planned unit delivers its fertilizer too.
# v5: sd_surv_fb = from this hour the executor's own survival routes (surv_reserve: a plant dying / an animal escaping
# tonight, nearest-arrival routes) keep their units and tiles: the planner plans neither (guaranteed fallback).
# sectors (2026-09-25, research copy agents/mgt_lead_sector.py): each unit has a home quadrant (a hand: the quadrant of
# the tile it spawned on; the farmer: the second = NW); an op outside home costs sd_sector_w coins in the route objective
# (a soft term, not a constraint; hard / survival ops and plan structural jobs PLANT / BUILD / PLACE are exempt). At the
# hours sd_sector_hours the homes rebalance: while one quadrant's remaining ops per home hand exceed sd_sector_ratio x
# another's, the hand of the lighter quadrant nearest to the heavier one moves its home there. Pickups stay sized to each
# route's own need (the route evaluation's running balance), never to a sector's. sd_hop_w = coins per step of a hop
# beyond one between consecutive job tiles of a route (user: each trip works a chain of adjacent tiles), applied in the
# patch only: tiles within sd_hop_central steps of the shed (the animals) are en-route ops on the way out / back.
# ============================================================================================
import random as _sd_random

_SD_SP = ("GOOSE", "COW", "SHEEP")
_SD_SPI = {s: i for i, s in enumerate(_SD_SP)}
_SD_Z3 = (0, 0, 0)
_SD_TAB = []           # [D, SD, SA, DS, NS] 100 x 100 tile tables (built once per process)
_SD_MOVES = ("NORTH", "SOUTH", "EAST", "WEST")
_SD_WORK = ("WATER", "FEED", "CARE", "HARVEST", "FERTILIZE", "COLLECT_FERTILIZER", "PLANT", "DIG", "BUILD_COOP",
            "BUILD_PASTURE")
_SD_PLANC = ("PLANT", "PLACE", "BUILD_COOP", "BUILD_PASTURE")
_SD_FAIL = (False, 0.0, 99, 0, 0, _SD_Z3, -1, 0, None)
_SD_FAILS = {k: (False, 0.0, k, 0, 0, _SD_Z3, -1, 0, None) for k in (
    "stock_a", "hard_stock", "pred_later", "pred_none", "dayend", "cut", "hard_late", "lastday")}
_SD_T = []             # [entry time of the current step] (set by the entry point)
# job tuple: 0 tile, 1 n ops, 2 wheat need, 3 fertilizer need, 4 animal species index (-1), 5 wheat gained, 6 fertilizer
# gained, 7 per-op values, 8 per-op deadlines, 9 release hour, 10 hard op index (-1), 11 predecessor job (-1), 12 lag
# after the predecessor's finish, 13 is a predecessor, 14 leading ops that may stand alone when the day ends inside the
# job (maintenance: all; plan parts: 0), 15 deliverable units gained, 16 deliverable value gained, 17 deliverable
# product types gained, 18 FERTILIZE op indices, 19 FEED (+ CARE) op indices (skipped when the item cannot be had),
# 20 in-day delivery credit gained (v2), 21 soft time target (op index, hour, coins per hour later) or None (v3),
# 22 quadrant index (0 NW, 1 NE, 2 SW, 3 SE), 23 exempt from the sector term (hard op or plan structural job)


def _sd_dv_table(S, day, prices, shed):
    """v2: coins credited per unit of each product delivered in time for a same-day sale = CFG sd_dv_frac[p] x the
    current price + CFG sd_dv_coins[p] (a number, or [[first_day, coins], ...]: the last entry with first_day <= day).
    Wheat is never deliverable here (the executor keeps it for feeding). sd_dv_quota with the leader sell rule
    (sell_source "leader": we sell up to the leader's cumulative units of the day): only products whose quota still
    has room after the units already in the shed (the rule then reproduces the leaders: melons sold the day they are
    picked, strawberries / tomatoes mostly the next morning)."""
    fr = CFG["sd_dv_frac"] or {}
    co = CFG["sd_dv_coins"] or {}
    gate = bool(CFG["sd_dv_quota"]) and CFG.get("sell_source") == "leader" and _T is not None and not CFG["sd_clean"]
    d_ = min(day, _T.n - 1) if gate else 0
    out = {}
    for k in PRODUCTS:
        if k == "WHEAT":
            continue
        if gate and _T.cum_sold[d_].get(k, 0) - S["sold"][k] - int(shed.get(k, 0) or 0) <= 0:
            continue
        c = co.get(k, 0.0)
        if isinstance(c, (list, tuple)):
            cc = 0.0
            for d0, v0 in c:
                if day >= int(d0):
                    cc = float(v0)
            c = cc
        per = float(fr.get(k, 0.0)) * float(prices.get(k, 0) or 0) + float(c)
        if per > 0:
            out[k] = per
    return out


def _sd_tables():
    if not _SD_TAB:
        D = [[abs(a % 10 - b % 10) + abs(a // 10 - b // 10) for b in range(100)] for a in range(100)]
        sheds = [q[1] * 10 + q[0] for q in SHED]
        SD = [[0] * 100 for _ in range(100)]
        SA = [[0] * 100 for _ in range(100)]
        for a in range(100):
            Da = D[a]
            for b in range(100):
                best = None
                for s in sheds:
                    c = (Da[s] + D[s][b], Da[s], s)       # least detour, then the shed nearest to the unit
                    if best is None or c < best:
                        best = c
                SD[a][b] = best[0]
                SA[a][b] = best[2]
        DS = [min(D[a][s] for s in sheds) for a in range(100)]
        NS = []
        for a in range(100):
            q = _near_shed((a % 10, a // 10))             # the executor's delivery target
            NS.append(q[1] * 10 + q[0])
        _SD_TAB.extend([D, SD, SA, DS, NS])
    return _SD_TAB


def _sd_state(S):
    L = S.get("sd")
    if L is None:
        L = {"day": -1, "routes": {}, "walk": {}, "pred_seen": {}, "recs": [], "path": None, "off": False,
             "prev_kind": None, "prev_thirst": None, "water23": set(), "seq": {}, "seq_day": -1, "lastP": None,
             "final_done": False,
             "st": {"steps": 0, "plan_ms": [], "plan_ms_first": [], "step_ms": [], "evals": 0, "time_capped": 0,
                    "errors": 0, "last_error": "", "fb_step": 0, "fb_unit": 0, "fb_pickup": 0, "fb_noop": 0,
                    "fb_notask": 0, "idle_unit": 0, "planned_unit": 0, "pred_wait": 0, "switch_steps": 0,
                    "moves": 0, "work": 0, "shed_cmds": 0, "shed_visits": 0, "shed_arrivals": 0, "passes": 0,
                    "walk_after_last": 0, "walk_after_last_nodeliv": 0, "unit_days": 0, "unit_steps": 0,
                    "dropped_jobs": 0, "dropped_value": 0.0, "dropped_prod_jobs": 0, "dropped_prod_value": 0.0,
                    "dropped_prod_units": 0, "dropped_hard": 0, "plants_lost": 0, "plants_lost_thirst": 0,
                    "animals_lost": 0, "planned_drop_first": 0, "planned_drop_first_value": 0.0,
                    "planned_hard_unplanned": 0, "deliv_deferred": 0, "agree": 0, "agree_n": 0, "bank_used": 0.0, "steps_over_1s": 0,
                    "rr_tried": 0, "rr_acc": 0, "load_proj_h23": [], "cash0": [], "days_planned": 0,
                    "forced_hard": 0, "idle_deliver": 0, "offered_harvest": 0, "surv_fb_units": 0}}
        S["sd"] = L
    return L


class _SdP(object):
    """one planning problem (jobs, units, plan state)."""
    pass


def _sd_want_hands(day):
    """the market's default hand count for the day (hire_demand / sched_hire off)."""
    T = _T
    d = min(day, T.n - 1)
    want = T.hands[d] + CFG["hire_extra"]
    if CFG["hands_d29_fix"] and d == T.n - 1 and T.hands[d] == 0 and d > 0:
        want = T.hands[d - 1] + CFG["hire_extra"]
    return max(0, int(want))


def _sd_spawn(pos, k):
    """spawn tiles of k hires in order (engine rule: least occupied shed tile, NWSE order)."""
    order = [(4, 4), (5, 4), (4, 5), (5, 5)]
    occ = {q: 0 for q in order}
    for p in pos:
        if tuple(p) in occ:
            occ[tuple(p)] += 1
    out = []
    for _ in range(k):
        q = sorted(order, key=lambda q: (occ[q], order.index(q)))[0]
        occ[q] += 1
        out.append(q)
    return out


def _sd_harvest(t, cmds, day):
    """(product, units) a HARVEST in this op list takes (a WATER earlier in the list included)."""
    if not isinstance(t, dict):
        return None, 0
    if _is_plant(t):
        c = CROPS.get(t.get("crop"))
        if c is None:
            return None, 0
        y = int(t.get("yield_units", 0) or 0)
        if not c["ongoing"] and "WATER" in cmds and not t.get("watered_today"):
            ws = (c["maxday"] + 1) // 2
            age = day - int(t.get("planted_day", day))
            if ws <= age <= c["maxday"]:
                y = min(c["max"], y + (2 if t.get("fertilized_until_day", -1) >= day else 1))
        return t.get("crop"), y
    sp = _animal(t)
    if sp:
        return ANIMALS[sp]["product"], int(t.get("yield_units", 0) or 0)
    return None, 0


_SD_MR = {}            # v3: product -> marginal revenue / price of this step (sd_mr)
_SD_MKT = {"WHEAT": (25, 400, "sqrt", 0.80, "log", 0.20), "CARROT": (35, 450, "hinge", 1.00, "sqrt", 0.70),
           "TOMATO": (60, 200, "hinge", 0.40, "sqrt", 0.60), "STRAWBERRY": (120, 100, "sqrt", 0.70, "linear", 1.60),
           "MELON": (250, 300, "log", 0.20, "sq", 3.60), "EGG": (50, 332, "hinge", 0.40, "log", 0.20),
           "MILK": (160, 122, "sqrt", 0.60, "linear", 1.60), "WOOL": (200, 105, "log", 0.20, "sq", 3.20),
           "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40)}   # engine market params (docs/environment.md)


def _sd_price(item, inv):
    """the engine's price curve, unrounded (base, T, below shape / target, above shape / target; I0 = 10000)."""
    import math
    base, T, fb, tb, fa, ta = _SD_MKT[item]

    def f(fn, x):
        x = max(0.0, x)
        if fn == "linear":
            return x
        if fn == "sq":
            return x * x
        if fn == "sqrt":
            return x ** 0.5
        if fn == "log":
            return math.log(1.0 + x)
        u = x / T
        return u + 8.0 * max(0.0, u - 1.0) ** 2
    if inv < 10000:
        return base + tb * base / f(fb, T) * f(fb, 10000 - inv)
    return max(1.0, base - ta * base / f(fa, T) * f(fa, inv - 10000))


_SD_SHOPS = {"BAKERY": ("EGG", "WHEAT"), "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
             "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"), "YARN_STORE": ("WOOL",),
             "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"), "PET_CAFE": ("CARROT",),
             "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"), "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY")}


def _sd_mr_table(S, obs, day, st):
    """v3: product -> marginal revenue / price. A unit sold raises the market inventory for good, so it costs our later
    units the price slope each; only the supply beyond the market's remaining consumption stays (demand now: town
    center 1 a day, 6 a day per listed shop product, 12 for a single-product shop; future shops ignored): loss = chord
    slope over 10 units x max(0, our units still to sell x 2 (the rival assumed alike) - consumption) / 2."""
    out = {}
    inv = dict(((obs.get("market") or {}).get("inventory")) or {})
    dem = Counter({k: 1 for k in PRODUCTS if k != "FERTILIZER"})
    for sh in list(((obs.get("town") or {}).get("unlocked_shops")) or []):
        ps = _SD_SHOPS.get(str(sh), ())
        for q in ps:
            dem[q] += 12 if len(ps) == 1 else 6
    rem = max(0, 29 - day) + 1
    fl = float(CFG["sd_mr_floor"])
    for k in PRODUCTS:
        if k not in inv or k not in _SD_MKT:
            continue
        x = float(inv[k])
        p0 = _sd_price(k, x)
        sl = max(0.0, (p0 - _sd_price(k, x + 10)) / 10.0)
        try:
            n = max(0, int(_T.cum_sold[_T.n - 1].get(k, 0)) - int(S["sold"][k]))
        except Exception:
            n = 0
        mr = p0 - sl * max(0.0, 2.0 * n - dem[k] * rem) / 2.0
        r = max(fl, min(1.0, mr / p0)) if p0 > 0 else 1.0
        out[k] = r
        if st is not None:
            st["mrs_" + k] = st.get("mrs_" + k, 0.0) + r
            st["mrv_" + k] = st.get("mrv_" + k, 0.0) + max(0.0, mr)
    if st is not None:
        st["mrn"] = st.get("mrn", 0) + 1
    return out


def _sd_hv_pref(t, cmds, vals, day):
    """v3: the leaders' harvest timing as soft preferences (CFG sd_hv_pref; {} = off). Returns (vals with a bonus on
    the HARVEST op, soft time target (op index, hour, coins per hour later) or None)."""
    tab = CFG["sd_hv_pref"]
    if not tab or "HARVEST" not in cmds or not _is_plant(t):
        return vals, None
    crop = t.get("crop")
    c = CROPS.get(crop)
    if c is None:
        return vals, None
    prod, units = _sd_harvest(t, cmds, day)
    if units <= 0:
        return vals, None
    i = cmds.index("HARVEST")
    age = day - int(t.get("planted_day", day))
    ent = tab.get(crop) or {}
    b = 0.0
    if c["ongoing"]:
        b += float(ent.get("bonus", 0.0))                 # tomatoes / strawberries: every production
    else:
        if age >= c["maxday"]:
            b += float((tab.get("decay") or {}).get("bonus", 0.0))   # decays from tomorrow
        for d0, d1, a0, a1 in ent.get("ages", ()):
            if int(d0) <= day <= int(d1) and int(a0) <= age <= int(a1):
                b += float(ent.get("bonus", 0.0))
                break
        if ent.get("full") and units >= c["max"]:
            b += float(ent.get("bonus", 0.0))             # melons: the first day today's water brings them to 6
    soft = None
    if ent.get("by_hour") is not None and float(ent.get("hour_w", 0.0)) > 0:
        soft = (i, int(ent["by_hour"]), float(ent["hour_w"]))
    if b:
        vals = tuple(v + (b if k == i else 0.0) for k, v in enumerate(vals))
    return vals, soft


def _sd_opvals(S, idx, t, ops, plan, day, E, last_day):
    """(per-op values, per-op deadlines, hard op index, may be cut) of one tile task, by the executor's own values."""
    n = len(ops)
    last = E - 1
    vmin = float(CFG["sd_vmin"])
    if plan:
        return tuple([0.0] * (n - 1) + [float(CFG["plan_value"])]), tuple([last] * n), -1, False
    asset = start = None
    if _is_plant(t):
        asset, start = t.get("crop"), t.get("planted_day")
    elif _animal(t):
        asset, start = t.get("animal"), t.get("placed_day")
    mj = ()
    if CFG["sched_maint"] and (idx, asset, start) in S.get("mj_known", ()):
        mj = S.get("mj", {}).get(idx, ())
    vals, dls, hi = [], [], -1
    used = set()
    for i, o in enumerate(ops):
        c = o[0]
        v, dl, hard = None, last, False
        for k, jm in enumerate(mj):
            if k in used or jm.get("asset") != asset or jm.get("cmd") != c:
                continue
            used.add(k)
            if jm.get("optional"):
                v = float(jm.get("held", 0)) * float(jm.get("price", 0)) * CFG["opt_harvest_frac"]
            else:
                v = max(0.0, float(jm.get("value", 0.0))) * _SD_MR.get(jm.get("product"), 1.0)
                dl = min(last, int(jm.get("deadline", last)))
                hard = jm.get("kind") == "survival"
            break
        if v is None:
            v = 50.0                                  # the executor's own-rule tasks (no solve yet): 50 an op
        if CFG["sd_hp_parity"] and _is_plant(t):     # parity with the executor's harvest_policy task values
            try:
                pr_ = float((S.get("prices") or {}).get(t.get("crop"), 0) or 0)
                if (c == "HARVEST" and CFG.get("harvest_policy") == "leader_tendency"
                        and t.get("crop") in CFG.get("hp_crops", ()) and _hp_window(t, day, idx)):
                    v = max(v, float(t.get("yield_units", 0) or 0) * pr_ * float(CFG["hp_frac"]))
                elif (c == "WATER" and CFG.get("harvest_policy") == "leader_tendency" and t.get("crop") == "MELON"
                      and "MELON" in CFG.get("hp_crops", ()) and 6 <= day - int(t.get("planted_day", day)) <= 10
                      and int(t.get("yield_units", 0) or 0) < CROPS["MELON"]["max"] and not t.get("watered_today")):
                    v = max(v, pr_ or 200.0)
            except Exception:
                pass
        if (CFG["sd_water_tomorrow"] and c == "WATER" and _is_plant(t) and not t.get("watered_today")
                and day < last_day):
            v = max(v, float(CFG["sd_water_tomorrow"]))   # tomorrow's labour saved (a dry plant is a must-do tomorrow)
        if CFG.get("sd_feed_bonus") and c in ("FEED", "CARE") and _animal(t):
            v += float(CFG["sd_feed_bonus"])        # user: a bonus on animals fed / cared
        if CFG["sd_collect_market"] and c == "COLLECT_FERTILIZER" and _animal(t):
            v = max(1.0, float((S.get("prices") or {}).get("FERTILIZER", 0) or 0))   # sd_collect_market
        elif CFG["sd_collect_floor"] and c == "COLLECT_FERTILIZER" and _animal(t):
            v = max(v, float(CFG["sd_collect_floor"]))   # sd_collect_floor
        if hard and c == "WATER" and CFG["sd_retire"] and idx in ((S.get("sd") or {}).get("retired_now") or ()):
            hard = False                               # sd_retire: the plan retires this plant (no forced water)
        rt_ = CFG["sd_retire"] and idx in ((S.get("sd") or {}).get("retired_now") or ())
        if day < last_day and not rt_ and ((c == "WATER" and _is_plant(t) and not t.get("watered_today")
                                and t.get("consecutive_unwatered", 0) >= 1)
                               or (c == "FEED" and _animal(t) and not t.get("fed_today")
                                   and t.get("consecutive_unfed", 0) >= 1)):
            hard = True
        if hard and hi < 0:
            hi = i
            v += float(CFG["sd_hard"])
            dl = last
        vals.append(max(v, vmin))
        dls.append(dl)
    return tuple(vals), tuple(dls), hi, True


def _sd_qi(idx):
    """quadrant index of a tile index: 0 NW (second), 1 NE (first), 2 SW (third), 3 SE (fourth)."""
    return (0 if idx // 10 < 5 else 2) + (0 if idx % 10 < 5 else 1)


def _sd_angle(idx):
    import math
    return math.atan2(idx // 10 - 4.5, idx % 10 - 4.5)


def _sd_corridors(P, L, hour, n):
    """radial corridors for the day: at the first plan with hands, the job tiles sorted by angle around the shed are cut
    into as many contiguous angular ranges as units, with equal work (ops); range r goes to the unit whose position
    angle matches (cyclic assignment with the least total angle gap). P.tcorr[tile] = range, P.ucorr[unit] = range."""
    import math
    cr = L.get("corr")
    day = L.get("day")
    if (cr is None or cr.get("day") != day) and n > 1:
        units = [u for u in range(n) if P.ue[u] >= 0]
        W = {}
        for j in range(P.J):
            if P.real[j]:
                W[P.jb[j][0]] = W.get(P.jb[j][0], 0) + P.jb[j][1]
        H = max(1, len(units))
        tiles = sorted(W, key=lambda i: (_sd_angle(i), i))
        tot = float(sum(W.values())) or 1.0
        cuts, acc, k = [], 0.0, 1
        for i in tiles:
            acc += W[i]
            while k < H and acc >= k * tot / H:
                cuts.append(_sd_angle(i) + 1e-6)
                k += 1
        while len(cuts) < H - 1:
            cuts.append(math.pi)
        edges = [-math.pi - 1e-9] + cuts + [math.pi + 1e-9]
        mids = [(edges[r] + edges[r + 1]) / 2.0 for r in range(H)]
        ua = sorted(units, key=lambda u: (_sd_angle(P.up[u]), u))
        best = None
        for sh in range(H):
            gap = 0.0
            for r in range(H):
                d = abs(_sd_angle(P.up[ua[(r + sh) % H]]) - mids[r])
                gap += min(d, 2 * math.pi - d)
            if best is None or gap < best[0] - 1e-9:
                best = (gap, sh)
        u2r = {ua[(r + best[1]) % H]: r for r in range(H)}
        cr = {"day": day, "edges": edges, "u2r": u2r}
        L["corr"] = cr
        def rng_of(i):
            a = _sd_angle(i)
            for r in range(H):
                if edges[r] <= a < edges[r + 1]:
                    return r
            return H - 1
        tc = [rng_of(i) for i in range(100)]
        r2u = {r: u for u, r in u2r.items()}
        L.setdefault("corridor_log", {})[str(day)] = {str(r2u[r]): [i for i in range(100) if tc[i] == r
                                                                    and (i % 10, i // 10) not in SHED]
                                                      for r in range(H) if r in r2u}
        L["st"]["corridor_days"] = L["st"].get("corridor_days", 0) + 1
    if cr is None or cr.get("day") != day:
        P.tcorr, P.ucorr = None, [-1] * P.U
        return
    edges, u2r = cr["edges"], cr["u2r"]
    H = len(edges) - 1

    def rng_of(i):
        a = _sd_angle(i)
        for r in range(H):
            if edges[r] <= a < edges[r + 1]:
                return r
        return H - 1
    P.tcorr = [rng_of(i) for i in range(100)]
    P.ucorr = [u2r.get(u, -1) for u in range(P.U)]


def _sd_sector(P, L, hour, n):
    """home quadrants of the units (P.uhome) and the rebalancing at the sectors' hours."""
    home = L.setdefault("home", {})
    uh = []
    L.setdefault("sector_log", {}).setdefault(str(L.get("day")), {})["0"] = "NW"
    for u in range(P.U):
        if u == 0:
            uh.append(0)                           # the farmer: the second quadrant (NW)
        elif u < n:
            if u not in home:
                home[u] = _sd_qi(P.up[u])
                L.setdefault("sector_log", {}).setdefault(str(L.get("day")), {})[str(u)] = ("NW", "NE", "SW", "SE")[home[u]]
            uh.append(home[u])
        else:
            uh.append(_sd_qi(P.up[u]))             # virtual hires: their spawn tile
    hrs = CFG["sd_sector_hours"] or ()
    if hour in hrs and L.get("sector_h") != (L.get("day"), hour):
        L["sector_h"] = (L.get("day"), hour)
        W = [0.0] * 4
        for j in range(P.J):
            if P.real[j] and not P.jb[j][23]:
                W[P.jb[j][22]] += P.jb[j][1]
        ctl = [u for u in range(1, min(n, P.U)) if P.uctrl[u] and P.ue[u] >= 0]
        ratio = float(CFG["sd_sector_ratio"])
        for _ in range(4):
            H = [0] * 4
            for u in ctl:
                H[uh[u]] += 1
            ld = [W[q] / max(H[q], 0.5) for q in range(4)]
            qh = max(range(4), key=lambda q: (ld[q], -q))
            don = [q for q in range(4) if H[q] >= 1 and q != qh]
            if not don or W[qh] <= 0:
                break
            ql = min(don, key=lambda q: (ld[q], q))
            if ld[qh] <= ratio * ld[ql] + 1.0:
                break
            cx, cy = (2, 2) if qh in (0, 1) else (7, 7), 0
            tx, ty = (2 if qh in (0, 2) else 7), (2 if qh in (0, 1) else 7)
            u = min((u for u in ctl if uh[u] == ql),
                    key=lambda u: (abs(P.up[u] % 10 - tx) + abs(P.up[u] // 10 - ty), u))
            uh[u] = qh
            home[u] = qh
            L.setdefault("sector_changes", []).append([int(L.get("day", 0)) * 24 + int(hour), int(u), ("NW", "NE", "SW", "SE")[qh]])
            L["st"]["sector_moves"] = L["st"].get("sector_moves", 0) + 1
    P.uhome = uh


def _sd_bundle(S, L, P, idx, t, ops, job, carried, prices, day, E, last_day, hour, last, add, gains):
    """sd_bundle_build: the tile's clearing ops (WATER if due, HARVEST / DIG) + BUILD + PLACE + FEED + CARE as one job
    (the harvest_before_build task holds only the clearing ops: the structure part is appended). Value: the clearing
    ops' own values + a day of the animal (2 x its product price / interval + the fertilizer price) on the last op; only
    the clearing ops may stand alone at the day end. Without the animal (bought at hour 0 at the earliest) the structure
    waits whole: hour 0 plans nothing on the tile, later hours only the clearing ops. Returns True when handled."""
    sp = job[2]
    cmds = [o[0] for o in ops]
    if not any(c in ("BUILD_COOP", "BUILD_PASTURE") for c in cmds):
        if not all(c in ("WATER", "HARVEST", "DIG") for c in cmds):
            return False
        ops = [list(o) for o in ops] + [["BUILD_" + job[1]], ["PLACE", sp], ["FEED"], ["CARE"]]
        cmds = [o[0] for o in ops]
    ib = next(i for i, c in enumerate(cmds) if c in ("BUILD_COOP", "BUILD_PASTURE"))
    clear = ops[:ib]
    avail = P.ava[_SD_SPI[sp]] + carried.get(sp, 0) > 0
    if not avail:
        L["st"]["bundle_wait"] = L["st"].get("bundle_wait", 0) + 1
        if hour == 0 or not clear:
            return True
        ops, cmds = clear, cmds[:ib]
    if not any(o[0] == "PLACE" for o in ops) and any(c in ("BUILD_COOP", "BUILD_PASTURE") for c in cmds):
        return True                                # never an empty structure
    cv, cd, chi, _ = _sd_opvals(S, idx, t, clear, False, day, E, last_day) if clear else ((), (), -1, True)
    cv, soft = _sd_hv_pref(t, [o[0] for o in clear], cv, day) if clear else (cv, None)
    n = len(ops)
    if len(ops) > len(clear):
        a = ANIMALS[sp]
        dv = (2.0 * float(prices.get(a["product"], 0) or 0) / max(1, a["interval"])
              + float(prices.get("FERTILIZER", 0) or 0)) if CFG["sd_bundle_value"] == "auto" else float(CFG["sd_bundle_value"])
        vals = tuple(cv) + tuple([0.0] * (n - len(clear) - 1) + [dv])
        dls = tuple(cd) + tuple([last] * (n - len(clear)))
    else:
        vals, dls = tuple(cv), tuple(cd)
    gw, gf, gdu, gdv, gty, gcv = gains(t, [o[0] for o in clear]) if clear else (0, 0, 0, 0.0, 0, 0.0)
    add(idx, idx, ops, vals, dls, chi, len(clear), hour, -1, 0, True, None, gw, gf, gdu, gdv, gty, gcv, soft)
    L["st"]["bundle_jobs"] = L["st"].get("bundle_jobs", 0) + (1 if len(ops) > len(clear) else 0)
    return True


def _sd_retired(S, tiles, day):
    """sd_retire: plants the plan retires: abandoned by the maintenance module (its abandonment log), or whose tile the
    plan clears (a planting or a structure on it, today or within 3 days) before the plant could produce again (an
    ongoing crop: before its next production day; a one-time crop: while it holds no yield yet)."""
    out = set()
    ab = set()
    for e in S.get("abandon") or ():
        try:
            ab.add((int(e["tile"][1]) * 10 + int(e["tile"][0]), e.get("kind"), int(e.get("start_day"))))
        except Exception:
            pass
    T = _T
    for idx in range(100):
        t = _tile(tiles, idx)
        if not _is_plant(t):
            continue
        crop, pd = t.get("crop"), int(t.get("planted_day", day))
        if (idx, crop, pd) in ab:
            out.add(idx)
            continue
        if T is None:
            continue
        clear = None
        for d in range(day, min(T.n, day + 4)):
            if idx in T.plant[d] or (d < len(T.struct_by_day) and idx in T.struct_by_day[d]):
                clear = d
                break
        if clear is None:
            continue
        c = CROPS[crop]
        age = day - pd
        if c["ongoing"]:
            nxt = None
            for a in range(max(age, c["first"]), _ongoing_last_age(crop) + 1):
                if (a - c["first"]) % c["interval"] == 0:
                    nxt = pd + a
                    break
            if nxt is None or nxt > clear:
                out.add(idx)
        elif int(t.get("yield_units", 0) or 0) <= 0 and pd + c["first"] > clear:
            out.add(idx)
    return out


def _sd_build(S, L, ctx):
    D, SD, SA, DS, NS = _sd_tables()
    day, hour, tiles, tasks = ctx["day"], ctx["hour"], ctx["tiles"], ctx["tasks"]
    if CFG["sd_retire"]:
        L["retired_now"] = _sd_retired(S, tiles, day)
        L.setdefault("retired_log", {}).setdefault(str(day), set()).update(L["retired_now"])
    invs, pos, shed, seeds, assign = ctx["invs"], ctx["pos"], ctx["shed"], ctx["seeds"], ctx["assign"]
    n, last_day, prices = len(pos), ctx["last_day"], ctx["prices"]
    fert_keep = bool(ctx["fert_keep"])
    P = _SdP()
    P.d, P.sd, P.sa, P.ds, P.ns = D, SD, SA, DS, NS
    P.day, P.hour = day, hour
    P.lastday = day >= last_day
    E = 24 if day < last_day else 23
    P.E = E
    P.lam = float(CFG["sd_lambda"])
    P.late_frac = float(CFG["sd_late_frac"])
    P.switch_w = float(CFG["sd_switch"])
    P.cap_w = float(CFG["sd_cap_w"])
    P.cap_lim = float(CFG["sd_cap"] - CFG["sd_cap_margin"])
    P.nev = 0
    P.deliv = bool(CFG["sd_deliv"])
    P.dunits = float(CFG["deliver_units"])
    P.dval = float(CFG["deliver_value"])
    P.dval_late = float(CFG["deliver_value_late"])
    P.late_h = CFG["late_hour"] if CFG["prio3"] else 99
    P.short = bool(S.get("short"))
    P.fert_keep = fert_keep
    _SD_MR.clear()
    if CFG["sd_mr"]:
        _SD_MR.update(_sd_mr_table(S, ctx["obs"], day, L["st"] if hour == 1 else None))
    dvt = {} if P.lastday else _sd_dv_table(S, day, prices, shed)   # day 29: the endgame rule delivers everything
    P.dvc = bool(dvt)                                  # v2: in-day delivery credit on
    P.dvt = dvt
    P.dv_h1 = int(CFG["sd_dv_hour"]) + 1                 # a delivery ending by this hour sells the same day
    P.ftrip = bool(CFG["sd_final_trip"])
    P.hlw = float(CFG["sd_hard_late_w"])
    P.hsafe = int(CFG["sd_hard_safe"])
    carried = Counter()
    for inv in invs:
        carried.update(inv)
    P.base_load = float(sum(int(shed.get(k, 0) or 0) for k in ("WHEAT", "FERTILIZER") + _SD_SP)
                        + sum(v for v in carried.values() if v > 0))
    if CFG["sd_cap_all"]:                          # v3: products that stay in the shed overnight count too
        ss = CFG.get("sell_source")
        for k in PRODUCTS:
            v = int(shed.get(k, 0) or 0)
            if k in ("WHEAT", "FERTILIZER") or v <= 0:
                continue
            if ss == "leader" and _T is not None:  # the rest of the leader's quota of the day sells today
                v -= min(v, max(0, _T.cum_sold[min(day, _T.n - 1)].get(k, 0) - S["sold"][k]))
            elif ss == "sem" and k != "STRAWBERRY":
                v = 0                              # the sem rule sells everything but strawberries at once
            P.base_load += v
    # shed stock shared by the routes (wheat: + the executor's feed buy of this step, in the shed next step)
    dw = max(0, int(ctx["demand"].get("WHEAT", 0)) - int(carried.get("WHEAT", 0)) - int(shed.get("WHEAT", 0)))
    P.avw = int(shed.get("WHEAT", 0)) + dw
    P.avf = 0 if CFG["sd_fert_sell"] == 1 else int(shed.get("FERTILIZER", 0))   # sd_fert_sell 1: no fertilizer pickups
    P.ava = [int(shed.get(s, 0)) for s in _SD_SP]
    pf_price = float(prices.get("FERTILIZER", 0) or 0)
    last = E - 1
    pv = float(CFG["plan_value"])
    # ---------------------------------------------------------------- jobs
    keys, JB, OPS, REAL, CROPI, NET, HARD, VRAW = [], [], [], [], [], [], [], []
    kidx = {}

    def add(key, tile, ops, vals, dls, hi, cutp, rel, pred, lag, real, crop_i, gw, gf, gdu, gdv, gty, gcv=0.0,
            soft=None):
        cmds = [o[0] for o in ops]
        nw = cmds.count("FEED")
        nf = cmds.count("FERTILIZE")
        na = -1
        for o in ops:
            if o[0] == "PLACE" and len(o) > 1 and o[1] in _SD_SPI:
                na = _SD_SPI[o[1]]
        fi = tuple(i for i, c in enumerate(cmds) if c == "FERTILIZE")
        wi = tuple(i for i, c in enumerate(cmds) if c == "FEED" or (c == "CARE" and nw))   # no wheat: no FEED, no CARE
        j = len(keys)
        keys.append(key)
        kidx[key] = j
        JB.append((tile, len(ops), nw, nf, na, gw, gf, vals, dls, int(rel), int(hi), pred, int(lag), False,
                   int(cutp), gdu, gdv, gty, fi, wi, gcv, soft, _sd_qi(tile),
                   hi >= 0 or any(c_ in ("PLANT", "BUILD_COOP", "BUILD_PASTURE", "PLACE") for c_ in cmds)))
        OPS.append(ops)
        REAL.append(real)
        CROPI.append(crop_i)
        NET.append(gw + gf - nw - nf - (1 if na >= 0 else 0))
        HARD.append(hi >= 0)
        VRAW.append(sum(vals) - (float(CFG["sd_hard"]) if hi >= 0 else 0.0))
        return j

    def gains(t, cmds):
        prod, units = _sd_harvest(t, cmds, day) if "HARVEST" in cmds else (None, 0)
        gw = units if prod == "WHEAT" else 0
        gf = cmds.count("COLLECT_FERTILIZER")
        gdu, gdv, gty, gcv = 0, 0.0, 0, 0.0
        if prod is not None and prod != "WHEAT" and units > 0:
            gdu, gdv, gty = units, units * float(prices.get(prod, 0) or 0), 1
            gcv = units * dvt.get(prod, 0.0)
        if gf and not fert_keep:
            gdu += gf
            gdv += gf * pf_price
            gty += 1
            gcv += gf * dvt.get("FERTILIZER", 0.0)
        return gw, gf, gdu, gdv, gty, gcv

    stiles = ctx.get("stiles") or ()
    for idx in sorted(tasks):
        if idx in stiles:
            continue                               # v5: the greedy's survival route serves this tile
        ops, need, prio = tasks[idx]
        t = _tile(tiles, idx)
        if CFG["sd_coop_pair"]:
            jb_ = ctx["jobs"].get(idx)
            if jb_ is not None and jb_[0] == "BUILD" and len(jb_) > 2 and jb_[2] in _SD_SPI:
                oc_ = [o[0] for o in ops]
                sp_ = jb_[2]
                emp_ = (isinstance(t, dict) and t.get("kind") == ANIMALS[sp_]["structure"] and "animal" not in t
                        and oc_[:1] == ["PLACE"])      # the structure stands empty: the rest of the pair
                if emp_ or any(c_ in ("BUILD_COOP", "BUILD_PASTURE") for c_ in oc_):
                    if P.ava[_SD_SPI[sp_]] + carried.get(sp_, 0) > 0 and any(o[0] == "PLACE" for o in ops):
                        pops = [list(o) for o in ops if o[0] not in ("FEED", "CARE")]
                        ip_ = max(i_ for i_, o in enumerate(pops) if o[0] == "PLACE")
                        pops = pops[:ip_ + 1]
                        hd_ = CFG["sd_coop_pair"] >= 2        # must complete by the day end (any hour): a hard op
                        by_ = int(CFG["sd_coop_by"])       # hard deadline hour of the PLACE (day end once passed)
                        dl_ = last if hour >= by_ else min(last, by_)
                        add(idx, idx, pops, tuple([0.0] * ip_ + [pv + (float(CFG["sd_hard"]) if hd_ else 0.0)]),
                            tuple([dl_] * len(pops)), ip_ if hd_ else -1, 0, hour, -1, 0, True, None, 0, 0, 0, 0.0, 0,
                            0.0)
                        L["st"]["coop_pair"] = L["st"].get("coop_pair", 0) + 1
                    else:
                        L["st"]["coop_wait"] = L["st"].get("coop_wait", 0) + 1
                    continue                       # never an empty structure: without the animal the pair waits
        if CFG["sd_bundle_build"]:
            jb_ = ctx["jobs"].get(idx)
            if jb_ is not None and jb_[0] == "BUILD" and len(jb_) > 2 and jb_[2] in _SD_SPI:
                if _sd_bundle(S, L, P, idx, t, ops, jb_, carried, prices, day, E, last_day, hour, last, add, gains):
                    continue
        kept = []
        placing_blocked = False
        for o in ops:                              # an animal nobody can supply today: PLACE and its FEED / CARE go
            c = o[0]
            if c == "PLACE" and len(o) > 1 and o[1] in _SD_SPI:
                sp = o[1]
                if P.ava[_SD_SPI[sp]] + carried.get(sp, 0) <= 0:
                    placing_blocked = True
                    continue
            if placing_blocked and c in ("FEED", "CARE"):
                continue
            kept.append(o)
        if not kept:
            continue
        cmds = [o[0] for o in kept]
        job_ = ctx["jobs"].get(idx)
        # plan part = from the first structural op (DIG / PLANT / BUILD / PLACE) on; the maintenance ops before it (the
        # current plant's WATER / HARVEST of a replant) are a job of their own, and the plan part follows it (order pair)
        k0 = next((i for i, c in enumerate(cmds) if c in ("DIG",) + _SD_PLANC), None)
        if k0 is not None and not any(c in _SD_PLANC for c in cmds):
            k0 = None                              # a lone DIG (weed / removal) is maintenance
        if job_ is not None and job_[0] == "BUILD" and cmds == ["HARVEST"]:
            k0 = 0                                 # harvest_before_build: clears the tile for the structure
        pre, planp = (kept, []) if k0 is None else (kept[:k0], kept[k0:])
        rel_ = hour
        if idx in (ctx.get("mflag") or {}):
            pre = []                               # the melon hand does this tile's water / harvest
            rel_ = max(hour, int(ctx["mflag"][idx]))   # harvested-by flag: the replant waits for the harvest
        j1 = None
        if pre:
            pc = [o[0] for o in pre]
            vals, dls, hi, trunc = _sd_opvals(S, idx, t, pre, False, day, E, last_day)
            vals, soft = _sd_hv_pref(t, pc, vals, day)
            gw, gf, gdu, gdv, gty, gcv = gains(t, pc)
            j1 = add(idx, idx, pre, vals, dls, hi, len(pre), hour, -1, 0, True, None, gw, gf, gdu, gdv, gty, gcv,
                     soft)
        if planp:
            pc = [o[0] for o in planp]
            crop_i = next((o[1] for o in planp if o[0] == "PLANT"), None)
            nn = len(planp)
            vals, dls = tuple([0.0] * (nn - 1) + [pv]), tuple([last] * nn)
            gw, gf, gdu, gdv, gty, gcv = gains(t, pc) if (pc == ["HARVEST"]) else (0, 0, 0, 0.0, 0, 0.0)
            key = idx if j1 is None else ("B", idx)
            ip = next((i_ for i_ in range(1, nn) if pc[i_] == "PLACE" and pc[i_ - 1] in ("BUILD_COOP", "BUILD_PASTURE")),
                      None) if CFG["sd_split_place"] else None
            if ip is None:
                add(key, idx, planp, vals, dls, -1, 0, rel_, -1 if j1 is None else j1, 0, True, crop_i, gw, gf, gdu, gdv,
                    gty, gcv)
            else:                                  # the structure first (short, no pickup), the placement as its successor
                ja = add(key, idx, planp[:ip], tuple([0.0] * (ip - 1) + [float(CFG["sd_build_value"])]),
                         tuple([last] * ip), -1, 0, hour, -1 if j1 is None else j1, 0, True, None, 0, 0, 0, 0.0, 0, 0.0)
                add(("G", idx), idx, planp[ip:], tuple([0.0] * (nn - ip - 1) + [pv]), tuple([last] * (nn - ip)), -1, 0,
                    hour, ja, 0, True, None, 0, 0, 0, 0.0, 0, 0.0)
                jb = JB[ja]
                JB[ja] = jb[:13] + (True,) + jb[14:]
                L["st"]["split_place"] = L["st"].get("split_place", 0) + 1
            if j1 is not None:
                jb = JB[j1]
                JB[j1] = jb[:13] + (True,) + jb[14:]      # the prefix is a predecessor: its finish is tracked
    # sd_coop_pair: a tile still holding its crop (harvest_before_build) gets the pair predicted after its harvest job
    if CFG["sd_coop_pair"]:
        for idx, jb_ in sorted(ctx["jobs"].items()):
            if not (jb_ and jb_[0] == "BUILD" and len(jb_) > 2 and jb_[2] in _SD_SPI) or idx not in kidx:
                continue
            j1 = kidx[idx]
            if any(o[0] in ("BUILD_COOP", "BUILD_PASTURE") for o in OPS[j1]):
                continue
            sp_ = jb_[2]
            if P.ava[_SD_SPI[sp_]] + carried.get(sp_, 0) <= 0:
                continue
            hd_ = CFG["sd_coop_pair"] >= 2
            by_ = int(CFG["sd_coop_by"])
            dl_ = last if hour >= by_ else min(last, by_)
            add(("K", idx), idx, [["BUILD_" + jb_[1]], ["PLACE", sp_]],
                (0.0, pv + (float(CFG["sd_hard"]) if hd_ else 0.0)), (dl_, dl_), 1 if hd_ else -1, 0, hour, j1, 0, True,
                None, 0, 0, 0, 0.0, 0, 0.0)
            jb = JB[j1]
            JB[j1] = jb[:13] + (True,) + jb[14:]
            if hd_:
                HARD[j1] = True                    # the clearing harvest carries the pair: inserted / kept first
    # v3: melons offered at full yield (see the header)
    ment = (CFG["sd_hv_pref"] or {}).get("MELON") or {}
    if ment.get("offer") and not P.lastday:
        cm = CROPS["MELON"]
        pm = float(prices.get("MELON", 0) or 0)
        for idx in range(100):
            t = _tile(tiles, idx)
            if not (_is_plant(t) and t.get("crop") == "MELON") or ("B", idx) in kidx:
                continue
            age = day - int(t.get("planted_day", day))
            if age < cm["first"]:
                continue
            j1 = kidx.get(idx)
            c1 = [o[0] for o in OPS[j1]] if j1 is not None else []
            if "HARVEST" in c1 or "DIG" in c1:
                continue                           # the task harvests / removes it already
            wat = "WATER" in c1
            units = _sd_harvest(t, ["WATER", "HARVEST"], day)[1] if wat else int(t.get("yield_units", 0) or 0)
            if units < cm["max"]:
                continue
            soft = ((0, int(ment["by_hour"]), float(ment.get("hour_w", 0.0)))
                    if ment.get("by_hour") is not None and float(ment.get("hour_w", 0.0)) > 0 else None)
            add(("H", idx), idx, [["HARVEST"]], (max(float(ment.get("bonus", 0.0)), float(CFG["sd_vmin"])),),
                (last,), -1, 1, hour, j1 if wat else -1, 0, True, None, 0, 0, units, units * pm, 1,
                units * dvt.get("MELON", 0.0), soft)
            if wat:
                jb = JB[j1]
                JB[j1] = jb[:13] + (True,) + jb[14:]          # the WATER task is a predecessor: its finish is tracked
    # sd_water_tomorrow: plants the executor leaves dry today (no task: no production effect) get a planner-only water
    # job worth tomorrow's labour saved; idle capacity then waters the patch instead of passing
    if CFG["sd_water_tomorrow"] and not P.lastday:
        wv = float(CFG["sd_water_tomorrow"])
        for idx in range(100):
            if idx in kidx or ("B", idx) in kidx or ("H", idx) in kidx or idx in stiles:
                continue
            t = _tile(tiles, idx)
            if _is_plant(t) and not t.get("watered_today"):
                add(("W", idx), idx, [["WATER"]], (wv,), (last,), -1, 1, hour, -1, 0, True, None, 0, 0, 0, 0.0, 0, 0.0)
    # predicted jobs (1): plan plantings whose seeds are bought this step (tile free or weed, no task yet)
    pseen = L["pred_seen"]
    if CFG["sd_plan_jobs"]:
        for idx, job in sorted(ctx["jobs"].items()):
            if not job or job[0] != "PLANT" or idx in tasks or idx in kidx:
                continue
            crop = job[1]
            if seeds.get(crop, 0) > 0:
                continue
            t = _tile(tiles, idx)
            if not (t is None or _is_weed(t)):
                continue
            k = ("P", idx)
            first = pseen.setdefault(k, hour)
            if hour - first > 2:
                continue                           # the seeds never came: stop waiting for them
            ops = ([["DIG"]] if t is not None else []) + [["PLANT", crop], ["WATER"]]
            nn = len(ops)
            add(k, idx, ops, tuple([0.0] * (nn - 1) + [pv]), tuple([last] * nn), -1, 0, hour + 1, -1, 0, False,
                None, 0, 0, 0, 0.0, 0)
    # predicted jobs (2): the deploy's same-day replant after a wheat / carrot harvest (order pair: harvest -> plant +
    # water). The replant task appears the step after the harvest (the tile reads empty) when seeds are in stock, one
    # step later when they are bought then.
    if CFG["sd_pairs"] and "DEP_CFG" in globals() and "_DEP" in globals():
        try:
            dc = DEP_CFG
            ds_c = _DEP.get("ds_crops", {}) if _DEP.get("ds_day") == day else {}
            if dc.get("replant_same_day") and day >= dc.get("replant_from", 99) and ds_c:
                capped = False
                if dc.get("replant_cap") and _DEP.get("wh_pred", (None,))[0] == day:
                    n_wh = sum(1 for j in range(100) if _is_plant(_tile(tiles, j)) and _tile(tiles, j)["crop"] == "WHEAT")
                    n_wh += sum(1 for j, c in _T.plant[day].items() if c == "WHEAT" and _tile(tiles, j) is None)
                    capped = n_wh >= dc["replant_cap"] * _DEP["wh_pred"][1]
                in_stock = Counter(seeds)
                for j2, c2 in enumerate(CROPI):
                    if c2 is not None and REAL[j2]:
                        in_stock[c2] -= 1
                for idx in sorted(tasks):
                    j1 = kidx.get(idx)
                    if j1 is None or idx not in ds_c or ("B", idx) in kidx or ("K", idx) in kidx:
                        continue
                    crop = ds_c[idx]
                    t = _tile(tiles, idx)
                    cm = [o[0] for o in OPS[j1]]
                    if not (_is_plant(t) and t.get("crop") == crop and "HARVEST" in cm and "PLANT" not in cm):
                        continue
                    if idx in _T.plant[day] or day > dc["last_plant"].get(crop, -1) or (crop == "WHEAT" and capped):
                        continue
                    lag = 0 if in_stock.get(crop, 0) > 0 else 1
                    if in_stock.get(crop, 0) > 0:
                        in_stock[crop] -= 1
                    add(("R", idx), idx, [["PLANT", crop], ["WATER"]], (0.0, float(CFG["sd_replant_value"])),
                        (last, last), -1, 0, hour, j1, lag, False, None, 0, 0, 0, 0.0, 0)
                    jb = JB[j1]
                    JB[j1] = jb[:13] + (True,) + jb[14:]      # j1 is a predecessor: its finish is tracked
        except Exception:
            S["log"]["sd_pair_error"] += 1
    P.key, P.jb, P.ops, P.real, P.cropi, P.net, P.hard, P.vraw, P.kidx = (
        keys, JB, OPS, REAL, CROPI, NET, HARD, VRAW, kidx)
    P.anim = [any(o[0] in ("FEED", "CARE", "COLLECT_FERTILIZER") for o in ops_) for ops_ in OPS]   # radial: animal jobs
    J = len(keys)
    P.J = J
    P.succ = [-1] * J
    for j in range(J):
        if JB[j][11] >= 0:
            P.succ[JB[j][11]] = j
    P.seeds = {c: int(v) for c, v in seeds.items()}
    # ---------------------------------------------------------------- units
    cols = {k: [] for k in ("t0", "p", "w", "f", "a", "an", "du", "dv", "ty", "e", "ctrl", "virt", "swk", "swn",
                            "cv")}
    walk = L["walk"]

    def unit(t0, pi, inv, ctrl, virt, w):
        du = dv = cv = 0.0
        ty = 0
        for k_, v_ in inv.items():
            if v_ > 0 and k_ in PRODUCTS and k_ != "WHEAT" and not (k_ == "FERTILIZER" and fert_keep):
                du += v_
                dv += v_ * float(prices.get(k_, 0) or 0)
                cv += v_ * dvt.get(k_, 0.0)
                ty += 1
        cols["cv"].append(cv)
        cols["t0"].append(t0)
        cols["p"].append(pi)
        cols["w"].append(int(inv.get("WHEAT", 0)))
        cols["f"].append(int(inv.get("FERTILIZER", 0)))
        cols["a"].append(tuple(int(inv.get(s, 0)) for s in _SD_SP))
        cols["an"].append(sum(int(inv.get(s, 0)) for s in _SD_SP))
        cols["du"].append(du)
        cols["dv"].append(dv)
        cols["ty"].append(ty)
        cols["e"].append(E)
        cols["ctrl"].append(ctrl)
        cols["virt"].append(virt)
        cols["swk"].append(w[0] if w else None)
        cols["swn"].append(int(w[1]) if (w and w[0] is not None) else 0)

    for u in range(n):
        p = tuple(pos[u])
        pi = p[1] * 10 + p[0]
        inv = invs[u]
        t0 = hour
        ctrl = True
        if assign.get(u) == "D":                   # delivering: free once the executor's delivery is done
            dv = ctx["deliv_u"](u)
            s = _near_shed(p)
            si = s[1] * 10 + s[0]
            k = 1 if (dv and all(k_ in dv for k_ in inv)) else max(1, len(dv))
            t0 = hour + D[pi][si] + k
            pi = si
            inv = Counter({k_: v_ for k_, v_ in inv.items() if k_ not in dv})
            ctrl = False
        unit(t0, pi, inv, ctrl, False, walk.get(u))
    for u in ctx.get("keep") or ():                # v5: units on the greedy's survival routes are not planned
        if u < n:
            cols["e"][u] = -1
            cols["ctrl"][u] = False
    P.n_real = n
    if hour == 0 and n == 1 and day < last_day:            # hour 0: the day's hires spawn at hour 1 (virtual units)
        vu = ctx.get("vunits")
        if vu is None:
            vu = [(q, 1) for q in _sd_spawn(pos, _sd_want_hands(day))]
        for q, t0v in vu:
            unit(t0v, q[1] * 10 + q[0], Counter(), False, True, None)
    (P.ut0, P.up, P.uw, P.uf, P.ua, P.uan, P.udu, P.udv, P.uty, P.ue, P.uctrl, P.uvirt, P.uswk, P.uswn) = (
        cols["t0"], cols["p"], cols["w"], cols["f"], cols["a"], cols["an"], cols["du"], cols["dv"], cols["ty"],
        cols["e"], cols["ctrl"], cols["virt"], cols["swk"], cols["swn"])
    P.ucv = cols["cv"]
    U = len(P.ut0)
    P.U = U
    P.corrw = float(CFG["sd_corr_w"])
    P.radin, P.radside = float(CFG["sd_rad_in"]), float(CFG["sd_rad_side"])
    if P.corrw:
        _sd_corridors(P, L, hour, n)
    else:
        P.tcorr, P.ucorr = None, [-1] * U
    P.secw = float(CFG["sd_sector_w"])
    P.hopw = float(CFG["sd_hop_w"])
    P.hopc = int(CFG["sd_hop_central"])
    if P.secw:
        _sd_sector(P, L, hour, n)
    else:
        P.uhome = [-1] * U
    # ---------------------------------------------------------------- empty plan
    P.routes = [[] for _ in range(U)]
    P.rsc = [0.0] * U
    P.rpw = [0] * U
    P.rpf = [0] * U
    P.rpa = [_SD_Z3] * U
    P.rkp = [(-1, 0)] * U
    P.rfin = [None] * U
    P.rend = [0] * U
    P.where = [-1] * J
    P.ft = {}
    P.tpw = P.tpf = 0
    P.tpa = [0, 0, 0]
    P.seed_used = Counter()
    P.load = P.base_load
    for u in range(U):
        ev = _sd_eval(P, u, [])
        P.rsc[u] = ev[1]
        P.rend[u] = ev[2]
    return P


def _sd_eval(P, u, r):
    """(ok, score, t_end, pick wheat, pick fertilizer, pick animals (3), pickup position, pickup steps, finish of the
    predecessor jobs in r) for unit u doing the jobs r in order: the best of taking the wheat / fertilizer the route
    needs from the shed or leaving it (the FEED + CARE / FERTILIZE ops without it are skipped, as the executor's
    usable_ops does; a hard op among them fails that variant)."""
    ev = _sd_eval1(P, u, r, True, True)
    if not r or (not ev[0] and ev[2] not in ("dayend", "cut", "hard_late", "lastday")):
        return ev
    need_w = need_f = False
    if ev[0]:
        need_w, need_f = ev[3] > 0, ev[4] > 0
    else:                                          # infeasible with pickups: which items does the route need?
        JB = P.jb
        need_w = any(JB[j][2] for j in r) and P.uw[u] < sum(JB[j][2] for j in r)
        need_f = any(JB[j][3] for j in r) and P.uf[u] < sum(JB[j][3] for j in r)
    best = ev
    for aw, af in ((True, False), (False, True), (False, False)):
        if (not aw and not need_w) or (not af and not need_f):
            continue
        e2 = _sd_eval1(P, u, r, aw, af)
        if e2[0] and (not best[0] or e2[1] > best[1] + 1e-9):
            best = e2
    return best


def _sd_eval1(P, u, r, aw_ok, af_ok):
    """one variant of _sd_eval: aw_ok / af_ok = wheat / fertilizer may be picked up at the shed (the shared stock
    permitting; a route short of stock takes what is left and skips what it cannot supply)."""
    P.nev += 1
    t = P.ut0[u]
    t0 = t
    sw = 0.0
    if P.uswn[u] and (not r or P.key[r[0]] != P.uswk[u]):
        sw = P.switch_w * P.uswn[u]
    if not r:
        if P.ftrip and P.deliv and P.ucv[u] > 0:       # v2: an idle unit walks what it carries to the shed
            p = P.up[u]
            s = P.ns[p]
            ty = P.uty[u]
            nd = P.uw[u] > 0 or P.uan[u] > 0 or (P.uf[u] > 0 and P.fert_keep)
            tf = t + P.d[p][s] + ((ty if ty < 4 else 4) if nd else 1)
            if tf <= P.dv_h1:
                return (True, P.ucv[u] - P.lam * (tf - t0) - sw, tf, 0, 0, _SD_Z3, -1, 0, None)
        return (True, -sw, t, 0, 0, _SD_Z3, -1, 0, None)
    JB = P.jb
    D = P.d
    L_ = len(r)
    # ---- items: lowest running balance (wheat / fertilizer gained earlier in the route count)
    bw = P.uw[u]
    bf = P.uf[u]
    lw, lf = bw, bf
    neg = L_
    a0 = a1 = a2 = 0
    ua = P.ua[u]
    for k in range(L_):
        jb = JB[r[k]]
        x = jb[2]
        if x:
            bw -= x
            if bw < lw:
                lw = bw
                if bw < 0 and k < neg:
                    neg = k
        x = jb[3]
        if x:
            bf -= x
            if bf < lf:
                lf = bf
                if bf < 0 and k < neg:
                    neg = k
        x = jb[4]
        if x >= 0:
            if x == 0:
                a0 += 1
                c = a0
            elif x == 1:
                a1 += 1
                c = a1
            else:
                a2 += 1
                c = a2
            if c > ua[x] and k < neg:
                neg = k
        bw += jb[5]
        bf += jb[6]
    pw = -lw if lw < 0 else 0
    pf = -lf if lf < 0 else 0
    pa = (a0 - ua[0] if a0 > ua[0] else 0, a1 - ua[1] if a1 > ua[1] else 0, a2 - ua[2] if a2 > ua[2] else 0)
    kp = -1
    p = P.up[u]
    wsk = fsk = False
    if pw:
        aw = P.avw - (P.tpw - P.rpw[u]) if aw_ok else 0
        if pw > aw:
            pw = aw if aw > 0 else 0
            wsk = True
    if pf:
        af = P.avf - (P.tpf - P.rpf[u]) if af_ok else 0
        if pf > af:
            pf = af if af > 0 else 0
            fsk = True
    if pa[0] + pa[1] + pa[2]:
        ra = P.rpa[u]
        for i in range(3):
            if pa[i] and pa[i] > P.ava[i] - (P.tpa[i] - ra[i]):
                return _SD_FAILS["stock_a"]
    npk = (pw > 0) + (pf > 0) + (pa[0] > 0) + (pa[1] > 0) + (pa[2] > 0)
    if npk:
        SD = P.sd
        prev = p
        best = 999
        for k in range(neg + 1 if neg < L_ else L_):
            b = JB[r[k]][0]
            det = SD[prev][b] - D[prev][b]
            if det < best:
                best = det
                kp = k
            prev = b
    # ---- time
    val = 0.0
    prev = p
    fin = None
    E = P.ue[u]
    lf_ = P.late_frac
    deliv = P.deliv
    picked = not npk
    cw, cf, can = P.uw[u], P.uf[u], P.uan[u]
    if deliv:
        du, dv, ty = P.udu[u], P.udv[u], P.uty[u]
        late_h, dun, dva, dvl, short, fk = P.late_h, P.dunits, P.dval, P.dval_late, P.short, P.fert_keep
        cv, dvh1 = P.ucv[u], P.dv_h1
    hlw = P.hlw
    secw, uhq = P.secw, P.uhome[u]
    corrw, ucr, tcr = P.corrw, P.ucorr[u], P.tcorr
    radin, radside = P.radin, P.radside
    hopw, pj, hopc = P.hopw, False, P.hopc
    for k in range(L_):
        j = r[k]
        jb = JB[j]
        b = jb[0]
        if k == kp and not picked:
            s = P.sa[prev][b]
            t += D[prev][s] + npk
            prev = s
            pj = False
            picked = True
            cw += pw
            cf += pf
            can += pa[0] + pa[1] + pa[2]
        if hopw and pj and D[prev][b] > 1 and P.ds[prev] > hopc and P.ds[b] > hopc:   # contiguity in the patch
            val -= hopw * (D[prev][b] - 1)
        if (radin or radside) and pj:              # radial: job to job, inward and sideways steps cost
            da_, db_ = P.ds[prev], P.ds[b]
            val -= radin * (da_ - db_ if da_ > db_ else 0) + radside * (D[prev][b] - (db_ - da_ if db_ > da_ else da_ - db_))
        t += D[prev][b]
        rel = jb[9]
        pr = jb[11]
        if pr >= 0:
            f = fin.get(pr) if fin is not None else None
            if f is None:
                if pr in r:                        # the predecessor comes later in this route
                    return _SD_FAILS["pred_later"]
                f = P.ft.get(pr)
                if f is None:                      # predecessor not planned
                    return _SD_FAILS["pred_none"]
            if f + jb[12] > rel:
                rel = f + jb[12]
        if t < rel:
            t = rel
        n = jb[1]
        vals = jb[7]
        dls = jb[8]
        hi = jb[10]
        skip = ()
        nw, nf = jb[2], jb[3]
        if (wsk and nw and cw < nw) or (fsk and nf and cf < nf):
            if wsk and nw and cw < nw:
                skip = jb[19]
                nw = 0
            if fsk and nf and cf < nf:
                skip = skip + jb[18]
                nf = 0
            if hi in skip:
                return _SD_FAILS["hard_stock"]
        m = n - len(skip)                          # ops executed
        if hi >= 0 and hlw:                        # v2: a hard op done late in the day (it fails if not on time)
            x = t + (hi - sum(1 for s_ in skip if s_ < hi) if skip else hi) - P.hsafe
            if x > 0:
                val -= hlw * x
        if secw and uhq >= 0 and jb[22] != uhq and not jb[23]:   # sectors: ops outside the unit's home quadrant
            val -= secw * (m if t + m <= E else (E - t if E > t else 0))
        if corrw and ucr >= 0 and tcr is not None and tcr[b] != ucr and not jb[23]:   # radial corridors
            val -= corrw * (m if t + m <= E else (E - t if E > t else 0))
        sft = jb[21]
        if sft is not None and sft[0] not in skip:  # v3: soft time target (melons early in the morning)
            x = t + (sft[0] - sum(1 for s_ in skip if s_ < sft[0]) if skip else sft[0])
            if sft[1] < x < E:
                val -= sft[2] * (x - sft[1])
        if t + m > E:
            # the day ends inside this job: only the route's last job, only its leading maintenance ops
            if k != L_ - 1:
                return _SD_FAILS["dayend"]
            mm = E - t
            if mm <= 0 or mm > jb[14]:
                return _SD_FAILS["cut"]
            done = 0
            for i in range(n):
                if i in skip:
                    continue
                if done >= mm:
                    if i == hi:
                        return _SD_FAILS["cut"]
                    continue
                if t + done <= dls[i]:
                    val += vals[i]
                else:
                    val += vals[i] * lf_
                done += 1
            t = E
            prev = b
            break
        if skip:
            done = 0
            for i in range(n):
                if i in skip:
                    continue
                if t + done <= dls[i]:
                    val += vals[i]
                elif i == hi:
                    return _SD_FAILS["hard_late"]
                else:
                    val += vals[i] * lf_
                done += 1
        else:
            for i in range(n):
                if t + i <= dls[i]:
                    val += vals[i]
                elif i == hi:
                    return _SD_FAILS["hard_late"]
                else:
                    val += vals[i] * lf_
        t += m
        if jb[13]:
            if fin is None:
                fin = {}
            fin[j] = t
        prev = b
        pj = True
        cw += jb[5] - nw
        cf += jb[6] - nf
        if jb[4] >= 0:
            can -= 1
        if deliv:
            g = jb[15]
            if g:
                du += g
                dv += jb[16]
                ty += jb[17]
                cv += jb[20]
                if t < 22 and (((du >= dun or dv >= dva) and t < late_h) or (short and dv > 0)
                               or (dv >= dvl and t < 20)):
                    s = P.ns[b]                    # the executor's delivery: nearest shed tile, DROP / PLACE a type
                    nd = cw > 0 or can > 0 or (cf > 0 and fk)
                    t += D[b][s] + ((ty if ty < 4 else 4) if nd else 1)
                    if cv and t <= dvh1:           # v2: sold the same day
                        val += cv
                    prev = s
                    pj = False
                    du = dv = 0.0
                    ty = 0
                    cv = 0.0
                    if not picked and kp > k:      # the pending pickup rides on this visit
                        t += npk
                        picked = True
                        cw += pw
                        cf += pf
                        can += pa[0] + pa[1] + pa[2]
    if deliv and cv > 0 and P.ftrip:               # v2: after the last job the unit walks its products to the shed
        s = P.ns[prev]
        nd = cw > 0 or can > 0 or (cf > 0 and fk)
        tf = t + D[prev][s] + ((ty if ty < 4 else 4) if nd else 1)
        if tf <= dvh1:
            val += cv
            t = tf
            prev = s
    if P.lastday and t + P.ds[prev] + 1 > E:
        return _SD_FAILS["lastday"]
    te = t if t < E else E
    pen = 0.0
    if CFG.get("sd_animal_cap") and r:
        # radial (user): the central animals' feed / care / collect ride on every hand's way out -- at most
        # sd_animal_cap animal jobs a route, and animal jobs after the first patch job cost sd_animal_late_w each
        na_ = late_ = 0
        seen_ = False
        for j_ in r:
            if P.anim[j_]:
                na_ += 1
                late_ += 1 if seen_ else 0
            else:
                seen_ = True
        pen = (float(CFG.get("sd_animal_cap_w", 200.0)) * max(0, na_ - int(CFG["sd_animal_cap"]))
               + float(CFG.get("sd_animal_late_w", 0.0)) * late_)
    return (True, val - P.lam * (te - t0) - sw - pen, t, pw, pf, pa, kp, npk, fin)


def _sd_obj(P):
    ov = P.load - P.cap_lim
    return sum(P.rsc) - (P.cap_w * ov if ov > 0 else 0.0)


def _sd_commit(P, u, r, ev):
    """install route r (evaluated as ev) for unit u; keeps the counters consistent."""
    old = P.routes[u]
    for j in old:
        P.where[j] = -1
        P.load -= P.net[j]
        c = P.cropi[j]
        if c is not None and P.real[j]:
            P.seed_used[c] -= 1
        if j in P.ft:
            del P.ft[j]
    for j in r:
        P.where[j] = u
        P.load += P.net[j]
        c = P.cropi[j]
        if c is not None and P.real[j]:
            P.seed_used[c] += 1
    P.routes[u] = list(r)
    P.rsc[u] = ev[1]
    P.rend[u] = ev[2]
    P.tpw += ev[3] - P.rpw[u]
    P.tpf += ev[4] - P.rpf[u]
    ra = P.rpa[u]
    P.tpa = [P.tpa[i] + ev[5][i] - ra[i] for i in range(3)]
    P.rpw[u], P.rpf[u], P.rpa[u] = ev[3], ev[4], ev[5]
    P.rkp[u] = (ev[6], ev[7])
    P.rfin[u] = ev[8]
    if ev[8]:
        P.ft.update(ev[8])


def _sd_fix_pairs(P, us):
    """after routes us changed: a successor whose predecessor moved / vanished is re-timed (dropped if it no longer
    fits). sd_coop_pair: chains (a re-timed route holding another route's predecessor) propagate until nothing moves."""
    work = list(us)
    chain = bool(CFG["sd_coop_pair"])
    guard = 4 * P.U + 8
    while work:
        u = work.pop(0)
        for j in P.routes[u]:
            s = P.succ[j]
            if s < 0:
                continue
            v = P.where[s]
            if v < 0 or v == u:
                continue
            old = (P.rsc[v], P.rend[v], tuple(P.ft.get(x) for x in P.routes[v])) if chain else None
            ev = _sd_eval(P, v, P.routes[v])
            if not ev[0]:
                r2 = [x for x in P.routes[v] if x != s]
                ev = _sd_eval(P, v, r2)
                if ev[0]:
                    _sd_commit(P, v, r2, ev)
            else:
                _sd_commit(P, v, P.routes[v], ev)
            if chain and guard > 0 and v not in work and old != (P.rsc[v], P.rend[v],
                                                                 tuple(P.ft.get(x) for x in P.routes[v])):
                work.append(v)
                guard -= 1
    for j in range(P.J):                          # successors of predecessors no longer planned
        pr = P.jb[j][11]
        if pr >= 0 and P.where[j] >= 0 and P.where[pr] < 0:
            v = P.where[j]
            r2 = [x for x in P.routes[v] if x != j]
            ev = _sd_eval(P, v, r2)
            if ev[0]:
                _sd_commit(P, v, r2, ev)


def _sd_seed_ok(P, j):
    c = P.cropi[j]
    return c is None or not P.real[j] or P.seed_used[c] < P.seeds.get(c, 0)


def _sd_load_delta(P, dnet):
    a = P.load - P.cap_lim
    b = P.load + dnet - P.cap_lim
    return -P.cap_w * ((b if b > 0 else 0.0) - (a if a > 0 else 0.0))


def _sd_cands(P, j):
    """candidate units for job j: the nearest routes / units (sd_k_units) + the two nearest idle units."""
    D = P.d
    if P.hard[j] and CFG["sd_hard_all"]:
        return [u for u in range(P.U) if P.ue[u] >= 0]    # v2: every unit may take a survival job
    b = P.jb[j][0]
    near, idle = [], []
    for u in range(P.U):
        if P.ue[u] < 0:
            continue
        r = P.routes[u]
        dm = D[b][P.up[u]]
        for x in r:
            dx = D[b][P.jb[x][0]]
            if dx < dm:
                dm = dx
        (near if r else idle).append((dm, u))
    near.sort()
    idle.sort()
    return [u for _, u in near[:CFG["sd_k_units"]]] + [u for _, u in idle[:2]]


def _sd_best_ins(P, j, units, skip_u=-1):
    """best and second-best (over units) insertion of job j: (d1, u1, k1, ev1, d2) or None."""
    if not _sd_seed_ok(P, j):
        return None
    ld = _sd_load_delta(P, P.net[j])
    best = {}
    for u in units:
        if u == skip_u:
            continue
        r = P.routes[u]
        base = P.rsc[u]
        bu = None
        for k in range(len(r) + 1):
            nr = r[:k] + [j] + r[k:]
            ev = _sd_eval(P, u, nr)
            if not ev[0]:
                continue
            d = ev[1] - base + ld
            if bu is None or d > bu[0]:
                bu = (d, u, k, ev)
        if bu is not None:
            best[u] = bu
    if not best:
        return None
    vals = sorted(best.values(), key=lambda x: -x[0])
    d2 = vals[1][0] if len(vals) > 1 else None
    d1, u1, k1, ev1 = vals[0]
    return (d1, u1, k1, ev1, d2)


def _sd_insert_many(P, pool, rng=None, noise=0.0, deadline=None):
    """regret-2 insertion of the jobs in pool (hard jobs first); jobs that fit nowhere with a positive gain stay
    unplanned. Returns the number inserted."""
    pool = [j for j in pool if P.where[j] < 0]
    if not pool:
        return 0
    cu = {j: _sd_cands(P, j) for j in pool}
    best = {j: _sd_best_ins(P, j, cu[j]) for j in pool}
    done = 0
    guard = 4 * len(pool) + 8
    while best and guard > 0:
        guard -= 1
        if deadline is not None and time.perf_counter() > deadline:
            break
        sel = None
        for j, b in best.items():
            if b is None or b[0] <= 1e-6:
                continue
            reg = 1e9 if b[4] is None else b[0] - b[4]
            if noise and rng is not None:
                reg += noise * rng.random()
            key = (P.hard[j], reg, b[0], -j)
            if sel is None or key > sel[0]:
                sel = (key, j)
        if sel is None:
            break
        j = sel[1]
        d1, u, k, ev, _ = best.pop(j)
        r = P.routes[u]
        nr = r[:k] + [j] + r[k:]
        ev = _sd_eval(P, u, nr)                   # reservations may have moved since it was scored
        if not ev[0] or not _sd_seed_ok(P, j):
            b = _sd_best_ins(P, j, cu[j])
            if b is not None:
                best[j] = b
            continue
        _sd_commit(P, u, nr, ev)
        if P.jb[j][13] or P.jb[j][11] >= 0 or (CFG["sd_coop_pair"] and P.rfin[u]):   # sd_coop_pair: a shifted predecessor too
            _sd_fix_pairs(P, [u])
        done += 1
        for j2 in list(best):
            if u in cu[j2] or best[j2] is None:
                best[j2] = _sd_best_ins(P, j2, cu[j2])
    return done


def _sd_repair(P, u, r):
    """drop jobs from r until the route is feasible (the removal that leaves the best score, non-hard first)."""
    r = list(r)
    ev = _sd_eval(P, u, r)
    while not ev[0] and r:
        best = None
        for i in range(len(r)):
            r2 = r[:i] + r[i + 1:]
            e2 = _sd_eval(P, u, r2)
            if not e2[0]:
                continue
            key = (not P.hard[r[i]], e2[1])
            if best is None or key > best[0]:
                best = (key, i, e2)
        if best is None:
            r = r[:-1]                             # nothing single fixes it: shorten from the end
            ev = _sd_eval(P, u, r)
        else:
            r = r[:best[1]] + r[best[1] + 1:]
            ev = best[2]
    return r, ev


def _sd_construct(P):
    """initial plan by an event simulation of the executor's greedy (each free unit takes the cheapest reachable job:
    travel with a shed detour when it lacks items, +10 for low-value jobs after late_hour)."""
    import heapq
    D, SD = P.d, P.sd
    JB = P.jb
    heap = [(P.ut0[u], u) for u in range(P.U) if P.ue[u] > 0]
    heapq.heapify(heap)
    upos = list(P.up)
    cw, cf = list(P.uw), list(P.uf)
    left = set(j for j in range(P.J) if JB[j][11] < 0)
    seq = [[] for _ in range(P.U)]
    seeds = Counter()
    late = CFG["late_hour"]
    p1 = float(CFG["p1_min_value"])
    while heap and left:
        t, u = heapq.heappop(heap)
        if t >= P.ue[u]:
            continue
        p = upos[u]
        best = None
        for j in left:
            jb = JB[j]
            b = jb[0]
            lack = jb[2] > cw[u] or jb[3] > cf[u] or jb[4] >= 0
            trav = (SD[p][b] + 1) if lack else D[p][b]
            st = max(t + trav, jb[9])
            if st + jb[1] > P.ue[u] or (jb[10] >= 0 and st + jb[10] > jb[8][jb[10]]):
                continue
            c = trav + (10 if (t >= late and P.vraw[j] <= p1) else 0) - min(4000.0, P.vraw[j]) * 1e-4
            if best is None or c < best[0]:
                best = (c, j, st)
        if best is None:
            continue
        _, j, st = best
        jb = JB[j]
        c = P.cropi[j]
        if c is not None and P.real[j]:
            if seeds[c] >= P.seeds.get(c, 0):
                left.discard(j)
                heapq.heappush(heap, (t, u))
                continue
            seeds[c] += 1
        left.discard(j)
        seq[u].append(j)
        if jb[2] > cw[u] or jb[3] > cf[u]:
            cw[u] = max(cw[u], jb[2])
            cf[u] = max(cf[u], jb[3])
        cw[u] = cw[u] - jb[2] + jb[5]
        cf[u] = cf[u] - jb[3] + jb[6]
        upos[u] = jb[0]
        s = P.succ[j]
        if s >= 0:
            left.add(s)
        heapq.heappush(heap, (st + jb[1], u))
    for u in range(P.U):
        if seq[u]:
            r, ev = _sd_repair(P, u, seq[u])
            _sd_commit(P, u, r, ev)
    _sd_fix_pairs(P, range(P.U))


def _sd_intra(P, u, deadline, ev_end):
    """2-opt and or-opt (segments of 1-3) on route u until no improvement."""
    improved = True
    any_imp = False
    while improved:
        improved = False
        r = P.routes[u]
        L_ = len(r)
        if L_ < 2:
            return any_imp
        base = P.rsc[u]
        best = None
        for i in range(L_ - 1):                    # 2-opt: reverse r[i..k]
            for k in range(i + 1, L_):
                nr = r[:i] + r[i:k + 1][::-1] + r[k + 1:]
                ev = _sd_eval(P, u, nr)
                if ev[0] and ev[1] > base + 1e-6 and (best is None or ev[1] > best[1][1]):
                    best = (nr, ev)
        for sl in (1, 2, 3):                       # or-opt: move a segment
            for i in range(L_ - sl + 1):
                seg = r[i:i + sl]
                rest = r[:i] + r[i + sl:]
                for k in range(len(rest) + 1):
                    if k == i:
                        continue
                    nr = rest[:k] + seg + rest[k:]
                    ev = _sd_eval(P, u, nr)
                    if ev[0] and ev[1] > base + 1e-6 and (best is None or ev[1] > best[1][1]):
                        best = (nr, ev)
        if best is not None:
            _sd_commit(P, u, best[0], best[1])
            if P.rfin[u] or any(P.jb[j][11] >= 0 for j in best[0]):
                _sd_fix_pairs(P, [u])
            improved = any_imp = True
        if time.perf_counter() > deadline or P.nev >= ev_end:
            break
    return any_imp


def _sd_relocate(P, j):
    """move job j to its best position anywhere (its own route included); True when the objective improved."""
    u = P.where[j]
    if u < 0:
        return False
    r = P.routes[u]
    i = r.index(j)
    r0 = r[:i] + r[i + 1:]
    ev0 = _sd_eval(P, u, r0)
    if not ev0[0]:
        return False
    gain0 = ev0[1] - P.rsc[u]
    best = None
    cands = _sd_cands(P, j)
    if u not in cands:
        cands.append(u)
    for v in cands:
        rv = r0 if v == u else P.routes[v]
        base = ev0[1] if v == u else P.rsc[v]
        for k in range(len(rv) + 1):
            if v == u and k == i:
                continue
            nr = rv[:k] + [j] + rv[k:]
            ev = _sd_eval(P, v, nr)
            if not ev[0]:
                continue
            d = (ev[1] - P.rsc[u]) if v == u else (gain0 + ev[1] - base)
            if d > 1e-6 and (best is None or d > best[0]):
                best = (d, v, nr, ev)
    if best is None:
        return False
    d, v, nr, ev = best
    if v == u:
        _sd_commit(P, u, nr, ev)
    else:
        _sd_commit(P, u, r0, ev0)                 # re-check the target against the reservations after the move
        ev = _sd_eval(P, v, nr)
        if not ev[0]:
            r1 = r0[:i] + [j] + r0[i:]
            ev1 = _sd_eval(P, u, r1)
            if ev1[0]:
                _sd_commit(P, u, r1, ev1)
            return False
        _sd_commit(P, v, nr, ev)
    if P.jb[j][13] or P.jb[j][11] >= 0 or P.rfin[u] or (v != u and P.rfin[v]):
        _sd_fix_pairs(P, [u, v])
    return True


def _sd_snap(P):
    return ([list(r) for r in P.routes], list(P.rsc), list(P.rend), list(P.rpw), list(P.rpf), list(P.rpa),
            list(P.rkp), list(P.rfin), list(P.where), dict(P.ft), P.tpw, P.tpf, list(P.tpa), Counter(P.seed_used),
            P.load)


def _sd_restore(P, s):
    (P.routes, P.rsc, P.rend, P.rpw, P.rpf, P.rpa, P.rkp, P.rfin, P.where, P.ft, P.tpw, P.tpf, P.tpa, P.seed_used,
     P.load) = ([list(r) for r in s[0]], list(s[1]), list(s[2]), list(s[3]), list(s[4]), list(s[5]), list(s[6]),
                list(s[7]), list(s[8]), dict(s[9]), s[10], s[11], list(s[12]), Counter(s[13]), s[14])


def _sd_rr(P, rng, deadline):
    """ruin (a seed job and its nearest planned jobs) and recreate (regret insertion with noise, the nearby
    unplanned jobs included); kept only when the objective improves."""
    planned = [j for j in range(P.J) if P.where[j] >= 0]
    if not planned:
        return False
    D = P.d
    seed = rng.choice(planned)
    b0 = P.jb[seed][0]
    m = rng.randint(2, max(2, CFG["sd_rr_max"]))
    near = sorted(planned, key=lambda j: (D[b0][P.jb[j][0]], rng.random()))[:m]
    snap = _sd_snap(P)
    obj0 = _sd_obj(P)
    touched = set(P.where[j] for j in near)
    rm = set(near)
    for u in touched:
        r2 = [x for x in P.routes[u] if x not in rm]
        ev = _sd_eval(P, u, r2)
        if not ev[0]:
            _sd_restore(P, snap)
            return False
        _sd_commit(P, u, r2, ev)
    _sd_fix_pairs(P, touched)
    pool = list(near) + [j for j in range(P.J) if P.where[j] < 0 and j not in rm
                         and (P.hard[j] or D[b0][P.jb[j][0]] <= 3)]
    _sd_insert_many(P, pool, rng, CFG["sd_rr_noise"], deadline)
    if _sd_obj(P) > obj0 + 1e-6:
        return True
    _sd_restore(P, snap)
    return False


def _sd_force_hard(P, deadline):
    """v2: each hard job still unplanned goes where the route stays feasible after dropping the non-hard jobs whose
    removal costs least (the nearest six units, every position); the dropped jobs are re-inserted where they fit.
    Returns the number of hard jobs placed."""
    D = P.d
    placed = 0
    for j in [j for j in range(P.J) if P.where[j] < 0 and P.hard[j]]:
        if time.perf_counter() > deadline or not _sd_seed_ok(P, j) or P.where[j] >= 0:
            continue
        b = P.jb[j][0]

        def dist(u):
            dm = D[b][P.up[u]]
            for x in P.routes[u]:
                if D[b][P.jb[x][0]] < dm:
                    dm = D[b][P.jb[x][0]]
            return dm
        units = sorted((u for u in range(P.U) if P.ue[u] >= 0), key=lambda u: (dist(u), u))[:6]
        best = None
        for u in units:
            r0 = P.routes[u]
            for k in range(len(r0) + 1):
                nr = r0[:k] + [j] + r0[k:]
                ev = _sd_eval(P, u, nr)
                rm = []
                while not ev[0]:
                    cand = None
                    for i, x in enumerate(nr):
                        if x == j or P.hard[x]:
                            continue
                        r2 = nr[:i] + nr[i + 1:]
                        e2 = _sd_eval(P, u, r2)
                        sc = e2[1] if e2[0] else -1e18
                        if cand is None or sc > cand[0]:
                            cand = (sc, i, e2)
                    if cand is None:
                        break
                    rm.append(nr[cand[1]])
                    nr = nr[:cand[1]] + nr[cand[1] + 1:]
                    ev = cand[2]
                if not ev[0]:
                    continue
                d = ev[1] - P.rsc[u]
                if best is None or d > best[0]:
                    best = (d, u, nr, ev, rm)
            if time.perf_counter() > deadline:
                break
        if best is None:
            continue
        d, u, nr, ev, rm = best
        _sd_commit(P, u, nr, ev)
        _sd_fix_pairs(P, [u])
        placed += 1
        if rm:
            _sd_insert_many(P, rm, None, 0.0, deadline)
    return placed


def _sd_seed_repair(P):
    """sd_seed_fix: the warm start re-adds the previous step's planting jobs without a seed check (seeds used or not
    bought since): drop the latest-placed real planting of an over-committed crop until the plan fits the seeds held."""
    for c in list(P.seed_used):
        over = P.seed_used[c] - P.seeds.get(c, 0)
        while over > 0:
            best = None
            for u in range(P.U):
                for i, j in enumerate(P.routes[u]):
                    if P.cropi[j] == c and P.real[j] and (best is None or (i, u) > (best[1], best[0])):
                        best = (u, i)
            if best is None:
                break
            u, i = best
            r2 = P.routes[u][:i] + P.routes[u][i + 1:]
            ev = _sd_eval(P, u, r2)
            if not ev[0]:
                r2, ev = _sd_repair(P, u, r2)
            _sd_commit(P, u, r2, ev)
            over -= 1
    _sd_fix_pairs(P, range(P.U))


def _sd_search(P, rng, t_end, evals_max):
    """improve the plan inside the budget; returns (iterations, rr tried, rr accepted, time capped)."""
    ev_end = P.nev + evals_max
    unpl = [j for j in range(P.J) if P.where[j] < 0]
    _sd_insert_many(P, unpl, None, 0.0, t_end)
    P.forced = 0
    if CFG["sd_hard_eject"] and any(P.hard[j] and P.where[j] < 0 for j in range(P.J)):
        P.forced = _sd_force_hard(P, t_end)
    capped = False
    it = rr_t = rr_a = 0
    for u in range(P.U):
        if P.routes[u] and P.nev < ev_end:
            _sd_intra(P, u, t_end, ev_end)
    while True:
        if time.perf_counter() > t_end:
            capped = True
            break
        if P.nev >= ev_end:
            break
        it += 1
        imp = False
        order = [j for j in range(P.J) if P.where[j] >= 0]
        rng.shuffle(order)
        for j in order:
            if P.nev >= ev_end or time.perf_counter() > t_end:
                break
            if P.where[j] >= 0 and _sd_relocate(P, j):
                imp = True
        for u in range(P.U):
            if P.routes[u] and P.nev < ev_end and _sd_intra(P, u, t_end, ev_end):
                imp = True
        unpl = [j for j in range(P.J) if P.where[j] < 0]
        if unpl and P.nev < ev_end and _sd_insert_many(P, unpl, None, 0.0, t_end):
            imp = True
        if imp:
            continue
        stall = 0                                  # local optimum: ruin and recreate until the budget / a stall
        while P.nev < ev_end and stall < CFG["sd_rr_stall"]:
            if time.perf_counter() > t_end:
                capped = True
                break
            rr_t += 1
            if _sd_rr(P, rng, t_end):
                rr_a += 1
                stall = 0
            else:
                stall += 1
        break
    if time.perf_counter() > t_end:
        capped = True
    return it, rr_t, rr_a, capped


def _sd_once_steal(P, rec):
    """sd_once_steal: a unit with an empty route takes the nearest job it can start earlier than its current holder would
    (an unassigned job always qualifies; a job of another unit's route only if it is not that route's head, i.e. not
    started or being walked to). Candidates nearest first until one fits; one job per repair."""
    D = P.d

    def starts(v):                                 # planned start hour of each job of route v (walk + ops, no detours)
        t, at, out = P.ut0[v], P.up[v], {}
        for j in P.routes[v]:
            b = P.jb[j][0]
            t = max(t + D[at][b], P.jb[j][9])
            out[j] = t
            t += P.jb[j][1]
            at = b
        return out
    for u in range(P.n_real):
        if P.ue[u] < 0 or P.routes[u]:
            continue
        cand = []
        for j in range(P.J):
            if P.where[j] < 0 and P.real[j]:
                cand.append((D[P.up[u]][P.jb[j][0]], j, -1))
        for v in range(P.n_real):
            if v == u or len(P.routes[v]) < 2:
                continue
            sv = starts(v)
            for j in P.routes[v][1:]:
                arr = P.ut0[u] + D[P.up[u]][P.jb[j][0]]
                if arr < sv[j]:
                    cand.append((D[P.up[u]][P.jb[j][0]], j, v))
        for d_, j, v in sorted(cand):
            if not _sd_seed_ok(P, j) and v < 0:
                continue
            nu = [j]
            evu = _sd_eval(P, u, nu)
            if not evu[0]:
                continue
            if v >= 0:
                rv = [x for x in P.routes[v] if x != j]
                evv = _sd_eval(P, v, rv)
                if not evv[0]:
                    continue
                _sd_commit(P, v, rv, evv)
            _sd_commit(P, u, nu, _sd_eval(P, u, nu))
            rec(u, "reassigned" if v >= 0 else "empty_route", j)
            if v >= 0:
                P.moved = getattr(P, "moved", 0) + 1
            break


def _sd_once_repair(P, L, ctx, prev, t_end):
    """sd_plan_once after the morning plan: the warm start kept every unit's own route (no re-optimisation, no
    reassignment); log what it dropped, then repair locally: (a) a planned job gone (its task vanished while the unit is
    not on the tile, i.e. not completed by it) or dropped as infeasible (input missing, stock, day end); (b) a new
    must-do (hard: a plant dying / an animal escaping tonight) or a job that did not exist at the previous step (a ripe
    melon, a replant, a structure's next part): best local insertion, nothing removed; (c) a unit with an empty route:
    its nearest open jobs appended (up to 3). Every repair: L["repairs"] [step, unit, reason, tile, key]."""
    step, pos = int(ctx["step"]), ctx["pos"]
    log = L.setdefault("repairs", [])
    st = L["st"]
    D = P.d

    def rec(u, reason, j=None, tile=None, key=None):
        log.append([step, int(u), reason, int(P.jb[j][0]) if j is not None else tile,
                    str(P.key[j]) if j is not None else key])
        st["repair_" + reason] = st.get("repair_" + reason, 0) + 1
    for u, keys in (prev or {}).items():
        if u >= P.U:
            continue
        kept = set(P.key[j] for j in P.routes[u])
        for i, k in enumerate(keys):
            j = P.kidx.get(k)
            if j is None and isinstance(k, tuple):
                j = P.kidx.get(k[1])
                if j is None:
                    j = P.kidx.get(("P", k[1]))
            tile = k[1] if isinstance(k, tuple) else k
            if j is None:
                p_ = tuple(pos[u]) if u < len(pos) else None
                if not (i == 0 and p_ is not None and p_[1] * 10 + p_[0] == tile):
                    rec(u, "gone", tile=tile, key=str(k))        # (a) the task vanished, not completed by this unit
            elif P.where[j] != u and P.key[j] not in kept:
                rec(u, "infeasible", j)                           # (a) dropped by the warm start's feasibility repair
    old = L.get("once_keys") or set()
    pool = [j for j in range(P.J) if P.where[j] < 0 and (P.hard[j] or P.key[j] not in old)]
    if pool:
        before = set(j for j in pool if P.where[j] < 0)
        _sd_insert_many(P, pool, None, 0.0, t_end)
        for j in before:
            if P.where[j] >= 0:
                rec(P.where[j], "must_do" if P.hard[j] else "new_job", j)
    if CFG["sd_once_steal"]:                       # (c) as a limited reassignment
        _sd_once_steal(P, rec)
    for u in range(P.n_real):
        if CFG["sd_once_steal"] or P.ue[u] < 0 or P.routes[u]:
            continue
        added = 0
        while added < 3:
            at = P.up[u] if not P.routes[u] else P.jb[P.routes[u][-1]][0]
            cand = sorted((D[at][P.jb[j][0]], j) for j in range(P.J) if P.where[j] < 0 and P.real[j])
            done = False
            for d_, j in cand[:12]:
                if not _sd_seed_ok(P, j):
                    continue
                nr = P.routes[u] + [j]
                ev = _sd_eval(P, u, nr)
                if ev[0] and ev[1] > P.rsc[u] + 1e-6:
                    _sd_commit(P, u, nr, ev)
                    rec(u, "empty_route", j)
                    added += 1
                    done = True
                    break
            if not done:
                break
    _sd_fix_pairs(P, range(P.U))


def _sd_step(S, L, ctx):
    """one planning run. Returns None (the greedy acts for everyone) or {P, units, first, claimed}."""
    st = L["st"]
    day, hour, step = ctx["day"], ctx["hour"], ctx["step"]
    if L["day"] != day:
        L["day"] = day
        L["routes"] = {}
        L["walk"] = {}
        L["pred_seen"] = {}
        L["home"] = {}
        L["first_of_day"] = True
        st["days_planned"] += 1
    t_start = time.perf_counter()
    first = L.pop("first_of_day", False) or not L["routes"]
    budget = CFG["sd_budget0"] if first else CFG["sd_budget"]
    evals = CFG["sd_evals0"] if first else CFG["sd_evals"]
    once = bool(CFG["sd_plan_once"])
    frozen = once and L.get("frozen_day") == day
    once_now = (once and not frozen and hour >= 1
                and (len(ctx["pos"]) - 1 >= _sd_want_hands(day) or hour >= 2))   # the day's hires are all on the board
    if once_now:
        budget, evals = max(CFG["sd_budget0"], budget), int(CFG["sd_once_evals"])
    if _SD_T:
        budget = min(budget, CFG["sd_step_cap"] - (time.time() - _SD_T[0]))
    budget = max(0.005, budget)
    t_end = t_start + budget
    try:
        P = _sd_build(S, L, ctx)
        rng = _sd_random.Random(int(CFG["sd_seed"]) * 100003 + step)
        prev = L["routes"]
        if prev:
            for u in range(P.U):
                r = []
                seen = set()
                for k in prev.get(u, ()):
                    j = P.kidx.get(k)
                    if j is None and isinstance(k, tuple):
                        j = P.kidx.get(k[1])                   # a predicted job whose task now exists
                        if j is None:
                            j = P.kidx.get(("P", k[1]))
                    if j is None or j in seen or P.where[j] >= 0:
                        continue
                    pr = P.jb[j][11]
                    if pr >= 0 and pr not in seen and P.where[pr] < 0:
                        continue                   # successor before its predecessor is planned: re-inserted later
                    seen.add(j)
                    r.append(j)
                if r:
                    r, ev = _sd_repair(P, u, r)
                    _sd_commit(P, u, r, ev)
            _sd_fix_pairs(P, range(P.U))
            if CFG["sd_seed_fix"]:
                _sd_seed_repair(P)
        else:
            _sd_construct(P)
        P.obj_start = _sd_obj(P)
        if frozen:                                 # plan once: frozen routes, local repairs on breakage only
            it, rr_t, rr_a, capped = 0, 0, 0, False
            _sd_once_repair(P, L, ctx, prev, t_end)
        else:
            it, rr_t, rr_a, capped = _sd_search(P, rng, t_end, evals)
        if once_now:
            L["frozen_day"] = day
            L.setdefault("once_steps", []).append(int(step))
        if once:
            L["once_keys"] = set(P.key)
        L["routes"] = {u: [P.key[j] for j in P.routes[u]] for u in range(P.U) if P.routes[u]}
    except Exception as exc:
        st["errors"] += 1
        st["fb_step"] += 1
        st["last_error"] = ("%s: %s" % (type(exc).__name__, exc))[:300]
        try:
            S["log"]["sd_err:step:" + st["last_error"][:100]] += 1      # the text survives in agent_log
        except Exception:
            pass
        L["routes"] = {}
        return None
    ms = 1000.0 * (time.perf_counter() - t_start)
    st["steps"] += 1
    st["plan_ms"].append(round(ms, 2))
    if first:
        st["plan_ms_first"].append(round(ms, 2))
    st["evals"] += P.nev
    st["time_capped"] += 1 if capped else 0
    st["rr_tried"] += rr_t
    st["rr_acc"] += rr_a
    st["forced_hard"] += getattr(P, "forced", 0)
    unpl = [j for j in range(P.J) if P.where[j] < 0 and P.real[j]]
    unv = sum(P.vraw[j] for j in unpl)
    if hour == 1 or (first and hour > 1):
        st["planned_drop_first"] += len(unpl)
        st["planned_drop_first_value"] += unv
    st["planned_hard_unplanned"] += sum(1 for j in unpl if P.hard[j])
    if hour == 23:
        st["load_proj_h23"].append(round(P.load, 1))
    if CFG["sd_log"]:
        L["recs"].append({"s": step, "ms": round(ms, 1), "J": P.J, "U": P.U, "un": len(unpl), "unv": round(unv, 1),
                          "unh": sum(1 for j in unpl if P.hard[j]), "ev": P.nev, "it": it, "rr": [rr_t, rr_a],
                          "cap": int(capped), "load": round(P.load, 1), "obj0": round(P.obj_start, 1),
                          "obj": round(_sd_obj(P), 1),
                          "busy": sum(max(0, P.rend[u] - P.ut0[u]) for u in range(P.U) if P.routes[u])})
    if CFG["sd_keep"]:
        L["lastP"] = P
    if CFG["sd_plan_log"]:                         # viewer: each hand's planned job tiles (route order), on every change
        snap = {str(u): [int(P.jb[j][0]) for j in P.routes[u]] for u in range(P.n_real)}
        if snap != L.get("plan_last"):
            L.setdefault("plan_log", {})[str(step)] = snap
            L["plan_last"] = snap
    first_job, claimed = {}, set()
    for u in range(P.n_real):
        fk = None
        for j in P.routes[u]:
            if P.real[j]:
                claimed.add(P.jb[j][0])
                if fk is None:
                    fk = P.jb[j][0]
        if fk is not None:
            first_job[u] = fk
    ctrl = set(u for u in range(P.n_real) if P.uctrl[u])
    return {"P": P, "ctrl": ctrl, "first": first_job, "claimed": claimed}


def _sd_hire_plan(S, L, ctx):
    """hour 0: the day's hire count (sd_hire_demand) and the spawn steering (sd_spawn_steer); L["hire"]."""
    day, hour, pos = ctx["day"], ctx["hour"], ctx["pos"]
    st = L["st"]
    L.setdefault("hire_extra0", CFG["hire_extra"])
    CFG["hire_extra"] = L["hire_extra0"]           # the executor's own count this morning
    if L["day"] != day:                            # the day's first step: no stale walks / predicted jobs in the tries
        L["walk"] = {}
        L["pred_seen"] = {}
    want = _sd_want_hands(day)
    ks = list(range(max(1, want - 6), want + 1)) if CFG["sd_hire_demand"] else [want]
    rng = _sd_random.Random(int(CFG["sd_seed"]) * 7919 + day)
    best, plans = None, {}
    cap = 10                                       # the engine executes 10 market orders a step: hires beyond wait for hour 1
    for k in ks:
        vu = [(q, 1) for q in _sd_spawn(pos, min(k, cap))] + [(q, 2) for q in _sd_spawn([], k - min(k, cap))]
        P = _sd_build(S, L, dict(ctx, vunits=vu))
        _sd_construct(P)
        _sd_search(P, rng, time.perf_counter() + 10.0, int(CFG["sd_hire_evals"]))
        net = _sd_obj(P) - sum(_fib(i) for i in range(k))
        plans[k] = P
        if best is None or net > best[0] + 1e-6:
            best = (net, k)
    k = best[1]
    st["hire_k"] = st.get("hire_k", 0) + k
    st["hire_want"] = st.get("hire_want", 0) + want
    F, k0 = tuple(pos[0]), min(k, cap)
    vunits = [(q, 1) for q in _sd_spawn(pos, k0)] + [(q, 2) for q in _sd_spawn([], k - k0)]
    if CFG["sd_spawn_steer"]:
        P = plans[k]
        W = [0.0] * 4
        for j in range(P.J):
            if P.real[j]:
                W[_sd_qi(P.jb[j][0])] += P.jb[j][1]
        tot = sum(W) or 1.0
        tgt = [(k + 1) * W[q] / tot for q in range(4)]
        tgt[0] -= 1.0                              # the farmer works the second quadrant (NW)
        f0 = tuple(pos[0])
        opts = [(f0, 0.0)] + [((f0[0] + dx, f0[1] + dy), 0.1) for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1))]
        cand = None
        for Fp, fc in opts:
            if not (0 <= Fp[0] < 10 and 0 <= Fp[1] < 10):
                continue
            for k0_ in range(min(k, cap), max(-1, min(k, cap) - 5), -1):
                sp0 = _sd_spawn([Fp], k0_)
                sp1 = _sd_spawn([], k - k0_)       # at hour 1 the hour-0 units have left the shed tiles
                cnt = [0] * 4
                for q in sp0 + sp1:
                    cnt[_sd_qi(q[1] * 10 + q[0])] += 1
                sc = sum(abs(cnt[q] - tgt[q]) for q in range(4)) + 0.25 * (k - k0_) + fc
                key = (round(sc, 6), -k0_)
                if cand is None or key < cand[0]:
                    cand = (key, Fp, k0_, [(q, 1) for q in sp0] + [(q, 2) for q in sp1], cnt)
        _, F, k0, vunits, cnt = cand
        st["steer_moves"] = st.get("steer_moves", 0) + (1 if F != f0 else 0)
        st["steer_h1"] = st.get("steer_h1", 0) + (k - k0)
    L["hire"] = {"day": day, "k": int(k), "k0": int(k0), "F": F, "vunits": vunits}


def _sd_pre(S, obs, me, step, day, hour, last_day, tiles, pos, invs, tasks, jobs, shed, seeds, prices, assign, taken,
            surv_route, deliv_u, fert_keep, demand, prev):
    """HOOK 1 (after the delivery rule and the survival routes, before the greedy matching): plan; in active mode the
    planned units get their first planned tile as their assignment (the greedy matching skips them) and leave the
    greedy's survival routes; the greedy keeps the units without a route. A delivery the executor's rule starts THIS
    step for a planned unit standing on its current planned tile waits until the tile is done (the routes check the
    trigger after each job; a mid-tile delivery abandoned a seedling between PLANT and WATER)."""
    L = _sd_state(S)
    run = {"active": False, "units": set(), "P": None, "first": {}, "claimed": set(), "acted": set(), "jobs": jobs}
    try:
        _sd_watch(L, tiles, day, hour)
    except Exception as exc:
        L["st"]["errors"] += 1
        L["st"]["last_error"] = ("watch %s: %s" % (type(exc).__name__, exc))[:300]
        try:
            S["log"]["sd_err:" + L["st"]["last_error"][:100]] += 1
        except Exception:
            pass
    if CFG["sd_water_first"]:
        for idx, (ops_, need_, prio_) in list(tasks.items()):
            if ops_ and ops_[0][0] == "HARVEST" and not any(o[0] == "WATER" for o in ops_):
                t_ = _tile(tiles, idx)
                if _is_plant(t_) and not t_.get("watered_today"):
                    c_ = CROPS.get(t_.get("crop"))
                    if c_ and not c_["ongoing"]:
                        a_ = day - int(t_.get("planted_day", day))
                        if (c_["maxday"] + 1) // 2 <= a_ <= c_["maxday"] and int(t_.get("yield_units", 0) or 0) < c_["max"]:
                            tasks[idx] = ([["WATER"]] + [list(o) for o in ops_], need_, prio_)
                            L["st"]["water_first"] = L["st"].get("water_first", 0) + 1
    win = CFG["sd_days"]
    if L["off"] or (win is not None and not (int(win[0]) <= day <= int(win[1]))):
        return run
    if CFG["sd_tier"]:                             # tiered fixed plan: planned at hour 0, executed by _tier_override
        try:
            _tier_pre(S, L, obs, step, day, hour, last_day, tiles, pos, invs, tasks, jobs, shed, seeds, prices, assign,
                      deliv_u, fert_keep, demand)
        except Exception as exc:
            L["st"]["errors"] += 1
            L["st"]["last_error"] = ("tier %s: %s" % (type(exc).__name__, exc))[:300]
            try:
                import traceback as _tb
                L["st"]["tier_tb"] = _tb.format_exc()[-1500:]
                S["log"]["sd_err:" + L["st"]["last_error"][:100]] += 1
            except Exception:
                pass
        return run
    if CFG["dispatch_search"] == "active" and CFG["sd_finish_tile"] and L["day"] == day:
        for u in [u for u, v in assign.items() if v == "D" and prev.get(u) != "D" and u < len(pos)]:
            p = tuple(pos[u])
            idx = p[1] * 10 + p[0]
            r = L["routes"].get(u)
            k0 = (r[0] if isinstance(r[0], int) else r[0][1]) if r else None
            if idx in tasks and k0 == idx and day < last_day:
                assign.pop(u, None)
                L["st"]["deliv_deferred"] += 1
    keep, stiles = set(), set()
    mflag = {}
    if CFG["sd_melon_rule"] and day < last_day:
        ml_ = S.get("melon") or {}
        if hour == 0 and len(pos) == 1 and ml_.get("fday") != day:
            ml_ = _mel_plan_farmer(S, day, tiles, tuple(pos[0]))
        if ml_.get("day") != day and (len(pos) > 1 or hour >= 2):
            ml_ = _mel_plan(S, day, hour, tiles, pos)
            L["st"]["melon_plan"] = [list(x) for x in ml_.get("plan", [])]
            L["st"]["melon_left_out"] = list(ml_.get("left_out", []))
        if ml_.get("day") == day or ml_.get("fday") == day:
            keep |= {u for u, r in ml_.get("routes", {}).items() if not r["done"] and u < len(pos)}
            # harvested-by flag (user): the melon hand harvests these tiles at the planned hour; nobody else waters /
            # harvests them, and a replant there may only start after that hour
            for i_ in ml_.get("tiles", ()):
                if i_ in tasks:
                    ops_, need_, prio_ = tasks[i_]
                    rest_ = [list(o) for o in ops_ if o[0] not in ("WATER", "HARVEST")]
                    if rest_:
                        tasks[i_] = (rest_, need_, prio_)
                    else:
                        del tasks[i_]
                mflag[i_] = int(ml_.get("hby", {}).get(i_, hour)) + 1
    if CFG["sd_surv_fb"] is not None and hour >= int(CFG["sd_surv_fb"]) and surv_route:
        keep |= set(surv_route)
        stiles |= set(i_ for r_ in surv_route.values() for i_, o_ in r_)
        L["st"]["surv_fb_units"] += len(keep)
    ctx = {"keep": keep, "stiles": stiles, "mflag": mflag, "obs": obs, "day": day, "hour": hour, "step": step, "tiles": tiles, "tasks": tasks, "invs": invs, "pos": pos,
           "shed": shed, "seeds": seeds, "assign": assign, "last_day": last_day, "jobs": jobs, "prices": prices,
           "deliv_u": deliv_u, "fert_keep": fert_keep, "demand": demand}
    if (hour == 0 and len(pos) == 1 and day < last_day and CFG["dispatch_search"] == "active"
            and (CFG["sd_hire_demand"] or CFG["sd_spawn_steer"])):
        try:
            _sd_hire_plan(S, L, ctx)
        except Exception as exc:
            L["st"]["errors"] += 1
            L["st"]["last_error"] = ("hire %s: %s" % (type(exc).__name__, exc))[:300]
            L.pop("hire", None)
    hp = L.get("hire")
    if hp and hp.get("day") == day and hour == 0:
        ctx["vunits"] = hp["vunits"]
    r = _sd_step(S, L, ctx)
    if r is None:
        return run
    run.update(P=r["P"], first=r["first"], claimed=r["claimed"])
    if CFG["dispatch_search"] != "active":
        return run
    P = r["P"]
    run["active"] = True
    idle_pass = CFG["sd_idle"] == "pass"
    for u in r["ctrl"]:
        if not P.routes[u]:
            if idle_pass and u not in surv_route:
                run["units"].add(u)                # planned idle (delivers what it carries, else waits)
            continue                               # no route but a greedy survival route: the greedy keeps it
        run["units"].add(u)
        surv_route.pop(u, None)
        fk = r["first"].get(u)
        if fk is not None and fk in tasks:
            assign[u] = fk
        elif u in assign and assign[u] != "D":
            assign.pop(u, None)
    taken.clear()
    taken.update(v for v in assign.values() if v != "D")
    taken.update(k for k in r["claimed"] if k in tasks)
    return run


def _sd_idle_v2(P, run, st, u, p, pi, inv, tiles, hour, deliv_u):
    """sd_idle_v2 (user rules): only a unit whose planned route is empty; outside route insertion, no values. First its
    sellable stock and fertilizer to the shed while a same-day sale is still possible, then the nearest dry plant in its
    home quadrant (the quadrant it stands in without a home) that no route plans and no other idle unit is heading to."""
    dv = dict(deliv_u(u))
    if inv.get("FERTILIZER", 0) > 0:
        dv["FERTILIZER"] = int(inv["FERTILIZER"])
    if dv and hour < 23:
        s = _near_shed(p)
        if hour + _dist(p, s) + 1 <= P.dv_h1:     # the drop ends by the sale hour: sold the same day
            st["idle_v2_deliver"] = st.get("idle_v2_deliver", 0) + 1
            if p != s:
                return _step_toward(p, s)
            if all(k in dv for k in inv):
                return ["DROP"]
            k = sorted(dv)[0]
            return ["PLACE", k, int(inv[k])]
    pt = run.get("ptiles")
    if pt is None:
        pt = run["ptiles"] = set(P.jb[j][0] for r_ in P.routes for j in r_)
    tg = run.setdefault("idle_tgt", set())
    q = P.uhome[u] if P.uhome[u] >= 0 else _sd_qi(pi)
    best = None
    for idx in range(100):
        if idx in pt or idx in tg or _sd_qi(idx) != q:
            continue
        t = _tile(tiles, idx)
        if not (_is_plant(t) and not t.get("watered_today")):
            continue
        d = P.d[pi][idx]
        if best is None or (d, idx) < best:
            best = (d, idx)
    if best is None:
        return None
    b = best[1]
    tg.add(b)
    st["idle_v2_water"] = st.get("idle_v2_water", 0) + 1
    if pi != b:
        return _step_toward(p, (b % 10, b // 10))
    return ["WATER"]


def _sd_act(S, run, u, p, inv, tasks, tiles, shed_left, seeds_left, plant_count, carried, hour, usable_ops, deliv_u):
    """HOOK 2: next command of planned unit u, or None (the greedy code decides this unit's step)."""
    P = run["P"]
    L = S["sd"]
    st = L["st"]
    walk = L["walk"]
    pi = p[1] * 10 + p[0]
    r = P.routes[u]
    if CFG["sd_coop_pair"]:                        # never an empty structure: standing on one with its animal, place it
        t_ = _tile(tiles, pi)
        if isinstance(t_, dict) and t_.get("kind") in ("COOP", "PASTURE") and "animal" not in t_:
            for sp_ in _SD_SP:
                if ANIMALS[sp_]["structure"] == t_["kind"] and inv.get(sp_, 0) > 0:
                    st["pair_place_now"] = st.get("pair_place_now", 0) + 1
                    st["planned_unit"] += 1
                    run["acted"].add(u)
                    return ["PLACE", sp_]
    if not r:
        st["idle_unit"] += 1
        w = walk.get(u)
        if w and w[1]:
            st["switch_steps"] += w[1]
        walk[u] = (None, 0)
        if CFG["sd_idle_v2"]:
            a_ = _sd_idle_v2(P, run, st, u, p, pi, inv, tiles, hour, deliv_u)
            return a_ if a_ is not None else ["PASS"]
        dv = deliv_u(u)
        if CFG["sd_idle_fert"] and inv.get("FERTILIZER", 0) > 0 and "FERTILIZER" not in dv:
            dv = dict(dv)
            dv["FERTILIZER"] = int(inv["FERTILIZER"])   # an idle unit has no fertilize job left: its fertilizer to the shed
        if dv and hour < 23:
            st["idle_deliver"] += 1
            s = _near_shed(p)
            if p != s:
                return _step_toward(p, s)
            if all(k in dv for k in inv):
                return ["DROP"]
            k = sorted(dv)[0]
            return ["PLACE", k, int(inv[k])]
        return ["PASS"]
    j0 = r[0]
    b0 = P.jb[j0][0]
    key0 = P.key[j0]
    w = walk.get(u, (None, 0))
    if w[0] is not None and w[0] != key0 and w[1]:
        st["switch_steps"] += w[1]
    kp, npk = P.rkp[u]
    if kp == 0 and npk:
        s = P.sa[pi][b0]
        if pi != s:
            walk[u] = (None, 0)
            st["planned_unit"] += 1
            return _step_toward(p, (s % 10, s // 10))
        if CFG["sd_hs_drop"] and CFG["hand_stock"] and hour >= CFG["hs_drop_hour"] and P.rpw[u] == 0:
            sur = inv.get("WHEAT", 0) - sum(P.jb[j][2] for j in r) - CFG["hs_buffer"]
            if sur > 0:
                S["log"]["hs_drop"] += int(sur)
                st["planned_unit"] += 1
                return ["PLACE", "WHEAT", int(sur)]
        pa = P.rpa[u]
        for item, amt in (("WHEAT", P.rpw[u]), ("FERTILIZER", P.rpf[u]), ("GOOSE", pa[0]), ("COW", pa[1]),
                          ("SHEEP", pa[2])):
            if amt > 0:
                a = min(int(amt), int(shed_left.get(item, 0)))
                if a > 0:
                    shed_left[item] -= a
                    carried[item] += a
                    walk[u] = (None, 0)
                    st["planned_unit"] += 1
                    return ["PICKUP", item, a]
        st["fb_unit"] += 1
        st["fb_pickup"] += 1
        return None
    if pi != b0:
        walk[u] = (key0, (w[1] + 1) if w[0] == key0 else 1)
        st["planned_unit"] += 1
        return _step_toward(p, (b0 % 10, b0 // 10))
    walk[u] = (None, 0)
    if not P.real[j0]:
        st["pred_wait"] += 1
        st["planned_unit"] += 1
        return ["PASS"]                            # predicted job: wait on the tile for its task
    if isinstance(key0, tuple) and key0[0] == "W" and b0 not in tasks:   # sd_water_tomorrow: a planner-only water
        t = _tile(tiles, b0)
        if _is_plant(t) and not t.get("watered_today"):
            st["planned_unit"] += 1
            st["water_tomorrow"] = st.get("water_tomorrow", 0) + 1
            run["acted"].add(u)
            return ["WATER"]
    if isinstance(key0, tuple) and key0[0] == "H" and b0 not in tasks:   # v3: an offered melon harvest
        t = _tile(tiles, b0)
        if _is_plant(t) and int(t.get("yield_units", 0) or 0) > 0:
            st["planned_unit"] += 1
            st["offered_harvest"] += 1
            run["acted"].add(u)
            return ["HARVEST"]
    if b0 not in tasks:
        st["fb_unit"] += 1
        st["fb_notask"] += 1
        return None
    ops, need, prio = tasks[b0]
    t = _tile(tiles, b0)
    act = None
    for op in usable_ops(u, ops, need):
        c = op[0]
        if c == "FEED" and inv.get("WHEAT", 0) <= 0:
            continue
        if c == "CARE" and isinstance(t, dict) and not t.get("fed_today") and any(o[0] == "FEED" for o in ops):
            continue
        if c == "FERTILIZE" and inv.get("FERTILIZER", 0) <= 0:
            continue
        if c == "PLACE" and inv.get(op[1], 0) <= 0:
            break
        if c in ("BUILD_COOP", "BUILD_PASTURE") and (CFG["sd_bundle_build"] or CFG["sd_coop_pair"]):
            sp_ = next((o[1] for o in ops if o[0] == "PLACE" and len(o) > 1), None)
            if sp_ and inv.get(sp_, 0) <= 0:       # never an empty structure: fetch the animal first (or wait)
                if shed_left.get(sp_, 0) > 0:
                    st["fb_unit"] += 1
                    st["fb_pickup"] += 1
                    return None
                st["planned_unit"] += 1
                return ["PASS"]
        if c == "PLANT":
            if seeds_left.get(op[1], 0) <= 0 or hour >= 23:
                break
            seeds_left[op[1]] -= 1
            plant_count[op[1]] += 1
        act = op
        break
    if act is None:
        st["fb_unit"] += 1
        st["fb_noop"] += 1
        return None
    st["planned_unit"] += 1
    run["acted"].add(u)
    return list(act)


def _sd_watch(L, tiles, day, hour):
    """plants that turned into weeds (dried out or decayed) and animals gone since the previous step."""
    st = L["st"]
    cur, thirst = [], set()
    for idx in range(100):
        t = _tile(tiles, idx)
        if _is_plant(t):
            cur.append("P")
            if not t.get("watered_today") and t.get("consecutive_unwatered", 0) >= 1:
                thirst.add(idx)
        elif _animal(t):
            cur.append("A")
        elif _is_weed(t):
            cur.append("W")
        else:
            cur.append(None)
    prev = L.get("prev_kind")
    if prev is not None:
        pth = L.get("prev_thirst") or set()
        w23 = L.get("water23") or set()
        for idx in range(100):
            if prev[idx] == "P" and cur[idx] == "W":
                st["plants_lost"] += 1
                if hour == 0 and idx in pth and idx not in w23:
                    st["plants_lost_thirst"] += 1
            elif prev[idx] == "A" and cur[idx] != "A":
                st["animals_lost"] += 1
    L["prev_kind"] = cur
    L["prev_thirst"] = thirst
    if hour == 0:
        L["water23"] = set()


# ---------------------------------------------------------------- melon rule (user, 2026-09-28; hard-coded) ----------
# Every melon harvestable today is watered (if that brings it to full units), harvested and PLACEd at a shed tile.
# Delivery hour h (the hour of the PLACE): before 8 earns sd_mel_bonus per melon unit per hour early, 8-12 costs
# sd_mel_pen per unit per hour late, after 12 is not allowed. Plans are ranked (lateness cost, hands used, -early bonus):
# a hand takes several melons only while that keeps the lateness cost minimal. Melon hands and melon tiles are kept out
# of the planner until the melons are placed; then the hand rejoins normal work.
import itertools as _mel_it


def _mel_ripe(t, day):
    if not (isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == "MELON"):
        return False
    return day - int(t.get("planted_day", day)) >= CROPS["MELON"]["first"] and int(t.get("yield_units", 0) or 0) > 0


def _mel_needs_water(t, day):
    c = CROPS["MELON"]
    a = day - int(t.get("planted_day", day))
    return (not t.get("watered_today")) and (c["maxday"] + 1) // 2 <= a <= c["maxday"] and int(t.get("yield_units", 0)) < c["max"]


def _mel_block(p0, hour, block, tiles, day):
    """best order of the melon tiles in block for a unit at p0 acting from `hour`: (drop hour, cost, units, order,
    {tile: planned harvest hour})."""
    best = None
    for order in _mel_it.permutations(block):
        p, steps, units, hh = tuple(p0), 0, 0, {}
        for i in order:
            q = (i % 10, i // 10)
            t = _tile(tiles, i)
            steps += _dist(p, q)
            w = _mel_needs_water(t, day)
            steps += 1 + (1 if w else 0)
            hh[i] = hour + steps - 1
            units += min(CROPS["MELON"]["max"], int(t.get("yield_units", 0)) + (1 if w else 0))
            p = q
        s = _near_shed(p)
        steps += _dist(p, s) + 1
        drop = hour + steps - 1
        if best is None or drop < best[0]:
            best = (drop, units, order, hh)
    drop, units, order, hh = best
    if drop > 12:
        cost = float("inf")
    else:
        cost = units * (float(CFG["sd_mel_pen"]) * max(0, drop - 8) - float(CFG["sd_mel_bonus"]) * max(0, 8 - drop))
    return drop, cost, units, order, hh


def _mel_partitions(items):
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for part in _mel_partitions(rest):
        for k in range(len(part)):
            yield part[:k] + [[first] + part[k]] + part[k + 1:]
        yield [[first]] + part


def _mel_hand_starts():
    return [(4, 4), (5, 4), (4, 5), (5, 5)]


def _mel_plan_farmer(S, day, tiles, pos0):
    """hour 0: the farmer (the only unit on the board) takes the melons no hand starting at hour 1 from a shed tile can
    drop by 12 but he can (best block of up to 3)."""
    ripe = [i for i in range(100) if _mel_ripe(_tile(tiles, i), day)]
    L = S.setdefault("melon", {})
    L.clear()
    L.update(fday=day, routes={}, tiles=set(), plan=[], hby={})
    only_f = []
    for i in ripe:
        hand_best = min(_mel_block(s0, 1, [i], tiles, day)[0] for s0 in _mel_hand_starts())
        far = _mel_block(pos0, 0, [i], tiles, day)
        if hand_best > 12 and far[0] <= 12:
            only_f.append(i)
    best = None
    for k in range(min(3, len(only_f)), 0, -1):
        for blk in _mel_it.combinations(only_f, k):
            b = _mel_block(pos0, 0, list(blk), tiles, day)
            if b[1] == float("inf"):
                continue
            key = (-k, b[1])
            if best is None or key < best[0]:
                best = (key, b)
        if best is not None:
            break
    if best is not None:
        drop, cost, units, order, hh = best[1]
        L["routes"][0] = {"tiles": list(order), "done": False}
        L["tiles"].update(order)
        L["hby"].update(hh)
        L["plan"].append((0, list(order), drop))
    return L


def _mel_plan(S, day, hour, tiles, pos):
    L = S.setdefault("melon", {})
    if L.get("fday") != day:
        L.clear()
        L.update(routes={}, tiles=set(), plan=[], hby={})
    L["day"] = day
    busy = {u for u, r in L["routes"].items() if not r["done"]}
    ripe = [i for i in range(100) if _mel_ripe(_tile(tiles, i), day) and i not in L["tiles"]]
    units = [u for u in range(len(pos)) if u not in busy]
    # a melon nobody can drop by 12 stays out of the rule (user: after 12 = +INF): the planner harvests it later
    ok_ripe = [i for i in ripe if units and min(_mel_block(pos[u], hour, [i], tiles, day)[0] for u in units) <= 12]
    L["left_out"] = [i for i in ripe if i not in ok_ripe]
    if not ok_ripe:
        return L
    best = None
    for part in _mel_partitions(ok_ripe[:8]):
        if len(part) > len(units):
            continue
        cand = []
        for b in part:
            opts = sorted((_mel_block(pos[u], hour, b, tiles, day) + (u,) for u in units), key=lambda x: (x[1], x[0]))
            cand.append((opts, b))
        cand.sort(key=lambda c: -c[0][0][1] if c[0][0][1] != float("inf") else -1e18)
        used, tot, bonus, asg = set(), 0.0, 0.0, []
        ok = True
        for opts, b in cand:
            pick = next((o for o in opts if o[5] not in used), None)
            if pick is None or pick[1] == float("inf"):
                ok = False
                break
            used.add(pick[5])
            tot += max(0.0, pick[1])
            bonus += max(0.0, -pick[1])
            asg.append((pick[5], list(pick[3]), pick[0], pick[4]))
        if not ok:
            continue
        key = (round(tot, 3), len(part), -bonus)
        if best is None or key < best[0]:
            best = (key, asg)
    if best is None:
        return L
    for u, order, drop, hh in best[1]:
        L["routes"][u] = {"tiles": list(order), "done": False}
        L["tiles"].update(order)
        L["hby"].update(hh)
        L["plan"].append((u, list(order), drop))
    return L


def _mel_act(S, day, hour, tiles, pos, invs, actions, last_day):
    L = S.get("melon") or {}
    if L.get("day") != day and L.get("fday") != day:
        return
    for u, r in L.get("routes", {}).items():
        if r["done"] or u >= len(pos) or u >= len(actions):
            continue
        p = tuple(pos[u])
        while r["tiles"] and not _mel_ripe(_tile(tiles, r["tiles"][0]), day):
            L["tiles"].discard(r["tiles"].pop(0))     # harvested (by us) or gone
        if r["tiles"]:
            i = r["tiles"][0]
            q = (i % 10, i // 10)
            if p != q:
                actions[u] = _step_toward(p, q)
            else:
                t = _tile(tiles, i)
                actions[u] = ["WATER"] if _mel_needs_water(t, day) else ["HARVEST"]
            continue
        inv = invs[u] if u < len(invs) else {}
        n = int(inv.get("MELON", 0) or 0)
        if n <= 0:
            r["done"] = True
            continue
        s = _near_shed(p)
        actions[u] = _step_toward(p, s) if p != s else ["PLACE", "MELON", n]


# ---------------------------------------------------------------- tiered fixed plan (user, 2026-09-28) ----------------
# sd_tier = 1: the day is planned ONCE at hour 0 and never re-planned. Every hand is a PRIORITY-HARVEST hand (melons, the
# melon rule's partition: back at the shed by 8, else by 12 with a penalty) or an OUTBOUND hand (never walks back; what it
# carries reaches the shed with the midnight dump). Order (user):
#   A. melon hands (a melon hand also replants its melon tile when its drop stays on time, i.e. by 8);
#   B. mandatory work -- harvests, the leader's plantings / builds (replants), keep-alive waterings (and the water before a
#      harvest), keep-alive feeds -- split into SECTORS = each hand's tiles of responsibility (one owner per plant tile) by
#      a heuristic search: every mandatory op done by hour 23 (hard), each patch consecutive (hop weight), fertilizer
#      collectable on the outbound leg rewarded (for the fertilize work in the patch);
#   C. extras on the outbound hands: collect -> fertilize pairs, extra waterings;
#   D. animal work (feed / care / collect) from the melon hands' leftover labour first (and an animal hand, if hired);
#   E. the slack left anywhere, by value per hour.
# Execution: each hand walks its fixed list; the only fixes are local (dig a weed before planting, skip an op that cannot
# be done, wait for a tile another hand has not cleared yet). Every breakage is logged in S["tier"]["log"].
import math as _tier_math
import random as _tier_random

_TIER_SHED_I = [q[1] * 10 + q[0] for q in SHED]
_TIER_D = [[abs(a % 10 - b % 10) + abs(a // 10 - b // 10) for b in range(100)] for a in range(100)]
_TIER_CC = {"n": 0}    # sd_tier_collect_c: phase C collects placed today
_TIER_WY = {}          # sd_tier_feed_harvest: tile -> wheat units a harvest there yields today (set per planning call)
_TIER_ANG = [_tier_math.atan2(-((i // 10) - 4.5), (i % 10) - 4.5) for i in range(100)]
_TIER_BIG = 1000.0
_TIER_RANK = {"DIG": 0, "COLLECT_FERTILIZER": 1, "FEED": 2, "CARE": 3, "FERTILIZE": 4, "WATER": 5, "HARVEST": 6, "PLACE_HARVEST": 6.5,
              "PLANT": 7, "WATER2": 8, "BUILD_COOP": 9, "BUILD_PASTURE": 9, "PLACE": 10}


def _tier_near_shed(i):
    return min(_TIER_SHED_I, key=lambda s: (_TIER_D[i][s], s))


def _tier_op(c, m, v, tier, after_plant=False):
    k = "WATER2" if (c[0] == "WATER" and after_plant) else c[0]
    return {"c": list(c), "m": bool(m), "v": float(v), "tier": int(tier), "rank": _TIER_RANK.get(k, 5)}


def _tier_picks(stops):
    nf, na = 0, Counter()
    hw = 0                                         # sd_tier_feed_harvest: wheat in hand from this route's own harvests
    for s in stops:
        for o in s["ops"]:
            c = o["c"]
            if c[0] == "HARVEST" and _TIER_WY and o["m"] and s["tile"] in _TIER_WY                     and not any(o2["c"][0] == "PLACE_HARVEST" for o2 in s["ops"]):
                hw += _TIER_WY[s["tile"]]
            elif c[0] == "FEED":
                if hw > 0:
                    hw -= 1
                    continue
                nf += 1
            elif c[0] == "PLACE" and len(c) > 1 and c[1] in ANIMALS:
                na[c[1]] += 1
    return nf, na


def _tier_eval(seg, stops=None, want_hours=False):
    """(end hour, lateness, hops inside the patch, supply failures[, op hours]) of a segment {"p0", "t0", "stops"}: the
    pickups (one wheat per FEED, the animals it PLACEs) happen at the shed before its first stop; lateness = hours a
    mandatory op runs after 23 plus hours any op runs past the day."""
    D = _TIER_D
    stops = seg["stops"] if stops is None else stops
    t, p = seg["t0"], seg["p0"]
    gr = seg.get("goose_ready", 2)
    late = hop = bad = 0
    nf, na = _tier_picks(stops)
    fp_ = int(seg.get("fpick", 0) or 0)                # sd_tier_sclu_fert: fertilizer picked up at the start
    if CFG["sd_wheat_fert_mand"]:                      # mandatory fertilizes not covered by the route's collects: shed pickup
        fp_ += _tier_fmand_need(stops, fp_)
    w, f = 0, 0
    an = Counter()
    kd = 0
    while kd < len(stops) and stops[kd].get("dawn"):   # sd_tier_dawn: the dawn leg first, the pickups after it (DSM's order)
        kd += 1
    if seg.get("hold0") and t == 0 and not ((kd == 0 and (nf or na or fp_) and p in _TIER_SHED_I)
                                            or (stops and stops[0]["tile"] == p)):
        t = 1                                      # sd_tier_farmer_h0pick: he may not move at hour 0 (the hires' spawn)
    hours = [] if want_hours else None
    first = True
    for i_s in range(len(stops) + 1):
        if i_s == kd:
            if nf or na or fp_:
                if p not in _TIER_SHED_I:
                    s_ = _tier_near_shed(p)
                    t += D[p][s_]
                    p = s_
                if nf:
                    t += 1
                    w = nf
                if fp_:
                    t += 1
                    f += fp_
                for a_, v_ in na.items():
                    t = max(t, gr) + 1
                    an[a_] = v_
            first = True
        if i_s == len(stops):
            break
        s = stops[i_s]
        b = s["tile"]
        d = D[p][b]
        t += d
        if not first and d > 1:
            hop += d - 1
        first = False
        if t < s["rel"]:
            t = s["rel"]
        for o in s["ops"]:
            c = o["c"][0]
            if c == "COLLECT_FERTILIZER":
                f += 1
            elif c == "FERTILIZE":
                if f <= 0:
                    bad += 1
                else:
                    f -= 1
            elif c == "FEED":
                w -= 1
            elif c == "PLACE" and len(o["c"]) > 1 and o["c"][1] in ANIMALS:
                an[o["c"][1]] -= 1
            if want_hours:
                hours.append((b, o["c"], t))
            t += 1
            if o["m"] and t - 1 > 23:
                late += t - 1 - 23
        p = b
    if t > 24:
        late += t - 24
    if want_hours:
        return t, late, hop, bad, hours
    return t, late, hop, bad


def _evening_wheat_surplus(S, day, shed, invs, farm, sells):
    """sd_evening_wheat_surplus (see the flag): appends / enlarges a SELL WHEAT order."""
    tiles = farm["tiles"]
    load = sum(int(v or 0) for v in shed.values()) + sum(int(v or 0) for inv in invs for k, v in (inv or {}).items() if k in PRODUCTS)
    inc_w = sum(int((inv or {}).get("WHEAT", 0) or 0) for inv in invs)
    TP = S.get("tier")
    if TP and TP.get("day") == day:
        for R_ in TP["routes"].values():
            for j_, it_ in enumerate(R_["items"][R_["k"]:]):
                if it_.get("kind") != "stop":
                    continue
                t_ = _tile(tiles, it_["tile"])
                for c_ in (it_["ops"][R_["sub"]:] if j_ == 0 else it_["ops"]):
                    if not (isinstance(c_, list) and c_):
                        continue
                    if c_[0] == "HARVEST" and isinstance(t_, dict):
                        u_ = int(t_.get("yield_units", 0) or 0)
                        load += u_
                        if t_.get("crop") == "WHEAT":
                            inc_w += u_
                    elif c_[0] == "COLLECT_FERTILIZER":
                        load += 1
                    elif c_[0] == "FERTILIZE":
                        load -= 1
    sold_now = sum(int(o[2]) for o in sells if o[0] == "SELL")
    excess = load - sold_now - (100 - int(CFG["sd_tier_dump_buffer"]))
    if excess <= 0:
        return
    n_anim = sum(1 for r in tiles for t in r if _animal(t))
    already_w = sum(int(o[2]) for o in sells if o[0] == "SELL" and o[1] == "WHEAT")
    shed_w = int(shed.get("WHEAT", 0) or 0) - already_w
    surplus = shed_w + inc_w - int(round(float(CFG["sd_ews_keep"]) * n_anim * int(CFG["wheat_days"])))
    n = min(excess, surplus, shed_w)
    if n <= 0:
        return
    for o in sells:
        if o[0] == "SELL" and o[1] == "WHEAT":
            o[2] = int(o[2]) + int(n)
            break
    else:
        sells.append(["SELL", "WHEAT", int(n)])
    S["log"]["evening_wheat_surplus_sold"] += int(n)


def _tier_collect_make_room(segs, rest, collects, tiles, day, st):
    """sd_collect_make_room (see the flag)."""
    n_anim = sum(1 for r in tiles for t in r if _animal(t))
    loads = [_tier_load(sg, sg["stops"], tiles, day) for sg in segs]
    home_w = sum(int(l.get("WHEAT", 0)) for l in loads)
    res_w = max(0, n_anim * int(CFG["wheat_days"]) - home_w) if CFG["sd_wheat_net"] else n_anim * int(CFG["wheat_days"])
    budget = 100 - res_w - int(CFG["sd_tier_dump_buffer"]) - sum(sum(v for v in l.values() if v > 0) for l in loads)
    cand = {}
    for bd in rest:
        for o in bd["ops"]:
            if o["c"][0] == "COLLECT_FERTILIZER":
                cand[bd["tile"]] = (bd, o)
    for t_, o in collects.items():
        cand.setdefault(t_, (None, o))
    added = removed = 0
    for tile, (bd, co) in sorted(cand.items(), key=lambda kv: -float(kv[1][1]["v"])):
        if budget <= 0:
            break
        best = None
        for k, sg in enumerate(segs):
            j = next((jj for jj, x in enumerate(sg["stops"]) if x["tile"] == tile and not x.get("turn")), None)
            if j is None:
                continue
            ev0 = _tier_eval(sg)
            trial = [dict(x, ops=list(x["ops"])) for x in sg["stops"]]
            trial[j]["ops"] = sorted(trial[j]["ops"] + [dict(co)], key=lambda o: o["rank"])
            lost = 0.0
            ok = True
            while True:
                ev = _tier_eval(sg, trial)
                if ev[1] <= ev0[1] and ev[3] <= ev0[3] and ev[0] <= max(24, ev0[0]):
                    break
                opts = sorted((float(o2["v"]), k2, id(o2)) for k2, x2 in enumerate(trial) if not x2.get("turn")
                              for o2 in x2["ops"] if not o2["m"] and o2["c"][0] not in ("COLLECT_FERTILIZER", "FERTILIZE", "DELIVER")
                              and not (k2 == j and o2["c"][0] == "COLLECT_FERTILIZER"))
                if not opts or opts[0][0] + lost >= float(co["v"]):
                    ok = False
                    break
                v2, k2, oid = opts[0]
                trial[k2]["ops"] = [o2 for o2 in trial[k2]["ops"] if id(o2) != oid]
                lost += v2
                trial = [x for x in trial if x["ops"]]
                j = next((jj for jj, x in enumerate(trial) if x["tile"] == tile and not x.get("turn")), j)
            if ok and (best is None or lost < best[0]):
                best = (lost, k, trial)
        if best is None:
            continue
        lost, k, trial = best
        segs[k]["stops"] = trial
        segs[k]["ver"] = segs[k].get("ver", 0) + 1
        added += 1
        removed += int(lost > 0)
        budget -= 1
        if bd is not None:
            bd["ops"] = [o for o in bd["ops"] if o is not co]
            bd["v"] = sum(float(o["v"]) for o in bd["ops"])
        collects.pop(tile, None)
    rest[:] = [bd for bd in rest if bd["ops"]]
    st["collect_make_room"] = st.get("collect_make_room", 0) + added
    st["collect_make_room_swaps"] = st.get("collect_make_room_swaps", 0) + removed
    return added


def _tier_fert_use(segs, rec, tiles, day, st):
    """sd_tier_fert_use (see the flag): spend each route's carried fertilizer on unplaced fertilizes of its own stops."""
    placed = {x["tile"] for sg in segs for x in sg["stops"] for o in x["ops"] if o["c"][0] == "FERTILIZE"}
    cand = {}
    for i, r_ in rec.items():
        fz = [o for o in r_["ops"] if o["c"][0] == "FERTILIZE" and not o["m"] and o["v"] > 0]
        t_ = _tile(tiles, i)
        if fz and i not in placed and _is_plant(t_) and int(t_.get("fertilized_until_day", -1)) < day:
            cand[i] = fz[0]
    n_ins = n_room = 0
    for sg in segs:
        if sg["kind"] == "central" or not sg["stops"]:
            continue
        changed = True
        while changed and cand:
            changed = False
            ev0 = _tier_eval(sg)
            f = int(sg.get("fpick", 0) or 0)
            for k, x in enumerate(sg["stops"]):
                for o in x["ops"]:
                    c = o["c"][0]
                    if c == "COLLECT_FERTILIZER":
                        f += 1
                    elif c == "FERTILIZE":
                        f -= 1
                if f <= 0 or x.get("dawn") or x["tile"] not in cand:
                    continue
                t_ = _tile(tiles, x["tile"])
                if not (t_.get("watered_today") or any(o["c"][0] == "WATER" for o in x["ops"])):
                    continue                       # the gain needs today's water on the tile
                o_new = dict(cand[x["tile"]])
                trial = [dict(s_) for s_ in sg["stops"]]
                trial[k]["ops"] = sorted(trial[k]["ops"] + [o_new], key=lambda o: o["rank"])
                ev = _tier_eval(sg, trial)
                if ev[3] > ev0[3]:
                    continue
                if ev[1] > ev0[1] or ev[0] > max(24, ev0[0]):
                    ok = False                     # make room: the cheapest optional op worth less, elsewhere
                    opts = sorted((float(o2["v"]), k2, j2) for k2, s2 in enumerate(trial) if k2 != k and not s2.get("turn")
                                  for j2, o2 in enumerate(s2["ops"])
                                  if not o2["m"] and o2["c"][0] not in ("FERTILIZE", "COLLECT_FERTILIZER", "DELIVER")
                                  and float(o2["v"]) < float(o_new["v"]))
                    for v2, k2, j2 in opts[:8]:
                        t2 = [dict(s_) for s_ in trial]
                        t2[k2]["ops"] = [o3 for jj, o3 in enumerate(t2[k2]["ops"]) if jj != j2]
                        t2 = [s_ for s_ in t2 if s_["ops"]]
                        ev2 = _tier_eval(sg, t2)
                        if ev2[3] <= ev0[3] and ev2[1] <= ev0[1] and ev2[0] <= max(24, ev0[0]):
                            trial, ev, ok = t2, ev2, True
                            n_room += 1
                            break
                    if not ok:
                        continue
                sg["stops"] = trial
                sg["ver"] = sg.get("ver", 0) + 1
                del cand[x["tile"]]
                n_ins += 1
                changed = True
                break
    st["tier_fert_use"] = st.get("tier_fert_use", 0) + n_ins
    st["tier_fert_use_room"] = st.get("tier_fert_use_room", 0) + n_room
    return n_ins


def _tier_pensweep(segs, rec, anim, owner, st, rng):
    """sd_pen_sweep (see the flag). Returns (unplaced optional bundles, {pen: unplaced collect op})."""
    import math
    t_start = time.perf_counter()
    vmin = float(CFG["sd_pen_sweep_vmin"])
    idx = [k for k, sg in enumerate(segs) if sg["kind"] in ("out", "post")]
    for k in idx:
        segs[k]["stops"] = []
        segs[k]["lo"] = 0
    units = {}
    for i, r_ in rec.items():
        ops = [dict(o) for o in r_["ops"] if o["m"] or float(o["v"]) >= vmin
               or (o["c"][0] == "COLLECT_FERTILIZER" and float(o["v"]) > 0)]   # a pen's collect: the routes' fertilizer
        if ops:
            units[i] = {"tile": i, "ops": sorted(ops, key=lambda o: o["rank"]), "rel": r_.get("rel", 0),
                        "mand": any(o["m"] for o in ops)}
    if not idx or not units:
        return [], {}

    def uval(ops):
        return sum(float(o["v"]) for o in ops if not o["m"])

    def rscore(sg, stops):
        if not stops:
            return 0.0, (sg["t0"], 0, 0, 0)
        ev = _tier_eval(sg, stops)
        v = sum(uval(x["ops"]) for x in stops) + 3000.0 * sum(1 for x in stops for o in x["ops"] if o["m"])
        return v - 1000.0 * (ev[1] + ev[3]) - 0.01 * ev[0], ev

    def fits(sg, stops):
        if not stops:
            return True
        ev = _tier_eval(sg, stops)
        return ev[1] == 0 and ev[3] == 0 and ev[0] <= 24

    def trim(sg, stops, pool):
        """drop optional ops (lowest value first; a FERTILIZE without supply first) until the route fits"""
        stops = [dict(x, ops=list(x["ops"])) for x in stops]
        while stops and not fits(sg, stops):
            ev = _tier_eval(sg, stops)
            cand = []
            for j, x in enumerate(stops):
                for o in x["ops"]:
                    if not o["m"]:
                        pri = -1e9 if (ev[3] > 0 and o["c"][0] == "FERTILIZE") else float(o["v"])
                        cand.append((pri, j, id(o)))
            if not cand:
                mj = [j for j, x in enumerate(stops)]
                j = mj[-1]                         # a mandatory unit that cannot fit: back to the pool
                pool.append(stops.pop(j))
                continue
            _, j, oid = min(cand)
            o = next(o for o in stops[j]["ops"] if id(o) == oid)
            stops[j]["ops"].remove(o)
            pool.append({"tile": stops[j]["tile"], "ops": [o], "rel": stops[j]["rel"], "mand": False})
            if not stops[j]["ops"]:
                stops.pop(j)
        return stops

    D = _TIER_D
    keys = list(units)
    wk = {i: len(units[i]["ops"]) + 1.0 for i in keys}
    ang = {i: math.atan2(i // 10 - 4.5, i % 10 - 4.5) for i in keys}
    order = sorted(keys, key=lambda i: ang[i])
    hours = {k: max(1.0, 24.0 - float(segs[k]["t0"])) for k in idx}
    best = None
    for off in range(int(CFG["sd_tier_offsets"])):
        rot = order[(off * len(order)) // (2 * int(CFG["sd_tier_offsets"])):] + order[:(off * len(order)) // (2 * int(CFG["sd_tier_offsets"]))]
        tot = sum(wk[i] for i in rot)
        H = sum(hours.values())
        arcs, cur, acc, kk = [], [], 0.0, 0
        caps = [tot * hours[k] / H for k in idx]
        for i in rot:
            cur.append(i)
            acc += wk[i]
            if acc >= caps[min(kk, len(caps) - 1)] and kk < len(idx) - 1:
                arcs.append(cur)
                cur, acc = [], 0.0
                kk += 1
        arcs.append(cur)
        while len(arcs) < len(idx):
            arcs.append([])
        # hands to arcs: nearest entry (greedy on the pair distances)
        pairs = []
        for a, arc in enumerate(arcs):
            for k in idx:
                dmin = min((D[segs[k]["p0"]][i] for i in arc), default=0)
                pairs.append((dmin + 0.2 * float(segs[k]["t0"]), a, k))
        pairs.sort()
        ua, uk, assign = set(), set(), {}
        for _, a, k in pairs:
            if a in ua or k in uk:
                continue
            assign[k] = arcs[a]
            ua.add(a)
            uk.add(k)
        routes, pool = {}, []
        for k in idx:
            arc = list(assign.get(k, []))
            pos, seq = segs[k]["p0"], []
            while arc:
                pens_ = [i for i in arc if i in anim]
                src_ = pens_ if pens_ else arc         # pens first (their collects supply the crops' fertilizes)
                nx = min(src_, key=lambda i: (D[pos][i], -wk[i], i))
                arc.remove(nx)
                seq.append({"tile": nx, "ops": [dict(o) for o in units[nx]["ops"]], "rel": units[nx]["rel"],
                            "mand": units[nx]["mand"]})
                pos = nx
            routes[k] = trim(segs[k], seq, pool)
        sc = sum(rscore(segs[k], routes[k])[0] for k in idx) - 5000.0 * sum(1 for x in pool if x["mand"])
        if best is None or sc > best[0]:
            best = (sc, routes, pool)
    _, routes, pool = best

    def ins_best(x, allow_room):
        """cheapest feasible insertion of unit x (merged into a stop on the same tile when the route has one)"""
        bb = None
        for k in idx:
            R = routes[k]
            base = rscore(segs[k], R)[0]
            same = next((j for j, y in enumerate(R) if y["tile"] == x["tile"]), None)
            cands = []
            if same is not None:
                R2 = [dict(y, ops=list(y["ops"])) for y in R]
                R2[same]["ops"] = sorted(R2[same]["ops"] + list(x["ops"]), key=lambda o: o["rank"])
                cands.append(R2)
            else:
                for j in range(len(R) + 1):
                    cands.append(R[:j] + [dict(x, ops=list(x["ops"]))] + R[j:])
            for R2 in cands:
                if fits(segs[k], R2):
                    gain = rscore(segs[k], R2)[0] - base
                    if bb is None or gain > bb[0]:
                        bb = (gain, k, R2, [])
                elif allow_room:
                    extra = []
                    R3 = trim(segs[k], R2, extra)
                    if any(y["mand"] for y in extra) or not any(y["tile"] == x["tile"] for y in R3):
                        continue
                    gain = rscore(segs[k], R3)[0] - base
                    if bb is None or gain > bb[0]:
                        bb = (gain, k, R3, extra)
        return bb

    # leftover mandatory units first (room made by dropping optional ops), then optional ones
    pool.sort(key=lambda x: (not x["mand"], -uval(x["ops"])))
    left = []
    for x in pool:
        bb = ins_best(x, x["mand"])
        if bb is None or (not x["mand"] and bb[0] <= 0):
            left.append(x)
            continue
        routes[bb[1]] = bb[2]
        left.extend(bb[3])
    # local search
    n_it = int(CFG["sd_pen_sweep_iters"])
    acc_ = 0
    for it in range(n_it):
        mv = rng.random()
        ks = [k for k in idx if routes[k]]
        if not ks:
            break
        if mv < 0.45:                              # relocate one visit to another route
            a = rng.choice(ks)
            j = rng.randrange(len(routes[a]))
            x = routes[a][j]
            near = sorted(idx, key=lambda k: min([D[segs[k]["p0"]][x["tile"]]] + [D[y["tile"]][x["tile"]] for y in routes[k]]))[:4]
            b = rng.choice(near)
            if b == a:
                continue
            Ra = routes[a][:j] + routes[a][j + 1:]
            s0 = rscore(segs[a], routes[a])[0] + rscore(segs[b], routes[b])[0]
            bestb = None
            for q in range(len(routes[b]) + 1):
                Rb = routes[b][:q] + [x] + routes[b][q:]
                if not fits(segs[b], Rb):
                    continue
                s1 = rscore(segs[a], Ra)[0] + rscore(segs[b], Rb)[0]
                if bestb is None or s1 > bestb[0]:
                    bestb = (s1, Rb)
            if bestb and bestb[0] > s0 + 1e-6:
                routes[a], routes[b] = Ra, bestb[1]
                acc_ += 1
        elif mv < 0.65:                            # swap two visits between routes
            a, b = rng.choice(ks), rng.choice(ks)
            if a == b:
                continue
            i, j = rng.randrange(len(routes[a])), rng.randrange(len(routes[b]))
            Ra = routes[a][:i] + [routes[b][j]] + routes[a][i + 1:]
            Rb = routes[b][:j] + [routes[a][i]] + routes[b][j + 1:]
            if fits(segs[a], Ra) and fits(segs[b], Rb):
                s0 = rscore(segs[a], routes[a])[0] + rscore(segs[b], routes[b])[0]
                s1 = rscore(segs[a], Ra)[0] + rscore(segs[b], Rb)[0]
                if s1 > s0 + 1e-6:
                    routes[a], routes[b] = Ra, Rb
                    acc_ += 1
        elif mv < 0.85:                            # 2-opt inside a route
            a = rng.choice(ks)
            if len(routes[a]) < 3:
                continue
            i = rng.randrange(len(routes[a]) - 1)
            j = rng.randrange(i + 1, len(routes[a]))
            Ra = routes[a][:i] + routes[a][i:j + 1][::-1] + routes[a][j + 1:]
            if fits(segs[a], Ra) and rscore(segs[a], Ra)[0] > rscore(segs[a], routes[a])[0] + 1e-6:
                routes[a] = Ra
                acc_ += 1
        elif left:                                 # try a leftover optional unit again
            x = left.pop(rng.randrange(len(left)))
            bb = ins_best(x, False)
            if bb is not None and bb[0] > 0:
                routes[bb[1]] = bb[2]
                acc_ += 1
            else:
                left.append(x)
    # fertilize pairing: an unplaced FERTILIZE goes into the route that visits its tile; the fertilizer comes from a
    # collect moved into that route (from the pen's route, when that route keeps its own supply)
    lf = [x for x in left if any(o["c"][0] == "FERTILIZE" for o in x["ops"])]
    n_pair = 0
    for x in sorted(lf, key=lambda x: -uval(x["ops"])):
        fo = next(o for o in x["ops"] if o["c"][0] == "FERTILIZE")
        done_ = False
        for k in idx:
            R = routes[k]
            j = next((jj for jj, y in enumerate(R) if y["tile"] == x["tile"]), None)
            if j is None:
                continue
            R2 = [dict(y, ops=list(y["ops"])) for y in R]
            R2[j]["ops"] = sorted(R2[j]["ops"] + [fo], key=lambda o: o["rank"])
            if fits(segs[k], R2):
                routes[k] = R2
                done_ = True
                break
            base = rscore(segs[k], R)[0]
            pens_ = sorted((pp for pp in anim), key=lambda pp: min([D[segs[k]["p0"]][pp]] + [D[y["tile"]][pp] for y in R[:j + 1]]))[:4]
            for pp in pens_:
                src = None
                for q in idx:                      # the route holding pp's collect
                    for jj, y in enumerate(routes[q]):
                        co = next((o for o in y["ops"] if o["c"][0] == "COLLECT_FERTILIZER"), None)
                        if y["tile"] == pp and co is not None:
                            src = (q, jj, co)
                if src is None:
                    continue
                q, jj, co = src
                if q == k:
                    continue
                Rq = [dict(y, ops=[o for o in y["ops"] if o is not co]) for y in routes[q]]
                Rq = [y for y in Rq if y["ops"]]
                if not fits(segs[q], Rq):
                    continue
                for pos_ in range(j + 1):
                    R3 = [dict(y, ops=list(y["ops"])) for y in R2]
                    jm = next((a for a, y in enumerate(R3[:j + 1]) if y["tile"] == pp), None)
                    if jm is not None:
                        R3[jm]["ops"] = sorted(R3[jm]["ops"] + [co], key=lambda o: o["rank"])
                    else:
                        R3 = R3[:pos_] + [{"tile": pp, "ops": [co], "rel": 0, "mand": False}] + R3[pos_:]
                    if fits(segs[k], R3) and rscore(segs[k], R3)[0] + rscore(segs[q], Rq)[0] > base + rscore(segs[q], routes[q])[0]:
                        routes[k], routes[q] = R3, Rq
                        done_ = True
                        break
                    if jm is not None:
                        break
                if done_:
                    break
            if done_:
                break
        if done_:
            left.remove(x)
            n_pair += 1
    # low-value work into spare time (optional ops worth less than sd_pen_sweep_vmin, e.g. waters)
    n_low = 0
    for i, r_ in sorted(rec.items(), key=lambda kv: -max([float(o["v"]) for o in kv[1]["ops"] if not o["m"]] or [0.0])):
        low = [dict(o) for o in r_["ops"] if not o["m"] and 0.0 < float(o["v"]) < vmin and o["c"][0] != "FERTILIZE"]
        if not low:
            continue
        bb = ins_best({"tile": i, "ops": low, "rel": r_.get("rel", 0), "mand": False}, False)
        if bb is not None and bb[0] > 0:
            routes[bb[1]] = bb[2]
            n_low += 1
    for k in idx:                                  # merge consecutive visits of one tile
        mg = []
        for x in routes[k]:
            if mg and mg[-1]["tile"] == x["tile"]:
                mg[-1] = dict(mg[-1], ops=mg[-1]["ops"] + x["ops"])
            else:
                mg.append(x)
        routes[k] = mg
    placed_f = 0
    for k in idx:
        segs[k]["stops"] = [{"tile": x["tile"], "ops": sorted(x["ops"], key=lambda o: o["rank"]), "rel": x["rel"]} for x in routes[k]]
        segs[k]["ver"] = segs[k].get("ver", 0) + 1
        for x in routes[k]:
            if x["tile"] not in anim:
                owner[x["tile"]] = k
            placed_f += sum(1 for o in x["ops"] if o["c"][0] == "FERTILIZE")
    mand_left = [x["tile"] for x in left if x["mand"]]
    rest, collects = [], {}
    for x in left:
        opt = [o for o in x["ops"] if not o["m"]]
        for o in opt:
            if o["c"][0] == "COLLECT_FERTILIZER":
                collects[x["tile"]] = o
        if opt:
            rest.append({"tile": x["tile"], "ops": opt, "v": uval(opt)})
    st["_pensweep_day"] = {"units": len(units), "mand_left": mand_left, "opt_left": len(rest), "fert": placed_f,
                           "pair": n_pair, "low": n_low,
                           "moves": acc_, "ms": round((time.perf_counter() - t_start) * 1000.0, 1)}
    st["pensweep_mand_left"] = st.get("pensweep_mand_left", 0) + len(mand_left)
    return rest, collects


_MANUAL_PLANS = {}


def _tier_manual_apply(S, segs, rec, day, st):
    """sd_manual_plan (see the flag): replace the segments' stops by the hand routes of this world / day."""
    path = CFG["sd_manual_plan"]
    if path not in _MANUAL_PLANS:
        import json as _json
        try:
            _MANUAL_PLANS[path] = _json.load(open(path, encoding="utf-8"))
        except Exception:
            _MANUAL_PLANS[path] = {}
    plan = (_MANUAL_PLANS[path].get(str(_TGT_EP)) or {}).get(str(day))
    if not plan:
        return
    S["_manual_today"] = day
    by_u = {int(R["u"]): R for R in plan["routes"]}
    used = {}
    n_ops = n_new = 0
    for sg in segs:
        R = by_u.get(int(sg["u"]))
        if R is None:
            continue
        seq, stops = [], []
        for x, y, ops in R["stops"]:
            tile = int(y) * 10 + int(x)
            od = []
            for op in ops:
                if op == "PICKUP":
                    if od:
                        stp = {"tile": tile, "ops": od, "rel": 0}
                        seq.append(stp)
                        stops.append(stp)
                        od = []
                    seq.append({"pick_item": "WHEAT", "tile": tile})
                    continue
                if op == "DROP":
                    od.append(_tier_op(["DROP"], True, 0.0, 2))
                    continue
                cand = [o for o in (rec.get(tile) or {}).get("ops", []) if o["c"][0] == op and id(o) not in used.get(tile, set())]
                if cand:
                    used.setdefault(tile, set()).add(id(cand[0]))
                    od.append(dict(cand[0]))
                else:
                    od.append(_tier_op([op], False, 1.0, 3))
                    n_new += 1
                n_ops += 1
            if od:
                stp = {"tile": tile, "ops": od, "rel": 0}
                seq.append(stp)
                stops.append(stp)
        sg["stops"] = stops
        sg["manual_seq"] = seq
        sg["fpick"] = int(R.get("fpick", 0) or 0)
        sg["ver"] = sg.get("ver", 0) + 1
    st["_manual_day"] = {"routes": len(by_u), "ops": n_ops, "not_in_catalogue": n_new}


def _tier_fmand_need(stops, fp0):
    """sd_wheat_fert_mand: extra fertilizer a route must pick up at its start so that every MANDATORY fertilize has one in
    hand (collects on the way count; optional fertilizes keep their own supply rules)."""
    f, need = fp0, 0
    for s in stops:
        for o in s["ops"]:
            c = o["c"][0]
            if c == "COLLECT_FERTILIZER":
                f += 1
            elif c == "FERTILIZE":
                if f > 0:
                    f -= 1
                elif o["m"]:
                    need += 1
    return need


def _tier_cost(seg, ev=None, stops=None):
    stops = seg["stops"] if stops is None else stops
    if not stops:
        return 0.0
    t, late, hop, bad = ev if ev is not None else _tier_eval(seg, stops)
    c = _TIER_BIG * (late + bad) + seg["wu"] * (t - seg["t0"]) + float(CFG["sd_tier_hop_w"]) * hop
    cw = float(CFG["sd_tier_coll_w"])
    if cw and seg.get("fneed"):
        need = sum(1 for s in stops if s["tile"] in seg["fneed"])
        if need:
            p = seg["p0"] if seg["p0"] in _TIER_SHED_I else _tier_near_shed(seg["p0"])
            b1 = next((x["tile"] for x in stops if not x.get("dawn")), stops[0]["tile"])
            D = _TIER_D
            on = sum(1 for a in seg["anim"] if D[p][a] + D[a][b1] == D[p][b1])
            c -= cw * min(on, need)
    return c


def _tier_route(seg, ids, stops_all):
    """nearest-neighbour order of the stop ids from the segment's start, then or-opt; returns the ordered ids."""
    D = _TIER_D
    p = seg["p0"]
    rest = list(ids)
    out = []
    while rest:
        j = min(rest, key=lambda i: (D[p][stops_all[i]["tile"]], stops_all[i]["tile"]))
        out.append(j)
        rest.remove(j)
        p = stops_all[j]["tile"]
    return _tier_oropt(seg, out, stops_all)


def _tier_seg_cost(seg, ids, stops_all):
    return _tier_cost(seg, None, [stops_all[i] for i in ids])


def _tier_oropt(seg, ids, stops_all):
    best = _tier_seg_cost(seg, ids, stops_all)
    improved = True
    while improved and len(ids) > 1:
        improved = False
        for i in range(len(ids)):
            x = ids[i]
            r = ids[:i] + ids[i + 1:]
            for k in range(len(r) + 1):
                if k == i:
                    continue
                nr = r[:k] + [x] + r[k:]
                c = _tier_seg_cost(seg, nr, stops_all)
                if c < best - 1e-9:
                    best, ids, improved = c, nr, True
                    break
            if improved:
                break
    return ids


def _tier_search(segs, stops_all, budget, rng):
    """sectors: stop ids per segment. Sweep start (angular arcs of balanced work over the outbound segments, every
    rotation of arcs to segments), then simulated annealing over relocate / swap / intra moves within the budget."""
    D = _TIER_D
    n = len(stops_all)
    outs = [k for k, s in enumerate(segs) if s["kind"] == "out"]
    t_end = time.perf_counter() + budget
    best = None
    if outs and n:
        order = sorted(range(n), key=lambda i: _TIER_ANG[stops_all[i]["tile"]])
        work = [len(stops_all[i]["ops"]) + 1.5 for i in order]
        tot = sum(work)
        K = len(outs)
        segs_by_ang = sorted(outs, key=lambda k: (_TIER_ANG[segs[k]["p0"]], k))
        for off in range(0, n, max(1, n // int(CFG["sd_tier_offsets"]))):
            seq = order[off:] + order[:off]
            wq = work[off:] + work[:off]
            arcs, cur, acc = [], [], 0.0
            for i, w_ in zip(seq, wq):
                cur.append(i)
                acc += w_
                if acc >= tot * (len(arcs) + 1) / K - 1e-9 and len(arcs) < K - 1:
                    arcs.append(cur)
                    cur = []
            arcs.append(cur)
            while len(arcs) < K:
                arcs.append([])
            rbest = None
            for rot in range(K):                   # proxy: each start's distance to the nearest stop of its arc
                px = 0
                for a_i, arc in enumerate(arcs):
                    if arc:
                        p_ = segs[segs_by_ang[(a_i + rot) % K]]["p0"]
                        px += min(D[p_][stops_all[i]["tile"]] for i in arc)
                if rbest is None or px < rbest[0]:
                    rbest = (px, rot)
            rots = range(K) if CFG["sd_tier_rot_all"] else [rbest[1]]   # rot_all: every rotation routed (no proxy)
            for rot in rots:
                asg = [[] for _ in segs]
                for a_i, arc in enumerate(arcs):
                    asg[segs_by_ang[(a_i + rot) % K]] = arc
                asg = [_tier_route(segs[k], asg[k], stops_all) if asg[k] else [] for k in range(len(segs))]
                c = sum(_tier_seg_cost(segs[k], asg[k], stops_all) for k in range(len(segs)))
                if best is None or c < best[0]:
                    best = (c, asg)
    if best is None:
        return [[] for _ in segs], 0.0
    cur = [list(r) for r in best[1]]
    cc = [_tier_seg_cost(segs[k], cur[k], stops_all) for k in range(len(segs))]
    tot_c = sum(cc)
    best_c, best_r = tot_c, [list(r) for r in cur]
    where = {}
    for k, r in enumerate(cur):
        for i in r:
            where[i] = k
    T0, T1 = float(CFG["sd_tier_t0"]), 0.05
    it = 0
    t_start = time.perf_counter()
    while True:
        it += 1
        if it > int(CFG["sd_tier_iters"]) or (it % 64 == 0 and time.perf_counter() > t_end):
            break
        frac = min(1.0, it / max(1.0, float(CFG["sd_tier_iters"])))
        T = T0 * (1.0 - frac) + T1
        mv = rng.random()
        s = rng.randrange(n)
        a = where[s]
        if mv < 0.55:                              # relocate s to the best position of a route near it
            near = [k for k in range(len(segs)) if k != a and (not cur[k] and segs[k]["kind"] != "post" or any(
                D[stops_all[s]["tile"]][stops_all[i]["tile"]] <= 3 for i in cur[k]))]
            if not near:
                continue
            b = rng.choice(near)
            ra = [i for i in cur[a] if i != s]
            ca = _tier_seg_cost(segs[a], ra, stops_all)
            bb = None
            for k in range(len(cur[b]) + 1):
                rb = cur[b][:k] + [s] + cur[b][k:]
                c = _tier_seg_cost(segs[b], rb, stops_all)
                if bb is None or c < bb[0]:
                    bb = (c, rb)
            delta = ca + bb[0] - cc[a] - cc[b]
            if delta < 0 or rng.random() < _tier_math.exp(-delta / T):
                cur[a], cur[b] = ra, bb[1]
                cc[a], cc[b] = ca, bb[0]
                where[s] = b
                tot_c += delta
        elif mv < 0.8:                             # swap s with a stop of another route near it
            cand = [i for i in range(n) if where[i] != a and D[stops_all[s]["tile"]][stops_all[i]["tile"]] <= 4]
            if not cand:
                continue
            s2 = rng.choice(cand)
            b = where[s2]
            if CFG["sd_tier_swap_oropt"]:          # full: both routes re-optimized after the swap
                ra = _tier_oropt(segs[a], [s2 if i == s else i for i in cur[a]], stops_all)
                rb = _tier_oropt(segs[b], [s if i == s2 else i for i in cur[b]], stops_all)
                ca, cb = _tier_seg_cost(segs[a], ra, stops_all), _tier_seg_cost(segs[b], rb, stops_all)
            else:
                ra0 = [i for i in cur[a] if i != s]
                rb0 = [i for i in cur[b] if i != s2]
                ca, ra = min(((_tier_seg_cost(segs[a], ra0[:k] + [s2] + ra0[k:], stops_all), ra0[:k] + [s2] + ra0[k:])
                              for k in range(len(ra0) + 1)), key=lambda x: x[0])
                cb, rb = min(((_tier_seg_cost(segs[b], rb0[:k] + [s] + rb0[k:], stops_all), rb0[:k] + [s] + rb0[k:])
                              for k in range(len(rb0) + 1)), key=lambda x: x[0])
            delta = ca + cb - cc[a] - cc[b]
            if delta < 0 or rng.random() < _tier_math.exp(-delta / T):
                cur[a], cur[b] = ra, rb
                cc[a], cc[b] = ca, cb
                where[s], where[s2] = b, a
                tot_c += delta
        else:                                      # intra: move s within its route
            r = [i for i in cur[a] if i != s]
            bb = None
            for k in range(len(r) + 1):
                nr = r[:k] + [s] + r[k:]
                c = _tier_seg_cost(segs[a], nr, stops_all)
                if bb is None or c < bb[0]:
                    bb = (c, nr)
            delta = bb[0] - cc[a]
            if delta < -1e-9:
                cur[a], cc[a] = bb[1], bb[0]
                tot_c += delta
        if tot_c < best_c - 1e-9:
            best_c, best_r = tot_c, [list(r) for r in cur]
    return best_r, best_c


def _tier_merge(stops, tile, ops, rel=0, k=None):
    """stops with ops merged into the stop on tile (in rank order), else inserted as a new stop at position k."""
    out = [dict(s) for s in stops]
    for i, s in enumerate(out):
        if s["tile"] == tile and not s.get("dawn"):
            s["ops"] = sorted(s["ops"] + [dict(o) for o in ops], key=lambda o: o["rank"])
            return out, i
    k = len(out) if k is None else k
    out.insert(k, {"tile": tile, "ops": sorted([dict(o) for o in ops], key=lambda o: o["rank"]), "rel": rel})
    return out, k


def _tier_best_ins(seg, bundle, collects, lo=0):
    """best insertion of an extras bundle {"tile", "ops", "v"} into seg (merged into its stop on the tile, else a new
    stop at the best position >= lo); a FERTILIZE the route has no fertilizer for is paired with a COLLECT from the
    free collects (tile -> op) placed before it. Returns (score, delta hours, new stops, collect tile or None) or None."""
    if bundle.get("dawn"):
        return _tier_dawn_ins(seg, bundle)
    if bundle.get("coll_c") and int(CFG["sd_tier_collect_c_max"]) and _TIER_CC["n"] >= int(CFG["sd_tier_collect_c_max"]):
        return None
    has = any(s["tile"] == bundle["tile"] for s in seg["stops"])
    if bundle.get("inplace") and not has:
        return None                                # sd_tier_collect_c 1: only into a stop the route already has on the pen
    ev0 = _tier_eval(seg)
    c0 = _tier_cost(seg, ev0)
    opts = []
    if has:
        opts.append(_tier_merge(seg["stops"], bundle["tile"], bundle["ops"]))
    else:
        for k in range(lo, len(seg["stops"]) + 1):
            opts.append(_tier_merge(seg["stops"], bundle["tile"], bundle["ops"], 0, k))
    best = None
    need_f = any(o["c"][0] == "FERTILIZE" for o in bundle["ops"])
    top_ = int(CFG["sd_tier_pair_top"])
    evs_ = [(st_, kpos, _tier_eval(seg, st_)) for st_, kpos in opts]
    pair_ok = None
    if top_ and need_f:                            # pairing only for the best positions (by time, supply ignored)
        pair_ok = set(id(x[0]) for x in sorted(evs_, key=lambda x: (x[2][1], x[2][0]))[:top_])
    shed_ok_ = (need_f and CFG["sd_tier_fert_shed"] and _FSHED["left"] > 0 and seg["kind"] in ("out", "post")
                and seg["p0"] in _TIER_SHED_I and not any(x.get("dawn") for x in seg["stops"]))
    for pass_s_ in ((False, True) if shed_ok_ else (False,)):
      if pass_s_ and best is not None:
          break                                    # sd_tier_fert_shed: the shed only when no collect pairing fits (adds, not replaces)
      for st_, kpos, ev in evs_:
        cands = [(st_, ev, None, 0.0)] if not pass_s_ else []
        if pass_s_ and ev[3] > ev0[3]:             # one more fertilizer picked up at the route start
            cands.append((st_, _tier_eval(dict(seg, fpick=int(seg.get("fpick", 0) or 0) + 1), st_), "SHED", 0.0))
        if not pass_s_ and need_f and ev[3] > ev0[3] and collects and (pair_ok is None or id(st_) in pair_ok):
            D = _TIER_D
            b = bundle["tile"]
            p0_ = seg["p0"]
            na_ = 2 if top_ else 4
            near_ = sorted(collects, key=lambda a: D[a][b])[:na_]
            near_ += [a for a in sorted(collects, key=lambda a: D[a][p0_])[:na_] if a not in near_]   # on the way out
            for a in near_:
                for k2 in range(lo, kpos + 1):
                    st2, _ = _tier_merge(st_, a, [collects[a]], 0, k2)
                    cands.append((st2, _tier_eval(seg, st2), a, float(collects[a]["v"])))
        cap = int(CFG["sd_tier_coll_cap"])
        n0c = sum(1 for s_ in seg["stops"] for o in s_["ops"] if o["c"][0] == "COLLECT_FERTILIZER") if cap else 0
        for st2, ev2, a, va in cands:
            if ev2[1] > ev0[1] or ev2[3] > ev0[3]:
                continue
            if cap:
                n2c = sum(1 for s_ in st2 for o in s_["ops"] if o["c"][0] == "COLLECT_FERTILIZER")
                if n2c > n0c and n2c > cap:
                    if n2c > cap + 1:
                        continue
                    if ev2[0] - ev0[0] > len(bundle["ops"]) + (1 if a is not None else 0):
                        continue                   # the extra collect only on the way (no extra walking)
            c = _tier_cost(seg, ev2, st2)
            dh = max(0.25, c - c0)
            sc = (bundle["v"] + (0.0 if CFG["sd_tier_pair_own"] else va)) / dh
            if best is None or sc > best[0]:
                best = (sc, c - c0, st2, a)
    return best


def _tier_dawn_ins(seg, bundle):
    """sd_tier_dawn 2: a dawn leg bundle {"tile" (pen), "ops" (its HARVEST / PLACE_HARVEST), "v", "prod", "rel"} put at the
    start of an outbound route that starts on a shed tile by hour sd_tier_dawn_t0max and has no dawn leg yet: walk to the
    pen, harvest, DELIVER on the shed tile nearest to it (a pen on a shed tile: PLACE_HARVEST in place) by hour
    sd_tier_dawn_by, then the route's pickups and stops. Returns (score, delta cost, new stops, None) or None."""
    D = _TIER_D
    if seg["kind"] != "out" or seg["t0"] > int(CFG["sd_tier_dawn_t0max"]) or seg["p0"] not in _TIER_SHED_I:
        return None
    if any(x.get("dawn") for x in seg["stops"]):
        return None
    idx, p0 = bundle["tile"], seg["p0"]
    ops = sorted([dict(o) for o in bundle["ops"]], key=lambda o: o["rank"])
    legs = [{"tile": idx, "ops": ops, "rel": bundle.get("rel", 0), "dawn": True}]
    if idx in _TIER_SHED_I:
        if not any(o["c"][0] == "PLACE_HARVEST" for o in ops):
            ops.append(_tier_op(["PLACE_HARVEST", bundle["prod"]], False, 0.0, 4))
    else:
        sh = min(_TIER_SHED_I, key=lambda q: (D[idx][q], D[q][p0], q))
        legs.append({"tile": sh, "ops": [_tier_op(["DELIVER"], True, 0.0, 2)], "rel": 0, "turn": True, "dawn": True})
    trial = legs + list(seg["stops"])
    ev0 = _tier_eval(seg)
    ev = _tier_eval(seg, trial, want_hours=True)
    if ev[1] > ev0[1] or ev[3] > ev0[3]:
        return None
    nd = sum(len(x["ops"]) for x in legs)
    if ev[4][nd - 1][2] > int(CFG["sd_tier_dawn_by"]):
        return None
    c0 = _tier_cost(seg, ev0)
    c = _tier_cost(seg, ev[:4], trial)
    return (bundle["v"] / max(0.25, c - c0), c - c0, trial, None)


def _tier_fill(segs, sidx, bundles, collects, owner, rate, st, tag, steal=False):
    """greedy: repeatedly the best (value / added hours) feasible insertion of a bundle into one of the segments sidx."""
    n_ins = 0
    cache = {}
    while bundles:
        best = None
        nn_ = int(CFG["sd_tier_fill_near"])
        for bi, bd in enumerate(bundles):
            ks_ = sidx
            if nn_ and len(sidx) > nn_ and not steal:   # only the hands nearest to the extra (speed)
                D_ = _TIER_D
                b_ = bd["tile"]
                ks_ = sorted(sidx, key=lambda k: min([D_[segs[k]["p0"]][b_]] + [D_[x["tile"]][b_] for x in segs[k]["stops"]]))[:nn_]
            for k in ks_:
                if segs[k]["kind"] == "central":
                    continue                       # the central hand's day is fixed
                o_ = owner.get(bd["tile"])
                if o_ is not None and o_ != k and not bd.get("shared") and not steal:
                    continue                           # (steal: sd_tier_rebalance moves a busy sector's tile to a free hand)
                key = (id(bd), bd.get("bv", 0), k, segs[k]["ver"])
                r = cache.get(key)
                if r is None:
                    r = _tier_best_ins(segs[k], bd, collects if segs[k]["kind"] != "prio_melon" else {},
                                       segs[k].get("lo", 0))
                    cache[key] = r if r is not None else False
                if not r:
                    continue
                if (r[3] == "SHED" and _FSHED["left"] <= 0) or (r[3] is not None and r[3] != "SHED" and r[3] not in collects):   # recompute
                    r = _tier_best_ins(segs[k], bd, collects if segs[k]["kind"] != "prio_melon" else {},
                                       segs[k].get("lo", 0))
                    cache[key] = r if r is not None else False
                    if not r:
                        continue
                if r[0] < rate:
                    continue
                if best is None or r[0] > best[0]:
                    best = (r[0], bi, k, r)
        if best is None:
            break
        _, bi, k, r = best
        bd = bundles.pop(bi)
        segs[k]["stops"] = r[2]
        segs[k]["ver"] += 1
        if bd.get("dawn"):                         # sd_tier_dawn 2: later insertions go after the dawn leg
            segs[k]["lo"] = sum(1 for x in r[2] if x.get("dawn"))
            st["tier_dawn_legs"] = st.get("tier_dawn_legs", 0) + 1
        if not bd.get("shared"):
            owner[bd["tile"]] = k
        if any(o["c"][0] == "COLLECT_FERTILIZER" for o in bd["ops"]):
            collects.pop(bd["tile"], None)             # cached pairings on it are rechecked when picked
        if bd.get("coll_c"):
            _TIER_CC["n"] += 1
            st["tier_collect_c"] = st.get("tier_collect_c", 0) + 1
        if r[3] == "SHED":                         # sd_tier_fert_shed: the fertilizer comes from the shed at the route start
            segs[k]["fpick"] = int(segs[k].get("fpick", 0) or 0) + 1
            _FSHED["left"] -= 1
            st["tier_fert_shed"] = st.get("tier_fert_shed", 0) + 1
        elif r[3] is not None:
            collects.pop(r[3], None)
            for bd2 in list(bundles):                  # that animal's fertilizer is taken
                if bd2["tile"] == r[3]:
                    bd2["ops"] = [o for o in bd2["ops"] if o["c"][0] != "COLLECT_FERTILIZER"]
                    bd2["v"] = sum(o["v"] for o in bd2["ops"])
                    bd2["bv"] = bd2.get("bv", 0) + 1
                    if not bd2["ops"]:
                        bundles.remove(bd2)
        n_ins += 1
    st["tier_fill_" + tag] = st.get("tier_fill_" + tag, 0) + n_ins
    return n_ins


def _tier_harvest_day(idx, t, day):
    """planned harvest day of a one-time crop: the leader plan's next planting on the tile, else its last window day."""
    c = CROPS[t["crop"]]
    pd = int(t.get("planted_day", day))
    hd = pd + c["maxday"]
    try:
        for dd in range(day, min(hd + 1, _T.n)):
            if idx in _T.plant[dd]:
                return dd
    except Exception:
        pass
    return hd


def _tier_fert_gain(idx, t, day):
    """units one FERTILIZE on `day` (before the day's water) adds for plant t, watered on every day it pays, compared with
    no fertilize in its 3-day cover; 0 unless today itself pays (first useful day: tomorrow's supply covers the rest)."""
    c = CROPS.get(t.get("crop"))
    if not c:
        return 0
    pd = int(t.get("planted_day", day))
    fu = int(t.get("fertilized_until_day", -1) or -1)
    if fu >= day:
        return 0
    last = day + 2
    if not c["ongoing"]:
        w0, w1 = (c["maxday"] + 1) // 2, c["maxday"]
        hd = _tier_harvest_day(idx, t, day)
        if not (w0 <= day - pd <= w1) or day > hd:
            return 0

        def units(fert):
            y = int(t.get("yield_units", 0) or 0)
            for dd in range(day, hd + 1):
                if w0 <= dd - pd <= w1:
                    f = (fert and dd <= last) or fu >= dd
                    y = min(c["max"], y + (2 if f else 1))
            return y
        return units(True) - units(False)
    first, iv, mx = c["first"], max(1, c["interval"]), c["max"]

    def prod(dd):                                  # a production at the end of day dd (the engine's next_day = dd + 1)
        ds = dd + 1 - pd - first
        return ds >= 0 and ds % iv == 0 and ds // iv + 1 <= mx
    if not prod(day):
        return 0
    return sum(1 for dd in range(day, last + 1) if prod(dd) and dd > fu)


def _tier_anim_value(rec, tiles, day, last_day, prices, st, replace=False):
    """sd_path_planner (KB107: sheep care 236 -> 170, wool -70 units, when care was valued ~20-40 against a collect's 80):
    CARE and optional FEED valued by the engine rule - a fed + cared day banks one unit for the next production (paid
    only when fed that night), a fed production night cashes the bank. CARE = product price when a production night
    is still ahead; FEED = bank x price on a production day + half a unit when a production is still ahead. The larger
    of this and the op's old value."""
    n = 0
    for idx, r_ in rec.items():
        t = _tile(tiles, idx)
        if not _animal(t):
            continue
        a = ANIMALS[t["animal"]]
        pr = float(prices.get(a["product"], 0) or 0)
        pd = int(t.get("placed_day", day))

        def prod(k):
            ds = k + 1 - pd - a["first"]
            return ds >= 0 and ds % a["interval"] == 0
        later = any(prod(k) for k in range(day + 1, last_day))
        today = prod(day)
        bank = int(t.get("pending_care_bonus", 0) or 0)
        for o in r_["ops"]:
            c = o["c"][0]
            if c == "CARE" and o["m"] and replace:
                continue
            if c == "CARE" and later:
                v = pr
            elif c == "CARE" and replace:
                v = 0.0                            # sd_anim_value_exact: no production ahead, the care is wasted
            elif c == "FEED" and not o["m"]:
                v = (bank * pr if today else 0.0) + (0.5 * pr if later else 0.0)
            else:
                continue
            if v > o["v"] or (replace and v != o["v"]):
                o["v"] = v
                n += 1
    st["tier_anim_value"] = st.get("tier_anim_value", 0) + n


def _tier_fert_exact(rec, tiles, day, prices, st):
    """sd_tier_fert_exact: every plant's FERTILIZE valued by _tier_fert_gain x its product's price - the charged fertilizer
    price; added where it pays and is missing (with the day's WATER it depends on), removed where it does not."""
    fp = float(prices.get("FERTILIZER", 0) or 0)
    ff = CFG.get("sd_fert_frac")
    charge = (float(ff) if ff is not None else 1.0) * fp
    added = removed = 0
    for idx in range(100):
        t = _tile(tiles, idx)
        if not _is_plant(t):
            continue
        r_ = rec.get(idx)
        cm = [o["c"][0] for o in r_["ops"]] if r_ else []
        if "HARVEST" in cm and not CROPS.get(t.get("crop"), {}).get("ongoing", True):
            continue                               # harvested today (sd_tier_fert_skip_harv)
        if any(c_ in ("PLANT", "DIG", "BUILD_COOP", "BUILD_PASTURE") for c_ in cm):
            continue
        g = _tier_fert_gain(idx, t, day)
        price = float(prices.get(t["crop"], 0) or 0)
        v = g * price - charge
        if g > 0 and CFG["sd_fert_bonus"] and t["crop"] in (CFG["sd_fert_bonus_crops"] or ()):
            v += float(CFG["sd_fert_bonus"])      # sd_fert_bonus
        if v <= 0:
            if r_ and "FERTILIZE" in cm:
                r_["ops"] = [o for o in r_["ops"] if o["c"][0] != "FERTILIZE"]
                removed += 1
            continue
        if r_ is None:
            r_ = rec.setdefault(idx, {"ops": [], "rel": 0})
        if "FERTILIZE" in cm:
            for o in r_["ops"]:
                if o["c"][0] == "FERTILIZE":
                    o["v"] = v
        else:
            r_["ops"].append(_tier_op(["FERTILIZE"], False, v, 3))
            added += 1
        if "WATER" not in cm:                      # the gain needs today's water
            r_["ops"].append(_tier_op(["WATER"], False, 0.01, 3))
        r_["ops"].sort(key=lambda o: o["rank"])
    st["tier_fert_exact_added"] = st.get("tier_fert_exact_added", 0) + added
    st["tier_fert_exact_removed"] = st.get("tier_fert_exact_removed", 0) + removed


def _tier_relief(segs, pool, collects, owner, rate, st):
    """user: a hand with a small patch takes over work so a busier hand can do what it had no time for. For each unplanned
    extra (most valuable first): move one stop of a route near it to a hand with spare time, then insert the extra into
    that route; kept when every mandatory op stays on time and the extra's value covers the added hours."""
    D = _TIER_D
    moves = 0
    slack = int(CFG["sd_tier_relief_slack"])
    for _pass in range(int(CFG["sd_tier_relief_passes"])):
        changed = False
        for bd in sorted(list(pool), key=lambda b: -b["v"]):
            if bd not in pool or not bd["ops"] or bd["v"] < float(CFG["sd_tier_relief_minv"]):
                continue
            o_ = owner.get(bd["tile"])
            if o_ is not None and not bd.get("shared"):
                cand_r = [o_]
            else:
                cand_r = [k for k, s_ in enumerate(segs) if s_["stops"] and s_["kind"] != "central"
                          and min(D[x["tile"]][bd["tile"]] for x in s_["stops"]) <= 2]
            best = None
            for r in cand_r:
                R = segs[r]
                evR = _tier_eval(R)
                cR = _tier_cost(R, evR)
                for i, x in enumerate(R["stops"]):
                    if x.get("place") or x.get("dawn") or x.get("svc") or x["tile"] == bd["tile"]:
                        continue
                    R2 = dict(R, stops=R["stops"][:i] + R["stops"][i + 1:])
                    ev2 = _tier_eval(R2)
                    if ev2[3] > evR[3]:
                        continue                   # the stop supplied a later fertilize
                    ins = _tier_best_ins(R2, bd, collects, R.get("lo", 0))
                    if not ins:
                        continue
                    evR3 = _tier_eval(R, ins[2])
                    if evR3[1] > evR[1] or evR3[3] > evR[3]:
                        continue
                    cR3 = _tier_cost(R, evR3, ins[2])
                    for k, S in enumerate(segs):
                        if k == r or S["kind"] == "central":
                            continue
                        evS = _tier_eval(S)
                        if evS[0] > 24 - slack:
                            continue
                        cS = _tier_cost(S, evS)
                        for pos in range(S.get("lo", 0), len(S["stops"]) + 1):
                            stS, _ = _tier_merge(S["stops"], x["tile"], x["ops"], x.get("rel", 0), pos)
                            evS2 = _tier_eval(S, stS)
                            if evS2[1] > evS[1] or evS2[3] > evS[3]:
                                continue
                            cS2 = _tier_cost(S, evS2, stS)
                            sc = bd["v"] / max(0.25, (cR3 - cR) + (cS2 - cS))
                            if sc >= rate and (best is None or sc > best[0]):
                                best = (sc, r, ins[2], k, stS, x["tile"], ins[3])
            if best is None:
                continue
            _, r, stR, k, stS, xt, a = best
            segs[r]["stops"], segs[k]["stops"] = stR, stS
            segs[r]["ver"] += 1
            segs[k]["ver"] += 1
            if owner.get(xt) == r:
                owner[xt] = k
            if not bd.get("shared"):
                owner[bd["tile"]] = r
            gone = ([a] if a is not None else []) + (
                [bd["tile"]] if any(o["c"][0] == "COLLECT_FERTILIZER" for o in bd["ops"]) else [])
            for a_ in gone:
                collects.pop(a_, None)
                for bd2 in list(pool):
                    if bd2 is not bd and bd2["tile"] == a_:
                        bd2["ops"] = [o for o in bd2["ops"] if o["c"][0] != "COLLECT_FERTILIZER"]
                        bd2["v"] = sum(o["v"] for o in bd2["ops"])
                        if not bd2["ops"]:
                            pool.remove(bd2)
            pool.remove(bd)
            moves += 1
            changed = True
        if not changed:
            break
    st["tier_relief"] = st.get("tier_relief", 0) + moves
    return moves


def _tier_load(seg, stops, tiles, day):
    """units a segment still carries at midnight: harvests (today's held yield, + the watering before it inside a one-time
    crop's window), collected fertilizer not used."""
    load = Counter()
    for x in stops:
        if x.get("turn"):                          # sd_tier_turnaround: the goods carried so far go to the shed here
            load = Counter({"FERTILIZER": load["FERTILIZER"]})
            continue
        t = _tile(tiles, x["tile"])
        watered = fert = False
        for o in x["ops"]:
            c = o["c"][0]
            if c == "WATER":
                watered = True
            elif c == "FERTILIZE":
                fert = True
                load["FERTILIZER"] -= 1
            elif c == "COLLECT_FERTILIZER":
                load["FERTILIZER"] += 1
            elif c == "PLACE_HARVEST" and CFG["sd_tier_turnaround"]:
                load[o["c"][1]] = 0                # sd_tier_access_drop: that product is already in the shed
            elif c == "HARVEST" and isinstance(t, dict):
                if _is_plant(t):
                    cr = CROPS.get(t.get("crop"))
                    u = int(t.get("yield_units", 0) or 0)
                    if cr and not cr["ongoing"] and watered and not t.get("watered_today"):
                        a = day - int(t.get("planted_day", day))
                        if (cr["maxday"] + 1) // 2 <= a <= cr["maxday"]:
                            f2 = fert or int(t.get("fertilized_until_day", -1) or -1) >= day
                            u = min(cr["max"], u + (2 if f2 else 1))
                    if cr and u > 0:
                        load[t["crop"]] += u
                elif _animal(t):
                    u = int(t.get("yield_units", 0) or 0)
                    if u > 0:
                        load[ANIMALS[_animal(t)]["product"]] += u
    return Counter({k: v for k, v in load.items() if v > 0})


def _tier_copy_rec(rec):
    """a copy of rec whose op dicts are the SAME objects (a trial run removes them only from the copy's lists)."""
    return {i: dict(r_, ops=list(r_["ops"])) for i, r_ in rec.items()}


def _tier_prio_run(S, rec, tiles, day, fu, st, mode):
    """a melon-mode run for strawberries (mode "straw"): tiles holding >= sd_tier_prio_straw_min (or due), with their
    WATER in the same visit, best units x price per added hour while the drop at the shed stays by the deadline."""
    D = _TIER_D
    u, p0, t0 = fu
    pi = p0[1] * 10 + p0[0]
    prices = S.get("_tier_prices") or {}
    smin = int(CFG["sd_tier_prio_straw_min"])
    by = int(CFG["sd_tier_prio_straw_by"])
    cand = {}
    for idx, r_ in rec.items():
        t_ = _tile(tiles, idx)
        if not _is_plant(t_) or t_.get("crop") != "STRAWBERRY":
            continue
        hv = [o for o in r_["ops"] if o["c"][0] in ("HARVEST", "PLACE_HARVEST")]
        if not any(o["c"][0] == "HARVEST" for o in hv):
            continue
        y_ = int(t_.get("yield_units", 0) or 0)
        due = any(o["m"] for o in hv if o["c"][0] == "HARVEST")
        if not (due or y_ >= smin):
            continue
        cand[idx] = {"ops": hv + [o for o in r_["ops"] if o["c"][0] == "WATER"], "dv": y_ * float(prices.get("STRAWBERRY", 0) or 0)}
    if not cand:
        return None
    seg = {"p0": pi, "t0": t0, "stops": []}

    def with_drop(sts):
        sh = min(_TIER_SHED_I, key=lambda q: D[sts[-1]["tile"]][q])
        return sts + [{"tile": sh, "ops": [_tier_op(["DELIVER"], True, 0.0, 1)], "rel": 0, "turn": True}]

    stops, taken, value = [], [], 0.0
    t_cur = t0
    while cand:
        best = None
        for idx, c in cand.items():
            stp = {"tile": idx, "ops": sorted([dict(o, m=True, tier=1) for o in c["ops"]], key=lambda o: o["rank"]),
                   "rel": rec[idx]["rel"]}
            ev = _tier_eval(seg, with_drop(stops + [stp]), want_hours=True)
            if ev[1] > 0 or max(h for (b_, c_, h) in ev[4] if c_[0] == "DELIVER") > by:
                continue
            sc = c["dv"] / max(1, ev[0] - t_cur)
            if best is None or sc > best[0]:
                best = (sc, idx, stp, ev)
        if best is None:
            break
        _, idx, stp, ev = best
        stops.append(stp)
        taken.append(idx)
        t_cur = ev[0]
        c = cand.pop(idx)
        value += c["dv"]
        ids = set(id(o) for o in c["ops"])
        rec[idx]["ops"] = [o for o in rec[idx]["ops"] if id(o) not in ids]
        if not rec[idx]["ops"]:
            rec.pop(idx)
    if not taken:
        return None
    final = with_drop(stops)
    ev = _tier_eval(seg, final, want_hours=True)
    return {"stops": final, "p0": pi, "t0": t0, "_value": value,
            "drop": max(h for (b_, c_, h) in ev[4] if c_[0] == "DELIVER"),
            "hh": {b_: h for (b_, c_, h) in ev[4] if c_[0] == "HARVEST"}}


def _tier_srun(S, rec, tiles, day, fu, st):
    """sd_tier_srun: one hand's strawberry run (see the flag), built like a melon run: {"stops" (strawberry tiles, then a
    DELIVER at the nearest shed tile), "p0", "t0", "drop", "hh", "_units"}; the taken ops leave rec."""
    D = _TIER_D
    u, p0, t0 = fu
    pi = p0[1] * 10 + p0[0]
    by = int(CFG["sd_tier_srun_by"])
    smin = int(CFG["sd_tier_srun_min"])
    rad = CFG["sd_tier_srun_radius"]
    cand = {}
    for idx, r_ in rec.items():
        t_ = _tile(tiles, idx)
        if not _is_plant(t_) or t_.get("crop") != "STRAWBERRY":
            continue
        if rad is not None and min(D[idx][q] for q in _TIER_SHED_I) > int(rad):
            continue
        hv = [o for o in r_["ops"] if o["c"][0] in ("HARVEST", "PLACE_HARVEST")]
        if not any(o["c"][0] == "HARVEST" for o in hv):
            continue
        y_ = int(t_.get("yield_units", 0) or 0)
        due = any(o["m"] for o in hv if o["c"][0] == "HARVEST")
        if not (due or y_ >= smin) or y_ <= 0:
            continue
        wt = [o for o in r_["ops"] if o["c"][0] == "WATER"]
        cand[idx] = {"ops": hv + wt, "units": y_, "mx": sum(1 for o in wt if o["m"])}
    if not cand:
        return None
    seg = {"p0": pi, "t0": t0, "stops": []}

    def stop_of(idx):
        return {"tile": idx, "ops": sorted([dict(o, m=True, tier=1) for o in cand[idx]["ops"]], key=lambda o: o["rank"]),
                "rel": rec[idx]["rel"]}

    def with_drop(sts):
        sh = min(_TIER_SHED_I, key=lambda q: D[sts[-1]["tile"]][q])
        return sts + [{"tile": sh, "ops": [_tier_op(["DELIVER"], True, 0.0, 1)], "rel": 0, "turn": True}]

    def ok(sts):                                   # (feasible, drop hour, end)
        if not sts:
            return True, t0, t0
        ev = _tier_eval(seg, with_drop(sts), want_hours=True)
        dh = max(h for (b_, c_, h) in ev[4] if c_[0] == "DELIVER")
        return (ev[1] == 0 and ev[3] == 0 and dh <= by), dh, ev[0]

    route, taken = [], set()
    end0 = t0
    while True:                                    # (2) most units: cheapest insertion by units per added hour
        best = None
        for idx, c in cand.items():
            if idx in taken:
                continue
            stp = stop_of(idx)
            for k in range(len(route) + 1):
                trial = route[:k] + [stp] + route[k:]
                f_, dh, end = ok(trial)
                if not f_:
                    continue
                sc = (c["units"] / max(1, end - end0), c["mx"], -dh)
                if best is None or sc > best[0]:
                    best = (sc, idx, trial, end)
        if best is None:
            break
        _, idx, route, end0 = best
        taken.add(idx)
    if not route:
        return None
    for _ in range(int(CFG["sd_tier_srun_passes"])):
        moved = False
        _, dh0, _ = ok(route)
        for i_ in range(len(route)):               # (3) earliest drop for the same set: move one stop to its best place
            rest = route[:i_] + route[i_ + 1:]
            for k in range(len(rest) + 1):
                trial = rest[:k] + [route[i_]] + rest[k:]
                f_, dh, _ = ok(trial)
                if f_ and dh < dh0:
                    route, dh0, moved = trial, dh, True
                    break
            if moved:
                break
        units0 = sum(cand[x["tile"]]["units"] for x in route)
        for i_ in range(len(route)):               # (2) more units: swap a taken tile for a richer untaken one
            for idx, c in cand.items():
                if idx in taken or c["units"] <= cand[route[i_]["tile"]]["units"]:
                    continue
                trial = route[:i_] + [stop_of(idx)] + route[i_ + 1:]
                f_, dh, _ = ok(trial)
                if f_:
                    taken.discard(route[i_]["tile"])
                    taken.add(idx)
                    route, moved = trial, True
                    break
        if not moved:
            break
    for x in route:                                # the taken ops leave rec
        ids = set(id(o) for o in cand[x["tile"]]["ops"])
        rec[x["tile"]]["ops"] = [o for o in rec[x["tile"]]["ops"] if id(o) not in ids]
        if not rec[x["tile"]]["ops"]:
            rec.pop(x["tile"])
    final = with_drop(route)
    ev = _tier_eval(seg, final, want_hours=True)
    units = sum(cand[x["tile"]]["units"] for x in route)
    st["_srun_day"] = {"u": u, "tiles": [x["tile"] for x in route], "units": units,
                       "drop": max(h for (b_, c_, h) in ev[4] if c_[0] == "DELIVER"),
                       "cand": len(cand), "cand_units": sum(c["units"] for c in cand.values())}
    return {"stops": final, "p0": pi, "t0": t0, "_units": units, "_value": units,
            "drop": st["_srun_day"]["drop"], "hh": {b_: h for (b_, c_, h) in ev[4] if c_[0] == "HARVEST"}}


def _fert_useful(t, day):
    """a FERTILIZE on this plant still buys a unit: the engine covers day..day+2; an ongoing crop needs a production
    night in that window, within its max_yield productions and not already covered (user: a strawberry at the end of its
    life is not fertilized - it is replanted)"""
    if not _is_plant(t):
        return False
    cd = CROPS.get(t.get("crop"))
    if not cd or not cd["ongoing"]:
        return True
    pd = int(t.get("planted_day", day))
    itv = max(1, int(cd.get("interval", 1) or 1))
    for d in (day, day + 1, day + 2):
        k = d + 1 - pd - cd["first"]
        if k >= 0 and k % itv == 0 and k // itv + 1 <= cd["max"] and d > int(t.get("fertilized_until_day", -1) or -1):
            return True
    return False


def _tier_sclu(S, rec, tiles, day, units, busy, st):
    """sd_tier_sclu: strawberry cluster trips (see the flag). Returns {u: melon-style run}; the taken ops leave rec."""
    import itertools as _it
    D = _TIER_D
    R = int(CFG["sd_tier_sclu_r"])
    by = int(CFG["sd_tier_sclu_by"])
    umin = int(CFG["sd_tier_sclu_min"])
    xy = lambda i: (i % 10, i // 10)
    dsh = lambda i: min(D[i][q] for q in _TIER_SHED_I)
    cand = {}
    ready_ = 0
    for idx, r_ in rec.items():
        t_ = _tile(tiles, idx)
        if not _is_plant(t_) or t_.get("crop") != "STRAWBERRY":
            continue
        if not any(o["c"][0] == "HARVEST" for o in r_["ops"]):
            continue
        y_ = int(t_.get("yield_units", 0) or 0)
        ready_ += max(0, y_)
        if y_ > 0 and (CFG["sd_tier_sclu_dmax"] is None or dsh(idx) <= int(CFG["sd_tier_sclu_dmax"])):
            cand[idx] = y_
    fert_ = int(CFG["sd_tier_sclu_fert"]) or int(CFG["sd_tier_sclu_outfert"])
    favail = max(0, int((S.get("_shed_h0") or {}).get("FERTILIZER", 0) or 0) - int(CFG["sd_tier_sclu_fert_keep"])) if fert_ else 0
    if CFG["sd_tier_sclu_need_min"] is not None:  # only when we would fall behind DSM's strawberry schedule today
        cum_n_ = _books_cum(S)
        if cum_n_ is not None:
            need_ = (int((cum_n_.get(day * 24 + 23) or {}).get("STRAWBERRY", 0)) - int(S["sold"]["STRAWBERRY"])
                     - int((S.get("_shed_h0") or {}).get("STRAWBERRY", 0) or 0))
            if need_ < int(CFG["sd_tier_sclu_need_min"]):
                st["_sclu_day"] = {"clusters": [], "cand": len(cand), "need": need_, "gate": "need"}
                return {}
    if ready_ < int(CFG["sd_tier_sclu_day_min"]):
        st["_sclu_day"] = {"clusters": [], "cand": len(cand), "cand_units": sum(cand.values()), "ready": ready_, "gate": "closed"}
        return {}
    dawn_u = set()
    if int(CFG["sd_tier_dawn"]) == 3:
        dawn_u = {int(tr[0]) for tr in (_dawn_shape(day, tiles).get(str(day)) or [])}
    free = [(u, p0, t0) for u, p0, t0 in units if u != 0 and u not in busy and t0 <= 1 and u not in dawn_u]
    EXTRA = ("WATER", "CARE", "FEED", "COLLECT_FERTILIZER", "HARVEST", "PLACE_HARVEST")
    out = {}
    rec_ = st["_sclu_day"] = {"clusters": [], "cand": len(cand), "cand_units": sum(cand.values()), "ready": ready_, "favail": favail}
    while cand and free and len(out) < int(CFG["sd_tier_sclu_max"]):
        best = None
        for c0 in cand:                             # a cluster grown from each seed: nearest first, all pairs within R
            mem = [c0]
            for t in sorted(cand, key=lambda q: (D[c0][q], q)):
                if t != c0 and all(D[t][m] <= R for m in mem):
                    mem.append(t)
            uu = sum(cand[m] for m in mem)
            key = (uu, -len(mem), -min(D[m][q] for m in mem for q in _TIER_SHED_I))
            if best is None or key > best[0]:
                best = (key, mem)
        if best is None or best[0][0] < umin:
            break
        mem = best[1]
        if len(mem) > 6:                            # keep the richest 6 (brute-force order below)
            mem = sorted(mem, key=lambda q: -cand[q])[:6]
        fu = min(free, key=lambda f: min(D[f[1][1] * 10 + f[1][0]][m] for m in mem))
        u, p0, t0 = fu
        pi = p0[1] * 10 + p0[0]
        order = None
        for perm in _it.permutations(mem):          # the direct path: shed -> cluster -> nearest shed tile
            c_ = D[pi][perm[0]] + sum(D[perm[k]][perm[k + 1]] for k in range(len(perm) - 1)) + min(D[perm[-1]][q] for q in _TIER_SHED_I)
            if order is None or c_ < order[0]:
                order = (c_, perm)
        perm = list(order[1])
        sh = min(_TIER_SHED_I, key=lambda q: D[perm[-1]][q])
        seg = {"p0": pi, "t0": t0, "stops": []}
        taken = {}                                  # tile -> [ops]

        def stops_of(seq):
            out_ = []
            prods_ = {"STRAWBERRY"}
            for b in seq:
                ops = sorted([dict(o, m=True, tier=1) for o in taken[b]], key=lambda o: o["rank"])
                out_.append({"tile": b, "ops": ops, "rel": rec[b]["rel"] if b in rec else 0})
                if any(o["c"][0] == "HARVEST" for o in ops):
                    tb_ = _tile(tiles, b)
                    prods_.add(ANIMALS[tb_["animal"]]["product"] if _animal(tb_) else tb_.get("crop"))
            dl_ = [_tier_op(["DELIVER", p_], True, 0.0, 1) for p_ in sorted(prods_, key=lambda q: q != "STRAWBERRY")]
            return out_ + [{"tile": sh, "ops": dl_, "rel": 0, "turn": True, "sell_now": True}]

        def nfert(seq):
            return sum(1 for b in seq for o in taken.get(b, []) if o["c"][0] == "FERTILIZE")

        def feasible(seq):
            seg["fpick"] = nfert(seq)
            ev = _tier_eval(seg, stops_of(seq), want_hours=True)
            dh = max(h for (b_, c_, h) in ev[4] if c_[0] == "DELIVER")
            return ev[1] == 0 and ev[3] == 0 and dh <= by, ev, dh

        for b in perm:
            taken[b] = [o for o in rec[b]["ops"] if o["c"][0] in ("HARVEST", "PLACE_HARVEST", "WATER")]
            fz_ = [o for o in rec[b]["ops"] if o["c"][0] == "FERTILIZE"] if _fert_useful(_tile(tiles, b), day) else []
            if int(CFG["sd_tier_sclu_fert"]) and fz_ and nfert(perm) + len(fz_) <= favail:
                taken[b] += fz_                     # the cluster's own fertilize, fertilizer from the shed
        seq = list(perm)
        f_, ev, dh = feasible(seq)
        if not f_:
            for b in perm:
                taken.pop(b, None)
            cand = {k: v for k, v in cand.items() if k not in mem}
            continue
        sector_ = CFG["sd_tier_sclu_sector_d"] is not None and max(dsh(b) for b in perm) <= int(CFG["sd_tier_sclu_sector_d"])
        if int(CFG["sd_tier_sclu_extra"]):         # extra work on the legs: tiles inside each leg's box, monotone order
            dmax_ = by if sector_ else dh + int(CFG["sd_tier_sclu_extra_h"])   # a short trip: the path is this hand's sector
            dh0_ = dh
            legs = [pi] + perm + [sh]
            new_seq = []
            for k in range(len(legs) - 1):
                a, b = legs[k], legs[k + 1]
                rest = perm[k:]
                (ax, ay), (bx, by_) = xy(a), xy(b)
                sx = (bx > ax) - (bx < ax)
                sy = (by_ > ay) - (by_ < ay)
                of_ = k == 0 and int(CFG["sd_tier_sclu_outfert"])   # branch 2: other hands' fertilize on the outbound
                EX_ = EXTRA + (("FERTILIZE",) if of_ else ())
                box = [t for t in rec if t not in taken and t not in (a, b)
                       and min(ax, bx) <= t % 10 <= max(ax, bx) and min(ay, by_) <= t // 10 <= max(ay, by_)
                       and any(o["c"][0] in EX_ for o in rec[t]["ops"])]
                box.sort(key=lambda t: (D[a][t], -sum(o["v"] + (1000 if o["m"] else 0) for o in rec[t]["ops"] if o["c"][0] in EXTRA)))
                last = a
                for t in box:
                    (px, py), (qx, qy) = xy(last), xy(t)
                    if (qx - px) * sx < 0 or (qy - py) * sy < 0:
                        continue
                    taken[t] = [o for o in rec[t]["ops"] if o["c"][0] in EXTRA]
                    fz_ = [o for o in rec[t]["ops"] if o["c"][0] == "FERTILIZE"] if (of_ and _fert_useful(_tile(tiles, t), day)) else []
                    if fz_ and nfert(new_seq + rest) + nfert([x for x in seq if x not in new_seq and x not in rest]) + len(fz_) <= favail:
                        taken[t] += fz_
                    else:
                        fz_ = []
                    if not taken[t]:
                        taken.pop(t)
                        continue
                    cap_ = min(by, max(dmax_, dh0_ + int(CFG["sd_tier_sclu_extra_h"]) + int(CFG["sd_tier_sclu_outfert_h"]))) if fz_ else dmax_
                    ok_, _, dh_ = feasible(new_seq + [t] + rest)
                    if ok_ and dh_ <= cap_:
                        new_seq.append(t)
                        last = t
                    else:
                        taken.pop(t)
                if k < len(perm):
                    new_seq.append(perm[k])
            seq = new_seq
        f_, ev, dh = feasible(seq)
        if not f_:                                  # safety: the cluster alone
            for b in list(taken):
                if b not in perm:
                    taken.pop(b)
            seq = list(perm)
            f_, ev, dh = feasible(seq)
            if not f_:
                break
        for b, ops in taken.items():                # the taken ops leave rec
            ids = set(id(o) for o in ops)
            rec[b]["ops"] = [o for o in rec[b]["ops"] if id(o) not in ids]
            if not rec[b]["ops"]:
                rec.pop(b)
        final = stops_of(seq)
        fp_ = nfert(seq)
        favail -= fp_
        out[u] = {"stops": final, "p0": pi, "t0": t0, "drop": dh, "_value": sum(cand[m] for m in mem), "fpick": fp_,
                  "hh": {b_: h for (b_, c_, h) in ev[4] if c_[0] == "HARVEST"}}
        rec_["clusters"].append({"u": u, "tiles": list(perm), "units": sum(cand[m] for m in mem), "extra": [b for b in seq if b not in perm],
                                 "drop": dh, "fpick": fp_, "sector": bool(sector_),
                                 "fert_cluster": sum(1 for b in perm for o in taken.get(b, []) if o["c"][0] == "FERTILIZE"),
                                 "fert_out": sum(1 for b in seq if b not in perm for o in taken.get(b, []) if o["c"][0] == "FERTILIZE")})
        free = [f for f in free if f[0] != u]
        cand = {k: v for k, v in cand.items() if k not in mem and k in rec and any(o["c"][0] == "HARVEST" for o in rec[k]["ops"])}
    return out


def _tier_prio_ani(S, rec, tiles, day, fu, st):
    """sd_tier_prio_ani: the farmer's morning run of important animal harvests (see the flag), built like a melon run:
    {"stops" (pens, then a DELIVER stop at the shed), "p0", "t0", "drop", "hh"}; the taken ops leave rec."""
    D = _TIER_D
    u, p0, t0 = fu
    pi = p0[1] * 10 + p0[0]
    prices = S.get("_tier_prices") or {}
    mins = CFG["sd_tier_prio_ani_min"] or {}
    by = int(CFG["sd_tier_prio_ani_by"])
    cand = {}
    for idx, r_ in rec.items():
        t_ = _tile(tiles, idx)
        if not _animal(t_) or t_["animal"] not in mins:
            continue
        hv = [o for o in r_["ops"] if o["c"][0] in ("HARVEST", "PLACE_HARVEST")]
        if not any(o["c"][0] == "HARVEST" for o in hv):
            continue
        y_ = int(t_.get("yield_units", 0) or 0)
        due = any(o["m"] for o in hv if o["c"][0] == "HARVEST")
        if not (due or y_ >= int(mins[t_["animal"]])):
            continue
        prod_ = ANIMALS[t_["animal"]]["product"]
        cand[idx] = {"ops": hv + [o for o in r_["ops"] if o["c"][0] in ("FEED", "CARE")],
                     "dv": y_ * float(prices.get(prod_, 0) or 0), "prod": prod_}
    if not cand:
        return None
    seg = {"p0": pi, "t0": t0, "stops": []}

    def with_drop(sts, prods):
        sh = min(_TIER_SHED_I, key=lambda q: D[sts[-1]["tile"]][q])
        return sts + [{"tile": sh, "ops": [_tier_op(["DELIVER"], True, 0.0, 1) for _ in sorted(prods)], "rel": 0, "turn": True}]

    def drop_hour(ev):
        return max(h for (b_, c_, h) in ev[4] if c_[0] == "DELIVER")

    stops, prods, taken = [], set(), []
    t_cur = t0
    while cand:
        best = None
        for idx, c in cand.items():
            pen = {"tile": idx, "ops": sorted([dict(o, m=True, tier=1) for o in c["ops"]], key=lambda o: o["rank"]),
                   "rel": rec[idx]["rel"]}
            full = with_drop(stops + [pen], prods | {c["prod"]})
            ev = _tier_eval(seg, full, want_hours=True)
            if ev[1] > 0 or drop_hour(ev) > by:
                continue
            sc = c["dv"] / max(1, ev[0] - t_cur)
            if best is None or sc > best[0]:
                best = (sc, idx, pen, ev)
        if best is None:
            break
        _, idx, pen, ev = best
        stops.append(pen)
        prods.add(cand[idx]["prod"])
        taken.append(idx)
        t_cur = ev[0]
        c = cand.pop(idx)
        ids = set(id(o) for o in c["ops"])
        rec[idx]["ops"] = [o for o in rec[idx]["ops"] if id(o) not in ids]
        if not rec[idx]["ops"]:
            rec.pop(idx)
    if not taken:
        return None
    final = with_drop(stops, prods)
    ev = _tier_eval(seg, final, want_hours=True)
    st["tier_prio_ani_runs"] = st.get("tier_prio_ani_runs", 0) + 1
    st["tier_prio_ani_pens"] = st.get("tier_prio_ani_pens", 0) + len(taken)
    return {"stops": final, "p0": pi, "t0": t0, "drop": drop_hour(ev),
            "hh": {b_: h for (b_, c_, h) in ev[4] if c_[0] == "HARVEST"}}


def _tier_dawn(S, rec, tiles, day, units, busy, st):
    """sd_tier_dawn: DSM's dawn round trips (see the flag). Pens by product value (units x price), each to the free
    early unit whose leg ends first (ties: nearer start, lower index), one leg per unit. Returns {u: leg} with leg =
    {"stops" (pen, then a DELIVER stop on the shed tile nearest the pen; a pen on a shed tile: HARVEST + PLACE_HARVEST),
    "p0", "t0", "end" (hour the unit is free at the shed), "tile" (that shed tile), "drop", "pen", "units", "prod"};
    the taken HARVEST / PLACE_HARVEST ops leave rec (the pen's FEED / CARE / COLLECT stay for the planner)."""
    D = _TIER_D
    prices = S.get("_tier_prices") or {}
    mins = CFG["sd_tier_dawn_min"] or {}
    rad = int(CFG["sd_tier_dawn_radius"])
    by = int(CFG["sd_tier_dawn_by"])
    t0max = int(CFG["sd_tier_dawn_t0max"])
    nmax = int(CFG["sd_tier_dawn_max"] or 0)
    pens = []
    for idx, r_ in rec.items():
        t_ = _tile(tiles, idx)
        if not _animal(t_) or t_["animal"] not in mins:
            continue
        y_ = int(t_.get("yield_units", 0) or 0)
        if y_ < int(mins[t_["animal"]]) or min(D[idx][q] for q in _TIER_SHED_I) > rad:
            continue
        hv = [o for o in r_["ops"] if o["c"][0] in ("HARVEST", "PLACE_HARVEST")]
        if not any(o["c"][0] == "HARVEST" for o in hv):
            continue
        prod_ = ANIMALS[t_["animal"]]["product"]
        pens.append((y_ * float(prices.get(prod_, 0) or 0), idx, hv, prod_, y_))
    free = [(u, p0, t0) for u, p0, t0 in units if t0 <= t0max and u not in busy]
    out = {}
    for val, idx, hv, prod_, y_ in sorted(pens, key=lambda x: (-x[0], x[1])):
        if nmax and len(out) >= nmax:
            break
        best = None
        for u, p0, t0 in free:
            if u in out:
                continue
            pi = p0[1] * 10 + p0[0]
            ops = sorted([dict(o, m=True, tier=1) for o in hv], key=lambda o: o["rank"])
            stops = [{"tile": idx, "ops": ops, "rel": rec[idx]["rel"]}]
            if idx in _TIER_SHED_I:
                if not any(o["c"][0] == "PLACE_HARVEST" for o in ops):
                    ops.append(_tier_op(["PLACE_HARVEST", prod_], True, 1.0, 1))
            else:
                sh = min(_TIER_SHED_I, key=lambda q: (D[idx][q], D[q][pi], q))
                stops.append({"tile": sh, "ops": [_tier_op(["DELIVER"], True, 0.0, 1)], "rel": 0, "turn": True})
            ev = _tier_eval({"p0": pi, "t0": t0, "stops": []}, stops, want_hours=True)
            drop = max(h for (b_, c_, h) in ev[4] if c_[0] in ("DELIVER", "PLACE_HARVEST"))
            if ev[1] > 0 or ev[3] > 0 or drop > by:
                continue
            key = (ev[0], D[pi][idx], u)
            if best is None or key < best[0]:
                best = (key, u, pi, t0, stops, ev, drop)
        if best is None:
            st["tier_dawn_nounit"] = st.get("tier_dawn_nounit", 0) + 1
            continue
        _, u, pi, t0, stops, ev, drop = best
        out[u] = {"stops": stops, "p0": pi, "t0": t0, "end": ev[0], "tile": stops[-1]["tile"], "drop": drop, "pen": idx,
                  "units": y_, "prod": prod_, "hours": [(b_, c_[0], h) for b_, c_, h in ev[4]]}
        ids = set(id(o) for o in hv)
        rec[idx]["ops"] = [o for o in rec[idx]["ops"] if id(o) not in ids]
        if not rec[idx]["ops"]:
            rec.pop(idx)
        out[u]["svc"] = _tier_dawn_svc(rec, [idx])
        st["tier_dawn_legs"] = st.get("tier_dawn_legs", 0) + 1
        st["tier_dawn_units"] = st.get("tier_dawn_units", 0) + y_
    return out


def _tier_dawn_svc(rec, pens):
    """sd_tier_dawn_service: the pen's non-mandatory FEED / CARE / COLLECT_FERTILIZER ops worth > 0 leave rec (the mandatory
    ones stay for the sector search); returned as service stops {"tile", "ops" (copies, mandatory), "orig" (the rec ops, put
    back when the service does not fit), "rel", "svc"} for the leg's unit."""
    out = []
    if not CFG["sd_tier_dawn_service"]:
        return out
    for ti in pens:
        r_ = rec.get(ti)
        if not r_:
            continue
        sv = [o for o in r_["ops"] if o["c"][0] in ("FEED", "CARE", "COLLECT_FERTILIZER") and not o["m"] and o["v"] > 0]
        if not sv:
            continue
        ids = set(id(o) for o in sv)
        r_["ops"] = [o for o in r_["ops"] if id(o) not in ids]
        if not r_["ops"]:
            rec.pop(ti)
        out.append({"tile": ti, "ops": sorted([dict(o, m=True, tier=2) for o in sv], key=lambda o: o["rank"]),
                    "orig": sv, "rel": r_["rel"], "svc": True})
    return out


def _tier_dawn_shape(S, rec, tiles, day, units, busy, st):
    """sd_tier_dawn 3: DSM's recorded early trips of this day (see sd_tier_dawn_shape), in its order, each to one of our
    free units acting from the same hour; returns {u: leg} in _tier_dawn's format (+ "dsm": the DSM trip); the taken
    HARVEST / PLACE_HARVEST ops leave rec."""
    D = _TIER_D
    trips = _dawn_shape(day, tiles).get(str(day)) or []
    out = {}
    for tr in trips:
        du, act_h, dstart, dtiles, ddrop = tr[0], int(tr[1]), int(tr[2]), tr[3], int(tr[4])
        st["tier_shape_dsm"] = st.get("tier_shape_dsm", 0) + 1
        take, prods = [], []
        for ti, what in dtiles:
            ti = int(ti)
            t_ = _tile(tiles, ti)
            r_ = rec.get(ti)
            if not (_animal(t_) and t_["animal"] == what and int(t_.get("yield_units", 0) or 0) > 0 and r_):
                continue
            hv = [o for o in r_["ops"] if o["c"][0] in ("HARVEST", "PLACE_HARVEST")]
            if not any(o["c"][0] == "HARVEST" for o in hv):
                continue
            take.append((ti, hv, int(t_.get("yield_units", 0) or 0)))
            prods.append(ANIMALS[what]["product"])
        if not take:
            st["tier_shape_nomatch"] = st.get("tier_shape_nomatch", 0) + 1
            continue
        cand = [(u, p0, t0) for u, p0, t0 in units if u not in busy and u not in out and t0 == act_h
                and (u == 0) == (du == 0)]
        if not cand:
            st["tier_shape_nounit"] = st.get("tier_shape_nounit", 0) + 1
            continue
        first = take[0][0]
        u, p0, t0 = min(cand, key=lambda c: (0 if c[1][1] * 10 + c[1][0] == dstart else 1,
                                             D[c[1][1] * 10 + c[1][0]][first], c[0]))
        pi = p0[1] * 10 + p0[0]
        stops = []
        for ti, hv, y_ in take:
            ops = sorted([dict(o, m=True, tier=1) for o in hv], key=lambda o: o["rank"])
            if not (len(take) == 1 and ti in _TIER_SHED_I):
                ops = [o for o in ops if o["c"][0] != "PLACE_HARVEST"]
            elif not any(o["c"][0] == "PLACE_HARVEST" for o in ops):
                ops.append(_tier_op(["PLACE_HARVEST", prods[0]], True, 1.0, 1))
            stops.append({"tile": ti, "ops": ops, "rel": rec[ti]["rel"]})
        if not (len(take) == 1 and take[0][0] in _TIER_SHED_I):
            sh = ddrop if ddrop in _TIER_SHED_I else min(_TIER_SHED_I, key=lambda q: (D[stops[-1]["tile"]][q], q))
            stops.append({"tile": sh, "ops": [_tier_op(["DELIVER"], True, 0.0, 1) for _ in sorted(set(prods))], "rel": 0,
                          "turn": True})
        ev = _tier_eval({"p0": pi, "t0": t0, "stops": []}, stops, want_hours=True)
        drop = max(h for (b_, c_, h) in ev[4] if c_[0] in ("DELIVER", "PLACE_HARVEST"))
        out[u] = {"stops": stops, "p0": pi, "t0": t0, "end": ev[0], "tile": stops[-1]["tile"], "drop": drop,
                  "pen": take[0][0], "units": sum(y for _, _, y in take), "prod": prods[0],
                  "hours": [(b_, c_[0], h) for b_, c_, h in ev[4]], "dsm": list(tr), "pens": [ti for ti, _, _ in take]}
        for ti, hv, _ in take:
            ids = set(id(o) for o in hv)
            rec[ti]["ops"] = [o for o in rec[ti]["ops"] if id(o) not in ids]
            if not rec[ti]["ops"]:
                rec.pop(ti)
        out[u]["svc"] = _tier_dawn_svc(rec, [ti for ti, _, _ in take])
        st["tier_dawn_legs"] = st.get("tier_dawn_legs", 0) + 1
        st["tier_dawn_units"] = st.get("tier_dawn_units", 0) + out[u]["units"]
    return out


def _tier_central(S, cseg, rec, tiles, day, st):
    """sd_tier_central_hand: build the farmer's whole day as the central hand (see the flag)."""
    D = _TIER_D
    rad = int(CFG["sd_tier_central_radius"])
    prices = S.get("_tier_prices") or {}
    last_day = int(S.get("_tier_last_day", 29))
    rate = float(CFG["sd_tier_rate"])
    cand = {}
    for idx, r_ in rec.items():
        t_ = _tile(tiles, idx)
        if not _animal(t_) or min(D[idx][q] for q in _TIER_SHED_I) > rad:
            continue
        a_ = ANIMALS[t_["animal"]]
        pd_ = int(t_.get("placed_day", day))
        prod_ = lambda n: (n + 1 - pd_ - a_["first"]) >= 0 and (n + 1 - pd_ - a_["first"]) % a_["interval"] == 0
        care_ok = any(prod_(n) for n in range(day + 1, last_day))
        pr_ = float(prices.get(a_["product"], 0) or 0)
        take = []
        val = 0.0
        for o in r_["ops"]:
            c_ = o["c"][0]
            if c_ == "FEED":
                take.append(o)
                if prod_(day):
                    val += int(t_.get("pending_care_bonus", 0) or 0) * pr_
            elif c_ == "CARE" and care_ok:
                take.append(o)
                val += pr_
            elif c_ in ("HARVEST", "PLACE_HARVEST") and (o["m"] or (
                    CFG["sd_tier_central_hmin"] and int(t_.get("yield_units", 0) or 0) >= int((CFG["sd_tier_central_hmin"] or {}).get(t_["animal"], 99)))):
                take.append(o)
        if not take:
            continue
        must = any(o["m"] for o in take)
        hv = any(o["c"][0] == "HARVEST" for o in take)
        units_ = int(t_.get("yield_units", 0) or 0) if hv else 0
        cand[idx] = {"ops": take, "v": val + (1e6 if must else 0.0), "hv": hv, "prod": a_["product"], "dv": units_ * pr_}
    stops, taken = [], []
    if str(CFG["sd_tier_central_mode"]) == "deliver":   # morning round: pens with product first, drop after each
        while True:
            ev0 = _tier_eval(cseg, stops) if stops else (cseg["t0"], 0, 0, 0)
            best = None
            for idx, c in cand.items():
                if not c["hv"] or c["dv"] <= 0:
                    continue
                add = [{"tile": idx, "ops": [dict(o, m=True, tier=2) for o in c["ops"]], "rel": rec[idx]["rel"]}]
                if idx not in _TIER_SHED_I:
                    sh = min(_TIER_SHED_I, key=lambda q: D[idx][q])
                    add.append({"tile": sh, "ops": [_tier_op(["DELIVER"], True, 0.0, 2)], "rel": 0, "turn": True})
                trial = stops + add
                ev = _tier_eval(cseg, trial)
                if ev[1] > 0 or ev[0] > 24:
                    continue
                sc = c["dv"] / max(1, ev[0] - ev0[0])
                if best is None or sc > best[0]:
                    best = (sc, idx, trial)
            if best is None:
                break
            _, idx, trial = best
            stops = trial
            taken.append(idx)
            c = cand.pop(idx)
            ids = set(id(o) for o in c["ops"])
            rec[idx]["ops"] = [o for o in rec[idx]["ops"] if id(o) not in ids]
            if not rec[idx]["ops"]:
                rec.pop(idx)
            st["tier_central_deliver_pens"] = st.get("tier_central_deliver_pens", 0) + 1
    while cand:
        ev0 = _tier_eval(cseg, stops) if stops else (cseg["t0"], 0, 0, 0)
        best = None
        for idx, c in cand.items():
            add = [{"tile": idx, "ops": [dict(o, m=True, tier=2) for o in c["ops"]], "rel": rec[idx]["rel"]}]
            if c["hv"] and idx not in _TIER_SHED_I:
                sh = min(_TIER_SHED_I, key=lambda q: D[idx][q])
                add.append({"tile": sh, "ops": [_tier_op(["DELIVER"], True, 0.0, 2)], "rel": 0, "turn": True})
            trial = stops + add
            ev = _tier_eval(cseg, trial)
            if ev[1] > 0 or ev[0] > 24:
                continue
            dh = max(1, ev[0] - ev0[0])
            sc = c["v"] / dh
            if c["v"] < 1e6 and sc < rate:
                continue
            if best is None or sc > best[0]:
                best = (sc, idx, trial)
        if best is None:
            break
        _, idx, trial = best
        stops = trial
        taken.append(idx)
        c = cand.pop(idx)
        ids = set(id(o) for o in c["ops"])
        rec[idx]["ops"] = [o for o in rec[idx]["ops"] if id(o) not in ids]
        if not rec[idx]["ops"]:
            rec.pop(idx)
    cseg["stops"] = stops
    cseg["kind"] = "central"
    st["tier_central_pens"] = st.get("tier_central_pens", 0) + len(taken)
    st["tier_central_days"] = st.get("tier_central_days", 0) + 1


def _tier_dayret(segs_m, tiles, day, st):
    """sd_tier_dayret_shape: DSM's daytime returns of this day (see the flag) inserted into our mandatory routes."""
    D = _TIER_D
    data = ((_dsm_data("dayret") or {}).get("days") or {}).get(str(day)) or []
    used = set()
    rec_ = st["_dayret_day"] = {"dsm": len(data), "in": [], "late": 0, "nomatch": 0}
    for ret in data:
        rtiles = [int(x[0]) for x in ret[3]]
        prods = sorted({x[1] for x in ret[3]})
        best = None
        for k, sg in enumerate(segs_m):
            if sg["kind"] != "out" or k in used or not sg["stops"]:
                continue
            pos = [i for i, x in enumerate(sg["stops"]) if x["tile"] in rtiles and any(o["c"][0] == "HARVEST" for o in x["ops"])]
            if pos and (best is None or len(pos) > best[0]):
                best = (len(pos), k, pos[-1])
        st["tier_dayret_dsm"] = st.get("tier_dayret_dsm", 0) + 1
        if best is None:
            st["tier_dayret_nomatch"] = st.get("tier_dayret_nomatch", 0) + 1
            rec_["nomatch"] += 1
            continue
        _, k, j = best
        sg = segs_m[k]
        a = sg["stops"][j]["tile"]
        b = sg["stops"][j + 1]["tile"] if j + 1 < len(sg["stops"]) else None
        sh = min(_TIER_SHED_I, key=lambda q: D[a][q] + (D[q][b] if b is not None else 0))
        turn = {"tile": sh, "ops": [_tier_op(["DELIVER", p_], True, 0.0, 2) for p_ in prods], "rel": 0, "turn": True, "copy": True}
        trial = sg["stops"][:j + 1] + [turn] + sg["stops"][j + 1:]
        ev0, ev = _tier_eval(sg), _tier_eval(sg, trial)
        moves_ = {}
        if (ev[1] > ev0[1] or ev[3] > ev0[3]) and int(CFG["sd_tier_dayret_relocate"]):
            # make room (user: reassign tiles from busy sectors): move this hand's tail stops after the return, last first,
            # to the outbound hand where each fits cheapest without lateness, until the return adds no lateness
            cur_ = list(trial)
            ti_ = cur_.index(turn)
            for _ in range(int(CFG["sd_tier_dayret_relocate"])):
                tail_ = [i for i in range(ti_ + 1, len(cur_)) if not cur_[i].get("turn")]
                if not tail_:
                    break
                i_ = tail_[-1]
                stop_ = cur_[i_]
                bd_ = {"tile": stop_["tile"], "ops": stop_["ops"], "v": 1.0}
                best2_ = None
                for kk, s2 in enumerate(segs_m):
                    if kk == k or s2["kind"] != "out":
                        continue
                    tmp_ = dict(s2, stops=moves_.get(kk, s2["stops"]))
                    r2_ = _tier_best_ins(tmp_, bd_, {}, 0)
                    if r2_ and (best2_ is None or r2_[1] < best2_[0][1]):
                        best2_ = (r2_, kk)
                if best2_ is None:
                    break
                cur_ = cur_[:i_] + cur_[i_ + 1:]
                moves_[best2_[1]] = best2_[0][2]
                ev = _tier_eval(sg, cur_)
                if ev[1] <= ev0[1] and ev[3] <= ev0[3]:
                    trial = cur_
                    break
            else:
                moves_ = {}
            if ev[1] > ev0[1] or ev[3] > ev0[3]:
                moves_ = {}
        if ev[1] > ev0[1] or ev[3] > ev0[3]:
            st["tier_dayret_late"] = st.get("tier_dayret_late", 0) + 1
            rec_["late"] += 1
            continue
        for kk, ns_ in moves_.items():
            segs_m[kk]["stops"] = ns_
            segs_m[kk]["ver"] += 1
        rec_["moved"] = rec_.get("moved", 0) + len(moves_)
        rec_["in"].append([sg.get("u"), prods, j])
        sg["stops"] = trial
        sg["ver"] += 1
        used.add(k)
        st["tier_dayret_in"] = st.get("tier_dayret_in", 0) + 1


def _tier_pen_round(segs_m, tiles, day, st):
    """sd_tier_pen_round: an outbound hand whose (mandatory) route holds animal harvests within sd_tier_pen_radius of
    the shed does them first (nearest first) and, for pens off the access tiles, walks back to the shed and DELIVERs the
    product (sold at once) before its other stops; kept only when the time model adds no lateness / supply failure."""
    D = _TIER_D
    rad = int(CFG["sd_tier_pen_radius"])
    for sg in segs_m:
        if sg["kind"] != "out" or not sg["stops"]:
            continue
        near = lambda x: min(D[x["tile"]][q] for q in _TIER_SHED_I)
        pens = [x for x in sg["stops"] if not x.get("turn") and _animal(_tile(tiles, x["tile"]))
                and any(o["c"][0] == "HARVEST" for o in x["ops"]) and near(x) <= rad]
        if not pens:
            continue
        pens.sort(key=near)
        rest = [x for x in sg["stops"] if not any(x is y for y in pens)]
        off = [x for x in pens if x["tile"] not in _TIER_SHED_I]
        new = list(pens)
        if off:
            prods = sorted({ANIMALS[_animal(_tile(tiles, x["tile"]))]["product"] for x in off})
            last = pens[-1]["tile"]
            sh = min(_TIER_SHED_I, key=lambda q: D[last][q] + (D[q][rest[0]["tile"]] if rest else 0))
            new.append({"tile": sh, "ops": [_tier_op(["DELIVER"], True, 0.0, 2) for _ in prods], "rel": 0, "turn": True,
                        "pen": True})
        trial = new + rest
        ev0, ev = _tier_eval(sg), _tier_eval(sg, trial)
        if ev[1] > ev0[1] or ev[3] > ev0[3]:
            st["tier_pen_rejected"] = st.get("tier_pen_rejected", 0) + 1
            continue
        sg["stops"] = trial
        sg["ver"] += 1
        st["tier_pen_rounds"] = st.get("tier_pen_rounds", 0) + 1
        st["tier_pen_stops"] = st.get("tier_pen_stops", 0) + len(pens)


def _tier_turn_plan(segs_m, tiles, day, st, prices):
    """sd_tier_turn_plan: each outbound hand gets one shed stop after its harvest leg, inserted into the mandatory route
    (before the extras fill): the insertion point after >= sd_tier_turn_min harvested units, reached by
    sd_tier_turn_hour, detour <= sd_tier_turn_detour tiles, best delivered value per added hour, no added lateness."""
    D = _TIER_D
    hmax, dmax, umin = int(CFG["sd_tier_turn_hour"]), int(CFG["sd_tier_turn_detour"]), int(CFG["sd_tier_turn_min"])
    for sg in segs_m:
        stops = sg["stops"]
        if sg["kind"] != "out" or len(stops) < 2:
            continue
        ev0 = _tier_eval(sg, want_hours=True)
        hrs = ev0[4]
        lt = max((i for i, x in enumerate(stops) if x.get("turn")), default=-1)
        best, cum = None, 0
        for j in range(1, len(stops)):
            cum += len(stops[j - 1]["ops"])
            if j <= lt + 1 or stops[j].get("turn") or cum == 0 or cum > len(hrs):
                continue
            if hrs[cum - 1][2] + 1 > hmax:
                break
            lk = _tier_load(sg, stops[:j], tiles, day)
            dl = {p_: v for p_, v in lk.items() if p_ != "FERTILIZER" and v > 0}
            units = sum(dl.values())
            if units < umin:
                continue
            a, b = stops[j - 1]["tile"], stops[j]["tile"]
            sh = min(_TIER_SHED_I, key=lambda q: D[a][q] + D[q][b])
            if D[a][sh] + D[sh][b] - D[a][b] > dmax:
                continue
            turn = {"tile": sh, "ops": [_tier_op(["DELIVER"], True, 0.0, 2) for _ in dl], "rel": 0, "turn": True}
            trial = stops[:j] + [turn] + stops[j:]
            ev = _tier_eval(sg, trial)
            if ev[1] > ev0[1] or ev[3] > ev0[3]:
                continue
            val = sum(v * float(prices.get(p_, 0) or 0) for p_, v in dl.items())
            sc = val / max(1, ev[0] - ev0[0])
            if best is None or sc > best[0]:
                best = (sc, trial, units)
        if best is not None:
            sg["stops"] = best[1]
            sg["ver"] += 1
            st["tier_turn_plans"] = st.get("tier_turn_plans", 0) + 1
            st["tier_turn_plan_units"] = st.get("tier_turn_plan_units", 0) + best[2]


def _tier_pass_drop(segs_m, tiles, day, st):
    """sd_tier_pass_drop: along each outbound route, wherever the walk between two stops can cross a shed-access tile at
    no extra distance (or the next stop is on one) and the hand carries >= sd_tier_pass_min units, a DELIVER stop is put
    on that tile (one op per product); kept only when the time model adds no lateness / supply failure."""
    D = _TIER_D
    umin = int(CFG["sd_tier_pass_min"])
    for sg in segs_m:
        if sg["kind"] != "out" or len(sg["stops"]) < 2:
            continue
        j = 1
        while j < len(sg["stops"]):
            stops = sg["stops"]
            if stops[j].get("turn") or stops[j - 1].get("turn"):
                j += 1
                continue
            a, b = stops[j - 1]["tile"], stops[j]["tile"]
            on = [q for q in _TIER_SHED_I if q != a and D[a][q] + D[q][b] == D[a][b]]
            if not on:
                j += 1
                continue
            lk = _tier_load(sg, stops[:j], tiles, day)
            dl = {p_: v for p_, v in lk.items() if p_ != "FERTILIZER" and v > 0}
            if sum(dl.values()) < umin:
                j += 1
                continue
            sh = b if b in on else min(on, key=lambda q: D[a][q])
            turn = {"tile": sh, "ops": [_tier_op(["DELIVER"], True, 0.0, 2) for _ in dl], "rel": 0, "turn": True,
                    "pass": True}
            trial = stops[:j] + [turn] + stops[j:]
            ev0, ev = _tier_eval(sg), _tier_eval(sg, trial)
            if ev[1] > ev0[1] or ev[3] > ev0[3]:
                st["tier_pass_rejected"] = st.get("tier_pass_rejected", 0) + 1
                j += 1
                continue
            sg["stops"] = trial
            sg["ver"] += 1
            st["tier_pass_drops"] = st.get("tier_pass_drops", 0) + 1
            j += 2


def _tier_turn(segs, tiles, day, st, prices, room, total):
    """sd_tier_turnaround (the leaders' type-B delivery): while the projected midnight load exceeds room, insert into the
    best hand's route a shed stop between two stops (detour <= sd_tier_turn_detour tiles, reached by sd_tier_turn_hour)
    carrying one DELIVER op per harvested product; no hand gets later mandatory work or supply failures."""
    D = _TIER_D
    hmax, dmax, umin = int(CFG["sd_tier_turn_hour"]), int(CFG["sd_tier_turn_detour"]), int(CFG["sd_tier_turn_min"])
    done = set()
    while total > room or int(CFG["sd_tier_turnaround"]) >= 2:   # 2: every feasible turnaround, not only on overflow
        best = None
        for k, sg in enumerate(segs):
            stops = sg["stops"]
            if k in done or sg["kind"] not in ("out", "ani") or len(stops) < 2:
                continue
            ev0 = _tier_eval(sg, want_hours=True)
            hrs = ev0[4]
            cum = 0
            for j in range(1, len(stops)):
                cum += len(stops[j - 1]["ops"])
                if cum == 0 or cum > len(hrs):
                    continue
                end_h = hrs[cum - 1][2] + 1
                if end_h > hmax:
                    break
                if stops[j].get("dawn"):
                    continue
                lk = _tier_load(sg, stops[:j], tiles, day)
                dl = {p_: v for p_, v in lk.items() if p_ != "FERTILIZER" and v > 0}
                units = sum(dl.values())
                if units < umin:
                    continue
                a, b = stops[j - 1]["tile"], stops[j]["tile"]
                sh = min(_TIER_SHED_I, key=lambda q: D[a][q] + D[q][b])
                if D[a][sh] + D[sh][b] - D[a][b] > dmax:
                    continue
                turn = {"tile": sh, "ops": [_tier_op(["DELIVER"], True, 0.0, 2) for _ in dl], "rel": 0, "turn": True}
                trial = stops[:j] + [turn] + stops[j:]
                ev = _tier_eval(sg, trial)
                if ev[1] > ev0[1] or ev[3] > ev0[3]:
                    continue
                val = sum(v * float(prices.get(p_, 0) or 0) for p_, v in dl.items())
                sc = val / max(1, ev[0] - ev0[0])
                if best is None or sc > best[0]:
                    best = (sc, k, trial, units)
        if best is None:
            break
        _, k, trial, units = best
        segs[k]["stops"] = trial
        segs[k]["ver"] += 1
        done.add(k)
        total -= units
        st["tier_turnarounds"] = st.get("tier_turnarounds", 0) + 1
        st["tier_turn_units"] = st.get("tier_turn_units", 0) + units
    return total


def _tier_deliver(S, segs, tiles, day, st):
    """sd_tier_deliver: when the projected midnight dump (every hand's load) will not fit the shed (100 minus tomorrow's
    feed wheat and a buffer), the hands with the most valuable loads per added hour end their day at the nearest shed tile
    with a DROP (sold at once); low-value extras at a route's end are trimmed when the day is too short for the walk."""
    prices = S.get("_tier_prices") or {}
    n_anim = sum(1 for r in tiles for t in r if _animal(t))
    room = 100 - n_anim * int(CFG["wheat_days"]) - int(CFG["sd_tier_dump_buffer"])
    loads = [_tier_load(sg, sg["stops"], tiles, day) for sg in segs]
    if CFG["sd_wheat_net"]:                        # tomorrow's feed wheat net of the wheat the hands bring home tonight
        home_w_ = sum(int(l.get("WHEAT", 0)) for l in loads)
        room = 100 - max(0, n_anim * int(CFG["wheat_days"]) - home_w_) - int(CFG["sd_tier_dump_buffer"])
        st["_wheat_net_room"] = room
    total = sum(sum(l.values()) for l in loads)
    st["tier_dump_proj"] = st.get("tier_dump_proj", 0) + total
    if CFG["sd_tier_turnaround"]:
        total = _tier_turn(segs, tiles, day, st, prices, room, total)
        loads = [_tier_load(sg, sg["stops"], tiles, day) for sg in segs]
    total0 = total
    target_ = 0
    if CFG["sd_tier_copy_returns"] and day >= int(CFG["sd_tier_copy_returns_from"]):
        dr_ = _dsm_data("returns")
        target_ = int((((dr_ or {}).get("days") or {}).get(str(day)) or {}).get("hands", 0))
    has_ = lambda sg: any(x.get("deliver") or x.get("turn") for x in sg["stops"])
    done = set()
    while total > room or (target_ and sum(1 for sg in segs if has_(sg)) < target_):
        best = None
        for k, sg in enumerate(segs):
            if k in done or not loads[k]:
                continue
            val = sum(v * float(prices.get(p, 0) or 0) for p, v in loads[k].items())
            ev0 = _tier_eval(sg)
            stops = list(sg["stops"])
            lost = 0.0
            for trim in range(4):
                last = stops[-1]["tile"] if stops else sg["p0"]
                sh = _tier_near_shed(last)
                copy_ = total <= room                 # added only to reach the leader's count of daytime returns
                trial = stops + [{"tile": sh, "ops": [_tier_op(["DROP"], True, 0.0, 2)], "rel": 0, "deliver": True,
                                  "copy": bool(copy_ and int(CFG["sd_tier_copy_returns_end"]))}]
                ev = _tier_eval(sg, trial)
                end_ok_ = not (copy_ and int(CFG["sd_tier_copy_returns_end"])) or ev[0] <= int(CFG["sd_tier_copy_returns_end"])
                if ev[1] <= ev0[1] and ev[3] <= ev0[3] and end_ok_:
                    lk = _tier_load(sg, trial[:-1], tiles, day)
                    v2 = sum(v * float(prices.get(p, 0) or 0) for p, v in lk.items())
                    dh = max(1, ev[0] - ev0[0])
                    sc = (v2 - lost) / dh
                    if v2 - lost > 0 and (best is None or sc > best[0]):
                        best = (sc, k, trial, lk)
                    break
                if not stops or any(o["m"] for o in stops[-1]["ops"]):
                    break                              # only extras (no mandatory op) may be trimmed
                lost += sum(o["v"] for o in stops[-1]["ops"])
                stops = stops[:-1]
        if best is None:
            break
        _, k, trial, lk = best
        segs[k]["stops"] = trial
        segs[k]["ver"] += 1
        done.add(k)
        total -= sum(lk.values())
        st["tier_deliveries"] = st.get("tier_deliveries", 0) + 1
    deferred_ = 0
    if int(CFG["sd_defer_shed"]):                  # DSM: glut goods stay on the animals, not in the shed
        shed0_ = (S.get("_shed_h0") or {})
        glut_ = {p_ for p_, v_ in shed0_.items() if int(v_ or 0) >= int(CFG["sd_defer_shed"])}
        if glut_:
            for k, sg in enumerate(segs):
                for x in list(sg["stops"]):
                    if x.get("deliver") or x.get("turn") or x.get("place"):
                        continue
                    t_ = _tile(tiles, x["tile"])
                    if not _animal(t_) or ANIMALS[t_["animal"]]["product"] not in glut_:
                        continue
                    if not any(o["c"][0] == "HARVEST" for o in x["ops"]) or not _tier_defer_ok(t_, day):
                        continue
                    u_ = int(t_.get("yield_units", 0) or 0)
                    x["ops"] = [o for o in x["ops"] if o["c"][0] not in ("HARVEST", "PLACE_HARVEST")]
                    if not x["ops"]:
                        sg["stops"] = [y for y in sg["stops"] if y is not x]
                    sg["ver"] += 1
                    total -= u_
                    deferred_ += u_
                    st["tier_defer_shed"] = st.get("tier_defer_shed", 0) + u_
    if CFG["sd_tier_dump_defer"]:                  # leave holdable harvests for tomorrow instead of deleting them
        cap_ = int(CFG["sd_tier_dump_defer_cap"]) or (100 - int(CFG["sd_tier_dump_buffer"]))
        while total > cap_:
            best_ = None
            for k, sg in enumerate(segs):
                for x in sg["stops"]:
                    if x.get("deliver") or x.get("turn") or x.get("place"):
                        continue
                    cs_ = [o["c"][0] for o in x["ops"]]
                    if "HARVEST" not in cs_ or any(c_ in ("PLANT", "DIG", "BUILD_COOP", "BUILD_PASTURE") for c_ in cs_):
                        continue
                    t_ = _tile(tiles, x["tile"])
                    if not isinstance(t_, dict):
                        continue
                    kf_ = CFG["sd_harvest_follow_keep"]
                    if kf_ and any(o.get("follow") for o in x["ops"]) and (
                            not isinstance(kf_, (list, tuple)) or (t_.get("animal") or t_.get("crop")) in kf_):
                        continue                   # DSM harvested it today (sd_harvest_follow_keep: 1 = all, or kinds)
                    u_ = int(t_.get("yield_units", 0) or 0)
                    if u_ <= 0 or not _tier_defer_ok(t_, day):
                        continue
                    prod_ = ANIMALS[t_["animal"]]["product"] if _animal(t_) else t_.get("crop")
                    pr_ = float(prices.get(prod_, 0) or 0)
                    if best_ is None or pr_ < best_[0]:
                        best_ = (pr_, k, x, u_)
            if best_ is None:
                break
            _, k, x, u_ = best_
            x["ops"] = [o for o in x["ops"] if o["c"][0] not in ("HARVEST", "PLACE_HARVEST")]
            if not x["ops"]:
                segs[k]["stops"] = [y for y in segs[k]["stops"] if y is not x]
            segs[k]["ver"] += 1
            total -= u_
            deferred_ += u_
        st["tier_dump_deferred"] = st.get("tier_dump_deferred", 0) + deferred_
    cap_true_ = 100 - int(CFG["sd_tier_dump_buffer"])
    if CFG["sd_tier_deliver_skip"] and total - cap_true_ >= int(CFG["sd_tier_deliver_skip_min"]):
        # user: heavy overflow expected even after the deferral - a few hands give up optional jobs to drop at the shed
        # (end of day or mid-route, up to sd_tier_deliver_skip_trips drops a hand)
        ntr_ = {k: sum(1 for x in sg["stops"] if x.get("deliver") or x.get("turn")) for k, sg in enumerate(segs)}
        for _round in range(2 * len(segs)):
            if total <= cap_true_:
                break
            best = None
            for k, sg in enumerate(segs):
                if sg["kind"] not in ("out", "post", "ani") or not sg["stops"] or ntr_.get(k, 0) >= int(CFG["sd_tier_deliver_skip_trips"]):
                    continue
                ev0 = _tier_eval(sg)
                l0 = sum(v for v in _tier_load(sg, sg["stops"], tiles, day).values() if v > 0)
                stops2 = list(sg["stops"])
                lost2 = 0.0
                for _i in range(int(CFG["sd_tier_deliver_skip_max"]) + 1):
                    found_ = None
                    for pos in range(1, len(stops2) + 1):   # a DROP after stop pos-1 (pos = len: the end of the day)
                        prev_ = stops2[pos - 1]
                        if prev_.get("dawn"):
                            continue
                        dstop = {"tile": _tier_near_shed(prev_["tile"]), "ops": [_tier_op(["DROP"], True, 0.0, 2)], "rel": 0,
                                 "deliver": pos == len(stops2), "turn": pos < len(stops2), "sell_all": True}
                        trial = stops2[:pos] + [dstop] + stops2[pos:]
                        ev = _tier_eval(sg, trial)
                        if ev[1] > ev0[1] or ev[3] > ev0[3] or ev[0] > 24:
                            continue
                        lk_after = _tier_load(sg, trial, tiles, day) if pos < len(stops2) else Counter()
                        lk_drop = _tier_load(sg, trial[:pos], tiles, day)
                        red_ = l0 - sum(v for v in lk_after.values() if v > 0)
                        nd_ = sum(v for v in lk_drop.values() if v > 0)
                        if red_ <= 0 or nd_ <= 0:
                            continue
                        avgp = sum(max(0, v) * float(prices.get(p, 0) or 0) for p, v in lk_drop.items()) / nd_
                        net_ = min(red_, total - cap_true_) * avgp - lost2
                        if net_ > 0 and (found_ is None or net_ > found_[0]):
                            found_ = (net_, trial, red_)
                    if found_ is not None:
                        if best is None or found_[0] > best[0]:
                            best = (found_[0], k, found_[1], found_[2])
                        break
                    cand_ = [(float(o["v"]), i_, j_) for i_, x in enumerate(stops2) if not x.get("dawn") and not x.get("turn") and not x.get("deliver")
                             for j_, o in enumerate(x["ops"]) if not o["m"] and (CFG["sd_tier_deliver_skip_collects"] or o["c"][0] != "COLLECT_FERTILIZER")]
                    if not cand_:
                        break
                    v_, i_, j_ = min(cand_)
                    lost2 += v_
                    x = stops2[i_]
                    ops2 = [o for jj, o in enumerate(x["ops"]) if jj != j_]
                    stops2 = stops2[:i_] + ([dict(x, ops=ops2)] if ops2 else []) + stops2[i_ + 1:]
            if best is None:
                break
            _, k, trial, red_ = best
            segs[k]["stops"] = trial
            segs[k]["ver"] += 1
            ntr_[k] = ntr_.get(k, 0) + 1
            total -= red_
            st["tier_deliver_skip"] = st.get("tier_deliver_skip", 0) + 1
    st["tier_dump_left_over"] = st.get("tier_dump_left_over", 0) + max(0, total - room)
    st["_dump_day"] = {"proj": total0, "room": room, "left": total, "target": target_, "skip": st.get("tier_deliver_skip", 0),
                       "with_delivery": sum(1 for sg in segs if has_(sg)), "deferred": deferred_}


def _tier_melon(day, tiles, units):
    """the melon rule's partition over units [(u, p0 xy, t0)] each from its own start hour: blocks ranked (lateness
    cost, blocks, -early bonus); melons nobody can drop by 12 are left out (normal harvest)."""
    ripe = [i for i in range(100) if _mel_ripe(_tile(tiles, i), day)]
    if not ripe or not units:
        return [], ripe
    ok = [i for i in ripe if min(_mel_block(p0, t0, [i], tiles, day)[0] for _, p0, t0 in units) <= 12]
    left = [i for i in ripe if i not in ok]
    best = None
    for part in _mel_partitions(ok[:8]):
        if len(part) > len(units):
            continue
        cand = []
        for b in part:
            opts = sorted((_mel_block(p0, t0, b, tiles, day) + (u,) for u, p0, t0 in units), key=lambda x: (x[1], x[0]))
            cand.append((opts, b))
        cand.sort(key=lambda c: -c[0][0][1] if c[0][0][1] != float("inf") else -1e18)
        used, tot, bonus, asg = set(), 0.0, 0.0, []
        ok_ = True
        for opts, b in cand:
            pick = next((o for o in opts if o[5] not in used), None)
            if pick is None or pick[1] == float("inf"):
                ok_ = False
                break
            used.add(pick[5])
            tot += max(0.0, pick[1])
            bonus += max(0.0, -pick[1])
            asg.append((pick[5], list(pick[3]), pick[0], pick[4]))
        if not ok_:
            continue
        key = (round(tot, 3), len(part), -bonus)
        if best is None or key < best[0]:
            best = (key, asg)
    return (best[1] if best else []), left


def _tier_defer_ok(t, day, exact=False):
    """sd_tier_dump_defer: the tile keeps its units until tomorrow without losing production. exact (sd_follow_defer_exact):
    a one-time crop whose decay starts at the start of the day after tomorrow may wait (the engine decays from
    max_lifespan_step on; the default test also refuses that last full day, so an age-3 wheat never waits for age 4)."""
    if _animal(t):
        return not _tier_anim_harv_needed(t, day)
    crop = t.get("crop")
    if not crop or crop == "MELON":
        return False
    cd = CROPS[crop]
    ls = int(t.get("max_lifespan_step", -1) or -1)
    if ls != -1 and (ls < (day + 2) * 24 if exact else ls <= (day + 2) * 24):
        return False                               # decays by tomorrow's end
    if cd["ongoing"]:
        dsf = day + 1 - int(t.get("planted_day", day)) - cd["first"]
        add = 0
        if dsf >= 0 and cd["interval"] and dsf % cd["interval"] == 0 and dsf // cd["interval"] + 1 <= cd["max"]:
            add = 2 if int(t.get("fertilized_until_day", -1)) >= day else 1
        return int(t.get("yield_units", 0) or 0) + add <= cd["max"]
    return True


def _tier_anim_harv_needed(t, day):
    """animal thread (sd_tier_anim_harv): today's harvest is needed when tonight's production (1 + the banked bonus) would
    not fit under max_held, or from sd_tier_anim_harv_end on (everything held must reach the market by the end)."""
    if day >= int(CFG["sd_tier_anim_harv_end"]):
        return True
    a = ANIMALS[t["animal"]]
    held = int(t.get("yield_units", 0) or 0)
    dsf = day + 1 - int(t.get("placed_day", day)) - a["first"]
    if dsf < 0 or dsf % a["interval"] != 0:
        return held >= a["max_held"]
    return held + 1 + int(t.get("pending_care_bonus", 0) or 0) > a["max_held"]


def _tier_anim_mand(rec, tiles, minv, st):
    """animal thread (sd_tier_anim_mand_minv): on a live animal the non-mandatory FEED / CARE become mandatory (tier B) when
    their joint value is >= minv; a CARE only with a feed today (mandatory FEED or already fed), as it pays only then."""
    n = 0
    for idx, r_ in rec.items():
        t = _tile(tiles, idx)
        if not _animal(t):
            continue
        fc = [o for o in r_["ops"] if o["c"][0] in ("FEED", "CARE") and not o["m"]]
        if not fc or sum(o["v"] for o in fc) < minv:
            continue
        fed = t.get("fed_today") or any(o["c"][0] == "FEED" for o in r_["ops"])
        for o in fc:
            if o["c"][0] == "CARE" and not fed:
                continue
            o["m"], o["tier"] = True, 2
            n += 1
    st["tier_anim_mand"] = st.get("tier_anim_mand", 0) + n


def _tier_goose_care(rec, tiles, day, last_day, prices, st):
    """KWE (sd_tier_goose_care): goose CARE (and FEED) made mandatory. A care banks +1 only on a fed day and is paid at the
    next production only if the goose is fed that day, so a CARE needs a FEED today (planned mandatory or already done);
    useful only while that production is still harvestable (the refresh of day last_day - 1 is the last one)."""
    mode = int(CFG["sd_tier_goose_care"])
    if day + 2 > last_day:
        return
    pe = float(prices.get("EGG", 0) or 0) or 50.0
    n_c = n_f = 0
    for idx in range(100):
        t = _tile(tiles, idx)
        if _animal(t) != "GOOSE" or t.get("cared_today"):
            continue
        r_ = rec.get(idx)
        ops = r_["ops"] if r_ else []
        feed_m = bool(t.get("fed_today")) or any(o["c"][0] == "FEED" and o["m"] for o in ops)
        any_m = any(o["m"] for o in ops)
        if mode == 1 and not feed_m:
            continue
        if mode == 2 and not (feed_m or any_m):
            continue
        r_ = rec.setdefault(idx, {"ops": [], "rel": 0})
        if not t.get("fed_today"):
            f = next((o for o in r_["ops"] if o["c"][0] == "FEED"), None)
            if f is None:
                r_["ops"].append(_tier_op(["FEED"], True, pe, 2))
                n_f += 1
            elif not f["m"]:
                f["m"], f["tier"] = True, 2
                n_f += 1
        c = next((o for o in r_["ops"] if o["c"][0] == "CARE"), None)
        if c is None:
            r_["ops"].append(_tier_op(["CARE"], True, pe, 2))
        else:
            c["m"], c["tier"] = True, 2
        r_["ops"].sort(key=lambda o: o["rank"])
        n_c += 1
    st["tier_goose_care"] = st.get("tier_goose_care", 0) + n_c
    st["tier_goose_feed"] = st.get("tier_goose_feed", 0) + n_f


def _tier_collect_swap(segs, rest, owner, rate, st):
    """sd_tier_collect_swap: move collects from full hands to hands with spare time on the way (see the flag)."""
    D = _TIER_D
    det = 2 * int(CFG["sd_tier_path_collect_detour"])
    n = 0
    for ka, A in enumerate(segs):
        for _rep in range(3):                      # up to three swaps a hand
            if A["kind"] not in ("out", "post", "ani") or not A["stops"]:
                break
            evA = _tier_eval(A)
            if evA[0] < 24:
                break                              # only a full hand gains from giving work away
            done_ = False
            for ia, x in enumerate(A["stops"]):
                cops = [o for o in x["ops"] if o["c"][0] == "COLLECT_FERTILIZER"]
                if not cops or x.get("dawn"):
                    continue
                a = x["tile"]
                if len(cops) == len(x["ops"]):
                    stA = A["stops"][:ia] + A["stops"][ia + 1:]
                else:
                    stA = A["stops"][:ia] + [dict(x, ops=[o for o in x["ops"] if o["c"][0] != "COLLECT_FERTILIZER"])] + A["stops"][ia + 1:]
                evA2 = _tier_eval(A, stA)
                if evA2[3] > evA[3] or evA2[1] > evA[1] or evA[0] - evA2[0] < 1:
                    continue                       # it feeds A's own fertilize, or frees nothing
                best = None
                for kb, B in enumerate(segs):
                    if kb == ka or B["kind"] not in ("out", "post", "ani") or not B["stops"]:
                        continue
                    evB = _tier_eval(B)
                    if evB[0] >= 24:
                        continue
                    tb_ = [B["p0"]] + [y["tile"] for y in B["stops"]]
                    opts = []
                    if any(y["tile"] == a for y in B["stops"]):
                        opts.append(_tier_merge(B["stops"], a, cops)[0])
                    else:
                        for k in range(len(B["stops"])):
                            if D[tb_[k]][a] + D[a][tb_[k + 1]] <= D[tb_[k]][tb_[k + 1]] + det and not B["stops"][k].get("dawn"):
                                opts.append(_tier_merge(B["stops"], a, cops, 0, k)[0])
                    for stB in opts:
                        evB2 = _tier_eval(B, stB)
                        if evB2[0] > 24 or evB2[1] > evB[1] or evB2[3] > evB[3]:
                            continue
                        if best is None or evB2[0] - evB[0] < best[0]:
                            best = (evB2[0] - evB[0], kb, stB)
                if best is None:
                    continue
                _, kb, stB = best
                segs[kb]["stops"] = stB
                segs[kb]["ver"] += 1
                A["stops"] = stA
                A["ver"] += 1
                n += 1
                pool_ = []                         # refill without harvests: the dump deferral already cut them (KB55: +352 deleted a world)
                for bd in rest:
                    ops2 = [o for o in bd["ops"] if o["c"][0] not in ("HARVEST", "PLACE_HARVEST")]
                    if ops2:
                        pool_.append(dict(bd, ops=ops2, v=sum(o["v"] for o in ops2), _src=bd))
                n_r_ = _tier_fill(segs, [ka], pool_, {}, owner, rate, st, "swap")
                if n_r_:
                    taken_ = {id(bd.get("_src")) for bd in pool_}
                    for bd in [b for b in rest if id(b) not in taken_]:
                        bd["ops"] = [o for o in bd["ops"] if o["c"][0] in ("HARVEST", "PLACE_HARVEST")]
                    rest[:] = [b for b in rest if b["ops"]]
                st["tier_swap_refill"] = st.get("tier_swap_refill", 0) + n_r_
                done_ = True
                break
            if not done_:
                break
    return n


def _tier_fert_merge(segs, tiles, day, prices, st, budget):
    """sd_tier_fert_merge: fertilizes merged into a hand's own watering stops, fertilizer from the shed (see the flag)."""
    n = 0
    pf_ = float(prices.get("FERTILIZER", 0) or 0)
    for sg in segs:
        if budget[0] <= 0 and not int(CFG["sd_tier_fert_merge_collect"]):
            break
        if sg["kind"] not in ("out", "post") or sg["p0"] not in _TIER_SHED_I or any(x.get("dawn") for x in sg["stops"]):
            continue
        while budget[0] > 0 or int(CFG["sd_tier_fert_merge_collect"]):
            ev0 = _tier_eval(sg)
            if ev0[0] >= 24:
                break
            fp_ = int(sg.get("fpick", 0) or 0)
            best = None
            for i, x in enumerate(sg["stops"]):
                cs = [o["c"][0] for o in x["ops"]]
                if "WATER" not in cs or "FERTILIZE" in cs:
                    continue
                t = _tile(tiles, x["tile"])
                if not _is_plant(t) or t.get("watered_today"):
                    continue
                g = _tier_fert_gain(x["tile"], t, day)
                if g <= 0:
                    continue
                val = g * float(prices.get(t.get("crop"), 0) or 0) - pf_
                if val <= 0:
                    continue
                st_ = [dict(y) for y in sg["stops"]]
                st_[i] = dict(x, ops=sorted(x["ops"] + [_tier_op(["FERTILIZE"], False, val, 3)], key=lambda o: o["rank"]))
                own_ = False
                if int(CFG["sd_tier_fert_merge_collect"]):   # the route's own unspent collected fertilizer first
                    ev = _tier_eval(sg, st_)
                    own_ = ev[0] <= 24 and ev[1] <= ev0[1] and ev[3] <= ev0[3]
                if not own_:
                    if budget[0] <= 0:
                        continue
                    ev = _tier_eval(dict(sg, fpick=fp_ + 1), st_)
                    if ev[0] > 24 or ev[1] > ev0[1] or ev[3] > ev0[3]:
                        continue
                if best is None or val > best[0]:
                    best = (val, st_, own_)
            if best is None:
                break
            sg["stops"] = best[1]
            if not best[2]:
                sg["fpick"] = fp_ + 1
                budget[0] -= 1
            else:
                st["tier_fert_merge_own"] = st.get("tier_fert_merge_own", 0) + 1
            sg["ver"] += 1
            n += 1
            st["tier_fert_merge_val"] = st.get("tier_fert_merge_val", 0) + best[0]
    return n


def _tier_early_deliver(S, segs, tiles, day, st):
    """sd_tier_early_deliver: one delivery per hand from spare time for products we are behind DSM on (see the flag)."""
    prods = set(CFG["sd_tier_early_deliver"] or ())
    cum = _books_cum(S)
    if cum is None or not prods:
        return 0
    shed0 = S.get("_shed_h0") or {}
    need = {p: int((cum.get(day * 24 + 23) or {}).get(p, 0)) - int(S["sold"][p]) - int(shed0.get(p, 0) or 0) for p in prods}
    rec_ = st["_edel_day"] = {"need": dict(need), "drops": 0, "units": 0}

    def prod_of(t):
        return ANIMALS[t["animal"]]["product"] if _animal(t) else (t.get("crop") if _is_plant(t) else None)

    def positions(sg, stops, ev0):
        best = None
        carry = Counter()
        for pos in range(1, len(stops) + 1):
            x = stops[pos - 1]
            if x.get("turn") or x.get("deliver"):
                carry = Counter()
                continue
            t = _tile(tiles, x["tile"])
            if any(o["c"][0] == "HARVEST" for o in x["ops"]) and not any(o["c"][0] == "PLACE_HARVEST" for o in x["ops"]):
                p = prod_of(t)
                if p in prods:
                    carry[p] += int(t.get("yield_units", 0) or 0)
            if x.get("dawn"):
                continue
            want = {p: min(u, max(0, need[p])) for p, u in carry.items() if need.get(p, 0) > 0 and u > 0}
            u = sum(want.values())
            if u <= 0:
                continue
            dl = {"tile": _tier_near_shed(x["tile"]), "ops": [_tier_op(["DELIVER", p], True, 0.0, 2) for p in sorted(want)],
                  "rel": 0, "turn": True, "early": True}
            trial = stops[:pos] + [dl] + stops[pos:]
            ev = _tier_eval(sg, trial)
            if ev[0] > 24 or ev[1] > ev0[1] or ev[3] > ev0[3]:
                continue
            sc = u / max(1, ev[0] - ev0[0])
            if best is None or sc > best[0]:
                best = (sc, trial, want, u)
        return best

    uval = float(CFG["sd_tier_early_deliver_uval"])
    n = 0
    for sg in segs:
        if not any(v > 0 for v in need.values()):
            break
        if sg["kind"] not in ("out", "post", "ani") or not sg["stops"] or any(x.get("turn") and x.get("early") for x in sg["stops"]):
            continue
        ev0 = _tier_eval(sg)
        best = positions(sg, sg["stops"], ev0) if ev0[0] < 24 else None
        if best is None and uval > 0:              # give up the cheapest optional jobs while the timing gain beats them
            stops2 = list(sg["stops"])
            lost = 0.0
            for _i in range(int(CFG["sd_tier_early_deliver_skip_max"])):
                cand_ = [(float(o["v"]), i_, j_) for i_, x in enumerate(stops2) if not x.get("dawn") and not x.get("turn") and not x.get("deliver")
                         for j_, o in enumerate(x["ops"]) if not o["m"] and o["c"][0] not in ("HARVEST", "PLACE_HARVEST", "COLLECT_FERTILIZER")]
                if not cand_:
                    break
                v_, i_, j_ = min(cand_)
                lost += v_
                x = stops2[i_]
                ops2 = [o for jj, o in enumerate(x["ops"]) if jj != j_]
                stops2 = stops2[:i_] + ([dict(x, ops=ops2)] if ops2 else []) + stops2[i_ + 1:]
                b2 = positions(sg, stops2, ev0)
                if b2 is not None:
                    if b2[3] * uval > lost:
                        best = b2
                        rec_["skipped_value"] = rec_.get("skipped_value", 0) + lost
                    break
        if best is None:
            continue
        sg["stops"] = best[1]
        sg["ver"] += 1
        for p, u in best[2].items():
            need[p] -= u
            rec_["units"] += u
        rec_["drops"] += 1
        n += 1
    return n


def _tier_pdrop(S, segs, tiles, day, st):
    """sd_tier_pdrop: goods dropped where a planned route already passes a shed access tile (see the flag)."""
    D = _TIER_D
    prods = list(CFG["sd_tier_pdrop"] or ())
    if not prods:
        return 0
    books = set(CFG["sd_books_sell"] or ())
    cum = _books_cum(S)
    shed0 = S.get("_shed_h0") or {}
    need = {}
    for p in prods:
        if p in books and int(CFG["sd_tier_pdrop_need"]):
            need[p] = (int((cum.get(day * 24 + 23) or {}).get(p, 0)) - int(S["sold"][p]) - int(shed0.get(p, 0) or 0)) if cum is not None else 0
        else:
            need[p] = 10 ** 6
    rec_ = {"need": {p: v for p, v in need.items() if v < 10 ** 6}, "drops": 0, "units": Counter(), "cost": 0, "why": Counter()}
    st.setdefault("_pdrop_day", []).append(rec_)   # every planning pass of the day (spawn passes, counterfactual plan)
    why = rec_["why"]
    if int(CFG.get("sd_tier_pdrop_dbg", 0)) == 1:
        return 0
    cap = int(CFG["sd_tier_pdrop_cost"])
    hmax = int(CFG["sd_tier_pdrop_hmax"])
    nops = int(CFG["sd_tier_pdrop_ops"])
    umin = int(CFG["sd_tier_pdrop_min"])

    def prod_of(t):
        return ANIMALS[t["animal"]]["product"] if _animal(t) else (t.get("crop") if _is_plant(t) else None)

    n = 0
    for sg in segs:
        if sg["kind"] not in ("out", "post", "ani") or not sg["stops"]:
            continue
        for _k in range(int(CFG["sd_tier_pdrop_max"])):
            if not any(v > 0 for v in need.values()):
                break
            ev0 = _tier_eval(sg)
            why["routes"] += 1
            if int(CFG.get("sd_tier_pdrop_dbg", 0)) == 2:
                break
            if ev0[0] >= 24:
                why["full"] += 1
                break
            stops = sg["stops"]
            best = None
            carry = Counter()
            for pos in range(1, len(stops)):            # mid-route only: the hand goes back out after the drop
                x = stops[pos - 1]
                if x.get("turn") or x.get("deliver"):
                    carry = Counter()
                    continue
                t = _tile(tiles, x["tile"])
                if any(o["c"][0] == "HARVEST" for o in x["ops"]) and not any(o["c"][0] == "PLACE_HARVEST" for o in x["ops"]):
                    p = prod_of(t)
                    if p in need:
                        carry[p] += int(t.get("yield_units", 0) or 0)
                if x.get("dawn") or stops[pos].get("dawn"):
                    continue
                want = sorted(((min(u, max(0, need[p])), p) for p, u in carry.items() if need.get(p, 0) > 0 and u > 0), reverse=True)[:nops]
                want = [(u, p) for u, p in want if u > 0]
                u_ = sum(u for u, _ in want)
                if u_ < umin:
                    why["few_units" if not carry else "not_needed"] += 1
                    continue
                why["cand"] += 1
                a, b = x["tile"], stops[pos]["tile"]
                sh = min(_TIER_SHED_I, key=lambda q: (D[a][q] + D[q][b], q))
                dl = {"tile": sh, "ops": [_tier_op(["DELIVER", p], True, 0.0, 2) for _, p in want], "rel": 0, "turn": True, "pdrop": True}
                trial = stops[:pos] + [dl] + stops[pos:]
                ev = _tier_eval(sg, trial, want_hours=True)
                add = ev[0] - ev0[0]
                if ev[0] > 24 or ev[1] > ev0[1] or ev[3] > ev0[3] or add > cap:
                    why["end" if ev[0] > 24 else "late" if ev[1] > ev0[1] else "supply" if ev[3] > ev0[3] else "cost"] += 1
                    continue
                if max(h for (b_, c_, h) in ev[4] if c_[0] == "DELIVER") > hmax:
                    why["hmax"] += 1
                    continue
                sc = (u_ / max(1, add), u_)
                if best is None or sc > best[0]:
                    best = (sc, trial, want, add)
            if best is None:
                break
            sg["stops"] = best[1]
            sg["ver"] += 1
            for u, p in best[2]:
                need[p] -= u
                rec_["units"][p] += u
            rec_["drops"] += 1
            rec_["cost"] += best[3]
            n += 1
    return n


def _tier_path_collect(segs, collects, st, budget):
    """sd_tier_path_collect: collects on the pens a planned route already passes (see the flag); returns the count."""
    D = _TIER_D
    n_ins = 0
    for sg in segs:
        if sg["kind"] not in ("out", "post", "ani") or not sg["stops"]:
            continue
        while budget[0] > 0 and collects:
            ev0 = _tier_eval(sg)
            if ev0[0] >= 24:
                break
            tiles_ = [sg["p0"]] + [x["tile"] for x in sg["stops"]]
            best = None
            for a, op in collects.items():
                if any(x["tile"] == a and any(o["c"][0] == "COLLECT_FERTILIZER" for o in x["ops"]) for x in sg["stops"]):
                    continue
                opts = []
                if any(x["tile"] == a for x in sg["stops"]):
                    opts.append(_tier_merge(sg["stops"], a, [op])[0])          # a pen the hand already stops at
                else:
                    for k in range(len(sg["stops"])):                           # a pen inside a leg's box: no detour
                        pa, pb = tiles_[k], tiles_[k + 1]
                        if D[pa][a] + D[a][pb] <= D[pa][pb] + 2 * int(CFG["sd_tier_path_collect_detour"]) and not sg["stops"][k].get("dawn"):
                            opts.append(_tier_merge(sg["stops"], a, [op], 0, k)[0])
                for st_ in opts:
                    ev = _tier_eval(sg, st_)
                    if ev[0] > 24 or ev[1] > ev0[1] or ev[3] > ev0[3]:
                        continue
                    key = (ev[0] - ev0[0], -float(op["v"]))
                    if best is None or key < best[0]:
                        best = (key, a, st_)
            if best is None:
                break
            _, a, st_ = best
            sg["stops"] = st_
            sg["ver"] += 1
            collects.pop(a, None)
            budget[0] -= 1
            n_ins += 1
    return n_ins


def _tier_anim_out(segs, idx, pool_a, pool_b, collects, anim, rate, st, spare=None, budget=None):
    """user idea (sd_tier_anim_out): an outbound hand whose planned day ends by 24 - spare feeds / cares / collects the
    animals lying on (or within sd_tier_anim_out_detour tiles of) a shortest path from its start to its first patch stop
    (the first stop off the animal tiles), inserted before that stop by value per added hour (detour 0 first); FEED /
    CARE come from the unplanned animal bundles (pool_a / pool_b), a COLLECT from the free collects within the per-hand
    cap (one more only at detour 0). The wheat pickup is the route's implicit one (+1 hour for its first FEED)."""
    D = _TIER_D
    dmax = 2 * int(CFG["sd_tier_anim_out_detour"])
    spare = int(CFG["sd_tier_anim_out_spare"]) if spare is None else int(spare)
    cap = int(CFG["sd_tier_coll_cap"])
    n_ins = 0
    for k in idx:
        sg = segs[k]
        if not sg["stops"]:
            continue
        ev0 = _tier_eval(sg)
        p0 = sg["p0"]
        kb = next((i for i, x in enumerate(sg["stops"]) if x["tile"] not in anim), None)
        if kb is None:
            continue
        b1 = sg["stops"][kb]["tile"]
        fcb = {}
        for pl in (() if CFG["sd_tier_anim_out_collect_only"] else (pool_a, pool_b)):
            for bd in pl:
                if bd["tile"] in anim and any(o["c"][0] in ("FEED", "CARE") for o in bd["ops"]):
                    fcb[bd["tile"]] = (pl, bd)
        cands = sorted((D[p0][a] + D[a][b1] - D[p0][b1],
                        -((fcb[a][1]["v"] if a in fcb else 0.0) + (collects[a]["v"] if a in collects else 0.0)), a)
                       for a in set(fcb) | set(collects))
        for det, _nv, a in cands:
            if det > dmax:
                break
            if ev0[0] > 24 - spare:
                break
            if budget is not None and budget[0] <= 0 and a in collects:
                break
            ops = []
            pb = fcb.get(a)
            if pb is not None:
                ops += [o for o in pb[1]["ops"] if o["c"][0] in ("FEED", "CARE")]
            use_c = False
            if a in collects:
                nc = sum(1 for x in sg["stops"] for o in x["ops"] if o["c"][0] == "COLLECT_FERTILIZER")
                if not cap or nc < cap or (nc == cap and det == 0):
                    ops.append(collects[a])
                    use_c = True
            if not ops:
                continue
            v = sum(o["v"] for o in ops)
            kb_now = next(i for i, x in enumerate(sg["stops"]) if x["tile"] == b1)
            if any(x["tile"] == a for x in sg["stops"][:kb_now]):
                opts = [_tier_merge(sg["stops"], a, ops)[0]]
            else:
                opts = [_tier_merge(sg["stops"], a, ops, 0, pos)[0] for pos in range(sg.get("lo", 0), kb_now + 1)]
            best = None
            for st_ in opts:
                ev = _tier_eval(sg, st_)
                if ev[1] > ev0[1] or ev[3] > ev0[3] or ev[0] > 24:
                    continue
                sc = v / max(0.25, ev[0] - ev0[0])
                if sc >= rate and (best is None or sc > best[0]):
                    best = (sc, st_, ev)
            if best is None:
                continue
            sg["stops"] = best[1]
            sg["ver"] += 1
            ev0 = best[2]
            n_ins += 1
            if pb is not None:
                pl, bd = pb
                bd["ops"] = [o for o in bd["ops"] if o["c"][0] not in ("FEED", "CARE")]
                bd["v"] = sum(o["v"] for o in bd["ops"])
                bd["bv"] = bd.get("bv", 0) + 1
                if not bd["ops"]:
                    pl.remove(bd)
                fcb.pop(a, None)
            if use_c:
                collects.pop(a, None)
                if budget is not None:
                    budget[0] -= 1
                for pl in (pool_a, pool_b):            # the tile's collect bundle is taken
                    for bd in list(pl):
                        if bd["tile"] == a and any(o["c"][0] == "COLLECT_FERTILIZER" for o in bd["ops"]):
                            bd["ops"] = [o for o in bd["ops"] if o["c"][0] != "COLLECT_FERTILIZER"]
                            bd["v"] = sum(o["v"] for o in bd["ops"])
                            bd["bv"] = bd.get("bv", 0) + 1
                            if not bd["ops"]:
                                pl.remove(bd)
    st["tier_anim_out"] = st.get("tier_anim_out", 0) + n_ins
    return n_ins


def _tier_pre(S, L, obs, step, day, hour, last_day, tiles, pos, invs, tasks, jobs, shed, seeds, prices, assign,
              deliv_u, fert_keep, demand):
    """hour 0: plan the whole day (S["tier"]); later hours: nothing (the plan is fixed)."""
    if hour != 0 or len(pos) != 1 or day >= last_day or (S.get("tier") or {}).get("day") == day:
        return
    t_start = time.perf_counter()
    st = L["st"]
    S["_shed_h0"] = dict(shed or {})
    want = _sd_want_hands(day)
    k0 = min(want, 10)
    vunits = [(q, 1) for q in _sd_spawn(pos, k0)] + [(q, 2) for q in _sd_spawn([], want - k0)]
    ctx = {"keep": set(), "stiles": set(), "mflag": {}, "obs": obs, "day": day, "hour": hour, "step": step,
           "tiles": tiles, "tasks": tasks, "invs": invs, "pos": pos, "shed": shed, "seeds": seeds, "assign": assign,
           "last_day": last_day, "jobs": jobs, "prices": prices, "deliv_u": deliv_u, "fert_keep": fert_keep,
           "demand": demand, "vunits": vunits}
    P = _sd_build(S, L, ctx)
    S["_tier_prices"] = dict(prices)
    S["_tier_last_day"] = last_day
    # ---- per-tile ops (pre job, then plan job), tiered
    rec = {}
    skipped = 0
    for j in range(P.J):
        key = P.key[j]
        if not P.real[j]:
            skipped += 1
            continue
        b = P.jb[j][0]
        ops = P.ops[j]
        vals = P.jb[j][7]
        hi = P.jb[j][10]
        r_ = rec.setdefault(b, {"ops": [], "rel": 0})
        r_["rel"] = max(r_["rel"], int(P.jb[j][9]))
        plant_seen = any(o["c"][0] == "PLANT" for o in r_["ops"])
        for i, o in enumerate(ops):
            c = o[0]
            if c == "PLANT":
                plant_seen = True
            nxt = ops[i + 1][0] if i + 1 < len(ops) else None
            if i == hi or c in ("PLANT", "DIG", "BUILD_COOP", "BUILD_PASTURE", "PLACE", "HARVEST"):
                m, tier = True, 2
            elif c == "WATER" and (plant_seen or nxt == "HARVEST"):
                m, tier = True, 2
            elif c in ("WATER", "FERTILIZE"):
                m, tier = False, 3
            else:
                m, tier = False, 4                 # FEED (not keep-alive), CARE, COLLECT_FERTILIZER
            v_ = vals[i] if i < len(vals) else 0.0
            if (c == "HARVEST" and CFG["sd_tier_anim_harv"] and i != hi and _animal(_tile(tiles, b))
                    and not _tier_anim_harv_needed(_tile(tiles, b), day)
                    and not (CFG["sd_tier_pen_round"] and int(CFG["sd_tier_pen_min"]) > 0
                             and min(_TIER_D[b][q] for q in _TIER_SHED_I) <= int(CFG["sd_tier_pen_radius"])
                             and int(_tile(tiles, b).get("yield_units", 0) or 0) >= int(CFG["sd_tier_pen_min"]))):
                t_ = _tile(tiles, b)          # animal thread: harvest deferred (nothing overflows tonight)
                m, tier = False, 4
                v_ = (float(t_.get("yield_units", 0) or 0) * float(prices.get(ANIMALS[t_["animal"]]["product"], 0) or 0)
                      * float(CFG["sd_tier_anim_harv_frac"]))
                st["tier_anim_harv_deferred"] = st.get("tier_anim_harv_deferred", 0) + 1
            if CFG["sd_glut_stop"] and not m and c in ("CARE", "FEED") and _animal(_tile(tiles, b)):
                t_g = _tile(tiles, b)
                if ANIMALS[t_g["animal"]]["product"] in (S.get("glut") or {}):
                    a_g = ANIMALS[t_g["animal"]]
                    dsf_g = day + 1 - int(t_g.get("placed_day", day)) - a_g["first"]
                    prod_g = dsf_g >= 0 and dsf_g % a_g["interval"] == 0
                    if c == "CARE" or not prod_g:
                        st["tier_glut_skipped_" + c] = st.get("tier_glut_skipped_" + c, 0) + 1
                        continue                       # DSM: a trickle of service once the product is glutted
            r_["ops"].append(_tier_op(o, m, v_, tier, after_plant=plant_seen and c == "WATER"))
    st["tier_pred_skipped"] = st.get("tier_pred_skipped", 0) + skipped
    if CFG["sd_collect_at_floor"] and day < last_day:   # the module emits no collect job at a $1 fertilizer quote
        fv_ = max(float(prices.get("FERTILIZER", 0) or 0), float(CFG["sd_collect_floor"] or 0))
        pens_ = [i_ for i_ in range(100) if _animal(_tile(tiles, i_)) and _tile(tiles, i_).get("fertilizer_available")
                 and not any(o["c"][0] == "COLLECT_FERTILIZER" for o in (rec.get(i_) or {}).get("ops", []))]
        if int(CFG["sd_collect_at_floor"]) >= 2:   # mode 2: only as many as the fertilizes still lacking a supply
            fz_ = [i_ for i_, r_ in rec.items() if any(o["c"][0] == "FERTILIZE" and o["v"] > 0 for o in r_["ops"])]
            have_ = sum(1 for r_ in rec.values() for o in r_["ops"] if o["c"][0] == "COLLECT_FERTILIZER")
            need_ = max(0, len(fz_) - have_)
            pens_ = sorted(pens_, key=lambda i_: min([_TIER_D[i_][j_] for j_ in fz_] or [99]))[:need_]
        for idx_ in pens_:
            r_ = rec.setdefault(idx_, {"ops": [], "rel": 0})
            r_["ops"].append(_tier_op(["COLLECT_FERTILIZER"], False, fv_, 4))
            st["tier_collect_at_floor"] = st.get("tier_collect_at_floor", 0) + 1
    if CFG["sd_harvest_follow_dsm"]:               # harvest days as DSM's (same tiles: the plan is followed tile-exact)
        hs_ = _T.harv_tiles[day] if day < len(getattr(_T, "harv_tiles", ())) else set()
        crops_ = set(CFG["sd_harvest_follow_dsm"])
        fr_ = st["_follow_day"] = {"dsm": sorted(hs_), "added": [], "marked": [], "held": []}
        for idx_ in range(100):
            t_ = _tile(tiles, idx_)
            an_ = _animal(t_) and t_.get("animal") in crops_
            if not ((_is_plant(t_) and t_.get("crop") in crops_) or an_):
                continue
            r_ = rec.get(idx_)
            has_ = bool(r_) and any(o["c"][0] == "HARVEST" for o in r_["ops"])
            if has_ and idx_ not in hs_ and _tier_defer_ok(t_, day, exact=bool(CFG["sd_follow_defer_exact"])):
                r_["ops"] = [o for o in r_["ops"] if o["c"][0] not in ("HARVEST", "PLACE_HARVEST")]
                st["tier_follow_held"] = st.get("tier_follow_held", 0) + 1
                fr_["held"].append(idx_)
            elif not has_ and idx_ in hs_ and int(t_.get("yield_units", 0) or 0) > 0 and (
                    an_ or day - int(t_.get("planted_day", day)) >= CROPS[t_["crop"]]["first"]):
                r_ = rec.setdefault(idx_, {"ops": [], "rel": 0})
                o_ = _tier_op(["HARVEST"], True, 0.0, 2)
                o_["follow"] = True
                r_["ops"].append(o_)
                st["tier_follow_added"] = st.get("tier_follow_added", 0) + 1
                fr_["added"].append(idx_)
            elif has_ and idx_ in hs_:
                for o_ in r_["ops"]:                # DSM harvests it today: the harvest is mandatory (an optional extra
                    if o_["c"][0] == "HARVEST":     # lost the labor competition: 112604454 day 17, pens 26 / 48)
                        o_["follow"] = True
                        if not o_["m"]:
                            o_["m"], o_["tier"] = True, 2
                            st["tier_follow_forced"] = st.get("tier_follow_forced", 0) + 1
                fr_["marked"].append(idx_)
        for idx_ in [i for i, r_ in rec.items() if not r_["ops"]]:
            del rec[idx_]
    if CFG["sd_maint_follow_dsm"]:                 # upkeep on DSM's tiles of the day (same board: the plan is tile-exact)
        lm_ = _T.maint[day] if day < len(getattr(_T, "maint", ())) else {}
        mf_ = st["_mfollow_day"] = Counter()
        drop_ = set(CFG["sd_maint_follow_drop"] or ())
        done_key_ = {"FEED": "fed_today", "CARE": "cared_today", "WATER": "watered_today"}
        for c_ in CFG["sd_maint_follow_dsm"]:
            dsm_t_ = set(lm_.get(c_, ()))
            for idx_ in range(100):
                t_ = _tile(tiles, idx_)
                if not (_animal(t_) if c_ in ("FEED", "CARE") else _is_plant(t_)):
                    continue
                if CFG["sd_maint_follow_kinds"] and (t_.get("animal") or t_.get("crop")) not in CFG["sd_maint_follow_kinds"]:
                    continue
                r_ = rec.get(idx_)
                ops_ = [o for o in (r_ or {}).get("ops", []) if o["c"][0] == c_]
                if idx_ in dsm_t_:
                    if ops_:
                        for o in ops_:
                            if not o["m"]:
                                o["m"], o["tier"] = True, 2
                                mf_["promoted_" + c_] += 1
                    elif c_ in done_key_ and not t_.get(done_key_[c_]):
                        r_ = rec.setdefault(idx_, {"ops": [], "rel": 0})
                        r_["ops"].append(_tier_op([c_], True, 0.0, 2))
                        mf_["added_" + c_] += 1
                elif c_ in drop_ and ops_ and all(not o["m"] for o in ops_):
                    r_["ops"] = [o for o in r_["ops"] if o["c"][0] != c_]
                    mf_["dropped_" + c_] += 1
        for idx_ in [i for i, r_ in rec.items() if not r_["ops"]]:
            del rec[idx_]
    if CFG["sd_keep_alive_guard"]:                 # R2 exact: no animal with >= 2 production nights left may escape
        for idx_ in range(100):
            t_ = _tile(tiles, idx_)
            if not _animal(t_) or int(t_.get("consecutive_unfed", 0) or 0) < 1:
                continue
            a_ = ANIMALS[t_["animal"]]
            left_ = sum(1 for k_ in range(day, 29) if (k_ + 1 - int(t_.get("placed_day", day)) - a_["first"]) >= 0
                        and (k_ + 1 - int(t_.get("placed_day", day)) - a_["first"]) % a_["interval"] == 0)
            if left_ < int(CFG["sd_keep_alive_guard_min"]):
                continue
            r_ = rec.setdefault(idx_, {"ops": [], "rel": 0})
            fd_ = [o for o in r_["ops"] if o["c"][0] == "FEED"]
            if fd_:
                for o in fd_:
                    if not o["m"]:
                        o["m"], o["tier"] = True, 2
                        st["tier_keepalive_forced"] = st.get("tier_keepalive_forced", 0) + 1
            else:
                r_["ops"].insert(0, _tier_op(["FEED"], True, 0.0, 2))
                st["tier_keepalive_added"] = st.get("tier_keepalive_added", 0) + 1
    if CFG["sd_tier_anim_mand_minv"] is not None:  # animal thread: valuable FEED / CARE are mandatory (tier B)
        _tier_anim_mand(rec, tiles, float(CFG["sd_tier_anim_mand_minv"]), st)
    if CFG["sd_tier_access_drop"]:                 # harvest on a shed-access tile -> put the product in the shed, sold at once
        for idx, r_ in rec.items():
            if not _is_shed_adjacent_t((idx % 10, idx // 10)):
                continue
            t_ = _tile(tiles, idx)
            if _animal(t_):
                prod_ = ANIMALS[t_["animal"]]["product"]
            elif _is_plant(t_):
                prod_ = t_.get("crop")
            else:
                continue
            new_ = []
            for o in r_["ops"]:
                new_.append(o)
                if o["c"][0] == "HARVEST":
                    o2 = _tier_op(["PLACE_HARVEST", prod_], o["m"], 1.0, o["tier"])
                    new_.append(o2)
                    st["tier_access_drop"] = st.get("tier_access_drop", 0) + 1
            r_["ops"] = new_
    if CFG["sd_tier_pen_bundle"]:                  # one service stop per pen (learned from DSM)
        nb_ = 0
        for idx, r_ in rec.items():
            t_ = _tile(tiles, idx)
            if not _animal(t_):
                continue
            a_ = ANIMALS[t_["animal"]]
            pd_ = int(t_.get("placed_day", day))
            prod_ = lambda n: (n + 1 - pd_ - a_["first"]) >= 0 and (n + 1 - pd_ - a_["first"]) % a_["interval"] == 0
            care_ok = any(prod_(n) for n in range(day + 1, last_day))
            cash_ = prod_(day) and int(t_.get("pending_care_bonus", 0) or 0) > 0
            has_care = care_ok and any(o["c"][0] == "CARE" for o in r_["ops"])
            hmin_ = int(CFG["sd_tier_pen_bundle_hmin"])
            for o in r_["ops"]:
                c_ = o["c"][0]
                if o["m"]:
                    continue
                if ((c_ == "COLLECT_FERTILIZER" and CFG["sd_tier_pen_bundle_collect"]) or (c_ == "CARE" and care_ok) or (c_ == "FEED" and (has_care or cash_))
                        or (c_ in ("HARVEST", "PLACE_HARVEST") and hmin_ > 0 and int(t_.get("yield_units", 0) or 0) >= hmin_)):
                    o["m"], o["tier"], o["pb"] = True, 2, True
                    nb_ += 1
        st["tier_pen_bundle_ops"] = st.get("tier_pen_bundle_ops", 0) + nb_
    if int(CFG["sd_tier_feed_bank"]) > 0:         # protect the bank: feed on the production day
        for idx, r_ in rec.items():
            t_ = _tile(tiles, idx)
            if not _animal(t_) or t_.get("fed_today"):
                continue
            a_ = ANIMALS[t_["animal"]]
            dsf_ = day + 1 - int(t_.get("placed_day", day)) - a_["first"]
            if dsf_ < 0 or dsf_ % a_["interval"] != 0 or int(t_.get("pending_care_bonus", 0) or 0) < int(CFG["sd_tier_feed_bank"]):
                continue
            for o in r_["ops"]:
                if o["c"][0] == "FEED" and not o["m"]:
                    o["m"], o["tier"] = True, 2
                    st["tier_feed_bank"] = st.get("tier_feed_bank", 0) + 1
    if int(CFG["sd_tier_goose_care"]) > 0:        # KWE: goose CARE with the FEED
        _tier_goose_care(rec, tiles, day, last_day, prices, st)
    if CFG["sd_exact_retire"] and CFG["sd_exact_retire_prefeed"] and not CFG["sd_clean_plan"]:
        for idx_ in S.get("_xfeed") or ():
            r_ = rec.setdefault(idx_, {"ops": [], "rel": 0})
            fd_ = [o for o in r_["ops"] if o["c"][0] == "FEED"]
            for o in fd_:
                o["m"], o["tier"] = True, 2
            if not fd_:
                r_["ops"].insert(0, _tier_op(["FEED"], True, 0.0, 2))
            st["xretire_prefeed"] = st.get("xretire_prefeed", 0) + 1
    if (CFG["sd_exact_retire"] or CFG["sd_own_retire"]) and S.get("_xretire"):   # DSM's escapes copied / sd_own_retire (after every feed-forcing pass)
        for idx_, tonight_ in S["_xretire"].items():
            t_ = _tile(tiles, idx_)
            r_ = rec.get(idx_)
            if r_:
                n0_ = len(r_["ops"])
                r_["ops"] = [o for o in r_["ops"] if o["c"][0] not in ("FEED", "CARE")]
                st["xretire_dropped"] = st.get("xretire_dropped", 0) + n0_ - len(r_["ops"])
            if tonight_ and int(t_.get("yield_units", 0) or 0) > 0:
                r_ = rec.setdefault(idx_, {"ops": [], "rel": 0})
                hv_ = [o for o in r_["ops"] if o["c"][0] == "HARVEST"]
                for o in hv_:
                    o["m"], o["tier"] = True, 2
                if not hv_:
                    r_["ops"].append(_tier_op(["HARVEST"], True, 0.0, 2))
                    st["xretire_harvest_added"] = st.get("xretire_harvest_added", 0) + 1
            st["xretire_animals"] = st.get("xretire_animals", 0) + 1
        for idx_ in [i for i, r_ in rec.items() if not r_["ops"]]:
            del rec[idx_]
    if CFG["sd_wheat_h3_opt"]:                     # the day-3 wheat harvest (and its water) optional, by value
        pw_ = float((prices or {}).get("WHEAT", 0) or 0)
        fr_ = float(CFG["sd_wheat_h3_frac"])
        for idx_, r_ in rec.items():
            t_ = _tile(tiles, idx_)
            if not (_is_plant(t_) and t_.get("crop") == "WHEAT"):
                continue
            job_ = jobs.get(idx_)
            if job_ and job_[0] in ("PLANT", "BUILD"):
                continue                          # the tile is replanted / built today: as planned
            if (day - int(t_.get("planted_day", day)) >= CROPS["WHEAT"]["maxday"] or day >= last_day - 1
                    or not _tier_defer_ok(t_, day, exact=True)):
                continue
            hv_ = [o for o in r_["ops"] if o["c"][0] == "HARVEST" and o["m"]]
            if not hv_:
                continue
            wat_ = any(o["c"][0] == "WATER" for o in r_["ops"]) and not t_.get("watered_today")
            bonus_ = (2 if int(t_.get("fertilized_until_day", -1)) >= day else 1) if wat_ else 0
            units_ = min(CROPS["WHEAT"]["max"], int(t_.get("yield_units", 0) or 0) + bonus_)
            hard_ = int(t_.get("consecutive_unwatered", 0) or 0) >= 1 and not t_.get("watered_today")
            for o in r_["ops"]:
                c_ = o["c"][0]
                if c_ == "HARVEST" and o["m"]:
                    o["m"], o["tier"], o["v"] = False, 3, max(1.0, fr_ * units_ * pw_)
                elif c_ == "PLACE_HARVEST" and o["m"]:
                    o["m"], o["tier"], o["v"] = False, 3, max(1.0, float(o["v"]))
                elif c_ == "WATER" and o["m"] and o["rank"] == _TIER_RANK["WATER"] and not hard_:
                    o["m"], o["tier"], o["v"] = False, 3, max(0.5, float(CFG["sd_wheat_h3_wv"]) * bonus_ * pw_)
            st["wheat_h3_opt"] = st.get("wheat_h3_opt", 0) + 1
    if CFG["sd_wheat_d3"]:                         # wheat harvests by value: day 3 only with a replant, else the last full day
        pw_ = float((prices or {}).get("WHEAT", 0) or 0)
        for idx_ in range(100):
            t_ = _tile(tiles, idx_)
            if _is_plant(t_) and t_.get("crop") == "WHEAT" and (jobs.get(idx_) or (None,))[-1] == "d3":
                rec.setdefault(idx_, {"ops": [], "rel": 0})
            r_ = rec.get(idx_)
            if not (r_ and _is_plant(t_) and t_.get("crop") == "WHEAT"):
                continue
            if not any(o["c"][0] == "HARVEST" for o in r_["ops"]) and not (jobs.get(idx_) or (None,))[-1] == "d3":
                continue
            job_ = jobs.get(idx_)
            hold_ = (_tier_defer_ok(t_, day, exact=True) and day < last_day - 1
                     and day - int(t_.get("planted_day", day)) < CROPS["WHEAT"]["maxday"])
            if job_ and job_[0] == "PLANT" and not (len(job_) > 3 and job_[3] == "d3"):
                continue                          # DSM replants today: harvest + plant as planned
            if job_ and len(job_) > 3 and job_[3] == "d3" and not hold_:
                continue                          # last full day: the replant job stays mandatory (below)
            if not hold_:
                continue
            n0_ = len(r_["ops"])
            r_["ops"] = [o for o in r_["ops"] if o["c"][0] not in ("HARVEST", "PLACE_HARVEST")]
            st["wheat_d3_held"] = st.get("wheat_d3_held", 0) + (1 if len(r_["ops"]) < n0_ else 0)
            if job_ and len(job_) > 3 and job_[3] == "d3":
                if not t_.get("watered_today"):   # the day-3 water is mandatory (the day-4 path needs it too)
                    wo_ = [o for o in r_["ops"] if o["c"][0] == "WATER"]
                    for o in wo_:
                        o["m"], o["tier"] = True, 2
                    if not wo_:
                        r_["ops"].append(_tier_op(["WATER"], True, 0.0, 2))
                v3_ = float(CFG["sd_wheat_d3_v"]) * pw_ / 3.0
                r_["ops"] = [o for o in r_["ops"] if o["c"][0] != "FERTILIZE"]
                r_["ops"] += [_tier_op(["HARVEST"], False, v3_, 3), _tier_op(["PLANT", "WHEAT"], False, v3_, 3),
                              _tier_op(["WATER"], False, v3_, 3, after_plant=True)]
                r_["ops"] = sorted(r_["ops"], key=lambda o: o["rank"])
                r_["d3"] = True
                st["wheat_d3_bundles"] = st.get("wheat_d3_bundles", 0) + 1
        for idx_ in [i for i, r_ in rec.items() if not r_["ops"]]:
            del rec[idx_]
    # ---- the leader's plan for today that the hour-0 task list does not show yet (seeds / animals bought later)
    added = 0
    for idx, job in sorted(jobs.items()):
        if not job:
            continue
        if (rec.get(idx) or {}).get("d3"):
            continue                              # sd_wheat_d3: the optional day-3 bundle replaces the plan job
        r_ = rec.setdefault(idx, {"ops": [], "rel": 0})
        cm = [o["c"][0] for o in r_["ops"]]
        t = _tile(tiles, idx)
        pre = []
        if job[0] in ("PLANT", "BUILD") and not any(c in ("PLANT", "BUILD_COOP", "BUILD_PASTURE") for c in cm):
            if t is None:
                pre = []
            elif _is_plant(t):
                c_ = CROPS.get(t.get("crop"), {})
                ripe_ = (int(t.get("yield_units", 0) or 0) > 0
                         and day - int(t.get("planted_day", day)) >= c_.get("first", 99))
                if "HARVEST" in cm:
                    pre = [["DIG"]] if c_.get("ongoing") else []
                elif ripe_ and not c_.get("ongoing"):
                    pre = [["HARVEST"]]
                elif CFG["sd_exact_site"] and ripe_ and c_.get("ongoing"):
                    pre = [["HARVEST"], ["DIG"]]     # sd_exact_site: take the units, then dig
                else:
                    pre = [["DIG"]]
                if CFG["sd_exact_site"] and t.get("crop") != (job[1] if job[0] == "PLANT" else None):
                    r_["ops"] = [o for o in r_["ops"] if o["c"][0] not in ("WATER", "FERTILIZE")]   # the plant is replaced
            elif isinstance(t, dict) and "animal" not in t:
                pre = [["DIG"]]
            new = [_tier_op(o, True, 0.0, 2) for o in pre]
            if CFG["sd_exact_site"]:
                for o in new:
                    if o["c"][0] == "DIG":
                        o["rank"] = 6.7              # after HARVEST / PLACE_HARVEST (DIG ranks first otherwise)
            if job[0] == "PLANT":
                new += [_tier_op(["PLANT", job[1]], True, float(CFG["plan_value"]), 2),
                        _tier_op(["WATER"], True, 0.0, 2, after_plant=True)]
            else:
                new += [_tier_op(["BUILD_" + job[1]], True, 0.0, 2)]
                if len(job) > 2 and job[2] in ANIMALS:
                    new += [_tier_op(["PLACE", job[2]], True, float(CFG["plan_value"]), 2)]
            r_["ops"] = sorted(r_["ops"] + new, key=lambda o: o["rank"])
            added += 1
    st["tier_plan_added"] = st.get("tier_plan_added", 0) + added
    if CFG["sd_tier_fert_skip_harv"]:              # a fertilize is wasted where the crop is harvested (one-time) or replaced today
        nd_ = 0
        for idx, r_ in rec.items():
            cm = [o["c"][0] for o in r_["ops"]]
            if "FERTILIZE" not in cm:
                continue
            t = _tile(tiles, idx)
            onetime = _is_plant(t) and not CROPS.get(t.get("crop"), {}).get("ongoing", True)
            if ("HARVEST" in cm and onetime) or any(c in ("PLANT", "DIG", "BUILD_COOP", "BUILD_PASTURE") for c in cm):
                r_["ops"] = [o for o in r_["ops"] if o["c"][0] != "FERTILIZE"]
                nd_ += 1
        st["tier_fert_dropped"] = st.get("tier_fert_dropped", 0) + nd_
    if CFG["sd_tier_fert_exact"]:
        _tier_fert_exact(rec, tiles, day, prices, st)
    if int(CFG["sd_path_planner"]) or CFG["sd_anim_value_exact"]:   # care / feed by their engine effect
        _tier_anim_value(rec, tiles, day, last_day, prices, st, replace=bool(CFG["sd_anim_value_exact"]))
    if CFG["sd_wheat_fert_mand"]:                  # every wheat plant fertilized at age 2 (mandatory, shed-supplied)
        for idx_ in range(100):
            t_ = _tile(tiles, idx_)
            if not (_is_plant(t_) and t_.get("crop") == "WHEAT") or day >= last_day - 1:
                continue
            if day - int(t_.get("planted_day", day)) != 2 or int(t_.get("fertilized_until_day", -1)) >= day:
                continue
            r_ = rec.setdefault(idx_, {"ops": [], "rel": 0})
            cm_ = [o["c"][0] for o in r_["ops"]]
            if any(c_ in ("HARVEST", "PLANT", "DIG", "BUILD_COOP", "BUILD_PASTURE") for c_ in cm_):
                continue                          # harvested / replaced today
            fz_ = [o for o in r_["ops"] if o["c"][0] == "FERTILIZE"]
            for o in fz_:
                o["m"], o["tier"] = True, 2
            if not fz_:
                r_["ops"].append(_tier_op(["FERTILIZE"], True, 1.0, 2))
            if not t_.get("watered_today"):
                wo_ = [o for o in r_["ops"] if o["c"][0] == "WATER"]
                for o in wo_:
                    o["m"], o["tier"] = True, 2
                if not wo_:
                    r_["ops"].append(_tier_op(["WATER"], True, 0.0, 2))
            r_["ops"].sort(key=lambda o: o["rank"])
            st["wheat_fert_mand"] = st.get("wheat_fert_mand", 0) + 1
    if CFG["sd_water_useless_zero"]:               # no optional water before a one-time crop's window
        nz_ = 0
        for idx_, r_ in rec.items():
            t_ = _tile(tiles, idx_)
            if not (_is_plant(t_) and t_.get("crop") in ("WHEAT", "CARROT")) or t_.get("watered_today"):
                continue
            cd_ = CROPS[t_["crop"]]
            if (day - int(t_.get("planted_day", day)) >= (cd_["maxday"] + 1) // 2
                    or int(t_.get("consecutive_unwatered", 0) or 0) >= 1):
                continue
            n0_ = len(r_["ops"])
            r_["ops"] = [o for o in r_["ops"] if not (o["c"][0] == "WATER" and not o["m"] and o["rank"] == _TIER_RANK["WATER"])]
            nz_ += n0_ - len(r_["ops"])
        st["water_useless_dropped"] = st.get("water_useless_dropped", 0) + nz_
        for idx_ in [i for i, r_ in rec.items() if not r_["ops"]]:
            del rec[idx_]
    if CFG["sd_keepalive_wheat"]:                  # wheat keep-alive water: the wheat it saves + one action, optional
        pw_ = float((prices or {}).get("WHEAT", 0) or 0)
        lab_ = float(CFG["sd_labor_price"])
        cw_ = CROPS["WHEAT"]
        for idx_, r_ in rec.items():
            t_ = _tile(tiles, idx_)
            if not (_is_plant(t_) and t_.get("crop") == "WHEAT") or t_.get("watered_today"):
                continue
            if int(t_.get("consecutive_unwatered", 0) or 0) < 1:
                continue
            if any(o["c"][0] in ("HARVEST", "PLANT", "DIG", "BUILD_COOP", "BUILD_PASTURE") for o in r_["ops"]):
                continue                          # harvested / replaced today
            age_ = day - int(t_.get("planted_day", day))
            bonus_ = ((2 if int(t_.get("fertilized_until_day", -1)) >= day else 1)
                      if (cw_["maxday"] + 1) // 2 <= age_ <= cw_["maxday"] else 0)
            v_ = min(cw_["max"], int(t_.get("yield_units", 0) or 0) + bonus_) * pw_ + lab_
            for o in r_["ops"]:
                if o["c"][0] == "WATER" and o["m"] and o["rank"] == _TIER_RANK["WATER"]:
                    o["m"], o["tier"], o["v"] = False, 3, v_
                    st["keepalive_wheat"] = st.get("keepalive_wheat", 0) + 1
    if CFG["sd_tier_straw_fert_days"]:             # user: very high weight on the cycle's fertilize days (9, 13)
        fdays_ = set(int(x) for x in CFG["sd_tier_straw_fert_days"])
        for idx, r_ in rec.items():
            t_ = _tile(tiles, idx)
            if _is_plant(t_) and t_.get("crop") == "STRAWBERRY" and day - int(t_.get("planted_day", day)) in fdays_:
                for o in r_["ops"]:
                    if o["c"][0] == "FERTILIZE" and not o["m"]:
                        o["v"] = float(o["v"]) * float(CFG["sd_tier_straw_fert_day_mult"])
                        st["tier_straw_fert_day"] = st.get("tier_straw_fert_day", 0) + 1
    if CFG["sd_tier_straw_odd_water"]:             # user: strawberry waters staggered from the fertilize days (odd days since planting)
        pr_s_ = float(prices.get("STRAWBERRY", 0) or 0)
        cds_ = CROPS["STRAWBERRY"]
        for idx in range(100):
            t_ = _tile(tiles, idx)
            if not (_is_plant(t_) and t_.get("crop") == "STRAWBERRY"):
                continue
            off_ = day - int(t_.get("planted_day", day))
            if off_ <= 0 or t_.get("watered_today"):
                continue
            r_ = rec.get(idx)
            wops_ = [o for o in (r_ or {}).get("ops", []) if o["c"][0] == "WATER"]
            if off_ % 2 == 1:
                k_ = off_ + 1 - cds_["first"]
                prod_ = k_ >= 0 and k_ % cds_["interval"] == 0 and k_ // cds_["interval"] + 1 <= cds_["max"]
                fz_ = int(t_.get("fertilized_until_day", -1) or -1) >= day or any(
                    o["c"][0] == "FERTILIZE" for o in (r_ or {}).get("ops", []))
                v_ = max(float(CFG["sd_tier_straw_odd_water_v"]), pr_s_ if (prod_ and fz_) else 0.0)
                if wops_:
                    for o in wops_:
                        if not o["m"] and o["v"] < v_:
                            o["v"] = v_
                else:
                    rec.setdefault(idx, {"ops": [], "rel": 0})["ops"].append(_tier_op(["WATER"], False, v_, 3))
                    st["tier_straw_odd_added"] = st.get("tier_straw_odd_added", 0) + 1
            elif r_ is not None and any(not o["m"] for o in wops_):
                r_["ops"] = [o for o in r_["ops"] if not (o["c"][0] == "WATER" and not o["m"])]
                st["tier_straw_even_dropped"] = st.get("tier_straw_even_dropped", 0) + 1
        for idx_ in [i for i, r_ in rec.items() if not r_["ops"]]:
            del rec[idx_]
    if float(CFG["sd_tier_straw_fert_mult"]) != 1.0:   # user: more value on strawberry fertilization
        for idx, r_ in rec.items():
            t_ = _tile(tiles, idx)
            if _is_plant(t_) and t_.get("crop") == "STRAWBERRY":
                for o in r_["ops"]:
                    if o["c"][0] == "FERTILIZE" and not o["m"]:
                        o["v"] = float(o["v"]) * float(CFG["sd_tier_straw_fert_mult"])
    if CFG["sd_tier_water_exact"]:                 # extra waterings valued by engine rules (user: shift the weights)
        nw_ = 0
        for idx, r_ in rec.items():
            t_ = _tile(tiles, idx)
            if not _is_plant(t_) or t_.get("watered_today"):
                continue
            cr_ = CROPS.get(t_.get("crop"))
            if not cr_:
                continue
            y_ = int(t_.get("yield_units", 0) or 0)
            fz_ = int(t_.get("fertilized_until_day", -1) or -1) >= day
            age_ = day - int(t_.get("planted_day", day))
            gain_ = 0
            if not cr_["ongoing"]:
                if (cr_["maxday"] + 1) // 2 <= age_ <= cr_["maxday"]:
                    gain_ = min(cr_["max"], y_ + (2 if fz_ else 1)) - y_
            else:
                ds_ = age_ + 1 - cr_["first"]
                itv_ = max(1, int(cr_.get("interval", 1) or 1))
                if ds_ >= 0 and ds_ % itv_ == 0 and ds_ // itv_ + 1 <= cr_["max"] and fz_:
                    gain_ = min(cr_["max"], y_ + 2) - min(cr_["max"], y_ + 1)
            v_ = gain_ * float(prices.get(t_["crop"], 0) or 0) + float(CFG["sd_water_tomorrow"] or 0)
            for o in r_["ops"]:
                if o["c"][0] == "WATER" and not o["m"]:
                    o["v"] = v_
                    nw_ += 1
        st["tier_water_exact"] = st.get("tier_water_exact", 0) + nw_
    if CFG["sd_tier_straw_water"] is not None:
        sw_ = float(CFG["sd_tier_straw_water"])
        for idx, r_ in rec.items():
            t = _tile(tiles, idx)
            if _is_plant(t) and t.get("crop") == "STRAWBERRY":
                for o in r_["ops"]:
                    if o["c"][0] == "WATER" and not o["m"] and o["v"] < sw_:
                        o["v"] = sw_
    # ---- wheat for today's feeds (keep-alive and animal work): what the shed lacks is bought at hour 0, first in the order
    # list (it lands before the hour-1 pickups), which moves one hour-0 hire to hour 1
    wbuy = 0
    if CFG["sd_tier_wheat"]:
        nfeed = sum(1 for r_ in rec.values() for o in r_["ops"] if o["c"][0] == "FEED")
        have_w = int(shed.get("WHEAT", 0) or 0) + int((invs[0] if invs else {}).get("WHEAT", 0) or 0)
        wbuy = max(0, nfeed - have_w)
        if wbuy and want >= 10:
            k0 = 9
    front = []
    stock_h0 = {p_: int(shed.get(p_, 0) or 0) for p_ in (CFG["sd_h0_front"] or [])}
    if CFG["sd_hourly_profile"] and CFG["sd_h0_front"]:   # only the pattern's hour-0 share counts
        d_ = min(day, _T.n - 1)
        for p_ in list(stock_h0):
            if p_ in CFG["sd_hourly_profile"]:
                prev_ = _T.cum_sold[d_ - 1].get(p_, 0) if d_ >= 1 else 0
                q0_ = int(prev_ + float(CFG["sd_hourly_profile"][p_][0]) * (_T.cum_sold[d_].get(p_, 0) - prev_) - S["sold"][p_])
                stock_h0[p_] = max(0, min(stock_h0[p_], q0_))
    if CFG["sd_h0_front"]:                         # hour-0 sale of the largest pile, first in the order list
        cand_ = sorted(((stock_h0[p_] * float(prices.get(p_, 0) or 0), p_) for p_ in CFG["sd_h0_front"]
                        if stock_h0[p_] >= int(CFG["sd_h0_front_min"])), reverse=True)
        front = [p_ for _, p_ in cand_[:int(CFG["sd_h0_front_n"])]]
        if float(CFG["sd_h0_front_gain"]) > 0:     # per-product expected gain against the cost of a delayed hire
            ed_ = S.setdefault("h0edge", dict(CFG["sd_h0_front_edge0"] or {}))
            gl_ = sorted(((stock_h0[p_] * float(ed_.get(p_, 0.0)), p_) for p_ in CFG["sd_h0_front"]
                          if stock_h0[p_] > 0), reverse=True)
            free_ = max(0, 10 - k0 - (1 if wbuy else 0))
            front = [p_ for i_, (g_, p_) in enumerate(gl_) if (g_ > 0 if i_ < free_ else g_ >= float(CFG["sd_h0_front_gain"]))]
            S["h0q"] = {"day": day, "q": {p_: float(prices.get(p_, 0) or 0) for p_ in CFG["sd_h0_front"]}, "sold": list(front)}
        if front:
            k0 = min(k0, 10 - len(front) - (1 if wbuy else 0))
    nb0 = 0
    if int(CFG["sd_books_h0_slots"]) and CFG["sd_books_sell"] and CFG["sd_books_source"] not in ("hazard", "pace"):
        cum_b_ = _books_cum(S)                     # the plan's hour-0 sells (the market block's own count, before its walk cap)
        if cum_b_ is not None:
            inv_b_ = dict(_g(_g(obs, "market", {}), "inventory", {}) or {})
            for p_ in sorted(set(CFG["sd_books_sell"])):
                n_ = min(int(shed.get(p_, 0) or 0), int((cum_b_.get(day * 24) or {}).get(p_, 0)) - int(S["sold"][p_]))
                if int(CFG["sd_books_h0_lot"]):
                    n_ = min(n_, int((cum_b_.get(day * 24) or {}).get(p_, 0)) - int((cum_b_.get(day * 24 - 1) or {}).get(p_, 0)))
                if n_ > 0 and CFG["sd_books_walk"] and p_ in inv_b_:
                    n_ = _walk_cap(p_, int(inv_b_[p_]), float(CFG["sd_books_minpx"]), n_)
                nb0 += 1 if n_ > 0 else 0
            nb0 = min(nb0, int(CFG["sd_books_h0_slots"]))
            if nb0:
                k0 = max(0, min(k0, 10 - nb0 - len(front) - (1 if wbuy else 0)))
    if int(CFG["sd_books_h0_slots"]) and CFG["sd_books_sell"] and CFG["sd_books_source"] == "pace":
        P_ = _pace_tables()                        # DSM-free: the learned pace's hour-0 sells get their slots too
        ph_ = "early" if day <= 17 else ("mid" if day <= 23 else "late")
        inv_b_ = dict(_g(_g(obs, "market", {}), "inventory", {}) or {})
        for p_ in sorted(set(CFG["sd_books_sell"])):
            n_ = min(int(shed.get(p_, 0) or 0), int(round(float(P_["p1"].get("%s|%s|0" % (p_, ph_), 0.0)) * int(shed.get(p_, 0) or 0))))
            if n_ > 0 and CFG["sd_books_walk"] and p_ in inv_b_:
                n_ = _walk_cap(p_, int(inv_b_[p_]), float(CFG["sd_books_minpx"]), n_)
            nb0 += 1 if n_ > 0 else 0
        nb0 = min(nb0, int(CFG["sd_books_h0_slots"]))
        if nb0:
            k0 = max(0, min(k0, 10 - nb0 - len(front) - (1 if wbuy else 0)))
    # ---- units: farmer (hour 0) + the day's hires (hour 1; beyond 10 hour 2). The hires spawn after the farmer's hour-0
    # command (least occupied shed tile), the late ones after everyone's hour-1 command: plan, derive the spawn tiles the
    # plan's own first moves imply, re-plan until they agree (at most 3 passes)
    import copy as _tier_copy
    f0 = tuple(pos[0])
    ft0 = 0
    if CFG["sd_tier_farmer_hold"] and min(_dist(f0, q) for q in SHED) <= 1:
        ft0 = 1                                    # on / next to the shed: he holds at hour 0, so the hires' spawn is known
    if int(CFG["sd_tier_dawn"]) == 3 and f0 in SHED and any(
            int(tr[0]) == 0 and int(tr[1]) == 0 for tr in (_dawn_shape(day, tiles).get(str(day)) or [])):
        ft0 = 0                                    # sd_tier_dawn 3: DSM's farmer makes his early trip from hour 0
    sp0 = _sd_spawn([f0] if ft0 else ([] if f0 in SHED else [f0]), k0)
    sp1 = _sd_spawn([], want - k0)
    st["_hold0"] = bool(int(CFG["sd_tier_farmer_h0pick"]) and ft0 == 1 and f0 in SHED)
    TP = None
    for pass_ in range(int(CFG["sd_tier_spawn_passes"])):
        units = [(0, f0, ft0)] + [(u + 1, q, 1) for u, q in enumerate(sp0)] + [
            (u + 1 + k0, q, 2) for u, q in enumerate(sp1)]
        TP = _tier_core(S, L, st, day, tiles, _tier_copy.deepcopy(rec), units, want, t_start)
        if 0 in TP["routes"]:
            TP["routes"][0]["t0"] = 0 if TP["routes"][0].get("hold0") else ft0
        f1 = f0 if ft0 else _tier_walk(TP["routes"].get(0), f0, 1)
        n0 = _sd_spawn([f1], k0)
        TP["summary"]["spawn_pass"] = pass_ + 1
        if n0 == sp0:
            break
        sp0 = n0
        st["tier_respawn"] = st.get("tier_respawn", 0) + 1
    after1 = [_tier_walk(TP["routes"].get(0), f0, _tier_f_cmds(TP["routes"].get(0), f0, ft0))] + [
        _tier_walk(TP["routes"].get(u + 1), q, 1) for u, q in enumerate(sp0)]
    if int(CFG["sd_tier_spawn_exact"]) >= 2 and TP.get("_sp1_true") is not None:
        for pass3_ in range(2):                    # feed the exact tiles back into the search; keep the fewest mismatches
            if not TP.get("_spx_wrong"):
                break
            sp1_try = [tuple(q) for q in TP["_sp1_true"]]
            units = [(0, f0, ft0)] + [(u + 1, q, 1) for u, q in enumerate(sp0)] + [
                (u + 1 + k0, q, 2) for u, q in enumerate(sp1_try)]
            TP2 = _tier_core(S, L, st, day, tiles, _tier_copy.deepcopy(rec), units, want, t_start)
            if 0 in TP2["routes"]:
                TP2["routes"][0]["t0"] = 0 if TP2["routes"][0].get("hold0") else ft0
            st["tier_spawn_exact_replan"] = st.get("tier_spawn_exact_replan", 0) + 1
            if TP2.get("_sp1_true") is not None and (TP2.get("_spx_wrong") or 0) <= (TP.get("_spx_wrong") or 0):
                TP = TP2
            else:
                break
        after1 = [_tier_walk(TP["routes"].get(0), f0, _tier_f_cmds(TP["routes"].get(0), f0, ft0))] + [
            _tier_walk(TP["routes"].get(u + 1), q, 1) for u, q in enumerate(sp0)]
        TP["summary"]["spx_wrong_final"] = TP.get("_spx_wrong")
    if int(CFG["sd_tier_spawn_exact"]) and TP.get("_sp1_true") is not None:
        sp1 = [tuple(q) for q in TP["_sp1_true"]]  # the core planned the hour-1 hires from these (consistent by construction)
        if _sd_spawn(after1, want - k0) != sp1:
            st["tier_spawn_exact_off"] = st.get("tier_spawn_exact_off", 0) + 1
    if want > k0 and _sd_spawn(after1, want - k0) != sp1:
        st["tier_spawn_h2_off"] = st.get("tier_spawn_h2_off", 0) + 1
        if CFG["sd_tier_spawn_h2"]:                # re-plan the hour-1 hires from the tiles they will really spawn on
            for pass2_ in range(2):
                sp1 = _sd_spawn(after1, want - k0)
                units = [(0, f0, ft0)] + [(u + 1, q, 1) for u, q in enumerate(sp0)] + [
                    (u + 1 + k0, q, 2) for u, q in enumerate(sp1)]
                TP = _tier_core(S, L, st, day, tiles, _tier_copy.deepcopy(rec), units, want, t_start)
                if 0 in TP["routes"]:
                    TP["routes"][0]["t0"] = 0 if TP["routes"][0].get("hold0") else ft0
                    if TP["routes"][0].get("kind") != "post":
                        TP["routes"][0]["wt0"] = max(ft0, 1)
                after1 = [_tier_walk(TP["routes"].get(0), f0, _tier_f_cmds(TP["routes"].get(0), f0, ft0))] + [
                    _tier_walk(TP["routes"].get(u + 1), q, 1) for u, q in enumerate(sp0)]
                st["tier_spawn_h2_replan"] = st.get("tier_spawn_h2_replan", 0) + 1
                if _sd_spawn(after1, want - k0) == sp1:
                    break
            if CFG["sd_tier_spawn_buffer"] and _sd_spawn(after1, want - k0) != sp1:
                sp1 = _sd_spawn(after1, want - k0)     # still unsettled: plan the hour-1 hires with an hour of slack
                units = [(0, f0, ft0)] + [(u + 1, q, 1) for u, q in enumerate(sp0)] + [
                    (u + 1 + k0, q, 3) for u, q in enumerate(sp1)]
                TP = _tier_core(S, L, st, day, tiles, _tier_copy.deepcopy(rec), units, want, t_start)
                if 0 in TP["routes"]:
                    TP["routes"][0]["t0"] = 0 if TP["routes"][0].get("hold0") else ft0
                    if TP["routes"][0].get("kind") != "post":
                        TP["routes"][0]["wt0"] = max(ft0, 1)
                for u_ in range(k0 + 1, want + 1):
                    if u_ in TP["routes"]:
                        TP["routes"][u_]["t0plan"] = 2       # they still act from hour 2 (the executor starts them then)
                        TP["routes"][u_]["t0"] = 0
                after1 = [_tier_walk(TP["routes"].get(0), f0, _tier_f_cmds(TP["routes"].get(0), f0, ft0))] + [
                    _tier_walk(TP["routes"].get(u + 1), q, 1) for u, q in enumerate(sp0)]
                st["tier_spawn_buffer"] = st.get("tier_spawn_buffer", 0) + 1
    if CFG["sd_tier_dawn_cf"] and int(CFG["sd_tier_dawn"]):   # same state, same units, dawn legs off (diagnosis)
        units_cf = [(0, f0, TP["routes"][0]["t0"] if 0 in TP["routes"] else ft0)] + [
            (u + 1, q, 1) for u, q in enumerate(sp0)] + [(u + 1 + k0, q, 2) for u, q in enumerate(sp1)]
        if 0 in TP["routes"] and int(CFG["sd_tier_dawn"]) == 3 and TP["routes"][0]["t0"] == 0 and CFG["sd_tier_farmer_hold"] \
                and min(_dist(f0, q) for q in SHED) <= 1:
            units_cf[0] = (0, f0, 1)               # without the DSM trip the farmer would have held at hour 0
        mode_ = CFG["sd_tier_dawn"]
        try:
            CFG["sd_tier_dawn"] = 0
            TPc = _tier_core(S, L, {}, day, tiles, _tier_copy.deepcopy(rec), units_cf, want, t_start)
        finally:
            CFG["sd_tier_dawn"] = mode_
        TP["summary"]["cf"] = {"units": [{"u": x["u"], "end": x["end"], "late": x["late"], "stops": x.get("stops_v") or x["stops"]}
                                         for x in TPc["summary"]["units"]],
                               "unplanned": TPc["summary"]["unplanned"], "mand_late": TPc["summary"]["mand_late"]}
    if TP.get("_pol") is not None:               # sd_polish_final: once, on the plan the passes kept
        segs_p, rest_p, build_p = TP["_pol"]
        _tier_polish(S, segs_p, rest_p, tiles, day, st)
        if (st.get("_polish_day") or {}).get("committed"):
            by_u_ = {}
            for s_p in segs_p:
                r_out, sm = build_p(s_p, count=False)
                keep_ = TP["routes"].get(s_p["u"]) or {}
                for k_ in ("t0", "wt0", "t0plan"):         # the passes' own start fixes stay
                    if k_ in keep_:
                        r_out[k_] = keep_[k_]
                TP["routes"][s_p["u"]] = r_out
                by_u_[s_p["u"]] = sm
            TP["summary"]["units"] = [by_u_.get(x["u"], x) for x in TP["summary"]["units"]]
            TP["summary"]["unplanned"] = [[bd["tile"], [o["c"][0] for o in bd["ops"]], round(bd["v"], 1)] for bd in rest_p]
    TP.pop("_pol", None)
    TP["summary"]["spawn"] = [list(q) for q in sp0 + sp1]
    TP["summary"]["after1"] = [list(q) for q in after1]     # diagnostics: the plan's unit positions at the hour-1 market
    TP["wheat_buy"] = wbuy
    TP["summary"]["wheat_buy"] = wbuy
    TP["summary"]["dump"] = st.pop("_dump_day", None)
    TP["summary"]["dayret"] = st.pop("_dayret_day", None)
    TP["summary"]["refill"] = st.pop("_refill_day", None)
    TP["summary"]["follow"] = st.pop("_follow_day", None)
    TP["summary"]["srun"] = st.pop("_srun_day", None)
    TP["summary"]["sclu"] = st.pop("_sclu_day", None)
    TP["summary"]["fcarry"] = st.pop("_fcarry_day", None)
    TP["summary"]["ocl"] = st.pop("_ocl_day", None)
    TP["summary"]["pcl"] = st.pop("_pcl_day", None)
    if CFG["sd_polish"]:
        TP["summary"]["polish"] = st.pop("_polish_day", None)
    if CFG["sd_tp_iface"]:
        TP["summary"]["tp_leak"] = dict(_TP_LEAK)
    TP["summary"]["psw"] = st.pop("_pensweep_day", None)
    TP["summary"]["manual"] = st.pop("_manual_day", None)
    TP["summary"]["swap"] = st.pop("_swap_day", None)
    TP["summary"]["fmerge"] = st.pop("_fmerge_day", None)
    TP["summary"]["edel"] = st.pop("_edel_day", None)
    TP["summary"]["pdrop"] = st.pop("_pdrop_day", None)
    TP["summary"]["feedh"] = st.pop("_feedh_day", None)
    TP["summary"]["spx"] = dict(st.pop("_spx_day", None) or {}) or None
    TP["summary"]["path"] = dict(st.pop("_path_day", None) or {}) or None
    st.pop("_hold0", None)
    TP["summary"]["mfollow"] = dict(st.pop("_mfollow_day", None) or {}) or None
    TP["k0"] = k0
    TP["h0_books"] = nb0
    TP["summary"]["h0_books"] = nb0
    TP["h0_front"] = front
    TP["summary"]["k0"] = k0
    TP["summary"]["h0_front"] = front
    S["tier"] = TP
    L.setdefault("tier_days", {})[str(day)] = TP["summary"]


def _tier_spawn_exact(segs, units, rest, collects, owner, rate, st, build_route):
    """sd_tier_spawn_exact: returns the hour-1 hires' exact spawn tiles (hire order) after reassigning their routes to them."""
    import itertools as _it
    h1u = sorted(u for u, p0, t0 in units if u > 0 and t0 >= 2)
    if not h1u:
        return None
    seg_of = {sg["u"]: sg for sg in segs}
    after1 = []
    for u, p0, t0 in units:
        if t0 > 1:
            continue
        sg = seg_of.get(u)
        R_ = build_route(sg, count=False)[0] if sg is not None else None
        after1.append(_tier_walk(R_, p0, 2 - t0))
    true_ = _sd_spawn(after1, len(h1u))
    tgt = dict(zip(h1u, true_))
    rec_ = st.setdefault("_spx_day", Counter())
    rec_["hires"] += len(h1u)
    movable = [sg for sg in segs if sg["u"] in tgt and sg["kind"] == "out" and not sg.get("dawn")]
    rec_["fixed_kind"] += sum(1 for sg in segs if sg["u"] in tgt and sg not in movable)
    st["_spx_wrong_last"] = 0
    if not movable:
        return true_
    units_m = [sg["u"] for sg in movable]
    before = {id(sg): sg["p0"] for sg in movable}
    wrong_ = sum(1 for sg in movable if sg["p0"] != tgt[sg["u"]][1] * 10 + tgt[sg["u"]][0])
    rec_["wrong_before"] += wrong_
    st["_spx_wrong_last"] = wrong_

    def cost(sg, u):
        tq = tgt[u]
        e = _tier_eval(dict(sg, p0=tq[1] * 10 + tq[0], t0=2)) if sg["stops"] else (2, 0, 0, 0)
        return (e[1] + e[3]) * 1000 + e[0]
    if len(movable) <= 6:
        best = min(_it.permutations(units_m), key=lambda pm: sum(cost(sg, u) for sg, u in zip(movable, pm)))
    else:                                          # greedy for many hires
        left_, best = list(units_m), []
        for sg in movable:
            u = min(left_, key=lambda u: cost(sg, u))
            best.append(u)
            left_.remove(u)
    for sg, u in zip(movable, best):
        late0 = _tier_eval(sg)[1] if sg["stops"] else 0
        tq = tgt[u]
        sg["u"], sg["p0"], sg["t0"] = u, tq[1] * 10 + tq[0], 2
        sg["ver"] += 1
        rec_["moved"] += before[id(sg)] != sg["p0"]
        while sg["stops"]:                         # a route that now runs late sheds optional tail ops
            e = _tier_eval(sg)
            if e[1] <= late0 and e[0] <= 24:
                break
            k = next(((i, j) for i in range(len(sg["stops"]) - 1, -1, -1) for j in range(len(sg["stops"][i]["ops"]) - 1, -1, -1)
                      if not sg["stops"][i]["ops"][j]["m"] and not sg["stops"][i].get("turn")), None)
            if k is None:
                rec_["late_left"] += 1
                break
            i, j = k
            x = sg["stops"][i]
            ops2 = [o for jj, o in enumerate(x["ops"]) if jj != j]
            sg["stops"] = sg["stops"][:i] + ([dict(x, ops=ops2)] if ops2 else []) + sg["stops"][i + 1:]
            rec_["trimmed"] += 1
    planned = {(x["tile"], o["c"][0]) for sg in segs for x in sg["stops"] for o in x["ops"]}
    pool = []                                      # leftover extras for the freed time (no harvests: the midnight load)
    for bd in rest:
        ops2 = [o for o in bd["ops"] if o["c"][0] not in ("HARVEST", "PLACE_HARVEST") and (bd["tile"], o["c"][0]) not in planned
                and (o["c"][0] != "COLLECT_FERTILIZER" or (bd["tile"] in collects and int(CFG["sd_tier_spawn_exact"]) < 2))]
        if ops2:
            pool.append(dict(bd, ops=ops2, v=sum(o["v"] for o in ops2)))
    rec_["filled"] += _tier_fill(segs, [segs.index(sg) for sg in movable], pool, collects, owner, rate, st, "spx")
    return true_


def _tier_f_cmds(R, f0, ft0):
    """commands the farmer issues before the hour-1 market: 2 - ft0, or 2 for a sd_tier_farmer_h0pick route whose
    hour-0 command is a pickup / an in-place job (else it PASSes at hour 0 and only its hour-1 command counts)."""
    if not (R and R.get("hold0")):
        return 2 - ft0
    it = next(iter(R["items"]), None)
    if it is not None and (it["kind"] == "pick" or (it["kind"] == "stop" and (it["tile"] % 10, it["tile"] // 10) == tuple(f0))):
        return 2
    return 1


def _tier_walk(R, p, n):
    """position of a unit after its first n commands of route R (geometry only: picks and ops stay, moves step)."""
    p = tuple(p)
    if not R:
        return p
    items, k, sub = R["items"], 0, 0
    for _ in range(n):
        if k >= len(items):
            break
        it = items[k]
        q = _near_shed(p) if it["kind"] == "pick" else (it["tile"] % 10, it["tile"] // 10)
        if p != q:
            dx, dy = q[0] - p[0], q[1] - p[1]
            p = (p[0] + (1 if dx > 0 else -1), p[1]) if dx else (p[0], p[1] + (1 if dy > 0 else -1))
            continue
        if it["kind"] in ("pick", "place"):
            k += 1
            continue
        sub += 1
        if sub >= len(it["ops"]):
            k, sub = k + 1, 0
    return p


def _tier_wy_fill(tiles):
    """sd_tier_feed_harvest: today's wheat yield per wheat tile (the feed supply of a route's own harvests)."""
    for i_ in range(100):
        t_ = _tile(tiles, i_)
        if _is_plant(t_) and t_.get("crop") == "WHEAT" and int(t_.get("yield_units", 0) or 0) > 0:
            _TIER_WY[i_] = int(t_["yield_units"])


def _tier_psearch(segs, segs_m, rec, anim, owner, st, rng, fbud=0):
    """sd_path_planner: routes of whole tile services by value of the work done minus a labour price (see the flag).
    Sets the stops of segs_m; returns the optional services left unvisited as bundles (diagnostics)."""
    D = _TIER_D
    lam = float(CFG["sd_path_lambda"]) + float(CFG["sd_path_eps"])
    near_d = int(CFG["sd_path_near"])
    srv = {}                                       # tile -> {mode: ops}, values, rel
    for i, r_ in rec.items():
        ops_all = sorted([o for o in r_["ops"] if o["m"] or o["v"] > 0], key=lambda o: o["rank"])
        if not ops_all:
            continue
        req = [o for o in ops_all if o["m"]]
        opt = [o for o in ops_all if not o["m"]]
        modes = {}
        if req:
            modes["req"] = (req, 0.0)
        if opt:
            modes["full"] = (ops_all, sum(o["v"] for o in opt))
            nof = [o for o in ops_all if o["c"][0] != "FERTILIZE"]
            if len(nof) < len(ops_all) and any(not o["m"] for o in nof):
                modes["nof"] = (nof, sum(o["v"] for o in nof if not o["m"]))
        srv[i] = {"modes": modes, "req": bool(req), "rel": r_["rel"]}
    K = len(segs_m)
    pre = [list(sg["stops"][:int(sg.get("lo", 0) or 0)]) for sg in segs_m]   # fixed legs (dawn service) stay first
    ent = []
    seen = set()
    for k, sg in enumerate(segs_m):
        e = []
        for x in sg["stops"][int(sg.get("lo", 0) or 0):]:
            t = x["tile"]
            if t in srv and "req" in srv[t]["modes"] and t not in seen:
                e.append([t, "req"])
                seen.add(t)
        ent.append(e)
    pool = [t for t, v in srv.items() if not v["req"] and t not in seen]

    def build(k, e):
        return pre[k] + [{"tile": t, "ops": [dict(o) for o in srv[t]["modes"][m][0]], "rel": srv[t]["rel"]} for t, m in e]

    def need_fp(stops):                            # fertilizer to pick up at the shed: the route's worst deficit
        run = need = 0
        for x in stops:
            for o in x["ops"]:
                c = o["c"][0]
                if c == "COLLECT_FERTILIZER":
                    run -= 1
                elif c == "FERTILIZE":
                    run += 1
                    need = max(need, run)
        return need

    def rcost(k, e):
        sg = segs_m[k]
        stops = build(k, e)
        fp = need_fp(stops) if fbud > 0 else 0
        ev = _tier_eval(dict(sg, fpick=fp) if fp else sg, stops)
        val = sum(srv[t]["modes"][m][1] for t, m in e)
        return _TIER_BIG * (ev[1] + ev[3]) + lam * sg["wu"] * (ev[0] - sg["t0"]) - val

    cc = [rcost(k, ent[k]) for k in range(K)]

    def best_ins(k, t, modes):
        best = None
        e = ent[k]
        for m in modes:
            for pos in range(len(e) + 1):
                e2 = e[:pos] + [[t, m]] + e[pos:]
                c = rcost(k, e2)
                if best is None or c < best[0]:
                    best = (c, e2)
        return best

    def late_of(k, e):
        sg = segs_m[k]
        stops = build(k, e)
        fp = need_fp(stops) if fbud > 0 else 0
        ev = _tier_eval(dict(sg, fpick=fp) if fp else sg, stops)
        return ev[1] + ev[3]

    def make_room(k, e, keep):
        """drop the least valuable optional work (optional-only tiles out, others to required-only / no fertilize)
        until the route has no lateness; keep = the index just inserted (never dropped). Returns (entries, ejected)."""
        e = [list(x) for x in e]
        ej = []
        guard = 0
        while late_of(k, e) > 0 and guard < 12:
            guard += 1
            best = None
            for j, (t, m) in enumerate(e):
                if keep is not None and t == keep:
                    continue
                md = srv[t]["modes"]
                v, nops = md[m][1], len(md[m][0])
                if not srv[t]["req"]:
                    cand = (v / max(1, nops), j, None)          # the whole tile out
                else:
                    lo = [q for q in ("nof", "req") if q in md and q != m and len(md[q][0]) < nops]
                    if not lo:
                        continue
                    q = lo[-1] if m == "full" else lo[0]
                    cand = ((v - md[q][1]) / max(1, nops - len(md[q][0])), j, q)
                if best is None or cand[0] < best[0]:
                    best = cand
            if best is None:
                break
            _, j, q = best
            if q is None:
                ej.append(e[j][0])
                e = e[:j] + e[j + 1:]
            else:
                e[j][1] = q
        return e, ej

    def best_ins_eject(k, t, modes):
        """best insertion of tile t into route k, making room by dropping cheaper optional work"""
        best = None
        e = ent[k]
        for m in modes:
            for pos in range(len(e) + 1):
                e2 = e[:pos] + [[t, m]] + e[pos:]
                e3, ej = make_room(k, e2, t)
                c = rcost(k, e3)
                if best is None or c < best[0]:
                    best = (c, e3, ej)
        return best

    def near_routes(t, skip=None):
        out = []
        for k in range(K):
            if k == skip:
                continue
            if ((not ent[k] and segs_m[k]["kind"] == "out") or D[t][segs_m[k]["p0"]] <= near_d
                    or any(D[t][x[0]] <= near_d for x in ent[k])):
                out.append(k)
        return out

    rec_ = st.setdefault("_path_day", Counter())
    # 1. upgrades: required-only stops to their best mode
    for k in range(K):
        for idx in range(len(ent[k])):
            t, m0 = ent[k][idx]
            for m in srv[t]["modes"]:
                if m == ent[k][idx][1]:
                    continue
                e2 = [list(x) for x in ent[k]]
                e2[idx][1] = m
                ej = []
                if int(CFG["sd_path_eject"]) and late_of(k, e2) > 0:
                    e2, ej = make_room(k, e2, t)
                c = rcost(k, e2)
                if c < cc[k] - 1e-9:
                    ent[k], cc[k] = e2, c
                    pool.extend(ej)
                    rec_["upgraded"] += 1
    # 2. optional-only tiles by value, each to its best route / position if it pays
    for t in sorted(pool, key=lambda t: -max(v[1] for v in srv[t]["modes"].values())):
        if t not in pool:
            continue
        best = None
        for k in near_routes(t):
            b = best_ins_eject(k, t, list(srv[t]["modes"])) if int(CFG["sd_path_eject"]) else best_ins(k, t, list(srv[t]["modes"]))
            if b is not None and b[0] - cc[k] < -1e-9 and (best is None or b[0] - cc[k] < best[0]):
                best = (b[0] - cc[k], k, b)
        if best is not None:
            _, k, b = best
            ent[k], cc[k] = b[1], b[0]
            pool.remove(t)
            for x in (b[2] if len(b) > 2 else []):
                pool.append(x)
                rec_["ejected"] += 1
            rec_["inserted"] += 1
    # 3. annealing
    T0, T1 = float(CFG["sd_path_t0"]), 0.5
    n_it = int(CFG["sd_path_iters"])
    tot = sum(cc)
    best_tot, best_ent = tot, [[list(x) for x in e] for e in ent]
    for it in range(n_it):
        T = T0 * (1.0 - it / max(1, n_it)) + T1
        mv = rng.random()
        if mv < 0.3:                               # relocate
            ks = [k for k in range(K) if ent[k]]
            if not ks:
                continue
            a = rng.choice(ks)
            idx = rng.randrange(len(ent[a]))
            t, m = ent[a][idx]
            tgt = near_routes(t, skip=a)
            if not tgt:
                continue
            b = rng.choice(tgt)
            ra = ent[a][:idx] + ent[a][idx + 1:]
            ca = rcost(a, ra)
            bb = best_ins(b, t, [m])
            d = ca + bb[0] - cc[a] - cc[b]
            if d < 0 or rng.random() < _tier_math.exp(-d / T):
                ent[a], cc[a], ent[b], cc[b] = ra, ca, bb[1], bb[0]
                tot += d
        elif mv < 0.45:                            # swap two entries of two routes
            ks = [k for k in range(K) if ent[k]]
            if len(ks) < 2:
                continue
            a = rng.choice(ks)
            ia = rng.randrange(len(ent[a]))
            ta = ent[a][ia][0]
            cand = [(k, j) for k in ks if k != a for j, x in enumerate(ent[k]) if D[ta][x[0]] <= near_d]
            if not cand:
                continue
            b, ib = rng.choice(cand)
            ra = [list(x) for x in ent[a]]
            rb = [list(x) for x in ent[b]]
            ra[ia], rb[ib] = rb[ib], ra[ia]
            ca, cb = rcost(a, ra), rcost(b, rb)
            d = ca + cb - cc[a] - cc[b]
            if d < 0 or rng.random() < _tier_math.exp(-d / T):
                ent[a], cc[a], ent[b], cc[b] = ra, ca, rb, cb
                tot += d
        elif mv < 0.6:                             # reorder within a route
            ks = [k for k in range(K) if len(ent[k]) > 1]
            if not ks:
                continue
            a = rng.choice(ks)
            idx = rng.randrange(len(ent[a]))
            x = ent[a][idx]
            r = ent[a][:idx] + ent[a][idx + 1:]
            bb = None
            for pos in range(len(r) + 1):
                r2 = r[:pos] + [x] + r[pos:]
                c = rcost(a, r2)
                if bb is None or c < bb[0]:
                    bb = (c, r2)
            d = bb[0] - cc[a]
            if d < -1e-9:
                ent[a], cc[a] = bb[1], bb[0]
                tot += d
        elif mv < 0.75:                            # toggle a stop's mode
            ks = [k for k in range(K) if ent[k]]
            if not ks:
                continue
            a = rng.choice(ks)
            idx = rng.randrange(len(ent[a]))
            t, m = ent[a][idx]
            ms = [q for q in srv[t]["modes"] if q != m]
            if not ms:
                continue
            e2 = [list(x) for x in ent[a]]
            e2[idx][1] = rng.choice(ms)
            c = rcost(a, e2)
            d = c - cc[a]
            if d < 0 or rng.random() < _tier_math.exp(-d / T):
                ent[a], cc[a] = e2, c
                tot += d
        elif mv < 0.87:                            # visit an unvisited optional tile
            if not pool:
                continue
            t = rng.choice(pool)
            tgt = near_routes(t)
            if not tgt:
                continue
            b = rng.choice(tgt)
            bb = best_ins_eject(b, t, list(srv[t]["modes"])) if int(CFG["sd_path_eject"]) else best_ins(b, t, list(srv[t]["modes"]))
            d = bb[0] - cc[b]
            if d < 0 or rng.random() < _tier_math.exp(-d / T):
                ent[b], cc[b] = bb[1], bb[0]
                pool.remove(t)
                pool.extend(bb[2] if len(bb) > 2 else [])
                tot += d
        elif mv < 0.95:                            # drop an optional-only tile
            opts = [(k, j) for k in range(K) for j, x in enumerate(ent[k]) if not srv[x[0]]["req"]]
            if not opts:
                continue
            a, idx = rng.choice(opts)
            t = ent[a][idx][0]
            r = ent[a][:idx] + ent[a][idx + 1:]
            c = rcost(a, r)
            d = c - cc[a]
            if d < 0 or rng.random() < _tier_math.exp(-d / T):
                ent[a], cc[a] = r, c
                pool.append(t)
                tot += d
        else:                                      # whole routes between two same-start hands
            ks = [k for k in range(K) if segs_m[k]["kind"] == "out" and not pre[k]]
            if len(ks) < 2:
                continue
            a, b = rng.sample(ks, 2)
            if segs_m[a]["t0"] != segs_m[b]["t0"] or segs_m[a]["p0"] == segs_m[b]["p0"]:
                continue
            ca, cb = rcost(a, ent[b]), rcost(b, ent[a])
            d = ca + cb - cc[a] - cc[b]
            if d < 0 or rng.random() < _tier_math.exp(-d / T):
                ent[a], ent[b] = ent[b], ent[a]
                cc[a], cc[b] = ca, cb
                tot += d
                rec_["route_swaps"] += 1
        if tot < best_tot - 1e-9:
            best_tot, best_ent = tot, [[list(x) for x in e] for e in ent]
    ent = best_ent
    fps = [need_fp(build(k, ent[k])) if fbud > 0 else 0 for k in range(K)]
    while sum(fps) > fbud:                         # the shed holds fbud: the least valuable fertilizes go
        cand = [(srv[t]["modes"][m][1] - srv[t]["modes"].get("nof", srv[t]["modes"].get("req", ((), 0.0)))[1], k, j)
                for k in range(K) if fps[k] > 0 for j, (t, m) in enumerate(ent[k])
                if m == "full" and any(o["c"][0] == "FERTILIZE" for o in srv[t]["modes"]["full"][0])
                and ("nof" in srv[t]["modes"] or "req" in srv[t]["modes"])]
        if not cand:
            break
        _, k, j = min(cand)
        t = ent[k][j][0]
        ent[k][j][1] = "nof" if "nof" in srv[t]["modes"] else "req"
        fps[k] = need_fp(build(k, ent[k]))
        rec_["fert_trimmed"] += 1
    placed = set()
    for k, sg in enumerate(segs_m):
        sg["stops"] = build(k, ent[k])
        if fps[k] > 0:
            sg["fpick"] = fps[k]
            rec_["fert_picked"] += fps[k]
        sg["ver"] = sg.get("ver", 0) + 1
        for x in sg["stops"]:
            placed.add(x["tile"])
            if x["tile"] not in anim:
                owner[x["tile"]] = segs.index(sg)
        for t, m in ent[k]:
            rec_["mode_" + m] += 1
    left = [t for t in srv if t not in placed]
    rec_["left_optional"] += len(left)
    rec_["value"] += sum(srv[t]["modes"][m][1] for e in ent for t, m in e)
    return [{"tile": t, "ops": [o for o in srv[t]["modes"]["full"][0] if not o["m"]], "v": srv[t]["modes"]["full"][1]}
            for t in left if "full" in srv[t]["modes"]]


def _tier_route_swap_final(segs, owner, anim, st):
    """sd_tier_route_swap 2: finished same-start outbound routes traded between hands (their spawn tiles) to cut the sum
    of end hours; the route's own order is kept; returns swaps made."""
    cand = [sg for sg in segs if sg["kind"] == "out" and not sg.get("dawn") and sg["stops"]
            and not any(x.get("dawn") for x in sg["stops"])]
    keys = ("stops", "fpick", "lo")

    def ev_with(sg, route):
        return _tier_eval(dict(sg, **route))

    n = 0
    for _it in range(40):
        best = None
        for a in range(len(cand)):
            for b in range(a + 1, len(cand)):
                A, B = cand[a], cand[b]
                if A["t0"] != B["t0"] or A["p0"] == B["p0"]:
                    continue
                ra = {k: A.get(k) for k in keys}
                rb = {k: B.get(k) for k in keys}
                ea, eb = _tier_eval(A), _tier_eval(B)
                ea2, eb2 = ev_with(A, rb), ev_with(B, ra)
                if ea2[0] > 24 or eb2[0] > 24 or ea2[1] + eb2[1] > ea[1] + eb[1] or ea2[3] + eb2[3] > ea[3] + eb[3]:
                    continue
                d = (ea2[0] + eb2[0]) - (ea[0] + eb[0])
                if d < 0 and (best is None or d < best[0]):
                    best = (d, A, B, ra, rb)
        if best is None:
            break
        d, A, B, ra, rb = best
        for k in keys:
            A[k], B[k] = rb[k], ra[k]
        A["ver"] = A.get("ver", 0) + 1
        B["ver"] = B.get("ver", 0) + 1
        for sg in (A, B):
            for x in sg["stops"]:
                if x["tile"] not in anim:
                    owner[x["tile"]] = segs.index(sg)
        n += 1
        st["tier_route_swap2_hours"] = st.get("tier_route_swap2_hours", 0) - d
    st["tier_route_swap2"] = st.get("tier_route_swap2", 0) + n
    return n


def _tier_route_swap(segs_m, owner, anim, segs, st):
    """sd_tier_route_swap: whole-route swaps between same-start outbound segments (see the flag); returns swaps made."""
    cand = [sg for sg in segs_m if sg["kind"] == "out" and not sg.get("dawn") and sg["stops"]]

    def reorder(sg, stops):
        if len(stops) <= 1:
            return stops
        ids = _tier_route(sg, list(range(len(stops))), stops)
        return [stops[i] for i in ids]

    def cost(sg, stops):
        ev = _tier_eval(sg, stops)
        return _tier_cost(sg, ev, stops), ev[1]
    n = 0
    for _it in range(40):
        best = None
        for a in range(len(cand)):
            for b in range(a + 1, len(cand)):
                A, B = cand[a], cand[b]
                if A["t0"] != B["t0"] or A["p0"] == B["p0"]:
                    continue
                ca, la = cost(A, A["stops"])
                cb, lb = cost(B, B["stops"])
                sa = reorder(A, [dict(x) for x in B["stops"]])
                sb = reorder(B, [dict(x) for x in A["stops"]])
                ca2, la2 = cost(A, sa)
                cb2, lb2 = cost(B, sb)
                if la2 + lb2 > la + lb:
                    continue
                d = (ca2 + cb2) - (ca + cb)
                if d < -0.5 and (best is None or d < best[0]):
                    best = (d, A, B, sa, sb)
        if best is None:
            break
        d, A, B, sa, sb = best
        A["stops"], B["stops"] = sa, sb
        A["ver"] = A.get("ver", 0) + 1
        B["ver"] = B.get("ver", 0) + 1
        for sg in (A, B):
            for x in sg["stops"]:
                if x["tile"] not in anim:
                    owner[x["tile"]] = segs.index(sg)
        n += 1
        st["tier_route_swap_gain"] = st.get("tier_route_swap_gain", 0.0) - d
    st["tier_route_swap"] = st.get("tier_route_swap", 0) + n
    return n


def _tier_polish(S, segs, rest, tiles, day, st):
    """sd_polish (see the flag): hill climbing over the finished routes on engine-true values; commits only a gain."""
    import random as _rnd
    D = _TIER_D
    prices = S.get("_tier_prices") or {}
    last_day = int(S.get("_tier_last_day", 29))
    rng = _rnd.Random(int(CFG["sd_polish_seed"]) * 1009 + day)
    fp = float(prices.get("FERTILIZER", 0) or 0)
    wc = float(CFG["sd_polish_water_c"])
    sw = float(CFG["sd_polish_step_w"])
    OPT = ("WATER", "FERTILIZE", "CARE", "FEED", "COLLECT_FERTILIZER")
    FIX = ("DELIVER", "DROP", "PLACE_HARVEST", "PICKUP", "PLACE", "BUILD_COOP", "BUILD_PASTURE")
    fed0 = set()                                   # fed whatever the search does: fed already or a mandatory FEED
    for sg in segs:
        for x in sg["stops"]:
            if any(o["c"][0] == "FEED" and o["m"] for o in x["ops"]):
                fed0.add(x["tile"])
    for idx_ in range(100):
        t_ = _tile(tiles, idx_)
        if _animal(t_) and t_.get("fed_today"):
            fed0.add(idx_)

    def movable(x):
        return not (x.get("dawn") or x.get("copy") or x.get("sell_all") or x.get("place") or x.get("turn")
                    or x.get("deliver") or any(o["c"][0] in FIX for o in x["ops"]))

    def pr(k):
        return float(prices.get(k, 0) or 0)

    def prod_night(t, n):                          # an ongoing crop's production at the end of day n
        cr = CROPS[t["crop"]]
        iv = max(1, int(cr["interval"]))
        ds = n + 1 - int(t.get("planted_day", n)) - cr["first"]
        return ds >= 0 and ds % iv == 0 and ds // iv + 1 <= cr["max"]

    def anim_prod(t, n):
        a = ANIMALS[t["animal"]]
        ds = n + 1 - int(t.get("placed_day", n)) - a["first"]
        return ds >= 0 and ds % a["interval"] == 0

    def fert_gain(t, watered):
        cr = CROPS[t["crop"]]
        pd = int(t.get("planted_day", day))
        fu = int(t.get("fertilized_until_day", -1) or -1)
        if fu >= day:
            return 0
        if not cr["ongoing"]:
            w0, w1 = (cr["maxday"] + 1) // 2, cr["maxday"]
            if not (w0 <= day - pd <= w1):
                return 0
            y0 = int(t.get("yield_units", 0) or 0)

            def units(f):
                y = y0
                for dd in range(day, pd + w1 + 1):
                    if w0 <= dd - pd <= w1:
                        y = min(cr["max"], y + (2 if (f and dd <= day + 2) else 1))
                return y
            return units(True) - units(False)
        return sum(1 for dd in range(day, min(day + 3, last_day)) if prod_night(t, dd) and (dd > day or watered))

    def stop_val(x, feeds):
        t = _tile(tiles, x["tile"])
        if not isinstance(t, dict):
            return 0.0
        cs = [o["c"][0] for o in x["ops"]]
        fh, wh, hh = "FERTILIZE" in cs, "WATER" in cs, "HARVEST" in cs
        v = 0.0
        for o in x["ops"]:
            if o["m"]:
                continue
            c = o["c"][0]
            if c == "COLLECT_FERTILIZER" and _animal(t):
                v += fp
            elif c == "FERTILIZE" and _is_plant(t):
                v += fert_gain(t, wh or t.get("watered_today")) * pr(t["crop"]) - fp
            elif c == "WATER" and _is_plant(t) and not t.get("watered_today"):
                cr = CROPS[t["crop"]]
                a = day - int(t.get("planted_day", day))
                fn = fh or int(t.get("fertilized_until_day", -1) or -1) >= day
                if not cr["ongoing"] and (cr["maxday"] + 1) // 2 <= a <= cr["maxday"]:
                    v += min(2 if fn else 1, max(0, cr["max"] - int(t.get("yield_units", 0) or 0))) * pr(t["crop"])
                elif cr["ongoing"] and fn and prod_night(t, day):
                    v += pr(t["crop"])
                if not hh and int(t.get("consecutive_unwatered", 0) or 0) == 0 and day < last_day - 1:
                    v += wc
            elif c == "CARE" and _animal(t):              # banks +1 only on a fed day
                if ((x["tile"] in fed0 or x["tile"] in feeds or "FEED" in cs)
                        and any(anim_prod(t, n) for n in range(day + 1, last_day))):
                    v += pr(ANIMALS[t["animal"]]["product"])
            elif c == "FEED" and _animal(t):              # an unfed animal still produces 1: the feed pays the bank on a
                p_ = pr(ANIMALS[t["animal"]]["product"])  # production night, and a skipped feed makes tomorrow's a must
                if anim_prod(t, day):
                    v += int(t.get("pending_care_bonus", 0) or 0) * p_
                if int(t.get("consecutive_unfed", 0) or 0) == 0 and day < last_day - 1:
                    v += wc
        return v

    def seg_eval(sg, stops):
        if not stops:
            return {"val": 0.0, "pen": 0.0, "hrs": 0, "load": 0}
        ev = _tier_eval(sg, stops)
        feeds = {x["tile"] for x in stops if any(o["c"][0] == "FEED" for o in x["ops"])}
        return {"val": sum(stop_val(x, feeds) for x in stops), "pen": 1000.0 * (ev[1] + ev[3]), "hrs": max(0, ev[0] - sg["t0"]),
                "load": sum(_tier_load(sg, stops, tiles, day).values())}

    cur = [list(sg["stops"]) for sg in segs]
    E = [seg_eval(sg, cur[k]) for k, sg in enumerate(segs)]
    load0 = sum(e["load"] for e in E)
    dd = st.get("_dump_day") or {}
    head = max(0, 100 - int(CFG["sd_tier_dump_buffer"]) - int(dd.get("left", 100))) if dd else 0

    def total(E_):
        return (sum(e["val"] - e["pen"] - sw * e["hrs"] for e in E_)
                - 1000.0 * max(0, sum(e["load"] for e in E_) - load0 - head))

    base = best = total(E)
    pool = []                                      # (bundle, op) unplaced optional maintenance ops
    for bd in rest:
        for o in bd["ops"]:
            if o["c"][0] in OPT and not o["m"]:
                pool.append((bd, o))
    added, dropped = [], []
    nmov = Counter()

    def try_set(ch, kind):
        nonlocal best
        E2 = list(E)
        for k, stops in ch.items():
            E2[k] = seg_eval(segs[k], stops)
        v = total(E2)
        if v > best + 1e-6:
            best = v
            for k, stops in ch.items():
                cur[k] = stops
                E[k] = E2[k]
            nmov[kind] += 1
            return True
        return False

    def cpx(x, ops=None):
        return dict(x, ops=list(x["ops"] if ops is None else ops))

    def near_segs(tile, excl=None, n=3):
        cand = []
        for k, sg in enumerate(segs):
            if k == excl:
                continue
            dmin = min([D[sg["p0"]][tile]] + [D[y["tile"]][tile] for y in cur[k]])
            cand.append((dmin, k))
        return [k for _, k in sorted(cand)[:n]]

    def lo(k):                                     # the route's first real stop (after a dawn prefix): it stays first, so the
        j = 0                                      # hands' first moves and the hires' spawn prediction do not change
        while j < len(cur[k]) and cur[k][j].get("dawn"):
            j += 1
        return j

    def mv_ok(k, j):
        return movable(cur[k][j]) and j != lo(k)

    def spots(k, tile):                            # insertion positions next to the two nearest stops, and the end
        f = lo(k) + 1
        near = sorted(range(len(cur[k])), key=lambda j: D[cur[k][j]["tile"]][tile])[:2]
        qs = {len(cur[k])}
        for j in near:
            qs.update((j, j + 1))
        return sorted(q for q in qs if f <= q <= len(cur[k]))

    iters = int(CFG["sd_polish"])
    for _ in range(iters):
        mv = rng.random()
        ks = [k for k in range(len(segs)) if any(mv_ok(k, j) for j in range(len(cur[k])))]
        if not ks:
            break
        if mv < 0.35:                              # relocate a stop to the best position of a nearby route
            a = rng.choice(ks)
            js = [j for j in range(len(cur[a])) if mv_ok(a, j)]
            j = rng.choice(js)
            x = cur[a][j]
            sa = cur[a][:j] + cur[a][j + 1:]
            ea = seg_eval(segs[a], sa)
            bestq = None
            for b in near_segs(x["tile"], a):
                for q in spots(b, x["tile"]):
                    sb = cur[b][:q] + [cpx(x)] + cur[b][q:]
                    E2 = list(E)
                    E2[a] = ea
                    E2[b] = seg_eval(segs[b], sb)
                    v = total(E2)
                    if bestq is None or v > bestq[0]:
                        bestq = (v, b, sb)
            if bestq and bestq[0] > best + 1e-6:
                try_set({a: sa, bestq[1]: bestq[2]}, "relocate")
        elif mv < 0.5:                             # swap two stops between routes
            a, b = rng.choice(ks), rng.choice(ks)
            if a == b:
                continue
            ia = rng.choice([j for j in range(len(cur[a])) if mv_ok(a, j)])
            ib = rng.choice([j for j in range(len(cur[b])) if mv_ok(b, j)])
            sa, sb = list(cur[a]), list(cur[b])
            sa[ia], sb[ib] = cpx(cur[b][ib]), cpx(cur[a][ia])
            try_set({a: sa, b: sb}, "swap")
        elif mv < 0.7:                             # reverse a run of movable stops inside a route
            a = rng.choice(ks)
            if len(cur[a]) < 3:
                continue
            i = rng.randrange(len(cur[a]) - 1)
            j = rng.randrange(i + 1, len(cur[a]))
            if not all(mv_ok(a, q) for q in range(i, j + 1)):
                continue
            sa = cur[a][:i] + cur[a][i:j + 1][::-1] + cur[a][j + 1:]
            try_set({a: sa}, "reverse")
        elif mv < 0.7 + float(CFG["sd_polish_xch"]) and pool:   # exchange: an unplaced op into a stop the route already
            pi = rng.randrange(len(pool))          # makes (no walking), a lower-value optional op of that route out
            bd, o = pool[pi]
            owners = [(k, j) for k in range(len(segs)) for j, y in enumerate(cur[k]) if y["tile"] == bd["tile"] and movable(y)
                      and not any(o2["c"][0] == o["c"][0] for o2 in y["ops"])]
            if not owners:
                continue
            k, j = rng.choice(owners)
            cands = [(j2, o2) for j2, y in enumerate(cur[k]) if movable(y) for o2 in y["ops"] if o2["c"][0] in OPT and not o2["m"]]
            if not cands:
                continue
            bestx = None
            for j2, o2 in rng.sample(cands, min(6, len(cands))):
                sk = list(cur[k])
                sk[j] = cpx(cur[k][j], sorted(cur[k][j]["ops"] + [o], key=lambda z: z.get("rank", 5)))
                ops2 = [z for z in sk[j2]["ops"] if z is not o2]
                if not ops2 and j2 == lo(k):
                    continue
                sk = sk[:j2] + ([cpx(sk[j2], ops2)] if ops2 else []) + sk[j2 + 1:]
                E2 = list(E)
                E2[k] = seg_eval(segs[k], sk)
                v = total(E2)
                if bestx is None or v > bestx[0]:
                    bestx = (v, sk, j2, o2)
            if bestx and bestx[0] > best + 1e-6:
                y2 = cur[k][bestx[2]]
                if try_set({k: bestx[1]}, "exchange"):
                    pool.pop(pi)
                    added.append((bd, o))
                    pool.append(({"tile": y2["tile"], "ops": [bestx[3]], "v": 0.0, "rel": y2.get("rel", 0)}, bestx[3]))
                    dropped.append((y2["tile"], bestx[3]))
        elif mv < 0.88 + float(CFG["sd_polish_xch"]) and pool:   # add an unplaced optional op: to its tile's visit, else a new stop
            pi = rng.randrange(len(pool))
            bd, o = pool[pi]
            tile = bd["tile"]
            own = next(((k, j) for k in range(len(segs)) for j, y in enumerate(cur[k]) if y["tile"] == tile and movable(y)), None)
            ok = False
            if own is not None:
                k, j = own
                if not any(o2["c"][0] == o["c"][0] for o2 in cur[k][j]["ops"]):
                    sk = list(cur[k])
                    sk[j] = cpx(cur[k][j], sorted(cur[k][j]["ops"] + [o], key=lambda z: z.get("rank", 5)))
                    ok = try_set({k: sk}, "add")
            else:
                bestq = None
                for k in near_segs(tile, None, 2):
                    for q in spots(k, tile):
                        sk = cur[k][:q] + [{"tile": tile, "ops": [o], "rel": int(bd.get("rel", 0) or 0)}] + cur[k][q:]
                        E2 = list(E)
                        E2[k] = seg_eval(segs[k], sk)
                        v = total(E2)
                        if bestq is None or v > bestq[0]:
                            bestq = (v, k, sk)
                if bestq and bestq[0] > best + 1e-6:
                    ok = try_set({bestq[1]: bestq[2]}, "add")
            if ok:
                pool.pop(pi)
                added.append((bd, o))
        else:                                      # drop an optional maintenance op (frees an hour / supply / room)
            a = rng.choice(ks)
            js = [j for j, x in enumerate(cur[a]) if movable(x) and any(o["c"][0] in OPT and not o["m"] for o in x["ops"])]
            if not js:
                continue
            j = rng.choice(js)
            x = cur[a][j]
            opts = [o for o in x["ops"] if o["c"][0] in OPT and not o["m"]]
            o = rng.choice(opts)
            ops2 = [z for z in x["ops"] if z is not o]
            if not ops2 and j == lo(a):
                continue                           # the first stop is never emptied (first moves / spawn prediction)
            sa = cur[a][:j] + ([cpx(x, ops2)] if ops2 else []) + cur[a][j + 1:]
            if try_set({a: sa}, "drop"):
                pool.append(({"tile": x["tile"], "ops": [o], "v": 0.0, "rel": x.get("rel", 0)}, o))
                dropped.append((x["tile"], o))
    gain = best - base
    if gain > 1e-6:
        for k, sg in enumerate(segs):
            if cur[k] is not sg["stops"] and cur[k] != sg["stops"]:
                sg["stops"] = cur[k]
                sg["ver"] = sg.get("ver", 0) + 1
        for bd, o in added:
            if o in bd["ops"]:
                bd["ops"] = [z for z in bd["ops"] if z is not o]
                bd["v"] = sum(z["v"] for z in bd["ops"])
        for tile, o in dropped:
            if not any(o is z for bd, z in added):
                rest.append({"tile": tile, "ops": [o], "v": float(o.get("v", 0.0))})
        rest[:] = [bd for bd in rest if bd["ops"]]
    st["_polish_day"] = {"gain": round(gain, 1), "moves": dict(nmov), "added": Counter(o["c"][0] for _, o in added),
                         "dropped": Counter(o["c"][0] for _, o in dropped), "load0": load0, "head": head,
                         "committed": gain > 1e-6}


def _tier_core(S, L, st, day, tiles, rec, units, want, t_start):
    _TIER_WY.clear()
    _TIER_CC["n"] = 0
    st.pop("_feedh_day", None)                     # the day's last planning pass counts
    if int(CFG["sd_tier_feed_harvest"]) == 1:
        _tier_wy_fill(tiles)
    n_ani = int(CFG["sd_tier_animal_hand"])
    ani_units = set(u for u, _, _ in units[-n_ani:]) if n_ani > 0 else set()
    # ---- A. melon hands
    mel_units = [(u, p0, t0) for u, p0, t0 in units if t0 <= 1 and u not in ani_units]
    masg, left = _tier_melon(day, tiles, mel_units)
    segs, owner = [], {}
    mel_of = {}
    melon_tiles = set()
    for u, order, drop, hh in masg:
        p0 = next(p for uu, p, _ in units if uu == u)
        t0 = next(t for uu, _, t in units if uu == u)
        stops = []
        for i in order:
            t = _tile(tiles, i)
            ops = ([_tier_op(["WATER"], True, 0.0, 1)] if _mel_needs_water(t, day) else []) + [
                _tier_op(["HARVEST"], True, 0.0, 1)]
            stops.append({"tile": i, "ops": ops, "rel": 0})
            melon_tiles.add(i)
        last = order[-1]
        sh = _tier_near_shed(last)
        stops.append({"tile": sh, "ops": [_tier_op(["PLACE", "MELON", 0], True, 0.0, 1)], "rel": 0, "place": True})
        mel_of[u] = {"stops": stops, "p0": p0[1] * 10 + p0[0], "t0": t0, "drop": drop, "hh": dict(hh)}
    # the rest of a melon tile's work: the melon hand does it when its drop stays by 8, else the tile's owner after the
    # planned harvest (harvested-by flag)
    for u, M in mel_of.items():
        for i in [s["tile"] for s in M["stops"] if not s.get("place")]:
            r_ = rec.get(i)
            if r_:
                r_["ops"] = [o for o in r_["ops"] if o["c"][0] not in ("WATER", "HARVEST") or o["rank"] == 8]
                if not r_["ops"]:
                    rec.pop(i)
                    continue
            else:
                continue
            rest = [o for o in r_["ops"] if o["m"] and not (o["c"][0] == "PLACE" and o["c"][1:2] and o["c"][1] in ANIMALS)]
            if rest and len(rest) == len([o for o in r_["ops"] if o["m"]]):
                seg_ = {"p0": M["p0"], "t0": M["t0"], "stops": M["stops"]}
                st2 = [dict(s) for s in M["stops"]]
                for s in st2:
                    if s["tile"] == i:
                        s["ops"] = s["ops"] + [dict(o) for o in rest]
                ev = _tier_eval(seg_, st2, want_hours=True)
                drop_h = next(h for (b_, c_, h) in ev[4] if c_[0] == "PLACE" and c_[1] == "MELON")
                if drop_h <= 8:
                    M["stops"] = st2
                    r_["ops"] = [o for o in r_["ops"] if o not in rest]
                    st["tier_melon_replant"] = st.get("tier_melon_replant", 0) + 1
                    if not r_["ops"]:
                        rec.pop(i)
                    continue
        ev = _tier_eval({"p0": M["p0"], "t0": M["t0"], "stops": M["stops"]}, want_hours=True)
        M["drop"] = next(h for (b_, c_, h) in ev[4] if c_[0] == "PLACE" and c_[1] == "MELON")
        for b_, c_, h in ev[4]:
            if c_[0] == "HARVEST":
                M["hh"][b_] = h
        for i, h in M["hh"].items():
            if i in rec:
                rec[i]["rel"] = max(rec[i]["rel"], h + 1)
    if CFG["sd_tier_prio_ani"]:                     # user: important animal harvests in melon mode (the farmer)
        fu_ = next(((u, p0, t0) for u, p0, t0 in units if u == 0), None)
        if fu_ is not None and 0 not in mel_of and fu_[2] <= 1:
            M_ = _tier_prio_ani(S, rec, tiles, day, fu_, st)
            if M_ is not None:
                mel_of[0] = M_
    if CFG["sd_tier_prio_straw"]:                   # user: strawberry harvests in melon mode (one hour-0 hire)
        best_ = None
        for u_, p0_, t0_ in units:
            if u_ == 0 or u_ in mel_of or t0_ > 1 or u_ in ani_units:
                continue
            rec_try = _tier_copy_rec(rec)
            M_ = _tier_prio_run(S, rec_try, tiles, day, (u_, p0_, t0_), st, "straw")
            if M_ is not None and (best_ is None or M_["_value"] > best_[0]):
                best_ = (M_["_value"], u_, (u_, p0_, t0_))
        if best_ is not None:
            M_ = _tier_prio_run(S, rec, tiles, day, best_[2], st, "straw")
            if M_ is not None:
                mel_of[best_[1]] = M_
                st["tier_prio_straw_runs"] = st.get("tier_prio_straw_runs", 0) + 1
    if CFG["sd_tier_sclu"]:                        # user: strawberry clusters, one hand each, direct path + extra work on it
        for u_, M_ in _tier_sclu(S, rec, tiles, day, units, set(mel_of) | ani_units, st).items():
            mel_of[u_] = M_
            st["tier_sclu_runs"] = st.get("tier_sclu_runs", 0) + 1
    if CFG["sd_tier_srun"]:                        # user: one hand brings strawberries home (deadline, units, early, extra work)
        best_ = None
        seen_ = set()
        for u_, p0_, t0_ in units:                 # one trial per distinct start (the hour-0 hires stand on shed tiles)
            if u_ == 0 or u_ in mel_of or t0_ > 1 or u_ in ani_units or (tuple(p0_), t0_) in seen_:
                continue
            seen_.add((tuple(p0_), t0_))
            M_ = _tier_srun(S, _tier_copy_rec(rec), tiles, day, (u_, p0_, t0_), {})
            if M_ is not None and (best_ is None or (M_["_units"], -M_["drop"]) > best_[0]):
                best_ = ((M_["_units"], -M_["drop"]), u_, (u_, p0_, t0_))
        if best_ is not None:
            M_ = _tier_srun(S, rec, tiles, day, best_[2], st)
            if M_ is not None:
                mel_of[best_[1]] = M_
                st["tier_srun_runs"] = st.get("tier_srun_runs", 0) + 1
    dawn_of = {}
    if int(CFG["sd_tier_dawn"]) == 1:              # learned from DSM: short dawn round trips to the near pens (forced)
        dawn_of = _tier_dawn(S, rec, tiles, day, units, set(mel_of) | ani_units, st)
    elif int(CFG["sd_tier_dawn"]) == 3:            # user: DSM's recorded early trips of the day, same hands / pens / hours
        dawn_of = _tier_dawn_shape(S, rec, tiles, day, units, set(mel_of) | ani_units, st)
    if CFG["sd_tier_fert_shed"]:                   # the day's shed fertilizer for route pickups (reset every planning pass)
        _FSHED["left"] = max(0, int((S.get("_shed_h0") or {}).get("FERTILIZER", 0) or 0) - int(CFG["sd_tier_sclu_fert_keep"])
                             - sum(int(M_.get("fpick", 0) or 0) for M_ in mel_of.values()))
    # ---- segments: outbound hands, the melon hands after their drop, animal hands
    anim = [i for i in range(100) if _animal(_tile(tiles, i))]
    fneed = set(i for i, r_ in rec.items() if any(o["c"][0] == "FERTILIZE" for o in r_["ops"]))
    for u, p0, t0 in units:
        pi = p0[1] * 10 + p0[0]
        if u in mel_of:
            M = mel_of[u]
            sh = M["stops"][-1]["tile"]
            segs.append({"u": u, "kind": "post", "p0": sh, "t0": M["drop"] + 1, "stops": [], "wu": float(CFG["sd_tier_prio_w"]),
                         "ver": 0, "anim": anim, "fneed": fneed})
        elif u in ani_units:
            segs.append({"u": u, "kind": "ani", "p0": pi, "t0": t0, "stops": [], "wu": 1.0, "ver": 0, "anim": anim,
                         "fneed": fneed})
        elif u in dawn_of:                         # sd_tier_dawn: an outbound hand from the shed tile of its dawn drop
            segs.append({"u": u, "kind": "out", "p0": dawn_of[u]["tile"], "t0": dawn_of[u]["end"], "stops": [], "wu": 1.0,
                         "ver": 0, "anim": anim, "fneed": fneed, "dawn": True})
        else:
            h0_ = bool(u == 0 and t0 == 1 and st.get("_hold0") and pi in _TIER_SHED_I)
            segs.append({"u": u, "kind": "out", "p0": pi, "t0": 0 if h0_ else t0, "stops": [], "wu": 1.0, "ver": 0, "anim": anim,
                         "fneed": fneed, "hold0": h0_})
    if CFG["sd_tier_central_hand"]:                # user: the farmer cares around the centre and returns to drop
        cseg = next((s_ for s_ in segs if s_["u"] == 0 and s_["kind"] == "out" and not s_.get("dawn")), None)
        if cseg is not None:
            _tier_central(S, cseg, rec, tiles, day, st)
    # ---- B. mandatory stops -> sectors (heuristic search)
    stops_all = []
    for i, r_ in sorted(rec.items()):
        mops = [o for o in r_["ops"] if o["m"]]
        if mops:
            stops_all.append({"tile": i, "ops": mops, "rel": r_["rel"]})
    rng = _tier_random.Random(int(CFG["sd_seed"]) * 7907 + day)
    segs_m = [s for s in segs if s["kind"] in ("out", "post")]
    routes, cost = _tier_search(segs_m, stops_all, float(CFG["sd_tier_budget"]), rng)
    for s, r in zip(segs_m, routes):
        s["stops"] = [dict(stops_all[i], ops=[dict(o) for o in stops_all[i]["ops"]]) for i in r]
        for x in s["stops"]:
            if x["tile"] not in anim:
                owner[x["tile"]] = segs.index(s)
    late_m = sum(_tier_eval(s)[1] for s in segs_m if s["stops"])
    if late_m > 0 and CFG["sd_tier_pen_bundle"] and any(o.get("pb") for r_ in rec.values() for o in r_["ops"]):
        for r_ in rec.values():                    # the bundles do not fit: their added ops go back to the extras
            for o in r_["ops"]:
                if o.get("pb"):
                    o["m"], o["tier"], o["pb"] = False, 4, False
        stops_all = []
        for i, r_ in sorted(rec.items()):
            mops = [o for o in r_["ops"] if o["m"]]
            if mops:
                stops_all.append({"tile": i, "ops": mops, "rel": r_["rel"]})
        routes, cost = _tier_search(segs_m, stops_all, float(CFG["sd_tier_budget"]), rng)
        for s, r in zip(segs_m, routes):
            s["stops"] = [dict(stops_all[i], ops=[dict(o) for o in stops_all[i]["ops"]]) for i in r]
            for x in s["stops"]:
                if x["tile"] not in anim:
                    owner[x["tile"]] = segs.index(s)
        late_m = sum(_tier_eval(s)[1] for s in segs_m if s["stops"])
        st["tier_pen_bundle_fallback"] = st.get("tier_pen_bundle_fallback", 0) + 1
    st["tier_mand_late"] = st.get("tier_mand_late", 0) + late_m
    if int(CFG["sd_tier_route_swap"]) == 1:        # user: whole routes to the hands whose spawn tile suits them
        _tier_route_swap(segs_m, owner, set(anim), segs, st)
    for sg in segs_m:                              # sd_tier_dawn_service: the leg pen's feed / care / collect right after the pickups
        sv_ = (dawn_of.get(sg["u"]) or {}).get("svc") if sg.get("dawn") else None
        for x in sv_ or []:
            ev0_ = _tier_eval(sg)
            k_ = next((i for i, y in enumerate(sg["stops"]) if y["tile"] == x["tile"]), None)
            if k_ is not None:                     # the search gave this unit the pen's mandatory work: same visit
                trial = [dict(y) for y in sg["stops"]]
                trial[k_]["ops"] = sorted(trial[k_]["ops"] + [dict(o) for o in x["ops"]], key=lambda o: o["rank"])
            else:
                trial = [{k2: v2 for k2, v2 in x.items() if k2 != "orig"}] + sg["stops"]
            ev1_ = _tier_eval(sg, trial)
            if ev1_[1] <= ev0_[1] and ev1_[3] <= ev0_[3] and ev1_[0] <= 24:
                sg["stops"] = trial
                sg["ver"] += 1
                if k_ is None:
                    sg["lo"] = max(sg.get("lo", 0), 1)   # the extras go after it
                st["tier_dawn_svc"] = st.get("tier_dawn_svc", 0) + 1
            else:                                  # it does not fit: its ops are plain extras again
                r_ = rec.setdefault(x["tile"], {"ops": [], "rel": x["rel"]})
                r_["ops"] = r_["ops"] + list(x["orig"])
                st["tier_dawn_svc_back"] = st.get("tier_dawn_svc_back", 0) + 1
    if CFG["sd_tier_dayret_shape"]:                # DSM's daytime return shape: shed stops after the same harvests
        _tier_dayret(segs_m, tiles, day, st)
    if CFG["sd_tier_pen_round"]:                   # learned from DSM: near-shed pens first, product into the shed
        _tier_pen_round(segs_m, tiles, day, st)
    if CFG["sd_tier_turn_plan"]:                   # learned from DSM: a shed stop after the harvest leg
        _tier_turn_plan(segs_m, tiles, day, st, S.get("_tier_prices") or {})
    if CFG["sd_tier_pass_drop"]:                   # user: whoever passes the shed with goods drops them
        _tier_pass_drop(segs_m, tiles, day, st)
    if int(CFG["sd_tier_feed_harvest"]) == 2:      # KB91 (mode 1): the search re-routed hands through wheat fields first,
        _tier_wy_fill(tiles)                       # shed hours -11 a world but moves +13: supply only after the search
    if CFG["sd_tier_pdrop"] and int(CFG["sd_tier_pdrop_early"]):   # the mid-day drop before the fills
        _tier_pdrop(S, segs_m, tiles, day, st)
    if int(CFG["sd_pen_sweep"]):                 # user: tile-service sweeps from the spawn tiles (see the flag)
        rest, collects = _tier_pensweep(segs, rec, set(anim), owner, st, rng)
        rate = float(CFG["sd_tier_rate"])
    elif int(CFG["sd_path_planner"]):            # user: tile services by value per hour, one search (see the flag)
        rest = _tier_psearch(segs, segs_m, rec, set(anim), owner, st, rng,
                             fbud=int((S.get("_shed_h0") or {}).get("FERTILIZER", 0) or 0))
        collects = {}
        rate = float(CFG["sd_tier_rate"])
    else:
        # ---- extras catalogue: bundles per tile and tier (the ops not already planned)
        collects = {}
        b3, b4 = [], []
        for i, r_ in sorted(rec.items()):
            ex = [o for o in r_["ops"] if not o["m"] and o["v"] > 0]
            if not ex:
                continue
            if i in anim:
                for o in ex:
                    if o["c"][0] == "COLLECT_FERTILIZER":
                        collects[i] = o
                        if int(CFG["sd_tier_collect_c"]):  # the stand-alone collect competes in phase C (see the flag)
                            b3.append({"tile": i, "ops": [o], "v": o["v"], "shared": True, "coll_c": True,
                                       "inplace": int(CFG["sd_tier_collect_c"]) == 1})
                        else:
                            b4.append({"tile": i, "ops": [o], "v": o["v"], "shared": True})
                fc = [o for o in ex if o["tier"] == 4 and o["c"][0] in ("FEED", "CARE")]
                if fc:
                    vfc = sum(o["v"] for o in fc)
                    minv_ = float(CFG["sd_tier_anim_c_minv"])
                    if CFG["sd_tier_goose_c_minv"] is not None and _animal(_tile(tiles, i)) == "GOOSE":
                        minv_ = float(CFG["sd_tier_goose_c_minv"])   # KWE: goose bundles against the waterings
                    if CFG["sd_tier_anim_c"] and vfc >= minv_:   # animal thread: tier C pool
                        mult_ = float(CFG["sd_tier_anim_c_mult"])
                        if CFG["sd_tier_goose_c_minv"] is not None and _animal(_tile(tiles, i)) == "GOOSE":
                            mult_ = float(CFG["sd_tier_goose_c_mult"])
                            st["tier_goose_c"] = st.get("tier_goose_c", 0) + 1
                        b3.append({"tile": i, "ops": fc, "v": vfc * mult_, "shared": True})
                        st["tier_anim_c"] = st.get("tier_anim_c", 0) + 1
                    else:
                        b4.append({"tile": i, "ops": fc, "v": vfc, "shared": True})
                hv = [o for o in ex if o["c"][0] in ("HARVEST", "PLACE_HARVEST")]
                t_d = _tile(tiles, i)
                dmin_ = (CFG["sd_tier_dawn_min"] or {}).get(t_d["animal"]) if int(CFG["sd_tier_dawn"]) == 2 else None
                if (hv and CFG["sd_tier_anim_harv"] and dmin_ is not None and any(o["c"][0] == "HARVEST" for o in hv)
                        and int(t_d.get("yield_units", 0) or 0) >= int(dmin_)
                        and min(_TIER_D[i][q] for q in _TIER_SHED_I) <= int(CFG["sd_tier_dawn_radius"])):
                    prod_ = ANIMALS[t_d["animal"]]["product"]    # sd_tier_dawn 2: the deferred harvest as a dawn-leg extra
                    y_ = int(t_d.get("yield_units", 0) or 0)
                    b3.append({"tile": i, "ops": hv, "v": y_ * float((S.get("_tier_prices") or {}).get(prod_, 0) or 0)
                               * float(CFG["sd_tier_dawn_frac"]), "v0": sum(o["v"] for o in hv), "shared": True, "dawn": True,
                               "prod": prod_, "units": y_, "rel": r_["rel"]})
                elif hv and CFG["sd_tier_anim_harv"]:            # animal thread: a deferred animal harvest is an extra
                    b4.append({"tile": i, "ops": hv, "v": sum(o["v"] for o in hv), "shared": True})
            else:
                e3 = [o for o in ex if o["tier"] == 3]
                if e3:
                    b3.append({"tile": i, "ops": e3, "v": sum(o["v"] for o in e3)})
        rate = float(CFG["sd_tier_rate"])
        idx_out = [k for k, s in enumerate(segs) if s["kind"] == "out"]
        idx_pri = [k for k, s in enumerate(segs) if s["kind"] in ("post", "ani")]
        # C. extras on the outbound hands: fertilize (paired with a collect) and waterings, by value per hour
        if CFG["sd_tier_anim_out"]:                    # user idea: pairs, then animals on the outbound leg, then the other extras
            rc_ = max(rate, float(CFG["sd_tier_rate_c"]))
            b3f = [bd for bd in b3 if any(o["c"][0] == "FERTILIZE" for o in bd["ops"])]
            b3r = [bd for bd in b3 if not any(o["c"][0] == "FERTILIZE" for o in bd["ops"])]
            _tier_fill(segs, idx_out, b3f, collects, owner, rc_, st, "c")
            _tier_anim_out(segs, idx_out, b3r, b4, collects, set(anim), rc_, st)
            _tier_fill(segs, idx_out, b3r, collects, owner, rc_, st, "c2")
            b3 = b3f + b3r
        else:
            _tier_fill(segs, idx_out, b3, collects, owner, max(rate, float(CFG["sd_tier_rate_c"])), st, "c")
        if int(CFG["sd_tier_dawn"]) == 2:              # dawn legs no hand took: plain deferred harvests again (phases D / E)
            for bd in [bd for bd in b3 if bd.get("dawn")]:
                b3.remove(bd)
                b4.append({"tile": bd["tile"], "ops": bd["ops"], "v": bd["v0"], "shared": True})
                st["tier_dawn_left"] = st.get("tier_dawn_left", 0) + 1
        if CFG["sd_tier_relief"] and b3:               # relief for the outbound extras before the melon hands take the free collects
            _tier_relief(segs, b3, collects, owner, max(rate, float(CFG["sd_tier_rate_c"])), st)
        # D. animal work: the melon hands' leftover labour first (and an animal hand)
        for bd in b4:                                  # collects already paired away are gone
            bd["ops"] = [o for o in bd["ops"] if o["c"][0] != "COLLECT_FERTILIZER" or bd["tile"] in collects]
            bd["v"] = sum(o["v"] for o in bd["ops"])
        b4 = [bd for bd in b4 if bd["ops"]]
        _tier_fill(segs, idx_pri, b4, collects, owner, rate, st, "d")
        # E. the slack left anywhere
        for bd in b4:
            bd["ops"] = [o for o in bd["ops"] if o["c"][0] != "COLLECT_FERTILIZER" or bd["tile"] in collects]
            bd["v"] = sum(o["v"] for o in bd["ops"])
        rest = [bd for bd in b3 + b4 if bd["ops"]]
        _tier_fill(segs, list(range(len(segs))), rest, collects, owner, rate, st, "e")
        if CFG["sd_tier_relief"] and rest:
            _tier_relief(segs, rest, collects, owner, rate, st)
    if CFG["sd_collect_make_room"]:               # collects at visited pens, room made by dropping cheaper optional ops
        _tier_collect_make_room(segs, rest, collects, tiles, day, st)
    if CFG["sd_tier_deliver"]:
        _tier_deliver(S, segs, tiles, day, st)
        if CFG["sd_tier_dump_refill"]:            # the hours the deferral / delivery trims freed: non-harvest extras
            rest2 = []
            for bd in rest:
                ops2 = [o for o in bd["ops"] if o["c"][0] not in ("HARVEST", "PLACE_HARVEST")
                        and (o["c"][0] != "COLLECT_FERTILIZER" or bd["tile"] in collects)]
                if ops2:
                    bd2 = dict(bd)
                    bd2["ops"] = ops2
                    bd2["v"] = sum(o["v"] for o in ops2)
                    rest2.append(bd2)
            rr_ = CFG["sd_tier_dump_refill_rate"]
            kinds_ = Counter(o["c"][0] + "|" + str(_animal(_tile(tiles, bd["tile"])) or (_tile(tiles, bd["tile"]) or {}).get("crop") if isinstance(_tile(tiles, bd["tile"]), dict) else "-")
                             for bd in rest2 for o in bd["ops"])
            n0_ = len(rest2)
            _tier_fill(segs, list(range(len(segs))), rest2, collects, owner, rate if rr_ is None else float(rr_), st, "r",
                       steal=bool(CFG["sd_tier_rebalance"]))
            st["_refill_day"] = {"cands": n0_, "left": len(rest2), "kinds": dict(kinds_),
                                 "ends": sorted(_tier_eval(sg)[0] for sg in segs if sg["stops"])}
    if CFG["sd_tier_path_collect"]:                # user: unspent hours -> inspect the pens along the planned path
        dd_ = st.get("_dump_day") or {}
        bud_ = [max(0, 100 - int(CFG["sd_tier_dump_buffer"]) - int(dd_.get("left", 0) or 0))]
        b0_ = bud_[0]
        free0_ = sum(max(0, 24 - _tier_eval(sg)[0]) for sg in segs if sg["kind"] in ("out", "post", "ani") and sg["stops"])
        n_pc_ = _tier_path_collect(segs, collects, st, bud_)
        free1_ = sum(max(0, 24 - _tier_eval(sg)[0]) for sg in segs if sg["kind"] in ("out", "post", "ani") and sg["stops"])
        st["_pcl_day"] = {"collects": n_pc_, "room": b0_, "free_h_before": free0_, "free_h_after": free1_, "left_collects": len(collects)}
    if CFG["sd_tier_early_deliver"]:               # user: strawberry / wool / milk early, from spare hand-hours, when behind DSM
        _tier_early_deliver(S, segs, tiles, day, st)
    if CFG["sd_tier_pdrop"] and not int(CFG["sd_tier_pdrop_early"]):   # user: DSM-style mid-day drops where the route already passes the shed
        _tier_pdrop(S, segs, tiles, day, st)
    if CFG["sd_tier_fert_merge"]:                  # user: shed fertilizer at the turn start, used on the hand's own watering stops
        fbud_ = [max(0, int((S.get("_shed_h0") or {}).get("FERTILIZER", 0) or 0) - int(CFG["sd_tier_sclu_fert_keep"])
                      - sum(int(M_.get("fpick", 0) or 0) for M_ in mel_of.values())
                      - sum(int(sg.get("fpick", 0) or 0) for sg in segs))]
        b0f_ = fbud_[0]
        n_fm_ = _tier_fert_merge(segs, tiles, day, S.get("_tier_prices") or {}, st, fbud_)
        st["_fmerge_day"] = {"fert": n_fm_, "budget": b0f_}
    if CFG["sd_tier_collect_swap"]:                # user: a full hand's collect moves to a hand with a spare hour on the way
        r0_ = st.get("tier_swap_refill", 0)
        n_sw_ = _tier_collect_swap(segs, rest, owner, rate, st)
        st["_swap_day"] = {"swaps": n_sw_, "refilled": st.get("tier_swap_refill", 0) - r0_}
    if CFG["sd_tier_out_collect_late"]:            # user: hands with free steps at the end collect fertilizer on the way out
        dd_ = st.get("_dump_day") or {}
        bud_ = [max(0, 100 - int(CFG["sd_tier_dump_buffer"]) - int(dd_.get("left", 0) or 0))]
        b0_ = bud_[0]
        co_ = CFG["sd_tier_anim_out_collect_only"]
        CFG["sd_tier_anim_out_collect_only"] = 1
        try:
            n_oc_ = _tier_anim_out(segs, [k for k, sg in enumerate(segs) if sg["kind"] in ("out", "post")], [], [], collects,
                                   set(anim), rate, st, spare=0, budget=bud_)
        finally:
            CFG["sd_tier_anim_out_collect_only"] = co_
        st["_ocl_day"] = {"collects": n_oc_, "room": b0_}
    if CFG["sd_tier_fert_carry"]:                  # user: hands with free hours carry shed fertilizer and fertilize more
        fav_ = max(0, int((S.get("_shed_h0") or {}).get("FERTILIZER", 0) or 0) - int(CFG["sd_tier_sclu_fert_keep"])
                   - sum(int(M_.get("fpick", 0) or 0) for M_ in mel_of.values()))
        dd_ = st.get("_dump_day") or {}
        head_ = max(0, 100 - int(CFG["sd_tier_dump_buffer"]) - int(dd_.get("left", 0) or 0))
        fb_ = []                                   # unplanned useful fertilize jobs (one bundle a tile)
        placed_ = {(x["tile"]) for sg in segs for x in sg["stops"] if any(o["c"][0] == "FERTILIZE" for o in x["ops"])}
        for i_, r_ in rec.items():
            fz_ = [o for o in r_["ops"] if o["c"][0] == "FERTILIZE"]
            if fz_ and i_ not in placed_ and _fert_useful(_tile(tiles, i_), day):
                fb_.append({"tile": i_, "ops": fz_[:1], "v": float(fz_[0]["v"]), "shared": True})
        fc_ = {"hands": 0, "picked": 0, "fert": 0, "cand": len(fb_), "avail": fav_, "head": head_}
        order_ = sorted(range(len(segs)), key=lambda k: _tier_eval(segs[k])[0]) if int(CFG["sd_tier_fert_carry_min"]) else range(len(segs))
        for k_ in order_:                          # earliest-ending hands first (sd_tier_fert_carry_min)
            sg = segs[k_]
            if fav_ <= 0:
                break
            if sg["kind"] not in ("out", "post") or sg["p0"] not in _TIER_SHED_I or sg.get("dawn"):
                continue
            ev0_ = _tier_eval(sg)
            if ev0_[0] >= 24:
                continue                           # no free hours at the end
            if not fb_:
                bm_ = min(int(CFG["sd_tier_fert_carry_min"]), fav_, head_)
                if bm_ > 0:                        # nothing to insert: carry for the day's end (sd_tier_idle_fert)
                    sg["fpick"] = bm_
                    head_ -= bm_
                    fav_ -= bm_
                    sg["ver"] += 1
                    fc_["hands"] += 1
                    fc_["picked"] += bm_
                    fc_["carry_only"] = fc_.get("carry_only", 0) + 1
                continue
            nf0_ = sum(1 for x in sg["stops"] for o in x["ops"] if o["c"][0] == "FERTILIZE")
            sg["fpick"] = min(fav_, 24 - ev0_[0])
            n_ = _tier_fill(segs, [k_], fb_, {}, owner, rate, st, "fc")
            need_, run_ = 0, 0                     # the pickup the route needs: max over the route of fertilizes - collects
            for x in sg["stops"]:
                for o in x["ops"]:
                    if o["c"][0] == "COLLECT_FERTILIZER":
                        run_ -= 1
                    elif o["c"][0] == "FERTILIZE":
                        run_ += 1
                        need_ = max(need_, run_)
            if not n_ or need_ <= 0:
                bm_ = min(int(CFG["sd_tier_fert_carry_min"]), fav_, head_)
                sg["fpick"] = bm_ if bm_ > 0 else 0
                if bm_ > 0:                        # nothing inserted: carry for the day's end (sd_tier_idle_fert)
                    head_ -= bm_
                    fav_ -= bm_
                    sg["ver"] += 1
                    fc_["hands"] += 1
                    fc_["picked"] += bm_
                    fc_["carry_only"] = fc_.get("carry_only", 0) + 1
                continue
            need_ = max(need_, int(CFG["sd_tier_fert_carry_min"]))
            sp_ = min(int(CFG["sd_tier_fert_carry_spare"]), head_, fav_ - need_)
            sg["fpick"] = need_ + max(0, sp_)
            head_ -= max(0, sp_)
            fav_ -= sg["fpick"]
            sg["ver"] += 1
            fc_["hands"] += 1
            fc_["picked"] += sg["fpick"]
            fc_["fert"] += sum(1 for x in sg["stops"] for o in x["ops"] if o["c"][0] == "FERTILIZE") - nf0_
        st["_fcarry_day"] = fc_
    if CFG["sd_tier_fert_use"]:                    # carried fertilizer spent on the route's own unplaced fertilizes
        n_fu_ = _tier_fert_use(segs, rec, tiles, day, st)
        st["_fuse_day"] = n_fu_
    if CFG["sd_wheat_fert_mand"]:                  # the routes' shed pickups for their mandatory fertilizes
        fav_m = max(0, int((S.get("_shed_h0") or {}).get("FERTILIZER", 0) or 0)
                    - sum(int(M_.get("fpick", 0) or 0) for M_ in mel_of.values())
                    - sum(int(sg.get("fpick", 0) or 0) for sg in segs))
        fm_ = {"need": 0, "picked": 0, "short": 0}
        for sg in segs:
            n_ = _tier_fmand_need(sg["stops"], int(sg.get("fpick", 0) or 0))
            if n_ <= 0:
                continue
            k_ = min(n_, fav_m)
            sg["fpick"] = int(sg.get("fpick", 0) or 0) + k_
            fav_m -= k_
            fm_["need"] += n_
            fm_["picked"] += k_
            fm_["short"] += n_ - k_
        st["_fmand_day"] = fm_
    if int(CFG["sd_polish"]) and not int(CFG["sd_polish_final"]):   # hand-plan lessons (see the flag)
        _tier_polish(S, segs, rest, tiles, day, st)
    if CFG["sd_manual_plan"]:                      # research: the day's hand plan replaces the planned routes
        _tier_manual_apply(S, segs, rec, day, st)
    # ---- routes per unit
    def build_route(s, count=True):
        u = s["u"]
        items = []
        if s["kind"] == "post":
            M = mel_of[u]
            nfm_ = sum(1 for x in M["stops"] for o in x["ops"] if o["c"][0] == "FEED")
            if nfm_:                                   # an animal priority run feeds on its way: wheat first
                items.append({"kind": "pick", "item": "WHEAT", "n": nfm_})
            if M.get("fpick"):                         # sd_tier_sclu_fert: the trip's fertilizer from the shed
                items.append({"kind": "pick", "item": "FERTILIZER", "n": int(M["fpick"])})
            for x in M["stops"]:
                items.append({"kind": "place" if x.get("place") else "stop", "tile": x["tile"],
                              "ops": [o["c"] for o in x["ops"]], "mand": [o["m"] for o in x["ops"]]})
                if x.get("sell_now"):
                    items[-1]["sell_now"] = True
        if u in dawn_of:                           # sd_tier_dawn: the round trip first, the wheat pickup after it
            for x in dawn_of[u]["stops"]:
                items.append({"kind": "stop", "tile": x["tile"], "ops": [o["c"] for o in x["ops"]],
                              "mand": [o["m"] for o in x["ops"]], "rel": x.get("rel", 0)})
        if s.get("manual_seq") is not None:         # sd_manual_plan: the hand route's own item sequence
            seq_ = s["manual_seq"]
            nf0_ = 0
            for x in seq_:
                if x.get("pick_item"):
                    break
                nf0_ += sum(1 for o in x["ops"] if o["c"][0] == "FEED")
            if nf0_:
                items.append({"kind": "pick", "item": "WHEAT", "n": nf0_})
            if s.get("fpick"):
                items.append({"kind": "pick", "item": "FERTILIZER", "n": int(s["fpick"])})
            for j_, x in enumerate(seq_):
                if x.get("pick_item"):
                    n_ = sum(1 for y_ in seq_[j_ + 1:] if not y_.get("pick_item") for o in y_["ops"] if o["c"][0] == "FEED")
                    items.append({"kind": "pick", "item": "WHEAT", "n": max(1, n_)})
                else:
                    items.append({"kind": "stop", "tile": x["tile"], "ops": [o["c"] for o in x["ops"]],
                                  "mand": [o["m"] for o in x["ops"]], "rel": 0})
            ev = _tier_eval(s, want_hours=True) if s["stops"] else (s["t0"], 0, 0, 0, [])
            r_out = {"items": items, "k": 0, "sub": 0, "kind": s["kind"], "waited": 0, "wait": {}, "t0plan": s["t0"],
                     "p0plan": s["p0"], "hold0": bool(s.get("hold0")), "plan_hours": [(b_, c_[0], h) for b_, c_, h in ev[4]]}
            sm = {"u": u, "kind": s["kind"], "t0": s["t0"], "end": ev[0], "late": ev[1], "hop": ev[2], "bad": ev[3],
                  "drop": None, "melons": [], "manual": True, "stops": [[x["tile"], [o["c"][0] for o in x["ops"]]] for x in s["stops"]]}
            if CFG["sd_tier_log_v"]:
                sm["stops_v"] = [[x["tile"], [[o["c"][0], int(o["m"]), o["tier"], round(o["v"], 1)] for o in x["ops"]]]
                                 for x in s["stops"]]
            return r_out, sm
        nf, na = _tier_picks(s["stops"])
        if _TIER_WY and count:
            st["_feedh_day"] = st.get("_feedh_day", 0) + sum(1 for x in s["stops"] for o in x["ops"] if o["c"][0] == "FEED") - nf
        kd_ = 0
        while kd_ < len(s["stops"]) and s["stops"][kd_].get("dawn"):   # sd_tier_dawn 2: the dawn leg before the pickups
            x = s["stops"][kd_]
            items.append({"kind": "stop", "tile": x["tile"], "ops": [o["c"] for o in x["ops"]],
                          "mand": [o["m"] for o in x["ops"]], "rel": x.get("rel", 0)})
            kd_ += 1
        if nf:
            items.append({"kind": "pick", "item": "WHEAT", "n": nf})
        if s.get("fpick"):                         # sd_tier_fert_carry: the route's fertilizer from the shed
            items.append({"kind": "pick", "item": "FERTILIZER", "n": int(s["fpick"])})
        for a_, v_ in na.items():
            items.append({"kind": "pick", "item": a_, "n": v_})
        for x in s["stops"][kd_:]:
            items.append({"kind": "stop", "tile": x["tile"], "ops": [o["c"] for o in x["ops"]],
                          "mand": [o["m"] for o in x["ops"]], "rel": x.get("rel", 0)})
            if x.get("copy"):
                items[-1]["copy"] = True
            if x.get("sell_all"):                  # sd_tier_deliver_skip: a go-home drop sells everything, wheat included
                items[-1]["sell_all"] = True
        ev = _tier_eval(s, want_hours=True) if s["stops"] else (s["t0"], 0, 0, 0, [])
        r_out = {"items": items, "k": 0, "sub": 0, "kind": s["kind"], "waited": 0, "wait": {}, "t0plan": s["t0"], "p0plan": s["p0"],
                 "hold0": bool(s.get("hold0")),
                 "plan_hours": (list(dawn_of[u]["hours"]) if u in dawn_of else []) + [(b_, c_[0], h) for b_, c_, h in ev[4]]}
        sm = {"u": u, "kind": s["kind"], "t0": s["t0"], "end": ev[0], "late": ev[1], "hop": ev[2], "bad": ev[3],
              "drop": mel_of[u]["drop"] if u in mel_of else None,
              "melons": [x["tile"] for x in mel_of[u]["stops"] if not x.get("place")] if u in mel_of else [],
              "stops": [[x["tile"], [o["c"][0] for o in x["ops"]]] for x in s["stops"]]}
        if u in dawn_of:
            sm["dawn"] = [dawn_of[u]["pen"], dawn_of[u]["units"], dawn_of[u]["drop"]]
            if "dsm" in dawn_of[u]:
                sm["dawn_dsm"] = dawn_of[u]["dsm"]
                sm["dawn_pens"] = dawn_of[u]["pens"]
        elif s["stops"] and s["stops"][0].get("dawn"):
            nd_ = sum(len(x["ops"]) for x in s["stops"] if x.get("dawn"))
            t_p = _tile(tiles, s["stops"][0]["tile"])
            sm["dawn"] = [s["stops"][0]["tile"], int(t_p.get("yield_units", 0) or 0) if isinstance(t_p, dict) else 0,
                          ev[4][nd_ - 1][2] if len(ev[4]) >= nd_ else None]
        if CFG["sd_tier_log_v"]:                   # animal thread: [op, mandatory, tier, value] per planned op
            sm["stops_v"] = [[x["tile"], [[o["c"][0], int(o["m"]), o["tier"], round(o["v"], 1)] for o in x["ops"]]]
                             for x in s["stops"]]
        return r_out, sm

    if int(CFG["sd_tier_route_swap"]) == 2:        # user: finished routes to the hands whose spawn tile suits them
        _tier_route_swap_final(segs, owner, set(anim), st)
    sp1_true = None
    spx_wrong = None
    if int(CFG["sd_tier_spawn_exact"]):            # two-stage plan: the hour-1 hires from their exact spawn tiles (see the flag)
        st.pop("_spx_wrong_last", None)
        sp1_true = _tier_spawn_exact(segs, units, rest, collects, owner, rate, st, build_route)
        spx_wrong = st.pop("_spx_wrong_last", None)
    routes_u = {}
    summ = []
    for s in segs:
        r_out, sm = build_route(s)
        routes_u[s["u"]] = r_out
        summ.append(sm)
    unplanned = [[bd["tile"], [o["c"][0] for o in bd["ops"]], round(bd["v"], 1)] for bd in rest]
    pol_ = (segs, rest, build_route) if (int(CFG["sd_polish"]) and int(CFG["sd_polish_final"])) else None
    return {"day": day, "routes": routes_u, "log": [], "cnt": Counter(), "owner": owner, "_sp1_true": sp1_true, "_spx_wrong": spx_wrong,
            "_pol": pol_,
                 "summary": {"units": summ, "left_out_melons": left, "mand_late": late_m, "unplanned": unplanned,
                             "plan_ms": round(1000 * (time.perf_counter() - t_start), 1), "search_cost": round(cost, 2),
                             "want": want, "n_mand_stops": len(stops_all)}}


def _tier_check(c, t, inv, day, seeds_left):
    """do / skip / dig / wait for command c on tile t with the unit's inventory."""
    op = c[0]
    if op == "WATER":
        return "do" if (_is_plant(t) and not t.get("watered_today")) else "skip"
    if op == "HARVEST":
        if isinstance(t, dict) and int(t.get("yield_units", 0) or 0) > 0:
            if _is_plant(t):
                cr = CROPS.get(t.get("crop"))
                return "do" if cr and day - int(t.get("planted_day", day)) >= cr["first"] else "skip"
            return "do" if _animal(t) else "skip"
        return "skip"
    if op in ("PLANT", "BUILD_COOP", "BUILD_PASTURE"):
        if t is None:
            if op == "PLANT" and seeds_left.get(c[1], 0) <= 0:
                return "noseed"
            return "do"
        if _is_weed(t) or (isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE") and "animal" not in t
                           and not (op == "BUILD_COOP" and t.get("kind") == "COOP")):
            return "dig"
        if _is_plant(t):
            return "wait"
        return "skip"
    if op == "DIG":
        return "do" if (t is not None and not _animal(t)) else "skip"
    if op == "PLACE":
        if len(c) > 1 and c[1] in ANIMALS:
            ok = (isinstance(t, dict) and t.get("kind") == ANIMALS[c[1]]["structure"] and "animal" not in t
                  and inv.get(c[1], 0) > 0)
            return "do" if ok else "skip"
        return "skip"
    if op == "FEED":
        return "do" if (_animal(t) and not t.get("fed_today") and inv.get("WHEAT", 0) > 0) else "skip"
    if op == "CARE":
        return "do" if (_animal(t) and not t.get("cared_today")) else "skip"
    if op == "COLLECT_FERTILIZER":
        return "do" if (_animal(t) and t.get("fertilizer_available")) else "skip"
    if op == "DROP":
        if not any(v > 0 for v in inv.values()):
            return "skip"
        return "do"
    if op == "FERTILIZE":
        return "do" if (_is_plant(t) and inv.get("FERTILIZER", 0) > 0
                        and int(t.get("fertilized_until_day", -1)) < day) else "skip"
    return "do"


def _tier_pending(TP, skip_u=None):
    """tiles the routes (all units, or all but skip_u) still FERTILIZE / WATER today"""
    pf, pw = set(), set()
    for u2, R2 in TP["routes"].items():
        if u2 == skip_u:
            continue
        for j2, it2 in enumerate(R2["items"][R2["k"]:]):
            if it2.get("kind") != "stop":
                continue
            ops2 = it2["ops"][R2["sub"]:] if j2 == 0 else it2["ops"]
            if any(c2[0] == "FERTILIZE" for c2 in ops2):
                pf.add(it2["tile"])
            if any(c2[0] == "WATER" for c2 in ops2):
                pw.add(it2["tile"])
    return pf, pw


def _tier_rest_time(R, p):
    """hours the unit's remaining plan needs from position p (walks + ops + shed pickups)"""
    t, q = 0, tuple(p)
    for j, it in enumerate(R["items"][R["k"]:]):
        if it["kind"] == "pick":
            s_ = _near_shed(q)
            t += abs(q[0] - s_[0]) + abs(q[1] - s_[1]) + 1
            q = s_
        else:
            b = (it["tile"] % 10, it["tile"] // 10)
            t += abs(q[0] - b[0]) + abs(q[1] - b[1]) + len(it["ops"][R["sub"]:] if j == 0 else it["ops"])
            q = b
    return t


def _tier_fert_opp(TP, R, u, p, inv, tiles, day, hour):
    """sd_tier_fert_opp: FERTILIZE / WATER on the tile the unit stands on, or None (see the flag)."""
    idx = p[1] * 10 + p[0]
    cur = R.get("_opp_tgt")
    t = _tile(tiles, idx)
    if cur is not None:
        R["_opp_tgt"] = None
        if cur == idx and _is_plant(t) and not t.get("watered_today") and int(t.get("fertilized_until_day", -1) or -1) >= day and hour <= 23:
            TP["cnt"]["fert_opp_water"] += 1
            R.setdefault("done", []).append((hour, idx, "WATER"))
            return ["WATER"]
    if not _is_plant(t) or int(t.get("fertilized_until_day", -1) or -1) >= day:
        return None
    own_f = sum(1 for j, it in enumerate(R["items"][R["k"]:]) if it["kind"] == "stop"
                for c in (it["ops"][R["sub"]:] if j == 0 else it["ops"]) if c[0] == "FERTILIZE")
    if int(inv.get("FERTILIZER", 0) or 0) <= own_f:
        return None
    if _tier_fert_gain(idx, t, day) <= 0:
        return None
    pf, pw = _tier_pending(TP)
    if idx in pf:
        return None
    wat = not t.get("watered_today") and idx not in pw
    if hour + 1 + (1 if wat else 0) + _tier_rest_time(R, p) > 23:
        return None
    R["_opp_tgt"] = idx if wat else None
    TP["cnt"]["fert_opp_done"] += 1
    R.setdefault("done", []).append((hour, idx, "FERTILIZE"))
    return ["FERTILIZE"]


def _tier_idle_fert(TP, R, u, p, inv, tiles, day, hour, shed_left):
    """sd_tier_idle_fert: the next command of a hand with no planned work left, or None (see the flag). A target gets
    FERTILIZE then WATER when not watered today (engine: a one-time crop grows on a WATER in its window, +2 when fertilized
    at that moment; an ongoing crop's fertilized production needs the night's water) - unwatered targets first."""
    cnt = TP["cnt"]
    claims = TP.setdefault("_idle_fert_claims", {})         # tile -> unit, for the day
    if TP.get("_idle_fert_day") != day:
        claims.clear()
        TP["_idle_fert_day"] = day
    left = 23 - hour
    dist = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
    cur = R.get("_idle_tgt")
    if cur is not None:                             # finishing a target: its WATER after the FERTILIZE
        t = _tile(tiles, cur)
        if tuple(p) == (cur % 10, cur // 10) and _is_plant(t) and not t.get("watered_today") and int(t.get("fertilized_until_day", -1) or -1) >= day                 and left >= 1:
            R["_idle_tgt"] = None
            claims.pop(cur, None)
            cnt["idle_fert_water"] += 1
            R.setdefault("done", []).append((hour, cur, "WATER"))
            return ["WATER"]
        R["_idle_tgt"] = None
        claims.pop(cur, None)
    pend_f, pend_w = set(), set()                  # tiles other hands' plans still fertilize / water today
    for u2, R2 in TP["routes"].items():
        if u2 == u:
            continue
        for j2, it2 in enumerate(R2["items"][R2["k"]:]):
            if it2.get("kind") != "stop":
                continue
            ops2 = it2["ops"][R2["sub"]:] if j2 == 0 else it2["ops"]
            if any(c2[0] == "FERTILIZE" for c2 in ops2):
                pend_f.add(it2["tile"])
            if any(c2[0] == "WATER" for c2 in ops2):
                pend_w.add(it2["tile"])
    targets = []
    for i in range(100):
        t = _tile(tiles, i)
        if not _is_plant(t) or claims.get(i, u) != u or i in pend_f:
            continue
        if int(t.get("fertilized_until_day", -1) or -1) >= day:
            continue
        g = _tier_fert_gain(i, t, day)
        if g <= 0:
            continue
        wet = bool(t.get("watered_today")) or i in pend_w   # a planned water later collects the bonus
        targets.append((wet, dist(p, (i % 10, i // 10)), -g, i))
    targets.sort()
    have = int(inv.get("FERTILIZER", 0) or 0)
    if have > 0:
        for wet, d_, g_, i in targets:
            if d_ + 1 + (0 if wet else 1) > left:
                continue
            for k2 in [k2 for k2, v2 in claims.items() if v2 == u and k2 != i]:
                del claims[k2]
            claims[i] = u
            q = (i % 10, i // 10)
            if d_ == 0:
                R["_idle_tgt"] = None if wet else i
                if wet:
                    claims.pop(i, None)
                cnt["idle_fert_done"] += 1
                R.setdefault("done", []).append((hour, i, "FERTILIZE"))
                return ["FERTILIZE"]
            return _step_toward(p, q)
        return None
    sh = _near_shed(p)
    ds = dist(p, sh)
    reach = [i for wet, d_, g_, i in targets if ds + 1 + dist(sh, (i % 10, i // 10)) + 1 + (0 if wet else 1) <= left]
    stock = int(shed_left.get("FERTILIZER", 0) or 0)
    head = 100 - int(CFG["sd_tier_dump_buffer"]) - int(TP.get("_load_now", 0) or 0) - int(TP.get("_harv_left", 0) or 0)
    k = min(len(reach), stock, int(CFG["sd_tier_idle_fert_max"]), max(0, head))
    if k <= 0:
        return None
    if p != sh:
        return _step_toward(p, sh)
    shed_left["FERTILIZER"] = stock - k
    cnt["idle_fert_picked"] += k
    return ["PICKUP", "FERTILIZER", k]


def _tier_idle_work(TP, R, u, p, inv, tiles, day, hour):
    """sd_tier_idle_work: the next command of a hand with no planned work left, or None (see the flag)."""
    S = _S or {}
    prices = S.get("_tier_prices") or {}
    last_day = int(S.get("_tier_last_day", 29))
    if hour >= 24 or day >= last_day:
        return None
    cnt = TP["cnt"]
    claims = TP.setdefault("_idle_claims", {})
    if TP.get("_idle_day") != day:
        claims.clear()
        TP["_idle_day"] = day
        TP["_idle_coll"] = 0
    for k_ in [k_ for k_, v_ in claims.items() if v_ == u]:
        del claims[k_]
    left = 24 - hour
    pend = {c_: set() for c_ in ("WATER", "CARE", "FEED", "COLLECT_FERTILIZER")}
    for u2, R2 in TP["routes"].items():
        if u2 == u:
            continue
        for j2, it2 in enumerate(R2["items"][R2["k"]:]):
            if it2.get("kind") != "stop":
                continue
            for c2 in (it2["ops"][R2["sub"]:] if j2 == 0 else it2["ops"]):
                if c2[0] in pend:
                    pend[c2[0]].add(it2["tile"])
    pr = lambda k: float(prices.get(k, 0) or 0)
    fp = pr("FERTILIZER")
    wc = float(CFG["sd_tier_idle_work_wc"])
    head = (100 - int(CFG["sd_tier_dump_buffer"]) - int(TP.get("_load_now", 0) or 0) - int(TP.get("_harv_left", 0) or 0)
            - int(TP.get("_idle_coll", 0) or 0))
    best = None
    for i in range(100):
        if claims.get(i, u) != u:
            continue
        t = _tile(tiles, i)
        if not isinstance(t, dict):
            continue
        q = (i % 10, i // 10)
        d_ = abs(p[0] - q[0]) + abs(p[1] - q[1])
        if d_ + 1 > left:
            continue
        cands = []
        if _animal(t):
            a = ANIMALS[t["animal"]]
            pd_ = int(t.get("placed_day", day))
            ahead = any((n + 1 - pd_ - a["first"]) >= 0 and (n + 1 - pd_ - a["first"]) % a["interval"] == 0
                        for n in range(day + 1, last_day))
            if (not t.get("cared_today") and i not in pend["CARE"] and ahead
                    and (t.get("fed_today") or i in pend["FEED"])):
                cands.append((pr(a["product"]), "CARE"))
            if t.get("fertilizer_available") and i not in pend["COLLECT_FERTILIZER"] and head > 0 and fp >= 2:
                cands.append((fp, "COLLECT_FERTILIZER"))
        elif _is_plant(t) and not t.get("watered_today") and i not in pend["WATER"]:
            cr = CROPS.get(t.get("crop"))
            if cr:
                a_ = day - int(t.get("planted_day", day))
                fn = int(t.get("fertilized_until_day", -1) or -1) >= day
                v = 0.0
                if not cr["ongoing"] and (cr["maxday"] + 1) // 2 <= a_ <= cr["maxday"]:
                    v = min(2 if fn else 1, max(0, cr["max"] - int(t.get("yield_units", 0) or 0))) * pr(t["crop"])
                elif cr["ongoing"] and fn:
                    iv = max(1, int(cr["interval"]))
                    ds = day + 1 - int(t.get("planted_day", day)) - cr["first"]
                    if ds >= 0 and ds % iv == 0 and ds // iv + 1 <= cr["max"]:
                        v = pr(t["crop"])
                if int(t.get("consecutive_unwatered", 0) or 0) == 0 and day < last_day - 1:
                    v += wc
                cands.append((v, "WATER"))
        for v, c in cands:
            if v < float(CFG["sd_tier_idle_work_minv"]):
                continue
            sc = v / (d_ + 1)
            if best is None or sc > best[0]:
                best = (sc, i, c, d_, q)
    if best is None:
        return None
    sc, i, c, d_, q = best
    if d_ == 0:
        cnt["idle_work_" + c] += 1
        if c == "COLLECT_FERTILIZER":
            TP["_idle_coll"] = int(TP.get("_idle_coll", 0) or 0) + 1
        R.setdefault("done", []).append((hour, i, c))
        return [c]
    claims[i] = u
    cnt["idle_work_walk"] += 1
    return _step_toward(p, q)


def _tier_cmd(TP, R, u, p, inv, tiles, day, hour, step, seeds_left, shed_left):
    items = R["items"]
    lg = TP["log"]
    cnt = TP["cnt"]
    if hour < int(R.get("t0", 0)):
        return ["PASS"]                            # the farmer holds at hour 0 (sd_tier_farmer_hold)
    if CFG["sd_tier_fert_opp"] and int(inv.get("FERTILIZER", 0) or 0) > 0:
        a_ = _tier_fert_opp(TP, R, u, p, inv, tiles, day, hour)
        if a_ is not None:
            return a_
    guard = 0
    while R["k"] < len(items) and guard < 50:
        guard += 1
        it = items[R["k"]]
        if it["kind"] == "pick":
            s = _near_shed(p)
            if p != s:
                return _step_toward(p, s)
            have = int(shed_left.get(it["item"], 0))
            n = min(int(it["n"]), have)
            if n <= 0:
                if it["item"] == "WHEAT" and CFG["sd_tier_wheat"] and hour < 8 and R["waited"] < 2:
                    R["waited"] += 1
                    cnt["wait_wheat"] += 1
                    return ["PASS"]
                if it["item"] in ANIMALS and hour < 20 and R["waited"] < 6:
                    R["waited"] += 1
                    cnt["wait_pick"] += 1
                    return ["PASS"]
                lg.append([step, u, "pick_none", s[1] * 10 + s[0], it["item"]])
                cnt["pick_none"] += 1
                R["k"] += 1
                continue
            shed_left[it["item"]] = have - n
            R["k"] += 1
            R.setdefault("done", []).append((hour, s[1] * 10 + s[0], "PICKUP"))
            if n < int(it["n"]):
                lg.append([step, u, "pick_short", s[1] * 10 + s[0], "%s %d/%d" % (it["item"], n, it["n"])])
                cnt["pick_short"] += 1
            return ["PICKUP", it["item"], n]
        if it["kind"] == "place":
            m = int(inv.get("MELON", 0) or 0)
            q = (it["tile"] % 10, it["tile"] // 10)
            if m <= 0:
                R["k"] += 1
                continue
            if p != q:
                return _step_toward(p, q)
            R["k"] += 1
            R.setdefault("done", []).append((hour, it["tile"], "PLACE"))
            return ["PLACE", "MELON", m]
        q = (it["tile"] % 10, it["tile"] // 10)
        if p != q:
            return _step_toward(p, q)
        if R["sub"] >= len(it["ops"]):
            R["k"] += 1
            R["sub"] = 0
            continue
        c = it["ops"][R["sub"]]
        t = _tile(tiles, it["tile"])
        if c[0] == "DELIVER":                      # sd_tier_turnaround: the harvested goods into the shed, sold at once
            R["sub"] += 1
            later = [c2 for it2 in items[R["k"] + 1:] if it2["kind"] == "stop" for c2 in it2["ops"]]
            keep_ = {"WHEAT": sum(1 for c2 in later if c2[0] == "FEED"),
                     "FERTILIZER": sum(1 for c2 in later if c2[0] == "FERTILIZE")}
            cand_ = [(int(n_ or 0) - keep_.get(k_, 0), k_) for k_, n_ in inv.items() if k_ in PRODUCTS]
            if len(c) > 1:                             # a named product (sd_tier_dayret_shape): that product, not the largest pile
                cand_ = [x for x in cand_ if x[1] == c[1]]
            cand_ = [x for x in cand_ if x[0] > 0]
            if cand_ and _is_shed_adjacent_t(p):
                n_, k_ = max(cand_)
                TP.setdefault("dsell", Counter())[k_] += n_
                if it.get("sell_now"):             # sd_tier_sclu: sold on arrival, books products included
                    TP.setdefault("dsell_now", Counter())[k_] += n_
                TP["cnt"]["turn_place"] += 1
                TP["cnt"]["turn_units"] += n_
                R.setdefault("done", []).append((hour, it["tile"], "DELIVER"))
                return ["PLACE", k_, n_]
            continue
        if c[0] == "PLACE_HARVEST":                # sd_tier_access_drop: the harvested product into the shed, sold at once
            R["sub"] += 1
            n_ = int(inv.get(c[1], 0) or 0)
            if CFG["sd_tier_access_keep"] and c[1] == "WHEAT":   # keep the feed wheat of the rest of this route
                need_ = 0
                for j_, it2_ in enumerate(R["items"][R["k"]:]):
                    ops2_ = it2_.get("ops") or []
                    ops2_ = ops2_[R["sub"]:] if j_ == 0 else ops2_
                    need_ += sum(1 for c2_ in ops2_ if isinstance(c2_, list) and c2_ and c2_[0] == "FEED")
                n_ = max(0, n_ - need_)
                if need_:
                    TP["cnt"]["access_keep_wheat"] += min(need_, int(inv.get(c[1], 0) or 0))
            if n_ > 0 and _is_shed_adjacent_t(p):
                TP.setdefault("dsell", Counter())[c[1]] += n_
                TP["cnt"]["access_drop"] += 1
                TP["cnt"]["access_drop_units"] += n_
                R.setdefault("done", []).append((hour, it["tile"], "PLACE_HARVEST"))
                return ["PLACE", c[1], n_]
            continue
        v = _tier_check(c, t, inv, day, seeds_left)
        if v == "do" and c[0] == "DROP" and CFG["sd_tier_deliver_check"] and TP.get("_load_now") is not None and not it.get("copy"):
            if TP["_load_now"] + (int(TP.get("_harv_left", 0)) if CFG["sd_tier_dump_fix"] else 0) <= 100 - int(CFG["sd_tier_dump_buffer"]):
                v = "skip"                             # the shed will hold everything at midnight: no delivery needed
                cnt["deliver_skipped"] += 1
        if v == "do":
            R["sub"] += 1
            if c[0] == "PLANT":
                seeds_left[c[1]] = seeds_left.get(c[1], 0) - 1
            if c[0] == "DROP":                         # planned delivery: the market sells the goods this hour
                nosell_ = set(CFG["sd_tier_deliver_keep"] or ())
                all_ = bool(it.get("sell_all"))       # a go-home drop on a heavy night: wheat too (room beats keeping it)
                TP.setdefault("dsell", Counter()).update(
                    {k: int(v) for k, v in inv.items() if k in PRODUCTS and (all_ or (k != "WHEAT" and k not in nosell_)) and v > 0})
                if all_:
                    cnt["skipdrop_units"] += sum(int(v) for k, v in inv.items() if k in PRODUCTS and v > 0)
                cnt["deliver"] += 1
            R.setdefault("done", []).append((hour, it["tile"], c[0]))
            return list(c)
        if v == "dig":
            lg.append([step, u, "dig_fix", it["tile"], c[0]])
            cnt["dig_fix"] += 1
            return ["DIG"]
        wk = (R["k"], R["sub"])
        nw = R["wait"].get(wk, 0)
        if v in ("wait", "noseed") and hour < 23 and nw < int(CFG["sd_tier_wait_max"]):
            R["wait"][wk] = nw + 1
            cnt["wait_" + v] += 1
            if nw == 0:
                lg.append([step, u, "wait_" + v, it["tile"], c[0]])
            return ["PASS"]
        lg.append([step, u, "skip", it["tile"], " ".join(str(x) for x in c)])
        cnt["skip_" + c[0]] += 1
        R["sub"] += 1
    if CFG["sd_tier_idle_fert"] and hour < 23:     # the plan is done: fertilize more with shed fertilizer (user)
        a_ = _tier_idle_fert(TP, R, u, p, inv, tiles, day, hour, shed_left)
        if a_ is not None:
            return a_
    if CFG["sd_tier_idle_work"]:                   # the plan is done: the best job on the live board (see the flag)
        a_ = _tier_idle_work(TP, R, u, p, inv, tiles, day, hour)
        if a_ is not None:
            return a_
    return ["PASS"]


def _tier_override(S, obs, step, day, hour, tiles, pos, invs, actions, seeds, shed):
    TP = S.get("tier")
    if not TP or TP.get("day") != day:
        return
    L = _sd_state(S)
    seeds_left = dict(seeds)
    shed_left = dict(shed)
    snap = {}
    TP["_load_now"] = sum(int(v or 0) for v in shed.values()) + sum(int(v or 0) for inv_ in invs for k_, v_ in (inv_ or {}).items()
                                                                  for v in [v_] if k_ in PRODUCTS)
    if CFG["sd_tier_dump_fix"]:                    # units the routes still harvest today (they reach the midnight dump)
        hl_ = 0
        for R_ in TP["routes"].values():
            for j_, it_ in enumerate(R_["items"][R_["k"]:]):
                if it_.get("kind") != "stop":
                    continue
                ops_ = it_["ops"][R_["sub"]:] if j_ == 0 else it_["ops"]
                if any(isinstance(c_, list) and c_ and c_[0] == "HARVEST" for c_ in ops_):
                    hl_ += int((_tile(tiles, it_["tile"]) or {}).get("yield_units", 0) or 0) if isinstance(_tile(tiles, it_["tile"]), dict) else 0
        TP["_harv_left"] = hl_
    if CFG["sd_tier_spawn_remap"] and not TP.get("_remapped"):
        late_ = sorted(u for u, R_ in TP["routes"].items() if R_.get("t0plan") == 2 and u > 0 and R_.get("k", 0) == 0)
        if (late_ and int(CFG["sd_tier_spawn_exact"]) and all(u < len(pos) for u in late_)
                and all(TP["routes"][u].get("p0plan") == pos[u][1] * 10 + pos[u][0] for u in late_)):
            TP["_remapped"] = True                 # sd_tier_spawn_exact: everyone stands where planned
            TP["cnt"]["spawn_exact_ok"] += 1
            late_ = []
        if late_ and all(u < len(pos) for u in late_):
            TP["_remapped"] = True                 # the hour-1 hires exist now: match routes to their real spawn tiles
            import itertools as _it

            def first_tile(R_):
                for it_ in R_["items"]:
                    if it_["kind"] != "pick":
                        return (it_["tile"] % 10, it_["tile"] // 10)
                return None

            tgt = {u: first_tile(TP["routes"][u]) for u in late_}
            cost_ = lambda a, u: 0 if tgt[u] is None else abs(pos[a][0] - tgt[u][0]) + abs(pos[a][1] - tgt[u][1])
            best_ = None
            for perm in _it.permutations(late_):
                c_ = sum(cost_(a, u) for a, u in zip(late_, perm))
                if best_ is None or c_ < best_[0]:
                    best_ = (c_, perm)
            base_ = sum(cost_(a, a) for a in late_)
            if best_ and best_[0] < base_:
                old_ = {u: TP["routes"][u] for u in late_}
                for a, u in zip(late_, best_[1]):
                    TP["routes"][a] = old_[u]
                TP["cnt"]["spawn_remap"] += 1
                TP["cnt"]["spawn_remap_saved"] += base_ - best_[0]
    for u in sorted(TP["routes"]):
        R = TP["routes"][u]
        if u >= len(pos) or u >= len(actions):
            if not R.get("missing") and hour >= 2:
                R["missing"] = True
                TP["log"].append([step, u, "unit_missing", -1, ""])
                TP["cnt"]["unit_missing"] += 1
            continue
        inv = invs[u] if u < len(invs) else {}
        actions[u] = _tier_cmd(TP, R, u, tuple(pos[u]), inv, tiles, day, hour, step, seeds_left, shed_left)
        if hour == 0 and R.get("hold0") and isinstance(actions[u], list) and actions[u] and actions[u][0] in ("NORTH", "SOUTH", "EAST", "WEST"):
            actions[u] = ["PASS"]                  # sd_tier_farmer_h0pick: the hour-0 hires spawn around where he stands
            TP["cnt"]["h0pick_hold"] += 1
        elif hour == 0 and R.get("hold0"):
            TP["cnt"]["h0pick_" + str((actions[u] or ["?"])[0])] += 1
        snap[str(u)] = [it["tile"] for it in R["items"][R["k"]:] if it["kind"] == "stop"]
    if CFG["sd_wheat_pick_now"]:                   # the shed stock this step's PICKUP commands take (read by _market)
        TP["_picked_now"] = (int(step), {k_: int(shed.get(k_, 0) or 0) - int(shed_left.get(k_, 0) or 0)
                                         for k_ in shed if int(shed.get(k_, 0) or 0) > int(shed_left.get(k_, 0) or 0)})
    if CFG["sd_plan_log"] and snap != L.get("plan_last"):
        L.setdefault("plan_log", {})[str(step)] = snap
        L["plan_last"] = snap
    if hour == 23:
        TP["summary"]["breakages"] = list(TP["log"])
        TP["summary"]["exec"] = {str(u): {"plan": R.get("plan_hours"), "done": R.get("done", [])} for u, R in TP["routes"].items()}
        TP["summary"]["cnt"] = dict(TP["cnt"])
        TP["summary"]["unfinished"] = {str(u): [[it.get("tile", it.get("item")), (it["ops"][R["sub"]:] if i == 0 else it["ops"]) if "ops" in it else it.get("n")]
                                                for i, it in enumerate(R["items"][R["k"]:])]
                                       for u, R in TP["routes"].items() if R["k"] < len(R["items"])}


def _is_shed_adjacent_t(p):
    return tuple(p) in ((4, 4), (5, 4), (4, 5), (5, 5))


def _sd_post(S, run, obs, me, step, day, hour, last_day, tiles, pos, tasks, assign, actions):
    """HOOK 3 (after every unit's command, before the market): counters, shadow agreement."""
    L = _sd_state(S)
    st = L["st"]
    try:
        if run.get("P") is not None and not run["active"]:
            for u, k in run["first"].items():      # shadow: plan's next job vs the greedy's assignment
                g = assign.get(u)
                if g is None or g == "D":
                    continue
                st["agree_n"] += 1
                st["agree"] += 1 if g == k else 0
        _sd_track(S, L, obs, me, step, day, hour, last_day, len(pos), pos, actions, tiles)
        hp = L.get("hire")
        if hp and hp.get("day") == day and CFG["dispatch_search"] == "active" and hour <= 12:
            if hour == 0 and tuple(pos[0]) != tuple(hp["F"]) and actions:
                actions[0] = _step_toward(tuple(pos[0]), tuple(hp["F"]))
            CFG["hire_extra"] = int((hp["k0"] if hour == 0 else hp["k"]) - _T.hands[min(day, _T.n - 1)])
        elif "hire_extra0" in L:
            CFG["hire_extra"] = L["hire_extra0"]
        if CFG.get("sd_path_collect") and actions and run.get("P") is not None and run.get("active"):
            # user cycle: collect on the way out -- a planned unit carrying less fertilizer than sd_path_collect steps onto
            # an animal with fertilizer available when that tile is on a shortest path to its next job (no detour); the
            # collect-before-leaving rule then collects it, and the next plan can give it fertilize jobs
            P_ = run["P"]
            invs_ = ((obs.get("private") or {}).get("inventories") or []) if isinstance(obs, dict) else []
            for u_ in range(min(len(pos), len(actions), len(invs_))):
                a_ = actions[u_]
                if not (isinstance(a_, list) and a_ and a_[0] in ("NORTH", "SOUTH", "EAST", "WEST")):
                    continue
                if int((invs_[u_] or {}).get("FERTILIZER", 0) or 0) >= int(CFG["sd_path_collect"]):
                    continue
                if u_ >= len(P_.routes) or not P_.routes[u_]:
                    continue
                ti_ = P_.jb[P_.routes[u_][0]][0]
                tg_ = (ti_ % 10, ti_ // 10)
                p_ = tuple(pos[u_])
                dc_ = _dist(p_, tg_)
                for dx_, dy_, mv_ in ((0, -1, "NORTH"), (0, 1, "SOUTH"), (1, 0, "EAST"), (-1, 0, "WEST")):
                    q_ = (p_[0] + dx_, p_[1] + dy_)
                    if not (0 <= q_[0] < 10 and 0 <= q_[1] < 10) or _dist(q_, tg_) >= dc_:
                        continue
                    t2_ = _tile(tiles, q_[1] * 10 + q_[0])
                    if isinstance(t2_, dict) and t2_.get("animal") and t2_.get("fertilizer_available"):
                        if mv_ != a_[0]:
                            actions[u_] = [mv_]
                            st["path_collect"] = st.get("path_collect", 0) + 1
                        break
        if CFG.get("sd_finish_collect") and actions:
            # one visit per tile (user): a unit about to walk off an animal tile whose fertilizer is still there collects it first
            coll_ = {tuple(pos[v_]) for v_ in range(min(len(pos), len(actions)))
                     if isinstance(actions[v_], list) and actions[v_][:1] == ["COLLECT_FERTILIZER"]}
            for u_ in range(min(len(pos), len(actions))):
                a_ = actions[u_]
                if not (isinstance(a_, list) and a_ and a_[0] in ("NORTH", "SOUTH", "EAST", "WEST", "PASS")):
                    continue
                p_ = tuple(pos[u_])
                if p_ in coll_:
                    continue                    # another unit collects this tile this hour (one collect per tile)
                t_ = _tile(tiles, p_[1] * 10 + p_[0])
                if isinstance(t_, dict) and t_.get("animal") and t_.get("fertilizer_available") and day < last_day:
                    actions[u_] = ["COLLECT_FERTILIZER"]
                    coll_.add(p_)
                    st["finish_collect"] = st.get("finish_collect", 0) + 1
        if CFG["sd_fert_ret"] and actions:
            # user cycle: a unit delivering goods at the shed drops everything, its unused fertilizer included (sold)
            invs_ = ((obs.get("private") or {}).get("inventories") or []) if isinstance(obs, dict) else []
            P_ = run.get("P")
            for u_ in range(min(len(pos), len(actions), len(invs_))):
                a_ = actions[u_]
                if not (isinstance(a_, list) and len(a_) >= 2 and a_[0] == "PLACE" and a_[1] in PRODUCTS
                        and a_[1] != "FERTILIZER" and _is_shed_adjacent_t(tuple(pos[u_]))):
                    continue
                inv_ = invs_[u_] or {}
                if int(inv_.get("FERTILIZER", 0) or 0) <= 0 or any(int(inv_.get(sp_, 0) or 0) > 0 for sp_ in _SD_SP):
                    continue
                cm = set()
                if P_ is not None and run.get("active") and u_ < len(P_.routes):
                    for j_ in P_.routes[u_]:
                        for o_ in P_.ops[j_]:
                            cm.add(o_ if isinstance(o_, str) else o_[0])
                else:
                    a_i = assign.get(u_)
                    if a_i in tasks:
                        cm.update(o_[0] for o_ in tasks[a_i][0])
                if "FERTILIZE" in cm or (int(inv_.get("WHEAT", 0) or 0) > 0 and "FEED" in cm):
                    continue
                actions[u_] = ["DROP"]
                st["fert_ret"] = st.get("fert_ret", 0) + 1
        if CFG["sd_coop_place"] and actions:
            # never an empty structure, for every unit (greedy / survival-fallback units too): standing on an empty
            # coop / pasture with its animal in hand, the unit places it now
            invs_ = ((obs.get("private") or {}).get("inventories") or []) if isinstance(obs, dict) else []
            for u_ in range(min(len(pos), len(actions), len(invs_))):
                p_ = tuple(pos[u_])
                t_ = _tile(tiles, p_[1] * 10 + p_[0])
                if not (isinstance(t_, dict) and t_.get("kind") in ("COOP", "PASTURE") and "animal" not in t_):
                    continue
                for sp_ in _SD_SP:
                    if ANIMALS[sp_]["structure"] == t_["kind"] and int((invs_[u_] or {}).get(sp_, 0) or 0) > 0:
                        if list(actions[u_] or []) != ["PLACE", sp_]:
                            actions[u_] = ["PLACE", sp_]
                            st["pair_place_post"] = st.get("pair_place_post", 0) + 1
                        break
        if CFG["sd_coop_pair"] and run.get("active"):
            # the pair job buys its animal from hour 0: a BUILD job's tile still holding its crop has only the clearing
            # task ([WATER,] HARVEST: harvest_before_build, water first), whose need carries no animal
            for idx, job in (run.get("jobs") or {}).items():
                if job and job[0] == "BUILD" and len(job) > 2 and job[2] and idx in tasks:
                    ops_, need_, prio_ = tasks[idx]
                    if ([o[0] for o in ops_] in (["HARVEST"], ["WATER", "HARVEST"]) and need_.get(job[2], 0) <= 0):
                        need_[job[2]] += 1
                        st["pair_buy"] = st.get("pair_buy", 0) + 1
        if CFG["sd_early_animal"] and run.get("active"):
            # a BUILD job with an animal whose tile still holds a harvestable one-time crop has only a HARVEST task
            # (harvest_before_build), so the market would buy the animal only after that harvest: count it now (the
            # market reads the tasks' needs after this hook; nothing else reads them this step)
            for idx, job in (run.get("jobs") or {}).items():
                if job and job[0] == "BUILD" and len(job) > 2 and job[2] and idx in tasks:
                    ops_, need_, prio_ = tasks[idx]
                    if [o[0] for o in ops_] == ["HARVEST"] and need_.get(job[2], 0) <= 0:
                        need_[job[2]] += 1
                        st["early_animal"] = st.get("early_animal", 0) + 1
        if CFG["sd_melon_rule"] and actions:
            invs_ = ((obs.get("private") or {}).get("inventories") or []) if isinstance(obs, dict) else []
            _mel_act(S, day, hour, tiles, pos, invs_, actions, last_day)   # hard-coded melon routes win over everything
    except Exception as exc:
        st["errors"] += 1
        st["last_error"] = ("post %s: %s" % (type(exc).__name__, exc))[:300]
        try:
            S["log"]["sd_err:" + st["last_error"][:100]] += 1
        except Exception:
            pass


def _sd_track(S, L, obs, me, step, day, hour, last_day, n, pos, actions, tiles):
    """executed-command counters for the per-game summary (all modes but off)."""
    st = L["st"]
    seq = L["seq"]
    if L.get("seq_day") != day:
        L["seq_day"] = day
        seq.clear()
    if hour == 0:
        st["cash0"].append(round(float(obs["farms"][me]["money"]), 1))
    for u in range(n):
        a = actions[u] if u < len(actions) else ["PASS"]
        c = a[0] if a else "PASS"
        p = tuple(pos[u])
        st["unit_steps"] += 1
        if c in _SD_MOVES:
            kind = "M"
            st["moves"] += 1
            dx, dy = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}[c]
            q = (p[0] + dx, p[1] + dy)
            if 0 <= q[0] < 10 and 0 <= q[1] < 10 and q in SHED and p not in SHED:
                st["shed_arrivals"] += 1
        elif c in ("PICKUP", "DROP") or (c == "PLACE" and p in SHED and not (
                len(a) > 1 and a[1] in ANIMALS and isinstance(_tile(tiles, p[1] * 10 + p[0]), dict)
                and _tile(tiles, p[1] * 10 + p[0]).get("kind") == ANIMALS[a[1]]["structure"])):
            kind = "S"
            st["shed_cmds"] += 1
        elif c == "PASS":
            kind = "P"
            st["passes"] += 1
        else:
            kind = "W"
            st["work"] += 1
            if c == "WATER" and hour == 23:
                L["water23"].add(p[1] * 10 + p[0])
        sq = seq.setdefault(u, [])
        if kind == "S" and (not sq or sq[-1] != "S"):
            st["shed_visits"] += 1
        sq.append(kind)
    if hour == 23 or step >= 718:
        for u, sq in seq.items():
            st["unit_days"] += 1
            last = max((i for i, k in enumerate(sq) if k == "W"), default=-1)
            tail = sq[last + 1:]
            st["walk_after_last"] += tail.count("M")
            nd = run_m = 0                         # moves of a final delivery trip (moves then a shed command) excluded
            for k in tail:
                if k == "M":
                    run_m += 1
                elif k == "S":
                    run_m = 0
                else:
                    nd += run_m
                    run_m = 0
            st["walk_after_last_nodeliv"] += nd + run_m
        seq.clear()
    if hour == 23 and day < last_day:
        # dropped = a fresh maintenance solve's jobs (value > 0) still open after this step's commands, valued by the
        # executor's own module (the idle tracer's definition); production-affecting = units > 0
        done23, gone23 = set(), set()
        for u in range(n):
            a = actions[u] if u < len(actions) else ["PASS"]
            if a and a[0] in ("WATER", "FEED", "CARE", "HARVEST", "FERTILIZE", "COLLECT_FERTILIZER"):
                i23 = pos[u][1] * 10 + pos[u][0]
                done23.add((i23, a[0]))
                t23 = _tile(tiles, i23)
                if a[0] == "HARVEST" and _is_plant(t23) and not CROPS[t23["crop"]]["ongoing"]:
                    gone23.add(i23)                # a one-time crop harvested now: its other jobs are moot
        try:
            jl = _sm()["maintenance_jobs"](obs, me, prices=None, fertilize=_mj_fert(), include_optional=False,
                                          collect=CFG["mj_collect"])
        except Exception:
            jl = []
        for j in jl:
            idx = j["tile"][1] * 10 + j["tile"][0]
            v = float(j.get("value", 0.0))
            if v <= 0 or (idx, j["cmd"]) in done23 or idx in gone23:
                continue
            st["dropped_jobs"] += 1
            st["dropped_value"] += v
            if j.get("units", 0) > 0:
                st["dropped_prod_jobs"] += 1
                st["dropped_prod_value"] += v
                st["dropped_prod_units"] += int(j.get("units", 0))
            if j.get("kind") == "survival":
                st["dropped_hard"] += 1
    if hour == 23 or step >= 718:
        _sd_flush(S, False)


def _sd_summary(S):
    st = S["sd"]["st"]

    def q(xs, f):
        if not xs:
            return 0.0
        xs = sorted(xs)
        return xs[min(len(xs) - 1, int(f * (len(xs) - 1) + 0.5))]
    pm, sm, pf = st["plan_ms"], st["step_ms"], st["plan_ms_first"]
    out = {k: v for k, v in st.items() if not isinstance(v, list) and not k.startswith(("mrs_", "mrv_"))}
    for k in PRODUCTS:                             # v3: mean marginal revenue / price and coins (hour-1 plans)
        if st.get("mrn"):
            out["mr_" + k] = round(st.get("mrs_" + k, 0.0) / st["mrn"], 3)
            out["mrc_" + k] = round(st.get("mrv_" + k, 0.0) / st["mrn"], 1)
    out.update(plan_ms_max=max(pm) if pm else 0.0, plan_ms_mean=round(sum(pm) / len(pm), 2) if pm else 0.0,
               plan_ms_p95=q(pm, 0.95), plan_ms_first_max=max(pf) if pf else 0.0,
               plan_ms_first_mean=round(sum(pf) / len(pf), 2) if pf else 0.0,
               step_ms_max=max(sm) if sm else 0.0, step_ms_mean=round(sum(sm) / len(sm), 2) if sm else 0.0,
               step_ms_p95=q(sm, 0.95), moves_per_op=round(st["moves"] / max(1, st["work"]), 4),
               bank_min_remaining=round(60.0 - st["bank_used"], 3),
               load_proj_h23_mean=round(sum(st["load_proj_h23"]) / len(st["load_proj_h23"]), 2)
               if st["load_proj_h23"] else 0.0, mode=CFG["dispatch_search"], days=CFG["sd_days"])
    return out


def _sd_flush(S, final):
    """write the step records (and the game summary at the end) to CFG sd_log; numeric summary -> _MGT_REPORT."""
    import json as _json
    import os as _os
    L = S["sd"]
    if final and not L["final_done"]:
        L["final_done"] = True
        summ = _sd_summary(S)
        num = {"sd_" + k: v for k, v in summ.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        try:
            for k, v in num.items():               # lead_g1 / lead_sem4 keep S["log"] as agent_log (diagnostics only)
                S["log"][k] = v
        except Exception:
            pass
        try:
            _MGT_REPORT.update(num)                # the deploy: ladder_panel's "router" record
        except Exception:
            pass
        L["recs"].append({"summary": summ, "cash0": list(S["sd"]["st"]["cash0"])})
    if not CFG["sd_log"]:
        del L["recs"][:]
        return
    try:
        if L["path"] is None:
            _os.makedirs(CFG["sd_log"], exist_ok=True)
            L["path"] = _os.path.join(CFG["sd_log"], "%d_%d.jsonl" % (_os.getpid(), int(time.time() * 1000)))
        with open(L["path"], "a", encoding="utf-8") as f:
            for r in L["recs"]:
                f.write(_json.dumps(r) + "\n")
    except Exception:
        pass
    del L["recs"][:]


def _sd_step_end(step, t_entry):
    """HOOK 5 (entry point, after everything): whole-step time and the 1 s overage bank estimate; the planner switches
    itself off for the rest of the game when the estimated bank use passes sd_bank_stop."""
    S = _S
    if S is None:
        return
    L = _sd_state(S)
    st = L["st"]
    dt = time.time() - t_entry
    st["step_ms"].append(round(1000.0 * dt, 2))
    if dt > 1.0:
        st["steps_over_1s"] += 1
        st["bank_used"] += dt - 1.0
        if st["bank_used"] > CFG["sd_bank_stop"] and not L["off"]:
            L["off"] = True
            st["last_error"] = "bank stop at step %d" % step
    if step >= 718:
        _sd_flush(S, True)
# ===== END SEARCH DISPATCH BLOCK =============================================================


# ---- sd_fert_first (user, F3): FERTILIZE on the first day it adds units, not the last -------------------------------
# The maintenance module emits FERTILIZE only when today is the last day it still pays, timed against its own harvest
# day; our executor harvests / replants on the leader's (earlier) schedule, so the deferred day rarely comes. With the
# flag the module's job list also gets FERTILIZE for every unfertilized plant whose fertilizer-free plan makes more
# units than its no-fertilizer plan, while fertilizer is in hand or in the shed (the highest gains first, at most as
# many as the fertilizer held). The host's _sm() is wrapped here (the block is appended after it); off = unchanged.
_SD_SM_ORIG = _sm


def _sd_fert_first(ns, obs, player, jobs, k):
    step = int(obs["step"])
    day, hour = divmod(step, 24)
    if day >= ns["SM_LAST_DAY"]:
        return jobs
    farm = obs["farms"][player]
    priv = obs.get("private") or {}
    avail = 0 if CFG.get("sd_fert_sell") == 1 else int((priv.get("shed") or {}).get("FERTILIZER", 0) or 0)   # sd_fert_sell 1: hands only
    avail += sum(int((i or {}).get("FERTILIZER", 0) or 0) for i in (priv.get("inventories") or []))
    if CFG.get("sd_tier") and CFG.get("sd_tier_fert_supply"):   # tiered plan: today's collections supply the fertilize jobs
        avail += sum(1 for row in farm["tiles"] for t in row
                     if isinstance(t, dict) and "animal" in t and t.get("fertilizer_available"))
    have = set(tuple(j["tile"]) for j in jobs if j.get("cmd") == "FERTILIZE")
    avail -= len(have)
    if avail <= 0:
        return jobs
    pr = ns["_sm_prices"](obs, k.get("prices"))
    fh, vc = k.get("future_hour", 8), k.get("visit_cost", 0.0)
    ff = CFG.get("sd_fert_frac")
    inp = float(ff) * float(pr["FERTILIZER"]) if ff is not None else 0.0     # the charged fertilizer price
    cand = []
    for y, row in enumerate(farm["tiles"]):
        for x, t in enumerate(row):
            if not (isinstance(t, dict) and t.get("kind") == "PLANT") or (x, y) in have:
                continue
            crop = t.get("crop")
            if crop not in ns["SM_CROPS"] or int(t.get("fertilized_until_day", -1) or -1) >= day:
                continue
            if CFG.get("sd_fert_first_crops") and crop not in CFG["sd_fert_first_crops"]:
                continue
            fa_ = (CFG.get("sd_fert_ages") or {}).get(crop)
            if fa_ is not None and not (int(fa_[0]) <= day - int(t.get("planted_day", day)) <= int(fa_[1])):
                continue                           # sd_fert_ages: fertilize this crop only at these ages (wheat 1-2 -> 5 units at age 3)
            prod = ns["_sm_product"](crop)
            price = float(pr.get(prod, ns["SM_BASE_PRICE"][prod]))
            st = ns["_sm_state"](crop, t)
            p1 = ns["sm_tile_plan"](crop, st, day, hour, price, inp, True, fh, vc)
            p0 = ns["sm_tile_plan"](crop, st, day, hour, price, inp, False, fh, vc)
            du = int(p1["units"]) - int(p0["units"])
            lg_ = _S["log"] if _S is not None else None
            if lg_ is not None and crop == "WHEAT":
                lg_["ffw_seen"] += 1
                lg_["ffw_du0" if du <= 0 else ("ffw_val0" if du * price - inp <= 0 else "ffw_ok")] += 1
            if du > 0 and du * price - inp > 0:
                cand.append((du * price - inp, x, y, crop, du, price, prod))
    cand.sort(reverse=True)
    if _S is not None:
        _S["log"]["ffw_capped"] += max(0, sum(1 for c_ in cand if c_[3] == "WHEAT") - sum(1 for c_ in cand[:avail] if c_[3] == "WHEAT"))
    for v, x, y, crop, du, price, prod in cand[:avail]:
        jobs.append({"tile": (x, y), "cmd": "FERTILIZE", "value": round(v, 1), "deadline": 23,
                     "needs": {"FERTILIZER": 1}, "reason": "fertilised yield +%d (first day it pays)" % du,
                     "kind": "bonus", "order": 0, "units": du, "product": prod, "price": price, "asset": crop})
    return jobs


def _sm():
    ns = _SD_SM_ORIG()
    if CFG.get("sd_fert_frac") is not None and ns is not None and not ns.get("_sd_fm"):
        om = ns["_sm_fert_mode"]
        fr = float(CFG["sd_fert_frac"])

        def fert_mode(fertilize, crop, price, fert_price):
            ok, _inp = om(fertilize, crop, price, fert_price)
            return ok, (fr * float(fert_price) if ok else _inp)   # applying costs a fraction; collection keeps its price
        ns["_sm_fert_mode"] = fert_mode
        ns["_sd_fm"] = True
    if CFG.get("sd_wheat_frac") is not None and ns is not None and not ns.get("_sd_wf"):
        ot = ns["sm_tile_plan"]
        wf_ = float(CFG["sd_wheat_frac"])
        an_ = ns["SM_ANIMALS"]

        def tile_plan(kind, state, day, hour, price=None, input_price=None, *a_, **k_):
            if kind in an_ and input_price is not None:
                input_price = wf_ * float(input_price)   # feeding charges only this fraction of the wheat price
            return ot(kind, state, day, hour, price, input_price, *a_, **k_)
        ns["sm_tile_plan"] = tile_plan
        ns["_sd_wf"] = True
    if CFG.get("sd_fert_first") and ns is not None and not ns.get("_sd_ff"):
        orig = ns["maintenance_jobs"]

        def maintenance_jobs(obs, player, *a, **k):
            jobs = orig(obs, player, *a, **k)
            try:
                return _sd_fert_first(ns, obs, player, jobs, k)
            except Exception:
                return jobs
        ns["maintenance_jobs"] = maintenance_jobs
        ns["_sd_ff"] = True
    return ns

