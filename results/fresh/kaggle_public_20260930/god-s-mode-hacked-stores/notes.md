<style>
:root{
  --ink:#173322;--ink2:#294438;--muted:#607468;--line:#d4e3da;
  --green:#1d7b4a;--teal:#16889a;--gold:#b27b12;--violet:#8357a8;
  --red:#b85348;--paper:#fcfefc;--paper2:#f2f8f4;
  --shadow:0 10px 28px rgba(20,60,38,.08);
}
.jp-RenderedHTMLCommon p,.jp-RenderedHTMLCommon li,.rendered_html p,.rendered_html li{line-height:1.68}
.jp-RenderedHTMLCommon h2,.rendered_html h2,h2{
  color:var(--ink)!important;background:linear-gradient(90deg,#fff,#f3faf6 60%,#eef8f7)!important;
  border:1px solid var(--line)!important;border-left:6px solid var(--green)!important;
  border-radius:17px;padding:13px 18px!important;margin-top:1.8em!important;box-shadow:var(--shadow)
}
.jp-RenderedHTMLCommon h3,.rendered_html h3,h3{color:var(--ink)!important}
code{background:rgba(80,120,95,.12)!important;padding:.12em .34em;border-radius:6px}
blockquote{border-left:4px solid var(--gold)!important;background:#fff9ec;padding:12px 16px!important;border-radius:0 12px 12px 0}
.sc-hero{position:relative;overflow:hidden;margin:6px 0 24px;padding:34px;border-radius:28px;color:#f7fff9;
  background:radial-gradient(circle at 85% 10%,rgba(88,243,166,.24),transparent 24%),linear-gradient(135deg,#08261a,#103a2a 48%,#123c50);
  box-shadow:0 18px 42px rgba(6,31,20,.19)}
.sc-hero:before{content:"";position:absolute;inset:0;background:linear-gradient(rgba(255,255,255,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.04) 1px,transparent 1px);background-size:26px 26px;pointer-events:none}
.sc-hero-grid{position:relative;display:grid;grid-template-columns:minmax(0,1.55fr) minmax(280px,.75fr);gap:24px}
.sc-kicker{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#a8ebc2;font-weight:800}
.sc-hero h1{color:white!important;font-size:46px;line-height:1.03;letter-spacing:-.04em;margin:10px 0 14px}
.sc-hero p{color:#f1fff6!important;font-size:17px;line-height:1.6;margin:0}
.sc-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}.sc-chip{padding:7px 11px;border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.08);border-radius:999px;font-size:12px;font-weight:700}
.sc-stats{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.sc-stat{background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.15);border-radius:17px;padding:14px}.sc-stat b{display:block;color:white;font-size:27px}.sc-stat span{display:block;color:#cfe9d9;font-size:12px;line-height:1.35}
.sc-grid{display:grid;grid-template-columns:repeat(2,minmax(250px,1fr));gap:12px;margin:14px 0}
.sc-card{border:1px solid var(--line);border-top:5px solid var(--green);border-radius:18px;background:linear-gradient(145deg,#f4fbf6,#fff);padding:17px;box-shadow:var(--shadow);color:var(--ink2)}
.sc-card.teal{border-top-color:var(--teal);background:linear-gradient(145deg,#eff9fa,#fff)}.sc-card.gold{border-top-color:var(--gold);background:linear-gradient(145deg,#fff8e9,#fff)}.sc-card.red{border-top-color:var(--red);background:linear-gradient(145deg,#fff2ef,#fff)}
.sc-card .tag{font-size:10px;letter-spacing:.13em;text-transform:uppercase;font-weight:900;color:var(--green)}.sc-card.teal .tag{color:var(--teal)}.sc-card.gold .tag{color:var(--gold)}.sc-card.red .tag{color:var(--red)}
.sc-card b{display:block;color:var(--ink);margin:6px 0}.sc-card span{font-size:14px;line-height:1.55;color:#50665a}
.sc-note{border:1px solid var(--line);border-left:5px solid var(--green);border-radius:15px;padding:14px 16px;margin:14px 0;background:#f3faf6;color:var(--ink2);box-shadow:var(--shadow)}
.sc-note.gold{border-left-color:var(--gold);background:#fff9ec}.sc-note.red{border-left-color:var(--red);background:#fff3f0}.sc-note.teal{border-left-color:var(--teal);background:#eef9fb}
.sc-note b{color:var(--ink)}
.sc-flow{display:grid;grid-template-columns:repeat(5,minmax(110px,1fr));gap:8px;margin:16px 0}.sc-step{position:relative;text-align:center;border:1px solid var(--line);border-radius:15px;padding:13px 9px;background:#fff;box-shadow:0 5px 15px rgba(20,60,38,.05);color:var(--ink)}.sc-step b{display:block;margin-bottom:4px}.sc-step small{color:var(--muted)}
.sc-figure{background:linear-gradient(145deg,#fbfdfb,#f2f8f4);border:1px solid var(--line);border-radius:20px;padding:14px;margin:16px 0;box-shadow:var(--shadow);overflow-x:auto}.sc-figure figcaption{font-size:12px;line-height:1.5;color:var(--muted);margin:8px 6px 2px}
.sc-math{background:#fff;border:1px solid var(--line);border-radius:16px;padding:15px 18px;margin:13px 0;color:var(--ink2);box-shadow:var(--shadow)}
.sc-math .meaning{color:#52695c;font-size:14px;line-height:1.58}
.sc-ledger{width:100%;border-collapse:separate;border-spacing:0;border:1px solid var(--line);border-radius:15px;overflow:hidden;background:white!important;color:var(--ink2)!important}.sc-ledger th,.sc-ledger td{padding:10px 12px;border-bottom:1px solid #e2ece5;background:white!important;color:var(--ink2)!important;text-align:left}.sc-ledger th{background:#f1f7f3!important;color:var(--ink)!important}.sc-ledger tr:last-child td{border-bottom:0}
.sc-scroll{overflow-x:auto;margin:14px 0;border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow)}
.sc-price-range{min-width:1320px;width:100%;border-collapse:collapse;background:#fff!important;color:var(--ink2)!important;font-size:11.5px}.sc-price-range th,.sc-price-range td{padding:8px 9px;border-bottom:1px solid #e3ece6;background:#fff!important;color:var(--ink2)!important;text-align:right;white-space:nowrap}.sc-price-range th{background:#f1f7f3!important;color:var(--ink)!important;font-size:10px;text-transform:uppercase;letter-spacing:.025em}.sc-price-range th:first-child,.sc-price-range th:nth-child(2),.sc-price-range td:first-child,.sc-price-range td:nth-child(2){text-align:left}.sc-price-range th:nth-child(4),.sc-price-range th:nth-child(7),.sc-price-range th:nth-child(10),.sc-price-range th:nth-child(13),.sc-price-range td:nth-child(4),.sc-price-range td:nth-child(7),.sc-price-range td:nth-child(10),.sc-price-range td:nth-child(13){border-left:2px solid var(--line)}.sc-price-range tbody tr:nth-child(even) td{background:#f9fbfa!important}.sc-price-range tr:last-child td{border-bottom:0}
.sc-pill{display:inline-block;padding:4px 8px;border-radius:999px;font-size:10px;font-weight:900;letter-spacing:.08em}.proven{background:#dff3e7;color:#176a40}.measured{background:#e1f1f4;color:#0d7180}.modelled{background:#f5ead1;color:#865e0b}.open{background:#f5dfdc;color:#9f3f35}
@media(max-width:820px){.sc-hero-grid,.sc-grid{grid-template-columns:1fr}.sc-flow{grid-template-columns:1fr 1fr}.sc-hero h1{font-size:37px}.sc-stats{grid-template-columns:1fr 1fr}}
</style>

<div class="sc-hero">
  <div class="sc-hero-grid">
    <div>
      <div class="sc-kicker">Kaggriculture 1.32.7 · causal inference · active sensing · adversarial control</div>
      <h1>⚡ God's Mode: Hacked Stores</h1><p><b>Can We Shape the Shops? Hidden-Seed Control in Kaggriculture</b></p>
      <p>A hidden seed chooses the shops. The agents cannot read that seed, but their farms consume the same random stream before each shop draw. This notebook separates four questions: can we change a shop, can we infer enough hidden state, can we request a specific shop, and does that intervention improve the final score?</p>
      <div class="sc-chips"><span class="sc-chip">392 controlled matches</span><span class="sc-chip">3,136 exact checks</span><span class="sc-chip">98 real replays</span><span class="sc-chip">31-bit seed audit</span></div>
    </div>
    <div class="sc-stats">
      <div class="sc-stat"><b>76.6%</b><span>one-cell interventions changed the next shop</span></div>
      <div class="sc-stat"><b>43.8%</b><span>seed-oracle PET_CAFE reachability with bounded offsets</span></div>
      <div class="sc-stat"><b>10–18%</b><span>projected directed coverage of all matches with the current design</span></div>
      <div class="sc-stat"><b>unknown</b><span>share of matches with positive score impact</span></div>
    </div>
  </div>
</div>

## One notebook, two execution modes

Both modes contain the complete original analysis, both interactive HTML dashboards, and the same submission agent. `SUBMISSION` skips rendering; `ARTICLE` renders everything for the public page. No external Dataset is required.


<div class="sc-callout"><b>Submission layer.</b> The exact Farming Score V2 parent is wrapped by the shop-evidence observer and the settlement-safe revealed-shop timing layer. Approximate future-shop particles are telemetry-only; action changes use shops that are already open and public state.</div>


## 1. Executive answer

The farm can causally change future shops. This is measured, not inferred from correlation. A legal one-cell `DIG` immediately before an unlock changed the next shop in **98 of 128 paired interventions (76.6%)**.

That does not mean we can choose any shop in 76.6% of matches. Directed control needs three additional layers: information about the hidden seed, an action that reaches the requested shop, and enough stability against the opponent's simultaneous action.

<div class="sc-flow">
  <div class="sc-step"><b>Observe</b><small>shops and weeds</small></div>
  <div class="sc-step"><b>Infer</b><small>seed candidates</small></div>
  <div class="sc-step"><b>Predict</b><small>opponent delta</small></div>
  <div class="sc-step"><b>Act</b><small>change empty count</small></div>
  <div class="sc-step"><b>Value</b><small>choose a profitable shop</small></div>
</div>

With ten maintained sensor cells and the current player-0-only indexing design, the projected result is:

- enough information for an informed last-shop decision in about **34% of all matches**;
- near-exact seed information by that point in about **16%**;
- at least one requested late shop in roughly **10–18%**;
- positive final-score impact: **not measured yet**.

<div class="sc-note gold"><b>The 43.8% result is strong but conditional.</b> It is the seed-oracle ceiling for reaching PET_CAFE with offsets −3…+3 across tested decisions. It assumes the hidden seed is already known. It is not the current live-agent success rate.</div>

### The economic reason to care appears before the RNG details

The default view below is copied from the engine-constant model behind `field_shops.html`: **TOMATO**, the last **K=6** reveals guaranteed as `PIZZA_SHOP`, and the same shop's effects on **MILK** and **WHEAT**. Worst, expected, and best refer only to the two earlier reveals. No player buying or selling is included.

The interactive figure preserves the useful behavior of the dashboard: hover for exact step, day, price and market inventory; click products or scenarios in the legend to isolate a trajectory. The game continues for six days after the eighth reveal. That tail is why late controlled shops can still matter.

### Full interactive Shop Stats dashboard

This is the complete `field-shops.html` research instrument, not a screenshot or a reduced reconstruction. Product selectors, the guaranteed-shop slider, scenario controls, hover details, sale calculator, demand tables, and every original chart remain active inside the notebook.

The notebook looks for the two HTML assets in any attached Kaggle dataset. The prepared asset folder is `shop-dashboard-assets`.

## Full interactive Field Worlds dashboard

This is the complete `field-worlds.html` interface with the source filter, all 64 ordered worlds, sortable performance metrics, the eight early worlds, probability-shape charts for every reveal, match drill-down, world-specific demand, and crop profitability. Click a world row to propagate the selection through the lower panels.

## How to read the replay atlas before the causal analysis

Here, a **world** is the ordered pair of the first shop on day 3 and the second shop on day 6. This is the earliest 64-way context used by several replay-routed agents. The current `field_worlds.html` archive contains **4,139 episodes from 17 sources**, and all **64 of 64** ordered worlds appear.

The largest source is the Daily Top-10 archive with **2,835 episodes (68.5%)**. The archive is therefore useful for mapping observed behavior, but it is not an IID sample of all possible games.

### World frequency — all 64 possible worlds on day 6

If the two revealed shop labels were independent and uniformly distributed, every ordered world would have probability:

<div class="sc-math">

$$P(W=(a,b))=\frac18\times\frac18=\frac1{64}=1.5625\%$$

<div class="meaning"><b>Meaning.</b> Across 4,139 episodes, the reference count is 64.7 observations per cell. The observed range is 38–89; the matrix-wide standard deviation is 8.19 episodes.</div>
</div>

The most common world is **PET_CAFE → PET_CAFE** with 89 observations (2.15%). The least common is **PIZZA_SHOP → FARMERS_MARKET** with 38 (0.92%). A descriptive uniformity statistic gives $\chi^2/df=66.43/63=1.05$. Because the archive repeats agents and collection windows, this is a shape diagnostic, not a formal IID hypothesis test.

### Probability shape — every reveal from day 3 to day 24

Use the dashboard's source buttons to compare the pooled distribution with each agent/archive separately. Across all 64 pooled shop/day cells, observed shares range from 11.48% to 13.29%. The pooled marginal shape stays close to uniform at every reveal. This does **not** prove that the shop is independent of the agents. Occupancy can shift the RNG index while the marginal result over many random seeds remains approximately uniform. The controlled one-cell intervention later in this notebook answers the causal question; this chart answers only the distributional question.

### World performance is a hypothesis map, not a causal ranking

`field_worlds.html` also records tie rate, average absolute margin, maximum score, and the average of the eight highest individual scores for each world. The strongest observed ceilings concentrate around dairy/tomato/strawberry shops, while some worlds produce much larger score gaps.

For example, **ICE_CREAM → ICE_CREAM** has the highest observed top-eight average at $171,690, while **PIZZA → FARMERS** has the largest average absolute margin at $17,390. These values mix world economics, agent quality, source composition, and historical meta. They identify worlds worth testing; they do not estimate what would happen if we forced that world.

## 2. Evidence ledger

This study uses four labels. **Proven** means exact agreement with engine behavior. **Measured** means empirical frequency in a fixed sample. **Modelled** means a projection based on explicit assumptions. **Open** means the final experiment has not been completed.

<table class="sc-ledger"><thead><tr><th>Claim</th><th>Status</th><th>Evidence</th></tr></thead><tbody>
<tr><td>Shop draw depends on seed, end-day, and total empty tiles consumed before the draw.</td><td><span class="sc-pill proven">PROVEN</span></td><td>3,136 / 3,136 controlled unlocks matched the reconstructed engine formula.</td></tr>
<tr><td>A one-cell occupancy intervention can change the next shop.</td><td><span class="sc-pill measured">MEASURED</span></td><td>98 / 128 paired interventions changed it.</td></tr>
<tr><td>Episode metadata reveals the seed through common mappings.</td><td><span class="sc-pill measured">REJECTED</span></td><td>0 exact matches across 3,954 unique episode/seed pairs.</td></tr>
<tr><td>Natural shop and weed history usually identifies the seed early.</td><td><span class="sc-pill measured">REJECTED</span></td><td>0 / 98 replays were near-exact by day 15; 3 / 98 by day 24.</td></tr>
<tr><td>Ten deliberate sensor cells can make late inference useful.</td><td><span class="sc-pill modelled">MODELLED</span></td><td>Conservative random-function screen; exact 31-bit index is not built.</td></tr>
<tr><td>Directed shop control improves Leaderboard score.</td><td><span class="sc-pill open">OPEN</span></td><td>Control and economic value have not passed a held-out paired test together.</td></tr>
</tbody></table>

## 3. The engine creates a causal lever

At every end of day, the engine initializes a deterministic Python random generator:

<div class="sc-math">

$$R_d = \operatorname{Random}\left((s\cdot 1{,}000{,}003)\oplus d\right)$$

<div class="meaning"><b>Meaning.</b> $s$ is the hidden 31-bit episode seed, $d$ is the day that just ended, and $\oplus$ is bitwise XOR. The generator is reset for each day.</div>
</div>

It then calls `random()` once for every empty tile on player 0's farm, then once for every empty tile on player 1's farm. If a shop opens, the next random value selects one of eight shop types.

<div class="sc-math">

$$S_d = f(s,d,E_0+E_1)$$

<div class="meaning"><b>Meaning.</b> $E_0$ and $E_1$ are the empty-tile counts after the players' last actions and before weed spawning. Coordinates, crop type, money, and player identity do not directly enter the shop draw. They matter only when they change the number or ordering of prior random calls.</div>
</div>

<figure class="sc-figure"><svg viewBox="0 0 980 225" width="100%" role="img" aria-label="Random stream before a shop draw">
<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#779486"/></marker></defs>
<rect x="35" y="65" width="165" height="85" rx="14" fill="#eaf6ee" stroke="#1d7b4a"/><text x="117" y="97" text-anchor="middle" font-family="sans-serif" font-weight="700" fill="#173322">hidden seed + day</text><text x="117" y="124" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#607468">initialize RNG</text>
<rect x="260" y="65" width="170" height="85" rx="14" fill="#edf8fa" stroke="#16889a"/><text x="345" y="97" text-anchor="middle" font-family="sans-serif" font-weight="700" fill="#173322">player 0 empties</text><text x="345" y="124" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#607468">consume E₀ draws</text>
<rect x="490" y="65" width="170" height="85" rx="14" fill="#f7f1fb" stroke="#8357a8"/><text x="575" y="97" text-anchor="middle" font-family="sans-serif" font-weight="700" fill="#173322">player 1 empties</text><text x="575" y="124" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#607468">consume E₁ draws</text>
<rect x="720" y="65" width="220" height="85" rx="14" fill="#fff7e7" stroke="#b27b12"/><text x="830" y="97" text-anchor="middle" font-family="sans-serif" font-weight="700" fill="#173322">next random value</text><text x="830" y="124" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#607468">select one of 8 shops</text>
<path d="M200 107 H250 M430 107 H480 M660 107 H710" stroke="#779486" stroke-width="3" marker-end="url(#arr)"/></svg><figcaption>A legal action that changes the final empty count changes the RNG position used for the shop.</figcaption></figure>

## 4. Controlled intervention: does one tile matter?

The causal experiment held the seed and both policies fixed. The intervention agent used one legal `DIG` on hour 23 immediately before a selected shop unlock. This increased the total empty count by one.

The sample contains three families:

- **occupancy sweep:** every controlled occupancy from 0 through 25 on one farm;
- **allocation control:** the same total split differently between the two players;
- **one-cell intervention:** identical paired games with and without one final `DIG`.

Across **392 complete games** and **3,136 shop events**, the reconstructed formula predicted every shop. The one-cell intervention changed **98 of 128** paired outcomes.

<div class="sc-grid">
  <div class="sc-card"><div class="tag">Formula validation</div><b>3,136 / 3,136</b><span>The engine reconstruction matched every controlled unlock.</span></div>
  <div class="sc-card teal"><div class="tag">Causal actuator</div><b>98 / 128 = 76.6%</b><span>One extra RNG call changed the categorical shop result.</span></div>
  <div class="sc-card gold"><div class="tag">What this proves</div><b>The world is action-dependent</b><span>Two agents can create different shop sequences on the same episode seed.</span></div>
  <div class="sc-card red"><div class="tag">What this does not prove</div><b>No requested-shop guarantee</b><span>A changed shop can be worse. Control requires information and value selection.</span></div>
</div>

## 5. What the live agent can and cannot observe

The episode seed is present in the environment's private state and later in the replay. It is removed from the live agent configuration. The agent observes public farm state, previous shops, and weed outcomes, but not the current seed.

This blocks the simplest implementation: calculate all possible offsets from the exact seed and choose the best one.

I tested whether replay metadata could act as a seed surrogate. The audit covered **3,954 unique episode/seed pairs**:

- zero seeds were reused across distinct episodes;
- 12 common mappings from EpisodeId, timestamp, UUID, CRC32, and SHA256 produced zero exact matches;
- EpisodeId/seed correlation was **−0.0099**;
- chronological ExtraTrees seed-bit accuracy was **50.20%**, versus a **49.96%** majority-bit baseline;
- exact predicted seeds: **0 of 989 holdout episodes**.

<div class="sc-note red"><b>Current conclusion.</b> No usable live metadata route to the seed was found. This is evidence against the tested mappings, not a proof that every unknown platform mapping is impossible.</div>

## 6. Previous shops alone are not an oracle

Suppose we ignore weeds and condition only on shops already revealed. I trained a history-to-offset policy on 32,768 seeds and evaluated it on 8,192 independent seeds. Each of the eight unlocks was evaluated, giving 65,536 held-out decisions.

For PET_CAFE:

- natural rate with no intervention: **12.631%**;
- best fixed offset: **12.340%**;
- learned history policy: **12.389%**;
- seed-oracle upper bound using offsets −3…+3: **43.802%**.

The learned seed-blind policy did not beat the natural draw. Yet the oracle found a requested PET_CAFE in almost half of decisions. This gap identifies the real bottleneck: **information**, not lack of an actuator.

<div class="sc-math">

$$\text{control gap}=P(\text{target}\mid\text{known seed, best offset})-P(\text{target}\mid\text{history only})$$

$$=0.4380-0.1239=0.3141$$

<div class="meaning"><b>Meaning.</b> About 31 percentage points of target reachability are available in the tested offset set, but shop history alone does not reveal which offset captures them.</div>
</div>

## 7. Why weeds are information

Each empty cell produces one Bernoulli weed observation with probability $p=0.005$. A normal no-weed result carries almost no realized information. A rare weed carries much more.

<div class="sc-math">

$$I(\text{weed})=-\log_2(0.005)=7.64\text{ bits}$$

<div class="meaning"><b>Meaning.</b> A weed is rare under a wrong seed. Observing one can eliminate many candidate seeds.</div>
</div>

<div class="sc-math">

$$I(\text{no weed})=-\log_2(0.995)=0.0072\text{ bits}$$

<div class="meaning"><b>Meaning.</b> A single failure is expected under almost every seed. Thousands of failures can still accumulate evidence, but each one contributes very little.</div>
</div>

The expected information per empty-cell day is the binary entropy:

<div class="sc-math">

$$H_2(p)=-p\log_2p-(1-p)\log_2(1-p)=0.0454\text{ bits}$$

<div class="meaning"><b>Meaning.</b> The average is small because 99.5% of observations are weak no-weed results. The distribution is heavy-tailed: a few weed-rich episodes become identifiable much earlier.</div>
</div>

## 8. Natural evidence in 98 real replays

For a history with $w$ weeds, $n-w$ no-weed draws, and $m$ known shops, the independent random-function screen estimates:

<div class="sc-math">

$$\mathbb{E}[N_{\text{compatible}}]\approx 1+(2^{31}-1)p^w(1-p)^{n-w}8^{-m}$$

<div class="meaning"><b>Meaning.</b> The true seed contributes one candidate. The second term estimates how many false 31-bit seeds would accidentally reproduce the same weed and shop signature. This is a likelihood screen, not exact Python-MT inversion.</div>
</div>

Natural route evidence narrows the posterior too late for universal control. Before day 15, no replay was close. Before day 24, 13 of 98 replays had an expected candidate count at or below ten, but only three were at or below two.

<div class="sc-note teal"><b>Rare opportunity remains real.</b> A weed-rich episode can become almost identified late. The data rejects universal early inference, not opportunistic late inference.</div>

## 9. Active sensing: make the farm observe the RNG

Natural play does not create enough reliable evidence. Active sensing deliberately maintains a small set of empty cells. Every end of day, each cell produces another observed weed/no-weed bit from the shop's random stream.

The proposed player-0 architecture keeps the first $K$ owned cells in row-major order empty. Because the engine consumes player 0's empty cells first, those observations form a fixed prefix independent of the opponent.

<figure class="sc-figure"><svg viewBox="0 0 980 290" width="100%" role="img" aria-label="Ten empty sensor cells on player zero farm">
<text x="40" y="35" font-family="sans-serif" font-weight="700" fill="#173322">PLAYER 0: FIXED PREFIX</text><text x="585" y="35" font-family="sans-serif" font-weight="700" fill="#173322">PLAYER 1: VARIABLE SUFFIX</text>
<g transform="translate(40,58)">
<rect width="400" height="180" rx="14" fill="#f4faf6" stroke="#1d7b4a"/>
<g fill="#fff4cf" stroke="#b27b12"><rect x="20" y="20" width="34" height="34"/><rect x="58" y="20" width="34" height="34"/><rect x="96" y="20" width="34" height="34"/><rect x="134" y="20" width="34" height="34"/><rect x="172" y="20" width="34" height="34"/><rect x="210" y="20" width="34" height="34"/><rect x="248" y="20" width="34" height="34"/><rect x="286" y="20" width="34" height="34"/><rect x="324" y="20" width="34" height="34"/><rect x="20" y="58" width="34" height="34"/></g>
<text x="200" y="135" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#294438">10 maintained empty sensor cells</text><text x="200" y="159" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#607468">same RNG indices every observed refresh</text></g>
<g transform="translate(540,58)"><rect width="400" height="180" rx="14" fill="#f5f1f8" stroke="#8357a8"/><path d="M45 50 C120 10 180 110 245 55 S340 95 370 42" fill="none" stroke="#8357a8" stroke-width="4" stroke-dasharray="8 6"/><text x="200" y="135" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#294438">opponent empties consume unknown draws</text><text x="200" y="159" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#607468">the prefix length changes with its final action</text></g>
<path d="M440 148 H530" stroke="#779486" stroke-width="3"/><text x="485" y="136" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#607468">then</text>
</svg><figcaption>The same design does not transfer directly to player 1 because player 0 consumes a variable number of draws first.</figcaption></figure>

The cost is economic. Sensor cells do not produce crops or structures. Spawned weeds must be cleared if the index is to remain stable. The information gain must exceed lost production, movement, and repair cost.

## 10. Conservative sensor projection

The first screen assumed five natural empty-cell draws per day. That assumption was too optimistic for the observed replay routes. The table below therefore counts **only deliberate sensor draws**. It gives the method no credit for uncontrolled natural evidence.

For ten sensors, the probability of an expected candidate set no larger than ten is:

- **15.6%** of compatible player-0 games by day 15;
- **20.9%** by day 18;
- **26.4%** by day 21;
- **68.4%** by day 24.

If seats are balanced and the fixed-prefix resolver works only in player 0, divide these by two when reporting coverage of all matches.

<div class="sc-note gold"><b>Model boundary.</b> These probabilities use an independent random-function approximation. They do not prove exact uniqueness under Python's MT19937, runtime feasibility, or positive economics.</div>

## 11. Fixed-index prototype and the 31-bit cost

A 65,536-seed prototype used ten cells over 20 days, or 200 deliberate observations. It produced 14,619 distinct signatures.

- median bucket for a random seed: **125 seeds**;
- 90th percentile bucket: **24,190 seeds**;
- maximum bucket: **24,190 seeds**;
- no-weed signature probability: approximately **36.7%**.

The no-weed tail explains the large collision bucket. Ten cells do not guarantee identification. They create a lottery: a rare weed can make the posterior sharp, while a common all-clear history remains broad.

A complete 31-bit reverse index needs at least:

<div class="sc-math">

$$2^{31}\text{ seeds}\times4\text{ bytes}=8\text{ GiB}$$

<div class="meaning"><b>Meaning.</b> This is only the raw seed array. A signature directory, collision checks, archive packaging, extraction time, and lookup code add overhead. The size is plausible under a large attached Dataset, but the hosted build and runtime remain unvalidated.</div>
</div>

## 12. The second-seat problem

The current fixed sensor index is straightforward only for player 0. The engine processes player 0's empty cells first. Therefore player 0 can reserve the first $K$ RNG indices.

For player 1, the opponent's empty count is an unknown prefix. Even if our ten cells remain empty, they may correspond to indices 7–16 in one match and 11–20 in another. The observed signature cannot be looked up without predicting that prefix.

There are three possible repairs:

1. infer the opponent's final empty-count delta and enumerate a small prefix range;
2. build a shift-tolerant signature index that searches several possible starting positions;
3. use only total weed counts and shop consensus, accepting less information.

Until one passes an exact paired test, current all-match coverage includes the 50% seat factor.

## 13. Simultaneous action is uncertainty, not total chaos

We see the opponent's completed previous step, not its action on the step we are currently choosing. The final action can change its empty count immediately before the shop draw.

In 250 public replays, 4,000 pre-unlock terminal states showed no opponent empty-count change **92.7%** of the time overall. The rate varied by unlock:

- day 12: **71.4%**;
- day 15: **95.0%**;
- day 18: **95.8%**;
- day 21: **91.8%**;
- day 24: **88.6%**.

A held-out model split by agent identity reached **94.9% raw accuracy** and **68.9% balanced accuracy**. Raw accuracy is high because zero is common. Balanced accuracy is the more honest measure of whether the minority changes are detected.

<div class="sc-note teal"><b>Operational rule.</b> Act only when the target survives the posterior over both seed candidates and plausible opponent deltas. Abstention is part of the controller.</div>

## 14. From 76.6% change to 10–18% directed match coverage

Four probabilities must not be mixed:

<div class="sc-math">

$$P(\text{useful control})\approx P(I)\times P(R\mid I)\times P(S)\times P(V)$$

<div class="meaning"><b>Meaning.</b> $I$ means enough information, $R$ means the requested shop is reachable by a legal bounded action, $S$ means the opponent does not invalidate the chosen offset, and $V$ means the new shop is worth more than the intervention and sensor cost.</div>
</div>

The current estimate omits $P(V)$ because score value is not measured. It combines the information milestones with multiple remaining opportunities:

- near-exact seed information supports a conservative **about 10%** directed-match estimate;
- allowing consensus actions over candidate sets up to ten gives an optimistic **about 18%**;
- solving the second seat could raise the technical directed range toward **20–35%**;
- these are projected match-level opportunities, not guaranteed wins.

<figure class="sc-figure"><svg viewBox="0 0 980 250" width="100%" role="img" aria-label="Control probability funnel">
<g font-family="sans-serif"><rect x="45" y="35" width="890" height="38" rx="9" fill="#dfeee5"/><text x="65" y="60" font-weight="700" fill="#173322">Physical change on a tested one-cell intervention</text><text x="905" y="60" text-anchor="end" font-weight="800" fill="#173322">76.6%</text>
<rect x="130" y="88" width="720" height="38" rx="9" fill="#dff1f4"/><text x="150" y="113" font-weight="700" fill="#173322">Enough information by the last shop · 10 sensors · current seat support</text><text x="820" y="113" text-anchor="end" font-weight="800" fill="#173322">34.2%</text>
<rect x="245" y="141" width="490" height="38" rx="9" fill="#f4e9cf"/><text x="265" y="166" font-weight="700" fill="#173322">Directed requested shop at least once · projected range</text><text x="705" y="166" text-anchor="end" font-weight="800" fill="#173322">10–18%</text>
<rect x="355" y="194" width="270" height="38" rx="9" fill="#f5dfdc"/><text x="375" y="219" font-weight="700" fill="#173322">Positive score impact</text><text x="595" y="219" text-anchor="end" font-weight="800" fill="#173322">OPEN</text></g></svg><figcaption>Each number answers a different question. The funnel prevents a causal effect from being reported as a competitive gain.</figcaption></figure>

## 15. Why a shop can be economically valuable

Each shop removes selected products from the market over its remaining active ticks. Repeated shops can create a cumulative deficit. Prices rise nonlinearly when inventory becomes scarce.

For a product $g$:

<div class="sc-math">

$$D_g(t)=C_g(t)+\sum_j q_{j,g}(t)-\sum_{a\in\{0,1\}}\operatorname{SELL}_{a,g}(t)$$

<div class="meaning"><b>Meaning.</b> $C_g$ is Town Center withdrawal, $q_{j,g}$ is shop consumption, and player sales refill the market. A positive deficit can raise price, but both players can destroy it by selling into the same market.</div>
</div>

PET_CAFE consumes carrot at multiplier two. In a demand-only ceiling with no player sales, repeated PET_CAFE copies produce the following carrot prices:

- one copy: **63**;
- two: **136**;
- three: **377**;
- four: **724**;
- five: **1,111**;
- six: **1,485**.

These are not revenue forecasts. They are upper ceilings before either player sells carrots. The opponent observes the same price and can plant the same fast crop.

The target should therefore be selected as a **portfolio**, not fixed to PET_CAFE. A basket shop can spread demand across several products and be harder for the opponent to collapse.

### Price range: worst / expected / best, given the last K reveals are guaranteed to fit

This is the full table from the same engine-constant model. In every group, the **last K reveals are fixed** to the single shop that drains that product fastest. Only the remaining early reveals vary:

- **worst:** every early reveal misses the product;
- **expected:** early reveals contribute their uniform 1-in-8 expected demand;
- **best:** every early reveal also selects the same best shop.

The projection runs through day 30 and includes Town Center consumption. It includes no player buying or selling. Therefore, each number is a controlled demand-pressure scenario, not an expected match price.

<div class="sc-scroll"><table class="sc-price-range"><thead><tr><th rowspan="2">Product</th><th rowspan="2">Best shop</th><th rowspan="2">Base</th><th colspan="3">Last 3 guaranteed</th><th colspan="3">Last 4 guaranteed</th><th colspan="3">Last 5 guaranteed</th><th colspan="3">Last 6 guaranteed</th></tr><tr><th>Worst</th><th>Expected</th><th>Best</th><th>Worst</th><th>Expected</th><th>Best</th><th>Worst</th><th>Expected</th><th>Best</th><th>Worst</th><th>Expected</th><th>Best</th></tr></thead><tbody><tr><td><b>WHEAT</b></td><td>BAKERY (1/tick)</td><td>$25</td><td>$39</td><td>$50</td><td>$54</td><td>$42</td><td>$51</td><td>$54</td><td>$45</td><td>$51</td><td>$54</td><td>$48</td><td>$52</td><td>$54</td></tr><tr><td><b>CARROT</b></td><td>PET (2/tick)</td><td>$35</td><td>$65</td><td>$133</td><td>$2,363</td><td>$104</td><td>$260</td><td>$2,363</td><td>$277</td><td>$498</td><td>$2,363</td><td>$657</td><td>$892</td><td>$2,363</td></tr><tr><td><b>TOMATO</b></td><td>PIZZA (1/tick)</td><td>$60</td><td>$86</td><td>$252</td><td>$2,319</td><td>$151</td><td>$406</td><td>$2,319</td><td>$343</td><td>$655</td><td>$2,319</td><td>$721</td><td>$1,030</td><td>$2,319</td></tr><tr><td><b>STRAWBERRY</b></td><td>BRUNCH (1/tick)</td><td>$120</td><td>$242</td><td>$315</td><td>$368</td><td>$267</td><td>$324</td><td>$368</td><td>$292</td><td>$333</td><td>$368</td><td>$317</td><td>$344</td><td>$368</td></tr><tr><td><b>MELON</b></td><td>none</td><td>$250</td><td>$280</td><td>$280</td><td>$280</td><td>$280</td><td>$280</td><td>$280</td><td>$280</td><td>$280</td><td>$280</td><td>$280</td><td>$280</td><td>$280</td></tr><tr><td><b>EGG</b></td><td>BAKERY (1/tick)</td><td>$50</td><td>$63</td><td>$75</td><td>$523</td><td>$68</td><td>$96</td><td>$523</td><td>$87</td><td>$140</td><td>$523</td><td>$154</td><td>$218</td><td>$523</td></tr><tr><td><b>MILK</b></td><td>PIZZA (1/tick)</td><td>$160</td><td>$286</td><td>$346</td><td>$416</td><td>$312</td><td>$358</td><td>$416</td><td>$338</td><td>$371</td><td>$416</td><td>$364</td><td>$385</td><td>$416</td></tr><tr><td><b>WOOL</b></td><td>YARN (2/tick)</td><td>$200</td><td>$251</td><td>$254</td><td>$264</td><td>$255</td><td>$256</td><td>$264</td><td>$257</td><td>$259</td><td>$264</td><td>$260</td><td>$260</td><td>$264</td></tr><tr><td><b>FERTILIZER</b></td><td>none</td><td>$100</td><td>$100</td><td>$100</td><td>$100</td><td>$100</td><td>$100</td><td>$100</td><td>$100</td><td>$100</td><td>$100</td><td>$100</td><td>$100</td><td>$100</td></tr></tbody></table></div>

<div class="sc-note gold"><b>How to read it.</b> Compare ranges within one product, not raw prices across unrelated products. Tomato and carrot have sharp hinge responses. Wheat is touched by five shop types but has a damped response. Melon and fertilizer are not consumed by any shop, so guaranteeing shop reveals cannot change their range.</div>

## 16. Which target is safer than a single-product spike?

For four to six controlled late shops, a basket screen evaluated peak price, price after a standard probe sale, total probe revenue, and the weakest product line. Selected six-shop results:

- FARMERS_MARKET: wheat + carrot + tomato + strawberry; basket peak **1,041**, probe revenue **88,149**;
- PIZZA_SHOP: milk + tomato + wheat; basket peak **1,006**, probe revenue **85,510**;
- ICE_CREAM_SHOP: strawberry + milk + wheat; basket peak **716**, probe revenue **69,559**;
- SMOOTHIE_SHOP: strawberry + milk; basket peak **668**, probe revenue **64,899**;
- PET_CAFE: carrot only; basket peak **534**, probe revenue **45,937**;
- YARN_STORE: wool only; basket peak **259**, probe revenue **25,887**.

The sum alone is not enough. A good target must fit products already producible by our route, remain valuable after both players sell, and avoid gifting more value to the opponent.

<div class="sc-math">

$$V(j)=\mathbb E[\Delta \text{own liquidation}\mid j]-\mathbb E[\Delta \text{opponent liquidation}\mid j]-C_{\text{sensor}}-C_{\text{actuator}}$$

<div class="meaning"><b>Meaning.</b> Shop $j$ is useful only when the additional value of our inventory exceeds the value given to the opponent and the full opportunity cost of controlling it.</div>
</div>

## 17. Control is not the same as winning

A known-seed campaign successfully produced four to six PET_CAFEs in several local worlds. It also exposed the most important failure mode: forcing demand while keeping an incompatible inherited production route.

Against two stronger opponents on seeds 0 and 3, the unchanged baseline had positive margins of **+3,396, +6,303, +4,363, and +7,040**. The PET_CAFE campaign changed those to **−7,984, −10,557, −3,405, and −7,547**.

The controller shaped the shops and still lost. The opponent received the same market, while our route did not convert the new demand into enough additional inventory and sale priority.

<div class="sc-note red"><b>Necessary promotion gate.</b> Never promote a controller because it created the requested shop. Promote only when a paired held-out experiment improves score after sensor cost, route changes, opponent benefit, and both seats.</div>

## 18. A production controller needs five gates

The final overlay should be modular. It must leave any parent agent unchanged unless every gate passes.

1. **Sensor gate:** can we maintain the chosen cells without breaking the parent route?
2. **Information gate:** is the posterior small enough, or do candidate seeds agree on one action?
3. **Opponent gate:** does the target survive plausible final empty-count deltas?
4. **Reachability gate:** is a legal action available and does it produce the selected shop?
5. **Value gate:** is expected relative value positive after all costs?

<div class="sc-math">

$$a^*=\arg\max_{a\in\mathcal A}\ \mathbb E_{s\sim P(s\mid h),\ \delta\sim P(\delta\mid x)}[V(S(s,d,E+a+\delta))]-C(a)$$

<div class="meaning"><b>Meaning.</b> The controller chooses a legal occupancy action $a$ across the posterior over seeds and opponent deltas. It acts only if the expected shop value exceeds the action cost. Otherwise it returns the parent agent's action unchanged.</div>
</div>

This structure lets the module wrap a new open agent without rewriting its core policy. The integration contract is one bounded action override plus telemetry.

## 19. Exact next experiments

The work should proceed through falsifiable gates.

### A. Build the real player-0 resolver

- create a 31-bit signature index for ten fixed sensor cells;
- measure archive size, extraction time, lookup latency, and true-seed retention;
- reject if it cannot run inside the hosted action budget.

### B. Replace candidate count with action consensus

- for every compatible seed, calculate the shop under each legal offset;
- act when one offset yields positive value for at least a chosen posterior mass;
- measure calibration: predicted success versus realized success.

### C. Repair player 1

- enumerate plausible opponent prefixes using the terminal-action model;
- test shift-tolerant signatures;
- report player 0 and player 1 separately before combining them.

### D. Couple control to economy

- choose the target from current inventory, future production, opponent inventory, and remaining ticks;
- compare single-product targets with basket targets;
- include sensor cells and repair actions in projected value.

### E. Run the decisive paired test

- same seed, opponent, and seat: parent versus parent+controller;
- unseen seeds and several strong opponent families;
- primary metric: paired final-margin delta;
- secondary metrics: requested-shop success, abstention, sensor cost, opponent benefit, and failure stage.

<div class="sc-note"><b>Promotion rule.</b> Require a positive paired mean, a confidence interval that excludes a material loss, no seat collapse, and no large tail failures. Shop accuracy alone is never sufficient.</div>

## 20. Private-test robustness

This method relies on engine semantics, not on memorized public worlds. That is an advantage only if the private evaluation keeps the same RNG order, weed probability, shop list, and action timing.

The controller must fingerprint the public observation schema and abstain when assumptions fail. A private change could include:

- different seed distribution but identical mechanics: the method should transfer;
- different shops or economic parameters: inference may transfer, value model must adapt;
- different RNG ordering or weed probability: the signature index becomes invalid;
- different simultaneous-action timing: actuator predictions become invalid.

The safe design stores engine version and mechanism assumptions next to every index. It never guesses after a version mismatch.

## 21. Final conclusion

The central discovery is real: **agents do not merely react to a pre-generated shop world; their farms help generate it**.

The actuator is strong. A one-cell intervention changed 76.6% of paired shop outcomes. With the hidden seed known, a bounded set of offsets reached PET_CAFE in 43.8% of tested decisions.

The missing layer is online information. Natural play resolves only a rare late tail. Ten deliberate sensor cells create a plausible path to directed control in about 10–18% of all matches under the current player-0-only design. Supporting both seats could approximately double the technical opportunity.

The final competitive value remains open. The first forced-shop campaign showed why: changing the market without changing production can help the opponent more than us.

> The next objective is not “force more PET_CAFEs.” It is “act only when a posterior-robust shop change raises our expected margin after every cost.”

### Reproducibility boundary

All headline figures are tied to Kaggriculture engine version 1.32.7 and fixed local artifacts: 392 controlled matches, 3,136 unlock events, 98 downloaded Seven-Turn replays, 3,954 metadata-linked episodes, and an 8,192-seed held-out control screen. Modelled coverage is labelled separately from measured frequency.

## Submit this same article version

Run this notebook with `MODE = "ARTICLE"`, save the completed version, then choose `/kaggle/working/submission.tar.gz` from its Output tab and submit it to Kaggriculture. The saved version contains the full article and interactive dashboards; the competition score is attached to the submission created from that version.
