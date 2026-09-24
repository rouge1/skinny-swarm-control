You are a REVIEWER on Swarm Control. Do not edit, create or delete any file. Do not run git commands that change
state. Do not list or read anything outside the working directory. You may run the test suite and short python
snippets with /data/python/learn/swarm-control/.venv/bin/python to probe.

Another model wrote phase 4 contracts and acceptance tests from the spec below. The implementation does NOT exist yet,
so the new tests are expected to fail today; do not report that. Judge the TESTS. See what changed with:
    git diff main -- tests/ swarm_control/config.py swarm_control/protocol.py CONTRACTS.md

Review for:
1. Spec coverage: every rule in the spec has a test (shop only while won; price; max level; not enough tokens;
   each upgrade's measurable effect; persistence across restart and next; campaign end; snapshot fields; protocol
   validation). List missing rules.
2. Wrong or over-specified tests: asserts that contradict the spec, or pin details the spec leaves open (exact
   positions of fanned-out agents beyond "12 px apart, centred", exact ordering), or depend on level balance.
3. Flaky tests: timing, floating point equality, randomness without a seed.
4. Passability: could a correct implementation pass all of them? Point out any test that is impossible or
   self-contradictory.
5. Protocol/config changes: correct and consistent with the spec.

Reply with exactly this format and nothing else:
verdict: pass | changes
issues:
- [high|medium|low] <file:test or file:line> <one line: what is wrong and the fix>

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
