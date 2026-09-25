"""xfix static check (no games): agents/mgt_lead_fix.py with every fix off == agents/mgt_lead.py on synthetic
observations (day 0 and leader boards of days 11 / 14 / 20 at several hours); every fix on runs without error."""
import copy, gzip, importlib.util, json, sys
sys.path.insert(0, 'scripts')
import xopen_static as XS
sem = json.load(gzip.open('data/leader_semantics/16732748/112655730.json.gz', 'rt', encoding='utf-8'))
base = {'p1_min_value': 30, 'release_stale_d': True, 'fert_hold': 1}
ON = dict(replant_leader=1, fert_follow=1, fert_gross=1, fert_shadow=1, idle_deliver=1, lead_harvest_bonus=4,
          harvest_policy='leader_tendency', upkeep_scale=0.65, busy_upkeep_pen=4, deliver_credit=1, fert_release=1, pf_log=1)


def load(p, n):
    spec = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


seq = [XS.obs_of(0, [XS.new_farm(), XS.new_farm()], XS.new_private())]
for d, money in ((11, 2405.0), (14, 15000.0), (20, 30000.0)):
    fs = [XS.new_farm(money), XS.new_farm()]
    fs[0]['tiles'] = XS.board_from_sem(sem, d)
    fs[0]['unlocked_quadrants'] = ['NW', 'NE', 'SW', 'SE']
    pv = XS.new_private(); pv['shed']['WHEAT'] = 30; pv['shed']['FERTILIZER'] = 5
    for h in range(4):
        fs[0]['hands'].append([4 + (h % 2), 4 + (h // 2)]); pv['inventories'].append({'FERTILIZER': 2, 'MELON': 3} if h == 1 else {})
    for hr in (0, 1, 7, 19, 21):
        seq.append(XS.obs_of(d * 24 + hr, copy.deepcopy(fs), copy.deepcopy(pv)))
A, B, C = load('agents/mgt_lead_fix.py', 'fA'), load('agents/mgt_lead.py', 'cB'), load('agents/mgt_lead_fix.py', 'fC')
A.configure(sem, **base); B.configure(sem, **base); C.configure(sem, **dict(base, **ON))
same = all(json.dumps(A.agent(copy.deepcopy(o)), sort_keys=True) == json.dumps(B.agent(copy.deepcopy(o)), sort_keys=True) for o in seq)
for o in seq:
    C.agent(copy.deepcopy(o))
print('fixes off == mgt_lead.py on %d observations: %s; fixes on ran; log %s' % (len(seq), same,
      {k: v for k, v in C._S['log'].items() if k.startswith(('hp_', 'replant', 'fert_shadow', 'idle'))}))
