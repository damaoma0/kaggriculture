"""O1 (leaders' opening + day-6 handoff) on the ladder panel: paired report against the full-library m1 build.

  report_opening_panel.py <candidate> [baseline=mgt_lib584] [remote=<run>]

Per world: margin difference, own/rival cash, the router's day-6 handoff (tape, tile Hamming, demand distance) and
whether the fallback (no tape within 8 tiles) fired, our no-effect commands (foreign tiles the tape does not know),
revenue / units by product, spend, and games where the recorded opponent's tape broke (opp no-effect +40).
Frozen opponent: the recorded moves cannot react to a different opening.
"""
import json, random, shutil, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / 'results/fresh/ladder_panel'


def ci(xs, n=10000):
    if not xs:
        return (0, 0)
    rng = random.Random(7)
    m = sorted(sum(rng.choices(xs, k=len(xs))) / len(xs) for _ in range(n))
    return m[int(.025 * n)], m[int(.975 * n)]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    cand = sys.argv[1]
    base = next((a for a in sys.argv[2:] if not a.startswith('remote=')), 'mgt_lib584')
    for a in sys.argv[2:]:
        if a.startswith('remote='):
            for f in (ROOT / 'results/fresh/kaggle_remote' / a[7:] / 'output').rglob('*.json'):
                if f.name == 'run_info.json' or f.parent.name.startswith('kgr-'):
                    continue
                dst = PANEL / f.parent.name / f.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dst.exists():
                    shutil.copy(f, dst)
    C = {f.stem: json.loads(f.read_text(encoding='utf-8')) for f in (PANEL / cand).glob('*.json')}
    B = {f.stem: json.loads(f.read_text(encoding='utf-8')) for f in (PANEL / base).glob('*.json')}
    eps = sorted(set(C) & set(B))
    rows = []
    for e in eps:
        c, b = C[e], B[e]
        sw = c.get('switches') or []
        d6 = next((s for s in sw if s[0] == 6), None)
        rows.append(dict(ep=e, d=c['margin'] - b['margin'], mc=c['margin'], mb=b['margin'], own=c['final'] - b['final'],
                         riv=c['rival'] - b['rival'], broken=c['opp_dead'] - b['opp_dead'] > 40,
                         ham6=d6[3] if d6 else None, dist6=d6[2] if d6 else None, tape6=d6[1] if d6 else None,
                         fallback=(c.get('router') or {}).get('opening_fallback', 0), dead=c['dead'] - b['dead'],
                         rev={k: c['revenue'].get(k, 0) - b['revenue'].get(k, 0) for k in set(c['revenue']) | set(b['revenue'])},
                         units={k: c['sold'].get(k, 0) - b['sold'].get(k, 0) for k in set(c['sold']) | set(b['sold'])},
                         spend={k: c['spend'].get(k, 0) - b['spend'].get(k, 0) for k in set(c['spend']) | set(b['spend'])},
                         short=bool(c['hires']['short_days']), short_b=bool(b['hires']['short_days']),
                         last=sw[-1][0] if sw else None))
    ok = [r for r in rows if not r['broken']]
    d = [r['d'] for r in ok]
    lo, hi = ci(d)
    print(f'{cand} vs {base}: {len(rows)} paired worlds, {len(rows) - len(ok)} dropped (opponent tape broke)')
    print(f"  W {sum(r['mb'] > 0 for r in ok)} -> {sum(r['mc'] > 0 for r in ok)}; paired margin {sum(d) / len(d):+,.0f} (95% CI {lo:+,.0f}..{hi:+,.0f}); "
          f"better/worse/same {sum(x > 0 for x in d)}/{sum(x < 0 for x in d)}/{sum(x == 0 for x in d)}; own {sum(r['own'] for r in ok) / len(ok):+,.0f}, "
          f"rival {sum(r['riv'] for r in ok) / len(ok):+,.0f}")
    hs = [r['ham6'] for r in ok if r['ham6'] is not None]
    print(f"  day-6 handoff: fallback (no tape within 8 tiles) in {sum(r['fallback'] for r in ok)} games; tile Hamming at handoff "
          f"median {sorted(hs)[len(hs) // 2] if hs else '-'}, max {max(hs) if hs else '-'}; distinct handoff tapes {len({r['tape6'] for r in ok})}")
    print(f"  no-effect commands vs baseline: {sum(r['dead'] for r in ok) / len(ok):+.0f} a game; hire-short games {sum(r['short'] for r in ok)} (baseline {sum(r['short_b'] for r in ok)})")
    for lab, key in (('revenue', 'rev'), ('units sold', 'units'), ('spend', 'spend')):
        tot = Counter()
        for r in ok:
            tot.update(r[key])
        print(f"  {lab} per game:", {k: round(v / len(ok), 1 if key == 'units' else 0) for k, v in sorted(tot.items(), key=lambda z: z[1]) if abs(v / len(ok)) >= (0.5 if key == 'units' else 20)})
    for lab, sel in (('handoff Hamming <= 6', lambda r: r['ham6'] is not None and r['ham6'] <= 6),
                     ('handoff Hamming 7-8', lambda r: r['ham6'] is not None and 7 <= r['ham6'] <= 8),
                     ('fallback / Hamming > 8', lambda r: r['fallback'] or (r['ham6'] or 0) > 8)):
        rs = [r for r in ok if sel(r)]
        if rs:
            dd = [r['d'] for r in rs]
            l2, h2 = ci(dd)
            print(f"  {lab:24s} n={len(rs):3d} paired {sum(dd) / len(dd):+7,.0f} ({l2:+,.0f}..{h2:+,.0f})")
    worst = sorted(ok, key=lambda r: r['d'])[:5]
    print('  five worst:', [(r['ep'], round(r['d']), r['ham6'], r['fallback']) for r in worst])
    print('  five best:', [(r['ep'], round(r['d']), r['ham6']) for r in sorted(ok, key=lambda r: -r['d'])[:5]])
    (ROOT / f'results/fresh/newphase_20260923/opening/panel_{cand}_vs_{base}.json').write_text(json.dumps(rows), encoding='utf-8')


if __name__ == '__main__':
    main()
