# V5 strategic diagnosis and an isolated reveal-feature prototype (corrected window)

This analysis uses completed old-KB115LT V5 live development8 and authorized
modern100 DSM training. It reads no qualification results and runs no games.
The new KB115LT2 baseline needs prospective testing: old service losses need not
persist with the new executor. The most concrete policy defect is that the block
regression uses cumulative shop demand but omits which shop just appeared.

## Losses and costs

| V5 loss | Cash margin | Revenue minus rival | Spending minus rival |
| --- | ---: | ---: | ---: |
| live02 | -2,495 | +2,645 | +5,140 |
| live03 | -999 | +7,654 | +8,653 |
| live06 | -8,893 | +3,536 | +12,429 |
| live07 | -8,043 | -2,968 | +5,075 |

All eight V5 farms pay $4,000 more for land than the V9-lite opponent. Native
modern100 also buys four quadrants, so this observation alone does not justify
returning to three quadrants. Three losses earn more gross revenue than their
rival; a production increase must cover its capital, feed and labour costs.
Live06 spends an extra $3,186 on wheat and $2,595 on wages. Its herd reaches
25–26 at D15–21, compared with modern100 means22.3,22.3,21.7. Other V5 herds are
generally close to the native range; a blanket animal cap has weak support.

Egg delivery stands out as a service assumption to recalibrate. Sum of actual
D6–29 harvested product divided by the policy's calendar prediction is:

| Product | V5 development8 | Native modern100 |
| --- | ---: | ---: |
| Milk | 95.6% | 91.8% |
| Wool | 96.7% | 91.7% |
| Eggs | 79.6% | 92.6% |

The V5 window was corrected after initial reporting: cumulative ledgers use
morning boundaries, so D6–29 output is ledger[30] minus ledger[6]. This correction
does not affect training labels, LOO results, model coefficients or runtime.
These are descriptive output ratios, not causal care efficiency. The calendar
assumes85% effective animal care and does not exactly model delivery, held yield,
retirement or capacity. Native compact harvest records omit fertilizer collection,
so no native fertilizer ratio is claimed. The egg discrepancy suggests that a
model calibrated to native service overvalues extra goose work on old KB, but the
new executor may change this. It is not evidence that every goose is unprofitable.

## Opening counts are already learnable

Leave-one-episode-out comparison uses all100 sources, excluding the held-out
episode from both fit and normalization. At D6 the existing nearest joint block
has MAE0.22 cows,0.16 sheep,0.05 geese,0.81 strawberries and1.47 wheat per three-day
budget. It matches the held-out cumulative demand exactly in92/100 cases. The
fixed-calendar median is much worse. The D6 model should be retained while
execution, funding and timely delivery are repaired.

Exact demand-prefix coverage falls to46/100 atD9,20/100 atD12 and10/100 atD18.
The count regression is useful in these sparser later blocks: D9 wheat MAE2.49
versus3.96 for nearest retrieval, and strawberries1.38 versus2.13. Switching the
whole strategy back to nearest schedules is unsupported by this diagnostic.

Native timing is deliberate. D6–8 mean strawberry plantings are7.34,0.55,0.12;
D12–14 are3.30,0.87,0.10; D15–17 are2.09,0.10,0.01. Later strawberry investment
is concentrated at the reveal, preserving more harvest dates. Tomatoes have a
second planting pulse atD18 (3.92 average), falling to1.09 atD19 and0.15 atD20.
Native wheat exits occur mostly at ages3 (7,258) and4 (5,717), with2,202 at age2;
these are observed cohort exits, not a claim that every exit is a harvest.
The readiness/annual-release investigation remains separate.

## Missing reveal identity

The native sheep expansion label is almost an event response:

| Block | Sources adding sheep | Of those, newly opened Yarn | Ridge false additions on source-zero cases |
| --- | ---: | ---: | ---: |
| D9–11 | 7 | 6 | 12/93 |
| D12–14 | 15 | 15 | 7/85 |
| D15–17 | 10 | 10 | 13/90 |
| D18–20 | 9 | 9 | 22/91 |
| D21–23 | 2 | 2 | 0/98 |

The D9 exception establishes four sheep in a non-Yarn block after an earlier
expansion. A hard rule forbidding all such additions could discard legitimate
unfinished commitments. The implemented prototype therefore uses regularized
features, not a hard no-new-Yarn rule. Already purchased animals are still credited
and placed by the inherited block policy.

An eight-way one-hot vector identifies the just-observed reveal. The complete
all-output fit was examined and had mixed effects. Development-selected deployment
changes only SHEEP-add and STRAWBERRY-plant columns; all other original coefficients
are preserved exactly with zero coefficients for the new features. Retirement
rules and fitted retirement columns, annual counts, cow/geese columns, daily shares,
hands, land and D6 nearest examples are unchanged.

| Output/block | Original LOO MAE | Reveal-feature LOO MAE |
| --- | ---: | ---: |
| Sheep D9 | 0.25 | 0.18 |
| Sheep D12 | 0.20 | 0.16 |
| Sheep D15 | 0.33 | 0.33 |
| Sheep D18 | 0.37 | 0.31 |
| Sheep D21 | 0.06 | 0.13 |
| Strawberry D9 | 1.38 | 1.32 |
| Strawberry D12 | 1.28 | 1.16 |
| Strawberry D15 | 0.91 | 0.81 |

The late sheep deterioration is retained and disclosed. The broader fit would
also worsen D9 wheat2.49→2.64 and D21 wheat4.97→5.19, among other regressions;
these output columns are not changed. All-output, all-block metrics, including
cows, geese, carrots, tomatoes and retirements, are in the diagnostic JSON.
Selecting two outputs after inspecting these metrics makes this a development
choice, not an independent validation or profit result.

## Lifetime and service implications

Remaining production dates matter more than merely reaching the first date.
New sheep atD18 can produce atD24 and27; sheep atD21 have onlyD27 before season
end. The latter still require purchase, seven feed nights and service work.
A blanket late ban would discard the rare high-price new-Yarn opportunity, but
the regressor's extra late false positives deserve scrutiny in the next test.
For strawberries, D15 planting retains D25/27/29; D16 retains D26/28. A one-day
delay can remove a complete harvest. These are engine-calendar feasibility
statements, not value guarantees.

The next separate semantic service gate worth testing would defer at most one
UNBOUGHT animal for one day when observed animals of the same species are already
unfed without retirement intent, while preserving held animals and the block's
outstanding budget. Reconsider it each morning. This could free early capital and
placement work without changing the executor. However it activates mainly during
D9–11 in all eight old V5 games, including winners, so it is not selected or
implemented here. Paid backlog is chiefly an execution constraint, and the
new-KB results should precede such an intervention. No whole-season valuation
number is treated as reliable enough to prove these additions unprofitable.

## Prototype, checks and integration

New runtime module:
`scripts/semantic_strategy_blocks_reveal_20260928.py`.
New model:
`results/fresh/semantic_strategy_20260928/block_model_reveal_modern100.json`.
Instantiate `SemanticRevealBlockPolicy(model_path, config)` with
`reveal_features=True` for the prospective candidate. Omission or false uses the
embedded exact baseline model and is fully OFF. Runtime adds no numpy dependency;
numpy is used only by the separate offline builder.

The current reveal is indexed by current block and observed shop order. A modeled
unrevealed future shop uses a uniform one-hot expectation, and D27 has no new
reveal. No world identity, actual future shop suffix or private rival data enters
the feature. Future forecasts remain assumptions and do not overwrite the actual
block's completion memory.

Seven new tests pass. A static replay of192 saved V5 dawns establishes OFF equality
of the complete proposal, including forecasts; D6 today and memory match in8/8.
Enabled counts change at15 dawns, current retirement decisions match192/192.
An extra strawberry can displace wheat through inherited capacity admission
(two saved dawns), despite unchanged wheat coefficients. Additional sheep can
raise inferred hands. Later forecast or observed cohorts can also change future
retirement quantities and other proposals through the original coefficients.
Only the two fitted output columns are isolated; other realized decisions are
not guaranteed unchanged. These indirect effects are part of the proposed ablation.
Repeated daily requests are unfinished budgets, not repeated actual purchases.

Static memory uses daily observations and prior retirement intent, without
reconstructing hourly public history. It establishes identical-input OFF behavior,
not native action parity or a counterfactual game. No qualification or new game
has been run. Existing base policy, block policy and model files were not edited.
The root's integration also adds compact `policy_input_memory` diagnostic records
and a class selector; those wrapper/harness provenance changes must be disclosed
in the prospective freeze rather than describing the entire artifact as merely
a model-file substitution.

Artifacts under `results/fresh/semantic_strategy_20260928/`:

* `strategic_v5_what_when_diagnostic_v2.json`: source/result hashes, full100 LOO,
  native timing and old-executor cost/service evidence.
* `reveal_feature_static_audit.json`: all192 static comparisons and source hashes.
* `block_model_reveal_modern100_training_manifest.json`: same100 training IDs and
  provenance; previous DSM40 are training for this stage, protocol183 excluded.
* `reveal_feature_prototype_manifest.json`: freeze hashes and integration settings.

Reproducers are `scripts/diagnose_semantic_strategy_v5_20260928_v2.py`,
`scripts/build_semantic_reveal_model_20260928.py` and
`scripts/check_semantic_reveal_static_20260928.py`. They run no game workers.
