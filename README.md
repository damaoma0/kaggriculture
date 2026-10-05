# Kaggriculture — Planning, Scheduling & Evaluation

An autonomous farming agent and experimental framework for [Kaggle's Kaggriculture competition](https://www.kaggle.com/competitions/kaggriculture), developed by Yiyang Xu under team Ghost Rule.

Highest standing top 50, current standing on public leaderboard is top 150 out of 10246. 

The project evolved from a public-router baseline and recorded-action selection into a **semantic planner → tiler → executor** architecture. The main research question became: how can a high-level economic plan be turned into feasible worker actions without losing its value over a full season? Parallel market and opponent-behaviour studies informed the economic assumptions and tested which signals were useful for decisions.

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

## Market and opponent-behaviour research

Alongside the planning architecture, I investigated **how prices form, what public observations reveal about opponents, and whether better forecasts improve decisions**. These studies span the early router and later scenario-search stages; not every research model was integrated into the semantic agent.

### Market mechanics and sale ordering

I derived the opening wheat round-trip payoffs from the engine's discrete price curve and interleaved order execution, checked them against engine runs, and separated speculative trading from the need to retain wheat for feed. The analysis also tested how price changes interact with an opponent's tightly constrained opening budget. See the [wheat-opening derivation](docs/wheat_flip_derivation.md).

For ongoing sales, I compared ordering by current price impact and lot size with alternatives using inferred rival flow and delivery rhythms. Rival net trades were inferred from public market changes after accounting for our own trades; price-floor and ambiguous overflow cases were excluded. An availability-only control separated genuine price-ordering value from simply moving empty sale orders out of the way. **The simpler current-price/lot-size rule won the local selection test; opponent forecasts were not used by that selected rule.** These were early, limited-opponent experiments, not evidence of superiority over the final leaderboard. See [adaptive market ordering](docs/adaptive_market_order.md).

### Forecasting supply and delivery prices

An event-based model combined visible crop maturity, animal production schedules, observed harvests, estimated delivery windows and our own stock to forecast aggregate market inventory, then applied the engine's price curve. Ridge calibration was fitted by product and horizon. It did not read an opponent's private holdings or actual future shop draws.

On **eight held-out seeds / 48 games**, mean absolute price error for wheat and carrots at 24/48/72-turn horizons fell to **0.320**, versus **0.723** for flow extrapolation and **0.576** for an equally calibrated model without production/stock features. The latter control isolates the added feature group. Both seats and related opponent variants share seeds, so this is eight independent held-out seeds, not 48 independent worlds.

The separate, fresh investment-policy test changed few decisions and missed its predeclared promotion gate: only three of eight seed averages improved, five were unchanged, and wins did not increase. The existing policy was retained. **Better price prediction did not automatically become a meaningful policy improvement.** See the [forecast study](docs/event_prices.md) and [policy-level test](docs/event_inputs.md).

### What opponents condition on

I reconstructed **52 public matches** and analysed production around three-day demand reveals, controlling for the seasonal calendar and comparing action histories. The sampled leaders increased production of crops demanded by newly revealed shops. That association alone does not distinguish reading the shop list from reacting to the resulting prices.

For the sampled September 17 version of Unknown Mother-Goose, matched games shared the first two shops but faced different opponents and prices, yet retained identical actions for **8–12 in-game days**. In contrast, another leader sometimes changed actions despite identical observed histories, preventing the same attribution test. These are version- and sample-specific findings, not a claim that all leaders ignore opponents or that their algorithms were fully identified. The distinction helped motivate transferring economic decisions rather than exact command sequences. See the [leader behaviour study](docs/leader_segments.md).

Later [opponent-scenario modelling](scripts/rival_trajectory_model_v3.py) matched the visible rival farm, including cohort ages and revealed demand, to a **115-game historical training library**. It adjusted candidate sale trajectories to the current farm's estimated production and sampled future-demand scenarios. This supplied hypotheses for rollout search, not access to the opponent's true future actions.

### Competitive value and experimental controls

The [revenue decomposition](docs/efficiency_decomposition.md) separated land, utilisation, crop mix, yield and realised prices and reconciled them to cash outcomes. It exposed an important comparison trap: self-play agents supplying the same crops can depress prices, so a cross-pool revenue gap is not automatically a farming-efficiency gap. Some recorded-opponent controls also broke when their market conditions changed; the report retains the subsequent correction rather than treating those gains as live strength.

The research therefore distinguishes **forecast error, our own profit and profit relative to the opponent**, as well as recorded-action diagnostics versus responsive-opponent tests. Reported figures here are historical experiment results, not newly reproduced benchmarks or an attribution of the leaderboard result to every component.

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
| `scripts/` | Planning, tiling, scheduling, market/opponent modelling, replay analysis, evaluation and packaging tools. |
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

The project's contributions include the architectural redesign, market-mechanics and opponent-behaviour studies, public-state supply forecasting, planning/tiling integration, execution and recovery experiments, time-budgeted path-partitioning formulation, and evaluation tooling. They should be read alongside—not as a claim of authorship of—the reused public baseline code, replay data or official game engine. See the [early tape-based study](docs/mg_tape_base.md) and preserved source notices for provenance.

Development used AI coding assistance. I set research direction, proposed designs and evaluated the resulting implementations and experiments. The reports retain unsuccessful approaches and limitations rather than presenting only successful trials.

The game and environment are provided by [Kaggle](https://www.kaggle.com/competitions/kaggriculture). Upstream notices and terms continue to apply to reused material; this README does not assign a new repository-wide licence.
