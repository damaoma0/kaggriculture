# Growth opening: value beyond day 9

Selected research opening: **small-herd**, implemented in `agents/opening_v2.py`.

## Evaluation

Screened 19 configurations on two seed pairs (38 games). Compared three shortlisted growth openings and the old six-sheep control on four new seed pairs, both seats, and two continuation policies (64 games). Each opening runs through action 215; the evaluator takes over at day 9, step 216, and finishes the 30-day season. The opponent is the local public `tschinkel_router_v31.py`, reacting throughout.

Selection primarily uses mean terminal cash margin against the opponent. After examining the shortlist, we treated margins within 1% of the leading deficit as practically tied and preferred higher own cash: small-herd gives up only 155 mean margin to c6s4-m0 but earns 14,362 more. This tie-break is an exploratory choice, not a pre-registered criterion. Maintenance keeps existing assets; replanting also replaces cleared crop slots with wheat. Both use the same evaluator staffing rule, capped at 10 hands. Neither buys new animals. The future seed is hidden from the policies. Seeds are paired between candidates, but farm-dependent random draws can produce different subsequent shops.

## Shortlist results

| Opening | Mean day-9 cash | Mean final cash | Mean final margin | Margin improvement over control | Paired improvements |
|---|---:|---:|---:|---:|---:|
| c6s4-m0 | 692 | 33,556 | -77,438 | +43,798 | 16/16 |
| small-herd | 64 | 47,918 | -77,593 | +43,643 | 16/16 |
| c8s4-m12 | 1,333 | 41,794 | -79,694 | +41,542 | 13/16 |
| control-sheep6 | 9,204 | 39,098 | -121,236 | +0 | 0/16 |

## Selected opening by continuation

| Continuation | Opening final cash | Control final cash | Opening margin | Control margin |
|---|---:|---:|---:|---:|
| maintain | 44,491 | 33,624 | -84,049 | -126,061 |
| replant | 51,346 | 44,573 | -71,136 | -116,410 |

## Opening targets

```json
{
  "cows": 4,
  "sheep": 4,
  "initial_animals": 4,
  "grow_day": 2,
  "grow_every": 1,
  "melons": 12,
  "strawberries": 18,
  "strawberry_day": 3,
  "land_day": 3,
  "land_buffer": 100,
  "hands": 8,
  "late_hands": 10,
  "late_hands_day": 5,
  "cash_crop": "WHEAT",
  "harvest_age": 4
}
```

Targets are conditional on affordability and worker progress, not guaranteed purchases on a fixed turn. Animal pens stay in fixed positions close to the shed. The initial herd grows gradually; future pens stay reserved so new animals do not displace crop assignments. Workers preserve their destinations, water crops, feed and care for animals, collect produce and fertilizer, and sell available shed goods. Fertilizer is sold rather than applied.

## Limits and checks

All 102 screen/shortlist games completed with valid intermediate statuses and exact continuation cash reconciliation. Opening crop/animal loss counts: 0. Seed requests were checked against available seeds on every opening decision.

The shortlist set is used to select the final configuration; it is not an untouched final performance estimate. Maintenance and replanting reuse each opening state, so 16 rows per candidate are eight distinct opening scenarios, not 16 independent openings. This is a small, opponent-specific experiment. The continuation is a simple service controller and may undervalue farms that need specialized routing. Lower opponent income can improve margin even when our own income falls. These values are policy-conditioned estimates, not optimal board values or leaderboard win rates. The router remains ahead on average. Midgame investment and late-game routing still need work.

See [board valuation](board_value.md) and [open-source sources](board_value_sources.md) for the evaluator's basis.

## Reproduce

```powershell
.venv/Scripts/python.exe scripts/search_growth_openings.py --stage screen --workers 3
.venv/Scripts/python.exe scripts/search_growth_openings.py --stage validate --names control-sheep6 c6s4-m0 c8s4-m12 small-herd --workers 3
```

## Frozen opening: fresh-seed check

After selection, seed 86201 / future 96201 was run in both seats. Selected opening mean final cash: 58,517; control: 31,162. Selected margin: -60,915; control: -66,392. Both seats happened to produce identical outcomes; this is one new seed, not two independent samples. The smaller improvement in margin reinforces the need for more opponent/scenario coverage.

The standalone entry point passed all 432 recorded decisions across both seats, with no observation mutation, seed overdraw, or opening deaths (`scripts/verify_growth_opening.py`).

### Actual build, fresh seed, seat 0

Counts below are at the start of each zero-based day. These are observed assets, rather than target quantities.

| Day | Cash | Tiles | Animals | Crops |
|---:|---:|---:|---|---|
| 0 | 3,000 | 25 | — | — |
| 1 | 9 | 25 | 2 cow, 2 sheep | 11 melon |
| 2 | 90 | 25 | 2 cow, 2 sheep | 12 melon |
| 3 | 241 | 25 | 2 cow, 2 sheep | 12 melon |
| 4 | 86 | 25 | 2 cow, 2 sheep | 12 melon, 2 strawberry |
| 5 | 118 | 25 | 2 cow, 2 sheep | 12 melon, 3 strawberry |
| 6 | 153 | 25 | 2 cow, 2 sheep | 12 melon, 5 strawberry |
| 7 | 672 | 25 | 2 cow, 2 sheep | 12 melon, 5 strawberry |
| 8 | 353 | 25 | 4 cow, 4 sheep | 12 melon, 5 strawberry |
| 9 | 467 | 50 | 4 cow, 4 sheep | 12 melon, 9 strawberry, 5 wheat |

[Exact opening moves](../results/fresh/growth_opening/small-herd-86201-seat0/moves.md) · [Full replay JSON](../results/fresh/growth_opening/small-herd-86201-seat0/full_replay.json)

```powershell
.venv/Scripts/python.exe scripts/search_growth_openings.py --stage record --names control-sheep6 small-herd --workers 3
.venv/Scripts/python.exe scripts/verify_growth_opening.py
.venv/Scripts/python.exe scripts/report_growth_openings.py
```

The record command creates new folders and refuses to overwrite existing ones; use `--out` for a separate rerun directory.
