# small-herd: opening moves

Seed 86301, seat 0; zero-based day/hour.

## Day 0

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PASS']` | `[]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 8], ['BUY_ANIMAL', 'COW', 2], ['BUY_ANIMAL', 'SHEEP', 2], ['BUY_SEED', 'MELON', 8]]` |
| 1 | `['PICKUP', 'COW', 1]` | `[['PICKUP', 'SHEEP', 1]]` | `[['HIRE'], ['BUY_SEED', 'MELON', 3]]` |
| 2 | `['BUILD_PASTURE']` | `[['WEST'], ['PICKUP', 'COW', 1]]` | `[['HIRE']]` |
| 3 | `['PLACE', 'COW', 1]` | `[['NORTH'], ['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[['HIRE']]` |
| 4 | `['PICKUP', 'WHEAT', 2]` | `[['BUILD_PASTURE'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 5 | `['FEED']` | `[['PLACE', 'SHEEP', 1], ['BUILD_PASTURE'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 6 | `['CARE']` | `[['SOUTH'], ['PLACE', 'COW', 1], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 7 | `['WEST']` | `[['PICKUP', 'WHEAT', 2], ['EAST'], ['BUILD_PASTURE'], ['NORTH'], ['WEST'], ['NORTH']]` | `[]` |
| 8 | `['NORTH']` | `[['NORTH'], ['PICKUP', 'WHEAT', 2], ['PLACE', 'SHEEP', 1], ['PLANT', 'MELON'], ['WEST'], ['NORTH']]` | `[]` |
| 9 | `['NORTH']` | `[['FEED'], ['WEST'], ['SOUTH'], ['WATER'], ['PLANT', 'MELON'], ['NORTH']]` | `[]` |
| 10 | `['NORTH']` | `[['CARE'], ['FEED'], ['SOUTH'], ['NORTH'], ['WATER'], ['NORTH']]` | `[]` |
| 11 | `['PLANT', 'MELON']` | `[['WEST'], ['CARE'], ['PICKUP', 'WHEAT', 2], ['PLANT', 'MELON'], ['WEST'], ['PLANT', 'MELON']]` | `[]` |
| 12 | `['WATER']` | `[['WEST'], ['NORTH'], ['NORTH'], ['WATER'], ['PLANT', 'MELON'], ['WATER']]` | `[]` |
| 13 | `['WEST']` | `[['WEST'], ['NORTH'], ['NORTH'], ['WEST'], ['WATER'], ['WEST']]` | `[]` |
| 14 | `['PLANT', 'MELON']` | `[['PLANT', 'MELON'], ['NORTH'], ['FEED'], ['PLANT', 'MELON'], ['NORTH'], ['WEST']]` | `[]` |
| 15 | `['WATER']` | `[['WATER'], ['NORTH'], ['CARE'], ['WATER'], ['PLANT', 'MELON'], ['PLANT', 'MELON']]` | `[]` |
| 16 | `['EAST']` | `[['EAST'], ['EAST'], ['SOUTH'], ['PASS'], ['WATER'], ['WATER']]` | `[]` |
| 17 | `['EAST']` | `[['EAST'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['SOUTH']` | `[['EAST'], ['SOUTH'], ['DROP'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['SOUTH']` | `[['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['SOUTH']` | `[['DROP'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['DROP']` | `[['PASS'], ['DROP'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 1

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['NORTH'], ['PASS']]` | `[]` |
| 5 | `['PASS']` | `[['CARE'], ['FEED'], ['SOUTH'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 6 | `['PASS']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['PICKUP', 'WHEAT', 1], ['PASS']]` | `[['HIRE']]` |
| 7 | `['PASS']` | `[['SOUTH'], ['COLLECT_FERTILIZER'], ['NORTH'], ['PASS'], ['PASS']]` | `[['HIRE']]` |
| 8 | `['PASS']` | `[['DROP'], ['EAST'], ['NORTH'], ['PASS'], ['PASS'], ['PASS']]` | `[['HIRE']]` |
| 9 | `['PASS']` | `[['PASS'], ['DROP'], ['FEED'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 10 | `['PASS']` | `[['PASS'], ['PASS'], ['CARE'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1], ['BUY_SEED', 'MELON', 1]]` |
| 11 | `['WEST']` | `[['PASS'], ['PASS'], ['COLLECT_FERTILIZER'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 12 | `['NORTH']` | `[['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 13 | `['NORTH']` | `[['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 14 | `['NORTH']` | `[['PASS'], ['PASS'], ['DROP'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 15 | `['NORTH']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 16 | `['PLANT', 'MELON']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 6]]` |
| 17 | `['WATER']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 2

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['HIRE']]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 8 | `['WATER']` | `[['WEST'], ['WEST'], ['CARE'], ['WATER'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 9 | `['NORTH']` | `[['NORTH'], ['WEST'], ['COLLECT_FERTILIZER'], ['WEST'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 10 | `['NORTH']` | `[['WATER'], ['WEST'], ['WEST'], ['WEST'], ['WATER'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 11 | `['WATER']` | `[['EAST'], ['WATER'], ['WEST'], ['WATER'], ['PASS'], ['WATER'], ['NORTH'], ['NORTH']]` | `[]` |
| 12 | `['PASS']` | `[['EAST'], ['EAST'], ['NORTH'], ['PASS'], ['PASS'], ['PASS'], ['WATER'], ['NORTH']]` | `[]` |
| 13 | `['PASS']` | `[['SOUTH'], ['EAST'], ['NORTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['NORTH']]` | `[]` |
| 14 | `['PASS']` | `[['SOUTH'], ['EAST'], ['WATER'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['WATER']]` | `[]` |
| 15 | `['PASS']` | `[['DROP'], ['EAST'], ['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['PASS'], ['DROP'], ['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 17 | `['PASS']` | `[['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1], ['BUY_PRODUCT', 'WHEAT', 6]]` |
| 18 | `['PASS']` | `[['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['PASS'], ['DROP'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 3

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 4]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['PASS']` | `[['CARE'], ['FEED'], ['NORTH'], ['NORTH'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['PASS']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['PASS'], ['PASS']]` | `[['HIRE'], ['BUY_SEED', 'STRAWBERRY', 1]]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 8 | `['WEST']` | `[['WEST'], ['EAST'], ['CARE'], ['NORTH'], ['WEST'], ['WEST'], ['WEST'], ['PASS']]` | `[]` |
| 9 | `['WEST']` | `[['WEST'], ['DROP'], ['COLLECT_FERTILIZER'], ['NORTH'], ['WEST'], ['WEST'], ['WEST'], ['PASS']]` | `[]` |
| 10 | `['NORTH']` | `[['WEST'], ['PASS'], ['SOUTH'], ['WATER'], ['WEST'], ['WEST'], ['WEST'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 11 | `['NORTH']` | `[['NORTH'], ['PASS'], ['SOUTH'], ['PASS'], ['NORTH'], ['NORTH'], ['WEST'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 12 | `['NORTH']` | `[['PLANT', 'STRAWBERRY'], ['PASS'], ['DROP'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 13 | `['PASS']` | `[['WATER'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 14 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_SEED', 'STRAWBERRY', 1]]` |
| 15 | `['PLANT', 'STRAWBERRY']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 16 | `['WATER']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['DROP'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_SEED', 'STRAWBERRY', 1]]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 4

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['HIRE']]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 8 | `['WATER']` | `[['WEST'], ['WEST'], ['CARE'], ['WATER'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 9 | `['NORTH']` | `[['NORTH'], ['WEST'], ['COLLECT_FERTILIZER'], ['WEST'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 10 | `['NORTH']` | `[['WATER'], ['WEST'], ['WEST'], ['WEST'], ['WATER'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 11 | `['WATER']` | `[['WEST'], ['WATER'], ['WEST'], ['WATER'], ['WEST'], ['WATER'], ['NORTH'], ['NORTH']]` | `[]` |
| 12 | `['WEST']` | `[['NORTH'], ['EAST'], ['NORTH'], ['PASS'], ['WEST'], ['PASS'], ['WATER'], ['NORTH']]` | `[]` |
| 13 | `['NORTH']` | `[['NORTH'], ['EAST'], ['NORTH'], ['PASS'], ['WEST'], ['PASS'], ['PASS'], ['NORTH']]` | `[]` |
| 14 | `['PLANT', 'STRAWBERRY']` | `[['EAST'], ['EAST'], ['WATER'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['WATER']]` | `[]` |
| 15 | `['WATER']` | `[['EAST'], ['EAST'], ['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['EAST'], ['DROP'], ['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['SOUTH'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 18 | `['PASS']` | `[['SOUTH'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_SEED', 'STRAWBERRY', 1]]` |
| 19 | `['NORTH']` | `[['SOUTH'], ['PASS'], ['SOUTH'], ['PASS'], ['PLANT', 'STRAWBERRY'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['SOUTH'], ['PASS'], ['SOUTH'], ['PASS'], ['WATER'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['DROP'], ['PASS'], ['DROP'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 2]]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 6]]` |
## Day 5

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['PASS']]` | `[['HIRE'], ['BUY_SEED', 'STRAWBERRY', 1]]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST'], ['PASS'], ['PASS']]` | `[['HIRE']]` |
| 8 | `['NORTH']` | `[['WEST'], ['EAST'], ['CARE'], ['NORTH'], ['WEST'], ['PASS'], ['PASS'], ['PASS']]` | `[['HIRE']]` |
| 9 | `['NORTH']` | `[['WEST'], ['DROP'], ['COLLECT_FERTILIZER'], ['NORTH'], ['WEST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 10 | `['NORTH']` | `[['WEST'], ['PASS'], ['SOUTH'], ['WATER'], ['NORTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 11 | `['WATER']` | `[['NORTH'], ['PASS'], ['SOUTH'], ['PASS'], ['NORTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['HIRE']]` |
| 12 | `['PASS']` | `[['NORTH'], ['PASS'], ['DROP'], ['PASS'], ['WATER'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 13 | `['PASS']` | `[['NORTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 14 | `['PASS']` | `[['PLANT', 'STRAWBERRY'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 15 | `['PASS']` | `[['WATER'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 6

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['HARVEST'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['CARE'], ['CARE'], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['HIRE']]` |
| 7 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 8 | `['WATER']` | `[['WEST'], ['WEST'], ['HARVEST'], ['WATER'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 9 | `['NORTH']` | `[['WEST'], ['WEST'], ['CARE'], ['WEST'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 10 | `['NORTH']` | `[['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['WEST'], ['WATER'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST'], ['WEST']]` | `[]` |
| 11 | `['WATER']` | `[['WATER'], ['WATER'], ['WEST'], ['WATER'], ['PASS'], ['WATER'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 12 | `['PASS']` | `[['EAST'], ['EAST'], ['WEST'], ['PASS'], ['PASS'], ['PASS'], ['WATER'], ['NORTH'], ['NORTH'], ['WEST']]` | `[]` |
| 13 | `['PASS']` | `[['EAST'], ['EAST'], ['WEST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['NORTH'], ['NORTH'], ['WEST']]` | `[]` |
| 14 | `['PASS']` | `[['EAST'], ['EAST'], ['WEST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['WATER'], ['NORTH'], ['NORTH']]` | `[]` |
| 15 | `['PASS']` | `[['SOUTH'], ['EAST'], ['NORTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['NORTH'], ['NORTH']]` | `[]` |
| 16 | `['PASS']` | `[['DROP'], ['DROP'], ['WATER'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['WATER'], ['NORTH']]` | `[]` |
| 17 | `['PASS']` | `[['PASS'], ['PASS'], ['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['NORTH']]` | `[['SELL', 'WOOL', 6], ['SELL', 'FERTILIZER', 2]]` |
| 18 | `['PASS']` | `[['PASS'], ['PASS'], ['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['WATER']]` | `[['BUY_PRODUCT', 'WHEAT', 10], ['BUY_ANIMAL', 'COW', 2]]` |
| 19 | `['PASS']` | `[['PASS'], ['PASS'], ['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['PASS'], ['PASS'], ['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 7

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WOOL', 6], ['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_ANIMAL', 'SHEEP', 2]]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'COW', 1]]` | `[['HIRE']]` |
| 5 | `['PICKUP', 'SHEEP', 1]` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'COW', 1]]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[['HIRE']]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 8 | `['BUILD_PASTURE']` | `[['NORTH'], ['WEST'], ['CARE'], ['DIG'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['PLACE', 'SHEEP', 1]` | `[['NORTH'], ['WEST'], ['COLLECT_FERTILIZER'], ['BUILD_PASTURE'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 10 | `['EAST']` | `[['NORTH'], ['WATER'], ['NORTH'], ['PLACE', 'COW', 1], ['BUILD_PASTURE'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST'], ['WEST']]` | `[]` |
| 11 | `['EAST']` | `[['WATER'], ['NORTH'], ['NORTH'], ['EAST'], ['PLACE', 'COW', 1], ['BUILD_PASTURE'], ['WATER'], ['WEST'], ['WEST'], ['WEST']]` | `[]` |
| 12 | `['PICKUP', 'WHEAT', 2]` | `[['WEST'], ['WATER'], ['WATER'], ['SOUTH'], ['SOUTH'], ['PLACE', 'SHEEP', 1], ['NORTH'], ['NORTH'], ['WEST'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 13 | `['WEST']` | `[['WEST'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2], ['SOUTH'], ['EAST'], ['WATER'], ['NORTH'], ['WEST'], ['NORTH']]` | `[]` |
| 14 | `['WEST']` | `[['WEST'], ['WATER'], ['WEST'], ['WEST'], ['SOUTH'], ['SOUTH'], ['NORTH'], ['NORTH'], ['NORTH'], ['NORTH']]` | `[]` |
| 15 | `['FEED']` | `[['WATER'], ['WEST'], ['WATER'], ['NORTH'], ['PICKUP', 'WHEAT', 2], ['SOUTH'], ['WATER'], ['WATER'], ['NORTH'], ['WATER']]` | `[]` |
| 16 | `['CARE']` | `[['SOUTH'], ['SOUTH'], ['EAST'], ['FEED'], ['NORTH'], ['PICKUP', 'WHEAT', 2], ['PASS'], ['PASS'], ['WATER'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 17 | `['EAST']` | `[['SOUTH'], ['WATER'], ['EAST'], ['CARE'], ['NORTH'], ['WEST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['EAST']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['NORTH'], ['NORTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['DROP']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['SOUTH'], ['FEED'], ['NORTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['WATER'], ['EAST'], ['SOUTH'], ['DROP'], ['CARE'], ['FEED'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['EAST'], ['EAST'], ['SOUTH'], ['PASS'], ['SOUTH'], ['CARE'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 22 | `['PASS']` | `[['EAST'], ['SOUTH'], ['DROP'], ['PASS'], ['SOUTH'], ['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['EAST'], ['DROP'], ['PASS'], ['PASS'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
## Day 8

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'FERTILIZER', 2], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['HARVEST']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['DROP']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['CARE']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['SELL', 'MILK', 6], ['HIRE']]` |
| 5 | `['COLLECT_FERTILIZER']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1], ['BUY_LAND']]` |
| 6 | `['DROP']` | `[['COLLECT_FERTILIZER'], ['HARVEST'], ['NORTH'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1], ['BUY_SEED', 'STRAWBERRY', 5], ['BUY_SEED', 'WHEAT', 1]]` |
| 7 | `['PICKUP', 'WHEAT', 2]` | `[['WEST'], ['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['NORTH'], ['PLANT', 'STRAWBERRY']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 8 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['CARE'], ['FEED'], ['WEST'], ['NORTH'], ['WATER'], ['WEST']]` | `[['HIRE'], ['BUY_SEED', 'WHEAT', 3]]` |
| 9 | `['NORTH']` | `[['WATER'], ['NORTH'], ['COLLECT_FERTILIZER'], ['CARE'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST'], ['NORTH']]` | `[['HIRE']]` |
| 10 | `['NORTH']` | `[['NORTH'], ['NORTH'], ['WEST'], ['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['PLANT', 'STRAWBERRY'], ['WEST'], ['NORTH'], ['WEST']]` | `[]` |
| 11 | `['FEED']` | `[['WATER'], ['NORTH'], ['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['WATER'], ['NORTH'], ['NORTH'], ['WEST']]` | `[]` |
| 12 | `['CARE']` | `[['NORTH'], ['WATER'], ['WEST'], ['WEST'], ['WEST'], ['CARE'], ['NORTH'], ['WATER'], ['NORTH'], ['WEST']]` | `[]` |
| 13 | `['COLLECT_FERTILIZER']` | `[['WATER'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['PLANT', 'STRAWBERRY'], ['NORTH'], ['WATER'], ['NORTH']]` | `[]` |
| 14 | `['WEST']` | `[['WEST'], ['WATER'], ['NORTH'], ['NORTH'], ['WATER'], ['EAST'], ['WATER'], ['NORTH'], ['EAST'], ['WATER']]` | `[]` |
| 15 | `['NORTH']` | `[['WEST'], ['EAST'], ['WATER'], ['NORTH'], ['EAST'], ['PLANT', 'STRAWBERRY'], ['EAST'], ['WATER'], ['PLANT', 'STRAWBERRY'], ['PASS']]` | `[]` |
| 16 | `['NORTH']` | `[['SOUTH'], ['EAST'], ['EAST'], ['WATER'], ['EAST'], ['WATER'], ['EAST'], ['PASS'], ['WATER'], ['PASS']]` | `[]` |
| 17 | `['WATER']` | `[['SOUTH'], ['EAST'], ['EAST'], ['EAST'], ['EAST'], ['EAST'], ['NORTH'], ['PASS'], ['EAST'], ['PASS']]` | `[]` |
| 18 | `['EAST']` | `[['WATER'], ['PLANT', 'WHEAT'], ['EAST'], ['EAST'], ['EAST'], ['EAST'], ['PLANT', 'WHEAT'], ['PASS'], ['EAST'], ['PASS']]` | `[]` |
| 19 | `['EAST']` | `[['EAST'], ['WATER'], ['SOUTH'], ['EAST'], ['DROP'], ['NORTH'], ['WATER'], ['PASS'], ['EAST'], ['PASS']]` | `[]` |
| 20 | `['SOUTH']` | `[['EAST'], ['WEST'], ['SOUTH'], ['EAST'], ['PASS'], ['PLANT', 'WHEAT'], ['PASS'], ['PASS'], ['PLANT', 'WHEAT'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 21 | `['SOUTH']` | `[['EAST'], ['SOUTH'], ['SOUTH'], ['SOUTH'], ['PASS'], ['WATER'], ['PASS'], ['PASS'], ['WATER'], ['PASS']]` | `[['BUY_SEED', 'WHEAT', 3]]` |
| 22 | `['SOUTH']` | `[['EAST'], ['SOUTH'], ['SOUTH'], ['SOUTH'], ['PASS'], ['WEST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['SOUTH']` | `[['SOUTH'], ['SOUTH'], ['DROP'], ['SOUTH'], ['PASS'], ['WEST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |