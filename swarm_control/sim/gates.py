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

import numpy as np

from swarm_control import config
from swarm_control.sim.pool import UnitPool

_NUM_TYPES = (int, float, np.integer, np.floating)


def _as_number(value: object, name: str) -> float:
    """Coerce a real scalar to float; TypeError for wrong types, ValueError if not finite."""
    if isinstance(value, bool) or not isinstance(value, _NUM_TYPES):
        raise TypeError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def move_gates(gates: list[dict], dt: float, field_w: float = config.FIELD_W) -> None:
    """Move gates horizontally, bouncing off the field walls in place."""
    if not isinstance(gates, (list, tuple)):
        raise TypeError("gates must be a list")
    step = _as_number(dt, "dt")
    if step < 0:
        raise ValueError("dt must be >= 0")
    width = _as_number(field_w, "field_w")
    if width <= 0:
        raise ValueError("field_w must be > 0")
    for g in gates:
        if not isinstance(g, dict):
            raise TypeError("each gate must be a dict")
        try:
            raw_x = g["x"]
            raw_w = g["w"]
        except KeyError as exc:
            raise ValueError(f"gate is missing {exc.args[0]!r}") from None
        x = _as_number(raw_x, "gate 'x'")
        w = _as_number(raw_w, "gate 'w'")
        if w < 0:
            raise ValueError("gate 'w' must be >= 0")
        limit = width - w
        if limit <= 0.0:
            # Wider than the field: pin to the left wall, moving or not.
            g["x"] = 0.0
            continue
        if "vx" not in g:
            continue
        vx = _as_number(g["vx"], "gate 'vx'")
        if vx == 0.0 or step == 0.0:
            continue
        # Clamp into range before integrating so a gate starting outside cannot jump.
        x0 = min(max(x, 0.0), limit)
        period = 2.0 * limit
        folded = (x0 + vx * step) % period
        if folded > limit:
            g["x"] = period - folded
            g["vx"] = -vx
        else:
            g["x"] = folded
            g["vx"] = vx


def _parse_gate(g: object, index: int) -> tuple[float, float, float, float, str, int]:
    """Validate one gate for apply_gates and return its numeric fields."""
    if not isinstance(g, dict):
        raise TypeError(f"gate {index} must be a dict")
    try:
        raw_x = g["x"]
        raw_y = g["y"]
        raw_w = g["w"]
        raw_h = g["h"]
        op = g["op"]
        value = g["value"]
    except KeyError as exc:
        raise ValueError(f"gate {index} is missing {exc.args[0]!r}") from None
    gx = _as_number(raw_x, f"gate {index} 'x'")
    gy = _as_number(raw_y, f"gate {index} 'y'")
    gw = _as_number(raw_w, f"gate {index} 'w'")
    gh = _as_number(raw_h, f"gate {index} 'h'")
    if gw < 0 or gh < 0:
        raise ValueError(f"gate {index} 'w' and 'h' must be >= 0")
    if op not in ("mul", "add"):
        raise ValueError(f"gate {index} 'op' must be 'mul' or 'add'")
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or int(value) < 1:
        raise ValueError(f"gate {index} 'value' must be an int >= 1")
    return gx, gy, gw, gh, op, int(value)


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
    if not isinstance(passed, np.ndarray):
        raise TypeError("passed must be a uint32 array")
    if passed.dtype != np.uint32:
        raise TypeError("passed must be a uint32 array")
    if passed.shape != (pool.capacity,):
        raise ValueError("passed must have shape (pool.capacity,)")
    if not isinstance(gates, (list, tuple)):
        raise TypeError("gates must be a list")
    if len(gates) > config.MAX_GATES:
        raise ValueError(f"at most {config.MAX_GATES} gates are supported")
    if not callable(getattr(rng, "uniform", None)):
        raise TypeError("rng must provide a uniform method")
    scatter_f = _as_number(scatter, "scatter")
    if scatter_f < 0:
        raise ValueError("scatter must be >= 0")
    parsed = [_parse_gate(g, i) for i, g in enumerate(gates)]
    if len(parsed) == 0:
        return 0

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
        free = pool.capacity - pool.count
        if free <= 0:
            continue
        # Cap first: only repeat as many parents as can fit, so huge values never
        # allocate more than ~2 * free entries and never overflow.
        need = (free + per_parent - 1) // per_parent
        kept = crossing[:need] if need < crossing.size else crossing
        each = per_parent if per_parent < free else free
        take = np.repeat(kept, each)[:free]
        n_spawn = int(take.size)
        if n_spawn == 0:
            continue
        dx = rng.uniform(-scatter_f, scatter_f, size=n_spawn)
        dy = rng.uniform(-scatter_f, 0.0, size=n_spawn)
        new_slots = pool.spawn_many(
            pool.x[take] + dx,
            pool.y[take] + dy,
            pool.vx[take],
            pool.vy[take],
            pool.kind[take],
            pool.hp[take],
        )
        if new_slots.size > 0:
            passed[new_slots] = passed[take[: new_slots.size]]
            total += int(new_slots.size)
    return total
