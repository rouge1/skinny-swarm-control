Task: phase 5 BALANCE FIX — make Swarm Control's levels hit the balance targets by editing only waves.py LEVELS.

Read AGENTS.md first and follow it. Do not list or read anything outside the working directory.
Read swarm_control/sim/waves.py (LEVELS and its module docstring contract), swarm_control/config.py, and the
acceptance tests in tests/test_balance.py (already committed; DO NOT edit it — it is the spec). Also read
scripts/balance.py: it is your measurement tool, run it as you iterate.

Edit only the LEVELS list in swarm_control/sim/waves.py (enemy_hp, player_hp, gates, waves — anything inside an
entry of LEVELS). Do not touch get_level, validate_level, WaveSpawner, or any other file. Keep every level valid
per validate_level's contract (gate bounds, wave fields) and keep exactly 3 levels with ids 1, 2, 3 in order,
each still harder than the last (more total bugs and higher enemy_hp than the one before, per the module
docstring). Gate labels must keep reading like the theme (e.g. "x2 fork", "+N subagents", "x3 worktree").

Targets (measured by tests/test_balance.py, and you can watch scripts/balance.py's table too):
- idle and every stand@x scripted player LOSE every level, every seed.
- A sweep player (fire, alternate left/right every 2 s) wins every level, every seed, with median time-to-win
  rising by level: level 1 in 45-75 s, level 2 in 70-100 s, level 3 in 95-130 s.
- A sweep-fast player (alternate every 1 s) also wins every level, every seed.
- With upgrades bought as tokens allow (greedily, cheapest first), each level is won faster than without upgrades.
Right now level 1 is winnable by a standing player and level 3 is easier (faster to sweep-win) than level 2 —
both must be fixed. Favor the smallest change to LEVELS that meets every target (e.g. raise level-1 enemy_hp or
retime its waves so standing loses but sweeping still wins in range; raise level 3's enemy_hp/wave pressure so it
takes longer than level 2 without exceeding its own target window or making it unwinnable).

Iterate with:
    /data/python/learn/swarm-control/.venv/bin/python scripts/balance.py --seeds 3
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_balance.py -q

Done when:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest -q
(the FULL suite, not just test_balance.py — your LEVELS changes must not break tests/test_world_levels.py,
tests/test_world_p3.py, tests/test_progression.py or anything else that touches levels/rewards) and
    /data/python/learn/swarm-control/.venv/bin/ruff check .
both pass. End with a short summary: what you changed per level and why, and paste the final
scripts/balance.py --seeds 3 table/warnings in your answer.
