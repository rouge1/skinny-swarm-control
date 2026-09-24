Task: write a headless BALANCE REPORT script for Swarm Control, used in phase 5 to tune levels.

Read AGENTS.md first and follow it. Do not list or read anything outside the working directory.
Read swarm_control/config.py, swarm_control/sim/world.py (World, set_input, step, status, elapsed, enemy_hp,
player_hp, launcher_x), swarm_control/sim/waves.py (LEVELS, get_level) and tests/test_world_p3.py (the scripted
players in test_every_level_is_winnable_by_a_scripted_player, test_idle_player_loses_every_level and
test_standing_still_is_not_a_quick_win).

Create only scripts/balance.py (new; do not edit any other file). It must:
- For every level in LEVELS and several seeds (default 1..5, --seeds N), run these scripted players at fixed
  dt = 1/TICK_HZ for up to 180 s of game time: "sweep" (fire, alternate left/right every 2 s as in the test),
  "sweep-fast" (alternate every 1 s), "idle" (never fires), and "stand" at x in 90/180/270/360/450 (fire, no move).
- Report per level and player: win rate, median / min / max time to win or lose, median final HP of both bases,
  and peak blue/red unit counts. Print an aligned text table; --json writes the same data to a file.
- Flag problems in a final "WARNINGS" list: an idle or standing player that wins; a sweep that loses; a later
  level that a sweep wins faster than an earlier one (difficulty should rise).
- Use only the public World API; no changes to game code. Standard library + numpy only.
- `python scripts/balance.py --seeds 2` must finish in under 3 minutes on this machine; print progress to stderr.

Done when:
    /data/python/learn/swarm-control/.venv/bin/python scripts/balance.py --seeds 1
runs and prints the table, and `/data/python/learn/swarm-control/.venv/bin/ruff check .` passes.
