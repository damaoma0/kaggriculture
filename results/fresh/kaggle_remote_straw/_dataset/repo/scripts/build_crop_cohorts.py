"""Build standalone research variants without editing the frozen parent."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
VARIANTS={
 'carrot_stagger':dict(crop='CARROT',start=20,plots=4,per_day=1,gate=False),
 'carrot_batch':dict(crop='CARROT',start=20,plots=4,per_day=4,gate=False),
 'tomato_stagger':dict(crop='TOMATO',start=18,plots=2,per_day=1,gate=False),
 'tomato_batch':dict(crop='TOMATO',start=18,plots=2,per_day=2,gate=False),
}
if __name__=='__main__':
    base=(ROOT/'agents/v45_event_opening_fixed.py').read_text(encoding='utf-8')
    overlay=(ROOT/'agents/crop_cohort_overlay.py').read_text(encoding='utf-8')
    for name,config in VARIANTS.items():
        source=base+'\n'+overlay+'\n_COHORT_CONFIG = '+repr(config)+'\n'
        compile(source,name,'exec')
        (ROOT/f'agents/v45_cohort_{name}.py').write_text(source,encoding='utf-8')
    print(json.dumps(VARIANTS))
