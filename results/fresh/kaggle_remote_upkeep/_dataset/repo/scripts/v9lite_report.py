"""Per-world table for the V9-lite sample: y3 and V9 (Kaggle p2750 panel), V9 and lite replayed locally, decisions.

usage: v9lite_report.py <lite_label> [<bench.json>]
  results/fresh/v9lite_20260924/phase1/        V9 games (agents/mgt_v9lite.py, V9LITE_ACT=v9) + their decisions
  results/fresh/v9lite_20260924/<lite_label>/  lite games + their decisions
  bench.json                                   same-checkpoint timings (scripts/v9lite_bench.py)
"""
import glob
import json
import statistics
import sys
from pathlib import Path

R = Path('results/fresh/v9lite_20260924')


def load(pattern):
    out = {}
    for f in glob.glob(pattern):
        d = json.load(open(f, encoding='utf-8'))
        out[int(d['episode'])] = d
    return out


def decisions(path, key):
    out = {}
    if not Path(path).exists():
        return out
    for line in open(path, encoding='utf-8'):
        r = json.loads(line)
        if key in r:
            out.setdefault(int(r['tag']), {})[r['step'] // 24] = (r[key]['selected'], r[key + '_seconds'])
    return out


def main():
    label = sys.argv[1]
    y3 = load('results/fresh/kaggle_remote_y2/p2750eval/output/*/out/mgt_y3/*.json')
    v9k = load('results/fresh/kaggle_remote/v9pb*/output/*/out/mgt_v9y3/*.json')
    v9l = load(str(R / 'phase1' / '*.json'))
    lite = load(str(R / label / '*.json'))
    dv9 = decisions(R / 'phase1' / 'v9lite_decisions.jsonl', 'v9')
    dli = decisions(R / label / 'v9lite_decisions.jsonl', 'lite')
    print(f"{'episode':>10} {'y3':>8} {'V9 kag':>8} {'V9 loc':>8} {'lite':>8} {'V9-y3':>7} {'lite-y3':>7}  V9 decisions (d:route)        lite decisions")
    gains = []
    for ep in sorted(lite):
        a, b = y3[ep]['margin'], v9k[ep]['margin']
        c = v9l.get(ep, {}).get('margin')
        e = lite[ep]['margin']
        gains.append((b - a, e - a))
        fmt = lambda d: ' '.join(f"{k}:{v[0]}" for k, v in sorted(d.items()))
        print(f"{ep:>10} {a:>8.0f} {b:>8.0f} {c if c is None else round(c):>8} {e:>8.0f} {b - a:>+7.0f} {e - a:>+7.0f}  "
              f"{fmt(dv9.get(ep, {})):<30} {fmt(dli.get(ep, {}))}")
    if gains:
        print('mean gain vs y3: V9 %+.0f  lite %+.0f  (n=%d)  kept %.0f%%' % (
            statistics.mean(g[0] for g in gains), statistics.mean(g[1] for g in gains), len(gains),
            100 * sum(g[1] for g in gains) / max(1e-9, sum(g[0] for g in gains))))
    secs = [v[1] for d in dli.values() for v in d.values()]
    if secs:
        per_game = [sum(v[1] for v in d.values()) for d in dli.values()]
        print('lite in-game seconds per decision: median %.2f max %.2f; per game median %.1f max %.1f' % (
            statistics.median(secs), max(secs), statistics.median(per_game), max(per_game)))
    if len(sys.argv) > 2:
        b = json.load(open(sys.argv[2], encoding='utf-8'))
        rows = b['rows']
        v9s = [r['v9']['seconds'] for r in rows]
        lis = [r['lite']['seconds'] for r in rows]
        agree = sum(r['v9']['selected'] == r['lite']['selected'] for r in rows)
        print('bench (same process, same %d checkpoints): V9 median %.2f max %.2f total %.1f | lite median %.2f max %.2f '
              'total %.1f | ratio %.3f | same decision %d/%d | runtime build %.2f s, first cold lite %.2f s' % (
                  len(rows), statistics.median(v9s), max(v9s), sum(v9s), statistics.median(lis), max(lis), sum(lis),
                  sum(lis) / sum(v9s), agree, len(rows), b['runtime_construct_s'], b.get('first_lite_cold_s', -1)))
        tv = sum(r['v9']['turns'] for r in rows)
        tl = sum(r['lite']['turns'] for r in rows)
        print('simulated turns: V9 %d lite %d (ratio %.3f); V9 s/1k turns %.2f, lite %.2f' % (
            tv, tl, tl / tv, 1000 * sum(r['v9']['rollout_s'] for r in rows) / tv,
            1000 * sum(r['lite']['rollout_s'] for r in rows) / max(1, tl)))
        st = {}
        for r in rows:
            for k, v in r['v9']['stages'].items():
                st.setdefault(k, [0, 0, 0])
                for i in range(3):
                    st[k][i] += v[i]
        other = sum(r['v9']['other_s'] for r in rows)
        print('V9 time by stage (s, rollouts, turns):', {k: [round(v[0], 1), v[1], v[2]] for k, v in st.items()},
              'other (shortlist/assess) %.1f' % other)
        for r in rows:
            if r['v9']['selected'] != r['lite']['selected']:
                print('  differs:', r['ckpt'], 'V9', r['v9']['selected'], 'lite', r['lite']['selected'])


if __name__ == '__main__':
    main()
