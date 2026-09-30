## Mathematical rule

For product $g$, let $q_g$ be the parent's executable sale, $d_g$ the demand
from revealed shops, and $p_g(I)$ the market price at inventory $I$. The
maximum delayed quantity is

$$
r_g=\min\{8,q_g,d_g,H\},
$$

where $H$ is capacity headroom after all inherited sales. A delay is allowed
only when

$$
p_g(I-d_g)-p_g(I)\ge 3
$$

and

$$
r_g\left[p_g(I-d_g)-p_g(I)\right]\ge 10.
$$

The quantity is released at the next shop-settlement interval. The controller
never delays wheat or fertilizer, never invents a sale, and never truncates a
different market order to settle its debt.


## Guarded changes

- A due quantity cannot be delayed again on its release turn.
- Capacity uses post-parent-sale stock rather than total product availability.
- If all ten market slots are occupied, unsettled debt remains pending instead
  of deleting another order or being silently forgotten.
- Partial stock settles partially and retries the remainder.
- Unknown configuration or shop schema returns the parent action unchanged.
- The parent's effective cash-sale queue closure runs once after the overlay.
