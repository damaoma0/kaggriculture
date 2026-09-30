# Current leaders' openings: research assessment, 24 September 2026

## Recommendation

**Yes: give opening research a focused, gated trial.** The current leaders demonstrate earlier productive
cohorts, different financing schedules, and an alternative that expands the herd after the first shop.
These are meaningful changes to the production plans available to us. Improving selection among our existing
584 tapes cannot create an opening cohort that none of those tapes contains.

The return from replacing our opening is still unmeasured. Earlier integration failures establish problems
with replay feasibility and continuation compatibility. They do not establish that the leaders' openings
have inferior economics. The first research deliverable should be one reliably executed, coherent opening
and continuation family, followed by a paired comparison against our current agent.

## Fresh evidence and scope

- Read Kaggle's leaderboard and public submission/episode metadata at **2026-09-24 09:16:42 UTC**.
- Inspected the three most recent completed games for each of the top six teams' highest-rated submissions.
  Also inspected one game from each distinct latest submission. These form **19 unique recent games** because
  some leaders played each other. Selection used recency, not the game's winner or final margin.
- Downloaded three previously identified Ghost Rule games to inspect our established opening with the same
  inventory/cohort schema. Its board counts agree with the earlier 12-game exact-state opening profile.
- **22 complete source replays retained.** Re-executed both recorded action streams through the start of day 18:
  **9,504 joint transitions**. Farms, market, town and both private inventories matched every recorded transition;
  successful transaction ledgers reconciled exactly to cash at every step.
- All days here use the game's **zero-based day counter**. A day-6 board means the morning of day 6, before
  its actions. Cumulative sales at day 15 include actions through day 14.
- This is an observational strategy audit, not a new head-to-head performance test. Three games per main
  submission identify opening patterns; they do not estimate win rates or isolate the effect of an opening.

The public [Kaggle leaderboard](https://www.kaggle.com/competitions/kaggriculture/leaderboard) and the local
[API snapshot](../results/fresh/leader_opening_review_20260924_01a0/snapshot.json) identify the submissions:

| Rank | Team | Rating at snapshot | Highest-rated submission | Latest, if different |
|---:|---|---:|---:|---:|
| 1 | DSM | 3128.8 | 56495569 | 56498734, 3105.1 |
| 2 | DECEM | 3047.0 | 56489091 | 56517128, 829.7; only 4 completed games in response |
| 3 | M & M & P & Q | 3043.7 | 56497780 | 56509757, 30.4 |
| 4 | Vadim Vasilenko | 3023.5 | 56501059 | Same |
| 5 | Unknown Mother-Goose | 3000.6 | 56507372 | Same |
| 6 | Fourth Quadrant | 2996.1 | 56505223 | 56506325, 2599.8 |

A team's newest upload is not necessarily the submission responsible for its leaderboard position.
In particular, M & M & P & Q's latest sampled upload finishes with zero reward and has only one melon and
no animals on day 6. Its 3043.7-rated submission is the substantive strategy considered below.

## What the leaders actually build

Ranges below are observed across three games for each highest-rated submission. Counts are installed assets
from engine observations, not purchase requests. Our row uses the three historical own-agent games.

| Opening / team | Day-6 cows | Sheep | Strawberries | Melons | Wheat | First strawberry planting | First strawberry sale |
|---|---:|---:|---:|---:|---:|---|---|
| Our established opening | 4 | 2 | 4 | 12 | 3 | D5 | D16 |
| DSM | 2 | 3 | 10 | 10 | 0 | D2 | D13 |
| DECEM | 2 | 3 | 9 | 11 | 0 | D2 | D13 |
| Vadim Vasilenko | 2 | 3 | 10 | 10 | 0 | D2 | D13–14 |
| Unknown Mother-Goose, current | 2 | 3 | 10 | 10 | 0 | D2 | D13 |
| M & M & P & Q | 3–5 | 3–6 | 6–8 | 9 | 0–1 | D2 | D14–15 |
| Fourth Quadrant | 3–6 | 2–4 | 7–10 | 8–10 | 0 | D1 | D12 |

### 1. The common early-strawberry opening

DSM starts with two cows and three sheep. It reaches ten melons, then replaces early wheat with four
strawberries on day 2 and six on day 3. Its day-6 crop and animal cohorts are identical across the three games,
despite first shops of Yarn or Pizza. The current Mother-Goose, Vadim and DECEM use closely related openings.
Mother-Goose and DECEM show some later strawberry planting within the same broad plan.

Our comparison opening has twelve day-0 melons, four day-5 strawberries, two day-0 cows, a day-2 cow and a day-3
cow. Thus the change concerns **cohort ages and the timing of cash generation**, as well as asset counts.

The leaders begin planting berries before the first shop is revealed on day 3. That is a fixed investment
under uncertain future demand. A research policy can evaluate that investment ex ante, while making subsequent
shop-dependent changes only from revealed information. The observations do not imply access to future shops.

There is a concrete reason to investigate this fixed investment: four of the eight shop types consume
strawberries. Under the engine's uniform draws with replacement, four shops have appeared by day 12, giving
an expected two strawberry-consuming shops and a **93.75% probability of at least one**. This is a demand
prior, not a profit guarantee: quantity, competing supply, timing, labor and forgone production still matter.

The similarity among four teams is evidence that this family is competitive in their complete agents. It is
not four independent causal demonstrations that this opening is optimal.

### 2. M & M & P & Q: an alternative with earlier herd growth

Its initial opening uses two cows, three sheep, six melons and twelve wheat plants. By day 3 it has three cows,
three sheep, nine melons and one strawberry. It then expands the herd during days 3–5:

- [Yarn first, episode 112799998](https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=56497780&episodeId=112799998):
  sheep rise from 3 to 4 to 5 to 6 at the starts of days 3, 4, 5 and 6; cows remain at 3.
- [Smoothie first, episode 112791778](https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=56497780&episodeId=112791778):
  cows rise from 3 on day 3 to 4 on day 4 and 5 on day 5; sheep remain at 3.
- Bakery first also reaches five cows and three sheep in the third sampled game.

This is consistent with a branch after the first reveal, though three observations cannot establish the
complete decision rule. It is an especially relevant research hypothesis for us: reacting on days 3–5
can change animal maturity and fertilizer supply before our later repair searches operate.

### 3. Fourth Quadrant: even earlier berries and a larger early herd

Its three sampled games begin with three cows, two sheep, eight melons and nine wheat plants. It plants three
strawberries during **day 1**, reaches seven to ten by day 6, and makes its first strawberry sale at **D12 H1**
in all three games. Its day-6 herd varies by game.

This is a useful second challenger to the common two-cow/three-sheep family. It also has substantially different
market behavior: repeated wheat and fertilizer purchases and sales. Gross revenue is therefore misleading.
By day 6 it averages 3,994 fertilizer revenue and 1,188 fertilizer purchase spending, for **2,806 net fertilizer
cash receipts**. Our corresponding net receipts are 2,278. This difference includes production and trading;
it is not a measured arbitrage profit. Its day-6 cash is only 0–22 in these games, so copying its order stream
would face the same funding sensitivity already found in DSM replays.

## What the head start gains and what it costs

All values below are descriptive means from separate games. Future shops, opponents and later development
differ. These are not paired treatment effects.

| Quantity | Our opening | DSM | DECEM | Vadim | Current Mother-Goose |
|---|---:|---:|---:|---:|---:|
| Strawberry units sold before D15 | 0 | 16.3 | 14.7 | 13.7 | 15.7 |
| Strawberry revenue before D15 | 0 | 2,687 | 3,054 | 2,742 | 3,137 |
| Melon units sold before D12 | 72 | 54 | 54 | 54 | 54 |
| Milk units sold before D12 | 30 | 14 | 15 | 14 | 14.7 |
| Cumulative wages before D6 | 57 | 82.7 | 94 | 88.7 | 94 |
| Cash at D6 | 219 | 884 | 838 | 869 | 653 |

The earlier berries create a real observed sales window before our first sale. Earlier sales may also capture
higher prices or reduce rivals' prices, but neither effect has been isolated here. The reduced early melon and
milk supply and increased labor spending show why the berry revenue cannot be called net improvement.

The cash row also needs inventory context. In these games we enter day 6 holding **19–20 wheat**, **9 wheat
seeds**, **4 strawberry seeds** and **2–3 carrot seeds**. DSM holds **3–5 wheat and no seeds**. DSM's additional
cash is partly a different allocation between cash and supplies. It must not be treated as a free 665 gain.

Later continuation choices matter too: DSM has spent 7,000 on all three extra quadrants by day 12 in these
games; our sample and M & M & P & Q have spent 3,000. Final cash comparisons across these games would combine
opening, expansion, shop demand, opponent strength and execution.

## What the earlier failures establish

The existing [opening integration study](new_opening_20260924.md) contains valuable mechanical diagnoses:

1. A few coins of price drift can prevent an early hire, shift worker assignments and break the recorded plan.
2. A day-6 board with similar labels can still have incompatible ages, positions, seeds, feed and worker state.
3. A coherent DSM tape library also loses fidelity when later purchases leave insufficient money for labor.

Those explain why a raw opening graft lost roughly 87k in the earlier panel. **That experiment did not isolate
the economic value of the opening.** The 109-tape DSM library result is also affected by execution failures,
coverage and continuation selection.

The earlier report's roughly +754 result for games that happened to replay faithfully is conditioned on
post-treatment outcomes. It is neither an unbiased estimate of fixing execution nor a rigorous upper bound.
It cannot establish that the opening is incapable of beating our current policy. Equally, the fresh leaderboard
and early revenue measurements here do not establish that it will beat our policy.

## A useful bounded experiment

### First: one coherent family with reliable execution

Start with the common DSM-style opening, because its early target cohorts are simple and already documented.
Keep the associated continuation family through the initial expansion. Avoid a handoff to old Mother-Goose
instructions solely because day-6 tile labels are close.

The narrow implementation work is:

- Extract successful planting, placement, feeding and harvest outcomes into dated jobs and resource needs.
  The new audit already records exact cohorts, stocks and successful transactions; it does not need LLM extraction.
- Use the existing labor scheduler for those jobs, with purchase quantities tied to actual inventory and cash.
- Reserve feed and the next required hiring budget before discretionary purchases. Include overnight wages;
  a check covering only the next two hours misses the recorded day-7/day-8 failures.
- Validate day-3, day-6 and day-9 cohort ages, survival, inventory and job feasibility. Similar asset counts alone
  are insufficient. Any later switch needs a feasible plan for reconciling the full relevant state.

This is a narrower hypothesis than building a universal target-reaching planner. The scheduler gives us a
useful component, but purchasing, cash reservation and continuation compatibility still need implementation.
The time and performance needed are not established by the existing results.

### Then: compare complete policies on matched worlds

Use the existing local harness and separate development/qualification worlds. A suitable initial screen is
32 worlds balanced across the eight possible first shops, crossed with live V56 and original m1, with seats
balanced. Fix the shop sequences in the evaluator so different boards do not change the future random draws;
keep unrevealed shops hidden from every policy. Add recent leader recordings as a separate robustness panel,
with their limitation that recorded opponents do not respond to our changes.

Freeze opening and continuation choices before qualification. Runtime selection may use only revealed shops
and the current public state; selecting a donor using its full future shop sequence would invalidate the test.

Measure terminal **cash margin**, own and rival cash, lower-tail losses, successful hires, cohort survival,
and the product-by-product ledger. Give every arm a coherent continuation. Do not use day-6 cash, gross
strawberry revenue or a favorable replay subset as the success criterion. Only expand the research once a
reliably executed family earns its place in a clean paired comparison.

If the first family passes, the next candidates are M & M & P & Q's day-3 herd branch and Fourth Quadrant's
day-1 berry cohort. These test different mechanisms and offer more information than minor variations of
one copied recording.

### Immediate relevance to tape matching

These opening families are also useful inputs to an opponent forecast. A rival selling berries on day 12 or
13 has a different supply schedule from the older day-16 opening. Condition rival scenarios on its observed
cohorts and purchases; evaluate this separately from replacing our own opening. This connects directly to the
recent R4 diagnosis that fixed rival supply and missing rival costs can reverse a route's predicted advantage.

## Artifacts and reproduction

- [Research script](../scripts/review_leader_openings_20260924.py)
- [Leaderboard, submissions and episode metadata](../results/fresh/leader_opening_review_20260924_01a0/snapshot.json)
- [Replay selection](../results/fresh/leader_opening_review_20260924_01a0/replay_selection.json)
- [Exact daily profiles and cohorts](../results/fresh/leader_opening_review_20260924_01a0/profiles.json)
- [Verified transaction ledgers](../results/fresh/leader_opening_review_20260924_01a0/ledger_audit.json)
- [Computed group summaries](../results/fresh/leader_opening_review_20260924_01a0/summary.json)

The stages are `snapshot`, `replays`, `profiles`, `ledgers`, and `summary`. API stages require Kaggle network
access. Extraction and replay verification run serially. No playing-policy code or competition submission was
changed. `agents/mgt_m1.py` remains SHA-256
`1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470`.
