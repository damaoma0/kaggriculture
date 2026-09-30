"""Optional reveal-identity features; OFF unless explicitly enabled.

The unchanged block policy still owns quantities, completion reconciliation,
retirements and financing. Only two fitted output columns use these features.
"""
from copy import deepcopy
import json
from pathlib import Path

from semantic_strategy_blocks_20260928 import SemanticBlockPolicy


def reveal_features(day, shops_prefix, shop_types, modelled=False):
    block_start=3*(int(day)//3)
    if block_start<3 or block_start>24:
        return [0.]*len(shop_types)
    index=block_start//3-1
    # Index the shop revealed at this block. A later appended field cannot
    # become the current reveal. Normal public_state supplies only visible shops.
    if index<len(shops_prefix):
        return [float(shops_prefix[index]==shop) for shop in shop_types]
    if modelled:
        return [1./len(shop_types)]*len(shop_types)
    raise ValueError('Current block reveal is absent from visible shops')


class SemanticRevealBlockPolicy(SemanticBlockPolicy):
    def __init__(self,model_or_path,config=None):
        bundle=(json.loads(Path(model_or_path).read_text()) if isinstance(model_or_path,(str,Path))
                else deepcopy(model_or_path))
        self.reveal_enabled=bool((config or {}).get('reveal_features',False))
        self.reveal_shop_types=tuple(bundle['reveal_shop_types'])
        chosen=bundle['reveal_model'] if self.reveal_enabled else bundle['baseline_model']
        super().__init__(chosen,config)

    def _features(self,state,modelled):
        base=super()._features(state,modelled)
        if not self.reveal_enabled:return base
        return base+reveal_features(state['day'],state['shops_prefix'],self.reveal_shop_types,modelled)
