Task: write the phase 5 balance acceptance tests for Swarm Control (tests come BEFORE the balance fix).

Read AGENTS.md first and follow it. Do not list or read anything outside the working directory.
Read swarm_control/config.py, swarm_control/sim/world.py (World, set_input, step, status, elapsed, enemy_hp,
player_hp, launcher_x, tokens, buy_* actions), swarm_control/sim/waves.py (LEVELS, get_level) and
scripts/balance.py (the scripted players "sweep", "sweep-fast", "idle", "stand@X" and how it drives a World —
you may copy/adapt that driving logic into the test file; do not import scripts/balance.py itself, tests must be
self-contained).

Create only tests/test_balance.py (new; do not edit any other file, including scripts/balance.py or waves.py).
It must assert these targets, run with NO upgrades bought except the one block below that explicitly buys them:
- idle player and every stand@x player (x in 90/180/270/360/450, launcher pinned, fire held, never move) LOSE
  every level, every seed used. (Today stand@180 wins level 1 around 43s — this must become impossible.)
- A sweeping player (fire while alternating left/right every 2 s, as in scripts/balance.py's "sweep") wins 100%
  of levels/seeds, and the median time-to-win rises with level number:
  level 1 in 45-75 s, level 2 in 70-100 s, level 3 in 95-130 s.
- A sweep-fast player (alternate every 1 s) also wins every level, every seed.
- With upgrades bought (buy whatever each level's reward affords, cheapest upgrade first, greedily, the moment
  tokens allow, between levels — i.e. simulate the campaign: win level 1 with no upgrades, spend reward on the
  cheapest affordable upgrade(s), replay/continue, etc.), each level is won faster than the equivalent no-upgrade
  run above (compare median or single-seed time; upgraded must be strictly faster).
Use fewer seeds than balance.py's default 5 if needed to keep the whole file under ~60 s wall time (e.g. seeds
1-3, or 1-2 for the stand/idle checks which are fast and deterministic-ish). Keep dt = 1/config.TICK_HZ and a
generous step budget (up to 180 s of game time) per run, matching scripts/balance.py's approach. Mark the module
or slow tests with a comment noting they are intentionally slow; no need for pytest.mark.slow (no such marker
exists in this repo — check pyproject.toml/conftest.py first and match existing conventions).

These tests MUST fail against today's waves.py (level 1 is winnable by a standing player, level 3 is easier than
level 2) — that is expected and correct; the next task will change swarm_control/sim/waves.py LEVELS to make them
pass. Do not weaken a target to make it pass today.

Done when:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_balance.py -q
runs to completion (failures on today's waves.py are fine and expected) in well under 2 minutes, and
    /data/python/learn/swarm-control/.venv/bin/ruff check .
passes. End with a short summary: which targets are encoded as which test functions, current pass/fail against
today's waves.py, and how long the file takes to run.
