"""Assemble an isolated, self-contained experimental continuation agent."""
import ast
import base64
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import zlib

ROOT = Path(__file__).resolve().parents[1]


def without_local_imports(source):
    tree = ast.parse(source)
    tree.body = [n for n in tree.body if not (
        isinstance(n, ast.ImportFrom) and (n.module or '').startswith(('fragments', 'cumulative_engine_profiles')) or
        isinstance(n, ast.Import) and any(a.name.startswith('fragments') for a in n.names))]
    return ast.unparse(tree)


def main():
    baseline = ROOT / 'agents/mgt_m1.py'
    folder = ROOT / 'results/fresh/continuation_executor'
    folder.mkdir(parents=True, exist_ok=True)
    sources = {'baseline': baseline.read_text(encoding='utf-8')}
    for name in ('continuation_executor', 'continuation_projection', 'continuation_calendar', 'continuation_control'):
        sources[name] = (ROOT / ('scripts/fragments/' + name + '.py')).read_text(encoding='utf-8')
    sources['base_helpers'] = (ROOT / 'scripts/fragments/segment_job_executor_v3.py').read_text(encoding='utf-8')
    engine = (ROOT / 'data/kaggriculture.py').read_text(encoding='utf-8').split('\njson_path =', 1)[0]
    engine = engine.replace('from kaggle_environments.utils import resolve_episode_seed',
                            'def resolve_episode_seed(env): return env.info.get("seed", 0)')
    sources['engine'] = engine
    nodes = json.loads((ROOT / 'results/fresh/segment_stitch/library.json').read_text(encoding='utf-8'))['segments']
    nodes = [{k: n[k] for k in ('id', 'day', 'start_shops', 'start_farm', 'jobs')} for n in nodes]
    for n in nodes:
        n['jobs'] = [{k: j[k] for k in ('day', 'hour', 'cmd', 'pre_tile') if k in j} for j in n['jobs']]
    blob = base64.b85encode(zlib.compress(json.dumps(nodes, separators=(',', ':')).encode(), 9)).decode()
    out = sources['baseline'] + '\n\n# Experimental state-based continuation; baseline source preserved.\n'
    out += 'from types import SimpleNamespace as _CT_NS\nimport base64 as _CT_B64, zlib as _CT_ZLIB, json as _CT_JSON\n'
    out += f'_CT_ENGINE_NS = {{"__file__": "embedded_kaggriculture.py"}}\nexec({engine!r}, _CT_ENGINE_NS)\n_CT_ENGINE = _CT_NS(**_CT_ENGINE_NS)\n'
    out += f'_CT_EXEC_NS = {{}}\nexec({sources["base_helpers"]!r}, _CT_EXEC_NS)\n'
    out += f'exec({without_local_imports(sources["continuation_executor"])!r}, _CT_EXEC_NS)\n_CT_EXEC = _CT_NS(**_CT_EXEC_NS)\n'
    out += f'_CT_PROJ_NS = {{"_CP_ENGINE": _CT_ENGINE}}\nexec({without_local_imports(sources["continuation_projection"])!r}, _CT_PROJ_NS)\n_CT_PROJ = _CT_NS(**_CT_PROJ_NS)\n'
    out += f'_CT_CAL_NS = {{"_CC_ENGINE": _CT_ENGINE}}\nexec({without_local_imports(sources["continuation_calendar"])!r}, _CT_CAL_NS)\n'
    out += '_CT_CTRL_NS = {"executor": _CT_EXEC, "projection": _CT_PROJ, "adapt_calendar": _CT_CAL_NS["adapt_calendar"]}\n'
    out += f'exec({without_local_imports(sources["continuation_control"])!r}, _CT_CTRL_NS)\n'
    out += f'_CT_NODES = _CT_JSON.loads(_CT_ZLIB.decompress(_CT_B64.b85decode({blob!r})))\n'
    out += '''
_CT_BASE = mgt_kaggle_entry
_CT_CONTROLLERS = {}
SEGMENT_REPORT = {}

def _ct_assets(farm):
    result = {}
    for row in farm['tiles']:
        for tile in row:
            if isinstance(tile, dict):
                p = tile.get('crop') or tile.get('animal')
                if p: result[p] = result.get(p, 0) + 1
    return result

def _ct_donor(obs):
    shops = obs['town']['unlocked_shops']
    assets = _ct_assets(obs['farms'][obs['player']])
    def score(n):
        b = _ct_assets(n['start_farm'])
        demand = sum(abs(shops.count(p) - n['start_shops'].count(p)) for p in _CT_ENGINE.SHOPS)
        board = sum(abs(assets.get(p, 0) - b.get(p, 0)) for p in set(assets) | set(b))
        return 100 * demand + 4 * board, n['id']
    candidates = [n for n in _CT_NODES if n['day'] == obs['day']]
    return min(candidates, key=score) if candidates else None

def continuation_entry(observation, configuration=None):
    player, step = int(observation['player']), int(observation['step'])
    if player not in _CT_CONTROLLERS or step == 0:
        _CT_CONTROLLERS[player] = _CT_CTRL_NS['ContinuationController']()
    control = _CT_CONTROLLERS[player]
    SEGMENT_REPORT.clear(); SEGMENT_REPORT.update(control.report)
    if observation['hour'] == 0 and observation['day'] in (12, 15, 18, 21, 24, 27):
        donor = _ct_donor(observation)
        if donor is not None: control.propose(observation, donor)
    if control.active:
        result = control.action(observation)
    else:
        result = _CT_BASE(observation, configuration)
    SEGMENT_REPORT.clear(); SEGMENT_REPORT.update(control.report)
    return result
'''
    target = ROOT / 'agents/mgt_continuation_dev.py'
    compile(out, str(target), 'exec')
    target.write_text(out, encoding='utf-8')
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from kaggle_environments.agent import get_last_callable
        function = get_last_callable(out, path=str(target))
    assert function.__name__ == 'continuation_entry'
    manifest = {'agent': str(target.relative_to(ROOT)), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                'bytes': target.stat().st_size, 'nodes': len(nodes),
                'sources': {k: hashlib.sha256(v.encode()).hexdigest() for k, v in sources.items()},
                'experimental': True, 'submitted': False}
    (folder / 'build.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest), flush=True)


if __name__ == '__main__': main()
