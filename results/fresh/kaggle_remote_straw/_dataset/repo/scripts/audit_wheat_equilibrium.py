"""Exact wheat-only market simulator; restricted-game equilibrium audit.

Strategy entries: signed quantities, positive BUY, negative SELL, zero idle.
The full order queue is committed before either player's actions are observed.
"""
from pathlib import Path
import json
import numpy as np
from scipy.optimize import linprog

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/wheat_equilibrium'

def simulate(a,b,prices):
    """Broadcast batches of fixed order sequences; exactly mimic lockstep quotes."""
    a=np.asarray(a,dtype=int);b=np.asarray(b,dtype=int)
    shape=np.broadcast_shapes(a.shape[:-1],b.shape[:-1])
    cash=[np.full(shape,3000,dtype=np.int64),np.full(shape,3000,dtype=np.int64)]
    stock=[np.zeros(shape,dtype=np.int64),np.zeros(shape,dtype=np.int64)]
    for t in range(max(a.shape[-1],b.shape[-1])):
        ops=[np.broadcast_to(x[...,t] if t<x.shape[-1] else 0,shape) for x in (a,b)]
        remaining=[np.abs(x).copy() for x in ops]
        for _ in range(100):
            total=stock[0]+stock[1]
            quotes=[prices[total+(op>0)] for op in ops]
            ok=[]
            for i in (0,1):
                valid=(remaining[i]>0)&np.where(ops[i]>0,(cash[i]>=quotes[i])&(stock[i]<100),stock[i]>0)
                ok.append(valid)
            if not any(np.any(x) for x in ok):break
            for i in (0,1):
                direction=np.sign(ops[i]);cash[i]-=ok[i]*direction*quotes[i];stock[i]+=ok[i]*direction
                remaining[i]=np.where(ok[i],remaining[i]-1,0)
    return cash[0],cash[1],stock[0],stock[1]

def solve(strategies,prices,label):
    arr=np.array([s+[0]*(10-len(s)) for s in strategies])
    c0,c1,h0,h1=simulate(arr[:,None,:],arr[None,:,:],prices)
    assert np.array_equal(c0,c1.T)
    payoff=c0-c1
    n=len(arr)
    sol=linprog(np.r_[np.zeros(n),-1],A_ub=np.c_[-payoff.T,np.ones(n)],b_ub=np.zeros(n),A_eq=[np.r_[np.ones(n),0]],b_eq=[1],bounds=[(0,None)]*n+[(None,None)],method='highs')
    assert sol.success,sol.message
    p=sol.x[:-1];support=np.flatnonzero(p>1e-8)
    # Symmetric zero-sum equilibrium; measure all pure unilateral deviations.
    br=payoff@p;regret=float(br.max())
    assert regret<1e-6
    pure_cash=[i for i in range(n) if c0[i,i]==c0[:,i].max()]
    result=dict(label=label,strategies=n,terminal_inventory_range=[int(h0.min()),int(h0.max())],support=[dict(index=int(i),orders=strategies[i],probability=float(p[i])) for i in support],value=float(sol.x[-1]),max_unilateral_margin_gain=regret,
        symmetric_pure_own_cash_equilibria=[dict(orders=strategies[i],cash=int(c0[i,i])) for i in pure_cash],
        probes=[])
    for q in (0,5,14,70,100):
        if [q,-100] in strategies:
            i=strategies.index([q,-100]);best=int(np.argmax(payoff[:,i]));bestcash=int(np.argmax(c0[:,i]))
            result['probes'].append(dict(q=q,self_cash=int(c0[i,i]),best_margin_response=strategies[best],best_margin=int(payoff[best,i]),best_own_cash_response=strategies[bestcash],best_own_cash=int(c0[bestcash,i])))
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/f'{label}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)
    return result,p,arr

def verify(prices):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    from copy import deepcopy
    rng=np.random.default_rng(154000)
    env=make('kaggriculture');env.reset(2);initial=deepcopy(env.state)
    cases=[([70,-70],[14,-10]),([5],[5]),([100,-100],[100,-100])]
    cases += [(rng.integers(-100,101,size=10).tolist(),rng.integers(-100,101,size=10).tolist()) for _ in range(300)]
    for a,b in cases:
        states=deepcopy(initial)
        for i,s in enumerate((a,b)):
            states[i].action={'market':[[('BUY_PRODUCT' if q>0 else 'SELL'),'WHEAT',abs(q)] for q in s]}
        E._process_market(states,env)
        expected=tuple([states[0].observation.farms[i]['money'] for i in (0,1)]+[states[i].observation.private.shed['WHEAT'] for i in (0,1)])
        actual=tuple(int(v) for v in simulate(a,b,prices))
        assert actual==expected,(a,b,actual,expected)
    return len(cases)

def verify_certificate(prices,certificates):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    from copy import deepcopy
    env=make('kaggriculture');env.reset(2);initial=deepcopy(env.state);checked=0
    for cert in certificates:
        target=cert['target_stock']
        for row in cert['cases']:
            # This is a precommitted best-response sequence, not intra-turn observation.
            orders=[row['first_order'],target-row['after_first_stock']]
            for seat in (0,1):
                states=deepcopy(initial)
                for i,s in ((seat,orders),(1-seat,[target])):
                    states[i].action={'market':[[('BUY_PRODUCT' if q>0 else 'SELL'),'WHEAT',abs(q)] for q in s]}
                E._process_market(states,env)
                assert states[0].observation.farms[seat]['money']==row['settled_cash']
                assert states[0].observation.farms[1-seat]['money']==row['opponent_cash']
                assert states[seat].observation.private.shed['WHEAT']==target
                checked+=1
    return checked

def main():
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    prices=np.array([E.market_price('WHEAT',10000-i) for i in range(202)])
    simulator_cases=verify(prices)
    print('verified',simulator_cases,flush=True)
    solve([[q,-100] for q in range(101)],prices,'two_order_flat')
    solve([[5]]+[[q,-100,5] for q in range(1,101)],prices,'three_order_feed')
    # Additional retained-feed strategies whose first purchases are always affordable.
    safe=max(q for q in range(101) if sum(prices[2*k-1] for k in range(1,q+1))<=3000)
    print('safe_quantity',safe,flush=True)
    solve([[q,-(q-5)] for q in range(5,safe+1)],prices,'two_order_keep_five')
    # Full-sequence certificate against a candidate with one opening purchase.
    # After slot 0 the opponent never trades again: subsequent own purchases and
    # sales telescope along a fixed price curve, independent of their ordering.
    potential=np.r_[0,np.cumsum(prices[1:])]
    certificates=[]
    for target in (0,5):
        first=np.arange(-100,101)
        c0,c1,h0,h1=simulate(first[:,None],np.array([target]),prices)
        assert np.all(h1==target)
        final_cash=c0+potential[target+h0]-potential[2*target]
        baseline=int(simulate([target],[target],prices)[0])
        rows=[dict(first_order=int(q),after_first_cash=int(c0[i]),after_first_stock=int(h0[i]),settled_cash=int(final_cash[i]),opponent_cash=int(c1[i])) for i,q in enumerate(first)]
        certificate=dict(target_stock=target,candidate_orders=[target] if target else [],symmetric_cash=baseline,
            max_own_cash=int(final_cash.max()),max_unilateral_own_cash_gain=int(final_cash.max()-baseline),max_unilateral_margin_gain=int((final_cash-c1).max()),
            best_first_buy_quantities=[int(first[i]) for i in range(201) if first[i]>=0 and final_cash[i]==final_cash.max()],cases=rows,
            proof='Opponent acts only at order slot 0. Enumerate every distinct possible first wheat order (buy 0..100 or sell/no-op). Afterward opponent inventory stays fixed. With F(n)=sum_{k=1}^n price(10000-k), every subsequent own trade changes cash by minus the change in F(own_stock+opponent_stock). Thus all feasible continuations ending at target stock have the enumerated settled cash. Orders above 100 are equivalent to 100 under shed capacity. Invalid/no-op orders are equivalent to zero. The reduction covers all fixed wheat-only queues of at most ten slots, not other commodities, altered game rules or unrestricted terminal inventories.')
        assert certificate['max_unilateral_own_cash_gain']==0 and certificate['max_unilateral_margin_gain']==0
        certificates.append(certificate)
        print('certificate',json.dumps({k:v for k,v in certificate.items() if k not in ('cases','proof','best_first_buy_quantities')}),flush=True)
    (OUT/'full_sequence_certificates.json').write_text(json.dumps(certificates,indent=2),encoding='utf-8')
    examples=[]
    for a,b in [([70,-70],[70,-70]),([28,-28],[70,-70]),([29,-29],[70,-70]),([70,-70],[14,-10]),([5],[70,-70]),([5],[5]),([14,-9],[5]),([70,-70,5],[5])]:
        values=[int(v) for v in simulate(a,b,prices)]
        examples.append(dict(a=a,b=b,cash=values[:2],wheat=values[2:]))
    (OUT/'examples.json').write_text(json.dumps(examples,indent=2),encoding='utf-8');print('examples',json.dumps(examples),flush=True)
    from hashlib import sha256
    verification=dict(random_and_edge_engine_cases=simulator_cases,certificate_engine_cases=verify_certificate(prices,certificates),
        engine_file=E.__file__,engine_sha256=sha256(Path(E.__file__).read_bytes()).hexdigest(),script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),price_at_deficit=prices.tolist(),initial_cash=3000,shed_capacity=100,max_orders=10)
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8');print('engine certificates verified',verification['certificate_engine_cases'],flush=True)

if __name__=='__main__':main()
