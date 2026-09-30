"""Kaggle-side runner for a ladder-panel shard (pushed by scripts/kaggle_remote/remote_panel.py).

The private dataset `yiyangxudmm/kaggriculture-panel-bundle` holds a trimmed copy of the repo (scripts, agents under
test, recorded ladder games, tape library). This kernel installs the pinned engine, unpacks the bundle into scratch
space (NOT /kaggle/working, so it is not saved as output), runs scripts/ladder_panel.py on the shard below and
copies only the per-game result files plus a timing record into /kaggle/working/out.
"""
import glob, json, os, platform, shutil, subprocess, sys, time, zipfile
from pathlib import Path

SHARD = {'agents': ['mgt_y3_cal'], 'submission': 'p2750', 'episodes': ['110937191', '111416249', '111681195', '111902048', '111998078', '112047507', '112094437', '112135839', '112180322', '112184989', '112221082', '112268458', '112308704', '112344897', '112385217', '112397197', '112413049', '112445421', '112460119', '112465574', '112476470', '112483478', '112497197', '112531888', '112555452', '112590067', '112601882', '112610449', '112610620', '112611793', '112612486', '112612772', '112612822', '112612897', '112612960', '112612975', '112613720', '112613950', '112614194', '112614650', '112614959', '112615129', '112615282', '112615450', '112615698', '112615933', '112616127', '112616187', '112616224', '112616239', '112616252', '112616477', '112616587', '112616959', '112617154', '112617290', '112617409', '112617516', '112617587', '112617612', '112617667', '112618695'], 'workers': 4}          # filled in by remote_panel.py: {'agents': [...], 'submission': '...', 'episodes': [...], 'workers': 4}

t0 = time.time()
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'kaggle-environments==1.32.7'], check=True)
t_pip = time.time() - t0

src = None
for cand in glob.glob('/kaggle/input/**/scripts/ladder_panel.py', recursive=True):
    src = Path(cand).parents[1]
    break
work = Path('/tmp/repo')
if src is not None:
    shutil.copytree(src, work, dirs_exist_ok=True)
else:
    zips = glob.glob('/kaggle/input/**/repo*.zip', recursive=True)
    assert zips, 'bundle not found under /kaggle/input'
    with zipfile.ZipFile(zips[0]) as z:
        z.extractall('/tmp')
    if not (work / 'scripts/ladder_panel.py').exists():          # zip may hold the repo contents at top level
        inner = next(Path('/tmp').rglob('scripts/ladder_panel.py')).parents[1]
        work = inner

# Kaggle decompresses uploaded .gz files. The bundle carries gz_manifest.txt, the list of every .gz it held; each
# is re-wrapped from its decompressed copy (same content), wherever it lives (ladder games, tapes, V9's libraries).
import gzip
listed = work / 'gz_manifest.txt'
todo = [work / l.strip()[:-3] for l in listed.read_text().splitlines() if l.strip()] if listed.exists() else     [f for sub in ('data/ladder_panel', 'data/mg_tapes') for f in (work / sub).rglob('*.json')]
restored = 0
for f in todo:
    if f.exists() and not Path(str(f) + '.gz').exists():
        with open(f, 'rb') as fi, gzip.open(str(f) + '.gz', 'wb') as fo:
            fo.write(fi.read())
        f.unlink()
        restored += 1
missing_gz = [str(f) for f in todo if not Path(str(f) + '.gz').exists()]
assert not missing_gz, f'gz files not restored: {missing_gz[:5]}'

env = dict(os.environ, LP_WORKERS=str(SHARD.get('workers', 4)), PYTHONUNBUFFERED='1')
t1 = time.time()
if SHARD.get('cmd'):
    # generic mode: any repo script; result files matching SHARD['collect'] (repo-relative globs) are returned
    cmd = [sys.executable] + list(SHARD['cmd'])
else:
    cmd = [sys.executable, 'scripts/ladder_panel.py', 'run', ','.join(SHARD['agents']), SHARD['submission'], ','.join(SHARD['episodes'])]
proc = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True)
t_run = time.time() - t1

out = Path('/kaggle/working/out')
out.mkdir(parents=True, exist_ok=True)
n = 0
if SHARD.get('cmd'):
    for pattern in SHARD.get('collect') or []:
        for f in work.glob(pattern):
            if f.is_file():
                dst = out / 'repo' / f.relative_to(work)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(f, dst)
                n += 1
else:
    for f in (work / 'results/fresh/ladder_panel').glob('*/*.json'):
        dst = out / f.parent.name
        dst.mkdir(exist_ok=True)
        shutil.copy(f, dst / f.name)
        n += 1
import kaggle_environments
info = dict(shard=SHARD, games=n, pip_seconds=t_pip, run_seconds=t_run, returncode=proc.returncode,
            cpus=os.cpu_count(), python=platform.python_version(), engine=getattr(kaggle_environments, '__version__', '?'),
            cpu_model=next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.startswith('model name')), '?'),
            mem_gb=round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 1e9, 1),
            stdout_tail=[l for l in proc.stdout.splitlines() if 'margin' in l or 'games' in l or 'FAILED' in l or 'completed' in l][-60:],
            stderr_tail=proc.stderr.splitlines()[-30:])
(out / 'run_info.json').write_text(json.dumps(info, indent=1))
print(json.dumps({k: v for k, v in info.items() if k not in ('stdout_tail', 'stderr_tail')}, indent=1))
print('\n'.join(info['stdout_tail'][-10:]))
