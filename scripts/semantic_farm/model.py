"""Small interpretable joint-decision library, trained on eligible submissions."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import json
from .common import public_features, asset_counts, E, SPECIES

ROOT=Path(__file__).resolve().parents[2]
DEFAULT=ROOT/'data/semantic_farm/model.json'


def distance(live, source):
    def l1(a,b): return sum(abs(a.get(k,0)-b.get(k,0)) for k in set(a)|set(b))
    return (3*l1(live['shops'],source['shops']) + .35*l1(live['assets'],source['assets'])
            + .12*l1(live['ages'],source['ages']) + .002*abs(live['money']-source['money'])
            + 2*abs(live['land']-source['land']))


class DecisionModel:
    def __init__(self,path=DEFAULT):
        self.data=json.loads(Path(path).read_text(encoding='utf8'))
        self.rows=self.data['rows']

    def opening(self,obs):
        day=min(obs['day'],5)
        counts=asset_counts(obs)
        target=self.data['opening'][str(day)]
        return dict(name='early_berries',quantities={s:max(0,n-counts[s]) for s,n in target['end_assets'].items()},
                    early_wheat=target.get('early_wheat',0), desired_land=1,
                    source_episode=self.data['opening_episode'])

    def proposals(self,obs,limit=3,exclude_episode=None):
        if obs['day']<6: return [self.opening(obs)]
        live=public_features(obs)
        rows=[r for r in self.rows if r['day']==obs['day'] and r['episode']!=exclude_episode]
        rows.sort(key=lambda r:(distance(live,r['features']),r['episode']))
        counts=asset_counts(obs)
        proposals=[];seen=set()
        for row in rows:
            # Learn the expert's additions, not its entire accumulated farm.
            # A different history does not authorize buying all missing cohorts.
            quantities={s:min(row['additions'].get(s,0),max(0,row['end_assets'].get(s,0)-counts[s])) for s in SPECIES
                if obs['day']+(E.CROPS[s]['first_yield_day'] if s in E.CROPS else E.ANIMALS[s]['first_yield_day'])<=29}
            quantities={s:n for s,n in quantities.items() if n}
            key=tuple(quantities.items()),row['land']
            if key in seen:continue
            seen.add(key)
            proposals.append(dict(name=f"expert-{row['episode']}",quantities=quantities,
                early_wheat=row['early_wheat'],desired_land=row['land'],source_episode=row['episode'],
                distance=distance(live,row['features'])))
            if len(proposals)>=limit:break
        return proposals
