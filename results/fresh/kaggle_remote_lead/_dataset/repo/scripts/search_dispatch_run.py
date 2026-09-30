"""Runner for the search-dispatch tests in leader worlds (Kaggle side; games never run on the shared laptop).

It plays agents/mgt_lead_search.py through scripts/lead_sem4.py's play() (the lead_g1 world: recorded seed, forced shop
sequence, the opponent's recorded actions, our executor in the leader's seat following the leader's exact plan; sem4's
REPRO arms reproduce lead_g1 / lead_ablation results to the dollar) because it records the metrics wanted here
(effective maintenance ops by type, moves, deaths, rot units, discards, per quadrant / day). Arms are injected into
lead_sem4.ARMS in memory and its output directory is redirected (the file is not edited):

  SDoff  dispatch_search off      (= the source mgt_lead.py decisions)     + EXEC_CFG
  SDsh   dispatch_search shadow   (greedy acts; must equal SDoff to the dollar)
  SDa12  dispatch_search active, sd_days [12, 23]
  SDall  dispatch_search active, every day
  (EXEC_CFG = p1_min_value 30, release_stale_d True, fert_hold 1: the deploy's executor defaults, as the G1 / sem4 runs)

usage: search_dispatch_run.py --arms SDoff,SDsh (--g1 | --games team:ep,... | --worlds FILE [--shard i/n])
                              [--workers 4] [--cfg 'k=v;k=v'] [--suffix X]
Results: results/fresh/search_dispatch_20260925/lead_worlds/<arm><suffix>/<ep>.json (+ manifest)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import lead_g1  # noqa: E402
import lead_sem4 as L4  # noqa: E402

AGENT = 'agents/mgt_lead_search.py'
EXEC = dict(L4.EXEC_CFG)
ARMS = {
    'SDoff': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='off')),
    'SDsh': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='shadow')),
    'SDa12': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active', sd_days=[12, 23])),
    'SDall': dict(kind='module', path=AGENT, cfg=dict(EXEC, dispatch_search='active')),
}


def main(argv):
    L4.ARMS.update(ARMS)
    L4.OUT = ROOT / 'results/fresh/search_dispatch_20260925/lead_worlds'
    out = []
    i = 0
    while i < len(argv):
        if argv[i] == '--g1':
            out += ['--games', ','.join(lead_g1.GAMES)]
            i += 1
        else:
            out.append(argv[i])
            i += 1
    L4.run(out)


if __name__ == '__main__':
    main(sys.argv[1:])
