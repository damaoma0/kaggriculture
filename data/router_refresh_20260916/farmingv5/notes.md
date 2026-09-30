# Farming Score V5


## 1. Same-day weed recovery

Suppose one worker's intended suffix before dawn is

$$
(P, W, a_1, a_2, \ldots, a_k, \operatorname{PASS}),
$$

where $P$ plants a crop and $W$ waters it. If the target tile is unexpectedly a
weed, replacing $P$ by `DIG` and discarding the seed loses the crop. When a later
idle slot exists in the same day, the safe transformed suffix is

$$
(\operatorname{DIG}, P, W, a_1, a_2, \ldots, a_k).
$$

The inserted command creates a FIFO delay of exactly one action. The original
`PASS` absorbs that delay, so the worker returns to the parent tape before dawn.
The branch is enabled only when the next intended command is `WATER`, the seed
batch is funded, every shifted command is valid in the observed state, and the
idle slot is known to occur before the day boundary. Otherwise the parent action
is returned unchanged.


## 2. Confirmed-mirror sale ordering

For product $i$, let $I_i$ be public market inventory and let $p_i(I_i)$ be the
official rounded price curve. A sale permutation $\pi$ has modeled revenue

$$
R(\pi)=\sum_i\sum_{u=0}^{q_i-1}
p_i\!\left(I_i+u+c_i(\pi,u)\right),
$$

where $q_i$ is saleable stock and $c_i(\pi,u)$ counts rival units processed before
that unit under the simultaneous queue. The rival model uses the same queue and
the same saleable-stock vector; it is activated only after the inherited public
cash-response probe has confirmed mirror-like behavior.

At the final turn of a 72-turn block, deterministic pair swaps seek

$$
\pi^{\star}=\arg\max_{\pi\in\mathcal{N}}R(\pi),
$$

where $\mathcal{N}$ is the bounded sequence of improving pair swaps. A reorder is
accepted only if the modeled gain is at least 25 coins, public farm similarity is
at least $0.90$, and our cash lead is at most 500 coins. The multiset of market
orders is invariant:

$$
\operatorname{multiset}(A_{\text{new}})
=\operatorname{multiset}(A_{\text{parent}}).
$$

Thus this layer changes neither sold quantities nor future market inventory; it
changes only which product receives the earlier quote in a confirmed close race.


## 3. Shop-conditioned livestock substitution

Let animal $a$ produce good $g(a)$, with first productive day $f_a$, production
interval $d_a$, purchase cost $C_a$, and daily feed burden $F_a$. A compact
remaining-horizon value proxy is

$$
V_a(t)=\sum_{\tau=t}^{29}
\mathbf{1}\!\left[\tau\ge f_a\ \land\
(\tau-f_a)\bmod d_a=0\right]
y_a\,p_{g(a)}(\tau)-C_a-F_a.
$$

The examined loss opened both available shops as `BAKERY` or `BRUNCH_SPOT`, so
eggs had two delivery outlets while milk had none. In precisely that regime,
the two-animal day-6 cow order is changed to geese. This is a substitution, not
an expansion: the quantity, two pickup actions, two structure actions, two
placement actions, and subsequent generic `FEED`/`CARE`/`HARVEST` tape remain
the same. Geese also cost less and produce daily, reducing capital lock-up while
aligning output with observed demand.

Execution is transactional. The purchase must appear as two geese in the next
observation before any physical command is changed. Each later mutation is
licensed by current inventory and tile state:

$$
\texttt{COW in hand}\rightarrow\texttt{GOOSE in hand},\qquad
\texttt{PASTURE}\rightarrow\texttt{COOP},\qquad
\texttt{PLACE COW}\rightarrow\texttt{PLACE GOOSE}.
$$

## 4. Exact dawn-overflow recovery

Let $L_j=(x_{j,1},x_{j,2},\ldots)$ be worker $j$'s inventory in true insertion
order after the current field actions. The engine's dawn deposit stream is

$$
S=L_0\mathbin{\Vert}L_1\mathbin{\Vert}\cdots\mathbin{\Vert}L_m.
$$

If the post-market shed has $r$ free slots, the discarded stream is the suffix
$D=S[r:]$. A sale vector $q$ is accepted only when it consists of a prefix of
$D$, every sold unit already exists in the shed, and exact simulation proves

$$
\operatorname{Deposit}(\operatorname{Sell}(W,q),S)
=\operatorname{Deposit}(W,S).
$$

Thus the complete next-day shed vector is invariant, while otherwise destroyed
units become current cash. Replays alphabetize dictionary keys, so their visible
order is not a valid deposit order. V44 instead reconstructs each $L_j$ across
consecutive observations. Since one unit executes one action per turn, at most
one new item kind can enter one worker's inventory in a callback. Any ambiguous
transition disables the branch. The expected shed vector is checked in the next
observation; a failed contract disables further overflow changes for that game.

## 5. Safety envelope

The added policy is deliberately sparse.

- Crop recovery must resynchronize within the current day.
- Market adaptation is all-SELL only; buys, hires, land, seeds, and animals are
  never reordered.
- Livestock substitution requires two observed egg shops, no milk shop, exactly
  one two-cow order, and no unrelated goose stock.
- Overflow recovery preserves the full next-day shed vector, requires at least
  25 coins of visible quote exposure, and never changes field actions.
- All four branches use only the current observation and persistent local state.
- Any unsupported configuration, invalid command, nonconsecutive callback, or
  exception returns the parent decision.
- The existing terminal physical-delivery planner remains authoritative.

The replay audit identifies opportunities, but it is not a full counterfactual
game engine: changed actions can change later observations. Accordingly, the
submission claims bounded mechanism-level improvements rather than guaranteed
scores on the supplied matches.


## 6. Standalone agent source


## 7. Source and entry-point verification


## 8. Deterministic submission archive


## 9. Interpretation

The backbone remains a deterministic portfolio of farm routes with public-shop
routing, market reservation, input protection, physical-state checks, and final
liquidation. The new crop branch converts one recoverable obstruction into a
finite queue-shift problem. The new market branch converts a confirmed mirror
collision into a small discrete optimization problem. Both additions are
state-verified and abstain outside their proof envelope. The livestock branch
adds a third bounded transformation: it preserves the proven labor skeleton but
maps two production slots to the commodity demanded by both observed shops.
Finally, the insertion ledger turns V43's warehouse idea into an exact stream
problem: only a discarded prefix that reproduces the complete baseline shed
vector is monetized. No production route is changed by this fourth layer.
