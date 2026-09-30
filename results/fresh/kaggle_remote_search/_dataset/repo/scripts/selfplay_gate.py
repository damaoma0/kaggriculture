"""Self-play acceptance gate: each candidate against the FROZEN current agent.

Acceptance is head-to-head win rate against agents/benchmark_frozen_56280048.py (the uploaded
submission 56280048), not absolute revenue: the V45 family is the bulk of the current ladder, so
beating our own deployed agent is the test that should translate.

Design
  - paired seeds, both seats: each seed contributes one game with the candidate in seat 0 and one
    in seat 1, on the same engine seed, so shop/weed draws are matched across seats.
  - both participants are loaded with Kaggle's own get_last_callable, so the benchmark plays
    exactly what the ladder plays.
  - every game must produce 720 states, terminal DONE for both seats, and a cash ledger that
    reconciles to the reward; otherwise the game is recorded as a failure and excluded loudly.
  - statistics cluster by seed (two seats of one seed are not independent): win rate and mean
    margin get a 95% bootstrap interval over seed clusters.

Usage: python selfplay_gate.py [tag] [candidate ...]
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import json, os, random, statistics as st, sys, time
from market_corpus import ROOT
from evaluate_boards import Ledger

OUT = ROOT / 'results/fresh/selfplay'
BENCH = ROOT / 'agents/benchmark_frozen_56280048.py'
BENCH_SHA = '07c313e53d390ab6e1dd563fa2059dd1ea78988af4e0df3f8bbe1c6d8085ea4f'
# The panel: GATE_RIVAL names the opponent file in agents/ (default: our frozen current agent). Each rival is
# reported separately; results against different rivals are never pooled.
RIVAL_NAME = os.environ.get('GATE_RIVAL', 'benchmark_frozen_56280048')
RIVAL = ROOT / 'agents' / f'{RIVAL_NAME}.py'
# GATE_SEED_BASE selects the seed block: 171000 was the development block used to diagnose the
# strawberry glut, so candidates derived from that diagnosis are gated on a later, unused block.
_SEED_BASE = int(os.environ.get('GATE_SEED_BASE', 171000))
SEEDS = list(range(_SEED_BASE, _SEED_BASE + int(os.environ.get('GATE_SEEDS', 16))))
BOOTSTRAP = 10000
CI_SEED = 20260917


def run(job):
    seed, seat, candidate = job
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E

    path = ROOT / 'agents' / f'{candidate}.py'
    source = path.read_text(encoding='utf-8')
    own = get_last_callable(source, path=str(path))
    # Record the exact agent bytes this game played: rebuilding a candidate mid-run would otherwise
    # silently mix versions inside one summary.
    candidate_sha = sha256(path.read_bytes()).hexdigest()
    rival = get_last_callable(RIVAL.read_text(encoding='utf-8'), path=str(RIVAL))
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
    times = [[], []]

    def wrap(fn, i):
        def act(obs):
            start = time.perf_counter()
            action = fn(obs)
            times[i].append(time.perf_counter() - start)
            return action
        return act

    players = [None, None]
    players[seat] = wrap(own, seat)
    players[1 - seat] = wrap(rival, 1 - seat)
    with Ledger(E) as ledger:
        env.run(players)
        assert len(env.steps) == 720 and all(s.status == 'DONE' for s in env.state), job
        for i in (0, 1):
            assert 3000 + sum(ledger.data[i]['revenue'].values()) - sum(ledger.data[i]['spend'].values()) \
                == env.state[i].reward, job
        ledgers = [dict(revenue=dict(ledger.data[i]['revenue']), sold_units=dict(ledger.data[i]['sold_units']),
                        spend=dict(ledger.data[i]['spend'])) for i in (0, 1)]
    cash = [env.state[i].reward for i in (0, 1)]
    row = dict(candidate=candidate, candidate_sha256=candidate_sha, rival=RIVAL_NAME,
               rival_sha256=sha256(RIVAL.read_bytes()).hexdigest(), seed=seed, seat=seat, cash=cash[seat], bench_cash=cash[1 - seat],
               margin=cash[seat] - cash[1 - seat], shops=list(env.steps[-1][0].observation.town.unlocked_shops),
               ledger_candidate=ledgers[seat], ledger_benchmark=ledgers[1 - seat],
               telemetry=getattr(own, 'sp_telemetry', {}),
               parent_diagnostics={k: v for k, v in (getattr(own, 'telemetry', {}) or {}).items()
                                   if v and any(t in k for t in ('error', 'shortfall', 'declin'))},
               max_seconds=[round(max(t), 3) if t else 0 for t in times])
    suffix = '' if RIVAL_NAME == 'benchmark_frozen_56280048' else f'-vs-{RIVAL_NAME}'
    (OUT / 'games' / f'{candidate}-{seed}-{seat}{suffix}.json').write_text(json.dumps(row, indent=1), encoding='utf-8')
    return row


def boot(clusters, fn, rounds=BOOTSTRAP):
    """95% percentile interval over resampled seed clusters."""
    rng = random.Random(CI_SEED)
    keys = list(clusters)
    draws = []
    for _ in range(rounds):
        pick = [clusters[rng.choice(keys)] for _ in keys]
        draws.append(fn([v for cluster in pick for v in cluster]))
    draws.sort()
    lo = draws[int(0.025 * len(draws))]
    hi = draws[int(0.975 * len(draws)) - 1]
    return round(lo, 1), round(hi, 1)


def summarise(rows, label):
    wins = sum(1 for r in rows if r['margin'] > 0)
    ties = sum(1 for r in rows if r['margin'] == 0)
    losses = sum(1 for r in rows if r['margin'] < 0)
    clusters = {}
    for r in rows:
        clusters.setdefault(r['seed'], []).append(r)
    win_ci = boot(clusters, lambda rs: 100.0 * sum(1 for r in rs if r['margin'] > 0) / len(rs))
    margin_ci = boot(clusters, lambda rs: st.mean(r['margin'] for r in rs))
    per_seed = {str(s): round(st.mean(r['margin'] for r in rs)) for s, rs in sorted(clusters.items())}
    shas = sorted({r.get('candidate_sha256') for r in rows})
    assert len(shas) == 1, f'{label}: games played {len(shas)} different builds: {shas}'
    out = dict(label=label, build_sha256=shas[0], games=len(rows), seeds=len(clusters), wins=wins, ties=ties, losses=losses,
               win_rate=round(100.0 * wins / len(rows), 1), win_rate_ci95=win_ci,
               mean_margin=round(st.mean(r['margin'] for r in rows), 1), margin_ci95=margin_ci,
               median_margin=st.median(r['margin'] for r in rows),
               mean_cash=round(st.mean(r['cash'] for r in rows)),
               mean_bench_cash=round(st.mean(r['bench_cash'] for r in rows)),
               seeds_positive=sum(1 for v in per_seed.values() if v > 0),
               per_seed_margin=per_seed,
               telemetry={k: sum(r['telemetry'].get(k, 0) for r in rows) for k in
                          {k for r in rows for k in r['telemetry']}},
               parent_diagnostics={k: sum(r['parent_diagnostics'].get(k, 0) for r in rows) for k in
                                   {k for r in rows for k in r['parent_diagnostics']}},
               max_seconds=max(max(r['max_seconds']) for r in rows))
    print(f"\n== {label}: {out['wins']}W-{out['ties']}T-{out['losses']}L over {out['games']} games "
          f"({out['seeds']} seeds, both seats)")
    print(f"   win rate {out['win_rate']}% (95% CI {win_ci[0]}-{win_ci[1]}%), "
          f"mean margin {out['mean_margin']:+.0f} (95% CI {margin_ci[0]:+.0f} to {margin_ci[1]:+.0f}), "
          f"median {out['median_margin']:+.0f}")
    print(f"   candidate cash {out['mean_cash']} vs benchmark {out['mean_bench_cash']}; "
          f"seeds with positive mean margin {out['seeds_positive']}/{out['seeds']}; "
          f"max agent call {out['max_seconds']}s")
    if out['telemetry']:
        print('   layer telemetry:', out['telemetry'])
    if out['parent_diagnostics']:
        print('   benchmark-layer errors/shortfalls under this change:', out['parent_diagnostics'])
    return out


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else 'gate'
    candidates = sys.argv[2:] or list(json.loads((OUT / 'candidates.json').read_text())['candidates'])
    actual = sha256(BENCH.read_bytes()).hexdigest()
    assert actual == BENCH_SHA, f'frozen benchmark changed: {actual}'
    (OUT / 'games').mkdir(parents=True, exist_ok=True)
    jobs = [(seed, seat, c) for c in candidates for seed in SEEDS for seat in (0, 1)]
    manifest = dict(tag=tag, started=time.strftime('%Y-%m-%d %H:%M:%S'), benchmark_sha256=BENCH_SHA,
                    rival=RIVAL_NAME, rival_sha256=sha256(RIVAL.read_bytes()).hexdigest(),
                    seeds=SEEDS, candidates=candidates, seed_base=_SEED_BASE,
                    design='Paired seeds and both seats against the frozen uploaded agent. Natural engine '
                           'RNG for shops and weeds. Seed-clustered bootstrap intervals. No tuning on these seeds.',
                    sources={f'agents/{c}.py': sha256((ROOT / 'agents' / f'{c}.py').read_bytes()).hexdigest()
                             for c in candidates})
    (OUT / f'manifest-{tag}.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    print(f'{len(jobs)} games: {len(candidates)} candidates x {len(SEEDS)} seeds x 2 seats', flush=True)
    rows, failures = [], []
    with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
        futures = {pool.submit(run, j): j for j in jobs}
        for f in as_completed(futures):
            job = futures[f]
            try:
                row = f.result()
                rows.append(row)
                print(f"  {row['candidate']} seed {row['seed']} seat {row['seat']}: "
                      f"{row['cash']:.0f} vs {row['bench_cash']:.0f} -> {row['margin']:+.0f}", flush=True)
            except Exception as exc:
                failures.append(dict(job=list(job), error=f'{type(exc).__name__}: {exc}'))
                print(f'  FAILED {job}: {type(exc).__name__}: {exc}', flush=True)
    summary = dict(manifest=manifest, failures=failures,
                   candidates={c: summarise([r for r in rows if r['candidate'] == c], c)
                               for c in candidates if any(r['candidate'] == c for r in rows)})
    if failures:
        print(f'\n{len(failures)} games FAILED and are excluded; see summary.')
    (OUT / f'summary-{tag}.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')
    print('\nwrote', OUT / f'summary-{tag}.json')


if __name__ == '__main__':
    main()
