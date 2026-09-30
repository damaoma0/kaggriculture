from pathlib import Path
import run_coherent_switch_v6 as B
from coherent_switch_v7 import make_policy

B.H.fresh_policy=make_policy
B.H.OWNED_SOURCES.extend([Path(__file__).resolve(),Path(__file__).with_name('coherent_switch_v7.py')])
B.H.OWNED_SOURCES.extend(Path(__file__).parent.glob('value_tape_search*.py'))
B.H.OWNED_SOURCES.extend(Path(__file__).parent.glob('rival_trajectory_model*.py'))
B.H.OWNED_SOURCES.extend([Path(__file__).with_name('cumulative_engine_profiles.py'),Path(__file__).with_name('test_labour_selfplay.py')])
for name in ('rival_library','modern_rival_library'):
    B.H.OWNED_SOURCES.extend(p for p in (B.H.ROOT/'results/fresh/value_tape_followup_20260923'/name).rglob('*') if p.is_file())

if __name__=='__main__':B.main()
