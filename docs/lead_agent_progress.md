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
