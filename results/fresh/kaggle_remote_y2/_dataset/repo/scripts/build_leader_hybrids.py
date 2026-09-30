"""Three standalone mechanism-transfer candidates, preserving the submission."""
from hashlib import sha256
from market_corpus import ROOT
import json

def main():
    source=ROOT/'agents/v45_event_candidate.py'
    assert sha256(source.read_bytes()).hexdigest()=='07c313e53d390ab6e1dd563fa2059dd1ea78988af4e0df3f8bbe1c6d8085ea4f'
    overlay=(ROOT/'agents/leader_opening_overlay.py').read_text(encoding='utf-8')
    hashes={}
    for mode in ('berries','herd','both'):
        path=ROOT/f'agents/v45_leader_{mode}.py'
        path.write_text(source.read_text(encoding='utf-8')+f'\n_HYBRID_MODE={mode!r}\n'+overlay,encoding='utf-8')
        hashes[mode]=sha256(path.read_bytes()).hexdigest()
    print(json.dumps(hashes,indent=2))

if __name__=='__main__':main()
