"""p2750 panel report: validity checks (CLAUDE.md task B) and the candidate-vs-baseline comparison
(task C.3), 2026-09-23.

Validity:
  (a) mgt_t10 replayed on the p2750 games that were OUR actual t10 games (source=='own_ladder',
      our_submission==56368334) must reproduce the recorded result to the dollar -- same harness
      check as scripts/ladder_panel.py's report(), restricted to the p2750 subset.
  (b) any game (any agent) whose run shows opp_dead > 40 is flagged: the fixed, recorded opponent
      script no longer makes sense once our build has changed the state enough (the harness's rule;
      here there is no natural per-episode baseline run for a game we were never in, so the absolute
      count is used instead of a paired difference).

Comparison: <candidate> vs <baseline> (default mgt_m1), paired on p2750 episodes both have, excluding
games where either build's run broke the opponent's tape (opp_dead diff > 40, the ladder_panel.py
convention) -- W-L, mean margin (95% CI), paired diff (95% CI), better/worse/same.

Usage: .venv/Scripts/python.exe scripts/report_p2750.py <candidate> [baseline=mgt_m1] [--validity-only agent1,agent2,...]
Merge remote results first: KGR_STAGE=... .venv/Scripts/python.exe scripts/kaggle_remote/merge_into_local.py <run>
"""
import gzip
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / 'results/fresh/ladder_panel'
P2750 = ROOT / 'data/ladder_panel/p2750'


def load_agent(agent):
    d = PANEL / agent
    if not d.exists():
        return {}
    return {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in d.glob('*.json')}


def ci(xs, n=10000, seed=7):
    if not xs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    k = len(xs)
    m = sorted(sum(rng.choices(xs, k=k)) / k for _ in range(n))
    return m[int(0.025 * n)], m[int(0.975 * n)]


def validity_t10(index):
    t10 = load_agent('mgt_t10')
    own_eps = [ep for ep, meta in index.items() if meta['source'] == 'own_ladder' and meta.get('our_submission') == 56368334]
    ok = bad = missing = 0
    for ep in own_eps:
        r = t10.get(ep)
        if r is None:
            missing += 1
            continue
        gp = P2750 / f'{ep}.json.gz'
        if not gp.exists():
            missing += 1
            continue
        g = json.loads(gzip.open(gp, 'rt', encoding='utf-8').read())
        seat = g['seat']
        recorded = g['rewards']
        if round(r['final']) == round(recorded[seat]) and round(r['rival']) == round(recorded[1 - seat]):
            ok += 1
        else:
            bad += 1
    print(f'validity (a) mgt_t10 on {len(own_eps)} own-t10 p2750 games: {ok} reproduce to the dollar, '
          f'{bad} MISMATCH, {missing} not yet run/found')
    return ok, bad, missing


def validity_opp_dead(agents):
    print('validity (b) opp_dead > 40 (opponent tape broken) per agent, absolute count:')
    for a in agents:
        rows = load_agent(a)
        eps = [ep for ep in rows if ep in INDEX]
        broken = [ep for ep in eps if rows[ep].get('opp_dead', 0) > 40]
        print(f'  {a:<20} {len(broken)}/{len(eps)} flagged' + (f'  e.g. {broken[:5]}' if broken else ''))


def compare(cand, base):
    C, B = load_agent(cand), load_agent(base)
    eps = sorted(set(C) & set(B) & set(INDEX))
    broken = {e for e in eps if C[e].get('opp_dead', 0) - B[e].get('opp_dead', 0) > 40
              or B[e].get('opp_dead', 0) - C[e].get('opp_dead', 0) > 40}
    ok = [e for e in eps if e not in broken]
    print(f'\n{cand} vs {base}: {len(eps)} paired p2750 episodes, {len(broken)} dropped (opponent tape broke)')
    if not ok:
        print('  no usable paired episodes yet')
        return
    m = [C[e]['margin'] for e in ok]
    lo, hi = ci(m)
    d = [C[e]['margin'] - B[e]['margin'] for e in ok]
    dlo, dhi = ci(d)
    print(f'  n={len(ok)}  W-L {sum(x>0 for x in m)}-{sum(x<0 for x in m)}  mean margin {sum(m)/len(m):+,.0f} ({lo:+,.0f}..{hi:+,.0f})')
    print(f'  paired diff {sum(d)/len(d):+,.0f} ({dlo:+,.0f}..{dhi:+,.0f})  better/worse/same '
          f'{sum(x>0 for x in d)}/{sum(x<0 for x in d)}/{sum(x==0 for x in d)}')
    by_source = {}
    for e in ok:
        by_source.setdefault(INDEX[e]['source'], []).append(e)
    for src, es in by_source.items():
        dd = [C[e]['margin'] - B[e]['margin'] for e in es]
        print(f'    [{src}] n={len(es)}  paired diff {sum(dd)/len(dd):+,.0f}')


def main():
    global INDEX
    index_path = P2750 / 'index.json'
    INDEX = json.loads(index_path.read_text(encoding='utf-8'))['games']
    args = sys.argv[1:]
    if args and args[0] == '--validity-only':
        agents = args[1].split(',')
        validity_t10(INDEX)
        validity_opp_dead(agents)
        return
    cand = args[0]
    base = args[1] if len(args) > 1 else 'mgt_m1'
    validity_t10(INDEX)
    validity_opp_dead(sorted({cand, base, 'mgt_t10'}))
    compare(cand, base)


if __name__ == '__main__':
    main()
