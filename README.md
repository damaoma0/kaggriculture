# Kaggriculture — Planning, Scheduling & Evaluation

An autonomous farming agent and experimental framework for [Kaggle's Kaggriculture competition](https://www.kaggle.com/competitions/kaggriculture), developed by **Yiyang Xu · Team Ghost Rule**.

**Reached the public leaderboard's top 150 within two weeks of development, in a competition with 10,246 teams and a nine-week submission window.** This was my first Kaggle competition.

The project evolved from a public-router baseline and recorded-action selection into a **semantic planner → tiler → executor** architecture. The main research question became: how can a high-level economic plan be turned into feasible worker actions without losing its value over a full season?

*The ranking is a historical public-leaderboard milestone, not a final placing or a claim that every experimental component contributed to that result. The submission window ran from 29 July to 30 September 2026; final evaluation is separate. [Competition timeline](https://www.kaggle.com/competitions/kaggriculture/overview/timeline) · [Team-count listing](https://www.kaggle.com/c) (checked 5 October 2026).*

## The problem

Each game lasts 30 in-game days, or 720 turns. Two agents manage separate farms but trade in a shared market. Decisions couple crop and animal production, land investment, hiring, inventory, transport and sale timing. Producing more is not automatically better: it can consume scarce worker time, delay cash receipts or reduce the prices available to both players.

This is a planning and resource-allocation project, rather than a conventional supervised-learning Kaggle submission.

## Architecture

```text
Current observation: farm, cash, inventory, revealed demand, public opponent state
                                  |
                         Semantic planner
              What to grow, buy, replace, retire and hire
                                  |
                              Tiler
           Map decisions onto our actual board and crop lifecycles
                                  |
                             Executor
           Assign workers, order jobs, route movement, issue actions
                                  |
                          Game environment
                                  |
                   Observe effects and update the plan
```

**Semantic planner.** Produces structured economic decisions rather than copying a recorded sequence of commands. It uses revealed information and historical decision examples; unknown future demand remains a model assumption. In the research entry point, an opening adapter handles days 0–5 and the main planning loop operates from day 6.

**Tiler.** Converts anonymous decisions such as crop counts, new structures and retirements into spatial plans. It tracks cohort lifetimes, occupied tiles and intended retirements explicitly: an asset scheduled for removal is not treated as already absent.

**Executor.** Turns the spatial plan into worker tasks and movement under daily time, inventory and cash constraints. Execution is checked against the observed farm, with recovery paths for issues such as newly unlocked land or incomplete pickups. Multiple scheduling approaches were investigated rather than treating the executor as a fixed implementation detail.

“Semantic” here means separating **what should happen** from **where it happens** and **which actions carry it out**. The repository retains earlier baselines and opening adapters; not every experiment replaces every component.

**Start reading:** [agent entry point](agents/semantic_strategy_20260928.py) · [semantic strategy development](docs/semantic_strategy_20260928.md) · [tiler interface and examples](docs/semantic_tile_planner_usage_20260928.md).

## Executor research

The scheduling work explored regret insertion, ruin-and-recreate, 2-opt / or-opt route improvement, and a time-budgeted path-partitioning formulation.

My path-partitioning design separates each tile's work into **mandatory, optional and slack** tasks. It preserves essential work, fits useful optional work within a worker's day, then reduces travel. Early return trips are planned first; work is removed by priority when a route exceeds its budget. Tasks that cannot produce value before the season ends are excluded rather than added as filler.

The implementation uses angular sectors, nearest-neighbour routes, 2-opt and local exchanges of boundary tiles. The earlier labour-search implementation explores moving jobs between workers through regret insertion and ruin-and-recreate.

| Recorded result | Scope and interpretation |
| --- | --- |
| **12–19% less main-route travel** than the reference agent | Offline study of **774 fixed-plan game-days across 43 recorded games**, using reference starting states, plans and crew sizes. Roughly 10% less travel when the separate early-return legs are included. |
| All modelled mandatory and optional jobs fit with the reference crew | A result within the daily routing model, not proof of a stronger full-season policy. Cash constraints, market timing and subsequent days require separate evaluation. |

These figures are reported in the committed experiments; rewriting this README does not constitute a fresh benchmark run. See the [path-partitioning study](docs/time_path_partition_20260930.md), [implementation](scripts/path_partition_20260930.py) and [labour-search implementation](scripts/labour_search.py).

### When a promising local result was not enough

The daily routing results justified further investigation, but full-season integration exposed interactions outside the local objective. Examples included collecting remaining produce before removing a plant, and preserving servicing actions whose payoff depended on later feeding. Better routes alone did not establish better end-of-season profit.

The useful conclusion was not that the measured travel reduction was false. It was that **improving a component metric does not establish an improvement in the complete system**. The path-partitioning executor remained promising research; I did not finish refining and qualifying it before the submission deadline. The report also flags measurements from superseded executor configurations, so those losses should not be presented as a verdict on every later variant.

## Evaluation and engineering

The research tooling includes matched-seed comparisons, both-seat evaluation, seed-clustered bootstrap intervals, frozen agent/source hashes, replay reconstruction and cash-ledger checks. Reports distinguish three different kinds of evidence:

- **Component tests:** isolate a planner, tiler or scheduler, sometimes using reference plans or known future decisions. These do not establish a deployable end-to-end policy.
- **Recorded-opponent tests:** replay a fixed action stream. The opponent cannot adapt, and changing its market or cash conditions can invalidate a naive strength comparison.
- **Live-agent tests:** execute both policies through the environment. Correct completion, runtime limits and economic performance are separate checks.

The semantic runtime is intended to use current observations and static learned artifacts, not test-episode IDs or future shop schedules. Historical replay inputs and oracle-assisted component experiments are kept conceptually separate from that runtime boundary. The [strategy report](docs/semantic_strategy_20260928.md) records development results, failure diagnoses and qualification limits; [tests](tests/) contain input-boundary, state and execution checks.

## Repository guide

| Path | Contents |
| --- | --- |
| `agents/` | Research entry points, generated candidates and historical baselines. |
| `scripts/` | Planning, tiling, scheduling, replay analysis, evaluation and packaging tools. |
| `tests/` | Unit and integration checks; some require research artifacts. |
| `docs/` | Experiment designs, measured outcomes, failed approaches and usage notes. |
| `data/` | Selected reference data and model inputs; not the complete local corpus. |
| `results/`, `outputs/` | Selected summaries and research artifacts, not all raw runs. |
| `submissions/` | Historical submission snapshots and packaging material. |
| `viz/` | Selected diagnostic visualisations. |
| [RESEARCH_LOG.md](RESEARCH_LOG.md) | Previous README preserved unchanged, including its chronological research updates. |

For a short reading path, start with the [semantic architecture proposal](docs/semantic_architecture_proposal_20260924.md), then the [implemented strategy](docs/semantic_strategy_20260928.md), the [tiler interface](docs/semantic_tile_planner_usage_20260928.md), and the [executor study](docs/time_path_partition_20260930.md). The proposal describes the design at that stage; the implementation reports establish what was actually built and tested.

## Working with this snapshot

**This is a research snapshot, not a one-command release of the final agent.** The upload retained source, documentation and selected summaries while leaving large raw game/replay artifacts local. Some runtime files, model data and fixtures referenced by scripts may need restoring before those scripts can run.

Clone and create an isolated environment:

```bash
git clone --depth 1 --branch leader-shed-overflow https://github.com/damaoma0/kaggriculture.git
cd kaggriculture
python -m venv .venv
```

Activate with `source .venv/bin/activate` on Linux/macOS or `.venv\Scripts\Activate.ps1` in PowerShell, then install the research dependencies:

```bash
python -m pip install -r requirements.txt
```

The dependency list is currently unpinned. Several September studies reference `kaggle-environments` 1.32.7; record the installed version and check the relevant experiment's engine/source hashes before comparing results. A successful installation alone does not reproduce the historical environment.

A limited syntax check, which does not import the agent or require its game artifacts:

```bash
python -m py_compile agents/semantic_strategy_20260928.py scripts/labour_search.py scripts/path_partition_20260930.py
```

For artifact-backed execution, follow the [tiler usage guide](docs/semantic_tile_planner_usage_20260928.md) or the relevant experiment report. Restore their documented inputs and frozen executor dependencies first. Missing fixtures are not passing tests, and syntax checks are not gameplay validation. Kaggle credentials are only needed for authenticated Kaggle operations; keep them outside this repository.

## Development history and attribution

The first stage extended public Kaggle router baselines and selected from recorded action sequences, including Unknown Mother-Goose's public replays. Those experiments exposed limitations of transferring budget-sensitive commands and motivated the later semantic architecture. Public leader replays, including DSM's, also provided reference decisions and controlled comparison states.

The project's contributions include the architectural redesign, planning/tiling integration, execution and recovery experiments, time-budgeted path-partitioning formulation, and evaluation tooling. They should be read alongside—not as a claim of authorship of—the reused public baseline code, replay data or official game engine. See the [early tape-based study](docs/mg_tape_base.md) and preserved source notices for provenance.

Development used AI coding assistance. I set research direction, proposed designs and evaluated the resulting implementations and experiments. The reports retain unsuccessful approaches and limitations rather than presenting only successful trials.

The game and environment are provided by [Kaggle](https://www.kaggle.com/competitions/kaggriculture). Upstream notices and terms continue to apply to reused material; this README does not assign a new repository-wide licence.
