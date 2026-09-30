"""Paired exact-layout KB versus original DSM accounting; saved games only."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/fresh/semantic_strategy_20260928/oracle_diagnostics/d6_exact_vs_retile_v3'
PHASES = ((6, 11), (11, 18), (18, 24), (24, 30))
GOODS = ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER')
FIELDS = ('revenue', 'sold_units', 'spend', 'physical')
FOCUS = ('WOOL', 'STRAWBERRY', 'MILK')
ANIMALS = {'COW': (8, 2, 'MILK'), 'SHEEP': (6, 3, 'WOOL'), 'GOOSE': (4, 1, 'EGG')}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def subtract(a, b):
    return {k: a.get(k, 0)-b.get(k, 0) for k in set(a)|set(b) if a.get(k, 0) != b.get(k, 0)}


def period(ledger, start, end):
    return {field: subtract(ledger[end].get(field, {}), ledger[start].get(field, {})) for field in FIELDS}


def paired(a, b):
    return {field: subtract(a[field], b[field]) for field in FIELDS}


def flat(obs):
    return [cell for row in obs['own_farm']['tiles'] for cell in row]


def inventory(obs):
    private = obs.get('private')
    if private is None:
        return None
    result = Counter(private['shed'])
    for held in private['inventories']:
        result.update(held)
    return dict(result)


def cohorts(obs):
    counts, crop_births, animal_births, held, bonus, hungry = (Counter() for _ in range(6))
    for cell in flat(obs):
        if not isinstance(cell, dict):
            continue
        if cell.get('crop'):
            product = cell['crop']
            counts[product] += 1
            crop_births[f"{product}:{cell['planted_day']}"] += 1
            held[product] += cell.get('yield_units', 0)
        if cell.get('animal'):
            species = cell['animal']
            counts[species] += 1
            animal_births[f"{species}:{cell['placed_day']}"] += 1
            held[dict(COW='MILK', SHEEP='WOOL', GOOSE='EGG')[species]] += cell.get('yield_units', 0)
            bonus[species] += cell.get('pending_care_bonus', 0)
            hungry[species] += int(cell.get('consecutive_unfed', 0) > 0)
    return dict(counts=dict(counts), crop_births=dict(crop_births), animal_births=dict(animal_births),
                uncollected_yield=dict(held), pending_care_bonus=dict(bonus), hungry=dict(hungry), stock=inventory(obs))


def identity(cell):
    if not isinstance(cell, dict):
        return None
    if cell.get('animal'):
        return ('animal', cell['animal'], cell['placed_day'])
    if cell.get('crop'):
        return ('crop', cell['crop'], cell['planted_day'])
    return None


def potential_night(before, after, day):
    """Actual cohort/feed/fertilizer conditions, before held-yield capping."""
    rows = {}
    for tile, cell in enumerate(after):
        ident = identity(cell)
        if not ident:
            continue
        kind, species, birth = ident
        old = before[tile] if identity(before[tile]) == ident else {}
        if kind == 'animal':
            first, interval, product = ANIMALS[species]
            fed = cell['consecutive_unfed'] == 0
            production = day+1-birth >= first and (day+1-birth-first) % interval == 0
            old_bonus, new_bonus = old.get('pending_care_bonus', 0), cell.get('pending_care_bonus', 0)
            cared = fed and (new_bonus > 0 if production else new_bonus > old_bonus)
            rows[(tile, *ident)] = dict(product=product, base=int(production),
                bonus=old_bonus if production and fed else 0,
                total=(1+(old_bonus if fed else 0)) if production else 0,
                production=production, fed=fed, useful_care=cared,
                unfed_production_lost_bank=old_bonus if production and not fed else 0)
        elif species == 'STRAWBERRY':
            age = day+1-birth-10
            production = 0 <= age <= 6 and age % 2 == 0
            fertilized = cell['consecutive_unwatered'] == 0 and cell.get('fertilized_until_day', -1) >= day
            rows[(tile, *ident)] = dict(product=species, base=int(production),
                bonus=int(production and fertilized), total=int(production)*(1+int(fertilized)),
                production=production)
    return rows


def production_audit(source, exact, seat):
    observations = [[row['current_observation'] for row in game['diagnostics'][seat]] for game in (source, exact)]
    nights = [[potential_night(flat(obs[d]), flat(obs[d+1]), d) for d in range(29)] for obs in observations]
    phases = {}
    for start, end in ((6, 11), (11, 18), (18, 24)):
        phase = {}
        for good in FOCUS:
            both = []
            for index, (game, obs, daily) in enumerate(zip((source, exact), observations, nights)):
                base = sum(row['base'] for d in range(start, end) for row in daily[d].values() if row['product'] == good)
                bonus = sum(row['bonus'] for d in range(start, end) for row in daily[d].values() if row['product'] == good)
                collected = period(game['daily'][seat], start, end)['physical'].get('produced:'+good, 0)
                old_yield = cohorts(obs[start])['uncollected_yield'].get(good, 0)
                new_yield = cohorts(obs[end])['uncollected_yield'].get(good, 0)
                residual = base+bonus-collected-new_yield+old_yield
                assert residual >= 0, ('yield_balance', game['case']['episode'], start, end, good, residual)
                stocked = inventory(obs[end]).get(good, 0)-inventory(obs[start]).get(good, 0)
                sold = period(game['daily'][seat], start, end)['sold_units'].get(good, 0)
                assert collected-sold-stocked >= 0, ('stock_balance', good, collected, sold, stocked)
                both.append(dict(base_generation=base, care_or_fertilizer_generation=bonus,
                    potential_generation=base+bonus, collected=collected, board_yield_change=new_yield-old_yield,
                    cap_or_removed_uncollected_yield=residual, stock_change=stocked, sold=sold,
                    discarded_after_collection=collected-sold-stocked))
            attribution_counts = Counter()
            for day in range(start, end):
                n, e = nights[0][day], nights[1][day]
                for key in set(n)|set(e):
                    rn, re = n.get(key), e.get(key)
                    if (rn or re)['product'] != good:
                        continue
                    if rn and re:
                        attribution_counts['same_cohort_generation_delta'] += re['total']-rn['total']
                        if 'fed' in rn:
                            attribution_counts['same_cohort_animal_days'] += 1
                            attribution_counts['native_fed_exact_unfed'] += int(rn['fed'] and not re['fed'])
                            attribution_counts['exact_fed_native_unfed'] += int(re['fed'] and not rn['fed'])
                            attribution_counts['native_useful_care_exact_missing'] += int(rn['useful_care'] and not re['useful_care'])
                            attribution_counts['exact_useful_care_native_missing'] += int(re['useful_care'] and not rn['useful_care'])
                    else:
                        attribution_counts['native_only_cohort_generation'] += rn['total'] if rn else 0
                        attribution_counts['exact_only_cohort_generation'] += re['total'] if re else 0
            delta = subtract(both[1], both[0])
            assert delta.get('potential_generation', 0) == (attribution_counts['same_cohort_generation_delta'] +
                attribution_counts['exact_only_cohort_generation']-attribution_counts['native_only_cohort_generation'])
            phase[good] = dict(native=both[0], exact=both[1], delta=delta, cohort_attribution=dict(attribution_counts))
        phases[f'{start}-{end-1}'] = phase
    birth_sets = []
    for obs in observations:
        births = set()
        for current in obs:
            for tile, cell in enumerate(flat(current)):
                ident = identity(cell)
                if ident:
                    births.add((tile, *ident))
        birth_sets.append(births)
    early_births = []
    used = set()
    for native in sorted(birth_sets[0], key=lambda key: (key[-1], key[0])):
        tile, kind, species, birth = native
        if not (6 <= birth <= 10 and (kind == 'animal' or species == 'STRAWBERRY')):
            continue
        next_native = min((row[-1] for row in birth_sets[0] if row[0] == tile and row[-1] > birth), default=30)
        candidates = [row for row in birth_sets[1] if row not in used and row[:3] == native[:3]
                      and birth <= row[-1] < next_native]
        match = min(candidates, key=lambda row: row[-1]) if candidates else None
        if match:
            used.add(match)
        early_births.append(dict(tile=tile, kind=kind, species=species, native_birth=birth,
            exact_birth=match[-1] if match else None, delay=match[-1]-birth if match else None,
            note='First observed same-tile/type cohort before next native replacement; delayed birth may include a replacement after an unobserved same-day loss.'))
    return dict(method='Potential midnight generation uses actual survivor birth dates, observed feeding/care bank and fertilization/water state before yield capping. Potential minus collection and held-yield change is cap loss or yield removed with a cohort; daily snapshots cannot separate those two. Same-cohort comparisons require identical tile/type/birth surviving that night in both arms, so deliberate native exits are excluded.', phases=phases, early_birth_matching=early_births)


def attribution(q0, r0, q1, r1):
    """Exact daily arithmetic; an undefined price stays unallocated, never invented."""
    if q0 and q1:
        p0, p1 = r0/q0, r1/q1
        volume = (q1-q0)*(p0+p1)/2
        price = (p1-p0)*(q0+q1)/2
        unmatched = 0
    else:
        p0, p1 = (r0/q0 if q0 else None), (r1/q1 if q1 else None)
        volume = price = 0
        unmatched = r1-r0
    assert abs((r1-r0)-(volume+price+unmatched)) < 1e-7
    return dict(native_units=q0, exact_units=q1, native_revenue=r0, exact_revenue=r1,
                native_average_price=p0, exact_average_price=p1,
                matched_daily_volume_component=volume, matched_daily_average_price_component=price,
                unmatched_sale_day_revenue=unmatched, identical_units=q0 == q1)


def analyze(native_path):
    exact_path = BASE / 'runs/exact' / native_path.name
    source = json.loads(native_path.read_text())
    exact = json.loads(exact_path.read_text())
    assert source['eligible'] and exact['eligible'] and source['recorded_cash_match']
    assert source['ledger_verified'] and exact['ledger_verified']
    seat = source['case']['seat']
    assert source['shops'] == exact['shops']
    original_actions = native_path.with_suffix('.actions.json')
    exact_actions = exact_path.with_suffix('.actions.json')
    a0, a1 = json.loads(original_actions.read_text()), json.loads(exact_actions.read_text())
    assert a0[1-seat] == a1[1-seat]
    sides = {}
    for side, player in (('own', seat), ('rival', 1-seat)):
        ledgers = source['daily'][player], exact['daily'][player]
        total = paired(period(ledgers[1], 6, 30), period(ledgers[0], 6, 30))
        cash_delta = ledgers[1][-1]['money']-ledgers[0][-1]['money']
        assert cash_delta == sum(total['revenue'].values())-sum(total['spend'].values())
        days = []
        for day in range(6, 30):
            n, e = (period(ledger, day, day+1) for ledger in ledgers)
            products = {good: attribution(n['sold_units'].get(good, 0), n['revenue'].get(good, 0),
                e['sold_units'].get(good, 0), e['revenue'].get(good, 0)) for good in GOODS}
            days.append(dict(day=day, delta=paired(e, n), products=products))
        phases = {f'{start}-{end-1}': paired(period(ledgers[1], start, end), period(ledgers[0], start, end)) for start, end in PHASES}
        checkpoints = {}
        for day in (6, 11, 12, 18, 24, 29):
            n = source['diagnostics'][player][day]['current_observation']
            e = exact['diagnostics'][player][day]['current_observation']
            nc, ec = cohorts(n), cohorts(e)
            checkpoints[str(day)] = dict(native=nc, exact=ec,
                delta={k: subtract(ec[k], nc[k]) if ec[k] is not None else None for k in nc})
        sides[side] = dict(total=total, cash_delta=cash_delta, phases=phases,
                           days=days, checkpoints=checkpoints)
    market = []
    for day in range(6, 30):
        n, e = (game['diagnostics'][seat][day]['current_observation']['market'] for game in (source, exact))
        delta_inv = subtract(e['inventory'], n['inventory'])
        proofs = {}
        for good in FOCUS:
            own_sales_delta = exact['daily'][seat][day]['sold_units'].get(good, 0)-source['daily'][seat][day]['sold_units'].get(good, 0)
            rival_sales_delta = exact['daily'][1-seat][day]['sold_units'].get(good, 0)-source['daily'][1-seat][day]['sold_units'].get(good, 0)
            # Neither side buys these products; identical shops yield the same draw.
            assert all(not game['daily'][s][day]['spend'].get('BUY_PRODUCT:'+good, 0) for game in (source, exact) for s in (0, 1))
            # Official _commit_unit does not add supply for a $1 sale. The
            # residual therefore measures the difference in floor-price sales
            # ignored by the market; it must not be treated as missing trades.
            ignored_floor_sales_delta = own_sales_delta+rival_sales_delta-delta_inv.get(good, 0)
            proofs[good] = dict(own_cumulative_sales_delta=own_sales_delta, rival_cumulative_sales_delta=rival_sales_delta,
                market_inventory_delta=delta_inv.get(good, 0), implied_floor1_excluded_supply_delta=ignored_floor_sales_delta,
                native_price=n['prices'][good], exact_price=e['prices'][good])
        market.append(dict(day=day, inventory_delta=delta_inv, price_delta=subtract(e['prices'], n['prices']), focus_inventory_conservation=proofs))
    rival_physical_equal_each_day = all(not row['delta']['physical'] for row in sides['rival']['days'])
    return dict(episode=source['case']['episode'], seat=seat,
        hashes={str(p.relative_to(ROOT)): sha(p) for p in (native_path, exact_path, original_actions, exact_actions)},
        native_margin=source['margin'], exact_margin=exact['margin'],
        recorded_rival_actions_exact=True, rival_physical_equal_each_day=rival_physical_equal_each_day,
        sides=sides, market=market, production=production_audit(source, exact, seat))


def aggregate(rows):
    n = len(rows)
    result = dict(worlds=n, native_mean_margin=sum(r['native_margin'] for r in rows)/n,
                  exact_mean_margin=sum(r['exact_margin'] for r in rows)/n)
    for side in ('own', 'rival'):
        total = {field: Counter() for field in FIELDS}
        phases = {f'{start}-{end-1}': {field: Counter() for field in FIELDS} for start, end in PHASES}
        components = {g: Counter() for g in GOODS}
        for row in rows:
            data = row['sides'][side]
            for field in FIELDS:
                total[field].update(data['total'][field])
            for phase in phases:
                for field in FIELDS:
                    phases[phase][field].update(data['phases'][phase][field])
            for day in data['days']:
                for good, attr in day['products'].items():
                    c = components[good]
                    for key in ('matched_daily_volume_component', 'matched_daily_average_price_component', 'unmatched_sale_day_revenue'):
                        c[key] += attr[key]
                    c['days_identical_positive_units'] += int(attr['identical_units'] and attr['native_units'] > 0)
                    c['days_changed_units'] += int(not attr['identical_units'])
        result[side] = dict(mean_cash_delta=sum(row['sides'][side]['cash_delta'] for row in rows)/n,
            mean_total={f: {k: v/n for k, v in c.items()} for f, c in total.items()},
            mean_phases={phase: {f: {k: v/n for k, v in c.items()} for f, c in fields.items()} for phase, fields in phases.items()},
            attribution_by_product={good: {k: v if k.startswith('days_') else v/n for k, v in c.items()} for good, c in components.items()})
    result['rival_physical_identical_each_day_worlds'] = sum(row['rival_physical_equal_each_day'] for row in rows)
    result['focus_dawn_inventory_records'] = len(rows)*24*len(FOCUS)
    result['production_mean_phases'] = {}
    for phase in ('6-10', '11-17', '18-23'):
        result['production_mean_phases'][phase] = {}
        for good in FOCUS:
            groups = {k: Counter() for k in ('native', 'exact', 'delta', 'cohort_attribution')}
            for row in rows:
                for k, group in groups.items():
                    group.update(row['production']['phases'][phase][good][k])
            result['production_mean_phases'][phase][good] = {k: {key: val/n for key, val in c.items()} for k, c in groups.items()}
    result['early_birth_delay_counts'] = {}
    for row in rows:
        for birth in row['production']['early_birth_matching']:
            counts = result['early_birth_delay_counts'].setdefault(birth['species'], Counter())
            counts[str(birth['delay']) if birth['delay'] is not None else 'not_observed'] += 1
    return result


def main():
    rows = [analyze(path) for path in sorted((BASE / 'controls').glob('oracle6-*.json')) if not path.name.endswith('.actions.json')]
    assert len(rows) == 8
    result = dict(scope='EIGHT_OLD_WORLD_COMPONENT_DIAGNOSTICS_NOT_NEW_WORLD_POLICY',
        games_executed=0, source_script_sha256=sha(Path(__file__)),
        method='Daily paired sold-unit and revenue identity. Matched days split symmetrically into quantity and realized-average-price components; no price is invented on zero-sale days. Same-world dawn inventory differs by sales at prices above $1: official _commit_unit excludes $1 sales from market supply. The residual is reported explicitly. These are accounting decompositions, not independent causal profit estimates.',
        aggregate=aggregate(rows), worlds=rows)
    path = BASE / 'exact_vs_source_product_audit.json'
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding='utf-8')
    print(json.dumps(dict(path=str(path), sha256=sha(path), worlds=len(rows))))


if __name__ == '__main__':
    main()
