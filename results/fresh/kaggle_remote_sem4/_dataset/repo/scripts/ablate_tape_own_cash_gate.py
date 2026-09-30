"""Post-hoc public-score admission ablation on the frozen development branches.

Remove only the own-cash-positive gate for fully evaluated ordinary donors.
Retain physical, margin-risk, downside gates and the current R3 repair choice.
This is a checkpoint ablation, not a complete newly qualified playing agent.
"""
import tape_opportunity_audit as A

def pick(decision):
    current=next(c for c in decision['rows'] if c['selected'])
    allowed=[current]
    for c in decision['rows']:
        m=c['metadata']
        if (c['group']=='original' and c['route'] is not None
                and m.get('fully_evaluated') and not m.get('protection_failures')
                and m.get('risk_score',0)>350
                and m['minimum_margin']>=-m['loss_budget']):
            allowed.append(c)
    return max(allowed,key=lambda c:c['metadata'].get('risk_score',0))

def main():
    rows=[]
    for spec in A.read(A.OUT/'design.json')['specs']:
        case=spec['id'];decision=A.read(A.OUT/'candidates'/f'{case}.json')
        selected=pick(decision)
        current=next(c for c in decision['rows'] if c['selected'])
        a=A.read(A.OUT/'arms'/f"{case}-{selected['id']}-native.json")
        b=A.read(A.OUT/'arms'/f"{case}-{current['id']}-native.json")
        rows.append(dict(case=case,current=current['route'],ablated=selected['route'],
                         changed=current['id']!=selected['id'],margin_delta=a['margin']-b['margin'],
                         predicted=selected['metadata'].get('mean_margin'),
                         predicted_own=selected['metadata'].get('cash_deltas')))
    result=dict(protocol=__doc__,rows=rows,mean_delta=sum(r['margin_delta'] for r in rows)/len(rows))
    A.write(A.OUT/'own_cash_gate_ablation.json',result)
    print(A.json.dumps(result,indent=2))

if __name__=='__main__':main()
