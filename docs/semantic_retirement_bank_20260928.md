# Current-bank retirement identity prototype

V8 live03 retires the cow at tile50 onD15 after placing it onD9. It has four
banked care units and its first output would appearD17. Seven alternative cows
each have two banked units. All eight have seven remaining production dates, so
the existing compiler selects tile50 by its distance tie-break. Its pasture is
used for a tomato plantedD18. These facts identify a choice worth testing, not a
proof that keeping the young cow improves profit: route distance and replacement
production also matter.

The new optional tile setting `retire_policy: current_bank` preserves the exact
requested retirement count. When remaining production counts tie, it retires
the animal with the smaller current public care bank before applying the old
distance/birth/tile tie-break. It applies only to today's observed state; it does
not reuse a stale bank for modeled future retirements. Already committed
retirements remain committed. If only a preproduction animal is available, it
can still be selected. There is no blanket survival or first-yield veto.

The option is OFF in the reference and every currently frozen candidate,
including V11. Five pure tests pass: current-bank identity choice with unchanged
semantic counts, continued retirement without alternatives, unchanged future
ranking, equal-bank fallback, and preservation of prior retirement intent.
Gameplay profit and the eight-world screen have not been measured for it.

Native retirement and low-price disposal remain legitimate. In particular,
late sheep departures in live06 cannot all be labeled harmful merely because
held wool disappears. Output, available delivery/storage and realized prices
must be checked together.
