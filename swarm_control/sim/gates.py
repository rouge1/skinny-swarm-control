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

import numpy as np  # noqa: F401  (for the implementation)

from swarm_control import config  # noqa: F401
from swarm_control.sim.pool import UnitPool  # noqa: F401


def move_gates(gates: list[dict], dt: float, field_w: float = config.FIELD_W) -> None:
    raise NotImplementedError


def apply_gates(pool, passed, gates, rng, scatter: float = config.GATE_SCATTER) -> int:
    raise NotImplementedError
