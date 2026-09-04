# Kaggriculture

Workspace for the [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture) Kaggle simulation competition.

Build an autonomous agent that runs a virtual farm for a 30-day season (one turn = one in-game hour):
plant and harvest crops, care for animals, hire labor, buy land, and trade on a shared market where
prices react to supply and demand. Agents compete head-to-head on a live leaderboard by profit.

- Prize pool: $50,000 (top 10 x $5,000)
- Entry deadline: 2026-09-23

## Layout

| Path | Purpose |
|------|---------|
| `agents/` | Agent source. `agents/baseline.py` is the starting point; each new strategy gets its own file. |
| `scripts/` | Local runners: play episodes, agent-vs-agent matches, evaluate. |
| `notebooks/` | Exploration of episode data and market dynamics. |
| `data/episodes/` | Downloaded episode replays (git-ignored). |
| `submissions/` | Frozen copies of what was submitted, one folder per submission. |
| `docs/` | Rules notes, strategy ideas, environment observations. |

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Kaggle CLI needs an API token at `%USERPROFILE%\.kaggle\kaggle.json` (Kaggle > Settings > API > Create New Token).

## Useful datasets

- Kaggriculture Episodes Index: https://www.kaggle.com/datasets/kaggle/kaggriculture-episodes-index
- Community episode dump: https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes
