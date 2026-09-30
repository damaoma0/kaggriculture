"""Hire-reserve guard report: mgt_dsm_a vs mgt_dsm_a2 (= mgt_dsm_a + `hire_reserve=1`), both scored against t10's
own recorded ladder result on the same 180 worlds, decomposed by hire shortfall and router board-hamming, plus the
subset of worlds where the grafted-opening build mgt_o1r had an eligible day-6 handoff.

  report_dsm_guard.py [a=DIR] [a2=DIR] [o1r=DIR] [remote=<run>[@stage]] [remote=<run2>[@stage2]] ...

`a=`/`a2=` default to results/fresh/ladder_panel/mgt_dsm_a(2); `o1r=` defaults to
results/fresh/kaggle_remote/o1r/output. Each `remote=<run>` (optionally `@some/stage/dir`, default
results/fresh/kaggle_remote) is merged into results/fresh/ladder_panel/<agent>/<episode>.json first, keyed by each
result's own 'agent'/'episode' fields (same convention as report_opening_panel.py's `remote=`), so a freshly
fetched Kaggle panel (e.g. `remote_panel.py fetch dsma2` staged under KGR_STAGE) is picked up without a separate
copy step -- pass e.g. remote=dsma20@results/fresh/kaggle_remote_opening remote=dsma21@results/fresh/kaggle_remote_opening
for the two dsma2 shards.

"vs t10" = a world's (candidate margin) - (t10's own recorded margin = recorded[0] - recorded[1]); t10 reproduces
its own recorded ladder result to the dollar, so this isolates what the candidate does differently.

O1r "eligible day-6 handoff": mgt_o1r replays DSM's opening raw for days 0-5, then at day 6 the router either
switches to a library tape (a genuine handoff) or falls back and keeps playing the raw opening past day 6 because
no tape was within the router's hamming limit (`router.opening_fallback`). A world is "eligible" here when mgt_o1r's
own result has a `switches` entry at day 6 (`any(s[0] == 6 for s in switches)`); on this panel that coincides
exactly with `not router.opening_fallback` and gives 46/180 worlds (docs/new_opening_20260924.md's "46 worlds with
an eligible handoff (7-8 tiles)" -- one of the 46 has dist_d6 fractionally over 8, from the router's weighted score
rather than a raw tile count, so we do not additionally filter on dist_d6/hamming_max here).
"""
import json, random, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / 'results/fresh/ladder_panel'


def ci(xs, n=10000):
    if not xs:
        return (0, 0)
    rng = random.Random(7)
    m = sorted(sum(rng.choices(xs, k=len(xs))) / len(xs) for _ in range(n))
    return m[int(.025 * n)], m[int(.975 * n)]


def load_dir(d):
    p = Path(d)
    if not p.exists():
        return {}
    return {f.stem: json.loads(f.read_text(encoding='utf-8')) for f in p.glob('*.json')}


def merge_remote(spec):
    run, _, stage = spec.partition('@')
    stage_dir = ROOT / (stage or 'results/fresh/kaggle_remote')
    n = 0
    for f in (stage_dir / run / 'output').rglob('*.json'):
        if f.name == 'run_info.json' or f.parent.name.startswith('kgr-'):
            continue
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            continue
        if 'agent' not in d or 'episode' not in d:
            continue
        dst = PANEL / d['agent'] / f"{d['episode']}.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy(f, dst)
            n += 1
    print(f'merged {n} new files from remote run {run} ({stage_dir})')


def vs_t10(d):
    rec = d.get('recorded')
    if not rec:
        return None
    return d['margin'] - (rec[0] - rec[1])


def first_short_day(d):
    sd = d.get('hires', {}).get('short_days') or []
    return sd[0][0] if sd else None


def hamming_max(d):
    return (d.get('router') or {}).get('hamming_max')


def eligible_o1r(o1r_dir):
    out = set()
    p = Path(o1r_dir)
    if not p.is_dir():
        return out
    for f in p.glob('**/*.json'):
        if f.name == 'run_info.json':
            continue
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            continue
        ep = d.get('episode')
        if ep is None:
            continue
        sw = d.get('switches') or []
        has_day6 = any(s[0] == 6 for s in sw)
        fallback = bool((d.get('router') or {}).get('opening_fallback'))
        if has_day6 and not fallback:
            out.add(str(ep))
    return out


def report(name, results):
    rows = []
    for ep, d in results.items():
        v = vs_t10(d)
        if v is None:
            continue
        rows.append(dict(ep=ep, v=v, short=bool(d.get('hires', {}).get('short_days')),
                          first_short=first_short_day(d), ham=hamming_max(d)))
    if not rows:
        print(f'{name}: 0 results with a recorded field (nothing to report)')
        return {}
    vs = [r['v'] for r in rows]
    lo, hi = ci(vs)
    print(f"{name}: {len(rows)} worlds vs t10 recorded, mean {sum(vs) / len(vs):+,.0f} (95% CI {lo:+,.0f}..{hi:+,.0f})")
    noshort8 = [r['v'] for r in rows if not r['short'] and r['ham'] is not None and r['ham'] <= 8]
    short = [r['v'] for r in rows if r['short']]
    if noshort8:
        print(f"  no shortfall, board <= 8 tiles    n={len(noshort8):3d} mean {sum(noshort8) / len(noshort8):+,.0f}")
    if short:
        print(f"  hire shortfall (any day)          n={len(short):3d} mean {sum(short) / len(short):+,.0f}")
        by_day = {}
        for r in rows:
            if r['first_short'] is not None:
                by_day.setdefault(r['first_short'], []).append(r['v'])
        for day in sorted(by_day):
            vv = by_day[day]
            print(f"    first shortfall day {day:<3d}            n={len(vv):3d} mean {sum(vv) / len(vv):+,.0f}")
    return {r['ep']: r for r in rows}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    for a in sys.argv[1:]:
        if a.startswith('remote='):
            merge_remote(a[len('remote='):])
    kv = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a and not a.startswith('remote='))
    a_dir = kv.get('a', str(PANEL / 'mgt_dsm_a'))
    a2_dir = kv.get('a2', str(PANEL / 'mgt_dsm_a2'))
    o1r_dir = kv.get('o1r', str(ROOT / 'results/fresh/kaggle_remote/o1r/output'))

    A, A2 = load_dir(a_dir), load_dir(a2_dir)
    print(f'mgt_dsm_a: {len(A)} result files in {a_dir}')
    print(f'mgt_dsm_a2: {len(A2)} result files in {a2_dir}')
    ra = report('mgt_dsm_a', A)
    ra2 = report('mgt_dsm_a2', A2)

    common = sorted(set(ra) & set(ra2))
    if common:
        d = [ra2[e]['v'] - ra[e]['v'] for e in common]
        lo, hi = ci(d)
        print(f"mgt_dsm_a2 - mgt_dsm_a paired (both vs t10): n={len(common)} mean {sum(d) / len(d):+,.0f} "
              f"(95% CI {lo:+,.0f}..{hi:+,.0f}); better/worse/same "
              f"{sum(x > 0 for x in d)}/{sum(x < 0 for x in d)}/{sum(x == 0 for x in d)}")

    elig = eligible_o1r(o1r_dir)
    print(f"mgt_o1r eligible day-6 handoff: {len(elig)} worlds (see module docstring for the definition)")
    for name, rows in (('mgt_dsm_a', ra), ('mgt_dsm_a2', ra2)):
        sub = [rows[e]['v'] for e in rows if e in elig]
        if sub:
            lo, hi = ci(sub)
            print(f"  {name} on the O1r-eligible subset: n={len(sub):3d} mean {sum(sub) / len(sub):+,.0f} (95% CI {lo:+,.0f}..{hi:+,.0f})")


if __name__ == '__main__':
    main()
