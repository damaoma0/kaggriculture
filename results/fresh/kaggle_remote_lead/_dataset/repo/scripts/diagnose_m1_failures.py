"""Observe animal servicing in exact recorded m1 games; do not change decisions."""
import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
from research_labour_profit import Simulator, engine

OUT = ROOT / 'results/fresh/all_umg_m1/diagnosis'


def audit(episode):
    destination = OUT / f'{episode}.json'
    if destination.exists():
        return json.loads(destination.read_text(encoding='utf8'))
    with gzip.open(ROOT / f'data/ladder_panel/56395605/{episode}.json.gz', 'rt', encoding='utf8') as f:
        game = json.load(f)
    E = engine()
    s = game['seat']
    actions = [None, None]
    actions[s], actions[1-s] = game['our_actions'], game['opp_actions']
    totals = [defaultdict(Counter), defaultdict(Counter)]
    cohorts = {}
    daily = []
    with Simulator(game) as sim:
        original = E._daily_refresh_animals

        def refresh(farm, day):
            seat = sim.seats[id(farm)]
            before = [(x, y, deepcopy(c)) for y, row in enumerate(farm['tiles'])
                      for x, c in enumerate(row) if isinstance(c, dict) and c.get('animal')]
            result = original(farm, day)
            for x, y, c in before:
                species = c['animal']
                a = E.ANIMALS[species]
                after = farm['tiles'][y][x]
                survives = isinstance(after, dict) and after.get('animal') == species
                age = day + 1 - c['placed_day'] - a['first_yield_day']
                due = age >= 0 and age % a['interval'] == 0
                fed, cared = bool(c['fed_today']), bool(c['cared_today'])
                bank = c.get('pending_care_bonus', 0)
                earned = (after['yield_units'] - c['yield_units']) if survives and due else 0
                cap_loss = max(0, 1 + (bank if fed else 0) - earned) if survives and due else 0
                wiped = bank if survives and due and not fed else 0
                row = dict(day=day, seat=seat, species=species, x=x, y=y,
                           placed_day=c['placed_day'], fed=fed, cared=cared,
                           production_due=due, survived=survives, new_yield=earned,
                           bank_wiped_by_unfed_production=wiped,
                           capacity_blocked_yield=cap_loss,
                           unharvested_at_escape=0 if survives else c['yield_units'])
                daily.append(row)
                key = (seat, x, y, c['placed_day'], species)
                cohort = cohorts.setdefault(key, dict(seat=seat, species=species, x=x, y=y,
                    placed_day=c['placed_day'], feeds=[], care=[], production=[], escaped_day=None))
                if fed:
                    cohort['feeds'].append(day)
                if fed and cared:
                    cohort['care'].append(day)
                if survives and due:
                    cohort['production'].append(dict(day=day+1, units=earned, fed=fed,
                        bank_wiped=wiped, cap_loss=cap_loss))
                if not survives:
                    cohort['escaped_day'] = day+1
                t = totals[seat][species]
                t.update(animal_days=1, fed_days=int(fed), cared_and_fed_days=int(fed and cared),
                         production_events=int(survives and due),
                         unfed_production_events=int(survives and due and not fed),
                         new_yield=earned, bank_wiped_by_unfed_production=wiped,
                         capacity_blocked_yield=cap_loss, escaped=int(not survives),
                         unharvested_at_escape=row['unharvested_at_escape'])
            return result

        E._daily_refresh_animals = refresh
        try:
            replay = sim.run(sim.initial, 0, 719, actions)
        finally:
            E._daily_refresh_animals = original
        assert replay['money'] == game['rewards'], (episode, replay['money'], game['rewards'])
    doc = dict(episode=episode, original_seat=s, cash_matches=True,
               sides=[totals[s], totals[1-s]], cohorts=list(cohorts.values()), daily=daily,
               notes='sides are [m1, opponent]; daily/cohort seats retain original seats. '
                     'Counts cover the 29 executed overnight refreshes. Missing care is not '
                     'automatically profitable to supply; no counterfactual money is estimated.')
    OUT.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(doc), encoding='utf8')
    return doc


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('episodes', nargs='*', type=int)
    parser.add_argument('--wool-under2500', action='store_true')
    args = parser.parse_args()
    episodes = args.episodes
    if args.wool_under2500:
        data = json.loads((OUT.parent / 'summary.json').read_text(encoding='utf8'))
        episodes = [x['episode'] for x in data['losses'] if x['under2500'] and x['top']['product'] == 'WOOL']
    if not episodes:
        episodes = [111262874, 111678108, 111743130, 112109339]
    for ep in episodes:
        doc = audit(ep)
        print(json.dumps(dict(episode=ep, sides=doc['sides'], cash_matches=doc['cash_matches'])), flush=True)
