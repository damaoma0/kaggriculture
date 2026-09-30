"""Serial paired exact-engine runner for coherent opening/continuation arms.

Designs are persisted before games. Policies receive only their live observation.
This harness intentionally contains no policy logic.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import random
import secrets
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import research_labour_profit as R

OUT = ROOT / 'results/fresh/coherent_opening_20260924_01a0'
OPPONENTS = {
    'mgt_m1': ROOT / 'agents/mgt_m1.py',
    'v56': ROOT / 'data/router_refresh_20260922/v56/main.py',
}
OWNED_SOURCES = [ROOT / 'scripts/run_coherent_opening_study.py',
                 ROOT / 'scripts/research_labour_profit.py',
                 ROOT / 'agents/mgt_dsm_a.py',
                 ROOT / 'agents/mgt_m1.py', OPPONENTS['v56'],
                 ROOT / 'scripts/coherent_opening_policy.py']


def source_hashes():
    paths = [p for p in OWNED_SOURCES if p.exists()]
    # Include the candidate's extracted inputs, including their manifest.
    extraction = ROOT / 'results/fresh/coherent_opening_20260924_01a0/extraction'
    if extraction.exists():
        paths += [p for p in extraction.rglob('*') if p.is_file()]
    return {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}


def shop_names():
    E = R.engine()
    return sorted(E.SHOPS)


def freeze_design(phase, refresh=False):
    nworlds = 8 if phase == 'development' else 32
    path = OUT / phase / 'design.json'
    if path.exists():
        design = json.loads(path.read_text(encoding='utf-8'))
        if phase == 'qualification':
            if refresh:
                raise RuntimeError('qualification design is immutable')
            dev_path = OUT / 'development' / 'design.json'
            if dev_path.exists():
                dev = json.loads(dev_path.read_text(encoding='utf-8'))
                assert not ({w['seed'] for w in design['worlds']} & {w['seed'] for w in dev['worlds']}), 'qualification seeds overlap development'
            return design
        return design
    OUT.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    names = shop_names()
    master = secrets.randbits(128)
    rng = random.Random(master)
    excluded = set()
    if phase == 'qualification' and (OUT / 'development' / 'design.json').exists():
        dev = json.loads((OUT / 'development' / 'design.json').read_text(encoding='utf-8'))
        excluded = {w['seed'] for w in dev['worlds']}
    seeds = []
    used = set(excluded)
    while len(seeds) < nworlds:
        candidate = rng.randrange(1_000_000_000, 4_000_000_000)
        if candidate not in used:
            used.add(candidate)
            seeds.append(candidate)
    worlds = []
    for i, seed in enumerate(seeds):
        first = names[i % len(names)] if phase == 'development' else names[i // 4]
        shops = [first] + [rng.choice(names) for _ in range(7)]
        worlds.append(dict(id=f'w{i:02d}', seed=seed, shops=shops,
                           first_shop=first, cohort='all'))
    specs = []
    for world in worlds:
        for opponent in OPPONENTS:
            specs.append(dict(id=f"{world['id']}-{opponent}", world=world,
                              opponent=opponent, seat=(int(world['id'][1:]) + list(OPPONENTS).index(opponent)) % 2))
    protocol = ('8 random worlds; first shop balanced across all shop types, seven independently uniform draws; '
                'each world crossed with both opponents and seats balanced.') if phase == 'development' else (
                '32 fresh random worlds; four worlds per first-shop type, seven independently uniform draws; '
                'each world crossed with both opponents and seats balanced. Qualification is immutable.')
    design = dict(phase=phase, master_seed=master, specs=specs, worlds=worlds,
                  arms=['baseline', 'dsm', 'normalized', 'funded'], opponents=list(OPPONENTS), protocol=protocol,
                  shop_lock='At step 0 and immediately after each natural end-of-day update, set unlocked_shops to the persisted sequence prefix for that day. Policy sees observation only.')
    path.write_text(json.dumps(design, indent=2), encoding='utf-8')
    return design


def freeze_manifest(phase, revision='v1', refresh=False):
    path = OUT / phase / revision / 'source_manifest.json'
    current = source_hashes()
    if path.exists():
        if refresh:
            if phase != 'development':
                raise RuntimeError('qualification source manifest is immutable')
            archive = OUT / phase / 'archive' / (revision + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
            archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path.parent), str(archive))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(dict(phase=phase, revision=revision, hashes=current), indent=2), encoding='utf-8')
            return current
        saved = json.loads(path.read_text(encoding='utf-8'))['hashes']
        if saved != current:
            raise RuntimeError('source manifest differs from the phase snapshot')
        return saved
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(phase=phase, revision=revision, hashes=current), indent=2), encoding='utf-8')
    return current


def load_callable(path, name):
    from kaggle_environments.agent import get_last_callable
    return get_last_callable(path.read_text(encoding='utf-8'), path=str(path))


def fresh_policy(arm):
    path = ROOT / 'scripts/coherent_opening_policy.py'
    spec = importlib.util.spec_from_file_location('coherent_policy_' + arm, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.make_policy(arm)


def public(x):
    if hasattr(x, 'toJSON'):
        return x.toJSON()
    if isinstance(x, dict):
        return {k: public(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [public(v) for v in x]
    return x


def snapshot(state, t, ledgers, spec, events, failed_hires):
    rows = []
    for seat in range(2):
        farm = state[seat].observation.farms[seat]
        private = state[seat].observation.private
        this_day = max(0, (t - 1) // 24) if t else 0
        hires_today = sum(1 for et, s, op, _, _ in events
                          if s == seat and op == 'HIRE' and et // 24 == this_day)
        unit_counts = {}
        for et, s, op, item, _ in events:
            if s == seat and et // 24 == this_day and op not in ('HIRE', 'BUY_LAND'):
                key = op + (':' + (item or '') if item else '')
                unit_counts[key] = unit_counts.get(key, 0) + 1
        failed_hires_today = sum(1 for et, s in failed_hires if s == seat and et // 24 == this_day)
        assets = []
        for y, row in enumerate(farm.get('tiles', [])):
            for x, tile in enumerate(row):
                if tile is not None:
                    assets.append(dict(pos=[x, y], tile=public(tile)))
        rows.append(dict(seat=seat, cash=int(farm['money']), hands=len(farm.get('hands', [])),
                         hires_today=int(farm.get('hires_today', 0)),
                         successful_hires_today=hires_today,
                         failed_hires_today=failed_hires_today,
                         successful_sale_buy_units_today=unit_counts,
                         seeds=public(private.get('seeds', {})), shed=public(private.get('shed', {})),
                         inventory=public(private.get('inventories', [])),
                         assets=assets, tile_counts=tile_counts(farm.get('tiles', [])),
                         revenue=ledgers[seat]['revenue'], spend=ledgers[seat]['spend'],
                         successful_hires=sum(1 for _, s, op, _, _ in events if s == seat and op == 'HIRE')))
    return dict(step=t, phase=spec.get('phase'), cohort='first_shop:' + spec['world']['first_shop'],
                world_id=spec['world']['id'], seats=rows)


def tile_counts(tiles):
    from collections import Counter
    counts = Counter()
    for row in tiles:
        for tile in row:
            if isinstance(tile, dict):
                counts[tile.get('kind', 'UNKNOWN')] += 1
                if tile.get('animal'):
                    counts['ANIMAL:' + str(tile['animal'])] += 1
                if tile.get('crop'):
                    counts['CROP:' + str(tile['crop'])] += 1
    return dict(counts)


def play(spec, arm):
    E = R.engine()
    seat = spec['seat']
    shops = spec['world']['shops']
    game_spec = dict(seed=spec['world']['seed'], seat=seat, episode=0,
                     shops=[shops[:min(8, d // 3)] for d in range(31)])
    policy, rival = fresh_policy(arm), load_callable(OPPONENTS[spec['opponent']], spec['opponent'])
    entries = [None, None]
    entries[seat], entries[1-seat] = policy, rival
    sim = R.Simulator(game_spec)
    action_hash = sha256()
    max_action = [0.0, 0.0]
    failed_spending = [0, 0]
    failed_hires = []
    daily = []
    try:
        with sim:
            old_commit = E._commit_unit
            def tracked_commit(op, item, price, farm, private, market, *a, **kw):
                result = old_commit(op, item, price, farm, private, market, *a, **kw)
                if not result and op in ('BUY_PRODUCT', 'BUY_SEED', 'BUY_ANIMAL'):
                    failed_spending[sim.seats.get(id(farm), 0)] += 1
                return result
            E._commit_unit = tracked_commit
            old_hire = E._do_hire
            def tracked_hire(farm, *a, **kw):
                before = int(farm.get('money', 0))
                result = old_hire(farm, *a, **kw)
                if int(farm.get('money', 0)) == before:
                    failed_hires.append((sim.t, sim.seats.get(id(farm), 0)))
                return result
            E._do_hire = tracked_hire
            state = deepcopy(sim.initial)
            expected = shops[:0]
            state[0].observation.town.unlocked_shops[:] = expected
            assert list(state[seat].observation.town.unlocked_shops) == expected
            daily.append(snapshot(state, 0, ledgers_from_events([]), spec, [], failed_hires))
            for t in range(719):
                sim.t = t
                sim.seats = {id(f): s for s, f in enumerate(state[0].observation.farms)}
                for s in state:
                    s.observation.step = t
                expected = shops[:min(8, (t // 24) // 3)]
                actual = list(state[seat].observation.town.unlocked_shops)
                assert actual == expected, (t, actual, expected)
                for s in range(2):
                    started = time.perf_counter()
                    state[s].action = entries[s](deepcopy(state[s].observation))
                    max_action[s] = max(max_action[s], time.perf_counter() - started)
                action_hash.update(json.dumps([public(s.action) for s in state], sort_keys=True).encode())
                E.interpreter(state, sim.env)
                if (t + 1) % 24 == 0:
                    day = (t + 1) // 24
                    expected = shops[:min(8, day // 3)]
                    state[0].observation.town.unlocked_shops[:] = expected
                    assert list(state[seat].observation.town.unlocked_shops) == expected
                    if day <= 29:
                        daily.append(snapshot(state, t + 1, ledgers_from_events(sim.events), spec, sim.events, failed_hires))
            for s in state:
                s.observation.step = 719
            daily.append(snapshot(state, 719, ledgers_from_events(sim.events), spec, sim.events, failed_hires))
            cash = [int(s.observation.farms[i]['money']) for i, s in enumerate(state)]
            ledgers = ledgers_from_events(sim.events)
            verified = []
            for s in range(2):
                start_cash = 3000
                expected = start_cash + sum(ledgers[s]['revenue'].values()) - sum(ledgers[s]['spend'].values())
                verified.append(expected == cash[s])
            assert all(verified), {'cash': cash, 'ledgers': ledgers, 'verified': verified}
            if not all(s.status == 'DONE' for s in state):
                raise RuntimeError('engine did not complete both seats')
            telemetry = {}
            for key, entry in (('policy', policy), ('opponent', rival)):
                for attr in ('stats', 'history', 'sp_telemetry'):
                    value = getattr(entry, attr, None)
                    if value is not None:
                        telemetry[key + '.' + attr] = public(value)
            return dict(spec=spec, arm=arm, completed=True, cash=cash, ledgers=ledgers,
                        ledger_verified=verified, daily=daily, failed_spending=failed_spending,
                        failed_hires=failed_hires,
                        action_sha256=action_hash.hexdigest(), max_action_seconds=max_action,
                        telemetry=telemetry)
    finally:
        # Simulator.__exit__ restores the original hooks. Never reassign the
        # in-context wrapper here; it closes over this completed Simulator.
        assert E._commit_unit is sim.old_commit
        assert E._apply_unit_action is sim.old_unit
        assert E._do_hire is sim.old_hire
        assert E._do_buy_land is sim.old_land


def ledgers_from_events(events):
    from collections import Counter
    ledgers = [dict(revenue=Counter(), spend=Counter()) for _ in range(2)]
    for t, seat, op, item, amount in events:
        key = item or ''
        target = 'revenue' if op == 'SELL' else 'spend'
        ledgers[seat][target][op + (':' + key if key else '')] += int(amount)
    return [{k: dict(v) for k, v in row.items()} for row in ledgers]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=('development', 'qualification'), required=True)
    ap.add_argument('--arms', default='baseline,dsm,normalized,funded')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--case')
    ap.add_argument('--revision', default='v1')
    ap.add_argument('--refresh-development', action='store_true')
    args = ap.parse_args()
    if args.refresh_development and args.phase != 'development':
        raise SystemExit('--refresh-development is development-only')
    design = freeze_design(args.phase, args.refresh_development)
    frozen_sources = freeze_manifest(args.phase, args.revision, args.refresh_development)
    arms = args.arms.split(',')
    specs = list(design['specs'])
    if args.case:
        specs = [s for s in specs if s['id'] == args.case]
        if not specs:
            raise SystemExit('unknown case id')
    if args.limit is not None:
        specs = specs[:args.limit]
    phase_dir = OUT / args.phase / args.revision
    results = phase_dir / 'games'
    results.mkdir(parents=True, exist_ok=True)
    # Memory gate for long-lived engine state; bounded polling, no parallel workers.
    try:
        import psutil
        while psutil.virtual_memory().available / 1e9 < 2.6:
            time.sleep(20)
    except ImportError:
        pass
    for spec in specs:
        for arm in arms:
            target = results / f"{spec['id']}-{arm}.json"
            if target.exists():
                continue
            started = time.perf_counter()
            try:
                row = play(spec, arm)
            except Exception:
                row = dict(spec=spec, arm=arm, completed=False, error=traceback.format_exc())
            row['seconds'] = time.perf_counter() - started
            target.write_text(json.dumps(row, indent=2), encoding='utf-8')
            print(json.dumps(dict(id=spec['id'], arm=arm, completed=row['completed'],
                                  seconds=row['seconds'], error=row.get('error'))), flush=True)
    if source_hashes() != frozen_sources:
        raise RuntimeError('source files changed during the batch')


if __name__ == '__main__':
    main()
