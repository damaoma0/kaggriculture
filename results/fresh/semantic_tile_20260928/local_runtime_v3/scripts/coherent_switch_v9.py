"""Reject unfunded continuations before comparing their demand/state scores.

The explicit router body is preserved from V6, with one change: failure to
fund a hire or source-successful purchase is a feasibility veto, rather than
one unit of soft matching cost. Incumbents receive the same score treatment.
"""
import time
from coherent_switch_v8 import CompleteGuardPolicy, make_policy as previous_policy


class SafetyGuardPolicy(CompleteGuardPolicy):
    def router(self, obs, step, state):
        ns = self.ns
        current = state.setdefault('route', ns['_MGT_CFG']['default_route'])
        if step % 24 or step < 72 or step > 28*24:
            return current
        day = step//24; own = int(obs['player'])
        farm = obs['farms'][own]
        board = ns['_mgt_labels'](ns['_mgt_board'](farm))
        shops = obs['town']['unlocked_shops']
        vectors = [ns['_mgt_vec'](shops, j) for j in range(9)]
        live_animals = [j for j, label in enumerate(board) if label in ns['_MGT_ANIMAL_LABELS']]
        ranked = []
        for route, tape in enumerate(ns['_MGT_TAPES']):
            mismatch = ns['_mgt_hamming'](board, tape['lab'][day])
            if mismatch > 8 and route != current:
                continue
            score = ns['_mgt_distance'](vectors, shops, tape, len(shops)) + mismatch
            if mismatch > 8: score += 4
            score += 4*sum(tape['lab'][day][j] not in ns['_MGT_ANIMAL_LABELS'] and
                           tape['lab'][min(29,day+2)][j] not in ns['_MGT_ANIMAL_LABELS']
                           for j in live_animals)
            contract = self.state_cost(farm, obs['private'], self.references[route], day)
            ranked.append(dict(route=route, score=score+contract, state_cost=contract,
                               mismatches=mismatch))
        ranked.sort(key=lambda row:(row['score'], row['route']!=current, row['mismatches'], row['route']))
        selected = ranked[0]['route']
        probes = []
        started = time.perf_counter()
        if self.probe_enabled and selected != current:
            # Keep the incumbent in the compared set. No new candidate outside
            # the normal physical-neighborhood gate is admitted here.
            options = ranked[:4]
            if current not in [r['route'] for r in options]:
                options.append(next(r for r in ranked if r['route']==current))
            by_route = {r['route']:self.probe(obs, r['route']) for r in options}
            base_lost = {tuple(x) for x in by_route[current]['lost']}
            for row in options:
                p = by_route[row['route']]
                added_loss = len({tuple(x) for x in p['lost']}-base_lost)
                penalty = 1000*bool(p.get('failed_hires',0) or p.get('failed_spending',0)) + 8*added_loss
                probes.append(dict(row, probe=p, added_asset_losses=added_loss,
                                   guarded_score=row['score']+penalty))
            selected = min(probes, key=lambda r:(r['guarded_score'],r['route']!=current,
                                                 r['mismatches'],r['route']))['route']
        state['route'] = selected
        self.stats['contract_decisions'] += 1
        self.stats['probe_rollouts'] += len(probes)
        self.stats['contract_switches'] += selected != current
        self.history.append(dict(event='contract_selection', step=step, incumbent=current,
            selected=selected, shortlist=ranked[:5], probes=probes, seconds=time.perf_counter()-started))
        return selected


def make_policy(arm):
    if arm=='safe_guard':return SafetyGuardPolicy()
    return previous_policy(arm)
