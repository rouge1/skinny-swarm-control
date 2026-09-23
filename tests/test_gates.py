"""Acceptance tests for swarm_control.sim.gates (phase 3)."""

import time

import numpy as np
import pytest

from swarm_control import config
from swarm_control.sim.gates import apply_gates, move_gates
from swarm_control.sim.pool import UnitPool


def gate(x=100.0, y=400.0, w=120.0, h=30.0, op="mul", value=3, vx=0.0):
    return {"x": x, "y": y, "w": w, "h": h, "op": op, "value": value, "label": f"{op}{value}", "vx": vx}


def setup(cap=64):
    return UnitPool(cap), np.zeros(cap, np.uint32), np.random.default_rng(0)


# ------------------------------------------------------------------ movement


def test_move_gates_linear():
    g = [gate(x=100, vx=50)]
    move_gates(g, 0.5)
    assert g[0]["x"] == pytest.approx(125) and g[0]["vx"] == 50


def test_move_gates_bounces_right_wall():
    g = [gate(x=400, w=120, vx=100)]  # right edge at 520, wall at 540
    move_gates(g, 0.5)  # would reach x=450 -> right edge 570 -> reflect to 2*(540-120)-450 = 390
    assert g[0]["x"] == pytest.approx(390) and g[0]["vx"] == -100


def test_move_gates_bounces_left_wall():
    g = [gate(x=10, vx=-40)]
    move_gates(g, 0.5)  # would reach -10 -> reflect to 10
    assert g[0]["x"] == pytest.approx(10) and g[0]["vx"] == 40


def test_static_gate_without_vx():
    g = [gate()]
    del g[0]["vx"]
    move_gates(g, 1.0)
    assert g[0]["x"] == 100


def test_gate_stays_inside_field_over_time():
    g = [gate(x=0, w=200, vx=333)]
    for _ in range(600):
        move_gates(g, 1 / 60)
        assert 0 <= g[0]["x"] <= config.FIELD_W - 200 + 1e-6


# ------------------------------------------------------------------ multiplying


def test_mul_gate_copies_and_marks():
    pool, passed, rng = setup()
    i = pool.spawn(150, 410, vy=-260, kind=2, hp=3)
    n = apply_gates(pool, passed, [gate(op="mul", value=3)], rng)
    assert n == 2 and pool.count == 3
    act = pool.active_indices()
    assert np.all(passed[act] & 1)
    others = act[act != i]
    assert np.all(np.abs(pool.x[others] - 150) <= config.GATE_SCATTER + 1e-4)
    assert np.all((pool.y[others] <= 410 + 1e-4) & (pool.y[others] >= 410 - config.GATE_SCATTER - 1e-4))
    assert np.all(pool.vy[others] == -260) and np.all(pool.kind[others] == 2) and np.all(pool.hp[others] == 3)


def test_add_gate():
    pool, passed, rng = setup()
    pool.spawn_many([110, 200], [405, 420], vy=-260)
    assert apply_gates(pool, passed, [gate(op="add", value=5)], rng) == 10
    assert pool.count == 12


def test_mul_one_does_nothing_but_marks():
    pool, passed, rng = setup()
    i = pool.spawn(150, 410)
    assert apply_gates(pool, passed, [gate(op="mul", value=1)], rng) == 0
    assert passed[i] & 1


def test_gate_only_triggers_once_per_unit():
    pool, passed, rng = setup()
    pool.spawn(150, 410)
    g = [gate(op="mul", value=2)]
    assert apply_gates(pool, passed, g, rng) == 1
    assert apply_gates(pool, passed, g, rng) == 0
    assert pool.count == 2


def test_units_outside_or_inactive_ignored():
    pool, passed, rng = setup()
    pool.spawn(99.0, 410)  # just left of the gate
    pool.spawn(150, 399.0)  # just above
    j = pool.spawn(150, 410)
    pool.despawn(j)  # inactive but positioned inside
    assert apply_gates(pool, passed, [gate()], rng) == 0
    assert pool.count == 2 and not passed.any()


def test_edges_are_inside():
    pool, passed, rng = setup()
    pool.spawn_many([100.0, 220.0], [400.0, 430.0])
    assert apply_gates(pool, passed, [gate(op="mul", value=2)], rng) == 2


def test_copies_inherit_parent_mask():
    pool, passed, rng = setup()
    i = pool.spawn(150, 410)
    passed[i] = 0b100
    apply_gates(pool, passed, [gate(op="mul", value=2)], rng)
    act = pool.active_indices()
    assert np.all(passed[act] == 0b101)


def test_second_gate_uses_bit_one():
    pool, passed, rng = setup()
    pool.spawn(150, 410)
    gates = [gate(x=400, y=100), gate(op="mul", value=2)]
    assert apply_gates(pool, passed, gates, rng) == 1
    act = pool.active_indices()
    assert np.all(passed[act] == 0b10)


def test_chain_of_gates_over_time():
    pool, passed, rng = setup(256)
    pool.spawn(150, 500, vy=-100)
    gates = [gate(y=400, op="mul", value=2), gate(y=300, op="add", value=3), gate(y=200, op="mul", value=2)]
    for _ in range(4 * 60):
        pool.step(1 / 60)
        apply_gates(pool, passed, gates, rng)
    # 1 -> x2 = 2 -> +3 each = 8 -> x2 = 16 (copies scatter by <= 12px, gates are 30px tall and
    # 120px wide around x=150, so every copy still crosses the next gates)
    assert pool.count == 16


def test_pool_full_spawns_what_fits():
    pool, passed, rng = setup(cap=5)
    pool.spawn_many([150, 160], [410, 410])
    n = apply_gates(pool, passed, [gate(op="mul", value=5)], rng)
    assert n == 3 and pool.count == 5


def test_deterministic_with_rng():
    def run():
        pool, passed, _ = setup()
        pool.spawn_many([150, 160, 170], [410, 410, 410])
        apply_gates(pool, passed, [gate(op="mul", value=4)], np.random.default_rng(42))
        return pool.x.copy(), pool.y.copy()

    (x1, y1), (x2, y2) = run(), run()
    assert np.array_equal(x1, x2) and np.array_equal(y1, y2)


def test_apply_gates_performance():
    pool = UnitPool(config.BLUE_CAPACITY)
    passed = np.zeros(pool.capacity, np.uint32)
    rng = np.random.default_rng(1)
    pool.spawn_many(rng.uniform(0, 540, 3000), rng.uniform(0, 960, 3000))
    gates = [gate(x=60 * k, y=100 * k, w=60, h=20, op="add", value=1) for k in range(8)]
    passed[:] = 0xFF  # everything already passed: measures the steady-state cost
    t = time.perf_counter()
    for _ in range(200):
        apply_gates(pool, passed, gates, rng)
    assert (time.perf_counter() - t) / 200 < 0.004
