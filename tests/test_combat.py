"""Acceptance tests for swarm_control.sim.combat (phase 3)."""

import time

import numpy as np

from swarm_control import config
from swarm_control.sim.combat import collide, hit_bases
from swarm_control.sim.pool import UnitPool

R = config.UNIT_RADIUS


def pools(cap=4000):
    return UnitPool(cap), UnitPool(cap)


def no_contacts_left(blue, red, r=R):
    b, q = blue.active_indices(), red.active_indices()
    if not len(b) or not len(q):
        return True
    dx = blue.x[b][:, None] - red.x[q][None, :]
    dy = blue.y[b][:, None] - red.y[q][None, :]
    return not np.any(dx * dx + dy * dy < (2 * r) ** 2)


def test_single_pair_annihilates():
    blue, red = pools()
    blue.spawn(100, 100)
    red.spawn(100 + 2 * R - 0.1, 100)
    assert collide(blue, red) == 1
    assert blue.count == 0 and red.count == 0


def test_touching_exactly_is_not_contact():
    blue, red = pools()
    blue.spawn(100, 100)
    red.spawn(100 + 2 * R, 100)
    assert collide(blue, red) == 0
    assert blue.count == 1 and red.count == 1


def test_far_apart_untouched():
    blue, red = pools()
    blue.spawn_many([10, 200, 400], [10, 500, 900])
    red.spawn_many([300, 50], [300, 800])
    assert collide(blue, red) == 0
    assert blue.count == 3 and red.count == 2


def test_one_to_one_trade():
    blue, red = pools()
    blue.spawn_many(np.full(10, 200.0), np.full(10, 300.0))  # 10 agents stacked on one point
    red.spawn_many(np.full(4, 201.0), np.full(4, 301.0))  # 4 bugs next to them
    assert collide(blue, red) == 4
    assert blue.count == 6 and red.count == 0


def test_same_team_never_collides():
    blue, red = pools()
    blue.spawn_many(np.full(50, 100.0), np.full(50, 100.0))
    assert collide(blue, red) == 0 and blue.count == 50


def test_maximal_matching_random_clusters():
    rng = np.random.default_rng(7)
    for trial in range(20):
        blue, red = pools(600)
        cx, cy = rng.uniform(50, 490), rng.uniform(50, 900)
        nb, nr = rng.integers(1, 400), rng.integers(1, 400)
        blue.spawn_many(rng.normal(cx, 25, nb), rng.normal(cy, 25, nb))
        red.spawn_many(rng.normal(cx, 25, nr), rng.normal(cy, 25, nr))
        b0, r0 = blue.count, red.count
        n = collide(blue, red)
        assert b0 - blue.count == n == r0 - red.count, trial
        assert no_contacts_left(blue, red), f"trial {trial}: contacting pair survived"


def test_cells_boundaries_are_handled():
    # pairs straddling likely grid cell edges at many offsets
    blue, red = pools()
    xs = np.arange(0, 540, 7.3)
    blue.spawn_many(xs, np.full(len(xs), 500.0))
    red.spawn_many(xs + 9.9, np.full(len(xs), 500.0))  # just under 2R apart
    n = collide(blue, red)
    assert no_contacts_left(blue, red)
    assert n >= len(xs) // 2


def test_collide_performance_spread_out():
    rng = np.random.default_rng(3)
    blue, red = pools()
    blue.spawn_many(rng.uniform(0, 540, 2000), rng.uniform(480, 960, 2000))
    red.spawn_many(rng.uniform(0, 540, 2000), rng.uniform(0, 480, 2000))
    t = time.perf_counter()
    for _ in range(100):
        collide(blue, red)
    assert (time.perf_counter() - t) / 100 < 0.005


def test_collide_performance_dense_clash():
    rng = np.random.default_rng(4)
    blue, red = pools()
    blue.spawn_many(rng.uniform(200, 340, 1500), rng.uniform(400, 480, 1500))
    red.spawn_many(rng.uniform(200, 340, 1500), rng.uniform(470, 550, 1500))
    t = time.perf_counter()
    n = collide(blue, red)
    assert time.perf_counter() - t < 0.1
    assert n > 0 and no_contacts_left(blue, red)


def test_hit_bases():
    blue, red = pools()
    blue.spawn_many([100, 100, 100], [config.ENEMY_HIT_Y - 1, config.ENEMY_HIT_Y, config.ENEMY_HIT_Y + 1])
    red.spawn_many([100, 100], [config.PLAYER_BASE_Y, config.PLAYER_BASE_Y - 1])
    assert hit_bases(blue, red) == (2, 1)
    assert blue.count == 1 and red.count == 1


def test_hit_bases_custom_lines():
    blue, red = pools()
    blue.spawn(0, 50)
    red.spawn(0, 50)
    assert hit_bases(blue, red, enemy_y=40, player_y=60) == (0, 0)
    assert hit_bases(blue, red, enemy_y=50, player_y=50) == (1, 1)
