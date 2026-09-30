<div class="sc-hero iaf">
  <div class="sc-hero-grid">
    <div>
      <div class="sc-kicker">Kaggriculture 1.32.7 · public replays · fixed routes vs flexible play</div>
      <h1>❄️🔥 A Song of Ice and Fire</h1>
      <p><b>Fixed vs Flexible: what a top agent repeats in every game, and where it reacts.</b></p>
      <p><b>Ice</b> is what the agent does identically in every game. <b>Fire</b> is where its games part ways because the board, the shops or the opponent are different. The first graph overlays 461 winning games of Majkel1337, command by command, and shows both at once.</p>
    </div>
  </div>
</div>


`ARTICLE` renders the interactive graphs and needs the companion Dataset with the three dashboard files. `SUBMISSION` renders nothing and only builds the agent archive, so the commit is fast. The agent is the last cell of the notebook in both modes.


## 1. Ice and fire in one picture: Majkel1337, command by command

Majkel1337 sits at the top of the ladder. The graph below takes **461 of their winning games**, all played by one agent version, so the code is the same in every game. It lays the games over each other and asks, at each of the 720 steps and for every command that any game submitted: how many of the 461 games submitted it as well?

- A command that **every** game submits at that step is **ice**: a fixed part of the agent. Ice sits below the line, in blue.
- A command that only **some** games submit is **fire**: the agent reacted to something in that game. Fire stacks above the line and runs from red (one game) through orange and yellow to green (all but a few games).

A step is one turn, a day is 24 steps, a game is 30 days. A **command** is a class plus a good: `PICKUP:WHEAT`, `SELL:WOOL`, `BUY_SEED:WHEAT`. Move directions are merged into a single `MOVE`. A **command-unit** is one command at one step, for example `PICKUP:WHEAT` at step 144. The farmer, each hand and each market order can contribute commands; a game either submits a command-unit or it does not.

Two things to try first. Click the box **26/461** at the bottom of the fork tree and watch the fire above the line shrink and the ice below it grow. Then switch *Movement* and *Idle* off in the category row: what is left is the part of the agent that makes decisions.


### How to read it

- **The four tiles.** Games in the current selection, steps, command-units, and the *average agreement* over all command-units (30.6% for the full set).
- **The fork tree.** Every box is a group of games. `279/461` is the number of games in the group; `+301` is how many more ice cells the group has than the full set (the full set has 906). The label on a branch is the step where the group splits, with the day next to it. The colour deepens with the gain. **Click any box** and every chart below is recomputed for that group only.
- **The heat-grid.** The horizontal axis is the game from step 0 to step 719, with a marker every five days. In every column, the cells above the line are the command-units that some games submit, sorted so that the most agreed-upon sits closest to the line. Colours: red 0%+, orange 25%+, yellow 50%+, olive 70%+, light green 85%+, green 95%+, dark green "only one game differs". The blue cells below the line are the ice. **Gold triangles** are land purchases; a bigger triangle means more games bought land at that step. *Whole game* fits all 720 steps into the frame, *Zoom in* draws 4 pixels per step.
- **The category row.** Each category shows the share of its command-units that are ice. Untick a category to remove it from every chart; open *commands* to switch single commands.
- **Step detail.** Click any cell or triangle. The table lists every command-unit at that step: the command, its category, how many games submit it and the agreement in percent.
- **Average agreement by day.** One bar per day, in the same colours.

**What the data says.**

- Of the 11,828 command-units, **906 (7.7%) are ice**. 572 of those 906 ice cells (63%) belong to the Movement category: the farm's walking pattern is the fixed part. Growing is 3% ice and Market sell is 1%: what gets planted, and what gets sold and when, is where the games differ.
- **Day 0 is a tape.** 87 of the 99 command-units of the first day are ice; the average agreement is 93%. From day 1 to day 6 it falls to 35–48%, and from day 7 to the end of the game it stays between 25% and 32%.
- **The first land purchase is scheduled.** 459 of the 461 games buy their first land at step 150. Later purchases pile up at steps 218, 220 and 222 (141, 409 and 392 purchases). Together they hold 98% of all land purchases in the graph.
- **The tree is worth reading from the top.** The root splits at step 229 (day 9.54) into 279 and 182 games. Knowing which side a game is on lifts the ice in the 279-game group from 906 to 1207 cells. The best leaf, 26 games, agrees on 2041 cells, 2.3 times the full set.
- **What separates the two sides of the root.** In a follow-up check on the same 461 games, one farm-state variable, the number of hands carrying an animal at step 229, separates them for 400 games of 461 (86.8%). The state of the farm is where the fire of this agent comes from.

### How to apply it

1. **Blue cells are tape.** Click a step in the ice zone and read the table: those commands are safe to hardcode for that step. Long runs of ice, like most of day 0, are the scripted opening.
2. **Dark green cells are almost tape.** One game in 461 differs. They are candidates for the script with a guard around them.
3. **A tall red-orange column is a decision.** Click the step, read which commands compete, then open the fork tree and look for the split whose step is close to yours. The branches show which games go which way, and the state variable that separates them is the rule that the flexible layer needs.
4. **The gain number is a price list.** `+301` says that knowing this branch gives 301 more command-units that can be written down in advance. A branch with a large gain and a large game count is a good place to write a conditional script.
5. **Run the same picture on your own agent.** Play it on many seeds, cross-match its commands the same way, and compare the ice with this graph. Ice where Majkel1337 has fire is a rigid stretch; fire where Majkel1337 has ice is flexibility that is not needed.

### The math

<div class="sc-math">

$$A_g(t)=\{\ell\}\ \text{ the set of commands game } g \text{ submits at step } t,\qquad n_\ell(t)=\big|\{g:\ \ell\in A_g(t)\}\big|$$

<div class="meaning"><b>Meaning.</b> A command $\ell$ is a class and a good; move directions are merged. Several hands can submit the same command in one step, and it still counts once for that game. $n_\ell(t)$ is the number of games behind one command-unit $(t,\ell)$, and it is what the tooltip shows as `279/461`.</div>
</div>

<div class="sc-math">

$$a_\ell(t)=\frac{n_\ell(t)-1}{N-1},\qquad \text{ice: } n_\ell(t)=N,\qquad \bar a=\frac{1}{|\mathcal U|}\sum_{(t,\ell)\in\mathcal U}a_\ell(t)$$

<div class="meaning"><b>Meaning.</b> $a$ is the agreement drawn on the colour scale: 0 when only one game submits the command and 1 when all $N$ games do. $\mathcal U$ is the set of all command-units that appear at least once, and $\bar a$ is the average agreement in the tile, 30.6% here. Worked example: 391 of 461 games submit `MOVE` at step 144, so $a=390/460=0.85$, and the detail table prints 85%.</div>
</div>

<div class="sc-math">

$$U(S)=\big|\{(t,\ell):\ n^{(S)}_\ell(t)=|S|\}\big|,\qquad U(\text{all})=906$$

<div class="meaning"><b>Meaning.</b> $U(S)$ is the number of ice cells inside a group of games $S$: the command-units that every game of the group submits. Every box of the fork tree shows $U(S)-U(\text{all})$. A small group has more ice, because agreeing is easier with fewer games, so the tree weighs the gain by the size of the group.</div>
</div>

<div class="sc-math">

$$\text{split}(P)=\arg\max_{(t,\,C)}\ |C|\,\big(U(C)-U(P)\big)+|P\setminus C|\,\big(U(P\setminus C)-U(P)\big),\qquad 2\le|C|<|P|$$

<div class="meaning"><b>Meaning.</b> For a group $P$ the tree tries every step $t$ and every set $C$ of games that submitted the identical bundle at that step (the same farmer command, hand commands and market orders). $C$ and everybody else in $P$ become the two children, and the split with the largest size-weighted gain wins. The recursion stops at depth 4 or when the group has fewer than 4 games. Worked example for the root: the children have 279 and 182 games and ice of 1207 and 975 cells, so the score is $279\cdot301+182\cdot69=96537$. Without the weights, peeling off two nearly identical games would always win, because two games agree on thousands of cells.</div>
</div>

**Limits of this reading.** Only winning games are used. The 461 games come from one agent version, chosen because an earlier mix of two versions blended two different land-buying behaviours. Ice means "every one of these games did it", so it depends on the group size: a group of 26 agrees more easily than a group of 461, and that is why the gains in the tree are weighted. A command-unit ignores quantities and move directions.


<div style="background:#171a14;color:#ffffff;border:4px solid #d1a256;border-radius:14px;padding:20px 24px;margin:20px 0">
  <div style="color:#d1a256;font-size:22px;font-weight:800;letter-spacing:.04em">BEFORE YOU CONTINUE</div>
  <p><b>If this work is useful, please upvote the notebook, download the companion dataset, and leave a concrete idea or counterexample in the comments.</b></p>
  <p>I can run the same diagnostics on public agents and public replays. Add a public notebook or episode link in the comments if you want its failure points mapped.</p>
  <p style="margin-bottom:12px;"><b>Related parts of this research:</b></p>
  <a href="https://www.kaggle.com/code/leoprovorov/kaggricult-man-reverse-engineering-part-1" target="_blank" style="display:inline-block;padding:10px 16px;margin:0 8px 12px 0;background:#20BEFF;color:#000000;font-weight:700;text-decoration:none;border-radius:6px;">→ Part 1: General Overview &amp; Analysis</a>
  <a href="https://www.kaggle.com/code/leoprovorov/god-s-mode-hacked-stores/notebook?scriptVersionId=349839124" target="_blank" style="display:inline-block;padding:10px 16px;margin:0 8px 12px 0;background:#20BEFF;color:#000000;font-weight:700;text-decoration:none;border-radius:6px;">→ Part 2: Hacking the Store</a>
  <p style="margin-bottom:0"><b>This is Part 3.</b> It combines an article, an interactive research instrument and a reproducible agent build. The analysis cells are not required to run the submitted agent.</p>
</div>


# Part two: the same question for eleven top teams

Sections 2 to 4 ask the question of section 1 for every team of the top of the ladder, with the strictest possible test: a whole turn counts as one bundle, and two games agree at a step only when their bundles are identical.


## 2. Where do the winning games of a team stop being identical?

Take one player and every game that player won. Line the games up step by step and ask, at each step, how many of them are doing the same thing. Where nearly all of them do, that stretch is a script. Where every game does its own thing, the player is reacting to the board, the shops, the market or the opponent.

Terms used in both dashboards of this part. A game has 720 steps: 24 steps per day, 30 days. The eight shops open one at a time at steps 72, 144, 216, 288, 360, 432, 504 and 576, on the same schedule in every game. A **turn bundle** is everything a player submits in one step: the farmer's command, every hand's command and every market order. Two bundles count as the same when they have the same number of hands and contain the same kinds of commands on the same goods. Move directions and quantities are ignored, because the board layout differs between games and quantities vary between games that follow the same plan.

This chart compares whole bundles, the strictest possible test: one different hand command makes the whole step count as different. That is why Majkel1337 already shows divergence in the first steps here, while the picture in section 1, which compares single commands, keeps 87 of 99 command-units of day 0 as ice. Pick a player in the row above the charts, then click THIRD FARM CLUB and Majkel1337 in turn and compare the first 150 steps.


### How to read the charts

- **Action divergence by step.** The share of the player's winning games that are *not* submitting the majority bundle at this step. Near 0 means almost every game does the same thing; near 1 means almost no two games agree. Dashed vertical lines are shop openings; the shaded band spans this player's earliest to latest first land purchase.
- **Distinct lines in play.** How many different bundles are on the board at this step. 1 means one script; a number close to the game count means every game is on its own line.
- **How that count is made up.** The same distinct lines, sized: the five biggest groups in colour and everything else in grey. It tells "one big group and stragglers" apart from "five competing groups of similar size".
- **Commands common to every single game.** How many individual commands appear in literally every game at this step, counted per game and not per worker. Hover to see which ones. This is the closest thing to a guaranteed backbone.
- **The biggest single pattern.** The largest group of games that submitted an identical bundle at one step, taken only from steps where that group is at most 60% of the games, so a near-unanimous accident cannot win.

**What the data says.** Between step 0 and step 72 the mean divergence is **0.004** for THIRD FARM CLUB and **0.424** for Majkel1337. Between step 72 and step 144 it is **0.007** and **0.651**. THIRD FARM CLUB's winning games are one script for the first six days; on average 42% of Majkel1337's games are off the majority bundle before the first shop opens.

### How to apply it

1. **A flat stretch near 0 is safe to hardcode.** A recorded tape reproduces it. The length of the flat stretch is how far a script can run before it has to decide anything.
2. **Where the curve lifts off, ask what changed at that step.** A dashed line right there means public information arrived (a shop opened), so the fork can be a lookup keyed on that information. No dashed line means something private to the game changed (the board, prices, the opponent's moves), so the fork needs logic that reads the state.
3. **Plot your own agent the same way.** Run it on many seeds and feed its bundles through the same chart. Flat where the top players' curve lifts means the agent is too rigid there; lifting where theirs is flat means it spends flexibility it does not need.

### The math

<div class="sc-math">

$$f_g(t)=\Big(\operatorname{op}(\text{farmer}),\ n_{\text{hands}},\ \text{sorted}\{\operatorname{op}(h)\}_{h},\ \{\operatorname{op}(m)\}_{m}\Big),\qquad \operatorname{op}=(\text{class},\ \text{good})$$

<div class="meaning"><b>Meaning.</b> The bundle of game $g$ at step $t$. The class of a command is its name, with NORTH, SOUTH, EAST and WEST merged into one MOVE class; the good is the crop, animal or product it names (PLANT MELON differs from PLANT WHEAT). The hands' commands are compared as a sorted list and the market orders as a set. Quantities are dropped.</div>
</div>

<div class="sc-math">

$$D(t)=1-\frac{\max_{c}\,n_c(t)}{N(t)},\qquad K(t)=\big|\{f_g(t)\}_{g=1}^{N(t)}\big|,\qquad n_c(t)=\big|\{g:\ f_g(t)=c\}\big|$$

<div class="meaning"><b>Meaning.</b> $N(t)$ is the number of games that have a step $t$. $D$ is the divergence and $K$ the number of distinct lines. Worked example: five games at one step, three with bundle $X$, one with $Y$, one with $Z$. Then $\max_c n_c=3$, so $D=1-3/5=0.4$, $K=3$, and the stacked chart draws bars of size $3,1,1$ plus an empty rest.</div>
</div>

<div class="sc-math">

$$C(t)=\Big|\bigcap_{g=1}^{N(t)}A_g(t)\Big|,\qquad \bar A(t)=\frac1{N(t)}\sum_{g=1}^{N(t)}\big|A_g(t)\big|$$

<div class="meaning"><b>Meaning.</b> $A_g(t)$ is the set of individual commands (class, good) that game $g$ submits at step $t$: the farmer's, each hand's and each market order, every distinct one once. $C(t)$ is how many of them all games share; $\bar A(t)$ is the average size of a game's set, drawn as context so that "2 shared" can be read against "7 in total".</div>
</div>


## 3. Do the shops decide the fork? 64 shop worlds

Shops are the only public information that arrives on a fixed schedule. The first two shops that open, in order, define a **world**: 8 × 8 = 64 of them. If the shops decide how a game goes, games in the same world should follow a more similar line than games in different worlds.


### How to read it

- The **grid** has the first shop in the rows and the second in the columns. The number in a cell is how many of the player's winning games landed in that world; brighter blue means more games, and a cell without fill means none.
- **Click a cell.** The three charts under the grid are the charts from section 2, recomputed for only the games in that world.
- **Which worlds are similar enough to pool together.** For every pair of worlds, the table gives the step up to which their majority routes agree ("matches up to"), the share of steps where they agree over the whole game, and the number of games behind each world.

**What the data says.** A world holds at most 8 games here. The longest shared opening in Majkel1337's table is PET_CAFE then FARMERS_MARKET (3 games) against PET_CAFE then YARN_STORE (6 games): they agree up to step 145, and over the whole game only 22.5%. With samples that small, a long shared prefix is a lead to check with more games and not a result.

### How to apply it

1. **Count the tapes you need.** If two worlds share an opening to step $L$, one tape can play to step $L$ and then split. If every world parts ways early, each world needs its own tape from the start.
2. **Spend the games where the hypothesis is weak.** The cells with 1 or 2 games say which worlds need more replays before a tape for them is trustworthy.
3. **Check the fork against the shop pair.** A world-specific chart that is flat where the population chart rises says the shops explain that stretch; one that rises anyway says something else does.

### The math

<div class="sc-math">

$$W=(s_1,s_2),\quad s_1,s_2\in\{8\ \text{shops}\},\quad |\{W\}|=64,\qquad r_W(t)=\arg\max_{c}\,n^{(W)}_c(t)$$

<div class="meaning"><b>Meaning.</b> Every world has its own majority route $r_W$, computed from the games in that world only.</div>
</div>

<div class="sc-math">

$$S(A,B)=\frac{\big|\{t:\ r_A(t)=r_B(t)\}\big|}{\big|\{t:\ \text{both have data}\}\big|},\qquad L(A,B)=\max\Big\{T:\ \tfrac1T\sum_{t<T}\mathbf 1\big[r_A(t)\neq r_B(t)\big]\le 0.10\Big\}$$

<div class="meaning"><b>Meaning.</b> $S$ is the whole-game similarity. $L$ is the longest prefix over which at most 10% of the steps disagree, which is the number that matters for sharing a tape. Two worlds can share a 300-step opening and still score about 42% on $S$ because they part ways afterwards; that is why both numbers are shown.</div>
</div>


## 4. Ice and fire, team by team

The dashboards above show one player at a time. This chart puts all eleven teams on one axis and reduces each of them to one number: the first step at which a quarter of that team's winning games stop doing what most of them do.


### How to read it

Each bar runs from step 0 to the first step at which the divergence exceeds 0.25. The dashed lines are the openings of shops 1, 2 and 3. Long blue bars are long scripts; short orange bars are teams whose games part ways almost at once. Hover a bar for the 10%, 25% and 50% steps, and the number of games.

**What the data says.** feel the agi (151), AI是我的豆包 (146) and THIRD FARM CLUB (145) part ways within 7 steps of the second shop opening at step 144. Majkel1337 (4), SpaTaro (2) and M &amp; M &amp; P &amp; Q (1) part ways within the first four steps. The ranking by this number is not a ranking by strength: M &amp; M &amp; P &amp; Q, the shortest script here, has the highest average winning score in the sample.

### How to apply it

Use the bar as the boundary between the two halves of an agent. Before it, a tape. After it, or at the first shop-explained fork, a router and rules. It also says how much the tape can vary: a team whose bar ends at step 145 can be copied step by step for six days, while a team whose bar ends at step 4 has no script to copy.

### The math

<div class="sc-math">

$$p_q=\min\{t:\ D(t)>q\},\qquad q\in\{0.10,\ 0.25,\ 0.50\}$$

<div class="meaning"><b>Meaning.</b> $p_{0.25}$ is the bar. $p_{0.10}$ and $p_{0.50}$ show how sharp the parting is: for feel the agi, $p_{0.10}=6$ but $p_{0.25}=151$, which means a few games deviate early and the majority stays on the script until step 151.</div>
</div>

**Limits of this reading.** Only winning games are used, so a pattern that exists only in losses is invisible. The sample is public replays of eleven teams, between 48 and 234 wins each; Majkel1337 appears here with 234 wins of several agent versions and in section 1 with 461 wins of one version. The thresholds (10%, 25% and 50% for the parting) are choices, and the fingerprint ignores quantities and move directions, so two games with the same bundles can still differ in how much they buy or where they walk.


## 5. Putting the map to work

| Stretch | How to spot it | How to build it | Example in this notebook |
|---|---|---|---|
| **Fixed** | Blue cells in the heat-grid; divergence near 0 | A recorded tape | Day 0 of Majkel1337; THIRD FARM CLUB, steps 0 to 144 |
| **Conditional** | A fork right after a shop opening (a dashed line); a fork whose branches a public variable separates | A lookup keyed on the revealed shops | The agent below: 15 shop pairs pick 11 plans at step 144 |
| **Flexible** | Tall red-orange columns; divergence rising with no shop line; forks separated by a farm-state variable | Rules that read the live state: prices, board, hands, opponent | Majkel1337 from day 1 onwards |

The graphs say where each stretch starts and ends for a given player. Which flexible rule wins is decided by the games against real opponents.


> **Version update.** The last cell now submits **MarketShock-M1-WR1K**: MarketShock-M1 with one audited day-21 local watering repair and exact parent pass-through everywhere else. The original analysis below is unchanged.

## 6. The agent in the last cell

The submitted agent is the frozen Seven-Turn Rescue Wide Search bundle. It is the fixed side of this picture: one shared opener until step 144 (day 6), then a route chosen from the first two shops (15 named shop pairs select 11 plans: the earlier yarn-market route and ten newer continuations; every other pair keeps plan 0), then final liquidation from step 648 (day 27). A bounded terminal planner works on the last seven callbacks, steps 712 to 718. Part 1 maps the route table of the same agent family against real replays.

<div class="sc-note gold"><b>Credits and licence.</b> The router and its route data (<code>router_parent.py</code>, <code>actions.json</code>) are unchanged public work by Yusuke Hayashi (<code>yhay81/shop-router-0909</code>, version 3), which credits aurax7's Reactive Router for sale timing and shed projection. The planner lineage builds on Thomas Tschinkel's public state router (<a href="https://www.kaggle.com/code/thomastschinkel/kaggriculture-93-8-win-rate-public-state-router?scriptVersionId=347936183" target="_blank">Kaggriculture: 93.8% Win Rate Public State Router</a>, Apache-2.0). <code>unit_model.py</code> holds unit-action and crop-decay definitions extracted from Kaggle's <code>kaggle-environments</code> 1.32.7 (Apache-2.0). Local changes are the adapter (<code>main.py</code>, <code>policy.py</code>) and the bounded terminal planner. The Apache-2.0 text and the full notice ship inside the submission archive as <code>LICENSE.txt</code> and <code>NOTICE.txt</code>. No endorsement by the original authors is implied.</div>


## Continue the experiment

Upvote if you want the full toolkit and more replay studies published. Put public notebook links, episode links, and concrete mechanism ideas in the comments. For collaboration, contact me on Kaggle or [LinkedIn](https://rs.linkedin.com/in/aleksei-provorov-832050308).


## Build the exact agent

The hidden cell below is the last cell of the notebook. It writes `/kaggle/working/submission.tar.gz` from a hash-checked payload in both modes. Choose that file on the Output tab of the saved version to submit it.
