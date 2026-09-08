# Strategy notes

Compiled 2026-09-06 from the competition discussion forum and top public notebooks. Local copies of
the notebooks studied live in `data/public_notebooks/` (git-ignored; other people's code).

## What the top of the ladder looks like
- Almost no one runs an online planner. The 1-second turn limit and the sensitivity of the farm
  layout to early turns pushed the meta toward **fixed 719-action "tapes"** distilled from top
  replays, replayed regardless of observation.
- The converged mature farm (as of mid/late August): **3 quadrants (NW+NE+SW, not SE), ~8 cows,
  ~6 sheep, ~12 hired hands/day, ~21 melon seeds and ~44 strawberry seeds** over the season, plus
  wheat for feed. Ranks 3-20 were 99-100% identical on field actions at one snapshot.
- Fourth quadrant (SE, $4000) tested negative by Rayk Kretzschmar: every 4-quadrant variant lost
  10-0 to the 3-quadrant agent. Labor and travel cost, weed exposure and market glut outweigh it.
- The current edge is **market timing, not farm composition**: when to sell premium goods
  (melon, strawberry, milk, wool) relative to the opponent, since the market is shared and
  premium goods crash to $1 on a glut of about one field's worth.

## Latest generation (September): tapes with public-state branching
- Kaito Fukami v48/v58, Thomas Tschinkel "Public State Router", Pilkwang Kim v5: one shared opening
  prefix, then at a few checkpoints (steps ~72/96/144/226/360/433) pick a continuation tape based
  only on public state: which shops unlocked, market inventory/prices, opponent's visible farm and
  cash. Tschinkel: best single route 62% -> router 70.6% -> router + online repairs 74.5%.
- "Online repairs" that added wins with no losses: idle unit standing on a weed digs it; sell
  leftover shed stock before turn 720; clamp SELL orders to what the shed actually holds.
- Rejected ideas (hurt win rate): sells before buys; hiring last; feeding/caring on idle turns
  (overflowed shed).

## Economics cheat sheet (from Georgy Mamarin's measurements)
- Actions are the scarce resource, not money. 5 hands cost 12 coins for 115 unit-turns. ~10 hands
  cost ~143 coins/day. But hands only help if there is a job list for them.
- Land pays back in days at even $25/tile-day; its real cost is the labor to work it plus commute.
- Melon dominates per tile-day on paper (a simple melon bot beats the carrot bot by ~+11.7k vs
  starter) and the price floor only bites at very high volume (~158 units). Carrot is the best
  early cash-flow crop (3-day turnover). Wheat's real job is animal feed.
- CARE is huge: a cared animal yields 1 + interval units per production instead of 1 (goose 2,
  cow 3, sheep 4). First payout is larger (goose 4, cow 6, sheep 6). Sheep ends up the best animal
  with care, worst without. Each animal also gives 1 fertilizer/day, sellable.
- Slippage: selling 6 at a time costs ~nothing; a 36-melon lump gave back ~645 coins. Split sales.
- Fertilizer can be SOLD. Docs originally said otherwise.

## Rating and submission mechanics (Ryo Hasegawa's analysis)
- New submission starts at 600, ~90% converged after ~60 games (~5 hours). First ~10 games have a
  huge K factor, so early luck dominates the live number. Identical copies can end 300-1400 apart.
- Live leaderboard is NOT the final ranking: a Bradley-Terry fit on the ~2 weeks of post-deadline
  games decides. Only the latest 2 submissions matter. Never re-submit an unchanged bot.
- Optimize win rate against strong opponents on both seats with fixed seeds, not mean bank.
  A change that adds +3k coins on average but flips two wins to losses is a regression.
- Seat 0 has a measured small win-rate edge; always test both seats.

## Known loss mechanisms of strong tapes (useful for attacking the meta)
- **Opening feed denial**: opponent buys 14-19 wheat on turn 0 before your wheat order; shared price
  rises; you can afford 4 not 5; one animal starves on day 2. Fix: put the 5-wheat buy first.
- **One-turn preemption**: opponent sells fertilizer/wheat/premium one turn before your batch and
  takes the better price. Fix: move part of a planned sale one turn earlier, subtract it from the
  next turn (conserves total liquidation).
- Random weed on a tile the tape needs -> productive action silently fails. Fix: substitute DIG,
  delay that unit by one turn, resync at next PASS.
- Step 718 is the last executed action; index 719 never executes. Terminal cleanup must be done by
  717-718.
- Kaggle's file loader picks the LAST callable bound in main.py. Make sure `agent` is last.

## Balance changes to be aware of (engine >= 1.32.7 is current)
- 1.32.6: town center demand cut to 1/day flat; shops sampled with replacement.
- 1.32.7: carrot/tomato/egg got hinge scarcity curves. Prices spike only when shop demand is high
  and nobody produces: tomato ~50% of games, carrot ~26%, egg ~22%. Field responded by planting
  carrots (6% -> 44% of games); tomato went unadopted. Host says this is the last balance change.

## Data sources
- Official daily top-episodes index: https://www.kaggle.com/datasets/kaggle/kaggriculture-episodes-index
- Georgy Mamarin's episodes dataset (has engine_version column): https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes
- Rayk Kretzschmar's notebooks include a replay downloader and a "Rank Your Agent" harness.

## Candidate directions for our own agent
1. **Fast floor**: reconstruct a current top public tape (e.g. from kaitofukami v48 or Tschinkel
   v3.1 main.py) and get it running locally as the sparring baseline. This is the bar to beat.
2. **Own route**: write a real closed-loop farm controller (feed/water/care invariants, hand job
   lists, shed drops, split sells) rather than a tape. Nobody has made this beat the tapes yet;
   the 1 s budget is enough for greedy scheduling, not search.
3. **Market layer**: opponent-aware sell timing (the documented source of the current edge) on top
   of whichever field route we use.
4. **Evaluation harness first**: paired seeds, both seats, per-opponent records, veto on losing to
   the incumbent. Without it every "improvement" is noise.

## Learnings from building greedy_v2 (2026-09-07)
- Walking is the dominant labor cost. Scoring jobs by distance + small class weights, letting a
  unit finish every job on the tile it stands on, and sticky tile claims cut moves from 75% to ~50%.
- The public router's crew is not more efficient (40-50% moves, plenty of PASS); its edge is
  sequencing: 4 animals on day 0, a cow the moment 400 coins exist, 4 strawberry seeds/day from day 4,
  land on day 6, fertilizer sold the same day it is collected, and fertilized strawberries (8 units
  per tile instead of 4).
- Melon race: tapes dump at day 10 hour 9. Harvesting at 5 units without watering from hour 1 and
  carrying straight to the shed sells first. 20 melons did not beat 12 (cash and labor early).
- Demand model: town drain + shops + expected future shop draws (one every 3 days from a known
  table) + opponent's visible animals/plants. It correctly avoids milk when the opponent runs 9 cows
  and no milk shop exists, but must not hold tiles or cash for products it will not buy.
- Cash flow early: put the two largest SELL orders before purchases so same-turn proceeds fund buys.

## Hybrid and late-game findings (2026-09-08)
- Replaying the router's opening verbatim (264 steps) put the farm at parity with it on day 11;
  everything after is the planner's. The remaining gap (~25k) is units produced, not sell prices:
  after handover our per-unit prices equal the router's.
- Conditional watering (see CLAUDE.md working notes) was worth more than any market change.
- Ladder tapes reveal strategies the public router lacks: ~10 rolling melon tiles all season and
  wheat trading. Both are now in plan_v1 (melon rolling, feed stockpiling).
- Opponent trades can be inferred exactly from public market inventory minus town drain minus our
  own orders (`Planner.infer_opponent`).
