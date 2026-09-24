Review feedback on your combat (swarm_control/sim/combat.py). Fix all of these; edit only that file.
New acceptance tests were added to tests/test_combat.py (dense stacks, gate-burst clumps, a dense box within one
60 Hz frame); they must pass.

1. [high] Dense stacks run one matching round per unit: every agent proposes to the same lowest-index bug, so
   only one pair matches per round (O(n^3) overall). Measured: 300v300 on one point 0.74 s; a 400v400 gate-burst
   clump 133 ms (8 frames). Fix:
   a) pre-match: units that share a grid cell of side <= radius are always in contact (cell diagonal
      r*sqrt(2) < 2r), so first pair agents and bugs within the same small cell by rank (sort by cell key, rank
      within cell, join on (cell, rank)) and despawn those pairs in one vectorised step;
   b) in the remaining rounds, have each agent propose to a random (or rank-offset) contacting bug instead of
      the minimum index, so the number of rounds stays small.
2. [high] Stacked clusters build an n_blue x n_red candidate edge list (4000v4000 on one point: 16M edges,
   2.9 GB). The same-cell pre-matching removes full cells before any edges are built.
3. [medium] Per round, drop matched units with boolean masks indexed by unit number instead of re-running
   lexsort and np.isin over the whole edge list.
4. [low] Units with absurd coordinates (|x| or |y| > ~1e12, or non-finite) must be left out of collision, not
   raise ValueError mid-game.
5. [low] Cell keys alias across rows at the top/bottom edge; skip neighbour queries outside the grid or pad it.
6. [low] Tidy the red-dedup indexing and trim input guards to what the contract needs.

Done when these pass:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_combat.py tests/test_pool.py
    /data/python/learn/swarm-control/.venv/bin/ruff check .
