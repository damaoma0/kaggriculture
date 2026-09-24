# Lead agent (board-plan follower) progress, 2026-09-24

Agent: `agents/mgt_lead.py`. Gate: `scripts/lead_g1.py` (target game's own world: recorded seed, forced
shops, opponent = recorded opp_actions; our agent in the leader's seat). Results:
`results/fresh/lead_agent_20260924/<tag>/`. Diagnostics: `scripts/lead_sum.py <tag>` (deaths/moves),
`scripts/lead_compare.py <tag> <ep>` (revenue/spend by product vs the leader), `scripts/lead_trace.py`,
`scripts/lead_animals.py`.

## Design (as built)
- Target interface (`Target` class): per day `events` (plant day, tile, crop), `struct_by_day` (tile -> COOP/PASTURE
  wanted at end of day), `animals_by_day` (tile -> species), `fert[d]` (tiles), `hands[d]`, `cum_sold[d]` (product ->
  cumulative units), `land_day` (quadrant -> day). Mode (2) (composition targets) would only have to fill these.
- Planner (every step, O(100)): structural diff toward the target (build/place wherever our tile lacks the
  target's structure/animal, catch-up included; plantings for the target's events of today plus late catch-up
  (wheat/carrot 1, melon 3, tomato 5, strawberry 6 days); remap to the nearest free tile when ours is occupied by a live asset). Tile op pipelines are
  recomputed from the live board every step (closed loop): DIG/HARVEST/PLANT/WATER, BUILD/PLACE/FEED/CARE,
  FERTILIZE (target's tiles), maintenance of all our live assets, harvests, COLLECT_FERTILIZER.
- Executor: own greedy dispatcher (not continuation_executor: that one compiles a whole day open-loop at hour 0
  and fails hard on any budget/capacity deviation; here the opening is cash-bound to the last coin, so
  purchases and jobs must be retried hourly). Nearest task with shed detours for wheat/fertilizer/animals,
  delivery of produce for same-day sale when cash binds.
- Market: sell = target's cumulative sold units per product (fixed one-day shift of the semantics' market block),
  capped by stock minus feed/fertilizer reserve; buy wheat for feed first, hires (target's hands), land on the
  target's unlock day, animals/seeds for today's jobs, all retried hourly.
- Data quirk found: in `data/leader_semantics/*`, `market.*`, `animals.bought` and `labour.hires_arrived` of index d
  are day d+1's events (index 0 = days 0+1) because the extractor's commit/hire hooks use `day_now`, which is only
  updated at end of day. Boards, plantings, maintenance, `hands_present` are correctly dated.

## Iterations (G1 = our final cash / leader's final cash, in the leader's own world)
| tag | change | games | mean ratio |
|---|---|---|---:|
| v0 | first build | 1 | 0.000 (cows starved day 2, cash 0 all game) |
| v1 | deliver collected fertilizer for same-day sale; wheat-for-feed first in buy order | 1 | 0.540 |
| v2 | item logistics (no CARE without FEED), delivery when cash-short, fertilizer reserve | 1 | 0.490 |
| v3 | work zones (curve chunks per unit) | 1 | 0.229 (zones: units leave shed without wheat) |
| v4a | zones off, pick up wheat/fert whenever at shed, priority only late in the day | 3 | 0.732 |
| v4a12 | same | 12 | 0.691 |
| v5 | fresh greedy matching every step (keep-bonus 1.5) instead of sticky tasks | 12 | 0.702 |
| v5w / v5h | water every plant daily / +1 hand | 12 | 0.670 / 0.682 (rejected) |
| v6 | never start a plant pipeline that cannot be watered by hour 23 | 12 | 0.693 (age-0 deaths down) |
| v6z | zones again (penalty 6) | 12 | 0.429 (rejected; zone split is buggy) |
| v7 | fertilize our producing strawberries/tomatoes (engine rule) + value-based same-day delivery | 12 | 0.702 |
| v8 | window water of one-time crops = urgent; keep 1 day of feed wheat out of sales; deliver >= $300 | 12 | 0.719 |
| v9 = **final** | catch-up windows ST 6 / TO 5 / ME 3 days (default now) | 12 | **0.721** |
| v9b / v9m1 / v9m2 | hands = leader +1 / -1 / -2 | 12 | 0.646 / 0.662 / 0.671 (leader's count is best) |
| v10l12 | urgency from hour 12 | 12 | 0.681 (rejected) |

### final table (tag `final`, defaults of agents/mgt_lead.py; deterministic, reproduces v9 exactly)
| game | team | final | target | ratio | opp (its recorded) | Hamming d6/d12/d20 | failed buys | hires (leader) | plants died | animals lost | max s/step |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| 112655730 | DSM | 62794 | 97066 | 0.647 | 116840 (92826) | 1/20/33 | 1 | 291 (291) | 58 | 0 | 0.042 |
| 112661570 | DSM | 87283 | 107042 | 0.815 | 158298 (110114) | 1/26/44 | 1 | 287 (287) | 67 | 4 | 0.013 |
| 112667461 | DSM | 95282 | 160169 | 0.595 | 70371 (56921) | 1/17/31 | 1 | 290 (292) | 70 | 0 | 0.068 |
| 112673479 | DSM | 61916 | 103786 | 0.597 | 106879 (92501) | 1/17/29 | 1 | 279 (279) | 53 | 3 | 0.016 |
| 112708229 | Vadim | 80659 | 83602 | 0.965* | 24078 (82753) | 1/16/26 | 1 | 289 (290) | 69 | 0 | 0.014 |
| 112714050 | Vadim | 54080 | 73589 | 0.735 | 80818 (76344) | 1/15/25 | 1 | 280 (280) | 51 | 0 | 0.062 |
| 112715010 | Vadim | 56975 | 73089 | 0.780 | 96417 (76791) | 1/22/21 | 1 | 271 (271) | 35 | 4 | 0.011 |
| 112721923 | Vadim | 74014 | 95661 | 0.774 | 122102 (91455) | 1/22/31 | 1 | 285 (285) | 65 | 4 | 0.058 |
| 112444381 | UMG | 114150 | 158088 | 0.722 | 164869 (129574) | 0/11/22 | 1 | 280 (280) | 46 | 1 | 0.055 |
| 112445586 | UMG | 59134 | 78200 | 0.756 | 81147 (67796) | 1/7/15 | 0 | 281 (281) | 36 | 0 | 0.032 |
| 112447950 | UMG | 69687 | 105308 | 0.662 | 105865 (87008) | 1/20/21 | 1 | 275 (275) | 52 | 4 | 0.063 |
| 112449129 | UMG | 59226 | 98814 | 0.599 | 111370 (80865) | 0/20/35 | 1 | 284 (284) | 69 | 0 | 0.039 |
| **mean** | | | | **0.721** | | | | | | | |

\* the replayed opponent collapsed (its open-loop orders fail in our market), which inflates this one ratio;
mean without it 0.699. No-effect commands: 0 in every game. Per-step time max 0.068 s, about 2 s a game.

Cash / leader cash by day (final): day 6 0.43-0.80, day 9 0.04-1.29 (trough), day 12 0.14-0.79, day 15
0.44-0.73, then flat 0.6-0.8 to the end. The loss is made in the cash-bound days 6-12 and never recovered.

Revenue gap per game (final, mean over 12): ours 101.5k vs 134.3k. Strawberry -11.2k (harvest 98 vs 208 units),
wheat -10.2k (harvest 453 vs 681), tomato -4.2k (38 vs 105), carrot -4.0k (100 vs 204), egg -3.2k, melon -1.7k;
milk +1.5k and wool +0.7k (animals are on par or better). Spend 19.9k vs 22.6k.

## Biggest remaining losses and next fixes
1. Execution: moves are the same as the leader's (about 3,100 a game in both), but we do fewer tile actions
   (about 3,500 vs 3,980; the rest of our unit-steps are idle, mostly hours 18-23) and do them in the wrong
   order: 50-70 plants still die unwatered (mostly on the "must water" day of the every-other-day rhythm, age 2/4/...),
   and window waterings are missed. Fix: a real daily route plan (contiguous sweeps per hand, with the wheat
   and fertilizer each hand needs picked up at spawn), re-planned closed-loop when the board deviates. The
   zone attempt here was buggy, not refuted.
2. Days 6-12 cash trough: the leader sells each harvest the same day (milk day 8, melons day 10) and spends
   to the last coin; we lag 1 day on several items (one cow placed day 1, melons harvested over days 10-12),
   so land, strawberries and geese come 1-3 days late (strawberry tile-days 79%, geese 69%) and compounding
   does the rest. Fix: plan same-day harvest-deliver-sell chains on the days the target sells, and give the
   day-0 animal placements top priority.
3. Fertilizer: we apply about half the leader's (~100 vs 206 per game); that is most of the per-tile gap
   on strawberries/tomatoes/wheat.

## Round 2 (2026-09-24, after commit 11990a5)

Interface: `Target` unchanged. File now has three delimited sections: `TARGET (interface)` (documents the fields a
target must supply), `PLANNER (target -> tile jobs)`, `EXECUTOR + MARKET` (target-agnostic except `_market`, which
reads `_T.cum_sold`, `_T.hands`, `_T.land_day`, `_T.fert`). New CFG keys: `dispatch` ("greedy" default, "route"
experimental), `prio3`, `late_p1`, `fert_prio`, `pick_cap`, `hires_first`, `hires_at_front`, `deliver_value_late`,
route knobs (`two_opt`, `travel_w`, `reach_w`, `insert_by_finish`, `pick_k`, `steal_radius`). `--cfg` in
`scripts/lead_g1.py` now separates keys with `;`.

| tag | change | mean12 | mean11 (w/o 112708229) |
|---|---|---:|---:|
| final (round 1) | | 0.721 | 0.698 |
| r1-r5 | route dispatcher: sweep sectors around the shed, NN + 2-opt, pickups for the route at spawn, closed-loop pruning / insertion / stealing (fixed: shed PICKUP/PLACE ping-pong of fertilizer; hour-0 farmer grabbing all wheat) | 0.506 (r5) | - |
| g1 | 3-tier priorities: prio 0 = dies tonight / plant+place pipelines, 1 = window water, harvest at overflow/decay risk, feed; 2 = rest; no value deliveries after the late hour | 0.699 | 0.669 (one game collapsed: melon harvest deferred -> no cash day 10 -> no hires) |
| g2 | + one-time crop harvests back to prio 1; hires funded first (sell beyond quota if needed) | 0.722 | 0.696 |
| g3 | + FERTILIZE prio 1, fertilizer pickup cap 4, late delivery of loads >= $1000 | 0.720 | 0.693 |
| g4 | + HIRE orders at the front of hour 0 when cash covers them (sells were crowding hires out of the 10-order cap) | 0.735 | 0.710 |
| g5 | + when cash does not cover hires: fewest sells needed, then hires | 0.733 | 0.707 |
| g6w / **g6p = final2** | water everything daily / no late penalty on prio-1 work | 0.710 / **0.747** | 0.690 / **0.717** |

Route dispatcher verdict: not refuted but far worse as built (0.506). Plans were feasible on paper, but hands
spend the day on 4-op animal tiles, the plan is rebuilt when hires arrive at hour 1 and 2, and late insertions /
steals send hands across the farm. It is kept behind `CFG["dispatch"]="route"`; the zone and route failures both
traced partly to the hour-0 farmer picking up the whole day's wheat (fixed only in route mode via `pick_k`).

### final2 table (defaults; deterministic)
| game | team | final | target | ratio | Hamming d6/d12/d20 | failed buys | hires (leader) | plants died | animals lost | FERTILIZE | cash/leader d9/d12/d20 |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|
| 112655730 | DSM | 63960 | 97066 | 0.659 | 1/25/26 | 2 | 291 (291) | 54 | 0 | 178 | 0.26/0.31/0.56 |
| 112661570 | DSM | 86013 | 107042 | 0.804 | 1/19/40 | 3 | 287 (287) | 48 | 2 | 163 | 0.89/0.27/0.56 |
| 112667461 | DSM | 99256 | 160169 | 0.620 | 1/16/22 | 5 | 292 (292) | 53 | 1 | 162 | 0.20/0.37/0.60 |
| 112673479 | DSM | 61734 | 103786 | 0.595 | 1/16/33 | 1 | 279 (279) | 55 | 0 | 153 | 0.23/0.36/0.58 |
| 112708229 | Vadim | 90275 | 83602 | 1.080* | 1/17/25 | 1 | 290 (290) | 46 | 0 | 132 | 0.35/0.67/0.80 |
| 112714050 | Vadim | 54484 | 73589 | 0.740 | 1/19/27 | 1 | 280 (280) | 39 | 1 | 123 | 0.63/0.43/0.71 |
| 112715010 | Vadim | 60571 | 73089 | 0.829 | 1/21/20 | 1 | 271 (271) | 19 | 3 | 147 | 0.50/0.75/0.79 |
| 112721923 | Vadim | 80232 | 95661 | 0.839 | 1/26/32 | 1 | 285 (285) | 52 | 2 | 117 | 0.28/0.36/0.74 |
| 112444381 | UMG | 121943 | 158088 | 0.771 | 0/18/16 | 1 | 280 (280) | 31 | 3 | 167 | 0.11/0.37/0.59 |
| 112445586 | UMG | 52269 | 78200 | 0.668 | 1/9/18 | 0 | 281 (281) | 24 | 3 | 173 | 0.56/0.59/0.63 |
| 112447950 | UMG | 73580 | 105308 | 0.699 | 1/16/13 | 1 | 275 (275) | 35 | 3 | 176 | 0.30/0.66/0.62 |
| 112449129 | UMG | 65733 | 98814 | 0.665 | 0/27/27 | 1 | 284 (284) | 42 | 2 | 182 | 0.03/0.20/0.47 |
| **mean** | | | | **0.747** (11 games without *: **0.717**) | | | | 41.5 | 1.7 | 158 | |

\* opponent replay collapsed (24k vs its recorded 83k). No-effect commands 0 everywhere; max 0.092 s per step.

Whole-game action mix (g3, per game, ours vs leader): moves 3158/3116, WATER 941/1261, HARVEST 402/583, COLLECT
381/467, FEED 418/381, CARE 391/380, PLANT 266/295, FERTILIZE 146/207, PICKUP 327/191, PASS 378/267.
Unit-steps: 7141 (g5) vs the leader's 7365: some hires still land after hour 0 on cash-bound days.

### What still loses money (in order)
1. Days 6-12 cash trough (cash/leader at day 9 is 0.03-0.89): day-8 milk is 6 vs 12 (one cow placed a day late),
   day-10 melons 27.5 vs 36 units, strawberries start a day late. Every purchase after it (land, strawberries, geese)
   is delayed, and the ratio then stays flat.
2. Crop yield per tile: WATER -320 and HARVEST -181 actions a game vs the leader; 20-55 plants still die unwatered
   (age-2 must-water day of wheat/carrots dominates); fertilizer is plentiful (about 16 units unused at 23:00
   daily) but only 117-182 applications vs the leader's ~207.
3. Extra PICKUP actions (+136/game): small wheat/fertilizer pickups; a bigger wheat cap (6) did not help.

## Round 3 (after commit at 0.747)
| tag | change | mean12 | mean11 | cash/leader d9 / d12 |
|---|---|---:|---:|---|
| final2 | round-2 final | 0.747 | 0.717 | 0.36 / 0.45 |
| h1 | animal placements get an assignment bonus (all game) | 0.719 | 0.705 | 0.51 / 0.51 |
| h2 | bonus on day 0 only (`place_bonus_days=0`): all 5 animals placed on day 0 in all 12 games (was 4) | 0.729 | 0.718 | 0.68 / 0.43 |
| h3 | fertilizer reserve only for strawberry/tomato tiles producing within 3 days (early fertilizer is sold, as the leader does) | 0.740 | 0.731 | 1.10 / 0.44 |
| h3b | + melon window water as a hard deadline (priority 0) | identical to h3 | | |
| h4 | lazy fetch (shed detour only when the next op needs the item) | 0.727 | 0.716 | 1.07 / 0.42 (rejected) |
| **h5** | a build/place job on a harvestable crop first becomes a bare HARVEST task (melons on future coop tiles were never harvested: the bundled pipeline needed a goose detour and always lost to nearer tasks) | **0.757** | **0.747** | 1.13 / 0.68 |
| h6 | full-day wheat allotment per hand at spawn (share of the day's feeding) | 0.745 | 0.733 | 1.11 / 0.65 (pickups 306 vs 309: no effect; off) |
| h7r | route dispatcher built once per day when the full crew is present, never rebuilt, additions only within 3 tiles, idle hands take the nearest unrouted task (`dispatch="route"`) | 0.459 | 0.453 | 1.18 / 0.32 (plants died 72.8/game; rejected) |
| **final3** | defaults = h5 (greedy dispatch; `spawn_allot` off; route mode behind `CFG["dispatch"]`) | **0.757** | **0.747** | 1.13 / 0.68 |

New CFG keys (round 3): `place_bonus`, `place_bonus_days`, `window_p0`, `fert_reserve_soon`, `lazy_fetch` (off),
`harvest_before_build`, `spawn_allot` (off), `route_once`, `add_radius`. Target interface unchanged.
New helper script: `scripts/lead_means.py <tags>` (12- and 11-game means, day-1 animals, deaths, unit-steps,
pickups, cash/leader at days 9 and 12).

### final3 table (deterministic; max 0.27 s a step measured on a loaded laptop, earlier unloaded runs <= 0.09 s)
| game | team | ratio | Hamming d6/d12/d20 | failed buys | hires (leader) |
|---|---|---:|---|---:|---:|
| 112655730 | DSM | 0.711 | 1/15/29 | 1 | 291 (291) |
| 112661570 | DSM | 0.833 | 1/16/40 | 2 | 287 (287) |
| 112667461 | DSM | 0.677 | 1/17/28 | 1 | 292 (292) |
| 112673479 | DSM | 0.609 | 1/17/26 | 1 | 279 (279) |
| 112708229 | Vadim | 0.876* | 1/19/23 | 1 | 290 (290) |
| 112714050 | Vadim | 0.769 | 1/16/30 | 1 | 280 (280) |
| 112715010 | Vadim | 0.842 | 1/22/20 | 1 | 271 (271) |
| 112721923 | Vadim | 0.839 | 1/13/32 | 1 | 285 (285) |
| 112444381 | UMG | 0.777 | 1/13/18 | 1 | 280 (280) |
| 112445586 | UMG | 0.750 | 1/7/14 | 0 | 281 (281) |
| 112447950 | UMG | 0.703 | 1/13/13 | 1 | 275 (275) |
| 112449129 | UMG | 0.701 | 2/23/28 | 1 | 284 (284) |
| **mean** | | **0.757** (11 games: **0.747**) | | | |

\* opponent replay partly collapsed (73k vs its recorded 83k; worse in earlier runs). No-effect commands 0.
Plants died 39.8/game, animals lost ~2/game. Cash/leader at day 9 is now 1.13 (was 0.36 at the start of round 3),
at day 12 0.68 (was 0.45); the remaining gap opens on days 12-20 (per-tile yields: waterings, harvests, fertilizer).

## Ablation (hold-one-out around G1; `scripts/lead_ablation.py`)

`lead_ablation.py run CELL[,CELL] [--workers 2]` / `lead_ablation.py report CELL[,CELL]`; results in
`results/fresh/lead_agent_20260924/abl_<cell>/`. Same 12 games, the leader's own world (recorded seed, forced shops,
opponent = recorded opp_actions). Each cell swaps ONE component, everything else as A:

- **A baseline** = current G1 defaults (leader plan + leader tiles + leader cumulative sell schedule + our maintenance +
  our hires/dispatch). Reproduces final3 exactly.
- **B maintenance = LEADER EXACT**: `CFG maint_source="leader"`: WATER/FEED/CARE/FERTILIZE happen only on the tiles in the
  leader's per-day maintenance lists (semantics `maintenance`, correctly dated), mapped through our remaps; our own
  engine-derived rules (smart water, own fertilizing, feed/care all animals) are off. Structural pipelines keep their
  seedling water / new-animal feed. Harvests stay ours.
- **C market = OURS**: `CFG sell_source="shed"`: mgt_lead_deploy's rule (sell every product as soon as it is in the shed,
  keep the wheat the herd eats until the end).
- **D hires = LEADER EXACT**: `CFG hire_source="leader_steps"`: the leader's HIRE orders at the leader's own steps (tape).
  A already hires the leader's exact daily count (hands_present == corrected hires_arrived on all 324 checked
  game-days), so D isolates hire timing (leader: ~8 HIREs at hour 0, ~3 at hour 1; A: up to 10 at hour 0).
- **E plan = OURS**: mgt_lead_deploy's target builder (family-A exemplar opening, retrieval at days 3/6/9, count model
  from day 12) with this episode excluded from retrieval (`exclude_episode`, any seat) and, when the game is the day-0
  exemplar (112655730), the next family-A game (112661570) as exemplar. Hands and the sell schedule are overwritten
  with the leader's every step, and the no-feed hook is off, so only the plan differs from A. Caveat: the ridge count
  model (days 12+) was fitted on the corpus that contains these games (1 of 240 games; not refitted).
- **E2** (reference) = the full mgt_lead_deploy agent (its plan + its market + its hires + no-feed), same exclusion.

Interface note: `Target` gained two OPTIONAL fields (`maint`, `hire_steps`) used only by B/D; three CFG flags
(`maint_source`, `sell_source`, `hire_source`) default to A's behaviour, so mgt_lead_deploy's verbatim executor copy
is unaffected until E2 re-copies it.

### Ablation results (12 games each; mean11 = without 112708229, whose replayed opponent collapses)
| cell | mean12 | mean11 | vs A | revenue gap vs leader, k$/game (top 4) | failed buys/game | no-effect | Hamming to leader d6/d12/d20 | hires (leader) | plants died | animals lost | diverges from A: first day >0 / >5 tiles (median) |
|---|---:|---:|---:|---|---:|---:|---|---:|---:|---:|---|
| A baseline | 0.757 | 0.747 | | -28.3: wheat -9.3, straw -7.3, carrot -3.9, tomato -3.6 | 1.0 | 0 | 1/16/25 | 283 (283) | 39.8 | 1.8 | - |
| B maintenance = leader exact | 0.669 | 0.663 | -0.088 | -36.7: straw -11.5, wheat -9.3, melon -5.3, carrot -3.8 | 1.1 | 0 | 4/36/30 | 283 (283) | 113.9 | 10.8 | day 2 / day 7 |
| B2 = B + survival net (water/feed only what would die tonight, beyond the leader's lists) | 0.796 | 0.785 | +0.038 | -26.2: wheat -8.2, straw -6.4, egg -3.9, carrot -3.7 | 1.1 | 0 | 1/16/20 | 283 (283) | 33.4 | 1.8 | day 2 / day 10 |
| E plan = ours (mgt_lead_deploy targets, episode held out; leader hires + sell schedule) | 0.795 | 0.783 | +0.038 | -29.4: wheat -8.8, carrot -7.9, egg -6.0, tomato -3.6 | 0.9 | 0 | 2/40/57 (by design) | 283 (283) | 8.8 | 2.8 | day 1 / day 7 |
| C market = ours (sell as it reaches the shed) | 0.745 | 0.735 | -0.013 | -29.8: wheat -10.8, straw -7.7, carrot -3.9, tomato -3.5 | 0.9 | 0 | 1/17/24 | 283 (283) | 42.2 | 1.5 | day 7 / day 11 |
| D hires = leader exact steps | 0.878 | 0.870 | +0.120 | -18.4: wheat -8.8, straw -5.5, tomato -3.6, egg -3.4 | 4.2 | 0 | 0/23/25 | 285 (283) | 44.2 | 1.0 | day 1 / day 6 |
| D' = A with `hires_first` off (D's side effect alone) | 0.755 | 0.743 | -0.003 | -29.2 | 1.0 | 0 | 1/17/25 | 283 (283) | 39.6 | 1.4 | day 8 / day 11 |
| A29 = A + hire the day-28 count on day 29 | 0.792 | 0.780 | +0.035 | -24.5: wheat -8.3, straw -6.8, tomato -3.4, carrot -3.1 | 1.0 | 0 | 1/16/25 | 294 (283) | 39.8 | 1.8 | no divergence at any day start |
| X = A29 + B2 (combined, measured) | 0.824 | 0.812 | +0.067 | -23.1: wheat -7.3, straw -6.0, egg -3.6, tomato -3.2 | 1.1 | 0 | 1/16/20 | 294 (283) | 33.4 | 1.8 | day 2 / day 10 |

**Opponent-collapse control (mean-nc).** The opponent is the tape's open-loop action stream; when our market
behaviour changes, its orders can fail and its farm collapses, which inflates our ratio. In A the opponent already
ends at 1.03-1.41x its recorded cash (we sell less than the leader, so prices stay higher for it). Cells where it ends
below 0.8x: D in 112715010 (0.31, our ratio 1.786), 112673479 (0.54, 1.051), 112708229 (0.74); 112708229 in A too
(0.88 -> excluded as mean11). mean-nc = the 9 games where no cell's opponent falls below 0.8x:
A 0.751, A29 0.785, X 0.790, B 0.650, B2 0.764, E 0.775, C 0.736, D 0.748, D' 0.740.

**Isolation.** Failed purchases stay at ~1/game in every cell except D (4.2: its hires cost cash at the leader's hours
and wheat/seed buys fail 37+8 times in 12 games); no-effect commands 0 in every cell. Board divergence from A starts
on day 1-2 in B/B2/D/E (they change day-0/1 work) and exceeds 5 tiles by day 6-11; C diverges only from day 7;
A29 is identical to A through day 29 (it only changes the last day).

**What the ablation says about the gap (A = 0.751 on clean games, i.e. a 25% gap):**
1. Last-day labour is a pure bug worth +0.035: the semantics' `hands_present` of day 29 is always 0 (the end-of-day
   hook never runs on the last day), so A hired nobody on day 29 while the leader hires ~10. Fix = A29.
2. Maintenance POLICY: +0.013 to +0.038 when the leader's per-tile lists are used with a survival net (B2); used
   bare (B) they lose 0.10 because our crops are not exactly the leader's (a day or a tile off), so the leader's
   every-other-day rhythm lands on the wrong days (114 plants and 11 animals lost a game). The leader's policy feeds
   and cares less (332/290 vs 416/385 actions), waters more (1033 vs 959) and buys 1.2k less wheat.
3. Plan: our own plan (E) beats following the leader's plan in the leader's world (+0.024 clean, +0.038 all), mostly
   because it never buys the $4000 SE quadrant (revenue is about equal: 104.9k vs 106.0k) and has far fewer
   deaths (8.8 vs 39.8). With our execution the leader's full four-quadrant plan does not pay for its last quadrant.
4. Market: the deploy sell-at-once rule costs 0.013-0.015 vs following the leader's sell schedule.
5. Hires: the leader's exact hire timing on days 0-28 is neutral to slightly worse than ours (D clean 0.748 includes
   the day-29 gain); the +0.120 all-game figure is opponent collapse.
Measured combination X (A29 + B2): 0.824 all / 0.790 clean, close to additive (+0.034 + 0.013 expected +0.047 clean,
measured +0.039). What remains, about 0.21 of the leader's cash on clean games, is spread over crop yields (wheat
-7k, strawberry -6k, egg/tomato -3k each per game) = execution labour, which no single swap here removes; E suggests
part of it is plan density (the leader's 4th quadrant only pays with the leader's execution).
Not run: F (layout; lowest priority), E2 (full deploy reference). Count-model leakage in E (1/240 games) not removed.

## Scheduler (proposal section 16; values, deadlines, marginal-wage hiring)
Flags (all default off = A29 behaviour): `sched_maint` (maintenance ops of every live asset from
`scripts/fragments/sem_maintenance.maintenance_jobs(obs, player, fertilize='auto', include_optional=True,
collect=True)`, re-solved at hour 0 and when the asset set changes, at most every 3 hours; assets planted/placed after
the last solve use our own rules until the next solve; optional early harvests valued at held x price x 0.15; plan
jobs valued 400), `sched_dispatch` + `sched_cost` ("density" = value / time among jobs finishable before their deadline;
"prize" = travel + ops - value/step_value; "skip" = values only choose today's temporary skips (lowest value density
beyond the crew's remaining unit-hours), routing stays distance-based), `sched_hire` (n-th hand while the value only it
adds, in value-density order within the day's unit-hours, exceeds fib(n-1); plan jobs whose inputs have not arrived
are counted). Logged per game: `mj_calls`, `skipped_value` (value left undone at 23:00), `hire_hands`,
`hire_cut_value`, abandonment log (`S["abandon"]`). `scripts/lead_g1.py` now takes `LEAD_AGENT_PATH` (a frozen agent
copy per batch, so the agent can be edited while games run).

Targets: A29 = 0.792 / 0.780 / 0.785 (12 / 11 / clean-9), X = 0.824 / 0.812 / 0.790.

| cell | change | games | mean | notes |
|---|---|---|---:|---|
| S1 v0 | sched_maint | 1 | 0.708 (A29 0.742) | age-0 deaths 3 -> 31: plantings after the last solve had no planting-day water (module note 2) |
| S2 density | + value-density dispatch | 1 / 3 | 0.593 / 0.621 | 93-118 plants died: high-density jobs (collect, harvest) first, cheap survival waters left for a day that runs out |
| S3 v0 | + marginal-wage hiring | 1 | 0.517 | 218 hires vs 291 (planting jobs invisible at hour 0; fixed) |
| S2 prize 20 / 80 | prize-collecting cost | 3 | 0.575 / 0.699 | the stronger the value pull, the worse (travel) |
| S1 v1 | + own rules for assets newer than the last solve | 3 | 0.759 (A29 0.765, X 0.783) | age-2 deaths 30 -> 3 (the module's minimum schedule fixes the must-water day); plants died 29 vs ~40 |
| **S1** (12 games) | sched_maint, our dispatcher | 12 | **0.829 / 0.807 / clean9 0.784** | vs A29 0.792 / 0.780 / 0.785: +0.037 / +0.027 / -0.001. Plants died 28.6 (A29 39.8); animals lost 8.0 (module end-of-life stops, deliberate). Gains concentrated: 112715010 +0.216, 112673479 +0.095, 112661570 +0.074; losses 112445586 -0.072, 112714050 / 112721923 -0.029. Revenue gap -19.7k vs -24.5k (strawberry -4.0k vs -6.8k, wheat -12.4k vs -8.3k) |
| S2 skip (12 games) | + values choose today's skips, distance routes | 12 | 0.764 / 0.755 / 0.729 | worse than S1 (77 plants died): dropping low-density jobs (mostly cheap survival / bonus waterings) when the estimate says capacity is short kills plants the executor would have reached |
| bug found in S1 | optional early harvests (held x price x 0.15) also fired on one-time crops | - | - | S1 harvested 323 wheat/game vs A29 543 (wheat at age 2 with 2 units instead of 4; harvesting ends a one-time crop). Fix: optional harvests only for animals and strawberry/tomato. S1f = fixed S1 |
| **S1f** (12 games) | S1 with the fix | 12 | **0.862 / 0.854 / clean9 0.833** | beats A29 (0.792 / 0.780 / 0.785) and X (0.824 / 0.812 / 0.790) on all three; better than A29 in all 12 games (+0.026 .. +0.270; median +0.045). Revenue gap -18.2k vs -24.5k (strawberry harvest 153 vs 132/game, wheat 516 vs 543). Plants died 40.7 (A29 39.8), animals lost 5.9 (module end-of-life stops). No failed-command change (1.1/game), no-effect 0. Opponent ends 0.82-1.38x its recorded cash (never collapsed). Max 0.123 s a step, 3-6 s a game. **Now the default (`sched_maint=True`).** |
| S1h (12 games) | S1f + marginal-wage hiring | 12 | 0.749 / 0.747 / 0.746 | worse: hires 269 vs 294 (the value model under-counts the day's work: harvests appear after watering, deliveries, re-plans), skipped value +16k. Hiring stays the leader's count. |

Notes: the agent now loads `scripts/fragments/sem_maintenance.py` at runtime (research); the single-file build must paste
it in (it is stdlib-only with `_sm_`/`SM_` prefixes). Value-based DISPATCH (density, prize, skip) lost in every form
tried (0.575-0.764); only the value/deadline JOB LIST won. Not done in the time box: dispatch that uses deadlines
without dropping cheap survival jobs, and a hiring model calibrated on realised work.

## Survival reservation and deployment (after commit fd664f8)
Step 1, reproduction: the committed defaults (cell CUR, frozen copy of agents/mgt_lead.py) reproduce S1f exactly in all
12 games (same final cash, same day-start boards every day): 0.862 / 0.854 / clean9 0.833. No drift.
Step 2, survival reservation (`surv_reserve`, `surv_hour`): from surv_hour, every step, the tiles whose asset dies
tonight (plant with consecutive_unwatered >= 1 not yet watered; animal with consecutive_unfed >= 1 not yet fed, when
wheat exists) get nearest-arrival greedy routes over all hands (wheat detours included); a hand with a survival route
goes there and does only the survival op; every other hand keeps the distance-based greedy. Diagnostic at 23:00 (CUR):
66 dying tiles/game still had a WATER task queued (dispatch, not policy) and 2.8 had no task (module's choice).

| cell | mean12 | mean11 | clean9 | plants died | animals lost | revenue gap | notes |
|---|---:|---:|---:|---:|---:|---|---|
| CUR (= S1f) | 0.862 | 0.854 | 0.833 | 40.7 | 5.9 | -18.2k | |
| **R16** | **0.874** | **0.866** | **0.844** | **7.6** | 4.7 | -17.3k | +0.012 on all three means; failed buys 0.9, no-effect 0.1 |
| R12 | 0.851 | 0.845 | 0.827 | 2.6 | 2.7 | -19.9k | reserving from noon saves more plants but costs other work |
| R19 | 0.862 | 0.853 | 0.831 | 18.8 | 5.6 | -17.9k | too late: no better than CUR |

R16 is the new default (`surv_reserve=True`, `surv_hour=16`).

Step 3, deployment: `scripts/resync_lead_deploy.py` copied the current executor (sched_maint + surv_reserve R16,
sha256 2a8f6eb72f9e4891, header updated) into `agents/mgt_lead_deploy.py`; its DEPLOY section is unchanged. Also
`_sm()` no longer needs `__file__` (Kaggle's loader exec's the source; it falls back to cwd/scripts/fragments).
Smoke test on the 12 p2750 worlds of the earlier local deploy run (ladder_panel, opponent = recorded actions,
1 worker): copies `agents/mgt_lead_deploy_pre.py` (committed deploy before the resync, executor h5) and
`agents/mgt_lead_deploy_s1.py` (after the resync), so the old `mgt_lead_deploy` results stay intact.

| build (12 worlds) | mean margin | own cash | W-L | paired vs y3 (95% CI) |
|---|---:|---:|---|---|
| mgt_y3 (reference) | +4,672 | 110,322 | 9-3 | - |
| mgt_lead_deploy (older local run, same 12) | -47,260 | 75,444 | 0-12 | -51,932 |
| deploy before resync (executor h5) | -29,202 | 84,793 | 0-12 | -33,875 (-39,483 .. -28,017), 0/12 better |
| **deploy after resync (sched_maint + R16)** | **-19,300** | **92,068** | **1-11** | **-23,973 (-28,989 .. -18,354), 0/12 better** |

The executor upgrade carries into new worlds: +9,902 margin (+7,992 .. +11,852) vs the pre-resync deploy, better in
12/12 worlds (own cash +7.3k). The deploy mode is still 24k a game behind y3 there: the remaining gap is the
target builder (plan, market, hires), not the executor. The p2750 before-resync number (-33.9k on these 12)
matches the committed full-panel v2 figure (-33.7k), so these 12 worlds look representative.

## Deployment gap decomposition (hold-one-out on the deploy agent, 12 G1 leader worlds)
Harness cells (scripts/lead_ablation.py, `_DeployAdapter(mode='full', swap=...)`; the deploy file frozen at commit
b4ed59e via `LEAD_DEPLOY_PATH`): E2 = the full deploy agent (retrieval days 0-11 with this episode excluded, count
model from day 12, sell-as-it-reaches-the-shed, hands regression, no-feed hook, land_max 2). One component swapped for
the leader's at a time: E2s sell schedule (leader's cumulative units), E2h hires (leader's daily count, day-29
artifact corrected), E2p plan (leader's game as the Target all 30 days, all its land; deploy's sell rule, hands
regression from day 12 and no-feed hook kept), E2d plan through day 11 (leader's Target, then the count model).
R16 = the current G1 agent (leader plan + leader sell + leader hires) as reference.

| cell | mean12 | mean11 | clean9 | vs E2 (12) | revenue gap vs leader, k$/game | failed buys | no-effect | Hamming d6/d12/d20 | hires (leader) | plants died | animals lost | diverges from A |
|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|---:|---|
| R16 (leader plan + sell + hires) | 0.874 | 0.866 | 0.844 | +0.031 | -17.3: wheat -8.7, carrot -3.6, strawberry -2.9 | 0.9 | 0.1 | 1/19/22 | 294 (283) | 7.6 | 4.7 | 2 / 10 |
| **E2 full deploy** | **0.843** | **0.834** | **0.823** | | -26.0: carrot -7.7, wheat -5.8, tomato -3.6, egg -3.3 | 0.9 | 0 | 2/38/57 | 290 (283) | 2.0 | 12.2 | 1 / 7 |
| E2s + leader sell schedule | 0.893 | 0.883 | 0.871 | **+0.050** | -20.2: carrot -7.2, egg -4.3, wheat -4.0 | 0.9 | 0.3 | 2/38/57 | 291 (283) | 1.2 | 11.7 | 1 / 7 |
| E2h + leader hires | 0.859 | 0.851 | 0.837 | +0.016 | -23.5 | 0.9 | 0 | 2/39/57 | 294 (283) | 1.7 | 11.9 | 1 / 7 |
| E2p + leader plan (all days) | 0.746 | 0.738 | 0.732 | -0.097 | -19.8 | 0.9 | 0 | 1/18/23 | 307 (283) | 5.4 | 26.4 | 2 / 10 |
| E2d + leader plan to day 11, count model after | 0.804 | 0.797 | 0.781 | -0.039 | -23.7 | 0.9 | 0 | 1/18/45 | 300 (283) | 4.4 | 11.0 | 2 / 10 |

Isolation: failed buys 0.9/game in every cell, no-effect <= 0.3; the replayed opponent does not collapse in these
cells (10 of 12 games clean across all listed cells).

What it says:
1. In the leaders' own worlds the full deploy agent is only 0.03 behind the leader-following agent (0.843 vs 0.874);
   its own plan is not the problem there: with the leader's sell schedule it BEATS the leader-plan agent
   (E2s 0.893 vs R16 0.874).
2. The biggest single deploy component is the SELL RULE: +0.050 of leader cash (~5k a game) from the leader's schedule.
   Same units (strawberry 180 vs 175, milk 146 vs 139) at higher prices: milk 134.6 vs 126.7, wool 165.2 vs 149.4,
   carrot 65.2 vs 58.4, fertilizer 61.4 vs 58.9; the leader's schedule also sells more wheat (346 vs 294 units).
3. Hires: +0.016 with the leader's daily count (the regression hires ~1 hand/day too few early).
4. The deploy's other rules do not transfer onto the leader's plan: E2p loses 0.10, mostly the no-feed hook and the
   hands regression on a bigger four-quadrant farm (26 animals lost a game vs 12). E2d (leader's opening, then the
   count model) is below E2 too (-0.039): the count-model phase does better from the deploy's own (two-quadrant)
   opening than from the leader's; the retrieval phase itself is not the loser.
5. Strawberry calendar (G1 worlds): deploy first strawberry tiles day 3.8 (leader 3.0), first sale day 12.9 (leader
   13.2), units sold by day 15: 21 (leader 26, R16 19); total strawberry revenue 27.0k (leader 29.3k). The exemplar
   opening puts the deploy nearly on the leader's strawberry calendar in these worlds.
6. The new-world gap is different from the leader-world gap. In the 12 p2750 smoke worlds (deploy after resync vs
   y3, per game): own cash 92.1k vs 110.3k, revenue 114.9k vs 135.2k, spend 25.9k vs 27.9k. The deploy sells FEWER
   UNITS of everything at HIGHER prices: wheat 282 vs 442 units (-5.2k), milk 169 vs 209 (-3.2k), melon 72 vs 82
   (-2.9k), carrot 23 vs 87 (-2.8k), strawberry 167 vs 193 (-1.9k), wool 108 vs 138 (-1.6k), fertilizer 189 vs 225
   (-1.6k), tomato 75 vs 91 (-1.4k); eggs equal. The rival ends +5.7k richer against the deploy (our lower volumes
   keep its prices up). So in new worlds the deploy's loss is production VOLUME (plan scale: two quadrants by
   land_max, count-model targets), not the executor and mostly not the sell rule; in the leaders' worlds (where its
   retrieval has the leader-family opening and the count model is fitted on the same corpus) it keeps volume and loses
   mainly on sell prices.
7. Strawberry calendar in the p2750 smoke worlds (y3 re-run as a copy `agents/mgt_y3_cal.py` so per-day revenue is
   recorded; it reproduces y3's earlier panel margins in all 12): the deploy sells its first strawberries on day 13 in
   all 12 worlds, y3 on day 16. Cumulative strawberry revenue per game, deploy vs y3: day 16 3.8k vs 0, day 18 8.9k vs
   4.6k, day 21 15.4k vs 13.4k, day 25 20.0k vs 19.7k, end 24.0k vs 25.9k (167 vs 193 units). So the family-A opening
   IS in the deploy agent (3 days earlier than y3, and on the leader's calendar in the G1 worlds: day 12.9 vs 13.2),
   and its early price advantage is being realised; the deploy then falls behind on late-season strawberry volume
   (and on every other product), i.e. the new-world gap is plan scale after day 12, not the opening.
   (`scripts/lead_strawberry_calendar.py`; the panel's `revenue_daily` is cumulative per day boundary.)

Summary of where the deploy's -24k (new worlds) / -0.13 (leader worlds) sits:
- Executor: already shared with G1 (R16); its residual is the same ~0.13 of leader cash as G1's.
- Sell rule: -0.05 of leader cash in leader worlds (price per unit); in new worlds it is masked by lower volume.
- Hires: -0.016 (regression slightly short).
- Plan: fine in leader worlds (E2s > R16), too small in new worlds (units -15..-75% per product vs y3); the
  count-model phase does worse from the leader's four-quadrant opening (E2d) and the deploy's other rules do not
  transfer onto the leader's plan (E2p: no-feed + hands regression lose 26 animals a game).
Next levers, in order: plan volume in new worlds (land_max, count-model targets per product vs y3's units), a sell
rule that holds and batches like the leaders (worth ~5k a game), hands regression +1 early.

## Plan volume in new worlds (deploy research copy `agents/mgt_lead_deploy_pv.py`; variants `agents/mgt_lpv_<name>.py`)
Levers are DEP_CFG overrides (`scripts/lead_pv_variant.py NAME '{...}'`); `mgt_lead_deploy_pv` adds `cm_file` (count
model file) and `hands_add_early` (extra hands on days before compose_from). Measured on the 12 p2750 smoke worlds
(`scripts/lead_pv_report.py`, 1 worker per variant, two variants in parallel), paired vs y3 and vs the deploy baseline
(mgt_lead_deploy_s1 = committed deploy). G1 check (`ABL_SUFFIX=_<name> LEAD_DEPLOY_PATH=agents/mgt_lpv_<name>.py
lead_ablation.py run E2`) only for variants that help in the new worlds. Selling is out of scope (sem_market thread);
note the deploy's wheat-keep rule (holds the herd's feed to the end) lowers its wheat units sold.

| variant | margin | vs y3 | vs deploy_s1 (95% CI, better/12) | units wheat / carrot / milk / wool / straw / tomato / melon / egg |
|---|---:|---:|---|---|
| y3 | +4,672 | | | 442 / 87 / 209 / 138 / 193 / 91 / 82 / 118 |
| deploy_s1 (baseline) | -19,300 | -23,973 | | 282 / 23 / 169 / 108 / 167 / 75 / 72 / 122 |
| land3 (`land_max` 3: the SE quadrant) | -24,614 | -29,287 | -5,314 (-6,981..-3,454) 1/12 | 388 / 37 / 177 / 102 / 168 / 95 / 67 / 111 |
| cm600 (600-game count model) | -18,503 | -23,176 | +797 (-420..+1,969) 8/12 | 233 / 36 / 171 / 109 / 168 / 98 / 70 / 119 |
| he1 (`hands_add_early` 1) | -18,566 | -23,238 | +734 (-1,655..+3,411) 5/12 | 282 / 19 / 172 / 106 / 165 / 75 / 73 / 128 |
| wc15 (`pred_mult` WH, CA x1.5) | -18,653 | -23,325 | +648 (-207..+1,700) 4/12 | 298 / 15 / 170 / 106 / 168 / 75 / 72 / 121 |
| **nf99** (`nofeed_from` 99: the deploy's no-feed hook off; the executor's maintenance module still stops end-of-life animals) | **-14,507** | **-19,179** | **+4,794 (+2,352..+7,786) 11/12** | 230 / 22 / **212** / **130** / 167 / 76 / 71 / 125 (fertilizer 230) |
| hl6 (`h_long` 6) | -19,757 | -24,429 | -456 (-1,485..+589) 6/12 | 240 / 25 / 172 / 107 / 165 / 110 / 58 / 126 |
| **c1** = nf99 + cm600 + he1 | **-12,657** | **-17,329** | **+6,643 (+3,373..+10,157) 9/12** | 230 / 15 / 219 / 127 / 165 / 92 / 72 / 128 (fertilizer 242) |

G1 check (leader worlds, E2 cell with the variant, this episode held out of retrieval): **nf99 0.867 / 0.862 / 0.851**
(12 / 11 / clean9) vs E2 0.843 / 0.834 / 0.823 (+0.024; animals lost 3.7 vs 12.2 a game, plants died 1.1). Passes.
| c2 = c1 + `pred_mult` CA x2, ST x1.2 + `max_new_per_crop` 16 | -13,493 | -18,165 | +5,807 (+2,417..+9,482) 10/12 | 174 / 19 / 218 / 124 / **189** / 89 / 70 / 129 |

G1 check: **c1 0.871 / 0.865 / 0.846** (plants died 2.3, animals lost 4.3, failed buys 0.6/game). Passes (E2 0.843 / 0.834 / 0.823).
Carrot units do not respond to the count-model scale (x1.5: 15, x2: 19 vs y3 87): the carrot target is small in the
leaders' own data, so scaling it does little; strawberries do respond (x1.2: 189 vs y3 193) but take wheat tiles.
| c3 = c1 + `pred_mult` ST x1.2 | -13,282 | -17,954 | +6,019 (+2,543..+9,696) 9/12 | 179 / 15 / 217 / 124 / 191 / 90 / 71 / 128 |
| c4 = c1 + `hands_add` 2 (compose days) | -13,894 | -18,566 | +5,406 (+1,686..+9,434) 9/12 | 230 / 14 / 221 / 130 / 169 / 99 / 72 / 136 |

**Result.** Best: **c1 = `nofeed_from` 99 + `cm_file` count_model_600.json + `hands_add_early` 1**: new worlds
-12,657 margin (vs y3 -17,329, was -23,973: **+6,643 a game, 95% CI +3,373..+10,157**), leader worlds 0.871 / 0.865 /
0.846 (E2 0.843 / 0.834 / 0.823). Almost all of it is the no-feed hook (nf99 alone +4,794, 11/12 better; leader
worlds +0.024): the executor's maintenance module already stops end-of-life animals, so the deploy's own hook starved
producing animals (milk 169 -> 212-219 units, wool 108 -> 127-130, fertilizer 189 -> 230-242: now at or above y3).
The 600-game model and the early hand add +0.7..+0.8k each (not significant alone). The unit gap left vs y3: wheat
(230 vs 442; mostly the wheat-keep sell rule and y3's wheat trading, sell-rule thread), carrots (15 vs 87: leaders'
count targets are small; scaling does not raise them), strawberries (165 vs 193; x1.2 closes it but costs wheat
tiles, net -0.6k). The FOURTH quadrant (SE, $4000; the third PURCHASE after NE $1000 and SW $2000, i.e. 4 of 4 quadrants held) loses 5.3k; a longer horizon (6) and more composition hands lose.
Recommended deploy defaults: `nofeed_from` 99 (or drop the hook), `cm_file` count_model_600.json, `hands_add_early` 1
(`agents/mgt_lpv_c1.py` = the deploy with exactly these overrides; `agents/mgt_lead_deploy_pv.py` adds the two new
DEP_CFG options). `agents/mgt_lead_deploy.py` itself is not edited.

## c1 ported into the deploy, full p2750 panel, remaining new-world gap (2026-09-25)
Step 1: `agents/mgt_lead_deploy.py` now has c1 as DEFAULTS (`nofeed_from` 99, `cm_file` count_model_600.json,
`hands_add_early` 1, both new options ported). On the 12 p2750 smoke worlds it reproduces `agents/mgt_lpv_c1.py` to the
dollar (12/12, own and rival cash). The old local deploy results of those 12 worlds (an early version, -47k) were moved
to `results/fresh/ladder_panel/mgt_lead_deploy_oldlocal/`.
Step 2: full 185-game p2750 panel pushed to Kaggle (private dataset yiyangxudmm/kaggriculture-panel-bundle-lead, stage
results/fresh/kaggle_remote_lead, runs leadv30/31/32, 62/62/61 games, 4 workers each), results pending.
Step 3 (12 smoke worlds; `scripts/lead_newworld_gap.py mgt_lead_deploy mgt_y3_cal`): revenue gap vs y3 -16.8k a game
(118.4k vs 135.2k; spend equal 27.4k vs 27.9k). Split: VOLUME -14.8k (units short x y3's price), PRICE -2.0k (our units
x price difference; the market layer's share). By product (volume part): wheat -7.7k (230 vs 442 units; wheat-keep
rule and y3's wheat trading, sell thread), strawberry -3.8k (165 vs 193), carrot -3.2k (15 vs 87), melon -1.9k (72 vs
82), wool -1.4k (127 vs 138); milk +1.5k, fertilizer +1.0k, egg +0.5k. By day window (all products): days 0-11 -5.3k
(melon -4.3k, milk -2.0k: y3 sells its melons and first milk earlier), days 12-17 +3.7k (our early strawberries +4.1k
and milk +3.2k), days 18-23 -6.1k (strawberry -3.8k, wheat -1.8k), days 24-29 -9.1k (carrot -3.1k, strawberry -2.6k,
wheat -2.1k, tomato -1.3k). So after the market layer the gap left is late-season VOLUME: the second strawberry
cohort and late carrots/tomatoes (count-model targets fall off after day ~18; last_plant ST 18 / TO 20) plus wheat, and
the early melon timing.
Step 2 note, determinism bug found and fixed: the first Kaggle run (leadv3) drifted from the local runs in all 12
common worlds (by 100 to 10,700 own cash; engine 1.32.7 and Python 3.12 on both sides). Cause: `_dep_sem_path` took
the first hit of an unsorted `glob` over `data/leader_semantics/*/<episode>.json.gz`, and 48 of the 552 corpus episodes
exist under two teams (leaders who met each other), including the day-0 exemplar 112655730 (DSM vs Mother-Goose).
NTFS returns directories alphabetically, so every LOCAL measurement used 16730612 = Mother-Goose's seat of that game
as the opening (and the first-sorting seat of any duplicated retrieved episode); Linux returns them in arbitrary order.
Fix: `sorted(glob(...))` (reproduces the measured local behaviour everywhere). leadv3 is discarded (not merged); the
panel is re-run as leadv4. Follow-up for the plan thread: the exemplar is labelled "DSM" but is really Mother-Goose's
seat, and retrieval returns an episode, not a (team, episode) pair, so a duplicated episode resolves to the first
team by id; the retrieval should carry the team.
