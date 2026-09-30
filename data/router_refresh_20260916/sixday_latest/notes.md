# Kaggriculture: 93.8% Win Rate Public State Router
## Safe Six Day Slices and Pure Market Driven Routing

Replaying top ladder games gets you far, but fixed tapes hit a wall when town shops and market prices change across seeds. Online planning sounds nice in theory, but search is slow and prone to timing bugs.

Here is v5 of my public state router. The idea is simple:
1. Split the season into six day blocks (144 turns each).
2. Store five clean public tapes from top ladder runs.
3. At key block boundaries, inspect public state to pick the best continuation.

Zero online farming heuristics. Zero desync. Just clean data driven routing.

Results across 44,096 frozen test games (689 distinct opponent tapes, 32 seeds, both seats):
1. Fixed Base Tape: 84.57% win rate (37,291 wins)
2. Without Day 6 Routing: 85.74% win rate (37,807 wins)
3. Without Day 24 Routing: 91.98% win rate (40,559 wins)
4. Full V5 Router: 93.76% win rate (41,344 wins, plus 4,053 net wins)

An independent 256 seed stress panel scored 93.85% (3,844 wins out of 4,096 games).
In live test matches against older agents:
1. Against strong heuristic agent: 12 wins, 4 losses
2. Against submission v2.8: 16 wins, 0 losses
3. Against submission v3.3: 16 wins, 0 losses


## 1. How the Router Makes Decisions

The agent starts with a fixed opening schedule up to turn 143 (day 6).
Then it checks only public observation data to choose the next block:

1. Turn 144 (Day 6):
If a yarn store exists in town, switch to the sheep heavy block.
Otherwise, if town shops demand milk, switch to the milk block.
Otherwise, stick with the balanced tape.

2. Turn 576 (Day 24):
If the carrot market price is 54 coins or lower, switch to late harvest liquidation.
Otherwise, continue the base tape to the buzzer.

3. Turns 288 and 432 (Days 12 and 18):
Continue following the winning trajectory.

Why six day blocks?
Earlier experiments showed that micro switching every few turns causes tile desync.
Units try to harvest empty tiles or water unplanted dirt.
By using full six day blocks that share identical opening prefixes, the farm state stays aligned.


## 2. Ablations and What Failed

A big lesson from this version: keep it clean.
I tested several heuristic repair layers on 2,048 development games:
1. Extra liquidation on the final day: zero gain (1,953 wins)
2. Weed clearance during idle turns: only plus 1 win (not worth the code risk)
3. Delivery deadline override: lost 4 games (1,949 wins)
4. Purchase budget liquidation prototype: lost 440 games (1,513 wins)

The clean replay router beat every hand crafted repair layer.
Simplicity won.


## 3. Standalone Agent Code (main.py)

The cell below generates main.py.
It includes the five compressed public tapes and the decision trees.
It uses only standard python modules with zero external packages.


## 4. Local Test Match (720 Turns)

Let us run a full 720 turn match using the official Kaggle environment to verify execution.


## 5. Build submission.tar.gz

Now we package main.py into submission.tar.gz.
This archive is what you submit directly to the Kaggle competition.


## Summary

Key takeaways from v5.1:
1. Replay routing beats manual online planning on both win rate and runtime speed.
2. Six day block alignment prevents tile desync and protects farm logistics.
3. Simple market indicators (yarn store, milk demand, carrot price) provide strong guidance.
4. Clean code wins: removing complex repairs produced higher test stability.

If this notebook helps your ladder climb, please drop an upvote!
Good luck on the leaderboard!
