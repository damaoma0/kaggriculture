"""Freeze bounded native-route crop-substitution candidates."""
from pathlib import Path
from hashlib import sha256
import json
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    base=(ROOT/'agents/v45_event_opening_fixed.py').read_text(encoding='utf-8')
    overlay=(ROOT/'agents/native_crop_swap_overlay.py').read_text(encoding='utf-8')
    for plots in (2,4):
        source=base+'\n'+overlay+f'\n_SWAP_CONFIG["max_plots"] = {plots}\n'
        compile(source,'native_crop_swap','exec')
        path=ROOT/f'agents/v45_native_carrot_{plots}.py'
        path.write_text(source,encoding='utf-8')
        print(json.dumps(dict(path=str(path),sha256=sha256(path.read_bytes()).hexdigest())))
    value=(ROOT/'agents/native_crop_value_gate.py').read_text(encoding='utf-8')
    source=base+'\n'+overlay+'\n'+value
    compile(source,'native_crop_value','exec')
    path=ROOT/'agents/v45_native_carrot_value.py'
    path.write_text(source,encoding='utf-8')
    print(json.dumps(dict(path=str(path),sha256=sha256(path.read_bytes()).hexdigest())))
