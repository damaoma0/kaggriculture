"""Next-morning state after one day, arm vs arm (labor viewer frames): cash, goods in the shed and in hands, units held on
tiles (by product), animal banks (pending care bonus), pens with fertilizer waiting, plant states (dry, fertilized),
and a coin value of the difference at the morning's prices (goods and tile units at price, banks at one unit each,
fertilizer on pens at the fertilizer price).
usage: day_state_diff.py <labor_viz json> <day> <armA> <armB> [<armC> ...]"""
import json
import sys
from collections import Counter

ANPROD = {'SHEEP': 'WOOL', 'COW': 'MILK', 'GOOSE': 'EGG'}


def state(r, arm, step):
    tab = r['tiles']
    f = next(x for x in r[arm]['frames'] if x['step'] == step)
    b = [tab[i] if i is not None and i >= 0 else None for i in f['board']]
    goods = Counter()
    for k, v in (f['shed'] or {}).items():
        goods[k] += v
    for inv in f['inv']:
        for k, v in inv.items():
            goods[k] += v
    held, bank, fert_wait, dry, fert_on, plants = Counter(), Counter(), 0, 0, 0, Counter()
    for t in b:
        if not t:
            continue
        if t.get('kind') == 'PLANT':
            held[t['crop']] += int(t.get('yield_units', 0) or 0)
            plants[t['crop']] += 1
            dry += int(t.get('consecutive_unwatered', 0) or 0) >= 1
            fert_on += int(t.get('fertilized_until_day', -1)) >= step // 24
        elif t.get('animal'):
            p = ANPROD[t['animal']]
            held[p] += int(t.get('yield_units', 0) or 0)
            bank[p] += int(t.get('pending_care_bonus', 0) or 0)
            fert_wait += bool(t.get('fertilizer_available'))
    return dict(cash=f['cash'], goods=goods, held=held, bank=bank, fert_wait=fert_wait, dry=dry, fert_on=fert_on, plants=plants)


def main():
    r = json.load(open(sys.argv[1], encoding='utf-8'))[0]
    day = int(sys.argv[2])
    arms = [a.lower() for a in sys.argv[3:]]
    step = (day + 1) * 24
    S = {a: state(r, a, step) for a in arms}
    price = {}
    f = next(x for x in r[arms[0]]['frames'] if x['step'] == step)
    print(f'next morning (day {day + 1} hour 0) state, arms {arms}')
    base = S[arms[0]]
    for a in arms[1:]:
        s = S[a]
        print(f'== {a} - {arms[0]}: cash {s["cash"] - base["cash"]:+.0f}')
        for key in ('goods', 'held', 'bank'):
            dif = {k: s[key][k] - base[key][k] for k in set(s[key]) | set(base[key]) if s[key][k] != base[key][k]}
            print(f'   {key:6s} {dif}')
        print(f'   pens with fertilizer waiting {s["fert_wait"] - base["fert_wait"]:+d} | dry plants {s["dry"] - base["dry"]:+d}'
              f' | fertilized plants {s["fert_on"] - base["fert_on"]:+d} | plants {dict((k, s["plants"][k] - base["plants"][k]) for k in s["plants"] if s["plants"][k] != base["plants"][k])}')


if __name__ == '__main__':
    main()
