# Tape matching and release qualification — 24 September 2026

## Status

**The fresh 384-game panel passed; an output-stream race was fixed and the derived
archive passed both official-loader checks.** No policy tuning used these outcomes.
Submission status is recorded at the end of this report.

## What this round established

We continued the leading-team opening research by adding semantic continuation
contracts: crop/animal identity and age, production stage, outstanding work, hires,
and spending requirements. The extracted library contains 144 source routes and
4,320 daily contracts. The contracts are research artifacts; they are not silently
included in the release candidate below.

The four targeted development cases showed that continuation checks can recover
large losses from the fragile opening branch. For example, the static state-cost
selector recovered 50,860 cash in w08 against live m1 relative to semantic_bank,
finishing 1,170 above the original m1. However, performance across the four cases
remained inferior to original m1. These cases were selected to investigate known
failures, so they cannot establish population-wide improvement.

The most conservative continuation experiment eliminated all failed hires in the
four cases. It still ended between 2,715 and 16,690 cash below original m1 in each
case. Execution feasibility alone does not determine the most profitable farm.
Adding more crops or animals also needs a full-season value comparison accounting
for labor, fertilizer/feed, sale timing, and the opponent's use of market demand.

One concrete failure was a day-6 switch to route 140 in w26 against V56. The complete
policy forecast predicted a failed purchase and no failed hires; live execution
later recorded three failed hires while that route remained active. Treating the
purchase failure as a small cost admitted the switch. Making forecast failures a
strong rejection eliminated those hires, but did not repair the route's full-season
economics. The forecast's modeled rival market remains an approximation.

An initial probe also incorrectly interpreted the simulator's `None` hire return
as failure. It was corrected to compare actual `hires_today` changes. Those initial
results are explicitly invalid and excluded. A later correction forecast the full
agent, including trade and herd overlays, instead of only its underlying action
chassis. Valid targeted results and source snapshots are retained in
`results/fresh/coherent_switch_20260924_01a0/pilot_audit.{json,md}`.

## Candidate selected for release qualification

The candidate is the existing **V9-lite selector over mgt_y3** (original m1 plus the
late-Yarn repair), built by the concurrent development effort. This turn audited
and promoted that exact artifact into durable repository storage. It was selected
using previously completed tests, before inspecting the fresh qualification's cash
outcomes. It is not presented as a newly implemented version of the contract pilot.

- Archive: `submissions/2026-09-24-v9lite-candidate-01a0/submission.tar.gz`
- SHA-256: `6f5e2c2781325a91525b56343dd6fb73f6aeba2fabde63e55cfeae9fdb390f3b`
- Entry SHA-256: `04e4a5e89d801b6fd6fcabd3f420782e1c3aabd822068a2367d9b88420176114`
- All 185 package files match their manifest and archive bytes.
- Original source and ownership are recorded in that directory's `PROVENANCE.md`.

Prior evidence from the concurrent effort: in 185 frozen-opponent recordings,
V9-lite improved paired competitive margin by 611.081 on average relative to Y3,
with 32 better, 145 identical, and 8 worse results. Wins increased from 87 to 96;
555 search decisions had zero recorded search errors. These are counterfactual
recording tests, not a live-opponent rating estimate. The new panel below is the
release gate.

The historical gain decomposes into +212.643 own cash and -398.438 opponent cash.
One of those 185 cases crosses the old panel's broken-opponent-replay threshold;
excluding it gives 184 cases and +614.913 mean margin. The raw result is retained
for provenance, with this limitation. The new qualification uses live opponents
so their responses can change when our actions change.

## Exact deployed selection algorithm

1. Play Y3 normally. Reconsider tapes only when shops reveal on days 12, 15, and 18.
2. Use the V9 public-state and own-memory shortlist, up to seven entries including
   the native policy. Discard alternatives more than 12 tile labels away. Skip a
   commitment to the same route the native router already picked.
3. Run exact full-season native and candidate forecasts in one modeled world.
   Only scouts gaining more than 350 competitive-margin units proceed.
4. Expand at most two candidates to four modeled rival/shop worlds. The second
   expansion is skipped if the first candidate already satisfies admission.
5. Require all four forecasts to finish, no cohort/hire protection failures,
   positive mean own-cash gain, `mean margin gain - 0.5 * standard deviation > 350`,
   and worst-world margin gain at least `-max(500, 0.25 * mean margin gain)`.
6. Commit an admitted route for three days, then return to native routing. A
   timed-out or incomplete candidate cannot justify a commitment.

The board-distance filter is only candidate retrieval. Admission uses simulated
full-policy consequences and protected productive cohorts. This is not guaranteed
tile-exact reproduction of a source farm, nor a proof that every switch is safe
against every possible opponent. The evidence must measure its actual losses as
well as recoveries.

Protection has a precise scope: animals and existing tomato, strawberry, and melon
cohorts are identified by tile, species, and placement/planting day. A candidate
must retain the cohorts that native play would retain at the next three-day
boundary, and must not add forecast failed hires relative to native play. Wheat
and carrot replacements are not prohibited by this cohort guard; their economic
cost is evaluated in the full-season forecasts.

The wrapper builds a private forecast runtime in a background thread, optionally
warms a rollout on day 10, and joins that thread before search. Search budgets use
the observed overage bank: a maximum of 30 seconds on day 12, 20 on days 15/18,
eight seconds of reserve, and six seconds set aside for each later reveal. Cold
loading, warm-up contention, and live deadline behavior therefore require archive
tests; an unbudgeted search benchmark is insufficient.

Forecasts use a separately compiled engine module. Their hooks do not replace the
live evaluation's accounting hooks. Future shops are sampled from revealed shops
and public day information; the persisted hidden evaluation schedule is confined
to the harness.

## Fresh qualification design

The frozen design contains 64 new independent worlds. Each world draws eight shops
uniformly with replacement and faces both live original m1 and live V56. Seats are
balanced. Each matchup is evaluated with original m1, Y3, and the exact V9-lite
archive: 128 matched triples, 384 games. Every game runs in a fresh subprocess,
serially, with the candidate unchanged.

The primary metric is paired final competitive margin: own cash minus opponent
cash. Confidence intervals resample worlds, keeping both opponent matchups
together. The analysis uses 10,000 bootstrap replicates and also reports own cash,
win counts, regressions, runtime, interventions, and component comparisons.

Predeclared release requirements:

- All 384 games complete, both players' ledgers reconcile, no time-bank exhaustion
  or candidate search errors.
- Mean competitive-margin gain over original m1 is positive and its world-cluster
  bootstrap 95% lower bound is above zero.
- No material mean degradation relative to Y3; inspect every large new regression.
- The unchanged archive passes separate official file-loader checks.

Source review added one concrete verification requirement before release: the
wrapper replaces the native code with Y3 but leaves an internal `SOURCE_SHA256`
constant naming m1. Its inherited observation-ownership assertion therefore does
not itself certify Y3. The six Y3 AST changes appear to read observations and
mutate policy-owned state only; the earlier dynamic audit covered m1. A separate
runtime ownership audit explicitly bound to the exact Y3 bytes is required.
Archive and entry identities above come from actual file hashes, not that legacy
internal constant.

Additional parity checks compare V9-lite against Y3 before the first possible
switch and across the full game when the candidate reports zero switches. Frozen
source and archive hashes are checked before and after the batch. The framework's
source hashes were recorded after the first worlds but before outcome inspection;
that pins the observed environment, not retroactive evidence of every earlier
process import.

Artifacts are under
`results/fresh/coherent_switch_20260924_01a0/release_lite_qualification/`:
`design.json`, `manifest.json`, `environment_manifest.json`, `protocol_audit.md`,
the frozen `package/`, archive, and per-game records. The records contain final
ledgers, daily cash, timings, and action hashes. They do not retain complete daily
inventories or tile states, so detailed new loss diagnoses may require explicitly
labeled diagnostic replays.

## Qualification results and submission

All 384 games completed. All 768 seat ledgers reconcile exactly. The archive,
driver, and opponents passed the final frozen-hash check. All 128 candidate games
match Y3's action prefix before day 12; all 103 games without a selected switch
match Y3's complete action hash and both final cash balances. There were 384 search
decisions, 26 commitments across 25 games, and zero search or warm-up errors.

| Paired contrast | Mean own-cash gain (95% world CI) | Mean competitive-margin gain (95% world CI) |
|---|---:|---:|
| V9-lite minus original m1 | +538.43 [166.17, 998.90] | +913.83 [413.46, 1,476.93] |
| V9-lite minus Y3 | +417.60 [63.62, 836.67] | +604.49 [144.83, 1,113.88] |
| Y3 minus original m1 | +120.83 [-46.82, 283.47] | +309.34 [147.79, 492.94] |

The predeclared primary statistical gate passes. The search adds a positive mean
gain over its Y3 component control, with both cash and margin intervals above zero.

| Agent | Wins / ties / losses, all 128 games | Wins against V56, out of 64 | Score with half credit for ties |
|---|---:|---:|---:|
| Original m1 | 52 / 52 / 24 | 47 | 60.94% |
| Y3 | 71 / 32 / 25 | 48 | 67.97% |
| V9-lite | 80 / 28 / 20 | 51 | 73.44% |

The large tie count comes from the m1 self-play control. These are local matched
panel results, not a prediction of Kaggle Elo. Mean margin gains over original m1
were +1,056.05 against live m1 and +771.61 against live V56. Relative to Y3, search
produced 19 better margins, 103 identical margins, and six worse margins; own cash
improved in 16 cases, stayed identical in 103, and fell in nine.

### Runtime and ownership

Candidate own-call time including initial file loading averaged 8.40 seconds per
game; the maximum total was 34.58 seconds. The slowest individual call was 13.79
seconds. Minimum remaining bank was 31.30 of 60 seconds; mean remaining bank was
55.56 seconds. These measurements exclude opponent/framework work and background
work outside calls. They are local timings, not Kaggle server measurements.

The additional exact-Y3 ownership audit passed 5,748 checked calls across two real
Y3 games, days 12/18, native/alternative routes, and two forecast worlds. Neither
observations nor caller memory changed, and no checked mutable observation aliases
were retained. Its source guard was explicitly bound to Y3's actual file hash in
the audit process. The tested archive itself was unchanged.

### Gains and losses

Relative to Y3, the average +417.60 own cash is +223.05 sales revenue plus 194.55
less spending. Notable average sales changes were strawberry +310.43, wool +218.11,
tomato +87.96, wheat -312.19, and carrot -133.09. Average labor spending fell 114.83,
purchased wheat fell 94.59, and sheep purchases rose 54.69. Opponent cash fell
186.89 on average, giving the +604.49 competitive-margin gain. No extra actual
failed hires occurred in any candidate/control pair.

All six margin regressions against Y3 are retained:

| Case | Own-cash change | Opponent-cash change | Margin change |
|---|---:|---:|---:|
| r00-v56 | -4,134 | +1,116 | -5,250 |
| r15-mgt_m1 | -2,700 | +344 | -3,044 |
| r15-v56 | -4,635 | -1,626 | -3,009 |
| r21-v56 | +2,618 | +4,966 | -2,348 |
| r46-v56 | +7,400 | +8,314 | -914 |
| r54-v56 | -513 | +3,145 | -3,658 |

The worst margin regression, r00-v56, lost 2,628 in sales and spent 1,506 more.
Tomato sales gained 2,041, but strawberry lost 1,980, carrot lost 1,869, wheat lost
766, and milk lost 640; other items partly offset those losses. Extra spending
included 665 labor, 599 purchased wheat, and 302 fertilizer. This was an economic
misallocation, with zero failed hires. In r21 and r46 our farm earned more, but the
opponent gained still more. These cases remain weaknesses in forecasting market
competition; the scenario loss rule is not a realized-loss guarantee.

Largest own-cash recovery over Y3: r01-mgt_m1, +10,297 cash and +8,299 margin.
Detailed item-level paired ledgers are in `paired.json`; exact trajectory diagnostic
replays are in `diagnostics/`. All 14 replays (six losses plus the largest own-cash
gain, each candidate/control) match original action hashes and final cash exactly.
The independent six-case review is `regression_review.md`.

### Final archive correction

The first cold official-loader test with the original archive completed its game,
but the process exited with `ValueError: I/O operation on closed file`. Background
forecast initialization called two research-helper contexts that redirected
process-global stdout/stderr. These can overlap the official agent loader's own
temporary capture buffers. Warming only the engine would not address the second
redirect in simulator initialization.

A derived archive removes those two redirect contexts, replacing them with
`nullcontext`. It changes only `scripts/research_labour_profit.py`; the other 184
files, including main.py, native Y3, search, and all data, are byte-identical.
Both context bodies retain the same engine import/construction/reset operations.
The original qualified archive and results remain intact.

- Release archive: `submissions/2026-09-24-v9lite-iofix-01a0/submission.tar.gz`
- Release SHA-256: `372237589610a204abd156db65f865a41f9c0535744ff2cfe251e94438961c9e`
- Parent archive SHA-256: `6f5e2c2781325a91525b56343dd6fb73f6aeba2fabde63e55cfeae9fdb390f3b`

The derived archive passed two fresh-process official-loader games from separate
working directories, both seats represented, with the second test decompressing
the packaged JSON libraries to exercise the upload fallback. Both ran 720 recorded
steps with DONE/DONE, zero search errors, and all three reveal searches. Their
minimum time banks were 56.85 and 54.52 seconds; both preserved stdout/stderr and
exited normally. They use the engine's natural shop schedule, so they are loader
and runtime checks, not repeats of the panel's externally fixed shop sequences.

The 384-game economic estimates above belong to the original archive. The release
inherits the same policy/search bytes with this output-capture fix; it is not
claimed to have run another 384-game panel. Independent structural/state-equivalence
checks and these derived-archive loader results document the bridge.

### Submission status

The independent structural/state-equivalence audit passed: only one package file
changed, the simulator operation bodies are structurally unchanged, and constructor
states match on both persisted seeds. See `io_fix_audit.md` in the qualification directory.

Submitted to Kaggle on **2026-09-24 at 15:26:20 UTC**, with description beginning
`mgt_v9lite_y3_iofix`. Kaggle acknowledged the uploaded `submission.tar.gz` and
displayed **Pending**, still pending after refreshing at 15:30 UTC. Server validation
and a new competition rating are not yet established. The submitted archive is the corrected release with SHA-256
`372237589610a204abd156db65f865a41f9c0535744ff2cfe251e94438961c9e`.

Status page: https://www.kaggle.com/competitions/kaggriculture/submissions
