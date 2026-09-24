# The leaders' new opening inside the tape architecture (2026-09-23/24)

**Result: it measurably fails, for established reasons.** No submission. `mgt_m1` / `mgt_t10` are unchanged.
All panels: the 180 frozen ladder worlds of `mgt_t10` (`results/fresh/newphase_20260923/coverage_worlds.json`), paired
against `mgt_lib584` (= `mgt_m1`), run on Kaggle (dollar-exact; rebuilt-m1 controls 20/20 identical each time).
Report script: `scripts/report_opening_panel.py`. Frozen-opponent caveat as always.

## What is learnable (measured)
- DSM, DECEM, the current Mother-Goose and Vadim play one fixed opening (day-6 boards identical, whatever the shops).
- Their day-6 board is within the router's 8-tile limit of 10-16 of our 584 tapes on the **day-6 morning only**
  (0 tapes on days 3-5 and from day 7 on; `scripts/opening_handoff_probe.py`).
- A recorded DSM opening replays open-loop in our ladder worlds: the best source reproduces the day-6 board exactly
  in 14/16 early-ladder worlds (`scripts/opening_replay_probe.py`), but only 4/16 in the later, stronger-opponent
  worlds (`scripts/opening_variant_probe.py`).

## Attempt 1: DSM's opening grafted onto our tapes (O1, `--opening`, day-6 handoff)
| build | wins (of 180) | paired margin vs m1 | day-6 handoff |
|---|---|---|---|
| `mgt_o1`: opening through our chassis and layers | 127 → 2 | **−66,130** | median 12 tiles off; fallback in 133 |
| `mgt_o1r`: opening passed through raw (layers from day 6) | 126 → 2 | **−87,443** | median 15 tiles off; fallback in 132 |

1. **Budget-exact recording.** DSM over-requests hires on purpose (8 + 8 on day 1; 3 + 1 arrive with about 6 coins).
   Against opponents whose day-0 wheat buy raises the price, we reach day 1 with 2 coins instead of 6, lose a hand,
   and every later hand index shifts. Our hire / budget guards rewrite the stream instead (o1). Fixing hires to the
   counts that arrived, plus one wheat sale when short, puts all 16 test openings within 8 tiles; 4/16 are exact.
2. **Hidden state breaks the graft even when the tiles match.** In the 46 worlds with an eligible handoff (7-8 tiles)
   O1r still lost about 51k a game. At the handoff we hold 0 wheat / 0 carrot / 1 strawberry seeds and 5 wheat;
   the tape's own world had 9 / 3 / 4 seeds and 20 wheat. Mother-Goose's days 6+ plant, feed and place animals
   from stock and pastures her own days 0-5 created. In one traced world the tape bought 4 cows where m1 bought
   10 (milk 27k against 51k), with 628 failed commands against 51. Seven matching tile labels is not a compatible
   plan state.

## Attempt 2: DSM's own games as tapes (coherent plan, `--tape-dir data/dsm_tapes --no-fix-opening --normalize-hires`)
109 DSM tapes (`scripts/extract_dsm_tapes.py`); HIREs cut to the counts that arrived in DSM's own game.

- **Replay fidelity** (`scripts/dsm_tape_fidelity_probe.py`: 10 tapes x 3 of our worlds, the tape's OWN shops
  forced). Board within 8 tiles of DSM's own board on d6 / d9 / d12 / d24: raw 77 / 40 / 30 / 33%, **hire-fixed
  80 / 50 / 50 / 57%**. Collapses (final < 20k): 6/30 raw, 5/30 fixed. Median final 95.5k against DSM's own
  109.2k. The collapse mechanism: about 1 coin on days 1-2, then unconditional land / animal purchases leave nothing
  for wages; no hands, no harvest, zero cash from day 12. A closed-loop policy's recording stays budget-exact for
  the whole early game.

| build | wins (of 180) | paired margin vs m1 | notes |
|---|---|---|---|
| `mgt_dsm_a`: DSM library, hire-fixed, m1's layers | 124 → 81 | **−7,081** (−9,663..−4,673) | 63 better / 106 worse; strawberry −37.5 units, melon −24.3; +287 failed commands; hire-short 38 |
| `mgt_dsm_b`: same without budget / hire guards | 125 → 63 | −13,131 | the guards prevent collapse |
| earlier 108-tape DSM library (09-22, raw) | | −9,921 (vs V56) | |

Even perfectly executed, a 109-tape library carries the coverage handicap measured in
`docs/losses_winners_coverage_20260923.md` (146 random Mother-Goose tapes: −3.2k against 584).

## Why it failed: two mechanical desynchronisations, not a measurement of the opening (traced 2026-09-24)

`scripts/trace_opening_o1r.py` (day by day, `mgt_o1r` against `mgt_m1` in the same recorded world; `o1r_traces.json`):

| day | world 110921861 (opening reproduced): o1r board vs DSM / vs its tape; failed commands o1r / m1; cash o1r / m1 | world 111828437 (opening broke): same columns |
|---|---|---|
| 1 | 0 / –; 2 / 0; 7 / 25 | 0 / –; 6 / 0; 2 / 22 (DSM had 6) |
| 3 | 0 / –; 1 / 0 | 9 / –; 17 / 0 (a hand short since day 1) |
| 6 | 0 / 0 at handoff (7-tile tape); 15 / 0 | 11 / 16 at handoff (fallback, no tape within 8); 53 / 0 |
| 7-8 | – / 15-17; 22-29 / 0 | – / 42; 47-73 / 0; cows start dying |
| 10 | revenue 9.3k / 17.8k (melon day) | revenue 3.1k / 16.1k |
| 15-27 | – / 11-17; 23-36 a day / 3-4 | – / 40-64; 87-110 a day / 0; no cows left |
| final | 107,883 / 137,122 (rival 66,748 / 44,707) | 26,482 / 169,131 (rival 202,734 / 167,809) |

1. **The opening replay breaks on day 1 in most worlds (132 of 174 in the panel).** The recording is budget-exact:
   a few coins of price drift (the opponent's own day-0 wheat buy) leave us 2 coins where DSM had 6, one hire fails,
   every later hand gets the wrong commands, and the board is 9-11 tiles off DSM's by day 6. This is a replay
   feasibility failure. The hire-trimmed + sell-when-short variant brings all 16 test openings within 8 tiles
   (`scripts/opening_variant_probe.py`), which shows it is fixable mechanically.
2. **Even a perfect opening desynchronises at the handoff.** Where the opening reproduced exactly (0 tiles from DSM
   every day through 6), the tape's own commands fail from day 6 on (15-42 a day against 0) and our board drifts to
   15-17 tiles from the tape within two days. Mother-Goose's day-6+ commands presuppose her own days 0-5: seeds and
   feed stock she bought (we hold 0 / 0 / 1 seeds and 5 wheat against 9 / 3 / 4 and 20), pastures and cows at her
   coordinates, melons at her tiles. Board labels within 8 tiles do not make the plan state compatible.
3. **So −87k is desynchronisation, and the opening's value was never measured.** The average mixes the collapse
   worlds (opening broke, fallback handoff: about −99k) and the clean-opening worlds (handoff desync: about −51k).
   The DSM library (`mgt_dsm_a`, −7.1k) is the only coherent test (DSM opening + DSM continuation), and it is
   contaminated by the same budget-exact replay (half the replays drift by day 12, 1 in 6 collapse).

**Correction.** The earlier line "their plans are coherent only together with their own price-aware execution"
overstated what was shown. What the evidence supports: (a) a closed-loop agent adjusts purchases and hires by a few
coins to reach the same board (DSM's boards identical across games while its actions differ), so a recording is
budget-exact and fragile; (b) grafting two plan families breaks on hidden state at the handoff. Both are execution /
feasibility mechanics. Whether the leaders' PRODUCTION PLANS respond to prices is a separate question
(`results/fresh/newphase_20260923/price_awareness/`).

## Does this machinery generalise into plan / semantics learning?
- **Learning side: yes.** Boards are shop-driven (70-100% of count variance by day 9; `plan_jitter/summary.md`),
  the opening is fixed, and the extraction built here (hire-normalised compact tapes, per-step hands and cash,
  day-start boards, shop sequences for 109 DSM games plus 120 other-leader full replays) is exactly the dataset a
  shop-conditioned production-target model needs, past day 9 as well.
- **Execution side: this is the bottleneck, not the learning.** Every attempt to turn targets into moves without
  the source policy's adaptation has failed: the grafts here, the DSM library, and earlier continuation executors
  (−4k to −12k). A usable plan learner needs a price- and budget-aware executor that can reach a target board from
  our actual state. That is a multi-week build and cannot land by 2026-09-28.

## Follow-up checks (2026-09-24)

**Shop-conditioned targets past day 9** (`scripts/shop_target_predictability.py`; ridge on shop counts, leave-one-out,
DSM's 109 exact boards). Out-of-sample R² of DSM's day-d counts from the shops revealed by day d:

| day | sheep | cows | geese | strawberry | tomato | wheat | carrot |
|---|---|---|---|---|---|---|---|
| 9 | 0.74 | 0.64 | 0.63 | 0.67 | – | 0.66 | −0.06 |
| 12 | 0.84 | 0.89 | 0.74 | 0.85 | 0.46 | 0.51 | 0.56 |
| 15 | 0.92 | 0.86 | 0.91 | 0.89 | 0.72 | 0.54 | 0.63 |
| 18 | 0.90 | 0.77 | 0.61 | 0.88 | 0.81 | 0.52 | 0.59 |
| 24 | 0.75 | 0.71 | 0.34 | 0.57 | 0.62 | 0.56 | 0.64 |

Mother-Goose old (584 tapes) is similar (day 15: 0.90 / 0.86 / 0.84 / 0.81 / 0.69). The leaders' production plans are
learnable from shops through the whole season, not only the opening. The learning side generalises; execution is
the bottleneck.

**Why t10 is rated above m1 while weaker on the 2750-3000 panel.** On the panel, t10 − m1 is negative in all three
kinds of game, including t10's own ladder games (−314; m1's own −510; team-vs-team −343, CI −722..−8), so the panel
does not favour the build that actually played. On the real ladder, t10 played 148 games at 81.8% against opponents
rated about 2,135 before m1 existed. In the shared window since, its higher rating drew stronger opponents (2,563
against 2,426), and it won 64.6% against m1's 67.6%. The rating gap is head start plus matchmaking.
`mgt_y3` − m1 is positive in all three kinds of game (+289 / +182 / +343).

## DSM library: how much is replay fidelity? (2026-09-24, existing panel data, no new games)

`mgt_dsm_a` (router over 109 DSM tapes, hires trimmed to arrivals, m1's guards) on the same 180 worlds, paired with
t10's recorded result in each world (the panel reproduces t10 to the dollar; m1 runs exist for only 61 of these
worlds: −6,663 vs m1 there). All 180: **−5,916** mean, median −4,436.

| replay condition (outcome-defined) | worlds | margin vs t10 recorded | own cash | rival cash |
|---|---|---|---|---|
| no hire shortfall, board within 8 tiles of the tape all game | 113 | **+754** (±2,080) | −2,236 | −2,989 |
| no hire shortfall, board drifts past 8 tiles | 27 | −13,337 | −10,577 | +2,760 |
| hire shortfall, board within 8 tiles | 22 | −12,694 | −10,240 | +2,454 |
| hire shortfall and drift | 18 | −28,375 | −18,528 | +9,847 |

- Hire shortfalls: 40 worlds, first on day 1 in 12 (the budget-exact opening), day 7 in 18, day 8 in 4 (−59,921 mean).
  Traced world 111574686: the tape spends day 6 down to 4 coins (animals and seeds that its own world funded),
  ends day 7 on 5 coins, asks for 8 hands on day 8 and gets 3. The existing hire guard only looks two hours ahead,
  and it cannot trim purchases once the HIRE itself is unfunded, so an overnight shortfall is invisible to it.
- The faithful-replay row is conditioned on outcomes (a world that replays cleanly is also a friendlier world), so
  +754 is an optimistic ceiling for a perfect budget guard, not an estimate of one. Even that ceiling is break-even
  with t10; y3 is about +0.5k over t10 on the same worlds (+183 over m1; m1 is +314 over t10 in t10's own games).
- **Conclusion: the DSM opening cannot beat y3 by 2026-09-28** by any route measured: graft (O1r −51k even in the
  46 eligible-handoff worlds), DSM library (ceiling ≈ break-even with t10). The handoff alternatives (another day,
  reconcile before handoff, select on the reached board, opening as production targets) all need the target-reaching
  executor described above; "select on the reached board" is what O1r already does.
