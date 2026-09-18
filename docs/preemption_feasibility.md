# V48 integration and pre-emption feasibility

Goal (user, 2026-09-18): beat both Mother-Goose and V48 (latest public router) reliably. Mother-Goose is
a research vehicle, not necessarily a submission target; the component should be general: simulate a
deterministic, shop-conditioned opponent forward and best-respond.

## 1. V48: fetched, reviewed, integrated

Source: Kaggle notebook `ahmedberatozer/kaggriculture-v48-clear-the-queue` (383,986-byte `.ipynb`),
pulled into `data/router_refresh_20260918/v48/`. The agent source was extracted as data without running
notebook cells: 357,742 bytes, 4,042 lines, SHA-256 `4b540288…89bb96`, matching the notebook's embedded
digest. Standard-library imports only; `exec` is used to load embedded modules, as in V45. Unmodified
copy: `agents/v48_public.py`; Kaggle entry point `_e335_agent` (line 4041); max 0.37 s per turn in our
runs.

### What V48 changed relative to V45

The diff is 15 hunks: small edits inside V45 plus 515 appended lines.

| Change | Origin | What it does |
|---|---|---|
| **Opening** | V46 EXP293 | Step 0 `BUY 7, SELL 2` (keeps the 5 feed wheat — essentially the certified Nash opening); step 1 drops the tape's failing `SELL 13` and duplicate `BUY 5`. The 70-unit flip is gone. |
| **Step-1 spoiler attack** | V46 EXP293 | If cash ≥ 2,860, `BUY 30` wheat at index 0 of turn 1 and sell it back on turn 2. Code comment: "every tape of this lineage buys its five feed units at index 1 of the first market turn; a product purchase at index 0 executes before it and lifts its quotes below the tape's day-0 cash slack." |
| Sale advance | V46, after sdy623/jaxa623 "Beyond 48-0" | Sells cash products up to 3 turns ahead of the tape "ahead of a rival executing the same tape". |
| Mirror gate | V46 EXP288 | A rival whose cash after turn 1 equals ours is treated as a copy; the sale race horizon rises to 24. |
| Clone lockstep ordering, pre-guard, clone horizon | V47, from Seyit Kaan Gunes's "kaggriculture-2820-score" | Best-response SELL ordering against a detected clone; sells at hours 21-22 what the day-end storage guard would dump at 23. |
| Shop-aware herd | V47, same source | Swaps animals by shops on days 8-11 (Yarn → sheep, geese options). |
| Queue compaction | V48 EXP334/335 | Removes sale slots that cannot sell and merges repeated sales. |
| Terminal planner tweaks | EXP303, E182 | Resource proposals in the last-seven-turn planner. |

The community frontier is already "recognise a deterministic opponent from the same lineage and
pre-empt it" — aimed at its own clones. Our agent is one of those clones.

## 2. The panel so far (seeds 173000-173015, both seats, 32 games per row)

| Our agent / variant | vs frozen benchmark | vs V48 |
|---|---|---|
| Frozen benchmark (56280048) | 0-32-0, ±0 | **0-0-32, −1,753** (−2,115 to −1,391) |
| Nash-5 opening | 32-0-0, +1 | 0-0-32, −2,033 (−2,894 to −1,360) |
| Flip-5 opening | 32-0-0, +234 | 0-0-32, −2,009 (−2,788 to −1,354) |
| Flip-35 opening | 32-0-0, +1,375 | 0-0-32, −1,741 (−2,111 to −1,378) |

Opening changes do nothing against V48. It opens Nash-like, so there is no large flip to exploit, and
its edge over us is in the sale race, which it is designed to win against V45-lineage tapes.

Mother-Goose's recorded plan against V48, live (30 games):

| | MG W-T-L | MG margin (95% CI) | Her day-0 wheat cost | Hire fails day 1 |
|---|---|---|---|---|
| no cushion | 3-0-27 | −18,509 (−25,299 to −12,432) | 154 | 30/30 |
| cushion 40 (removed from score) | **30-0-0** | **+12,220** (+10,117 to +14,345) | 154 | 0/30 |

V48's step-1 attack does exactly what its comment says: it pushes her opening past its slack and her
frozen tape collapses. With the slack restored, her intact plan beats V48 by about the same margin it
beats us (+12.6k). Two caveats hold for both results: a tape cannot adapt where her live policy might,
and none of her 30 recorded opponents opened with a flip or a step-1 attack, so there is no evidence of
how her live code handles one.

**The live Mother-Goose opponent is not built yet.** It needs her executor, not only the phase-1
decision rules; see §6.

## 3. Can we simulate her forward from shops alone?

`scripts/opponent_forecast.py` — a general k-nearest-neighbour forecaster over an opponent's recorded
games, using only shop features visible at the forecast origin (per-product demand counts plus the
first-two-shops route key). Leave-one-out over her 30 games. Error = sum over plant/animal types of
|predicted − actual| count, against ~47-74 productive tiles.

| Forecast made at | Day predicted | Shop-kNN error | No-shop baseline | Execution-noise floor |
|---|---:|---:|---:|---|
| day 0 | 5 | 0.1 | 0.2 | 0.1 (47 pairs) |
| day 6 | 8 | 2.5 | 4.3 | 0.3 (7 pairs) |
| day 6 | 12 | 5.6 | 9.3 | 0.0 (1 pair) |
| day 12 | 15 | 12.4 | 20.6 | 4.0 (1 pair) |
| day 12 | 18 | 16.6 | 24.7 | — |
| day 12 | 24 | 20.3 | 32.4 | — |
| day 12 | 27 | 19.2 | 29.4 | — |
| day 18 | 24 | 21.5 | 32.4 | — |

- Days 0-5 are known exactly; days 6-11 to within a few tiles.
- From day 12, error is 17-27% of her productive tiles, against 28-44% without shop information.
- **The error plateaus rather than compounding**: ~17-21 from day 18 onward. Forecasting from day 18
  instead of day 12 barely helps, so the residual comes from library coverage (30 games against 8⁸
  shop sequences), not missing information. Execution noise is small where it can be measured (0-4
  tiles). A rules-based simulator (the phase-1 rules) generalises to unseen shop combinations and
  should beat kNN on days 12+; not yet built.

**Her sales.** Forecast from day-12 shops, per product per day:

| Product | Units/day | MAE, shop-kNN | MAE, no-shop | Peak day within ±1, kNN | Peak day, no-shop |
|---|---:|---:|---:|---:|---:|
| Strawberry | 16.4 | 4.4 | 5.5 | 21/30 | 20/30 |
| Tomato | 5.8 | 3.3 | 4.4 | 20/30 | 22/30 |
| Carrot | 8.1 | 4.1 | 6.9 | 30/30 | 30/30 |
| Milk | 11.3 | 4.1 | 4.4 | 11/30 | 11/30 |
| Wool | 7.7 | 4.0 | 5.5 | 12/30 | 6/30 |
| Egg | 9.7 | 4.2 | 5.2 | 17/30 | 16/30 |

Her sale *days* barely depend on shops — the no-shop average finds her strawberry peak as often as
the forecaster — and her sale *hours* are concentrated: strawberries at hour 5 (25% of orders), 9 and
0; eggs at hour 0 (40%); tomatoes at hours 21-23 (47%); milk at hour 1 (23%).

## 4. Which exploits survive prediction error

| Exploit | What must be predicted | Available accuracy | Robust? |
|---|---|---|---|
| Sell ahead of her sale window | Day and hour of her orders; rough quantity | Hours fixed per product; strawberry/tomato peak day ~70% ±1, carrot/wheat 100% | **Yes** — needs the hour, which is fixed |
| Avoid what she will flood, supply what she leaves short | Product quantities, days 12-29 | 27-40% of level | Only for large differences (e.g. her strawberry surge in strawberry-rich worlds) |
| Anticipate her animals | Route key from the first two shops | Rule derived, high confidence | Yes, but little to exploit: animal markets are separate |
| Opening spoiler (V48's step-1 attack) | Her order structure on turn 1 | Known exactly | Breaks her *tape*; effect on her live policy unknown |

## 5. Identifying her on the ladder

`scripts/opponent_fingerprint.py` — the public farm trajectory (worker and hand positions, hires,
tiles; not cash, which depends on our own orders) over the first 48 steps, across every replay on disk:
392 seat-trajectories, 196 episodes, 147 teams.

| Through step | Her games matching her canonical trajectory | Other seats matching |
|---:|---:|---:|
| 0 | 30/30 | 362 |
| 2 | 30/30 | 100 |
| 3-20 | 30/30 | 8 (six lineage-mates: Bandito Gangesterito, BigAngel, Catalyst, Crop Dustas, Yiyang Xu, bzczz123) |
| 23 | 29/30 | 7 |
| **25** | **28/30** | **0** |

She is uniquely identified by step 25 (day 1, hour 1) with no false positives among 362 other seats,
and 93% recall; the two misses are the execution-noise deviations already seen (a cash-short PASS on
day 0, a weed dug on day 1), which a tolerant match would absorb. Through step 20 she is
indistinguishable from six lineage-mates that share her opening routing. Majkel1337, being
nondeterministic, cannot be fingerprinted this way (his own games stop matching his canonical
trajectory at step 4).

## 6. The same approach against V48

V48 is public and has no randomness, so its production plan can be simulated exactly by running its
code — no inference needed. Two limits: its sale-race layers read our moves and its private shed, which
we cannot see, so its sales can be predicted only approximately; and it already runs anti-clone
pre-emption against V45-lineage agents, so a pre-emptive layer of ours would enter a timing contest with
one that exists (its sale advance looks 3 turns ahead).

## 7. What building next would take

1. **A live Mother-Goose opponent.** Her decision rules (phase 1) plus an executor. She is V45-lineage
   with her own worker routing; the closest route is her rules on the V45 chassis, validated for
   fidelity against her recorded boards and against her tape's +12.6k versus our benchmark. Without it,
   the "beat Mother-Goose" half of the panel can only be measured against her tape.
2. **A rules-based forecaster** from the phase-1 rules, to replace kNN on days 12+.
3. **A first pre-emptive exploit**: sell ahead of her fixed sale hours (strawberries before hour 5), the
   one exploit that is robust to forecast error.

The opening changes help only against 70-flippers: against V48 every variant loses 0-32, so the flip
should not be counted as a win against the new panel.
