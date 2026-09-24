You are a REVIEWER on Swarm Control. Do not edit, create or delete any file. Do not run git commands that change
state. Do not list or read anything outside the working directory. You may run the test suite and short python
snippets with /data/python/learn/swarm-control/.venv/bin/python to probe.

Another model implemented the phase 4 world (server-side progression: upgrades, shop actions, campaign end,
snapshot fields) from the spec below, on top of the already-committed phase 4 tests. See what changed with:
    git diff main -- swarm_control/ CONTRACTS.md

Run the full suite first: /data/python/learn/swarm-control/.venv/bin/python -m pytest -q
and note the pass/fail count, plus ruff: /data/python/learn/swarm-control/.venv/bin/ruff check .

Review for:
1. Spec compliance: "next" only when won and a next level exists (tokens/upgrades carry over); buy_* actions only
   while won, only if affordable and below max level, otherwise ignored; restart keeps tokens/upgrades.
2. Upgrade effects are correct AND read from config.py constants (not hardcoded numbers): fire_rate interval x0.85
   per level (max 4, prices 20/40/80/160); multishot +1 agent per shot fanned 12px apart centred on launcher (max 2,
   prices 30/90); speed x1.25 per level (max 3, prices 15/30/60).
3. State persistence: upgrades and tokens survive restart, next, and load_level, for the rest of the World's life.
4. Determinism: same inputs/seed produce the same snapshot; no reliance on dict ordering, set iteration, wall-clock
   time, or unseeded randomness for game-affecting behaviour.
5. Vectorised multishot: extra agents from multishot should be produced without an unvectorised per-agent Python
   loop where the codebase already vectorises movement/collision (numpy or equivalent); flag any O(n) Python loop
   added to a hot path (step/collide) that wasn't there before.
6. No performance regression: run
   /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_world_p3.py::test_step_performance_under_load -q -s
   and compare the reported timing/assertions to what you'd expect pre-phase-4 (the test's own budget is the bar;
   flag it only if it is slow, skipped, weakened, or newly flaky).
7. Snapshot/protocol correctness: has_next, upgrades, prices (null when maxed), level_name all present and typed
   per protocol.validate_state; waves.py LEVELS rewards changed only as needed (reward >= 20 on level 1) and nothing
   else in waves.py changed.
8. Campaign end: last level won, "next" is a no-op, snapshot says no next level.

Reply with exactly this format and nothing else:
verdict: pass | changes
issues:
- [high|medium|low] <file:line> <one line: what is wrong and the fix>

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
