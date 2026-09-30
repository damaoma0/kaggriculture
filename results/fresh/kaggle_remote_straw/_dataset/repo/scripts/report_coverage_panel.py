"""Report the library-size coverage panel: paired margin of each library subset against the full-library
build (mgt_lib584 = mgt_m1 code) on the same frozen ladder worlds. Seed-free bootstrap over worlds."""
import json, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'results/fresh/ladder_panel'
OUT = ROOT / 'results/fresh/newphase_20260923'
ARMS = ['mgt_lib584', 'mgt_lib292', 'mgt_lib146', 'mgt_lib146b', 'mgt_lib073', 'mgt_lib036']
N = {'mgt_lib584': 584, 'mgt_lib292': 292, 'mgt_lib146': 146, 'mgt_lib146b': 146, 'mgt_lib073': 73, 'mgt_lib036': 36}


def ci(xs, n=10000, seed=7):
    rng = random.Random(seed); k = len(xs)
    m = sorted(sum(rng.choices(xs, k=k)) / k for _ in range(n))
    return m[int(.025 * n)], m[int(.975 * n)]


def main():
    worlds = json.loads((OUT / 'coverage_worlds.json').read_text())
    R = {a: {} for a in ARMS}
    for a in ARMS:
        for w in worlds:
            f = P / a / f'{w}.json'
            if f.exists():
                R[a][w] = json.loads(f.read_text(encoding='utf-8'))
    base = R['mgt_lib584']
    common = [w for w in worlds if w in base]          # each arm is paired with the control on its own overlap
    m1 = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in (P / 'mgt_m1').glob('*.json')}
    same = [w for w in common if w in m1]
    ident = sum(1 for w in same if round(m1[w]['margin']) == round(base[w]['margin']))
    print(f'worlds complete in all arms: {len(common)}; mgt_lib584 identical to cached mgt_m1 in {ident}/{len(same)}')
    out = {}
    print(f"{'arm':12s} {'N':>4s} {'n':>4s} {'W-L':>9s} {'mean margin':>12s} | {'paired vs 584 (95% CI)':>30s} {'b/w/s':>10s} | switches/game")
    for a in ARMS:
        ws = [w for w in common if w in R[a]]
        if not ws:
            continue
        m = [R[a][w]['margin'] for w in ws]
        d = [R[a][w]['margin'] - base[w]['margin'] for w in ws]
        lo, hi = ci(d) if any(d) else (0, 0)
        sw = sum(len(R[a][w].get('switches') or []) for w in ws) / len(ws)
        out[a] = dict(N=N[a], n=len(ws), wins=sum(x > 0 for x in m), losses=sum(x < 0 for x in m), mean=sum(m) / len(m),
                      paired=sum(d) / len(d), ci=[lo, hi], better=sum(x > 0 for x in d), worse=sum(x < 0 for x in d), switches=sw)
        print(f'{a:12s} {N[a]:>4d} {len(ws):>4d} {out[a]["wins"]:>4d}-{out[a]["losses"]:<4d} {out[a]["mean"]:>+12,.0f} | '
              f'{out[a]["paired"]:>+10,.0f} ({lo:>+7,.0f} to {hi:>+7,.0f}) {out[a]["better"]:>3d}/{out[a]["worse"]}/{len(ws) - out[a]["better"] - out[a]["worse"]} | {sw:.2f}')
    (OUT / 'coverage_panel_summary.json').write_text(json.dumps(out, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
