"""Fixed-capacity unit pool (struct of numpy arrays).

Thousands of agents and bugs are alive at once, so units are never created
or destroyed as Python objects. A pool pre-allocates arrays for `capacity`
units; spawning activates a free slot and despawning returns it.

CONTRACT (tests/test_pool.py is the acceptance test):

    pool = UnitPool(capacity)
    pool.capacity                     -> int
    pool.x, pool.y, pool.vx, pool.vy, pool.hp   float32 arrays, shape (capacity,)
    pool.kind                         int8 array, shape (capacity,)
    pool.active                       bool array, shape (capacity,)
    pool.count                        -> int, number of active units (O(1))
    pool.spawn(x, y, vx=0, vy=0, kind=0, hp=1.0) -> slot index, or -1 when full
    pool.spawn_many(x, y, vx=0, vy=0, kind=0, hp=1.0) -> int64 array of slots used
        x and y are equal-length array-likes; the other arguments are scalars
        or arrays of that length. Spawns min(len(x), free slots) units, in order.
    pool.despawn(idx) -> int          idx is an int or array-like of ints;
        inactive or repeated indices are ignored; returns how many were despawned.
    pool.active_indices() -> int64 array of active slots, ascending
    pool.step(dt)                     x += vx*dt, y += vy*dt for active units only
    pool.cull(xmin, ymin, xmax, ymax) -> int   despawn active units strictly
        outside the rectangle (points on the edge stay); returns how many.
    pool.clear()                      despawn everything

Rules: the arrays are allocated once and never replaced (same objects for the
life of the pool); freed slots are reused; all bulk operations are vectorised.
"""

import numpy as np  # noqa: F401  (for the implementation)


class UnitPool:
    def __init__(self, capacity: int) -> None:
        raise NotImplementedError
