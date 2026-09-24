Two independent reviewers (Muse and Flash) reviewed your phase 4 tests; a third agent merged their reviews and
verified every claim against your code. Apply the fix list below. Same file rules as before: edit only
swarm_control/config.py, swarm_control/protocol.py, CONTRACTS.md, tests/test_progression.py, tests/test_protocol.py.
Do not edit world.py or waves.py. Do not list or read anything outside the working directory.

Notes:
- The "level 1 reward >= 20" test will fail until the implementer raises the reward in waves.py; that is expected.
- Also fix [low] the misindented action line (5 spaces) in the protocol.py docstring.

Check before finishing: ruff passes and `pytest --collect-only -q` collects without errors.

fix list (for the test author):

- [high] tests/test_progression.py:58 Change assertion from `assert w.tokens == 0 and w.upgrades["fire_rate"] == 0` to `assert w.tokens == 0 and w.upgrades["fire_rate"] == 1` (the buy should succeed after winning with 20 tokens when price is 20) (source: A+B)
- [high] tests/test_progression.py Add test that `next` action is ignored when status is "playing", "paused", or "lost" (only works when status=="won") (source: A)
- [medium] tests/test_progression.py:92,98 Extend fire_rate test from 0.5s to 1.0s run time for more reliable shot count difference (0.5s yields ~4 vs ~5 shots, too marginal) (source: B)
- [medium] tests/test_progression.py:128-139 In `test_upgrades_persist_restart_and_load_level`, call `win(w)` again after `restart` before calling `next`, and verify level id actually changed (currently `next` is ignored because status is "playing" not "won") (source: A+B)
- [medium] tests/test_progression.py Add assertion that when an upgrade reaches max level, `prices[upgrade]` becomes None (source: A)
- [medium] tests/test_progression.py Add test or snapshot assertion that `has_next` is True when a next level exists (complementary to existing test that checks `has_next` is False at end) (source: A+B)
- [medium] tests/test_progression.py Add test that verifies `get_level(1)["reward"] >= 20` per spec (level 1 must reward enough to afford at least one upgrade) (source: A+B)
- [medium] tests/test_progression.py Add explicit assertion that `tokens` persist across `restart`, `next`, and `load_level` calls (currently only upgrades are checked) (source: A+B)
- [medium] tests/test_progression.py Add test that `buy_fire_rate`, `buy_multishot`, and `buy_speed` actions are ignored when status is "paused" or "lost" (only tested for "playing" currently) (source: A)
- [medium] tests/test_protocol.py Add test that validate_state detects missing individual hud fields (has_next, upgrades, prices, level_name) as errors; currently only tests removal of entire hud (source: A)
- [medium] tests/test_protocol.py Add test that validate_state rejects bool values for hud.level, hud.blue_count, hud.red_count, hud.tokens (currently accepts them, unlike new fields which explicitly reject bool) (source: A)
- [medium] tests/test_progression.py:142-152 In `test_campaign_end_snapshot_and_next_are_stable`, improve mock setup to patch both `world_module.get_level` and `world_module.LEVELS` to only contain level 1, preventing KeyError if implementation tries to check for level 2 (source: B)

