"""Replay leader tape vs our season streams in the same world; record both players' SELL commits (price per unit) and
BUY_PRODUCT commits by day. usage: sales_replay.py team:ep arm_stream_dir,... -> JSON on stdout"""
import sys, json
sys.path.insert(0, r'C:\Users\xyygl\Documents\kaggriculture\scripts')
import upkeep_engine as UE
E = UE.engine()
orig = E._commit_unit
REC = {'w': None, 'seat': 0, 't': 0, 'log': None}


def hook(op, item, price, farm, private, market, shed_capacity=100):
    r = orig(op, item, price, farm, private, market, shed_capacity)
    w = REC['w']
    if r and w is not None and op in ('SELL', 'BUY_PRODUCT'):
        side = 'us' if farm is w.farms[REC['seat']] else 'opp'
        REC['log'].append((REC['t'], side, op, item, float(price)))
    return r


E._commit_unit = hook


def run(tape, stream_actions):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    REC.update(w=w, seat=seat, log=[])
    while w.t < 720:
        t = w.t
        REC['t'] = t
        if stream_actions is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream_actions[t] if t < len(stream_actions) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        opp = UE.tape_action(tape['opp_actions'], t)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, opp
        w.step(acts)
    fin = [float(w.farms[seat]['money']), float(w.farms[1 - seat]['money'])]
    log = REC['log']
    REC['w'] = None
    return fin, log


if __name__ == '__main__':
    game = sys.argv[1]
    team, ep = game.split(':')
    tape = UE.load_tape(team, int(ep))
    out = {'leader': dict(zip(('final', 'log'), run(tape, None)))}
    for d in sys.argv[2].split(','):
        s = json.load(open(rf'C:\Users\xyygl\Documents\kaggriculture\results\fresh\day12_viz\{d}_streams\{ep}.json'))
        out[d] = dict(zip(('final', 'log'), run(tape, s['actions'])))
    json.dump(out, sys.stdout)
