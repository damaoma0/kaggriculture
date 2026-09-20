# mgt_t10's ladder losses: did something break? (2026-09-20)

Scripts: `scripts/ladder_trace.py` (one replay), `scripts/ladder_batch.py` (all losses + as many wins),
`scripts/ladder_counterfactual.py` (same seed and shops, the opponent's recorded moves, our build live).
Data: `results/fresh/ladder_t10/` (episode list, games.json, one trace per game, batch.json, cf_*.json).

Ladder on 2026-09-20 12:00 UTC: **116-24** over 140 games; by the opponent TEAM's leaderboard score: <1800 25-1
(+30.2k), 1800-2200 32-6, 2200-2500 41-9, 2500-2800 17-8, 2800+ 1-0.

## The traced game: episode 110933872, lost to "sleeping king" (team score 1444, rank 2717)
Ours 92,078, theirs 94,038 (-1,960), we sat in seat 1. Shops: Pet Bru Smo Piz Piz Bru Piz Yarn.
- **Nothing broke mechanically.** The submitted file fed the recorded observations reproduces all 719 recorded
  actions (no timeout, no crash fallback; overage 54-60 s). 278 of 278 hires arrived, no order past the 10-order
  cap, 29 of 6,169 commands had no effect (0.5%).
- **We played the tape faithfully and the tape was wrong for the world.** Final tape 109853597 was recorded in
  Bru Pet Piz Bru Smo Pet Farm Farm; her result there was 91,176 and ours here is +902 on that. Board Hamming
  distance to the tape 0-2 all season, cash within ~1k of her original path at every checkpoint. Router distance
  0.0 at day 6, 3.0 at day 12, 17.5 at day 18, 36.5 at day 24; last switch day 12. This world has three Pizza Shops
  and a Smoothie Shop: the opponent sold 242 milk for 34.1k against our 140 for 20.5k (and 161 wool against 53);
  we sold 233 carrots and 230 eggs into one Pet Cafe and two Brunch Spots.
- **One real failure inside it.** The old tape placed a sheep on (6,2) on day 8 (cared, not fed). On day 9 shop 3
  appeared, the router switched to a tape with an empty pasture there (Hamming 1), nobody fed the sheep and it
  escaped that night. The overlay DID flag the orphan at hour 2, but (a) valued it at one day of wool, below 1.5x
  the wage, and (b) when valued as the animal it still could not act: cash was ~0 (her opening spends to the last
  coin; lowest cash 3) and the HIRE failed. A sheep is 500 plus ~1-2k of wool: about the size of the margin.

## Aggregate: 24 losses against 24 randomly drawn wins
| | losses | wins |
|---|---|---|
| our final / theirs | 108.8k / 114.5k | 109.8k / 100.8k |
| recorded actions that differ from the submitted file | 0 | 0 |
| status problems, lowest overage | none, 53.9 s | none, 54.4 s |
| commands with no effect | 1.64% (0.84% without the expansion games) | 0.59% (0.47%) |
| games with a HIRE that did not arrive | 3 | 0 |
| animals lost before day 25 | 20 in 14 games (9 within 3 days of a switch) | 24 in 16 games (6) |
| tape switch after day 12 | 9 games | 3 games |
| late shops of the world missing from the final tape's world | 2.62 of 4 | 2.42 of 4 |

**Our own score is the same in wins and losses; we lose when the opponent scores 14k more.** The tape mismatch is
universal (2.5 of the last four shops are wrong in wins too), so the losses are that problem meeting an opponent
who fits the world, not breakage. Two distinct failure modes exist and are small:
1. **HIRE shortfall** (3 of 24 losses, 0 of 24 wins): -22.4k, -7.2k, -0.4k. One missing hand shifts every later
   hand index for the day. Two of the three are games where our own sheep expansion spent the cash.
2. **Orphaned animal after a tape switch**: ~0.3 a game, equally in wins and losses; cannot be rescued by a hired
   hand in the opening third because there is no cash. A router rule (do not strand an animal bought in the last
   two days) is the only place to fix it; the blanket `animal_weight` tested -228 earlier.

## The sheep expansion fires on the ladder (it never did in our panels)
Against V50 the glut gate declines almost everywhere; on the ladder it committed in 5 of the 48 traced games (4
losses, 1 win), with 300-500 "dead" commands each - the tape's wheat commands on tiles we turned into pastures -
and 21-53 hidden hand-days at 12th-14th-hand wages. Counterfactual (the harness reproduces all 8 ladder results
to the dollar for `mgt_t10`):

| episode | recorded | `mgt_t10` | `mgt_k0` (= b1 code) | `mgt_k2` (expansion off) |
|---|---|---|---|---|
| 110950148 | -22,371 | -22,371 | -21,863 | -31,314 |
| 111182088 | -7,829 | -7,829 | -16,946 | -9,491 |
| 110980406 | -1,585 | -1,585 | -8,873 | -11,441 |
| 111069352 | -415 | -415 | -1,045 | -9,983 |
| 111159609 | +11,913 | +11,913 | +12,682 | +8,324 |

- **The expansion is not the bug**: switching it off is worse in 4 of 5. It is a spoiler: in 111182088 it costs us
  21.7k of own cash and the wool-selling opponent 23.4k.
- **The current build is 7-9k worse than the submitted `mgt_t10` in two of these worlds** (one more sheep, +2.3k
  wages, +1.0k wheat, -1.5k wool). b1's measured gain (+21..+24) came from panels where the expansion never
  fires. Any b1-family submission needs this checked first.
