"""Small notebook repair cell for the initially omitted library manifests."""
import base64
import gzip
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
payload=HERE/'payload'
missing={f'results/fresh/value_tape_followup_20260923/{name}/manifest.json':
    (payload/f'results/fresh/value_tape_followup_20260923/{name}/manifest.json').read_bytes().decode()
    for name in ('rival_library','modern_rival_library')}
encoded=base64.b64encode(gzip.compress(json.dumps(missing).encode(),mtime=0)).decode()
expected=hashlib.sha256((payload/'manifest.json').read_bytes()).hexdigest()
cell=f'''import base64, gzip, hashlib, json, pathlib, subprocess, sys
root=pathlib.Path('/kaggle/working/tape_speed_01a0')
missing=json.loads(gzip.decompress(base64.b64decode({encoded!r})))
manifest=json.loads((root/'manifest.json').read_text())
for name, text in missing.items():
    data=text.encode()
    (root/name).write_bytes(data)
    manifest['sha256'][name]=hashlib.sha256(data).hexdigest()
manifest['sha256']=dict(sorted(manifest['sha256'].items()))
(root/'manifest.json').write_text(json.dumps(manifest,indent=2))
assert hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()=={expected!r}
print('Repaired archive verified:', len(manifest['sha256']), 'files', flush=True)
completed=subprocess.run([sys.executable,'-u',str(root/'cloud_benchmark.py')])
assert completed.returncode==0
'''
(HERE/'repair_cell.py').write_text(cell)
print(cell)
