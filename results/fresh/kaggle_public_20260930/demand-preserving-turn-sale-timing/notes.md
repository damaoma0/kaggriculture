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
  content:"Strategy note";display:inline-block;margin-right:11px;padding:4px 9px;font-size:10px;font-weight:800;
  letter-spacing:.14em;text-transform:uppercase;color:#fff;background:linear-gradient(135deg,var(--green),#35a664);
  border-radius:999px;vertical-align:middle
}
code{background:rgba(102,129,112,.12)!important;padding:.12em .34em;border-radius:6px}
pre,.jp-OutputArea-output pre,.output_subarea pre{border:1px solid var(--line);border-radius:15px;padding:14px;background:#fbfdfb!important}
blockquote{border-left:4px solid var(--gold)!important;padding:12px 16px!important;border-radius:0 12px 12px 0;background:#fffaf0}
.kg-hero{position:relative;box-sizing:border-box;margin:6px 0 24px;padding:31px;border-radius:30px;overflow:hidden;
 background:radial-gradient(circle at 84% 12%,rgba(118,255,182,.25),transparent 23%),radial-gradient(circle at 73% 88%,rgba(63,196,255,.15),transparent 28%),linear-gradient(135deg,#07271d 0%,#103b30 43%,#123b4a 100%);
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
/* Force notebook tables into a light, high-contrast surface even when Kaggle/Jupyter uses dark mode. */
.jp-RenderedHTMLCommon table,.jp-OutputArea-output table,.output_html table,.rendered_html table,table.dataframe,.kgvt,.forest-table{background:#ffffff!important;color:#203a2c!important;border-color:#d6e3da!important;color-scheme:light!important}
.jp-RenderedHTMLCommon table thead,.jp-OutputArea-output table thead,.output_html table thead,.rendered_html table thead,table.dataframe thead,.kgvt thead,.forest-table thead{background:#edf5f0!important;color:#173322!important}
.jp-RenderedHTMLCommon table th,.jp-OutputArea-output table th,.output_html table th,.rendered_html table th,table.dataframe th,.kgvt th,.forest-table th{background:#edf5f0!important;color:#173322!important;border-color:#d6e3da!important}
.jp-RenderedHTMLCommon table tbody,.jp-RenderedHTMLCommon table tr,.jp-RenderedHTMLCommon table td,.jp-OutputArea-output table tbody,.jp-OutputArea-output table tr,.jp-OutputArea-output table td,.output_html table tbody,.output_html table tr,.output_html table td,.rendered_html table tbody,.rendered_html table tr,.rendered_html table td,table.dataframe tbody,table.dataframe tr,table.dataframe td,.kgvt tbody,.kgvt tr,.kgvt td,.forest-table tbody,.forest-table tr,.forest-table td{background:#ffffff!important;color:#203a2c!important;border-color:#e2ebe5!important}
.jp-RenderedHTMLCommon table tbody tr:nth-child(even) td,.jp-OutputArea-output table tbody tr:nth-child(even) td,.output_html table tbody tr:nth-child(even) td,.rendered_html table tbody tr:nth-child(even) td,table.dataframe tbody tr:nth-child(even) td,.kgvt tbody tr:nth-child(even) td,.forest-table tbody tr:nth-child(even) td{background:#f7faf8!important}
.jp-RenderedHTMLCommon table tbody tr:hover td,.jp-OutputArea-output table tbody tr:hover td,.output_html table tbody tr:hover td,.rendered_html table tbody tr:hover td,table.dataframe tbody tr:hover td,.kgvt tbody tr:hover td,.forest-table tbody tr:hover td{background:#edf7f1!important;color:#173322!important}
@media(max-width:920px){.kg-roadmap{grid-template-columns:repeat(2,minmax(0,1fr))}.kg-hero-grid{grid-template-columns:1fr}}
@media(max-width:700px){.kg-hero{padding:22px}.kg-hero h1{font-size:37px}.kg-roadmap,.kg-grid{grid-template-columns:1fr}.kg-stat-row{grid-template-columns:1fr 1fr 1fr}}
</style>

<div class="kg-hero"><div class="kg-hero-grid"><div>
<div class="kg-kicker">Kaggriculture · strongest measured search head</div>
<h1>Step1009 · Forty-first final fixed-sell closure</h1>
<p>One execution-grounded closure pass beyond the promoted Step1008 parent. The notebook reconstructs the exact promoted submission bytes, loads the production callable, and validates a complete 720-turn season while preserving the established visual shell.</p>
</div></div></div>


## Read the notebook in four passes
<div class="kg-roadmap"><div class="kg-road"><span class="n">01</span><span class="t">Keep the promoted production chassis</span><span class="d">Step1008 remains the exact parent, including the compact closure implementation and its measured residual passes.</span></div><div class="kg-road teal"><span class="n">02</span><span class="t">Apply one measured residual pass</span><span class="d">A single additional inventory-safe SELL/fixed-order reorder is applied after Step1008.</span></div><div class="kg-road gold"><span class="n">03</span><span class="t">Preserve safety boundaries</span><span class="d">No seed, seat, opponent, result-family, or future-state branch is introduced.</span></div><div class="kg-road violet"><span class="n">04</span><span class="t">Verify exact production bytes</span><span class="d">Reconstruct the deterministic archive, load its final callable, and run an exact 720-turn season.</span></div></div>


## 1. One residual closure pass after Step1008
<div class="kg-prose"><div class="lead">Step1009 starts from the exact promoted Step1008 policy and applies the established deterministic fixed-sell reorder exactly once more. Current-head traces showed real action residuals after Step1008, so this remains an execution-grounded policy extension rather than an automatic wrapper increment.</div></div>


## 2. Why the mechanism stays narrow
<div class="kg-prose"><div class="lead">The added pass uses the same inventory-safe closure already present in the accepted strategy. It changes no price threshold, product rule, quantity rule, seed condition, seat condition, opponent condition, result-family condition, or future-state branch; fixed non-SELL market orders remain protected.</div></div>


## 3. Promoted parent, one measured extension
<div class="kg-grid"><div class="kg-card green"><div class="eyebrow">Parent</div><b>The exact promoted Step1008 implementation remains intact.</b></div><div class="kg-card teal"><div class="eyebrow">Extension</div><b>One extra deterministic closure pass is applied only after Step1008 returns its action.</b></div></div>


## 4. Freeze the exact submission archive
<div class="kg-prose"><div class="lead">The next cell reconstructs the exact deterministic submission archive and verifies both archive and main.py SHA-256 identities before any game is run.</div></div>


### Production loader boundary
<div class="kg-prose"><div class="lead">Load the reconstructed source through Kaggle's callable loader and verify that the final callable is the promoted Step1009 production entrypoint.</div></div>


## 5. Watch one exact 720-turn production-path season
<div class="kg-prose"><div class="lead">Run the reconstructed submission as a file-path agent in the supplied Kaggriculture environment and require 720 states, final step 719, and DONE/DONE.</div></div>


## 6. Evidence board — one executed season, four views
<div class="kg-prose"><div class="lead">A single self-play run is a behavior and packaging audit, not a strength estimate. These views confirm that the frozen composite executes the full season and expose workload, market movement, capacity, and action mix without changing the agent.</div></div>

## 7. Three trends expose the timing
<div class="kg-prose"><div class="lead">The overview compresses the season. These traces restore the day-by-day rhythm: farm workload versus market orders, visible shared prices, and the relationship between farm capacity and bank.</div></div>

## 8. Phase ledger — six-day operating windows
<div class="kg-prose"><div class="lead">Six-day blocks provide a compact diagnostic view of workload and market activity. They are descriptive only; the controller still acts from the live observation on every turn.</div></div>

## 9. Inside the composite
<div class="kg-flow"><b>public observation</b><br>&nbsp;&nbsp;↓<br><b>accepted production strategy</b><br>&nbsp;&nbsp;↓<br><b>compact thirty-four-pass closure loop</b><br>&nbsp;&nbsp;↓<br><b>Step1003 residual closure pass</b><br>&nbsp;&nbsp;↓<br><b>Step1004 residual closure pass</b><br>&nbsp;&nbsp;↓<br><b>Step1005 residual closure pass</b><br>&nbsp;&nbsp;↓<br><b>Step1006 residual closure pass</b><br>&nbsp;&nbsp;↓<br><b>Step1007 residual closure pass</b><br>&nbsp;&nbsp;↓<br><b>Step1008 residual closure pass</b><br>&nbsp;&nbsp;↓<br><b>one additional Step1009 residual closure pass</b><br>&nbsp;&nbsp;↓<br><b>submission action</b></div>


## 10. What remains deliberately simple
<div class="kg-grid"><div class="kg-card green"><div class="eyebrow">Deterministic</div><b>No external service, hidden state, or runtime tuning is required.</b></div><div class="kg-card teal"><div class="eyebrow">Auditable</div><b>The notebook reconstructs and hashes the exact submitted bytes.</b></div></div>


## 11. Submission boundary
<div class="kg-prose"><div class="lead">Charts and animation are notebook-only diagnostics. The submission archive contains only the license, notice, and exact production main.py.</div></div>


## Takeaways
<div class="kg-grid"><div class="kg-card green"><div class="eyebrow">Production entrypoint</div><b>Step1009 loads directly from the reconstructed main.py: exact Step1008 parent semantics plus one execution-grounded final fixed-sell closure pass.</b></div><div class="kg-card teal"><div class="eyebrow">Validation</div><b>Exact archive identity, syntax, callable loading, and a complete 720-turn season are checked in-notebook.</b></div></div>
