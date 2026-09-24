"""Phase 4 acceptance tests for campaign progression and upgrades."""

import copy

import pytest

from swarm_control import config
from swarm_control.sim import world as world_module
from swarm_control.sim.waves import get_level
from swarm_control.sim.world import World

DT = 1 / config.TICK_HZ


def level(**changes):
    result = {
        "id": 1,
        "name": "Tiny One",
        "enemy_hp": 1,
        "player_hp": 100,
        "reward": 1000,
        "gates": [],
        "waves": [],
    }
    result.update(changes)
    return result


def win(world):
    world.blue.spawn(270, config.ENEMY_HIT_Y + 1, vy=-config.AGENT_SPEED)
    world.step(DT)
    assert world.status == "won"


def run(world, seconds, **keys):
    world.set_input(keys.get("left", False), keys.get("right", False), keys.get("fire", False))
    for _ in range(round(seconds * config.TICK_HZ)):
        world.step(DT)


def test_next_loads_next_level_and_carries_progress(monkeypatch):
    levels = {1: level(), 2: level(id=2, name="Tiny Two", reward=7)}
    monkeypatch.setattr(world_module, "get_level", lambda number: copy.deepcopy(levels[number]))
    w = World(level=levels[1])
    win(w)
    w.action("buy_fire_rate")
    assert w.tokens == 980
    assert w.snapshot()["hud"]["has_next"] is True
    w.action("next")
    assert w.status == "playing" and w.level["id"] == 2
    assert w.tokens == 980 and w.upgrades["fire_rate"] == 1
    assert w.snapshot()["hud"]["has_next"] is False


def test_next_is_ignored_unless_status_is_won(monkeypatch):
    levels = {1: level(), 2: level(id=2, name="Tiny Two")}
    monkeypatch.setattr(world_module, "get_level", lambda number: copy.deepcopy(levels[number]))
    for status in ("playing", "paused", "lost"):
        w = World(level=levels[1])
        if status == "paused":
            w.action("pause")
        else:
            w.status = status
        w.action("next")
        assert w.level["id"] == 1 and w.status == status


def test_shop_only_works_after_winning_and_prices_are_spent():
    w = World(level=level(reward=20))
    w.action("buy_fire_rate")
    assert w.tokens == 0 and w.upgrades["fire_rate"] == 0
    win(w)
    w.action("buy_fire_rate")
    assert w.tokens == 0 and w.upgrades["fire_rate"] == 1

    w.tokens = config.FIRE_RATE_PRICES[0]
    w.action("buy_fire_rate")
    assert w.tokens == 0 and w.upgrades["fire_rate"] == 1


@pytest.mark.parametrize(
    ("action", "prices", "attribute"),
    [
        ("buy_fire_rate", config.FIRE_RATE_PRICES, "fire_rate"),
        ("buy_multishot", config.MULTISHOT_PRICES, "multishot"),
        ("buy_speed", config.SPEED_PRICES, "speed"),
    ],
)
def test_shop_rejects_not_enough_tokens_and_max_level(action, prices, attribute):
    w = World(level=level(reward=0))
    win(w)
    w.tokens = prices[0] - 1
    w.action(action)
    assert w.upgrades[attribute] == 0 and w.tokens == prices[0] - 1
    w.tokens = sum(prices)
    for _price in prices:
        w.action(action)
        assert w.upgrades[attribute] <= len(prices)
    tokens = w.tokens
    w.action(action)
    assert w.upgrades[attribute] == len(prices) and w.tokens == tokens
    assert w.snapshot()["hud"]["prices"][attribute] is None


def test_fire_rate_upgrade_increases_shots_per_second():
    base = World(level=level(reward=100))
    win(base)
    base.action("restart")
    run(base, 1.0, fire=True)

    upgraded = World(level=level(reward=100))
    win(upgraded)
    upgraded.action("buy_fire_rate")
    upgraded.action("restart")
    run(upgraded, 1.0, fire=True)
    assert upgraded.blue.count > base.blue.count


def test_multishot_upgrade_adds_centered_fanned_agents():
    w = World(level=level(reward=100))
    win(w)
    w.action("buy_multishot")
    w.action("restart")
    run(w, DT, fire=True)
    xs = sorted(float(w.blue.x[i]) for i in w.blue.active_indices())
    assert len(xs) == 2
    assert xs == pytest.approx([w.launcher_x - 6, w.launcher_x + 6])


def test_speed_upgrade_increases_launcher_displacement():
    base = World(level=level(reward=100))
    win(base)
    base.action("restart")
    run(base, 0.25, right=True)
    upgraded = World(level=level(reward=100))
    win(upgraded)
    upgraded.action("buy_speed")
    upgraded.action("restart")
    run(upgraded, 0.25, right=True)
    assert upgraded.launcher_x - config.FIELD_W / 2 == pytest.approx(
        (base.launcher_x - config.FIELD_W / 2) * config.LAUNCHER_SPEED_FACTOR
    )


def test_upgrades_persist_restart_and_load_level(monkeypatch):
    levels = {1: level(), 2: level(id=2, name="Two")}
    monkeypatch.setattr(world_module, "get_level", lambda number: copy.deepcopy(levels[number]))
    w = World(level=levels[1])
    win(w)
    w.action("buy_speed")
    tokens = w.tokens
    w.action("restart")
    assert w.upgrades["speed"] == 1 and w.tokens == tokens
    win(w)
    w.action("next")
    assert w.level["id"] == 2
    assert w.upgrades["speed"] == 1 and w.tokens == tokens
    w.load_level(levels[1])
    assert w.upgrades["speed"] == 1 and w.tokens == tokens


def test_campaign_end_snapshot_and_next_are_stable(monkeypatch):
    only = {1: level(name="Final")}
    monkeypatch.setattr(world_module, "get_level", lambda number: copy.deepcopy(only[number]))
    monkeypatch.setattr(world_module, "LEVELS", [only[1]], raising=False)
    w = World(level=only[1])
    win(w)
    snapshot = w.snapshot()
    assert snapshot["status"] == "won"
    assert snapshot["hud"]["has_next"] is False
    assert snapshot["hud"]["level_name"] == "Final"
    w.action("next")
    assert w.status == "won" and w.level["name"] == "Final"


def test_level_one_reward_can_buy_an_upgrade():
    assert get_level(1)["reward"] >= config.FIRE_RATE_PRICES[0]


def test_shop_actions_are_ignored_while_paused_or_lost():
    for status in ("paused", "lost"):
        w = World(level=level(reward=0))
        w.tokens = 100
        w.status = status
        for action in ("buy_fire_rate", "buy_multishot", "buy_speed"):
            w.action(action)
        assert w.tokens == 100
        assert w.upgrades == {"fire_rate": 0, "multishot": 0, "speed": 0}


def test_snapshot_has_progression_fields_and_is_deterministic():
    a, b = World(seed=9, level=level()), World(seed=9, level=level())
    for w in (a, b):
        win(w)
        w.action("buy_speed")
    assert a.snapshot() == b.snapshot()
    hud = a.snapshot()["hud"]
    assert hud["upgrades"] == {"fire_rate": 0, "multishot": 0, "speed": 1}
    assert hud["prices"] == {"fire_rate": 20, "multishot": 30, "speed": 30}
    assert hud["level_name"] == "Tiny One"
