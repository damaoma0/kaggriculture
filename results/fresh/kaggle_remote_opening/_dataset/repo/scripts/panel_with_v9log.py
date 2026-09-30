"""Run ladder_panel.py with V9Y3_REPORT_DIR set, so packaged mgt_v9y3 logs every search (time, budget, choice).
usage: panel_with_v9log.py <log_dir> <ladder_panel args...>"""
import os, runpy, sys
from pathlib import Path

log = Path(sys.argv[1])
log.mkdir(parents=True, exist_ok=True)
os.environ['V9Y3_REPORT_DIR'] = str(log.resolve())
sys.argv = ['scripts/ladder_panel.py'] + sys.argv[2:]
runpy.run_path('scripts/ladder_panel.py', run_name='__main__')
