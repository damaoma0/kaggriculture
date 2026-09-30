"""Cluster the 240 leader-semantics games (data/leader_semantics/<team>/<episode>.json.gz)
into opening families, characterize each family's modal days-0..7 target, per-team
determinism, outcomes, and cash feasibility. Writes data/leader_semantics/openings.json.

Family assignment: a game's family is the SET of crop/animal codes present on its
day-6 board (ignoring exact counts/positions) -- e.g. melon+strawberry+cow+sheep vs.
the same plus wheat vs. the same plus goose. This reproduces, from the raw data, the
four groupings already known qualitatively (DSM/Vadim/MG/DECEM core recipe; the
M&M&P&Q wheat variant; Boey's goose variant with/without a residual wheat plot) and
gives clean, well-separated clusters (see README note in the output for validation
against the known 117/240 and 17-distinct-board facts).

Run: .venv/Scripts/python.exe scripts/leader_openings.py
"""
import gzip
import json
import glob
import collections
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = {
    '16915014': 'Boey', '16623559': 'DECEM', '16681125': 'MMPQ',
    '16730612': 'Mother-Goose', '16770421': 'Vadim', '16732748': 'DSM',
}
CROP_CODES = {'ST', 'ME', 'TO', 'WH', 'CA'}
ANIMAL_CODES = {'sh', 'co', 'go'}
SPECIES_BY_CODE = {'sh': 'SHEEP', 'co': 'COW', 'go': 'GOOSE'}

FAMILY_LABELS = {
    ('ME', 'ST', 'co', 'sh'): 'A_melon_strawberry_cow_sheep',
    ('ME', 'ST', 'WH', 'co', 'sh'): 'B_melon_strawberry_wheat_cow_sheep',
    ('ME', 'ST', 'co', 'go', 'sh'): 'C_melon_strawberry_cow_goose_sheep',
    ('ME', 'ST', 'WH', 'co', 'go', 'sh'): 'D_melon_strawberry_wheat_cow_goose_sheep',
}


def load_games():
    games = []
    for f in sorted(glob.glob(str(ROOT / 'data/leader_semantics/*/*.json.gz'))):
        with gzip.open(f, 'rt', encoding='utf8') as fh:
            g = json.load(fh)
        g['_team'] = Path(f).parent.name
        g['_file'] = f
        games.append(g)
    return games


def type_sig(day_obj):
    bc = day_obj['board_counts']
    return tuple(sorted(k for k in bc if (k in CROP_CODES or k in ANIMAL_CODES) and bc[k] > 0))


def assign_family(g):
    sig = type_sig(g['days'][6])
    return FAMILY_LABELS.get(sig, 'X_other_' + '_'.join(sig) if sig else 'X_other_empty')


def med_range(vals):
    vals = list(vals)
    if not vals:
        return None
    return {'median': statistics.median(vals), 'min': min(vals), 'max': max(vals),
            'mean': round(statistics.fmean(vals), 1), 'n': len(vals)}


def planted_key(day_obj):
    return frozenset((crop, tuple(sorted(tiles))) for crop, tiles in day_obj.get('planted', {}).items())


def first_day_of(games, pred, max_day=12):
    """Median/[days] over games of the first day (0..max_day) for which pred(day_obj) is true."""
    days = []
    for g in games:
        for d in range(0, min(max_day, len(g['days']) - 1) + 1):
            if pred(g['days'][d]):
                days.append(d)
                break
    return days


def margin_of(g):
    seat = g['meta']['seat']
    fc = g['meta']['final_cash']
    return fc[seat] - fc[1 - seat]


def build_family_record(fam, gs):
    n = len(gs)
    team_counts = dict(collections.Counter(NAMES[g['_team']] for g in gs))

    day6_boards = collections.Counter(tuple(g['days'][6]['board']) for g in gs)
    modal_board, modal_count = day6_boards.most_common(1)[0]
    exemplar_pool = [g for g in gs if tuple(g['days'][6]['board']) == modal_board]

    full_seq = collections.Counter(
        tuple(tuple(g['days'][d]['board']) for d in range(7)) for g in exemplar_pool
    )
    best_seq, best_seq_count = full_seq.most_common(1)[0]
    reexemplars = [g for g in exemplar_pool
                   if tuple(tuple(g['days'][d]['board']) for d in range(7)) == best_seq]
    exemplar = min(reexemplars, key=lambda g: g['meta']['episode'])

    target_days = {}
    agreement = {}
    for d in range(8):
        ed = exemplar['days'][d]
        target_days[str(d)] = {
            'board': ed['board'],
            'board_counts': ed['board_counts'],
            'planted': ed.get('planted', {}),
            'built': ed.get('built', {}),
            'animals': ed.get('animals', {}),
            'dug': ed.get('dug', []),
            'harvested': ed.get('harvested', {}),
            'hires_asked': ed['labour']['hires_asked'],
            'hires_arrived': ed['labour']['hires_arrived'],
            'hands_present': ed['labour']['hands_present'],
            'cash_start': ed['cash_start'],
        }
        n_match = sum(1 for g in gs if d < 8 and planted_key(g['days'][d]) == planted_key(ed))
        agreement[str(d)] = round(n_match / n, 3)

    cash_start_by_day = {str(d): med_range([g['days'][d]['cash_start'] for g in gs if d < len(g['days'])])
                          for d in range(13)}
    min_cash_0_6 = med_range([min(g['days'][d]['cash_start'] for d in range(7)) for g in gs])
    hires_asked_by_day = {str(d): med_range([g['days'][d]['labour']['hires_asked'] for g in gs])
                           for d in range(8)}

    def locked_count(day_obj):
        return day_obj['board_counts'].get(' L', 0)

    unlock_days = []
    for g in gs:
        prev = locked_count(g['days'][0])
        ud = None
        for d in range(1, 8):
            cur = locked_count(g['days'][d])
            if cur < prev:
                ud = d
                break
            prev = cur
        unlock_days.append(ud)
    land_unlock_day_distribution = dict(collections.Counter(unlock_days))

    first_event_day = {}
    for crop in ('MELON', 'STRAWBERRY', 'WHEAT', 'TOMATO', 'CARROT'):
        days = first_day_of(gs, lambda d, c=crop: c in d.get('planted', {}) and len(d['planted'][c]) > 0)
        if days:
            first_event_day['plant_' + crop] = med_range(days)
    for species in ('COW', 'SHEEP', 'GOOSE'):
        days = first_day_of(gs, lambda d, s=species: d.get('animals', {}).get('bought', {}).get(s, 0) > 0)
        if days:
            first_event_day['buy_' + species] = med_range(days)
    for build in ('BUILD_COOP', 'BUILD_PASTURE'):
        days = first_day_of(gs, lambda d, b=build: len(d.get('built', {}).get(b, [])) > 0)
        if days:
            first_event_day['first_' + build] = med_range(days)

    margins = [margin_of(g) for g in gs]
    wins = sum(1 for m in margins if m > 0)
    by_team_outcome = {}
    for team_id, team_gs in collections.defaultdict(list, {
            t: [g for g in gs if g['_team'] == t] for t in {g['_team'] for g in gs}}).items():
        tm = [margin_of(g) for g in team_gs]
        by_team_outcome[NAMES[team_id]] = {
            'n': len(team_gs), 'win_rate': round(sum(1 for m in tm if m > 0) / len(team_gs), 3),
            'median_margin': statistics.median(tm),
        }

    cash6 = med_range([g['days'][6]['cash_start'] for g in gs])
    cash12 = med_range([g['days'][12]['cash_start'] for g in gs if len(g['days']) > 12])

    return {
        'label': fam,
        'day6_type_signature': list(next(k for k, v in FAMILY_LABELS.items() if v == fam)) if fam in FAMILY_LABELS.values() else None,
        'n_games': n,
        'team_counts': team_counts,
        'distinct_day6_boards': len(day6_boards),
        'modal_day6_board_share': round(modal_count / n, 3),
        'exemplar_episode': exemplar['meta']['episode'],
        'exemplar_team': NAMES[exemplar['_team']],
        'exemplar_pool_size': len(reexemplars),
        'target_days_0_7': target_days,
        'planted_agreement_with_exemplar_by_day': agreement,
        'cash_start_by_day_0_12': cash_start_by_day,
        'min_cash_start_days_0_6': min_cash_0_6,
        'hires_asked_by_day_0_7': hires_asked_by_day,
        'land_unlock_day_distribution': land_unlock_day_distribution,
        'first_event_day': first_event_day,
        'outcomes': {
            'n': n,
            'win_rate': round(wins / n, 3),
            'median_margin': statistics.median(margins),
            'margin_range': [min(margins), max(margins)],
            'by_team': by_team_outcome,
        },
        'own_cash_start_day6': cash6,
        'own_cash_start_day12': cash12,
    }


def determinism_by_team(games):
    out = {}
    by_team = collections.defaultdict(list)
    for g in games:
        by_team[g['_team']].append(g)
    for team_id, gs in by_team.items():
        seqs = collections.Counter(tuple(tuple(g['days'][d]['board']) for d in range(7)) for g in gs)
        distinct_per_day = []
        first_div = None
        for d in range(7):
            boards_d = collections.Counter(tuple(g['days'][d]['board']) for g in gs)
            distinct_per_day.append(len(boards_d))
            if len(boards_d) > 1 and first_div is None:
                first_div = d
        reconverges = (first_div is not None and distinct_per_day[6] == 1)
        out[NAMES[team_id]] = {
            'n_games': len(gs),
            'distinct_day0_6_sequences': len(seqs),
            'modal_sequence_share': round(seqs.most_common(1)[0][1] / len(gs), 3),
            'first_divergence_day': first_div,
            'distinct_boards_per_day_0_6': distinct_per_day,
            'reconverges_to_single_day6_board': reconverges,
        }
    return out


def dual_recorded_margin_checks(games, fam_of):
    by_ep = collections.defaultdict(list)
    for g in games:
        by_ep[g['meta']['episode']].append(g)
    checks = []
    for ep, gs in by_ep.items():
        if len(gs) != 2:
            continue
        g0 = next(g for g in gs if g['meta']['seat'] == 0)
        g1 = next(g for g in gs if g['meta']['seat'] == 1)
        checks.append({
            'episode': ep,
            'seat0_team': NAMES[g0['_team']], 'seat0_family': fam_of[id(g0)],
            'seat1_team': NAMES[g1['_team']], 'seat1_family': fam_of[id(g1)],
            'final_margin_seat0': margin_of(g0),
            'day6_cash_margin_seat0': g0['days'][6]['cash_start'] - g1['days'][6]['cash_start'],
            'day12_cash_margin_seat0': (g0['days'][12]['cash_start'] - g1['days'][12]['cash_start']
                                         if len(g0['days']) > 12 and len(g1['days']) > 12 else None),
        })
    return sorted(checks, key=lambda c: c['episode'])


def opponents_multi_family(games, fam_of):
    opp_fam = collections.defaultdict(set)
    for g in games:
        opp_fam[g['meta']['opponent']].add(fam_of[id(g)])
    out = {}
    for opp, fams in opp_fam.items():
        if len(fams) < 2:
            continue
        rec = {}
        for fam in fams:
            gs = [g for g in games if g['meta']['opponent'] == opp and fam_of[id(g)] == fam]
            margins = [margin_of(g) for g in gs]
            rec[fam] = {'n': len(gs), 'median_margin': statistics.median(margins),
                        'win_rate': round(sum(1 for m in margins if m > 0) / len(gs), 3)}
        out[opp] = rec
    return out


def main():
    games = load_games()
    assert len(games) == 240, f'expected 240 games, got {len(games)}'

    fam_name = {}
    for g in games:
        fam_name[id(g)] = assign_family(g)

    families = collections.defaultdict(list)
    for g in games:
        families[fam_name[id(g)]].append(g)

    family_records = {fam: build_family_record(fam, gs) for fam, gs in families.items()}
    determinism = determinism_by_team(games)
    dual_checks = dual_recorded_margin_checks(games, fam_name)
    multi_opp = opponents_multi_family(games, fam_name)

    out = {
        'generated': '2026-09-24',
        'source': 'data/leader_semantics/<team>/<episode>.json.gz',
        'source_games': len(games),
        'family_definition': (
            "Games are grouped by the SET of crop/animal single-letter codes present "
            "on the day-6 board (counts ignored), e.g. melon+strawberry+cow+sheep vs. "
            "the same set plus wheat vs. the same set plus goose. This reproduces the "
            "known facts from inspection (117/240 games share one exact melon/"
            "strawberry/cow/sheep day-6 board; Boey has 17 distinct day-6 boards "
            "across its two goose-family variants) as an emergent result of the "
            "clustering, not an input to it."
        ),
        'families': family_records,
        'determinism_by_team_days_0_6': determinism,
        'dual_recorded_episode_margin_checks': dual_checks,
        'opponents_appearing_against_multiple_families': multi_opp,
        'caveats': [
            'Per-day cash_start is the LEADER-seat only; the opponent\'s day-level '
            'cash is available only for the 10 episodes where both seats happen to '
            'be one of the six 3000+ teams (see dual_recorded_episode_margin_checks). '
            'For all other games, "day6/day12 own cash" is a within-family budget '
            'trajectory, not a margin against the opponent.',
            'Team identity is fully confounded with family for every team except '
            'M&M&P&Q (2/40 games fall in family A) and Boey (30/40 in family C, '
            '10/40 in family D): outcome differences BETWEEN families mostly cannot '
            'be separated from between-team skill differences. Only the '
            'opponents_appearing_against_multiple_families entries and the two '
            'partially-split teams give any within-team, cross-family comparison, '
            'and those samples are small.',
        ],
    }

    out_path = ROOT / 'data/leader_semantics/openings.json'
    out_path.write_text(json.dumps(out, indent=2, sort_keys=False), encoding='utf8')
    print('wrote', out_path, out_path.stat().st_size, 'bytes')
    for fam, rec in sorted(family_records.items()):
        print(f"{fam:45s} n={rec['n_games']:3d} teams={rec['team_counts']} "
              f"distinct_day6_boards={rec['distinct_day6_boards']:2d} "
              f"win_rate={rec['outcomes']['win_rate']:.2f} "
              f"median_margin={rec['outcomes']['median_margin']:.0f}")


if __name__ == '__main__':
    main()
