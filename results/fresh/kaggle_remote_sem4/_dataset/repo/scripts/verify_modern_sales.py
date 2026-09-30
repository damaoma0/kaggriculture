"""Contracts for quantity projection, sale reservations and purchase barriers."""
from copy import deepcopy
from types import SimpleNamespace
from market_corpus import ROOT,load

def main():
    checks=0
    for base in ('v44','v45'):
        m=load('sales_contract_'+base,ROOT/f'agents/{base}_our_both.py')
        stock={'MILK':10,'WOOL':4}
        m.FarmView=lambda obs:SimpleNamespace(prices={'MILK':100,'WOOL':200},positions=[],inv=lambda i:{})
        m.projected_shed=lambda action,view:dict(stock)
        tape=[{'farmer':['PASS'],'hands':[],'market':[]} for _ in range(719)]
        tape[302]['market']=[['SELL','MILK',6],['SELL','WOOL',4]]
        tape[303]['market']=[['SELL','MILK',8]]
        state={'route':0,'pending':{},'sell_state':{'r36_debts':{302:{'MILK':2}}}}
        m._IMPL.chassis.players={0:state};m._IMPL.chassis.routes={0:tape,2:tape}
        obs={'step':300,'player':0,'market':{'inventory':dict.fromkeys(m._R37_MARKET_PARAMS,10000)}}
        action={'farmer':['PASS'],'hands':[],'market':[['SELL','MILK',3],['BUY_SEED','WHEAT',1]]}
        saved=deepcopy(action);result=m._port_liquidate(obs,action)
        assert action==saved and result['farmer']==action['farmer'] and result['hands']==action['hands']
        assert result['market']==[['SELL','MILK',10],['BUY_SEED','WHEAT',1],['SELL','WOOL',4]]
        assert state['sell_state']['r36_debts']=={302:{'MILK':6,'WOOL':4},303:{'MILK':3}}
        future=deepcopy(tape[302]);m._r36_suppress(future,state['sell_state'],302)
        assert future['market']==[['SELL','MILK',0],['SELL','WOOL',0]]
        full={'farmer':['PASS'],'hands':[],'market':[['BUY_SEED','WHEAT',0]]*10}
        assert m._port_liquidate(obs,full)==full
        assert m._port_liquidate(dict(obs,step=696),saved)==saved
        pickup=dict(saved,farmer=['PICKUP','MILK',1]);blocked=m._port_liquidate(obs,pickup)
        assert next(o[2] for o in blocked['market'] if o[:2]==['SELL','MILK'])==3
        sell={'farmer':['PASS'],'hands':[],'market':[['SELL','MILK',3],['SELL','WOOL',4],['BUY_SEED','WHEAT',1],['SELL','MILK',1]]}
        ordered=m._r37_reorder_sales(obs,deepcopy(sell))
        assert ordered['market'][2:]==sell['market'][2:]
        assert sorted(ordered['market'][:2])==sorted(sell['market'][:2])
        assert m._port_quote_priority(obs,['SELL','MILK',20],{'MILK':0})==0
        assert m._port_quote_priority(obs,['SELL','MILK',20],{'MILK':3})==m._port_quote_priority(obs,['SELL','MILK',3],{'MILK':3})
        checks+=11
    print(f'PASS: {checks} contracts across V44 and V45: physical actions, stock limits, existing reservations, future suppression, order cap, terminal abstention, pickups and purchase barriers')

if __name__=='__main__':main()
