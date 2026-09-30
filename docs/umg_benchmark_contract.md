# Original-UMG tape benchmark contract

## Baseline identity

The only honest “original UMG tape” baseline is the raw action sequence from the replay at `steps[t + 1][umg_seat].action`, replayed through the official engine. `scripts/tape_vs_bench.py` already reconstructs exactly that sequence in its `mg` arm, first verifying it reproduces the original replay and recording its original board keys and weed spawns.

Do **not** use an agent built by `build_mg_tape_agent.py` as this baseline. That builder replaces UMG's turn-0/1 wheat round trip with an equilibrium feed purchase, and its chassis can repair alignment, weeds, budgets, sales, and terminal actions. It is a useful executable continuation/router, but is not the historical UMG policy tape and can create an artificial opening advantage against a raw-tape comparison.

## Existing usable harness

`tape_vs_bench.py` is the existing helper that holds each replay's historical shop sequence without replacing the live opponent. `_play(..., shops_by_day, ...)` writes the recorded unlocked shops at each daily refresh. The live candidate receives only its normal current observation; it is never passed the future list. The helper also replays only the UMG farm's originally logged weed spawns, while the live farm's weeds remain normal. This prevents a board/RNG drift from being mistaken for a policy result.

Run its `mg` arm to get the raw tape and its validity diagnostics; run `live <candidate>` to place the same raw tape against a candidate loaded as a normal live agent. Retain the per-game `validity` result: first board divergence, failed-command day, and sale-fill degradation. Results after the recorded tape's valid window are not evidence that a candidate beat original UMG play.

## Required panels

| Control/panel | UMG side | Other side | Shops | Purpose |
|---|---|---|---|---|
| `raw_umg_reproduction` | Both original replay actions | Both original replay actions | Natural recorded world | Confirms action extraction and recorded reward. |
| `raw_umg_vs_live_candidate` | Raw UMG actions in its recorded seat | Candidate, normal live callback | Historical shops, original UMG weeds only | Optional direct candidate-versus-original-tape diagnostic. |
| `raw_umg_vs_live_baseline` | Raw UMG actions in its recorded seat | Frozen current baseline | Same historical shops/weed rule | Separates a candidate change from tape fragility. |
| `raw_umg_vs_v56` | Raw UMG actions in its recorded seat | V56, normal live callback | Historical shops, original UMG weeds only | V56 result in the native UMG-seat world. |
| `candidate_vs_v56_same_umg_world` | Candidate in the recorded UMG seat | V56, normal live callback | Same episode/seed/historical shops | Primary paired candidate comparison; compare margin with `raw_umg_vs_v56`. |
| `baseline_tape_vs_live_baseline` (`calib`) | Baseline's own frozen tape | Same live baseline | Same historical shops/weed rule | Measures the penalty of freezing a policy equal to the opponent. |
| `candidate_vs_live_baseline` | Candidate | Frozen baseline | Fresh or historical shops selected before run | Measures candidate quality without a frozen UMG opponent. |

`raw_umg_vs_v56` and `candidate_vs_v56_same_umg_world` are the required paired result: identical episode, seed, recorded UMG seat, historical shops, and V56 opponent. Pair margins by that tuple. For the matched historical qualification, apply the **same recorded own-farm weed opportunities to every arm**, spawning only when the target tile is empty; `_play` supports this. Do not give only the raw tape a favorable weed intervention while calling the conditions matched. Keep entirely natural weeds/shops in the separate live-V56 qualification panel. The `calib` arm is mandatory context, not a win target.

## Seat rule

A raw UMG tape should remain in its recorded seat for faithful reproduction: market order priority, cash fills, shared-world trajectory, and its validity reference are all recorded in that seat. A coordinate or hand-index incompatibility has not been established; do not claim one. Do not manufacture a “both seats” tape score by swapping the actions anyway, because it would be a distinct counterfactual that needs its own reproduction and validity evidence. Report all raw UMG recordings in their native seats. Use both candidate seats in ordinary live-V56 panels, and state any native-tape seat imbalance.

## Future-information rule

Historical shops are an environment intervention, not candidate input. Candidate construction, configuration, and runtime must use only the current town state. Do not select a continuation target from a replay's later shop sequence, pre-load it into the candidate, or choose actions conditional on `shops_by_day`. Tape actions inevitably encode what UMG did in its historical world; this is precisely why tape validity and the frozen-baseline calibration are reported.

The repaired/equilibrium-opening tape agent may be included as a separately named router/executor control. It must never be renamed “original UMG tape.” No panel above establishes reliable wins against a live UMG policy: its source executable is unavailable. They establish only raw-tape counterfactual margins, validity duration, and candidate performance against named live local opponents.
