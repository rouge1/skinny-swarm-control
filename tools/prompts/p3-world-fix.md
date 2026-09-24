Review feedback on your World wiring (quality 24/30; the reviewer confirmed step order, gate masks, restart,
determinism and performance). Three changes; edit only swarm_control/sim/world.py. New acceptance tests are in
tests/test_world_levels.py and must pass along with everything else.

1. [medium] When both bases reach 0 in the same step, the world currently declares "won" and pays the reward.
   Decision: a tie is a LOSS (your base was destroyed). Check player_hp first; no reward on a loss.
2. [low] The sandbox level (level=None) lacks id/name/enemy_hp/player_hp/reward; give the default level every key
   (id 0 or 1, name "Sandbox", hp 100/100, reward 0, empty gates and waves) so world.level[...] never KeyErrors.
3. [low] Add `load_level(level: dict) -> None`: deep-copy it as the new template and reset to it, keeping tokens,
   the held keys and the same pools (restart then replays the loaded level). Phase 4 uses this to advance levels.
   Mention it in the module docstring.

Done when these pass:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest
    /data/python/learn/swarm-control/.venv/bin/ruff check .
