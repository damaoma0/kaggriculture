# Optional animal market admission gate

The gate is implemented and **OFF by default**. It is a small experimental veto,
not a solution to the policy's large development deficits. No games were run.

`scripts/semantic_strategy_market_admission_20260928.py` provides the pure
`gate_unbought_animals(state, target, admitted, config, history)` helper. The block
subclass calls it only with `animal_market_gate=True`, after ordinary admission,
and reruns ordinary admission if its internal target changes. The base policy,
model and frozen v5/v6 snapshots are unchanged.

The fixed initial rule starts no earlier than D12 and withholds at most one
unbought animal from a daily plan. It requires a marginal competitive estimate
below **−$300 in all nine scenarios**: unrevealed demand at 0.5/1/1.5 times the
prior expectation, crossed with output of the visible rival farm at
0.5/1/1.5 times its model. Observed shops and current market inventory remain
fixed. The additional animal receives full care and delivery, and incurs no
incremental labor charge in the calculation; these favorable assumptions make
the veto more conservative. The −$300 buffer is declared before the static
activation check and was not tuned to its results.

This is not an upper bound over every possible future. It omits unknown rival
rotations, hidden stocks and strategic selling, and its delivery calendar is an
approximation. The buffer and scenario grid reduce confidence errors but cannot
prove that a veto improves realized margin.

Already bought animals in shed or hands bypass the gate. It does not remove
existing animals, change retirement intentions or consume the block's budget.
Only actual observed births complete jobs. A withheld unit is reconsidered on a
later morning while its block remains active. The gate cannot widen its D12 or
one-unit limits through configuration; later start dates, fewer units and larger
loss buffers are permitted.

The static audit uses the same 384 development observations as the block shadow
diagnostic. Gate OFF reproduces frozen v6's complete proposals, diagnostics and
memory exactly on every observation. Gate ON activates on three fixed-B mornings
(the same outstanding sheep request on consecutive days) and zero natural-v3
mornings. There are21 and17 eligible unbought-species decisions respectively.
Most negative unit estimates belong to animals already bought and intentionally
remain protected. These are off-policy requests, not three demonstrated avoided
purchases or a profit estimate.

The subsequent arithmetic correction includes the persistent effect of added
market inventory on later own and rival sales, including days without new
production. The original formula counted only each production day's incremental
price change. The corrected audit retains the same three/zero activations and
384/384 OFF equivalence. The original audit and source snapshot remain under
`market_admission_static_audit.json` and `research_snapshots/market_admission_v1/`;
use `market_admission_persistent_static_audit.json` for the corrected formula.
The cohort-ranking diagnostic changes the highest-valued species on 21/384
saved mornings, but it does not change an active policy or establish profit.
Incremental feed's price effect, hourly delivery timing, suppression of inventory
increases on $1 sales, and future rival rotations still remain outside this
approximation. In particular, the daily model can retain excess inventory which
the engine would discard at the price floor. It remains a research diagnostic.

Six gate regression tests pass: default/off equivalence, hard bounds, prepaid
shed/carried animals, uncertainty threshold, observed-success carryover, and
causal public-state sensitivity with identity/future poisoning. Five separate
persistent-inventory tests cover later rival sales, own-price harm, cancellation,
no double counting, and single-unit/bundle consistency. Full semantic strategy
discovery passes 97 tests; the separately discovered same-day newborn retirement
case is fixed in the tile compiler, and all 40 corrected D6 inputs compile.

Evidence and exact hashes:

- `results/fresh/semantic_strategy_20260928/market_admission_static_audit.json`
- `results/fresh/semantic_strategy_20260928/market_admission_prototype_manifest.json`
- `results/fresh/semantic_strategy_20260928/market_admission_persistent_static_audit.json`
- `results/fresh/semantic_strategy_20260928/persistent_market_value_diagnostic.json`
- `scripts/check_semantic_market_admission_20260928.py`
- `tests/test_semantic_strategy_market_admission_20260928.py`

The next priority remains early execution and funding: this gate's sparse
activation cannot account for the observed opening deficits.
