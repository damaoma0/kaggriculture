"""Kaggle-side runner for a ladder-panel shard (pushed by scripts/kaggle_remote/remote_panel.py).

The private dataset `yiyangxudmm/kaggriculture-panel-bundle` holds a trimmed copy of the repo (scripts, agents under
test, recorded ladder games, tape library). This kernel installs the pinned engine, unpacks the bundle into scratch
space (NOT /kaggle/working, so it is not saved as output), runs scripts/ladder_panel.py on the shard below and
copies only the per-game result files plus a timing record into /kaggle/working/out.
"""
import glob, json, os, platform, shutil, subprocess, sys, time, zipfile
from pathlib import Path

SHARD = {'agents': ['mgt_y3', 'mgt_m1_rebuild2'], 'submission': '56368334', 'episodes': ['110921861', '110923032', '110926193', '110927289', '110929542', '110934611', '110938272', '110939392', '110943802', '110945556', '110950384', '110956982', '110959188', '110959903', '110962484', '110963585', '110963800', '110965854', '110966967', '110969160', '110973546', '110975742', '110976828', '110977934', '110979032', '110981235', '110986740', '110992556', '111001477', '111050705', '111061861', '111069352', '111073763', '111079531', '111084752', '111105867', '111113509', '111137746', '111150914', '111159575', '111174074', '111174139', '111182088', '111183046', '111235175', '111239951', '111241026', '111247986', '111275874', '111279724', '111283246', '111295011', '111302438', '111349703', '111362566', '111374281', '111381831', '111386345', '111394080', '111398573', '111408302', '111437832', '111438214', '111443744', '111465956', '111479026', '111481434', '111487242', '111494792', '111501637', '111502736', '111513964', '111520505', '111529802', '111536131', '111542802', '111546996', '111554529', '111554912', '111564664', '111573876', '111574686', '111574938', '111579849', '111582496', '111591726', '111595826', '111599929', '111606235', '111616117', '111625952', '111629258', '111629503', '111638607', '111649661', '111650952', '111681195', '111697188', '111697276', '111712319', '111719171', '111721810', '111728874', '111735933', '111753736', '111758706', '111759161', '111764723', '111771903', '111777106', '111791271', '111791273', '111795661', '111818331', '111828437', '111829441', '111838599', '111846071', '111858516', '111858853', '111877555', '111901473', '111908370', '111910230', '111911086', '111918477', '111926090', '111945062', '111965197', '111970801', '111977997', '111990021', '111996384', '112004826', '112011453', '112015515', '112028499', '112039869', '112058755', '112078275', '112093957', '112098033', '112115594', '112120696', '112123353', '112133735', '112134828', '112142216', '112171785', '112181121', '112181990', '112187400', '112193616', '112196623', '112200803', '112207287', '112229900', '112247068', '112248887', '112254899', '112259762', '112261656', '112282761', '112293230', '112301654', '112308704', '112315139', '112358801', '112364883', '112373748', '112379913', '112393969', '112395209', '112408419', '112416042', '112424410', '112432936', '112446707', '112460119', '112462272'], 'workers': 4}          # filled in by remote_panel.py: {'agents': [...], 'submission': '...', 'episodes': [...], 'workers': 4}

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

# Kaggle decompresses uploaded .gz files; the harness reads data/*/<episode>.json.gz, so re-wrap them (same JSON)
import gzip
for sub in ('data/ladder_panel', 'data/mg_tapes'):
    for f in (work / sub).rglob('*.json'):
        with open(f, 'rb') as fi, gzip.open(str(f) + '.gz', 'wb') as fo:
            fo.write(fi.read())
        f.unlink()

env = dict(os.environ, LP_WORKERS=str(SHARD.get('workers', 4)), PYTHONUNBUFFERED='1')
t1 = time.time()
cmd = [sys.executable, 'scripts/ladder_panel.py', 'run', ','.join(SHARD['agents']), SHARD['submission'], ','.join(SHARD['episodes'])]
proc = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True)
t_run = time.time() - t1

out = Path('/kaggle/working/out')
out.mkdir(parents=True, exist_ok=True)
n = 0
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
            stdout_tail=[l for l in proc.stdout.splitlines() if 'margin' in l or 'games' in l or 'FAILED' in l][-60:],
            stderr_tail=proc.stderr.splitlines()[-30:])
(out / 'run_info.json').write_text(json.dumps(info, indent=1))
print(json.dumps({k: v for k, v in info.items() if k not in ('stdout_tail', 'stderr_tail')}, indent=1))
print('\n'.join(info['stdout_tail'][-10:]))
