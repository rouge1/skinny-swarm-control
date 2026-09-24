Review feedback on your World (swarm_control/sim/world.py). Fix all of these; edit only that file.

1. [medium] Fire cooldown drops the overshoot: after a shot you set the timer to FIRE_INTERVAL, so at dt=1/60
   shots land every 8 ticks (-11% rate) and the rate depends on dt. Use an accumulator
   (`timer += FIRE_INTERVAL` per shot) and fire every shot that is due within one step (spawn_many).
2. [medium] Releasing fire resets the timer to 0, so tapping fire every tick gives 3.6x the fire rate. While fire
   is released, count the timer down to a floor of 0 instead; the first shot after being idle stays immediate.
3. [medium] `restart` re-runs __init__ and drops the held keys; the client only sends input on change, so keys
   held through R are ignored. Keep the current input across restart.
4. [low] Validate dt at the top of step: ignore it unless it is finite and >= 0 (NaN dt corrupts the world).
5. [low] Restart must reuse the same UnitPool objects (call pool.clear()), not build new ones, and must start
   from a deep copy of the original level dict. Add an explicit `_reset()`.
6. [low] Split step into `_move_launcher`, `_fire`, `_move_units`, `_cull` methods (phase 3 adds gates,
   collisions and bases between them), and keep enemy/player hp, level and tokens as attributes the snapshot reads.
7. [low] Update the module docstring: it still calls the file a stub. Describe phase 2 behaviour and the step order.

Done when these pass:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_world.py tests/test_protocol.py tests/test_pool.py
    /data/python/learn/swarm-control/.venv/bin/ruff check .
