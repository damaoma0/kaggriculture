"""Run ladder-panel shards on Kaggle Notebooks (private) instead of the shared laptop.

  remote_panel.py bundle [agent ...]           build the repo bundle and create/version the private dataset
  remote_panel.py push <run> <agents> <submission> <episodes|@file.json> [shards=1] [workers=4]
  remote_panel.py status <run>
  remote_panel.py fetch <run>                  download outputs to results/fresh/kaggle_remote/<run>/
  remote_panel.py compare <run> [local_dir=results/fresh/ladder_panel]   dollar-exact check against local/recorded

Nothing public is created: the dataset and every kernel are private. Bundle = scripts, the named agents
(default: mgt_t10, mgt_m1, the frozen benchmark), data/ladder_panel, data/mg_tapes.
"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KAGGLE = str(ROOT / '.venv/Scripts/kaggle.exe')
USER = 'yiyangxudmm'
# a parallel thread sets KGR_DATASET / KGR_STAGE so its bundle versions never replace another thread's agents
DATASET = os.environ.get('KGR_DATASET', f'{USER}/kaggriculture-panel-bundle')
STAGE = ROOT / os.environ.get('KGR_STAGE', 'results/fresh/kaggle_remote')
TEMPLATE = Path(__file__).with_name('panel_kernel.py')


def sh(*args, check=True):
    p = subprocess.run([KAGGLE, *args], capture_output=True, text=True)
    if check and p.returncode:
        raise SystemExit(f'kaggle {" ".join(args)} failed:\n{p.stdout}\n{p.stderr}')
    return p.stdout + p.stderr


def bundle(agents):
    agents = agents or ['mgt_t10', 'mgt_m1', 'benchmark_frozen_56280048']
    d = STAGE / '_dataset'
    shutil.rmtree(d, ignore_errors=True)
    repo = d / 'repo'
    (repo / 'scripts').mkdir(parents=True)
    for f in (ROOT / 'scripts').glob('*.py'):
        shutil.copy(f, repo / 'scripts' / f.name)
    shutil.copytree(ROOT / 'scripts/fragments', repo / 'scripts/fragments', ignore=shutil.ignore_patterns('__pycache__'))
    (repo / 'agents').mkdir()
    for a in agents:
        shutil.copy(ROOT / 'agents' / f'{a}.py', repo / 'agents' / f'{a}.py')
    shutil.copytree(ROOT / 'data/ladder_panel', repo / 'data/ladder_panel', ignore=shutil.ignore_patterns('_raw'))
    shutil.copytree(ROOT / 'data/mg_tapes', repo / 'data/mg_tapes', ignore=shutil.ignore_patterns('_raw'))
    for extra in [x for x in os.environ.get('KGR_EXTRA', '').split(',') if x]:     # repo-relative files / dirs
        src = ROOT / extra
        if src.is_dir():
            shutil.copytree(src, repo / extra, ignore=shutil.ignore_patterns('__pycache__', '*.log'), dirs_exist_ok=True)
        else:
            (repo / extra).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, repo / extra)
    meta = dict(title=DATASET.split('/')[1], id=DATASET, licenses=[{'name': 'other'}])
    (d / 'dataset-metadata.json').write_text(json.dumps(meta))
    exists = sh('datasets', 'status', DATASET, check=False).strip().splitlines()[-1:] == ['ready']   # --mine listing lags
    if exists:
        print(sh('datasets', 'version', '-p', str(d), '-m', f'bundle {time.strftime("%Y-%m-%d %H:%M")}: {",".join(agents)}', '-r', 'zip'))
    else:
        print(sh('datasets', 'create', '-p', str(d), '-r', 'zip'))       # private by default


def push(run, agents, submission, episodes, shards=1, workers=4):
    if episodes.startswith('@'):
        eps = json.loads(Path(episodes[1:]).read_text())
    elif episodes == 'all':
        eps = sorted(p.name.split('.')[0] for s in submission.split(',') for p in (ROOT / 'data/ladder_panel' / s).glob('*.json.gz'))
    else:
        eps = episodes.split(',')
    code = TEMPLATE.read_text(encoding='utf-8')
    kernels = []
    for i in range(shards):
        part = eps[i::shards]
        slug = f'kgr-{run}-s{i}'.lower().replace('_', '-')
        kd = STAGE / run / f'kernel_s{i}'
        shutil.rmtree(kd, ignore_errors=True)
        kd.mkdir(parents=True)
        shard = dict(agents=agents.split(','), submission=submission, episodes=part, workers=workers)
        (kd / 'panel_kernel.py').write_text(code.replace('__SHARD__', repr(shard)), encoding='utf-8')
        (kd / 'kernel-metadata.json').write_text(json.dumps(dict(
            id=f'{USER}/{slug}', title=slug, code_file='panel_kernel.py', language='python', kernel_type='script',
            is_private=True, enable_gpu=False, enable_internet=True, dataset_sources=[DATASET],
            competition_sources=[], kernel_sources=[])))
        print(slug, len(part), 'games x', len(shard['agents']), 'agents:', sh('kernels', 'push', '-p', str(kd)).strip().splitlines()[-1])
        kernels.append(slug)
    (STAGE / run / 'kernels.json').write_text(json.dumps(dict(kernels=kernels, agents=agents, submission=submission,
                                                              pushed=time.time()), indent=1))


def pushcmd(run, cmd, collect):
    """One private kernel running `python <cmd...>` in the unpacked bundle; files matching the repo-relative globs in
    `collect` come back under output/<kernel>/out/repo/ (fetchcmd copies them into the repo where missing)."""
    code = TEMPLATE.read_text(encoding='utf-8')
    slug = f'kgr-{run}-s0'.lower().replace('_', '-')
    kd = STAGE / run / 'kernel_s0'
    shutil.rmtree(kd, ignore_errors=True)
    kd.mkdir(parents=True)
    shard = dict(cmd=cmd.split(), collect=collect.split(','), workers=4)
    (kd / 'panel_kernel.py').write_text(code.replace('__SHARD__', repr(shard)), encoding='utf-8')
    (kd / 'kernel-metadata.json').write_text(json.dumps(dict(
        id=f'{USER}/{slug}', title=slug, code_file='panel_kernel.py', language='python', kernel_type='script',
        is_private=True, enable_gpu=False, enable_internet=True, dataset_sources=[DATASET],
        competition_sources=[], kernel_sources=[])))
    print(slug, sh('kernels', 'push', '-p', str(kd)).strip().splitlines()[-1])
    (STAGE / run / 'kernels.json').write_text(json.dumps(dict(kernels=[slug], cmd=cmd, pushed=time.time()), indent=1))


def fetchcmd(run):
    fetch(run)
    n = 0
    for f in (STAGE / run / 'output').rglob('out/repo/**/*'):
        if f.is_file():
            rel = f.relative_to(next(p for p in f.parents if p.name == 'repo'))
            dst = ROOT / rel
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(f, dst)
                n += 1
    print(n, 'files merged into the repo')


def status(run):
    meta = json.loads((STAGE / run / 'kernels.json').read_text())
    for k in meta['kernels']:
        print(k, sh('kernels', 'status', f'{USER}/{k}', check=False).strip().splitlines()[-1])


def fetch(run):
    meta = json.loads((STAGE / run / 'kernels.json').read_text())
    for k in meta['kernels']:
        dst = STAGE / run / 'output' / k
        dst.mkdir(parents=True, exist_ok=True)
        print(k, sh('kernels', 'output', f'{USER}/{k}', '-p', str(dst), check=False).strip().splitlines()[-1:])


def compare(run, local_dir='results/fresh/ladder_panel'):
    rows = {}
    for f in (STAGE / run / 'output').rglob('*.json'):
        if f.name == 'run_info.json' or f.parent.name.startswith('kernel'):
            continue
        r = json.loads(f.read_text(encoding='utf-8'))
        rows[(r['agent'], str(r['episode']))] = r
    exact_local = exact_rec = n_local = n_rec = 0
    diffs = []
    for (agent, ep), r in sorted(rows.items()):
        lf = ROOT / local_dir / agent / f'{ep}.json'
        if lf.exists():
            l = json.loads(lf.read_text(encoding='utf-8'))
            n_local += 1
            ok = round(l['final']) == round(r['final']) and round(l['rival']) == round(r['rival'])
            exact_local += ok
            if not ok:
                diffs.append((agent, ep, 'local', l['final'] - r['final'], l['rival'] - r['rival']))
        if agent == 'mgt_t10':                        # t10 played these ladder games itself: must match the recording
            n_rec += 1
            ok = round(r['final']) == round(r['recorded'][0]) and round(r['rival']) == round(r['recorded'][1])
            exact_rec += ok
            if not ok:
                diffs.append((agent, ep, 'recorded', r['recorded'][0] - r['final'], r['recorded'][1] - r['rival']))
    infos = [json.loads(f.read_text()) for f in (STAGE / run / 'output').rglob('run_info.json')]
    print(f'{len(rows)} remote games; identical to local run: {exact_local}/{n_local}; t10 identical to its ladder recording: {exact_rec}/{n_rec}')
    for d in diffs[:10]:
        print('   DIFF', d)
    for i in infos:
        g = max(1, i['games'])
        print(f"   kernel: {i['games']} games in {i['run_seconds']:.0f} s ({60 * i['games'] / i['run_seconds']:.1f} games/min, "
              f"{i['run_seconds'] / g * i['shard']['workers']:.1f} s per game per worker), pip {i['pip_seconds']:.0f} s, "
              f"{i['cpus']} cpus {i['cpu_model']}, {i['mem_gb']} GB, python {i['python']}, engine {i['engine']}, rc {i['returncode']}")
        if i['returncode'] or not i['games']:
            print('   stderr:', '\n   '.join(i['stderr_tail'][-8:]))


if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'bundle':
        bundle(args)
    elif cmd == 'push':
        push(args[0], args[1], args[2], args[3], int(args[4]) if len(args) > 4 else 1, int(args[5]) if len(args) > 5 else 4)
    elif cmd == 'pushcmd':
        pushcmd(args[0], args[1], args[2])
    elif cmd == 'fetchcmd':
        fetchcmd(args[0])
    elif cmd == 'status':
        status(args[0])
    elif cmd == 'fetch':
        fetch(args[0])
    elif cmd == 'compare':
        compare(args[0], *args[1:])
