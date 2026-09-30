from pathlib import Path
import run_coherent_opening_study as H
from coherent_opening_v5 import make_policy
H.OWNED_SOURCES.extend([Path(__file__).resolve(),*[Path(__file__).with_name('coherent_opening_v'+str(i)+'.py') for i in (2,3,4,5)],
    H.OUT/'new_sources/pickup_sidecar_original3.json'])
H.OWNED_SOURCES.extend(p for p in (H.OUT/'new_sources/traces').rglob('*') if p.is_file())
H.fresh_policy=make_policy
if __name__=='__main__':H.main()
