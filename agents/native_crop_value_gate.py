"""Conservative economic gate for the bounded native carrot substitution.

Appended after native_crop_swap_overlay.py. No fitted thresholds or future shops:
compare two unfertilized carrot units with 3.5 displaced wheat units, including
the extra carrot seed cost (inherited wheat seed orders are retained).
"""
_VALUE_PROJECT = _cohort_project
_VALUE_TOPUP = _cohort_seed_topup

def _cohort_value_positive(obs):
    day=int(obs['step'])//24
    if not 12<=day<=24:return False
    shops=obs['town']['unlocked_shops']
    drain=1+12*shops.count('PET_CAFE')+6*shops.count('FARMERS_MARKET')
    # Conservative supply allowance: all observed carrots that can mature by
    # delivery contribute their maximum four units. Unknown future crops/shops
    # are not observed and are not supplied to this calculation.
    supply=0
    for farm in obs['farms']:
        for row in farm['tiles']:
            for tile in row:
                if isinstance(tile,dict) and tile.get('crop')=='CARROT' and tile['planted_day']+2<=day+3:
                    supply+=4
    inventory=obs['market']['inventory']['CARROT']-3*drain+supply
    price=sum(_r37_market_price('CARROT',inventory+j) for j in range(8))/8
    wheat=obs['market']['prices']['WHEAT']
    return 2*price-3.5*wheat-20>0

def _cohort_project(obs,action,state):
    state['enabled']=_cohort_value_positive(obs)
    return _VALUE_PROJECT(obs,action,state)

def _cohort_seed_topup(obs,action,state):
    # Last audited native wheat replants are day 24; reserve their seeds before
    # then rather than continually replacing the final consumed reserve.
    if int(obs['step'])//24>=24:return action
    return _VALUE_TOPUP(obs,action,state)

_SWAP_CONFIG.update(max_plots=4,last_plant_day=24)
agent=globals().pop('agent')
