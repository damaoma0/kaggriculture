# Causal semantic strategy development — 2026-09-28

Status: development in progress; neither shipping panel has been run. No submission.
The user has selected KB115LT2 as the new executor baseline. The current editable
stack is wired to it with all seven settings from the canonical KB115LT2 arm.
The frozen V8 stack completes all eight live development games: five wins, mean
margin +994.5, complete engine/actions and both ledgers, zero executor/V9 errors,
maximum measured overage21.6501s. Its recorded development panel is running.
Earlier KB115LT measurements remain historical controls.

The preceding strict tile planner passed its DSM40 component gate (26/40 wins,
versus 27/40 with exact source tiling). That experiment supplied future DSM change
counts. This stage must choose those counts from current observations instead.

## Requested gates and input boundary

The user requested at least 30/40 wins against the MGT tape machine and 30/40
against recorded actions of opponents rated 2750–3000. The working defaults are
packaged `mgt_v9lite` and a randomized panel of native recorded seed/shop/script
worlds. Fresh live qualification seeds and recorded qualification cases are frozen
and remain unused. The latter avoids claiming skill against scripts broken by an
unrelated initial world. Native two-tape source controls must reproduce both cash
totals before a recorded case is eligible. The original extra40-command fragility
screen remains in every strict report. The prospective shipping-score addendum
also reports actual technically verified wins against the unchanged scripts;
counterfactual command failures are disclosed separately. Qualification is still
unreleased, and no case is dropped from either denominator. See
`semantic_strategy_shipping_addendum_20260928.md`.

Runtime receives only the official current observation and configuration. The
semantic policy uses revealed shops, observed farm cohorts and ages, our cash and
private goods, public opponent harvest/care/cohort changes, and market inventory.
Unknown future shops are model assumptions. Historical episode IDs, future shop
suffixes, exact donor coordinates and test outcomes are not selection features.

The opening runs through D5. Each D6–29 morning the policy proposes anonymous
changes and hiring counts, the spatial compiler generates full daily tile states,
and frozen KB115LT2 executes them. A later morning starts from the actual farm.
Retirement intent is explicit while the animal still occupies its pen; an
accidental missed feed is not interpreted as an intended retirement.

## Opening and model

Current DSM's D6 board is identical in 95/100 recordings, although raw commands
diverge at step 20 because cash and execution vary. The compact opening adapter
matches coherent opening V5 on 1,152 saved observations from eight seats. Cold
initialization is approximately 0.25 seconds locally. Eight observed D6 handoff
checks preserve actual opening cohorts and board coordinates.

The initial model has 3,456 daily examples from 144 verified older DSM seats
(143 episodes), excluding both the earlier DSM40 and all 183 selected/reserve
recorded cases. Prices and opponent farms are absent from those training traces
and are explicitly missing, rather than reconstructed from unavailable data.
See `semantic_strategy_opening_20260928.md` for provenance and limitations.

## Frozen development observations

`smoke_v1` completed both development panels:

| Panel | Wins | Mean competitive margin | Valid games |
|---|---:|---:|---:|
| Fresh live V9-lite | 1/8 | -6,592.75 | 8/8 |
| Recorded 2750–3000 | 1/8 | -7,240 | 8/8 |

All games reached 720 states with both players DONE, both cash ledgers reconciled,
and no runtime, source-isolation or top-level errors. All eight recorded source
controls reproduced both original cash totals; candidate opponents had zero
additional failed or missing-worker commands. Qualification has not been released.
V1 did not capture caught internal executor error counters or private inventories
in diagnostics; later snapshots add those fields. These omissions do not change
the official observations supplied to the policy.

Observed causes under investigation:

* All eight live D6 plans requested expansion on newly purchased land, but none
  established a crop or animal that day. KB115LT's tier routes are fixed at dawn,
  when those squares were still locked. The original D11 component experiment
  began after expansion and did not exercise this boundary.
* Donor end-state matching sometimes purchased a fourth quadrant well after the
  donor's original expansion date. Investment and wages increased substantially.
* The initial WH4/ME12 release calendar lagged the executor's configured harvest
  behavior. Revised plans use WH3/ME10 with observed low-yield deferral.
* The original market projection included gross wheat production but omitted
  future feed consumption. The corrected projection includes both herds' feed.

Two matched snapshots have completed their natural live development runs:

| Candidate | Wins | Mean margin | Valid games |
|---|---:|---:|---:|
| `strategy_v2_nearest` | 1/8 | -7,144.875 | 8/8 |
| `strategy_v2_unlock` | 2/8 | -5,201.625 | 8/8 |
| `strategy_v3_modern4` | 1/8 | -9,671.75 | 8/8 |
| `strategy_v4_modern4_finance` | 1/8 | -6,623.0 | 8/8 |

`strategy_v2_nearest` caps land at three
quadrants, uses the nearest coherent donor counts, and corrects the crop/calendar
and feed accounting. `strategy_v2_unlock` changes only a configuration flag: after
an observed land unlock it switches to KB115LT's existing bounded hourly
dispatcher until the next morning. It clears stale fixed-route caches and uses
actual worker positions. The KB115LT source itself remains unchanged.

The routing arm establishes new assets on expansion days, but remains below the
requested win rate. A separate fixed-shop A/B development comparison is complete:
both arms have eight valid games and one win. Mean margin changes from
-7,141.875 to -4,078.25, a paired improvement of 3,063.625 (six improvements,
two regressions). Our cash changes by -105.625 and rival cash by -3,169.25.
Every pair uses newly executed controls with identical actual shop schedules;
six controls exactly reproduce their natural reference and two have recorded
timing-driven action differences. All 16 games pass the independent audit.
This small development result supports the execution repair, not the shipping
win-rate claim. Later research includes bounded wheat replenishment,
active-herd retirement counts, early investment funding, and 60 newer eligible
DSM worlds. Those modern recordings all expand to four quadrants on D10; their
targets should also be tested at their intended scale, with expansion execution
working, rather than assuming that the earlier four-quadrant result applies.

These development live runs use natural engine shop draws. Farm changes can alter
the future shop RNG sequence, so differences between variants are not isolated
same-shop causal cash estimates. The final untouched panels decide the requested
win-count gate.

The complete season ledgers also separate income from spending. In the eight
`strategy_v2_unlock` games, our mean revenue exceeds the rival's by 633, but our
mean spending exceeds it by 5,834.625. Wheat purchases account for 3,954 of that
spending difference, animal purchases for 3,212.5, while we buy no market
fertilizer and the rival spends 1,052 on it. Hiring differs by only 203.875 per
game. Thus excessive wages are not the principal remaining deficit in this arm.
Our wheat harvest is 478.5 units versus 582.5, and melon harvest is 60.875 versus
82.125; the latter contributes a 6,049.25 revenue difference. These are
descriptive comparisons between the two farms, not recoverable-profit estimates:
adding output also changes prices and the rival's behavior. Hashed inputs and
all product-level figures are in `development_ledger_decomposition.json`.
Gross wheat purchases should not be labeled a trading loss: the later fixed-B
audit finds 119 days with both buying and selling and 769 matched units, but its
daily average-price spread proxy is -259 in total. It provides no evidence of a
material spread loss; feeding and production balance remain the main questions.

The completed ablation, `strategy_v4_modern4_finance`, changes only the
modern-model candidate's early funding configuration (plus diagnostics and the
optional helper integration). It can release a safe observed shed lot from sales
pacing during D6–10 while today's admitted inputs need money. Its comparison
candidate `strategy_v3_modern4` has completed: all eight games are valid, with
one win and mean margin -9,671.75. Its measured overage is at most 11.045 seconds.
Thus the newer training source and fourth quadrant alone have not solved the
strategy. V4 finishes all eight games valid, with one win and mean margin -6,623;
its maximum measured overage is 11.712 seconds and all eight newly captured V9
internal error counters are zero. Natural shops can differ from V3, so their
3,048.75 mean margin difference is not an isolated same-shop financing effect.

The three-day budget policy `strategy_v5_blocks100_finance` finishes its eight
live development games with four wins and mean margin +242.375. It uses the
modern100 model and V4's funding configuration. All games are valid; maximum
measured overage is 11.982 seconds and all eight V9 internal error counters are
zero. Its recorded-opponent development panel completes eight technically valid
games, with four actual wins and mean margin -617.875. The original strict screen
admits five games and three wins; three cases have material script fragility.
The optional broad
stock-recovery V6 also completes eight valid games with four wins and mean margin
+1,629.625. The natural paired difference is +1,387.25 (five better, three worse;
bootstrap 95% interval -3,646.375 to +5,984.625), but final shops differ in six
pairs. Maximum overage is 11.236 seconds. These development figures do not isolate
a same-shop feed effect and do not meet either shipping gate.

The saved-ledger service audit finds no-intent animal exits fall from 11 in V5
to five in V6; exits before first production fall from four to one. Lost banked
bonuses instead rise from 16 to 33 units. The mix reinforces that survival and
profitable service are distinct. See `service_audit_v5_v6.json`; neither this
comparison nor the audit treats every animal exit as economic harm.

A separate modern100 model is now available for later strategy research. It
adds the previous DSM40 to the 60 newer training worlds and excludes every one
of the 183 new recorded development/qualification/reserve cases. Reusing those
40 is legitimate training for the separate stage-two gate, but any later result
on the old DSM40 must be labeled training evidence. The frozen modern60 model
and its running candidate remain unchanged. The new manifest explicitly records
that reuse; qualification outcomes remain unobserved.

Two exact replay-shadow traces now identify a separate feed execution defect.
Both reproduce the original full cash ledgers and all 30 dawn states; candidate
actions match for all 192 and 216 inspected calls. A tier route advances past a
partial wheat pickup (2/5 or 1/3), leaves the shed under-supplied, and later skips
mandatory feeds without refilling or reassigning them. The affected animals have
no retirement intention and remain in the plan lookahead. The next optional
repair switches to the existing rolling dispatcher after that recorded failure,
only during D6–10 and only when no exact retirement is active. Two bounded
continuations reproduce the original action prefixes, then rescue all three
diagnosed animals with feeding and care. One continuation costs 33 additional
cash at the next morning; the other also changes sales and animal purchases.
These are mechanism tests, not full-season profit estimates. The frozen
`strategy_v6_blocks100_recovery` adds this recovery to V5; all other sources and
its model remain identical. See `semantic_strategy_service_audit_20260928.md` and
`service_shadows/` for the hashed evidence.

The separate D6 oracle fixture initially omitted locked cells from its initial
tile dictionary. Preflight caught the resulting possibility of allocating into
future quadrants before any retile games ran. That arm is held for corrected,
versioned inputs and a per-placement land-purchase check. This export issue does
not affect the online adapter, which explicitly records all current locked
cells, or the completed DSM40 D11 experiment, whose farms had all four quadrants.

The corrected D6 diagnostic is complete: exact layouts win 4/8 with mean margin
-3,238.625; retiled counts win 3/8 with mean margin -3,616.5. Paired retile-minus-
exact margin is -377.875 (three better, five worse), with own cash +102.875 and
rival cash +480.75. All 16 candidate games and eight native source controls are
complete and ledger-verified. This is a small, selected training diagnostic,
not the stage-two shipping test. Valid exact/source controls were reused with
explicit hash binding in `oracle_diagnostics/d6_exact_vs_retile_locked_v4/`.
No game used the invalid unlocked-land export. All 40 corrected inputs now
compile; an additional newborn-retirement edge case is supported without
changing any of the eight frozen diagnostic plans.

Compared with original native DSM, the exact-layout executor loses 20,977.25
mean margin in those eight worlds: own cash -3,549 and rival cash +17,428.25.
Early collections at D11 are close to the source, but subsequent output and
delivery differences create a large opponent price effect. Rival daily physical
production is identical in all eight worlds. Its daily wool, strawberry and
milk sold quantities are also identical; those goods contribute verified price
gains of +6,214, +4,926.25 and +4,067.25 mean revenue, respectively. Together they
account for 85% of the rival's additional revenue. This is a per-world/day check,
not an inference from pooled average prices. The audit explicitly allows the
engine rule that $1 sales do not add market inventory. See
`oracle_diagnostics/d6_exact_vs_retile_v3/exact_vs_source_product_audit.json`.
This prevents treating the quantity model as the only remaining deficit.
Qualification remains untouched.

A separate public-readiness bug is now fixed: the adapter computed different
harvest dates for ready and underfull same-age crops, but the compiler could
permute those lifetimes between their initial tiles. The frozen V5 saved-state
audit reproduces all 192 daily plans and finds mismatches on 133 mornings. The
correction preserves every daily count and eliminates those mismatches, while
all 40 original DSM40 plans remain identical. Most premature harvests actually
executed, so this is primarily a yield/timing problem, not an explanation of all
idle labour. An isolated V7 comparison will change only the compiler and adapter
on the frozen V5 base. `strategy_v7_blocks100_readiness` completes eight valid
live games, three wins and mean margin -834.25. All eight final natural shop
sequences differ from V5; its -1,076.625 paired mean difference is not an isolated
same-shop readiness effect. See
`semantic_strategy_readiness_fix_20260928.md`.

After the user's baseline change, `strategy_v8_kb115lt2_readiness` copies V7 and
changes only the executor bytes and seven canonical recipe settings:
collect-at-floor1, polish3000/final1/exchange0.2/water-charge20, learned2 dawn,
and deferred animal-harvest fraction0.3. The pooled causal pace table and D6
handoff remain unchanged. V6 broad stock recovery, extra hands and the optional
market gate are absent. Manifest SHA256:
`f5133c24fdf845874c4fb3ba66760dfb3fe4eee3ee30a64b07fcc28364c56f5f`.
This is a new causal-stack test; the separate published KB115LT2 oracle-tiling
result does not establish its causal planner's strength.

V8's paired natural-world difference from V7 is +1,828.75 mean margin, six better
and two worse (bootstrap95 +761.625..+2,980.625). Shops differ in seven pairs, so
this is whole-stack evidence rather than an isolated same-shop executor estimate.
The normal1-second allowance and60-second bank remain enforced. A separate V9
reveal-feature candidate is frozen for the next development ablation; neither
shipping panel has been released.

Two further exact replay shadows identify why some V5 workers idle despite
available seeds. Their current routes begin with feeding, but those workers and
the shed have no wheat. Other workers hold enough wheat to satisfy the market
helper's global demand estimate, so it buys nothing despite ample cash. One
worker waits at the shed from H12 through H21; another waits on an animal tile
from H15 through H21. Both 264-call shadows match original actions and all cash,
ledger and dawn states. A bounded route-local replenishment repair is under
mechanism testing; it is absent from V7.

An optional market-admission prototype remains OFF. Its initial arithmetic
omitted the persistent effect of new inventory on later existing sales. A
separate corrected valuation module and five targeted tests now cover that
effect. The corrected static gate still activates on only three saved fixed-B
mornings and none of the natural-V3 mornings; these are requests in saved states,
not executed counterfactual purchases. It cannot explain the opening deficits.
Current dated semantic-strategy tests pass104/104, including reveal-feature,
scoring-addendum and technical-failure checks.

## Files and reproducibility

* Entry: `agents/semantic_strategy_20260928.py`.
* Quantity policy: `scripts/semantic_strategy_policy_20260928.py`.
* Online compiler adapter: `scripts/semantic_strategy_tiles_20260928.py`.
* Opening: `scripts/semantic_strategy_opening_20260928.py`.
* Harness and protocol usage: `docs/semantic_strategy_gate_20260928.md`.
* All frozen candidates, input hashes, actions, ledgers and reports:
  `results/fresh/semantic_strategy_20260928/`.

Source changes are frozen before each run; Windows workers never import an
editable candidate. Local execution only, at most four game workers globally and
currently one worker to accommodate V9-lite's memory use.
