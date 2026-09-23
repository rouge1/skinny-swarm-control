"""Acceptance tests for swarm_control.sim.waves (phase 3)."""

import copy

import numpy as np
import pytest

from swarm_control import config
from swarm_control.sim.gates import move_gates  # noqa: F401  (levels use the gate format)
from swarm_control.sim.pool import UnitPool
from swarm_control.sim.waves import LEVELS, WaveSpawner, get_level, validate_level

WAVES = [
    {"t": 2.0, "count": 5, "x": 270, "spread": 100, "speed": 80},
    {"t": 0.0, "count": 3, "x": 100, "spread": 0, "speed": 50, "hp": 2.0, "kind": 1},
    {"t": 5.0, "count": 4, "x": 530, "spread": 200, "speed": 60},
]


def make():
    return WaveSpawner(copy.deepcopy(WAVES), np.random.default_rng(0)), UnitPool(100)


def test_waves_spawn_on_time():
    sp, red = make()
    assert sp.remaining == 3 and not sp.done()
    assert sp.update(0.0, red) == 3
    assert sp.update(1.9, red) == 0
    assert sp.update(2.0, red) == 5
    assert sp.remaining == 1
    assert sp.update(10.0, red) == 4
    assert sp.done() and sp.remaining == 0
    assert red.count == 12
    assert sp.update(20.0, red) == 0


def test_late_update_spawns_all_due_waves():
    sp, red = make()
    assert sp.update(100.0, red) == 12


def test_bug_fields():
    sp, red = make()
    sp.update(0.0, red)
    idx = red.active_indices()
    assert np.allclose(red.x[idx], 100)
    assert np.all((red.y[idx] >= config.BUG_SPAWN_Y) & (red.y[idx] <= config.BUG_SPAWN_Y + 30))
    assert np.all(red.vy[idx] == 50) and np.all(red.vx[idx] == 0)
    assert np.all(red.hp[idx] == 2.0) and np.all(red.kind[idx] == 1)


def test_spread_and_clipping():
    sp, red = make()
    sp.update(100.0, red)
    x = red.x[red.active_indices()]
    assert np.all(x >= config.UNIT_RADIUS) and np.all(x <= config.FIELD_W - config.UNIT_RADIUS)


def test_custom_spawn_y():
    sp, red = make()
    sp.update(0.0, red, spawn_y=300)
    y = red.y[red.active_indices()]
    assert np.all((y >= 300) & (y <= 330))


def test_full_pool_loses_rest_of_wave():
    sp = WaveSpawner(copy.deepcopy(WAVES), np.random.default_rng(0))
    red = UnitPool(4)
    assert sp.update(2.0, red) == 4  # 3 from the t=0 wave + 1 of the t=2 wave
    assert sp.remaining == 1


def test_input_list_not_modified():
    waves = copy.deepcopy(WAVES)
    before = copy.deepcopy(waves)
    sp = WaveSpawner(waves, np.random.default_rng(0))
    sp.update(100, UnitPool(100))
    assert waves == before


def test_deterministic():
    a, ra = make()
    b, rb = make()
    a.update(100, ra)
    b.update(100, rb)
    assert np.array_equal(ra.x, rb.x) and np.array_equal(ra.y, rb.y)


# ------------------------------------------------------------------ levels


def test_levels_exist_and_are_valid():
    assert len(LEVELS) >= 3
    for i, lvl in enumerate(LEVELS, start=1):
        assert lvl["id"] == i
        assert validate_level(lvl) == [], (i, validate_level(lvl))


def test_levels_get_harder():
    bugs = [sum(w["count"] for w in lvl["waves"]) for lvl in LEVELS]
    hp = [lvl["enemy_hp"] for lvl in LEVELS]
    assert all(b2 > b1 for b1, b2 in zip(bugs, bugs[1:], strict=False))
    assert all(h2 > h1 for h1, h2 in zip(hp, hp[1:], strict=False))


def test_level_gates_are_themed():
    labels = [g["label"].lower() for lvl in LEVELS for g in lvl["gates"]]
    assert labels
    words = ("fork", "worktree", "subagent", "agent", "parallel", "branch", "spawn", "clone")
    assert all(any(w in label for w in words) for label in labels), labels


def test_get_level_returns_copy():
    a = get_level(1)
    a["gates"].clear()
    assert get_level(1)["gates"], "get_level must return a deep copy"
    with pytest.raises(KeyError):
        get_level(0)
    with pytest.raises(KeyError):
        get_level(len(LEVELS) + 1)


def G(**kw):
    g = {"x": 10, "y": 400, "w": 100, "h": 30, "op": "mul", "value": 2, "label": "x2 fork"}
    g.update(kw)
    return g


def W(**kw):
    w = {"t": 1, "count": 1, "x": 10, "spread": 0, "speed": 10}
    w.update(kw)
    return w


@pytest.mark.parametrize(
    "mutate",
    [
        lambda lv: lv.pop("waves"),
        lambda lv: lv.update(enemy_hp=0),
        lambda lv: lv.update(reward=-1),
        lambda lv: lv["gates"].append(G(x=500)),  # sticks out of the field
        lambda lv: lv["gates"].append(G(op="pow")),
        lambda lv: lv["gates"].append(G(value=0)),
        lambda lv: lv["waves"].append(W(t=-1)),
        lambda lv: lv["waves"].append(W(count=0)),
        lambda lv: lv["waves"].append(W(speed=0)),
        lambda lv: lv.update(gates=[G()] * 33),
    ],
)
def test_validate_level_catches_problems(mutate):
    lvl = get_level(1)
    mutate(lvl)
    assert validate_level(lvl) != []
