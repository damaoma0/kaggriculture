"""Re-sync agents/mgt_lead_deploy.py with the E1 executor: copies agents/mgt_lead.py (or a given file) verbatim
between the EXECUTOR SECTION markers and keeps the DEPLOY section (target construction + entry point) unchanged.

usage: .venv/Scripts/python.exe scripts/resync_lead_deploy.py [executor_file=agents/mgt_lead.py]
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'agents/mgt_lead.py'
dst = ROOT / 'agents/mgt_lead_deploy.py'
ex = src.read_text(encoding='utf-8').rstrip('\n')
cur = dst.read_text(encoding='utf-8')
begin = cur.index('# ===== BEGIN EXECUTOR SECTION')
a = cur.index('\n', cur.index('\n', begin) + 1) + 1            # after the '# ====' line under the BEGIN marker
end = cur.index('# ===== END EXECUTOR SECTION')
b = cur.rindex('\n', 0, end - 1) + 1                            # the '# ====' line above the END marker
out = cur[:a] + ex + '\n\n\n' + cur[b:]
dst.write_bytes(out.encode('utf-8'))              # keep LF line endings
print(f'{dst.name}: executor section <- {src} ({len(ex.splitlines())} lines, sha256 '
      f'{hashlib.sha256(ex.encode()).hexdigest()[:16]}); remember to update the sha in the header docstring')
