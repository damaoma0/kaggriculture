"""Late-Yarn service layer: paired ladder-panel report.

  report_late_yarn_layer.py <candidate> [baseline=mgt_lib584] [remote_run=...]

Pairs the candidate with the baseline (mgt_lib584 = mgt_m1 code with the full library) world by world on the frozen
ladder worlds, and splits the difference by the late-Yarn mismatch between the world and the FINAL tape the
BASELINE followed (world minus tape, shops 5-8). Also reports the collision checks: games where the existing sheep
expansion commits (overlay 'commitments') in either build, games with a hire shortfall, activations of the new
branch ('yarn_service'), and games where the opponent's recorded tape breaks (its no-effect commands rise by >40).
Remote results (scripts/kaggle_remote) are merged into results/fresh/ladder_panel/<agent>/ first.
"""
import gzip, json, random, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / 'results/fresh/ladder_panel'


def seq(sh):
    out, seen = [], 0
    for cur in sh:
        while len(cur) > seen:
            out.append(cur[seen]); seen += 1
    return out[:8]


def ci(xs, n=10000):
    if not xs:
        return (0, 0)
    rng = random.Random(7)
    m = sorted(sum(rng.choices(xs, k=len(xs))) / len(xs) for _ in range(n))
    return m[int(.025 * n)], m[int(.975 * n)]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    cand = sys.argv[1]
    base = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('remote=') else 'mgt_lib584'
    for a in sys.argv[2:]:
        if a.startswith('remote='):
            for f in (ROOT / 'results/fresh/kaggle_remote' / a[7:] / 'output').rglob('*.json'):
                if f.name == 'run_info.json' or f.parent.name.startswith('kgr-'):
                    continue
                dst = PANEL / f.parent.name / f.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dst.exists():
                    shutil.copy(f, dst)
    tape_shops = {}
    for p in (ROOT / 'data/mg_tapes').rglob('*.json.gz'):
        g = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        tape_shops[g['episode']] = seq(g['shops'])
    world = {}
    for p in (ROOT / 'data/ladder_panel').rglob('*.json.gz'):
        g = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        world[str(g['episode'])] = seq(g['shops'])
    C = {f.stem: json.loads(f.read_text(encoding='utf-8')) for f in (PANEL / cand).glob('*.json')}
    B = {f.stem: json.loads(f.read_text(encoding='utf-8')) for f in (PANEL / base).glob('*.json')}
    eps = sorted(set(C) & set(B))
    rows = []
    for e in eps:
        c, b = C[e], B[e]
        final = (b.get('switches') or [[0, None]])[-1][1]
        ts = tape_shops.get(final) or []
        ws = world.get(e) or []
        wl = sum(s == 'YARN_STORE' for s in ws[4:])
        tl = sum(s == 'YARN_STORE' for s in ts[4:]) if ts else None
        rows.append(dict(ep=e, d=c['margin'] - b['margin'], mc=c['margin'], mb=b['margin'], own=c['final'] - b['final'],
                         riv=c['rival'] - b['rival'], wl=wl, mis=(wl - tl) if tl is not None else None,
                         yarn_any='YARN_STORE' in ws, fired=(c.get('overlay') or {}).get('yarn_service', 0),
                         exp_c=(c.get('overlay') or {}).get('commitments', 0), exp_b=(b.get('overlay') or {}).get('commitments', 0),
                         short=bool(c['hires']['short_days']), short_b=bool(b['hires']['short_days']),
                         broken=c['opp_dead'] - b['opp_dead'] > 40,
                         wool=(c.get('sold') or {}).get('WOOL', 0) - (b.get('sold') or {}).get('WOOL', 0),
                         wool_rev=(c.get('revenue') or {}).get('WOOL', 0) - (b.get('revenue') or {}).get('WOOL', 0),
                         spend=sum((c.get('spend') or {}).values()) - sum((b.get('spend') or {}).values())))
    ok = [r for r in rows if not r['broken']]

    def line(lab, rs):
        if not rs:
            return
        d = [r['d'] for r in rs]
        lo, hi = ci(d)
        wins_c, wins_b = sum(r['mc'] > 0 for r in rs), sum(r['mb'] > 0 for r in rs)
        print(f"{lab:34s} n={len(rs):3d}  W {wins_b:3d} -> {wins_c:3d}  paired {sum(d) / len(d):+7,.0f} ({lo:+,.0f}..{hi:+,.0f})  "
              f"b/w/s {sum(x > 0 for x in d)}/{sum(x < 0 for x in d)}/{sum(x == 0 for x in d)}  own {sum(r['own'] for r in rs) / len(rs):+,.0f} "
              f"rival {sum(r['riv'] for r in rs) / len(rs):+,.0f}  wool units {sum(r['wool'] for r in rs) / len(rs):+.1f} "
              f"rev {sum(r['wool_rev'] for r in rs) / len(rs):+,.0f}  spend {sum(r['spend'] for r in rs) / len(rs):+,.0f}")
    print(f'{cand} vs {base}: {len(rows)} paired worlds, {len(rows) - len(ok)} dropped (opponent tape broke)')
    line('ALL', ok)
    line('any Yarn Store in the world', [r for r in ok if r['yarn_any']])
    line('no Yarn Store in the world', [r for r in ok if not r['yarn_any']])
    line('late Yarn: world has MORE than tape', [r for r in ok if (r['mis'] or 0) > 0])
    line('late Yarn: equal', [r for r in ok if r['mis'] == 0])
    line('late Yarn: world has FEWER', [r for r in ok if (r['mis'] or 0) < 0])
    line('layer fired (yarn_service > 0)', [r for r in ok if r['fired']])
    print('collision checks:')
    line('  expansion commits (either build)', [r for r in ok if r['exp_c'] or r['exp_b']])
    print(f"  expansion games: baseline {sum(1 for r in ok if r['exp_b'])}, candidate {sum(1 for r in ok if r['exp_c'])}; "
          f"hire-short games: baseline {sum(r['short_b'] for r in ok)}, candidate {sum(r['short'] for r in ok)}; "
          f"layer activations: {sum(r['fired'] for r in ok)} in {sum(1 for r in ok if r['fired'])} games")
    worst = sorted(ok, key=lambda r: r['d'])[:5]
    print('  five worst:', [(r['ep'], round(r['d']), r['mis'], r['fired'], r['exp_c']) for r in worst])
    (ROOT / f'results/fresh/newphase_20260923/layer_{cand}_vs_{base}.json').write_text(json.dumps(rows), encoding='utf-8')


if __name__ == '__main__':
    main()
