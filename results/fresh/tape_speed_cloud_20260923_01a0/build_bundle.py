"""Assemble a small private notebook from verified, frozen research inputs."""
import ast
import base64
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import shutil
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
FROZEN=ROOT/'results/fresh/value_tape_ranker_20260923/fresh_scout'
PAYLOAD=HERE/'payload'
PAYLOAD.mkdir(exist_ok=True)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def copy(source, relative, expected=None):
    data=source.read_bytes()
    if expected is not None:
        assert sha(data)==expected, str(source)
    target=PAYLOAD/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)
    assert source.read_bytes()==data, f'Source changed while copying: {source}'


def canonical(value):
    if isinstance(value,dict): return {str(k):canonical(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [canonical(v) for v in value]
    if isinstance(value,set): return sorted((canonical(v) for v in value),key=str)
    return value


design=json.loads((FROZEN/'design.json').read_text())
names=['value_tape_search','value_tape_search_v2','value_tape_search_v3',
       'value_tape_search_v5','value_tape_search_v6','value_tape_search_v7','value_tape_search_v8',
       'rival_trajectory_model','rival_trajectory_model_v3','research_labour_profit',
       'test_labour_selfplay','cumulative_engine_profiles']
for rel in ['agents/mgt_m1.py', *[f'scripts/{n}.py' for n in names]]:
    copy(FROZEN/'sources'/rel,rel,design['hashes'][rel.replace('/','\\')])
copy(ROOT/'data/kaggriculture.py','data/kaggriculture.py')
for tag in ['rival_library','modern_rival_library']:
    rel=f'results/fresh/value_tape_followup_20260923/{tag}'
    source=ROOT/rel
    copy(source/'manifest.json',rel+'/manifest.json',design['hashes'][(rel+'/manifest.json').replace('/','\\')])
    manifest=json.loads((source/'manifest.json').read_text())
    for row in manifest['games']:
        if row['split']=='train':
            name=f'{row["episode"]}.json.gz'
            copy(source/name,rel+'/'+name)

# Preserve the exact installed engine/framework bytes. Do not import other
# environments on the cloud just to time this one. Report this cold-start scope.
package=ROOT/'.venv/Lib/site-packages/kaggle_environments'
for source in sorted(package.iterdir()):
    if source.is_file() and source.suffix in ('.py','.json'):
        copy(source,'vendor/kaggle_environments/'+source.name)
for name in ['kaggriculture.py','kaggriculture.json']:
    copy(package/'envs/kaggriculture'/name,'vendor/kaggle_environments/envs/kaggriculture/'+name)
assert (PAYLOAD/'data/kaggriculture.py').read_bytes()==(PAYLOAD/'vendor/kaggle_environments/envs/kaggriculture/kaggriculture.py').read_bytes()

specs=[('historical-111262874-12',12),('historical-111269605-15',15),
       ('historical-111287532-12',12),('generalization-0-v56',18),
       ('generalization-5-pasture',15),('generalization-4-sixday',18)]
audit={row['id']:row for row in json.loads((ROOT/'results/fresh/value_tape_ranker_20260923/dataset_audit.json').read_text())['rows']}
points=[]
origins=[]
for name,day in specs:
    source=ROOT/f'results/fresh/value_tape_ranker_20260923/checkpoints/{name}.pkl.gz'
    data=source.read_bytes()
    assert sha(data)==audit[name]['artifact_sha256']
    raw=pickle.loads(gzip.decompress(data))
    if isinstance(raw,dict):
        raw=raw['points'] if 'points' in raw else raw['checkpoints']
    matches=[p for p in raw if p['obs']['day']==day]
    assert len(matches)==1
    point=matches[0]
    expected={str(row['route']):[sha(json.dumps(canonical(p),sort_keys=True,separators=(',',':')).encode()) for p in row['predictions']]
        for row in point['decision']['candidates']}
    identifier=f'{name}-d{day}'
    points.append(dict(id=identifier,obs=point['obs'],memory=point['memory'],
        expected_selected=point['decision']['selected'],expected_forecasts=expected))
    origins.append(dict(id=identifier,day=day,expected_selected=point['decision']['selected'],source_sha256=sha(data)))
(PAYLOAD/'checkpoints.pkl.gz').write_bytes(gzip.compress(pickle.dumps(points,protocol=4),mtime=0))
copy(HERE/'cloud_benchmark.py','cloud_benchmark.py')
hashes={p.relative_to(PAYLOAD).as_posix():sha(p.read_bytes()) for p in sorted(PAYLOAD.rglob('*'))
        if p.is_file() and p != PAYLOAD/'manifest.json' and '__pycache__' not in p.parts}
manifest=dict(cases=origins,sha256=hashes,framework_snapshot='Installed local kaggle-environments 1.32.7, exact Python/schema/engine bytes; other environments and renderers omitted.',
    protocol='Six prespecified checkpoints, D12/D15/D18; one fresh process per case and policy, cold choose then two warm repeats; V7/V8 order alternated by case. Serial single-worker CPU. No forecast sharing. Full choose timing includes per-decision environment preparation, candidate search and validation. Cold includes runtime construction, imports reported separately. Warm 0.8-second deadline probe follows V8. No competition submission or time-budget certification.')
(PAYLOAD/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8',newline='\n')
with zipfile.ZipFile(HERE/'benchmark_bundle.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for relative in [*hashes,'manifest.json']:
        archive.write(PAYLOAD/relative,relative)
with zipfile.ZipFile(HERE/'benchmark_bundle.zip') as archive:
    assert len(archive.namelist()) == len(hashes)+1
    for relative in hashes:
        assert sha(archive.read(relative)) == hashes[relative]
encoded=base64.b64encode((HERE/'benchmark_bundle.zip').read_bytes()).decode()
bundle_sha=sha((HERE/'benchmark_bundle.zip').read_bytes())
setup='''import base64, hashlib, io, os, pathlib, zipfile
bundle = base64.b64decode(BUNDLE_BASE64)
assert hashlib.sha256(bundle).hexdigest() == BUNDLE_SHA256
root = pathlib.Path('/kaggle/working/tape_speed_01a0')
root.mkdir(exist_ok=True)
with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
    for info in archive.infolist():
        destination = (root / info.filename).resolve()
        assert destination.is_relative_to(root.resolve())
    archive.extractall(root)
print('Frozen benchmark unpacked:', BUNDLE_SHA256)
'''.replace('BUNDLE_BASE64',repr(encoded)).replace('BUNDLE_SHA256',repr(bundle_sha))
run="""import os, subprocess, sys
command = [sys.executable, '-u', '/kaggle/working/tape_speed_01a0/cloud_benchmark.py']
completed = subprocess.run(command)
assert completed.returncode == 0
"""
notebook=dict(nbformat=4,nbformat_minor=5,metadata=dict(kernelspec=dict(display_name='Python 3',language='python',name='python3')),cells=[
    dict(cell_type='markdown',metadata={},source=['# Frozen tape search CPU benchmark\n',
        'Private research benchmark: V7 versus V8. Six fixed checkpoints, cold plus two warm repeats.\n',
        'No competition submission. Source and input SHA256 checks run before every worker.\n',
        'The bundled 1.32.7 framework includes only Kaggriculture, so import timing excludes unrelated environments.\n']),
    dict(cell_type='code',execution_count=None,metadata=dict(jupyter=dict(source_hidden=True)),outputs=[],source=setup.splitlines(True)),
    dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=run.splitlines(True)),
    dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=["from IPython.display import FileLink, display\n","display(FileLink('/kaggle/working/cloud_results/summary.json'))\n"])])
(HERE/'tape_speed_benchmark.ipynb').write_text(json.dumps(notebook),encoding='utf-8')
print(json.dumps(dict(files=len(hashes),bundle_bytes=(HERE/'benchmark_bundle.zip').stat().st_size,
    notebook_bytes=(HERE/'tape_speed_benchmark.ipynb').stat().st_size,bundle_sha256=bundle_sha,cases=origins),indent=2))
