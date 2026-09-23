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

## Why, in one line
The leaders' opening is learnable as boards but not executable from recordings: their plans are coherent only
together with their own adaptive, price-aware execution (budget-exact purchases, just-in-time seeds,
over-requested hires). Our tape format captures the actions, not the adaptation, and our tapes' later plans depend
on their own early investments.

## Does this machinery generalise into plan / semantics learning?
- **Learning side: yes.** Boards are shop-driven (70-100% of count variance by day 9; `plan_jitter/summary.md`),
  the opening is fixed, and the extraction built here (hire-normalised compact tapes, per-step hands and cash,
  day-start boards, shop sequences for 109 DSM games plus 120 other-leader full replays) is exactly the dataset a
  shop-conditioned production-target model needs, past day 9 as well.
- **Execution side: this is the bottleneck, not the learning.** Every attempt to turn targets into moves without
  the source policy's adaptation has failed: the grafts here, the DSM library, and earlier continuation executors
  (−4k to −12k). A usable plan learner needs a price- and budget-aware executor that can reach a target board from
  our actual state. That is a multi-week build and cannot land by 2026-09-28.
