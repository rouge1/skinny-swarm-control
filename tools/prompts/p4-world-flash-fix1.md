Your phase 4 World entry won the bake-off (score 96/100). All 144 tests pass and ruff is clean. One low-severity
style nit was confirmed by consensus review, please fix it:

- swarm_control/sim/world.py (around line 126, in your upgrade-buy/price logic): the max level for each upgrade is
  currently inferred from `len(prices)` (the price tuple's length) instead of using the explicit
  `FIRE_RATE_MAX_LEVEL`, `MULTISHOT_MAX_LEVEL`, `SPEED_MAX_LEVEL` constants from config.py. Gate the "already at
  max level" / "no next price" logic on those MAX_LEVEL constants directly, so the two sources (price-tuple length
  and the MAX_LEVEL constant) can never diverge if either is edited independently later. Behavior must stay
  identical (they currently agree, so no test should change).

When done: /data/python/learn/swarm-control/.venv/bin/python -m pytest -q (expect 144 passed) and
    /data/python/learn/swarm-control/.venv/bin/ruff check .
Report what you changed.
