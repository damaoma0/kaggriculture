# reactive-copy: opening moves

Seed 86301, seat 0; zero-based day/hour.

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
| 10 | `['NORTH']` | `[['NORTH'], ['WEST'], ['WEST'], ['PLANT', 'WHEAT']]` | `[]` |
| 11 | `['PLANT', 'WHEAT']` | `[['EAST'], ['EAST'], ['EAST'], ['WATER']]` | `[]` |
| 12 | `['WATER']` | `[['EAST'], ['EAST'], ['EAST'], ['PASS']]` | `[]` |
| 13 | `['PASS']` | `[['EAST'], ['EAST'], ['SOUTH'], ['PASS']]` | `[]` |
| 14 | `['PASS']` | `[['SOUTH'], ['EAST'], ['DROP'], ['PASS']]` | `[]` |
| 15 | `['PASS']` | `[['SOUTH'], ['DROP'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 16 | `['PASS']` | `[['DROP'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1], ['BUY_PRODUCT', 'WHEAT', 1], ['BUY_SEED', 'WHEAT', 4]]` |
| 17 | `['WEST']` | `[['PASS'], ['PASS'], ['PASS'], ['NORTH']]` | `[['SELL', 'FERTILIZER', 1], ['BUY_SEED', 'MELON', 1], ['BUY_SEED', 'WHEAT', 1]]` |
| 18 | `['PLANT', 'WHEAT']` | `[['PASS'], ['PASS'], ['PASS'], ['PLANT', 'WHEAT']]` | `[['BUY_SEED', 'MELON', 1]]` |
| 19 | `['WATER']` | `[['PASS'], ['PASS'], ['PASS'], ['WATER']]` | `[]` |
| 20 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
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
| 13 | `['WEST']` | `[['PLANT', 'MELON'], ['NORTH'], ['EAST'], ['PLANT', 'MELON']]` | `[]` |
| 14 | `['PLANT', 'WHEAT']` | `[['WATER'], ['NORTH'], ['WEST'], ['WATER']]` | `[]` |
| 15 | `['WATER']` | `[['EAST'], ['NORTH'], ['WEST'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['EAST'], ['NORTH'], ['NORTH'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['EAST'], ['PLANT', 'WHEAT'], ['NORTH'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['SOUTH'], ['WATER'], ['PLANT', 'WHEAT'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['SOUTH'], ['EAST'], ['WATER'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['DROP'], ['EAST'], ['EAST'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['EAST'], ['EAST'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 22 | `['PASS']` | `[['PASS'], ['EAST'], ['EAST'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 23 | `['PASS']` | `[['PASS'], ['SOUTH'], ['EAST'], ['PASS']]` | `[]` |
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
| 9 | `['NORTH']` | `[['WEST'], ['DROP'], ['COLLECT_FERTILIZER'], ['NORTH'], ['WEST']]` | `[]` |
| 10 | `['NORTH']` | `[['NORTH'], ['PASS'], ['EAST'], ['WATER'], ['NORTH']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 11 | `['WATER']` | `[['NORTH'], ['PASS'], ['SOUTH'], ['PASS'], ['NORTH']]` | `[]` |
| 12 | `['PASS']` | `[['NORTH'], ['PASS'], ['DROP'], ['PASS'], ['WATER']]` | `[]` |
| 13 | `['PASS']` | `[['WATER'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 14 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 15 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
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
| 8 | `['WATER']` | `[['NORTH'], ['WEST'], ['CARE'], ['DIG']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['NORTH']` | `[['WATER'], ['NORTH'], ['COLLECT_FERTILIZER'], ['BUILD_PASTURE']]` | `[]` |
| 10 | `['WATER']` | `[['NORTH'], ['WATER'], ['WEST'], ['PLACE', 'COW', 1]]` | `[]` |
| 11 | `['WEST']` | `[['WATER'], ['WEST'], ['NORTH'], ['SOUTH']]` | `[]` |
| 12 | `['WATER']` | `[['WEST'], ['WATER'], ['WATER'], ['SOUTH']]` | `[]` |
| 13 | `['WEST']` | `[['WATER'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[]` |
| 14 | `['WEST']` | `[['WEST'], ['WATER'], ['NORTH'], ['NORTH']]` | `[]` |
| 15 | `['WEST']` | `[['WEST'], ['SOUTH'], ['WATER'], ['NORTH']]` | `[]` |
| 16 | `['WATER']` | `[['WATER'], ['SOUTH'], ['NORTH'], ['FEED']]` | `[]` |
| 17 | `['SOUTH']` | `[['SOUTH'], ['WATER'], ['WATER'], ['CARE']]` | `[]` |
| 18 | `['SOUTH']` | `[['WATER'], ['WEST'], ['EAST'], ['SOUTH']]` | `[]` |
| 19 | `['SOUTH']` | `[['EAST'], ['NORTH'], ['WATER'], ['SOUTH']]` | `[]` |
| 20 | `['SOUTH']` | `[['EAST'], ['WATER'], ['EAST'], ['DROP']]` | `[]` |
| 21 | `['WATER']` | `[['EAST'], ['EAST'], ['EAST'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['EAST'], ['EAST'], ['SOUTH'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['PASS']]` | `[]` |
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
| 10 | `['WATER']` | `[['WEST'], ['NORTH'], ['WEST'], ['COLLECT_FERTILIZER'], ['NORTH']]` | `[]` |
| 11 | `['HARVEST']` | `[['NORTH'], ['NORTH'], ['WEST'], ['WEST'], ['NORTH']]` | `[]` |
| 12 | `['NORTH']` | `[['WATER'], ['NORTH'], ['WEST'], ['WEST'], ['WATER']]` | `[['BUY_SEED', 'STRAWBERRY', 1]]` |
| 13 | `['NORTH']` | `[['HARVEST'], ['NORTH'], ['NORTH'], ['WEST'], ['HARVEST']]` | `[]` |
| 14 | `['NORTH']` | `[['SOUTH'], ['WATER'], ['WATER'], ['NORTH'], ['PLANT', 'STRAWBERRY']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 15 | `['WATER']` | `[['NORTH'], ['HARVEST'], ['EAST'], ['NORTH'], ['WATER']]` | `[]` |
| 16 | `['EAST']` | `[['EAST'], ['PLANT', 'WHEAT'], ['EAST'], ['WATER'], ['EAST']]` | `[]` |
| 17 | `['EAST']` | `[['EAST'], ['WATER'], ['EAST'], ['EAST'], ['EAST']]` | `[]` |
| 18 | `['EAST']` | `[['EAST'], ['EAST'], ['SOUTH'], ['EAST'], ['SOUTH']]` | `[]` |
| 19 | `['EAST']` | `[['EAST'], ['EAST'], ['SOUTH'], ['EAST'], ['SOUTH']]` | `[]` |
| 20 | `['SOUTH']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['SOUTH']]` | `[]` |
| 21 | `['SOUTH']` | `[['SOUTH'], ['SOUTH'], ['DROP'], ['SOUTH'], ['SOUTH']]` | `[]` |
| 22 | `['SOUTH']` | `[['DROP'], ['SOUTH'], ['PASS'], ['SOUTH'], ['DROP']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 23 | `['SOUTH']` | `[['PASS'], ['SOUTH'], ['PASS'], ['SOUTH'], ['PASS']]` | `[['SELL', 'WHEAT', 6], ['SELL', 'FERTILIZER', 1], ['BUY_SEED', 'STRAWBERRY', 1]]` |
## Day 6

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 10], ['SELL', 'FERTILIZER', 2], ['HIRE'], ['BUY_SEED', 'STRAWBERRY', 1]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2], ['BUY_ANIMAL', 'COW', 1]]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 5 | `['PICKUP', 'COW', 1]` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['HARVEST'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 7 | `['WEST']` | `[['WEST'], ['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['NORTH'], ['WEST']]` | `[['HIRE']]` |
| 8 | `['BUILD_PASTURE']` | `[['NORTH'], ['COLLECT_FERTILIZER'], ['CARE'], ['FEED'], ['WEST'], ['NORTH'], ['WEST'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['PLACE', 'COW', 1]` | `[['WATER'], ['WEST'], ['COLLECT_FERTILIZER'], ['HARVEST'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 10 | `['EAST']` | `[['NORTH'], ['WEST'], ['NORTH'], ['CARE'], ['NORTH'], ['WATER'], ['NORTH'], ['WEST']]` | `[]` |
| 11 | `['EAST']` | `[['WATER'], ['WEST'], ['NORTH'], ['COLLECT_FERTILIZER'], ['NORTH'], ['WEST'], ['WATER'], ['WEST']]` | `[]` |
| 12 | `['PICKUP', 'WHEAT', 2]` | `[['NORTH'], ['NORTH'], ['WATER'], ['WEST'], ['WATER'], ['WEST'], ['WEST'], ['WATER']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 13 | `['WEST']` | `[['WATER'], ['NORTH'], ['WEST'], ['NORTH'], ['HARVEST'], ['WEST'], ['WATER'], ['WEST']]` | `[]` |
| 14 | `['WEST']` | `[['WEST'], ['NORTH'], ['WEST'], ['WATER'], ['PLANT', 'STRAWBERRY'], ['WEST'], ['WEST'], ['WATER']]` | `[['BUY_SEED', 'STRAWBERRY', 1]]` |
| 15 | `['FEED']` | `[['WEST'], ['WATER'], ['SOUTH'], ['WEST'], ['WATER'], ['NORTH'], ['PLANT', 'STRAWBERRY'], ['PASS']]` | `[]` |
| 16 | `['CARE']` | `[['SOUTH'], ['HARVEST'], ['WATER'], ['WEST'], ['EAST'], ['WATER'], ['WATER'], ['PASS']]` | `[]` |
| 17 | `['EAST']` | `[['SOUTH'], ['EAST'], ['EAST'], ['PLANT', 'STRAWBERRY'], ['EAST'], ['HARVEST'], ['PASS'], ['PASS']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 18 | `['EAST']` | `[['WATER'], ['WEST'], ['EAST'], ['WATER'], ['EAST'], ['PLANT', 'WHEAT'], ['PASS'], ['PASS']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 19 | `['DROP']` | `[['EAST'], ['PLANT', 'WHEAT'], ['SOUTH'], ['EAST'], ['SOUTH'], ['WATER'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['EAST'], ['WATER'], ['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['EAST'], ['EAST'], ['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['SOUTH'], ['EAST'], ['DROP'], ['EAST'], ['DROP'], ['EAST'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['SOUTH'], ['EAST'], ['PASS'], ['SOUTH'], ['PASS'], ['EAST'], ['PASS'], ['PASS']]` | `[['SELL', 'WHEAT', 2], ['SELL', 'FERTILIZER', 1]]` |
## Day 7

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 11], ['SELL', 'WOOL', 12], ['SELL', 'FERTILIZER', 3], ['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2], ['BUY_LAND']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 5], ['BUY_ANIMAL', 'COW', 2], ['BUY_SEED', 'WHEAT', 5], ['BUY_SEED', 'STRAWBERRY', 8]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'COW', 1]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['BUILD_PASTURE'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 5 | `['PICKUP', 'WHEAT', 2]` | `[['CARE'], ['FEED'], ['PLACE', 'COW', 1], ['NORTH'], ['PICKUP', 'COW', 1]]` | `[['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['PICKUP', 'WHEAT', 2], ['NORTH'], ['NORTH'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 3]]` |
| 7 | `['NORTH']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST'], ['NORTH']]` | `[['HIRE']]` |
| 8 | `['FEED']` | `[['WEST'], ['NORTH'], ['CARE'], ['FEED'], ['BUILD_PASTURE'], ['WEST'], ['NORTH'], ['WEST']]` | `[]` |
| 9 | `['CARE']` | `[['NORTH'], ['NORTH'], ['WEST'], ['CARE'], ['PLACE', 'COW', 1], ['NORTH'], ['NORTH'], ['WEST']]` | `[]` |
| 10 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WATER'], ['WEST'], ['COLLECT_FERTILIZER'], ['SOUTH'], ['FEED'], ['WATER'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 11 | `['WEST']` | `[['NORTH'], ['NORTH'], ['WEST'], ['WEST'], ['PICKUP', 'WHEAT', 2], ['CARE'], ['WEST'], ['WATER']]` | `[['BUY_PRODUCT', 'WHEAT', 3]]` |
| 12 | `['WEST']` | `[['WATER'], ['WATER'], ['WEST'], ['WEST'], ['NORTH'], ['COLLECT_FERTILIZER'], ['NORTH'], ['WEST']]` | `[]` |
| 13 | `['NORTH']` | `[['SOUTH'], ['EAST'], ['WATER'], ['WATER'], ['FEED'], ['WEST'], ['WATER'], ['WATER']]` | `[]` |
| 14 | `['NORTH']` | `[['WATER'], ['EAST'], ['EAST'], ['EAST'], ['CARE'], ['WEST'], ['EAST'], ['EAST']]` | `[]` |
| 15 | `['NORTH']` | `[['EAST'], ['PLANT', 'STRAWBERRY'], ['EAST'], ['EAST'], ['EAST'], ['WATER'], ['EAST'], ['EAST']]` | `[]` |
| 16 | `['WATER']` | `[['EAST'], ['WATER'], ['EAST'], ['EAST'], ['EAST'], ['EAST'], ['EAST'], ['EAST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 17 | `['EAST']` | `[['EAST'], ['EAST'], ['DROP'], ['NORTH'], ['NORTH'], ['EAST'], ['PLANT', 'WHEAT'], ['EAST']]` | `[]` |
| 18 | `['EAST']` | `[['EAST'], ['EAST'], ['PASS'], ['NORTH'], ['PLANT', 'STRAWBERRY'], ['EAST'], ['WATER'], ['EAST']]` | `[]` |
| 19 | `['EAST']` | `[['PLANT', 'STRAWBERRY'], ['PLANT', 'WHEAT'], ['PASS'], ['PLANT', 'WHEAT'], ['WATER'], ['EAST'], ['EAST'], ['EAST']]` | `[]` |
| 20 | `['SOUTH']` | `[['WATER'], ['WATER'], ['PASS'], ['WATER'], ['WEST'], ['DROP'], ['PLANT', 'WHEAT'], ['PLANT', 'STRAWBERRY']]` | `[]` |
| 21 | `['SOUTH']` | `[['WEST'], ['WEST'], ['PASS'], ['SOUTH'], ['WEST'], ['PASS'], ['WATER'], ['WATER']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 22 | `['SOUTH']` | `[['SOUTH'], ['WEST'], ['PASS'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
| 23 | `['SOUTH']` | `[['SOUTH'], ['SOUTH'], ['PASS'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_SEED', 'WHEAT', 1]]` |
## Day 8

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'FERTILIZER', 4], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_SEED', 'STRAWBERRY', 3]]` |
| 2 | `['HARVEST']` | `[['FEED'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['DROP']` | `[['CARE'], ['NORTH'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['CARE']` | `[['COLLECT_FERTILIZER'], ['NORTH'], ['NORTH'], ['PICKUP', 'WHEAT', 2]]` | `[['SELL', 'MILK', 6], ['HIRE']]` |
| 5 | `['COLLECT_FERTILIZER']` | `[['DROP'], ['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1], ['BUY_ANIMAL', 'COW', 2]]` |
| 6 | `['DROP']` | `[['PICKUP', 'COW', 1], ['HARVEST'], ['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 7 | `['PICKUP', 'WHEAT', 2]` | `[['EAST'], ['CARE'], ['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'COW', 1]]` | `[['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 8 | `['WEST']` | `[['BUILD_PASTURE'], ['COLLECT_FERTILIZER'], ['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['WEST']` | `[['PLACE', 'COW', 1], ['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['NORTH'], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 10 | `['FEED']` | `[['WEST'], ['WEST'], ['WEST'], ['WEST'], ['FEED'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST'], ['NORTH']]` | `[]` |
| 11 | `['CARE']` | `[['PICKUP', 'WHEAT', 2], ['WEST'], ['WEST'], ['WEST'], ['CARE'], ['CARE'], ['BUILD_PASTURE'], ['NORTH'], ['WEST'], ['NORTH']]` | `[['BUY_PRODUCT', 'WHEAT', 5]]` |
| 12 | `['COLLECT_FERTILIZER']` | `[['EAST'], ['NORTH'], ['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['COLLECT_FERTILIZER'], ['PLACE', 'COW', 1], ['NORTH'], ['NORTH'], ['NORTH']]` | `[]` |
| 13 | `['NORTH']` | `[['FEED'], ['WATER'], ['WEST'], ['NORTH'], ['WEST'], ['WEST'], ['SOUTH'], ['WATER'], ['NORTH'], ['WATER']]` | `[]` |
| 14 | `['WATER']` | `[['CARE'], ['WEST'], ['WATER'], ['NORTH'], ['WATER'], ['WEST'], ['SOUTH'], ['WEST'], ['NORTH'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 15 | `['NORTH']` | `[['EAST'], ['NORTH'], ['EAST'], ['WATER'], ['WEST'], ['WEST'], ['PICKUP', 'WHEAT', 2], ['WATER'], ['NORTH'], ['WATER']]` | `[]` |
| 16 | `['WATER']` | `[['EAST'], ['NORTH'], ['WATER'], ['SOUTH'], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST'], ['WATER'], ['WEST']]` | `[]` |
| 17 | `['EAST']` | `[['PLANT', 'STRAWBERRY'], ['WATER'], ['EAST'], ['SOUTH'], ['WATER'], ['NORTH'], ['NORTH'], ['WEST'], ['PASS'], ['WEST']]` | `[]` |
| 18 | `['EAST']` | `[['WATER'], ['EAST'], ['EAST'], ['WATER'], ['EAST'], ['WATER'], ['FEED'], ['WATER'], ['PASS'], ['SOUTH']]` | `[]` |
| 19 | `['SOUTH']` | `[['NORTH'], ['EAST'], ['EAST'], ['EAST'], ['EAST'], ['EAST'], ['CARE'], ['PASS'], ['PASS'], ['SOUTH']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 20 | `['SOUTH']` | `[['PLANT', 'STRAWBERRY'], ['EAST'], ['SOUTH'], ['EAST'], ['SOUTH'], ['EAST'], ['SOUTH'], ['PASS'], ['PASS'], ['SOUTH']]` | `[]` |
| 21 | `['DROP']` | `[['WATER'], ['EAST'], ['DROP'], ['EAST'], ['SOUTH'], ['EAST'], ['SOUTH'], ['PASS'], ['PASS'], ['WATER']]` | `[]` |
| 22 | `['PASS']` | `[['WEST'], ['SOUTH'], ['PASS'], ['EAST'], ['SOUTH'], ['EAST'], ['DROP'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 2]]` |
| 23 | `['PASS']` | `[['WEST'], ['SOUTH'], ['PASS'], ['DROP'], ['DROP'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |