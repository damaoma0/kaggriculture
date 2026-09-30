# Fresh game fetch and fix evaluation — 2026-09-23

Fetched the newly completed games for both live submissions; no submission was made. All 54 recorded-action replays reproduce both final balances exactly. The candidate tests below use the official local engine and recorded opponents, which cannot react.

| Build | New W–L | New mean margin | All cached W–L |
|---|---:|---:|---:|
| mgt_m1 | 14–11 | -179 | 271–134 |
| mgt_t10 | 12–17 | -3,910 | 345–160 |

These are different, small matchup cohorts; their rates do not establish that one build is better or that the policy itself deteriorated. Inventories are snapshots, so games completed after the fetch are excluded.

## What the losses show

| Mean product revenue gap, us minus rival | 28 losses | 26 wins |
|---|---:|---:|
| WOOL | -7,785 | -2,314 |
| STRAWBERRY | -5,130 | -943 |
| MILK | -2,799 | +3 |
| TOMATO | +2,881 | +3,753 |
| EGG | +1,745 | +1,972 |
| MELON | +2,105 | +1,249 |

These product differences describe realized outcomes, not the profit from adding production. Gross wheat/fertilizer turnover is deliberately omitted from this table: opponents buy and resell those goods. Their purchases must be netted before attributing profit. After netting, losses have a +566 wheat trade gap and a −2,089 fertilizer trade gap. The large gross wheat deficit is therefore not a cause of the losses. All 54 full revenue-minus-expense differences reconcile to the recorded margins.

Across the new cohort, strawberry plots average 17.1 versus 19.4 on day 9 and 21.2 versus 29.8 on day 12. In losses, harvested strawberries per planting average 7.36 versus 7.49, close to the eight-unit ceiling. This supports a cohort quantity/timing and product-mix deficit more than a universal fertilizer failure. Three of the 28 losses have our yield below 7 while the rival reaches at least 7.4.

The new games with three or more Yarn Stores are 2–6, versus 7–7 with none, 15–11 with one and 2–4 with two. Small descriptive strata support investigating wool response; they are not adjusted causal estimates.

### Concrete failures

| Episode / build | Margin | Largest observed production deficit |
|---|---:|---|
| 112543358 / m1 | −12,635 | Strawberry revenue −14,661; 36 versus 47 plantings; 282 versus 344 harvested units. |
| 112561320 / m1 | −12,299 | Wool −13,718 and milk −8,241; three Yarn Stores. |
| 112531372 / m1 | −10,534 | Milk −12,766; the wool deficit is only −1,758. |
| 112512725 / t10 | −25,594 | Wool −33,526; three Yarn Stores. |
| 112573085 / t10 | −27,015 | Broad egg/milk/berry deficits; day-9 berries 19 versus 31 and rival has an extra land block. |

A wool-only patch cannot address the berry- and milk-dominated losses. A day-12 tape change also cannot recover output already missed in the opening.

## Fresh paired candidate tests

### Late-Yarn y2, all 25 new m1 games

Mean paired margin change **+92** (game-bootstrap 95% interval +10 to +190). 9 improve, 1 worsen, 15 are unchanged. Wins: 14 → 15. Losses flipped: 1; wins lost: 0. Worst/best margin changes: -363 / +807.

### Value selector V9, 8 uniformly sampled new m1 games

Mean paired margin change **+1,011** (game-bootstrap 95% interval +0 to +2,474). 2 improve, 0 worsen, 6 are unchanged. Wins: 5 → 6. Losses flipped: 1; wins lost: 0. Worst/best margin changes: +0 / +5,853.

V9 chooses a different tape on 2/24 reveal decisions across 2/8 games. The sample was fixed with seed 230926 before candidate evaluation and includes wins and losses. Replanning uses only each reached observation at days 12, 15 and 18; actual future shops and recorded rival actions are evaluation inputs only.

V9 exceeds 60 seconds of measured cumulative per-turn overage in 0/8 games. This diagnostic excludes initial imports, process/serialization overhead and competition hardware differences, and does not enforce timeouts. It is not a deployment timing certificate.

### Why the fixes help, and what they leave unresolved

V9 rejects 67 of 138 alternative route evaluations because they fail to preserve protected crops or animals. The count is across decisions, not unique tapes. Its small switch count reflects feasibility and value gates; faster search by itself does not provide a new production plan.

In episode **112572245**, V9 selects donor 109534325 on day 15. Own cash rises **3,161**, rival cash rises 928, and margin improves **2,233**. Our egg sales increase by 55 units; hire expense falls 720 and wheat purchases fall 1,298, with other products changing too. The result remains a 4,464 loss.

In episode **112605999**, V9 selects donor 109640231 on day 15. Own cash falls **2,207**, but rival cash falls **8,060**, improving margin **5,853** and turning −252 into +5,601. Our wool sales rise by 47 units; rival wool revenue falls 10,579. In both changed games, the rival sells exactly the same quantity of every product as in the original replay. Thus the measured gain is not caused by losing rival sales volume, although responsive sale timing remains untested.

The y2 mean own-cash change is −4 versus −95 for the rival: nearly all of its +92 margin comes from the opponent-price effect. Its one new win ends at **+2**, too narrow to treat as a reliable live win. The previous historical y2 panel also contained a −3,153 regression; this fresh positive panel does not erase that risk.

**Assessment:** the value selector has demonstrated useful recovery on fresh records, but this eight-game sample is preliminary and its average is dominated by one price-impact win. The late-Yarn layer is a small incremental improvement, not a repair for the main losses. Earlier production allocation and feasible responses to wool/milk demand remain the important unresolved work. Before promotion, test V9 on the remaining fresh games and responsive opponents, and validate a self-contained submission with a time-bank policy.

Full native m1 replays match all 25 recorded results; V9 additionally verifies its native prefix and baseline suffix, and both changed-game economic ledgers reconcile. Source hashes are unchanged through the panel. Bootstrap intervals over these small, potentially related game samples should not be treated as strong live-ladder guarantees.

## Artifacts

- `results/fresh/records_refresh_20260923/manifest.json`: inventory counts and all 54 downloaded IDs.
- `diagnosis.json` and `audits/`: exact replay audits and product/crop/service accounts.
- `fix_design.json`: prespecified samples and source hashes.
- `paired/` and `v9/`: individual candidate results and reveal decisions.
- `summary.json`: machine-readable comparison and per-game improvements/regressions.
