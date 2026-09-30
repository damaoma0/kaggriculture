"""Kaggle-side runner for a ladder-panel shard (pushed by scripts/kaggle_remote/remote_panel.py).

The private dataset `yiyangxudmm/kaggriculture-panel-bundle` holds a trimmed copy of the repo (scripts, agents under
test, recorded ladder games, tape library). This kernel installs the pinned engine, unpacks the bundle into scratch
space (NOT /kaggle/working, so it is not saved as output), runs scripts/ladder_panel.py on the shard below and
copies only the per-game result files plus a timing record into /kaggle/working/out.
"""
import glob, json, os, platform, shutil, subprocess, sys, time, zipfile
from pathlib import Path

SHARD = {'agents': ['mgt_t10', 'mgt_m1', 'mgt_y2', 'mgt_y3'], 'submission': 'p2750', 'episodes': ['110937191', '111374151', '111376633', '111416249', '111554912', '111577649', '111681195', '111688786', '111871547', '111902048', '111916514', '111941962', '111998078', '112015515', '112021872', '112047507', '112070938', '112093957', '112094437', '112109339', '112117326', '112135839', '112154311', '112158883', '112180322', '112181121', '112181990', '112184989', '112200188', '112204835', '112221082', '112248887', '112254899', '112268458', '112275685', '112285759', '112308704', '112335336', '112336696', '112344897', '112354214', '112364883', '112385217', '112393969', '112395209', '112397197', '112405922', '112408419', '112413049', '112424410', '112424741', '112445421', '112445954', '112446707', '112460119', '112462272', '112463244', '112465574', '112474113', '112474911', '112476470', '112479629', '112480041', '112483478', '112491552', '112496304', '112497197', '112502033', '112512725', '112531888', '112543358', '112543662', '112555452', '112576717', '112583218', '112590067', '112594170', '112600049', '112601882', '112603592', '112608187', '112610449', '112610455', '112610475', '112610620', '112610631', '112611706', '112611793', '112611839', '112611956', '112612486', '112612492', '112612703', '112612772', '112612775', '112612821', '112612822', '112612835', '112612877', '112612897', '112612929', '112612954', '112612960', '112612969', '112612971', '112612975', '112613169', '112613630', '112613720', '112613940', '112613947', '112613950', '112613972', '112614040', '112614194', '112614245', '112614526', '112614650', '112614774', '112614872', '112614959', '112615102', '112615104', '112615129', '112615133', '112615140', '112615282', '112615291', '112615422', '112615450', '112615472', '112615688', '112615698', '112615702', '112615774', '112615933', '112615951', '112616124', '112616127', '112616132', '112616172', '112616187', '112616218', '112616221', '112616224', '112616230', '112616238', '112616239', '112616240', '112616251', '112616252', '112616400', '112616410', '112616477', '112616493', '112616560', '112616587', '112616826', '112616871', '112616959', '112616960', '112617101', '112617154', '112617248', '112617268', '112617290', '112617393', '112617395', '112617409', '112617419', '112617511', '112617516', '112617560', '112617565', '112617587', '112617600', '112617602', '112617612', '112617640', '112617649', '112617667', '112617840', '112617854', '112618695', '112618817'], 'workers': 4}          # filled in by remote_panel.py: {'agents': [...], 'submission': '...', 'episodes': [...], 'workers': 4}

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
