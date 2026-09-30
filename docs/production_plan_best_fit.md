# Current selection versus best-fitting production plans

Audit date: 22 September 2026. Baseline: submitted `mgt_m1` (56395605).

There is substantial room to improve matching to the revealed demand scenario.
However, much of that room requires a different production history, not just
different tile positions. A better match is not yet evidence of higher profit.

## Direct comparison

Compared the **actual selected tapes at 430 checkpoints in 86 recorded m1 games**
(days 12, 15, 18, 21 and 24) against **all 584 tapes embedded in the same agent**.
The saved m1 replay traces reproduce both players' recorded final cash in all
86 games. Their recorded switches identify the tape in use at each checkpoint.
The current agent file is byte-identical to the archived submitted file.

The primary alternative minimizes the existing revealed-demand-history score,
removing the coordinate mismatch gate, coordinate score and animal-stranding
penalty. Aggregate crop/animal count distance breaks demand-score ties. The
original small common-prefix preference remains in selection; the table reports
the demand component without that preference. No future shop, donor reward,
future output or future action enters retrieval.

| Selection rule | Different tape | Mean demand-history mismatch | Reduction | Mean difference from our current asset counts |
|---|---:|---:|---:|---:|
| Actual m1 selection | — | 20.28 | — | 2.46 |
| Best fit, asset-count distance no worse than current donor | 18/430 | 20.15 | 0.6% | 2.43 |
| Allow up to 4 additional units of asset-count distance | 109/430 | 19.30 | 4.8% | 3.10 |
| Allow up to 8 additional units of asset-count distance | 228/430 | 17.38 | 14.3% | 5.31 |
| Best fit, no asset-count restriction | 349/430 | 12.40 | 38.9% | 14.62 |

The demand score uses the current agent's product weights and revealed-history
checkpoints. Its units are weighted demand differences, **not coins or percentage
profit losses**. Asset distance sums absolute differences across five crop and
three animal counts; replacing one wheat plant with a carrot contributes two.
The sensitivity limits are descriptive count limits, not investment budgets.

The unrestricted alternative has strictly better demand-history fit in
**345/430 cases (80.2%)**. Of its 349 changed choices, 310 exceed the current
eight-tile mismatch limit. But its average asset-count difference is also much
larger: **14.62 versus 2.46**. Removing positions alone does not make these farms
equivalent.

## How different are the production plans?

Across all 430 checkpoints, the unrestricted history-fit alternative differs
from the selected tape by:

- **8.13** in total next-three-day crop-count L1: 3.67 wheat, 2.99 carrots,
  0.94 tomatoes and 0.53 strawberries on average; melon planting is unchanged.
- **10.90** when planting day is retained in that comparison.
- **3.59** in recorded herd-count L1 at the next three-day boundary.

These are absolute differences, not extra production. Crop counts are intended
`PLANT` commands in the stored tapes. They have not been executed on our current
farm, and the terminal herd counts describe the donor's recorded farm.

| Start day | Current history mismatch | Best unrestricted history mismatch | Next-three-day crop-count L1 difference |
|---|---:|---:|---:|
| 12 | 3.40 | 2.05 | 6.27 |
| 15 | 10.37 | 6.45 | 6.29 |
| 18 | 20.52 | 12.40 | 6.76 |
| 21 | 32.59 | 19.33 | 10.65 |
| 24 | 34.54 | 21.77 | 10.70 |

## If “scenario” means the shops open now

A separate alternative ranks current cumulative product demand first, asset
counts second, then the existing history score. It gives a different answer
because the original score also favors earlier demand history.

Current-demand mismatch falls **9.30 → 1.34 (85.6%)**; 408/430 tape choices change,
and 407 have strictly better current-demand fit. Exact current-demand matches
rise from **17 to 199**. However, average asset-count distance rises to **20.60**,
and history mismatch slightly increases, **20.28 → 20.57**. This is not a free
improvement to every notion of fit.

Concrete example: episode **111324137**, day 21:

| Plan | Next-three-day intended planting | Difference from our existing asset counts |
|---|---|---:|
| Actual selection, UMG 109560171 | 36 wheat, 0 carrots | 0 |
| Best existing-history fit, UMG 109568816 | 17 wheat, 15 carrots | 23 |
| Best current-demand fit, UMG 110372518 | 22 wheat, 17 carrots | 18 |

The third donor has the same revealed shop multiset as the scenario, in a
different order. Its planting calendar illustrates the production decision we
could borrow, while its differing inherited farm explains why copying the whole
tape is a separate execution problem.

## Interpretation and limits

The evidence supports retrieving crop/herd intentions independently of tile
arrangement, then evaluating their incremental value and connection cost on our
actual cohorts. It does not establish that our current planting quantities are
economically wrong, or that a demand-matched leader plan beats the current plan
against our opponent. Opponent supply and market saturation can change the answer.

“Best” here is an exhaustive optimum of a stated retrieval metric within the
584-tape library. It is not an optimal production plan or a cash-regret estimate.
Compact board labels omit crop ages, held yield, animal care, resource budgets and
work feasibility. Alternatives were queried at unchanged baseline states; no
alternative policy was rolled forward or benchmarked. The saved traces match
both final cash totals but do not retain source/action hashes, so that check is
weaker than action-by-action trace verification.

The previous nearest-continuation study used 105 rich donors, whereas this audit
uses the full embedded 584-tape library. Its larger donor-state gaps must not be
read as the current selector's measured gap.

The next useful performance experiment is to transfer just the next-window
investment intentions, preserve existing cohorts, and measure executed cash and
production against unchanged m1. No competitive agent or submission was changed.

## Reproduction

- Script: `scripts/audit_production_plan_fit.py`.
- Full checkpoint rows, source/trace hashes, fixed ranking definitions and
  sensitivity summaries: `results/fresh/production_plan_fit/audit.json`.
- Run: `.venv/Scripts/python.exe scripts/audit_production_plan_fit.py`.
- Assertions check all 584 donor IDs, all 430 checkpoint rows, all 86 replay cash
  pairs, zero saved router errors, identical archived/current agent source,
  exhaustive score dominance and the aggregate-count restriction.
