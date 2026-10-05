# Kaggriculture

Workspace for the [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture) Kaggle simulation competition.

Build an autonomous agent that runs a virtual farm for a 30-day season (one turn = one in-game hour):
plant and harvest crops, care for animals, hire labor, buy land, and trade on a shared market where
prices react to supply and demand. Agents compete head-to-head on a live leaderboard by profit.

- Prize pool: $50,000 (top 10 x $5,000)
- Entry deadline: 2026-09-23

## Fresh research (2026-09-15)

**d9c4o full-game panel, 43 worlds (2026-09-30):** the day-9 handover candidate (DSM-new cassette days 6-11, Q4 on
day 10) played whole games in all 43 DSM-new worlds (held-out folds) against the frozen recorded opponents: margin -4.1k
vs the live build (SE 1.0k, better 9/43); the 4th quadrant costs 9.1k more spend for 6.7k more revenue. Against
opponents rated 2650+ both lose (candidate 1/10, live 2/10 wins; DSM 10/10). Live vs DSM: -16.4k margin, of which
+12.8k is the opponent earning more (prices) and -3.6k our own cash. Executor switches on the 10 strongest worlds
(window-water value, idle filler, forced wheat fertilizing) leave 4Q level with live at best; the 4Q wheat gap is
fertilizer collection (d9c4 376 vs DSM 486 a world, same crew), not watering. See `docs/dsm4q_day9_handover_20260930.md`.

**Full stack (2026-09-30):** DSM prefix (days 0-10) -> the semantic planner + tiler (candidate d9c4o) -> the
time-based path-partition executor (`scripts/fullstack_smoke_20260930.py`). Two worlds: -19.4k / -21.7k vs DSM's own
continuation, 2.4-4.6k behind the same executor on DSM's hindsight plan; season cassettes with other leaders' figures
lose to the existing policy. Largest remaining item: wheat (-9.4k). With the candidate's own days 0-10 in front
(4 quadrants on time) the stack ends -19.3k / -19.8k, while the candidate alone (same day-11 state, its own tier executor
after day 11) ends -1.1k / -8.9k. That executor gap was measured with this thread's older TPP configuration (arm i); the
other thread's current TPP already fixes the strawberry dig bug found here - re-measure before quoting. See
`docs/time_path_partition_20260930.md`.

**Latest public agents vs the opening (2026-09-30):** seven recent public agents (one lineage: the V56-descended router
with a shop-keyed route table) smoked to day 11 in DSM-new world 115518441: all own 2 quadrants at the day-11 dawn
(2nd on day 6, none after) with ~$16.8k banked, vs DSM's 4 (days 6 / 8 / 10). None fixes the opening. See
`docs/public_agents_opening_20260930.md`.

**Post-day-11 solver: time-based path partition (2026-09-30):** user design - per tile mandatory / non-mandatory /
slack hours, one path-like route per worker (mandatory <= day, + non-mandatory <= day, + slack >= day + 1 h),
bring-backers planned first, cut slack then non-mandatory by value, fewest tiles walked, useless jobs never listed.
Offline on DSM's own farms (774 game-days, DSM's plan and crew): every mandatory and non-mandatory job fits, 12-19%
fewer tiles walked than DSM, 1-1.8 fewer workers needed; DSM itself drops ~75% of alternate-day waters and keeps ~99% of
deadline-tonight work. See `docs/time_path_partition_20260930.md`, viewer viz/path_partition_115518441_d15.html.

**Us vs the new DSM on days 9-10 (2026-09-30):** after an exact day-8 handover in 43 recorded DSM-new games, the live
build's day-11 board is 37.6 tiles off DSM's (it never buys Q4). A DSM-new cassette (targets by revealed shop types)
buys Q4 on DSM's schedule (day 10, hour 10) and halves the composition gap (28.7 -> 16-18 tiles), but plantings on
new land and on day 9 are still dropped: tier routes skipped still-locked Q4 stops (fixed by `sd_tier_defer_locked`),
and day-9 cash runs out after a day-9 Q3 purchase. See [the report](docs/dsm4q_day9_handover_20260930.md).

**Live n18rc99s ladder losses (2026-09-30):** all 133 ladder games of 56676484 were replayed exactly (112 W / 21 L;
2,400-2,600 opponents 11-8). Losses come from strawberries -4.2k, wheat -4.2k and wool -2.8k a game, while our egg,
tomato and milk edges shrink against strong teams. Clearest marker: the third quadrant bought on day 9-10 instead of
day 8 (cash short after contested day 6-8 sales). Those 25 games lost 16; the 108 day-8 games lost 5. The time bank
is not the cause, but ladder games use ~30 s of it. See [the loss report](docs/ladder_losses_n18rc99s_20260930.md).

**Marked tape revisions (2026-09-22):** a register now covers all 584 UMG tapes,
with 13 flagged for milk-to-wool review. The first revision changes four worker
commands on each of three active days in tape 109740300, shifting cow care to an
existing sheep. In its discovery replay: +314 own cash, +88 margin, +1 wool,
-3 milk and unchanged spending. Marked **diagnostic improvement**, with applicable
responsive-opponent validation outstanding. Three other-donor controls remain
identical; seven isolation/condition tests pass. See [the revision report](docs/tape_sequence_variants.md).

**Minimal m1 experiments (2026-09-22):** a six-line wool-forecast change has a small
positive confirmation result: +85 paired margin (95% seed-bootstrap CI +7..+214)
on 24 untouched seeds, both seats, against live V56. Seven games improve, 41 remain
identical, and wins stay at 32/48. On 198 available historical m1 games it gains +131
margin, flips two losses and loses no existing wins; recorded opponents cannot react.
Two separate purchase-gate edits changed no actions in their diagnostic/development
panels. The saved candidate is `agents/mgt_micro_wool_upturn.py`; m1 remains unchanged.
A -494 historical regression identifies a narrow next target: respecting planned
animal retirement and crop replacement. See [the experiment report](docs/mgt_m1_minimal_experiments.md).

**Continuation execution and recovery (2026-09-22):** retain `mgt_m1`. The new bounded
compiler exactly reproduces output and ending tiles in 8/12 native windows (previously
4/12), and ten runtime/engine/fault-injection tests pass. Three full-game development
variants all underperform m1: the best is 8–8 versus V56 against m1's 10–6, and the final
productive fallback is 4–12. Preserving assets without maintaining profitable
replacement cohorts can still cause large losses. See [implementation and results](docs/continuation_execution_and_recovery.md).

**Production-module integration (2026-09-21):** keep `mgt_m1`. Bounded leader-derived
carrot cycles now execute in the full farm using reserved native visits. Forced swaps
lose to the matched tape-holding control in every tested game: −465 margin/game on
the natural V48/V50 panel, −504 with shops held fixed, and −281 in 12 recorded ladder
worlds. The conservative value gate leaves the baseline unchanged. The executor is a
useful building block; this crop-selection policy is not an upgrade. See
[the integration report](docs/production_module_integration.md).

**V48 and pre-emption feasibility (2026-09-18):** V48 (`agents/v48_public.py`, fetched
from the public notebook) beats our current agent 0-0-32 by 1,753/game; no opening
variant helps (all 0-32). V48 already opens Nash-like and runs anti-clone pre-emption,
including a turn-1 attack on the budget slack of this lineage's openings. Mother-Goose's
intact recorded plan beats V48 30-0 by +12.2k. She is identifiable from her public farm
by step 25 with 0 false positives in 362 other seats; her board is forecastable from
shops to 17-27% error (bounded), and her sale hours are fixed. See
[the feasibility report](docs/preemption_feasibility.md).

**Tape repairs on the Mother-Goose base (2026-09-19/20):** current candidate `agents/mgt_t10.py` (= `mgt_t7` +
adoption of animals orphaned by a tape switch: +142 paired on natural seeds, 3 better / 0 worse; 54-10, +3,340 vs
V50). `agents/mgt_t7.py` = tape router (board term 1.0) + feed guard + demand-conditioned care top-up. Natural seeds 174000-174031, both seats, Kaggle loader:
**54-10 vs V50 (+3,199, CI +1,062..+5,292)** and **54-10 vs V48 (+4,735)**; the router alone is 40-24 (+1,758)
and the repairs are +1,441 paired (+755..+2,256). In leave-one-out (her 40 recorded worlds, her tape removed)
28-12 vs V50, +3.0k paired over the router. The feed guard is the big one: her crew feeds from the shed's own
wheat stock, a borrowed tape runs a few wheat short and her animals starve (one world -51k -> +16k for 11
wheat). Her care rate is demand-conditioned (46% of sheep-days with no Yarn Store, 75-90% with one), so a hand
of ours tops up what a low-demand tape skips. Her Yarn rule for adding sheep is gated off by an engine-curve
glut model: V50 runs sheep too and the wool market saturates. See [the tape base](docs/mg_tape_base.md).

**Mother-Goose's plan as the base (2026-09-19):** public V50 now beats V48 63-1 and our V45-based
candidates 57-7, and those candidates sit at ~2200 on the ladder, so the base changed: a router over 584 of
her recorded deterministic games on the public chassis core, with the equilibrium opening. Her native plan
beats live V50 37-3 by +8.5k; the router is level with V50 on natural seeds (+31) and +5.1k over our old
benchmark; routing costs ~9.8k, 40% of it one behaviour (adding sheep when Yarn Stores appear late). Her new
submissions are closed-loop and do not replay. See [the tape base](docs/mg_tape_base.md).

**Mother-Goose-based build, paused (2026-09-18):** crop swaps run on the V45 tape's own visits. The
crew's visit calendar is predicted exactly from the tape, and a swapped crop is serviced by rewriting
only that tile's actions. Result: 390/390 swapped tomatoes fully harvested with zero losses; the
benchmark's own day-18 tomato programme keeps working. A bidirectional strawberry rule, derived from an
engine-economics market model rather than her tables, gives +571 own cash (CI +72 to +1,133) and +231
margin (not significant) against the benchmark in her 30 worlds. With model-chosen second-wave melons
it is +679 and +309. The build was paused when she left the top: she wasn't beaten, she retired her
3185-rated submission herself. See [the build notes](docs/mg_build.md).

**Wheat flip derivation and opening × flip cross-test (2026-09-18):** the closed form
for the flip game matches the engine exactly (except near 100 units, where cash runs out).
A symmetric flip nets exactly 0 for every q, because price steps fall only on odd shortages.
As a pure round trip the equilibrium is 0 (or 1); "5" is right only as the feed purchase you
keep. The flip does **not** gate the Mother-Goose-style opening. Her plan with a 70-flip ends
day 0 on the same 22 coins as with no flip, keeps its board intact all season in 27/30 worlds,
and beats the benchmark 30-0 by +12.7k. What breaks it is her own 13/5/13 turn-0 orders: 5 coins
left, 30/30 day-1 hire failures, −18.0k. Spoiling is a cliff between our flip 8 (she keeps 7
coins and wins +12.6k) and flip 10 (5 coins, she loses −17.9k). See
[the derivation](docs/wheat_flip_derivation.md).

**Opening wheat flip, head to head (2026-09-18):** the certified equilibrium is *buy 5
feed wheat and keep them*; our live agent still flips 70. In isolation every flip nets
zero, but smaller flips beat larger ones: against our frozen benchmark, flip 35 wins
32-0 by +1,375 (CI +1,367 to +1,387), flip 5 32-0 by +234, Nash 5 32-0 by +1. Flips of
35+ push Mother-Goose's budget-exact opening past its ~29-coin slack and break her
recorded tape (30/30); smaller ones don't, and she then wins by ~12.6k. See
[the flip study](docs/wheat_flip_head_to_head.md).

**Mother-Goose's recorded moves vs our frozen agent (2026-09-18):** replaying its
actual recorded sequence (deterministic, so a real artefact of its policy) against our
live benchmark: 30-0, +12,581 (CI +10,299 to +15,069), +15,049 net of the frozen-tape
handicap. The tape needs a 40-coin opening cushion (removed from its score) because its
budget-exact opening otherwise loses a hire on day 1 to price drift from our wheat round
trip; with it, its board is byte-identical to its original game all season in 26/30.
Largest significant lines: tomato +4.6k, egg +2.3k; labour +0.6k, layout negative. See
[the tape test](docs/tape_vs_bench.md). The segment report's commonality re-check shows
the leaders' opening, land timing, melon cash-out and liquidation are our own tape.

**Efficiency decomposition (2026-09-18):** Mother-Goose's edge is not layout or
manpower — its productive tile-days equal ours (1,653 vs 1,647-1,676) and labour
saves only 0.6-1.8k/game. Most of the earlier-reported gap is the market our agent
plays in: realised price explains +11.6-19.2k across pools but +54 within its own
games, and our benchmark placed in its 30 games ends +5,141 ahead (CI −1,234 to
+11,704; opponent cannot react). Its head-to-head edge is ~3.5k, from melon and
tomato. The 9-11k strawberry gap in the segment report was a self-play market
artifact. See [the decomposition](docs/efficiency_decomposition.md) and
[the self-play imitation results](docs/leaderlike.md).

**Top-two segment and adaptation study (2026-09-17):** 52 public episodes of
rank 1 **Majkel1337** (56216119, 3185.5) and rank 2 **Unknown Mother-Goose**
(56266758, 3129.5), exactly replayed, analysed per 3-day shop segment. Both
leaders condition crop quantity on shop demand — a newly revealed shop raises
planting of the crop it wants within two segments (carrot +4.6/+3.3 plants,
tomato +0.9/+1.6, strawberry +3.2/+3.3, all p<0.03; wheat unaffected), while our
tape plants literal constants. Neither shows opponent-conditioned production:
Mother-Goose plays byte-identical action streams for 8-12 days against different
opponents and prices, and Majkel1337 is nondeterministic (15/210 pairs diverge
with identical observation histories), so its conditioning cannot be identified.
Liquidation timing, PASS counts and wheat trading are not where they gain. See
[the segment report](docs/leader_segments.md); no agent was changed.

**Leader-inspired hybrid tests (2026-09-16):** Earlier strawberries, a changed
herd, and their combination all lost margin in the eight-first-shop screen.
The best variant lost **2,009 mean margin** on fresh confirmation, winning
29/48 versus the baseline's 46/48. These are selective transfers onto V45's
layout, not the leader's complete opening. See [results and diagnosis](docs/leader_hybrids.md).

**Packaging correction:** The last-callable loader bypassed the forecast wrapper
in the previously submitted event candidate. A corrected export,
[`v45_event_entrypoint_fixed.py`](agents/v45_event_entrypoint_fixed.py), matches
all 719 research-entry actions in a full game. It has **not** been resubmitted.
Original sources and the uploaded archive are preserved; the forecast component
of submission 56280048 should not be assumed active.

**Rank-1 opening audit (2026-09-16):** Six public Majkel1337 replays show a
different capital schedule: an extra first-day sheep, staged melon planting,
and earlier wheat-to-strawberry conversion. All replay states were reproduced;
fixed-opponent-stream V45 controls are diagnostic, not live strength tests.
See [opening comparison and testable mechanisms](docs/leader_opening.md).

**Latest submitted candidate (2026-09-16):**
[`V45 event forecast`](submissions/2026-09-16-v45_event/main.py), submission
**56280048**, initially pending. Submitted at explicit user request despite the
offline consistency gate; the retained local baseline remains V45 + sale ordering.
Exact file, hash and upload record: [`submission archive`](submissions/2026-09-16-v45_event/NOTES.txt).

**Integrated working agents (2026-09-16):**
[`V45 + our sale ranking`](agents/v45_our_selected.py) and
[`V44 + our sale ranking`](agents/v44_our_selected.py). Our available-stock,
price-impact sale ranking passed independent confirmation on both bases:
**+137 average winning margin**, **+61 cash**, and positive averages on all
eight new seeds against three modern rivals. The V45 hybrid scored 48/0/0;
the V44 hybrid scored 32/0/16 on its panel. Aggressive milk/wool liquidation
lost about 1,500 margin in screening and was excluded. See the
[transfer study](docs/modern_sales_transfer.md). Neither hybrid has been submitted.

**Delivery-price input experiment (2026-09-16):** A standalone V45 hybrid
candidate values fertilizer-worker plans under sampled future shops and public
market-flow forecasts. Independent confirmation changed average margin by only
**+0.9** and cash by **+19.4**, with positive margin on **3/8 seeds**. It failed
the consistency gate; the existing V45 sale-ranking hybrid remains selected.
See the [experiment and diagnostic control](docs/delivery_inputs.md).

**Event-based forecast research (2026-09-16):** A model using both farms'
visible production, recent harvests, selling patterns and our known stock passed
an independent forecast gate. Wheat/carrot price error fell to **0.320**, versus
**0.723** for market-flow extrapolation and **0.576** for a calibrated model
without production/stock features. It improved all eight held-out seeds.
See the [forecast validation](docs/event_prices.md) and the separate
[V45 investment-policy test](docs/event_inputs.md). Forecast accuracy alone
does not establish a competitive improvement.
The isolated policy test gained **+11.7 margin / +16.6 cash**, with both agents
winning 48/48 games. Three seed averages improved and five were unchanged;
it missed the frozen six-positive-seeds gate. Keep the event forecast for
research and retain the existing V45 sale-ranking hybrid competitively.

**Retained modern baseline (2026-09-16):**
[`agents/modern_router_selected.py`](agents/modern_router_selected.py), the frozen
public V45 with economic feeding and crop-input planning. A new joint input-tour
candidate failed independent confirmation: +42 average cash but -21 winning
margin, with positive averages on only three of eight seeds. The unchanged
baseline remains selected locally. It scored 14/0/2 versus V44, 14/0/2 versus
Farming V5, and 16/0/0 versus Two Coins on the confirmation panel.
See [implementation and evaluation](docs/modern_router.md). This has **not**
been submitted; the uploaded control below is preserved.

**Previous submitted control (2026-09-16):**
[`agents/market_impact_selected.py`](agents/market_impact_selected.py), a self-contained six-day router
with the milk/wool sales adapter and ordering based on current price impact and
available lot sizes. It preserves the previous opening through turn 215.
Independent confirmation on eight fresh seeds, both seats and five opponent
behaviors: **80 wins, 0 ties, 0 losses** versus 64 wins, 16 ties and
0 losses for fixed priority on the same panel. Mean cash improved by
702; mean match margin improved by 1,304.
The [adaptive market-order study](docs/adaptive_market_order.md) records 600
evaluation games, all eight first shops, opponent-forecast controls, and a separate
availability-only control for stale sale orders. The price-impact rule beat the
forecast-based alternatives in discovery; opponent forecasts are not used in the
selected policy. These are local results against a limited opponent panel, not
a leaderboard claim. Submitted to Kaggle on 2026-09-16 as **56273827**;
the initial status was pending evaluation. The exact uploaded file and receipt
are archived in [`submissions/2026-09-16-market_impact/`](submissions/2026-09-16-market_impact/).

**Benchmark refresh:** the [new public-router comparison](docs/router_refresh.md)
supersedes any broad competitive interpretation of the earlier local wins.
Across eight fresh seeds in both seats, the submitted agent beat its six-day
parent 15–1, but lost 0–16 each to V44, V45, Farming Score V5 and Two Coins.
The unchanged parent also lost all those games. The 192-game comparison and
12 fixed-stream live-replay controls point to an older base strategy and narrow
benchmark coverage as the main weaknesses. The uploaded agent remains a control;
the newer agents are downloaded and available for subsequent work.

The [new-router mechanism study](docs/router_mechanisms.md) adds 192 paired
games disabling V45's tomato expansion, advance-sale reservations, terminal
planner and opening wheat round trip. Most of its advantage over our agent
survives all four removals. Wheat economics and the remaining production and
execution layers are the next research priorities; sale-timing gains depend
strongly on the opponent. No new policy was promoted or submitted.

The [wheat economics study](docs/wheat_economy.md) then ran 241 games including
replay checks and follow-up diagnostics. Economic feeding added about 1,450
winning margin against each rival; additional wheat/carrot fertilizer planning
added 1,261–1,655. Shop-dependent routing helped winning margin, sometimes mainly
through the opponent's changed outcome. Wheat stock reconciled after every
turn. The report distinguishes gross trading volume from net wheat profitability
and identifies the small replenishment-trimming rule as a low priority.

A separate [direct test against the original public router](docs/original_router_test.md)
(`tschinkel_router_v31.py`) finished **48–0**: 32 natural-shop games across 16
fresh seeds and 16 games covering every first shop, always in both seats.
Average cash margin was +19,712 on natural shops and +21,178 on the shop controls.

The [demand-aware pasture study](docs/demand_investment.md) completed 256 games
comparing sheep, cow and skipping the last pasture purchase under matched shop
draws. A simple milk-shop rule showed gains but substantial losses on additional
trigger coverage; the current selected agent remains unchanged. The study records
why future demand, both farms' supply and winning margin must be valued together.

Previous candidates remain available:
[`agents/market_priority_selected.py`](agents/market_priority_selected.py)
([opponent-aware sales study](docs/opponent_sales.md)) and
[`agents/production_selected.py`](agents/production_selected.py)
([production study](docs/production_research.md)).

The [market forecast and sales-DP study](docs/market_forecasting.md) (2026-09-16)
adds public opponents, held-out price forecasting, and audited full-game tests
of sale timing. Its report distinguishes forecasting gains from final-profit gains.

The current work starts from first principles. See [the opening study](docs/opening_study.md)
for the mission split: opening moves, then midgame investment, then late-game liquidation.
`agents/opening_v1.py` is the new opening-only baseline; it is not a completed submission.
The study includes exact move logs, day-3/6/9 checkpoints, and comparisons against the public router.
Earlier agents and strategy notes remain historical experiments.

The [board-value study](docs/board_value.md) replaces cash-only opening rankings
with official-engine continuations to the end of the season. It compares shared
maintenance/replanting rules and each original policy, with exact cash accounting.

The [growth opening study](docs/growth_opening.md) uses that evaluator to select
`agents/opening_v2.py`: staged animal purchases, premium crops, and an affordable
second quadrant. It is an experimental opening baseline, with complete move
logs and comparisons against v1; the midgame controller remains provisional.

The [router handoff experiment](docs/router_handoff.md) compares switching v2 to
the public router at day 9 with replanting and complete-router self-play controls.

The [reactive copying experiment](docs/reactive_copy.md) tests copying the
opponent's visible farm investments with independent worker scheduling.

The [router-opening replanting comparison](docs/router_replant.md) completes the
opening/continuation matrix using the same generic replanting rule on both openings.

The [direct both-replant match](docs/both_replant.md) puts our opening and the
router opening in the same game, then switches BOTH farms to replanting at day 9.

The [systematic shop-grid search](docs/shop_grid_search.md) completed 544 games
across training, validation and test panels balanced over all eight first shops.
The 16-configuration grid and shop-dependent selector did not establish an
improvement over the public-router opening. Keep that router opening as the
reference baseline; `agents/opening_v3.py` preserves the experimental selector.

The [midgame research report](docs/midgame_research.md) covers the maintenance
audit, herd/staffing/fertilizer grid, refinements, natural-shop held-out tests,
and common-endgame sensitivity. No new controller earned promotion; keep the
full conditional public router. `agents/midgame_selected.py` is the verified
local entry point for that selection.

The [router routine extraction](docs/router_routines.md) reconstructs crop
cohorts and timed work orders. The [scheduler prototype report](docs/router_scheduler.md)
tests production preservation and recovery from displaced workers. This is an
experimental execution layer; the selected competitive baseline remains the router.

The [worker allocation study](docs/router_allocator.md) adds inventory-constrained
exchanges of remaining daily job sequences, with paired tests of normal play,
displaced workers and interchangeable workers placed on each other's routes.

The [completed scheduling research](docs/scheduling_complete.md) adds individual
watering/harvest repair and closes the plan with an audited multi-checkpoint
evaluation and a frozen baseline recommendation.

## Project files

| Path | Purpose |
|------|---------|
| `agents/` | Agent source. `agents/baseline.py` is the starting point; each new strategy gets its own file. |
| `scripts/` | Local runners: play episodes, agent-vs-agent matches, evaluate. |
| `notebooks/` | Exploration of episode data and market dynamics. |
| `data/episodes/` | Downloaded episode replays (git-ignored). |
| `submissions/` | Frozen copies of what was submitted, one folder per submission. |
| `docs/` | Rules notes, strategy ideas, environment observations. |

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Kaggle CLI needs an API token at `%USERPROFILE%\.kaggle\kaggle.json` (Kaggle > Settings > API > Create New Token).

## Useful datasets

- Kaggriculture Episodes Index: https://www.kaggle.com/datasets/kaggle/kaggriculture-episodes-index
- Community episode dump: https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes
