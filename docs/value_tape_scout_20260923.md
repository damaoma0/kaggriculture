# Faster tape search with an exact first forecast

## Decision

V8 is a new research selector in `scripts/value_tape_search_v8.py`. It spends
one complete official-engine forecast on every shortlisted alternative, then
expands the best two. Every committed candidate still needs all eight paired
forecasts and the existing cash, downside, labor and cohort-protection gates.

The static learned semantic ranker remains experimental. It is fast, but its
shortlist misses valuable alternatives on reserved regression cases. V8 does
not use that model to exclude candidates.

The production agent `agents/mgt_m1.py` is unchanged. Its SHA256 remains
`1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470`.

## Algorithm

1. Build the existing shortlist: native continuation, incumbent, the normal
   reveal choice if different, then diverse alternatives within board-label
   distances 8, 14 and 24; at most seven including native.
2. Run native and every alternative in the first of the eight existing sampled
   shop/rival worlds. Each scout runs to season end using the official engine
   and our working labor scheduler. Stop early if a protected starting cohort
   is already lost at the next reveal.
3. Rank the survivors by the first world's competitive-margin improvement.
   A full-season extra failed hire is also disqualifying. Keep two alternatives,
   including negative-scoring ones if necessary: one negative forecast alone
   is not enough to establish that the other worlds are bad.
4. Expand those two and native to four common worlds. Apply the existing
   margin ranking and protection screen.
5. Expand qualifying finalists and native to all eight worlds. Commit only
   after the original admission rule passes: preserve baseline-retained
   starting cohorts, no extra failed hires, positive expected own-cash gain,
   mean margin minus half its standard deviation above 350, and forecast
   downside no worse than `-max(500, 0.25 * mean_margin)`.
6. Commit until the next shop reveal, then resume native routing and reconsider
   from the actual reached state on D12, D15 and D18.

The candidate search is approximate: a route with a weak first world can be
excluded despite being best across all eight. The simulator checks for
retained candidates are unchanged. Exact physics does not make the sampled
shops or modeled rival sales certain.

## Semantic extraction and learned ranking

The dataset reconstructs 72 previous live decision checkpoints from 36 games
in 24 independent shop worlds. All 36 games reproduce their previous cash and
prefix actions; the 18 multi-decision games also reproduce every action hash.
Three named historical checkpoints are reserved for regression. No target seed,
opponent identity, hidden stock, future shops or realized result enters the
feature function. Forecast labels are separate from its inputs.

All 584 archived tapes now have dated requested-plan profiles. Features include
the next three days' planting, animal additions, purchases, sales requests,
work and hiring; requested service coverage of current cohorts; current public
market/cohort context; and ideal future output, feed and fertilizer commitments
of new cohorts. Ideal production assumes complete service. Requested actions
and archived travel are not labeled as successful jobs.

There are 414 alternative-candidate labels. Every candidate has four forecast
worlds; only previous finalists have eight. The model learns the four-world
ranking and protection outcomes. It never labels an unevaluated eight-world
candidate as an unprofitable one.

Validation removes a whole shop world at a time, including all opponents and
dates from that world. Ridge strength is chosen on these development folds;
these diagnostics are not an independent policy test.

| First screen | Previous live selections retained in top 2 | Reserved major recoveries retained |
|---|---:|---:|
| Shop distance | 0 / 10 | Not used as the new policy |
| Board distance | 1 / 10 | Not used as the new policy |
| Ideal new-cohort value | 4 / 10 | Not used as the new policy |
| Learned semantic ranker | 5 / 10 | 0 / 2 |
| One exact scout world | 10 / 10 | 2 / 2 |

The learned model retains all ten live selections in its top three, but ranks
the reserved wool recovery sixth and strawberry recovery third. That is a
material reason to keep it out of the deployed shortlist. More training on
actual transition effects, including inventory and labor feasibility, is
needed before it can safely replace those forecasts.

Feature extraction plus linear scoring has a measured median of 3.32 ms for
the saved shortlists, after loading the profiles and model (0.62 seconds in
that measurement). This excludes native shortlist construction. Fast scoring
alone does not establish sufficient ranking accuracy.

## Prior-case equivalence

Saved forecasts resolve 74 of the 75 checkpoints. V8 and the corrected V7
reference make the same choice on every resolved checkpoint, reducing the
simulated work from 619,828 to 456,155 turns: **26.4% fewer**. This is fixture
work evidence, not a wall-time measurement.

The remaining checkpoint, seed2761107011 / seat1 / D18, lacked the native
eight-world forecast because the older V3 cash screen had stopped earlier.
Fresh forecasts resolve it: V7 and V8 both choose no switch. Thus all 75 old
checkpoints now have a checked matching choice. The original censored fixture
was preserved rather than filled with an assumed bad outcome.

Both major recoveries remain selected: route184 on 111262874 D12 (+18,449
previously measured margin), and route0 on 111269605 D15 (+10,034). Their full
common forecasts match the reference in the uncached engine checks. Those
profit figures remain historical development evidence.

## Uncached timing

One paired run per historical case, with the order reversed for the wool case:

| Case | V7 seconds | V8 seconds |
|---|---:|---:|
| Strawberry recovery | 24.01 | 30.04 |
| Wool recovery | 24.74 | 19.20 |
| Unchanged control | 34.57 | 21.72 |

The aggregate wall-time reduction is about 15%, with a clear slower outlier.
Initialization, cache state and machine load can affect these measurements;
their individual contributions were not isolated. Do not turn the deterministic
work reduction into a claim of uniform wall-time improvement.

## Fresh qualification

Six new IID shop worlds were frozen before execution and crossed with V56,
sixday and pasture. Seats alternate. Each matchup plays three complete
policies: native, full V7 search and V8 scouting. All 54 games finish, both
cash ledgers reconcile, and the pre-D12 action prefixes match. V56 uses its
actual Kaggle entry point, `e410_agent`.

| Metric | Result |
|---|---:|
| Paired matchups | 18, from 6 independent demand worlds |
| Improved / unchanged / worse competitive margin | 6 / 12 / 0 |
| Mean margin gain over native | +461.83 |
| Mean own-cash change | +54.17 |
| Mean rival-cash change | -407.67 |
| Wins, native / scout / full search | 15 / 15 / 15 |
| Scout choices matching full search | 54 / 54 |
| Full scout game action streams matching full search | 18 / 18 |
| Exact-search / scout simulated turns | 383,542 / 280,913 |
| Work reduction against the already-pruned V7 | **26.8%** |
| Exact-search / scout rollout calls | 1,131 / 871 |

All six changed games intervene once at D18. The fresh mean is substantially
smaller than the earlier development panel's +2,882; the higher figure should
not be presented as an established average recovery. The gains occur in two
of six new shop worlds, repeated against the three opponents. Those matchups
are correlated, and repeated successful commitments within one game remain
unvalidated.

| New world / opponent | Commitment | Margin change | Own cash | Rival cash |
|---|---|---:|---:|---:|
| 2 / V56 | Route74 | +2,410 | +281 | -2,129 |
| 2 / sixday | Route74 | +1,079 | -289 | -1,368 |
| 2 / pasture | Route74 | +1,350 | +695 | -655 |
| 5 / V56 | Keep route561 | +793 | +207 | -586 |
| 5 / sixday | Keep route561 | +1,277 | +75 | -1,202 |
| 5 / pasture | Keep route561 | +1,404 | +6 | -1,398 |

World2 reveals Yarn at D18. Against V56, route74 buys one extra sheep; season
sales change by +38 wool, +38 fertilizer, +6 eggs and +4 milk, while carrot
sales fall by 59, tomato by 18 and wheat by 20. Wages fall by 864. Our cash
rises by 281; the rival's wool revenue falls by 4,120, partly offset by higher
berry revenue. The margin moves from -6,452 to -4,042. This is a smaller
recovery, not a win conversion.

World5 illustrates avoiding an unnecessary switch. At D18 the native router
prefers route329, with shop distance9 and board distance6, to incumbent561,
with shop distance21 and board distance0. The value search instead commits
the incumbent for three days. That improves all three matchups. The choice
of a commitment does not necessarily mean changing tapes.

Common forecasts are computed once and shared between the scout and shadow
reference only for identical public observation, own memory, scenario, route
and protected cohorts. The reference then plays its own complete game, reusing
a shadow decision only when the portable input digest matches. Thus the
action/cash comparisons are complete-game checks, while shadow wall times
are intentionally unsuitable for a speed ratio.

The scout calls themselves have no forecast cache hits and take a median
10.51 seconds, range 5.80–23.04, in this panel. Per-decision simulator preparation
and initial runtime construction occur before this timer. These measurements
do not establish whether a complete game fits the 60-second overage bank.
Use the work reduction and separate uncached timing
table above for the speed claims.

Full audited metrics: `results/fresh/value_tape_ranker_20260923/final_metrics.json`.

## Deadline and verification

`choose(..., budget_seconds=...)` checks the deadline between stages and every
eight simulated turns. Interrupted forecasts restore the engine hooks and
cannot become admission evidence. If nothing has completed all eight worlds
and passed the gates, the result is native routing. A fully checked candidate
can still be chosen if a later candidate times out.

Four tests cover public-input isolation and route-ID invariance, reserved
recoveries and complete admission, pairwise ranking isolation, and interruption
cleanup followed by exact forecast reproduction. All pass. Deadline checks are
cooperative; initialization and individual engine calls can overrun the instant
of expiry. This is not a hard real-time guarantee.

Correction from the cloud audit: the installed competition budget is one second
per action plus **60 seconds of total overage**, not the previously reported
twelve seconds. The manual research panel does not enforce it. A
fallback prevents partly checked switches; it does not make this research
search competition-ready.

## Next engineering step

The useful target for learning is the value of the **actual transition after
the first three days**: what was successfully planted, which cohorts survived,
cash and stocks remaining, feed commitments, and labor consumed. A short
physical simulation can expose those facts much more cheaply than a full
season. Train its continuation-value model on the growing exact-forecast
dataset, then repeat whole-world validation before reducing the scout horizon.
The current static-request model is insufficient evidence for that shortcut.

## Artifacts

- `scripts/build_tape_ranker_dataset.py`: verified replay reconstruction.
- `scripts/tape_semantic_features.py`: dated requested-plan profiles/features.
- `scripts/train_tape_semantic_ranker.py`: grouped development training and
  source-family stress diagnostics; only two source submissions are represented.
- `scripts/value_tape_search_v8.py`: staged exact scouting and deadline fallback.
- `scripts/benchmark_tape_scout.py`: frozen three-policy live qualification and
  separate uncached engine/timing comparisons.
- `scripts/summarize_tape_scout.py`: frozen-source, prefix and cash-ledger audit.
- `tests/test_tape_scout.py`: four regression and isolation tests.
- `results/fresh/value_tape_ranker_20260923/`: checkpoints, profiles, model,
  all forecasts, frozen sources, split diagnostics and raw measurements.
