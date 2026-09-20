# The ladder panel, and the three defects from the ladder-loss trace (2026-09-20)

## The measurement: `scripts/ladder_panel.py` over `data/ladder_panel/`
Our natural-seed panels play V50, V48 and the old benchmark. Against them the overlay's sheep expansion never
commits and cash never runs as thin as it does against the ladder's price impact, so whole code paths were never
exercised. The ladder panel replays the worlds we actually met:
- `scripts/ladder_panel_fetch.py <submission>` downloads every completed ladder game of one of our submissions
  (~32 MB, ~2 s each), keeps seed, shops by day, the OPPONENT's 719 recorded actions, both results, and deletes the
  raw file (~20 KB a game). On disk: 141 games of `mgt_t10` (56368334) and 237 of `cand_v1` (56341683), 7.9 MB.
- `scripts/ladder_panel.py run <builds>` plays each build live (Kaggle loader) against the recorded opponent with
  the recorded shops forced; `report` gives W-L, mean margin, the paired difference to a reference build, the
  expansion games and the hire-short games separately. 141 games take ~7 min on 4 workers.
- **Validity: `mgt_t10` reproduces all 141 of its recorded ladder results to the dollar (117-24, +10,094).** The
  opponent cannot react; that is identical for every build compared, and a game is dropped from a comparison if the
  opponent's tape breaks against a build (never happened so far).
- Limits: 141 games contain 8 expansion games and 5 hire-short games - enough to see a defect, not enough to tune
  the expansion (per-game swings of +-7k). It measures builds that stay close to the recorded game; a build that
  plays very differently meets an opponent tape that was answering someone else.

## 1. The "mgt_b1 regression" (bisected on the panel)
| build | what | paired vs `mgt_t10` | better / worse / same | 8 expansion games |
|---|---|---|---|---|
| `mgt_q2` | t10's overlay + sell one step early | **+16 (+6 to +28)** | 77 / 10 / 54 | +7 |
| `mgt_q3` | current overlay, no sell-lead | -63 (-289 to +138) | 6 / 17 / 118 | -893 |
| `mgt_k0` | current overlay + sell-lead (= b1) | -46 (-271 to +155) | 74 / 21 / 46 | -869 |

- **Sell-one-step-early is innocent**: +16, positive in 77 of 87 changed games, and it does not change the flock.
- The difference is the overlay, and inside it one change: the expansion's labour model (hands from `_shp_runs`
  with shared top-up labour instead of the submitted per-head count). Single reverts on the 8 expansion games
  (mean margin): t10 +9,705; current +8,812; **labour model reverted +9,759**; collect-until-22 +8,532;
  no early delivery +8,921; one DROP +8,939; all four reverted = t10 exactly.
- It is not a clean regression: the new model is 4-9k worse in three games (two are the same world family) and
  0.5-6.6k better in four (it opens an expansion t10 declined in 111120009: -8.0k -> -1.4k). Net -0.9k on n=8 is
  inside the noise. Decision: go back to the submitted labour model (`labour_model=count`), which has 141 ladder
  games behind it, and do not tune the expansion until a panel has enough expansion games.

## 3. Hire shortfalls (done before 2 because it is the big one)
**The cause is not the expansion.** All shortfalls are on days 5-9 with cash under 500, before the expansion can
spend anything (it keeps a 2,000 margin). Her opening spends to the last coin, and against ladder price impact a
few coins are missing: (a) the tape lists 440 of seeds BEFORE eight HIREs with 456 cash, three hands never come
(110950148, day 9); (b) hour-0 purchases leave 73, the four hires of hour 1 cost 76 (three games, day 8);
(c) 4 cash for 8 of wages (day 5), 22 for 34 (day 9). One missing hand shifts every later hand index that day.

`hire_guard=1` (overlay, last step before the action leaves): walk the order list with the engine's prices; if a
HIRE now, or a tape HIRE in the next two hours, would not find its wage, put SELLs first and HIREs before every
purchase, then sell a few units of shed stock in front, and if there is nothing to sell buy a little less wheat
or wheat/carrot seed this hour. Games where no hire is at risk stay byte-identical.

| build | W-L | paired vs `mgt_k0` | hire-short games |
|---|---|---|---|
| `mgt_k0` | 117-24 | | 5 |
| `mgt_h1` guard on the current step only | 118-23 | +227 (-0 to +601) | 3 |
| **`mgt_h2` + two-hour look-ahead** | **118-23** | **+260 (+10 to +636)** | **0** |

The five games: -21,863 -> -1,395, -1,045 -> **+10,506** (a loss becomes a win), -7,575 -> -5,818, +107 ->
+2,032, +1,308 -> +3,328. The guard fires in 36 of 141 games (0.5 units sold, 0.1 units trimmed a game).
The 22k game is a one-off in size (two shortfalls, one of three hands); the typical shortfall costs ~2k and
the rate is 3.5% of games, so the defect was worth ~0.26k a game and one win in 141 - real, cheap, not the
biggest number in the project.

## 2. Orphaned animals: a narrow router rule (`--cfg strand_penalty=4.0`)
A live animal of ours on a tile where the candidate tape has no animal today NOR two days on is an animal nobody
will feed; each one adds `strand_penalty` to that tape's distance (the current tape included). Overlay tiles are
excluded. Unlike the blanket animal-tile weight (-228 earlier) it is one-directional and only about animals that
exist.

| build | W-L | paired vs `mgt_k0` | better / worse / same |
|---|---|---|---|
| `mgt_s2` penalty 2 | 118-23 | +241 (+36 to +483) | 10 / 2 / 129 |
| **`mgt_s4` penalty 4** | **120-21** | **+458 (+172 to +785)** | 15 / 3 / 123 |
| `mgt_s8` penalty 8 | 120-21 | +454 (+159 to +786) | 17 / 4 / 120 |

What it changes is mostly LATE switches (days 15-24) that stranded animals: 18 games move, three losses become
wins (110980138 -1.3k -> +3.8k, 110956982 -3.2k -> +3.2k, 110976828 -5.2k -> +1.5k) and the hire-short game
110954150 goes -7.6k -> +4.4k; the traced game improves -1,960 -> -723 (still lost: the world is wrong for the
tape). Orphan-days fall 0.65 -> 0.49 a game. This matches the aggregate of the loss study: a tape switch after
day 12 occurred in 9 of 24 losses against 3 of 24 wins.

## Combined candidate `mgt_m1`
`build_mg_tape_agent.py mgt_m1 --cfg hamming_weight=1.0,strand_penalty=4.0 --settings sell_lead=true --sheep
labour_model=count,hire_guard=1`

| build | W-L (141) | mean margin | paired vs `mgt_t10` | hire-short games |
|---|---|---|---|---|
| `mgt_t10` submitted | 117-24 | +10,094 | | 5 |
| `mgt_k0` (= b1 code) | 117-24 | +10,048 | -46 (-271 to +155) | 5 |
| `mgt_h2` hire guard | 118-23 | +10,309 | +215 (-134 to +644) | 0 |
| `mgt_s4` strand rule | 120-21 | +10,506 | +412 (+47 to +788) | 5 |
| **`mgt_m1` all** | **120-21** | **+10,697** | **+602 (+229 to +1,053)** | **0** |

Caveat: the guard and the rule were designed on these 141 games and the penalty was picked from three values on
them. The out-of-sample check is the 237 ladder worlds of our other submission (below).

**Out of sample: the 237 ladder worlds of our other submission (56341683), not used to design anything.**
| build | W-L | mean margin | paired vs `mgt_t10` | better / worse / same | hire-short games |
|---|---|---|---|---|---|
| `mgt_t10` | 174-63 | +6,516 | | | 4 |
| **`mgt_m1`** | **175-62** | +6,846 | **+330 (+55 to +614)** | 129 / 42 / 66 | **0** |

All 378 ladder worlds: `mgt_t10` 291-87 (77.0%) -> `mgt_m1` 295-83 (78.0%), paired **+432 (+200 to +677)**.
