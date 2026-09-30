"""Attribution control: move empty sales behind available sales, preserving ties."""
from adaptive_market_order import AdaptiveOrder


class AvailabilityOrder(AdaptiveOrder):
    def __init__(self,base):super().__init__(base,'fixed')

    def agent(self,obs):
        action=super().agent(obs)
        if obs['step']<216:return action
        positions=[i for i,o in enumerate(action['market']) if o[0]=='SELL']
        if len(positions)<2:return action
        self.stats['opportunities']+=1
        orders=[action['market'][i] for i in positions]
        scores=[int(min(int(o[2]),self.flow.private['shed'].get(o[1],0))>0) for o in orders]
        ranked=sorted(range(len(orders)),key=lambda i:-scores[i])
        if ranked!=list(range(len(orders))):
            self.stats['reordered_turns']+=1
            self.decisions.append({'step':obs['step'],'before':orders,'after':[orders[i] for i in ranked],'scores':scores,'forecast':{}})
            for position,i in zip(positions,ranked):action['market'][position]=orders[i]
        return action
