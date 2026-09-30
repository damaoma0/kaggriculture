"""Deposit-aware variant of the frozen first sales experiment."""
from copy import deepcopy
from collections import Counter
from market_forecast import E, forecast, sale_dp


class SalesPolicy:
    def __init__(self, base, method='visible'):
        self.base = base
        self.method = method
        self.history = []
        self.lot = None
        self.stats = Counter()

    def act(self, obs):
        t = obs['step']
        action = self.base.act(obs)
        assert len(self.history) == t
        history = self.history
        history.append({'inventory': dict(obs['market']['inventory']),
                        'shops': list(obs['town']['unlocked_shops'])})
        farm = obs['farms'][obs['player']]
        # Project our physical actions with the official transition, before market.
        pf, pp = deepcopy(farm), deepcopy(obs['private'])
        for i, a in enumerate([action['farmer'], *action['hands']]):
            E._apply_unit_action(pf, pp, i, a, 10, obs['day'], 24)
        stock = pp['shed']
        burden = sum(stock.values()) + sum(sum(v.values()) for v in pp['inventories'])
        orders = action['market']
        started = False
        if self.lot is None and 360 <= t <= 690 and farm['money'] >= 5000 and burden <= 70:
            for o in orders:
                if o[0] == 'SELL' and o[1] in ('CARROT','TOMATO','STRAWBERRY','MELON'):
                    q = min(10, int(o[2]), stock.get(o[1], 0))
                    if q > 0:
                        self.lot = [o[1], q, min(t+24, 718)]
                        started = True
                        self.stats['lots'] += 1
                        break
        if self.lot is None:
            return action
        item, left, deadline = self.lot
        if stock.get(item,0) < left:
            self.stats['reservation_shortfall'] += left-stock.get(item,0)
            left = stock.get(item,0)
        sell = 0
        forced = t >= deadline or farm['money'] < 5000 or burden >= 80
        if forced:
            sell = left
        elif started or t % 4 == 0:
            offsets = list(range(0, deadline-t+1, 4))
            if offsets[-1] != deadline-t: offsets.append(deadline-t)
            path = forecast(obs, history, deadline-t, self.method)[item]
            _, sell = sale_dp(item, [path[k] for k in offsets], left)
        # Reserve the lot against subsequent route sales. Other deposits can sell.
        available = max(0, stock.get(item,0)-left)
        kept = []
        for o in orders:
            if o[0] == 'SELL' and o[1] == item:
                n = min(int(o[2]), available)
                if n: kept.append(['SELL',item,n])
                available -= n
            else:
                kept.append(o)
        if sell:
            same = next((o for o in kept if o[0]=='SELL' and o[1]==item), None)
            if same is not None: same[2] += sell
            elif len(kept) < 10: kept.append(['SELL',item,sell])
            else: sell = 0; self.stats['order_slot_block'] += 1
        # Immediate sale must preserve the reference order exactly.
        if started and sell == left:
            kept = orders
        self.stats['held_unit_turns'] += left-sell
        self.stats['delayed_lots'] += int(started and sell < left)
        self.stats['released_units'] += sell
        self.stats['changed_turns'] += kept != orders
        left -= sell
        self.lot = [item,left,deadline] if left else None
        action['market'] = kept
        return action

