Review feedback on waves.py (swarm_control/sim/waves.py). Fix all of these; edit only that file. Do not list or read
anything outside the working directory.

Game facts for balancing: field 540x960; the launcher at y=900 fires ~8 agents/s straight up at 260 px/s; an agent
reaching y<=110 does 1 damage to the fortress; agents and bugs annihilate 1:1 on contact (bug "hp" and "kind" have
no effect); a bug reaching y>=940 does 1 damage to the player's base; bugs spawn at y=120-150.

1. [high] Levels are trivially easy with no ramp: in level 3 two gates are stacked in one column, so one shot
   becomes 42 agents, and standing still while firing wins L3 in 3.2 s, faster than L1. Rebalance:
   - never stack two gates so one column passes both; spread gates across different x ranges and give them vx
     so the player has to aim;
   - raise enemy_hp substantially and ramp it, roughly 60 / 200 / 450;
   - make winning take a real fight: the first bugs should reach the player's area before the fortress can fall.
2. [high] You cannot lose: total bugs 20/45/80 against player_hp 100. Make the waves a real threat: lower
   player_hp (e.g. 20 / 25 / 30) and/or raise bug counts, bring the first wave in within ~2-3 s, and ramp speed
   and count per level so a player who never fires loses every level.
3. [medium] NaN/inf slip through validation: a wave with t=NaN stalls the spawner forever; x/spread=inf crash
   rng.uniform; enemy_hp=nan validates as fine. Add one helper that accepts only finite real numbers (not bool)
   and use it for every numeric field in validate_level and in WaveSpawner.
4. [low] WaveSpawner keeps references to the caller's wave dicts; deep-copy (or extract fields) in __init__.
5. [low] count=10**12 raises MemoryError: draw only min(count, free slots) random positions.
6. [low] Accept numpy scalars: use numbers.Integral / numbers.Real (excluding bool), and let get_level accept
   numpy integers.
7. [low] Reject gates agents can never trigger: require 110 < y, y + h < 880 (the muzzle), and h >= 4.4
   (one tick of agent travel).
8. [low] Drop the "hp" and "kind" keys from the levels (they have no effect).

Done when these pass:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_waves.py tests/test_pool.py
    /data/python/learn/swarm-control/.venv/bin/ruff check .
The orchestrator will also check that each level is winnable by a sweeping player and lost by an idle one.
