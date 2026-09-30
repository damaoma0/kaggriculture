"""Compare recorded m1 tape choices with exhaustive, position-free plan retrieval.

Offline descriptive audit only. No future shops, rewards, output labels or future
actions enter retrieval. Donor next-window actions describe plan differences;
they are not proof of successful execution or an economic optimum.
"""
import ast
import base64
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import statistics
import zlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/production_plan_fit'
DAYS = (12, 15, 18, 21, 24)
LABELS = ('WH', 'CA', 'TO', 'ST', 'ME', 'go', 'co', 'sh')
CROPS = ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON')
ANIMALS = ('go', 'co', 'sh')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def mean(xs):
    return statistics.mean(xs) if xs else None


def l1(a, b, keys):
    return sum(abs(a.get(k, 0) - b.get(k, 0)) for k in keys)


def load_library():
    path = ROOT / 'agents/mgt_m1.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    namespace = {}
    wanted = {'_MGT_CFG', '_MGT_DEMAND', '_MGT_WEIGHT', '_MGT_CHECKPOINTS', '_MGT_PRODUCTS'}
    functions = {'_mgt_label', '_mgt_board', '_mgt_labels', '_mgt_vec', '_mgt_distance'}
    library = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in wanted:
                namespace[name] = ast.literal_eval(node.value)
            if name == '_MGT_LIB':
                payload = max((n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)), key=len)
                library = json.loads(zlib.decompress(base64.b85decode(payload)))
        elif isinstance(node, ast.FunctionDef) and node.name in functions:
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    namespace['_MGT_W'] = tuple(namespace['_MGT_WEIGHT'][p] for p in namespace['_MGT_PRODUCTS'])
    for tape in library['tapes']:
        tape['vec'] = [namespace['_mgt_vec'](tape['shops'], j) for j in range(9)]
        tape['lab'] = [namespace['_mgt_labels'](b) for b in tape['boards']]
        tape['counts'] = [Counter(b) for b in tape['lab']]
    return namespace, library


def plan(tape, day, actions):
    by_day = Counter()
    total = Counter()
    for step in range(day * 24, min((day + 3) * 24, len(tape['ids']))):
        action = actions[tape['ids'][step]]
        if not isinstance(action, dict):
            continue
        for command in [action.get('farmer') or [], *(action.get('hands') or [])]:
            if command and command[0] == 'PLANT' and len(command) > 1:
                total[command[1]] += 1
                by_day[f'{step // 24}:{command[1]}'] += 1
    return dict(plants=dict(total), plants_by_day=dict(by_day),
                terminal_assets={p: tape['counts'][day + 3][p] for p in LABELS})


def summarize(rows, mode):
    pairs = [(r['current'], r[mode]) for r in rows]
    changed = [(a, b) for a, b in pairs if a['episode'] != b['episode']]
    return dict(
        n=len(rows), changed_tape=len(changed),
        strictly_better_history_fit=sum(b['history_distance'] < a['history_distance'] - 1e-8 for a, b in pairs),
        strictly_better_current_demand=sum(b['current_demand_distance'] < a['current_demand_distance'] - 1e-8 for a, b in pairs),
        current_history_distance=mean([a['history_distance'] for a, b in pairs]),
        alternative_history_distance=mean([b['history_distance'] for a, b in pairs]),
        current_demand_distance=mean([a['current_demand_distance'] for a, b in pairs]),
        alternative_current_demand_distance=mean([b['current_demand_distance'] for a, b in pairs]),
        current_asset_count_l1=mean([a['asset_count_l1'] for a, b in pairs]),
        alternative_asset_count_l1=mean([b['asset_count_l1'] for a, b in pairs]),
        alternative_blocked_by_layout=sum(b['hamming'] > 8 and a['episode'] != b['episode'] for a, b in pairs),
        current_exact_demand=sum(a['current_demand_distance'] == 0 for a, b in pairs),
        alternative_exact_demand=sum(b['current_demand_distance'] == 0 for a, b in pairs),
        mean_changed_crop_count_l1=mean([l1(a['plan']['plants'], b['plan']['plants'], CROPS) for a, b in pairs]),
        mean_changed_dated_plant_l1=mean([l1(a['plan']['plants_by_day'], b['plan']['plants_by_day'], a['plan']['plants_by_day'].keys() | b['plan']['plants_by_day'].keys()) for a, b in pairs]),
        mean_changed_terminal_herd_l1=mean([l1(a['plan']['terminal_assets'], b['plan']['terminal_assets'], ANIMALS) for a, b in pairs]),
        materially_different_plan=sum(a['plan'] != b['plan'] for a, b in pairs),
        crop_absolute_change={p: mean([abs(a['plan']['plants'].get(p, 0) - b['plan']['plants'].get(p, 0)) for a, b in pairs]) for p in CROPS},
    )


def main():
    ns, lib = load_library()
    tapes = lib['tapes']
    actions = lib['actions']
    by_ep = {int(t['ep']): t for t in tapes}
    assert len(by_ep) == len(tapes) == 584
    own_path = ROOT / 'results/fresh/tape_gap_plans/dataset_primary.json'
    own = read(own_path)
    assert (ROOT/'agents/mgt_m1.py').read_bytes() == (ROOT/'submissions/2026-09-20-mgt_m1/main.py').read_bytes()
    rows, trace_hashes = [], {}
    for game in own['games']:
        ep, seat = game['episode'], game['seat']
        trace_path = ROOT / f'results/fresh/ladder_panel/mgt_m1/{ep}.json'
        trace = read(trace_path)
        assert [trace['final'], trace['rival']] == [game['rewards'][seat], game['rewards'][1-seat]], ep
        assert trace['router'].get('router_errors', 0) == 0
        trace_hashes[str(ep)] = sha256(trace_path.read_bytes()).hexdigest()
        for day in DAYS:
            cp = game['checkpoints'][str(day)]
            obs = cp['observation']
            shops = obs['town']['unlocked_shops']
            labels = ns['_mgt_labels'](ns['_mgt_board'](obs['farms'][seat]))
            counts = Counter(labels)
            current_ep = int([h for h in trace['switches'] if h[0] <= day][-1][1])
            vectors = [ns['_mgt_vec'](shops, j) for j in range(9)]
            scores = {}
            for tape in tapes:
                ident = int(tape['ep'])
                common = 0
                for a, b in zip(shops, tape['shops']):
                    if a != b:
                        break
                    common += 1
                native_score = ns['_mgt_distance'](vectors, shops, tape, len(shops))
                distance = native_score + .01 * common
                current_distance = sum(w * abs(x-y) for w, x, y in zip(ns['_MGT_W'], vectors[len(shops)], tape['vec'][len(shops)]))
                scores[ident] = dict(episode=ident, native_score=native_score, history_distance=distance,
                    current_demand_distance=current_distance,
                    asset_count_l1=l1(counts, tape['counts'][day], LABELS),
                    hamming=sum(a != b for a, b in zip(labels, tape['lab'][day])),
                    shops=tape['shops'][:len(shops)],
                    assets={p: tape['counts'][day][p] for p in LABELS})
            def rank(ident):
                s = scores[ident]
                return s['native_score'], s['asset_count_l1'], ident != current_ep, ident
            best = min(scores, key=rank)
            commitment_bound = scores[current_ep]['asset_count_l1']
            bounded = min((i for i in scores if scores[i]['asset_count_l1'] <= commitment_bound), key=rank)
            slack4 = min((i for i in scores if scores[i]['asset_count_l1'] <= commitment_bound + 4), key=rank)
            slack8 = min((i for i in scores if scores[i]['asset_count_l1'] <= commitment_bound + 8), key=rank)
            demand_first = min(scores, key=lambda i: (scores[i]['current_demand_distance'], scores[i]['asset_count_l1'], scores[i]['native_score'], i != current_ep, i))
            row = dict(episode=ep, seat=seat, day=day, shops=shops,
                       own_assets={p: counts[p] for p in LABELS})
            for name, ident in [('current', current_ep), ('position_free', best), ('commitment_bounded', bounded), ('asset_slack_4', slack4), ('asset_slack_8', slack8), ('current_demand_first', demand_first)]:
                row[name] = dict(scores[ident], plan=plan(by_ep[ident], day, actions))
            assert row['position_free']['native_score'] <= row['current']['native_score'] + 1e-8
            assert row['commitment_bounded']['asset_count_l1'] <= row['current']['asset_count_l1']
            rows.append(row)
    assert len(rows) == 430 and len(trace_hashes) == 86
    modes = ('position_free', 'commitment_bounded', 'asset_slack_4', 'asset_slack_8', 'current_demand_first')
    result = dict(
        protocol=dict(query='86 recorded m1 games, five current-state checkpoints per game; actual selected donors recovered from cash-matched saved replay traces.',
            candidates='All 584 embedded UMG tapes, same library as current m1.',
            position_free='Minimum existing revealed-demand-history score, then minimum productive asset-count L1; coordinates and animal stranding are omitted.',
            commitment_bounded='Same exhaustive ranking, restricted to donors with no larger asset-count L1 than the actual chosen tape.',
            asset_slack='Sensitivity: allow 4 or 8 additional units of productive asset-count L1 beyond the current donor. Not measured investment costs or feasibility bounds.',
            current_demand_first='Minimum demand distance for currently open shops; tie-break by asset counts, existing history score, then current tape and episode.',
            no_future_input=True,
            limitations=['Best fit means exhaustive optimum of an explicitly defined retrieval metric, not profit optimality.',
                         'Compact boards omit ages, held yields and care. Count compatibility does not certify feasible execution.',
                         'Plant counts are intended tape PLANT commands, not newly simulated successful plantings. Terminal assets are the donor recorded state.',
                         'Alternative plans are compared at baseline states; this is not a recursively executed alternative policy.',
                         'Saved traces match final cash for both seats but do not store source/action hashes; current source matches archived submitted source.']),
        source_sha256={str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), own_path, ROOT/'agents/mgt_m1.py', ROOT/'submissions/2026-09-20-mgt_m1/main.py')},
        trace_sha256=trace_hashes,
        summary={mode: dict(overall=summarize(rows, mode), by_day={str(d): summarize([r for r in rows if r['day'] == d], mode) for d in DAYS}) for mode in modes},
        rows=rows)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({mode: result['summary'][mode]['overall'] for mode in modes}, indent=2))


if __name__ == '__main__':
    main()
