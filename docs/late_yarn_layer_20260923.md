# Remote panels on Kaggle, the late-Yarn service layer, and plan-vs-jitter (2026-09-23)

Follows `docs/losses_winners_coverage_20260923.md`. No submission was made; `mgt_m1` / `mgt_t10` are unchanged.

## 1. Remote panels on Kaggle Notebooks (validated)

`scripts/kaggle_remote/remote_panel.py` builds a trimmed bundle (scripts, the agents under test, `data/ladder_panel`,
`data/mg_tapes`; 42-46 MB zipped) as the **private** dataset `yiyangxudmm/kaggriculture-panel-bundle`. It pushes
**private** script kernels (`kgr-<run>-s<i>`) that run `scripts/ladder_panel.py` shards (`panel_kernel.py`), then
fetches and compares the results. Kaggle decompresses uploaded `.gz` files, so the kernel re-wraps them.

| check | result |
|---|---|
| trial: `mgt_t10` + `mgt_m1` on 20 recorded ladder worlds | **40/40 identical to the local runs, to the dollar**; `mgt_t10` **20/20 identical to its recorded ladder results** |
| control: rebuilt `mgt_m1` (current fragments, new code switched off) on 44 worlds | **44/44 identical** to cached local `mgt_m1` |
| throughput per session (4 workers) | 5.8-11.5 games/min (Xeon 2.2 GHz about 7, AMD EPYC about 11); pip + start about 1-2 min |
| concurrency | 5 private batch sessions ran at once; 224 games in about 11 min wall (about 20 games/min) |

Caveat: the user's other agent system also pushes kernels on this account, so the 5 sessions are shared.

## 2. Late-Yarn service layer

**Diagnosis first** (`scripts/late_yarn_service_gap.py`; her 128 held-out worlds, `mgt_m1` in the ladder case).
Take the 27 worlds that got more late Yarn Stores than our final tape. There we start the late game with her flock
(6.3 against 6.4 sheep on day 12). After the reveal we keep 5.4 sheep to her 6.5 and feed / care them 69% / 51% of
days to her 88% / 78%, selling 24 fewer wool units (−5.3k revenue). The tape's own end-of-season wind-down (skip
feeds, still harvest) is left alone by the existing orphan rule. In worlds with fewer late Yarn Stores we
over-serve instead (82/68% against her 62/40%).

**The layer** (`scripts/fragments/mgt_sheep.py`, `yarn_service=1`; off by default, so the m1 build behaves
identically). While a Yarn Store is open, every sheep the tape does not feed today is fed (and cared, bank < 5) by
the existing top-up hands. It is valued as a live animal at the full wool outlook (not 0.8 of today's quote): a
day of wool, the bank on a production day, and the animal itself once it was unfed yesterday. It buys no sheep;
the existing expansion is untouched. `yarn_gate=1` (v2) fires only while the world has more Yarn Stores open than
the followed tape's world had by the same reveal (the tape's shops are known to the router).

| build | head-to-head vs her tape (128 worlds, paired vs m1) | ladder panel (180 frozen ladder worlds, paired vs m1) |
|---|---|---|
| `mgt_y1` (always on) | +29 (−59..+129); more-late-Yarn worlds +221 (n=27); other strata −64 / −94 | +44 (−36..+124); more-late-Yarn +213 (n=52); equal −8; fewer −62; wins 128 → 130 |
| **`mgt_y2` (gated)** | **+67 (−13..+156)**, 23 better / 11 worse; more-late-Yarn +244 (n=27); elsewhere ~0 | **+57 (−21..+133)**, 38 better / 19 worse; more-late-Yarn +183 (n=52); equal +10; fewer −3; wins 128 → 129 |

- **Mechanism works but only half-way.** In the target worlds v1 moves the flock from 5.4 to 5.8 sheep (her 6.5),
  fed 69% → 80% (her 88%), cared 51% → 65% (her 78%), keeps a sheep more alive by day 27, and sells 6-8 more wool
  units.
- **It is labour-bound.** In the target worlds the extra wool (+1.2k revenue on the head-to-head) is eaten by hands
  (+0.8k) and feed wheat (+0.4k). Most of the margin comes from the opponent's lower wool price: on the ladder
  panel our own cash is −219 and the rival's −401 in the target stratum. **Frozen-opponent caveat:** the recorded
  opponent keeps selling into the lower price; a reacting opponent could time its sales around our extra wool, so
  this part may shrink live.
- **Collision with the sheep expansion: none observed.** It commits in the same 6 of 180 ladder worlds (1 of 128
  head-to-head) in every build, −20 there for v2 (n=6); no hire shortfalls in any arm.
- **One real defect in the tail.** World 111302438 is −3,153 in both versions: with more feeding and care we sold
  13 fewer wool units. Candidate causes (engine facts in CLAUDE.md): a tile holding 6 units swallows the next
  production, our hands harvesting wool the shed then discards at midnight (100 cap), or an overlay sale at the
  wrong moment. It has to be traced before this goes near a submission.
- **Size.** About +60 a game on both panels (neither significant alone), against the ~4.5k measured in shops 5-8.
  Servicing the herd closes about half the service gap in the target worlds and a few percent of the money.

## 3. Strawberries: no late response to build

`scripts/late_strawberry_gap.py` (her 128 worlds). Our final tape and her native plan carry the same strawberry
tiles on days 12 / 15 / 18 (21.1 / 28.9 / 29.4 against 20.4 / 27.8 / 28.4 where the world has more late
strawberry demand). Units and revenue match hers in every stratum (217 against 216 units, 39.2k against 39.5k).
Neither she nor DSM changes strawberry tile counts after a late reveal (`leader_response/summary.md`). The
strawberry penalty in the ladder regression is today's opponents out-producing us from the **opening** (DSM has
17.6 strawberry tiles on day 7 against our 11.7). That cannot be reached by a late layer on top of the old-opening
tapes. Not built.

## 4. How deep is the top agents' non-determinism? (`scripts/analyze_plan_vs_jitter.py`, `plan_jitter/summary.md`)

- **Mother-Goose old (our tapes): pure jitter.** Boards of games that share a shop prefix stay identical (median
  L1 0) until their shops differ.
- **DSM, DECEM, Vadim, current Mother-Goose: small genuine drift on a shop-driven plan.** Pairs matched on the first
  two shops cross a 3-tile board difference around day 7-8, before any new shop (DSM n=78, DECEM 10, current MG 14,
  Vadim 6). DSM's one self-play game (same seed, same shops) is board-identical through day 9, 3+ tiles apart by
  day 11, 14 at most by day 24. By day 9 the revealed shops still explain 70-100% (R²) of the between-game
  variance in animal counts and most crop counts. This drift is state-dependent (they see prices and the
  opponent), not proven random.
- **Late game unresolved.** With 40 games per leader, 5-shop prefixes never repeat; DSM has 1-2 such pairs.
- **Consequence.** Plan-level harvesting (production targets as a function of shops) is viable in principle for
  the early and middle game, not as tapes. For the late game the only estimate is population-level: DSM keeps
  +1.9 sheep above its baseline after a late Yarn Store (Mother-Goose old +1.4), no strawberry tile response. That
  is the response the layer implements.
