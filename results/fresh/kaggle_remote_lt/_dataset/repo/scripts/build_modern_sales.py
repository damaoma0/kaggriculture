"""Build isolated, self-contained transfers to both public baselines."""
import ast,json
from hashlib import sha256
from market_corpus import ROOT
from compare_router_refresh import PATHS

def main():
    old=(ROOT/'agents/adaptive_market_order.py').read_text(encoding='utf-8')
    tree=ast.parse(old)
    helpers='\n\n'.join(ast.get_source_segment(old,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('execute_trade','priority_value'))
    helpers=helpers.replace('execute_trade','_port_execute_trade').replace('priority_value','_port_priority_value').replace('E.market_price','_r37_market_price')
    overlay=(ROOT/'agents/modern_sales_overlay.py').read_text(encoding='utf-8')
    result={}
    for base in ('v44','v45'):
        source=PATHS[base].read_text(encoding='utf-8')
        for mode in ('order','liquid','both'):
            path=ROOT/f'agents/{base}_our_{mode}.py'
            path.write_text(source+'\n\n'+helpers+f'\n\n_PORT_MODE={mode!r}\n'+overlay,encoding='utf-8')
            result[path.name]=sha256(path.read_bytes()).hexdigest()
    out=ROOT/'results/fresh/modern_sales';out.mkdir(parents=True,exist_ok=True)
    (out/'build.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
