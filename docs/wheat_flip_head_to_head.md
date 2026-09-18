# The opening wheat flip, head to head

Question (user): "remember Nash's equilibrium is at 5" — what does our V45 70-unit opening wheat
flip cost us, against our own benchmark and against Mother-Goose? Is it over-trading, or a
deliberate spoiler?

## What "equilibrium at 5" means precisely

`docs/wheat_flip_equilibrium.md` certified it (1,107 official-engine comparisons): in the opening
wheat subgame with five feed wheat required, the pure Nash equilibrium is to **buy the five feed units
on turn 0 and keep them** — not a five-unit *flip*. For a purely speculative round trip, the equilibrium
is no trade. That opening (`sp_nash5`) is the capital fix already built into
`agents/v45_event_opening_fixed.py`, never submitted. Our live agent (the frozen benchmark) still
opens `BUY 70 / SELL 70`.

Mother-Goose opens `BUY 13, BUY 5, SELL 13` then `SELL 5, BUY 5` in all 30 of her games: she holds the
five feed units, plus small 13- and 5-unit round trips. That is the public router's original tape,
before V45 replaced it with the 70-unit flip.

## Engine mechanics: turn-1 cash margin, row minus column

Every player ends turn 1 holding its five feed wheat, so cash is directly comparable
(`results/fresh/wheat_flip_matrix.log`).

| | flip 0 | flip 5 | flip 13 | flip 20 | flip 28 | flip 35 | flip 50 | flip 70 | Nash 5 | MG | worst |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| flip 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | −7 | −1 | −7 |
| flip 5 | 0 | 0 | +14 | +23 | +31 | +38 | +48 | +61 | −1 | +17 | −1 |
| flip 13 | 0 | −14 | 0 | +25 | +46 | +64 | +94 | +129 | −1 | +35 | −14 |
| flip 20 | 0 | −23 | −25 | 0 | +38 | +63 | +112 | +162 | −1 | +45 | −25 |
| flip 28 | 0 | −31 | −46 | −38 | 0 | +43 | +112 | +188 | −1 | +45 | −46 |
| flip 35 | 0 | −38 | −64 | −63 | −43 | 0 | +93 | +188 | −1 | +55 | −64 |
| flip 50 | 0 | −48 | −94 | −112 | −112 | −93 | 0 | +150 | −1 | +65 | −112 |
| **flip 70 (ours)** | 0 | −61 | −129 | −162 | −188 | −188 | −150 | 0 | −1 | **+75** | **−188** |
| **Nash 5** | +7 | +1 | +1 | +1 | +1 | +1 | +1 | +1 | 0 | 0 | **0** |
| MG | +1 | −17 | −35 | −45 | −45 | −55 | −65 | −75 | 0 | 0 | −75 |

- **In isolation and symmetrically, every flip nets exactly zero.** Buys are quoted post-buy, so a
  closed round trip against an unchanged market is neutral. The 70-flip does not give value away by
  itself.
- **Larger flips lose to smaller ones.** The 70-flip is the most exploitable size (worst case −188).
- **The flip does spoil small-flip openings.** Against Mother-Goose's opening, 70 gains +38 and costs
  her −37 (+75 margin).
- **Nash 5 is the only opening that cannot lose** (worst case 0), and it exploits nobody.

## Head to head against the frozen benchmark (self-play, seeds 173000-173015, 32 games each)

| Our opening | W-T-L | Mean margin (95% CI) |
|---|---|---|
| flip 70 (identity check) | 0-32-0 | +0 (0 to 0) |
| flip 0 | 0-32-0 | +0 (0 to 0) |
| **Nash 5** | **32-0-0** | **+1** (1 to 1) |
| **flip 5** | **32-0-0** | **+234** (+231 to +237) |
| **flip 35** | **32-0-0** | **+1,375** (+1,367 to +1,387) |

The turn-1 edge is amplified in the mirror match: +188 at turn 1 becomes +1,375 at the end, with a
remarkably tight distribution (every game +1,366 to +1,493). The turn-0 perturbation re-draws weeds
and shops in 28-30 of 32 games; both near-identical agents then make identical purchases, and the
extra margin shows up mainly in melon sales (+1,264 relative in flip-35 games). That fits two clones
racing to sell the same glut, with the small cash asymmetry deciding who sells first — the mechanism
is partly identified. Nash 5 changes nothing downstream and wins every mirror match by exactly one
coin, which is real under win/loss scoring but fragile against any non-identical opponent.

## Against Mother-Goose's recorded tape (no cushion, 30 games each)

| Our opening | Her day-0 net wheat cost | Hire fails on day 1 | Her tape coherent all game | Her margin (95% CI) |
|---|---:|---:|---:|---|
| flip 70 (benchmark) | 173 | 30/30 | 0/30 | −17,962 (−25,791 to −11,217) |
| flip 35 | 163 | 30/30 | 0/30 | −17,806 (−25,730 to −11,057) |
| flip 5 | 144 | 0/30 | 30/30 | +12,458 (+10,213 to +14,922) |
| flip 0 | 135 | 0/30 | 30/30 | +12,657 (+10,375 to +15,145) |
| Nash 5 | 136 | 0/30 | 30/30 | +12,710 (+10,418 to +15,218) |

Her opening leaves about 29 coins of slack. Flips of 35 and above push her day-0 wheat cost past it,
one hire fails on day 1 in every game, and her frozen tape collapses; below that she plays her full
plan and beats us by ~12.6k.

This ~30k swing is an **upper bound** on the spoiler value against her. A frozen tape cannot react,
while her live policy does adjust at the affordability margin (it planted 5 wheat instead of 7 when
short in one recorded game). None of her 30 recorded opponents opened with a 70-flip, so there is no
direct evidence of how her live policy handles one.

## Reading

1. **The 70-flip is not bad in absolute terms.** It costs nothing in isolation or against another
   70-flipper, and −1 against the Nash opening.
2. **It is a spoiler, and an exploitable one.** It profits against small-flip openings and can break a
   budget-exact plan, but every smaller flip beats it, and in the mirror against the V45 family that
   exploitation compounds: a 35-flip beats our benchmark 32-0 by ~1.4k.
3. **Flip 35 dominates flip 70 on both tests run here.** It wins the mirror by ~1.4k and still breaks
   Mother-Goose's tape. Its cost is exposure to smaller flippers (13-20 beat it by ~64 at turn 1, which
   could compound the same way in a near-mirror).
4. **Nash 5 is the safe choice.** It is unexploitable, wins the exact mirror by one coin, and gives up
   the spoiler effect entirely — against Mother-Goose we would then face her full ~12.6k policy edge.

## Not yet established

- All full-game evidence is against our own benchmark and one recorded opponent. The payoff of any
  flip depends on the opponent's own opening orders, so flip 35 / flip 28 / Nash 5 should be run
  against the other public agents (Two Coins, V44, Farming V5) before adopting one.
- The mirror-match amplification is specific to near-identical agents; against a different agent the
  turn-0 edge may stay at tens of coins.

Scripts: `scripts/build_selfplay_candidates.py` (`sp_flip*`, `sp_nash5`), `scripts/selfplay_gate.py`,
`scripts/tape_vs_bench.py live`, `scripts/report_wheat_flip.py`. Results: `results/fresh/selfplay/`
(`flipgate`), `results/fresh/tape_vs_bench/flip/`, `results/fresh/wheat_flip_report.log`,
`results/fresh/wheat_flip_matrix.log`.
