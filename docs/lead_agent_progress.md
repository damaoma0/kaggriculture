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

### Full p2750 panel, new deploy (c1 defaults + glob fix), Kaggle run leadv4 (185 games)
Remote vs local: identical to the dollar in the 12 worlds run on both sides (12/12); 3 shards of 61-62 games, 4 workers,
563-655 s each (5.6-6.6 games/min per kernel). Results merged into `results/fresh/ladder_panel/mgt_lead_deploy/`
(`scripts/lead_panel_report.py results/fresh/ladder_panel/mgt_lead_deploy mgt_y3,mgt_m1`).

| build | mean margin | W-L | own cash | paired vs y3 (95% CI), better | paired vs m1 (95% CI), better |
|---|---:|---|---:|---|---|
| y3 | +1,093 | 87-98 | | | |
| m1 | +787 | 84-101 | | | |
| deploy v2 (committed earlier) | | | | -33.7k | |
| **deploy (c1 + glob fix)** | **-17,558** | **10-175** | 89,019 | **-18,652 (-21,118 .. -16,178), 6/185** | **-18,345 (-20,807 .. -15,823), 6/185** |

The opponent's recorded tape breaks (its commands without effect +40 vs y3's game) in 31 of 185 games; without them the
deploy is -21,539 vs y3 (n=154). Seat split vs y3: seat 1 -20,328 (n=104), seat 0 -16,499 (n=81).
Units per game (deploy vs y3): wheat 222 vs 392, carrot 20 vs 129, milk 202 vs 185, wool 137 vs 157, strawberry 176 vs
198, tomato 80 vs 81, melon 70 vs 82, egg 134 vs 118, fertilizer 241 vs 223. Revenue 113.8k vs 133.2k (-19.4k): VOLUME
-15.7k, PRICE -3.6k. Volume by product: wheat -6.3k, carrot -5.2k, wool -3.0k, strawberry -3.0k, melon -2.3k; milk
+2.1k, fertilizer +1.0k, egg +0.8k. Price part: milk -3.4k (we sell milk at 103 vs 120: more units into the same
demand), fertilizer -1.2k, melon -0.8k; strawberry +1.0k, wool +0.5k.

### Remaining new-world gap after the market layer (step 3)
If the market layer brings our prices to y3's (the -3.6k price part), about -15.7k of volume remains, all in the
PLAN: (1) carrots -5.2k: 20 units vs 129 over the full panel (the leaders' count targets for carrots are small
and do not respond to scaling; y3 plants carrots for Pet Cafe / Farmers Market demand); (2) wheat -6.3k: 222 vs 392
(the wheat-keep rule holds the herd's feed plus y3 trades wheat; sell thread); (3) wool -3.0k (137 vs 157 sheep
output), strawberry -3.0k (176 vs 198), melon -2.3k (70 vs 82). By day (12 smoke worlds with daily revenue on both
sides, see above): days 0-11 -5.3k (melon timing, first milk), days 12-17 +3.7k (our early strawberries), days
18-23 -6.1k and 24-29 -9.1k (second strawberry cohort, late carrots/tomatoes, wheat). The late season is where
the plan stops: count-model targets fall off after day ~18 (last_plant ST 18 / TO 20) and carrots never scale.

## Clean corpus, team-aware retrieval, late-season plan (2026-09-25)
- Clean corpus (60 scripted Boey games quarantined): deploy `cm_file` = count_model_540.json. The leadv4 full panel
  was built before the quarantine (contaminated corpus in retrieval + count_model_600); its results were moved to
  `results/fresh/ladder_panel/mgt_lead_deploy_leadv4_contaminated/`. Clean re-run of the same build = Kaggle leadv5
  (pending). Smoke worlds, clean baseline `mgt_lpv_clean0` (c1 + count_model_540): -18,168 vs y3 (c1 on the
  contaminated corpus -17,329; the difference is within noise).
- Team-aware retrieval: `leader_plan_retrieval.retrieve` already returns (team_id, episode, weight); the deploy
  dropped the team and resolved the episode by glob. Now `_dep_retrieve` returns (team, episode), the medoid is
  computed over (team, episode) keys, `_dep_load_sem(ep, team)` loads that seat, and the day-0 exemplar is DSM's own
  seat (`exemplar_team` 16732748; all earlier runs used Mother-Goose's seat of 112655730). No change to the shared
  retrieval module. Smoke worlds (`mgt_lpv_tm0`): -18,670 vs y3 (-502 vs clean0, n.s.; eggs 132 -> 166: DSM's opening
  has geese earlier).
- Late-season fill (`fill_free`, new DEP_CFG option, default 0): on composition days, free tiles beyond
  `fill_keep_empty` (4) get wheat (to planting day 25, full harvest) / carrots (to 26), carrot share 0.2 + 0.15 per
  carrot-demanding shop (max 0.6), at most `fill_max` a day. It never fires on our three quadrants (trace of world
  111577649: the count model already replants every harvested tile the same day; empty tiles at day start are
  just-harvested ones): tf1 -18,992 vs y3, units unchanged. With the fourth quadrant (SE, $4,000) it does fill:
  tf1q4 -26,581 / tf2q4 (fill_max 20) -26,339 vs y3, -2.6k / -2.4k vs deploy_s1: wheat +60, carrot +20, tomato +16
  units a game, not enough to pay for the land, seeds and hands. Rejected.
- Wheat-to-carrot swap (`wc_swap`, default 0; share of the count model's wheat plantings turned into carrots, +0.15
  per carrot-demanding shop): sw1 (0.1) -19,295 / sw3 (0.3) -21,007 vs y3 on the smoke worlds: carrots 125 / 158 units
  (above y3's 87) but wheat 116 / 93; net worse than tm0 by 0.6k / 2.3k. Rejected.
- Full panel (Kaggle, 185 games, remote = local 12/12 in both runs):
  - leadv5 = clean baseline (c1 + count_model_540, sorted glob): **-18,833 vs y3 (95% CI -21,331 .. -16,327)**,
    -18,527 vs m1, W-L 10-175 (contaminated leadv4 was -18,652: the contamination did not matter). Merged as
    `results/fresh/ladder_panel/mgt_lead_deploy/`.
  - leadv6 = + team-aware retrieval and DSM's exemplar seat (current defaults): -19,025 vs y3 (-21,592 .. -16,259),
    **-191 vs leadv5 (-1,095 .. +877), better in 88/185: neutral**. `results/fresh/ladder_panel/mgt_lead_deploy_tm/`.
  - G1 leader worlds of the team-aware build: 0.849 / 0.844 / 0.837 (E2 0.843 / 0.834 / 0.823; c1 0.871 / 0.865 /
    0.846: DSM's own seat as the opening is 0.02 below Mother-Goose's in the leaders' worlds, within noise on p2750).
- Late-season plan: no lever found. Our three quadrants are full all season (the count model replants every
  harvested tile the same day), so there is nothing to fill; more land (fourth quadrant) and more carrots both lose.
  The unit gap to y3 (wheat 238 vs 392, carrot 14 vs 129) comes with y3's whole strategy (wheat trading, a different
  crop mix) rather than idle land or late count targets.
- Sell module merged (`scripts/sem_market_merge.py agents/mgt_lead_deploy.py agents/mgt_lead_deploy.py`,
  `sell_source` default "sem", strawberry-only hold; the block loads scripts/fragments/sem_market.py like
  sem_maintenance and sits INSIDE the executor section, so any `resync_lead_deploy.py` must be followed by a re-merge).
  Pre-merge copy: `results/fresh/lead_agent_20260924/snap/mgt_lead_deploy_premarket.py`.
  - smoke worlds (`mgt_lpv_sem`): -18,893 vs y3 (tm0 -18,670; own cash 93.9k vs 93.4k).
  - full panel leadv7 (remote = local 12/12): **-19,055 vs y3 (95% CI -21,654 .. -16,303), -18,749 vs m1, W-L 10-175;
    vs the pre-merge build (leadv6) -30 (-252 .. +196), better in 84/185: neutral in new worlds** (as the sell thread
    measured: -41, CI -337..+244), own cash +774 (89.7k vs 88.9k), revenue +820 (strawberry price 145.4 vs 142-ish).
    `results/fresh/ladder_panel/mgt_lead_deploy_sem/`.
  - remaining gap vs y3 with the market layer in: revenue -19.0k = VOLUME -16.4k (wheat -5.7k, carrot -5.4k, wool
    -3.4k, strawberry -3.1k, melon -2.2k; milk +2.2k, egg +1.1k, fertilizer +0.9k) + PRICE -2.6k (milk -3.4k at 103 vs
    120: the herd sells more milk into the same demand; strawberry +1.8k now).

Current deploy defaults (all measured above): c1 (no-feed off, early hand) + count_model_540 + sorted-glob seat lookup +
team-aware retrieval with DSM's exemplar seat + sem sell rule; `fill_free` and `wc_swap` exist but are off.
Full-panel margin vs y3 per game: leadv5 -18,833 -> leadv6 -19,025 -> leadv7 -19,055 (all within noise of each
other); the remaining new-world loss is production volume from the plan (crop mix and scale vs y3), not land left idle.

## Crop cycles per tile: deploy vs y3 (12 p2750 smoke worlds; `scripts/lead_cycles.py`)
Extracted from each agent's own observations (per-step tile diffs of its farm, no engine hooks): plantings,
harvests (units = yield just before the tile emptied / the yield reset to 0), crop age at harvest, cycle length per
tile (planting -> next planting on the same tile), tile-days (day-start crop tiles), deaths (plant -> weed; for
strawberry/tomato this includes the natural end of life after the 4th production). Per game:

| crop | plantings y3 / deploy | harvested units y3 / deploy | units per planting | harvest age - full-yield age | cycle days per tile | tile-days | died |
|---|---|---|---|---|---|---|---|
| wheat | 155.4 / 119.9 | 655.6 / 526.8 | 4.22 / 4.39 | -0.89 / -0.23 | **3.24 / 4.77** | 483 / 460 | 4.0 / 8.3 |
| carrot | 27.2 / 6.1 | 86.9 / 11.3 | 3.20 / 1.86 | -0.33 / -0.02 | 3.01 / 3.89 | 72 / 18 | 0.1 / 1.1 |
| strawberry | 25.7 / 23.5 | 194.6 / 163.9 | 7.58 / 6.98 | - | 16.07 / 17.52 | 415 / 384 | 6.8 / 21.8 |
| tomato | 12.8 / 13.5 | 87.2 / 77.7 | 6.79 / 5.75 | - | 11.12 / 12.72 | 141 / 151 | 2.0 / 10.8 |
| melon | 13.8 / 12.1 | 82.0 / 70.8 | 5.96 / 5.86 | 0 / +0.21 | 10.38 / 10.67 | 138 / 123 | 0 / 0 |

Where y3's extra wheat comes from: the same wheat area (483 vs 460 tile-days) turned over faster: y3 harvests about a
day before full yield (age ~3.1; 4.22 units a planting, i.e. fertilised wheat at age 3 gives 5) and replants the same
day: 3.24-day cycles, 1.30 wheat per tile-day. We harvest near full yield (age ~3.8) and the count model replants only
at the next day's compose: 4.77-day cycles, 0.92 per tile-day (+129 wheat a game for y3). Carrots are a planting
target gap (6 plantings vs 27), not a cycle gap. Strawberry/tomato: similar plantings, fewer units per planting (6.98
vs 7.58, 5.75 vs 6.79: fertilised productions) and a longer tail before replanting (17.5 vs 16.1 days).

### Harvest-when-ready / same-day replant test
New options (default off): executor `early_onetime` (sem_maintenance optional harvests also for wheat/carrot from one
day before full yield; `agents/mgt_lead.py`, re-synced into the deploy and the sell block re-merged), deploy
`replant_same_day` / `replant_from` (a wheat/carrot tile harvested during the day gets a same-crop planting event the
same day, count-model phase from day 12).

| build (12 smoke worlds) | margin | vs y3 | vs current deploy (sem), 95% CI, better | wheat / carrot / straw / tomato / melon units sold |
|---|---:|---:|---|---|
| current (sem) | -14,221 | -18,893 | | 223 / 11 / 163 / 81 / 71 |
| rp1 = same-day replant | -13,323 | -17,995 | +898 (-346 .. +2,042), 9/12 | 335 / 23 / 155 / 54 / 65 |
| rp1e = rp1 + early_onetime | -13,173 | -17,845 | +1,048 (-1,983 .. +4,202), 6/12 | 288 / 15 / 156 / 53 / 66 |

Cycle table for rp1 (smoke worlds): wheat plantings 151 (was 120; y3 155), wheat harvested 679 (was 527; y3 656), cycle
4.18 days (was 4.77; y3 3.24), BUT wheat tile-days 584 (was 460; y3 483): the replanted wheat keeps tiles the count
model would have given to other crops (tomato plantings 10.3 vs 13.5, units 51 vs 78; melon 65 vs 71).
G1 leader worlds (like for like, both with the sell module): current 0.858 / 0.852 / 0.842, rp1 0.862 / 0.856 / 0.847
(+0.004, 7/12 better): no harm.
**Full panel (Kaggle leadv8, remote = local 12/12): rp1 -18,980 vs y3 (-21,616 .. -16,095), -18,674 vs m1, W-L 13-172;
vs current deploy +75 (-473 .. +618), better in 101/185: neutral.** Volume moved exactly as intended for wheat (363 vs
238 units sold; y3 392), but tomato (40 vs 71), strawberry (165 vs 175) and melon (65 vs 71) fell by as much: revenue
113.5k vs 114.2k. The panel gap by product after rp1: carrot -5.1k, strawberry -4.5k (volume), melon -3.3k, tomato
-3.3k, wool -3.3k, wheat only -1.1k; milk price -3.7k.
Conclusion: the cycle mechanism is real and explains y3's extra wheat (faster turnover of the same area), but on our
three quadrants it only trades crops: tiles are the binding resource, and faster wheat takes tiles from higher-value
crops unless the count model's crop allocation accounts for it. Not adopted as a default (neutral); `replant_same_day`
stays available for a joint re-allocation (e.g. with the count model's wheat target reduced by the turnover gain).
Note: the G1 baseline run for the sem build started at 2.9 GB free (my wait loop timed out instead of aborting);
it completed normally at 2.1 GB.

## Units per planting (execution) and the capped replant (2026-09-25)
Local memory stayed at 2.1-2.7 GB (other desktop apps), so this round ran on Kaggle: smoke-world panels (runs pvs1,
pvs2), the cycle extraction as remote commands (cycsem, cycy3; `lead_cycles.py` now records day-start plant states),
and the G1 leader-world cells as a remote command (g1a; new harness cells E2sem/E2rpc1/E2rpc1h/E2sh point the deploy
adapter at a variant file; the remote E2sem reproduces the local run 12/12). `runpv.sh` / `memgate.sh` now ABORT
when free memory stays under 3 GB.

Per-planting fates (12 smoke worlds; `lead_cycles.py fates`):
- carrot 1.86 units/planting: only 56% of our carrot plantings are harvested (y3 98%); 18% die unharvested at age 4
  (the age-3 harvest deadline missed, then decay), 26% are never harvested before the season ends (late plantings);
  none fertilised (y3 fertilises 69% at age 2 and gets 3.78 at age 3). Watering is complete (100% at ages 0 and 2).
- wheat: 7% of our plantings die unharvested at age 5 (missed harvest); fertilised at age 2 only 5% (y3 64%).
- tomato 5.75 vs 6.79 and strawberry 6.98 vs 7.58: fertiliser and water on production days match y3 (81-91%);
  the gap is late plantings cut by the season end (our last harvests at ages 9-10 / 10-14, y3's almost all at 11 /
  16), i.e. the count model's last planting days (strawberry 18, tomato 20) vs y3 stopping earlier.
Variants (smoke worlds, paired vs the current deploy "sem"; G1 = leader worlds 12 / 11 / clean9):
| variant | vs y3 | vs current (95% CI), better | G1 | units wheat / carrot / straw / tomato / melon |
|---|---:|---|---|---|
| current (sem) | -18,893 | | 0.858 / 0.852 / 0.842 | 223 / 11 / 163 / 81 / 71 |
| fT = fertilize True for tomato, strawberry, wheat | -20,340 | -1,446 (-3,292 .. +932), 3/12 | | 220 / 12 / 163 / 87 / 72 |
| fTS = fertilize True for tomato, strawberry | -18,844 | +49 (-179 .. +261), 3/12 | | 222 / 11 / 163 / 80 / 71 |
| sh = harvest deadlines in the survival routes (`surv_harvest`) | -19,488 | -595 (-1,982 .. +795), 5/12 | 0.859 / 0.853 / 0.842 | 213 / 14 / 163 / 82 / 72 |
| **rpc1 = same-day replant, capped at the count model's wheat target** | **-16,908** | **+1,985 (+343 .. +3,689), 8/12** | **0.869 / 0.863 / 0.858** | 312 / 22 / 159 / 58 / 66 |
| rpc1h = rpc1 + surv_harvest | -17,679 | +1,214 (-382 .. +3,105), 7/12 | 0.857 / 0.851 / 0.838 | 312 / 26 / 162 / 50 / 66 |
| rpc1st = rpc1 + last planting strawberry 14 / tomato 18 | -16,889 | +2,005 (+180 .. +3,927), 8/12 | | 342 / 23 / 157 / 51 / 65 |
Fertiliser supply is not the constraint (we sell ~240 a game); forcing it onto wheat costs labour and loses.
Reserving end-of-day labour for harvest deadlines takes it from waterings/feeds and loses. The cap (no wheat replant
once wheat tiles reach the count model's wheat target) keeps most of the faster wheat turnover without starving the
other crops as much as the uncapped rp1 (smoke +1,985 vs +898).
**Full panel rpc1 (Kaggle leadv9, 185 games; its 12 smoke worlds equal the earlier remote smoke run 12/12):
-17,833 vs y3 (95% CI -20,446 .. -15,018), -17,527 vs m1, W-L 13-172; vs the current deploy (leadv7 "sem")
+1,222 (+759 .. +1,702), better in 118/185.** Units: wheat 330 (sem 238, y3 392), carrot 21, tomato 48 (sem 71),
melon 66 (71), strawberry 171 (175); revenue 114.4k (sem 114.2k) with lower spend. Adopted as the deploy default
(`replant_same_day` 1, `replant_cap` 1.0).

## Harvest value and planting cutoffs (2026-09-25)
Harvest value: the maintenance module already gives a one-time crop at full yield a HARVEST worth the whole crop
(carrot age 3, 3 units + window water: value 180 = 4 x 45, deadline 23; once decaying: deadline 0, "-1 unit per 2 h").
The dying carrots (smoke worlds) were not undervalued but UNVISITED on their age-3 day: they start age 4 unwatered
(consecutive_unwatered 1) at 2 units instead of 3, and decay kills them by hour 2, before the hands arrive. The greedy
dispatcher never reads job values (only priority classes and distance), so a whole-crop harvest competes like any
other task. Tested `atrisk_bonus` (new executor option: a distance bonus in the greedy cost, all day, for a one-time
crop at/after full yield with a harvest pending; no end-of-day reservation).
Planting cutoffs: new executor option `plant_cutoff` (crop -> last planting day with a full harvest; applies to every
planting event incl. retrieval-phase and catch-up plantings; skipped would-be plantings logged as `cut_<crop>`) plus
the deploy's count-model `last_plant` set to the same days (wheat 25, carrot 26, tomato 18, strawberry 13, melon 19).
Abandonment verdicts of the maintenance module are now logged at the end (`abandon_<verdict>_<kind>`).
All on Kaggle (pvs3 smoke panel, g1b leader-world cells; base3 reproduces the earlier rpc1 smoke run 12/12).

| variant | smoke vs y3 | smoke vs current (rpc1) (95% CI), better | G1 deploy (12 / 11 / clean9) | units wheat / carrot / straw / tomato |
|---|---:|---|---|---|
| current (rpc1) | -16,908 | | 0.869 / 0.863 / 0.858 | 312 / 22 / 159 / 58 |
| atrisk_bonus 4 | -24,679 | -7,771 (-10,166 .. -5,645), 0/12 | 0.850 / 0.841 / 0.823 | 399 / 23 / 153 / 42 |
| atrisk_bonus 8 | -28,322 | -11,413 (-13,872 .. -8,930), 0/12 | 0.847 / 0.838 / 0.818 | 421 / 25 / 144 / 38 |
| cutoffs | -17,024 | -116 (-734 .. +448), 6/12 | 0.874 / 0.869 / 0.862 | 322 / 34 / 154 / 52 |
G1 leader-plan agent (the G1 build itself, leader's plan): base 0.874 / 0.866 / 0.844, cutoffs 0.881 / 0.871 / 0.853,
atrisk 4 0.858 / 0.850 / 0.831.
Would-be plantings skipped per game (cutoffs): deploy strawberry 9.6, tomato 2.6, wheat 12.9, carrot 4.6 (catch-up and
replant events past the day); leader-plan agent strawberry 12.8, tomato 7.5, wheat 22.8, carrot 12.2 (the leaders' own
late plantings). Abandonment 'error' entries per game: leader-plan agent wheat 2.4, carrot 0.5, cow 1.8, sheep 0.7 ->
with cutoffs wheat 0, carrot 0 (cow 1.0, sheep 1.0 remain); deploy strawberry 0.2 -> 0 (errors were already rare there;
most abandonments are end-of-life: strawberry ~23, tomato ~6, sheep ~3 a game).
The at-risk bonus is rejected: every mature wheat tile qualifies, so hands chase wheat harvests and tomatoes collapse.
Cutoffs: neutral on the 12 smoke worlds, +0.005 (deploy) / +0.007 (leader plan) in the leader worlds.
**Full panel cutoffs (Kaggle leadv10, 185 games; its 12 smoke worlds equal the smoke run 12/12): -17,497 vs y3 (95% CI
-20,119 .. -14,687), -17,190 vs m1, W-L 11-174; vs the current deploy (rpc1) +336 (+99 .. +578), better in 108/185.**
Units: carrot 31 (21), wheat 335 (330), strawberry 168 (171), tomato 43 (48); own cash 90.8k (90.5k).
Adopted as defaults: executor `plant_cutoff` {strawberry 13, tomato 18, melon 19, wheat 25, carrot 26} (applies to the
G1 agent too: 0.881 / 0.871 / 0.853) and the deploy's `last_plant` = the same days. Deploy trajectory on the full panel
vs y3: sem -19,055 -> rpc1 -17,833 -> cutoffs -17,497.

## Per-product gap on the current build (cutoffs) vs y3, full panel (2026-09-25)
y3 re-run as `mgt_y3_cal` on all 185 games (Kaggle y3cal0-2; identical to the stored y3 results 185/185) so both
sides have daily revenue. `lead_newworld_gap.py mgt_lpv_cut mgt_y3_cal`: revenue -18.9k a game (114.3k vs 133.2k;
spend 26.5k vs 28.9k) = VOLUME -15.8k + PRICE -3.1k.
| product | units | rev gap | volume | price | d0-11 | d12-17 | d18-23 | d24-29 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| carrot | 31 vs 129 | -4,486 | -4,619 | +133 | 0 | +270 | -468 | -4,289 |
| melon | 66 vs 82 | -3,546 | -3,071 | -476 | -4,394 | +741 | -448 | +555 |
| tomato | 43 vs 81 | -2,983 | -3,048 | +65 | 0 | +2 | -364 | -2,620 |
| wool | 135 vs 157 | -2,619 | -3,251 | +632 | +1,595 | -1,782 | -1,426 | -1,007 |
| wheat | 335 vs 392 | -2,462 | -2,089 | -373 | -656 | -1,846 | -171 | +210 |
| strawberry | 168 vs 198 | -2,283 | -4,068 | +1,785 | 0 | +3,515 | -3,199 | -2,600 |
| milk | 207 vs 185 | -1,052 | +2,721 | -3,773 | -1,997 | +2,259 | -438 | -877 |
| fertilizer | 234 vs 223 | -429 | +604 | -1,034 | -162 | -952 | +430 | +255 |
| egg | 139 vs 118 | +970 | +1,017 | -47 | +222 | +94 | +227 | +427 |
| total | | -18,891 | -15,804 | -3,087 | -5,392 | +2,301 | -5,856 | -9,944 |
Value per tile-day (units x price / days a tile is held): carrot ~50, tomato ~47, wheat after rpc1 ~47, strawberry
~64, melon ~112. Carrots and tomatoes only replace wheat at equal value, which is why every carrot-for-wheat swap
tested neutral (wc_swap, um1). Melon is where a tile is worth most, and y3 plants 12 melons on day 0 (+~2 later;
13.8 a game, 82 units) against our 6 on day 0 + 4 on day 1 (+~2 in the count-model phase; 12.1, 71 units).

Hypothesis (b) tested first and rejected: "the capped wheat replant keeps harvested tiles occupied, so the count
model's tomato/strawberry/melon targets go unmet". Logged unmet targets (leader worlds, per game): wheat 102, carrot
47, tomato 2.0, melon 0.8, strawberry 0.5. Option `replant_unmet` (a harvested wheat/carrot tile takes the
highest-value crop whose target went unmet today) therefore mostly planted carrots on wheat tiles: smoke -213
(-1,525 .. +1,093), 4/12 better; carrots 34 -> 137, wheat 322 -> 180; G1 deploy 0.874 -> 0.864. The tomato decline
(71 -> 43 since rpc1/cutoffs) is the count model's autoregressive tomato target (+0.68 per current tomato tile,
+4.2 per tomato-demanding shop) starting from a low tomato count, plus the tomato cutoff at day 18.
Now testing (d) melons: count-model melon target x2 / x3 (`pred_mult` ME) in the composition phase.
Melon target (composition phase, `pred_mult` ME), all on Kaggle:
| variant | smoke vs current (cutoffs) (95% CI), better | G1 deploy (12 / 11 / clean9) | melon / wheat / tomato units |
|---|---|---|---|
| current (cutoffs) | | 0.874 / 0.869 / 0.862 | 66 / 322 / 52 (smoke) |
| ME x2 | +229 (-857 .. +1,200), 6/12 | 0.872 / 0.866 / 0.856 | 72 / 323 / 46 |
| ME x3 | +403 (-834 .. +1,439), 9/12 | 0.882 / 0.874 / 0.861 | 74 / 310 / 51 |
**Full panel ME x3 (Kaggle leadv11; its 12 smoke worlds equal the smoke run 12/12): -17,182 vs y3 (95% CI -19,759 ..
-14,385), -16,875 vs m1, W-L 12-173; vs cutoffs +315 (+23 .. +609), better in 101/185.** Melons 74 (66; y3 82),
revenue 114.7k (114.3k). Adopted as the deploy default (`pred_mult` {"ME": 3.0}). The count model's melon target is
small even tripled (+8 units); y3's melon lead is its day-0 opening (12 melons), which the family-A opening's cash
cannot fund without fewer animals. Deploy vs y3 on the full panel: sem -19,055 -> rpc1 -17,833 -> cutoffs -17,497 ->
melons x3 -17,182.

## Land use vs yield: ours (current deploy, melons x3) vs y3, 40 panel worlds (2026-09-25)
`lead_cycles.py` now also records the whole farm at each day start (empty, weed, locked, crop, animal, empty
structure) and animal harvests; `lead_cycles.py land <agents>` gives, per day window, the share of UNLOCKED tiles by
use and units harvested per unlocked tile-day. Extracted on Kaggle (landc0/1, landy0/1; 12 smoke + 28 random p2750
worlds; `mgt_lpv_cur5` = the current deploy).
| days | unlocked ours / y3 | empty | weed | wheat | carrot | tomato | strawberry | melon | animal | empty struct |
|---|---|---|---|---|---|---|---|---|---|---|
| 6-11 | 54.2 / 45.8 | 10.2 / 2.5% | 0 / 0 | 19.9 / 19.0 | 0.2 / 0 | 1.5 / 0 | 27.1 / 28.2 | 16.9 / 22.6 | 22.8 / 23.8 | 1.2 / 3.9 |
| 12-17 | 75 / 75 | 2.4 / 5.1% | 0.5 / 0.2 | 30.0 / 25.7 | 1.2 / 0.3 | 8.0 / 8.6 | 29.8 / 33.5 | 2.4 / 2.3 | 23.9 / 23.7 | 1.7 / 0.6 |
| 18-23 | 75 / 75 | 1.4 / 1.9% | 3.4 / 0.4 | 30.4 / 22.1 | 0.9 / 2.8 | 9.0 / 15.8 | 25.6 / 31.8 | 3.8 / 1.0 | 24.1 / 23.8 | 1.4 / 0.4 |
| 24-29 | 75 / 75 | **15.2 / 7.2%** | **7.0 / 1.0** | 38.0 / 34.5 | **2.4 / 16.6** | 2.3 / 5.4 | 8.3 / 12.4 | 1.3 / 0 | 22.9 / 21.6 | 2.7 / 1.2 |
Units harvested per unlocked tile-day (days 6-29): ours 0.838, y3 0.933 (-10%); base-price value 74.5 vs 82.8.
Units per game: ours 1,404 (wheat 610, milk 210, strawberry 165, egg 142, wool 135, melon 74, tomato 46, carrot 23),
y3 1,515 (wheat 588, strawberry 196, milk 186, wool 157, egg 114, carrot 108, tomato 83, melon 82).
Reading: through day 23 our land is as fully used as y3's (days 6-11 we have MORE unlocked, partly empty, because we
buy NE earlier). In days 24-29 we leave 22% of unlocked tiles empty or weed vs y3's 8% (about 63 idle tile-days a
game; y3 grows carrots there: 17% of its tiles). Before that, the gap is crop mix at equal land (more wheat, fewer
tomatoes/strawberries in days 18-23). Testing the end-season fill (`fill_free`, weeds count as free, cutoffs apply).

### End-season fill under the current cutoffs: neutral (Kaggle pvs6 / g1e)
| variant | smoke vs current (95% CI), better | smoke units wheat / carrot | G1 deploy (12 / 11 / clean9) |
|---|---|---|---|
| current (`mgt_lpv_cur5`; = the ME x3 smoke run 12/12) | | 310 / 31 | 0.882 / 0.874 / 0.861 |
| fl1 `fill_free` 1 (keep 4 empty, max 10/day) | +75 (+0 .. +224), 1/12 | 311 / 31 | 0.881 / 0.874 / 0.861 |
| fl2 keep 0, max 20/day, carrot share 0.5 | -93 (-270 .. +63), 5/12 | 309 / 32 | 0.881 / 0.873 / 0.859 |
The fill barely fires: units are unchanged. Why (day-by-day, same 40 worlds): our idle land is on days 27-29
(empty 11 / 20 / 29 tiles vs y3 1.6 / 4.2 / 21), i.e. AFTER our wheat 25 / carrot 26 cutoffs, so the fill (which
respects them) cannot touch it. y3 keeps planting past them and harvests on day 29: per game it plants 9.1 carrots on
day 27 (8.8 harvested, 19.3 units), 6.0 wheat on day 26 (23.6 units) and 4.0 wheat on day 27 (7.4 units), plus 7.5
carrots on day 26 (27.8 units) where we plant 2.8. Our cutoffs are "last FULL-harvest day"; a day-27 wheat/carrot
planting is 2 days old on day 29 (= first yield day) and our executor harvests any yielding one-time crop on day 29,
sem_maintenance does not abandon it (full_units > 0 by step 718). Testing wheat/carrot cutoffs 27 (`c27`, deploy
last_plant + executor plant_cutoff) and c27 + fill through day 27 (`c27f`, keep 0, max 20, carrot share 0.5) on
smoke + G1 (Kaggle pvs7 / g1f; Gc27 = leader-plan agent with the same cutoffs) and c27 on the full panel (pfc27).

### Later wheat / carrot cutoffs (27): negative (Kaggle pvs7 / g1f)
| variant | smoke vs current (95% CI), better/worse | smoke sold wheat / carrot | G1 (12 / 11 / clean9) |
|---|---|---|---|
| current deploy (`cur5`) | | 310 / 30 | 0.882 / 0.874 / 0.861 |
| c27 (wheat, carrot cutoffs 27) | **-884 (-1,464 .. -323), 3/9** | 321 / 22 | 0.866 / 0.859 / 0.845 |
| c27f (c27 + fill through day 27, keep 0, max 20, carrots 0.5) | -928 (-1,552 .. -330), 3/9 | 320 / 22 | 0.867 / 0.860 / 0.846 |
| leader-plan agent `mgt_lead` (current defaults, cutoffs 25/26; = Gcut 12/12) | | | 0.881 / 0.871 / 0.853 |
| leader-plan agent, cutoffs 27 (Gc27) | | | 0.872 / 0.865 / 0.846 |
Where c27 loses (smoke, per game): wheat revenue +388 for +198 wheat seed and +241 wages, carrot -340, and small
losses on fertilizer / egg / milk / melon / tomato (-485 together). G1 agent logs: carrot cuts 4.2 -> 0.7 (the day-27
carrots are planted), but skipped maintenance value 44.8k -> 48.2k, wheat dying while assigned 11.6 -> 13.4, unmet
carrot / wheat orders up, idle-hand passes down (h12 203 -> 182, h18 598 -> 562). The fill again adds nothing
(the extra free tiles are taken by same-day wheat replants). Days 26-29 are LABOUR-bound for our executor: the idle
tiles are not free capacity, every extra planting is paid for by jobs dropped elsewhere.
**Full panel c27 (Kaggle pfc27, 185 p2750 worlds): -1,152 vs current (95% CI -1,267 .. -1,037), better in 17/185;
-18,334 vs y3, W-L 12-173.** Sold units wheat 341 (332), carrot 18 (27): the later wheat cutoff lets same-day wheat
replants take the day 26-27 tiles and the extra wheat sells into a falling late price; carrots fall. Rejected.
**Land use vs yield, conclusion:** utilisation through day 23 equals y3's; the extra idle tile-days after day 26 cannot
be filled profitably by our executor (fill neutral, later cutoffs negative). The remaining plan-side gap is yield per
tile / crop mix, not land; plan-side work stops here as instructed.

## Idle passes vs dropped maintenance: trace (2026-09-25)
Tracer in the executor (`CFG idle_trace`, off by default; mgt_lead.py and the deploy copy): at every PASS it records
the open tasks and, per task, why that unit did not take it (taken by another unit + both distances / item neither
carried nor in the shed / plant pipeline too late / valid cost); at hour 23 a fresh sem_maintenance solve values the
jobs still open (non-optional, value > 0, minus what hour 23 itself does) in coins. Report: `scripts/lead_idle_report.py`.
The tracer is passive: smoke 12/12 and G1 12/12 identical to the current deploy, leader-plan agent G1 12/12 identical
to Gcut (the "Gbase" 0.874 in the previous table was a stale pre-cutoff directory; fixed above).
Note: the log's `skipped_value` (44.8k/game) mixes module coins with placeholder values (400 per plan job, 50 per
legacy op); the traced dropped value in module coins is **14.9k/game (smoke), 13.1k (G1 deploy), 24.5k (G1
leader-plan agent)**.
First result (smoke, deploy): idle passes and dropped jobs are on DIFFERENT days. Days 0-8 (opening, few assets):
40-88 idle passes a day, nothing dropped. Days 9-27: 4-17 idle passes a day, nearly all after 18h, and 0.3-2.0k of jobs
dropped a day. Of the dropped value, 11.4k is on jobs that were held by another unit at every idle pass that
coexisted with them (the owner did not finish), 2.5k had no idle unit at all, 0.66k had an idle unit with a valid
cost (units parked on a stale delivery assignment), plant-late 0.24k, missing items 0.15k, not in the task list
0.04k. Idle passes: 342/game "every open task already taken", 261 "nothing open" (226 of them after 18h),
111 "plant too late + rest taken", 49 "items missing". Refined run (owner distance, work account) in progress.
Refined trace (owner distance + work account; smoke trs2 and G1 trg2, both identical to the current deploy):
| | smoke (12) | G1 deploy (12) |
|---|---|---|
| dropped maintenance value per game (module coins) | 14,893 | 13,140 |
| ... with an idle unit able to reach it before 23h ("taken" + "valid") | 1,285 | 2,292 |
| ... of which the idle unit was nearer than the job's owner | 397 | 417 |
| ... no reachable idle unit (capacity / order) | 13,608 | 10,848 |
| days 9-26 unit-steps: walking / maintenance ops / plan ops / shed pick-drop-place / idle | 46.6 / 35.9 / 3.1 / 6.5 / 3.1% | 46.3 / 36.0 / 3.2 / 6.6 / 3.3% |
| executed ops worth < 30 coins / 0 / not in the module list (share of unit-steps) | 3.0 / 0.6 / 5.7% | 2.7 / 0.6 / 5.8% |
**Answer to "dropped jobs coexist with idle hands": they mostly do not.** Idle hands cluster on the slack opening
days (0-8) and in the last hours of saturated days, when every remaining job is already held by a unit and too far for
the idle one to reach before the day ends. At most 1.3k (smoke) / 2.3k (G1) of dropped value per game had an idle
unit that could have done it in time. The "valid" idle units are a one-step bug (a unit that DROPs two or more
products keeps its delivery assignment for one more step and passes; 4-7 steps a game). Dropped jobs are spread over
the farm like the tiles (not concentrated in far corners); by value: 16.9 jobs/game >= 200 coins (5.9k), 23.6 at
100-200 (3.6k). The lever is capacity (walking is 46% of unit time on saturated days) and order (low-value work done
while high-value work is dropped). Tests in flight: release of the stale delivery assignment (fx1); value threshold
for priority 1 (pv30 / pv60, ops worth less count as priority 2 = after 15h); no mid-day delivery trips unless cash
binds (nd); +1 hand on count-model days (h2); zone penalty 2 / 4 (z2 / z4).
Capacity / zone tests (Kaggle pvs8 / g1g):
| variant | smoke vs current (95% CI), better | G1 deploy (12 / 11 / clean9) |
|---|---|---|
| current | | 0.882 / 0.874 / 0.861 |
| h2: +1 hand on count-model days (hands_add 2) | -279 (-2,041 .. +1,731), 4/12 | 0.861 / 0.851 / 0.844 |
| z2: zone penalty 2 | -15,011 (-19,917 .. -11,143), 0/12 | 0.863 / 0.853 / 0.827 |
| z4: zone penalty 4 | -18,271 (-22,603 .. -13,958), 0/12 | 0.854 / 0.841 / 0.801 |
Rejected. A 13th hand's wage (233/day) is not recovered by the work it adds; zones (shed pickups sized to the whole
zone's need, units held to their chunk) are far worse than the free greedy.
Dispatcher fixes (Kaggle pvs9 / g1h; all include fx1 except the current row):
| variant | smoke vs current (95% CI), better/worse | G1 deploy (12 / 11 / clean9) |
|---|---|---|
| current | | 0.882 / 0.874 / 0.861 |
| fx1: release a delivery assignment once nothing deliverable is carried | +224 (-153 .. +633), 5/4 | 0.882 / 0.874 / 0.860 |
| **pv30: fx1 + maintenance ops worth <= 30 coins are priority 2 (after 15h only when nothing better)** | **+764 (+89 .. +1,450), 8/4** | **0.885 / 0.875 / 0.862** |
| pv60: same with 60 | -489 (-2,109 .. +1,095), 6/6 | 0.882 / 0.875 / 0.858 |
| nd: no mid-day delivery trips unless cash binds | -8,171 (-11,751 .. -5,132), 0/12 | 0.887 / 0.880 / 0.861 |
nd shows how much same-day selling is worth under the sem sell module (G1 sells on the leader's quota and does not
see it). pv30 goes to the full panel (pfpv30); helper split (hs1: a unit left free joins a held animal tile and takes
its last collect / harvest / care) on smoke + G1 (pvs10 / g1i).
| **hs1: fx1 + helper split (animal tiles)** | **+1,754 (+410 .. +3,667), 10/2; vs fx1 +1,531 (+273 .. +3,472)** | **0.884 / 0.876 / 0.864** |
hs1 adds ~31 helper steps per G1 game (the free unit walks to a held animal tile with >= 2 open ops and does its last
collect / harvest / care while the owner does the feed): the tail ops the owner ran out of hours for. Full panel
queued (pfhs1); hp = hs1 + pv30 on smoke + G1 (pvs11 / g1j).
| hp: hs1 + pv30 | +945 (-153 .. +2,316), 7/5; vs hs1 -810 (-1,758 .. +78), 3/9 | 0.884 / 0.874 / 0.863 |
**Full panel pv30 (Kaggle pfpv30, 185 p2750 worlds): +382 vs current (95% CI +61 .. +702), better in 105/185;
-16,800 vs y3 (current -17,182), W-L 15-170 (12-173).** Egg 144 (141), wheat 333 (332), revenue 115.1k (114.7k).
| hs2: hs1 + helper also on strawberry / tomato tiles | identical to hs1 (12/12); crop helper fires ~1 step a game (G1 helper steps 32.3 vs 31.5) | 0.884 / 0.876 / 0.864 |
**Full panel hs1 (Kaggle pfhs1): +202 vs current (95% CI -170 .. +571), better in 106/185; vs pv30 -180 (-584 .. +223);
-16,980 vs y3, W-L 13-172.** Its +1,754 smoke gain did not hold. Re-traced (trh, identical to hs1 12/12): dropped
maintenance value 15.3k/game vs 14.9k without it (stale-delivery drops 0.66k -> 0.01k, but "no idle unit" drops rose
2.5k -> 3.8k): the helper steps do not reduce what is dropped.
**Deploy default now pv30** (`agents/mgt_lead_deploy.py` executor CFG: p1_min_value 30, release_stale_d True; chosen on
full-panel evidence over hs1). `agents/mgt_lead.py` keeps 0 / False (leader-plan agent not measured with it); the
executor code is otherwise identical in both files (differences: these two defaults, sell_source, the SEM_MARKET block).
Deploy vs y3 on the full panel: melons x3 -17,182 -> pv30 -16,800.
**Conclusion of the idle-pass trace:** the dispatcher does connect free hands to open jobs; idle hands and dropped
jobs are on different days or in the last hours when every remaining job is already held by a unit and out of the
idle unit's reach. Dropped maintenance (~15k/game of module value) is a capacity-and-order effect of saturated days
9-27 (walking = 46% of unit time), not a matching defect: a 13th hand, zones, helper splits and deferring low-value work
recover at most ~0.4k/game. Rejected this round: c27 / c27f (later wheat/carrot cutoffs), fill, h2, z2, z4, nd, pv60,
hs1, hs2, hp.
Check: the new default deploy (copy `mgt_lpv_dep6`, Kaggle pvs13) reproduces pv30 on the 12 smoke worlds 12/12.

## Where the 12% goes: work / output / cash ledger, leader vs our leader-plan agent (G1 worlds, 2026-09-25)
`scripts/lead_ledger.py`: the leader's OWN recorded actions (tape `actions`) and our `mgt_lead` (current defaults,
= Gcut) played through the same engine hooks in the same world (seed, forced shops, recorded opponent). The leader
replay reproduces the recorded cash 12/12; ours / leader = 0.881 (= G1). First pass (Kaggle ledg1), per game:
| per game | d0-5 lead / ours | d6-11 | d12-17 | d18-23 | d24-29 | all |
|---|---|---|---|---|---|---|
| unit-steps | 843 / 844 | 1,488 / 1,486 | 1,693 / 1,706 | 1,707 / 1,720 | 1,634 / 1,664 | 7,366 / 7,420 |
| hires / wages | 31 / 31 | 59 / 59 | 68 / 68 | 69 / 69 | 66 / 67 | 293 / 294; 6,153 / 6,265 |
| moves | 375 / 313 | 718 / 760 | 657 / 809 | 657 / 799 | 709 / 819 | 3,116 / 3,500 |
| maintenance ops (effective) | 166 / 164 | 527 / 408 | 900 / 707 | 890 / 728 | 776 / 623 | **3,259 / 2,630** |
| all effective actions | 248 / 247 | 732 / 613 | 1,026 / 877 | 1,040 / 907 | 907 / 777 | 3,953 / 3,421 |
| idle (PASS) + no-effect | 221 / 284 | 39 / 113 | 10 / 19 | 10 / 14 | 19 / 68 | 297 / 499 |
| moves per maintenance op | 2.26 / 1.91 | 1.36 / 1.86 | **0.73 / 1.14** | **0.74 / 1.10** | 0.91 / 1.31 | 0.96 / 1.33 |
| shed arrivals per unit-day | 0.60 / 0.56 | 0.64 / 0.99 | **0.13 / 0.37** | **0.11 / 0.35** | 0.41 / 0.55 | 0.34 / 0.55 |
| pickups (items per pickup) | 20 / 23 (2.1 / 1.6) | 57 / 70 (2.6 / 1.7) | 42 / 77 (3.3 / 2.5) | 38 / 71 (2.6 / 2.7) | 25 / 66 (2.4 / 2.5) | 184 / 307 (2.7 / 2.3) |
| PLACE (mostly product deposits at the shed) | 23 / 12 | 49 / 40 | 6 / 23 | 4 / 21 | 6 / 27 | 88 / 123 |
| WATER / FERTILIZE / HARVEST | | | | | | 1,254 / 953; 207 / 127; 578 / 480 |
| FEED / CARE / COLLECT / PLANT | | | | | | 379 / 354; 375 / 323; 466 / 394; 295 / 231 |
**Finding (up front): the leader does MORE maintenance than we do (+24% effective maintenance ops, +31% waters, +63%
fertilizes, +20% harvests), with 11% FEWER moves, fewer idle steps, the same unit-steps and the same wages.** (a)
"thinner maintenance" is false; (c) "more unit-steps" is false (hire hours ~0.3 both). (b) holds: on saturated days
12-23 the leader needs 0.73 moves per maintenance op, we need 1.12 (+53%). Most of our extra walking is shed trips: we
arrive at the shed 3x as often on days 12-23 (0.36 vs 0.12 per unit-day), with 1.8x the pickups and 4-5x the
product deposits (PLACE); we pick up 709 items a game vs 490 while feeding and fertilizing less, so ~220 picked items a
game are not used. Per tile-day the leader waters wheat 0.98 vs 0.90, fertilizes wheat 0.18 vs 0.11, waters
strawberries 0.73 vs 0.53; we feed / care / harvest cows and sheep MORE late (days 18-29), and the leader lets more
animals go (cows 1.5 vs 0.7, geese 2.1 vs 0.5, sheep 5.3 vs 3.5 per game).
Output per game (harvested): wheat 681 / 495, carrot 204 / 126, egg 263 / 196, strawberry 208 / 159, tomato 105 / 69,
melon 60 / 58; milk 169 / 183 and wool 121 / 127 are higher for us. Plantings: wheat 171 / 135, carrot 70 / 50 (our
late wheat / carrot events are cut by plant_cutoff and not all executed).
Cash decomposition of the gap (13,450 a game, 100% explained): revenue +17,222 (volume +23.4k: wheat +8.5k, strawberry
+7.0k, carrot +3.6k, egg +3.3k, tomato +2.8k, melon +0.5k, milk -1.6k, wool -0.7k; price -6.2k: we sell fewer units at
higher prices), spend -3,884 in our favour (wheat bought 3.2k vs 6.2k, seeds -1.2k, animals +0.4k), wages +112.
So the 12% is output volume of crops and eggs, lost because we perform 24% fewer maintenance ops with the same
unit-steps; the unit-steps go into walking, mostly extra shed trips. Placement / distance metrics: ledg2 running.
Placement and distance (Kaggle ledg2, same 12 worlds, per game):
| | d0-5 | d6-11 | d12-17 | d18-23 | d24-29 | all |
|---|---|---|---|---|---|---|
| our occupied tile-days on the leader's tile with the same asset that day | 92.4% | 97.6% | 90.8% | 84.1% | 73.4% | 86.3% |
| our plantings on a tile the leader planted with that crop (<= 3 days before) | 100% | 94.6% | 88.9% | 81.8% | 85.8% | 89.4% |
| mean shed distance of occupied tiles, leader / ours | 3.99 / 3.95 | 3.95 / 3.95 | 3.86 / 3.89 | 3.86 / 3.80 | 3.74 / 3.64 | 3.85 / 3.82 |
| mean shed distance of the tiles operated on | 3.65 / 3.65 | 3.50 / 3.32 | 3.60 / 3.45 | 3.74 / 3.41 | 3.74 / 3.43 | 3.66 / 3.43 |
| mean distance between a unit's consecutive tile ops | 0.76 / 0.90 | 0.76 / 1.09 | 0.56 / 0.79 | 0.56 / 0.76 | 0.61 / 0.84 | 0.61 / 0.85 |
| moves = between-op walking + other (shed detours, walk out) | 375 = 118+257 / 313 = 136+177 | 718 = 390+328 / 760 = 412+348 | 657 = 461+196 / 809 = 495+314 | 657 = 476+182 / 799 = 503+296 | 709 = 438+271 / 819 = 452+367 | 3,116 = 1,882+1,234 / 3,500 = 1,998+1,502 |
The layout is the same (planner remaps 43.6 plant events a game, but 86% of our tile-days sit on the leader's tile and
the occupied tiles are equally far from the shed); we even operate on tiles nearer the shed (3.43 vs 3.66: far jobs are
the ones we drop). Per maintenance op on days 12-17 the leader walks 0.51 between ops + 0.22 other, we walk 0.70 +
0.44: our extra walking is half route order (consecutive ops 39% farther apart) and half shed detours (28 vs 10 shed
arrivals a game in days 12-17).
nd (no mid-day delivery trips) traced before building on it: on the 12 smoke worlds nd - fx1 = margin -8,395 but own
cash only -1,537; the rival's cash rises +6,858 (the frozen rival's recorded sales meet higher prices when our products
reach the market later). Own loss: strawberry -937, tomato -644, melon -401, wheat -401 revenue; milk +655, egg +317.
Paired one-world trace (midnight overflow, carried inventory, sale timing, failed buys) and item flows in progress.
**nd traced (Kaggle wtr1, `scripts/lead_world_trace.py`, two paired smoke worlds, nd vs fx1, reproduce the panel to
the dollar):** first divergence day 8 hour 11-12 (a hand collects fertilizer instead of walking to deliver).
| world | margin | own cash | rival cash | items lost to the shed cap at midnight (fx1 / nd) | units carried at midnight, days 12-27 (fx1 / nd, mean) |
|---|---|---|---|---|---|
| 111416249 | -23,399 | -10,180 | +13,219 | 29 / **175** (wheat 72, tomato 41, milk 24, strawberry 16) | 85 / 102 |
| 111688786 | -7,446 | -1,798 | +5,648 | 11 / **118** (wheat 77, strawberry 14, wool 7) | |
Two mechanisms, both real: (1) without mid-day deposits every carried product lands in the shed at the midnight dump
and the 100-item shed cap discards the overflow (5-15x more lost items); (2) our products reach the market a day later
and the frozen rival's recorded sales meet the higher prices (rival strawberry 139 vs 123 a unit, tomato 82 vs 78,
milk 223 vs 219); the rival's gain is larger than our own loss. So mid-day delivery is not waste: it keeps the shed
under its cap and sells ahead of the rival (how the leader avoids the cap with few deposits is not measured here).
The shed-trip fix must keep deliveries and target the other half of the extra walking (pickups, route order).
Item flows (Kaggle ledg4, same 12 G1 worlds, per game, leader / ours):
| | leader | ours |
|---|---|---|
| items picked up at the shed: wheat / fertilizer / animals | 442 / **24** / 24 | 473 / **196** / 40 |
| fertilizer collected from animals / applied (FERTILIZE) | 466 / **207** | 394 / **127** |
| items deposited at the shed (PLACE/DROP): fertilizer / wheat / egg / milk / wool / strawberry | 86 / 96 / 55 / 112 / 79 / 40 | 124 / 33 / 33 / 101 / 90 / 47 |
| deposit visits | 134 | 179 |
**The ~220 unused picked items are fertilizer.** The leader applies the fertilizer its units collect from animals in
the field (24 fertilizer picked at the shed for 207 applications). We route it through the shed: units deliver
collected fertilizer (124 deposited; `deliverable()` counts fertilizer unless the shed is short, and it counts toward
the >= 10-unit delivery trigger), then other units walk back to pick fertilizer up (196) and apply less (127). The
leader also delivers mid-day (134 deposit visits, mostly DROP), so "no deliveries" is not what it does.
Midnight shed cap (Kaggle ledg5 = the 12 G1 worlds for three sides; wtr2 = the 12 smoke worlds for the current deploy):
| per game | items discarded by the 100 cap at midnight | shed before dump / carried / shed after (days 12-28) | units sold a day (days 12-28) |
|---|---|---|---|
| leader (G1 worlds) | 9.1 (wheat 3.3, carrot 2.5, strawberry 1.2) | 6 / 82 / 87 | 85 |
| our leader-plan agent (G1) | 34.8 (wheat 16.1, egg 5.2, tomato 4.3, carrot 3.3, fertilizer 3.1) | 12 / 78 / 88 | 60 |
| current deploy (G1 worlds; reproduces its E2 cell, 0.885) | 41.8 (wheat 28.2, strawberry 3.3, egg 3.1) | 12 / 79 / 89 | 60 |
| current deploy (smoke worlds; reproduces pv30 12/12) | 21.8 (wheat 12.8, egg 2.2, strawberry 1.8) = ~1.2k coins at our own prices | | |
How the leader stays under the cap: it sells its stock every day (its shed holds 6 items before the midnight dump,
85 units sold a day); its units carry ~82 items at midnight and the dump fills the shed to ~87, which it sells next
day. We carry the same amount but keep 12 in the shed and sell 60 a day, so the dump pushes us to 88-95 and wheat
spills. Cap losses are real but ~1.2-2k a game; the fertilizer round trip is the larger walking defect.
**Build step (the biggest bucket: maintenance ops lost to walking, of which the fertilizer shed round trip is the
identifiable defect): `fert_hold`.** 1 = collected fertilizer is not delivered while fertilize jobs remain today (units
carry it to the jobs; the executor's cost already skips the shed detour when the item is carried); 2 = never
delivered mid-day. Deploy variants ff1 / ff2 on smoke (pvs14) and G1 (g1l, deploy E2 cells + leader-plan G cells).
| variant | smoke vs current (pv30) (95% CI), better | G1 deploy / leader-plan |
|---|---|---|
| **ff1: fertilizer kept on the unit while fertilize jobs remain** | **+792 (+106 .. +1,775), 8/12** | 0.881 / 0.873 / 0.865 (pv30 0.885 / 0.875 / 0.862); leader-plan 0.884 / 0.875 / 0.851 (0.881 / 0.871 / 0.853) |
| ff2: fertilizer never delivered mid-day | -10,154 (-12,787 .. -7,293), 1/12 | 0.886 / 0.859 / 0.867; leader-plan 0.838 / 0.825 / 0.831 |
ff1 goes to the full panel (smoke CI excludes zero; pfff1, 2 shards). G1 is neutral within noise both ways.
ff2's out-of-proportion loss, cheap split (no trace needed): smoke -10,154 = own -3,594 (well under the ~11.5k of
fertilizer revenue; spread over egg -1.0k, wheat -0.8k, wool -0.7k, tomato -0.6k, fertilizer -0.6k) + rival +6,560
(milk +2.7k, strawberry +1.8k, wool +1.0k). Fertilizer revenue on days 0-9 falls 4.6k -> 3.1k. G1 leader-plan (Gff2):
own -3,587 a game, opponent +5,085; in the worst world (112715010, -20.6k) cash on days 3 / 6 / 9 is 27 / 67 / 314
against 431 / 1,068 / 1,611, and idle passes rise at every hour band (h06 10 -> 41, h12 117 -> 239, h18 370 -> 469)
with fewer actions of every kind. Mechanism: fertilizer is the opening's cash flow (sold from day 2); never
delivering it mid-day starves the opening of cash, purchases stall and units idle; later, with fertilizer excluded
from the delivery trigger, other products ride to midnight as in nd (rival gains, cap). ff1 does not hit this
(no fertilize jobs in the opening, so fertilizer is still delivered there): G1 leader-plan own +363, with +4.5
fertilizes, +8.8 collects, +7.6 harvests, +6.8 feeds and -20 shed pick/place/drop actions a game.
**Full panel ff1 (Kaggle pfff1, 185 p2750 worlds): +462 vs pv30 (95% CI +67 .. +888), better 89 / worse 85 / same 11;
-16,338 vs y3 (pv30 -16,800), W-L 16-169 (15-170).** Sold units: egg 149 (144), strawberry 168 (166), fertilizer 236
(234), wheat 325 (333); revenue 115.4k (115.1k). **Deploy default now fert_hold 1** (`agents/mgt_lead_deploy.py`
executor CFG; mgt_lead.py keeps 0, leader-plan G1 neutral 0.884 vs 0.881). Deploy vs y3: pv30 -16,800 -> ff1 -16,338.
Round summary: the 12% (13.45k a game) is output volume (crops and eggs), because with the same unit-steps and wages we
perform 24% fewer maintenance ops than the leader; the unit-steps go into walking (1.14 vs 0.73 moves per maintenance
op on days 12-17): half from route order (consecutive ops 0.79 vs 0.56 tiles apart), half shed detours, of which the
identifiable defect was the fertilizer round trip (196 fertilizer picked at the shed vs the leader's 24). The layout
is the same (86% of tile-days on the leader's tiles, same shed distance). ff1 removes part of the round trip
(+4.5 fertilizes a game in G1); the route-order half is untouched.
Check: the new default deploy (fert_hold 1; copy `mgt_lpv_dep7`, Kaggle pvs15) reproduces ff1 on the 12 smoke worlds 12/12.

## Midnight shed cap: cap-aware sell guard (2026-09-25)
Why the old guard misses: it fires only at hour >= 20 when shed + carried > 95, sells down to 90, and ignores what the
units still harvest in the last hours (our shed + carried averages 12 + 79 = 91 at midnight, so it seldom fires, and
the late harvest then spills). The deploy keeps all feed wheat to the end (`wheat_keep_days` 99), so the shed holds
wheat the sell rule never releases; the sem wheat buy-ahead is off (`SMK_WHEAT.on` False), so it is not the filler.
`cap_guard` 1 (executor option, default 0 in both files): from `cap_hour` (16) projected midnight load = shed + carried
+ `cap_rate` x hours left - this step's sells; above 100 - `cap_margin` the excess is sold from the shed, wheat above
the feed reserve first, then other products cheapest first. cg1 = rate 2.5 / margin 3, cg2 = rate 4 / margin 5.
Smoke with discards per game (Kaggle wtr3, lead_world_trace: current default vs cg1 vs cg2) and G1 (g1m) running.
| variant | smoke vs current (ff1) (95% CI), better/worse | discards / game (current 25.8) | G1 deploy (ff1 0.881 / 0.873 / 0.865) |
|---|---|---|---|
| cg1: shed guard, rate 2.5, margin 3 | -269 (-984 .. +413), 6/6 | 27.5 | 0.879 / 0.871 / 0.862 (leader-plan 0.877 vs 0.881) |
| cg2: shed guard, rate 4, margin 5 | -374 (-1,016 .. +335), 3/9 | 29.8 | 0.884 / 0.875 / 0.865 |
**Finding: a shed-side guard cannot work, the overflowing stock is in the units' hands.** On the 32 overflow nights
(of 348) of the current default the shed holds ~3 items before the dump while the units carry ~106 (wheat 55,
fertilizer 20, egg 10, strawberry 8, milk 6, tomato 4); on 26 of them the carried items alone exceed 100. The units
carry the morning's feed wheat plus the day's harvested wheat (wheat is never deliverable) and, with fert_hold 1, the
fertilizer they hold for fertilize jobs (ff1 raised discards 21.8 -> 25.8 a game). The deploy's wheat keep is held in
hands, not in the shed. So the cap fix must bring the excess to the shed before midnight and sell it: `cap_deliver`
1 (with cap_guard): on a projected overflow from cap_hour, the units carrying the most products (wheat and fertilizer
included) deliver them, nearest first, until the projection fits; the guard then sells above the feed reserve.
cg3 = from hour 16, cg4 = from hour 19; smoke (wtr4) and G1 (g1n) running.
| cg3: cap delivery + guard from hour 16 | -2,092 (-3,464 .. -808), 2/10; own -1,441, rival +651 | **0.3** | 0.870 / 0.862 / 0.852 |
| cg4: cap delivery + guard from hour 19 | -1,153 (-2,726 .. +173), 4/8; own -708, rival +445 | 14.4 | 0.888 / 0.879 / 0.867 |
**Cap step rejected (no variant passes the full-panel rule).** The cap losses are real (current default 25.8 items a
game on smoke, ~1.2k coins) and cap delivery removes them (cg3: 0.3 a game), but the evening delivery trips cost more
output than they save: cg3 sells 7.4 fewer eggs, 5.0 fewer strawberries, 4.4 fewer tomatoes and 27 fewer wheat a game
(own cash -1,441), and G1 falls to 0.870. Starting at hour 19 (cg4) halves the discards and halves the cost, still
negative on smoke. The cheaper lever is upstream: less stock in hands at midnight (morning feed-wheat pickups sized to
the day's feeding; the wheat keep), not evening trips. cap_guard / cap_deliver stay in the executor, default off.
