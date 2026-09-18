# Mother-Goose's recorded moves against our frozen benchmark

User request: Mother-Goose is deterministic, so replay its actual recorded action sequence against our
frozen agent instead of approximating its policy — and build the test to expose the confound that a
recorded sequence cannot react to our prices.

**Result: its frozen sequence beats our live agent 30-0 by +12,581 (95% CI +10,299 to +15,069), and by
+15,049 (CI +12,873 to +17,475, 30/30) net of the cost of being a frozen tape. The largest significant
components are its tomato and egg lines; labour and layout are small or negative.**

## Design (`scripts/tape_vs_bench.py`, report `scripts/report_tape_vs_bench.py`)

- Each of Mother-Goose's 30 recorded games (submission 56266758) is re-run with the same seed, its
  recorded shop sequence, and its recorded weed spawns (logged from an exact re-run of the original).
  Its recorded actions play its original seat; `agents/benchmark_frozen_56280048.py` plays the other
  seat **live**, via Kaggle's loader. Our weeds stay random.
- **Validity** is measured per step: whether the tape's board is still byte-identical to the board its
  actions were chosen for, the daily rate of commands that failed (no effect, or aimed at a hand never
  hired), and whether sale requests still fill as they did originally.
- **Calibration arm**: our own benchmark is recorded against Two Coins on the same seed, seat and
  shops, and that frozen tape is replayed against the live benchmark the same way. It measures the cost
  of merely being a frozen tape for a policy equal to ours.

## 1. The confound bites immediately — and it is identifiable

Replayed as recorded, the tape loses **4-0-26, −17,962** and is invalid from day 1 in all 30 games: its
board diverges at step 22 (range 22-25) and 5-7% of its commands fail all season, against 0% in its
original games.

The mechanism is the same in every game. Mother-Goose's opening spends to the last coin (29 cash at the
end of day 0, range 7-33). Our benchmark's step-0 70-unit wheat round trip moves the wheat price, so the
tape's day-0 wheat buy costs about 30 more (range 2-35). It ends day 0 short, **one hire fails on day 1 in
30/30 games**, and it later fails to buy about 1,560 of its planned animals, whose feed/care/collect
commands then fail every day. That result measures a tape with a crippled herd, not the policy.

## 2. Remove that one break, and the tape stays valid all season

A sensitivity test gives the tape seat a small cash cushion at step 0 to absorb the opening price
drift, and **takes the same amount back out of its final cash** before scoring.

| Arm | W-T-L (n=30) | Mean margin (95% CI) | Board identical to its original game all season | Failed commands |
|---|---|---|---|---|
| Tape as recorded | 4-0-26 | −17,962 (−25,791 to −11,217) | 0/30 (diverges step 22) | 5-7% |
| **Tape, cushion 40** | **30-0-0** | **+12,581 (+10,299 to +15,069)** | **26/30** (others to step 157-318) | ~0.1% |
| Tape, cushion 500 | 30-0-0 | +12,821 (+10,464 to +15,387) | 30/30 | 0% |
| Calibration: our own tape | 0-0-30 | −2,468 (−3,075 to −2,019) | 29/30 | same as original |

Paired on seed, seat and shops, Mother-Goose's tape minus our own tape: **+15,049 (CI +12,873 to
+17,475), better in 30/30.**

Three reasons the cushion is not buying the win: it is subtracted from the score; 40 and 500 give the
same result, so money beyond fixing the day-1 break adds nothing; and with it the tape plays exactly the
game Mother-Goose actually played — in 26-30/30 games its board is byte-identical to its recorded game
for all 720 steps. A live Mother-Goose would simply have adjusted its purchase to the price; the
uncushioned tape is the less faithful representation of its policy, not the more faithful one.

The margin is built late. Cash margin by checkpoint (cushion 40): day 9 −673, day 18 −3,487, day 21
+310, day 24 +2,762, day 30 **+12,581**. The tape invests through mid-season and collects in the last
third, which is why an "early valid window" cash comparison would not show the edge.

## 3. Where the +12,581 comes from (same games, net by activity, 95% CI over games)

| Activity | Mother-Goose tape minus live benchmark |
|---|---:|
| **Tomato** | **+4,609** (+2,781 to +6,666) |
| Strawberry | +2,488 (−6 to +5,304) |
| **Egg** | **+2,299** (+1,566 to +3,003) |
| Carrot | +1,626 (−258 to +3,823) |
| Wheat trade (net of wheat bought) | +1,239 (+113 to +2,435) |
| Land (our occasional 4th quadrant; break-even per ablation) | +1,067 (+533 to +1,733) |
| Wool | +792 (−104 to +1,923) |
| Melon (its extra plant) | +711 (+643 to +775) |
| Labour | +610 (+107 to +1,147) |
| Milk | −241 (−1,585 to +1,288) |
| **Fertilizer trade** | **−2,620** (−2,877 to −2,375) |

Factor view (exact Shapley decomposition, same games): labour +610; land and utilisation together
−2,376 (the tape has *fewer* productive tile-days, 1,650 vs 1,677, and does fewer effective actions,
3,327 vs 3,429, at the same travel per action, 0.85 vs 0.86); crop/animal mix +4,064; realised price
+10,113; wheat/fertilizer buying net of resale roughly even.

Realised price is partly volume and partly timing. It sells fewer wool, milk and fertilizer units than
we do (117 vs 144, 194 vs 212, 216 vs 342) and gets better prices on them — mostly less self-glut. On
strawberries the volumes are nearly equal (240 vs 249) and it gets 164 vs 148, selling later (19% of its
strawberries in days 27-29 against our 12%). Its tomatoes arrive from day 18 onward (68 units) where
ours are 21 units, 83% sold in the final three days.

## 4. What this settles

- **The advantage is in the policy, not in reactivity.** A frozen sequence that cannot see our prices
  beats our live, adaptive agent in every one of 30 games.
- **The efficiency explanation does not carry it.** Labour is a real +0.6k; layout is negative. The
  tape holds *less* productive land and does *less* work than our benchmark.
- **The redeployment explanation carries the largest significant share.** Tomato, egg and the extra
  melon together are +7.6k and each is significant; strawberry timing adds a borderline +2.5k.
- **This corrects `docs/efficiency_decomposition.md`**, whose "our benchmark is not a worse farmer in
  Mother-Goose's markets" rested on placing our agent in its seat against a recorded opponent that
  could not react and lost 21.9k as a result. With Mother-Goose's plan intact and our agent live, it
  wins 30-0.

## What this does not establish

- Majkel1337 cannot be tested this way: it is nondeterministic, so no recorded sequence represents it.
- It does not separate demand conditioning from crop level: both sides see the same shops, so the test
  says the tomato and egg lines pay against us, not whether choosing them by demand is what makes them pay.
- 30 games from recent ladder matches; shops are the ones those games drew, not a uniform panel.
- The live Mother-Goose might play differently against our agent than its tape does; the calibration
  arm bounds the tape handicap at about 2.5k for a policy like ours, not for Mother-Goose's.
