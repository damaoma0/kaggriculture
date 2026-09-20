# The three cheap items (2026-09-20)

Plan approved by the user: melons first, production sized to shops, the non-wage spending gap; the executor parked.
Baseline for every test: `mgt_b1` = submitted `mgt_t10` + sell-one-step-early (`sell_lead`). Leave-one-out = her
recorded worlds with that world's tape removed, live V50, paired by world (40 worlds ~2 min, 80 worlds ~4 min).

## 1. Melons to market first: there is no timing to gain against this opponent class
`scratchpad/melon_dbg.py`, 40 worlds with melon tracing in `scripts/mgt_loo.py`:
- V50 (and V48: same tapes) and our agent play the IDENTICAL melon day, because every V45-family agent and her old
  policy share the public opening: the same 12 tiles planted on day 0, harvestable at d10 h00 (yield 5-6), harvested
  at h06-h10 and two at h20-21, and sold in the same seven lots on the same steps (6 at 272, 24 at 250, 12 at 226,
  6 at 197, 6 at 178, 6 at 156, 12 at 131), both with SELL MELON at order index 0. First melon sale in the same step
  in 36 of 40 worlds; we are first in 0.
- The engine fills order index i of both players in per-unit lockstep at one shared quote, so identical lots at the
  same step and index split the curve exactly. No shop buys melons (only the town centre, 1 a day), so the curve
  (250 - 0.01 x^2) is walked down once and never recovers: melon revenue is purely who sells more units earlier.
- Her +2.7k melon price edge over her PEERS exists because their openings differ (her median melon day 10.5 vs
  11.0). Against the 2000-2800 band it is a dead heat by construction.
- What would break the tie is being one step ahead on each lot (~+25 a unit, ~+2k own and about as much off the
  rival). Runners cannot do it: hands hired at h0-1 act from h1-2, the field is 3-6 steps from the shed, and her
  day-10 route already harvests from h05 and delivers from h09. It needs re-routing day 10, i.e. the executor.
  V50 realises 198 a melon against our 186 only because we also sell a late second wave (20 units at 100-130).

## 2. Production sized to the shops
**2a. More sheep where Yarn Stores pile up.**
- Converting her wheat fields is harmful beyond the wheat: her crew feeds animals with wheat they HARVEST on the way
  (FEED needs wheat in the unit's own inventory), so a pasture on a wheat tile breaks those chains and HER sheep
  starve (213 dead commands, her flock 13 -> 10 in world 109767903). Fixed by putting the extra flock in the SE
  quadrant, which her plan never buys (4,000; touches the shed at (5,5); `se_quadrant=1`).
- Two logistics bugs found and fixed on the way: a 54-wool DROP into a shed near its 100 cap destroyed a third of it
  (now PLACE what fits and SELL in the same step), and hands busy with COLLECT never came home before midnight (now
  deliver once everything is fed and it is 17:00 or the load is 24).
- Result: late expansions lose (day 15-16: -2.3k and -3.0k; too few production cycles left for 500 a sheep + 4,000
  land + 59 a day feed + a 12th-14th hand at 144-377 a day). Early-only (`last_day=12`, `mgt_c1`), 80 worlds: fires
  in 3 worlds, +11.1k, +7.6k, -7.6k; mean **+139 (-191..+557)**, W-L 58-22 vs 59-21. High variance, not
  significant. **Not shipped**; left behind `se_quadrant=1`.
- Her additive Yarn rule under-counts in multi-Yarn worlds (she ends on 14-20, V50 on 15), but her late additions are
  +2 for the same reason ours lose: the economics of a sheep bought after day 12 are thin.

**2b. Crop mix keyed to shops = tape choice.** In this architecture the crop mix IS the tape, so the lever is the
router. Probe (`MGT_FREEZE_DAY=12`, `MGT_PICK=k`): freezing on the k-th best tape at day 12 gives +4,436 / +2,226 /
+1,588 / +968 for k = 0..3, so the ranking is informative and switching after day 12 is worth nothing (+4,345
unfrozen). An oracle over the top four would be +6,196 (33-7 instead of 28-12): ~1.8k of headroom, part of it
unknowable at day 12 (shops 5-8 are hidden). First attempt to claim it - a term preferring tapes made for a typical
FUTURE (`future_weight`) - is strongly negative on 80 worlds: -2,371 / -2,385 / -4,295 for weights 0.25 / 0.5 / 1.0
(it swamps the match on the known shops at the early decisions). Not kept.

## 3. Where her spending gap to peers goes (`scripts/mg_spend_gap.py`)
All 72 replays re-simulated from their seeds with both sides' recorded actions inside the transaction ledger; the
final cash reproduces to the dollar in 72 of 72.

| per game, her minus opponent | old policy (+3,548) | new (+2,825) |
|---|---|---|
| total spending | -2,919 | -2,800 |
| wheat bought | **-2,573** (137 vs 200 units) | -1,195 (200 vs 227) |
| hires | -592 | -868 |
| seeds | -338 | -561 |
| animals, land, fertilizer | +585 | -176 |
| wheat, net cash (sold - bought) | **+1,447** (+10,744 vs +9,297) | **+5,032** (+12,330 vs +7,298) |
| revenue excluding wheat | +1,755 | -3,813 |

- The non-wage gap is WHEAT, not seeds - and most of the "wheat bought" line is ROUND-TRIP volume, not consumption.
  Physical wheat per game, old policy (cut + bought = fed + sold to within a unit or two on both sides):

  | | cut from fields | bought | fed to animals | sold |
  |---|---|---|---|---|
  | her | 588 | 137 | 320 | 403 |
  | opponents | 564 | 200 | 328 | 428 |
  | her, new submissions | 672 | 200 | 325 | 536 |
  | opponents of the new | 529 | 227 | 316 | 435 |

  She FEEDS almost exactly what her opponents feed (320 vs 328), so the -2,573 on purchases is not thrift on feed: her
  opponents buy 63 more wheat and sell 25 more (their wheat revenue is 1,126 higher). Net of the round trip her wheat
  position is +1,447: she cuts 24 more wheat from her own fields, feeds 8 fewer and buys at 35.1 against 37.0.
  (An earlier version of this note attributed the purchase gap to her demand-conditioned feeding. That was wrong: the
  feeding rule shifts WHICH days she feeds, not how much she feeds against these opponents.)
  Her +3,548 over peers adds up exactly: non-wheat revenue +1,755, wheat net +1,447, hires +592, seeds +338,
  animals / land / fertilizer -585.
- The new submissions changed the business: 169 wheat seeds against 135, 672 wheat cut against 529, 536 sold against
  435, +5.0k net on wheat and -3.8k on everything else. Against peers she now wins as a wheat farmer.
- For us: nothing to build. Our tapes are her old policy, so the feeding economy is inherited; what our overlay adds
  back is visible in the leave-one-out ledgers (wheat +0.5k, hires +0.3k a game) and is already gated on value.

## The hire-cap contradiction, resolved
Both statements were mine and they are not about the same thing. The measurement stands: capping hires on a replayed
tape is actively bad (cap 11 -3,857, cap 12 -2,530, cap 13 -895), because the tape's commands for the missing hands
are simply not executed - planned work is deleted, nothing is re-planned. Her lower wage bill (-0.6k to -0.9k, a fifth
of her cost edge) comes from a PLAN that needs 9.3 hands a day instead of 9.5, not from a cap. "Avoid the 12th and
13th hand" was the wrong lesson and is withdrawn as a recommendation for the base. Where the Fibonacci wage does bind
is our own overlay: each of its hands is the 12th-14th hire of the day (144-377), which is why the care top-up only
hires when a run is worth 1.5x its wage and why the sheep expansion does not pay.

## Where the current build stands, on a fresh and larger block (seeds 176000-176127, both seats, 256 games each)
`mgt_b1` (= submitted `mgt_t10` + sell one step early). The 32-seed block 174000-174031 was the one every change was
gated on, and it flattered us (84%); these seeds were never looked at before.

| Opponent | W-L | Win rate (95% CI) | Mean margin (95% CI) |
|---|---|---|---|
| V50 | 183-73 | 71.5% (63.7-78.9) | +3,482 (+2,239..+4,746) |
| V48 | 197-59 | 77.0% (69.9-83.6) | +5,125 (+3,795..+6,448) |
| frozen benchmark | 199-57 | 77.7% (70.7-84.4) | +5,196 (+3,903..+6,518) |

## Router headroom, second look: the ranking already takes what is knowable
Offline on the 160 frozen-pick games (40 worlds x the four best tapes at day 12), choosing among the four by any
single feature available at day 12 is WORSE than taking rank 0 (+4,436, 28-12):

| Rule among the top four | Mean margin | W-L |
|---|---|---|
| highest recorded cash of the tape's own game | +2,644 | 28-12 |
| highest recorded margin | +2,016 | 24-16 |
| lowest board distance | +3,859 | 28-12 |
| most / fewest sheep in the tape | +2,548 / +1,836 | 24-16 / 26-14 |
| most strawberries | +3,148 | 29-11 |
| HINDSIGHT: most of shops 5-8 matching ours | +3,923 | 28-12 |
| oracle | +6,196 | 33-7 |

Within a world the only feature that correlates with the outcome is the rank itself (-0.35); recorded cash, margin,
herd, strawberries, board distance and even the hindsight match of the hidden shops are all within +-0.12. The 1.8k
between rank 0 and the oracle is therefore mostly variance between near-equivalent tapes (weeds, the rival's
reaction), not information a better ranking could use. Learning the router's weights is not the next lever either.
