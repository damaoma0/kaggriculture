"""Audit every native WHEAT opportunity in the frozen library, including day-zero watering."""
import ast
import base64
import json
from pathlib import Path
import re
import runpy
import zlib
import argparse

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/rotation_experiments'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fixed',action='store_true');args=parser.parse_args()
    source=(OUT/'development/frozen/mgt_exp_rotate.py').read_text(encoding='utf-8')
    fragment=(ROOT/'scripts/fragments/rotation_calendar_overlay.py').read_text() if args.fixed else source
    tree=ast.parse(fragment)
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_rot_plan','_rot_usable')]
    namespace={}
    exec(compile(ast.Module(body=selected,type_ignores=[]),'calendar-audit','exec'),namespace)
    blob=re.search(r"_MGT_LIB = _mgt_json.loads\(_mgt_zlib.decompress\(_mgt_b64.b85decode\('([^']+)'",source)[1]
    lib=json.loads(zlib.decompress(base64.b85decode(blob)))
    sim=runpy.run_path(str(ROOT/'scripts/fragments/tape_calendar.py'))['_tc_simulate']
    totals=dict(tapes=len(lib['tapes']),opportunities=0,accepted=0,missing_plant_day_water=0)
    examples=[]
    for tape in lib['tapes']:
        actions=[lib['actions'][i] for i in tape['ids']]
        calendar=sim(lambda t:actions[t],0,718,[(4,4)])
        for t in range(12*24,19*24):
            if (t-1)%24>=22:continue
            for u,(x,y,cmd) in enumerate(calendar[t]):
                if cmd!=['PLANT','WHEAT']:continue
                totals['opportunities']+=1
                p=namespace['_rot_plan'](calendar,t,u,(x,y))
                if not p:continue
                totals['accepted']+=1
                if not any(s//24==t//24 and job[1]==['WATER'] for s,job in p['jobs'].items()):
                    totals['missing_plant_day_water']+=1
                    if len(examples)<10:examples.append(dict(episode=tape['ep'],step=t,tile=[x,y]))
    result=dict(**totals,examples=examples)
    (OUT/('calendar_audit_fixed.json' if args.fixed else 'calendar_audit.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
