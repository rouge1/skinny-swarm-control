"""Acceptance tests for World, phase 2 (launcher, firing, agent flight, pause/restart)."""

import time

import numpy as np
import pytest

from swarm_control import config
from swarm_control.protocol import unpack_units, validate_state
from swarm_control.sim.pool import UnitPool
from swarm_control.sim.world import World

DT = 1 / config.TICK_HZ


def run(world, seconds, **keys):
    world.set_input(keys.get("left", False), keys.get("right", False), keys.get("fire", False))
    for _ in range(round(seconds * config.TICK_HZ)):
        world.step(DT)


def test_initial_state():
    w = World()
    assert w.tick == 0 and w.status == "playing"
    assert w.launcher_x == config.FIELD_W / 2
    assert isinstance(w.blue, UnitPool) and w.blue.capacity == config.BLUE_CAPACITY
    assert isinstance(w.red, UnitPool) and w.red.capacity == config.RED_CAPACITY
    assert w.blue.count == 0


def test_step_advances_tick():
    w = World()
    run(w, 0.5)
    assert w.tick == 30


def test_launcher_moves_right_and_left():
    w = World()
    run(w, 0.25, right=True)
    assert w.launcher_x == pytest.approx(config.FIELD_W / 2 + config.LAUNCHER_SPEED * 0.25, abs=0.5)
    run(w, 0.25, left=True)
    assert w.launcher_x == pytest.approx(config.FIELD_W / 2, abs=0.5)


def test_both_arrows_cancel():
    w = World()
    run(w, 0.5, left=True, right=True)
    assert w.launcher_x == config.FIELD_W / 2


def test_launcher_is_clamped():
    w = World()
    run(w, 3, right=True)
    assert w.launcher_x == pytest.approx(config.FIELD_W - config.LAUNCHER_MARGIN)
    run(w, 5, left=True)
    assert w.launcher_x == pytest.approx(config.LAUNCHER_MARGIN)


def test_first_shot_is_immediate():
    w = World()
    run(w, DT, fire=True)
    assert w.blue.count == 1
    i = w.blue.active_indices()[0]
    assert w.blue.x[i] == pytest.approx(w.launcher_x)
    assert w.blue.vy[i] == pytest.approx(-config.AGENT_SPEED)


def test_fire_rate():
    w = World()
    run(w, 1.0, fire=True)
    expected = 1 + int(1.0 / config.FIRE_INTERVAL)
    assert abs(w.blue.count - expected) <= 1


def test_no_fire_without_key():
    w = World()
    run(w, 1.0)
    assert w.blue.count == 0


def test_agents_fly_up_from_the_muzzle():
    w = World()
    run(w, DT, fire=True)
    i = w.blue.active_indices()[0]
    y0 = float(w.blue.y[i])
    assert y0 == pytest.approx(config.LAUNCHER_Y - config.MUZZLE_OFFSET, abs=config.AGENT_SPEED * DT + 0.5)
    run(w, 0.5)
    assert float(w.blue.y[i]) == pytest.approx(y0 - config.AGENT_SPEED * 0.5, abs=1.0)


def test_agents_leave_the_field_and_are_freed():
    w = World()
    run(w, 0.3, fire=True)
    assert w.blue.count > 0
    run(w, (config.FIELD_H + 50) / config.AGENT_SPEED)
    assert w.blue.count == 0


def test_pause_resume_restart():
    w = World()
    run(w, 0.5, fire=True, right=True)
    w.action("pause")
    assert w.status == "paused"
    tick, x, n = w.tick, w.launcher_x, w.blue.count
    ys = w.blue.y.copy()
    run(w, 0.5, fire=True, right=True)
    assert (w.tick, w.launcher_x, w.blue.count) == (tick, x, n)
    assert np.array_equal(w.blue.y, ys)
    w.action("resume")
    run(w, DT)
    assert w.tick == tick + 1
    w.action("restart")
    assert w.tick == 0 and w.blue.count == 0 and w.launcher_x == config.FIELD_W / 2 and w.status == "playing"


def test_unknown_action_ignored():
    w = World()
    w.action("explode")
    assert w.status == "playing"


def test_snapshot_valid_and_consistent():
    w = World()
    run(w, 0.5, fire=True, right=True)
    snap = w.snapshot()
    assert validate_state(snap) == []
    assert snap["tick"] == w.tick
    assert snap["hud"]["blue_count"] == w.blue.count == len(snap["blue"]) // 3
    assert snap["launcher"]["x"] == pytest.approx(w.launcher_x)
    for x, y, _k in unpack_units(snap["blue"]):
        assert 0 <= x <= config.FIELD_W and y <= config.FIELD_H


def test_deterministic():
    a, b = World(seed=3), World(seed=3)
    for w in (a, b):
        run(w, 0.4, fire=True, right=True)
        run(w, 0.4, fire=True, left=True)
    assert a.snapshot() == b.snapshot()


def test_step_performance_with_full_swarm():
    w = World()
    n = config.BLUE_CAPACITY
    w.blue.spawn_many(np.linspace(20, 520, n), np.full(n, 800.0), vy=-1.0)
    t = time.perf_counter()
    run(w, 10)  # 600 steps
    assert time.perf_counter() - t < 1.5
    assert w.blue.count == n
