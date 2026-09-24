Task: implement phase 4 (campaign progression and upgrades) in the Swarm Control World.

Read AGENTS.md first and follow it. Do not list or read anything outside the working directory.
Read CONTRACTS.md (the "Phase 4" section), swarm_control/config.py (phase 4 constants), swarm_control/protocol.py
(ACTIONS, validate_state), swarm_control/sim/world.py, swarm_control/sim/waves.py (LEVELS, get_level), and the
acceptance tests tests/test_progression.py and tests/test_protocol.py. The tests are the spec: do not edit any test.

Edit only:
- swarm_control/sim/world.py: the "next" and "buy_*" actions, upgrade state that survives restart/next/load_level,
  the upgrade effects (fire interval, multishot fan-out, launcher speed), and the new hud fields in snapshot()
  (has_next, upgrades, prices, level_name). Read every constant from config.py; no magic numbers. Update the
  module docstring.
- swarm_control/sim/waves.py: ONLY the "reward" values in LEVELS, so that level 1 pays >= 20 and each level buys
  roughly one or two upgrades. Nothing else in waves.py.

Keep performance: the fire/multishot path must stay vectorised (spawn_many), and test_step_performance_under_load
must still pass.

Done when all of these pass:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest
    /data/python/learn/swarm-control/.venv/bin/ruff check .

SPEC:
# Phase 4 spec: campaign progression and upgrades

Goal: after winning a level the player spends tokens on upgrades, then continues to the next level.
Everything happens in one browser session (no save file in this phase).

## Actions (client -> server, protocol "action")
Add to protocol.ACTIONS:
- "next": when status == "won" and another level exists, load the next level (World.load_level); tokens and
  upgrades carry over. Ignored otherwise.
- "buy_fire_rate", "buy_multishot", "buy_speed": buy one level of that upgrade. Only allowed while status == "won"
  (the between-levels shop) and only if tokens >= price and the upgrade is below its max level. Otherwise ignored.
- "restart" keeps working as today (replays the current level; tokens and upgrades are kept).

## Upgrades (all in config.py as constants)
| key | effect per level | max level | price for next level (tokens) |
|---|---|---|---|
| fire_rate | fire interval x 0.85 per level | 4 | 20, 40, 80, 160 |
| multishot | +1 agent per shot, fanned out 12 px apart, centred on the launcher | 2 | 30, 90 |
| speed | launcher speed x 1.25 per level | 3 | 15, 30, 60 |
Upgrades persist for the rest of the World's life (across restart, next and load_level).

## Campaign end
When the last level is won, status stays "won" and "next" does nothing; the snapshot says there is no next level.

## Snapshot additions (protocol "state" -> "hud"), validated by protocol.validate_state
- "has_next": bool (a next level exists)
- "upgrades": {"fire_rate": int, "multishot": int, "speed": int} (current levels)
- "prices": {"fire_rate": int | None, "multishot": int | None, "speed": int | None} (None when maxed)
- "level_name": str

## Level rewards
Rewards must let a player afford at least one upgrade after level 1 (reward >= 20) and roughly one or two per level.
(waves.py LEVELS reward values may change; nothing else in waves.py.)

## Client (later task)
Win screen becomes the shop: shows tokens, the three upgrades with level/max and price, keys 1/2/3 to buy, N for
the next level, R to replay. Campaign-complete screen after the last level.
