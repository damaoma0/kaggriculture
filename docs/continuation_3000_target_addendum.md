# Continuation 3000 target addendum

`promotion_protocol.json` is frozen byte-for-byte and remains the v1 promotion protocol. Its V56 gate was an improvement threshold: a mean win score of at least 0.60 and a clustered 95% lower interval above 0.50. It was not evidence for a 3000 Kaggle rating.

`results/fresh/tape_gap_plans/promotion_protocol_3000_v2.json` is a hash-checked overlay of that parent. It keeps the 128 natural worlds, the two seats per world, and all 64 historical UMG worlds and controls. The checker clusters both seats within each natural seed; they are not treated as 256 independent worlds. Scores are win = 1, tie = 0.5, loss = 0.

The v2 arithmetic assumes V56 is rated 2750 and uses the standard Elo scale of 400. The expected score of a 3000-rated agent against that opponent is `0.8083176725494586`. V2 therefore requires an observed mean score at least that value and the lower endpoint of its clustered two-sided 95% bootstrap interval to be strictly above it. The practical pre-run target is about 90% observed score over the 128 independent world clusters, so sampling uncertainty can still clear the stricter lower-bound gate.

This is still a named-opponent qualification gate, not a guarantee of a Kaggle 3000 rating. The inherited original-tape, repaired-opening, source-hash, timing, ledger, and readiness requirements all remain mandatory. A dedicated untaped stress panel is also required before a 3000 claim, but it is deliberately neither frozen nor run here. This addendum records no gameplay results.
