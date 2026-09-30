"""Compare service-weighted vacant-tile assignments; keep live assets fixed."""
from copy import deepcopy
from functools import lru_cache
from semantic_strategy import Cohort, place_cohorts
from cumulative_engine_profiles import engine_profile
from .common import E, species


@lru_cache(maxsize=256)
def service_load(s, day):
    tile=E._new_plant(s,day,24) if s in E.CROPS else E._new_animal(s,day)
    output,work,inputs,release=engine_profile(tile,day,30,fertilize=True)
    # One visit per service day plus pickup/drop burden; multiple commands on
    # one visit are not separate shed journeys.
    return sum(bool(j) for j in work.values()) + .25*sum(
        j.get('harvest',0)+j.get('collect_fertilizer',0)+j.get('feed',0)+j.get('fertilize',0)
        for j in work.values())


def allocatable(tile,day):
    if tile is None: return True
    if not isinstance(tile,dict): return False
    if tile.get('kind')=='WEED': return True
    s=species(tile)
    if s in E.CROPS and E.CROPS[s]['ongoing']:
        r=E.CROPS[s]
        last=tile['planted_day']+r['first_yield_day']+(r['max_yield']-1)*r['interval']
        return day>=last and tile.get('yield_units',0)==0
    return False


def assign(obs, quantities, mode='service'):
    farm=deepcopy(obs['farms'][obs['player']])
    for y,row in enumerate(farm['tiles']):
        for x,tile in enumerate(row):
            if allocatable(tile,obs['day']): farm['tiles'][y][x]=None
    # Opening wheat is a temporary occupant of future strawberry land. Allocate
    # the whole planned tile lifecycle, not just its first two wheat days.
    cohorts=[Cohort(s,int(n), (service_load(s,obs['day']) +
                (service_load('STRAWBERRY',obs['day']+2) if s=='WHEAT' and obs['day']<=1 else 0))
                if mode=='service' else 1)
             for s,n in quantities.items() if n>0]
    return place_cohorts(farm,cohorts)


def vacant_count(obs):
    return sum(allocatable(t,obs['day']) for row in obs['farms'][obs['player']]['tiles'] for t in row)
