You are doing CONSENSUS + RANKING for a 3-way bake-off. Do not edit, create or delete any file. Do not run any
git command that changes state (no checkout/switch/worktree/commit/merge) — read-only commands only
(git show <ref>:<path>, git diff <refA>..<refB> -- <path>, git log) are fine. Do not list or read anything
outside the working directory, except via `git show <branch>:<path>` / `git diff` against the branches named
below, which is how you inspect the other entries without checking them out.

Three models each independently implemented the phase 4 World (server-side campaign progression: upgrades, shop
actions, campaign end, snapshot fields) from the SPEC below, on the same starting point (branch p4/tests, which
this worktree is checked out on — HEAD here already includes a since-fixed test, see NOTES). Two other models
reviewed each entry (the two who did not write it). Below are: the entries' branches/commits, the ALREADY-VERIFIED
test/ruff results (trust these, do not re-run the suite), and the review issues. Your job: verify each review
claim by reading the actual code with `git show <branch>:<path>` (cite exact lines), then rank the three entries
and score each 0-100 (100 = perfect spec compliance, correct/config-driven upgrade effects, full state persistence,
determinism, vectorised multishot, no perf regression, clean code; deduct for confirmed bugs by severity: high
~25-40 pts, medium ~10-15, low ~2-5).

ENTRIES:
- luna: branch p4/world-luna, commit 1acbfba. Verified: 144/144 tests pass (at the time, against the OLD/buggy
  test), ruff clean.
- flash: branch p4/world-flash, commit 201010d. Verified: 143/144 tests pass (1 fail was the old buggy test,
  now fixed — see NOTES), ruff clean.
- muse: branch p4/world-muse, commit 3e48421. Verified: 142/144 tests pass (1 fail was the old buggy test, now
  fixed; 1 fail is a real bug, see reviews below), ruff clean.

NOTES (already confirmed by the orchestrator, sanity-checked against the code — treat as ground truth, no need to
re-verify): tests/test_progression.py::test_shop_only_works_after_winning_and_prices_are_spent originally asserted
that an unaffordable buy_fire_rate leaves tokens at 0 (i.e. it silently spends FIRE_RATE_PRICES[0] for nothing).
That contradicts the spec ("otherwise ignored"): an ignored buy must leave tokens and upgrade level completely
unchanged. The test has been fixed on p4/tests commit 01bd6f9 (HEAD of this worktree) to assert tokens stay
unchanged. Any review issue that is really just this test bug (not an implementation bug) should be treated as
NOT a code defect for scoring purposes — but if an entry's code contains a matching hack that deliberately drains
tokens on a failed buy (deducting prices[0] or similar) to satisfy the old wrong test, THAT is a real high-severity
implementation bug independent of the test fix (it violates the spec even against the corrected test).

REVIEWS OF luna's ENTRY (by muse and flash):
--- muse ---
verdict: changes
issues:
- [high] swarm_control/sim/world.py:130 unaffordable buy steals prices[0] tokens without granting a level instead of being ignored; remove the inner if/deduction and just return.
--- flash ---
verdict: changes
issues:
- [high] swarm_control/sim/world.py:129 spends tokens without granting an upgrade: when `tokens < prices[level]` but `tokens >= prices[0]` at level>=1 it deducts `prices[0]` and returns, so a failed buy silently burns tokens (25 tokens at fire_rate level 1 -> 5, no upgrade). Spec says unaffordable buys are ignored; delete the `if level and self.tokens >= prices[0]: self.tokens -= prices[0]` block so it just returns.
- [medium] tests/test_progression.py:76-78 encodes the same bug (see NOTES; already fixed on p4/tests).

REVIEWS OF flash's ENTRY (by luna and muse):
--- luna ---
verdict: changes
issues:
- [medium] tests/test_progression.py:76 test bug (see NOTES; already fixed on p4/tests).
- [low] swarm_control/sim/world.py:124 Upgrade maximums are inferred from price-tuple lengths instead of using `FIRE_RATE_MAX_LEVEL`, `MULTISHOT_MAX_LEVEL`, and `SPEED_MAX_LEVEL` from config.py; use the configured max constants directly.
--- muse ---
verdict: changes
issues:
- [high] tests/test_progression.py:78 test bug, mislabeled high by this reviewer (see NOTES; already fixed on p4/tests; treat as NOT a code defect).
- [low] swarm_control/sim/world.py:126 max level is derived from len(prices) while config FIRE_RATE_MAX_LEVEL/MULTISHOT_MAX_LEVEL/SPEED_MAX_LEVEL sit unused; gate _next_price on the MAX_LEVEL constants so the two sources cannot diverge.

REVIEWS OF muse's ENTRY (by luna and flash):
--- luna ---
verdict: changes
issues:
- [high] swarm_control/sim/world.py:249 Winning the same level after `restart` awards its reward again, contradicting the "adds its integer reward once" behavior and failing test_upgrades_persist_restart_and_load_level; track whether the current level has already paid its reward across replays.
- [low] swarm_control/sim/waves.py:78,123,177 Level 2 and 3 rewards were changed although the spec only requires changing rewards as needed (level 1 at least 20); retain existing later-level rewards unless higher rewards are demonstrably required.
--- flash ---
verdict: changes
issues:
- [high] swarm_control/sim/world.py:249 The reward is re-added every time a level is won, so a restart followed by re-winning the same level inflates tokens (test gets 1985 instead of 985). Track rewarded level numbers (e.g. `self._rewarded: set[int]` in __init__) and only add `self.level["reward"]` the first time a level is won.
- [low] swarm_control/sim/world.py:132 `_has_next` calls `get_level` (deep-copies the next level) on every snapshot(), ~30x/s; harmless but wasteful, could cache.

Reply with exactly this format and nothing else:
consensus: <N> confirmed, <M> rejected
fix list (verified real defects, by entry):
- luna: [sev] <file:line> <fix>  (or "none")
- flash: [sev] <file:line> <fix>  (or "none")
- muse: [sev] <file:line> <fix>  (or "none")
rejected:
- <issue> — <why it doesn't hold up, e.g. "test bug not code" or "could not reproduce">
scores:
- luna: <0-100> — <one line why>
- flash: <0-100> — <one line why>
- muse: <0-100> — <one line why>
winner: luna | flash | muse

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
