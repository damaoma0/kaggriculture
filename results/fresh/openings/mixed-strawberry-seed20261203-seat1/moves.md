# Opening moves

Policy: mixed-strawberry; seed 20261203; seat 1.

Actions are requests. Check their results in replay.json. Day/hour are zero-based.

## Day 0

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PASS']` | `[]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 8], ['BUY_ANIMAL', 'COW', 2], ['BUY_ANIMAL', 'SHEEP', 2], ['BUY_SEED', 'MELON', 8], ['BUY_SEED', 'WHEAT', 8]]` |
| 1 | `['PICKUP', 'COW', 1]` | `[['PICKUP', 'COW', 1]]` | `[['HIRE'], ['BUY_SEED', 'WHEAT', 5]]` |
| 2 | `['BUILD_PASTURE']` | `[['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[['HIRE']]` |
| 3 | `['PLACE', 'COW', 1]` | `[['NORTH'], ['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[['HIRE']]` |
| 4 | `['PICKUP', 'WHEAT', 2]` | `[['BUILD_PASTURE'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 5 | `['FEED']` | `[['PLACE', 'COW', 1], ['BUILD_PASTURE'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['HIRE']]` |
| 6 | `['CARE']` | `[['SOUTH'], ['PLACE', 'SHEEP', 1], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 7 | `['WEST']` | `[['PICKUP', 'WHEAT', 2], ['EAST'], ['BUILD_PASTURE'], ['PLANT', 'MELON'], ['WEST'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 8 | `['NORTH']` | `[['NORTH'], ['PICKUP', 'WHEAT', 2], ['PLACE', 'SHEEP', 1], ['WATER'], ['PLANT', 'MELON'], ['NORTH']]` | `[]` |
| 9 | `['NORTH']` | `[['FEED'], ['WEST'], ['SOUTH'], ['WEST'], ['WATER'], ['NORTH']]` | `[]` |
| 10 | `['PLANT', 'MELON']` | `[['CARE'], ['FEED'], ['SOUTH'], ['PLANT', 'MELON'], ['WEST'], ['PLANT', 'MELON']]` | `[]` |
| 11 | `['WATER']` | `[['NORTH'], ['CARE'], ['PICKUP', 'WHEAT', 2], ['WATER'], ['PLANT', 'MELON'], ['WATER']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 12 | `['NORTH']` | `[['NORTH'], ['WEST'], ['NORTH'], ['WEST'], ['WATER'], ['WEST']]` | `[]` |
| 13 | `['PLANT', 'MELON']` | `[['NORTH'], ['NORTH'], ['NORTH'], ['PLANT', 'WHEAT'], ['WEST'], ['NORTH']]` | `[]` |
| 14 | `['WATER']` | `[['PLANT', 'MELON'], ['NORTH'], ['FEED'], ['WATER'], ['PLANT', 'WHEAT'], ['PLANT', 'WHEAT']]` | `[]` |
| 15 | `['WEST']` | `[['WATER'], ['PLANT', 'WHEAT'], ['CARE'], ['NORTH'], ['WATER'], ['WATER']]` | `[]` |
| 16 | `['PLANT', 'WHEAT']` | `[['WEST'], ['WATER'], ['WEST'], ['PLANT', 'WHEAT'], ['NORTH'], ['WEST']]` | `[]` |
| 17 | `['WATER']` | `[['WEST'], ['WEST'], ['WEST'], ['WATER'], ['PLANT', 'WHEAT'], ['WEST']]` | `[]` |
| 18 | `['WEST']` | `[['PLANT', 'WHEAT'], ['WEST'], ['WEST'], ['PASS'], ['WATER'], ['PLANT', 'WHEAT']]` | `[]` |
| 19 | `['WEST']` | `[['WATER'], ['PLANT', 'WHEAT'], ['NORTH'], ['PASS'], ['PASS'], ['WATER']]` | `[]` |
| 20 | `['PLANT', 'WHEAT']` | `[['EAST'], ['WATER'], ['PLANT', 'WHEAT'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['WATER']` | `[['EAST'], ['EAST'], ['WATER'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['EAST']` | `[['SOUTH'], ['EAST'], ['EAST'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['EAST']` | `[['SOUTH'], ['EAST'], ['EAST'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 1

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 1], ['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 5 | `['PASS']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['PASS']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['WEST'], ['PASS'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 7 | `['PASS']` | `[['SOUTH'], ['COLLECT_FERTILIZER'], ['FEED'], ['WEST'], ['PASS'], ['PASS']]` | `[]` |
| 8 | `['PASS']` | `[['DROP'], ['EAST'], ['CARE'], ['NORTH'], ['PASS'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['PASS']` | `[['PASS'], ['DROP'], ['COLLECT_FERTILIZER'], ['NORTH'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 10 | `['PASS']` | `[['PASS'], ['PASS'], ['SOUTH'], ['NORTH'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 11 | `['PASS']` | `[['PASS'], ['PASS'], ['SOUTH'], ['NORTH'], ['PASS'], ['PASS']]` | `[]` |
| 12 | `['PASS']` | `[['PASS'], ['PASS'], ['DROP'], ['NORTH'], ['PASS'], ['PASS']]` | `[]` |
| 13 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PLANT', 'WHEAT'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 14 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['WATER'], ['PASS'], ['PASS']]` | `[]` |
| 15 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 2

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST']]` | `[]` |
| 7 | `['WATER']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['WATER'], ['NORTH'], ['WEST']]` | `[]` |
| 8 | `['WEST']` | `[['WEST'], ['NORTH'], ['CARE'], ['WEST'], ['NORTH'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['WATER']` | `[['WATER'], ['NORTH'], ['COLLECT_FERTILIZER'], ['NORTH'], ['WATER'], ['NORTH']]` | `[]` |
| 10 | `['NORTH']` | `[['NORTH'], ['NORTH'], ['NORTH'], ['WATER'], ['WEST'], ['WATER']]` | `[]` |
| 11 | `['WATER']` | `[['NORTH'], ['WATER'], ['NORTH'], ['WEST'], ['NORTH'], ['WEST']]` | `[]` |
| 12 | `['WEST']` | `[['WATER'], ['WEST'], ['WATER'], ['WATER'], ['WATER'], ['NORTH']]` | `[]` |
| 13 | `['WATER']` | `[['WEST'], ['WEST'], ['WEST'], ['WEST'], ['WEST'], ['NORTH']]` | `[]` |
| 14 | `['PASS']` | `[['NORTH'], ['WATER'], ['WEST'], ['WATER'], ['WEST'], ['WATER']]` | `[]` |
| 15 | `['PASS']` | `[['WATER'], ['EAST'], ['WEST'], ['PASS'], ['WEST'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['EAST'], ['EAST'], ['WEST'], ['PASS'], ['SOUTH'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['EAST'], ['EAST'], ['SOUTH'], ['PASS'], ['SOUTH'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['EAST'], ['SOUTH'], ['WATER'], ['PASS'], ['SOUTH'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['SOUTH'], ['SOUTH'], ['EAST'], ['PASS'], ['SOUTH'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['SOUTH'], ['SOUTH'], ['EAST'], ['PASS'], ['WATER'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['SOUTH'], ['DROP'], ['EAST'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['SOUTH'], ['PASS'], ['EAST'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 23 | `['PASS']` | `[['DROP'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 3

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'FERTILIZER', 2], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 8 | `['NORTH']` | `[['WEST'], ['WEST'], ['CARE'], ['NORTH'], ['WEST'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['WATER']` | `[['NORTH'], ['WEST'], ['COLLECT_FERTILIZER'], ['WATER'], ['WEST'], ['NORTH']]` | `[]` |
| 10 | `['WEST']` | `[['NORTH'], ['NORTH'], ['WEST'], ['NORTH'], ['WATER'], ['NORTH']]` | `[]` |
| 11 | `['WATER']` | `[['WATER'], ['NORTH'], ['WEST'], ['NORTH'], ['NORTH'], ['NORTH']]` | `[]` |
| 12 | `['NORTH']` | `[['WEST'], ['WATER'], ['WEST'], ['WATER'], ['NORTH'], ['WATER']]` | `[]` |
| 13 | `['NORTH']` | `[['WATER'], ['NORTH'], ['WEST'], ['PASS'], ['WATER'], ['PASS']]` | `[]` |
| 14 | `['WATER']` | `[['EAST'], ['NORTH'], ['NORTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 15 | `['PASS']` | `[['EAST'], ['WATER'], ['NORTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['EAST'], ['EAST'], ['WATER'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['SOUTH'], ['EAST'], ['EAST'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['SOUTH'], ['EAST'], ['EAST'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['SOUTH'], ['SOUTH'], ['EAST'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['DROP'], ['SOUTH'], ['EAST'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 22 | `['PASS']` | `[['PASS'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['DROP'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 4

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'FERTILIZER', 2], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 8 | `['NORTH']` | `[['NORTH'], ['WEST'], ['CARE'], ['NORTH'], ['WEST'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['WATER']` | `[['NORTH'], ['WATER'], ['COLLECT_FERTILIZER'], ['WATER'], ['WEST'], ['WATER']]` | `[]` |
| 10 | `['HARVEST']` | `[['NORTH'], ['NORTH'], ['WEST'], ['HARVEST'], ['WATER'], ['WEST']]` | `[]` |
| 11 | `['NORTH']` | `[['WATER'], ['NORTH'], ['WEST'], ['NORTH'], ['HARVEST'], ['WEST']]` | `[['BUY_SEED', 'STRAWBERRY', 2]]` |
| 12 | `['NORTH']` | `[['HARVEST'], ['NORTH'], ['WEST'], ['NORTH'], ['PLANT', 'STRAWBERRY'], ['WEST']]` | `[['BUY_SEED', 'STRAWBERRY', 1]]` |
| 13 | `['WATER']` | `[['PLANT', 'STRAWBERRY'], ['WATER'], ['WATER'], ['WATER'], ['WATER'], ['WATER']]` | `[['BUY_SEED', 'STRAWBERRY', 1]]` |
| 14 | `['HARVEST']` | `[['WATER'], ['HARVEST'], ['HARVEST'], ['HARVEST'], ['NORTH'], ['HARVEST']]` | `[]` |
| 15 | `['NORTH']` | `[['EAST'], ['PLANT', 'STRAWBERRY'], ['PLANT', 'STRAWBERRY'], ['WEST'], ['NORTH'], ['EAST']]` | `[['BUY_SEED', 'STRAWBERRY', 3]]` |
| 16 | `['WATER']` | `[['WATER'], ['WATER'], ['WATER'], ['WEST'], ['WATER'], ['EAST']]` | `[]` |
| 17 | `['HARVEST']` | `[['SOUTH'], ['EAST'], ['EAST'], ['SOUTH'], ['HARVEST'], ['WATER']]` | `[]` |
| 18 | `['SOUTH']` | `[['WATER'], ['WATER'], ['EAST'], ['WATER'], ['NORTH'], ['NORTH']]` | `[]` |
| 19 | `['SOUTH']` | `[['SOUTH'], ['EAST'], ['WATER'], ['HARVEST'], ['NORTH'], ['PLANT', 'STRAWBERRY']]` | `[]` |
| 20 | `['SOUTH']` | `[['SOUTH'], ['SOUTH'], ['EAST'], ['EAST'], ['WATER'], ['WATER']]` | `[]` |
| 21 | `['SOUTH']` | `[['SOUTH'], ['SOUTH'], ['SOUTH'], ['EAST'], ['EAST'], ['EAST']]` | `[]` |
| 22 | `['WATER']` | `[['DROP'], ['SOUTH'], ['SOUTH'], ['EAST'], ['EAST'], ['EAST']]` | `[]` |
| 23 | `['EAST']` | `[['PASS'], ['DROP'], ['DROP'], ['EAST'], ['EAST'], ['SOUTH']]` | `[['SELL', 'WHEAT', 2], ['SELL', 'FERTILIZER', 1]]` |
## Day 5

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 46], ['SELL', 'FERTILIZER', 2], ['HIRE'], ['BUY_SEED', 'STRAWBERRY', 1], ['BUY_SEED', 'WHEAT', 4]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['WEST'], ['WEST'], ['WEST']]` | `[]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['WEST'], ['WEST'], ['WEST']]` | `[]` |
| 8 | `['NORTH']` | `[['WEST'], ['WEST'], ['CARE'], ['NORTH'], ['WEST'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['PLANT', 'STRAWBERRY']` | `[['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['NORTH'], ['WEST'], ['NORTH']]` | `[]` |
| 10 | `['WATER']` | `[['NORTH'], ['WEST'], ['WEST'], ['NORTH'], ['NORTH'], ['NORTH']]` | `[]` |
| 11 | `['WEST']` | `[['NORTH'], ['NORTH'], ['WEST'], ['NORTH'], ['PLANT', 'STRAWBERRY'], ['NORTH']]` | `[]` |
| 12 | `['NORTH']` | `[['PLANT', 'WHEAT'], ['NORTH'], ['WEST'], ['NORTH'], ['WATER'], ['NORTH']]` | `[]` |
| 13 | `['NORTH']` | `[['WATER'], ['PLANT', 'WHEAT'], ['NORTH'], ['WATER'], ['PASS'], ['PLANT', 'STRAWBERRY']]` | `[]` |
| 14 | `['PLANT', 'WHEAT']` | `[['EAST'], ['WATER'], ['NORTH'], ['HARVEST'], ['PASS'], ['WATER']]` | `[]` |
| 15 | `['WATER']` | `[['EAST'], ['EAST'], ['PLANT', 'WHEAT'], ['EAST'], ['PASS'], ['PASS']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 16 | `['PASS']` | `[['EAST'], ['EAST'], ['WATER'], ['WEST'], ['PASS'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['SOUTH'], ['EAST'], ['EAST'], ['PLANT', 'WHEAT'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['SOUTH'], ['EAST'], ['EAST'], ['WATER'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['SOUTH'], ['SOUTH'], ['EAST'], ['EAST'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['DROP'], ['SOUTH'], ['SOUTH'], ['EAST'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['DROP'], ['SOUTH'], ['EAST'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['SOUTH'], ['EAST'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PASS']]` | `[]` |
## Day 6

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 4], ['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['HARVEST'], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST']]` | `[]` |
| 7 | `['WATER']` | `[['WEST'], ['CARE'], ['FEED'], ['WATER'], ['NORTH'], ['WEST']]` | `[]` |
| 8 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['HARVEST'], ['NORTH'], ['NORTH'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['WATER']` | `[['WATER'], ['WEST'], ['CARE'], ['NORTH'], ['WATER'], ['NORTH']]` | `[]` |
| 10 | `['WEST']` | `[['NORTH'], ['NORTH'], ['COLLECT_FERTILIZER'], ['WATER'], ['NORTH'], ['WATER']]` | `[]` |
| 11 | `['WATER']` | `[['NORTH'], ['NORTH'], ['WEST'], ['WEST'], ['WATER'], ['PASS']]` | `[]` |
| 12 | `['PASS']` | `[['WATER'], ['WATER'], ['NORTH'], ['WEST'], ['PASS'], ['PASS']]` | `[]` |
| 13 | `['PASS']` | `[['EAST'], ['EAST'], ['NORTH'], ['SOUTH'], ['PASS'], ['PASS']]` | `[]` |
| 14 | `['PASS']` | `[['EAST'], ['EAST'], ['WATER'], ['WATER'], ['PASS'], ['PASS']]` | `[]` |
| 15 | `['PASS']` | `[['SOUTH'], ['SOUTH'], ['EAST'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['SOUTH'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['SOUTH'], ['DROP'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['DROP'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'WOOL', 6], ['SELL', 'FERTILIZER', 1]]` |
| 19 | `['PASS']` | `[['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 20 | `['PASS']` | `[['PASS'], ['PASS'], ['DROP'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'WOOL', 6], ['SELL', 'FERTILIZER', 1]]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 7

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['NORTH']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['WEST'], ['WEST'], ['WEST']]` | `[]` |
| 7 | `['WATER']` | `[['NORTH'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 8 | `['NORTH']` | `[['NORTH'], ['WEST'], ['CARE'], ['NORTH'], ['WATER'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['WATER']` | `[['WATER'], ['NORTH'], ['COLLECT_FERTILIZER'], ['WATER'], ['WEST'], ['WEST']]` | `[]` |
| 10 | `['WEST']` | `[['WEST'], ['WATER'], ['WEST'], ['NORTH'], ['WATER'], ['WEST']]` | `[]` |
| 11 | `['NORTH']` | `[['WEST'], ['WEST'], ['WEST'], ['NORTH'], ['WEST'], ['NORTH']]` | `[]` |
| 12 | `['NORTH']` | `[['WEST'], ['WEST'], ['WEST'], ['NORTH'], ['NORTH'], ['WATER']]` | `[]` |
| 13 | `['WATER']` | `[['WATER'], ['NORTH'], ['WEST'], ['WATER'], ['NORTH'], ['EAST']]` | `[]` |
| 14 | `['EAST']` | `[['EAST'], ['NORTH'], ['WATER'], ['PASS'], ['NORTH'], ['EAST']]` | `[]` |
| 15 | `['EAST']` | `[['EAST'], ['WATER'], ['EAST'], ['PASS'], ['NORTH'], ['EAST']]` | `[]` |
| 16 | `['WATER']` | `[['EAST'], ['EAST'], ['EAST'], ['PASS'], ['WATER'], ['NORTH']]` | `[]` |
| 17 | `['PASS']` | `[['SOUTH'], ['EAST'], ['EAST'], ['PASS'], ['PASS'], ['NORTH']]` | `[]` |
| 18 | `['PASS']` | `[['SOUTH'], ['EAST'], ['EAST'], ['PASS'], ['PASS'], ['WATER']]` | `[]` |
| 19 | `['PASS']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['DROP'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['SOUTH'], ['DROP'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 22 | `['PASS']` | `[['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 23 | `['PASS']` | `[['PASS'], ['DROP'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 8

| Hour | Farmer | Hands | Market orders |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['HARVEST']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['DROP']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['CARE']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'MILK', 6], ['HIRE']]` |
| 5 | `['COLLECT_FERTILIZER']` | `[['HARVEST'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 6 | `['DROP']` | `[['CARE'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 7 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 8 | `['WEST']` | `[['WEST'], ['WEST'], ['CARE'], ['NORTH'], ['WEST'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['WATER']` | `[['NORTH'], ['NORTH'], ['COLLECT_FERTILIZER'], ['WATER'], ['WEST'], ['WATER']]` | `[]` |
| 10 | `['WEST']` | `[['NORTH'], ['NORTH'], ['NORTH'], ['EAST'], ['WATER'], ['WEST']]` | `[]` |
| 11 | `['NORTH']` | `[['NORTH'], ['NORTH'], ['WATER'], ['WATER'], ['EAST'], ['WATER']]` | `[]` |
| 12 | `['NORTH']` | `[['WATER'], ['WATER'], ['NORTH'], ['NORTH'], ['WATER'], ['WEST']]` | `[]` |
| 13 | `['WATER']` | `[['WEST'], ['WEST'], ['WATER'], ['WATER'], ['WEST'], ['NORTH']]` | `[]` |
| 14 | `['WEST']` | `[['WEST'], ['WEST'], ['SOUTH'], ['PASS'], ['NORTH'], ['NORTH']]` | `[]` |
| 15 | `['NORTH']` | `[['WATER'], ['WATER'], ['SOUTH'], ['PASS'], ['NORTH'], ['WATER']]` | `[]` |
| 16 | `['NORTH']` | `[['EAST'], ['EAST'], ['SOUTH'], ['PASS'], ['WATER'], ['PASS']]` | `[]` |
| 17 | `['WATER']` | `[['EAST'], ['EAST'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['EAST'], ['EAST'], ['DROP'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['SOUTH'], ['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 20 | `['PASS']` | `[['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['DROP'], ['DROP'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |