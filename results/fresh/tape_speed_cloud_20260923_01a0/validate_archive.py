"""Validate the archive itself, independently of the staging directory."""
import os
from pathlib import Path
import subprocess
import sys
import zipfile

here=Path(__file__).resolve().parent
target=here/'archive_validation'
assert not target.exists(), 'Use a fresh validation directory'
with zipfile.ZipFile(here/'benchmark_bundle.zip') as archive:
    archive.extractall(target)
env=dict(os.environ)
env['PYTHONPATH']=str(here.parents[2]/'.venv/Lib/site-packages')
subprocess.run([sys.executable,str(target/'cloud_benchmark.py'),'--validate-only'],env=env,check=True)
