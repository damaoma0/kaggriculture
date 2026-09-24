"""G1 hold-one-out cells for the sem_market sell rule (2026-09-24).

Runs agents/mgt_lead_deploy_sell.py (a copy of mgt_lead_deploy.py whose only change is the SEM_MARKET SELL BLOCK) in
the 12 G1 leader worlds through scripts/lead_ablation.py's deploy adapter (mode 'full', this episode excluded from
retrieval), exactly like cell E2. Cells:
  SMK0   sell_source='leader'  (the deploy quota = sell on arrival; must reproduce E2)
  SMK    sell_source='sem'     (scripts/fragments/sem_market.py defaults)
  more cells: env SMK_EXTRA_CELLS='NAME[,NAME:leader,...]' (sem unless ':leader'); env SEM_MARKET_JSON overrides the
  module parameters for the whole run; env LEAD_DEPLOY_PATH picks another deploy copy (e.g. mgt_lead_deploy_sell_c1.py)
usage: sem_market_g1.py run CELL[,CELL] [--workers 2] [--games ep,...]   (waits for >= 3 GB free, at most 2 workers)
       sem_market_g1.py report CELL[,CELL...]
Results: results/fresh/lead_agent_20260924/abl_<CELL>/<ep>.json
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('LEAD_DEPLOY_PATH', str(ROOT / 'agents/mgt_lead_deploy_sell.py'))
sys.path.insert(0, str(ROOT / 'scripts'))
import lead_ablation as LA  # noqa: E402

LA.CELLS['SMK0'] = dict(cfg={'sell_source': 'leader'}, deploy='full')
LA.CELLS['SMK'] = dict(cfg={'sell_source': 'sem'}, deploy='full')
for _k in list(os.environ.get('SMK_EXTRA_CELLS', '').split(',')):   # NAME (sell_source sem) or NAME:leader
    if _k:
        _n, _, _src = _k.partition(':')
        LA.CELLS[_n] = dict(cfg={'sell_source': _src or 'sem'}, deploy='full')


def main():
    argv = sys.argv[1:]
    cmd, cells = argv[0], argv[1].split(',')
    if cmd == 'report':
        print(LA.report(cells))
        return
    workers, games = 2, LA.lead_g1.GAMES
    i = 2
    while i < len(argv):
        if argv[i] == '--workers':
            workers = int(argv[i + 1]); i += 2
        elif argv[i] == '--games':
            sel = argv[i + 1].split(',')
            games = [g for g in LA.lead_g1.GAMES if any(g.endswith(s) for s in sel)]
            i += 2
        else:
            i += 1
    import psutil
    import time
    while psutil.virtual_memory().available / 1e9 < 3.0:          # shared laptop: start only with >= 3 GB free
        print(f'waiting: {psutil.virtual_memory().available / 1e9:.2f} GB free', flush=True)
        time.sleep(30)
    avail = psutil.virtual_memory().available / 1e9
    workers = max(1, min(workers, 2, int((avail - 1.0) / 1.0)))
    print(f'{len(games) * len(cells)} games, {workers} workers ({avail:.1f} GB free)', flush=True)
    jobs = [(g, c) for c in cells for g in games]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for game, cell, ratio, err in pool.map(LA.job, jobs):
            print(cell, game, ratio if err is None else err.splitlines()[0], flush=True)
            if err:
                print(err, flush=True)
    print(LA.report(['E2', 'E2s'] + cells))


if __name__ == '__main__':
    main()
