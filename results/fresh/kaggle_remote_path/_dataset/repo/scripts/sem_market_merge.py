"""Stack the sem_market sell block onto another copy of the deploy agent (2026-09-24).

usage: sem_market_merge.py <src_deploy.py> <dst.py> [--default leader|sem]

Takes the SEM_MARKET SELL BLOCK and both call sites from agents/mgt_lead_deploy_sell.py and applies them to <src>
(e.g. a newer agents/mgt_lead_deploy.py with other changes), writing <dst>. Fails loudly if an anchor is missing.
The CFG default of sell_source becomes "sem" (or stays "leader" with --default leader).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / 'agents/mgt_lead_deploy_sell.py'

A_MARKET = 'def _market(S, obs, day, hour, money, shed, seeds, carried, invs, tasks, jobs, demand, prices,\n'
A_SITE1 = '    # shed overflow guard: midnight drop discards above 100\n'
SITE1 = ('    if CFG["sell_source"] == "sem":      # SEM_MARKET CALL SITE (see the SEM_MARKET SELL BLOCK above _market)\n'
         '        sells = _smk_sells(S, obs, T, d, shed, reserve, endgame)\n')
A_SITE2 = '    buys = wheat_buy + buys\n'
SITE2 = ('    if CFG["sell_source"] == "sem" and not endgame:   # SEM_MARKET CALL SITE 2 (wheat buy-ahead, lowest priority)\n'
         '        buys = buys + _smk_wheat_buys(obs, day, shed, carried, reserve, farm, cash, sells, buys)\n')
CFG_RE = re.compile(r'^    "sell_source": "[a-z]+",.*$', re.M)


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    default = 'leader' if '--default' in sys.argv and sys.argv[sys.argv.index('--default') + 1] == 'leader' else 'sem'
    ref = REF.read_text(encoding='utf-8')
    b0 = ref.index('# ===== BEGIN SEM_MARKET SELL BLOCK')
    b1 = ref.index('# ===== END SEM_MARKET SELL BLOCK')
    block = ref[b0:ref.index('\n', b1) + 1] + '\n\n'
    s = src.read_text(encoding='utf-8')
    assert 'SEM_MARKET SELL BLOCK' not in s, 'source already has the block'
    for a in (A_MARKET, A_SITE1, A_SITE2):
        assert s.count(a) == 1, f'anchor not unique/missing: {a!r}'
    s = s.replace(A_MARKET, block + A_MARKET)
    s = s.replace(A_SITE1, SITE1 + A_SITE1)
    s = s.replace(A_SITE2, A_SITE2 + SITE2)
    assert len(CFG_RE.findall(s)) == 1, 'CFG sell_source line not found'
    s = CFG_RE.sub(f'    "sell_source": "{default}",  # sem = scripts/fragments/sem_market.py hold-and-batch rule; '
                   f'leader = the deploy quota (sell on arrival); shed = G1 ablation rule', s)
    dst.write_text(s, encoding='utf-8', newline='')
    print(f'wrote {dst} (sell_source default {default})')


if __name__ == '__main__':
    main()
