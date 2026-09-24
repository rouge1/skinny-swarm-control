Two independent reviewers of the phase 4 world bake-off (which built against your tests unchanged) confirmed a bug
in a test YOU wrote in tests/test_progression.py, in test_shop_only_works_after_winning_and_prices_are_spent:

    w.tokens = config.FIRE_RATE_PRICES[0]
    w.action("buy_fire_rate")
    assert w.tokens == 0 and w.upgrades["fire_rate"] == 1

At this point fire_rate is already level 1, so the next price is FIRE_RATE_PRICES[1] (40), and
FIRE_RATE_PRICES[0] (20) < 40. Per the spec, buy_* is "only allowed ... if tokens >= price ... Otherwise
ignored." An unaffordable buy must leave state completely unchanged: tokens stay 20, fire_rate stays at
level 1. The current assertion (tokens == 0, i.e. spent, but the upgrade level UNCHANGED at 1) instead
expects the world to silently burn the player's tokens on a failed purchase, which contradicts "ignored" and
rewards implementations that deduct partial payment for nothing.

Fix ONLY this: change the assertion so an unaffordable buy leaves tokens and upgrade level unchanged:
    w.tokens = config.FIRE_RATE_PRICES[0]
    w.action("buy_fire_rate")
    assert w.tokens == config.FIRE_RATE_PRICES[0] and w.upgrades["fire_rate"] == 1

Scan the rest of tests/test_progression.py and tests/test_protocol.py for any other assertion that expects
tokens to be partially spent (or any other state to change) on a buy_* action that should have been ignored
(insufficient funds or max level). Fix any you find the same way: on an ignored buy, tokens and upgrades must
be byte-for-byte unchanged from before the action. Do not change any other behavior or test.

When done: /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_progression.py tests/test_protocol.py -q
(these should mostly fail here since this worktree has no World implementation of phase 4 yet - that's expected;
just confirm collection succeeds, no syntax errors, and that the specific assertions you touched now match the
spec's "ignored means unchanged" rule) and
/data/python/learn/swarm-control/.venv/bin/ruff check tests/
Report which lines you changed.
