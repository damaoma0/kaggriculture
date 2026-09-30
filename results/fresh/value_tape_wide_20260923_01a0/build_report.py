"""Make the human-readable report from audited panel artifacts."""
from pathlib import Path
import json
import statistics
from collections import Counter

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]

def n(value):
    return f'{value:,.0f}'

def signed(value):
    return f'{value:+,.0f}'

def main():
    s=json.loads((OUT/'summary.json').read_text())
    anchor_path=OUT/'anchor_summary.json'
    anchor=json.loads(anchor_path.read_text()) if anchor_path.exists() else None
    rd=json.loads((OUT/'recording_design.json').read_text())
    date=json.loads((OUT/'leaderboard_snapshot.json').read_text())['fetched_utc']
    lines=['# Wider V9 tape-selector evaluation — 2026-09-23','',
        f'**Status: {s["completed_pairs"]}/96 paired matchups complete.** '+
        ('The prespecified panel is finished.' if s['complete'] else 'Partial results; do not treat these as the final panel.')+
        (f' Additional exact-control follow-up: {anchor["completed"]}/{anchor["planned"]} pairs.' if anchor else ''),'',
        'The candidate is unchanged V9. The control is original `mgt_m1`. V9 reconsiders at days 12, 15 and 18, '
        'commits an admitted route for three days, then resumes native routing. The production agent was not changed or submitted.','',
        '## Results','',
        'Margin means our final cash minus the opponent’s final cash. All deltas below compare V9 with the original m1 control in the same world.','',
        '| Opponent panel | Pairs | Better / worse / same | Mean margin change | Mean own cash change | Control → candidate wins |',
        '|---|---:|---:|---:|---:|---:|']
    for label,key in [('Live V56','v56'),('Live original m1','original_m1')]:
        r=s['live_by_opponent'][key]
        if r['n']:
            lines.append(f'| {label} | {r["n"]} | {r["improved"]} / {r["regressed"]} / {r["unchanged"]} | '
                f'{signed(r["mean_margin"])} | {signed(r["mean_own_cash"])} | {r["baseline_wins"]} → {r["candidate_wins"]} |')
    for label,key in [('Rated recordings without major playback failure','replay_without_material_command_break'),
                      ('All rated recordings, including broken playback (diagnostic)','replay_all')]:
        r=s[key]
        if r['n']:
            lines.append(f'| {label} | {r["n"]} | {r["improved"]} / {r["regressed"]} / {r["unchanged"]} | '
                f'{signed(r["mean_margin"])} | {signed(r["mean_own_cash"])} | {r["baseline_wins"]} → {r["candidate_wins"]} |')
    if anchor and anchor['stats']['n']:
        r=anchor['stats']
        lines.append(f'| Additional original-m1 recordings, exact native control | {r["n"]} | {r["improved"]} / {r["regressed"]} / {r["unchanged"]} | '
            f'{signed(r["mean_margin"])} | {signed(r["mean_own_cash"])} | {r["baseline_wins"]} → {r["candidate_wins"]} |')
    lines+=['','The recorded-opponent rows measure frozen-action counterfactuals, not live-policy win rates. '
        f'**{s["replay_material_command_breaks"]}/32 playbacks materially failed after their original rival was replaced.** '
        'Their inflated margins cannot support opponent-strength claims. All cases are retained for transparency; '
        'the subset without major failures is still subject to the opponent’s inability to react.','',
        '## Design and fidelity','',
        '- 32 fresh IID worlds, each crossed with live V56 and live original m1: 64 pairs. Sixteen worlds use each seat. '
        'Each world independently samples eight shops uniformly; both arms see the same seed and shop sequence. '
        'This removes the engine’s policy-dependent shop-RNG drift. The same world against two opponents is counted once for uncertainty.',
        '- 32 recordings from eight active opponent submissions rated 2750–3000 at fetch time: four recordings per opponent, '
        'two in each opponent seat. Two teams were randomly sampled within each 62.5-point rating stratum. '
        'No win/loss filtering was used. All 115 rival-model training episodes were excluded.',
        '- The baseline and candidate each start from day 0. The selector receives only the current public observation and its own memory; '
        'the seed, actual future shops, opponent identity and recorded future actions are held by the evaluation harness.',
        '- All 151 frozen source/data dependencies are hashed. Each arm starts in a fresh process. '
        'Original m1 opponents have independent globals and player memory. V56 uses its verified `e410_agent` entry point.',
        f'- **{s["exact_recorded_reproductions"]}/{s["recorded_reproductions"]} recordings reproduce exactly:** final cash and both full observations '
        'at day boundaries and the final state, excluding the framework’s timing/step metadata. The shared market, private inventories and farms all match.',
        '- Every evaluated arm must finish all 719 actions, reach DONE in both seats and reconcile its complete cash ledger. '
        'The paired action prefix before day 12 must match exactly. No-intervention games must match all actions and both cash results.',
        '- Recorded-opponent counterfactuals preserve that opponent’s recorded weed spawns and actions. '
        'The opponent cannot react to new prices or our actions. Board divergence and extra ineffective commands are recorded; '
        'more than 40 extra failed commands is the prespecified material-break flag. All cases remain in the full result.','',
        '### Rated opponent submissions','',f'Leaderboard snapshot: `{date}`. Scores below are the selected submission’s score when its public metadata was fetched.','',
        '| Opponent | Submission | Rating | Recordings |','|---|---:|---:|---:|']
    for t in rd['selected']:
        lines.append(f'| {t["team"]["team"]} | {t["submission"]["id"]} | {t["submission"]["score"]:.1f} | {len(t["episodes"])} |')
    if anchor:
        lines+=['','### Exact-control follow-up','',
            'The initial replay panel exposed early opening collapses when the original rival was replaced. '
            'We therefore froze an additional panel from games actually played by original m1 (`56395605`). '
            'The current public metadata supplied ten qualifying episodes across six opponents, rated 2752.7–2804.4; '
            'all ten were included without selecting by reward. This is a follow-up diagnostic, separately reported from the prespecified panel.','',
            f'**{anchor["exact_native_controls"]}/{anchor["planned"]} native controls match the actual recording:** both final cash values, '
            'both physical boards at all 719 action boundaries and both private inventory states. '
            'A candidate is run only after that exact-control gate passes. '
            f'After intervention, {anchor["additional_major_playback_failures"]} cases have a major opponent-playback failure '
            f'and {anchor["candidate_board_divergences"]} have any opponent board divergence. '
            'The opponent still cannot react to our altered sales; full reactive-policy validation remains a separate task.','',
            '| Episode | Opponent | Rating | Original margin | V9 margin | Change |',
            '|---|---|---:|---:|---:|---:|']
        for r in anchor['rows']:
            lines.append(f'| {r["spec"]["episode"]} | {r["spec"]["opponent"]} | {r["spec"]["rating"]:.1f} | '
                f'{n(r["baseline_margin"])} | {n(r["candidate_margin"])} | {signed(r["margin_delta"])} |')
    lines+=['','## Coverage and uncertainty','']
    coverage=[('Live panel',s['live']),('Recorded panel, no major playback failure',s['replay_without_material_command_break'])]
    if anchor:coverage.append(('Exact-control follow-up',anchor['stats']))
    for label,r in coverage:
        if not r['n']:continue
        ci=r.get('margin_95pct_cluster_bootstrap')
        ci_text='' if ci is None else f' Mean-margin 95% cluster bootstrap interval: {signed(ci[0])} to {signed(ci[1])}.'
        cluster='world' if label=='Live panel' else 'opponent team'
        lines.append(f'- **{label}:** intervened in {r["interventions"]}/{r["n"]} games; '
            f'{r["multiple_interventions"]} games contain more than one intervention. '
            f'{r["baseline_losses_improved"]}/{r["baseline_losses"]} original losses improved; '
            f'{r["baseline_losses_worse"]} became worse. {r["losses_to_wins"]} losses became wins; '
            f'{r["wins_to_losses"]} wins became losses. Net deficit recovered among the original losses: '
            f'{signed(r["net_deficit_recovered"])} of {n(r["baseline_loss_deficit"])}.'+ci_text+f' Resampling unit: {cluster}. '
            f'Intervention types: `{r["intervention_types"]}`.')
    if s['replay_all']['n']:
        clean=s['replay_without_material_command_break']
        lines.append(f'- Recorded opponents: {s["replay_material_command_breaks"]}/{s["replay_all"]["n"]} have a material command break '
            f'in either arm; {s["replay_any_board_divergence"]} have some physical-board divergence. '
            f'The subset without a material command break contains {clean["n"]} pairs'+
            (f', with mean margin change {signed(clean["mean_margin"])}.' if clean['n'] else '.'))
    lines+=['','### Search coverage','',
        f'Accepted commitments by day: `{s["selected_by_day"]}`. Search counts: `{s["search_counts"]}`.','',
        'Candidate exclusions are diagnostic, not evidence that a profitable repair does not exist:','',
        '| Exit point | Candidate routes |','|---|---:|']
    for key,value in s['search_exclusions'].items():lines.append(f'| {key.replace("_"," ")} | {value} |')
    lines+=['','V9 still examines at most seven continuations, expands at most two, and checks eight sampled futures. '
        'It cannot synthesize an arbitrary crop/animal plan, and it does not reconsider at days 21 or 24. '
        'A no-switch loss can reflect omitted candidates, conservative gates, an inaccurate opponent forecast, '
        'or a useful plan missing from the library. This panel does not prove which cause applies without a follow-up search.','',
        '## Largest gains and regressions','',
        '| Case | Original margin | V9 margin | Change | Own cash change | Selected D12 / D15 / D18 | Major playback failure |',
        '|---|---:|---:|---:|---:|---|---|']
    all_rows=[json.loads(p.read_text()) for p in (OUT/'pairs').glob('*.json')]
    usable=[r for r in all_rows if r['completed'] and (r['spec']['kind']=='live' or
        not any(r[k]['material_command_break'] for k in ('baseline_divergence','candidate_divergence')))]
    shown=sorted([r for r in usable if r['margin_delta']>0],key=lambda r:-r['margin_delta'])[:5]+s['worst_regressions'][:5]
    for r in shown:
        broken=r['spec']['kind']=='replay' and any(r[k]['material_command_break'] for k in ('baseline_divergence','candidate_divergence'))
        lines.append(f'| {r["spec"]["id"]} | {n(r["baseline_margin"])} | {n(r["candidate_margin"])} | '
            f'{signed(r["margin_delta"])} | {signed(r["cash_delta"])} | `{r["selected"]}` | {"YES" if broken else "No"} |')
    for r in shown:
        case=r['spec']['id'];seat=r['spec']['seat']
        b=json.loads((OUT/'arms'/f'{case}-baseline.json').read_text())
        c=json.loads((OUT/'arms'/f'{case}-candidate.json').read_text())
        rev={p:c['economics'][seat]['revenue'].get(p,0)-b['economics'][seat]['revenue'].get(p,0)
             for p in set(c['economics'][seat]['revenue'])|set(b['economics'][seat]['revenue'])}
        top=sorted(rev.items(),key=lambda x:abs(x[1]),reverse=True)[:4]
        spend=sum(c['economics'][seat]['spend'].values())-sum(b['economics'][seat]['spend'].values())
        lines+=['',f'**{case}:** sales revenue changes '+', '.join(f'{p.lower()} {signed(v)}' for p,v in top)+
            f'; total spending change {signed(spend)}; rival cash change {signed(r["rival_delta"])}.']
    lines+=['','### Largest untouched original losses','',
        '| Case | Original margin | V9 change |','|---|---:|---:|']
    unresolved=sorted([r for r in usable if r['baseline_margin']<0 and r['margin_delta']==0],key=lambda r:r['baseline_margin'])
    for r in unresolved[:8]:lines.append(f'| {r["spec"]["id"]} | {n(r["baseline_margin"])} | 0 |')
    t=s['time']
    lines+=['','## Local timing','',
        f'Tested on the shared laptop, one search game at a time. {t["reveal_calls"]} measured reveal calls: '
        f'mean {t["mean_reveal"]:.2f}s, 95th percentile {t["p95_reveal"]:.2f}s, maximum {t["max_reveal"]:.2f}s. '
        f'Maximum observed worker RSS {t["max_rss_gib"]:.2f} GiB.','',
        'Each own action is charged together with search; planner imports and own-agent initialization are charged to the first action. '
        'The bank starts at 60 seconds and loses max(0, action duration − 1 second). The evaluation framework setup is excluded. '
        'Timing-bank exhaustion does not stop these research games: profitability and timing feasibility are separate outputs. '
        'This is not the competition’s sandbox or hardware, and serialization/process overhead is not fully emulated.','']
    for label,r in [('Live',s['live']),('Recorded',s['replay_all'])]:
        if r['n']:lines.append(f'- {label}: {r["measured_candidate_time_bank_failures"]}/{r["n"]} candidate games exhausted the measured bank; '
            f'minimum remaining bank {r["minimum_candidate_time_bank"]:.2f}s.')
    if anchor and anchor['stats']['n']:
        r=anchor['stats'];lines.append(f'- Exact-control follow-up: {r["measured_candidate_time_bank_failures"]}/{r["n"]} '
            f'candidate bank exhaustions; minimum remaining bank {r["minimum_candidate_time_bank"]:.2f}s.')
    lines+=['','## Reproduce and inspect','',
        'Artifacts: `results/fresh/value_tape_wide_20260923_01a0/`.','',
        '- `random_design.json`, `recording_design.json`: outcome-blind sampling and protocol.',
        '- `panel_manifest.json`, `source_manifest.json`, `payload/`: hashes and frozen executable sources.',
        '- `recordings/`, `api_metadata/`: fetched exact actions, observation checkpoints and specific-submission ratings.',
        '- `pairs/`: compact paired results; `arms/`: per-arm ledgers, timing, physical commands and replay validity.',
        '- `decisions/`: every candidate, forecast, risk score and rejection; `actions/`: complete action tapes.',
        '- `summary.json`: aggregated results, cluster intervals and complete unresolved-loss list.','',
        '```powershell',
        '$env:PYTHONPATH="$PWD/.venv/Lib/site-packages"',
        '$python="C:/Users/xyygl/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"',
        '& $python results/fresh/value_tape_wide_20260923_01a0/run_panel.py --kind all',
        '& $python results/fresh/value_tape_wide_20260923_01a0/summarize.py',
        '& $python results/fresh/value_tape_wide_20260923_01a0/build_report.py',
        '```','',
        'The runner resumes existing results and stops for insufficient RAM. Delete no completed evidence when rerunning; use a separate output directory for a changed policy.']
    path=ROOT/'docs/value_tape_wide_20260923.md'
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(str(path))

if __name__=='__main__':main()
