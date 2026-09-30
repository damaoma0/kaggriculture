"""Top up a team's leader-tape directory for a SPECIFIC submission id, bypassing
harvest_leader_tapes.py's "best active submission" auto-selection (which can pick a
brand-new, barely-rated submission over an established strong one once the older
submission drops out of the team's *active* submission list). Reuses
harvest_leader_tapes.handle() unmodified so the compact-tape format stays identical;
does not edit harvest_leader_tapes.py.

usage: topup_leader_tape_by_submission.py <team_id> <team_name> <submission_id> [K=40]
Output: data/leader_tapes/<team_id>_<submission_id>/<episode>.json.gz (tops up in place)
"""
import io, json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUTROOT = ROOT / 'data/leader_tapes'


def main():
    import harvest_leader_tapes as H
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi(); api.authenticate()
    team_id = int(sys.argv[1])
    team = sys.argv[2]
    sub_id = int(sys.argv[3])
    K = int(sys.argv[4]) if len(sys.argv) > 4 else 40
    outdir = OUTROOT / f'{team_id}_{sub_id}'
    have = {int(p.name.split('.')[0]) for p in outdir.glob('*.json.gz')} if outdir.exists() else set()
    eps = [e for e in api.competition_list_episodes(sub_id)
           if 'COMPLETED' in str(e.state) and len(e.agents or []) == 2]
    need = [e for e in eps if e.id not in have][:max(0, K - len(have))]
    print(f'{team} (id {team_id}) submission {sub_id}: have {len(have)}, {len(need)} more to fetch '
          f'(of {len(eps)} completed episodes total)', flush=True)
    counts = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for st in pool.map(H.handle, [(outdir, team, e.id) for e in need]):
            counts[st] = counts.get(st, 0) + 1
    print('   ', counts, flush=True)
    total = len(list(outdir.glob('*.json.gz'))) if outdir.exists() else 0
    print(f'   total tapes now: {total}', flush=True)
    idx_path = outdir / 'index.json'
    idx = json.loads(idx_path.read_text(encoding='utf-8')) if idx_path.exists() else {}
    idx.update(team_id=team_id, team=team, submission=sub_id,
               episodes=sorted({int(p.name.split('.')[0]) for p in outdir.glob('*.json.gz')}))
    with io.open(idx_path, 'w', encoding='utf-8') as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
