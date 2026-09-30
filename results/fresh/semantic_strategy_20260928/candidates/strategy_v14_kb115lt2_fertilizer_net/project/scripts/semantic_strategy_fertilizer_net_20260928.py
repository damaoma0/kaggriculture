"""Optional fertilizer resource calendar; pure expectations, not exact routing.

Fertilizer applied on day d covers watering/production service on d..d+2.
Ongoing output 1.65 is represented as 65% fully serviced cohorts and 35%
unfertilized cohorts. Existing output dates/amounts remain the policy's dates.
Only current cohorts and allowlisted current/past public crop state are read.
Future rotations, acquisitions, delivery and financing are not invented here.
"""
from collections import Counter


def public_crop_details(farm, day):
    return [dict(crop=t['crop'],birth=int(t['planted_day']),observation_day=int(day),
                 yield_units=int(t.get('yield_units',0)),
                 fertilized_until_day=int(t.get('fertilized_until_day',-1)),
                 watered_today=bool(t.get('watered_today',False)),count=1)
            for row in farm.get('tiles',[]) for t in row
            if isinstance(t,dict) and t.get('crop')]


def _annual_need(crop, birth, day, harvest, target, detail, rule):
    """Minimal three-day cover for bonuses needed by the inherited target.

    Without fresh yield, use the same modeled history from the planting date;
    earlier input is not charged again. A fresh public yield supersedes it.
    """
    fresh=detail is not None and int(detail.get('observation_day',-1))==day
    begin=day if fresh else birth
    initial=float(detail['yield_units']) if fresh else 1.
    active=int(detail.get('fertilized_until_day',-1)) if detail else -1
    window=(rule['last']+1)//2
    water=[d for d in range(max(begin,birth+window),min(harvest,birth+rule['last'])+1)
           if not (fresh and d==day and detail.get('watered_today',False))]
    baseline=initial+len(water)+sum(d<=active for d in water)
    missing=max(0.,target-baseline)
    inputs=Counter();uncovered=[d for d in water if d>active]
    while missing>1e-9 and uncovered:
        apply=uncovered[0]
        covered=[d for d in uncovered if d<=apply+2]
        inputs[apply]+=1.
        missing-=len(covered)
        uncovered=[d for d in uncovered if d>apply+2]
    return {d:n for d,n in inputs.items() if d>=day},max(0.,missing)


def crop_input_calendar(cohorts, day, release_age, crop_rules, details=None):
    """Expected fertilizer units by application day, plus explicit assumptions.

    Counts may be fractional. Fresh annual yield/water and known active effect
    are credited. Details are matched by public species/birth, never coordinates.
    Stale yields are never reused; an observed active-effect expiry remains a
    valid bound on later modeled days. Missing details use modeled history.
    """
    calendar={d:0. for d in range(day,30)};audit=[]
    grouped={}
    for detail in details or []:
        if int(detail.get('observation_day',day))>day:continue
        grouped.setdefault((detail.get('crop'),int(detail.get('birth',0))),[]).append(detail)
    for c in cohorts:
        crop=c.get('crop');rule=crop_rules.get(crop)
        if not rule:continue
        birth=int(c.get('birth',c.get('planted_day',0)));count=float(c.get('count',1))
        if count<=0:continue
        rows=[];left=count
        for detail in grouped.get((crop,birth),[]):
            n=min(left,max(0,float(detail.get('count',1))))
            if n:rows.append((n,detail));left-=n
            if left<=1e-9:break
        if left>1e-9:rows.append((left,None))
        if rule['interval']:
            # A yield at dawn D is serviced during D-1, not during D.
            dates=[birth+age-1 for age in range(rule['first'],rule['last']+1,rule['interval'])
                   if day<=birth+age-1 and birth+age<=29]
            for n,detail in rows:
                until=int(detail.get('fertilized_until_day',-1)) if detail else -1
                applications=[]
                for d in dates:
                    if d<=until:continue
                    calendar[d]+=.65*n;applications.append(d);until=d+2
                audit.append(dict(crop=crop,birth=birth,count=n,kind='ongoing',
                    fertilized_fraction=.65,service_dates=dates,applications=applications))
            continue
        harvest=min(29,birth+release_age[crop])
        if harvest<max(day,birth+rule['first']):continue
        age=harvest-birth
        units=min(rule['units'],1+max(0,age-(rule['last']+1)//2+1)*2)
        # Match output_calendar's observed annual readiness split exactly.
        remaining_ready=min(count,float(c.get('ready_count',count)))
        split=(harvest==day and day<29 and c.get('observation_day')==day and 'ready_count' in c)
        for n,detail in rows:
            if split and detail is not None and int(detail.get('observation_day',-1))==day:
                projected=int(detail.get('yield_units',0))
                if not detail.get('watered_today') and (rule['last']+1)//2<=day-birth<=rule['last']:
                    projected+=1+int(int(detail.get('fertilized_until_day',-1))>=day)
                ready=projected>={'WHEAT':5,'CARROT':4,'MELON':6}[crop]
                groups=[(n,harvest if ready else harvest+1,units if ready else min(rule['units'],units+2))]
                if ready:remaining_ready=max(0,remaining_ready-n)
            elif split:
                ready=min(n,remaining_ready);remaining_ready-=ready
                groups=[(ready,harvest,units),(n-ready,harvest+1,min(rule['units'],units+2))]
            else:groups=[(n,harvest,units)]
            for mass,end,target in groups:
                if mass<=0:continue
                applications,unachievable=_annual_need(crop,birth,day,end,target,detail,rule)
                for d,value in applications.items():calendar[d]+=mass*value
                audit.append(dict(crop=crop,birth=birth,count=mass,kind='annual',harvest=end,
                    target_units=target,applications=applications,
                    unachievable_units_under_current_yield=unachievable))
    return calendar,audit


def farm_input_calendars(state, config, crop_rules):
    own,oa=crop_input_calendar(state['own_crop_cohorts'],state['day'],config['release_age'],crop_rules,
                               state.get('own_fertilizer_crop_details'))
    rival,ra=crop_input_calendar(state['rival_crop_cohorts'],state['day'],config['release_age'],crop_rules,
                                 state.get('rival_fertilizer_crop_details'))
    return own,rival,dict(own=oa,rival=ra)


def market_input_debits(own, rival, own_private_stock=0.):
    """Own held fertilizer is outside baseline market supply, like held wheat.

    Rival private stock is unknown and receives no invented credit. Harvest
    blending is gross collection; it must not separately subtract these inputs.
    """
    stock=max(0.,float(own_private_stock));out={}
    for day in sorted(set(own)|set(rival)):
        own_need=max(0.,float(own.get(day,0)));rival_need=max(0.,float(rival.get(day,0)))
        carried=min(stock,own_need);stock-=carried
        out[day]=dict(own_use=own_need,rival_use=rival_need,own_stock_credit=carried,
            market_debit=own_need-carried+rival_need,remaining_own_stock=stock)
    return out


def apply_net_outputs(state, config, crop_rules, own, rival=None, history=None):
    """Convert fertilizer to signed inventory-affecting expected net flow.

    A market_net observation already includes its use/buys; only the unobserved
    model fraction is debited. Harvest observations remain gross. Calendars are
    local fresh objects. The rival return also feeds competitive price effects.
    """
    own_use,rival_use,audit=farm_input_calendars(state,config,crop_rules)
    debits=market_input_debits(own_use,rival_use,state.get('stock',{}).get('FERTILIZER',0))
    flow=(history or {}).get('rival_net_daily',{});kind=(history or {}).get('rival_flow_kind')
    if flow and kind not in ('harvest','market_net'):
        raise ValueError('fertilizer_forecast_requires_explicit_rival_flow_kind')
    factor=1.-float(config['observed_supply_weight']) if kind=='market_net' and 'FERTILIZER' in flow else 1.
    for day,row in debits.items():
        own[day]['FERTILIZER']-=row['own_use']-row['own_stock_credit']
        if rival is not None:rival[day]['FERTILIZER']-=factor*row['rival_use']
    return dict(debits=debits,crops=audit,rival_debit_fraction=factor)
