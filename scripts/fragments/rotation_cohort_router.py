# Penalize selecting a donor whose same-type plants/animals have different ages.
_RCO_BIRTH = _mgt_json.loads(_mgt_zlib.decompress(_mgt_b64.b85decode('__COHORT_BLOB__')))
_RCO_CONTEXT = None
_RCO_DISTANCE = _mgt_distance
_RCO_ROUTER = _MGT_IMPL.chassis.router
_ROT_REPORT = {'mode':'cohort','evaluations':0,'age_penalty_sum':0.0}


def _rco_distance(ours_vec, ours, tape, k):
    value = _RCO_DISTANCE(ours_vec, ours, tape, k)
    if _RCO_CONTEXT is None:return value
    day, current = _RCO_CONTEXT
    expected = _RCO_BIRTH.get(str(tape['ep']))
    if not expected:return value
    penalty=0.0
    for i, code, born in current:
        other=expected[day][i]
        if other>=0 and tape['lab'][day][i]==code:
            penalty+=0.35*min(4,abs(born-other))
    _ROT_REPORT['evaluations']+=1
    _ROT_REPORT['age_penalty_sum']+=penalty
    return value+penalty


_mgt_distance = _rco_distance


def _rco_router(obs,step,state):
    global _RCO_CONTEXT
    if step%24==0:
        farm=obs['farms'][int(obs['player'])];items=[]
        for y,row in enumerate(farm['tiles']):
            for x,t in enumerate(row):
                if isinstance(t,dict) and (t.get('crop') or t.get('animal')):
                    items.append((y*10+x,_mgt_label(t),int(t.get('planted_day',t.get('placed_day',step//24)))))
        _RCO_CONTEXT=(step//24,items)
    return _RCO_ROUTER(obs,step,state)


_MGT_IMPL.chassis.router=_rco_router


def rotation_cohort_entry(observation,configuration=None):
    return agent(observation,configuration)
