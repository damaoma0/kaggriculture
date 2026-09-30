"""Run ladder_panel.py with V9Y3_REPORT_DIR set, so packaged mgt_v9y3 logs every search (time, budget, choice).
usage: panel_with_v9log.py [--workers=N] <log_dir> <ladder_panel args...>"""
import os, runpy, sys
from pathlib import Path

args = sys.argv[1:]
if args and args[0].startswith('--workers='):
    os.environ['LP_WORKERS'] = args.pop(0).split('=', 1)[1]
sys.argv = [sys.argv[0]] + args
log = Path(sys.argv[1])
log.mkdir(parents=True, exist_ok=True)
os.environ['V9Y3_REPORT_DIR'] = str(log.resolve())
sys.argv = ['scripts/ladder_panel.py'] + sys.argv[2:]
runpy.run_path('scripts/ladder_panel.py', run_name='__main__')
