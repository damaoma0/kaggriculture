"""Post-hoc fixed-shop diagnostic of the natural-panel shop divergence."""
from contextlib import redirect_stdout, redirect_stderr
from hashlib import sha256
from copy import deepcopy
import gzip
import io
import json
import compare_live_labour as C


def main():
    seed = 226226
    parent = C.R.OUT / 'live_m1_wage_confirmation_v1'
    folder = C.R.OUT / 'live_m1_wage_shop_diagnostic'
    folder.mkdir(exist_ok=True)
    C.R.engine()
    from kaggle_environments import make
    source = parent / f'{seed}--1.actions.json.gz'
    actions = json.load(gzip.open(source, 'rt'))
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
        env.reset()
    shops = {0: deepcopy(env.state[0].observation.town.unlocked_shops)}
    for t in range(719):
        env.step([actions[s][t] for s in range(2)])
        if (t + 1) % 24 == 0:
            shops[(t + 1) // 24] = deepcopy(env.state[0].observation.town.unlocked_shops)
    baseline = json.loads((parent / f'{seed}--1.json').read_text())
    assert [s.reward for s in env.state] == baseline['cash']
    E = C.R.engine()
    original = E._end_of_day
    def forced(state, environment, day):
        original(state, environment, day)
        state[0].observation.town.unlocked_shops[:] = shops.get(day + 1, shops[max(shops)])
    # Projections install held shops themselves after interpreter, so this hook
    # affects the evaluator world only; decision input remains observation-only.
    E._end_of_day = forced
    try:
        rows = [C.run((seed, s, str(folder))) for s in (0, 1)]
    finally:
        E._end_of_day = original
    result = dict(label='Post-hoc diagnostic only; excluded from primary confirmation', seed=seed,
                  source_sha256=sha256(source.read_bytes()).hexdigest(), script_sha256=sha256(C.Path(__file__).read_bytes()).hexdigest(),
                  shops=shops, baseline_cash=baseline['cash'],
                  treated=[dict(seat=r['treatment'], cash=r['cash'],
                                own_gain=r['cash'][r['treatment']]-baseline['cash'][r['treatment']],
                                margin=r['cash'][r['treatment']]-r['cash'][1-r['treatment']]) for r in rows])
    (folder / 'summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
