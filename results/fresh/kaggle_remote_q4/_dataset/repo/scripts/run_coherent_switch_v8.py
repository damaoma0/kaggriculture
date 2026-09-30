from pathlib import Path
import run_coherent_switch_v7 as B
from coherent_switch_v8 import make_policy

B.B.H.fresh_policy=make_policy
B.B.H.OWNED_SOURCES.extend([Path(__file__).resolve(),Path(__file__).with_name('coherent_switch_v8.py')])

if __name__=='__main__':B.B.main()
