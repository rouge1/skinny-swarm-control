Task: you are the TEST AUTHOR for phase 4 of Swarm Control. Turn the spec below into contracts and acceptance
tests. Another model will implement it later without seeing you, so the tests are the spec: precise, deterministic,
and passable.

Read AGENTS.md first (rule 2 is lifted for this task: you MAY edit the files listed here). Do not list or read
anything outside the working directory. Read CONTRACTS.md, swarm_control/config.py, swarm_control/protocol.py,
swarm_control/sim/world.py (module docstring and public methods), swarm_control/sim/waves.py (LEVELS, get_level),
tests/test_world_levels.py (style to copy) and tests/test_protocol.py.

Edit / create only:
- swarm_control/config.py: add the upgrade constants (effects, max levels, prices) from the spec.
- swarm_control/protocol.py: add the new actions to ACTIONS and extend validate_state for the new hud fields
  (has_next bool, upgrades dict of 3 ints, prices dict of int-or-None, level_name str). Update the docstring.
- CONTRACTS.md: add a "Phase 4" section describing the new World behaviour and protocol fields.
- tests/test_progression.py (new): acceptance tests for the World: next level, shop rules (only while won, price,
  max level, not enough tokens), each upgrade's effect (measure it: shots per second, fan-out spacing, launcher
  speed), persistence across restart/next, campaign end, snapshot fields, determinism.
- tests/test_protocol.py: add tests for the new validate_state checks.
Do NOT edit swarm_control/sim/world.py or any other source file: the implementation does not exist yet, so your new
tests are EXPECTED to fail now. Tests must not depend on level balance (build tiny custom levels with
World(level=...) and win them quickly, as tests/test_world_levels.py does).

Check before finishing: `/data/python/learn/swarm-control/.venv/bin/ruff check .` passes, and
`/data/python/learn/swarm-control/.venv/bin/python -m pytest --collect-only -q` collects without errors.
Existing tests other than the new ones must still pass except where they assert the old ACTIONS/hud exactly.

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
