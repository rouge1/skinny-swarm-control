Review feedback on your UnitPool (it passed review; these are polish items). Fix them in
`swarm_control/sim/pool.py` only:

1. `step` runs 60x per second. Replace the boolean-mask gather/scatter with in-place ufuncs, e.g.
   `np.add(self.x, self.vx * dt, out=self.x, where=self.active)` (same for y), avoiding temporaries
   where you can.
2. `cull`: return 0 early without writing when nothing is outside the rectangle.
3. Coerce `capacity` to a plain `int` (after validating it), so `UnitPool(np.int64(4)).capacity` is an `int`.
4. `spawn_many` with `kind` outside the int8 range (-128..127) silently wraps; raise ValueError instead,
   before changing any state (same for `spawn`).
5. Remove the leftover `# noqa: F401  (for the implementation)` comment on the numpy import and add a short
   class docstring.

Keep everything else as is. Done when these pass:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_pool.py
    /data/python/learn/swarm-control/.venv/bin/ruff check .
