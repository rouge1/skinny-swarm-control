Task: wire phase 3 into the World in `swarm_control/sim/world.py`: levels, gates, bug waves, combat, bases,
win/lose.

Read `AGENTS.md` first and follow it. Do not list or read anything outside the working directory. Then read:
`CONTRACTS.md`; the module docstrings of `swarm_control/sim/gates.py`, `combat.py` and `waves.py` (finished,
reviewed modules; use them, do not change them); `swarm_control/config.py`; `swarm_control/protocol.py`; your own
phase 2 `World`; and the new acceptance tests in `tests/test_world_p3.py` (and the existing `tests/test_world.py`,
which must keep passing).

Edit only `swarm_control/sim/world.py`. Requirements (the tests are the precise spec):
- `World(seed=0, level=None)`: `level=None` means an empty sandbox level (no gates or waves, enemy and player hp
  100, reward 0). Keep a deep copy of the level as a template; the caller's dict must never change.
- `new_game(seed=0) -> World`: a world on level 1 (`waves.get_level(1)`), exported from world.py.
- New attributes: `level` (the live copy), `enemy_hp`, `enemy_hp_max`, `player_hp`, `player_hp_max`, `tokens`,
  and the elapsed level time.
- A uint32 `passed` array (one entry per blue slot) for `gates.apply_gates`; zero the entry for every agent the
  launcher spawns, so reused slots never inherit gate marks.
- Step order while playing: move launcher, fire, move gates, move both pools, apply gates, spawn due waves,
  collide, hit bases (subtract damage, never below 0), cull units outside the field, advance tick and time,
  then check: enemy_hp == 0 -> "won" (add the level's reward to tokens once), player_hp == 0 -> "lost".
- After "won" or "lost" nothing moves until restart. Restart restores the level from the template (hp, gates,
  waves, rng) but keeps tokens and the held keys, and reuses the same pools.
- `snapshot()` reports real gates (x, y, w, h, op, value, label), both unit lists, both bases and the hud
  (red_count, level id, tokens).
- Deterministic for a given seed; vectorised; the performance test must pass.

Done when these pass with no failures or errors:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest
    /data/python/learn/swarm-control/.venv/bin/ruff check .
Note: tests/test_world_p3.py includes "a sweeping player wins every level" and "an idle player loses every
level". If one of these fails because of level balance rather than your code, say so in your summary; do not
change waves.py.
