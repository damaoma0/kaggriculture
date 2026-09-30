"""Bounded, fresh-process ownership audit against frozen release Y3 code.

This replays only to selected reveal checkpoints; it does not run the v9lite
entrypoint or inspect qualification outcomes. Run only after the release panel.
"""
from copy import deepcopy
from hashlib import sha256
import argparse
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/coherent_switch_20260924_01a0/release_lite_qualification'
PACKAGE = OUT / 'package'
CASES = ('r01-mgt_m1', 'r00-v56')
CHECKPOINTS = (288, 432)


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(case):
    # Keep the exact frozen package's planner modules ahead of worktree scripts.
    pkg_scripts = PACKAGE / 'scripts'
    sys.path.insert(0, str(pkg_scripts))
    sys.path.insert(0, str(PACKAGE))
    import run_coherent_opening_study as H
    R = H.R
    # H deliberately puts the repo's harness scripts first; restore package
    # precedence before loading planner helpers. H.R itself was already audited
    # byte-identical to the package copy.
    sys.path.insert(0, str(pkg_scripts))
    from kaggle_environments.agent import get_last_callable
    import value_tape_search as V
    import value_tape_search_v9 as N

    source = PACKAGE / 'agents/mgt_y3.py'
    y3_sha = digest(source)
    manifest = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['package_files']['agents/mgt_y3.py'] == y3_sha
    # The base V6 guard is intentionally rebound only in this audit process.
    # Runtime.audit then verifies the actual Y3 CODE below, not stale m1 metadata.
    B6 = N.B.B.B
    V.SOURCE_PATH = source
    V.SOURCE = source.read_text(encoding='utf-8')
    V.CODE = compile(V.SOURCE, str(source), 'exec')
    V.SOURCE_SHA256 = y3_sha
    B6.SUPPORTED_AGENT = y3_sha
    assert B6.F.V.SOURCE_SHA256 == y3_sha
    assert B6.SUPPORTED_AGENT == y3_sha

    design = json.loads((OUT / 'design.json').read_text(encoding='utf-8'))
    spec = next(row for row in design['specs'] if row['id'] == case)
    seat = spec['seat']
    shops = spec['world']['shops']
    source_entry = get_last_callable(V.SOURCE, path=str(source))
    rival_path = H.OPPONENTS[spec['opponent']]
    rival = H.load_callable(rival_path, spec['opponent'])
    sim = R.Simulator(dict(seed=spec['world']['seed'], seat=seat, episode=0,
                           shops=[shops[:min(8, d // 3)] for d in range(31)]))
    E = R.engine()
    state = None
    checkpoints = {}
    with sim:
        state = deepcopy(sim.initial)
        state[0].observation.town.unlocked_shops[:] = []
        assert list(state[seat].observation.town.unlocked_shops) == []
        for t in range(max(CHECKPOINTS) + 1):
            sim.t = t
            sim.seats = {id(f): s for s, f in enumerate(state[0].observation.farms)}
            for s in state:
                s.observation.step = t
            expected = shops[:min(8, (t // 24) // 3)]
            assert list(state[seat].observation.town.unlocked_shops) == expected, (t, expected)
            if t in CHECKPOINTS:
                obs = deepcopy(state[seat].observation)
                memory = V.memory_of(source_entry)
                checkpoints[str(t)] = (obs, memory)
            state[seat].action = source_entry(deepcopy(state[seat].observation))
            state[1-seat].action = rival(deepcopy(state[1-seat].observation))
            E.interpreter(state, sim.env)
            if (t + 1) % 24 == 0:
                day = (t + 1) // 24
                state[0].observation.town.unlocked_shops[:] = shops[:min(8, day // 3)]
    assert all(s.status == 'ACTIVE' for s in state)
    assert E._commit_unit is sim.old_commit
    assert E._apply_unit_action is sim.old_unit
    assert E._do_hire is sim.old_hire
    assert E._do_buy_land is sim.old_land

    module_paths = {}
    for name, module in sorted(sys.modules.items()):
        if name.startswith(('value_tape_search', 'rival_trajectory_model')) and getattr(module, '__file__', None):
            module_paths[name] = str(Path(module.__file__).resolve())
            assert Path(module.__file__).resolve().is_relative_to(pkg_scripts.resolve()), (name, module_paths[name])
    assert len(checkpoints) == 2

    per_checkpoint = {}
    audited_turns_before = 0
    for tstr in map(str, CHECKPOINTS):
        obs, memory = checkpoints[tstr]
        before = deepcopy([obs, memory])
        runner = B6.Runtime(audit=True)
        runner.prepare(obs)
        candidates = runner.shortlist(obs, memory)
        assert [obs, memory] == before, 'shortlist mutated checkpoint observation or memory'
        native_route = runner.chassis.players[int(obs['player'])]['route']
        alternate = next((row['route'] for row in candidates
                          if row.get('route') is not None and row['route'] != native_route), None)
        assert alternate is not None, (tstr, candidates, native_route)
        runs = []
        for route_label, route in (('native', None), ('alternate', alternate)):
            for world_index in (0, 1):
                pair_before = deepcopy([obs, memory])
                # V5's M is the standalone trajectory model. N.M in the V9
                # chain is a wrapped world function that requires prepare().
                world = B6.F.M.world(obs, world_index)
                result = runner.rollout(obs, memory, route, world)
                assert [obs, memory] == pair_before, ('observation/memory mutated', tstr, route_label, world_index)
                assert isinstance(result, dict), ('rollout incomplete', tstr, route_label, world_index)
                # Do not retain economic predictions in this ownership-only report.
                runs.append(dict(route=route_label, route_id=route, world_index=world_index,
                                 rollout_returned=True))
        per_checkpoint[tstr] = dict(day=int(tstr)//24, seat=int(obs['player']), shop_prefix=list(obs['town']['unlocked_shops']),
                                    native_route=native_route, alternate_route=alternate, shortlist_count=len(candidates),
                                    runs=runs, audited_turns=runner.audited_turns)
        audited_turns_before += runner.audited_turns

    return dict(case=case, opponent=spec['opponent'], seed=spec['world']['seed'], seat=seat,
                first_shop=spec['world']['first_shop'], shops=shops, checkpoints=per_checkpoint,
                audited_turns=audited_turns_before, y3_sha256=y3_sha,
                supported_agent_sha256=B6.SUPPORTED_AGENT, source_entry='agents/mgt_y3.py via get_last_callable',
                helper_modules=module_paths, worktree_research_labour_profit_sha256=digest(ROOT/'scripts/research_labour_profit.py'),
                package_research_labour_profit_sha256=digest(PACKAGE/'scripts/research_labour_profit.py'),
                research_helper_byte_equal=(ROOT/'scripts/research_labour_profit.py').read_bytes()==(PACKAGE/'scripts/research_labour_profit.py').read_bytes(),
                audit_driver_sha256=digest(Path(__file__)), passed=True,
                scope='Y3 ownership audit only; no v9lite entrypoint, no qualification cash/outcome fields retained')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', choices=CASES, required=True,
                    help='One persisted qualification spec; each invocation is a fresh process.')
    args = ap.parse_args()
    dest = OUT / 'ownership_dynamic' / f'{args.case}.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    assert not dest.exists(), f'Refusing to overwrite {dest}'
    try:
        row = run(args.case)
    except Exception:
        row = dict(case=args.case, passed=False, error=traceback.format_exc(),
                   scope='Y3 ownership audit only; no qualification outcomes retained')
    dest.write_text(json.dumps(row, indent=2), encoding='utf-8')
    print(json.dumps({k: row[k] for k in ('case', 'passed', 'audited_turns', 'error') if k in row}), flush=True)
    if not row['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
