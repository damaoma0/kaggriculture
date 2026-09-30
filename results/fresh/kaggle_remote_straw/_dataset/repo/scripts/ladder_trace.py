"""Trace one of OUR ladder games from its Kaggle replay: did something break, or was it a bad tape match?

usage: ladder_trace.py <replay.json> [agent_file=submissions/2026-09-19-mgt_t10/main.py] [team="Ghost Rule"] [--brief]

1. Header: teams, seats, rewards, seed, shops; agent status / overage time.
2. Reproduction: the submitted file is fed the recorded observations; its actions must equal the recorded ones
   (a mismatch = timeout, crash fallback or nondeterminism). Router history and overlay telemetry come from that run.
3. Failures read off the observations: commands with no effect (classifier of mgt_dead.py), HIRE orders that did not
   produce a hand, order lists over the 10-order cap, animals that disappeared, lowest cash.
4. Tape match: the final tape's world against this world (shops), board Hamming distance by day, and our cash by day
   against the cash of the tape's ORIGINAL game (what the same tape does when it works).
5. Exact ledger of both sides by re-running the recorded actions from the seed (final cash must reproduce).
Writes results/fresh/ladder_t10/trace_<episode>.json
"""
import glob
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from mgt_dead import classify                                         # noqa: E402

SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}
SHORT = {'SMOOTHIE_SHOP': 'Smo', 'YARN_STORE': 'Yarn', 'FARMERS_MARKET': 'Farm', 'BAKERY': 'Bak', 'ICE_CREAM_SHOP': 'Ice',
         'PET_CAFE': 'Pet', 'PIZZA_SHOP': 'Piz', 'BRUNCH_SPOT': 'Bru'}


def merged(steps, t, seat):
    obs = dict(steps[t][0]['observation'])
    obs.update(steps[t][seat]['observation'])
    return obs


def ledger(replay):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    from evaluate_boards import Ledger
    steps = replay['steps']

    def player(i):
        state = {'t': 0}

        def act(obs, cfg=None):
            state['t'] += 1
            a = steps[state['t']][i].get('action') if state['t'] < len(steps) else None
            return a if isinstance(a, dict) else {'farmer': ['PASS'], 'hands': [], 'market': []}
        return act
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': replay['info']['seed']})
    with Ledger(E) as led:
        env.run([player(0), player(1)])
        final = [env.state[i].reward for i in (0, 1)]
        data = [dict(revenue=dict(led.data[i]['revenue']), spend=dict(led.data[i]['spend']), sold=dict(led.data[i]['sold_units'])) for i in (0, 1)]
    return final, data


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    brief = '--brief' in sys.argv
    path = Path(args[0])
    agent_file = Path(args[1]) if len(args) > 1 else ROOT / 'submissions/2026-09-19-mgt_t10/main.py'
    team = args[2] if len(args) > 2 else 'Ghost Rule'
    replay = json.loads(path.read_text(encoding='utf-8'))
    steps = replay['steps']
    names = replay['info'].get('TeamNames') or ['?', '?']
    seat = next(i for i, n in enumerate(names) if team.lower() in (n or '').lower())
    ep = replay['info'].get('EpisodeId')
    rewards = replay['rewards']
    shops = merged(steps, len(steps) - 1, seat)['town']['unlocked_shops']
    out = dict(episode=ep, seat=seat, teams=names, rewards=rewards, seed=replay['info'].get('seed'), shops=shops)
    print(f'episode {ep}: {names[seat]} (seat {seat}) {rewards[seat]:,.0f}  vs  {names[1 - seat]} {rewards[1 - seat]:,.0f}   margin {rewards[seat] - rewards[1 - seat]:+,.0f}')
    print('shops:', ' '.join(SHORT.get(s, s) for s in shops), '| steps', len(steps))

    # 1. status and time
    bad = Counter(s[seat].get('status') for s in steps if s[seat].get('status') not in ('ACTIVE', 'DONE', 'INACTIVE'))
    over = [s[seat]['observation'].get('remainingOverageTime') for s in steps if s[seat]['observation'].get('remainingOverageTime') is not None]
    print(f'status problems: {dict(bad) or "none"}; overage time {min(over):.1f}-{max(over):.1f} s' if over else f'status problems: {dict(bad) or "none"}')
    out['status'] = dict(bad)
    out['overage_min'] = min(over) if over else None

    # 2. reproduction with the submitted file
    from kaggle_environments.agent import get_last_callable
    entry = get_last_callable(agent_file.read_text(encoding='utf-8'), path=str(agent_file))
    G = entry.__globals__
    mism, first = 0, None
    dead, dead_day = Counter(), Counter()
    hire_req, hire_got, over_cap = Counter(), Counter(), 0
    cash, animals_by_day, lost = [], [], []
    prev_animals = {}
    min_cash = (10 ** 9, -1)
    for t in range(len(steps) - 1):
        obs = merged(steps, t, seat)
        rec = steps[t + 1][seat].get('action')
        try:
            mine = entry(obs, None)
        except Exception as exc:                                      # the real run would have crashed too
            mine = {'error': repr(exc)}
        if json.dumps(mine, sort_keys=True) != json.dumps(rec, sort_keys=True):
            mism += 1
            first = first if first is not None else (t, mine, rec)
        a = rec if isinstance(rec, dict) else {}
        farm = obs['farms'][seat]
        if t % 24 == 0:
            cash.append(farm['money'])
        if farm['money'] < min_cash[0]:
            min_cash = (farm['money'], t)
        shed = dict(obs['private'].get('shed') or {})
        seeds = obs['private'].get('seeds') or {}
        invs = obs['private'].get('inventories') or []
        units = [farm['farmer']] + list(farm['hands'])
        cmds = [a.get('farmer')] + list(a.get('hands') or [])
        for i, c in enumerate(cmds):
            if not c or c[0] == 'PASS':
                continue
            if i >= len(units):
                dead['command for a hand that does not exist'] += 1
                dead_day[t // 24] += 1
                continue
            u = tuple(units[i])
            inv = invs[i] if i < len(invs) else {}
            if c[0] == 'PLACE' and u in SHED and len(c) > 1 and int(inv.get(c[1], 0) or 0) > 0:
                continue                                              # deposit at the shed
            k = classify(c, u, farm['tiles'][u[1]][u[0]], inv, shed, seeds)
            if k:
                dead[k] += 1
                dead_day[t // 24] += 1
            if c[0] == 'PICKUP' and len(c) > 2:
                shed[c[1]] = max(0, int(shed.get(c[1], 0) or 0) - int(c[2]))
        market = a.get('market') or []
        over_cap += max(0, len(market) - 10)
        n_hire = sum(1 for o in market[:10] if o and o[0] == 'HIRE')
        if n_hire:
            nxt = merged(steps, t + 1, seat)['farms'][seat]
            got = len(nxt['hands']) - len(farm['hands']) if (t + 1) % 24 else 0
            if (t + 1) % 24:
                hire_req[t // 24] += n_hire
                hire_got[t // 24] += max(0, got)
        animals = {(x, y): c['animal'] for y, row in enumerate(farm['tiles']) for x, c in enumerate(row) if isinstance(c, dict) and c.get('animal')}
        for p, s in prev_animals.items():
            if p not in animals:
                lost.append((t // 24, s))
        prev_animals = animals
        if t % 24 == 0:
            animals_by_day.append(dict(Counter(animals.values())))
    print(f'reproduction: {mism} of {len(steps) - 1} recorded actions differ from the submitted file on the same observations'
          + (f'; first at step {first[0]}' if first else ''))
    if first and not brief:
        print('   ours    :', json.dumps(first[1])[:300])
        print('   recorded:', json.dumps(first[2])[:300])
    out['mismatch'] = mism
    hist = [list(h) for h in (G.get('_MGT_HISTORY') or [])]
    switches = [h for i, h in enumerate(hist) if i == 0 or h[1] != hist[i - 1][1]]
    rep = {k: v for k, v in (G.get('_SHP_REPORT') or {}).items() if isinstance(v, (int, float))}
    print('router: ' + ', '.join(f'd{h[0]} -> {h[1]} (dist {h[2]}, hamming {h[3]})' for h in switches))
    print('overlay telemetry:', rep, '| router:', {k: v for k, v in (G.get('_MGT_REPORT') or {}).items()})
    out.update(switches=switches, overlay=rep)

    # 3. failures
    tot_cmd = sum(1 for t in range(len(steps) - 1) for c in ([(steps[t + 1][seat].get('action') or {}).get('farmer')] + list((steps[t + 1][seat].get('action') or {}).get('hands') or [])) if c and c[0] != 'PASS')
    print(f'commands with no effect: {sum(dead.values())} of {tot_cmd}: ' + ', '.join(f'{k} {v}' for k, v in dead.most_common(8)))
    worst = ', '.join(f'd{d}: {n}' for d, n in sorted(dead_day.items(), key=lambda kv: -kv[1])[:6])
    print(f'   worst days: {worst}')
    failed = {d: (hire_req[d], hire_got[d]) for d in hire_req if hire_got[d] < hire_req[d]}
    print(f'HIRE orders: {sum(hire_req.values())} requested, {sum(hire_got.values())} arrived; short days: {failed or "none"}')
    print(f'orders past the 10-order cap: {over_cap}; lowest cash {min_cash[0]:,.0f} at step {min_cash[1]} (day {min_cash[1] // 24}); animals that disappeared: {lost or "none"}')
    out.update(dead=dict(dead), dead_total=sum(dead.values()), commands=tot_cmd, hire_short=failed, over_cap=over_cap, min_cash=min_cash, lost=lost)

    # 4. tape match
    final_ep = str(switches[-1][1]) if switches else None
    tp = next(iter(glob.glob(str(ROOT / f'data/mg_tapes/*/{final_ep}.json.gz'))), None) if final_ep else None
    if tp:
        tape = json.load(gzip.open(tp, 'rt', encoding='utf-8'))
        tshops = tape['shops'][30]
        print('tape world:', ' '.join(SHORT.get(s, s) for s in tshops), f'| her result in that game {tape["rewards"][tape["seat"]]:,.0f}')
        print('this world:', ' '.join(SHORT.get(s, s) for s in shops))
        lab = G.get('_mgt_labels')
        board_of = G.get('_mgt_board')
        ham = []
        for d in range(0, 30, 3):
            ours = lab(board_of(merged(steps, d * 24, seat)['farms'][seat]))
            hers = lab(''.join(tape['boards'][d]))
            ham.append((d, sum(1 for x, y in zip(ours, hers) if x != y)))
        print('board Hamming distance to the final tape, by day:', ' '.join(f'd{d}:{h}' for d, h in ham))
        print('cash at day start, ours vs the tape\'s original game (difference):')
        print('   ' + ' '.join(f'd{d}:{cash[d] - tape["cash"][d]:+,.0f}' for d in range(0, min(len(cash), 30), 3)) + f' | final {rewards[seat] - tape["rewards"][tape["seat"]]:+,.0f}')
        out.update(tape=final_ep, tape_shops=tshops, hamming=ham, cash_gap=[cash[d] - tape['cash'][d] for d in range(min(len(cash), 30))],
                   tape_final=tape['rewards'][tape['seat']])
    print('animals at day 12 / 18 / 24:', [animals_by_day[d] for d in (12, 18, 24) if d < len(animals_by_day)])

    # 5. exact ledger
    if not brief:
        final, data = ledger(replay)
        ok = [round(x or 0) for x in final] == [round(x or 0) for x in rewards]
        print(f'ledger re-run reproduces the final cash: {ok}')
        me, op = data[seat], data[1 - seat]
        prods = sorted(set(me['revenue']) | set(op['revenue']), key=lambda p: -(me['revenue'].get(p, 0)))
        print('revenue by product, ours / theirs (units): ' + ', '.join(f'{p} {me["revenue"].get(p, 0):,.0f}/{op["revenue"].get(p, 0):,.0f} ({me["sold"].get(p, 0)}/{op["sold"].get(p, 0)})' for p in prods))
        cats = sorted(set(me['spend']) | set(op['spend']), key=lambda c: -(me['spend'].get(c, 0)))
        print('spending, ours / theirs: ' + ', '.join(f'{c} {me["spend"].get(c, 0):,.0f}/{op["spend"].get(c, 0):,.0f}' for c in cats[:8]))
        out.update(ledger_ok=ok, revenue=me['revenue'], rival_revenue=op['revenue'], spend=me['spend'], rival_spend=op['spend'])
    (ROOT / 'results/fresh/ladder_t10').mkdir(parents=True, exist_ok=True)
    (ROOT / f'results/fresh/ladder_t10/trace_{ep}.json').write_text(json.dumps(out, default=list), encoding='utf-8')


if __name__ == '__main__':
    main()
