"""Build data/ladder_panel/p2750/: a ladder panel of recent games where at least one side is rated
2750-3000 (our own recorded ladder games are mostly against much weaker or much stronger opponents,
so this panel is a second, harder-opponent-mix benchmark; see CLAUDE.md task B, 2026-09-23).

Same compact schema as data/ladder_panel/<submission>/*.json.gz (scripts/ladder_panel_fetch.py):
  episode, created, submission, seat, seed, names, rewards,
  opponent{submission, team, team_id, reward}, shops (31 day lists), opp_actions (719), our_actions (719)
``seat`` is the seat OUR build will replay; ``submission`` is the real submission that was recorded in
that seat (not necessarily ours). The 2750-3000-rated side is always recorded as ``opponent``.

Two sources:
  (i)  own ladder games (56368334 mgt_t10, 56395605 mgt_m1) whose recorded opponent is 2750-3000-rated
       NOW (results/fresh/newphase_20260923/leaderboard_full.json, refreshed by this script) -- refreshed
       incrementally via ladder_panel_fetch.py, then filtered and copied in.
  (ii) games BETWEEN OTHER teams, at least one 2750-3000-rated: for every team in that leaderboard band
       (excluding our own), its submissions' recent COMPLETED 2-agent episodes (competition_list_episodes),
       up to --max-per-team each, preferring the last --recent-days days. The band team is `opponent`; the
       other side (whoever it is, whatever its rating) becomes `seat`/our_actions.

Provenance is recorded per game in data/ladder_panel/p2750/index.json (source, band team/score, fetch time).

Usage: .venv/Scripts/python.exe scripts/build_p2750_panel.py [--max-per-team 2] [--recent-days 3]
                                                              [--band-lo 2750] [--band-hi 3000]
                                                              [--our-subs 56368334,56395605] [--skip-refresh]
"""
import gzip
import io
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KAGGLE = ROOT / '.venv/Scripts/kaggle.exe'
PY = sys.executable
OUT_DIR = ROOT / 'data/ladder_panel/p2750'
RAW = ROOT / 'data/ladder_panel/_raw'
LB = ROOT / 'results/fresh/newphase_20260923/leaderboard_full.json'
OUR_TEAM = 'Ghost Rule'


def parse_created(s):
    s = (s or '').split('.')[0]
    for fmt in ('%Y-%m-%d %H:%M:%S',):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def load_band(band_lo, band_hi):
    rows = json.loads(LB.read_text(encoding='utf-8'))
    for r in rows:
        r['score'] = float(r['score']) if r['score'] not in (None, '') else None
    band = {r['team_id']: r for r in rows if r['score'] is not None and band_lo <= r['score'] <= band_hi}
    own = next((r for r in rows if r['team'] == OUR_TEAM), None)
    return band, own


def download_replay(episode_id):
    local = ROOT / f'data/ladder_t10/episode-{episode_id}-replay.json'
    if local.exists():
        return local, False
    path = RAW / f'episode-{episode_id}-replay.json'
    if path.exists():
        return path, False
    RAW.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(KAGGLE), 'competitions', 'replay', str(episode_id), '-p', str(RAW), '-q'],
                    capture_output=True, timeout=300)
    return (path, True) if path.exists() else (None, False)


def compact(episode_id, created, seat_submission, seat_index, opp_agent):
    """Build the compact game dict from a downloaded replay, or return None on failure."""
    path, is_tmp = download_replay(episode_id)
    if path is None:
        return None, 'FAILED download'
    try:
        r = json.loads(path.read_text(encoding='utf-8'))
        steps = r['steps']
        if len(steps) < 720:
            return None, 'short replay'
        names = r['info'].get('TeamNames') or []
        game = dict(episode=episode_id, created=created, submission=seat_submission, seat=seat_index,
                    seed=r['info']['seed'], names=names, rewards=r['rewards'],
                    opponent=dict(submission=opp_agent['submission'], team=opp_agent['team'],
                                  team_id=opp_agent['team_id'], reward=opp_agent['reward']),
                    shops=[steps[min(719, d * 24)][0]['observation']['town']['unlocked_shops'] for d in range(31)],
                    opp_actions=[steps[t + 1][1 - seat_index].get('action') or {} for t in range(719)],
                    our_actions=[steps[t + 1][seat_index].get('action') or {} for t in range(719)])
        return game, 'ok'
    except Exception as exc:
        return None, f'FAILED parse: {exc!r}'
    finally:
        if is_tmp:
            path.unlink(missing_ok=True)


def write_game(game):
    out = OUT_DIR / f'{game["episode"]}.json.gz'
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, 'wt', encoding='utf-8') as f:
        json.dump(game, f, separators=(',', ':'))


def save_index(index_path, index, meta_extra=None):
    """Checkpoint write, so a crash mid-run never loses provenance already fetched to disk."""
    meta = dict(checkpoint=datetime.now(timezone.utc).isoformat(), n_games=len(index), **(meta_extra or {}))
    tmp = index_path.with_suffix('.tmp')
    with io.open(tmp, 'w', encoding='utf-8') as f:
        json.dump(dict(meta=meta, games=index), f, ensure_ascii=False, indent=1)
    tmp.replace(index_path)


def fetch_own(our_subs, band, index, log):
    """Source (i): our own submissions' recorded games whose opponent is in the band NOW."""
    for sub in our_subs:
        print(f'[own] refreshing ladder_panel_fetch for {sub}...', flush=True)
        p = subprocess.run([PY, str(ROOT / 'scripts/ladder_panel_fetch.py'), str(sub), OUR_TEAM],
                            capture_output=True, text=True)
        print('  ', p.stdout.strip().splitlines()[-1:] or p.stderr.strip().splitlines()[-1:])
        d = ROOT / f'data/ladder_panel/{sub}'
        if not d.exists():
            continue
        for gp in sorted(d.glob('*.json.gz')):
            g = json.loads(gzip.open(gp, 'rt', encoding='utf-8').read())
            opp_tid = (g.get('opponent') or {}).get('team_id')
            if opp_tid not in band:
                continue
            ep = str(g['episode'])
            dest = OUT_DIR / f'{ep}.json.gz'
            if ep in index:
                continue
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(dest, 'wt', encoding='utf-8') as f:
                    json.dump(g, f, separators=(',', ':'))
            index[ep] = dict(source='own_ladder', our_submission=sub, band_team_id=opp_tid,
                              band_team=band[opp_tid]['team'], band_score=band[opp_tid]['score'],
                              created=g.get('created'))
            log.append(('own', ep, 'ok'))


def fetch_team_vs_team(band, own_team_id, our_subs_set, max_per_team, recent_days, index, log, index_path=None):
    """Source (ii): recent episodes of every OTHER band team, opponent = band team, seat = the other side."""
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    cutoff = datetime.now(timezone.utc) - timedelta(days=recent_days)
    jobs = []
    for team_id, row in sorted(band.items(), key=lambda kv: kv[1]['rank']):
        if team_id == own_team_id:
            continue
        try:
            cand = []
            subs = api.competition_team_submissions(team_id)
            for s in subs or []:
                sub_id = getattr(s, 'id', None) or getattr(s, 'submission_id', None)
                if sub_id is None or sub_id in our_subs_set:
                    continue
                try:
                    eps = api.competition_list_episodes(sub_id)
                except Exception as exc:
                    log.append(('team', team_id, f'FAILED list_episodes {sub_id}: {exc!r}'))
                    continue
                for e in eps:
                    if 'COMPLETED' not in str(e.state) or len(e.agents or []) != 2:
                        continue
                    agents = [dict(submission=a.submission_id, index=a.index, reward=a.reward,
                                    team=a.team_name, team_id=a.team_id) for a in e.agents]
                    if any(a['team_id'] == own_team_id for a in agents):
                        continue                                # already covered by source (i)
                    n_team = sum(1 for a in agents if a['team_id'] == team_id)
                    if n_team != 1:
                        continue                                # not exactly one side is the target team (0: not
                        # featured; 2: a mirror/self-play game with no distinct opponent side)
                    opp_agent = next(a for a in agents if a['team_id'] == team_id)
                    seat_agent = next(a for a in agents if a['team_id'] != team_id)
                    created = str(e.create_time)
                    cand.append((created, e.id, seat_agent, opp_agent))
        except Exception as exc:
            log.append(('team', team_id, f'FAILED team_submissions: {exc!r}'))
            continue
        if not cand:
            log.append(('team', team_id, 'no candidate episodes'))
            continue
        cand.sort(key=lambda c: c[0], reverse=True)
        recent = [c for c in cand if (parse_created(c[0]) or cutoff) >= cutoff]
        chosen = (recent or cand)[:max_per_team]
        for created, ep_id, seat_agent, opp_agent in chosen:
            ep = str(ep_id)
            if (OUT_DIR / f'{ep}.json.gz').exists() or ep in index:
                continue
            jobs.append((team_id, row, created, ep_id, seat_agent, opp_agent))
        time.sleep(0.1)                                        # be polite to the API

    def work(job):
        team_id, row, created, ep_id, seat_agent, opp_agent = job
        game, status = compact(ep_id, created, seat_agent['submission'], seat_agent['index'], opp_agent)
        if game is None:
            return team_id, str(ep_id), status
        write_game(game)
        index[str(ep_id)] = dict(source='team_vs_team', band_team_id=team_id, band_team=row['team'],
                                  band_score=row['score'], other_team=seat_agent['team'],
                                  other_team_id=seat_agent['team_id'], other_submission=seat_agent['submission'],
                                  created=created)
        return team_id, str(ep_id), 'ok'

    print(f'[team_vs_team] downloading {len(jobs)} candidate episodes...', flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=3) as pool:
        for team_id, ep, status in pool.map(work, jobs):
            log.append(('team', ep, status))
            print(f'  team {team_id} ep {ep}: {status}', flush=True)
            done += 1
            if index_path is not None and done % 10 == 0:
                save_index(index_path, index, dict(stage='team_vs_team in progress'))
    if index_path is not None:
        save_index(index_path, index, dict(stage='team_vs_team done'))


def main():
    args = sys.argv[1:]
    opt = dict(max_per_team=2, recent_days=3, band_lo=2750.0, band_hi=3000.0,
               our_subs='56368334,56395605', skip_refresh=False)
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--skip-refresh':
            opt['skip_refresh'] = True; i += 1; continue
        key = a.lstrip('-').replace('-', '_')
        opt[key] = args[i + 1]; i += 2
    max_per_team = int(opt['max_per_team'])
    recent_days = int(opt['recent_days'])
    band_lo, band_hi = float(opt['band_lo']), float(opt['band_hi'])
    our_subs = [int(x) for x in str(opt['our_subs']).split(',')]

    if not opt['skip_refresh']:
        print('refreshing leaderboard...', flush=True)
        subprocess.run([PY, str(ROOT / 'scripts/fetch_full_leaderboard.py')], check=True)

    band, own = load_band(band_lo, band_hi)
    print(f'{len(band)} teams rated [{band_lo}, {band_hi}]; own team {own}', flush=True)
    own_team_id = own['team_id'] if own else None

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index_path = OUT_DIR / 'index.json'
    index = json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {}
    log = []

    fetch_own(our_subs, band, index, log)
    print(f'after source (i): {len(index)} games', flush=True)
    save_index(index_path, index, dict(stage='own_ladder done'))

    fetch_team_vs_team(band, own_team_id, set(our_subs), max_per_team, recent_days, index, log, index_path=index_path)
    print(f'after source (ii): {len(index)} games', flush=True)

    meta = dict(built=datetime.now(timezone.utc).isoformat(), band_lo=band_lo, band_hi=band_hi,
                max_per_team=max_per_team, recent_days=recent_days, our_subs=our_subs,
                own_team_id=own_team_id, n_games=len(index), n_band_teams=len(band))
    with io.open(index_path, 'w', encoding='utf-8') as f:
        json.dump(dict(meta=meta, games=index), f, ensure_ascii=False, indent=1)
    ok = sum(1 for _, _, s in log if s == 'ok')
    print(f'\nDONE: {len(index)} games total in {OUT_DIR}, {ok} newly fetched this run '
          f'({sum(1 for s in index.values() if s["source"] == "own_ladder")} own_ladder, '
          f'{sum(1 for s in index.values() if s["source"] == "team_vs_team")} team_vs_team)', flush=True)
    fails = [x for x in log if x[2] != 'ok' and 'no candidate' not in x[2]]
    if fails:
        print(f'{len(fails)} non-ok log rows (see index.json for successes); first 20:')
        for x in fails[:20]:
            print('  ', x)


if __name__ == '__main__':
    main()
