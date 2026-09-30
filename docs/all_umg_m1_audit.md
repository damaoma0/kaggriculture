# All UMG animal tapes and mgt_m1 loss audit

Coverage: 584/584 existing UMG library tapes (submissions 56266758 and 56266899); 89/89 losses in 305 completed public mgt_m1 games (submission 56395605), as listed on 2026-09-22. 58 losses faced opponents rated below 2500 at match time. The submission API listing is the observable history, not a guarantee of unbounded archived history.

## Animal dates

Zero-based game days. Successful purchases count units; feed termination is the day after the final successful feed, including animals surviving the season. Dates alone do not prove deliberate retirement. Purchases cannot be uniquely matched to individual stored animals, so purchase events and animal placement/feed histories are separate.

| Species | Placed | Purchased D18+ | Latest purchase | Latest placement | Final feed D27 | Final feed D28 |
|---|---:|---:|---:|---:|---:|---:|---:|
| COW | 4253 | 2 | 18 | 23 | 2748 | 1027 |
| SHEEP | 3978 | 29 | 20 | 26 | 600 | 1034 |
| GOOSE | 2251 | 0 | 13 | 19 | 268 | 1929 |

Fed through D29, with termination unobserved: COW 2, SHEEP 4, GOOSE 2. Those termination cells are blank, not an asserted D30 stop.

## Loss mechanisms

Both seats are replayed using recorded actions, the official engine, and the recorded shop schedule. Both final cash results and revenue/spend ledgers must match. Every product revenue gap is exactly decomposed into quantity and realized-price components: ΔQ × mean(P) + ΔP × mean(Q). These are descriptive accounting components, not profits achievable by changing one crop. If one seat sells zero, its comparison price is set to the other seat’s realized average, allocating the gap to quantity.

A high-price production shortfall screen requires at least 11 fewer produced units, a quantity-component deficit over 1000, and either player’s realized average at least the product’s base price. A low-price production screen requires at least 20 units and at least half our harvested output harvested while the marginal quote was ≤25% of base. Wheat and fertilizer are excluded from these opportunity screens because they are inputs/byproducts. Low sales are measured separately at each actual execution price.

Direct cash gaps subtract product purchases, seeds and the associated animal purchases from revenue. Hired labor and land stay in a separate shared-cost bucket. These accounting buckets sum exactly to the cash margin; wheat feed cost stays in wheat and fertilizer input cost stays in fertilizer, so they are not stand-alone enterprise profits. This avoids misclassifying large wheat buy/resell turnover as farm underproduction.

### All losses

89 audited; 73 meet a high-price production-shortfall screen; 30 meet a low-price production screen (categories overlap).

| Product | Direct cash gap | Revenue gap | Quantity component | Price component | Biggest deficit in games | High-price shortfalls | Low-price production games |
|---|---:|---:|---:|---:|---:|---:|---:|
| CARROT | -8114 | -14934 | -27065 | 12131 | 5 | 37 | 0 |
| TOMATO | 368989 | 410939 | 417039 | -6100 | 2 | 5 | 0 |
| STRAWBERRY | -381637 | -415937 | -347027 | -68910 | 27 | 32 | 7 |
| MELON | 68952 | 79672 | 144177 | -64505 | 0 | 0 | 0 |
| EGG | 176543 | 209843 | 207285 | 2558 | 1 | 3 | 0 |
| MILK | -210041 | -212841 | -240557 | 27716 | 13 | 11 | 20 |
| WOOL | -503831 | -537831 | -522897 | -14934 | 40 | 9 | 6 |
| WHEAT | 142822 | -1237646 | -1169284 | -68362 | 1 | 0 | 0 |
| FERTILIZER | -229814 | -376459 | -544180 | 167721 | 0 | 0 | 0 |
### Opponent below 2500

58 audited; 44 meet a high-price production-shortfall screen; 19 meet a low-price production screen (categories overlap).

| Product | Direct cash gap | Revenue gap | Quantity component | Price component | Biggest deficit in games | High-price shortfalls | Low-price production games |
|---|---:|---:|---:|---:|---:|---:|---:|
| CARROT | 10994 | 7434 | 656 | 6778 | 3 | 21 | 0 |
| TOMATO | 244454 | 272354 | 276947 | -4593 | 1 | 4 | 0 |
| STRAWBERRY | -288859 | -311959 | -257181 | -54778 | 19 | 20 | 4 |
| MELON | 43269 | 50869 | 100642 | -49773 | 0 | 0 | 0 |
| EGG | 118066 | 139366 | 137464 | 1902 | 0 | 1 | 0 |
| MILK | -122149 | -122549 | -142918 | 20369 | 7 | 8 | 13 |
| WOOL | -305606 | -327106 | -335291 | 8185 | 27 | 5 | 4 |
| WHEAT | 107100 | -583943 | -550360 | -33583 | 1 | 0 | 0 |
| FERTILIZER | -150067 | -234991 | -356238 | 121247 | 0 | 0 | 0 |

## Execution and routing

Archived m1 decisions were regenerated on reconstructed observations in 89 losing games; 0 games have any mismatch with recorded actions. This separates a reproducible policy decision from a crash/fallback explanation. Detailed final-donor shop counts and last-switch dates are retained for each loss. Shop mismatch alone does not prove that a feasible better tape existed.

Across the 89 losses, 0 HIRE requests within the engine's order limit failed. Thus these losses do not reproduce the earlier missing-worker hiring bug.

Of 58 traced losses below 2500, 58 finish on a donor with different final shop counts; 54 last switched by D15. This is consistent with a production plan that becomes hard to adapt as more demand is revealed, but a loss-only cohort does not establish that mismatch predicts losing. Below 2500, m1 spent 15671 more on hired labor in aggregate, and spent more in 42 games.

## Concrete failure examples

- **111262874, seed 1190520739, Raagav & Pieter (2025.6): margin -12585.** STRAWBERRY: direct cash gap -18565 (revenue -19465); sold 141 vs 248, average 192.6 vs 188.0. WOOL: 151/283 units harvested at ≤25% of base. Last donor switch D6; differences: ICE_CREAM_SHOP 3 actual / 1 donor, YARN_STORE 1 actual / 2 donor, BRUNCH_SPOT 1 actual / 0 donor, BAKERY 0 actual / 1 donor, FARMERS_MARKET 0 actual / 1 donor. Shared labor/land contribution to margin: 60.
- **111642811, seed 194533913, Timbydude (2421.2): margin -12412.** STRAWBERRY: direct cash gap -9094 (revenue -9594); sold 201 vs 247, average 217.5 vs 215.8. Last donor switch D12; differences: ICE_CREAM_SHOP 2 actual / 1 donor, FARMERS_MARKET 1 actual / 0 donor, PET_CAFE 1 actual / 3 donor, BRUNCH_SPOT 2 actual / 1 donor, PIZZA_SHOP 0 actual / 1 donor. Shared labor/land contribution to margin: -1249.
- **111487784, seed 546154931, sdy623 (2318.7): margin -12258.** WOOL: direct cash gap -9015 (revenue -9515); sold 74 vs 131, average 165.3 vs 166.0. Last donor switch D24; differences: PET_CAFE 1 actual / 0 donor, BAKERY 0 actual / 1 donor. Shared labor/land contribution to margin: 6212.
- **111678108, seed 1464643264, Abish Pius (2427.7): margin -10424.** WOOL: direct cash gap -11201 (revenue -11701); sold 90 vs 155, average 177.2 vs 178.4. MILK: 69/116 units harvested at ≤25% of base. Last donor switch D12; differences: BRUNCH_SPOT 1 actual / 3 donor, FARMERS_MARKET 1 actual / 2 donor, ICE_CREAM_SHOP 1 actual / 0 donor, YARN_STORE 2 actual / 0 donor, BAKERY 1 actual / 0 donor, SMOOTHIE_SHOP 0 actual / 1 donor. Shared labor/land contribution to margin: -1901.
- **111743130, seed 1439155522, RngRng (2408.0): margin -9081.** WOOL: direct cash gap -11773 (revenue -12273); sold 71 vs 155, average 142.2 vs 144.3. Last donor switch D12; differences: PET_CAFE 3 actual / 1 donor, SMOOTHIE_SHOP 1 actual / 2 donor, YARN_STORE 1 actual / 0 donor, PIZZA_SHOP 0 actual / 1 donor, FARMERS_MARKET 0 actual / 1 donor. Shared labor/land contribution to margin: -1846.
- **112109339, seed 1625931664, Snorlax (2633.8): margin -25467.** WOOL: direct cash gap -12797 (revenue -16297); sold 516 vs 558, average 154.1 vs 171.7. MILK: 44/88 units harvested at ≤25% of base. Last donor switch D9; differences: YARN_STORE 3 actual / 4 donor, BAKERY 2 actual / 1 donor, FARMERS_MARKET 2 actual / 0 donor, BRUNCH_SPOT 0 actual / 2 donor. Shared labor/land contribution to margin: -12363.

The largest overall loss, 112109339, combines a wool revenue deficit with 12,363 extra hired-labor expense (16,668 versus 4,305); its 25 units of discarded wool and lower average wool price also matter. This is not explained by underproduction alone. In 111743130, the opponent bought thousands of wheat units for resale: comparing gross wheat revenue would give a misleading main cause; subtracting purchases exposes wool as the largest direct cash deficit.

## Implications for best-fit tape selection

1. Rank feasible plans by their incremental product quantities over the remaining season, using expected residual demand after both players’ supply and the game’s nonlinear price curve. Final shop-count distance and raw sale volume are incomplete proxies.
2. Give wool and strawberry output gaps priority when observed prices/demand support them. Their lead times mean a late need may require earlier cohort choices; do not assume a new sheep or strawberry root can fix the last few days.
3. Penalize maintaining milk/wool capacity whose next yields will arrive into a glut, but include fertilizer byproducts, wheat feed and shared labor before retiring animals. A positive low-price sale from already-produced stock is not itself a mistake.
4. Preserve animal age, crop maturity, inventory and feasible staffing when switching. A hindsight closer donor can fail if its expected mature herd or roots do not exist on our board.
5. Validate any proposed change on both wins and losses in fresh games against responsive opponents. The observed gaps establish what differed; they do not establish the gain from a replacement policy.

## Every loss, prioritized below 2500

| Episode / seed | Opponent / match rating | Cash margin | Main product gap | Other high-price shortfalls | Low-price production |
|---|---|---:|---|---|---|
| 111262874 / 1190520739 | Raagav & Pieter / 2025.6 | -12585 | STRAWBERRY: direct cash gap -18565 (revenue -19465); sold 141 vs 248, average 192.6 vs 188.0 | STRAWBERRY, MILK | WOOL |
| 111642811 / 194533913 | Timbydude / 2421.2 | -12412 | STRAWBERRY: direct cash gap -9094 (revenue -9594); sold 201 vs 247, average 217.5 vs 215.8 | STRAWBERRY | — |
| 111487784 / 546154931 | sdy623 / 2318.7 | -12258 | WOOL: direct cash gap -9015 (revenue -9515); sold 74 vs 131, average 165.3 vs 166.0 | CARROT, TOMATO | — |
| 111269605 / 181383218 | Suvrat Rai / 2209.8 | -11836 | WOOL: direct cash gap -12840 (revenue -13840); sold 80 vs 155, average 179.2 vs 181.8 | — | — |
| 111461796 / 383076948 | songling / 2432.0 | -10962 | WOOL: direct cash gap -6793 (revenue -7293); sold 103 vs 139, average 192.4 vs 195.1 | STRAWBERRY, MILK | — |
| 111627822 / 2083486147 | Oliver #2 / 2494.9 | -10846 | MILK: direct cash gap -6936 (revenue -7336); sold 139 vs 191, average 142.4 vs 142.0 | CARROT, WOOL | — |
| 111626554 / 735892656 | yuya / 2457.5 | -10620 | WOOL: direct cash gap -9588 (revenue -10588); sold 49 vs 129, average 122.1 vs 128.5 | — | — |
| 111678108 / 1464643264 | Abish Pius / 2427.7 | -10424 | WOOL: direct cash gap -11201 (revenue -11701); sold 90 vs 155, average 177.2 vs 178.4 | — | MILK |
| 111591604 / 1575888792 | XW / 2374.9 | -10408 | STRAWBERRY: direct cash gap -6885 (revenue -7385); sold 192 vs 246, average 62.7 vs 79.0 | CARROT | STRAWBERRY, MILK |
| 111337545 / 907382831 | Ali Eren Konak / 2292.9 | -10336 | WOOL: direct cash gap -13262 (revenue -13762); sold 58 vs 133, average 174.3 vs 179.5 | — | — |
| 111416249 / 347972805 | RS Turley / 2398.1 | -9726 | WOOL: direct cash gap -13613 (revenue -15113); sold 83 vs 152, average 158.5 vs 186.0 | TOMATO, MILK | — |
| 111324547 / 1920501641 | quantara.cv / 2368.6 | -9571 | WOOL: direct cash gap -9572 (revenue -10072); sold 78 vs 133, average 174.5 vs 178.1 | — | — |
| 111743130 / 1439155522 | RngRng / 2408.0 | -9081 | WOOL: direct cash gap -11773 (revenue -12273); sold 71 vs 155, average 142.2 vs 144.3 | CARROT | — |
| 111677758 / 1446781133 | shakedamo0w0 / 2464.0 | -8915 | WOOL: direct cash gap -11245 (revenue -11745); sold 84 vs 155, average 154.9 vs 159.7 | — | — |
| 111284610 / 598286766 | Николай Леухин / 2261.1 | -8732 | WOOL: direct cash gap -9993 (revenue -10993); sold 227 vs 273, average 237.1 vs 237.4 | WOOL | — |
| 111261836 / 132822741 | Cow Boy / 1973.7 | -8636 | WOOL: direct cash gap -7828 (revenue -8328); sold 67 vs 121, average 146.3 vs 149.8 | MILK | STRAWBERRY |
| 111479294 / 67224748 | ss / 2452.8 | -8562 | MILK: direct cash gap -7468 (revenue -7868); sold 160 vs 231, average 122.6 vs 119.0 | STRAWBERRY | — |
| 111345443 / 1323312411 | Kitsune0o / 2330.7 | -7922 | STRAWBERRY: direct cash gap -16757 (revenue -17657); sold 134 vs 245, average 176.4 vs 168.6 | STRAWBERRY | — |
| 111624954 / 1131357071 | forwardidear / 2386.0 | -7691 | WOOL: direct cash gap -9291 (revenue -9791); sold 97 vs 155, average 176.7 vs 173.8 | — | MILK |
| 111552384 / 1530258508 | Bala Baskar / 2330.1 | -7456 | WOOL: direct cash gap -8944 (revenue -9944); sold 65 vs 136, average 138.2 vs 139.1 | CARROT | — |
| 111290865 / 1227665987 | Fabian Friedland / 2256.9 | -6075 | WOOL: direct cash gap -8342 (revenue -8842); sold 90 vs 155, average 144.9 vs 141.2 | CARROT | STRAWBERRY, MILK |
| 111287532 / 1574435924 | Yan #2 / 2273.5 | -6063 | STRAWBERRY: direct cash gap -20542 (revenue -21942); sold 105 vs 238, average 177.0 vs 170.3 | STRAWBERRY | MILK |
| 111473690 / 1380437241 | Anubisyy / 2416.4 | -5981 | WOOL: direct cash gap -9288 (revenue -10288); sold 65 vs 138, average 140.7 vs 140.8 | CARROT | — |
| 111404055 / 1765149422 | elegantangel (628700) / 2389.0 | -5401 | CARROT: direct cash gap -5066 (revenue -5706); sold 31 vs 120, average 60.1 vs 63.1 | CARROT | — |
| 111462655 / 231716414 | Harshith revuru / 2433.8 | -5277 | WOOL: direct cash gap -12289 (revenue -13289); sold 75 vs 155, average 169.9 vs 167.9 | — | MILK |
| 111261724 / 1197981059 | Yusuraume / 2141.9 | -4863 | STRAWBERRY: direct cash gap -19655 (revenue -21055); sold 119 vs 245, average 180.9 vs 173.8 | STRAWBERRY | — |
| 111629568 / 1982779455 | ertu / 2460.7 | -4766 | MILK: direct cash gap -6195 (revenue -6595); sold 138 vs 191, average 141.3 vs 136.6 | CARROT | — |
| 111469243 / 558751393 | Lan_Sky / 2407.7 | -4726 | STRAWBERRY: direct cash gap -8343 (revenue -9843); sold 109 vs 247, average 117.4 vs 91.7 | MILK | — |
| 111604858 / 628833808 | Nat Bel ML Fun / 2368.9 | -4581 | WOOL: direct cash gap -6642 (revenue -7142); sold 71 vs 121, average 153.4 vs 149.1 | CARROT, TOMATO | — |
| 111519320 / 500932251 | YKuma / 2359.7 | -4511 | MILK: direct cash gap -5174 (revenue -5574); sold 131 vs 176, average 114.9 vs 117.2 | TOMATO, STRAWBERRY | — |
| 111321984 / 1454415506 | Rudra / 2291.9 | -4155 | WOOL: direct cash gap -3571 (revenue -4571); sold 51 vs 110, average 105.5 vs 90.4 | CARROT | — |
| 111293097 / 1399358392 | Inzilbêth / 2353.7 | -4141 | STRAWBERRY: direct cash gap -6396 (revenue -6696); sold 205 vs 247, average 169.0 vs 167.4 | CARROT, STRAWBERRY, EGG | — |
| 111331242 / 1991587061 | kaggle Osaka / 2366.6 | -4082 | WHEAT: direct cash gap -7152 (revenue -6276); sold 256 vs 394, average 43.3 vs 44.1 | CARROT | MILK |
| 111256107 / 619121910 | Shymohn / 1936.9 | -4000 | WOOL: direct cash gap -12163 (revenue -13663); sold 325 vs 386, average 229.7 vs 228.8 | STRAWBERRY, WOOL | MILK |
| 111756959 / 538329368 | No Name #2 / 2450.3 | -3683 | MILK: direct cash gap -5905 (revenue -5905); sold 184 vs 266, average 139.6 vs 118.8 | — | WOOL |
| 111668844 / 397426808 | 我的AI是豆包 / 2451.5 | -3659 | WOOL: direct cash gap -7408 (revenue -8408); sold 74 vs 139, average 149.6 vs 140.1 | — | STRAWBERRY |
| 111783885 / 1170180768 | Surya Bhattiprol / 2445.8 | -3381 | STRAWBERRY: direct cash gap -3166 (revenue -3366); sold 232 vs 247, average 188.5 vs 190.7 | STRAWBERRY | — |
| 111300962 / 1778347199 | kuengo / 2214.2 | -2889 | STRAWBERRY: direct cash gap -6976 (revenue -8476); sold 99 vs 251, average 94.9 vs 71.2 | MILK | WOOL |
| 111296485 / 1209339495 | Huifeng Li / 2338.0 | -2876 | MILK: direct cash gap -9099 (revenue -9099); sold 157 vs 245, average 109.6 vs 107.4 | — | — |
| 111569954 / 1087273234 | Hamachi / 2368.9 | -2529 | STRAWBERRY: direct cash gap -4060 (revenue -4360); sold 223 vs 247, average 95.9 vs 104.2 | — | — |
| 111571471 / 952320047 | qr farm / 2415.8 | -2520 | STRAWBERRY: direct cash gap -7698 (revenue -8598); sold 184 vs 247, average 158.6 vs 152.9 | STRAWBERRY, MILK | — |
| 111494799 / 981842211 | Mohammad Alnajdawi / 2413.5 | -2501 | STRAWBERRY: direct cash gap -5752 (revenue -6052); sold 205 vs 251, average 172.9 vs 165.3 | CARROT, STRAWBERRY, WOOL | — |
| 111253835 / 1352513297 | Grzegorz Sionkowski / 1904.0 | -2446 | WOOL: direct cash gap -6792 (revenue -7292); sold 71 vs 120, average 148.3 vs 148.5 | CARROT | — |
| 111525943 / 1294989734 | Crop It Like It's Hot / 2458.5 | -2204 | WOOL: direct cash gap -12527 (revenue -13527); sold 72 vs 152, average 167.1 vs 168.2 | CARROT | MILK |
| 111479555 / 113172614 | Jamie Nojek / 2397.3 | -1326 | WOOL: direct cash gap -3917 (revenue -4417); sold 59 vs 116, average 91.2 vs 84.4 | — | — |
| 111407510 / 1960861537 | Illia Dolenko / 2413.1 | -1156 | STRAWBERRY: direct cash gap -6442 (revenue -6942); sold 209 vs 247, average 178.4 vs 179.1 | STRAWBERRY, MILK | — |
| 111272956 / 657908329 | kowalskii / 2020.6 | -1109 | STRAWBERRY: direct cash gap -18871 (revenue -19971); sold 119 vs 242, average 181.4 vs 171.7 | STRAWBERRY | MILK |
| 111303211 / 1205478984 | edchax / 2271.2 | -1068 | STRAWBERRY: direct cash gap -14008 (revenue -15308); sold 126 vs 249, average 141.9 vs 133.3 | STRAWBERRY | WOOL |
| 111634164 / 1549410819 | Vitalie Cervinschi / 2390.7 | -757 | STRAWBERRY: direct cash gap -5949 (revenue -6349); sold 207 vs 247, average 124.8 vs 130.3 | STRAWBERRY | MILK |
| 111294229 / 124067286 | Kota Iizuka / 2274.6 | -752 | CARROT: direct cash gap -2732 (revenue -3152); sold 13 vs 94, average 36.8 vs 38.6 | CARROT | — |
| 111259496 / 1557597548 | Fedor / 2015.0 | -735 | MILK: direct cash gap -9144 (revenue -9944); sold 177 vs 256, average 142.8 vs 137.6 | CARROT | — |
| 111748490 / 1972016121 | tmcoder / 2468.4 | -575 | WOOL: direct cash gap -10602 (revenue -11102); sold 94 vs 155, average 176.4 vs 178.6 | CARROT | MILK |
| 111572050 / 136451532 | Inzilbêth / 2461.3 | -478 | WOOL: direct cash gap -5016 (revenue -5516); sold 229 vs 278, average 170.2 vs 160.1 | STRAWBERRY | — |
| 111291994 / 837282603 | Yam / 2337.7 | -472 | CARROT: direct cash gap -2726 (revenue -3086); sold 28 vs 94, average 45.1 vs 46.3 | CARROT | — |
| 111735916 / 1858857654 | Stanley Honkpehedji / 2370.0 | -468 | WOOL: direct cash gap -12286 (revenue -13786); sold 337 vs 410, average 222.9 vs 216.8 | WOOL | — |
| 111679209 / 1882883657 | Meng Di / 2491.4 | -456 | TOMATO: direct cash gap -4211 (revenue -4111); sold 88 vs 80, average 271.6 vs 350.1 | CARROT, STRAWBERRY | — |
| 111279666 / 387539145 | Eesh saxena / 2240.8 | -422 | STRAWBERRY: direct cash gap -12742 (revenue -13742); sold 141 vs 247, average 156.4 vs 144.9 | STRAWBERRY | MILK |
| 111385999 / 420733060 | We Forgot To Water / 2362.0 | -406 | STRAWBERRY: direct cash gap -8949 (revenue -9849); sold 182 vs 245, average 104.3 vs 117.7 | — | — |
| 112109339 / 1625931664 | Snorlax / 2633.8 | -25467 | WOOL: direct cash gap -12797 (revenue -16297); sold 516 vs 558, average 154.1 vs 171.7 | CARROT | MILK |
| 111971159 / 581039879 | Batuhan Ustun / 2613.6 | -18122 | WOOL: direct cash gap -39015 (revenue -43515); sold 146 vs 331, average 227.4 vs 231.7 | WOOL | — |
| 111681732 / 218620836 | l1aF / 2540.9 | -15335 | STRAWBERRY: direct cash gap -9195 (revenue -9895); sold 193 vs 247, average 195.2 vs 192.6 | STRAWBERRY | — |
| 112014484 / 1527325205 | TeamNexus / 2630.2 | -13191 | CARROT: direct cash gap -17661 (revenue -18661); sold 37 vs 201, average 120.6 vs 115.0 | CARROT | MILK |
| 112048711 / 1563692643 | TeamNexus / 2660.2 | -12595 | MILK: direct cash gap -13220 (revenue -13620); sold 110 vs 225, average 91.6 vs 105.3 | STRAWBERRY | — |
| 111918927 / 361899343 | Kucing Garong / 2510.3 | -12509 | STRAWBERRY: direct cash gap -9611 (revenue -10111); sold 192 vs 246, average 96.8 vs 116.7 | CARROT | MILK |
| 111998751 / 865062217 | Marti / 2614.6 | -12311 | WOOL: direct cash gap -21514 (revenue -24514); sold 206 vs 331, average 200.2 vs 198.6 | STRAWBERRY, WOOL | — |
| 111979020 / 2098326345 | nickyl / 2638.4 | -10263 | STRAWBERRY: direct cash gap -18355 (revenue -19355); sold 140 vs 245, average 196.6 vs 191.3 | STRAWBERRY | WOOL |
| 111817104 / 309746479 | Kenjo1209 / 2568.9 | -9781 | STRAWBERRY: direct cash gap -7258 (revenue -7658); sold 196 vs 249, average 156.3 vs 153.8 | CARROT, STRAWBERRY | — |
| 111926374 / 1852815200 | Yuan Weijun / 2662.2 | -9666 | WOOL: direct cash gap -9330 (revenue -9830); sold 75 vs 139, average 164.2 vs 159.3 | STRAWBERRY | — |
| 112016668 / 218365198 | MiMi / 2677.3 | -8412 | TOMATO: direct cash gap -10632 (revenue -10682); sold 64 vs 80, average 567.8 vs 587.7 | CARROT, TOMATO | — |
| 111916514 / 1580064094 | Yannik Schiffner / 2527.0 | -7004 | STRAWBERRY: direct cash gap -4227 (revenue -4327); sold 147 vs 182, average 139.1 vs 136.1 | CARROT, STRAWBERRY | — |
| 111751548 / 399325487 | Busya PRIME / 2555.8 | -6556 | MILK: direct cash gap -9731 (revenue -10131); sold 149 vs 245, average 120.0 vs 114.4 | CARROT | — |
| 111780110 / 1079538381 | keiz / 2542.7 | -6182 | CARROT: direct cash gap -10498 (revenue -12278); sold 197 vs 446, average 42.7 vs 46.4 | CARROT | — |
| 111792671 / 640896163 | Araik Tamazian / 2511.8 | -5818 | WOOL: direct cash gap -8469 (revenue -8969); sold 79 vs 131, average 175.6 vs 174.4 | CARROT | — |
| 112028389 / 1362717794 | Andrew Reed / 2565.9 | -5551 | WOOL: direct cash gap -11315 (revenue -11815); sold 205 vs 278, average 184.3 vs 178.4 | — | STRAWBERRY |
| 112099112 / 1055221699 | Satuker / 2620.4 | -5186 | STRAWBERRY: direct cash gap -8409 (revenue -9309); sold 141 vs 245, average 136.1 vs 116.3 | STRAWBERRY | — |
| 111978608 / 1139590499 | Hai Dang / 2666.1 | -5005 | WOOL: direct cash gap -12040 (revenue -13040); sold 67 vs 155, average 150.7 vs 149.3 | CARROT, MILK | — |
| 112010483 / 1838191280 | kyosan / 2637.7 | -4827 | WOOL: direct cash gap -7539 (revenue -8039); sold 83 vs 133, average 161.4 vs 161.2 | CARROT | — |
| 112086793 / 1869737788 | A. R. SEKKAT / 2688.3 | -4753 | MILK: direct cash gap -6196 (revenue -6596); sold 141 vs 192, average 157.9 vs 150.3 | CARROT | — |
| 112087027 / 1486037132 | lihaoruolhr / 2651.8 | -4732 | WOOL: direct cash gap -4557 (revenue -5057); sold 45 vs 99, average 111.8 vs 101.9 | STRAWBERRY | — |
| 111857175 / 763320241 | Omar Althobaiti / 2612.9 | -4658 | STRAWBERRY: direct cash gap -5560 (revenue -6060); sold 185 vs 246, average 56.6 vs 67.2 | CARROT | STRAWBERRY, MILK |
| 111610131 / 1825887801 | uki706 / 2568.7 | -3546 | WOOL: direct cash gap -7514 (revenue -8014); sold 70 vs 121, average 131.2 vs 142.1 | CARROT, EGG | MILK |
| 112039734 / 1473232749 | Ishan Karnick / 2616.9 | -3463 | WOOL: direct cash gap -7585 (revenue -8085); sold 104 vs 139, average 212.4 vs 217.1 | WOOL | — |
| 112006610 / 772632944 | Capitaalgain / 2718.2 | -3195 | MILK: direct cash gap -4675 (revenue -5075); sold 148 vs 191, average 170.5 vs 158.7 | CARROT, MILK | — |
| 111809584 / 1333139072 | lime0001 / 2523.5 | -3005 | MILK: direct cash gap -6241 (revenue -6641); sold 170 vs 242, average 96.2 vs 95.0 | CARROT | — |
| 111967793 / 1223149392 | Zalyaliev Marat / 2665.4 | -2224 | WOOL: direct cash gap -22061 (revenue -25061); sold 265 vs 386, average 217.2 vs 214.0 | WOOL | STRAWBERRY |
| 111712478 / 614504067 | 橋本真旺 / 2504.3 | -1732 | MILK: direct cash gap -5619 (revenue -6019); sold 121 vs 206, average 78.7 vs 75.4 | STRAWBERRY | — |
| 111871547 / 1477013077 | 吃白饭的大肥鱼 / 2616.8 | -372 | EGG: direct cash gap -3392 (revenue -4292); sold 0 vs 76, average n/a vs 56.5 | STRAWBERRY, EGG, MILK | WOOL |
| 111847995 / 223486659 | Chris Deotte / 2583.9 | -330 | WOOL: direct cash gap -5867 (revenue -5867); sold 173 vs 218, average 164.6 vs 157.5 | — | MILK |
| 111882524 / 1109651885 | 七月七月晴 忽然下起了大雪 不敢张开眼 希望是我的幻觉 / 2626.1 | -174 | STRAWBERRY: direct cash gap -8422 (revenue -9122); sold 194 vs 245, average 183.0 vs 182.1 | STRAWBERRY | MILK |

## Interpretation and limits

Do not replace every low-price sale with a skipped sale: selling already-produced stock still earns positive cash, and withholding it can increase the opponent’s prices. The production decision is whether to commit earlier land, seed, herd and labor to that product, conditional on expected demand and opponent supply. A price deficit can reflect production timing, delivery, market-order sequence or opponent sales; it is not automatically a sale-order bug.

Wheat sold may have been purchased and resold or consumed as feed. Fertilizer collected can be used rather than sold. The workbook therefore includes purchased, consumed, discarded and terminal inventory quantities, and reconciles quantities before interpreting a sales gap. Discarded means harvested/purchased stock lost from inventories, not unharvested potential yields. No-effect commands include harmless duplicate/guarded work, and do not by themselves establish the cash cost of execution failures.

Sources: public Kaggle episode replays and historical episode ratings; local official kaggriculture engine. Reproduction: `expand_umg_m1_fetch.py`, `extract_all_umg_animals.mjs`, `audit_all_m1_losses.py`, `summarize_all_umg_m1.mjs`. Detailed evidence: `results/fresh/all_umg_m1/`.
