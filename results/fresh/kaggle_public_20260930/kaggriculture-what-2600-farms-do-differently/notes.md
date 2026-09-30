*By [Georgy Mamarin](https://www.kaggle.com/georgymamarin)*

What the top of the board does, set against the middle of the same window: what they plant, when they
buy land, how big a crew they run. The page reruns on each new dataset version and reports which of
those the two bands actually differ on, which some days is none of them. Then the same comparison for
your own submission. Both read my
[Kaggriculture Episodes](https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes)
dataset: every finished [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture)
game in full, 720 turns, both players, every action.

<a id="s11"></a>
## Your submission against the ladder

The part worth forking. Put your own submission id in the cell below and you get a personal
report: where your best game lands in the whole field, and how your strategy fingerprint
compares with the record holder's. That is one farm rather than the band above, and single names
at the top turn over within hours, so treat it as a reference point. Find
your id in `episodes.csv`, or leave the default to see the record holder's own report.

Before spending a real submission slot, dry-run the agent: destbreso's
[benchmark](https://www.kaggle.com/datasets/destbreso/kaggriculture-benchmark-matchups) replays
45k recorded pairings seed for seed, and his
[Measure Your Agent](https://www.kaggle.com/code/destbreso/kaggriculture-measure-your-agent)
harness tells you what a local score can and cannot promise about the ladder.

**A live report, not a snapshot.** It re-runs on a schedule with the dataset, so every number in
the text below is computed at run time. Come back tomorrow and the ladder you see will be the
ladder as it is tomorrow.

<div class="alert alert-info" style="border-left: 5px solid #2196f3; padding: 12px 16px; border-radius: 4px;">
<b>Two companions, two jobs.</b> This one is about the data and the state of the ladder. My guide
<a href="https://www.kaggle.com/code/georgymamarin/kaggriculture-visualized-what-every-crop-pays">Kaggriculture, Visualized</a>
is about the game itself, with every rule and price curve drawn out plus a starter bot. Read that
one first if the mechanics are new to you.
</div>

**Built on this data, by the community:** a [replayable benchmark](https://www.kaggle.com/datasets/destbreso/kaggriculture-benchmark-matchups) of 45k matchups with resolved seeds (CC0), an [agent-testing harness](https://www.kaggle.com/code/destbreso/kaggriculture-measure-your-agent), a [no-OOM replay reader](https://www.kaggle.com/code/lucashmateo/kaggriculture-replays-no-oom-3-dataframes), and a [research series on openings, lineages and noise](https://www.kaggle.com/code/destbreso/everyone-is-playing-the-same-opening) — by destbreso and Lucas Mateo. The dataset stopped being a solo project; this page stays its daily pulse.

### In this notebook

Above: the fresh cohort at the top of the board and your own submission against it. Below,
the season in depth.

**Part I — the data.** Know what you are standing on before you quote it.
- [1. What is in the dataset today](#s1) — size, coverage, and how fast the corpus grows

**Part II — the ladder.** Nine views of the same 30-day season, from every recorded win down to pure luck.
- [2. The ladder right now](#s2) — every recorded win on one chart
- [3. The shape of a big game](#s3) — top coin curves against a median game
- [4. Strategy fingerprints](#s4) — crew, land and crops: leaders vs the mid-ladder
- [5. What separates a big bank from a small one](#s5) — measured across every replayed game
- [6. The market they create together](#s6) — every episode's price swings, then one game up close
- [7. How fast the bar is moving](#s7) — the meta clock, and who moved this week
- [8. Who beats whom](#s8) — head-to-head win rates the ratings hide
- [9. How much of this is luck](#s9) — same bot, different games
- [10. The openings they share](#s10) — byte-identical lines, measured by stream hashes

Plus [the honest caveats](#s12) behind every chart, and the [takeaways](#s13).

**Want this for your own bot?** Fork, put your submission id in the one marked line near the top,
and the personal report reruns for you: where your best game lands in the whole field, and how
your strategy compares with the record holder's.

# Part I — the data

<a id="s1"></a>
## 1. What is in the dataset today

Before the strategy talk, the shape of the data itself: how much of the ladder is captured, how
deep the replay coverage goes, and how fast the corpus grows. Column-level docs live on the
[dataset page](https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes).

# Part II — the ladder

<a id="s2"></a>
## 2. The ladder right now

Winners' final banks across the recorded ladder games, one dot per episode. The spread is the
story of this competition: the same board and the same rules produce farms that differ by an
order of magnitude.

<a id="s3"></a>
## 3. The shape of a big game

Coin curves of the biggest wins on record against a median game. Top games share a silhouette:
the bank stays near zero deep into the season while everything is reinvested, then compounding
takes over once the farm is built.

<a id="s4"></a>
## 4. Strategy fingerprints

Replays store actions, not just scores, so you can compare bots by what they do. Those
fingerprints already sit in `episode_features.csv`, one row per seat for every episode that has
a replay, and section 1 prints how deep that coverage runs, so you rarely need to open a replay
yourself. The cell below is the method behind the crew, land and crop columns; bank shape and
prices get measured in sections 3 and 6. It stays open on purpose: it defines exactly what
`peak_crew` or `first_land_day` mean, and it is where to start if you want to measure something
I did not. Leaders against the middle of the ladder:

<a id="s5"></a>
## 5. What actually separates a big bank from a small one

The fingerprints above describe single games. With `episode_features.csv` we can ask the blunter
question across every replayed episode at once: which measurable choices track a large final
bank, and which ones only feel important?

One column is deliberately missing from this chart. `elbow_day` correlates with the bank at 0.8,
but it is derived from the bank itself (the day a farm crosses a tenth of its own final total),
so a weak farm crosses its small tenth early and a strong one crosses late. That is arithmetic,
not strategy, and including it would be the most confident wrong claim in this notebook.

<a id="s6"></a>
## 6. The market they create together

Prices are shared between the two players of an episode, and `episode_features.csv` records
every episode's low and high for all nine goods. First the whole corpus, so you can see which
markets actually move; then one game up close, where you can watch them being moved.

<a id="s7"></a>
## 7. How fast the bar is moving

The number every competitor wants: how much the ladder improves while you sleep. Median
winning bank per time slice, against the record so far. Skip a few days and this is the gap you
come back to. Below the clock: the movers, teams whose rating travelled furthest over the last
seven days of recorded games.

<a id="s8"></a>
## 8. Who beats whom

Ratings compress everything into one number, and that hides the interesting part: matchups don't
have to be transitive. Head-to-head win rates between the busiest teams; read a row as the row
team's share of wins against the column team.

<a id="s9"></a>
## 9. How much of this is luck

Same bot, different games: how wide is its spread? This decides how many submissions you need
before believing a result, and whether that one great game was skill or a lucky matchup.
A useful floor for reading the chart: in
[destbreso's weed-spawn ablation](https://www.kaggle.com/code/destbreso/kaggriculture-the-free-experiment-you-already-ran)
the environment alone moves a bank by a few hundred coins, while the spreads below run in the
tens of thousands. Nearly everything you see here is matchup, not dice.

<a id="s10"></a>
## 10. The openings they share

Two seats with the same stream hash at turn N played byte-identical actions for N straight
turns: a shared opening is an observation, not a similarity threshold. Two honest limits, both
measured by destbreso: nothing observable differs before turn 48, so early agreement is partly
the engine's determinism rather than evidence of copying, and the full-game hash identifies the
episode rather than the agent, so lineage lives in the prefixes, never in `stream_h719` alone.
The hashes ship in the dataset's `stream_hashes.csv`, proposed by
[destbreso in the dataset discussion](https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes/discussion/734833).
This section computes itself only when stream-hash coverage clears its 95% gate: on a partial,
time-ordered slice these rates would measure the nightly hash backfill, not the meta.

<a id="s12"></a>
## Before you quote these numbers

The honest edges of this snapshot, so the charts above don't overclaim:

- Fingerprints read one best game per submission: a sketch of a strategy at its peak, not its
  average behavior.
- The corpus is a crawl, not a census. Episodes are discovered through pairings, so a brand-new
  submission can lag behind the ladder by a few hours; section 1 prints the exact replay
  coverage.
- Head-to-head cells stand on a handful of games. The count is printed inside every cell; a 100%
  built on two games is an anecdote, not a verdict.
- Spread estimates use submissions with four or more games each, a modest per-bot sample even
  on a mature ladder; treat them as order-of-magnitude.
- Daily time series mix real change with crawler drift: which submissions the crawl services
  shifts over time, so day-over-day movement partly reflects the lens, not the ladder
  (destbreso measures the split with a fixed panel of teams).
- The two banks of one episode share its market and weather and correlate at +0.73, so
  cross-episode comparisons of raw banks carry shared-world variance; within-episode margins
  are the cleaner ruler ([measured here](https://www.kaggle.com/code/destbreso/kaggriculture-what-kind-of-game-is-this)).
- A submission's consecutive games are serially correlated (matchmaking chains opponents), so
  win-rate confidence intervals built on "n independent games" are narrower than the truth;
  [Know Your Noise](https://www.kaggle.com/code/destbreso/kaggriculture-know-your-noise)
  measures by how much.
- Validation (self-play) episodes are excluded from every strength comparison; section 1 shows
  their share of the raw data.