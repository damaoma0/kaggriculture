"""Extract downloaded agent source as data, without running notebook cells."""
import ast,base64,json,hashlib
from market_corpus import ROOT

def main():
    root=ROOT/'data/router_refresh_20260916';manifest=[]
    for folder in root.iterdir():
        if not folder.is_dir():continue
        files=list(folder.glob('*.ipynb'))
        if not files:continue
        notebook=files[0];nb=json.loads(notebook.read_text(encoding='utf-8'))
        cells=[''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code'];data=None;expected=None
        for cell in cells:
            if cell.startswith('%%writefile main.py'):
                data=cell.split('\n',1)[1].encode('utf-8');break
            try:tree=ast.parse(cell)
            except SyntaxError:continue
            values={}
            for node in tree.body:
                if not isinstance(node,ast.Assign) or not isinstance(node.targets[0],ast.Name):continue
                name=node.targets[0].id
                try:values[name]=ast.literal_eval(node.value)
                except (ValueError,TypeError):
                    v=node.value
                    if name=='SOURCE_BYTES' and isinstance(v,ast.Call) and isinstance(v.func,ast.Attribute) and isinstance(v.func.value,ast.Constant) and v.func.value.value==b'' and v.func.attr=='join':
                        values[name]=b''.join(ast.literal_eval(v.args[0]))
            if 'SOURCE_BYTES' in values:data=values['SOURCE_BYTES'];expected=values.get('EXPECTED_MAIN_SHA256');break
            if 'MAIN_B64' in values:data=base64.b64decode(values['MAIN_B64']);expected=values.get('EXPECTED_MAIN_SHA256');break
        if data is None:
            print(folder.name,'NO_SOURCE',[(len(c),c[:100]) for c in cells]);continue
        if expected:assert hashlib.sha256(data).hexdigest()==expected
        ast.parse(data)
        (folder/'main.py').write_bytes(data)
        tree=ast.parse(data)
        imports=[ast.unparse(x) for x in ast.walk(tree) if isinstance(x,(ast.Import,ast.ImportFrom))]
        calls=sorted({ast.unparse(x.func) for x in ast.walk(tree) if isinstance(x,ast.Call) and any(word in ast.unparse(x.func) for word in ('exec','eval','open','write','system','subprocess','socket','requests'))})
        row={'name':folder.name,'notebook_sha256':hashlib.sha256(notebook.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'imports':imports,'review_calls':calls}
        manifest.append(row);print(json.dumps(row))
    (root/'extraction.json').write_text(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
