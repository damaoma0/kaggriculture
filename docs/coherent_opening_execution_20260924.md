# Leader openings: semantic inputs and coherent continuations

Research date: 2026-09-24. This experiment follows the leader-opening review.
The existing m1 agent is unchanged. The candidate is a research policy, not a submitted build.

## Result

The semantic input adapter generalizes to the fresh panel: it recovers **14,300 coins per game** relative to replaying the newer opening with the same library, and improves 59 of 64 paired cases. It eliminates the opening hire failures and restores the intended early strawberry/melon establishment.

This does **not** yet establish a better complete policy than m1. The repaired 112-tape policy earns 4,626 fewer coins per game than m1. Adding 32 recent tapes changes cash by -609 on average, with an interval spanning both gains and losses. The next priority is checking the resources and crop states required by a continuation before selecting it. One new continuation passed the tile-label check but subsequently lost 29,536 coins relative to the smaller library.

## What was built

The candidate keeps the leader opening and its complete continuation in the same DSM tape family. The library contains 109 previously collected DSM seats, the three fresh DSM recordings from the leader review, and optionally 32 more recent recordings from submission 56495569. The added recordings were selected by recency and complete-record validity, without filtering by score. They cover all eight first-shop types.

The execution changes are deliberately limited and inspectable:

1. **Successful purchases.** Replace recorded purchase requests with the quantities that actually succeeded in the source game. Preserve sale requests and inert queue slots. A request that happened to fail in its original market should not become an unintended purchase in another market.
2. **Successful pickups.** In the first two days, use the quantity each worker actually collected. Repeated pickup requests can be retries. Treating every retry as an additional allocation can leave one worker holding unnecessary feed.
3. **Feed deadlines.** In those first two days, buy wheat for the next scheduled pickup, using the live shed inventory. This replaces the recorded purchase/resale churn before wheat crops can mature.
4. **Seed deadlines.** Through day 5, buy the missing seeds for the next scheduled planting. Market actions happen after physical work, so purchases are issued one turn before planting. Seeds intended for a later day no longer consume the next morning's wages prematurely.
5. **More continuation coverage.** Add the 32 recent full-season tapes while retaining the same fixed opening source, episode 112802103. This separates library coverage from opening selection.

The physical routes still come from the tapes. This is an input execution adapter, not yet a general executor that can reconstruct any farm from production targets.

For example, the verified establishment jobs in opening source 112802103 are:

| Day | Planting | Animals placed |
|---|---|---|
| 0 | 6 melon, 9 wheat | 2 cows, 3 sheep |
| 1 | 4 melon, 1 wheat | — |
| 2 | 4 strawberry | — |
| 3 | 6 strawberry | — |

Watering, feeding, care, and deliveries have their own scheduled jobs. `semantic_contract_example.json` preserves the establishment times and tiles rather than reducing them to final asset counts.

## Failures that changed the implementation

### Reserving wages by cancelling capital was a bad repair

The first funding guard cancelled a planned land purchase to remove a projected wage shortfall of only 26 or 39 coins. The continuation needed that land immediately. In the paired development world, final cash fell by **38,957 against m1** and **56,894 against V56**, relative to the same normalized policy without that guard. The actual land purchase cost was 1,000. Daily snapshots and the complete cash ledger reconcile the resulting losses.

The final candidate does not perform that cancellation. Protecting a few hires while breaking the production schedule is not a valid funding repair.

### A tiny opening shortfall can shift every later worker command

In the traced newer-opening replay, day 0 ended with one coin. Three hires at the next morning's first turn cost four coins; only one succeeded. Subsequent tape commands then addressed the wrong available crew, and several crops were missed.

Buying feed at its pickup deadlines saved money, but the tape immediately spent the saving on a wheat seed intended for the next day. Moving seed purchases to their own deadlines retained **11 coins** at the end of day 0 and funded the intended crew.

There was a second allocation problem: a worker requested two wheat at both steps 34 and 36. The first request filled zero in the source game, while the second filled two. In a replay with more available wheat, both requests could fill. Normalizing these allocations and buying to their deadlines restored the missing day-1 melon in the traced case.

## Extraction and verification

- 143 unique source replays, containing 144 DSM target seats, were re-executed serially.
- Each replay has 719 transitions: **102,817 joint transitions** checked against recorded farms, market, town, and both private observations. Cash was reconciled independently from successful transaction events.
- The output includes original actions, successful orders aligned to market queue positions, daily farm/private snapshots, physical jobs, and shop reveals.
- Separate full-season checks establish source parity after purchase normalization, and after combined purchase/pickup normalization for episode 112802103. The combined check changed 69 market slots and seven pickups without changing the source execution.
- Mechanical extraction, downloading, and table audits were delegated to cheaper GPT-6 Luna agents. Their work was reviewed and corrected before use; in particular, the first inventory hook accidentally mutated absent-worker inventory slots, and the first harness draft revealed shops too early. Neither defect is present in the measured games.

## Test design

Development: eight random worlds, one per first-shop type, crossed with live m1 and frozen V56; 16 paired cases. The remaining seven shops are independent uniform draws. The same seed, seat, and shop schedule are reused across policy variants.

Qualification: 32 separate random worlds, four per first-shop type, crossed with the same opponents; 64 paired cases and four policies, for 256 games. Candidate code and input hashes were frozen before this panel. Qualification outcomes are not used for tuning.

Shops are revealed only at days 3, 6, ..., 24. Policies receive their current observation. The test harness enforces the hidden schedule after each day boundary so different farm actions cannot change the chosen shop sequence through random-number consumption. Both opponents act live and can react to changed prices.

Every completed game checks terminal status, both cash ledgers, shop-prefix visibility, and restoration of interpreter instrumentation. Intervals resample whole worlds, keeping the two opponent cases together. These are complete-policy comparisons; they do not isolate the causal value of the opening's crop mix alone.

## Development results

Mean change versus native m1, on the 16 fixed development cases:

| Policy | Our final cash | Our margin over the opponent |
|---|---:|---:|
| Original 109-tape DSM policy | -14,624 | -14,136 |
| Normalize its purchases | -10,845 | -7,128 |
| Newer opening, 112 tapes, normalized purchases | -25,921 | -40,898 |
| Semantic input execution, same 112 tapes | -6,920 | -1,243 |
| Semantic input execution, 144 tapes | -5,613 | +192 |

The final development candidate recovers **20,308 cash** and **41,090 opponent margin** versus the fragile newer-opening replay. It still earns less than m1. These development estimates motivated the separate fresh-panel measurements of input execution and library coverage below.

The newer replay averaged three failed hires in days 0-2; both semantic variants had zero in those days across all 16 development cases. The larger library averaged 4 strawberries and 9.875 melons at day 3, and 10 strawberries and 9.875 melons at day 6. The fragile newer replay averaged only 2 strawberries/5.5 melons at day 3 and 7.375/4.875 at day 6.

The extra 32 tapes were selected in six of the 16 development cases (three of the eight worlds). All six improved relative to the same semantic adapter with the smaller library. Mean coverage benefit was 1,307 cash across the entire panel. This is development evidence, not an independent estimate.

Coverage remains sparse: exact first-two-shop prefixes increase from 52/64 to 57/64, and first-three-shop prefixes from 99/512 to 124/512. A larger library cannot cover the combinatorial space by itself.

The full-season development cash gap is not just an opening wage problem. Mean strawberry receipts are 4,842 lower and wool receipts 2,876 lower than m1; melon receipts are 3,743 lower. Carrot, wheat, egg, and tomato receipts partly compensate. These are realized revenue differences under live opponent responses, not isolated estimates of the value of each production change. Full item-level receipts and costs reconcile to the final cash difference in `development_v5_loss_breakdown.json`.

## Qualification results

All **256 games** completed: 32 fresh worlds, two live opponents, four policies. All 283 frozen source/input hashes remained unchanged. Independent checks matched every record to its full predeclared specification and recomputed all 512 seat-level cash ledgers. Qualification seeds are distinct from development seeds.

Mean changes versus native m1 across the 64 paired cases:

| Policy | Our final cash | Our margin over the opponent |
|---|---:|---:|
| Newer opening, 112 tapes, normalized purchases | -18,926 | -28,924 |
| Semantic input execution, same 112 tapes | -4,626 | -2,047 |
| Semantic input execution, 144 tapes | -5,235 | -2,240 |

The prespecified primary comparison was the 144-tape candidate versus m1. Its mean cash difference is **-5,235**, with a 95% world-bootstrap interval of **[-9,634, -1,312]**. Its opponent-margin difference is -2,240, interval [-7,465, +2,296]. This panel does not support replacing m1 with that candidate.

The two ablations separate execution from library coverage:

| Change | Mean cash difference | 95% world-bootstrap interval | Better / same / worse cases |
|---|---:|---:|---:|
| Semantic inputs, same 112 tapes | +14,300 | [+11,104, +17,597] | 59 / 0 / 5 |
| Add 32 tapes, retain semantic inputs | -609 | [-3,070, +1,308] | 8 / 48 / 8 |

Input execution improves mean opponent margin by 26,877, interval [+22,103, +31,698]. Its remaining cash gap to m1 is -4,626, interval [-9,006, -709]. These exploratory intervals resample the 32 whole worlds, retaining both opponents; they are not Elo estimates or simultaneous bounds for every comparison.

The execution benefit appears against both opponents: +22,902 cash against live m1 and +5,697 against V56, relative to the fragile newer replay. The smaller semantic candidate still trails the corresponding m1 control by 4,657 and 4,595 respectively. The complete-policy deficit therefore is not confined to one opponent.

Raw win counts need care because the baseline includes m1 self-play. The 144-tape candidate records 37 wins and no ties; baseline records 23 wins and 27 ties. Counting a tie as half a point gives 37 versus 36.5 points out of 64, not a large demonstrated improvement.

### Opening execution and remaining costs

The fragile newer replay has **192 failed hires in days 0-2**, affecting all 64 cases. Both semantic variants have zero. At day 3, both semantic variants have four strawberries and ten melons in every case. At day 6 the larger bank averages ten of each; the smaller bank averages 9.875 strawberries and ten melons. Native m1 has zero strawberries/twelve melons at day 3 and four/twelve at day 6. Successful early establishment alone does not establish full-season profitability.

The smaller semantic candidate has no later hire failures on this panel. The larger bank has three later failures across two games. Its extra routes can therefore reintroduce funding failures after the protected opening.

For the smaller semantic candidate, mean revenue is **43 higher** than m1, but spending is **4,670 higher**, explaining the 4,626 cash deficit after rounding. The largest extra costs are wheat purchases (+3,368), labor (+908), cows (+825), and geese (+581); fertilizer purchases cost 964 less. Revenue shifts also matter: melon receipts fall 3,706 and strawberry receipts 2,439, offset mainly by wheat (+2,857), eggs (+2,109), carrots (+917), and wool (+610). These are reconciled realized ledger differences under reacting opponents, not separate causal effects.

The largest smaller-candidate cash loss against m1 is **49,901** in `w08-mgt_m1`: revenue falls 41,627 and spending rises 8,274. Strawberry receipts alone fall 27,068, despite successful opening hires. This is an important continuation/production case for subsequent work, rather than another instance of the repaired opening wage failure.

### A new continuation passes tile matching and then fails

In `w26-v56`, both semantic variants reach day 6 with the same 796 coins, ten strawberries, ten melons, two cows, and three sheep. The revealed shops are Smoothie Shop and Brunch Spot. The expanded bank selects episode **112639559** with **zero tile-label mismatches**, but one crop-cohort mismatch. Its recorded source had 845 coins and one strawberry seed; the live farm has no strawberry seeds. Wheat stock differs as well.

| Checkpoint | Smaller library | Expanded library |
|---|---:|---:|
| Day 7 opening cash | 138 | 34 |
| Failed hires during day 7 | 0 | 2 |
| Day 8 strawberry / melon plants | 22 / 10 | 18 / 6 |
| Day 15 sheep | 8 | 3 |
| Final cash | 108,004 | 78,468 |

The expanded route reaches ten tile mismatches at day 8 and stays on the same tape for the remainder of the game. Yarn Stores are revealed at days 9 and 12. The final cash difference is **-29,536**, reconciled as 22,339 less revenue plus 7,197 more spending. Wool receipts are 32,026 lower, partly offset by eggs and carrots. The early crew failure and the later production allocation both matter; this comparison does not assign the entire loss to the two failed hires.

The saved trajectory demonstrates why adding candidate tapes without checking their execution requirements can hurt. It also provides a concrete case for evaluating a better switch mechanism without assuming that tile-label equality implies a compatible continuation.

## Local speed

A fresh-process profile of development case `w05-mgt_m1` reproduced its saved full-game action hash. Across 719 calls, policy computation had a **0.122 ms median**, **0.886 ms p95**, and **12.824 ms maximum**. The maximum overlapped an 8.710 ms generation-1 garbage collection. These measurements are inside the policy wrapper; the harness copies observations before entering it.

The qualification batch recorded maximum calls of 1.210 seconds for the larger semantic bank, 1.172 seconds for the smaller semantic bank, and 2.275 seconds for m1. A fresh-process profile of the larger bank's exact outlier case (`w06-mgt_m1`) reproduced its action hash, with **0.100 ms median, 0.788 ms p95, and 9.721 ms maximum** over 719 calls. That maximum overlapped 8.067 ms of generation-1 garbage collection. The original long calls were not instrumented, so their causes are not established. Typical fresh-process performance is fast; the long-batch tail still needs attention before deployment.

The research factory took **6.106-6.644 seconds to initialize**, including loading and interpreting the trace library. That cost needs a compact compiled representation before deployment. Mean qualification simulation time was 6.75 seconds per full game for the larger bank, including the live opponent and instrumented engine; this is distinct from policy-call latency. These are measurements on the shared local machine, not Kaggle runtime guarantees. A reporting error in the development profiler required a second execution of that profiling case; both runs matched the saved action hash.

## Tape selection still has a separate limitation

This experiment retains the existing router. At each eligible day boundary it ranks tapes using weighted differences in **revealed** shop demand, tile-label distance, and a penalty for stranding animals. New candidates normally must be within eight tile labels; the incumbent can remain beyond that limit. Ties favor the incumbent. Unrevealed test shops are not supplied to the router.

Tile labels omit crop age, yield state, carried supplies, and the cash needed to complete a transition. The new adapter repairs some input timing failures, but it does not make a switch exact in those hidden dependencies. Later expansion and continuation failures remain distinct from the opening failures repaired here.

## Research decision and next experiment

Continue developing semantic execution and funding-aware continuation selection. The current evidence supports the input adapter's recovery, while the newer opening's complete policy still underperforms m1. Keep the 112-tape semantic variant as a research control; the extra 32 tapes have no established aggregate advantage with the present router.

The next experiment should give shortlisted continuations an explicit execution contract: crop ages/yields, required workers and carried inventory, seed/feed deadlines, critical capital jobs, and a feasible cash path through the next morning and three-day checkpoint. Rank feasible continuations by expected production value using revealed shops; evaluate uncertain later demand separately. Extend deadline procurement at each switch, preserve necessary capital purchases, and use the existing labor scheduler to repair jobs when the source worker assignments no longer apply.

Use the qualification failures above as diagnostic/development cases for that new version, then evaluate it on another untouched panel. The present qualification panel will no longer be independent once it guides further changes. Compile the extracted contracts and address initialization and latency tails before considering a submission.

## Reproduction and artifacts

- Main runner: `scripts/run_coherent_opening_v5.py`.
- Candidate: `scripts/coherent_opening_v5.py`, layered over the preserved earlier experimental revisions.
- Summary: `scripts/summarize_coherent_opening_study.py`.
- Full designs, source manifests/snapshots, and per-game ledgers: `results/fresh/coherent_opening_20260924_01a0/`.
- Detailed failure evidence: `v1_failure_audit.json`, `diagnostics/early_failure_audit.json`, and `diagnostics/w02-v56-deadlines-72.json` under that result root.
- Frozen qualification results: `qualification/v5/summary.json`, `paired.json`, `integrity_check.json`, and the saved `experiment_protocol.json` in the same directory.
- Qualification audits: `qualification_v5_audit.json`, `qualification_loss_breakdown.json`, `qualification_switch_failure_w26.json`, and `qualification_runtime_profile.json` under the result root.

Run with the project's bundled vendor path and Python runtime used by the study. For qualification:

```powershell
$env:PYTHONPATH="$PWD/results/fresh/tape_margin_20260924_01a0/payload/vendor;$PWD/.venv/Lib/site-packages;$PWD/scripts"
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/xyygl/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' scripts/run_coherent_opening_v5.py --phase qualification --revision v5 --arms baseline,latest,semantic_inputs,semantic_bank
```

The runner checks the frozen hashes and skips already completed files; it will refuse changed inputs under the same revision.
