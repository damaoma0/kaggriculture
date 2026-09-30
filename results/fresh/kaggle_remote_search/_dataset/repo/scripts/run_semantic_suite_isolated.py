"""Bound control-agent memory by evaluating one matched world per process."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True)
    p.add_argument('--panel-limit',type=int,default=0);p.add_argument('--seeds',default='924701')
    p.add_argument('--seats',default='0,1');p.add_argument('--arms',default='semantic,m1,y3,v9lite')
    args=p.parse_args()
    base=[sys.executable,str(ROOT/'scripts/run_semantic_farm.py'),'--out',args.out,'--arms',args.arms]
    if args.panel_limit:
        cases=[['--panel-offset',str(i),'--panel-limit','1'] for i in range(args.panel_limit)]
    else:
        cases=[['--seeds',seed,'--seats',seat] for seed in args.seeds.split(',') for seat in args.seats.split(',')]
    for case in cases:subprocess.run(base+case,cwd=ROOT,check=True)


if __name__=='__main__':main()
