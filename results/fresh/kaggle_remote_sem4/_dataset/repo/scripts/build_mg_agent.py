"""Build Mother-Goose-policy agents on our chassis: the frozen benchmark plus the MG slot layer.

Every build is agents/benchmark_frozen_56280048.py (verified by SHA-256) followed by one appended block:
  1. the parent capture (Kaggle's loader calls the last callable, so the block captures it first and
     re-exports `agent` last),
  2. scripts/fragments/tape_calendar.py  - forward simulation of the native crew's tape positions,
  3. scripts/fragments/mg_slots.py       - crop swaps serviced by the tape's own visits,
with the variant's configuration substituted for __MGS_CFG__. Output: agents/<name>.py (single file).

Usage: python build_mg_agent.py [name ...]   (no names = build all variants)
"""
from hashlib import sha256
import pprint, sys
from market_corpus import ROOT

BASE = ROOT / 'agents/benchmark_frozen_56280048.py'
BASE_SHA = '07c313e53d390ab6e1dd563fa2059dd1ea78988af4e0df3f8bbe1c6d8085ea4f'
FRAG = ROOT / 'scripts/fragments'

HEADER = '''

# --------------------------------------------------------------------------- {name}
# Mother-Goose policy on our chassis. Appended to the frozen benchmark
# (agents/benchmark_frozen_56280048.py, SHA-256 {sha}); built by scripts/build_mg_agent.py.
# {description}
_MGS_NAME = {name!r}
_MGS_PARENT = [v for v in globals().values() if callable(v)][-1]
'''

FOOTER = '''

agent = globals().pop('agent')
'''

STRAW11 = dict(name='straw11', **{'from': 'STRAWBERRY', 'to': 'TOMATO'}, days=(11, 11), min_units=4)

# Mother-Goose R5 + R9 on the tape's day-11 strawberry batch (docs/mg_policy.md). Her R5 counts refer to the
# ~14 tiles freed on days 12-13; here they are applied as FRACTIONS of our batch (table_slots=1): the share of
# the batch kept as strawberries by strawberry-demanding shop instances among the first four (the undrawn
# fourth counted at its expected 0.5): <=1 -> 0-2 of 14, 2 -> 5-9, 3 -> 9-16, 4 -> all. Tomatoes fill the rest,
# capped at 8 of 13 (her 7-11 of 14) when no tomato shop is visible. Her remainder-to-wheat is NOT copied:
# wheat on a strawberry calendar gets two units, so the remainder stays strawberry. R9: one melon on the
# batch, her tiles (3,6)/(1,6) preferred.
MG_BATCH = dict(name='mg_batch', kind='batch', days=(11, 11), decide_day=10, shops_upto=4, table_slots=1,
                straw_keep=[(0, 0.05), (1, 0.07), (2, 0.5), (3, 0.85), (4, 1.0)], tomato_cap_no_shop=8,
                melons=1, melon_tiles=[(3, 6), (1, 6)], melon_min_units=5, min_units=4,
                **{'from': 'STRAWBERRY'})
# Mother-Goose R6: share of wheat replants on days 14-21 that become tomatoes, by tomato-demanding shop
# instances visible (her fitted ranges 0 -> 0-11%, 1 -> 0-14%, 2 -> 6-24%, 3 -> 17-29%, 4 -> 53-64%; midpoints).
MG_R6 = dict(name='mg_r6', kind='share', days=(14, 21), decide_day=14, share_day=14, min_units=4,
             share=[(0, 0.05), (1, 0.07), (2, 0.15), (3, 0.23), (4, 0.58)], **{'from': 'WHEAT', 'to': 'TOMATO'})
# Step 2: demand-keyed strawberry allocation derived from engine economics (not her fitted table): a market
# model with the engine price curves and consumption rates values every allocation of the tape's day-11
# strawberry batch (strawberry / tomato / melon) and every conversion of day 11-13 wheat slots into
# strawberries, against a lineage-clone opponent; the margin-maximising allocation is committed.
ECON = dict(name='econ', kind='econ', days=(11, 11), decide_day=10, wheat_days=(11, 13), max_add=12,
            max_melons=0, objective='margin', min_gain=150.0, tape_units_per_straw=7.5, wheat_uplift=8)
# Step 4: her herd rule R8 - sheep placed by the tape on days 6-11 become geese unless a Yarn Store or two
# milk shops lead the route (first two shops); ``yarn_exception=False`` converts in Yarn worlds too.
HERD = dict(name='herd', kind='herd', days=(6, 11), decide_day=6, convert=('SHEEP',), to='GOOSE', condition='mg')
# decided at each purchase from the shops visible then: her default (sheep -> geese) only while no Yarn Store is
# visible; V48's direction (geese -> sheep) once a Yarn Store is visible.
HERD_NOYARN = dict(HERD, name='herd_noyarn', condition='no_yarn_visible')
HERD_V48 = dict(HERD, name='herd_v48', convert=('GOOSE',), to='SHEEP', condition='yarn_visible')
# Step 5 opponent: her policy as reimplemented on our chassis - her opening orders, her fitted R5 table in both
# directions (reductions from MG_BATCH; additions on day 11-13 wheat slots by strawberry-demanding shops among
# the first four: her 34-41 plants at 3, 43-49 at 4, against the tape's 33), R9 one melon, R6, R8.
MG_LIVE = {'opening': 'nash5', 'swaps': [dict(MG_BATCH, wheat_days=(11, 13), add_table=[(0, 0), (2.5, 0), (3, 4), (4, 12)]),
                                      MG_R6, HERD]}
HANDS = dict(enabled=True, max_hands=2, first_day=12, latest_hour=9, cash_margin=500)
VARIANTS = {
    'mgs_null': ('Null control: calendar and seed logic active, no swaps.', {'swaps': []}),
    'mgs_t11': ('Every day-11 tape strawberry planting that the calendar can service becomes a tomato.',
                {'swaps': [STRAW11]}),
    'mgs_t11_half': ('Every other day-11 tape strawberry planting becomes a tomato.',
                     {'swaps': [dict(STRAW11, every=2)]}),
    'mgs_w14': ('Every third tape wheat planting on days 14-18 becomes a tomato (wheat-slot servicing test).',
                {'swaps': [dict(name='wheat14', days=(14, 18), every=3, min_units=4,
                                **{'from': 'WHEAT', 'to': 'TOMATO'})]}),
    # milestone 2: her crop rules on the slot engine
    'mg2_batch': ('MG R5+R9: day-11 batch split strawberry/tomato by demand, one second-wave melon.',
                  {'swaps': [MG_BATCH]}),
    'mg2_batch_nomelon': ('MG R5 only (no second-wave melon).', {'swaps': [dict(MG_BATCH, melons=0)]}),
    'mg2_melon1': ('MG R9 only: one second-wave melon on the day-11 batch.',
                   {'swaps': [dict(MG_BATCH, straw_keep=[(0, 1.0), (4, 1.0)], melons=1)]}),
    'mg2_r6': ('MG R6 only: demand-keyed share of day 14-21 wheat replants become tomatoes.', {'swaps': [MG_R6]}),
    'mg2_batch_r6': ('MG R5+R9+R6.', {'swaps': [MG_BATCH, MG_R6]}),
    # steps 1-2
    'mg3_t11v': ('Step 1 check: every day-11 strawberry becomes a tomato, with V219 kept working.',
                 {'swaps': [STRAW11]}),
    'mg3_probe': ('Step 2 validation: the economic rule in dry-run mode (predictions only, no swaps).',
                  {'swaps': [dict(ECON, dry_run=True, probe_keep=[0, 6, 13])]}),
    'mg3_probe2': ('Step 2 validation, with per-product prediction breakdown (dry run).',
                   {'swaps': [dict(ECON, dry_run=True, probe_keep=[0, 6, 13])]}),
    'mg3_probe3': ('Step 2 validation: dry run logging every model input for offline calibration.',
                   {'swaps': [dict(ECON, dry_run=True, probe_keep=[0, 6, 13])]}),
    'mg3_econ': ('Step 2: demand-keyed strawberry allocation, both directions, margin objective.',
                 {'swaps': [ECON]}),
    'mg3_econ_own': ('Step 2 variant: same rule, own-revenue objective.',
                     {'swaps': [dict(ECON, objective='own')]}),
    # step 3: second-wave melon
    'mg4_econ_m': ('Step 3: economic rule may also give 0-2 batch slots to a second-wave melon.',
                   {'swaps': [dict(ECON, max_melons=2)]}),
    'mg4_econ_m1': ('Step 3: her rule - exactly one second-wave melon; the model sets the rest.',
                    {'swaps': [dict(ECON, max_melons=1, force_melons=1)]}),
    'mg4_herd_only': ('Step 4 isolation: her herd rule only.', {'swaps': [HERD]}),
    'mg6_herd_mg': ('Step 4: her R8 (sheep -> geese unless Yarn or two milk shops lead), decided at purchase.', {'swaps': [HERD]}),
    'mg6_herd_noyarn': ('Step 4: sheep -> geese at purchase while no Yarn Store is visible.', {'swaps': [HERD_NOYARN]}),
    'mg6_herd_v48': ('Step 4: V48 direction - geese -> sheep at purchase once a Yarn Store is visible.', {'swaps': [HERD_V48]}),
    'mg6_flip5': ('Step 4: turn-0 wheat flip 5 instead of 70.', {'flip': 5, 'swaps': []}),
    'mg6_nash5': ('Step 4: equilibrium opening - buy the 5 feed wheat on turn 0 and keep them; no turn-1 feed purchase '
                  'for the V48 index-1 attack to hit.', {'opening': 'nash5', 'swaps': []}),
    'mg4_r6_only': ('Isolation: her R6 wheat-to-tomato share only.', {'swaps': [MG_R6]}),
    # steps 2-3 with the calibrated market model (sales spread over 4 days; V219 tomato supply)
    'mg5_econ': ('Step 2 (calibrated model): demand-keyed strawberry allocation, both directions, margin.',
                 {'swaps': [ECON]}),
    'mg5_econ_own': ('Step 2 (calibrated model), own-revenue objective.', {'swaps': [dict(ECON, objective='own')]}),
    'mg5_econ_m': ('Step 3: calibrated rule may also give 0-2 batch slots to a second-wave melon.',
                   {'swaps': [dict(ECON, max_melons=2)]}),
    'mg5_econ_m1': ('Step 3: her rule - exactly one second-wave melon; the calibrated model sets the rest.',
                    {'swaps': [dict(ECON, max_melons=1, force_melons=1)]}),
    # fertilized-tomato fix: swapped tomatoes use the fertilizer the tape brings to the slot on its own visit
    'mg7_fert_t11': ('Fix isolation: every day-11 strawberry becomes a tomato, fertilized on the tape visit.',
                     {'fertilize_swaps': True, 'swaps': [STRAW11]}),
    # step 4 combined herd: sheep -> geese while no Yarn Store is visible, geese -> sheep once one is
    'mg8_herd_both': ('Step 4: both herd directions, each decided at purchase from the visible shops.',
                      {'swaps': [HERD_NOYARN, HERD_V48]}),
    # step 5 candidates: strawberry rule + model-chosen melons + both herd directions, per opening
    'cand_v1_flip70': ('Candidate: calibrated strawberry rule with melons, both herd directions, V45 opening (flip 70).',
                       {'swaps': [dict(ECON, max_melons=2), HERD_NOYARN, HERD_V48]}),
    'cand_v1_flip5': ('Candidate: same, turn-0 flip 5.', {'flip': 5, 'swaps': [dict(ECON, max_melons=2), HERD_NOYARN, HERD_V48]}),
    'cand_v1_nash5': ('Candidate: same, equilibrium opening (buy 5 feed wheat on turn 0 and keep them).',
                      {'opening': 'nash5', 'swaps': [dict(ECON, max_melons=2), HERD_NOYARN, HERD_V48]}),
    # owned hands (production-window servicing of swapped tomatoes)
    'mg9_hands_t11': ('Owned-hand isolation: every day-11 strawberry becomes a tomato; hands service ages 7-10.',
                      {'hands': dict(HANDS), 'swaps': [STRAW11]}),
    'mg9_hands_econ': ('Candidate v2: calibrated rule valuing tomatoes at 7.5 units with hand cost, melons, both herd '
                       'directions, equilibrium opening, owned hands.',
                       {'hands': dict(HANDS), 'opening': 'nash5',
                        'swaps': [dict(ECON, max_melons=2, tomato_units_per_plant=7.5), HERD_NOYARN, HERD_V48]}),
    'mg10_hands_t11': ('Owned hands v2 (tape-coverage subtraction, midnight dump, up to 3 hands): all 13 slots -> tomatoes.',
                       {'hands': dict(HANDS, max_hands=3), 'swaps': [STRAW11]}),
    'mg10_hands_econ': ('Candidate v2b: as mg9_hands_econ with owned hands v2.',
                        {'hands': dict(HANDS, max_hands=3), 'opening': 'nash5',
                         'swaps': [dict(ECON, max_melons=2, tomato_units_per_plant=7.5), HERD_NOYARN, HERD_V48]}),
    # scenario-weighted rule (econ2): six undrawn-shop demand scenarios, separable market sims, coarse option grid
    'mg11_probe': ('econ2 dry run: decisions only, no swaps.',
                   {'hands': dict(HANDS), 'swaps': [dict(ECON, kind='econ2', name='econ2', max_melons=2, tomato_units_per_plant=7.5, dry_run=True)]}),
    'mg11_econ2': ('Candidate v3: econ2 rule with hands v1, melons, both herd directions, equilibrium opening.',
                   {'hands': dict(HANDS), 'opening': 'nash5',
                    'swaps': [dict(ECON, kind='econ2', name='econ2', max_melons=2, tomato_units_per_plant=7.5), HERD_NOYARN, HERD_V48]}),
    'mg11_econ2_fast': ('Candidate v3 with a coarser option grid (keep 0/4/8/13, adds 0/3/6) for timing headroom.',
                        {'hands': dict(HANDS), 'opening': 'nash5',
                         'swaps': [dict(ECON, kind='econ2', name='econ2', max_melons=2, tomato_units_per_plant=7.5,
                                        keep_grid=(0, 4, 8, 13), add_grid=(0, 3, 6)), HERD_NOYARN, HERD_V48]}),
    # ---- V50-based builds (public frontier as the base; our production layers on top) ----
    'x50_null': ('V50 + slot layer with no swaps (control: must reproduce V50).', {'_base': 'v50', 'swaps': []}),
    'x50_econ2': ('V50 + scenario-weighted strawberry/tomato/melon rule + owned hands. V50 keeps its own opening and herd.',
                  {'_base': 'v50', 'hands': dict(HANDS),
                   'swaps': [dict(ECON, kind='econ2', name='econ2', max_melons=2, tomato_units_per_plant=7.5)]}),
    'x50_econ2_nohands': ('V50 + scenario-weighted rule, tape visits only (tomatoes valued at 5 units).',
                          {'_base': 'v50', 'swaps': [dict(ECON, kind='econ2', name='econ2', max_melons=2, tomato_units_per_plant=5.0)]}),
    # step 5 opponent
    'mg_live': ('Mother-Goose policy reimplemented on our chassis (opponent for the panel).', MG_LIVE),
    'mg_live_crops': ('Her reimplemented policy without her herd rule (R8 was a misreading and costs money).',
                      dict(MG_LIVE, swaps=[r for r in MG_LIVE['swaps'] if r.get('kind') != 'herd'])),
}


BASES = {None: (BASE, BASE_SHA),
         'v50': (ROOT / 'agents/v50_public.py', '044a26601be23816d397c51c22c4d86b938f8bac4b914f9bea1fbe38bac1e8a5')}


def build(name):
    description, cfg = VARIANTS[name]
    cfg = dict(cfg)
    base_path, base_sha = BASES[cfg.pop('_base', None)]
    base = base_path.read_bytes()
    assert sha256(base).hexdigest() == base_sha, f'{base_path.name} drifted'
    block = HEADER.format(name=name, sha=base_sha, description=description).replace(
        'agents/benchmark_frozen_56280048.py', f'agents/{base_path.name}').replace('frozen benchmark', 'base agent')
    block += (FRAG / 'tape_calendar.py').read_text(encoding='utf-8') + '\n\n'
    block += (FRAG / 'mg_slots.py').read_text(encoding='utf-8').replace('__MGS_CFG__', pprint.pformat(cfg, width=110))
    block += '\n\n' + (FRAG / 'mg_hands.py').read_text(encoding='utf-8')
    block += FOOTER
    out = ROOT / 'agents' / f'{name}.py'
    out.write_bytes(base + block.encode('utf-8'))
    src = out.read_text(encoding='utf-8')
    compile(src, str(out), 'exec')
    print(f'built {name}: sha {sha256(out.read_bytes()).hexdigest()[:12]}')


if __name__ == '__main__':
    for n in (sys.argv[1:] or VARIANTS):
        build(n)
