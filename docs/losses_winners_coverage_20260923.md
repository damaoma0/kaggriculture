# Losing games, new winner tapes, and tape coverage (2026-09-23)

Three directions from the user: 1. our losing games; 2. new winner tapes; 3. how to increase tape coverage under
limited resources, and the ceiling of perfect coverage. No agent was changed and nothing was submitted.
Ladder state today: `mgt_t10` (56368334) 2805.5, rank 49 of 9,911 teams; `mgt_m1` (56395605) 2700.5.

Everything is under `results/fresh/newphase_20260923/`. **Measured** = a game panel or an exact count.
**Fitted** = a regression on our ladder games (cross-sectional). **Derived** = arithmetic on measured numbers
under stated assumptions. The ladder panel and the head-to-head panel replay a frozen opponent that cannot react.

## Summary

- **We lose in wool worlds.** Each Yarn Store among shops 5-8 (days 15-24) multiplies our win odds by 0.37. That
  is P(win) 0.81 / 0.61 / 0.37 for 0 / 1 / 2 late Yarn Stores (fitted on 849 games, CI 0.27-0.47). In the 375
  late-Yarn games we win 57.3%, which is exactly what our rating predicts (57.5%). In no-Yarn worlds we win 84.2%
  where the rating predicts 55.8%. All of our edge over our rating sits in worlds without a late Yarn Store.
- **About half of that is tape mismatch, which coverage can fix.** The final tape is fixed by about day 12, so its
  late-Yarn count is effectively random against the world's. Each unit of |world − tape| late-Yarn mismatch gives
  odds ×0.51 (CI 0.34-0.74). Each late Yarn Store in the world gives a further ×0.63 even when matched. For
  strawberries only the mismatch matters.
- **Our own score is still the same in wins and losses; the opponent's decides.** Across 856 games the opponent's
  cash is 85% of the win/loss difference. In the current era (our rating 2800) it is all of it: our cash is
  105.8k in wins and 106.5k in losses.
- **There is no seat asymmetry.** Seat 0 wins 69.8% (n=440) and seat 1 wins 68.0% (n=416); rating-controlled odds
  ratio 0.95 (CI 0.71-1.27, p=0.71). The earlier m1 suggestion (n=86) does not replicate: at n=380 it is 67.6%
  against 67.7%.
- **No current winner can be harvested as a tape.** DSM, Boey, M&M&P&Q, the current Mother-Goose, Vadim Vasilenko
  and DECEM all split within about a day between games that have the same shops. Her old submission, which our
  library comes from, stays the same for 6+ days. A 108-tape DSM library already lost 9.9k when tested.
- **Adding random tapes is close to saturation.** On the ladder panel, halving the library (584 to 292) costs −505
  (95% CI −1,250 to +257) and cutting to 146 costs −3,174. Storage is not the limit: 100 MiB holds about 13,000
  tapes in the current encoding. The limit is supply. Only 658 recordings of the deterministic policy exist, and
  nobody deterministic is at the top now.
- **Ceiling (measured): perfect coverage turns −4,345 into +898.** There is no floor under coverage. But a perfect
  match on the four shops known at day 12 recovers only +0.7k. About 4.5k lives in shops 5-8, which no recorded
  library can cover (roughly 33,000 prefixes needed for reveal 5 alone). That value has to be generated as a
  late-game production response on top of the tape.
- **The top of the field has a new opening; the field we meet does not.** DSM, DECEM, the current Mother-Goose
  and Vadim Vasilenko (4 of the top 6) play the same fixed opening, in exact board counts: 2 cows and 3 sheep, 6
  melons on day 1 and 10 on day 2, strawberries from day 2 (about 10 tiles by day 6 against our 4), wheat 0 by
  day 6, day-6 cash 740-810 against our 213. M&M&P&Q (4 cows, 9 melons, early strawberries) and Boey (early geese)
  play two other openings. All six plant fewer melons and earlier strawberries than we do. 69% of our 856 ladder
  opponents still open the old way, and so does public V56. Every one of our 584 tapes starts from the old
  opening, so adopting the new one would desynchronise the whole library. Its value cannot be measured with a tape.

## 1. Losing games (856 ladder games of the two live submissions)

Data: every completed ladder game of both submissions was fetched with `scripts/ladder_panel_fetch.py`. t10 has
476 games (09-19 to 09-23, 333-143, 70.0%) and m1 has 380 (257-123, 67.6%). The per-game table is built by
`scripts/analyze_ladder_losses_2800.py` using the engine's shop demand table.

**World properties (fitted, logistic regression on 849 games with a rated opponent).**

| term | odds × | 95% CI |
|---|---|---|
| Yarn Stores among shops 5-8, each | **0.37** | 0.27-0.47 |
| Yarn Stores among shops 1-4, each | 0.56 | 0.43-0.69 |
| strawberry-buying shops, each | 0.85 | 0.75-0.95 |
| milk-buying shops, each | 0.81 | 0.72-0.91 |
| opponent's current team score, per 400 | 0.67 | 0.54-0.78 |
| seat 1 | 0.83 | 0.60-1.12 (n.s.) |
| m1 rather than t10 | 0.97 | 0.71-1.34 (n.s.) |

Raw win rate by total Yarn Stores: t10 82 / 67 / 57 / 60%, m1 87 / 67 / 48 / 55% for 0 / 1 / 2 / 3+. In margins
(OLS): each late Yarn Store costs 2,056 ± 1,006 and each strawberry-buying shop 1,313 ± 585. Carrot and egg shops
help us (+1.4k, +1.5k). Put simply: we are a carrot, egg and wheat farm, and we lose in worlds that pay for wool,
strawberries and milk.

Fitted counterfactual (`scripts/ladder_world_counterfactual.py`): if late Yarn cost us nothing, win rate would
rise from 68.8% to 75.5% (+6.7 points, CI +4.4 to +9.2). Removing early Yarn as well gives +8.4.

**Tape-match quality (panel margins, 535 unique worlds; `scripts/ladder_tape_match.py`).** The final tape shares
the world's first four shops in 6-7% of worlds and its last four in 0%; the median last switch is day 12. Win rate
by late-Yarn mismatch (world − final tape): −2 or less 64%, −1 72%, **0 87%**, +1 64%, +2 or more 59%. Too little
wool capacity hurts and so does too much. With both terms in one model, |late-Yarn mismatch| gives ×0.51 (CI
0.34-0.74) and world late Yarn gives ×0.63 (0.43-0.90). For strawberries, world demand ×0.73 and |mismatch| ×0.80
(borderline). An unsigned late-strawberry mismatch gives ×0.58 per unit of under-supply (CI 0.44-0.73).

**Own score against opponent score** (`scripts/analyze_ladder_ratings_seats.py`, ratings from the leaderboard
snapshot nearest each game):

| our rating era | games (W/L) | share of win-loss gap from our cash | from theirs |
|---|---|---|---|
| 2310 (09-19..20) | 141 (117/24) | 14% | 86% |
| 2472 (09-20..22) | 448 (317/131) | 22% | 78% |
| **2801 (09-22..23)** | 267 (156/111) | **−6%** | **106%** |

The prior finding holds and is stronger at 2800.

**Opponents.** 653 different teams across 856 games. Losses are not concentrated: the 15 teams we lose to most
account for 12% of losses, and teams in the current top 100 for 18%. **Caveat on ratings:** a team's leaderboard
score is its best submission, but we may have played its other active submission. Win rate barely moves with the
rating gap (63% against teams rated 300+ above us), so treat every rating-based number as weak. The world-feature
results do not use ratings.

**Trend.** Win rate falls as our rating rises: t10's chronological quartiles are 83 / 72 / 67 / 57%. At a 58%
current-era win rate the rating is close to where it stops climbing.

## 2. New winner tapes

**Who wins now** (leaderboard 2026-09-23): DSM 3166, Boey 3090, M&M&P&Q 3079, Unknown Mother-Goose (new build)
3050, Vadim Vasilenko 3020, DECEM 3012.

**Harvestability test** (`scripts/screen_leader_determinism.py`; 40 games each via
`scripts/harvest_leader_tapes.py`, 108 for DSM). Among an agent's own games, take the pairs whose first k shops
match and measure how long the recorded action streams stay identical.

| agent | games | median agreement, pairs with first 2 shops equal | pairs diverging within day 0 |
|---|---|---|---|
| Mother-Goose old (our library, control) | 584 | **166 steps (6.9 days)** | 23% |
| DSM (56444344) | 108 | 12 steps | 88% |
| M&M&P&Q | 39 | 9 steps | 69% |
| Mother-Goose current | 40 | 22 steps | 69% |
| DECEM | 40 | 25 steps | 18% |
| Vadim Vasilenko | 40 | 25 steps | 14% |
| Boey | 40 | 1 step | 100% |

All six current leaders react to something other than the shops (prices or the opponent) within the first day.
This is the class that desynchronises when replayed: the current Mother-Goose went 21-21 and −12k even in its own
worlds (`docs/mg_tape_base.md`), and the DSM library was −9.9k (`docs/rotation_experiments_random_seeds.md`).
**None of them can be harvested as tapes.** A refreshed library can only take more of her old deterministic
submission: 658 recorded games exist and 584 are in the library. The other 74 were left out by the builder's rating
≥2500 filter (her early climb), not because they are invalid plans. At the measured slope below they would be worth
about +0.1k.

**What the winners do instead** (`scripts/analyze_leader_production_response.py`, exact DSM board counts against
our library's boards). After a late Yarn Store, DSM holds +1.9 sheep above its own seasonal baseline and
Mother-Goose's old policy +1.4. DSM's day-24 sheep are 7.1 / 6.8 / 9.0 for 0 / 1 / 2+ late Yarn Stores; hers are
5.8 / 6.9 / 8.0. Neither changes its strawberry tile count after a late reveal (both follow the seasonal decline).
DSM carries more strawberries on day 12 (24.5 against 20.9), more cows (8.9 against 7.7) and more geese (5.6
against 3.8), and wins 107-0 by +26k in its own games. Her old policy already contains the late-Yarn herd response;
our borrowed tape does not, because it responded to its own world's late shops.

## 3. Tape coverage under limited resources

**Resources** (`results/fresh/newphase_20260923/library_structure/`). The submission limit is 100 MiB (Kaggle
runtime 6.5 GiB RAM, 1 s per step plus a 60 s bank). The shipped blob is 3.72 MB zlib, 7.8 KB of base85 per tape.
A token stream with LZMA gets this to 2.7 KB per tape. So 100 MiB holds about 13,000 tapes as encoded now and
about 39,000 re-encoded. Storage is not the constraint. Locally, each game worker is about 0.92 GB, and the
per-step router cost grows linearly with the library.

**Redundancy.** Tapes are identical through day 3 for most of the library (498 share the modal opening). Through
day 12 there are 389 distinct action prefixes among 584; after day 13, 571 of 584 are unique. Day-start boards
form 64 clusters (radius 8) on day 12, where 11 clusters hold 90% of tapes; 225 clusters on day 15; 365 on day 18.
Deduplicating would save bytes, not coverage.

**Which worlds are under-covered** (exact counts, `scripts/coverage_curve_offline.py`). There are 6,435 possible
8-shop multisets; the library holds 525 (8%). On day 12, 247 of 330 four-shop compositions are present and 38% of
our 856 ladder worlds have an exact demand match. The best achievable demand distance falls roughly as N^−0.4 with
library size: 22.1 at N=1, 5.9 at 64, 1.8 at 584. For the full 8 shops it is 72 at N=1 and 20 at 584, still
falling slowly. Late shops cannot be covered by drawing more whole tapes: each tape covers one late path out of
4,096 ordered continuations of its day-12 state.

**Would partial (late-segment) tapes be executable?** (`scripts/twin_board_compat.py`) Take pairs of her tapes that
agree on the first m−1 shops and differ at reveal m. On the morning of reveal m their boards are compatible
(≤8 tiles apart) in **100%** of pairs at every reveal, including days 15 and 18 (median 2-5 tiles). Three days later
they are still 100%. So a library that branches at each reveal would be executable. The 3-5k loss from forcing
the perfect tape on days 15-21 (`docs/gap_ceilings.md`) comes from arriving on a board built for different early
shops, not from the tape format. The binding constraint is that the right branch has to exist. From 584 tapes
there are 272 branch pairs at reveal 4, 34 at reveal 5 and 9 at reveal 6. We cannot generate new branches: her old
submission is retired and no deterministic leader is active.

**Coverage against performance, measured** (ladder panel, 180 frozen ladder worlds of t10, random library subsets
built by `mgt_lib*`; `scripts/report_coverage_panel.py`). The full-library control reproduces cached `mgt_m1`
exactly (44/44).

| library | worlds | W-L | mean margin | paired vs 584 (95% CI) | better / worse / same | switches a game |
|---|---|---|---|---|---|---|
| **584 (= m1)** | 180 | **128-52** | +5,188 | | | 3.35 |
| 292 | 180 | 123-57 | +4,683 | **−505** (−1,250 to +257) | 53 / 73 / 54 | 3.14 |
| 146 | 180 | 109-71 | +2,014 | **−3,174** (−4,588 to −1,836) | 65 / 97 / 18 | 2.98 |
| 146, second draw | 66 | 37-29 | +5,821 | −4,285 (−6,436 to −2,209) | 21 / 43 / 2 | 2.97 |
| 73 | 66 | 45-21 | +7,770 | −2,336 (−3,972 to −808) | 18 / 44 / 4 | 2.76 |
| 36 | 14 | 12-2 | | −6,486 (−11,392 to −2,239) | 3 / 11 / 0 | 2.43 |

The last three arms were stopped early to save memory. At n=66 the 73-tape arm beats both 146-tape draws, so the
spread between random draws is about as large as the effect at the small end. Only the 584/292/146 rows at n=180
support a slope. Measured: going from 146 to 292 tapes gains +2.7k and 5 wins in 180 games per 100 tapes added;
going from 292 to 584 gains +0.5k (not significant) and 5 wins in 180. Derived: returns per doubling fall by about
5× per doubling, so doubling to about 1,170 tapes would add roughly +0.1k, and even +0.5k at the most generous
constant rate. The 74 unused games of her old submission (+13%) are worth about +0.1k. More random tapes from the
same policy cannot close a 4-5k gap: every one covers a single late-shop path, and the router is already choosing
from 288 compatible tapes on day 12.

**The ceiling: what does −4,345 become with perfect coverage?** (`scripts/prefix_twin_ceiling.py`; measured in her
128 held-out recorded worlds where arm A = ladder case and arm B = her own tape are already known for `mgt_m1`.)
Our agent is forced onto one recorded "twin" tape that matches the world's first k shops exactly (in order, or by
the router's demand vector where no ordered twin exists) and is random after that. Her recorded moves play the
other seat, so the opponent cannot react. The margin is ours minus hers.

| shops covered exactly | worlds | W-L | mean margin (95% CI) | vs A, same worlds | vs B, same worlds |
|---|---|---|---|---|---|
| 1 (day 3) | 64 | 5-59 | −15,190 (−18,140..−12,387) | −11,352 | −16,230 |
| 2 (day 6) | 128 | 9-119 | −11,459 (−13,168..−9,793) | −7,114 | −12,357 |
| 3 (day 9) | 80 | 10-70 | −5,879 (−7,101..−4,661) | −1,629 (−2,916..−364) | −6,571 |
| 4 (day 12) | 37 (11 ordered) | 7-30 | −3,513 (−5,502..−1,433) | **+691 (−828..+2,370)** | −4,763 |
| 5 (day 15) | 6 | 2-4 | +114 | +3,872 (n=6) | −554 |
| **8 = her own tape (B)** | 128 | 112-16 | **+898** | +5,243 | |
| A = router over the other 583 tapes | 128 | 20-108 | **−4,345** | | |

1. **There is no floor under coverage.** With perfect coverage, meaning a tape recorded in this exact world, −4,345
   becomes **+898**: we beat her 112-16 on her own plan. The whole 5.2k gap is coverage.
2. **Almost none of it is reachable by covering what is known at day 12.** A perfect day-12 match recovers +0.7k
   (13%, not significant). About 4.5k lives in shops 5-8, which are drawn after the tape is chosen. Each extra
   exactly-covered shop is worth roughly 2.5-5k. The router's day-by-day choice from 583 tapes lands between
   "3 shops covered" and "4 shops covered".
3. **Late coverage would be executable but cannot be supplied.** Branches at each reveal are board-compatible
   (above), so a library that branched at days 15-24 would run. The count is the problem: covering reveal 5
   exactly needs 8 branches for every day-12 state, i.e. about 33,000 ordered 5-shop prefixes against the 576 we
   have. That is about 50 MB of late segments, which would fit in 100 MiB, but nobody can record them: the
   deterministic policy is retired, 658 recordings exist, and every current leader is closed-loop. Covering all
   of shops 5-8 needs about 10^7 segments.
4. **Derived translation to the ladder.** If the 5.2k measured against her tape carried over to today's
   opponents, our current-era win rate (58.4% at rating 2800) would become about 80%, roughly the 3000 target.
   Perfect selection from the existing library (+1.3k, `docs/gap_ceilings.md`) gives about 66%, and perfect day-12
   coverage (+0.7k) about 62%. This assumes a uniform shift of our margins and that her-tape results transfer to
   reacting opponents; both are unverified.

**Consequence for the plan.** The value is in covering shops 5-8, and recordings cannot supply that at any storage
budget. It has to be generated: a late-game production response (sheep and care after a late Yarn Store, sized
strawberry cohorts) applied on top of the running tape. That confirms the direction in `docs/gap_ceilings.md` with
the ceiling now measured at about 4.5k. More or better-deduplicated recorded tapes are worth at most about 0.5k.

## 4. The opening (days 0-6), added at the user's request

Exact board counts from full replays, parsed one at a time (`scripts/analyze_openings_2026.py`,
`results/fresh/newphase_20260923/openings/summary.md`). DSM has 109 farm-games; the other five leaders and ours
have 12 downloaded games each; Mother-Goose old is the 584 library tapes.

| agent | day 1: cows / sheep / melon / wheat | day 6: cows / sheep / melon / wheat / strawberry | day-6 cash | quadrant 2 at day start | turn-0 wheat |
|---|---|---|---|---|---|
| DSM (rank 1) | 2 / 3 / 6 / 9.6 | 2 / 3 / 10.2 / 0 / 9.8 | 742 | 7 (all 109) | buy 5 |
| DECEM | 2 / 3 / 6 / 9.8 | 2 / 3 / 10.9 / 0 / 9.1 | 806 | 7 | buy 5 |
| Mother-Goose current | 2 / 3 / 6 / 9.8 | 2 / 3 / 10 / 0 / 10 | 768 | 7 | buy 5 |
| Vadim Vasilenko | 2 / 3 / 6 / 9 | 2 / 3 / 10 / 0 / 10 | 811 | 7 | buy 5 |
| M&M&P&Q | 3 / 2 / 7.9 / 9.2 | 5.1 / 2 / 9.1 / 7.2 / 8.7 | 167 | 6 (10 of 12) | buy 5 |
| Boey | 2.9 / 2.1 / 6.8 / 13.1 | 5 / 2.8 / 10.2 / 0.1 / 4.5 (+2.4 geese) | 18 | 7 | buy 3 + 3 |
| **ours (= Mother-Goose old + equilibrium buy)** | 2 / 2 / 12 / 7 | 4 / 2 / 12 / 3 / 4 | 213 | 7 (all 12) | buy 5 |

- **A new shared convention exists at the very top.** Four of the top six are identical through day 6, with zero
  spread across their games and no dependence on the shop revealed on day 3. It matches what Majkel did as rank
  1 on 09-16 (`docs/leader_opening.md`): sheep over cows, staged melons, wheat converted to strawberries by day 4-5.
  M&M&P&Q and Boey each run their own fixed opening. What **all six** share against us: fewer melons (9-11
  against 12) and strawberries from day 2-3 (4.5-10 by day 6 against our 4). The public V56 is not the source; it
  opens the old way with a BUY 20 / SELL 15 wheat trade.
- **What is not different**: land timing (quadrant 2 appears at the day-7 start for us and for them, bought
  during day 6) and the wheat flip (we already buy 5 and keep them, like them). Earlier notes that these differ
  compared their play with Mother-Goose's raw tapes, not with our agent.
- **The field we actually meet has not moved.** Of our 856 ladder opponents, 69% open cow-led with a wheat
  round trip and land on day 6, and only 3% look like the new convention. Among our 11 recorded 2900+
  opponents, 8 no longer flip.
- **Value: not measurable with what we have.** Measured at cost, the new openings are more fully invested by day 7
  (8.3-8.7k against our 7.1k, mostly strawberry tiles at 100 each), but cost is not value. No deterministic agent
  plays the new opening through a whole game, and our 584 tapes all start from the old board: 12 melons against
  6-10, a cow-led herd, 7 wheat tiles. A new opening would put every tape's commands on the wrong tiles from day
  1. Earlier partial transplants (early strawberries or a changed herd on the V45 layout, 09-16) lost margin.
- **Bearing on direction 3.** The opening does not explain the measured coverage gap. That gap (5.2k, 4.5k of it
  in shops 5-8) is against the same old-opening policy, and our own score is flat between wins and losses. It does
  mean the tape approach is anchored to the old opening. Whether that costs anything against the new-convention
  top is untested: only 11 of our games are against 2900+ opponents.

## Method notes and limits

- **Frozen opponents.** Every game panel here (library sizes, prefix twins, tape match) replays a recorded
  opponent that cannot react. The ladder-panel harness reproduces recorded results to the dollar (the full-library
  control matches cached `mgt_m1` in 44/44). A reacting opponent could change the size of the ceilings, most
  likely the market-share part (her revenue rises when we mis-supply).
- **Twin arm.** The agent is forced onto one twin tape from day 0 (`MGT_ONLY`), so it is a
  single-tape-with-a-perfect-prefix measurement. With switching, the router would move off that tape as later
  shops arrive; with only 583 tapes there is usually nothing compatible to move to after day 15, which is the
  point. The k=4 cell uses demand-equivalent twins for 26 of 37 worlds, as the router's own distance does. k=5
  and k=6 are 6 and 1 worlds and are not interpretable.
- **Ratings.** The API has no per-game ratings. We use the leaderboard snapshot nearest each game (median 10 h
  stale), and a team's score may belong to a different submission than the one we met.
- **Opening.** Board counts are exact for the replays parsed (DSM 109; 12 per other leader; our 12). Field
  clusters use order requests only.
- **Memory.** All batches ran at ≤4 workers with a free-memory check (`ladder_panel.py` now sizes its pool from
  free memory; `prefix_twin_ceiling.py` starts each game only above 2 GB + one worker).

Scripts added: `analyze_ladder_losses_2800.py`, `ladder_world_counterfactual.py`, `ladder_tape_match.py`,
`analyze_ladder_ratings_seats.py`, `fetch_full_leaderboard.py`, `harvest_leader_tapes.py`,
`screen_leader_determinism.py`, `analyze_leader_production_response.py`, `analyze_openings_2026.py`,
`coverage_curve_offline.py`, `twin_board_compat.py`, `library_structure_analysis.py` (+ `_report`,
`library_resource_probe.py`, not run), `report_coverage_panel.py`, `prefix_twin_ceiling.py`. Research builds
`agents/mgt_lib{036,073,146,146b,292,584}.py` and `agents/mgt_m1r.py` are `mgt_m1` plus a library filter only.
