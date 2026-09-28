"""Build an isolated, exactly scored KB115LT2 polish-cache experiment.

Caches exist only inside one polish invocation. Random draws, move ordering,
iteration count and scoring arithmetic are unchanged. No original is edited.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA256 = "527d4c48b5d6bbef7854d430797e8691858724242d50eeec1e1636665ee124e7"


def transform(source: str) -> str:
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_tier_polish")
    lines = source.splitlines(keepends=True)
    original = "".join(lines[node.lineno - 1:node.end_lineno])
    patched = original.replace("    def stop_val(x, feeds):\n", "    def _stop_val_uncached(x, feeds):\n", 1)
    patched = patched.replace("    def seg_eval(sg, stops):\n", "    def _seg_eval_uncached(sg, stops):\n", 1)
    cache = '''    # Within this call, tiles, prices, day, CFG, fed0 and segment attributes
    # are fixed. Search proposals copy stops/operation lists; they never mutate
    # an operation dictionary. Final committing mutations occur after search.
    cache_enabled = bool(CFG.get("sd_polish_cache", 1))
    stop_values, segment_values, stop_keys = {}, {}, {}
    cache_limit = 8192

    def stop_key(x):
        saved = stop_keys.get(id(x))
        if saved is not None:
            return saved[1]
        # Every field read by _tier_eval/_tier_load/stop_val is represented.
        key = (x["tile"], x["rel"], bool(x.get("dawn")), bool(x.get("turn")),
               tuple((tuple(o["c"]), bool(o["m"])) for o in x["ops"]))
        if len(stop_keys) >= cache_limit:
            stop_keys.clear()
        # Retaining x prevents Python from recycling its identity in this map.
        stop_keys[id(x)] = (x, key)
        return key

    def stop_val(x, feeds):
        if not cache_enabled:
            return _stop_val_uncached(x, feeds)
        key = (stop_key(x), x["tile"] in feeds)
        value = stop_values.get(key)
        if value is None:
            value = _stop_val_uncached(x, feeds)
            if len(stop_values) >= cache_limit:
                stop_values.clear()
            stop_values[key] = value
        return value

    def seg_eval(sg, stops):
        if not cache_enabled:
            return _seg_eval_uncached(sg, stops)
        key = (id(sg), tuple(stop_key(x) for x in stops))
        value = segment_values.get(key)
        if value is None:
            value = _seg_eval_uncached(sg, stops)
            if len(segment_values) >= cache_limit:
                segment_values.clear()
            segment_values[key] = value
        return value

'''
    anchor = '    cur = [list(sg["stops"]) for sg in segs]\n'
    if patched.count(anchor) != 1 or patched == original:
        raise ValueError("Unexpected polish source; inspect before building")
    patched = patched.replace(anchor, cache + anchor)
    lines[node.lineno - 1:node.end_lineno] = [patched]
    result = "".join(lines)
    before = {n.name: ast.dump(n, include_attributes=False) for n in tree.body if isinstance(n, ast.FunctionDef)}
    after = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(result).body if isinstance(n, ast.FunctionDef)}
    changed = [name for name in before if before[name] != after[name]]
    if changed != ["_tier_polish"] or before.keys() != after.keys():
        raise AssertionError(changed)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "agents/mgt_lead_kb115lt2.py")
    parser.add_argument("--output", type=Path, default=ROOT / "agents/mgt_lead_kb115lt2_polishcache.py")
    parser.add_argument("--expected-source-sha256", default=BASE_SHA256,
                        help="Explicit hash when composing a separately reviewed experimental executor")
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        raise ValueError("The source executor must remain unchanged")
    source_bytes = args.source.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != args.expected_source_sha256:
        raise ValueError("Expected exact declared source; original KB115LT2 is the default")
    result = transform(source_bytes.decode("utf-8").replace("\r\n", "\n"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8", newline="\n")
    print(args.output)
    print(hashlib.sha256(args.output.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
