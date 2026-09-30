"""Extract the agent files embedded in public Kaggriculture notebooks WITHOUT executing notebook code (2026-09-30, user:
"look into latest open source code on kaggle and see if any of them fixes the opening problem"). The blobs are read
as literal constants with ast, decoded with the notebook's own scheme, and written to <notebook>/agent/; then every
extracted .py is scanned for anything beyond game logic (shell, network, file deletion, dynamic code).

usage: kaggle_public_extract_20260930.py [DIR]   (default results/fresh/kaggle_public_20260930)"""
import ast
import base64
import gzip
import io
import lzma
import re
import sys
import tarfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RISKY = [r"\bsubprocess\b", r"os\.system", r"os\.popen", r"\bsocket\b", r"urllib", r"\brequests\b", r"http\.client",
         r"shutil\.rmtree", r"os\.remove", r"os\.unlink", r"\bctypes\b", r"marshal\.loads", r"pickle\.loads",
         r"__import__\(", r"\bexec\(", r"\beval\(", r"open\([^)]*['\"][wa]b?['\"]", r"b64decode|b85decode|a85decode"]


def literals(code):
    """module-level NAME = <literal> assignments (also b''.join((...)) / ''.join([...]) of literals)"""
    out = {}
    tree = ast.parse(code)
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = node.value
            try:
                out[node.targets[0].id] = ast.literal_eval(v)
                continue
            except Exception:
                pass
            if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr == "join" and v.args:
                try:
                    sep = ast.literal_eval(v.func.value)
                    out[node.targets[0].id] = sep.join(ast.literal_eval(v.args[0]))
                except Exception:
                    pass
    return out


def untar(data):
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
        for m in tf.getmembers():
            if m.isfile():
                files[m.name] = tf.extractfile(m).read()
    return files


def extract(nb_dir):
    code = (nb_dir / "code.py").read_text(encoding="utf-8")
    cells = code.split("\n\n# ---- cell ----\n")
    files = {}
    for c in cells:
        if c.startswith("%%writefile"):
            name = Path(c.splitlines()[0].split()[1]).name
            files[name] = ("\n".join(c.splitlines()[1:]) + "\n").encode()
    lits = {}
    for c in cells:
        if c.lstrip().startswith(("%", "!")):
            continue
        try:
            lits.update(literals(c))
        except SyntaxError:
            continue
    if "MAIN_GZ_B64" in lits:
        files["main.py"] = gzip.decompress(base64.b64decode(lits["MAIN_GZ_B64"]))
    if "AGENT_B64" in lits:
        files["main.py"] = gzip.decompress(base64.b64decode(lits["AGENT_B64"]))
    if "SOURCE_BYTES" in lits:
        files["main.py"] = lits["SOURCE_BYTES"]
    if "PACKED_FILES" in lits:
        for k, v in lits["PACKED_FILES"].items():
            files[k] = lzma.decompress(base64.b85decode(v.encode("ascii")))
    if "FILES" in lits and isinstance(lits["FILES"], dict):
        for k, v in lits["FILES"].items():
            files[k] = zlib.decompress(base64.b85decode(v))
    if "ARCHIVE_PARTS" in lits:
        files.update(untar(base64.b85decode("".join(lits["ARCHIVE_PARTS"]).encode("ascii"))))
    if "ARCHIVE_B85" in lits:
        files.update(untar(base64.b85decode("".join(lits["ARCHIVE_B85"].split()).encode("ascii"))))
    if "PAYLOAD_B85" in lits:
        blob = lzma.decompress(base64.b85decode(lits["PAYLOAD_B85"]))
        cur = 0
        n = int.from_bytes(blob[cur:cur + 2], "big")
        cur += 2
        for _ in range(n):
            ns = int.from_bytes(blob[cur:cur + 2], "big")
            cur += 2
            name = blob[cur:cur + ns].decode()
            cur += ns
            ps = int.from_bytes(blob[cur:cur + 8], "big")
            cur += 8
            files[name] = blob[cur:cur + ps]
            cur += ps
    out = nb_dir / "agent"
    out.mkdir(exist_ok=True)
    for k, v in files.items():
        (out / Path(k).name).write_bytes(v)
    return files


def main():
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results/fresh/kaggle_public_20260930"
    for nb in sorted(p for p in d.iterdir() if (p / "code.py").exists()):
        try:
            files = extract(nb)
        except Exception as e:                            # noqa: BLE001
            print(f"{nb.name}: extraction failed: {e!r}")
            continue
        pys = {k: v for k, v in files.items() if k.endswith(".py")}
        print(f"{nb.name}: {', '.join(f'{k} ({len(v) // 1024} KB)' for k, v in files.items()) or 'no agent files'}")
        for k, v in pys.items():
            txt = v.decode("utf-8", "replace")
            hits = {pat: len(re.findall(pat, txt)) for pat in RISKY if re.search(pat, txt)}
            if hits:
                print(f"    scan {k}: {hits}")


if __name__ == "__main__":
    main()
