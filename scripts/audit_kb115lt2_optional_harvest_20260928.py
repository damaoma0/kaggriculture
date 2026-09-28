"""Read-only harvest accounting and bounded single-move screening on fixtures.

No environment is constructed, no agent is called, and no hill-climb is run.
Trusted captured argument graphs are read; the original nested scoring closures
are exposed in memory without modifying any executor file.
"""
import argparse
import ast
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import pickle
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = Path(r'C:\Users\xyygl\Documents\kaggriculture\results\fresh\semantic_strategy_20260928\polish_fixtures_v8_live01')


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    spec = importlib.util.spec_from_file_location('_strategy_kb115lt', path)
    mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    tree = ast.parse(path.read_text())
    fun = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_tier_polish')
    fun = deepcopy(fun); fun.name = '_audit_score_setup'
    stop = next(i for i, n in enumerate(fun.body) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'iters' for t in n.targets))
    fun.body = fun.body[:stop] + ast.parse("return dict(seg_eval=seg_eval, total=total, stop_val=stop_val, movable=movable, lo=lo, E=E, load0=load0, head=head, OPT=OPT)").body
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fun], type_ignores=[])), str(path), 'exec'), mod.__dict__)
    return mod


def entries(mod, rows, tiles, day, rest=False):
    out = []
    for sg in rows:
        for x in ([sg] if rest else sg['stops']):
            tile = x['tile']; t = mod._tile(tiles, tile)
            if not mod._animal(t): continue
            for op in x['ops']:
                if op['c'][0] != 'HARVEST': continue
                out.append(dict(unit=None if rest else sg['u'], tile=tile, animal=t['animal'],
                    held=int(t.get('yield_units', 0)), mandatory=bool(op['m']), original_value=float(op['v']),
                    needed_to_avoid_overflow_or_season_end=mod._tier_anim_harv_needed(t, day),
                    bundle=[o['c'] for o in x['ops']]))
    return out


def scan_moves(mod, ctx, args, after):
    S, segs, rest, tiles, day, st = after
    E = [ctx['seg_eval'](sg, sg['stops']) for sg in segs]
    score = ctx['total'](E)
    capacity = ctx['load0'] + ctx['head']
    candidates = []
    for bd in rest:
        tile = bd['tile']; t = mod._tile(tiles, tile)
        if not mod._animal(t): continue
        hv = [o for o in bd['ops'] if o['c'][0] == 'HARVEST' and not o['m']]
        if len(hv) != 1: continue
        paired = [o for o in bd['ops'] if o['c'][0] in ('HARVEST', 'PLACE_HARVEST')]
        value = float(hv[0]['v'])
        row = dict(tile=tile, animal=t['animal'], held=int(t.get('yield_units', 0)),
                   original_value=value, variants_considered=0, variants_feasible=0,
                   positive_feasible=0, best=None, rejected=Counter())
        for k, sg in enumerate(segs):
            for j, x in enumerate(sg['stops']):
                if x['tile'] != tile or not ctx['movable'](x): continue
                if any(o['c'][0] == 'HARVEST' for o in x['ops']): continue
                removals = [(None, None)]
                for j2, x2 in enumerate(sg['stops']):
                    if ctx['movable'](x2):
                        removals += [(j2, o) for o in x2['ops'] if o['c'][0] in ctx['OPT'] and not o['m']]
                for j2, remove in removals:
                    trial = list(sg['stops'])
                    trial[j] = dict(x, ops=sorted(x['ops'] + paired, key=lambda o:o.get('rank', 5)))
                    removed = None
                    if remove is not None:
                        ops = [o for o in trial[j2]['ops'] if o is not remove]
                        if not ops and j2 == ctx['lo'](k): continue
                        removed = dict(tile=trial[j2]['tile'], command=remove['c'])
                        trial = trial[:j2] + ([dict(trial[j2], ops=ops)] if ops else []) + trial[j2+1:]
                    row['variants_considered'] += 1
                    ev = mod._tier_eval(sg, trial)
                    old_ev = mod._tier_eval(sg, sg['stops'])
                    E2 = list(E); E2[k] = ctx['seg_eval'](sg, trial)
                    load = sum(e['load'] for e in E2)
                    reject = []
                    if ev[0] > 24 or ev[1] > old_ev[1] or ev[3] > old_ev[3]: reject.append('time_or_supply')
                    if load > capacity: reject.append('midnight_capacity')
                    if reject:
                        row['rejected'].update(reject); continue
                    row['variants_feasible'] += 1
                    raw = ctx['total'](E2) - score
                    corrected = raw + value
                    candidate = dict(unit=sg['u'], kind='add' if remove is None else 'exchange', removed=removed,
                        end_exclusive=ev[0], midnight_load=load, capacity_limit=capacity,
                        current_score_delta=round(raw, 6), score_delta_with_source_harvest_value=round(corrected, 6))
                    if corrected > 1e-6: row['positive_feasible'] += 1
                    if row['best'] is None or corrected > row['best']['score_delta_with_source_harvest_value']:
                        row['best'] = candidate
        row['rejected'] = dict(row['rejected']); candidates.append(row)
    return candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, default=DEFAULT)
    parser.add_argument('--output', type=Path, default=ROOT/'results/fresh/semantic_kb115lt2_recovery/optional_harvest_audit.json')
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    source = ROOT/'agents/mgt_lead_kb115lt2.py'; mod = load(source)
    manifest_path = args.fixtures/'manifest.json'; manifest = json.loads(manifest_path.read_text())
    assert manifest['verified']
    rows = []
    for rec in manifest['fixtures']:
        path = args.fixtures/rec['file']; assert sha(path) == rec['sha256']
        payload = pickle.loads(gzip.decompress(path.read_bytes()))
        fixture = pickle.loads(payload['input_pickle']); before = fixture['args']
        after = pickle.loads(payload['reference_output_pickle'])
        for key, value in fixture['globals'].items(): setattr(mod, key, deepcopy(value))
        S, segs, rest, tiles, day, st = before
        ctx = mod._audit_score_setup(*deepcopy(before))
        planned_before = entries(mod, segs, tiles, day)
        planned_after = entries(mod, after[1], tiles, day)
        identity = lambda rows: Counter((r['tile'], r['animal'], r['mandatory'], r['held'], r['original_value']) for r in rows)
        assert identity(planned_before) == identity(planned_after)
        opt_before = [r for r in planned_before if not r['mandatory']]
        opt_after = [r for r in planned_after if not r['mandatory']]
        unplaced = entries(mod, rest, tiles, day, rest=True)
        unplaced_after = entries(mod, after[2], tiles, day, rest=True)
        assert identity(unplaced) == identity(unplaced_after)
        E_after = [ctx['seg_eval'](sg, sg['stops']) for sg in after[1]]
        raw_gain = ctx['total'](E_after)-ctx['total'](ctx['E'])
        value_before = sum(r['original_value'] for r in opt_before)
        value_after = sum(r['original_value'] for r in opt_after)
        row = dict(day=day, fixture=rec['file'], fixture_sha256=rec['sha256'],
            optional_harvest_planned_before=opt_before, optional_harvest_planned_after=opt_after,
            optional_harvest_unplaced_before=unplaced, optional_harvest_unplaced_after=unplaced_after,
            all_animal_harvest_multiset_preserved=True, unplaced_harvest_multiset_preserved=True,
            ignored_planned_value_before=value_before, ignored_planned_value_after=value_after,
            raw_polish_gain=round(raw_gain, 6), gain_with_harvest_value=round(raw_gain+value_after-value_before, 6),
            original_polish_summary=after[5].get('_polish_day'), original_dump_summary=st.get('_dump_day'),
            final_midnight_load=sum(e['load'] for e in E_after), initial_midnight_load=ctx['load0'], additional_headroom=ctx['head'],
            strict_existing_visit_single_move_screen=scan_moves(mod, ctx, before, after))
        rows.append(row)
    result = dict(scope='READ_ONLY_CAPTURED_POLISH_ARGUMENTS_NO_ENGINE_NO_HILL_CLIMB',
        executor_sha256=sha(source), capture_manifest_sha256=sha(manifest_path), script_sha256=sha(Path(__file__)),
        rows=rows, conclusions=dict(existing_optional_harvest_drop_bug=False,
            existing_harvest_value_is_invariant_offset=True,
            unplaced_optional_harvest_outside_declared_polish_move_set=True),
        limitation='Single-move modeled-score screen, not jointly compatible moves, actual successful harvests, market revenue, or profit. Existing capacity/delivery positions are preserved. Original files untouched.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    for row in rows:
        print(json.dumps(dict(day=row['day'], optional_planned=len(row['optional_harvest_planned_before']),
            unplaced=len(row['optional_harvest_unplaced_before']), ignored_value=row['ignored_planned_value_before'],
            final_load=row['final_midnight_load'], positive_move_targets=[r for r in row['strict_existing_visit_single_move_screen'] if r['positive_feasible'] > 0])))
    print(args.output)


if __name__ == '__main__': main()
