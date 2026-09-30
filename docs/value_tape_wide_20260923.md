# Wider V9 tape-selector evaluation — 2026-09-23

**Status: 96/96 paired matchups complete.** The prespecified panel is finished. Additional exact-control follow-up: 10/10 pairs.

The candidate is unchanged V9. The control is original `mgt_m1`. V9 reconsiders at days 12, 15 and 18, commits an admitted route for three days, then resumes native routing. The production agent was not changed or submitted.

## Results

Margin means our final cash minus the opponent’s final cash. All deltas below compare V9 with the original m1 control in the same world.

| Opponent panel | Pairs | Better / worse / same | Mean margin change | Mean own cash change | Control → candidate wins |
|---|---:|---:|---:|---:|---:|
| Live V56 | 32 | 3 / 0 / 29 | +317 | +434 | 20 → 21 |
| Live original m1 | 32 | 4 / 0 / 28 | +543 | +630 | 8 → 11 |
| Rated recordings without major playback failure | 21 | 2 / 0 / 19 | +504 | +726 | 7 → 7 |
| All rated recordings, including broken playback (diagnostic) | 32 | 6 / 0 / 26 | +1,430 | +1,578 | 14 → 14 |
| Additional original-m1 recordings, exact native control | 10 | 2 / 0 / 8 | +665 | +606 | 6 → 6 |

The recorded-opponent rows measure frozen-action counterfactuals, not live-policy win rates. **11/32 playbacks materially failed after their original rival was replaced.** Their inflated margins cannot support opponent-strength claims. All cases are retained for transparency; the subset without major failures is still subject to the opponent’s inability to react.

## Design and fidelity

- 32 fresh IID worlds, each crossed with live V56 and live original m1: 64 pairs. Sixteen worlds use each seat. Each world independently samples eight shops uniformly; both arms see the same seed and shop sequence. This removes the engine’s policy-dependent shop-RNG drift. The same world against two opponents is counted once for uncertainty.
- 32 recordings from eight active opponent submissions rated 2750–3000 at fetch time: four recordings per opponent, two in each opponent seat. Two teams were randomly sampled within each 62.5-point rating stratum. No win/loss filtering was used. All 115 rival-model training episodes were excluded.
- The baseline and candidate each start from day 0. The selector receives only the current public observation and its own memory; the seed, actual future shops, opponent identity and recorded future actions are held by the evaluation harness.
- All 151 frozen source/data dependencies are hashed. Each arm starts in a fresh process. Original m1 opponents have independent globals and player memory. V56 uses its verified `e410_agent` entry point.
- **32/32 recordings reproduce exactly:** final cash and both full observations at day boundaries and the final state, excluding the framework’s timing/step metadata. The shared market, private inventories and farms all match.
- Every evaluated arm must finish all 719 actions, reach DONE in both seats and reconcile its complete cash ledger. The paired action prefix before day 12 must match exactly. No-intervention games must match all actions and both cash results.
- Recorded-opponent counterfactuals preserve that opponent’s recorded weed spawns and actions. The opponent cannot react to new prices or our actions. Board divergence and extra ineffective commands are recorded; more than 40 extra failed commands is the prespecified material-break flag. All cases remain in the full result.

### Rated opponent submissions

Leaderboard snapshot: `2026-09-23T21:48:23.463499+00:00`. Scores below are the selected submission’s score when its public metadata was fetched.

| Opponent | Submission | Rating | Recordings |
|---|---:|---:|---:|
| trantrikien239 | 56497709 | 2757.4 | 4 |
| Smackaveli | 56497826 | 2809.7 | 4 |
| ActiveMusyoku | 56492278 | 2856.2 | 4 |
| ShunkiKyoya | 56446454 | 2819.1 | 4 |
| TheEggman | 56498825 | 2885.0 | 4 |
| Otter Vibe | 56497078 | 2889.6 | 4 |
| Fourth Quadrant | 56497837 | 2951.7 | 4 |
| 吃白饭的大肥鱼 | 56483899 | 2984.3 | 4 |

### Exact-control follow-up

The initial replay panel exposed early opening collapses when the original rival was replaced. We therefore froze an additional panel from games actually played by original m1 (`56395605`). The current public metadata supplied ten qualifying episodes across six opponents, rated 2752.7–2804.4; all ten were included without selecting by reward. This is a follow-up diagnostic, separately reported from the prespecified panel.

**10/10 native controls match the actual recording:** both final cash values, both physical boards at all 719 action boundaries and both private inventory states. A candidate is run only after that exact-control gate passes. After intervention, 0 cases have a major opponent-playback failure and 0 have any opponent board divergence. The opponent still cannot react to our altered sales; full reactive-policy validation remains a separate task.

| Episode | Opponent | Rating | Original margin | V9 margin | Change |
|---|---|---:|---:|---:|---:|
| 111902048 | Evil Mango | 2804.4 | 6,763 | 6,763 | +0 |
| 112109339 | Snorlax | 2774.9 | -25,467 | -25,467 | +0 |
| 112158883 | Xiangyu Liu | 2757.4 | 6,180 | 6,405 | +225 |
| 112445421 | Dieter | 2796.3 | -5,182 | -5,182 | +0 |
| 112483478 | mikelou1 | 2752.7 | 2,741 | 2,741 | +0 |
| 112496304 | mikelou1 | 2780.8 | -3,195 | -3,195 | +0 |
| 112502033 | mikelou1 | 2752.7 | 3,548 | 3,548 | +0 |
| 112543358 | Evil Mango | 2801.0 | -12,635 | -6,214 | +6,421 |
| 112543662 | QQ农场 | 2774.9 | 5,839 | 5,839 | +0 |
| 112600049 | Xiangyu Liu | 2757.4 | 8,797 | 8,797 | +0 |

## Coverage and uncertainty

- **Live panel:** intervened in 7/64 games; 0 games contain more than one intervention. 2/15 original losses improved; 0 became worse. 1 losses became wins; 0 wins became losses. Net deficit recovered among the original losses: +5,061 of 79,095. Mean-margin 95% cluster bootstrap interval: +77 to +879. Resampling unit: world. Intervention types: `{'none': 57, 'change_tape': 3, 'hold_incumbent': 4}`.
- **Recorded panel, no major playback failure:** intervened in 2/21 games; 0 games contain more than one intervention. 1/14 original losses improved; 0 became worse. 0 losses became wins; 0 wins became losses. Net deficit recovered among the original losses: +2,816 of 95,665. Mean-margin 95% cluster bootstrap interval: +0 to +1,187. Resampling unit: opponent team. Intervention types: `{'none': 19, 'change_tape': 2}`.
- **Exact-control follow-up:** intervened in 2/10 games; 0 games contain more than one intervention. 1/4 original losses improved; 0 became worse. 0 losses became wins; 0 wins became losses. Net deficit recovered among the original losses: +6,421 of 46,479. Mean-margin 95% cluster bootstrap interval: +0 to +1,949. Resampling unit: opponent team. Intervention types: `{'none': 8, 'change_tape': 2}`.
- Recorded opponents: 11/32 have a material command break in either arm; 13 have some physical-board divergence. The subset without a material command break contains 21 pairs, with mean margin change +504.

### Search coverage

Accepted commitments by day: `{'12': 7, '18': 5, '15': 2}`. Search counts: `{'decisions': 288, 'native_fallback': 274, 'time_out': 0, 'rollout_calls': 4810, 'pruned_rollouts': 717, 'candidate_routes': 1665, 'scouted': 949, 'expanded': 510, 'all_eight_worlds': 67, 'admitted': 18}`.

Candidate exclusions are diagnostic, not evidence that a profitable repair does not exist:

| Exit point | Candidate routes |
|---|---:|
| four world screen did not advance | 442 |
| scout did not expand | 439 |
| protected cohort or hire failure | 717 |
| eight world cash or risk gate | 49 |

V9 still examines at most seven continuations, expands at most two, and checks eight sampled futures. It cannot synthesize an arbitrary crop/animal plan, and it does not reconsider at days 21 or 24. A no-switch loss can reflect omitted candidates, conservative gates, an inaccurate opponent forecast, or a useful plan missing from the library. This panel does not prove which cause applies without a follow-up search.

## Largest gains and regressions

| Case | Original margin | V9 margin | Change | Own cash change | Selected D12 / D15 / D18 | Major playback failure |
|---|---:|---:|---:|---:|---|---|
| replay-112581606 | 3,995 | 11,759 | +7,764 | +7,641 | `[57, None, None]` | No |
| anchor-112543358 | -12,635 | -6,214 | +6,421 | +5,924 | `[456, None, None]` | No |
| random-03-original_m1 | 0 | 5,590 | +5,590 | +4,949 | `[432, None, None]` | No |
| random-14-original_m1 | 0 | 4,811 | +4,811 | +3,626 | `[None, None, 264]` | No |
| random-15-original_m1 | 1,444 | 5,915 | +4,471 | +9,616 | `[410, None, None]` | No |

**replay-112581606:** sales revenue changes strawberry +13,531, wheat -3,685, carrot -1,964, tomato -636; total spending change +540; rival cash change -123.

**anchor-112543358:** sales revenue changes strawberry +8,332, tomato -2,373, wheat -1,153, milk +931; total spending change +50; rival cash change -497.

**random-03-original_m1:** sales revenue changes strawberry +13,107, carrot -6,786, tomato -2,088, fertilizer +869; total spending change +640; rival cash change -641.

**random-14-original_m1:** sales revenue changes tomato +2,316, wheat +1,686, carrot -694, strawberry +523; total spending change +59; rival cash change -1,185.

**random-15-original_m1:** sales revenue changes wool +6,244, carrot +3,776, wheat -2,751, egg +1,391; total spending change +1,836; rival cash change +5,145.

### Largest untouched original losses

| Case | Original margin | V9 change |
|---|---:|---:|
| anchor-112109339 | -25,467 | 0 |
| replay-112547678 | -12,254 | 0 |
| replay-112540733 | -11,743 | 0 |
| random-24-v56 | -11,047 | 0 |
| replay-112364218 | -10,630 | 0 |
| replay-112565891 | -10,621 | 0 |
| random-02-v56 | -9,979 | 0 |
| replay-112350251 | -9,873 | 0 |

## Local timing

Tested on the shared laptop, one search game at a time. 288 measured reveal calls: mean 2.89s, 95th percentile 6.39s, maximum 26.26s. Maximum observed worker RSS 1.91 GiB.

Each own action is charged together with search; planner imports and own-agent initialization are charged to the first action. The bank starts at 60 seconds and loses max(0, action duration − 1 second). The evaluation framework setup is excluded. Timing-bank exhaustion does not stop these research games: profitability and timing feasibility are separate outputs. This is not the competition’s sandbox or hardware, and serialization/process overhead is not fully emulated.

- Live: 0/64 candidate games exhausted the measured bank; minimum remaining bank 22.46s.
- Recorded: 0/32 candidate games exhausted the measured bank; minimum remaining bank 52.92s.
- Exact-control follow-up: 0/10 candidate bank exhaustions; minimum remaining bank 54.18s.

## Reproduce and inspect

Artifacts: `results/fresh/value_tape_wide_20260923_01a0/`.

- `random_design.json`, `recording_design.json`: outcome-blind sampling and protocol.
- `panel_manifest.json`, `source_manifest.json`, `payload/`: hashes and frozen executable sources.
- `recordings/`, `api_metadata/`: fetched exact actions, observation checkpoints and specific-submission ratings.
- `pairs/`: compact paired results; `arms/`: per-arm ledgers, timing, physical commands and replay validity.
- `decisions/`: every candidate, forecast, risk score and rejection; `actions/`: complete action tapes.
- `summary.json`: aggregated results, cluster intervals and complete unresolved-loss list.

```powershell
$env:PYTHONPATH="$PWD/.venv/Lib/site-packages"
$python="C:/Users/xyygl/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
& $python results/fresh/value_tape_wide_20260923_01a0/run_panel.py --kind all
& $python results/fresh/value_tape_wide_20260923_01a0/summarize.py
& $python results/fresh/value_tape_wide_20260923_01a0/build_report.py
```

The runner resumes existing results and stops for insufficient RAM. Delete no completed evidence when rerunning; use a separate output directory for a changed policy.
