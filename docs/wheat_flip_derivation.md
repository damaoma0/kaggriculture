# The opening wheat flip: derivation, simulation, and the opening it gates

User question: "It's been verified that 5 is the Nash equilibrium for the wheat flip minigame? You can
confirm this mathematically, and since both sides do the same opening, price changes are symmetric."
Follow-up objection: the 70-unit flip may block *us* from running the Mother-Goose-style opening, so the
flip and the opening must be tested together.

## What each side actually trades (all 30 of her games identical, executed positions verified)

| | Turn 0 | Turn 1 | Wheat held after turn 1 |
|---|---|---|---|
| Mother-Goose | BUY 13, BUY 5, SELL 13 (a 13-unit round trip, keeps 5) | SELL 5, BUY 5 (a 5-unit round trip) | 5 |
| Our benchmark (V45) | BUY 70, SELL 70 | SELL 13 (fails: holds nothing), BUY 5 | 5 |
| V48 | BUY 7, SELL 2 (keeps 5) | BUY 30 at index 0 (sold back turn 2) | 5 (+30 in transit) |
| Raw public-router tape under V45 | BUY 13, BUY 30, SELL 30 | SELL 13, BUY 5 | 5 |
| Certified equilibrium | BUY 5, keep | — | 5 |

Correction to an earlier report: her turn-0 orders are a modified version of the raw public tape, not
the tape itself.

## Derivation

**Engine facts, read from `kaggriculture.py`.** Below the neutral inventory, the wheat price is
`p(d) = round(25 + √d)`, d = 10,000 − market inventory (base 25, T 400, sqrt shape, target 0.8, so the
amplitude is 0.8·25/√400 = 1). A BUY quotes the post-buy inventory `p(d+1)`; a SELL quotes the current
one `p(d)`. Orders are matched by list index, and within an index both players quote from the same
pre-round inventory and then each commit one unit per round.

**The flip game.** Each side submits `[BUY q, SELL q]` on turn 0. With a = min(q_A, q_B) and
b = max(q_A, q_B): in buy rounds r ≤ a both buy at `p(2r−1)`; in rounds a < r ≤ b only the larger buys, at
`p(a+r)`. In sell rounds r ≤ a both sell at `p(a+b+2−2r)`; after that only the larger sells, at `p(b+1−r)`.

    π_small(a,b) = Σ_{r=1..a} [ p(a+b+2−2r) − p(2r−1) ]
    π_large(a,b) = π_small(a,b) + Σ_{r=a+1..b} [ p(b+1−r) − p(a+r) ]

**Verification.** The closed form matches the engine exactly in 178 of 196 cells of a 14×14 grid. The 18
mismatches are all at q = 100, where the engine stops a purchase when cash runs out (100 units at 30-40
coins exceeds the 3,000 starting cash); the capital constraint binds only above about 85 units.

### Result 1 — the symmetric flip nets exactly zero, for every q

In the symmetric case π = Σ_{k=1..q} [p(2k) − p(2k−1)]. `round(25 + √d)` steps up only when √d crosses
k + ½, i.e. at d = k² + k + 1, which is **always odd** (k² + k is even). Symmetric buys land on odd
shortages (2r−1) and symmetric sells on even ones (2k), so every pair lands on the same price. The
cancellation is exact, not approximate, and the engine confirms it: +0 for every q from 0 to 100.

### Result 2 — best response is about half the opponent's size

| Opponent flips | Best response (cash) | Gain | Best response (margin) | Margin gain |
|---:|---|---:|---|---:|
| 70 | 29-35 | +96 | 28-36 | +188 |
| 35 | 16 | +35 | 15 | +68 |
| 13 | 6-8 | +8 | 6 | +15 |
| 5 | 2-4 | +2 | 3 | +4 |
| 2 | 1 | +1 | 1 | +1 |
| 0 | anything | 0 | anything | 0 |

### Result 3 — in the pure flip game the equilibrium is 0 (or 1), not 5

The only symmetric pure Nash equilibria for q in 0..100 are **q = 0 and q = 1**, under both own-cash and
margin utility. A 5-unit flip is exploitable: a 3-unit flip takes 4 from it.

| Flip size | Worst margin against any other flip size |
|---:|---:|
| 0 | 0 |
| 1 | 0 |
| 2 | −1 |
| 5 | −4 |
| 13 | −15 |
| 35 | −68 |
| 70 | −188 |

### Why "5" is still right

The flip model omits the **feed requirement**: each side must end the opening holding 5 wheat. With it,
the certified equilibrium (`docs/wheat_flip_equilibrium.md`, 1,107 engine comparisons over all ten-order
wheat queues) is to **buy 5 on turn 0 and keep them**. So 5 is the right number as the quantity traded in
equilibrium; the speculative round trip on top of it should be zero. It is not a discreteness or capital
effect — the capital constraint binds only near 100 units.

## Side effects: the flip's value is all in them

Because the symmetric flip nets exactly zero, a flip only matters through asymmetric interactions. Against
Mother-Goose's opening (her feed purchase sits at index 1, inside our flip's price peak), our flip is a
**pure transfer**: every coin we gain in the two opening turns, she loses.

| Our flip q | Our gain | Her extra opening cost |
|---:|---:|---:|
| 5 | +9 | +9 |
| 6 | +10 | +10 |
| 7 | +15 | +15 |
| 8 | +16 | +16 |
| 10-15 | +18 | +18 |
| 20-25 | +23 | +23 |
| 30-40 | +28 | +28 |
| 45-50 | +33 | +33 |
| 60-70 | +38 | +38 |
| V48's turn-1 BUY 30 | — | +19 |

So 70 is not over-trading: against her it is profitable spoiling, and against another 70-flipper it is
exactly neutral. Its only cost is exploitability by smaller flips (−188 worst case).

### Derivation vs simulation: they agree

| Claim | Derivation | Simulation |
|---|---|---|
| Symmetric flip nets 0 | Exact for every q (Result 1) | Our flip-70 agent against the flip-70 benchmark: 0-29-1, −4 (−12 to 0); the one loss is a weed-spawn divergence late in the season, not the flip |
| Flip 0 against a 70-flipper nets 0 | π(0, 70) = π(70, 0) = 0 | Our flip-0 and flip-70 cells are identical on every recorded field in 30/30 worlds, in both rows of the cross-test below |
| Flip 5 against a 70-flipper gains 31 | π(5, 70) = 167 − 136 = +31 | Our cash at the end of day 0 is +31 higher in 30/30 worlds |
| Nash 5 (buy 5 and keep) against a 70-flipper costs the same as the tape's turn-1 feed purchase | Same five quotes | Cash identical at the end of day 0 in 30/30; final margin +1 in 30/30 |
| Flip ranking against the frozen benchmark | 35 > 5 > 0 ≈ Nash 5 (best response to 70 is about 29-35) | Earlier self-play panel: 35 wins +1,375, flip 5 +234, Nash 5 +1 (all 32-0) |

The simulations add one thing the flip model can't show: the flip's value sits almost entirely in what it
does to an opponent whose plan has no cash slack.

## Opening × flip cross-test: does the flip stop us running a Mother-Goose-style opening?

User hypothesis: a 70-unit flip loses us money and raises the wheat price for both sides, so while it
spoils her budget-exact opening it may also make that opening unaffordable for us.

**Setup.** We play in Mother-Goose's seat in each of her 30 recorded worlds, with her shops forced, against
the live frozen benchmark (which flips 70). Rows:
- **Current opening:** our V45 chassis, live, with the turn-0 wheat orders set to each option.
- **MG-style opening:** her recorded plan (deferred commitment and everything after), with only her
  turn-0 wheat orders replaced; her own 13/5/13 is kept as a fifth cell. Her weed spawns are replayed and
  there is no cash cushion.

Cash is in coins at the end of engine day 0 (step 24), the end of day 1 (step 48) and the start of day 12
(step 288). "Plan intact" means her board matches her original game byte for byte all season. Script:
`scripts/opening_flip_cross.py`; table: `scripts/report_opening_flip_cross.py`.

| Opening | Turn-0 wheat | Cash end d0 | Cash end d1 | Cash d12 | Hire fails d1 | Plan intact | W-T-L | Margin vs benchmark (95% CI) |
|---|---|---:|---:|---:|---:|---:|---|---|
| Current | flip 70 (= benchmark) | 22 | 81 | 14,240 | 0/30 | n/a | 0-29-1 | −4 (−12 to 0) |
| Current | flip 5 | 53 | 113 | 14,207 | 0/30 | n/a | 29-0-1 | +19 (−403 to +233); median +234 |
| Current | flip 0 | 22 | 81 | 14,240 | 0/30 | n/a | 0-29-1 | −4 (identical to flip 70) |
| Current | Nash 5 | 22 | 81 | 14,240 | 0/30 | n/a | 29-0-1 | −3 (+1 over flip 70 in every world) |
| MG-style | her 13/5/13 | **5** | 154 | 12,478 | **30/30** | **0/30** | 4-0-26 | **−17,962** (−25,647 to −11,002) |
| MG-style | flip 70 | 22 | 147 | 14,592 | 0/30 | 27/30 | 30-0-0 | **+12,710** (+10,472 to +15,259) |
| MG-style | flip 5 | 53 | 179 | 14,575 | 0/30 | 27/30 | 30-0-0 | **+13,140** (+10,924 to +15,664) |
| MG-style | flip 0 | 22 | 147 | 14,592 | 0/30 | 27/30 | 30-0-0 | +12,710 (identical to flip 70) |
| MG-style | Nash 5 | 22 | 147 | 14,592 | 0/30 | 27/30 | 30-0-0 | +12,711 |

In her original games she ended day 0 with 29 coins on average (range 7-33) and started day 12 with 16,305.

### Answer: no — the MG-style opening is affordable at every flip size, including 70

- **A 70-flip costs us nothing against a 70-flipper.** It nets exactly 0 (Result 1), so her plan with a
  70-flip ends day 0 with the same 22 coins as with no flip at all. It loses no hire, keeps her board
  byte-identical all season in 27/30 worlds, and wins 30-0 by +12.7k. The other 3 worlds diverge on
  days 6-13. The same 3 diverge at the same steps under flip 5 and under a 40-coin cushion, so the cause
  is not cash.
- **What breaks her opening is her own turn-0 orders**, not the flip size. Against a 70-flipper her
  13-unit round trip and her index-1 feed purchase trade inside the flipper's price peak. That costs her
  17 more coins than doing nothing (22 → 5 at the end of day 0) and loses a hire on day 1 in 30/30 worlds:
  a +30.7k swing (+24.7k to +37.8k). This is a weakness of her order structure. It doesn't carry over to us
  if we run her plan, because we choose the turn-0 orders too.
- **Affordability through day 12 is not the constraint.** Under the same flip, her plan holds +352 more
  cash than our current opening at day 12 (+151 to +549). Both openings end day 0 with the same 22 coins.
- **Flip 5 is a small, separate gain against a 70-flipper under either opening**: +31 coins on day 0 in
  every world. That becomes +430 final margin under her plan (+213 to +792, 28/30 positive) and a median
  +234 under ours. Against V48, which opens Nash-like, no opening variant helps (all 0-32; see
  `docs/preemption_feasibility.md`).

So the flip and the opening do not interact, and the flip does not gate the opening. Adopting a
Mother-Goose-style plan and choosing the flip size are separate decisions: the plan is worth about +12.7k
against the benchmark in her worlds (tape form), and the flip is worth 0 to +0.4k.

Caveats: the MG-style row is her frozen tape in her own shop worlds, not a live implementation. It
cannot adapt, and it shows her plan is affordable, not that our executor would reproduce it.

## Spoiling threshold: her own opening against our benchmark with a turn-0 flip of q

Her recorded plan with her own 13/5/13 opening, 30 worlds, against our frozen benchmark with only its
turn-0 flip changed (`scripts/tape_vs_bench.py live sp_flipN 0`; no cushion).

| Our flip q | Her extra opening cost | Her cash end d0 | Hire fails d1 | Her W | Her margin vs us (95% CI) |
|---:|---:|---:|---:|---:|---|
| 0 | 0 | 23 | 0/30 | 30/30 | +12,657 (+10,435 to +15,204) |
| 5 | +9 | 14 | 0/30 | 30/30 | +12,458 (+10,269 to +14,979) |
| 6 | +10 | 13 | 0/30 | 30/30 | +12,456 (+10,267 to +14,977) |
| 7 | +15 | 8 | 0/30 | 30/30 | +12,624 (+10,403 to +15,170) |
| 8 | +16 | 7 | 0/30 | 30/30 | +12,618 (+10,396 to +15,164) |
| **10** | **+18** | **5** | **30/30** | **5/30** | **−17,854** (−25,643 to −10,878) |
| 35 | +28 | 5 | 30/30 | 4/30 | −17,806 (−25,561 to −10,870) |
| 70 (benchmark) | +38 | 5 | 30/30 | 4/30 | −17,962 (−25,647 to −11,002) |
| V48 (BUY 7/SELL 2, turn-1 BUY 30) | — | 4 | 30/30 | 3/30 | −18,509 |

- **The threshold is a cliff between flip 8 and flip 10**: her extra cost of +16 (7 coins left at the end of
  day 0) is survivable in all 30 worlds; +18 (5 coins left) loses a hire on day 1 in all 30. Flip 9 (+17,
  6 coins left) is the only size not tested. Her margin barely moves anywhere else: flips 0-8 are all
  about +12.5k, and 10-70 are all about −17.9k.
- **So 70 is spoiling, and 10 spoils her exactly as much.** Against her tape everything the flip does comes
  from crossing the cliff (a swing of about 30k); the coins it transfers (at most 38) don't matter. Above
  10 a bigger flip adds nothing against her, and below the cliff the flip is worth nothing.
- Her own opening is also what leaves her exposed to V48: V48's turn-1 attack, aimed at this lineage's
  index-1 feed purchase, leaves her 4 coins.

Caveat, as before: this breaks her *tape*. Whether her live code re-plans with less cash is unknown; none
of her 30 recorded opponents opened with a flip or a turn-1 attack big enough to test it.

## What this means for the ordering

1. The flip does not gate the opening. We can adopt a Mother-Goose-style plan with any flip size, and
   the choice of flip is independent of it.
2. Against Mother-Goose, a flip of 10 or more breaks her recorded opening (a flip under 10 doesn't), at
   no cost to us. Against a 70-flipper, flip 5 gains +31 on day 0 (+234 to +430 final). Against V48
   no opening choice matters. The flip is a small tactical choice and should not be counted as a way to
   beat either panel member.
3. The +12.7k that her plan earns against the benchmark comes from the plan, not the opening: the
   pre-emption work should follow the plan.

