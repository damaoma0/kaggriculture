# reactive-copy: opening moves

Seed 86301, seat 1; zero-based day/hour.

## Day 0

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PASS']` | `[]` | `[['HIRE']]` |
| 1 | `['PASS']` | `[['PASS']]` | `[]` |
| 2 | `['PASS']` | `[['PASS']]` | `[['HIRE']]` |
| 3 | `['PASS']` | `[['PASS'], ['PASS']]` | `[['HIRE']]` |
| 4 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS']]` | `[['HIRE']]` |
| 5 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2], ['BUY_ANIMAL', 'COW', 1], ['BUY_SEED', 'MELON', 1]]` |
| 6 | `['PICKUP', 'COW', 1]` | `[['WEST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 2], ['BUY_ANIMAL', 'COW', 1]]` |
| 7 | `['BUILD_PASTURE']` | `[['WEST'], ['PICKUP', 'COW', 1], ['WEST'], ['PASS'], ['PASS']]` | `[['BUY_SEED', 'MELON', 1]]` |
| 8 | `['PLACE', 'COW', 1]` | `[['WEST'], ['NORTH'], ['NORTH'], ['WEST'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 2], ['BUY_ANIMAL', 'SHEEP', 1], ['BUY_SEED', 'MELON', 1]]` |
| 9 | `['PICKUP', 'WHEAT', 2]` | `[['NORTH'], ['NORTH'], ['NORTH'], ['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 10 | `['FEED']` | `[['PLANT', 'MELON'], ['BUILD_PASTURE'], ['NORTH'], ['WEST'], ['WEST']]` | `[['BUY_ANIMAL', 'SHEEP', 1], ['BUY_SEED', 'MELON', 2]]` |
| 11 | `['CARE']` | `[['WATER'], ['PLACE', 'COW', 1], ['NORTH'], ['NORTH'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 12 | `['PICKUP', 'SHEEP', 1]` | `[['EAST'], ['SOUTH'], ['PLANT', 'MELON'], ['PLANT', 'MELON'], ['BUILD_PASTURE']]` | `[]` |
| 13 | `['WEST']` | `[['NORTH'], ['PICKUP', 'WHEAT', 2], ['WATER'], ['WATER'], ['PLACE', 'SHEEP', 1]]` | `[['BUY_PRODUCT', 'WHEAT', 2], ['BUY_SEED', 'MELON', 2], ['BUY_SEED', 'WHEAT', 1]]` |
| 14 | `['NORTH']` | `[['PLANT', 'MELON'], ['NORTH'], ['WEST'], ['SOUTH'], ['EAST']]` | `[['BUY_SEED', 'MELON', 1]]` |
| 15 | `['BUILD_PASTURE']` | `[['WATER'], ['FEED'], ['PLANT', 'MELON'], ['PLANT', 'MELON'], ['PICKUP', 'WHEAT', 2]]` | `[]` |
| 16 | `['PLACE', 'SHEEP', 1]` | `[['WEST'], ['CARE'], ['WATER'], ['WATER'], ['WEST']]` | `[['BUY_SEED', 'MELON', 2], ['BUY_SEED', 'WHEAT', 1]]` |
| 17 | `['FEED']` | `[['PLANT', 'MELON'], ['SOUTH'], ['NORTH'], ['WEST'], ['FEED']]` | `[]` |
| 18 | `['CARE']` | `[['WATER'], ['DROP'], ['PLANT', 'MELON'], ['PLANT', 'MELON'], ['CARE']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 19 | `['PASS']` | `[['NORTH'], ['PASS'], ['WATER'], ['WATER'], ['EAST']]` | `[]` |
| 20 | `['PASS']` | `[['PLANT', 'MELON'], ['PASS'], ['PASS'], ['PASS'], ['DROP']]` | `[]` |
| 21 | `['PASS']` | `[['WATER'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 1

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 3]]` |
| 7 | `['NORTH']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['WEST']]` | `[]` |
| 8 | `['NORTH']` | `[['WEST'], ['WEST'], ['CARE'], ['NORTH']]` | `[]` |
| 9 | `['NORTH']` | `[['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['NORTH']]` | `[]` |
| 10 | `['NORTH']` | `[['NORTH'], ['NORTH'], ['WEST'], ['PLANT', 'WHEAT']]` | `[]` |
| 11 | `['PLANT', 'WHEAT']` | `[['EAST'], ['EAST'], ['EAST'], ['WATER']]` | `[]` |
| 12 | `['WATER']` | `[['EAST'], ['EAST'], ['EAST'], ['PASS']]` | `[]` |
| 13 | `['PASS']` | `[['EAST'], ['EAST'], ['SOUTH'], ['PASS']]` | `[]` |
| 14 | `['PASS']` | `[['SOUTH'], ['SOUTH'], ['DROP'], ['PASS']]` | `[]` |
| 15 | `['PASS']` | `[['SOUTH'], ['DROP'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 16 | `['PASS']` | `[['DROP'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1], ['BUY_PRODUCT', 'WHEAT', 1], ['BUY_SEED', 'WHEAT', 4]]` |
| 17 | `['WEST']` | `[['PASS'], ['PASS'], ['PASS'], ['NORTH']]` | `[['SELL', 'FERTILIZER', 1], ['BUY_SEED', 'MELON', 1], ['BUY_SEED', 'WHEAT', 1]]` |
| 18 | `['PLANT', 'WHEAT']` | `[['PASS'], ['PASS'], ['PASS'], ['NORTH']]` | `[['BUY_SEED', 'MELON', 1]]` |
| 19 | `['WATER']` | `[['PASS'], ['PASS'], ['PASS'], ['PLANT', 'WHEAT']]` | `[]` |
| 20 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['WATER']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 2

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['NORTH']]` | `[]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['WEST'], ['NORTH']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 6 | `['NORTH']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 7 | `['NORTH']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH']]` | `[]` |
| 8 | `['WATER']` | `[['WEST'], ['WEST'], ['CARE'], ['WATER']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['NORTH']` | `[['WATER'], ['WEST'], ['COLLECT_FERTILIZER'], ['WEST']]` | `[]` |
| 10 | `['WATER']` | `[['NORTH'], ['WATER'], ['WEST'], ['NORTH']]` | `[]` |
| 11 | `['WEST']` | `[['WATER'], ['WEST'], ['WEST'], ['WATER']]` | `[]` |
| 12 | `['WATER']` | `[['WEST'], ['WATER'], ['WATER'], ['EAST']]` | `[]` |
| 13 | `['WEST']` | `[['PLANT', 'MELON'], ['NORTH'], ['WEST'], ['PLANT', 'MELON']]` | `[]` |
| 14 | `['PLANT', 'WHEAT']` | `[['WATER'], ['NORTH'], ['NORTH'], ['WATER']]` | `[]` |
| 15 | `['WATER']` | `[['EAST'], ['DIG'], ['NORTH'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['EAST'], ['PLANT', 'WHEAT'], ['NORTH'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['EAST'], ['WATER'], ['PLANT', 'WHEAT'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['SOUTH'], ['EAST'], ['WATER'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['SOUTH'], ['EAST'], ['EAST'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['DROP'], ['EAST'], ['EAST'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['EAST'], ['EAST'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 22 | `['PASS']` | `[['PASS'], ['SOUTH'], ['EAST'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 23 | `['PASS']` | `[['PASS'], ['SOUTH'], ['SOUTH'], ['PASS']]` | `[]` |
## Day 3

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'FERTILIZER', 2], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['WEST'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 7 | `['NORTH']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['WEST'], ['WEST']]` | `[]` |
| 8 | `['NORTH']` | `[['WEST'], ['EAST'], ['CARE'], ['NORTH'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['NORTH']` | `[['WEST'], ['DROP'], ['COLLECT_FERTILIZER'], ['NORTH'], ['NORTH']]` | `[]` |
| 10 | `['NORTH']` | `[['WEST'], ['PASS'], ['EAST'], ['WATER'], ['NORTH']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 11 | `['WATER']` | `[['NORTH'], ['PASS'], ['SOUTH'], ['PASS'], ['NORTH']]` | `[]` |
| 12 | `['PASS']` | `[['NORTH'], ['PASS'], ['DROP'], ['PASS'], ['NORTH']]` | `[]` |
| 13 | `['PASS']` | `[['WATER'], ['PASS'], ['PASS'], ['PASS'], ['WATER']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 14 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 15 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['DROP'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_ANIMAL', 'COW', 1]]` |
## Day 4

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'COW', 1]]` | `[['BUY_PRODUCT', 'WHEAT', 3]]` |
| 5 | `['NORTH']` | `[['CARE'], ['FEED'], ['WEST'], ['NORTH']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 6 | `['NORTH']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 7 | `['NORTH']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH']]` | `[]` |
| 8 | `['WATER']` | `[['NORTH'], ['WEST'], ['CARE'], ['BUILD_PASTURE']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['NORTH']` | `[['WATER'], ['NORTH'], ['COLLECT_FERTILIZER'], ['PLACE', 'COW', 1]]` | `[]` |
| 10 | `['WATER']` | `[['NORTH'], ['WATER'], ['WEST'], ['SOUTH']]` | `[]` |
| 11 | `['WEST']` | `[['WATER'], ['WEST'], ['NORTH'], ['SOUTH']]` | `[]` |
| 12 | `['WATER']` | `[['WEST'], ['WATER'], ['WATER'], ['PICKUP', 'WHEAT', 2]]` | `[]` |
| 13 | `['WEST']` | `[['WATER'], ['NORTH'], ['WEST'], ['NORTH']]` | `[]` |
| 14 | `['WEST']` | `[['WEST'], ['WATER'], ['NORTH'], ['NORTH']]` | `[]` |
| 15 | `['WEST']` | `[['WEST'], ['SOUTH'], ['WATER'], ['FEED']]` | `[]` |
| 16 | `['WATER']` | `[['SOUTH'], ['SOUTH'], ['NORTH'], ['CARE']]` | `[]` |
| 17 | `['SOUTH']` | `[['WATER'], ['WATER'], ['WATER'], ['WEST']]` | `[]` |
| 18 | `['WATER']` | `[['SOUTH'], ['EAST'], ['EAST'], ['WEST']]` | `[]` |
| 19 | `['PASS']` | `[['WATER'], ['NORTH'], ['EAST'], ['WEST']]` | `[]` |
| 20 | `['PASS']` | `[['EAST'], ['NORTH'], ['EAST'], ['WEST']]` | `[]` |
| 21 | `['PASS']` | `[['EAST'], ['NORTH'], ['SOUTH'], ['SOUTH']]` | `[]` |
| 22 | `['PASS']` | `[['EAST'], ['NORTH'], ['SOUTH'], ['SOUTH']]` | `[]` |
| 23 | `['PASS']` | `[['EAST'], ['WATER'], ['SOUTH'], ['WATER']]` | `[]` |
## Day 5

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'FERTILIZER', 3], ['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 3]]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST']]` | `[]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST']]` | `[]` |
| 8 | `['WEST']` | `[['WEST'], ['WEST'], ['CARE'], ['FEED'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['NORTH']` | `[['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['CARE'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 10 | `['WATER']` | `[['NORTH'], ['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['NORTH']]` | `[]` |
| 11 | `['HARVEST']` | `[['NORTH'], ['NORTH'], ['WEST'], ['WEST'], ['NORTH']]` | `[]` |
| 12 | `['NORTH']` | `[['NORTH'], ['NORTH'], ['WEST'], ['WEST'], ['WATER']]` | `[['BUY_SEED', 'STRAWBERRY', 1]]` |
| 13 | `['NORTH']` | `[['WATER'], ['NORTH'], ['NORTH'], ['WEST'], ['HARVEST']]` | `[]` |
| 14 | `['NORTH']` | `[['HARVEST'], ['WATER'], ['WATER'], ['NORTH'], ['PLANT', 'STRAWBERRY']]` | `[]` |
| 15 | `['WATER']` | `[['EAST'], ['HARVEST'], ['EAST'], ['WATER'], ['WATER']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 16 | `['EAST']` | `[['EAST'], ['PLANT', 'WHEAT'], ['EAST'], ['EAST'], ['EAST']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 17 | `['PLANT', 'WHEAT']` | `[['EAST'], ['WATER'], ['EAST'], ['EAST'], ['EAST']]` | `[]` |
| 18 | `['WATER']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['SOUTH']]` | `[]` |
| 19 | `['EAST']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['SOUTH']]` | `[]` |
| 20 | `['EAST']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['SOUTH'], ['SOUTH']]` | `[]` |
| 21 | `['EAST']` | `[['SOUTH'], ['EAST'], ['DROP'], ['SOUTH'], ['SOUTH']]` | `[]` |
| 22 | `['SOUTH']` | `[['DROP'], ['SOUTH'], ['PASS'], ['DROP'], ['DROP']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 23 | `['SOUTH']` | `[['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'WHEAT', 7], ['SELL', 'FERTILIZER', 2], ['BUY_SEED', 'STRAWBERRY', 1]]` |
## Day 6

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 9], ['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_ANIMAL', 'COW', 1]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 5 | `['PICKUP', 'COW', 1]` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['HARVEST'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 7 | `['WEST']` | `[['WEST'], ['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['NORTH'], ['WEST']]` | `[['HIRE']]` |
| 8 | `['BUILD_PASTURE']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['CARE'], ['FEED'], ['WEST'], ['NORTH'], ['WEST'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['PLACE', 'COW', 1]` | `[['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['HARVEST'], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 10 | `['EAST']` | `[['WEST'], ['WEST'], ['NORTH'], ['CARE'], ['NORTH'], ['WATER'], ['NORTH'], ['WEST']]` | `[]` |
| 11 | `['EAST']` | `[['NORTH'], ['WATER'], ['NORTH'], ['COLLECT_FERTILIZER'], ['NORTH'], ['WEST'], ['WATER'], ['NORTH']]` | `[]` |
| 12 | `['PICKUP', 'WHEAT', 2]` | `[['WATER'], ['NORTH'], ['WATER'], ['WEST'], ['WATER'], ['WATER'], ['WEST'], ['WATER']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 13 | `['WEST']` | `[['HARVEST'], ['WATER'], ['WEST'], ['NORTH'], ['HARVEST'], ['WEST'], ['WEST'], ['WEST']]` | `[]` |
| 14 | `['WEST']` | `[['PLANT', 'STRAWBERRY'], ['WEST'], ['WATER'], ['WATER'], ['EAST'], ['WATER'], ['WEST'], ['NORTH']]` | `[['BUY_SEED', 'STRAWBERRY', 2]]` |
| 15 | `['FEED']` | `[['WATER'], ['SOUTH'], ['EAST'], ['WEST'], ['WEST'], ['PASS'], ['NORTH'], ['WATER']]` | `[]` |
| 16 | `['CARE']` | `[['EAST'], ['WATER'], ['SOUTH'], ['WEST'], ['PLANT', 'STRAWBERRY'], ['PASS'], ['NORTH'], ['PASS']]` | `[]` |
| 17 | `['EAST']` | `[['EAST'], ['EAST'], ['SOUTH'], ['SOUTH'], ['WATER'], ['PASS'], ['WATER'], ['PASS']]` | `[]` |
| 18 | `['EAST']` | `[['EAST'], ['EAST'], ['SOUTH'], ['PLANT', 'STRAWBERRY'], ['EAST'], ['PASS'], ['HARVEST'], ['PASS']]` | `[]` |
| 19 | `['DROP']` | `[['EAST'], ['EAST'], ['SOUTH'], ['WATER'], ['EAST'], ['PASS'], ['EAST'], ['PASS']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 20 | `['PASS']` | `[['SOUTH'], ['EAST'], ['DROP'], ['EAST'], ['EAST'], ['PASS'], ['EAST'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['SOUTH'], ['DROP'], ['PASS'], ['EAST'], ['SOUTH'], ['PASS'], ['EAST'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 22 | `['PASS']` | `[['DROP'], ['PASS'], ['PASS'], ['EAST'], ['SOUTH'], ['PASS'], ['EAST'], ['PASS']]` | `[['SELL', 'WOOL', 6], ['SELL', 'FERTILIZER', 1]]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['EAST'], ['SOUTH'], ['PASS'], ['SOUTH'], ['PASS']]` | `[['SELL', 'WHEAT', 4], ['SELL', 'FERTILIZER', 1], ['BUY_LAND']]` |
## Day 7

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 5], ['SELL', 'WOOL', 6], ['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_ANIMAL', 'COW', 1], ['BUY_SEED', 'WHEAT', 4], ['BUY_SEED', 'STRAWBERRY', 1]]` |
| 1 | `['FEED']` | `[['PICKUP', 'COW', 1]]` | `[['HIRE'], ['BUY_ANIMAL', 'COW', 1], ['BUY_SEED', 'STRAWBERRY', 7]]` |
| 2 | `['CARE']` | `[['BUILD_PASTURE'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 3]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['PLACE', 'COW', 1], ['NORTH'], ['PICKUP', 'COW', 1]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['PICKUP', 'WHEAT', 2], ['NORTH'], ['NORTH'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 5 | `['PICKUP', 'WHEAT', 2]` | `[['FEED'], ['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['NORTH']` | `[['CARE'], ['CARE'], ['BUILD_PASTURE'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 7 | `['NORTH']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['PLACE', 'COW', 1], ['FEED'], ['WEST'], ['WEST'], ['NORTH']]` | `[['HIRE']]` |
| 8 | `['FEED']` | `[['WEST'], ['WEST'], ['SOUTH'], ['CARE'], ['NORTH'], ['WEST'], ['NORTH'], ['WEST']]` | `[]` |
| 9 | `['CARE']` | `[['WEST'], ['NORTH'], ['PICKUP', 'WHEAT', 2], ['COLLECT_FERTILIZER'], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 10 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WATER'], ['NORTH'], ['WEST'], ['FEED'], ['FEED'], ['WATER'], ['WEST']]` | `[]` |
| 11 | `['WEST']` | `[['NORTH'], ['WEST'], ['FEED'], ['WEST'], ['CARE'], ['CARE'], ['WEST'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 12 | `['WEST']` | `[['NORTH'], ['WEST'], ['CARE'], ['WATER'], ['COLLECT_FERTILIZER'], ['COLLECT_FERTILIZER'], ['WATER'], ['WATER']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 13 | `['WEST']` | `[['NORTH'], ['WEST'], ['WEST'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST'], ['EAST']]` | `[]` |
| 14 | `['NORTH']` | `[['WATER'], ['NORTH'], ['WEST'], ['WATER'], ['NORTH'], ['WEST'], ['WATER'], ['EAST']]` | `[]` |
| 15 | `['NORTH']` | `[['EAST'], ['WATER'], ['WEST'], ['EAST'], ['NORTH'], ['WATER'], ['EAST'], ['EAST']]` | `[]` |
| 16 | `['WATER']` | `[['EAST'], ['EAST'], ['NORTH'], ['EAST'], ['WATER'], ['EAST'], ['EAST'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 17 | `['WEST']` | `[['EAST'], ['EAST'], ['WATER'], ['EAST'], ['EAST'], ['EAST'], ['EAST'], ['NORTH']]` | `[]` |
| 18 | `['PLANT', 'WHEAT']` | `[['PLANT', 'WHEAT'], ['EAST'], ['EAST'], ['SOUTH'], ['EAST'], ['EAST'], ['EAST'], ['PLANT', 'STRAWBERRY']]` | `[]` |
| 19 | `['WATER']` | `[['WATER'], ['EAST'], ['EAST'], ['DROP'], ['EAST'], ['EAST'], ['PLANT', 'STRAWBERRY'], ['WATER']]` | `[]` |
| 20 | `['EAST']` | `[['SOUTH'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PLANT', 'WHEAT'], ['DROP'], ['WATER'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 21 | `['EAST']` | `[['SOUTH'], ['SOUTH'], ['SOUTH'], ['PASS'], ['WATER'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1], ['BUY_SEED', 'WHEAT', 2]]` |
| 22 | `['EAST']` | `[['SOUTH'], ['SOUTH'], ['DROP'], ['PASS'], ['WEST'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_SEED', 'STRAWBERRY', 1]]` |
| 23 | `['EAST']` | `[['SOUTH'], ['DROP'], ['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
## Day 8

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'FERTILIZER', 3], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_SEED', 'STRAWBERRY', 2]]` |
| 2 | `['HARVEST']` | `[['FEED'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['DROP']` | `[['CARE'], ['NORTH'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['CARE']` | `[['COLLECT_FERTILIZER'], ['NORTH'], ['NORTH'], ['PICKUP', 'WHEAT', 2]]` | `[['SELL', 'MILK', 6], ['HIRE']]` |
| 5 | `['COLLECT_FERTILIZER']` | `[['DROP'], ['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1], ['BUY_ANIMAL', 'COW', 2]]` |
| 6 | `['DROP']` | `[['PICKUP', 'COW', 1], ['HARVEST'], ['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 7 | `['PICKUP', 'WHEAT', 2]` | `[['EAST'], ['CARE'], ['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'COW', 1]]` | `[['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 8 | `['WEST']` | `[['DIG'], ['COLLECT_FERTILIZER'], ['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['WEST']` | `[['BUILD_PASTURE'], ['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['NORTH'], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 10 | `['FEED']` | `[['PLACE', 'COW', 1], ['WEST'], ['WEST'], ['WEST'], ['FEED'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST'], ['NORTH']]` | `[]` |
| 11 | `['CARE']` | `[['WEST'], ['WEST'], ['WEST'], ['WEST'], ['CARE'], ['CARE'], ['BUILD_PASTURE'], ['NORTH'], ['WEST'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 3]]` |
| 12 | `['COLLECT_FERTILIZER']` | `[['PICKUP', 'WHEAT', 2], ['NORTH'], ['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['COLLECT_FERTILIZER'], ['PLACE', 'COW', 1], ['NORTH'], ['NORTH'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 13 | `['NORTH']` | `[['EAST'], ['WATER'], ['WEST'], ['NORTH'], ['WEST'], ['NORTH'], ['SOUTH'], ['WATER'], ['NORTH'], ['WATER']]` | `[]` |
| 14 | `['WATER']` | `[['FEED'], ['EAST'], ['WATER'], ['NORTH'], ['WATER'], ['NORTH'], ['SOUTH'], ['WEST'], ['NORTH'], ['WEST']]` | `[]` |
| 15 | `['WEST']` | `[['CARE'], ['WATER'], ['SOUTH'], ['WATER'], ['WEST'], ['WATER'], ['PICKUP', 'WHEAT', 2], ['WATER'], ['NORTH'], ['WEST']]` | `[]` |
| 16 | `['WATER']` | `[['EAST'], ['WEST'], ['WATER'], ['EAST'], ['WEST'], ['EAST'], ['NORTH'], ['PASS'], ['WATER'], ['WATER']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 17 | `['EAST']` | `[['NORTH'], ['WEST'], ['EAST'], ['SOUTH'], ['NORTH'], ['EAST'], ['NORTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['EAST']` | `[['PLANT', 'STRAWBERRY'], ['NORTH'], ['EAST'], ['SOUTH'], ['NORTH'], ['EAST'], ['FEED'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['EAST']` | `[['WATER'], ['WATER'], ['EAST'], ['WATER'], ['WATER'], ['EAST'], ['CARE'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 20 | `['SOUTH']` | `[['WEST'], ['EAST'], ['EAST'], ['EAST'], ['EAST'], ['PLANT', 'STRAWBERRY'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['DROP']` | `[['WEST'], ['EAST'], ['DROP'], ['EAST'], ['EAST'], ['WATER'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['SOUTH'], ['EAST'], ['PASS'], ['EAST'], ['EAST'], ['WEST'], ['DROP'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 2]]` |
| 23 | `['PASS']` | `[['DROP'], ['EAST'], ['PASS'], ['DROP'], ['SOUTH'], ['WEST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_SEED', 'STRAWBERRY', 1]]` |