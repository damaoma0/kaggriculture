"""Engine-derived maintenance, replacement releases and explicit skips."""
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import json
from semantic_strategy import maintenance, maintenance_skip_effect, production_days
from .common import E, species, tiles


@lru_cache(maxsize=16384)
def _skip(tile_json, day, op):
    return maintenance_skip_effect(json.loads(tile_json),day,op,E)


def choose_service(tile, day, prices, *, optimize=True, opening=False):
    commands, omissions = maintenance(tile,day,E)
    if not optimize or not species(tile):
        return commands, omissions
    # Sequential, not additive, decisions: at most one changed operation per
    # asset/day. Each candidate preserves life under full subsequent maintenance.
    candidates = []
    for op in ('WATER','CARE','FERTILIZE','FEED'):
        if [op] not in commands:
            continue
        effect = _skip(json.dumps(tile,sort_keys=True),day,op)
        if effect['skipped']['lost_to_lack_of_service']:
            continue
        delta = sum(n*prices.get(p,0) for p,n in effect['output_delta'].items())
        saved = sum((effect['full']['consumed'].get(p,0)-effect['skipped']['consumed'].get(p,0))
                    *prices.get(p,0) for p in set(effect['full']['consumed'])|set(effect['skipped']['consumed']))
        # Full care remains default. Allow a zero-output-loss skip or an input
        # saving whose estimated lost output is smaller. The opening can fund
        # survival before purchasing an otherwise unreachable maximal cohort.
        harmless = all(n >= 0 for n in effect['output_delta'].values())
        if harmless or (op == 'FERTILIZE' and delta+saved>0) or (
                opening and op=='FEED' and day==0 and tile.get('animal')):
            candidates.append((delta+saved,op,effect,harmless))
    if candidates:
        _,op,effect,harmless=max(candidates,key=lambda r:(r[0],r[1]))
        commands=[c for c in commands if c != [op]]
        # Care without feeding does not enter the bonus bank.
        if op=='FEED': commands=[c for c in commands if c != ['CARE']]
        omissions.append(dict(op=op, reason='zero_output_loss' if harmless else
            'opening_finance_tradeoff' if op=='FEED' else 'input_cost_exceeds_estimated_output',
            output_delta=effect['output_delta']))
    return commands, omissions


def job_chain(pos, commands, tile):
    result=[]
    for command in commands:
        effect={}
        if command[0]=='HARVEST':
            s=species(tile)
            p=E.ANIMALS[s]['product'] if s in E.ANIMALS else s
            n=tile.get('yield_units',0)
            if s in E.CROPS and not E.CROPS[s]['ongoing']:
                n=E.CROPS[s]['max_yield']
            effect[p]=n
        result.append(dict(tile=list(pos),cmd=command,effect=effect))
    return result


def existing_jobs(obs, *, optimize=True, opening=False, early_wheat=0, collect_only=False):
    jobs, skips=[],[]
    for pos,tile in tiles(obs):
        if not species(tile):
            continue
        commands,omissions=choose_service(tile,obs['day'],obs['market']['prices'],
                                          optimize=optimize,opening=opening)
        s=species(tile)
        if s=='WHEAT' and early_wheat>0 and obs['day']-tile['planted_day']>=2:
            # The early strawberry family deliberately sacrifices later wheat
            # growth to release land. Harvest maturity is checked by the engine.
            commands=[['HARVEST']]
            early_wheat-=1
        if collect_only:
            commands=[c for c in commands if c[0] in ('HARVEST','COLLECT_FERTILIZER')]
        elif s in E.CROPS and E.CROPS[s]['ongoing']:
            last=tile['planted_day']+E.CROPS[s]['first_yield_day']+(E.CROPS[s]['max_yield']-1)*E.CROPS[s]['interval']
            if obs['day']>=last:
                commands=[c for c in commands if c[0]=='HARVEST']+[['DIG']]
        jobs.extend(job_chain(pos,commands,tile))
        skips.extend(dict(tile=list(pos),**r) for r in omissions)
    return jobs,skips


def establishment_jobs(obs, assignments, *, optimize=True, opening=False):
    jobs,skips=[],[]
    for row in assignments:
        s,pos=row['species'],row['tile']
        current=obs['farms'][obs['player']]['tiles'][pos[1]][pos[0]]
        before=[]
        if isinstance(current,dict):
            # Layout allows weeds and genuinely spent plants only.
            before=[['DIG']]
        if s in E.CROPS:
            tile=E._new_plant(s,obs['day'],24)
            before.append(['PLANT',s])
        else:
            tile=E._new_animal(s,obs['day'])
            before.extend([['BUILD_'+E.ANIMALS[s]['structure']],['PLACE',s,1]])
        commands,omissions=choose_service(tile,obs['day'],obs['market']['prices'],
                                           optimize=optimize,opening=opening)
        jobs.extend(job_chain(pos,before+commands,tile))
        skips.extend(dict(tile=list(pos),**r) for r in omissions)
    return jobs,skips
