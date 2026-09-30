"""Extract public artifacts as data; never execute notebook setup cells."""
import ast,base64,hashlib,io,json,tarfile,zlib
from pathlib import Path
from evaluate_boards import ROOT

def main():
    root=ROOT/'data/public_candidates';manifest=[]
    for owner in ('reyhanksatria','indarkarhana','thomastschinkel'):
        path=next((root/owner).glob('*.ipynb'))
        nb=json.loads(path.read_text(encoding='utf-8'))
        cells=[''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code']
        out=root/owner/'extracted';out.mkdir(exist_ok=True)
        if owner=='thomastschinkel':
            cell=next(c for c in cells if c.startswith('%%writefile main.py'))
            (out/'main.py').write_text(cell.split('\n',1)[1],encoding='utf-8')
        else:
            literals={}
            for cell in cells:
                tree=ast.parse(cell)
                for node in tree.body:
                    if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name):
                        try:literals[node.targets[0].id]=ast.literal_eval(node.value)
                        except (ValueError,TypeError):pass
            payload=base64.b64decode(literals.get('PAYLOAD',literals.get('ARCHIVE_B64')))
            if 'PAYLOAD' in literals:payload=zlib.decompress(payload)
            assert hashlib.sha256(payload).hexdigest()==literals['EXPECTED_ARCHIVE_SHA']
            with tarfile.open(fileobj=io.BytesIO(payload),mode='r:*') as tar:
                for member in tar.getmembers():
                    dest=(out/member.name).resolve()
                    assert dest.is_relative_to(out.resolve()) and member.isfile(),member.name
                    data=tar.extractfile(member).read()
                    if 'EXPECTED_MEMBERS' in literals:assert hashlib.sha256(data).hexdigest()==literals['EXPECTED_MEMBERS'][member.name]
                    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        files={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
        manifest.append({'owner':owner,'files':files});print(owner,len(files),'files')
    (root/'extracted_manifest.json').write_text(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
