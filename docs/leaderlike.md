# Leader imitation, measured by self-play against the frozen current agent

## Acceptance test

The frozen benchmark is `agents/benchmark_frozen_56280048.py`, a byte copy of uploaded submission
56280048 (SHA-256 `07c313e5…85ea4f`, ladder score 2507.3). Every candidate is that exact file plus
one appended layer, so the only behavioural difference is the layer under test, and Kaggle's own
`get_last_callable` loads both sides, so the benchmark plays what the ladder plays.

Acceptance is **head-to-head win rate against that frozen agent**, on paired seeds with both seats,
with seed-clustered bootstrap intervals — not absolute revenue. Rationale accepted from the user: the
V45 family is the bulk of the current ladder, so beating our own deployed agent is the test that
should translate.

Harness: `scripts/selfplay_gate.py`. Every game must produce 720 states, both seats terminal DONE,
and a cash ledger reconciling to the reward; each game records the SHA-256 of the exact agent file it
played, and a summary refuses to mix builds. The null control (`sp_null`, benchmark plus a no-op
layer) returns **0W-32T-0L with +0 margin in every game**, because identical policies play
identically — the harness has no seat or loader bias.

Seed discipline: block 171000-171015 is the development block (it was used to diagnose the
strawberry glut); block 172000-172015 is the evaluation block for everything derived from that
diagnosis.

## Round 1: individual leader behaviours transplanted into our chassis

Seeds 171000-171015, 32 games each.

| Candidate | W-T-L | Win rate (95% CI) | Mean margin (95% CI) | Verdict |
|---|---|---|---|---|
| `sp_null` (control) | 0-32-0 | 0% (0-0) | +0 (0 to 0) | harness unbiased |
| `sp_hirecap11` | 14-2-16 | 43.8% (18.8-68.8) | **−3,857** (−7,001 to −1,049) | rejected |
| `sp_hirecap12` | 0-26-6 | 0% | −2,530 (−5,608 to 0) | rejected |
| `sp_hirecap13` | 0-26-6 | 0% | −895 (−2,082 to 0) | rejected |
| `sp_noquad4` | 4-26-2 | 12.5% (0-31.2) | −349 (−1,376 to +301) | no measurable effect |
| `sp_fertretain` | 0-0-32 | 0% | −111,072 | **invalid**: layer broken |

Why the hire ceiling fails: the leaders spend exactly 696 per 3-day segment on labour (11 hires/day)
and never more, but V45 spends hires differently — its conditional programs hire *dedicated* workers
on top of the tape's crew. Capping starves them: telemetry shows 122 `input_hire_errors` and 34
`sheep_hire_shortfalls` at cap 11. The graded result (−3,857 at 11, −2,530 at 12, −895 at 13) says
our surplus hands more than repay their Fibonacci cost. My earlier estimate of +750 to +950 priced
the hire cost and ignored those hands' output; it was wrong.

The fertilizer candidate is not a test of the idea — its stock floor withheld 355,154 sale units,
because collected fertilizer is sold straight out of unit inventories rather than accumulating in the
shed the way the layer assumed. The fertilizer question remains **untested**.

The lesson that motivated the imitation: individual leader behaviours transplanted into V45's chassis
do not help, because the chassis is co-adapted.

## What the imitation is, and what it inherits

`scripts/build_leaderlike.py` builds the imitation on the benchmark's execution chassis. That choice
is deliberate and worth stating plainly, because it bounds the claim:

- The segment study found our tape **already matches** the leaders on the timing half of their
  policy: fixed opening through day 5, second quadrant days 6-8 and third days 9-11, melon cash-out
  days 9-11, liquidation days 27-29 at ~17.5% of season revenue, 11 hires/day once ramped. Those are
  inherited, not re-implemented.
- What differs is crop **quantity** conditioning, the crop calendar (strawberry replanting through
  day 16, carrot ramp from day 18 instead of day 24) and the refusal of the fourth quadrant. That is
  what the controller implements.
- Round 1 is the evidence for not rebuilding the execution layer: pulling single behaviours out of
  the chassis costs money, and a from-scratch executor would also have to re-earn the 45 versions of
  routing, care scheduling, sale ordering and terminal planning that V45 already has. The repo's own
  history is the cautionary case: `plan_v1`, a hand-built planner, scored ~1013 on the ladder against
  V45-family agents at ~2500.

The targets use engine constants only — no thresholds fitted to any seed:

- a shop instance consumes one unit of each product it demands per 4 turns = 6/day; single-product
  shops (Yarn, Pet Cafe) consume double; the town centre consumes 1/day;
- shops unlock on days 3, 6, … 24, so undrawn shops contribute the mean rate over the eight equally
  likely types, discounted by 0.5 because the leaders condition on *revealed* demand (their plantings
  correlate +0.93/+0.94 with demand visible at day 12);
- a plant's contribution is its scheduled productions that still fit before day 29 (strawberry at
  ages 10/12/14/16, tomato 8/9/10/11, carrot at 3, one unit each unfertilised, carrot three);
- the opponent is assumed to mirror our supply, so we can clear about half of total absorption.

Two modes were built. `leaderlike_v1` sets a *plant-count* target and suppresses plantings above it.
`leaderlike_v2` replaces that with a **marginal-unit test**: it adds up what we are already committed
to selling (stock on hand, yield standing on tiles, every scheduled production still to come) and
allows one more plant only if the town can still absorb its output. The fidelity check below is why
v2 exists.

## Imitation fidelity: does the model reproduce their quantities?

`scripts/check_leaderlike_fidelity.py` runs the controller's target formula over the shops each
leader actually saw and compares it with what that leader actually had planted.

| Policy | Checkpoint | Model mean | Leader's actual | Mean abs error | Model range | Actual range | Rank corr |
|---|---|---:|---:|---:|---|---|---:|
| Majkel1337 | day 9 | 22.3 | 23.2 | 4.5 | 9-32 | 14-27 | +0.53 |
| Majkel1337 | day 12 | 18.1 | 27.8 | 9.7 | 8-27 | 14-37 | +0.75 |
| Mother-Goose | day 9 | 22.7 | 17.1 | 6.3 | 9-32 | 13-19 | +0.37 |
| Mother-Goose | day 12 | 18.8 | 21.3 | 4.2 | 8-27 | 17-23 | +0.37 |
| (our benchmark) | both | — | 33 exactly | — | — | 33-33 | — |

Carrots at day 18: model 6.9 (1-15) versus Majkel's actual 3.9 (0-21); model 7.2 (1-20) versus
Mother-Goose's 1.1 (0-12).

Reading: at day 9 the model lands on the leaders' level, and it moves in the same direction as their
choices across worlds (positive rank correlation), but it is not their rule — it explains part of
their variation, not all of it. At day 12 the plant-count version under-targets, because it judged a
standing cohort by the productivity of a *new* plant; that is the defect the marginal-unit test in v2
fixes. The carrot targets run above their actual counts.

## Round 2: the imitation against the frozen agent

Seeds 172000-172015 (evaluation block), 32 games per candidate.

| Candidate | W-T-L | Win rate (95% CI) | Mean margin (95% CI) | Our cash | Benchmark cash |
|---|---|---|---|---:|---:|
| `leaderlike_v2` (full imitation) | 0-0-32 | 0% (0-0) | **−17,553** (−22,057 to −13,604) | 90,010 | 107,563 |
| `leaderlike_v1` (count-target full) | 0-0-32 | 0% (0-0) | −14,495 (−19,033 to −10,653) | 87,581 | 102,076 |
| `leaderlike_v2cap` (strawberry cap only) | 4-0-28 | 12.5% (0-31.2) | −10,720 (−14,038 to −7,170) | 91,709 | 102,429 |
| `leaderlike_v2swaps` (crop calendar only) | 0-0-32 | 0% (0-0) | −2,803 (−3,410 to −2,193) | 92,579 | 95,382 |

The imitation loses every game, and the two ablations split the damage: the demand-conditioned
strawberry cap costs about 10,700 and the earlier carrot ramp about 2,800. Maximum agent call time
0.176s; zero controller errors in 128 games; each candidate's games all played one verified build.

## Where the two leaders differ, and which one to imitate

| | Majkel1337 (56216119) | Unknown Mother-Goose (56266758) |
|---|---|---|
| Determinism | **nondeterministic** (15/210 pairs diverge with identical observation histories) | deterministic (0/226) |
| Day-0 herd | 2 cows + 3 sheep | 3 cows + 2 sheep (same as ours) |
| Early strawberries | 1.8 plants by day 2 | none before day 3 |
| Mid-game melon | none | plants exactly 1 more melon on days 9-11, every game |
| Tomatoes | up to 19 plants, 4,019 revenue | up to 25 plants, **7,647** |
| Eggs / geese spend | 3,420 / 540 | **6,411** / 1,160 |
| Carrots planted | up to 176 | up to 98 |
| Idle time | 56 PASS per game | 882 PASS per game |
| Fertilizer bought | 0 | 1,002 |
| Final cash (this sample) | 112,283 | 119,380 |

Mother-Goose is the right imitation target and I agree with that framing: it is deterministic, so its
policy is in principle a recoverable function; its opening board is already identical to ours, which
isolates the delta to the mid-game; and it outscores Majkel in this sample despite being the simpler
policy. Where the two differ I followed Mother-Goose, except that I kept our own opening (identical
to its own) and did not copy its extra day-9 melon or its fertilizer purchases, both of which are
single behaviours of the kind round 1 showed do not transplant.

## What the imitation cannot reproduce

1. **Majkel1337's conditioning rule.** Not identifiable: identical full observation histories produce
   different actions, so no amount of replay evidence pins the rule. Nothing here tries to model it.
2. **Their executor.** We inherit V45's routing, care scheduling, sale ordering and terminal planner.
   The leaders' own labour allocation (7,220 and 7,056 commands per game, with 36.5 DIG and their own
   watering cadence) is observable in replays but not reconstructible as a policy from 30 games, and
   round 1 argues against replacing parts of a co-adapted chassis piecemeal.
3. **Mother-Goose's tomato program**, which is its single biggest revenue edge over us (7,647 versus
   2,937). Tomatoes mature in 8 days with four daily productions; the chassis's wheat-cycle visits to
   a tile neither wait for that nor revisit on the right days, so a tomato planted at a wheat visit
   would be under-served. Reproducing it needs a tile-owning mini-executor with reserved labour —
   exactly the component whose absence made the earlier crop-cohort attempts fail
   (`docs/crop_cohort_experiment.md`: the prototypes "prebuy seeds before proving a feasible
   commitment" and "do not reserve a complete future care schedule"). Not attempted here; flagged
   rather than faked.
4. **Order-level sale timing against a specific rival.** Neither leader conditions production on the
   opponent — Mother-Goose plays byte-identical action streams for 8-12 days against different
   opponents — so no opponent term was built, per the spec. Whether their *sale ordering* reacts is
   untestable from replays.

## A caveat about the acceptance test itself

In a mirror market, cutting our supply of a glutted good raises the price for whoever still holds
units — and the frozen benchmark holds the units we gave up. Margin is ours minus theirs, so a change
that raises our own revenue can still lose margin if it raises theirs more. The decomposition in
`scripts/report_selfplay.py` measures both sides against the null control on the same seeds, so this
can be told apart from a change that simply does not work. This matters for how far self-play results
generalise to a ladder where opponents are not all strawberry-flooding clones of us.

### The mirror effect, measured against a null control on the same seeds

`sp_null` was run on the evaluation block too, so every candidate's effect can be split into what it
did to our revenue and what it did to the benchmark's. Null baseline: both sides 94,665 cash.

| Candidate | Our revenue | Benchmark revenue | Our spend | Margin |
|---|---:|---:|---:|---:|
| `sp_strawdemand` (trim ~2 plants/game) | **+1,966** | +2,471 | +378 | −343 |
| `leaderlike_swaps` | −1,237 | +675 | +597 | −2,492 |
| `leaderlike_v2swaps` | −1,483 | +737 | +603 | −2,803 |
| `leaderlike_cap` | −6,274 | +4,587 | −2,139 | −9,395 |
| `leaderlike_v2cap` | −3,978 | +8,153 | −1,021 | −10,720 |
| `leaderlike_v1` | −11,999 | +6,747 | −4,915 | −14,495 |
| `leaderlike_v2` | −9,644 | +13,255 | −4,989 | −17,553 |

In **every** candidate the benchmark gained more than we did. The strawberry line is where it
happens: under `leaderlike_v2cap` our strawberry revenue falls 6,823 while the benchmark's rises
6,198 — we hand over almost exactly what we give up. Our own realised price does improve (117 per
unit in the null, 167.6 with the cap) but not enough to pay for 114 fewer units.

Two findings follow, and they point in opposite directions from my earlier recommendation:

1. **Our 33 strawberries are close to own-revenue optimal in these worlds.** Only a marginal trim of
   about two plants per game raises our own revenue (`sp_strawdemand`, +1,966); every larger cut
   lowers it (−3,978 to −11,999). The development-block diagnosis — that the marginal units clear at
   the $1 floor — is true in the poorest worlds but not on average: across the evaluation block the
   units we cut were worth roughly 60 each, not 1.
2. **Even the trim that helps us helps the opponent more** (+2,471 against our +1,966), so it fails a
   margin test: −343, CI −887 to +11. This is the structural point in its cleanest form. Lifting a
   shared price is a public good, and the opponent holding more units collects more of it.

A dose-response curve across the five crop candidates — trim 2 plants → −343, trim ~14 → −9,395 to
−10,720, trim plus carrot ramp → −14,495 to −17,553 — makes the causal reading solid rather than
noisy.

The carrot ramp fails for a separate, simpler reason: swapping a wheat planting visit for a carrot
costs 2,122 of wheat revenue and returns 204 of carrot.

`leaderlike_v1`/`v2` also show a co-adaptation break worth recording: our tomato revenue drops 2,002
while the benchmark's *rises* 1,352-2,755, because our altered cash and board stopped V45's day-18
tomato program from firing for us while it still fired for the unmodified opponent.

### What this does and does not show

It does **not** show that the leaders' policy is worse than ours. It shows that the half of their
policy we could reproduce — cutting the glutted crop — is value-destroying on its own, and the half
that would make it pay is the half we could not build: redeploying freed land into goods the market
is short of. Mother-Goose earns 7,647 from tomatoes and 6,411 from eggs against our 2,937 and 3,460,
while in our self-play games tomato inventory sits 207 units below neutral and egg 153 below. Our
imitation freed strawberry tiles and put nothing on them.

The identified missing component is therefore a tile-owning planner with reserved labour that can
plant and service tomatoes on land freed from strawberries — the same component whose absence sank
the earlier crop-cohort attempts. Nothing in this round is shippable; the gate correctly rejected
all of it.

### Consequence for how candidates are judged

Head-to-head margin is necessary but not sufficient, and it is systematically hostile to any change
that works by lifting a shared price. Future candidates should be reported as **own-cash delta at
fixed opponent behaviour alongside margin** (both are in `scripts/report_selfplay.py`): the profile
worth shipping raises our cash without raising theirs, which is what supplying an unsupplied good
does and what a supply cut cannot do. A mixed panel of non-clone opponents and a per-tile-day
marginal-revenue diagnostic are the cheap next additions; replaying the leaders' recorded action
streams against the benchmark is available but confounded, since their orders cannot react to our
prices.

## Artifacts

- `agents/benchmark_frozen_56280048.py` — the frozen benchmark (never edited).
- `scripts/build_selfplay_candidates.py`, `scripts/build_leaderlike.py` — candidate builders.
- `scripts/selfplay_gate.py` — the acceptance gate; `scripts/report_selfplay.py` — two-sided
  decomposition; `scripts/check_leaderlike_fidelity.py` — imitation fidelity.
- `scripts/diagnose_strawberry.py` — the sale-attribution diagnostic that found the glut.
- `results/fresh/selfplay/` — per-game records, manifests and summaries for each round.
