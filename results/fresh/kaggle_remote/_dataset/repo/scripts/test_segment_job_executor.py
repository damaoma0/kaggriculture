"""Contract regressions. Production checks use validate_segment_executor.py."""
from fragments.segment_job_executor import segment_executor_start, segment_executor_action, _build_day


def observation():
    return {'player': 0, 'day': 12, 'hour': 0, 'step': 288,
            'farms': [{'money': 1000, 'farmer': [4, 4], 'hands': [], 'hires_today': 0,
                       'tiles': [[None for _ in range(10)] for _ in range(10)]}],
            'private': {'seeds': {'WHEAT': 1}, 'shed': {'SHEEP': 1}, 'inventories': [{}]},
            'market': {'prices': {'WHEAT': 20, 'FERTILIZER': 30}}}


def main():
    obs = observation()
    node = {'hire_to': 1, 'safety_assets': False, 'jobs': [
        {'day': 0, 'hour': 2, 'tile': [4, 3], 'cmd': ['PLANT', 'WHEAT']},
        {'day': 0, 'hour': 3, 'tile': [4, 3], 'cmd': ['WATER']},
        {'day': 0, 'hour': 4, 'tile': [5, 4], 'cmd': ['BUILD_PASTURE']},
        {'day': 0, 'hour': 5, 'tile': [5, 4], 'cmd': ['PLACE', 'SHEEP']}]}
    state = segment_executor_start(obs, node)
    assert state['ok'], state
    built, failure = _build_day(obs, state, 0)
    assert failure is None
    route = built['plan'][0]
    assert ['PICKUP', 'SHEEP', 1] in route
    assert route.index(['PICKUP', 'SHEEP', 1]) < route.index(['PLACE', 'SHEEP'])
    assert route.index(['PLANT', 'WHEAT']) < route.index(['WATER'])
    assert route.index(['BUILD_PASTURE']) < route.index(['PLACE', 'SHEEP'])
    assert len(built['scheduled']) == 4
    node['hire_to'] = 11
    state = segment_executor_start(obs, node)
    assert state['ok']
    assert segment_executor_action(obs, state)['market'] == [['HIRE']] * 10
    obs['farms'][0]['money'] = 0
    state = segment_executor_start(obs, node)
    assert not state['ok'] and state['failure']['reason'] == 'hire_budget_shortfall'
    assert not segment_executor_action(obs, state).get('market')
    print('Executor contract regressions passed')


if __name__ == '__main__': main()
