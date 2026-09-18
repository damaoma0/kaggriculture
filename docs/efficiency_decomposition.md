# Is Mother-Goose's edge labour and layout, or portfolio? A decomposition

> **Partly superseded (2026-09-18) by [the tape test](tape_vs_bench.md).** Reading 4 below ("our
> benchmark is not a worse farmer in Mother-Goose's markets") relied on a control whose recorded
> opponent could not react and lost 21.9k. With Mother-Goose's own recorded plan played intact against
> our live agent, it wins 30-0 by +12,581, and its tomato and egg lines are the largest significant
> components. The labour and layout findings below still hold; so does the point that cross-pool price
> gaps mostly reflect the market pool.

Question (user): did Mother-Goose simply make layouts more efficient and save manpower? Tested
against measured data, not argued from the earlier portfolio hypothesis.

**Answer: no — and the portfolio hypothesis shrinks too. Most of the gap previously attributed to
Mother-Goose's farming is the market our agent plays in.**

## Data

`scripts/analyze_efficiency.py` measures every unlocked tile at all 720 steps (each crop, each
animal, empty structure, fallow ground, weed) and every executed unit command (effective, travel,
PASS, no-effect), with ledgers reconciled to final cash, identically for:

- Mother-Goose 56266758 and Majkel1337 56216119: the 52 exactly replayed episodes, both seats, so
  each leader is also measured against its own opponents in the same market;
- our frozen benchmark (56280048, Kaggle loader): 16 self-play games and 32 games against Two Coins;
- our benchmark **in Mother-Goose's seat of its own 30 games** (same seed, recorded shop sequence
  forced, the opponent's recorded actions). A diagnostic, not a match: the recorded opponent cannot
  react, and its cash falls from 115,832 to 93,981, which flatters us.

`scripts/report_efficiency.py` decomposes each product's revenue exactly as land × utilisation ×
portfolio share × yield per source tile-day × price (Shapley over all orderings), adds spend
differences directly, and reconciles to the cash gap. Full output: `results/fresh/efficiency/report.log`.

## 1. Labour: real, cheaper, second-order

| | Mother-Goose | Majkel | Ours self-play | Ours vs Two Coins | Ours in MG's games |
|---|---:|---:|---:|---:|---:|
| Hire spend | 4,736 | 4,928 | 6,518 | 5,593 | 5,315 |
| Effective actions | 3,334 | 3,593 | 3,457 | 3,428 | 3,430 |
| Effective per 100 hire $ (per-game mean, 95% CI) | 70.4 (69.7-71.0) | 72.9 (71.8-73.9) | 61.2 (51.6-70.3) | 67.2 (61.5-72.1) | 64.5 |
| Moves per effective action | 0.85 | 0.95 | 0.87 | 0.87 | 0.86 |
| PASS per game | 882 | 56 | 578 | 541 | — |

Mother-Goose buys labour more cheaply, but it does not do more work (fewer effective actions than
us), does not walk less (moves per effective action identical), and idles more. The saving is
0.6-1.8k per game.

## 2. Layout: no productive-capacity edge

| | Mother-Goose | Ours self-play | Ours vs Two Coins | Ours in MG's games |
|---|---:|---:|---:|---:|
| Unlocked tile-days | 1,812 | 1,933 | 1,868 | — |
| Productive tile-days (95% CI) | **1,653** (1,647-1,658) | **1,676** (1,653-1,701) | **1,647** (1,635-1,662) | **1,676** |
| Productive share | 91.2% | 87.2% | 88.5% | 88.6% |
| Fallow tile-days | 143 | 246 | 211 | 204 |

Mother-Goose keeps more of its land productive, but only because it owns less of it: productive
tile-days are the same as ours. Our extra fallow is land we buy and leave idle (the fourth quadrant),
which is why removing it measured inert (−349). Yield per productive tile-day is not higher on any
major crop (strawberry 0.468 vs 0.464, wheat 0.958 vs 0.966, melon 0.606 vs 0.609).

## 3. Decomposition, net by activity

Mother-Goose minus each comparison; wheat and fertilizer are netted against their own purchases so a
trading round trip is not misread as efficiency.

| Mother-Goose minus | Wheat trade | Fertilizer trade | Strawberry | Tomato | Melon | Carrot | Animals | Labour | Land | **Cash gap** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Ours, self-play | +1,453 | −867 | +9,356 | +5,233 | +2,597 | −470 | +4,381 | +1,781 | +1,250 | **+24,714** |
| Ours vs Two Coins | +773 | −572 | +8,711 | +7,172 | +3,407 | +589 | −8,793 | +857 | +500 | **+12,645** |
| Its own opponents (same games) | +1,538 | −353 | −1,610 | +2,342 | +3,997 | −1,225 | −1,866 | +592 | +133 | **+3,548** |
| Ours in its seat (same games) | +1,040 | −2,664 | −459 | +2,222 | +721 | +653 | −8,300 | +578 | +1,067 | **−5,141** |

Factor view of the cross-pool gap: realised price accounts for +19,230 (vs self-play) and +11,633
(vs Two Coins), but only **+54** within Mother-Goose's own games. Labour + land + utilisation + yield
together net −6,417, −12,509 and −171; portfolio +4,578, +417 and +1,338.

## Reading

1. **Labour and layout do not explain the gap.** Together with yield they net to about zero or
   negative in every comparison; the only consistent piece is a 0.6-1.8k labour-cost saving.
2. **The large gap is the market, not the farming.** The strawberry edge (+8.7-9.4k against our
   pools) turns into −1.6k against Mother-Goose's own opponents and −0.5k against our agent placed in
   its games, where we realise 155.9 per strawberry against its 159.1. The 9-11k strawberry gap
   reported in `docs/leader_segments.md` was measured against our self-play pool and is a market
   artifact: two V45-family agents dumping the same crop at the same hours.
3. **What does distinguish Mother-Goose head-to-head is small and spread out**: +3.5k over its own
   opponents, from melon (+4.0k), tomato (+2.3k), wheat trade (+1.5k) and labour (+0.6k), offset by
   strawberry, carrot and animals. Melon and tomato are the only lines positive in all four
   comparisons.
4. **Our benchmark is not a worse farmer in Mother-Goose's markets.** Placed in its seat, it finishes
   +5,141 ahead (95% CI −1,234 to +11,704; higher in 15/30) — with the caveat that the recorded
   opponent cannot react and collapses by 21.9k, which inflates our number.

## What would separate this cleanly

- **Mother-Goose against V45-family opponents** in live ladder games would be the user's acceptance
  test with Mother-Goose as the candidate. None of its 30 sampled opponents run V45's opening
  (17 use Majkel's), so this needs its episode list filtered by opponent opening and those replays
  downloaded.
- A true head-to-head of Mother-Goose against our agent needs its code, which is not available; the
  seat-replacement control above is the closest substitute and is biased in our favour.
