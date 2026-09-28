"""Memoize repeated scalar route costs within one mandatory-route search."""
from __future__ import annotations
import argparse
import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA256 = '9981c45c9ef4f4c19fad92d6c436d92cf4bd621d32fbbc66fc2af91b01095059'


def transform(source):
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_tier_search')
    lines = source.splitlines(keepends=True)
    original = ''.join(lines[node.lineno-1:node.end_lineno])
    assert '_search_cost_cache' not in original
    patched = original.replace('_tier_seg_cost(', '_search_cost(')
    anchor = '    D = _TIER_D\n'
    cache = '''    # Inputs and scoring globals are fixed throughout this search. Segment
    # objects stay alive in segs, so identity keys cannot be recycled here.
    _search_cost_cache = {}
    _search_cache_enabled = bool(CFG.get("sd_tier_search_cache", 1))
    def _search_cost(seg, ids, all_stops):
        if not _search_cache_enabled:
            return _tier_seg_cost(seg, ids, all_stops)
        key = (id(seg), tuple(ids))
        value = _search_cost_cache.get(key)
        if value is None:
            value = _tier_seg_cost(seg, ids, all_stops)
            if len(_search_cost_cache) >= 16384:
                _search_cost_cache.clear()
            _search_cost_cache[key] = value
        return value
'''
    assert patched.count(anchor) == 1
    patched = patched.replace(anchor, cache + anchor, 1)
    lines[node.lineno-1:node.end_lineno] = [patched]
    result = ''.join(lines)
    before = {n.name: ast.dump(n, include_attributes=False) for n in tree.body if isinstance(n, ast.FunctionDef)}
    after = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(result).body if isinstance(n, ast.FunctionDef)}
    assert [n for n in before if before[n] != after[n]] == ['_tier_search']
    assert before.keys() == after.keys()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'agents/mgt_lead_kb115lt2_eval_fast.py')
    parser.add_argument('--output', type=Path, default=ROOT/'agents/mgt_lead_kb115lt2_runtime_fast.py')
    parser.add_argument('--expected-source-sha256', default=BASE_SHA256)
    args = parser.parse_args()
    assert args.source.resolve() != args.output.resolve()
    assert hashlib.sha256(args.source.read_bytes()).hexdigest() == args.expected_source_sha256
    args.output.write_text(transform(args.source.read_text(encoding='utf-8')), encoding='utf-8', newline='\n')
    print(hashlib.sha256(args.output.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
