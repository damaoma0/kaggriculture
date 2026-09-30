"""Precompile proven V5 opening inputs, avoiding runtime replay-trace loading."""
from __future__ import annotations
import ast
import gzip
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data/semantic_strategy/opening_v5_contracts_20260928.json.gz'


def engine_work_source():
    path = ROOT / '.venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py'
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    named = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            named[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    named[target.id] = node
    selected, pending = {}, ['_apply_unit_action']
    while pending:
        name = pending.pop()
        if name in selected or name not in named:
            continue
        node = selected[name] = named[name]
        pending.extend(n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load))
    nodes = sorted({node.lineno: node for node in selected.values()}.values(), key=lambda n: n.lineno)
    text = '\n\n'.join(ast.get_source_segment(source, node) for node in nodes)
    ns = {}
    exec(compile(text, 'opening_exact_work_helpers', 'exec'), ns)
    assert callable(ns['_apply_unit_action'])
    return text, hashlib.sha256(source.encode()).hexdigest()


def main():
    from coherent_opening_v5 import SemanticInputPolicy
    start = time.perf_counter()
    policy = SemanticInputPolicy()
    unique, actions, tapes = {}, [], []
    for index, tape in enumerate(policy.ns['_MGT_TAPES']):
        ids = []
        for action in policy.chassis.routes[index]:
            key = json.dumps(action, sort_keys=True, separators=(',', ':'))
            if key not in unique:
                unique[key] = len(actions)
                actions.append(action)
            ids.append(unique[key])
        tapes.append(dict(ep=tape['ep'], shops=tape['shops'], boards=tape['boards'], ids=ids))
    source_path = ROOT / 'agents/mgt_dsm_a.py'
    source = source_path.read_text(encoding='utf-8')
    lines = source.splitlines()
    assignment = next(n for n in ast.parse(source).body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == '_MGT_LIB' for t in n.targets))
    lines[assignment.lineno - 1:assignment.end_lineno] = ['# _MGT_LIB is the precompiled immutable historical input contract.']
    source = '\n'.join(lines)
    source = source.replace('import os as _mgt_os', 'from types import SimpleNamespace as _OpeningNamespace\n_mgt_os = _OpeningNamespace(environ={})')
    work, engine_sha = engine_work_source()
    artifact = dict(schema_version=1, permitted_steps=[0, 143], source='coherent_opening_v5.SemanticInputPolicy',
        source_agent_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(), engine_sha256=engine_sha,
        default_route=policy.ns['_MGT_CFG']['default_route'], library=dict(actions=actions, tapes=tapes),
        core_source=source, work_source=work,
        notes=['Historical normalized routes are policy data; no evaluation observation or future shop is stored.',
               'Source route suffixes remain only to preserve early guard/calendar behavior exactly.',
               'Environment research hooks are disabled. Adapter refuses calls at day 6 or later.'])
    DEST.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(filename=str(DEST), mode='wb', mtime=0) as handle:
        handle.write(json.dumps(artifact, separators=(',', ':')).encode())
    print(json.dumps(dict(path=str(DEST), bytes=DEST.stat().st_size, routes=len(tapes), unique_actions=len(actions),
        preparation_seconds=round(time.perf_counter() - start, 3))))


if __name__ == '__main__':
    main()
