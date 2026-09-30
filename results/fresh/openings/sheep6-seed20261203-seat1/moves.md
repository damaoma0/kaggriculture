# Opening moves

Policy: sheep6; seed 20261203; seat 1.

Actions are requests. Check their results in replay.json. Day/hour are zero-based.

## Day 0

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PASS']` | `[]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 12], ['BUY_ANIMAL', 'SHEEP', 5], ['BUY_SEED', 'WHEAT', 8]]` |
| 1 | `['PICKUP', 'SHEEP', 1]` | `[['PICKUP', 'SHEEP', 1]]` | `[['HIRE'], ['BUY_SEED', 'WHEAT', 1]]` |
| 2 | `['BUILD_PASTURE']` | `[['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[['HIRE']]` |
| 3 | `['PLACE', 'SHEEP', 1]` | `[['NORTH'], ['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[['HIRE']]` |
| 4 | `['PICKUP', 'WHEAT', 2]` | `[['BUILD_PASTURE'], ['NORTH'], ['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[['HIRE']]` |
| 5 | `['FEED']` | `[['PLACE', 'SHEEP', 1], ['BUILD_PASTURE'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 6 | `['CARE']` | `[['SOUTH'], ['PLACE', 'SHEEP', 1], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 7 | `['WEST']` | `[['PICKUP', 'WHEAT', 2], ['EAST'], ['BUILD_PASTURE'], ['NORTH'], ['NORTH'], ['WEST']]` | `[]` |
| 8 | `['WEST']` | `[['NORTH'], ['PICKUP', 'WHEAT', 2], ['PLACE', 'SHEEP', 1], ['BUILD_PASTURE'], ['NORTH'], ['NORTH']]` | `[]` |
| 9 | `['NORTH']` | `[['FEED'], ['WEST'], ['SOUTH'], ['PLACE', 'SHEEP', 1], ['PLANT', 'WHEAT'], ['NORTH']]` | `[]` |
| 10 | `['PLANT', 'WHEAT']` | `[['CARE'], ['FEED'], ['SOUTH'], ['EAST'], ['WATER'], ['PLANT', 'WHEAT']]` | `[]` |
| 11 | `['WATER']` | `[['NORTH'], ['CARE'], ['PICKUP', 'WHEAT', 2], ['SOUTH'], ['WEST'], ['WATER']]` | `[]` |
| 12 | `['NORTH']` | `[['NORTH'], ['WEST'], ['NORTH'], ['PICKUP', 'WHEAT', 2], ['PLANT', 'WHEAT'], ['NORTH']]` | `[]` |
| 13 | `['PLANT', 'WHEAT']` | `[['NORTH'], ['WEST'], ['NORTH'], ['WEST'], ['WATER'], ['NORTH']]` | `[]` |
| 14 | `['WATER']` | `[['PLANT', 'WHEAT'], ['PLANT', 'WHEAT'], ['FEED'], ['NORTH'], ['WEST'], ['PLANT', 'WHEAT']]` | `[]` |
| 15 | `['WEST']` | `[['WATER'], ['WATER'], ['CARE'], ['FEED'], ['PLANT', 'WHEAT'], ['WATER']]` | `[]` |
| 16 | `['EAST']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['CARE'], ['WATER'], ['PASS']]` | `[]` |
| 17 | `['EAST']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['EAST']` | `[['SOUTH'], ['EAST'], ['DROP'], ['SOUTH'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['SOUTH']` | `[['SOUTH'], ['DROP'], ['PASS'], ['DROP'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['SOUTH']` | `[['DROP'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['DROP']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 1

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 5 | `['PASS']` | `[['CARE'], ['FEED'], ['NORTH'], ['EAST']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 6 | `['PASS']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['PICKUP', 'WHEAT', 1]]` | `[['HIRE'], ['BUY_SEED', 'WHEAT', 4]]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 8 | `['WEST']` | `[['WEST'], ['WEST'], ['CARE'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 9 | `['WEST']` | `[['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 10 | `['NORTH']` | `[['NORTH'], ['WEST'], ['WEST'], ['FEED'], ['WEST'], ['WEST']]` | `[]` |
| 11 | `['PLANT', 'WHEAT']` | `[['PLANT', 'WHEAT'], ['NORTH'], ['WEST'], ['CARE'], ['WEST'], ['NORTH']]` | `[]` |
| 12 | `['WATER']` | `[['WATER'], ['PLANT', 'WHEAT'], ['WEST'], ['COLLECT_FERTILIZER'], ['PLANT', 'WHEAT'], ['PASS']]` | `[]` |
| 13 | `['PASS']` | `[['EAST'], ['WATER'], ['EAST'], ['EAST'], ['WATER'], ['PASS']]` | `[]` |
| 14 | `['PASS']` | `[['EAST'], ['EAST'], ['EAST'], ['SOUTH'], ['PASS'], ['PASS']]` | `[]` |
| 15 | `['PASS']` | `[['EAST'], ['EAST'], ['EAST'], ['DROP'], ['PASS'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 17 | `['PASS']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_SEED', 'WHEAT', 6]]` |
| 18 | `['NORTH']` | `[['DROP'], ['SOUTH'], ['DROP'], ['PASS'], ['NORTH'], ['PASS']]` | `[]` |
| 19 | `['NORTH']` | `[['PASS'], ['DROP'], ['PASS'], ['PASS'], ['NORTH'], ['PASS']]` | `[['SELL', 'FERTILIZER', 2]]` |
| 20 | `['PLANT', 'WHEAT']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PLANT', 'WHEAT'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 21 | `['WATER']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['WATER'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 9]]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 2

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 5 | `['NORTH']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 6 | `['NORTH']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['HIRE']]` |
| 7 | `['NORTH']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST']]` | `[]` |
| 8 | `['WATER']` | `[['WEST'], ['NORTH'], ['CARE'], ['FEED'], ['NORTH'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['NORTH']` | `[['WATER'], ['NORTH'], ['COLLECT_FERTILIZER'], ['CARE'], ['WATER'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 10 | `['WATER']` | `[['NORTH'], ['NORTH'], ['WEST'], ['COLLECT_FERTILIZER'], ['WEST'], ['WATER']]` | `[]` |
| 11 | `['WEST']` | `[['WATER'], ['WATER'], ['NORTH'], ['WEST'], ['NORTH'], ['WEST']]` | `[]` |
| 12 | `['WEST']` | `[['WEST'], ['EAST'], ['NORTH'], ['WEST'], ['WATER'], ['NORTH']]` | `[]` |
| 13 | `['PLANT', 'WHEAT']` | `[['WEST'], ['SOUTH'], ['WATER'], ['NORTH'], ['PASS'], ['NORTH']]` | `[]` |
| 14 | `['WATER']` | `[['NORTH'], ['SOUTH'], ['EAST'], ['NORTH'], ['PASS'], ['NORTH']]` | `[]` |
| 15 | `['PASS']` | `[['NORTH'], ['SOUTH'], ['SOUTH'], ['NORTH'], ['PASS'], ['PLANT', 'WHEAT']]` | `[]` |
| 16 | `['PASS']` | `[['PLANT', 'WHEAT'], ['DROP'], ['SOUTH'], ['PLANT', 'WHEAT'], ['PASS'], ['WATER']]` | `[]` |
| 17 | `['PASS']` | `[['WATER'], ['PASS'], ['SOUTH'], ['WATER'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 18 | `['PASS']` | `[['EAST'], ['PASS'], ['SOUTH'], ['EAST'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['EAST'], ['PASS'], ['DROP'], ['EAST'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['EAST'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 21 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS']]` | `[]` |
## Day 3

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'FERTILIZER', 2], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 8 | `['NORTH']` | `[['WEST'], ['NORTH'], ['CARE'], ['FEED'], ['WEST'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['WATER']` | `[['WEST'], ['NORTH'], ['COLLECT_FERTILIZER'], ['CARE'], ['WEST'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 10 | `['NORTH']` | `[['WEST'], ['WATER'], ['NORTH'], ['COLLECT_FERTILIZER'], ['WATER'], ['NORTH']]` | `[]` |
| 11 | `['NORTH']` | `[['WATER'], ['WEST'], ['WATER'], ['WEST'], ['EAST'], ['NORTH']]` | `[]` |
| 12 | `['WATER']` | `[['EAST'], ['WEST'], ['NORTH'], ['WATER'], ['WATER'], ['WATER']]` | `[]` |
| 13 | `['EAST']` | `[['EAST'], ['WEST'], ['WATER'], ['EAST'], ['EAST'], ['PASS']]` | `[]` |
| 14 | `['WATER']` | `[['NORTH'], ['WATER'], ['SOUTH'], ['NORTH'], ['EAST'], ['PASS']]` | `[]` |
| 15 | `['PASS']` | `[['WATER'], ['EAST'], ['SOUTH'], ['NORTH'], ['NORTH'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['EAST'], ['EAST'], ['SOUTH'], ['WATER'], ['NORTH'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['EAST'], ['EAST'], ['SOUTH'], ['EAST'], ['NORTH'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['SOUTH'], ['EAST'], ['DROP'], ['SOUTH'], ['NORTH'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['SOUTH'], ['SOUTH'], ['PASS'], ['SOUTH'], ['WATER'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 20 | `['PASS']` | `[['DROP'], ['SOUTH'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['DROP'], ['PASS'], ['DROP'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 2]]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_ANIMAL', 'SHEEP', 1]]` |
## Day 4

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 7 | `['NORTH']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['WATER'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 8 | `['WATER']` | `[['FEED'], ['NORTH'], ['HARVEST'], ['WATER'], ['WEST'], ['NORTH']]` | `[]` |
| 9 | `['HARVEST']` | `[['CARE'], ['NORTH'], ['NORTH'], ['HARVEST'], ['WATER'], ['NORTH']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 10 | `['PLANT', 'WHEAT']` | `[['COLLECT_FERTILIZER'], ['NORTH'], ['WATER'], ['WEST'], ['HARVEST'], ['FEED']]` | `[['BUY_SEED', 'WHEAT', 2]]` |
| 11 | `['WATER']` | `[['NORTH'], ['WATER'], ['HARVEST'], ['WATER'], ['PLANT', 'WHEAT'], ['CARE']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 12 | `['NORTH']` | `[['NORTH'], ['HARVEST'], ['PLANT', 'WHEAT'], ['HARVEST'], ['WATER'], ['COLLECT_FERTILIZER']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 13 | `['NORTH']` | `[['NORTH'], ['PLANT', 'WHEAT'], ['WATER'], ['PLANT', 'WHEAT'], ['NORTH'], ['SOUTH']]` | `[['BUY_SEED', 'WHEAT', 2]]` |
| 14 | `['WATER']` | `[['WATER'], ['WATER'], ['WEST'], ['WATER'], ['WATER'], ['SOUTH']]` | `[]` |
| 15 | `['HARVEST']` | `[['HARVEST'], ['WEST'], ['WEST'], ['WEST'], ['NORTH'], ['DROP']]` | `[]` |
| 16 | `['PLANT', 'WHEAT']` | `[['PLANT', 'WHEAT'], ['WEST'], ['WATER'], ['WEST'], ['WATER'], ['PICKUP', 'SHEEP', 1]]` | `[['SELL', 'FERTILIZER', 1]]` |
| 17 | `['WATER']` | `[['WATER'], ['NORTH'], ['WEST'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['BUY_SEED', 'WHEAT', 2]]` |
| 18 | `['WEST']` | `[['EAST'], ['WATER'], ['WEST'], ['WATER'], ['WATER'], ['WEST']]` | `[]` |
| 19 | `['WEST']` | `[['SOUTH'], ['WEST'], ['WATER'], ['SOUTH'], ['EAST'], ['BUILD_PASTURE']]` | `[]` |
| 20 | `['SOUTH']` | `[['PLANT', 'WHEAT'], ['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['PASS']]` | `[]` |
| 21 | `['WATER']` | `[['WATER'], ['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['PASS']]` | `[]` |
| 22 | `['EAST']` | `[['SOUTH'], ['SOUTH'], ['EAST'], ['WATER'], ['SOUTH'], ['PASS']]` | `[]` |
| 23 | `['EAST']` | `[['SOUTH'], ['WATER'], ['EAST'], ['EAST'], ['SOUTH'], ['PASS']]` | `[]` |
## Day 5

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 36], ['SELL', 'FERTILIZER', 3], ['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 8 | `['NORTH']` | `[['WEST'], ['WEST'], ['CARE'], ['FEED'], ['WEST'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['WATER']` | `[['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['CARE'], ['WEST'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 10 | `['HARVEST']` | `[['NORTH'], ['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['WATER'], ['PLACE', 'SHEEP', 1]]` | `[]` |
| 11 | `['PLANT', 'WHEAT']` | `[['WATER'], ['NORTH'], ['WEST'], ['WEST'], ['HARVEST'], ['EAST']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 12 | `['WATER']` | `[['HARVEST'], ['WATER'], ['WEST'], ['WEST'], ['PLANT', 'WHEAT'], ['EAST']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 13 | `['NORTH']` | `[['PLANT', 'WHEAT'], ['HARVEST'], ['NORTH'], ['WEST'], ['WATER'], ['PICKUP', 'WHEAT', 2]]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 14 | `['NORTH']` | `[['WATER'], ['PLANT', 'WHEAT'], ['WATER'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 15 | `['NORTH']` | `[['EAST'], ['WATER'], ['HARVEST'], ['WATER'], ['NORTH'], ['WEST']]` | `[]` |
| 16 | `['WATER']` | `[['NORTH'], ['NORTH'], ['PLANT', 'WHEAT'], ['HARVEST'], ['NORTH'], ['FEED']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 17 | `['EAST']` | `[['NORTH'], ['NORTH'], ['WATER'], ['PLANT', 'WHEAT'], ['WATER'], ['CARE']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 18 | `['EAST']` | `[['WATER'], ['NORTH'], ['EAST'], ['WATER'], ['EAST'], ['EAST']]` | `[]` |
| 19 | `['EAST']` | `[['EAST'], ['WATER'], ['EAST'], ['EAST'], ['EAST'], ['EAST']]` | `[]` |
| 20 | `['SOUTH']` | `[['EAST'], ['EAST'], ['EAST'], ['EAST'], ['EAST'], ['DROP']]` | `[]` |
| 21 | `['SOUTH']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['EAST'], ['PASS']]` | `[]` |
| 22 | `['SOUTH']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['SOUTH'], ['PASS']]` | `[]` |
| 23 | `['SOUTH']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['SOUTH'], ['SOUTH'], ['PASS']]` | `[]` |
## Day 6

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 23], ['SELL', 'FERTILIZER', 4], ['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 2 | `['HARVEST']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['DROP']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['CARE']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['SELL', 'WOOL', 6], ['HIRE']]` |
| 5 | `['COLLECT_FERTILIZER']` | `[['HARVEST'], ['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 6 | `['DROP']` | `[['CARE'], ['HARVEST'], ['NORTH'], ['NORTH'], ['WEST'], ['NORTH']]` | `[]` |
| 7 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['NORTH']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 8 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['HARVEST'], ['FEED'], ['WEST'], ['NORTH']]` | `[]` |
| 9 | `['NORTH']` | `[['WEST'], ['WEST'], ['CARE'], ['HARVEST'], ['FEED'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 10 | `['WATER']` | `[['NORTH'], ['WEST'], ['COLLECT_FERTILIZER'], ['CARE'], ['CARE'], ['WATER']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 11 | `['NORTH']` | `[['NORTH'], ['WATER'], ['NORTH'], ['COLLECT_FERTILIZER'], ['COLLECT_FERTILIZER'], ['WEST']]` | `[]` |
| 12 | `['WATER']` | `[['NORTH'], ['NORTH'], ['NORTH'], ['WEST'], ['NORTH'], ['WATER']]` | `[]` |
| 13 | `['WEST']` | `[['WATER'], ['NORTH'], ['WATER'], ['WEST'], ['NORTH'], ['NORTH']]` | `[]` |
| 14 | `['WEST']` | `[['HARVEST'], ['NORTH'], ['WEST'], ['WEST'], ['NORTH'], ['WATER']]` | `[]` |
| 15 | `['NORTH']` | `[['PLANT', 'WHEAT'], ['NORTH'], ['EAST'], ['NORTH'], ['WATER'], ['PASS']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 16 | `['NORTH']` | `[['WATER'], ['WATER'], ['WEST'], ['NORTH'], ['EAST'], ['PASS']]` | `[]` |
| 17 | `['WATER']` | `[['EAST'], ['HARVEST'], ['SOUTH'], ['WATER'], ['EAST'], ['PASS']]` | `[]` |
| 18 | `['HARVEST']` | `[['EAST'], ['PLANT', 'WHEAT'], ['EAST'], ['HARVEST'], ['SOUTH'], ['PASS']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 19 | `['PLANT', 'WHEAT']` | `[['SOUTH'], ['WATER'], ['SOUTH'], ['EAST'], ['SOUTH'], ['PASS']]` | `[['BUY_SEED', 'WHEAT', 2]]` |
| 20 | `['WATER']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['SOUTH'], ['PASS']]` | `[]` |
| 21 | `['EAST']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['DROP'], ['PASS']]` | `[]` |
| 22 | `['EAST']` | `[['SOUTH'], ['EAST'], ['DROP'], ['EAST'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 23 | `['EAST']` | `[['DROP'], ['SOUTH'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS']]` | `[['SELL', 'WOOL', 6], ['SELL', 'FERTILIZER', 1]]` |
## Day 7

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 16], ['SELL', 'WOOL', 18], ['SELL', 'FERTILIZER', 3], ['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 5 | `['PICKUP', 'WHEAT', 2]` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 8 | `['FEED']` | `[['WEST'], ['WEST'], ['CARE'], ['FEED'], ['WEST'], ['WEST']]` | `[]` |
| 9 | `['CARE']` | `[['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 10 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['NORTH'], ['COLLECT_FERTILIZER'], ['WATER'], ['WEST']]` | `[]` |
| 11 | `['NORTH']` | `[['WATER'], ['NORTH'], ['WATER'], ['WEST'], ['WEST'], ['WATER']]` | `[]` |
| 12 | `['WATER']` | `[['EAST'], ['WATER'], ['NORTH'], ['WEST'], ['NORTH'], ['EAST']]` | `[]` |
| 13 | `['NORTH']` | `[['WATER'], ['NORTH'], ['WATER'], ['NORTH'], ['WATER'], ['WATER']]` | `[]` |
| 14 | `['NORTH']` | `[['EAST'], ['NORTH'], ['WEST'], ['NORTH'], ['EAST'], ['PASS']]` | `[]` |
| 15 | `['WATER']` | `[['NORTH'], ['PLANT', 'WHEAT'], ['WATER'], ['WATER'], ['EAST'], ['PASS']]` | `[]` |
| 16 | `['EAST']` | `[['WATER'], ['WATER'], ['EAST'], ['EAST'], ['EAST'], ['PASS']]` | `[]` |
| 17 | `['EAST']` | `[['EAST'], ['EAST'], ['SOUTH'], ['EAST'], ['PLANT', 'WHEAT'], ['PASS']]` | `[]` |
| 18 | `['SOUTH']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['WATER'], ['PASS']]` | `[]` |
| 19 | `['SOUTH']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['SOUTH']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['DROP']` | `[['DROP'], ['SOUTH'], ['DROP'], ['SOUTH'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['SOUTH'], ['PASS'], ['DROP'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 3]]` |
| 23 | `['PASS']` | `[['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
## Day 8

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['WEST'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 7 | `['WEST']` | `[['NORTH'], ['COLLECT_FERTILIZER'], ['WATER'], ['NORTH'], ['NORTH'], ['WEST']]` | `[]` |
| 8 | `['WATER']` | `[['NORTH'], ['WEST'], ['HARVEST'], ['WATER'], ['NORTH'], ['NORTH']]` | `[]` |
| 9 | `['HARVEST']` | `[['NORTH'], ['FEED'], ['WEST'], ['HARVEST'], ['FEED'], ['FEED']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 10 | `['PLANT', 'WHEAT']` | `[['WATER'], ['CARE'], ['WATER'], ['NORTH'], ['CARE'], ['CARE']]` | `[['BUY_SEED', 'WHEAT', 2]]` |
| 11 | `['WATER']` | `[['HARVEST'], ['COLLECT_FERTILIZER'], ['HARVEST'], ['WATER'], ['COLLECT_FERTILIZER'], ['COLLECT_FERTILIZER']]` | `[]` |
| 12 | `['EAST']` | `[['PLANT', 'WHEAT'], ['EAST'], ['PLANT', 'WHEAT'], ['HARVEST'], ['WEST'], ['WEST']]` | `[['BUY_SEED', 'WHEAT', 2]]` |
| 13 | `['NORTH']` | `[['WATER'], ['NORTH'], ['WATER'], ['PLANT', 'WHEAT'], ['WEST'], ['WEST']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 14 | `['NORTH']` | `[['WEST'], ['NORTH'], ['WEST'], ['WATER'], ['NORTH'], ['WATER']]` | `[]` |
| 15 | `['NORTH']` | `[['WEST'], ['NORTH'], ['WEST'], ['WEST'], ['NORTH'], ['WEST']]` | `[]` |
| 16 | `['WATER']` | `[['WEST'], ['NORTH'], ['WEST'], ['WATER'], ['WATER'], ['WATER']]` | `[]` |
| 17 | `['HARVEST']` | `[['WATER'], ['WATER'], ['NORTH'], ['NORTH'], ['WEST'], ['SOUTH']]` | `[]` |
| 18 | `['PLANT', 'WHEAT']` | `[['EAST'], ['HARVEST'], ['WATER'], ['WATER'], ['WEST'], ['WATER']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 19 | `['WATER']` | `[['EAST'], ['PLANT', 'WHEAT'], ['EAST'], ['EAST'], ['SOUTH'], ['EAST']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 20 | `['EAST']` | `[['EAST'], ['WATER'], ['EAST'], ['EAST'], ['SOUTH'], ['EAST']]` | `[]` |
| 21 | `['EAST']` | `[['SOUTH'], ['EAST'], ['EAST'], ['EAST'], ['WATER'], ['EAST']]` | `[]` |
| 22 | `['SOUTH']` | `[['SOUTH'], ['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['EAST']]` | `[]` |
| 23 | `['SOUTH']` | `[['SOUTH'], ['SOUTH'], ['SOUTH'], ['SOUTH'], ['EAST'], ['DROP']]` | `[]` |