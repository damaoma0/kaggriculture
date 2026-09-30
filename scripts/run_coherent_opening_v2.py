"""Run the corrected opening policies with the original frozen world designs."""
from pathlib import Path
import run_coherent_opening_study as H
from coherent_opening_v2 import make_policy

H.OWNED_SOURCES.extend([Path(__file__).resolve(),Path(__file__).with_name('coherent_opening_v2.py')])
H.fresh_policy=make_policy

if __name__=='__main__':
    H.main()
