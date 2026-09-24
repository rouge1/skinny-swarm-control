Task: rebalance the three levels in `swarm_control/sim/waves.py` (the LEVELS list only).

Read `AGENTS.md` first. Do not list or read anything outside the working directory. Edit only the LEVELS data in
`swarm_control/sim/waves.py`; do not change WaveSpawner, get_level, validate_level, or any other file.

The World is now fully wired, so you can measure balance directly. Three acceptance tests in
tests/test_world_p3.py define "balanced":
  - test_every_level_is_winnable_by_a_scripted_player: sweeping left/right while firing wins every level;
  - test_idle_player_loses_every_level: never firing loses every level;
  - test_standing_still_is_not_a_quick_win (NEW, currently failing): holding fire without moving, at any of
    x = 90, 180, 270, 360, 450, must not win any level within 20 s. Right now level 1 is won in 9.7 s from x=90.

Game facts: field 540x960; the launcher at y=900 fires ~8 agents/s straight up at 260 px/s; an agent reaching
y<=110 does 1 damage to the fortress; agents and bugs annihilate 1:1; a bug reaching y>=940 does 1 damage to the
player; gates copy agents passing through them (see gates.py); moving gates (vx) bounce between the walls.

Levers: enemy_hp, gate positions/widths/values/vx (moving gates reward aiming; a static gate over one column
rewards camping), wave timing, counts, spread and speed, player_hp. Keep the difficulty ramp: more bugs and more
enemy_hp each level (test_waves.py checks this) and themed gate labels.

Done when all of these pass:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_world_p3.py tests/test_waves.py
    /data/python/learn/swarm-control/.venv/bin/ruff check .
The world tests take up to a minute; that is expected. In your summary, list the final numbers per level and the
time a sweeping player takes to win each level (you can measure it with a short script).
