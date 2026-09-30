"""Does the imitation's absorption model reproduce the leaders' observed crop quantities?

Runs the controller's target formula over the shops each leader actually saw, and compares the
target with what that leader actually had planted at the same checkpoint. This measures imitation
fidelity, which is separate from whether the imitation scores well.
"""
import json, statistics as st
from market_corpus import ROOT

SEG = ROOT / 'results/fresh/leader_segments'
SHOP_RATES = {
    'BAKERY': {'EGG': 6.0, 'WHEAT': 6.0},
    'PIZZA_SHOP': {'MILK': 6.0, 'TOMATO': 6.0, 'WHEAT': 6.0},
    'BRUNCH_SPOT': {'EGG': 6.0, 'WHEAT': 6.0, 'STRAWBERRY': 6.0},
    'YARN_STORE': {'WOOL': 12.0},
    'ICE_CREAM_SHOP': {'STRAWBERRY': 6.0, 'MILK': 6.0, 'WHEAT': 6.0},
    'PET_CAFE': {'CARROT': 12.0},
    'SMOOTHIE_SHOP': {'STRAWBERRY': 6.0, 'MILK': 6.0},
    'FARMERS_MARKET': {'WHEAT': 6.0, 'CARROT': 6.0, 'TOMATO': 6.0, 'STRAWBERRY': 6.0},
}
DRAW_DAYS = (3, 6, 9, 12, 15, 18, 21, 24)
END, TOWN, SHARE, FUTURE = 29, 1.0, 0.5, 0.5
PRODUCTIONS = {'STRAWBERRY': (10, 12, 14, 16), 'TOMATO': (8, 9, 10, 11), 'CARROT': (3,)}
UNITS = {'STRAWBERRY': 1.0, 'TOMATO': 1.0, 'CARROT': 3.0}
CYCLE = {'CARROT': 4}


def units_per_plant(crop, day):
    total = 0.0
    if crop in CYCLE:
        start = day
        while start + max(PRODUCTIONS[crop]) <= END:
            total += UNITS[crop]
            start += CYCLE[crop]
        return total
    for age in PRODUCTIONS[crop]:
        if day + age <= END:
            total += UNITS[crop]
    return total


def target(shops, crop, day, bounds):
    start = day + PRODUCTIONS[crop][0]
    if start >= END:
        return bounds[0]
    total = TOWN * (END - start)
    for index, name in enumerate(shops):
        reveal = DRAW_DAYS[index] if index < len(DRAW_DAYS) else DRAW_DAYS[-1]
        rate = SHOP_RATES.get(name, {}).get(crop, 0.0)
        if rate:
            total += rate * max(0, END - max(reveal, start))
    expected = sum(r.get(crop, 0.0) for r in SHOP_RATES.values()) / len(SHOP_RATES)
    for index in range(len(shops), len(DRAW_DAYS)):
        total += FUTURE * expected * max(0, END - max(DRAW_DAYS[index], start))
    per_plant = units_per_plant(crop, day)
    if per_plant <= 0:
        return bounds[0]
    return max(bounds[0], min(bounds[1], int(round(SHARE * total / per_plant))))


def main():
    sample = json.loads((SEG / 'sample.json').read_text(encoding='utf-8'))
    subs = {e['id']: [a['sub'] for a in e['agents']] for e in sample['sample']}
    groups = {'Majkel1337/56216119': ('Majkel1337', 56216119),
              'MotherGoose/56266758': ('Unknown Mother-Goose', 56266758)}
    rows = {name: [] for name in groups}
    for path in sorted(SEG.glob('segments-*.json')):
        game = json.loads(path.read_text(encoding='utf-8'))
        for seat_row in game['seats']:
            key = (seat_row['team'], subs[game['episode']][seat_row['seat']])
            for name, want in groups.items():
                if key == want:
                    rows[name].append((game['shops_by_segment'], seat_row['segments']))
    print('Strawberry: model target vs the leader\'s actual plants, at the day-9 and day-12 checkpoints')
    print(f"{'policy':22s} {'day':>4s} {'model mean':>11s} {'actual mean':>12s} {'mean abs err':>13s} "
          f"{'model range':>13s} {'actual range':>13s} {'rank corr':>10s}")
    for name, games in rows.items():
        for day, segment in ((9, 3), (12, 4)):
            models, actuals = [], []
            for shops_by_segment, segments in games:
                shops = shops_by_segment.get(str(segment), [])
                models.append(target(shops, 'STRAWBERRY', day, (8, 40)))
                actuals.append((segments[segment]['board_start'] or {}).get('STRAWBERRY', 0))
            errs = [abs(m - a) for m, a in zip(models, actuals)]
            def rank(v):
                order = sorted(range(len(v)), key=lambda i: v[i]); out = [0.0] * len(v); i = 0
                while i < len(order):
                    j = i
                    while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                        j += 1
                    for k in range(i, j + 1):
                        out[order[k]] = (i + j) / 2 + 1
                    i = j + 1
                return out
            rx, ry = rank(models), rank(actuals)
            mx, my = st.mean(rx), st.mean(ry)
            num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
            den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
            print(f'{name:22s} {day:4d} {st.mean(models):11.1f} {st.mean(actuals):12.1f} {st.mean(errs):13.1f} '
                  f'{min(models):6d}-{max(models):<6d} {min(actuals):6d}-{max(actuals):<6d} '
                  f'{(num/den if den else 0):+10.2f}')
    print('\nCarrot at day 18: model target vs the leader\'s actual plants at the day-18 checkpoint')
    for name, games in rows.items():
        models, actuals = [], []
        for shops_by_segment, segments in games:
            shops = shops_by_segment.get('6', [])
            models.append(target(shops, 'CARROT', 18, (0, 45)))
            actuals.append((segments[6]['board_start'] or {}).get('CARROT', 0))
        print(f'{name:22s} model {st.mean(models):5.1f} (range {min(models)}-{max(models)}) | '
              f'actual {st.mean(actuals):5.1f} (range {min(actuals)}-{max(actuals)})')
    print('\nFor reference, our benchmark holds exactly 33 strawberries and 0 carrots at both checkpoints.')


if __name__ == '__main__':
    main()
