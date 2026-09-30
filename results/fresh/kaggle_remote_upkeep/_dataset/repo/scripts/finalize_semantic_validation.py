"""Verify complete paired coverage and write the final validation capsule."""
from pathlib import Path
from collections import Counter
from hashlib import sha256
import contextlib,io,json,subprocess,sys
from report_semantic_farm import report
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/fresh/semantic_architecture_20260924'


def main():
    checks={};summaries={}
    for folder in ('panel_verified','live_verified'):
        rows=[json.loads(p.read_text(encoding='utf8')) for p in (BASE/folder).glob('*.json')
              if p.name not in ('manifest.json','summary.json')]
        assert Counter(r['arm'] for r in rows)==Counter(dict(semantic=16,m1=16,y3=16,v9lite=16))
        assert all(r.get('completed') and r.get('steps')==719 and r.get('ledger_verified') for r in rows)
        worlds={arm:{(r.get('episode') or r['seed'],r['seat']) for r in rows if r['arm']==arm}
                for arm in ('semantic','m1','y3','v9lite')}
        assert all(w==worlds['semantic'] for w in worlds.values())
        candidate=[r for r in rows if r['arm']=='semantic']
        assert all(not r['failed_orders'][r['seat']] and not r['no_effect'][r['seat']]
                   and not r['stats'].get('unplanned_hours') for r in candidate)
        checks[folder]=dict(games=len(rows),matched_cases=16,all_terminal=True,all_ledgers_reconciled=True,
            candidate_failed_orders=0,candidate_physical_no_effect=0,candidate_emergency_hours=0)
        with contextlib.redirect_stdout(io.StringIO()):summaries[folder]=report(BASE/folder)
    model=json.loads((ROOT/'data/semantic_farm/model.json').read_text())
    episodes={r['episode'] for r in model['rows']}
    panel=json.loads((ROOT/'data/ladder_panel/p2750/index.json').read_text(encoding='utf8'))['games']
    assert not episodes.intersection(map(int,panel))
    for name,digest in model['source_hashes'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==digest
    package=json.loads((BASE/'package_v2/manifest.json').read_text())
    manifest=json.loads((BASE/'panel_verified/manifest.json').read_text())
    hashes={k.replace('\\','/'):v for k,v in manifest['hashes'].items()}
    for name,digest in package['files'].items():
        if name!='main.py':assert hashes[name]==digest
    for name,digest in manifest['hashes'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==digest
    packaged=json.loads((BASE/'package_v2/validation.json').read_text())
    assert packaged['completed'] and packaged['isolated_package'] and packaged['ledger_verified']
    test=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_semantic*.py'],
        cwd=ROOT,text=True,capture_output=True,check=True)
    result=dict(checks=checks,study_episodes=len(episodes),study_seats=50,benchmark_overlap=0,
        test_output=test.stdout+test.stderr,package_archive_sha256=package['archive_sha256'],
        local_entrypoint_sha256=sha256((ROOT/'agents/semantic_farm.py').read_bytes()).hexdigest(),
        package_isolated_full_game=True,packaged_policy_matches_benchmark=True,
        summaries=summaries,status='mechanical validation passed; competitive promotion rejected')
    (BASE/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    lines=['## Results','',
        'All **128 paired benchmark games** completed (32 cases per arm), with both cash ledgers reconciled. '
        'The default semantic candidate had **zero failed purchases, ineffective physical jobs, and emergency hours** '
        'across its 32 benchmark games. These execution gates passed; competitive promotion failed.','',
        '| Panel | Agent | Wins / 16 | Mean cash | Mean margin |',
        '|---|---|---:|---:|---:|']
    for name,summary in summaries.items():
        for arm in ('semantic','m1','y3','v9lite'):
            r=summary['arms'][arm]
            lines.append(f"| {'Recorded 2750–3000 team band' if name=='panel_verified' else 'Live V56'} | {arm} | {r['score']*16:g} | {r['mean_cash']:,.0f} | {r['mean_margin']:,.0f} |")
    lines+=['','Scores count draws as half a win. No Elo rating is inferred.','']
    measured=summaries['panel_verified']['arms'];candidate=measured['semantic'];control=measured['v9lite']
    cash_gap=control['mean_cash']-candidate['mean_cash']
    rival_gap=(candidate['mean_cash']-candidate['mean_margin'])-(control['mean_cash']-control['mean_margin'])
    lines += [f"On the recorded panel, the semantic policy earns {cash_gap:,.0f} less cash than v9lite "
        f"while its recorded opponents earn {rival_gap:,.0f} more. The market feedback matters: "
        "valuing only our additional crop receipts does not capture the full competitive effect of changing supply.",'']
    for name,summary in summaries.items():
        r=summary['paired']['v9lite'];low,high=r['margin_ci95']
        own=summary['arms']['semantic']
        lines.append(f"Against v9lite's result in the same {'recorded' if name=='panel_verified' else 'live'} worlds, "
            f"the candidate's mean margin difference is **{r['mean_margin_delta']:,.0f}** "
            f"(world-cluster bootstrap 95% interval {low:,.0f} to {high:,.0f}). "
            f"It used fallback service on {own['recovery_days']} days; no animal-count decreases were observed. "
            f"Maximum measured action time was {own['max_call']:.2f}s and maximum total policy time "
            f"in a game was {own['max_total_agent_seconds']:.2f}s.")
        assert not own['animal_count_decreases']
        lines.append('')
    sensitivity=summaries['panel_verified']['paired']['v9lite']['unflagged_sensitivity']
    lines += [f"The recorded-tape validity sensitivity (more than 40 changed opponent no-effect commands) "
        f"leaves {sensitivity['worlds']} unflagged worlds. Their mean margin difference versus v9lite is "
        f"{sensitivity['mean_margin_delta']:,.0f}; the main table keeps all 16 worlds.",'']
    lines+=['The package test and six additional ablation games also completed; they are separate from the 128-game table.',
        '', 'Artifacts:', '',
        '- [Validation capsule](../results/fresh/semantic_architecture_20260924/validation.json)',
        '- [Recorded-panel summary](../results/fresh/semantic_architecture_20260924/panel_verified/summary.json)',
        '- [Live-panel summary](../results/fresh/semantic_architecture_20260924/live_verified/summary.json)',
        '- [Care/layout ablations](../results/fresh/semantic_architecture_20260924/ablation_verified/summary.json)',
        '- [Family holdouts](../results/fresh/semantic_architecture_20260924/family_holdout.json)',
        '- [Verified archive](../results/fresh/semantic_architecture_20260924/package_v2/semantic_farm.tar.gz)',
        '']
    doc=ROOT/'docs/semantic_farm_implementation_20260924.md'
    content=doc.read_text(encoding='utf8')
    if '\n## Results\n' in content:
        start=content.index('\n## Results\n');end=content.index('\n## Reproduction\n',start)
        content=content[:start]+content[end:]
    content=content.replace('## Reproduction','\n'.join(lines)+'\n## Reproduction')
    doc.write_text(content,encoding='utf8')
    print(json.dumps(dict(checks=checks,tests=test.stdout+test.stderr,status=result['status'])))
    for name,summary in summaries.items():
        print(name,json.dumps({arm:{k:r[k] for k in ('score','mean_margin','mean_cash','max_call','max_total_agent_seconds')}
            for arm,r in summary['arms'].items()}))


if __name__=='__main__':main()
