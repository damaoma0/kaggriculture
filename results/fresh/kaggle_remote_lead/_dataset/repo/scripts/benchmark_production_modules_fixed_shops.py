"""Diagnostic: active opponents, shops fixed to each baseline world's draws.

For the default engine a shop opens every three days; the ordered final shop
list therefore reconstructs the entire baseline sequence. Weed RNG remains
natural and both agents still react. This is not a natural Kaggle match.
"""
import json
from pathlib import Path
import sys
import benchmark_production_modules as B

RAW_RUN = B.run
SOURCE = B.ROOT / 'results/fresh/production_modules/integration'


def run(job):
    import tape_vs_bench as TV
    name, seed, seat, opponent, outpath = job
    baseline = json.loads((SOURCE / f'mgt_m1-{opponent}-{seed}-{seat}.json').read_text(encoding='utf-8'))
    shops = baseline['shops']
    by_day = [shops[:day // 3] for day in range(31)]
    original = TV._play
    def fixed(E, env, players, seat, shops_by_day, spawns, spawn_seat, record_seat, cushion=0):
        assert shops_by_day is None
        return original(E, env, players, seat, by_day, spawns, spawn_seat, record_seat, cushion)
    TV._play = fixed
    try:
        result = RAW_RUN(job)
    finally:
        TV._play = original
    result['shop_design'] = 'Fixed to natural baseline; active opponent, natural weeds'
    if name == 'mgt_m1':
        assert result['action_sha256'] == baseline['action_sha256'], 'baseline reconstruction changed actions'
        assert result['cash'] == baseline['cash'] and result['opponent_cash'] == baseline['opponent_cash']
    (Path(outpath) / f'{name}-{opponent}-{seed}-{seat}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    B.run = run
    assert '--out' in sys.argv, 'Use a separate output directory from the natural panel'
    output = B.ROOT / sys.argv[sys.argv.index('--out') + 1]
    assert output.resolve() != SOURCE.resolve()
    B.main()
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    manifest['design'] = 'Diagnostic: fixed baseline shops, active opponents, natural weeds, both seats'
    manifest['shop_source'] = str(SOURCE)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
