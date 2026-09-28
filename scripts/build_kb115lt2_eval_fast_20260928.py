"""Build an isolated exact scalar-route evaluator optimization.

The original evaluator stays available for detailed op-hour queries and an
OFF control. Search budgets, random draws and route objectives are unchanged.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA256 = "5c2dfb70eaf68e1b415fe14fd6414774b467afa81b4f66f9d170e792e0dfe833"

FAST = '''

def _tier_eval(seg, stops=None, want_hours=False):
    # The scalar result never uses wheat/animal inventory counters after
    # charging the initial pickups. Preserve the reference for hour traces.
    if want_hours or not CFG.get("sd_tier_eval_fast", 1):
        return _tier_eval_reference(seg, stops, want_hours)
    D = _TIER_D
    stops = seg["stops"] if stops is None else stops
    t, p = seg["t0"], seg["p0"]
    nf, hw = 0, 0
    animals = set()
    for s in stops:
        ops = s["ops"]
        for o in ops:
            c = o["c"]
            if (c[0] == "HARVEST" and _TIER_WY and o["m"]
                    and s["tile"] in _TIER_WY
                    and not any(o2["c"][0] == "PLACE_HARVEST" for o2 in ops)):
                hw += _TIER_WY[s["tile"]]
            elif c[0] == "FEED":
                if hw > 0:
                    hw -= 1
                else:
                    nf += 1
            elif c[0] == "PLACE" and len(c) > 1 and c[1] in ANIMALS:
                animals.add(c[1])
    fp = int(seg.get("fpick", 0) or 0)
    if CFG["sd_wheat_fert_mand"]:
        fp += _tier_fmand_need(stops, fp)
    kd = 0
    while kd < len(stops) and stops[kd].get("dawn"):
        kd += 1
    if seg.get("hold0") and t == 0 and not ((kd == 0 and (nf or animals or fp) and p in _TIER_SHED_I)
                                            or (stops and stops[0]["tile"] == p)):
        t = 1
    late = hop = bad = f = 0
    first = True
    for i in range(len(stops) + 1):
        if i == kd:
            if nf or animals or fp:
                if p not in _TIER_SHED_I:
                    shed = _tier_near_shed(p)
                    t += D[p][shed]
                    p = shed
                if nf:
                    t += 1
                if fp:
                    t += 1
                    f += fp
                if animals:
                    t = max(t, seg.get("goose_ready", 2)) + len(animals)
            first = True
        if i == len(stops):
            break
        s = stops[i]
        b = s["tile"]
        d = D[p][b]
        t += d
        if not first and d > 1:
            hop += d - 1
        first = False
        if t < s["rel"]:
            t = s["rel"]
        for o in s["ops"]:
            c = o["c"][0]
            if c == "COLLECT_FERTILIZER":
                f += 1
            elif c == "FERTILIZE":
                if f <= 0:
                    bad += 1
                else:
                    f -= 1
            t += 1
            if o["m"] and t - 1 > 23:
                late += t - 1 - 23
        p = b
    if t > 24:
        late += t - 24
    return t, late, hop, bad
'''


def transform(source: str) -> str:
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_tier_eval')
    if any(isinstance(n, ast.FunctionDef) and n.name == '_tier_eval_reference' for n in tree.body):
        raise ValueError('Source already transformed')
    lines = source.splitlines(keepends=True)
    original = ''.join(lines[node.lineno - 1:node.end_lineno])
    reference = original.replace('def _tier_eval(', 'def _tier_eval_reference(', 1)
    lines[node.lineno - 1:node.end_lineno] = [reference + FAST]
    result = ''.join(lines)
    before = {n.name: ast.dump(n, include_attributes=False) for n in tree.body if isinstance(n, ast.FunctionDef)}
    after = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(result).body if isinstance(n, ast.FunctionDef)}
    assert [n for n in before if before[n] != after[n]] == ['_tier_eval']
    assert set(after) - set(before) == {'_tier_eval_reference'}
    assert list(before)[-1] == list(after)[-1], 'Preserve the Kaggle entry callable'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'agents/mgt_lead_kb115lt2_routefix_fast.py')
    parser.add_argument('--output', type=Path, default=ROOT / 'agents/mgt_lead_kb115lt2_eval_fast.py')
    parser.add_argument('--expected-source-sha256', default=BASE_SHA256)
    args = parser.parse_args()
    assert args.source.resolve() != args.output.resolve()
    assert hashlib.sha256(args.source.read_bytes()).hexdigest() == args.expected_source_sha256
    result = transform(args.source.read_text(encoding='utf-8'))
    args.output.write_text(result, encoding='utf-8', newline='\n')
    print(hashlib.sha256(args.output.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
