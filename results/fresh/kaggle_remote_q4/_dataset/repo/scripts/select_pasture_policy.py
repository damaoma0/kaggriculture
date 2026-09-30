"""Freeze the fixed-species comparator using development continuations only."""
import json
from statistics import mean
from audit_router_advantage import OUT

def main():
    rows=json.loads((OUT/'validate_results.json').read_text())
    means={m:mean(r['cash'] for r in rows if r['mode']==m) for m in ('original','cow','sheep','dp')}
    groups={}
    for r in rows:groups.setdefault((r['seed'],r['seat'],r['opponent']),{})[r['mode']]=r
    pairs=[]
    for k,g in groups.items():
        assert len({r['predecision_hash'] for r in g.values()})==1, 'Alternatives have different prefixes'
        assert len({r['decision']['step'] for r in g.values()})==1
        scores=g['dp']['decision']['scores'];actual=g['sheep']['cash']-g['cow']['cash']
        pairs.append({'seed':k[0],'seat':k[1],'actual_sheep_minus_cow':actual,
          'predicted_sheep_minus_cow':scores['SHEEP']['value']-scores['COW']['value'],
          'feasible':g['dp']['decision']['feasible'],'selected':g['dp']['decision']['selected']})
    comparable=[p for p in pairs if len(p['feasible'])==2 and p['actual_sheep_minus_cow']!=0]
    result={'fixed_species':max(('cow','sheep'),key=lambda m:means[m]),'development_means':means,
      'ranking_agreement':sum((p['actual_sheep_minus_cow']>0)==(p['predicted_sheep_minus_cow']>0) for p in comparable),
      'comparable_pairs':len(comparable),'pairs':pairs,
      'placement_failures':sum(r.get('placement_failed',False) for r in rows),
      'criterion':'Higher average final cash on development seeds; keep both DP forecast variants as predeclared diagnostic comparators.'}
    assert result['placement_failures']==0
    (OUT/'selection.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
