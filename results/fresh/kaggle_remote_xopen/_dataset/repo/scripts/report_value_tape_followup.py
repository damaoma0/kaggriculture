"""Assemble the completed follow-up, with development/independent roles clear."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/value_tape_followup_20260923'


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def signed(n):return f'{n:+,.0f}'


def main():
    forecast=read(OUT/'modern_forecast_validation.json');old_forecast=read(OUT/'rival_forecast_validation.json')
    branch=read(OUT/'branch_risk/summary.json');live3=read(OUT/'v3_live/summary.json');live4=read(OUT/'v4_live/summary.json')
    historical=read(OUT/'v3_historical/summary.json')
    berry=read(OUT/'v4_historical/111262874-12.json');wool=read(OUT/'v4_historical/111269605-15.json')
    unchanged=read(OUT/'v4_historical/111287532-12.json')
    new=read(OUT/'v3_live/2867821829-0.json');trace=read(OUT/'selected_strawberry_recovery_trace.json')
    live_trace=read(OUT/'v3_live/2867821829-0.trace.json')
    audit=read(OUT/'false_positive-v3-audit.json')
    assert all(r['completed'] for r in (berry,wool,unchanged,new))
    assert live3['completed']==12 and live4['completed']==6 and historical['completed']==7
    assert trace['both_results_reproduced'] and live_trace['both_original_results_reproduced']
    baseline_sha=sha256((ROOT/'agents/mgt_m1.py').read_bytes()).hexdigest()
    assert baseline_sha=='1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470'
    selected=next(r for r in berry['decision']['candidates'] if r['route']==berry['selected'])
    lines=['# Tape matching follow-up — 23 September 2026','',
        '## Main result','',
        '**The corrected selector turns another historical loss into a win: −12,585 → +5,864, a recovery of 18,449.**',
        'Our own cash improves by **7,066**; rival cash falls by **11,383**. The earlier **10,034** wool recovery remains selected.',
        '',
        'These named historical cases are **development evidence**. Separate frozen live tests produced one new **+3,783** improvement in twelve V3 pairs; eleven stayed unchanged. Six further V4 pairs all stayed unchanged. This is a small confirmation sample, not proof of broad superiority.',
        '',
        '## What changed','',
        '1. **Forecast rival sales from the appropriate family of farms.** The original model extrapolated currently occupied plots and sold daily output at hour 1. The first replacement, trained on older UMG games, improved on that older population but still mispriced modern opponents. The final model retrieves from 75 older plus 40 modern verified training games, using public tile types, birth dates, held yield and care state. Twenty modern test games and all nineteen earlier target cases are excluded.',
        '2. **Include delivery timing and future planting.** Use successful donor transactions at their observed hours, update projected rival boards daily, and correct quantities for differences between visible cohorts using official tile mechanics. Donor future shops are compared with sampled scenario shops, never the target’s actual future.',
        '3. **Use eight shop futures.** At each unknown reveal every shop type occurs once across the eight scenarios. Duplicate shops within a world remain possible. These are paired worlds shared by all candidates.',
        '4. **Complete balanced evaluation before cash admission.** V3 screened on our expected cash after only the first four worlds. That prematurely discarded the 18,449 opportunity. V4 uses the first four for margin ranking, then applies cash and downside admission after all eight.',
        '5. **Protect existing cohorts and price the transition.** Continue the actual native executor through the official engine, accounting for seeds, animals, feed, fertilizer, wages, sales and market effects. Protect starting long crops/animals that the native baseline would retain at the next reveal; reject extra failed hires. Commit only until that next reveal.',
        '',
        'The existing native agent is unchanged. These are research selectors, not a competition-time-budget implementation.',
        '',
        '## Exact picking procedure','',
        '- Start with native adaptive continuation, the incumbent tape, and the native reveal-time choice. Fill a maximum-seven shortlist with two new candidates at each board-Hamming limit 8, 14 and 24, ordered by revealed-demand distance then Hamming distance. The cap may cut off later additions.',
        '- For each sampled world, rank rival training farms by public physical/cohort distance plus 0.6 times revealed-shop distance. Among the nearest twelve, use 0.25 times sampled-future-shop distance and rotate among the best three to represent different continuations.',
        '- Run four full-season projections for each candidate. V4 advances the best two candidates with positive risk-adjusted margin and no cohort/hire protection failure, plus native control, to eight projections.',
        '- Score = mean projected margin gain − 0.5 × population standard deviation. Require score > 350 and mean own-cash gain > 0. Maximum forecast setback must be no worse than max(500, 25% of mean margin gain). The 25% risk budget is a declared research setting, not a guarantee.',
        '- Choose the highest-scoring admitted route; otherwise retain native. Route zero is valid. Force the chosen route for three days, then restore native routing.',
        '',
        '**The 18,449 recovery also passes the original fixed 500 downside limit. It does not depend on the relaxed risk budget.** Its smallest projected margin gain is +1,208.',
        '',
        '## Rival forecast validation','',
        'Mean absolute error in cumulative net sold units per product, measured at day 15 on twenty excluded modern games:',
        '',
        '| Horizon | Original cohort extrapolation | Older-only retrieval | Mixed-family retrieval |',
        '|---|---:|---:|---:|']
    for s in forecast['summary']:
        lines.append(f"| {s['horizon']} days | {s['mae']['v1']:.2f} | {s['mae']['v2']:.2f} | {s['mae']['v3']:.2f} |")
    lines.extend(['',
        'That is **84% lower error over three days, 72% over six, and 62% through season end**, relative to the original extrapolation. Production/sales forecast accuracy is separate from policy profit.',
        '',
        'The older-only model had reduced end-of-season error from 57.66 to 25.09 on thirty excluded older games, but worsened modern-game error from 32.49 to 36.43. This exposed a population mismatch; adding the modern training sample corrected it.',
        '',
        '## Large strawberry recovery: episode 111262874, day 12','',
        'Revealed shops: **Ice Cream, Yarn, Pet Cafe, Brunch**. Future actual shops were not supplied to the selector.',
        'The chosen donor is **110025609, route 184**. Its current board has Hamming distance zero, but its future production choices differ substantially.',
        '',
        '| Metric | Native | Selected continuation | Change |',
        '|---|---:|---:|---:|'])
    for key,label in [('cash','Our cash'),('rival_cash','Rival cash'),('margin','Our margin')]:
        a,b=berry['baseline'][key],berry['candidate'][key];lines.append(f'| {label} | {a:,.0f} | {b:,.0f} | {signed(b-a)} |')
    lines.extend(['',
        'Semantic changes observed in successful engine actions:',
        '',
        '- On day 12, plant **eight strawberries instead of two**, and **two tomatoes instead of seven**; buy a cow. Other rotations also change later.',
        '- Avoid the native plan’s two sheep purchases on days 15 and 16.',
        '- All starting cohorts that the actual native continuation retained at the day-15 boundary also survive in the selected continuation.',
        '- Through season end: **+97 strawberry, +25 milk, +24 carrot**, with **−82 wool and −28 tomato** produced/sold. Wages fall by 432.',
        '',
        'Our revenue rises **5,541**, and total spending falls **1,525**, reconciling to **+7,066 cash**.',
        '',
        '| Own revenue change | Amount |','|---|---:|'])
    a,b=berry['baseline']['economics'],berry['candidate']['economics']
    for p in ('STRAWBERRY','MILK','CARROT','WOOL','TOMATO','WHEAT','FERTILIZER','EGG'):
        lines.append(f"| {p.title()} | {signed(b['revenue'].get(p,0)-a['revenue'].get(p,0))} |")
    lines.extend(['',
        'Rival quantities sold remain unchanged in this recorded-action counterfactual. Lower strawberry and milk prices cut rival revenue by **10,424** and **2,102**, partially offset by other goods. Rival revenue falls 11,040 and spending rises 343, giving **−11,383 cash**. This is why competitive recovery is much larger than our own cash gain.',
        '',
        'Projected margin gains across eight public-only worlds: '+', '.join(signed(x) for x in selected['margin_deltas'])+'.',
        'Projected own-cash gains: '+', '.join(signed(x) for x in selected['cash_deltas'])+'.',
        'The first four average −968.5 cash; all eight average +714. This explains the old premature-screening veto. The full-world margin score is +5,572.',
        '',
        'This route’s historical outcome was known from earlier counterfactual exploration. The new selection is public-only, but the case is therefore explicitly retrospective development evidence.',
        '',
        '## New independent live improvement','',
        'Seed **2867821829**, seat 0, day 12, donor **109863155 / route 136**:',
        '',
        '| Metric | Native | Selected | Change |','|---|---:|---:|---:|'])
    for key,label in [('cash','Our cash'),('rival_cash','Rival cash'),('margin','Our margin')]:
        a,b=new['baseline'][key],new['candidate'][key];lines.append(f'| {label} | {a:,.0f} | {b:,.0f} | {signed(b-a)} |')
    lines.extend(['',
        'A responsive V56 plays both sides of the counterfactual. Shops are fixed identically and both prefixes reproduce. The chosen tape buys one additional sheep on day 14. Successful postdecision work changes by **+53 feeds, +51 care actions, −39 waterings and −24 fertilizer applications**.',
        'Production increases **22 wool, 49 eggs, 20 milk**, while carrot, tomato and strawberry output decrease. Revenue rises 3,624 and spending falls 1,146; rival cash rises 987. Thus our own +4,770 becomes a competitive **+3,783**.',
        '',
        'V4 has exactly the same two finalists as V3 at this checkpoint (routes 136 and 137); its screening correction does not remove this selected candidate. This is an equivalence check using the saved forecasts, not a second independent live success.',
        '',
        '## What happened to the earlier false positive?','',
        'The previously chosen route 196 lost **2,456** under its original actual shop sequence. Across sixteen independently sampled continuations of the same checkpoint, it gains only **152.375 on average**, with **nine improvements, seven regressions**, a minimum of −2,456 and maximum +2,749. The earlier +3,000 model expectation was overconfident.',
        'With mixed-family rival forecasts, this candidate’s eight projected margin changes are '+', '.join(signed(x) for x in audit['margin_deltas'])+'.',
        'It now fails the existing downside admission check (−681 versus a 500 budget). This is a diagnostic rejection of that candidate; it does not establish that every future loss is preventable.',
        '',
        '## Complete panel accounting','',
        '| Panel | Role | Pairs | Switches | Mean margin change | Improved / worse / unchanged |',
        '|---|---|---:|---:|---:|---|'])
    for label,role,s in [('V3 seven historical cases','Development',historical),('V3 new live worlds','Independent frozen panel',live3),('V4 new live worlds','Independent frozen panel',live4)]:
        lines.append(f"| {label} | {role} | {s['completed']} | {s['changed']} | {signed(s['mean'])} | {s['positive']} / {s['negative']} / {s['completed']-s['positive']-s['negative']} |")
    lines.extend(['| V4 three named historical cases | Development | 3 | 2 | +9,494 | 2 / 0 / 1 |','',
        'V4 selected the +18,449 strawberry recovery and retained +10,034 wool; it made no change in episode 111287532. The two live versions ran on different seeds, so their panel means are not a paired comparison between versions.',
        '',
        'All fresh live outcomes:',
        '',
        '| Version | Seed / seat | Reveal day | Route | Baseline margin | Margin change | Own cash change |',
        '|---|---|---:|---:|---:|---:|---:|'])
    runtimes=[]
    for version,summary in [('v3',live3),('v4',live4)]:
        for short in sorted(summary['rows'],key=lambda r:r['spec']['seed']):
            spec=short['spec'];r=read(OUT/f'{version}_live'/f"{spec['seed']}-{spec['seat']}.json")
            assert r['completed'] and r['baseline']['ledger_verified'] and r['candidate']['ledger_verified']
            assert r['baseline']['prefix_sha256']==r['candidate']['prefix_sha256']
            runtimes.append(r['decision']['seconds'])
            lines.append(f"| {version.upper()} | {spec['seed']} / {spec['seat']} | {spec['day']} | {r['selected'] if r['selected'] is not None else 'native'} | {r['baseline']['margin']:,.0f} | {signed(r['margin_delta'])} | {signed(r['cash_delta'])} |")
    lines.extend(['',
        '## Verification and limits','',
        '- Five regression tests pass: excluded-data membership; public-only deterministic input handling without mutation; shop scenario marginals/prefixes; complete V1/V2 rollout equivalence under the same rival world; and the actual saved-forecast regression for postponing cash admission until all eight worlds.',
        '- All 105 older and 60 modern library replays match recorded final cash and reconcile ledgers. All completed historical controls reproduce their recorded results; all 18 fresh live pairs have equal prefixes, fixed paired shops, complete seasons and reconciled ledgers. Both highlighted traces independently reproduce their original outcomes.',
        '- The original `agents/mgt_m1.py` hash remains `'+baseline_sha+'`.',
        f'- Live selector time was **{min(runtimes):.0f}–{max(runtimes):.0f} seconds per decision** under concurrent workloads. This is substantially beyond the competition action budget.',
        '- Rival flow/board forecasts are sampled continuations. They do not reproduce the rival’s full price-responsive policy. Eight future-shop worlds only sparsely cover joint shop sequences. The useful gain is established in specific cases, not uniformly over opponents or worlds.',
        '- Named historical cases informed development. Six independent V4 tests made no switches, so they do not independently confirm the screening fix’s performance on a changed decision.',
        '- One reveal-time intervention was tested per live game. Repeated closed-loop decisions and an inexpensive competition implementation remain future work.',
        '- Cross-process forecast-cache reuse was refused because native memory includes process-local tape identities. The three V4 historical cases were rerun with fresh forecasts; hash checks were not bypassed.',
        '',
        '## Files','',
        '- Latest selector: `scripts/value_tape_search_v4.py` (uses V3 assessment and the V2 official-engine rollout).',
        '- Rival model: `scripts/rival_trajectory_model_v3.py`; immutable training membership in both library manifests.',
        '- Independent panels: `results/fresh/value_tape_followup_20260923/v3_live/` and `v4_live/`, including designs, source snapshots and all outcomes.',
        '- Detailed recovery trace: `selected_strawberry_recovery_trace.json`.',
        '- New independent gain trace: `v3_live/2867821829-0.trace.json`.',
        '- Tests: `tests/test_value_tape_followup.py`.',
        ''])
    report=ROOT/'docs/value_tape_followup_20260923.md';report.write_text('\n'.join(lines),encoding='utf-8')
    manifest=dict(report=str(report),baseline_sha256=baseline_sha,
        main_result=dict(episode=111262874,day=12,route=184,margin_delta=18449,cash_delta=7066,rival_delta=-11383),
        fresh_v3=live3,fresh_v4=live4,selector_seconds_range=[min(runtimes),max(runtimes)],
        sources={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in [ROOT/'scripts/value_tape_search_v4.py',ROOT/'scripts/value_tape_search_v3.py',ROOT/'scripts/value_tape_search_v2.py',ROOT/'scripts/rival_trajectory_model_v3.py',ROOT/'scripts/rival_trajectory_model.py',ROOT/'tests/test_value_tape_followup.py']})
    (OUT/'summary.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(dict(report=str(report),main_result=manifest['main_result'],live_v3=live3['mean'],live_v4=live4['mean'],runtime=manifest['selector_seconds_range']),indent=2))


if __name__=='__main__':main()
