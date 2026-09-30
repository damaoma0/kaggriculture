# shop-adaptive: opening moves

Seed 89000, seat 1; zero-based day/hour.

## Day 0

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PASS']` | `[]` | `[['BUY_PRODUCT', 'WHEAT', 13]]` |
| 1 | `['NORTH']` | `[]` | `[['SELL', 'WHEAT', 9], ['BUY_SEED', 'WHEAT', 7], ['BUY_SEED', 'MELON', 12], ['HIRE'], ['HIRE'], ['HIRE'], ['HIRE'], ['HIRE'], ['BUY_ANIMAL', 'COW', 2], ['BUY_ANIMAL', 'SHEEP', 2]]` |
| 2 | `['WEST']` | `[['PICKUP', 'COW'], ['WEST'], ['NORTH'], ['WEST'], ['PICKUP', 'COW']]` | `[]` |
| 3 | `['WEST']` | `[['NORTH'], ['PICKUP', 'SHEEP'], ['NORTH'], ['NORTH'], ['BUILD_PASTURE']]` | `[['SELL', 'WHEAT', 1], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 4 | `['PLANT', 'MELON']` | `[['BUILD_PASTURE'], ['PICKUP', 'WHEAT'], ['NORTH'], ['PICKUP', 'SHEEP'], ['PLACE', 'COW']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 5 | `['WATER']` | `[['PLACE', 'COW'], ['WEST'], ['NORTH'], ['PICKUP', 'WHEAT'], ['CARE']]` | `[['SELL', 'WHEAT', 2], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 6 | `['WEST']` | `[['CARE'], ['BUILD_PASTURE'], ['PLANT', 'MELON'], ['WEST'], ['WEST']]` | `[['SELL', 'WHEAT', 1], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 7 | `['PLANT', 'MELON']` | `[['WEST'], ['PLACE', 'SHEEP'], ['WATER'], ['NORTH'], ['WEST']]` | `[['SELL', 'WHEAT', 1], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 8 | `['WATER']` | `[['NORTH'], ['FEED'], ['WEST'], ['BUILD_PASTURE'], ['WEST']]` | `[['SELL', 'WHEAT', 1], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['EAST']` | `[['PLANT', 'MELON'], ['CARE'], ['WEST'], ['PLACE', 'SHEEP'], ['PLANT', 'MELON']]` | `[['SELL', 'WHEAT', 1], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 10 | `['EAST']` | `[['WATER'], ['NORTH'], ['WEST'], ['FEED'], ['WATER']]` | `[['SELL', 'WHEAT', 1], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 11 | `['CARE']` | `[['WEST'], ['NORTH'], ['WEST'], ['CARE'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 12 | `['PASS']` | `[['PLANT', 'MELON'], ['NORTH'], ['PLANT', 'WHEAT'], ['WEST'], ['PLANT', 'MELON']]` | `[]` |
| 13 | `['WEST']` | `[['WATER'], ['PLANT', 'MELON'], ['WATER'], ['NORTH'], ['WATER']]` | `[]` |
| 14 | `['EAST']` | `[['WEST'], ['WATER'], ['NORTH'], ['NORTH'], ['NORTH']]` | `[]` |
| 15 | `['PASS']` | `[['PLANT', 'MELON'], ['NORTH'], ['PLANT', 'WHEAT'], ['PLANT', 'MELON'], ['PLANT', 'WHEAT']]` | `[]` |
| 16 | `['WEST']` | `[['WATER'], ['PLANT', 'MELON'], ['WATER'], ['WATER'], ['WATER']]` | `[]` |
| 17 | `['EAST']` | `[['WEST'], ['WATER'], ['EAST'], ['WEST'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['PLANT', 'WHEAT'], ['EAST'], ['PLANT', 'WHEAT'], ['PLANT', 'WHEAT'], ['PASS']]` | `[]` |
| 19 | `['WEST']` | `[['WATER'], ['PLANT', 'MELON'], ['WATER'], ['WATER'], ['EAST']]` | `[]` |
| 20 | `['PASS']` | `[['PASS'], ['WATER'], ['EAST'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['PASS'], ['PLANT', 'WHEAT'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['WATER'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 1

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT']` | `[]` | `[['HIRE'], ['HIRE'], ['HIRE'], ['HIRE']]` |
| 1 | `['WEST']` | `[['WEST'], ['WEST'], ['WEST'], ['PICKUP', 'WHEAT']]` | `[]` |
| 2 | `['NORTH']` | `[['PICKUP', 'WHEAT'], ['WEST'], ['NORTH'], ['NORTH']]` | `[]` |
| 3 | `['FEED']` | `[['FEED'], ['NORTH'], ['NORTH'], ['FEED']]` | `[]` |
| 4 | `['CARE']` | `[['CARE'], ['BUILD_PASTURE'], ['NORTH'], ['CARE']]` | `[]` |
| 5 | `['COLLECT_FERTILIZER']` | `[['COLLECT_FERTILIZER'], ['WEST'], ['BUILD_PASTURE'], ['COLLECT_FERTILIZER']]` | `[]` |
| 6 | `['EAST']` | `[['PLACE', 'FERTILIZER'], ['WEST'], ['PASS'], ['SOUTH']]` | `[['SELL', 'FERTILIZER', 1], ['BUY_PRODUCT', 'WHEAT', 3]]` |
| 7 | `['SOUTH']` | `[['WEST'], ['NORTH'], ['SOUTH'], ['PLACE', 'FERTILIZER']]` | `[['SELL', 'FERTILIZER', 1], ['BUY_PRODUCT', 'WHEAT', 4]]` |
| 8 | `['PLACE', 'FERTILIZER']` | `[['COLLECT_FERTILIZER'], ['WATER'], ['SOUTH'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 9 | `['PASS']` | `[['CARE'], ['NORTH'], ['PICKUP', 'WHEAT'], ['CARE']]` | `[]` |
| 10 | `['PASS']` | `[['EAST'], ['WATER'], ['WEST'], ['PASS']]` | `[]` |
| 11 | `['PASS']` | `[['DROP'], ['EAST'], ['FEED'], ['PASS']]` | `[]` |
| 12 | `['PASS']` | `[['PASS'], ['NORTH'], ['PASS'], ['PASS']]` | `[]` |
| 13 | `['PASS']` | `[['PASS'], ['WATER'], ['PASS'], ['PASS']]` | `[]` |
| 14 | `['PASS']` | `[['PASS'], ['WEST'], ['PASS'], ['PASS']]` | `[]` |
| 15 | `['PASS']` | `[['PASS'], ['WATER'], ['PASS'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['PASS'], ['NORTH'], ['PASS'], ['PASS']]` | `[]` |
| 17 | `['PASS']` | `[['PASS'], ['WATER'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['PASS'], ['EAST'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['PASS'], ['WATER'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['PASS'], ['EAST'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['PASS'], ['WATER'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
## Day 2

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 4]` | `[]` | `[['HIRE'], ['HIRE'], ['HIRE'], ['HIRE'], ['BUY_SEED', 'WHEAT', 5]]` |
| 1 | `['FEED']` | `[['WEST'], ['WEST'], ['WEST'], ['WEST']]` | `[['SELL', 'WHEAT', 2]]` |
| 2 | `['CARE']` | `[['WEST'], ['WEST'], ['NORTH'], ['NORTH']]` | `[]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['NORTH'], ['NORTH']]` | `[]` |
| 4 | `['NORTH']` | `[['NORTH'], ['WEST'], ['NORTH'], ['WATER']]` | `[]` |
| 5 | `['FEED']` | `[['NORTH'], ['NORTH'], ['NORTH'], ['NORTH']]` | `[]` |
| 6 | `['CARE']` | `[['NORTH'], ['WATER'], ['WATER'], ['WATER']]` | `[]` |
| 7 | `['COLLECT_FERTILIZER']` | `[['WATER'], ['EAST'], ['NORTH'], ['WEST']]` | `[]` |
| 8 | `['WEST']` | `[['EAST'], ['WATER'], ['WATER'], ['WATER']]` | `[]` |
| 9 | `['FEED']` | `[['WEST'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 10 | `['CARE']` | `[['WEST'], ['WATER'], ['WATER'], ['WEST']]` | `[]` |
| 11 | `['COLLECT_FERTILIZER']` | `[['WEST'], ['NORTH'], ['WEST'], ['WATER']]` | `[]` |
| 12 | `['SOUTH']` | `[['SOUTH'], ['WATER'], ['WEST'], ['HARVEST']]` | `[]` |
| 13 | `['FEED']` | `[['EAST'], ['EAST'], ['WATER'], ['PLANT', 'WHEAT']]` | `[]` |
| 14 | `['CARE']` | `[['SOUTH'], ['WATER'], ['HARVEST'], ['WATER']]` | `[]` |
| 15 | `['COLLECT_FERTILIZER']` | `[['SOUTH'], ['SOUTH'], ['PLANT', 'WHEAT'], ['NORTH']]` | `[]` |
| 16 | `['EAST']` | `[['WATER'], ['WATER'], ['WATER'], ['WATER']]` | `[]` |
| 17 | `['PLACE', 'FERTILIZER', 4]` | `[['NORTH'], ['WEST'], ['EAST'], ['HARVEST']]` | `[['SELL', 'FERTILIZER', 4], ['BUY_ANIMAL', 'COW', 1]]` |
| 18 | `['PICKUP', 'COW']` | `[['NORTH'], ['WEST'], ['WATER'], ['PLANT', 'WHEAT']]` | `[]` |
| 19 | `['NORTH']` | `[['WEST'], ['WATER'], ['WEST'], ['WATER']]` | `[]` |
| 20 | `['NORTH']` | `[['WATER'], ['NORTH'], ['WEST'], ['EAST']]` | `[]` |
| 21 | `['PLACE', 'COW']` | `[['WEST'], ['WATER'], ['PASS'], ['SOUTH']]` | `[]` |
| 22 | `['CARE']` | `[['PASS'], ['PASS'], ['PASS'], ['WATER']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 3

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['EAST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['PICKUP', 'WHEAT', 1], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['WEST'], ['WEST'], ['WEST'], ['PASS']]` | `[['HIRE']]` |
| 8 | `['WEST']` | `[['WEST'], ['EAST'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['PASS'], ['PASS']]` | `[]` |
| 9 | `['NORTH']` | `[['WEST'], ['DROP'], ['COLLECT_FERTILIZER'], ['NORTH'], ['NORTH'], ['WEST'], ['PASS'], ['PASS']]` | `[]` |
| 10 | `['WATER']` | `[['WEST'], ['PASS'], ['SOUTH'], ['FEED'], ['NORTH'], ['NORTH'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 11 | `['PASS']` | `[['NORTH'], ['PASS'], ['SOUTH'], ['CARE'], ['NORTH'], ['NORTH'], ['PASS'], ['PASS']]` | `[]` |
| 12 | `['PASS']` | `[['WATER'], ['PASS'], ['DROP'], ['COLLECT_FERTILIZER'], ['WATER'], ['NORTH'], ['PASS'], ['PASS']]` | `[]` |
| 13 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['EAST'], ['PASS'], ['WATER'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 14 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 9]]` |
| 15 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['DROP'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 16 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 17 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['DROP'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 21 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 4

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 5 | `['WEST']` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 7 | `['WEST']` | `[['NORTH'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 8 | `['WEST']` | `[['NORTH'], ['NORTH'], ['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['NORTH']` | `[['WATER'], ['NORTH'], ['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['WEST'], ['WEST'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 10 | `['WATER']` | `[['NORTH'], ['WATER'], ['WEST'], ['COLLECT_FERTILIZER'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 11 | `['HARVEST']` | `[['WATER'], ['WEST'], ['NORTH'], ['WEST'], ['NORTH'], ['NORTH'], ['WEST'], ['NORTH']]` | `[]` |
| 12 | `['SOUTH']` | `[['WEST'], ['WATER'], ['WATER'], ['WEST'], ['WATER'], ['NORTH'], ['NORTH'], ['WATER']]` | `[]` |
| 13 | `['WATER']` | `[['WATER'], ['NORTH'], ['WEST'], ['WATER'], ['HARVEST'], ['WATER'], ['NORTH'], ['WEST']]` | `[]` |
| 14 | `['EAST']` | `[['WEST'], ['WATER'], ['WEST'], ['WEST'], ['EAST'], ['HARVEST'], ['WATER'], ['NORTH']]` | `[]` |
| 15 | `['WATER']` | `[['WEST'], ['EAST'], ['NORTH'], ['NORTH'], ['EAST'], ['EAST'], ['HARVEST'], ['WATER']]` | `[]` |
| 16 | `['EAST']` | `[['WEST'], ['EAST'], ['WATER'], ['NORTH'], ['SOUTH'], ['EAST'], ['EAST'], ['PASS']]` | `[]` |
| 17 | `['EAST']` | `[['WATER'], ['SOUTH'], ['EAST'], ['WATER'], ['SOUTH'], ['EAST'], ['EAST'], ['PASS']]` | `[]` |
| 18 | `['EAST']` | `[['EAST'], ['SOUTH'], ['EAST'], ['EAST'], ['SOUTH'], ['SOUTH'], ['EAST'], ['PASS']]` | `[]` |
| 19 | `['DROP']` | `[['EAST'], ['SOUTH'], ['EAST'], ['EAST'], ['SOUTH'], ['SOUTH'], ['EAST'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['EAST'], ['DROP'], ['SOUTH'], ['EAST'], ['DROP'], ['SOUTH'], ['SOUTH'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['EAST'], ['PASS'], ['SOUTH'], ['EAST'], ['PASS'], ['DROP'], ['SOUTH'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 22 | `['PASS']` | `[['SOUTH'], ['PASS'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['DROP'], ['PASS']]` | `[['SELL', 'WHEAT', 1]]` |
| 23 | `['PASS']` | `[['SOUTH'], ['PASS'], ['SOUTH'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[['SELL', 'WHEAT', 4]]` |
## Day 5

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 3], ['SELL', 'FERTILIZER', 3], ['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2], ['BUY_ANIMAL', 'COW', 1]]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 5 | `['PICKUP', 'COW', 1]` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 7 | `['WEST']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST'], ['WEST'], ['PASS']]` | `[['HIRE']]` |
| 8 | `['PLACE', 'COW', 1]` | `[['WEST'], ['EAST'], ['CARE'], ['FEED'], ['WEST'], ['WEST'], ['PASS'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 9 | `['EAST']` | `[['WEST'], ['DROP'], ['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['WEST'], ['PASS'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 1]]` |
| 10 | `['EAST']` | `[['WEST'], ['PASS'], ['SOUTH'], ['COLLECT_FERTILIZER'], ['NORTH'], ['WEST'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 11 | `['PICKUP', 'WHEAT', 2]` | `[['NORTH'], ['PASS'], ['SOUTH'], ['EAST'], ['NORTH'], ['NORTH'], ['PASS'], ['PASS']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 12 | `['WEST']` | `[['NORTH'], ['PASS'], ['DROP'], ['SOUTH'], ['NORTH'], ['NORTH'], ['PASS'], ['PASS']]` | `[]` |
| 13 | `['WEST']` | `[['NORTH'], ['PASS'], ['PASS'], ['DROP'], ['WATER'], ['NORTH'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 14 | `['FEED']` | `[['WATER'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['WATER'], ['PASS'], ['PASS']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 15 | `['CARE']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 16 | `['EAST']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 17 | `['EAST']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 18 | `['DROP']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 19 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 20 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 21 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 22 | `['PASS']` | `[['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
| 23 | `['PASS']` | `[['DROP'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS'], ['PASS']]` | `[]` |
## Day 6

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 1], ['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 5 | `['PICKUP', 'WHEAT', 2]` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['WEST']]` | `[['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['HARVEST'], ['NORTH'], ['NORTH'], ['NORTH'], ['WEST']]` | `[['HIRE']]` |
| 7 | `['WEST']` | `[['WEST'], ['CARE'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[['HIRE']]` |
| 8 | `['FEED']` | `[['WEST'], ['COLLECT_FERTILIZER'], ['CARE'], ['FEED'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 9 | `['CARE']` | `[['WATER'], ['WEST'], ['COLLECT_FERTILIZER'], ['HARVEST'], ['WATER'], ['NORTH'], ['WEST'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 10 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['NORTH'], ['CARE'], ['WEST'], ['WATER'], ['WEST'], ['WEST']]` | `[]` |
| 11 | `['WEST']` | `[['WATER'], ['WEST'], ['NORTH'], ['COLLECT_FERTILIZER'], ['WATER'], ['WEST'], ['WATER'], ['WEST']]` | `[]` |
| 12 | `['NORTH']` | `[['NORTH'], ['NORTH'], ['WATER'], ['NORTH'], ['WEST'], ['WEST'], ['WEST'], ['NORTH']]` | `[]` |
| 13 | `['WATER']` | `[['WATER'], ['NORTH'], ['SOUTH'], ['NORTH'], ['WEST'], ['WEST'], ['WATER'], ['NORTH']]` | `[]` |
| 14 | `['EAST']` | `[['EAST'], ['NORTH'], ['SOUTH'], ['NORTH'], ['SOUTH'], ['NORTH'], ['PASS'], ['NORTH']]` | `[]` |
| 15 | `['EAST']` | `[['EAST'], ['WATER'], ['SOUTH'], ['WATER'], ['WATER'], ['NORTH'], ['PASS'], ['NORTH']]` | `[]` |
| 16 | `['EAST']` | `[['SOUTH'], ['HARVEST'], ['SOUTH'], ['EAST'], ['PASS'], ['WATER'], ['PASS'], ['WATER']]` | `[]` |
| 17 | `['SOUTH']` | `[['SOUTH'], ['EAST'], ['DROP'], ['SOUTH'], ['PASS'], ['HARVEST'], ['PASS'], ['HARVEST']]` | `[]` |
| 18 | `['DROP']` | `[['SOUTH'], ['EAST'], ['PASS'], ['SOUTH'], ['PASS'], ['EAST'], ['PASS'], ['EAST']]` | `[['SELL', 'FERTILIZER', 1], ['BUY_SEED', 'STRAWBERRY', 1]]` |
| 19 | `['PASS']` | `[['DROP'], ['EAST'], ['PASS'], ['SOUTH'], ['PASS'], ['WEST'], ['PASS'], ['EAST']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 20 | `['PASS']` | `[['PASS'], ['EAST'], ['PASS'], ['SOUTH'], ['PASS'], ['PLANT', 'STRAWBERRY'], ['PASS'], ['EAST']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 21 | `['PASS']` | `[['PASS'], ['SOUTH'], ['PASS'], ['DROP'], ['PASS'], ['WATER'], ['PASS'], ['SOUTH']]` | `[['BUY_ANIMAL', 'SHEEP', 1]]` |
| 22 | `['PASS']` | `[['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['EAST'], ['PASS'], ['SOUTH']]` | `[['SELL', 'WOOL', 6], ['SELL', 'FERTILIZER', 1]]` |
| 23 | `['PASS']` | `[['PASS'], ['SOUTH'], ['PASS'], ['PASS'], ['PASS'], ['EAST'], ['PASS'], ['SOUTH']]` | `[['BUY_ANIMAL', 'SHEEP', 2]]` |
## Day 7

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 8], ['SELL', 'WOOL', 6], ['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2], ['BUY_ANIMAL', 'SHEEP', 3]]` |
| 2 | `['CARE']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['DROP']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 5 | `['PICKUP', 'WHEAT', 2]` | `[['CARE'], ['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[['SELL', 'FERTILIZER', 1], ['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 6 | `['WEST']` | `[['COLLECT_FERTILIZER'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[['HIRE']]` |
| 7 | `['WEST']` | `[['NORTH'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST'], ['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[['HIRE']]` |
| 8 | `['FEED']` | `[['NORTH'], ['NORTH'], ['CARE'], ['FEED'], ['WEST'], ['WEST'], ['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[]` |
| 9 | `['CARE']` | `[['WATER'], ['NORTH'], ['COLLECT_FERTILIZER'], ['CARE'], ['WEST'], ['NORTH'], ['WEST'], ['WEST']]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 10 | `['COLLECT_FERTILIZER']` | `[['NORTH'], ['WATER'], ['WEST'], ['COLLECT_FERTILIZER'], ['WEST'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 11 | `['NORTH']` | `[['WATER'], ['WEST'], ['NORTH'], ['WEST'], ['NORTH'], ['NORTH'], ['WEST'], ['WEST']]` | `[]` |
| 12 | `['WATER']` | `[['WEST'], ['WATER'], ['WATER'], ['WEST'], ['BUILD_PASTURE'], ['NORTH'], ['NORTH'], ['WEST']]` | `[]` |
| 13 | `['NORTH']` | `[['WATER'], ['WEST'], ['WEST'], ['WATER'], ['PLACE', 'SHEEP', 1], ['NORTH'], ['NORTH'], ['NORTH']]` | `[]` |
| 14 | `['NORTH']` | `[['WEST'], ['WATER'], ['WEST'], ['EAST'], ['EAST'], ['BUILD_PASTURE'], ['NORTH'], ['NORTH']]` | `[]` |
| 15 | `['WATER']` | `[['WEST'], ['EAST'], ['SOUTH'], ['EAST'], ['EAST'], ['PLACE', 'SHEEP', 1], ['BUILD_PASTURE'], ['BUILD_PASTURE']]` | `[]` |
| 16 | `['EAST']` | `[['WEST'], ['EAST'], ['SOUTH'], ['EAST'], ['EAST'], ['EAST'], ['PLACE', 'SHEEP', 1], ['PLACE', 'SHEEP', 1]]` | `[]` |
| 17 | `['EAST']` | `[['SOUTH'], ['EAST'], ['SOUTH'], ['SOUTH'], ['EAST'], ['EAST'], ['EAST'], ['EAST']]` | `[]` |
| 18 | `['SOUTH']` | `[['SOUTH'], ['SOUTH'], ['WATER'], ['DROP'], ['SOUTH'], ['SOUTH'], ['EAST'], ['EAST']]` | `[]` |
| 19 | `['SOUTH']` | `[['SOUTH'], ['SOUTH'], ['EAST'], ['PASS'], ['PICKUP', 'WHEAT', 2], ['SOUTH'], ['EAST'], ['EAST']]` | `[['SELL', 'FERTILIZER', 1], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 20 | `['SOUTH']` | `[['SOUTH'], ['DROP'], ['EAST'], ['PASS'], ['WEST'], ['SOUTH'], ['SOUTH'], ['EAST']]` | `[]` |
| 21 | `['DROP']` | `[['WATER'], ['PASS'], ['EAST'], ['PASS'], ['WEST'], ['SOUTH'], ['SOUTH'], ['SOUTH']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 22 | `['PASS']` | `[['EAST'], ['PASS'], ['DROP'], ['PASS'], ['WEST'], ['PICKUP', 'WHEAT', 2], ['SOUTH'], ['SOUTH']]` | `[['SELL', 'FERTILIZER', 1]]` |
| 23 | `['PASS']` | `[['EAST'], ['PASS'], ['PASS'], ['PASS'], ['WEST'], ['WEST'], ['PICKUP', 'WHEAT', 2], ['PICKUP', 'WHEAT', 2]]` | `[['SELL', 'FERTILIZER', 1], ['BUY_PRODUCT', 'WHEAT', 2]]` |
## Day 8

| Hour | Farmer | Hands | Market |
|---:|---|---|---|
| 0 | `['PICKUP', 'WHEAT', 2]` | `[]` | `[['SELL', 'WHEAT', 4], ['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 1 | `['FEED']` | `[['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 2]]` |
| 2 | `['HARVEST']` | `[['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1]]` |
| 3 | `['DROP']` | `[['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE']]` |
| 4 | `['CARE']` | `[['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['SELL', 'MILK', 6], ['HIRE']]` |
| 5 | `['COLLECT_FERTILIZER']` | `[['HARVEST'], ['FEED'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['HIRE'], ['BUY_PRODUCT', 'WHEAT', 1], ['BUY_LAND']]` |
| 6 | `['DROP']` | `[['CARE'], ['CARE'], ['NORTH'], ['NORTH'], ['WEST'], ['PICKUP', 'SHEEP', 1]]` | `[['HIRE'], ['BUY_SEED', 'STRAWBERRY', 5]]` |
| 7 | `['PICKUP', 'SHEEP', 1]` | `[['COLLECT_FERTILIZER'], ['COLLECT_FERTILIZER'], ['FEED'], ['NORTH'], ['WEST'], ['EAST'], ['PICKUP', 'WHEAT', 2]]` | `[['SELL', 'FERTILIZER', 1], ['HIRE']]` |
| 8 | `['EAST']` | `[['WEST'], ['WEST'], ['CARE'], ['FEED'], ['WEST'], ['NORTH'], ['WEST'], ['PICKUP', 'WHEAT', 2]]` | `[['BUY_PRODUCT', 'WHEAT', 2]]` |
| 9 | `['NORTH']` | `[['WEST'], ['WEST'], ['COLLECT_FERTILIZER'], ['CARE'], ['FEED'], ['BUILD_PASTURE'], ['WEST'], ['WEST']]` | `[]` |
| 10 | `['BUILD_PASTURE']` | `[['NORTH'], ['NORTH'], ['NORTH'], ['COLLECT_FERTILIZER'], ['CARE'], ['PLACE', 'SHEEP', 1], ['WEST'], ['WEST']]` | `[]` |
| 11 | `['PLACE', 'SHEEP', 1]` | `[['NORTH'], ['NORTH'], ['WATER'], ['NORTH'], ['COLLECT_FERTILIZER'], ['PICKUP', 'WHEAT', 2], ['WEST'], ['WEST']]` | `[]` |
| 12 | `['SOUTH']` | `[['NORTH'], ['NORTH'], ['NORTH'], ['WATER'], ['NORTH'], ['FEED'], ['WEST'], ['WEST']]` | `[]` |
| 13 | `['PICKUP', 'WHEAT', 2]` | `[['FEED'], ['FEED'], ['WATER'], ['NORTH'], ['WATER'], ['CARE'], ['NORTH'], ['NORTH']]` | `[]` |
| 14 | `['NORTH']` | `[['CARE'], ['CARE'], ['WEST'], ['WATER'], ['NORTH'], ['EAST'], ['FEED'], ['NORTH']]` | `[]` |
| 15 | `['FEED']` | `[['COLLECT_FERTILIZER'], ['COLLECT_FERTILIZER'], ['WEST'], ['NORTH'], ['WATER'], ['PLANT', 'STRAWBERRY'], ['CARE'], ['NORTH']]` | `[]` |
| 16 | `['CARE']` | `[['SOUTH'], ['SOUTH'], ['WEST'], ['WATER'], ['WEST'], ['WATER'], ['COLLECT_FERTILIZER'], ['FEED']]` | `[]` |
| 17 | `['NORTH']` | `[['WATER'], ['WATER'], ['WEST'], ['WEST'], ['SOUTH'], ['NORTH'], ['SOUTH'], ['CARE']]` | `[]` |
| 18 | `['PLANT', 'STRAWBERRY']` | `[['WEST'], ['WEST'], ['WATER'], ['WEST'], ['WATER'], ['PLANT', 'STRAWBERRY'], ['WATER'], ['COLLECT_FERTILIZER']]` | `[]` |
| 19 | `['WATER']` | `[['SOUTH'], ['NORTH'], ['EAST'], ['PLANT', 'STRAWBERRY'], ['EAST'], ['WATER'], ['EAST'], ['EAST']]` | `[]` |
| 20 | `['SOUTH']` | `[['SOUTH'], ['PLANT', 'STRAWBERRY'], ['EAST'], ['WATER'], ['EAST'], ['WEST'], ['EAST'], ['EAST']]` | `[]` |
| 21 | `['SOUTH']` | `[['SOUTH'], ['WATER'], ['EAST'], ['EAST'], ['EAST'], ['SOUTH'], ['EAST'], ['EAST']]` | `[]` |
| 22 | `['DROP']` | `[['WATER'], ['EAST'], ['EAST'], ['EAST'], ['SOUTH'], ['DROP'], ['EAST'], ['EAST']]` | `[]` |
| 23 | `['PASS']` | `[['EAST'], ['EAST'], ['SOUTH'], ['EAST'], ['DROP'], ['PASS'], ['DROP'], ['SOUTH']]` | `[]` |