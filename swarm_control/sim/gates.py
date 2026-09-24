"""Multiplier gates: moving rectangles that copy the agents passing through them.

CONTRACT (acceptance tests: tests/test_gates.py):

A gate is a dict:
    {"x": float, "y": float, "w": float, "h": float,   # x, y = top-left corner, field px
     "op": "mul" | "add", "value": int >= 1, "label": str,
     "vx": float}                                      # horizontal speed px/s; optional, default 0

move_gates(gates, dt, field_w=FIELD_W) -> None
    In place: x += vx * dt, bouncing off the field walls. When the gate would cross the left wall
    (x < 0) it is reflected (x = -x) and vx flips sign; when it would cross the right wall
    (x + w > field_w) it is reflected (x = 2 * (field_w - w) - x) and vx flips sign.
    A gate without "vx" does not move.

apply_gates(pool, passed, gates, rng, scatter=GATE_SCATTER) -> int
    `passed` is a uint32 array of shape (pool.capacity,): bit i set means the unit in that slot has
    already passed gate i (at most MAX_GATES gates). For each gate i, in list order:
      - crossing = active units inside the rectangle (x <= ux <= x + w and y <= uy <= y + h,
        edges included) whose bit i is not set;
      - set bit i on the crossing units;
      - each crossing unit gets copies: value - 1 for "mul", value for "add";
      - copies are spawned with pool.spawn_many at parent x + uniform(-scatter, scatter) and
        parent y + uniform(-scatter, 0), with the parent's vx, vy, kind and hp;
      - every copy's `passed` entry is set to its parent's (bit i included), so copies never
        re-trigger the gate that made them;
      - if the pool fills up, spawn what fits (in parent order) and carry on.
    Returns the total number of copies spawned. All randomness comes from `rng`.
    The caller must zero `passed[slot]` for units it spawns itself (e.g. the launcher).
    Vectorised: no Python loop over units (a loop over gates is fine).
"""

import math
import numbers

import numpy as np

from swarm_control import config
from swarm_control.sim.pool import UnitPool


def _is_real(value: object) -> bool:
    """Return True for int/float values (excluding bool, including numpy scalars)."""
    if isinstance(value, bool) or isinstance(value, np.bool_):
        return False
    return isinstance(value, (numbers.Real, np.number))


def _validate_move_inputs(gates: list[dict], dt: float, field_w: float) -> None:
    """Validate move_gates inputs without changing any state."""
    if not isinstance(gates, (list, tuple)):
        raise TypeError("gates must be a list")
    if not _is_real(dt) or not math.isfinite(float(dt)) or float(dt) < 0:
        raise ValueError("dt must be a finite number >= 0")
    if not _is_real(field_w) or not math.isfinite(float(field_w)) or float(field_w) <= 0:
        raise ValueError("field_w must be a finite number > 0")
    for g in gates:
        if not isinstance(g, dict):
            raise TypeError("each gate must be a dict")
        if "x" not in g or "w" not in g:
            raise ValueError("gate must contain 'x' and 'w'")
        x, w = g["x"], g["w"]
        if not _is_real(x) or not math.isfinite(float(x)):
            raise ValueError("gate 'x' must be finite")
        if not _is_real(w) or not math.isfinite(float(w)) or float(w) < 0:
            raise ValueError("gate 'w' must be a finite number >= 0")
        if "vx" in g:
            vx = g["vx"]
            if not _is_real(vx) or not math.isfinite(float(vx)):
                raise ValueError("gate 'vx' must be finite")


def move_gates(gates: list[dict], dt: float, field_w: float = config.FIELD_W) -> None:
    """Move gates horizontally, bouncing off the field walls in place."""
    _validate_move_inputs(gates, dt, field_w)
    step = float(dt)
    width = float(field_w)
    for g in gates:
        if "vx" not in g:
            continue
        vx = float(g["vx"])
        if vx == 0.0 or step == 0.0:
            continue
        w = float(g["w"])
        limit = width - w
        if limit <= 0.0:
            g["x"] = 0.0
            continue
        x_new = float(g["x"]) + vx * step
        bounces = 0
        while x_new < 0.0 or x_new + w > width:
            if x_new < 0.0:
                x_new = -x_new
                vx = -vx
            else:
                x_new = 2.0 * limit - x_new
                vx = -vx
            bounces += 1
            if bounces > 1_000_000:  # absurd step; force inside to guarantee termination
                x_new = min(max(x_new, 0.0), limit)
                break
        g["x"] = x_new
        g["vx"] = vx


def _validate_gate_for_apply(g: object, index: int) -> tuple[float, float, float, float, str, int]:
    """Validate one gate for apply_gates and return its numeric fields."""
    if not isinstance(g, dict):
        raise TypeError(f"gate {index} must be a dict")
    for key in ("x", "y", "w", "h", "op", "value"):
        if key not in g:
            raise ValueError(f"gate {index} is missing {key!r}")
    x, y, w, h, op, value = g["x"], g["y"], g["w"], g["h"], g["op"], g["value"]
    if not _is_real(x) or not math.isfinite(float(x)):
        raise ValueError(f"gate {index} 'x' must be finite")
    if not _is_real(y) or not math.isfinite(float(y)):
        raise ValueError(f"gate {index} 'y' must be finite")
    if not _is_real(w) or not math.isfinite(float(w)) or float(w) < 0:
        raise ValueError(f"gate {index} 'w' must be a finite number >= 0")
    if not _is_real(h) or not math.isfinite(float(h)) or float(h) < 0:
        raise ValueError(f"gate {index} 'h' must be a finite number >= 0")
    if op not in ("mul", "add"):
        raise ValueError(f"gate {index} 'op' must be 'mul' or 'add'")
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or int(value) < 1:
        raise ValueError(f"gate {index} 'value' must be an int >= 1")
    return float(x), float(y), float(w), float(h), op, int(value)


def apply_gates(
    pool: UnitPool,
    passed: np.ndarray,
    gates: list[dict],
    rng: np.random.Generator,
    scatter: float = config.GATE_SCATTER,
) -> int:
    """Apply gates in order, spawning copies for crossing units."""
    if not isinstance(pool, UnitPool):
        raise TypeError("pool must be a UnitPool")
    if not isinstance(passed, np.ndarray) or passed.dtype != np.uint32:
        raise ValueError("passed must be a uint32 array")
    if passed.shape != (pool.capacity,):
        raise ValueError("passed must have shape (pool.capacity,)")
    if not isinstance(gates, (list, tuple)):
        raise TypeError("gates must be a list")
    if len(gates) > config.MAX_GATES:
        raise ValueError(f"at most {config.MAX_GATES} gates are supported")
    if not hasattr(rng, "uniform") or not callable(rng.uniform):
        raise TypeError("rng must provide a uniform method")
    if not _is_real(scatter) or not math.isfinite(float(scatter)) or float(scatter) < 0:
        raise ValueError("scatter must be a finite number >= 0")
    parsed = [_validate_gate_for_apply(g, i) for i, g in enumerate(gates)]
    if len(parsed) == 0:
        return 0

    scatter_f = float(scatter)
    total = 0
    active = pool.active
    px = pool.x
    py = pool.y
    for i, (gx, gy, gw, gh, op, value) in enumerate(parsed):
        bit = np.uint32(1 << i)
        inside = (
            (px >= gx) & (px <= gx + gw) & (py >= gy) & (py <= gy + gh) & active & ((passed & bit) == 0)
        )
        crossing = np.flatnonzero(inside)
        if crossing.size == 0:
            continue
        passed[crossing] |= bit
        per_parent = value - 1 if op == "mul" else value
        if per_parent <= 0:
            continue
        parents = np.repeat(crossing, per_parent)
        free = pool.capacity - pool.count
        if free <= 0:
            continue
        n_spawn = int(min(parents.size, free))
        take = parents[:n_spawn]
        dx = np.asarray(rng.uniform(-scatter_f, scatter_f, size=n_spawn), dtype=np.float64)
        dy = np.asarray(rng.uniform(-scatter_f, 0.0, size=n_spawn), dtype=np.float64)
        cx = px[take].astype(np.float64, copy=False) + dx
        cy = py[take].astype(np.float64, copy=False) + dy
        new_slots = pool.spawn_many(cx, cy, pool.vx[take], pool.vy[take], pool.kind[take], pool.hp[take])
        if new_slots.size > 0:
            passed[new_slots] = passed[take[: new_slots.size]]
            total += int(new_slots.size)
    return total
