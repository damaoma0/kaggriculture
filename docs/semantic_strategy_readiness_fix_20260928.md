# Observed crop readiness in anonymous lifetime assignment

The online adapter correctly counted ready and underfull annual crops, but the
spatial compiler could assign their harvest lifetimes to the wrong initial tiles.
This affected 133 of V5's 192 saved planning mornings (724 initial crop cells:
492 wheat, 228 carrot, four melon). This is a development diagnosis, not an
estimate of recoverable profit.

For example, two D8 wheat crops are present at D11: tile44 holds five units and
tile0 holds two. The adapter asks to harvest one today and the other tomorrow.
The old compiler grouped both crops by type and birth date, then assigned the
longer lifetime to the tile closer to the shed. It consequently harvested and
replanted underfull tile0 while keeping ready tile44 another day.

The corrected adapter attaches a `harvest_not_before` bound to an initial crop
which cannot reach the harvest threshold after today's modeled watering. The
bound uses only that crop's current public yield, fertilizer status and age.
The compiler assigns the most constrained initial crops first, preserving its
existing distance preference within the remaining feasible paths. Future
plantings and lifecycle events remain anonymous. No recorded future tile or
harvest date enters this correction.

The saved-state audit reconstructs all 192 original end boards exactly from the
frozen V5 code. Recompiling with the correction leaves all 192 daily semantic
count rows unchanged and eliminates every observed-readiness mismatch. End-board
labels change on 84 mornings; harvest assignments can also change without a
different label when the same crop replaces itself.

This does not explain all idle workers. Of 362 underfull initial crops scheduled
too early, 293 have a planned replacement, but only three retain the original
cohort at the next dawn. Most premature harvests execute. The observed mismatch
therefore primarily concerns yield and timing, rather than a persistently blocked
target. Full-game value remains untested.

Nine adapter tests and six compiler tests pass. The mixed-readiness regression
checks wheat, carrot and melon in both near/far orientations and verifies input
isolation and unchanged count totals. All 40 original strict D11 plans remain
dictionary-identical to the tested `reuse_strict.json` artifact.

The isolated V7 candidate is based on frozen V5 with only the compiler and online
tile adapter replaced. The broader stock-recovery and extra-hand prototypes are
excluded. V5 and V6 snapshots and all completed games remain unchanged.

Evidence under `results/fresh/semantic_strategy_20260928/`:

- `v5_initial_readiness_audit.json`: original saved-state audit and source hashes.
- `v5_initial_readiness_fixed_audit.json`: corrected assignment and count checks.
- `readiness_fix_stage1_reproduction.json`: unchanged original DSM40 plans.
- `scripts/audit_semantic_strategy_readiness_20260928.py`: diagnostic source.
