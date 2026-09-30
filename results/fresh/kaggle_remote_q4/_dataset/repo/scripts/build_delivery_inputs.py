"""Build a standalone candidate without changing any selected agent."""
from market_corpus import ROOT
from hashlib import sha256

def main():
    base=ROOT/'agents/v45_our_selected.py'
    assert sha256(base.read_bytes()).hexdigest()=='88cb37b9a35434f4edb89a6dfa7c51a2681d21c12ebaa94c3a2dd5ad18650059'
    helpers=(ROOT/'agents/modern_input_overlay.py').read_text(encoding='utf-8')
    helpers=helpers[helpers.index('def _modern_tours'):helpers.index('def _r68_joint_plans')]
    text=base.read_text(encoding='utf-8')+'\n\n'+helpers+'\n'+(ROOT/'agents/delivery_input_overlay.py').read_text(encoding='utf-8')
    path=ROOT/'agents/v45_delivery_candidate.py';path.write_text(text,encoding='utf-8')
    print(path,sha256(path.read_bytes()).hexdigest())

if __name__=='__main__':main()
