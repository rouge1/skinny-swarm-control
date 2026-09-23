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

import operator

import numpy as np


class UnitPool:
    """Pre-allocated struct-of-arrays pool with O(1) count."""

    def __init__(self, capacity: int) -> None:
        """Allocate arrays once; start empty."""
        capacity = operator.index(capacity)
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity: int = int(capacity)
        self.x: np.ndarray = np.zeros(self.capacity, dtype=np.float32)
        self.y: np.ndarray = np.zeros(self.capacity, dtype=np.float32)
        self.vx: np.ndarray = np.zeros(self.capacity, dtype=np.float32)
        self.vy: np.ndarray = np.zeros(self.capacity, dtype=np.float32)
        self.hp: np.ndarray = np.zeros(self.capacity, dtype=np.float32)
        self.kind: np.ndarray = np.zeros(self.capacity, dtype=np.int8)
        self.active: np.ndarray = np.zeros(self.capacity, dtype=np.bool_)
        self._count: int = 0

    @property
    def count(self) -> int:
        """Number of active units (O(1))."""
        return self._count

    def spawn(
        self,
        x: float,
        y: float,
        vx: float = 0,
        vy: float = 0,
        kind: int = 0,
        hp: float = 1.0,
    ) -> int:
        """Activate one free slot; return its index or -1 when full."""
        free = np.flatnonzero(~self.active)
        if free.size == 0:
            return -1
        i = int(free[0])
        self.x[i] = np.float32(x)
        self.y[i] = np.float32(y)
        self.vx[i] = np.float32(vx)
        self.vy[i] = np.float32(vy)
        self.kind[i] = np.int8(kind)
        self.hp[i] = np.float32(hp)
        self.active[i] = True
        self._count += 1
        return i

    def spawn_many(
        self,
        x: np.ndarray,
        y: np.ndarray,
        vx: float | np.ndarray = 0.0,
        vy: float | np.ndarray = 0.0,
        kind: int | np.ndarray = 0,
        hp: float | np.ndarray = 1.0,
    ) -> np.ndarray:
        """Activate up to len(x) free slots, in order; return slots used."""
        xs = np.asarray(x).ravel()
        ys = np.asarray(y).ravel()
        n_req = int(xs.size)
        if n_req == 0:
            return np.empty(0, dtype=np.int64)
        free = np.flatnonzero(~self.active)
        n = n_req if n_req < free.size else int(free.size)
        if n == 0:
            return np.empty(0, dtype=np.int64)
        slots = free[:n].astype(np.int64, copy=True)
        self.x[slots] = xs[:n].astype(np.float32, copy=False)
        self.y[slots] = ys[:n].astype(np.float32, copy=False)
        self.vx[slots] = _broadcast(np.asarray(vx).ravel(), n, np.float32)
        self.vy[slots] = _broadcast(np.asarray(vy).ravel(), n, np.float32)
        self.kind[slots] = _broadcast(np.asarray(kind).ravel(), n, np.int8)
        self.hp[slots] = _broadcast(np.asarray(hp).ravel(), n, np.float32)
        self.active[slots] = True
        self._count += n
        return slots

    def despawn(self, idx: int | np.ndarray) -> int:
        """Deactivate slots; ignore inactive/duplicates; return count."""
        arr = np.asarray(idx).ravel()
        if arr.size == 0:
            return 0
        arr = arr.astype(np.int64, copy=False)
        valid = arr[(arr >= 0) & (arr < self.capacity)]
        if valid.size == 0:
            return 0
        uniq = np.unique(valid)
        was_active = self.active[uniq]
        n = int(np.count_nonzero(was_active))
        if n == 0:
            return 0
        self.active[uniq[was_active]] = False
        self._count -= n
        return n

    def active_indices(self) -> np.ndarray:
        """Active slots, ascending."""
        return np.flatnonzero(self.active).astype(np.int64, copy=False)

    def step(self, dt: float) -> None:
        """Advance active units: x += vx*dt, y += vy*dt."""
        act = self.active
        delta = np.float32(dt)
        self.x[act] += self.vx[act] * delta
        self.y[act] += self.vy[act] * delta

    def cull(self, xmin: float, ymin: float, xmax: float, ymax: float) -> int:
        """Despawn active units strictly outside the rect; return count."""
        out = (
            self.active
            & ((self.x < xmin) | (self.x > xmax) | (self.y < ymin) | (self.y > ymax))
        )
        n = int(np.count_nonzero(out))
        if n == 0:
            return 0
        self.active[out] = False
        self._count -= n
        return n

    def clear(self) -> None:
        """Despawn everything."""
        self.active[:] = False
        self._count = 0


def _broadcast(a: np.ndarray, n: int, dtype: np.dtype) -> np.ndarray:
    """Broadcast scalar-or-array `a` to length `n` with `dtype`."""
    if a.size == 1:
        return np.full(n, a[0], dtype=dtype)
    return a[:n].astype(dtype, copy=False)
