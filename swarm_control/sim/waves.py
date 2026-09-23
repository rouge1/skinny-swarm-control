"""Bug waves and level data.

CONTRACT (acceptance tests: tests/test_waves.py):

A wave is a dict:
    {"t": float >= 0,       # seconds after the level starts
     "count": int >= 1,     # bugs in the wave
     "x": float,            # centre of the wave
     "spread": float >= 0,  # bugs are spread uniformly over [x - spread/2, x + spread/2]
     "speed": float > 0,    # px/s downward
     "hp": float,           # optional, default 1.0
     "kind": int}           # optional, default 0

WaveSpawner(waves, rng)
    .update(t, red, spawn_y=BUG_SPAWN_Y) -> int
        Spawns every wave with wave["t"] <= t that has not spawned yet, in time order, and returns how
        many bugs were spawned. Bug x is drawn uniformly as above and then clipped to
        [UNIT_RADIUS, FIELD_W - UNIT_RADIUS]; y = spawn_y + uniform(0, 30); vx = 0; vy = speed.
        If the pool is full, the rest of that wave is lost (the wave still counts as spawned).
    .remaining -> int   waves not yet spawned
    .done() -> bool     True when every wave has spawned
    The spawner does not modify the `waves` list it was given. All randomness comes from `rng`.

A level is a dict:
    {"id": int >= 1, "name": str, "enemy_hp": number > 0, "player_hp": number > 0,
     "reward": int >= 0,                  # tokens for winning
     "gates": [gate, ...],                # see gates.py; at most MAX_GATES; inside the field
     "waves": [wave, ...]}

LEVELS: list of at least 3 levels with ids 1, 2, 3, ... in order, getting harder: more total bugs
    and a bigger enemy_hp in each level than the one before. Every gate label reads like the theme,
    e.g. "x2 fork", "+5 subagents", "x3 worktree".
get_level(n) -> dict       a deep copy of level n (1-based); KeyError if there is no level n.
validate_level(level) -> list[str]   problems with a level dict; empty means valid.
"""

import numpy as np  # noqa: F401  (for the implementation)

from swarm_control import config  # noqa: F401
from swarm_control.sim.pool import UnitPool  # noqa: F401

LEVELS: list[dict] = []


class WaveSpawner:
    def __init__(self, waves: list[dict], rng) -> None:
        raise NotImplementedError


def get_level(n: int) -> dict:
    raise NotImplementedError


def validate_level(level: dict) -> list[str]:
    raise NotImplementedError
