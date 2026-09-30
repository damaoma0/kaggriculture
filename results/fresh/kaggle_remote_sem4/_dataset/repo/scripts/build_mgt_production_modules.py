"""Build bounded production-module ablations from the frozen mgt_m1 baseline.

`mgt_pm_off.py` is copied byte-for-byte so an off arm cannot accidentally alter
the baseline's action stream.  The other arms append one self-contained overlay
and a fresh last callable for Kaggle's loader.
"""
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'agents' / 'mgt_m1.py'
FRAGMENT = ROOT / 'scripts' / 'fragments' / 'mgt_production_modules.py'
BASE_SHA256 = '1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470'


def build(name, cfg, base):
    overlay = FRAGMENT.read_text(encoding='utf-8').replace('__MPM_CFG__', repr(cfg))
    source = base + '\n\n' + overlay + '\n'
    compile(source, str(ROOT / 'agents' / name), 'exec')
    path = ROOT / 'agents' / (name + '.py')
    path.write_text(source, encoding='utf-8')
    return path


def main():
    base = BASE.read_text(encoding='utf-8')
    digest = sha256(BASE.read_bytes()).hexdigest()
    assert digest == BASE_SHA256, 'mgt_m1.py changed; explicitly refresh the frozen baseline hash'
    off = ROOT / 'agents' / 'mgt_pm_off.py'
    off.write_bytes(BASE.read_bytes())
    assert off.read_bytes() == BASE.read_bytes(), 'off arm must be byte-identical'
    common = dict(day_lo=12, day_hi=21, max_cycles=2, cash_margin=100)
    built = {
        'mgt_pm_forced': build('mgt_pm_forced', dict(common, mode='forced'), base),
        'mgt_pm_value': build('mgt_pm_value', dict(common, mode='value'), base),
        'mgt_pm_pin': build('mgt_pm_pin', dict(common, mode='pin_only'), base),
        'mgt_pm_off': off,
    }
    for name, path in built.items():
        print('%s %s baseline_sha256=%s' % (name, sha256(path.read_bytes()).hexdigest()[:12], digest))


if __name__ == '__main__':
    main()
