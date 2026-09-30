"""Dump our animal tiles (bank, yield, unfed) at hour 23 of each day in a G1 world."""
import sys, json
sys.path.insert(0, 'scripts')
import lead_g1
game, outp = sys.argv[1], sys.argv[2]
days = int(sys.argv[3]) if len(sys.argv) > 3 else 8
OUT = open(outp, 'w')
orig = lead_g1._load_agent
def wrapped(c):
    mod = orig(c)
    ag = mod.agent
    def tr(obs, config=None):
        act = ag(obs)
        t = int(obs['step'])
        if t % 24 == 23 and t // 24 < days:
            f = obs['farms'][obs['player']]
            row = []
            for y in range(10):
                for x in range(10):
                    tl = f['tiles'][y][x]
                    if isinstance(tl, dict) and tl.get('animal'):
                        row.append(f"{tl['animal'][:2]}({x},{y}) fed{int(tl['fed_today'])} care{int(tl['cared_today'])} bank{tl.get('pending_care_bonus',0)} y{tl['yield_units']} uf{tl['consecutive_unfed']}")
            OUT.write(f"d{t//24} $={f['money']:.0f} shed={ {k:v for k,v in obs['private']['shed'].items() if v} }\n  " + "\n  ".join(row) + "\n")
        return act
    mod.agent = tr
    return mod
lead_g1._load_agent = wrapped
r = lead_g1.play(game, {})
print('final', r['final'], 'ratio', round(r['ratio'], 3))
