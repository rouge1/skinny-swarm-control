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

import numpy as np


class UnitPool:
    """Pre-allocated pool of units stored in parallel numpy arrays."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = int(capacity)
        self.x = np.zeros(capacity, dtype=np.float32)
        self.y = np.zeros(capacity, dtype=np.float32)
        self.vx = np.zeros(capacity, dtype=np.float32)
        self.vy = np.zeros(capacity, dtype=np.float32)
        self.hp = np.zeros(capacity, dtype=np.float32)
        self.kind = np.zeros(capacity, dtype=np.int8)
        self.active = np.zeros(capacity, dtype=np.bool_)
        # Free slots occupy the first `_n_free` entries of `_free`.
        self._free = np.arange(capacity, dtype=np.int64)
        self._n_free = self.capacity

    @property
    def count(self) -> int:
        """Number of active units (O(1))."""
        return self.capacity - self._n_free

    def spawn(
        self,
        x: float,
        y: float,
        vx: float = 0.0,
        vy: float = 0.0,
        kind: int = 0,
        hp: float = 1.0,
    ) -> int:
        """Activate a free slot; return its index, or -1 when full."""
        if self._n_free == 0:
            return -1
        self._n_free -= 1
        i = int(self._free[self._n_free])
        self.x[i] = x
        self.y[i] = y
        self.vx[i] = vx
        self.vy[i] = vy
        self.kind[i] = kind
        self.hp[i] = hp
        self.active[i] = True
        return i

    def spawn_many(
        self,
        x: object,
        y: object,
        vx: object = 0.0,
        vy: object = 0.0,
        kind: object = 0,
        hp: object = 1.0,
    ) -> np.ndarray:
        """Spawn up to the number of free slots; return the slots used, in order."""
        xa = np.asarray(x)
        n = xa.shape[0] if xa.ndim else 1
        m = min(n, self._n_free)
        if m <= 0:
            return np.empty(0, dtype=np.int64)
        start = self._n_free - m
        slots = self._free[start:self._n_free][::-1].copy()
        self._n_free = start
        self.x[slots] = np.broadcast_to(np.asarray(x, dtype=np.float32), (n,))[:m]
        self.y[slots] = np.broadcast_to(np.asarray(y, dtype=np.float32), (n,))[:m]
        self.vx[slots] = np.broadcast_to(np.asarray(vx, dtype=np.float32), (n,))[:m]
        self.vy[slots] = np.broadcast_to(np.asarray(vy, dtype=np.float32), (n,))[:m]
        self.kind[slots] = np.broadcast_to(np.asarray(kind, dtype=np.int8), (n,))[:m]
        self.hp[slots] = np.broadcast_to(np.asarray(hp, dtype=np.float32), (n,))[:m]
        self.active[slots] = True
        return slots

    def despawn(self, idx: object) -> int:
        """Deactivate the given slots; ignore inactive/repeated ones. Returns count."""
        idxs = np.atleast_1d(np.asarray(idx, dtype=np.int64)).ravel()
        if idxs.size == 0:
            return 0
        valid = idxs[(idxs >= 0) & (idxs < self.capacity)]
        if valid.size == 0:
            return 0
        # Deduplicate within the batch and keep only currently active slots.
        marked = np.zeros(self.capacity, dtype=np.bool_)
        marked[valid] = True
        newly = marked & self.active
        freed = np.flatnonzero(newly)
        k = freed.size
        if k == 0:
            return 0
        self.active[freed] = False
        self._free[self._n_free:self._n_free + k] = freed
        self._n_free += k
        return int(k)

    def active_indices(self) -> np.ndarray:
        """Indices of active slots, ascending."""
        return np.flatnonzero(self.active)

    def step(self, dt: float) -> None:
        """Advance active units by their velocity for `dt`."""
        act = self.active
        self.x[act] += self.vx[act] * dt
        self.y[act] += self.vy[act] * dt

    def cull(self, xmin: float, ymin: float, xmax: float, ymax: float) -> int:
        """Despawn active units strictly outside the rectangle; return how many."""
        outside = (
            (self.x < xmin) | (self.x > xmax) | (self.y < ymin) | (self.y > ymax)
        ) & self.active
        freed = np.flatnonzero(outside)
        k = freed.size
        if k == 0:
            return 0
        self.active[freed] = False
        self._free[self._n_free:self._n_free + k] = freed
        self._n_free += k
        return int(k)

    def clear(self) -> None:
        """Despawn everything."""
        self.active[:] = False
        self._n_free = self.capacity
