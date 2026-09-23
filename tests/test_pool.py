"""Acceptance tests for swarm_control.sim.pool.UnitPool. Workers must not edit this file."""

import time

import numpy as np
import pytest

from swarm_control.sim.pool import UnitPool


@pytest.fixture
def pool():
    return UnitPool(8)


# --------------------------------------------------------------- construction


def test_arrays_shapes_and_dtypes():
    p = UnitPool(16)
    assert p.capacity == 16
    for name in ("x", "y", "vx", "vy", "hp"):
        arr = getattr(p, name)
        assert isinstance(arr, np.ndarray) and arr.shape == (16,) and arr.dtype == np.float32, name
    assert p.kind.shape == (16,) and p.kind.dtype == np.int8
    assert p.active.shape == (16,) and p.active.dtype == np.bool_


def test_starts_empty():
    p = UnitPool(5)
    assert p.count == 0
    assert not p.active.any()
    assert p.active_indices().size == 0


def test_rejects_non_positive_capacity():
    with pytest.raises(ValueError):
        UnitPool(0)


# --------------------------------------------------------------- spawn


def test_spawn_sets_fields(pool):
    i = pool.spawn(10.0, 20.0, vx=1.5, vy=-2.0, kind=3, hp=4.0)
    assert 0 <= i < pool.capacity
    assert pool.active[i]
    assert (pool.x[i], pool.y[i], pool.vx[i], pool.vy[i], pool.hp[i]) == (10.0, 20.0, 1.5, -2.0, 4.0)
    assert pool.kind[i] == 3
    assert pool.count == 1


def test_spawn_defaults(pool):
    i = pool.spawn(1.0, 2.0)
    assert (pool.vx[i], pool.vy[i], pool.kind[i], pool.hp[i]) == (0.0, 0.0, 0, 1.0)


def test_spawn_returns_distinct_slots_until_full(pool):
    slots = [pool.spawn(0, 0) for _ in range(pool.capacity)]
    assert sorted(slots) == list(range(pool.capacity))
    assert pool.spawn(0, 0) == -1
    assert pool.count == pool.capacity


def test_spawn_clears_stale_values_of_reused_slot(pool):
    i = pool.spawn(1, 1, vx=9, vy=9, kind=2, hp=7)
    pool.despawn(i)
    j = pool.spawn(3, 4)
    assert (pool.vx[j], pool.vy[j], pool.kind[j], pool.hp[j]) == (0.0, 0.0, 0, 1.0)


# --------------------------------------------------------------- spawn_many


def test_spawn_many_basic(pool):
    idx = pool.spawn_many([1, 2, 3], [4, 5, 6], vy=-10.0, kind=1)
    assert isinstance(idx, np.ndarray) and idx.dtype == np.int64 and len(idx) == 3
    assert len(set(idx.tolist())) == 3
    assert np.allclose(pool.x[idx], [1, 2, 3]) and np.allclose(pool.y[idx], [4, 5, 6])
    assert np.all(pool.vy[idx] == -10.0) and np.all(pool.kind[idx] == 1)
    assert pool.count == 3


def test_spawn_many_per_unit_arrays(pool):
    idx = pool.spawn_many([0, 0], [0, 0], vx=[1, 2], vy=[3, 4], kind=[5, 6], hp=[7, 8])
    assert pool.vx[idx].tolist() == [1, 2]
    assert pool.vy[idx].tolist() == [3, 4]
    assert pool.kind[idx].tolist() == [5, 6]
    assert pool.hp[idx].tolist() == [7, 8]


def test_spawn_many_truncates_when_nearly_full(pool):
    pool.spawn_many(np.zeros(6), np.zeros(6))
    idx = pool.spawn_many([10, 11, 12, 13], [0, 0, 0, 0])
    assert len(idx) == 2
    assert sorted(pool.x[idx].tolist()) == [10, 11]  # the first units in order are kept
    assert pool.count == 8
    assert len(pool.spawn_many([1], [1])) == 0


def test_spawn_many_empty(pool):
    idx = pool.spawn_many([], [])
    assert len(idx) == 0 and pool.count == 0


def test_spawn_many_does_not_overwrite_active(pool):
    a = pool.spawn(100, 100)
    idx = pool.spawn_many(np.arange(7), np.arange(7))
    assert a not in idx.tolist()
    assert pool.x[a] == 100


# --------------------------------------------------------------- despawn / reuse


def test_despawn_single(pool):
    i = pool.spawn(0, 0)
    assert pool.despawn(i) == 1
    assert not pool.active[i] and pool.count == 0


def test_despawn_ignores_inactive_and_duplicates(pool):
    idx = pool.spawn_many([0, 1, 2], [0, 0, 0])
    free_slot = next(s for s in range(pool.capacity) if s not in idx.tolist())
    n = pool.despawn([idx[0], idx[0], idx[1], free_slot])
    assert n == 2
    assert pool.count == 1
    assert pool.despawn(idx[0]) == 0


def test_despawn_accepts_numpy_and_empty(pool):
    idx = pool.spawn_many([0, 1], [0, 0])
    assert pool.despawn(np.array([], dtype=np.int64)) == 0
    assert pool.despawn(idx) == 2


def test_slots_are_reused_after_despawn(pool):
    idx = pool.spawn_many(np.zeros(8), np.zeros(8))
    pool.despawn(idx[:3])
    new = pool.spawn_many([1, 2, 3], [1, 2, 3])
    assert sorted(new.tolist()) == sorted(idx[:3].tolist())
    assert pool.count == 8


def test_count_tracks_many_operations():
    rng = np.random.default_rng(1)
    p = UnitPool(64)
    for _ in range(300):
        if rng.random() < 0.6:
            n = int(rng.integers(0, 10))
            p.spawn_many(rng.random(n) * 100, rng.random(n) * 100)
        else:
            act = p.active_indices()
            if act.size:
                p.despawn(rng.choice(act, size=min(act.size, int(rng.integers(1, 6))), replace=False))
        assert p.count == int(p.active.sum())


# --------------------------------------------------------------- queries / motion


def test_active_indices_sorted(pool):
    pool.spawn_many(np.zeros(5), np.zeros(5))
    pool.despawn([pool.active_indices()[1], pool.active_indices()[3]])
    act = pool.active_indices()
    assert act.dtype == np.int64
    assert act.tolist() == sorted(act.tolist()) and len(act) == 3
    assert act.tolist() == np.flatnonzero(pool.active).tolist()


def test_step_moves_only_active(pool):
    a = pool.spawn(0, 0, vx=10, vy=-20)
    b = pool.spawn(5, 5, vx=100, vy=100)
    pool.despawn(b)
    pool.step(0.5)
    assert (pool.x[a], pool.y[a]) == (5.0, -10.0)
    assert (pool.x[b], pool.y[b]) == (5.0, 5.0)


def test_cull_outside_rect(pool):
    inside = pool.spawn(50, 50)
    edge = pool.spawn(0, 100)
    out_left = pool.spawn(-1, 50)
    out_top = pool.spawn(50, -0.5)
    out_far = pool.spawn(101, 101)
    assert pool.cull(0, 0, 100, 100) == 3
    assert pool.active[inside] and pool.active[edge]
    assert not pool.active[[out_left, out_top, out_far]].any()
    assert pool.count == 2


def test_clear(pool):
    pool.spawn_many(np.zeros(8), np.zeros(8))
    pool.clear()
    assert pool.count == 0 and not pool.active.any()
    assert len(pool.spawn_many(np.zeros(8), np.zeros(8))) == 8


def test_arrays_are_never_reallocated():
    p = UnitPool(32)
    ids = {n: id(getattr(p, n)) for n in ("x", "y", "vx", "vy", "hp", "kind", "active")}
    p.spawn_many(np.zeros(40), np.zeros(40))
    p.step(0.1)
    p.despawn(p.active_indices()[:10])
    p.cull(0, 0, 1, 1)
    p.clear()
    assert {n: id(getattr(p, n)) for n in ids} == ids


# --------------------------------------------------------------- performance


def test_step_is_vectorised():
    p = UnitPool(4000)
    p.spawn_many(np.zeros(4000), np.zeros(4000), vx=1.0, vy=-1.0)
    t = time.perf_counter()
    for _ in range(1000):
        p.step(1 / 60)
    assert time.perf_counter() - t < 1.0, "1000 steps of 4000 units should take well under a second"
    assert np.allclose(p.x, 1000 / 60, atol=1e-2)


def test_bulk_spawn_and_despawn_are_vectorised():
    p = UnitPool(4000)
    t = time.perf_counter()
    for _ in range(50):
        idx = p.spawn_many(np.random.rand(4000), np.random.rand(4000))
        p.despawn(idx)
    assert time.perf_counter() - t < 0.5, "50 rounds of spawning and despawning 4000 units should be fast"
    assert p.count == 0
