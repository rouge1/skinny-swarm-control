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
    """Fixed-capacity pool of units stored in NumPy arrays."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        capacity = int(capacity)

        self.capacity = capacity
        self.x = np.zeros(capacity, dtype=np.float32)
        self.y = np.zeros(capacity, dtype=np.float32)
        self.vx = np.zeros(capacity, dtype=np.float32)
        self.vy = np.zeros(capacity, dtype=np.float32)
        self.hp = np.zeros(capacity, dtype=np.float32)
        self.kind = np.zeros(capacity, dtype=np.int8)
        self.active = np.zeros(capacity, dtype=np.bool_)
        self._count = 0

    @property
    def count(self) -> int:
        """Return the number of active units."""
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
        """Activate the first available slot and populate its fields."""
        if kind < -128 or kind > 127:
            raise ValueError("kind must fit in int8")
        slots = np.flatnonzero(~self.active)
        if slots.size == 0:
            return -1
        slot = int(slots[0])
        self.x[slot] = x
        self.y[slot] = y
        self.vx[slot] = vx
        self.vy[slot] = vy
        self.kind[slot] = kind
        self.hp[slot] = hp
        self.active[slot] = True
        self._count += 1
        return slot

    def spawn_many(
        self,
        x: object,
        y: object,
        vx: object = 0,
        vy: object = 0,
        kind: object = 0,
        hp: object = 1.0,
    ) -> np.ndarray:
        """Activate available slots for a batch of units."""
        x_array = np.asarray(x)
        y_array = np.asarray(y)
        if x_array.ndim != 1 or y_array.ndim != 1:
            raise ValueError("x and y must be one-dimensional")
        if x_array.size != y_array.size:
            raise ValueError("x and y must have equal length")

        requested = x_array.size

        def values(value: object, name: str) -> np.ndarray:
            array = np.asarray(value)
            if array.ndim == 0:
                return np.broadcast_to(array, requested)
            if array.ndim != 1 or array.size != requested:
                raise ValueError(f"{name} must be a scalar or have equal length to x")
            return array

        vx_array = values(vx, "vx")
        vy_array = values(vy, "vy")
        kind_array = values(kind, "kind")
        hp_array = values(hp, "hp")
        if np.any((kind_array < -128) | (kind_array > 127)):
            raise ValueError("kind must fit in int8")

        if requested == 0:
            return np.empty(0, dtype=np.int64)

        available = min(requested, self.capacity - self._count)
        if available == 0:
            return np.empty(0, dtype=np.int64)

        slots = np.flatnonzero(~self.active)[:available]
        self.x[slots] = x_array[:available]
        self.y[slots] = y_array[:available]
        self.vx[slots] = vx_array[:available]
        self.vy[slots] = vy_array[:available]
        self.kind[slots] = kind_array[:available]
        self.hp[slots] = hp_array[:available]
        self.active[slots] = True
        self._count += available
        return slots.astype(np.int64, copy=False)

    def despawn(self, idx: object) -> int:
        """Deactivate active slots in ``idx`` and return how many changed."""
        indices = np.asarray(idx, dtype=np.intp).reshape(-1)
        if indices.size == 0:
            return 0
        indices = np.unique(indices)
        indices = indices[(indices >= 0) & (indices < self.capacity)]
        active_indices = indices[self.active[indices]]
        count = int(active_indices.size)
        self.active[active_indices] = False
        self._count -= count
        return count

    def active_indices(self) -> np.ndarray:
        """Return active slot indices in ascending order."""
        return np.flatnonzero(self.active).astype(np.int64, copy=False)

    def step(self, dt: float) -> None:
        """Advance active units by ``dt``."""
        np.add(self.x, self.vx * dt, out=self.x, where=self.active)
        np.add(self.y, self.vy * dt, out=self.y, where=self.active)

    def cull(self, xmin: float, ymin: float, xmax: float, ymax: float) -> int:
        """Deactivate active units outside the inclusive rectangle."""
        outside = self.active & (
            (self.x < xmin) | (self.x > xmax) | (self.y < ymin) | (self.y > ymax)
        )
        count = int(outside.sum())
        if count == 0:
            return 0
        self.active[outside] = False
        self._count -= count
        return count

    def clear(self) -> None:
        """Deactivate all units."""
        self.active[:] = False
        self._count = 0
