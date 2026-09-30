"""Private, isolated Kaggle bundle and launch helper for the semantic tile mission.

bundle: freezes current required inputs, without touching any other cloud bundle.
push RUN ARMS [SHARDS=2] [PANEL]: runs the panel (default forty DSM worlds).
status/fetch RUN: use the established remote transport; fetch never overwrites.
"""
import copy
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MISSION = Path('results/fresh/semantic_tile_20260928')
STAGE = Path('results/fresh/kaggle_remote_semantic_tile_20260928')
os.environ['KGR_STAGE'] = STAGE.as_posix()
os.environ['KGR_DATASET'] = 'yiyangxudmm/kaggriculture-semantic-tile-20260928'
sys.path.insert(0, str(Path(__file__).resolve().parent))
import remote_panel as RP


def bundle():
    # A fresh version uses a fresh staging directory. No recursive deletion and
    # no change to frozen directories used by previous uploaded versions.
    version = 1
    while (ROOT / STAGE / f'dataset_v{version}').exists():
        version += 1
    stage = ROOT / STAGE / f'dataset_v{version}'
    repo = stage / 'repo'
    repo.mkdir(parents=True)
    files = list((ROOT / 'scripts').glob('*.py'))
    files += list((ROOT / 'scripts/fragments').glob('*.py'))
    for p in ('agents/mgt_lead_kb115lt.py', 'results/fresh/xfix_20260925/worlds42.json',
              'results/fresh/tile_plans/dsm40.json', 'results/fresh/threads_20260928/panel_dsm40b.txt',
              'results/fresh/threads_20260928/dsm_sell_pace_folds.json'):
        files.append(ROOT / p)
    files += list((ROOT / 'results/fresh/threads_20260928').glob('dsm_sell_pace_f[0-9].json'))
    files += list((ROOT / MISSION).glob('spec*.json'))
    files += list((ROOT / MISSION / 'plans').glob('*.json'))
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().strip().split(',')
    for game in games:
        team, ep = game.split(':')
        files.append(ROOT / f'data/leader_semantics/{team}/{ep}.json.gz')
        files.append(next(iter(sorted((ROOT / 'data/leader_tapes').glob(f'{team}_*/{ep}.json.gz')))))
    manifest = {}
    for src in sorted(set(files)):
        rel = src.relative_to(ROOT)
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        manifest[rel.as_posix()] = hashlib.sha256(src.read_bytes()).hexdigest()
    (repo / MISSION / f'bundle_v{version}_manifest.json').write_text(json.dumps(manifest, indent=2))
    (ROOT / MISSION / f'bundle_v{version}_manifest.json').write_text(json.dumps(manifest, indent=2))
    (repo / 'gz_manifest.txt').write_text('\n'.join(p.relative_to(repo).as_posix() for p in repo.rglob('*.gz')))
    meta = dict(title=RP.DATASET.split('/')[1], id=RP.DATASET, licenses=[{'name': 'other'}])
    (stage / 'dataset-metadata.json').write_text(json.dumps(meta))
    exists = RP.sh('datasets', 'status', RP.DATASET, check=False).strip().splitlines()[-1:] == ['ready']
    if exists:
        print(RP.sh('datasets', 'version', '-p', str(stage), '-m', f'Semantic tile frozen inputs version {version}', '-r', 'zip'))
    else:
        print(RP.sh('datasets', 'create', '-p', str(stage), '-r', 'zip'))
    print('Frozen bundle', version, len(manifest), 'files', flush=True)


def push(run, arms, shards=2, panel='results/fresh/threads_20260928/panel_dsm40b.txt'):
    panel_file = ROOT / panel
    games = panel_file.read_text().strip().split(',') if panel_file.exists() else panel.split(',')
    for i in range(shards):
        part = games[i::shards]
        name = f'sem28-{run}-{i}'
        out = (MISSION / 'runs' / run / f'shard{i}').as_posix()
        cmd = ' '.join(['scripts/semantic_tile_20260928_run.py', '--spec', (MISSION / 'spec.json').as_posix(),
                        '--arms', arms, '--games', ','.join(part), '--out', out, '--workers', '4'])
        if os.environ.get('ST28_NO_TIMEOUT') == '1':
            cmd += ' --no-timeout'
        collect = [f'{out}/**/*']
        collect += [f'results/fresh/day12_viz/{arm.lower()}_streams/*.json' for arm in arms.split(',')]
        RP.pushcmd(name, cmd, ','.join(collect))
    (ROOT / STAGE / f'{run}_shards.json').write_text(json.dumps([f'sem28-{run}-{i}' for i in range(shards)]))


if __name__ == '__main__':
    command, args = sys.argv[1], sys.argv[2:]
    if command == 'bundle':
        bundle()
    elif command == 'push':
        push(args[0], args[1], int(args[2]) if len(args) > 2 else 2,
             args[3] if len(args) > 3 else 'results/fresh/threads_20260928/panel_dsm40b.txt')
    else:
        names = json.loads((ROOT / STAGE / f'{args[0]}_shards.json').read_text())
        for name in names:
            if command == 'status':
                RP.status(name)
            elif command == 'fetch':
                RP.fetchcmd(name)
