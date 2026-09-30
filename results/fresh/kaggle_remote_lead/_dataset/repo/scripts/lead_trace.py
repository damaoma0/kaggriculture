"""Trace mgt_lead in a G1 world: write our orders/actions/cash/shed for a step range to a file.
usage: lead_trace.py team:ep from_step to_step out_file [k=v,...]"""
import sys, json
sys.path.insert(0, 'scripts')
import lead_g1
game, a, b, outp = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
OUT = open(outp, 'w')
def P(*x):
    OUT.write(' '.join(map(str, x)) + '\n'); OUT.flush()
cfg = {}
if len(sys.argv) > 5 and sys.argv[5]:
    for kv in sys.argv[5].split(','):
        k, v = kv.split('=')
        try: v = json.loads(v)
        except Exception: pass
        cfg[k] = v
orig = lead_g1._load_agent
def wrapped(c):
    mod = orig(c)
    ag = mod.agent
    def tr(obs, config=None):
        act = ag(obs)
        t = int(obs['step'])
        if a <= t <= b:
            me = obs['player']; f = obs['farms'][me]; pv = obs['private']
            shed = {k: v for k, v in pv['shed'].items() if v}
            seeds = {k: v for k, v in pv['seeds'].items() if v}
            invs = [dict(i) for i in pv['inventories']]
            P(f"t={t} d{t//24}h{t%24} $={f['money']:.0f} shed={shed} seeds={seeds} hands={len(f['hands'])}")
            P(f"   mkt={act.get('market')}")
            P(f"   units={[act['farmer']] + act['hands']} pos={[f['farmer']]+f['hands']} inv={invs}")
        return act
    mod.agent = tr
    return mod
lead_g1._load_agent = wrapped
r = lead_g1.play(game, cfg)
print('final', r['final'], 'target', r['target'], 'ratio', round(r['ratio'], 3))
