"""Summarize complete panels without treating mirrored seats as new seeds."""
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from hashlib import sha256

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/production_modules'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def comparison(rows, base, cash='cash'):
    pairs = [(r, base[k]) for k, r in rows.items()]
    ds = [r['margin'] - b['margin'] for r, b in pairs]
    return dict(games=len(ds), mean_margin_delta=mean(ds),
                mean_cash_delta=mean(r[cash] - b[cash] for r, b in pairs),
                better=sum(d > 0 for d in ds), worse=sum(d < 0 for d in ds),
                equal=sum(d == 0 for d in ds), worst=min(ds), best=max(ds),
                wins=sum(r['margin'] > 0 for r, b in pairs),
                base_wins=sum(b['margin'] > 0 for r, b in pairs))


def panel(directory, names):
    groups = {}
    for name in names:
        rows = [read(p) for p in directory.glob(name + '-*.json')]
        assert len(rows) == 16, (directory, name, len(rows))
        digest = sha256((ROOT / 'agents' / (name + '.py')).read_text(encoding='utf-8').encode()).hexdigest()
        assert all(r['sha256'] == digest for r in rows), ('stale agent results', name)
        assert all(r['statuses'] == ['DONE', 'DONE'] and r['actions'] == 719 for r in rows)
        groups[name] = {(r['seed'], r['seat'], r['opponent']): r for r in rows}
    result = {name: comparison(rows, groups['mgt_m1']) for name, rows in groups.items()}
    if 'mgt_pm_pin' in groups:
        result['forced_vs_pin'] = comparison(groups['mgt_pm_forced'], groups['mgt_pm_pin'])
    for name, rows in groups.items():
        totals = Counter()
        audits = []
        wheat_matches = []
        for k, r in rows.items():
            for field, val in r['telemetry'].items():
                if isinstance(val, (int, float)):
                    totals[field] += val
            if name != 'mgt_pm_forced':
                continue
            for p in r['telemetry'].get('active', {}).values():
                plant = [e for e in r['events'] if e['step'] == p['start'] and tuple(e['tile']) == tuple(p['tile'])
                         and e['command'] == ['PLANT', 'CARROT'] and e['after'] == 'CARROT']
                harvest = [e for e in r['events'] if p['start'] < e['step'] < p['end'] and tuple(e['tile']) == tuple(p['tile'])
                           and e['produced'].get('CARROT')]
                got = sum(e['produced']['CARROT'] for e in harvest)
                audits.append(dict(world=k, tile=p['tile'], start=p['start'], expected=p['expected'],
                                   units=got, correct=len(plant) == 1 and got == p['expected']))
                control = groups['mgt_pm_pin'][k]
                ce = [e for e in control['events'] if tuple(e['tile']) == tuple(p['tile'])]
                planted = any(e['step'] == p['start'] and e['command'] == ['PLANT', 'WHEAT'] and e['after'] == 'WHEAT' for e in ce)
                stop = min([e['step'] for e in ce if e['step'] > p['start'] and e['command'][0] == 'PLANT'] + [p['original_wheat_release']])
                wheat = sum(e['produced'].get('WHEAT', 0) for e in ce if p['start'] < e['step'] <= stop)
                wheat_matches.append(dict(matched=planted, wheat=wheat))
        result[name]['telemetry'] = dict(totals)
        if audits:
            result[name]['module_audit'] = dict(cycles=len(audits), correct=sum(a['correct'] for a in audits),
                                              produced=sum(a['units'] for a in audits), failures=[a for a in audits if not a['correct']])
            assert all(a['correct'] for a in audits), result[name]['module_audit']
            result[name]['pin_wheat_counterfactual'] = dict(matched=sum(a['matched'] for a in wheat_matches),
                produced=sum(a['wheat'] for a in wheat_matches if a['matched']))
    return result


def main():
    natural = panel(OUT / 'integration', ['mgt_m1', 'mgt_pm_forced', 'mgt_pm_value', 'mgt_pm_pin', 'mgt_pm_off'])
    fixed = panel(OUT / 'fixed_shops', ['mgt_m1', 'mgt_pm_forced', 'mgt_pm_pin'])
    episodes = [Path(p).name.split('.')[0] for p in read(OUT / 'ladder_selection.json')]
    groups = {name: {e: read(ROOT / f'results/fresh/ladder_panel/{name}/{e}.json') for e in episodes}
              for name in ['mgt_m1', 'mgt_pm_forced', 'mgt_pm_value', 'mgt_pm_pin']}
    ladder = {name: comparison(rows, groups['mgt_m1'], 'final') for name, rows in groups.items()}
    ladder['forced_vs_pin'] = comparison(groups['mgt_pm_forced'], groups['mgt_pm_pin'], 'final')
    for name, rows in groups.items():
        ladder[name]['opponent_breakage_flags'] = sum(r['opp_dead'] - groups['mgt_m1'][k]['opp_dead'] > 40 for k, r in rows.items())
        ladder[name]['hire_short_games'] = sum(bool(r['hires']['short_days']) for r in rows.values())
        ladder[name]['episodes'] = episodes
    result = dict(natural=natural, fixed_shops=fixed, recorded_ladder=ladder)
    (OUT / 'integration_findings.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    # Reconstitute the complete panel manifest after targeted trace-only replays.
    import benchmark_production_modules as B
    folder = OUT / 'integration'
    allrows = [read(p) for p in folder.glob('mgt*-*.json')]
    B.report(allrows, folder)
    manifest = read(folder / 'manifest.json')
    manifest['agents'] = {name: sha256((ROOT / 'agents' / (name + '.py')).read_bytes()).hexdigest()
                          for name in {r['agent'] for r in allrows}}
    manifest['jobs'] = len(allrows)
    manifest['event_schema_2_games'] = sum(r.get('event_schema') == 2 for r in allrows)
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({design: {n: {k: v for k, v in r.items() if k not in ('telemetry', 'episodes')} for n, r in rs.items()}
                      for design, rs in result.items()}, indent=2))


if __name__ == '__main__':
    main()
