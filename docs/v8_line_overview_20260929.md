# V8 line overview: what we are building, where it stands, the gaps (2026-09-29)

Sources: the other thread's worktree `C:/Users/xyygl/.codex/worktrees/semantic-kb115lt2/kaggriculture` (branch
`codex/semantic-kb115lt2-recovery`, docs `semantic_*_20260928.md`, `kb115lt2_*_20260928.md`), the shared study
`results/fresh/semantic_strategy_20260928/` (runs, reports, fresh_smokes), and this thread's own runs
(`results/fresh/semantic_h2h_20260929/`, `results/fresh/kb_vs_v9_20260929/`, `docs/dsm_melon_reaction_20260929.md`).

## The stack

| Layer | Days | What it is | Owner |
|---|---|---|---|
| Opening | 0-5 | compact adapter replaying current DSM's opening (DSM's day-6 board is identical in 95/100 recordings) | other thread |
| Semantic policy | 6-29 | each morning: what to plant / buy / retire, land, hands; block model trained on DSM daily decisions (modern100); no prices or rival farm in its training traces | other thread |
| Spatial compiler | 6-29 | where: full daily tile states from the policy's anonymous changes | other thread (user trains a tile planner over KB115LT separately) |
| Executor | 6-29 | KB115LT2 (tier planner, hand routes, market), frozen; the other thread edits copies | this thread |

Targets: 30/40 against live packaged MGT (`mgt_v9lite`) and 30/40 against recorded scripts of 2750-3000 teams.
Qualification panels are frozen and have not run. Development = the same 8 live worlds and 8 recorded worlds throughout.

## Lineage and scores (development panels, laptop, official 1 s + 60 s limits)

| Candidate | Change | Live V9-lite (8 dev worlds) | Recorded 2750-3000 (8) | Max overage (laptop) |
|---|---|---|---|---|
| smoke_v1 | first stack | 1/8, -6,593 | 1/8, -7,240 | 14 s |
| V2 nearest / unlock | tiling variants | 1/8 -7,145 / 2/8 -5,202 | - | 3-6 s |
| V3 modern4, V4 +finance | policy retrained, financing | 1/8 -9,672 / 1/8 -6,623 | - | 11-12 s |
| V5 blocks100 finance | block model on modern100 | 4/8, +242 | 4/8, -618 | 11 s |
| V6 recovery, V7 readiness | recovery / readiness rules | 4/8 +1,630 / 3/8 -834 | - | 9-15 s |
| **V8** | executor -> KB115LT2 | **5/8, +994** | 4/8, -496 | 19-21 s |
| V9 reveal | reveal features | rejected: 2 of 8 timed out (3/6 valid wins) | - | 42 s |
| V10 / V11 | polish cache / route fix | V10 timed out in smoke | - | - |
| V12 runtime fast | exact evaluator + caches, wheat retry | 5/8, +1,993 | 4/8, -147 | 48 s |
| **V13** | + bounded harvest exchange | **7/8, +2,838** | 4/8, -14 | 39-50 s |
| V14 | + net-fertilizer forecast | not run | 4/8, -775 (paired -761 vs V13) -> out | 41 s |
| V15 | land limit 4 -> 3 | not run | 1/8, -8,319 (paired -8,305) -> out | 26 s |
| prepared, unrun | unfunded BUILD guard; mandatory-feed wheat priority (both default off) | - | - | - |

Same frozen V13 elsewhere: **4 fresh worlds vs live V9-lite 0/4, -3,685** (all valid).

This thread's runs on the same line:
- V8 on Kaggle CPU under official limits: every game exhausted the time bank (invalid). With the limit lifted it
  reproduces the laptop results exactly (5/8, +994) but uses **131-145 s** of overage per game (laptop 19 s).
- V8 + melon rush (sd_melon_fert + sd_melon_rush): 3/8, -2,613 on the same 8 worlds (melon margin +1,050, the rest
  diverges after day 12).
- KB115LT2 with DSM's exact tile plan vs V9-lite: 1/8, -33,159 (fixed plan, cash spiral days 10-18). The morning
  re-plan of the semantic layer is what lifts V8 to 5/8.

## What the evidence says

1. **The development live panel is used up.** Eight iterations were selected on the same 8 worlds; V13's 7/8 there
   sits beside 0/4 on fresh worlds. Recorded panel has been flat at 4/8 since V5 (strict script-fragility: 3/5).
2. **Where V13 loses to V9-lite on fresh worlds** (other thread's accounting, 4 games): revenue +3,145 a game, spending
   +6,830.
   - land: 4 quadrants bought D6/D9/D10 ($7,000) vs V9-lite's 3 on D6/D11 ($3,000);
   - 12 hands in mid-season vs 11 (+$1,400-2,400 wages; 300 vs 280 hand-days);
   - melons: 58-60 sold vs 78-84, **-$5,755 to -$6,555 a game**; V9-lite also sells from hour 9 while we sell at
     8-10 (and the top field now ships its first tile at hour 6);
   - newborn deaths D6-8 in 3 of 4 games (cows/goose placed D6, never fed): the executor's wheat allocation and
     market stock accounting (same-turn pickups double counted, a cash-capped buy latches, optional feeds take the
     mandatory cows' wheat), plus a hire deferred by the 10-order cap;
   - result: +$400-560 at D6 dawn, **-$8,000 to -11,000 at D12 dawn**.
3. **Scale is not the problem by itself**: capping land at 3 quadrants (V15) keeps the crew and loses output
   (-$98k revenue for -$42k spending over 8 games). The plan's marginal admission (does the 4th quadrant plus the
   12th hand pay back, given cash on that day) is missing, not the quadrant.
4. **Price interaction is invisible to the policy.** Its training traces have no prices or rival farm; V13 case 06
   sells 28 more wool and the rival gains more than we do. V14's forecast change flipped a crop ranking and lost.
5. **Runtime is a hard blocker for shipping.** Laptop overage rose from 19 s (V8) to 39-50 s (V12-V14; the laptop is
   shared, so not a controlled comparison) and Kaggle CPU needs about 7x the laptop time for this stack.

## Gaps, in the order they block the goal

| # | Gap | Evidence | Next step |
|---|---|---|---|
| 1 | Does not fit Kaggle's time bank | V8 131-145 s on Kaggle CPU vs 60 s allowed | executor budget governor: per-call cap, drop polish / extra tier passes when the bank is low; verify with the official runner on Kaggle vs V9-lite |
| 2 | No trustworthy scoreboard | dev 7/8 vs fresh 0/4 | fresh-world panel on Kaggle (16+ worlds, both seats) for every step; dev-8 only as a regression check |
| 3 | Early economy D0-12 | melon -$6k a game, D12 -$8-11k | opening: 12 day-0 melons, first tile at hour 6 or earlier (farmer, fertilized melon at cap), bulk before the rival; land D11 instead of D9/D10 unless cash allows |
| 4 | Executor feed / stock defects D6-8 | newborns lost in 3/4 fresh games | wire the prepared wheat-priority and unfunded-build guards, fix the same-turn pickup double count and the buy latch |
| 5 | Marginal admission of land / hands | V15 cap -8.3k; V13 pays +$6.8k for +$3.1k revenue | score the 4th quadrant and 12th hand with their crew, service and cash date, not a cap |
| 6 | Prices and rival not in the policy | V13 case 06, V14 | price-aware value for the plan (own and rival price effects) |
| 7 | Reveal response | V9 rejected on time | revisit after gap 1 |

Tested and ruled out as fixes: more recorded tapes (saturated), a blunt land cap (V15), the net-fertilizer
forecast (V14). Per-hand routing still trails DSM (12.4 vs 13.1 work ops a hand-day, 1.75 vs 2.06 ops a visit) but
is small next to gaps 1-5.
