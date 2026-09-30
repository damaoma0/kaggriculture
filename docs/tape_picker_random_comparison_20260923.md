# Random-seed comparison: mgt_m1, mgt_t10, and V56

Completed 23 September 2026. `mgt_v10` in the request was confirmed to mean
`agents/mgt_t10.py`. The current `mgt_m1` and `mgt_t10` sources were not edited.
No candidate was submitted or promoted.

## Protocol

The first design froze eight development seeds and sixteen untouched holdout
seeds before play. Every matchup used both seats, natural shop reveals and
weeds, the official Kaggriculture 1.32.7 engine, and a fresh process for every
full 719-action game. V56 is the existing frozen public source at
`data/router_refresh_20260922/v56/main.py`. The generic runner and hash-checked
frozen sources are under `results/fresh/tape_picker_study_20260923/`.

The reported intervals resample whole seeds, retaining both seats. The two
seats are often nearly identical and must not be treated as 32 independent
worlds. All reported games finished with reconciled cash ledgers, no agent
call over one second, and zero recorded router or overlay errors. Natural shop
paths can diverge after policies act, so paired results measure complete
policies rather than an isolated tape switch.

## Original agents

| Panel | Agent | Games | W–L vs V56 | Mean final cash margin | Seed-clustered 95% interval |
|---|---|---:|---:|---:|---:|
| Development, 8 seeds | mgt_m1 | 16 | 10–6 | +5,887 | +1,130 to +11,575 |
| Development, 8 seeds | mgt_t10 | 16 | 14–2 | +6,773 | +2,471 to +12,272 |
| **Untouched holdout, 16 seeds** | **mgt_m1** | **32** | **24–8** | **+2,196** | **+106 to +4,442** |
| **Untouched holdout, 16 seeds** | **mgt_t10** | **32** | **28–4** | **+4,197** | **+1,469 to +7,474** |

On the holdout, t10's paired margin advantage over m1 against V56 was
**+2,001 per game** (95% interval **−197 to +5,440**), with four net additional
wins. This is a favorable point estimate for t10 against this opponent, not a
statistically resolved gain in margin.

Direct mgt_m1 versus mgt_t10 on the same 24 random seeds, both seats:
**40 wins, 8 losses for m1**, but mean margin **−480** (seed-clustered interval
**−2,090 to +644**). On the untouched 16-seed portion alone it was 27–5 and
−507. A few large losses, including a −16,206 game, outweigh many small m1
wins. Win frequency and mean margin therefore answer different questions here.

## Picker experiments

The incumbent picker scores weighted cumulative shop demand plus coarse board
Hamming distance; m1 also penalizes stranding live animals. I built isolated
self-contained variants with two additional signals:

1. `mgt_pick_recent` and `mgt_t10_recent` explicitly compare the latest
   revealed shop's product demand with the donor tape's latest shop through day
   15. This distinguishes different reveal orders with equal cumulative demand.
2. `mgt_pick_cohort` compares live strawberry/tomato planting dates with dates
   inferred from the donor's day-start tile labels. The proxy is imperfect when
   a donor replants the same crop between snapshots.

On the eight development seeds, `mgt_pick_cohort` was **−979** paired margin
versus m1. `mgt_pick_recent` was **+420** versus m1, but its mean V56 margin was
below the t10 family. `mgt_t10_recent` had the highest development mean V56
margin, **+7,012**, versus +6,773 for t10, and was frozen before the holdout.

| Untouched 16-seed holdout | Games | W–L vs V56 | Mean margin | Paired versus t10 |
|---|---:|---:|---:|---:|
| mgt_t10_recent | 32 | 24–8 | +3,387 | **−810** (95% interval −2,977 to +1,572) |

It also went **10–22 directly versus m1** (mean margin +158, interval −2,139
to +2,967) and **8–12 with 12 ties directly versus t10** (mean −417, interval
−1,885 to +1,105). The selected recent-shop picker did not beat the original
agents reliably on new seeds. Its worst paired V56 regression versus t10 was
−8,787. In the development case 1247696705, a day-12 switch increased our
cash by 5,051 but led to a different later shop path and much more rival cash;
its margin fell by 9,832. That case alone does not isolate the switch's causal
market effect.

I then tested a continuity condition: let the recent-shop term change rankings
only for tapes whose day-start board distance is no worse than the incumbent's.
The first implementation counted overlay-managed tiles inconsistently between
the incumbent and candidates; its rows are retained as diagnostics only. The
corrected `mgt_t10_reveal_safe2` and `mgt_m1_reveal_safe2` used the same board
distance formula on both sides. On eight newly sampled development seeds, their
paired V56 margins versus the corresponding original agents were **−2,796**
and **−2,851**, respectively. Both went 8–8 versus V56; the original agents
each went 12–4. Seed 1071336464 illustrates the limit of coarse labels: the
corrected m1 picker switched at day 12 to a tape with zero label mismatches
instead of the incumbent's one, yet lost 11,189 paired margin. Later shop paths
diverged, so this is a full-policy failure, not a fixed-shop estimate.

The predeclared second-stage gate required a candidate to improve V56 margin
and beat m1 directly on development seeds before using sixteen reserved
confirmation seeds. Neither corrected candidate passed the first requirement.
Those sixteen confirmation seeds and the direct screening were therefore not
run. `selection_v2.json` records that stop decision.

## Decision and next experiment

There is **no validated picker improvement** in this study. t10 had the higher
V56 holdout point estimate, while m1 won most direct games. Neither simple
recent-shop weighting nor a coarse-board continuity condition should replace
the existing agents on this evidence.

The next picker should compare *executable* continuations from the same actual
observation: crop planted day and remaining yield, animal care and feed,
worker positions, pending inputs and market capacity. It should compile a
short rescue schedule for obligations the new tape would drop, then project
incumbent and candidate through the next reveal under the same visible shops.
Only a funded, executable transition with a margin advantage above a risk
buffer should switch. This is a proposed experiment; the earlier continuation
executor's full-game policy failed, so offline matching or a three-day replay
alone cannot establish a better competitive agent.

Reproduce the source variants with `scripts/build_tape_picker_study.py` and
the game panels with `scripts/benchmark_segment_stitch.py`. The frozen seed
lists, source hashes, per-game ledgers, route histories, timing and complete
statistics are in `results/fresh/tape_picker_study_20260923/`; regenerate its
`summary.json` with `scripts/report_tape_picker_study.py`.
