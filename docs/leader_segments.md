# Top two teams: per-segment behaviour and adaptation tests

Snapshot 2026-09-17. **Rank 1 Majkel1337**, 3185.5 (active submissions 56216119 = 3185.5,
56156662 = 3165.3). **Rank 2 Unknown Mother-Goose**, 3129.5 (56266758 = 3129.5, 56266899 = 3067.8).
Yesterday's rank 2, M & M & P & Q, replaced both submissions at 00:24 today (44.2 and 17.6) and has
left the top of the board; its previous submission 56254996 is retained here as a third reference.
Our uploaded agent, 56280048, stands at **2507.3**.
[Leaderboard](https://www.kaggle.com/competitions/kaggriculture/leaderboard). Rankings move.

## What the terms mean (from the engine, not assumed)

- **3-day segment.** `_end_of_day` unlocks one shop when `next_day % townShopUnlockInterval == 0`,
  capped at `MAX_SHOP_INSTANCES = 8` (`kaggriculture.py:867-891`). So shops arrive at the start of
  days 3, 6, 9, 12, 15, 18, 21, 24 — ten 3-day segments, where segment 0 (days 0-2) opens with no
  shop and segment 9 (days 27-29) gets no new shop. Every segment boundary except the last is a new
  piece of demand information.
- **Shop generation.** `rng.choice(sorted(SHOPS))`, drawn with replacement from a `random.Random((seed
  * 1_000_003) ^ day)` stream that first spawns weeds on *both* farms. The draw therefore depends on
  both players' boards, and a shop can repeat (duplicates consume independently).
- **V45 public router.** ahmedberatozer's "V45 First-Turn Wheat Round Trip" notebook: 41 full-game
  719-step action tapes, one selected at step 144 from the ordered pair of the first two shops, plus
  overlay layers. Our upload adds our price-impact sale ordering; its forecast layer is inert because
  the last-callable export picks the parent wrapper (`docs/event_inputs.md`, verified in code).

## Evidence base

52 public episodes downloaded today and **exactly replayed** with the official engine: all 720 states
of both seats reproduced field-for-field and both cash ledgers reconciled, so every quantity below is
a successful transaction or an executed command, not a request. Sample design:

| Group | Games | Purpose |
|---|---:|---|
| Majkel 56216119 vs Mother-Goose 56266758 (head to head) | 8 | both leaders, opponent held fixed |
| Majkel 56216119 vs M&M&P&Q 56254996 | 8 | repeated opponent, varying shops |
| Mother-Goose 56266758 vs Majkel 56156662 | 8 | repeated opponent, varying shops |
| Majkel 56216119 vs 14 distinct high-ranked teams | 14 | varying opponent |
| Mother-Goose 56266758 vs 14 distinct high-ranked teams | 14 | varying opponent |

Each leader therefore has **30 games** (both seats: 15/15 and 16/14). For comparison, our uploaded
agent played **8 live games** (seeds 161000-161003, both seats) against the stock public V45 with the
same instrumentation. Artifacts: `results/fresh/leader_segments/` (per-game segment ledgers,
per-step digests, action logs, `summary.json`, `report.log`), scripts `analyze_leader_segments.py`,
`segment_profile_ours.py`, `report_leader_segments.py`.

Two sampling limits matter. The 52 games are *recent public matches*, so opponents skew to the top of
the ladder and each leader's opponent mix is not identical. And our 8 games are against a near-clone
of ourselves, which distorts any price-level comparison (see §4).

Outcome in this sample: Majkel 18/30 wins, mean final cash 112,283; Mother-Goose 21/30, mean
119,380; ours 8/8 versus stock V45 by a mean margin of **+90 cash** (110,964 vs 110,874), i.e. our
agent and public V45 are the same strength.

## 1. Per-segment behaviour, Majkel1337 (56216119)

Values are means over 30 games with [min-max] when they vary; a bare number means every game agreed.

| Days | Board at segment end | What it does in the segment |
|---|---|---|
| 0-2 | 6.3 wheat [5-10], 1.8 straw [1-2], 11.7 melon [9-12], **2 cow, 3 sheep** | Buys the whole herd on day 0 (2 cows + 3 sheep, every game), plants 12 melons and ~10 wheat, opens 1-2 strawberries already, 16 hires [15-31], sells 10 fertilizer + 4 wheat. Ends the segment on 30 cash. |
| 3-5 | wheat → 0, 8.1 straw [7-10], melon 11.8 | Converts wheat land to strawberries (6.3 planted), 18 hires, still no fertilizer applied; sells 15 fertilizer, 4 wheat. |
| 6-8 | 23.2 straw [14-27], 5.8 cow [4-9], 4.1 sheep [3-10], 1.8 goose [0-4] | **Second land purchase** (1,066 [1,000-3,000]), the herd expands and now varies by game, 15.3 strawberries planted [6-19], 26.7 hires, first wool/milk sales (3,626 + 2,146). |
| 9-11 | 23.1 wheat [14-30], 27.8 straw [14-37], melon → 2.1, 8.5 cow, 5 sheep | **Third land purchase** (1,933 [0-2,000]), melon harvest lands 38.7 units for 8,892, wheat replanting starts in bulk (27.1), hires hit the ceiling of 32-33, first fertilizer applied (1.7). |
| 12-14 | 31.4 straw [14-45], 2.2 tomato [0-10], 3.6 carrot [0-19] | First real crop reallocation: tomatoes and carrots appear in games whose shops want them; 19.2 wheat planted, 15.6 fertilizer applied, 822 commands (saturated), hire spend exactly **696 per segment** from here on. |
| 15-17 | 31.8 straw [11-45], 4.9 tomato [0-17], 3.9 carrot [0-21] | Strawberry harvest peak (49.7 units for 10,256), fertilizer applied doubles to 30.2, planting is now mostly wheat + whatever the shops reward. |
| 18-20 | 24.4 straw [3-37], 6.9 tomato [0-19], 7.3 carrot [0-26] | Strawberries start being cleared (DIG jumps to 9.2), carrots ramp (8.2 planted [0-30]), 82.8 harvests, revenue peak. |
| 21-23 | 29.8 wheat [17-42], 10.6 straw [0-24], 9 carrot [0-31] | Heavy conversion: DIG 15, 31.4 wheat and 10.6 carrots planted; strawberries down to 10.6. |
| 24-26 | 25.5 wheat, 6.2 straw, 18.6 carrot [0-35], 4.5 tomato | Carrot spam (21.5 planted [0-47]), fertilizer applied 33.2, wheat sales 74 units. |
| 27-29 | board emptied: 46.1 empty, 7.7 weeds | Liquidation: 138.5 wheat, 71 carrot, 47.8 strawberry, 26.9 tomato units sold; 17.8% of season revenue. Cash 112,283. |

Constant across all 30 games: the day-0 herd (2 cows, 3 sheep), exactly 3,000 spent on land (2nd and
3rd quadrants only — **never the 4th**), 822 unit commands per mid-game segment, and 696 hire spend
per segment from day 12, which is exactly 11 hires/day (fib 1+1+2+3+5+8+13+21+34+55+89 = 232).

## 2. Per-segment behaviour, Unknown Mother-Goose (56266758)

| Days | Board at segment end | What it does in the segment |
|---|---|---|
| 0-2 | **7 wheat, 12 melon, 3 cow, 2 sheep** (identical in all 30) | A 32-unit wheat buy and 20-unit sale on the opening turns, 13 hires, 366 commands, 110 PASS — a small, fixed, cheap opening. This board is byte-identical to V45's/ours. |
| 3-5 | 3 wheat [3-4], 3.9 straw [2-4], 4 cow [3-4] | Fixed script: 7 wheat + 3.9 strawberries planted, 1 cow, 3 carrot seeds bought, 31 hire spend. |
| 6-8 | 17.1 straw [13-19], 12.7 melon, 6 cow [4-9], 5.3 sheep [4-9], 1.6 goose | **Second land purchase** (1,000 in every game), 13.1 strawberries planted, 4 sheep [2-10], first fertilizer *bought* (1.2 units), 26 hires. |
| 9-11 | 19.2 wheat, 21.3 straw, 1.7 melon, 3.9 goose [0-7], 14 empty tiles | **Third land purchase** (2,000 in every game), melon harvest 71.9 units for 16,044 (the single biggest income event of its season), plants exactly 1 new melon in every game, buys 10 fertilizer. |
| 12-14 | 31.2 straw [18-43], 4.9 tomato [0-15] | The reallocation segment: 9.9 strawberries and 4.9 tomatoes planted, tomato seeds 5.5 [0-15]; 18.1 wheat; fertilizer applied 18.1. |
| 15-17 | 31.9 straw [18-49], 7.8 tomato [0-21], 1.1 carrot | Tomatoes grow on existing land; strawberry harvest 25.5 units; 32.4 hires. |
| 18-20 | 31.8 straw, 9.3 tomato [0-25], 1.9 carrot | Strawberry revenue peak 9,905; tomato/egg/milk sales run in parallel; hire spend reaches the 696 ceiling. |
| 21-23 | 25.3 wheat, 18 straw, 7 carrot [0-29] | Strawberries cleared (DIG 17.8), carrots ramp (7 planted), tomato revenue 2,077. |
| 24-26 | 27.8 wheat, 14.7 straw, 12.5 carrot [0-31] | Carrots 12.5 planted, fertilizer applied 44.2 (its maximum), 56 wheat units sold. |
| 27-29 | 43.3 empty, 11.4 weeds | Liquidation: 161.8 wheat, 69.3 carrot, 45 strawberry, 22.7 tomato units; 17.5% of season revenue. Cash 119,380. |

Constant across all 30 games: the entire day 0-5 build, land at exactly 1,000 (days 6-8) + 2,000
(days 9-11) and **never the 4th quadrant**, the single extra melon in days 9-11, and 11 hires/day
once ramped. Note the high PASS counts (882 per game vs Majkel's 56): Mother-Goose deliberately
leaves worker-hours idle and still outscores Majkel in this sample.

## 3. Adaptation tests

### 3a. Shops — yes, for both, with strong evidence

**Test D (the strongest test: within-game event study).** Unit of observation is (game, segment) for
the eight segments that open with a new shop. Treatment = the newly revealed shop demands crop C.
The segment-index mean is subtracted first, so the seasonal calendar cannot produce the effect;
p-values come from permuting treatment labels within segment index (4,000 draws).

| Crop planted in the 2 segments after the reveal | Majkel | Mother-Goose | Ours |
|---|---|---|---|
| Carrot | **+4.56 plants, p=0.026** | **+3.31, p=0.008** | +0.00, p=1.00 |
| Tomato | **+0.85, p=0.018** | **+1.64, p=0.0007** | -0.73, p=0.42 |
| Strawberry | **+3.23, p=0.0002** | **+3.31, p=0.0002** | +0.00, p=1.00 |
| Wheat (control) | -0.70, p=0.57 | +0.37, p=0.71 | +0.00, p=1.00 |

Both leaders plant more of exactly the crop a new shop wants, within days of the reveal, and neither
changes wheat — the crop whose demand is universal and whose role is feed. Our agent's response is
identically zero by construction.

**Test A (cross-game levels).** Season quantities track the demand composition visible at day 12
(all games have exactly 4 shops then, so this is composition, not count): strawberries planted
rho=+0.93/+0.94, sheep bought +0.89/+0.86, cows +0.72/+0.84, carrots +0.79/+0.74, tomatoes
+0.59/+0.82 (all p≤0.001, n=30 each). Geese are the exception (+0.31 p=0.09; +0.05 p=0.80). Land
spending is 3,000 in every single game for both teams — the one big decision they never condition.

**Test B3 (Mother-Goose's day-6 switch).** Mother-Goose is deterministic (below), so its action
stream can be attributed. Pairs of its games that share the first two shops stay identical **91 steps
longer** than pairs that differ (permutation p=0.002); 155 of 221 differing-shop pairs first diverge
inside the day-6 segment [144,168). That is the V45 `_router` signature — a plan selected at step
144 from `unlocked_shops[:2]`. Our own agent shows the same signature in its 8 games (10/10
differing-shop pairs diverge at step 144, same-shop pairs at step 401, p=0.010).

**Mechanism not identified.** Shops move prices, so "reads the shop list" and "reads prices the shops
caused" both produce these results. Distinguishing them would need controlled observation surgery,
which is impossible without their code.

### 3b. Opponent — no evidence of adaptation; for Mother-Goose, direct evidence against it

**Mother-Goose: clean negative result.** It is deterministic — 0 of 226 same-seat pairs show an
action difference without an observation difference. That licenses attribution, and the five pairs
that share the first two shops but face *different opponents* are decisive:

| Pair | Opponents | Opponent farm differs from | Market differs from | Actions identical until |
|---|---|---|---|---|
| 109712554 / 109887746 | Otter Vibe vs feel the agi | step 1 | step 1 | **step 226 (day 9)** |
| 109712554 / 109990277 | Otter Vibe vs Sida Zuo | step 1 | step 1 | **step 226 (day 9)** |
| 109853557 / 109964680 | Ebi vs Majkel1337 | step 1 | step 1 | **step 205 (day 8)** |
| 109887746 / 109990277 | feel the agi vs Sida Zuo | step 1 | step 1 | **step 294 (day 12)** |
| 109990245 / 110003132 | Majkel 56156662 vs 56216119 | step 4 | step 6 | **step 226 (day 9)** |

Completely different opponent boards and different market prices from the first hour produce
byte-identical action streams for 8 to 12 days. Whatever Mother-Goose conditions on in the first
third of the season, it is not the opponent and not prices. Across all 226 pairs the median step at
which the opponent's farm first differs is 1 and the market 2, while the median first action
difference is 150.

**Majkel1337: not identified, because the policy is nondeterministic.** 15 of 210 same-seat pairs
show an action difference with *every* observation component (both farms, market, town, private)
identical over the whole preceding history — e.g. episodes 109756255 vs 109763505 diverge at step 3,
one game's hand doing `PASS` where the other does `PICKUP SHEEP`, and 109793225 vs 109946452 differ
at step 12 by one extra `BUY_SEED MELON`. Same world, same history, different action. Pairwise action
agreement is only 0.28 in segment 0 and 0.00 from day 18, and the median first divergence is step 3.
This is the fingerprint of a wall-clock-budgeted search/planner, not a tape. Consequence: for Majkel
no pair-level attribution of *any* conditioning is possible, because action differences need no
observational cause. Note the same is true of M&M&P&Q 56254996 (10 of 12 pairs nondeterministic,
divergence at step 0-1), so two of the three strongest agents observed are randomized planners.

**Shop-controlled correlations with the opponent's visible board** are weak and inconsistent: Majkel
plants *fewer* strawberries after day 12 when its opponent has many (partial rho=-0.65, p<0.001)
which is what differentiation would look like, but the same test is null for its tomatoes (-0.04) and
carrots (-0.27); Mother-Goose shows the *opposite* sign (carrots +0.40, p=0.03; tomatoes +0.35,
p=0.06), which is more consistent with both farms responding to a common price signal than with
either watching the other. Neither team's plantings, hires or cash correlate with the opponent's
leaderboard rating (|rho| ≤ 0.35, all p>0.10). **Conclusion: no support for opponent modelling in
production decisions.** Sale *timing* may still be opponent-aware; this sample cannot test it,
because order-level price races are not separable from prices in the observation stream.

### 3c. How scripted is each segment

Probability that two same-seat games play the identical action at the same step, averaged within
segment (unbiased by sample size, unlike a modal share):

| Days | 0-2 | 3-5 | 6-8 | 9-11 | 12-14 | 15-17 | 18-20 | 21-23 | 24-26 | 27-29 |
|---|---|---|---|---|---|---|---|---|---|---|
| Majkel 56216119 | 0.28 | 0.11 | 0.10 | 0.04 | 0.02 | 0.01 | 0.00 | 0.00 | 0.00 | 0.00 |
| Mother-Goose 56266758 | 0.98 | 0.97 | 0.58 | 0.59 | 0.08 | 0.05 | 0.02 | 0.03 | 0.02 | 0.03 |
| Majkel 56156662 (older) | 0.95 | 0.76 | 0.18 | 0.16 | 0.06 | 0.03 | 0.01 | 0.01 | 0.01 | 0.01 |
| M&M&P&Q 56254996 | 0.15 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| **Ours (56280048)** | **1.00** | **1.00** | 0.51 | 0.39 | **0.59** | **0.53** | 0.09 | 0.13 | 0.04 | 0.15 |

Read this as the shape of each policy: we are fully scripted for six days, then run one of 41 tapes,
which keeps mid-game agreement *higher* than the leaders' (0.59 vs 0.08 at days 12-14) because our
tapes barely differ from each other. Mother-Goose is scripted for six days and then increasingly
state-driven. Majkel re-plans almost every hour.

## 4. Where we diverge from them

Per-game means. **Caveat: our column comes from games against public V45, a near-clone of ourselves,
while the leaders' columns come from recent ladder games. Level comparisons of price and revenue are
confounded by that; structural comparisons (what is fixed vs conditioned, spend curves, land, labour
cost, fertilizer flows) are not.**

| | Majkel | Mother-Goose | Ours (vs V45) |
|---|---:|---:|---:|
| Final cash | 112,283 | 119,380 | 110,964 |
| Strawberries planted / of which day 12+ | 32.7 / 4.5 | 31.9 / **10.6** | 33.0 / **0.0** |
| Tomatoes planted (range) | 5.2 (0-19) | 9.5 (0-25) | 1.3 (0 or 10) |
| Carrots planted (range) | 58 (0-176) | 35 (2-98) | 31 (always 31) |
| Land spend | 3,000 (always) | 3,000 (always) | 4,000 (3,000 or 7,000) |
| Hire spend / unit commands | 4,928 / 7,220 | 4,736 / 7,056 | **5,677 / 6,979** |
| Fertilizer collected / applied / sold | 354 / 160 / 192 | 387 / 185 / 217 | 368 / **116** / **340** |
| Fertilizer purchased ($) | **0** | 1,002 | **2,571** |
| Strawberry revenue | 40,103 | 38,274 | 29,020 |
| Tomato revenue | 4,019 | 7,647 | 2,937 |
| Egg revenue | 3,420 | 6,411 | 3,460 |
| Revenue realised in days 27-29 | 17.8% | 17.5% | 17.4% |

Divergences that plausibly explain their advantage:

1. **Crop mix responds to demand; ours cannot.** Their strawberry, tomato and carrot counts move with
   shop demand (§3a); ours are literally constants (33 strawberries, 31 carrots in all 8 games; 10
   tomatoes only when ≥3 pizza/farmers shops exist at step 432). Strawberry is the most
   glut-sensitive good in the game (target 100 units, linear penalty above), and it is our largest
   revenue line. In our games both clones produced 249 strawberry units and realised **117/unit**,
   versus 159-173 for the leaders. Part of that is the mirror match, but the mechanism is real: a
   fixed maximal strawberry program is exactly the program that crashes its own price whenever the
   opponent (very often a V45 descendant) does the same.
2. **They keep the ongoing crops producing to the end.** Mother-Goose plants 10.6 strawberries after
   day 12 and Majkel 4.5; we plant none after day 11, so our strawberry income dies around day 23
   and our final-segment strawberry revenue is 1,457 against their 7,402 / 5,995.
3. **Labour is cheaper for them.** Both cap at 11 hires/day (696 per segment) forever; we exceed that
   in the late game (up to 2,204 in a segment) and end up paying **+749 to +941** for **241 fewer**
   executed commands. The hire cost is Fibonacci in hires-per-day, so the 12th and 13th hand cost 144
   and 233 for one worker-day.
4. **Fertilizer is used, not traded.** Majkel buys none, applies 160 and sells 192; we buy 2,571 worth,
   apply 116 and sell 340. Ours is a round trip through the market at a loss of optionality.
5. ~~They never buy the fourth quadrant.~~ **Withdrawn (2026-09-18).** Avoiding it is field-wide
   received wisdom, not a leader edge. Our benchmark buys it in roughly 12-31% of games through V45's
   two conditional programs; the self-play ablation measured the purchase as break-even (−349, CI
   −1,376 to +301), so it is not an edge in either direction.

Divergences that look incidental:

- **Liquidation timing.** All three realise ~17.5% of revenue in the final segment. The endgame
  dump is not where they gain.
- **Idle time.** Majkel PASSes 56 times a game, Mother-Goose 882, we 517 — and Mother-Goose scores
  highest. Activity count is not the objective.
- **Wheat trading.** Requested wheat buys 221 / 146 / 184 units and 426 / 403 / 432 sold: we are
  already in the same regime.
- **Opening herd order.** Majkel takes 2 cows + 3 sheep on day 0, Mother-Goose and we take 3 cows +
  2 sheep; both work, and Mother-Goose's opening board is identical to ours.
- **Nondeterministic planning per se.** Rank 1 re-plans every hour and rank 2 does not; the shared
  feature is demand-conditioned production, not the search.

## 5. What to learn — revised after measurement (2026-09-18)

The list below this section is the original, unmeasured version and is kept for the record. Three
things changed it.

**A behaviour both leaders share is not automatically an edge.** It may be what everyone does,
including us. The discriminating question is what they do that our benchmark does not. Re-checked
against the frozen benchmark profiled per segment (16 self-play games, 32 against Two Coins;
`results/fresh/leader_segments/commonality_check.log`):

| Commonality | Mother-Goose | Majkel | Our benchmark | Verdict |
|---|---|---|---|---|
| Day-3 board (cows / sheep / melons / wheat) | 3 / 2 / 12 / 7 | 2 / 3 / 11.7 / 6.3 | **3 / 2 / 12 / 7** | field standard |
| Strawberries at day 6 | 3.9 | 8.1 | **4.0** | field standard |
| Land 1,000 days 6-8, 2,000 days 9-11 | yes | yes | **yes** | field standard |
| Melon cash-out days 9-11 (units) | 71.9 | 38.7 | **72.0** | field standard |
| Liquidation share days 27-29 | 17.3% | 17.8% | **15.6%** | field standard |
| Fourth quadrant | never | never | 12-31% of games | withdrawn (break-even) |
| Strawberries at day 12 | 21.3 (17-23) | 27.8 (14-37) | **32.9 (32-33)** | **discriminating** |
| Strawberries planted day 12+ | 10.6 | 4.5 | **0** | **discriminating** |
| Tomatoes planted | 9.5 (0-25) | 7.5 (0-19) | **1.2 (0 or 10)** | **discriminating** |
| Carrots planted days 9-20 | 3.3 | 19.7 | **0** | discriminating (Majkel) |
| Extra melons after day 3 | 1.7 | 0.3 | **0** | discriminating (Mother-Goose) |
| Geese at day 12 | 3.9 | 1.8 | **2.2** | discriminating (Mother-Goose) |
| Hire spend days 6-11 (ramp) | 714 | 838 | **612-623** | discriminating |
| Hire spend per segment days 12-26 | 654 (flat) | 696 (flat) | **814-941, spikes to 1,885** | discriminating |

The whole timing half of the leaders' profile is our own tape; Mother-Goose's first days are
literally our opening. That is also why the behavioural imitation lost: most of what it copied, we
already did.

**Measured outcomes of the original list** (self-play gate against the frozen benchmark,
`docs/leaderlike.md`): the hire cap lost at every level tested (−3,857 at 11/day); the fertilizer
layer was broken and remains untested; demand-conditioned strawberry cuts lost at every dose and
transfer value to the opponent; and the 9-11k strawberry gap quoted in item 1 below was a market
artifact of our self-play pool (`docs/efficiency_decomposition.md`).

**What remains as the target**: demand-conditioned quantities and the ongoing-crop calendar, the
tomato, egg and extra-melon lines, and the labour *shape* (heavier ramp, flat ceiling). The
fourth-quadrant item is removed from the list.

### Original list (superseded)

1. **Make crop quantity a function of visible demand, replacing the constants.** Highest expected
   value: it is the one behaviour both leaders share, it survives the strictest test we can run
   (within-game, calendar-controlled), and it is the only one plausibly worth five figures — the
   strawberry line alone differs by 9-11k. Concretely: choose strawberry/tomato/carrot counts from
   the demand composition at each 3-day boundary instead of from the tape, and cap glut-sensitive
   crops when our own projected supply approaches the price target (strawberry 100, melon 300, milk
   122, wool 105). *Confidence: high that they do this; medium that we can implement it profitably —
   our own two attempts at exactly this (docs/crop_cohort_experiment.md) lost margin because the
   swaps were not jointly scheduled with labour.*
2. **Keep planting the ongoing premium crop through the mid-game.** Strawberries planted on days
   12-16 still deliver 3-4 productions before day 29, and both leaders do it while we stop at day 11.
   This is a small, local change to the tape's planting calendar rather than a new planner.
   *Confidence: high on the fact; medium-high on the value, because the tiles are currently used for
   wheat and the exchange rate has to be measured.*
3. **Cap hires at 11/day and shift labour earlier.** Both leaders sit at exactly 696 hire spend per
   segment from the moment they ramp, and buy more hands than us in days 6-8. Cheap, mechanical,
   ~750-950 cash, and it also removes the worst-case 2,204 segment. *Confidence: high — this is an
   arithmetic property of the Fibonacci hire cost, and both leaders respect it.*
4. **Stop the fertilizer round trip: apply more, sell less, buy none.** Majkel spends 0 on fertilizer
   and applies 44 more units than us. Our 2,571 of purchases exists because the tape sells collected
   fertilizer early and then needs inputs later. *Confidence: medium — our own wheat-economy study
   found the gross-flow gap overstates the net value (docs/wheat_economy.md), so size it before
   shipping.*
5. *(Removed: the fourth quadrant is field-standard avoidance, not an edge.)*
6. **Do not copy the search.** Rank 1 re-plans hourly and is nondeterministic, which is expensive to
   build and cannot be validated with our paired-seed gates; rank 2 gets 3129 with a deterministic,
   six-day-scripted policy plus demand-conditioned mid-game. The cheaper target is rank 2's shape,
   which is also our shape. *Confidence: high on the observation; this is an argument about
   engineering cost, not about the ceiling.*
7. **Ignore, for now: opponent modelling, liquidation timing, PASS elimination.** No evidence in this
   sample that the leaders' edge comes from any of them, and one clean piece of evidence against
   opponent-aware production.

## What this study does not establish

- It cannot separate "reads the shop list" from "reads prices that shops caused" for either leader.
- It cannot test opponent-awareness in Majkel's policy at all (nondeterminism defeats pair-level
  attribution), nor sale-order-level opponent races for either.
- It does not prove any of the §5 changes profitable. Every item needs the usual gate: paired seeds,
  both seats, all eight first-shop types, multiple modern opponents, held-out seeds.
- Revenue and realised-price comparisons against our agent are confounded by our opponent pool
  (public V45 only). Re-running our 8-game profile against a mixed modern panel would fix this and
  costs about ten minutes.
- The 52-game sample is recent public matches of two submissions, not the full ladder, and both
  leaders may be running newer code by the time this is read.
