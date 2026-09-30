<style>
:root{
  --ink:#173322; --ink2:#2c4839; --muted:#64776b; --line:#d7e5dc;
  --green:#247a4b; --teal:#218b9b; --gold:#b47b18; --violet:#835ca4;
  --paper:#fcfefc; --paper2:#f2f8f4;
  --shadow:0 10px 28px rgba(20,60,38,.07);
}
.jp-RenderedHTMLCommon p,.jp-RenderedHTMLCommon li,.rendered_html p,.rendered_html li{line-height:1.7}
.jp-RenderedHTMLCommon h2,.rendered_html h2,h2{
  color:var(--ink)!important;background:linear-gradient(90deg,#fff,#f4faf6 58%,#eef7f3);
  border:1px solid #d2e2d8!important;border-left:6px solid var(--green)!important;border-radius:18px;
  padding:13px 18px 13px 22px!important;margin-top:1.85em!important;margin-bottom:.85em!important;
  letter-spacing:-.018em;box-shadow:0 8px 24px rgba(20,60,38,.05)
}
.jp-RenderedHTMLCommon h2::before,.rendered_html h2::before,h2::before{
  content:"Field note";display:inline-block;margin-right:11px;padding:4px 9px;font-size:10px;font-weight:800;
  letter-spacing:.14em;text-transform:uppercase;color:#fff;background:linear-gradient(135deg,var(--green),#35a664);
  border-radius:999px;vertical-align:middle
}
code{background:rgba(102,129,112,.12)!important;padding:.12em .34em;border-radius:6px}
pre,.jp-OutputArea-output pre,.output_subarea pre{border:1px solid var(--line);border-radius:15px;padding:14px;background:#fbfdfb!important}
blockquote{border-left:4px solid var(--gold)!important;padding:12px 16px!important;border-radius:0 12px 12px 0;background:#fffaf0}
.kg-hero{position:relative;box-sizing:border-box;margin:6px 0 24px;padding:31px;border-radius:30px;overflow:hidden;
 background:radial-gradient(circle at 84% 12%,rgba(118,255,182,.25),transparent 23%),radial-gradient(circle at 73% 88%,rgba(63,196,255,.15),transparent 28%),linear-gradient(135deg,#08261a 0%,#103624 43%,#113a49 100%);
 color:#f6fff9;border:1px solid rgba(255,255,255,.12);box-shadow:0 18px 42px rgba(6,31,20,.18)}
.kg-hero::before{content:"";position:absolute;inset:0;background:linear-gradient(rgba(255,255,255,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.04) 1px,transparent 1px);background-size:26px 26px;mask-image:linear-gradient(180deg,rgba(0,0,0,.7),transparent 92%);pointer-events:none}
.kg-hero-grid{position:relative;z-index:1;display:grid;grid-template-columns:minmax(0,1.45fr) minmax(310px,.9fr);gap:24px;align-items:stretch}
.kg-kicker{font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:#a6ebc0;font-weight:800}
.kg-hero h1{font-size:46px;line-height:1.02;margin:10px 0 12px;color:#fff!important;letter-spacing:-.045em}
.kg-hero-copy{margin-top:10px;padding:14px 16px;border-radius:16px;background:rgba(2,18,12,.34);border:1px solid rgba(255,255,255,.12)}
.kg-hero-copy p{font-size:17px;line-height:1.62;margin:0;color:#f5fff8!important}
.kg-chip-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}.kg-chip{border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.08);color:#effcf4;padding:7px 11px;border-radius:999px;font-size:12px;font-weight:700}
.kg-stat-row{display:grid;grid-template-columns:repeat(3,minmax(100px,1fr));gap:9px;margin-top:17px}.kg-stat{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:17px;padding:11px 12px}.kg-stat .v{display:block;color:#fff;font-weight:900;font-size:23px}.kg-stat .k{display:block;color:#cde7d8;font-size:11.5px;line-height:1.3}
.kg-art{background:linear-gradient(180deg,rgba(4,20,14,.42),rgba(10,30,21,.56));border-radius:24px;padding:14px;border:1px solid rgba(255,255,255,.14)}
.kg-art .label{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:#a8ecc2;font-weight:800;margin:2px 0 8px 4px}
.kg-prose{position:relative;background:linear-gradient(145deg,var(--paper),var(--paper2));color:var(--ink2);border:1px solid var(--line);border-radius:18px;padding:17px 18px;margin:12px 0 15px;box-shadow:var(--shadow)}
.kg-prose::before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;border-radius:18px 0 0 18px;background:linear-gradient(180deg,var(--green),#56b07a)}
.kg-prose .lead{font-size:15px;line-height:1.67}.kg-prose .micro{font-size:13px;color:var(--muted)}
.kg-roadmap{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:11px;margin:14px 0 8px}.kg-road{position:relative;border:1px solid var(--line);border-radius:20px;padding:17px 15px 15px;box-shadow:var(--shadow);overflow:hidden;background:linear-gradient(145deg,#fcfefc,#f3f8f5)}
.kg-road .n{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:13px;background:linear-gradient(135deg,var(--green),#35a664);color:#fff;font-weight:900}.kg-road.teal .n{background:linear-gradient(135deg,var(--teal),#2aa8bd)}.kg-road.gold .n{background:linear-gradient(135deg,var(--gold),#dba128)}.kg-road.violet .n{background:linear-gradient(135deg,var(--violet),#a37bc4)}
.kg-road .t{display:block;margin-top:13px;font-weight:800;color:var(--ink);font-size:15px}.kg-road .d{display:block;margin-top:6px;color:#53695d;line-height:1.52;font-size:13.5px}
.kg-grid{display:grid;grid-template-columns:repeat(2,minmax(240px,1fr));gap:12px;margin:14px 0}.kg-card{border:1px solid var(--line);border-radius:19px;padding:17px;box-shadow:var(--shadow);background:#fff;color:var(--ink)}.kg-card b{display:block;margin:5px 0}.kg-card span{color:#53695d;font-size:13.5px;line-height:1.52}.kg-card .eyebrow{font-size:10px;letter-spacing:.13em;text-transform:uppercase;font-weight:800}.kg-card.green{border-top:5px solid var(--green)}.kg-card.teal{border-top:5px solid var(--teal)}.kg-card.gold{border-top:5px solid var(--gold)}.kg-card.violet{border-top:5px solid var(--violet)}
.kg-note{border:1px solid var(--line);border-left:5px solid var(--green);border-radius:16px;padding:15px 17px;margin:14px 0;box-shadow:var(--shadow);background:linear-gradient(135deg,#eef9f2,#fbfdfb);color:var(--ink)}.kg-note.gold{border-left-color:var(--gold);background:linear-gradient(135deg,#fff7e5,#fffdf8)}.kg-note.teal{border-left-color:var(--teal);background:linear-gradient(135deg,#ebf8fa,#fbfefe)}.kg-note .title{font-weight:800;margin-bottom:5px}.kg-note .body{color:#486052;line-height:1.62;font-size:14px}
.kg-flow{background:#fff;border:1px solid var(--line);border-radius:22px;padding:13px;margin:15px 0;box-shadow:var(--shadow);overflow-x:auto}
.kg-terminal{background:linear-gradient(135deg,#0d2a1e,#12362a);color:#eaf8ef;border:1px solid #326247;border-radius:18px;padding:17px 19px;margin:14px 0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;line-height:1.8;box-shadow:0 10px 24px rgba(8,33,22,.16)}
.kg-terminal b{color:#9be5b7}.kg-terminal .dim{color:#a9c9b5}
.kg-caption{font-size:13px;color:#607468;margin-top:6px}
.jp-OutputArea-output table,.output_html table,.rendered_html table,table.dataframe{background:#fff!important;color:#203a2c!important;border-color:#d6e3da!important;color-scheme:light!important}.jp-OutputArea-output table thead,.output_html table thead,table.dataframe thead{background:#f2f7f4!important;color:#173322!important}
@media(max-width:920px){.kg-roadmap{grid-template-columns:repeat(2,minmax(0,1fr))}.kg-hero-grid{grid-template-columns:1fr}}
@media(max-width:700px){.kg-hero{padding:22px}.kg-hero h1{font-size:37px}.kg-roadmap,.kg-grid{grid-template-columns:1fr}.kg-stat-row{grid-template-columns:1fr 1fr 1fr}}
</style>

<div class="kg-hero">
<div class="kg-hero-grid">
<div>
<div class="kg-kicker">Kaggriculture · conserved route replay · three public checkpoints · one-slot capacity reserve</div>
<h1>🌾 Shape the Shop, Work the Pasture</h1>
<div class="kg-hero-copy"><p>The long programme still does the heavy lifting. Three public-state checkpoints may choose a prefix-compatible continuation, while a compact repair layer handles observable edge cases. The closeout remains value-aware, with one small addition: at day close the guard aims for 99 items instead of filling the 100-item shed exactly. That single slot gives carried stock a little breathing room without changing the route itself.</p></div>
<div class="kg-chip-row"><span class="kg-chip">720-turn season</span><span class="kg-chip">Prefix-safe route tails</span><span class="kg-chip">3 public checkpoints</span><span class="kg-chip">99 / 100 closeout target</span></div>
<div class="kg-stat-row"><div class="kg-stat"><span class="v">4</span><span class="k">compatible route tails</span></div><div class="kg-stat"><span class="v">3</span><span class="k">public-state checkpoints</span></div><div class="kg-stat"><span class="v">1</span><span class="k">reserved shed slot</span></div></div>
</div>
<div class="kg-side"><div class="kg-side-label">Core idea</div><div class="kg-side-big">Keep the route.<br>Leave one slot free.</div><div class="kg-side-small">The agent still sells only the small projected excess, protecting future route demand before using the visible quote as a tie-breaker.</div></div>
</div></div>

## Read the notebook in four passes
<div class="kg-roadmap">
<div class="kg-road"><span class="n">01</span><span class="t">What stays fixed?</span><span class="d">Movement, production, and the planned market route remain stored programmes.</span></div>
<div class="kg-road teal"><span class="n">02</span><span class="t">Where can the route change?</span><span class="d">Steps 226, 360, and 433 read visible state and switch only to a prefix-compatible tail.</span></div>
<div class="kg-road gold"><span class="n">03</span><span class="t">What is slightly stronger?</span><span class="d">The value-aware day-close guard keeps one shed slot in reserve, reducing near-capacity carryover risk while preserving the same route.</span></div>
<div class="kg-road violet"><span class="n">✓</span><span class="t">What actually ran?</span><span class="d">The exact generated <code>main.py</code> runs for all 720 turns; the animation and EDA use that same trajectory.</span></div>
</div>

## 1. The strategy is still mostly an invariant
<div class="kg-prose"><div class="lead">This is not a new planner. Stored routes do ordinary farm work, public checkpoints select compatible continuations, and a thin repair stack handles only observable failures at the edges.</div></div>
<div class="kg-flow"><svg viewBox="0 0 980 205" width="100%" role="img" aria-label="strategy flow">
<defs><style>.b{fill:#fff;stroke:#cfe0d5;stroke-width:2}.t{font:700 14px sans-serif;fill:#173322}.s{font:12px sans-serif;fill:#607168}.l{stroke:#9eb5a7;stroke-width:3;fill:none}.g{fill:#eaf7ef;stroke:#5fa47a}.u{fill:#eaf7f9;stroke:#61aab5}.o{fill:#fff5df;stroke:#cfa54a}</style></defs>
<rect class="b" x="22" y="64" width="178" height="82" rx="16"/><text class="t" x="111" y="93" text-anchor="middle">Conserved route tape</text><text class="s" x="111" y="117" text-anchor="middle">movement · production</text><text class="s" x="111" y="134" text-anchor="middle">planned market actions</text>
<path class="l" d="M200 105 H255"/><rect class="u" x="255" y="47" width="210" height="116" rx="16"/><text class="t" x="360" y="76" text-anchor="middle">Public-state router</text><text class="s" x="360" y="101" text-anchor="middle">226 · Yarn Store</text><text class="s" x="360" y="120" text-anchor="middle">360 · Carrot price</text><text class="s" x="360" y="139" text-anchor="middle">433 · Milk inventory</text>
<path class="l" d="M465 105 H520"/><rect class="g" x="520" y="47" width="205" height="116" rx="16"/><text class="t" x="622" y="76" text-anchor="middle">Repair layer</text><text class="s" x="622" y="101" text-anchor="middle">weed dig · clamp sells</text><text class="s" x="622" y="120" text-anchor="middle">dead stock</text><text class="s" x="622" y="139" text-anchor="middle">projected shed</text>
<path class="l" d="M725 105 H780"/><rect class="o" x="780" y="64" width="178" height="82" rx="16"/><text class="t" x="869" y="93" text-anchor="middle">99-slot target</text><text class="s" x="869" y="117" text-anchor="middle">one slot reserved</text><text class="s" x="869" y="134" text-anchor="middle">value-aware release</text>
</svg></div>

## 2. Three public-state route checkpoints
<div class="kg-prose"><div class="lead">Each switch reads only the current observation. A tail is allowed only when it is identical to the active route on every earlier turn, preventing arbitrary mid-season splicing.</div></div>


## 3. A small repair layer protects useful work
<div class="kg-grid"><div class="kg-card green"><div class="eyebrow">Weed recovery</div><b>Reuse only a turn that would certainly be wasted.</b><span>If a unit stands on a weed and its taped action is a guaranteed no-op, it digs instead.</span></div><div class="kg-card teal"><div class="eyebrow">Sell hygiene</div><b>Do not spend scarce market slots on impossible orders.</b><span><code>clamp_sells</code> removes or shrinks sells the projected shed cannot fill.</span></div><div class="kg-card violet"><div class="eyebrow">Dead stock</div><b>Convert inventory the remaining route will never sell.</b><span>Surplus uses only spare market capacity and prices above the $1 floor.</span></div><div class="kg-card gold"><div class="eyebrow">One-slot reserve · added</div><b>Aim for 99 items at day close, not exactly 100.</b><span>Only the tiny projected excess is released. Products with no remaining planned sale are preferred, then the higher visible quote.</span></div></div>

## 4. Freeze the exact standalone agent
<div class="kg-prose"><div class="lead">The next cell writes the exact one-file agent used below, verifies its SHA-256, compiles it, and creates the submission archive. Runtime uses no network and no external Dataset.</div></div>


### Import boundary
<div class="kg-prose"><div class="lead">Before visualization, load the generated module exactly as a standalone submission file and verify the public <code>agent(obs)</code> entry point.</div></div>


## 5. Watch one exact 720-turn season
<div class="kg-prose"><div class="lead">The visual section runs the exact generated <code>main.py</code> in both seats. The animation and every chart below read only from that executed <code>env.steps</code>. This is a deterministic diagnostic season, not a leaderboard claim.</div><div class="micro">Seed 910019 is used only to make the visualization reproducible.</div></div>

## 6. Evidence board — one season, four views
<div class="kg-prose"><div class="lead">The same completed trajectory is read through workload, shared market movement, farm capacity, and action allocation. These views explain what the programmed route actually produced with the one-slot closeout reserve.</div></div>

## 7. Three trends expose the timing
<div class="kg-prose"><div class="lead">The overview compresses the season. These traces restore the day axis: workload, shared market quotes, then farm footprint and bank.</div></div>


## 8. Phase ledger — around the three route checkpoints
<div class="kg-prose"><div class="lead">Four descriptive windows align the workload with the public route checkpoints. The one-slot reserve changes only day-close market handling, not these route boundaries.</div></div>

## 9. Inside one turn: route first, bounded repair second
<div class="kg-terminal"><span class="dim">current observation</span><br>&nbsp;&nbsp;↓<br><b>prefix-safe public router</b> may select a continuation at steps 226 / 360 / 433<br>&nbsp;&nbsp;↓<br><b>stored route tape</b> emits the complete action<br>&nbsp;&nbsp;↓<br><span class="dim">weed recovery → projected shed → 99-slot value-aware guard → sell clamp → dead-stock sale</span><br>&nbsp;&nbsp;↓<br><b>return bounded action</b></div>
<div class="kg-caption">At hour 23 the guard compares projected day-close load with a target of 99. It sells only the small excess, protecting items that still have planned route sales before visible quote value breaks ties.</div>

## 10. What remains unchanged
<div class="kg-grid"><div class="kg-card green"><div class="eyebrow">Route programme</div><b>The stored action tapes remain the backbone.</b><span>Ordinary movement, planting, livestock care, harvesting, and planned trading still come from the same route family.</span></div><div class="kg-card teal"><div class="eyebrow">Decision surface</div><b>Only three visible checkpoints select tails.</b><span>Yarn Store presence, carrot price, and milk inventory are read directly from the observation; hidden seeds and future shops are not used.</span></div><div class="kg-card violet"><div class="eyebrow">Repair scope</div><b>Repairs remain local, not a second planner.</b><span>The controller does not search future states or rewrite the farm layout.</span></div><div class="kg-card gold"><div class="eyebrow">Small reserve</div><b>The closeout target is 99 rather than 100.</b><span>That is the only new threshold; item ranking and route logic stay unchanged.</span></div></div>

## 11. Submission boundary
<div class="kg-prose"><div class="lead">The visual cells are notebook-only diagnostics. The competition artifact remains a single standalone <code>main.py</code> inside <code>submission.tar.gz</code>.</div></div>


## Takeaways
<div class="kg-grid"><div class="kg-card green"><div class="eyebrow">Programme</div><b>Most of the season remains deliberately fixed.</b><span>Long route tapes carry the farm through ordinary work.</span></div><div class="kg-card teal"><div class="eyebrow">Adaptation</div><b>Three public checkpoints choose compatible futures.</b><span>The route switches remain explicit, observable, and prefix-safe.</span></div><div class="kg-card gold"><div class="eyebrow">One-slot reserve</div><b>The day-close guard deliberately leaves a tiny capacity cushion.</b><span>Only projected excess above 99 is released, using the same value-aware ranking.</span></div><div class="kg-card violet"><div class="eyebrow">Evidence</div><b>Animation, tables, and charts come from the same completed exact-agent run.</b><span>The notebook can be rerun top to bottom without external data.</span></div></div>