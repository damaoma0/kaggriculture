"""Copy fetched Kaggle remote-panel outputs (scripts/kaggle_remote/remote_panel.py `fetch`) into
results/fresh/ladder_panel/<agent>/<episode>.json, so the existing local report tools
(scripts/ladder_panel.py report, scripts/report_late_yarn_layer.py, scripts/scan_y2_wool_regressions.py)
can use them exactly like a local run's output. Reads from the run's OWN KGR_STAGE (not the shared
default), so it only ever adds new per-agent files under results/fresh/ladder_panel/<new-agent-name>/
and never touches another thread's files.

Usage: KGR_STAGE=results/fresh/kaggle_remote_y2 .venv/Scripts/python.exe scripts/kaggle_remote/merge_into_local.py <run>
"""
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / os.environ.get('KGR_STAGE', 'results/fresh/kaggle_remote')
LOCAL = ROOT / 'results/fresh/ladder_panel'


def main():
    run = sys.argv[1]
    n, agents = 0, set()
    for f in (STAGE / run / 'output').rglob('*.json'):
        if f.name == 'run_info.json':
            continue
        try:
            r = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        agent, ep = r.get('agent'), r.get('episode')
        if not agent or ep is None:
            continue
        dst = LOCAL / agent / f'{ep}.json'
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy(f, dst)
            n += 1
        agents.add(agent)
    print(f'merged {n} new files into {LOCAL} for agents {sorted(agents)}')


if __name__ == '__main__':
    main()
