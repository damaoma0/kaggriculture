# Direct labor-scheduling self-play

Follow-up to [the labor-profit research](labour_profit_research.md), 2026-09-21.

The forecast-guided scheduler scores **40 wins, 0 ties and 0 losses** against the identical supplied plan without rescheduling, with **+146.15 mean head-to-head cash margin**. The labor-only scheduler scores **29 wins, 10 ties and 1 loss**, with **+130.85 mean margin**.

These are actual simultaneous matches with shared market impact, not separate replays against the original recorded opponent. Scheduling decisions use only the current observation and the player's supplied production/action plan. No candidate is accepted or rejected using the real future opponent actions or realized future state.

## Results

| Panel | Scheduler | W–T–L | Mean match margin | Paired-world 95% bootstrap |
|---|---|---:|---:|---:|
| ladder (12 worlds, 24 games) | Preserve sale times; minimize wages | 13–10–1 | +127.50 | +57.75 to +206.42 |
| ladder (12 worlds, 24 games) | Labor plus forecast sale timing | 24–0–0 | +154.92 | +76.58 to +245.42 |
| leaders (8 worlds, 16 games) | Preserve sale times; minimize wages | 16–0–0 | +135.88 | +86.12 to +183.00 |
| leaders (8 worlds, 16 games) | Labor plus forecast sale timing | 16–0–0 | +133.00 | +84.75 to +177.50 |
| all (20 worlds, 40 games) | Preserve sale times; minimize wages | 29–10–1 | +130.85 | +84.40 to +181.90 |
| all (20 worlds, 40 games) | Labor plus forecast sale timing | 40–0–0 | +146.15 | +96.85 to +204.80 |

The two seats of each world form one bootstrap cluster; they are not treated as independent worlds. These 20 plans/worlds were already used in the preceding research. The intervals describe this panel, not an unseen-world generalization test.

The single labor-only loss is episode 111240681 in seat 1: that seat loses by 459 in the unscheduled mirror control, and scheduling saves 327, narrowing the loss to 132. Its seat-swapped partner wins by 786. Thus the labor-only policy improves 15 paired worlds and ties five; it worsens none of the paired worlds.

## Where the gain comes from

Each world also runs the same unscheduled plan against itself. Comparing each treated player's cash with that control separates own profit from damage to the rival's sale prices.

| Scheduler | Own cash gain | Wages saved | Extra revenue | Other input saving | Rival cash change |
|---|---:|---:|---:|---:|---:|
| Preserve sale times; minimize wages | +130.85 | +130.85 | +0.00 | +0.00 | +0.00 |
| Labor plus forecast sale timing | +136.80 | +132.55 | +4.25 | +0.00 | -9.35 |

Means are per match. Head-to-head margin is the difference between the two players' final cash; own profit improvement is measured against that seat in the unscheduled control.

The sale-timing forecast is not uniformly better than labor-only scheduling. In episode 110003096 it gains 182 own cash versus 202 for labor-only, and its match margin falls from 202 to 173. The ability to hold goods preserves an option; a forecast can still choose the wrong sale time. The average benefit beyond wage-only is 5.95 own cash and 15.30 match margin on this panel.

## Production and correctness

- Preserve sale times; minimize wages: 0/40 games changed our harvested/collected quantities; 0/40 changed the rival's quantities. Our final farm/inventory changed in 0/40; the rival's changed in 0/40.
- Labor plus forecast sale timing: 0/40 games changed our harvested/collected quantities; 0/40 changed the rival's quantities. Our final farm/inventory changed in 0/40; the rival's changed in 0/40.

All 80 treated full seasons and 20 mirror controls reach DONE and reconcile final cash with the successful transaction ledger. An independent replay through Kaggle's normal framework checks every transition of 8 selected treated games (both selectors and seats, one world from each panel). Public farms, private inventories, market, town, time and final scores match. Every source file and archived executable schedule is hash-checked.

The information-isolation check uses a decision that actually changes the schedule. Altering the rival's private inventory and supplying bogus hidden-seed, future-shop and future-rival-action fields leaves that decision unchanged. Episode-file loading is disabled during the check.

## Exact protocol

1. Use the same 12 ladder-derived and 8 Mother-Goose-derived explicit plans as the prior study. Both contestants receive the source player's own plan, including its capped input and sale quantities. The original opposing action tape is never played in these matches.
2. Start both farms through the official engine with 3,000 cash, the recorded world seed, normal weeds and the recorded shop-opening history. Only the evaluator knows the future shop history. Run an unscheduled-versus-unscheduled mirror control.
3. For each selector, run a full game with the scheduler in seat 0 and another with it in seat 1. The other side executes the identical original plan. Future scheduled actions of the other side are not supplied to the planner, even though the experiment uses matching plans.
4. At each selected day boundary, provide the scheduler its current observation and the next 48 hours of its own plan. Optimize the first day's labor with the next day as a continuation check. Ladder plans use zero-based days 3,5,…,27; Mother-Goose plans use 4,6,…,26.
5. Project the physical engine with the rival taking PASS, unknown rival inventories empty, existing shops held constant, and no speculative new weeds. Require all planned input purchases, land purchases and hires to succeed in the baseline projection; otherwise retain the original schedule. This check uses predicted feasibility, not the actual future.
6. Generate the same bounded relocation, insertion, worker-removal and delivery candidates as the research prototype. Retain candidates preserving projected production, inventories and trade quantities. The wage selector preserves projected sale times; the forecast selector compares public-market scenarios using current shops and visible rival production. Do not use the realized-profit oracle.
7. Materialize all chosen physical and market actions and execute them in the real shared market. Record every resulting season, including losses and any production mismatch. There is no hindsight rollback or exclusion of bad outcomes.

The opponent here is a fixed-plan executor. This validates labor scheduling conditional on a supplied plan; it does not test an integrated, adaptive mgt_m1 production planner or a reacting rival policy.

## Search and runtime limits

- Preserve sale times; minimize wages changes 92 of 504 decision windows; 4 windows fall back because of projected input shortfalls. Maximum observed planning time is 3.04 seconds under this four-process local run.
- Labor plus forecast sale timing changes 118 of 504 decision windows; 4 windows fall back because of projected input shortfalls. Maximum observed planning time is 3.09 seconds under this four-process local run.

This Python research executor is not a competition-ready agent: the environment's default per-action limit is 1 second, and these matches precompute each selected window outside that limit. The algorithm still needs runtime work and integration before a live submission. It optimizes alternate days and a bounded candidate pool; neither minimum staffing nor global profit optimality is established.

A discarded engineering pilot (`selfplay_causal_pilot`) initialized projected observations incorrectly because Kaggle's Struct requires attribute assignment to synchronize attribute and dictionary values. It is not performance evidence. The fix and a projected-initial-state assertion precede the frozen run. The corrected pilot (`selfplay_causal_pilot_v2`) checks one of the 20 panel worlds. No algorithm changes were made during or after the final panel run.

## Per-world paired margins

Margins below average the two seat assignments. The last column counts any own production-quantity or terminal-farm/inventory mismatch over all four treated games in that world.

| Source episode | Panel | Labor-only margin | Forecast margin | Games with own mismatch |
|---|---|---:|---:|---:|
| 109712554 | leaders | +58.00 | +58.00 | 0 |
| 109940134 | leaders | +181.00 | +181.00 | 0 |
| 109971156 | leaders | +147.00 | +147.00 | 0 |
| 109978530 | leaders | +147.00 | +135.00 | 0 |
| 109983899 | leaders | +113.00 | +131.00 | 0 |
| 110003096 | leaders | +202.00 | +173.00 | 0 |
| 110003132 | leaders | +236.00 | +236.00 | 0 |
| 110022430 | leaders | +3.00 | +3.00 | 0 |
| 110615310 | ladder | +0.00 | +20.00 | 0 |
| 110645152 | ladder | +0.00 | +18.00 | 0 |
| 110676097 | ladder | +0.00 | +6.00 | 0 |
| 110838385 | ladder | +0.00 | +18.00 | 0 |
| 110845047 | ladder | +89.00 | +107.00 | 0 |
| 110940524 | ladder | +183.00 | +183.00 | 0 |
| 110947924 | ladder | +0.00 | +47.00 | 0 |
| 110951483 | ladder | +149.00 | +182.00 | 0 |
| 110972443 | ladder | +183.00 | +183.00 | 0 |
| 111017649 | ladder | +416.00 | +416.00 | 0 |
| 111240681 | ladder | +327.00 | +496.00 | 0 |
| 111266227 | ladder | +183.00 | +183.00 | 0 |

## Reproduction and artifacts

```powershell
.venv/Scripts/python.exe scripts/test_labour_selfplay.py --count 20 --workers 4 --tag selfplay_causal_v1
.venv/Scripts/python.exe scripts/check_labour_selfplay.py --tag selfplay_causal_v1
.venv/Scripts/python.exe scripts/report_labour_selfplay.py
```

Frozen inputs, code/engine hashes, all decisions and the exact compressed action pairs are in [selfplay_causal_v1](../results/fresh/labour_profit/selfplay_causal_v1/). See [summary.json](../results/fresh/labour_profit/selfplay_causal_v1/summary.json) and [verification.json](../results/fresh/labour_profit/selfplay_causal_v1/verification.json). The live agent and submissions are unchanged.
