"""Build standalone modern baseline and one joint input-planning candidate."""
from hashlib import sha256
from market_corpus import ROOT
import json

def main():
    source=ROOT/'data/router_refresh_20260916/v45/main.py'
    assert sha256(source.read_bytes()).hexdigest()=='2536d41ed5a00c75204b6350f1c76c54259c774cb065ba2a3a0072eedf210d94'
    baseline=ROOT/'agents/modern_router_baseline.py'
    baseline.write_bytes(source.read_bytes())
    overlay=ROOT/'agents/modern_input_overlay.py'
    candidate=ROOT/'agents/modern_router_candidate.py'
    candidate.write_text(source.read_text(encoding='utf-8')+'\n\n'+overlay.read_text(encoding='utf-8'),encoding='utf-8')
    print(json.dumps({p.name:sha256(p.read_bytes()).hexdigest() for p in (baseline,overlay,candidate)},indent=2))

if __name__=='__main__':main()
