"""Write a reviewable report from finished panels and their frozen manifests."""
import json
from pathlib import Path
from hashlib import sha256
from summarize_rotation_experiments import summarize

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/rotation_experiments'
LABELS={'mgt_m1':'Unchanged mgt_m1','mgt_exp_dsm':'DSM tape library',
        'mgt_exp_cohort':'Age-aware UMG routing','mgt_exp_rotate':'Two tomato rotations',
        'mgt_exp_hold':'Hold the selected tape (control)'}


def number(x):
    return f'{x:+,.1f}'


def table(s):
    lines=['| Approach | Games | W / T / L vs V56 | Mean margin | Change vs mgt_m1 | Own cash change |',
           '|---|---:|---:|---:|---:|---:|']
    for name,r in s['arms'].items():
        lines.append(f"| {LABELS[name]} | {r['completed']} | {r['wins']} / {r['ties']} / {r['losses']} | {number(r['mean_margin'])} | {number(r.get('mean_paired_margin_delta',0))} | {number(r.get('mean_paired_cash_delta',0))} |")
    return lines


def main():
    design=json.loads((OUT/'design.json').read_text())
    selection=json.loads((OUT/'selection.json').read_text())
    stages={stage:summarize(stage) for stage in ('smoke','development','validation','direct') if (OUT/stage/'manifest.json').exists()}
    for stage,s in stages.items():
        assert s['present']==s['expected']==s['completed'],f'Incomplete {stage}'
        manifest=json.loads((OUT/stage/'manifest.json').read_text())
        seen=set()
        for p in (OUT/stage/'games').glob('*.json'):
            g=json.loads(p.read_text(encoding='utf-8'))
            identity=(g['agent'],g['opponent'],g['seed'],g['seat'])
            assert identity not in seen
            seen.add(identity)
            assert g['seed'] in manifest['seeds'] and g['seat'] in manifest['seats']
            assert g['own_sha256']==manifest['source_hashes'][g['agent']]
            assert g['opponent_sha256']==manifest['source_hashes'][g['opponent']]
            assert g['completed'] and not g['errors'] and g['ledger_verified']
            assert g['states']==720 and g['actions']==719 and g['statuses']==['DONE','DONE']
            assert g['timing']['own']['calls']==g['timing']['opponent']['calls']==719
            assert not g['agent_reports']['own'].get('_MGT_REPORT',{}).get('router_errors',0)
            assert not g['agent_reports']['own'].get('_ROT_REPORT',{}).get('errors',0)
        for name,relative in manifest['source_paths'].items():
            assert sha256((ROOT/relative).read_bytes()).hexdigest()==manifest['source_hashes'][name]
    development=stages['development'];chosen=selection['candidate'];promising=False
    if chosen:
        assert 'validation' in stages and 'direct' in stages
        val=stages['validation']['arms'][chosen];direct=stages['direct']['arms'][chosen]
        promising=(val['margin_delta_seed_bootstrap_95'][0]>0 and val['mean_paired_cash_delta']>0
                   and direct['mean_margin']>0 and not val['runtime_errors'] and not direct['runtime_errors']
                   and not val['actions_over_1s'] and not direct['actions_over_1s'])
    assert sha256((ROOT/'agents/mgt_m1.py').read_bytes()).hexdigest()==design['build']['baseline_sha256']
    lines=['# DSM / UMG tape experiments on fresh random seeds','',
           '**Measured improvement found on this holdout; broader qualification remains separate.**' if promising else '**No reliable improvement established. Keep mgt_m1.**','',
           'The experiment tested three changes and a routing control. The baseline file was not edited, and no submission was made.','',
           '## Design','',
           '- Two random diagnostic seeds (both seats), followed by 12 development seeds (both seats). Five agents against the frozen V56 opponent: 20 diagnostic games and 120 development games.',
           '- A separate 32-seed validation set was sampled before any game outcomes. The highest positive development mean margin improvement selects one candidate; that candidate is evaluated unchanged against V56 with a same-seed m1 control, and directly against m1, both seats.',
           '- Complete 30-day games: 719 actions and 720 states. Natural engine RNG, active opponents, no forced shops, no extra starting cash, and reconciled cash ledgers.',
           '- Bootstrap intervals resample entire seeds, retaining both seats together (12,000 resamples). Seats are not treated as independent worlds.',
           '- New seeds were checked against 514 saved seed/experiment manifests: no overlap. The reserved qualification block was not used.',
           '- Same initial seed does not guarantee the same eventual shops: policy-dependent weed draws consume the shared RNG. The results estimate competitive performance under natural RNG, not a fixed-shop causal crop effect.','',
           '## Approaches','',
           '1. **DSM library:** replace the 584-tape UMG library with 108 complete DSM calendars, retaining the m1 execution and repair layers. Begin with a DSM opening and route within DSM; no late UMG-to-DSM coordinate splice.',
           '2. **Age-aware UMG selection:** retain all 584 tapes and add 0.35 per day of same-type cohort age mismatch, capped at four days per tile, to the routing score. Historical donor ages come from establishment actions; runtime queries use only the current farm.',
           '3. **Tomato rotations:** replace at most two native wheat plantings during days 12–18. Reserve native visits for watering, age-11 harvest, cleanup, and retain the route through the commitments. No added moves or hires. Seed purchases and lost native production are charged by the engine; supplemental sales require tracked delivery.',
           '4. **Hold control:** make the same commitment selection and retain the route, leaving native crops and market actions unchanged. This separates the routing restriction from crop substitution. It is adaptive, so later eligibility can differ once farms diverge.','',
           'These are bounded prototypes, not a general whole-farm continuation planner.','',
           '## Development results','']+table(development)
    lines+=['','Positive changes mean a larger final cash margin against V56 than m1 obtained on the same initial seed and seat.','']
    rotation=development['arms']['mgt_exp_rotate'];cohort=development['arms']['mgt_exp_cohort']
    lines += [f"The age-aware selector changed actions in {cohort['completed']-cohort['unchanged_action_games']}/{cohort['completed']} games. Its {number(cohort['mean_paired_margin_delta'])} gain came from {cohort['better_seeds']}/12 improved seeds; {cohort['equal_seeds']} were unchanged.",'',
              f"The rotations established and harvested {rotation['events'].get('plant_confirmed',0)} crops, yielding {rotation['event_units'].get('harvest_confirmed',0)} confirmed tomato units. Tracked delivery confirmed {rotation['event_units'].get('delivered',0)} units; not every harvested unit became separately credited delivery. Mean own cash fell {abs(rotation['mean_paired_cash_delta']):,.1f}.",'',
              f"Relative to the hold control, rotations changed mean margin by {number(development['rotation_vs_hold']['mean_margin_delta'])} (seed-bootstrap 95% interval {' to '.join(number(x) for x in development['rotation_vs_hold']['seed_bootstrap_95'])}).",'']
    if chosen:
        lines+=['## Independent validation','',f"Selected before inspecting validation outcomes: **{LABELS[chosen]}**.",'']+table(stages['validation'])
        ci=val['margin_delta_seed_bootstrap_95']
        lines+=['',f"Held-out paired margin improvement: **{number(val['mean_paired_margin_delta'])}**, 95% seed-bootstrap interval **{number(ci[0])} to {number(ci[1])}**. Better / unchanged / worse seeds: {val['better_seeds']} / {val['equal_seeds']} / {val['worse_seeds']}.",'',
                f"Directly against mgt_m1: **{direct['wins']} wins / {direct['ties']} ties / {direct['losses']} losses**, mean margin **{number(direct['mean_margin'])}**, 95% seed-bootstrap interval {' to '.join(number(x) for x in direct['mean_margin_seed_bootstrap_95'])}.",'',
                f"Only {val['same_shop_games']}/{val['completed']} candidate-versus-V56 games retained the control's full shop sequence. {val['unchanged_action_games']}/{val['completed']} action streams were identical to the control.",'']
    else:
        lines+=['No development candidate improved mean margin, so the predeclared stopping rule left the validation seeds unused.','']
    n=sum(s['completed'] for s in stages.values())
    max_time=max(r['max_action_seconds'] for s in stages.values() for r in s['arms'].values())
    timeouts=sum(r['actions_over_1s'] for s in stages.values() for r in s['arms'].values())
    lines+=['## Checks and limitations','',f"All **{n} benchmark games** completed. Across the evaluated own-agent calls, the largest measured decision was **{max_time:.4f} seconds**, with **{timeouts} calls over one second**. This offline harness measures decision time but does not enforce online timeouts. The V56 validation panel had no calls over one second for either m1 or the candidate; the spikes occurred in direct games hosting two large m1-family agents in one process.",'',
            'Each direct game had one slow seat-0 call: 32 charged to the candidate and 32 to unchanged m1. Two additional serial timing diagnostics preserve the exact recorded action hashes and rewards. Garbage-collection callbacks identify a generation-2 collection during the first player’s day-1 action (step 24), lasting 2.064 seconds with the candidate in seat 0 and 1.089 seconds with m1 there. The raw timing failures are retained, and the direct results are offline cash outcomes rather than certification under online time limits. No GC settings or agent code were changed to make the result pass.','',
            'The donor-age audit covered 105 hourly UMG replays: 170,517 of 170,542 inferred productive tile/day ages matched (99.985%); 3,697 productive observations had no inferred age and receive no age penalty. The other 479 tapes have inferred, unaudited ages. This is a limitation of the compact tape data.','',
            'The calendar audit examined 19,479 native wheat opportunities: the original frozen overlay accepted 10,956, including two late opportunities missing planting-day water. The editable template now explicitly rejects those; all 10,954 accepted schedules in the corrected audit have planting-day water. Frozen benchmark sources remain preserved. All 48 development rotations actually produced four tomatoes, so this edge case did not explain their measured result. Rebuilding the rotation/control from the corrected template produces new hashes; those rebuilds are not the versions in the benchmark tables.','',
            'DSM replay produced about 396 additional no-effect commands per game, 66 fewer strawberries, and 23 fewer melons than m1. This rejects this direct library transplant, not the value of DSM production data or the strength of the original live DSM agent.','',
            '## Reproduction and artifacts','',
            '- `results/fresh/rotation_experiments/design.json`: random seeds, selection rule, initial hashes.',
            '- `results/fresh/rotation_experiments/selection.json`: candidate selection before held-out results.',
            '- Each panel has `manifest.json`, immutable-for-this-run `frozen/` sources, all game rows, logs, and `summary.json`.',
            '- `scripts/rotation_experiment_panel.py`: frozen-source, resumable panel dispatch.',
            '- `scripts/summarize_rotation_experiments.py`: paired comparisons, cash ledgers, activation, timing, seed-cluster intervals.',
            '- `scripts/build_rotation_experiments.py`: rebuild variants from m1 and the local donor libraries (the rotation template includes the later day-zero guard).',
            '- `scripts/audit_rotation_births.py`, `scripts/audit_rotation_calendars.py`, `scripts/check_rotation_seed_overlap.py`: data and schedule audits.','',
            f"Baseline SHA-256: `{design['build']['baseline_sha256']}`.",'']
    path=ROOT/'docs/rotation_experiments_random_seeds.md'
    path.write_text('\n'.join(lines),encoding='utf-8')
    verdict={'candidate':chosen,'reliable_improvement':promising,'games':n,'report':str(path),
             'baseline_unchanged':True,'max_action_seconds':max_time,'actions_over_1s':timeouts}
    (OUT/'verdict.json').write_text(json.dumps(verdict,indent=2))
    print(json.dumps(verdict))


if __name__=='__main__':main()
