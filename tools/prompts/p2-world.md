Task: implement the real `World` in `swarm_control/sim/world.py` (phase 2: launcher, firing, agent flight).

Read `AGENTS.md` first and follow it. Then read `CONTRACTS.md`, the contract in the module docstring
of `swarm_control/sim/world.py`, `swarm_control/config.py`, `swarm_control/protocol.py`, and the
finished `UnitPool` in `swarm_control/sim/pool.py` (use it, do not change it).

Edit only `swarm_control/sim/world.py`. Keep the public interface exactly as documented.

Behaviour:
- `blue` and `red` are `UnitPool`s sized `BLUE_CAPACITY` / `RED_CAPACITY`. `red` stays empty in this phase.
- Launcher: starts at FIELD_W / 2, moves at LAUNCHER_SPEED px/s while exactly one of left/right is held,
  clamped to [LAUNCHER_MARGIN, FIELD_W - LAUNCHER_MARGIN].
- Firing: while fire is held, one agent every FIRE_INTERVAL seconds; the first shot happens on the first
  step with fire held. Agents spawn at (launcher_x, LAUNCHER_Y - MUZZLE_OFFSET), vx 0, vy -AGENT_SPEED, kind 0.
- Each step: move the launcher, fire, `blue.step(dt)`, then free agents that left the field
  (outside x in [0, FIELD_W], y in [-UNIT_RADIUS, FIELD_H]).
- `step` does nothing unless status == "playing"; `tick` counts steps taken while playing.
- Actions: "pause" (playing -> paused), "resume" (paused -> playing), "restart" (fresh world, same seed and
  level). Anything else is ignored.
- `snapshot()` returns a valid protocol "state": packed blue/red via `protocol.pack_units` (active units
  only), empty gates, bases at 100/100, hud counts from the pools, level 1, tokens 0.
- Deterministic: the same seed and inputs give identical snapshots. Use `np.random.default_rng(seed)`
  for any randomness you add.
- Vectorised: no Python loops over units.

Done when these succeed with no failures or errors:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_world.py tests/test_protocol.py tests/test_pool.py
    /data/python/learn/swarm-control/.venv/bin/ruff check .
