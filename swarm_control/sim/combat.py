"""Combat: agents and bugs annihilate on contact; units that reach a base damage it.

CONTRACT (acceptance tests: tests/test_combat.py):

collide(blue, red, radius=UNIT_RADIUS) -> int
    An active agent and an active bug are in contact when their centres are closer than
    2 * radius (strictly). Contacting pairs annihilate: both units are despawned. Each unit is in at
    most one pair per call. The pairs removed must form a MAXIMAL matching: after the call, no active
    agent is in contact with any active bug. Returns the number of pairs removed (the same number of
    units leaves each pool).
    Must scale: use a spatial grid, sorting or similar. Never build an all-pairs
    (n_blue x n_red) distance matrix. Vectorise the bulk work; a loop over a few matching rounds
    or over grid neighbour offsets is fine, a loop over units is not.

hit_bases(blue, red, enemy_y=ENEMY_HIT_Y, player_y=PLAYER_BASE_Y) -> tuple[int, int]
    Despawns active agents with y <= enemy_y and active bugs with y >= player_y.
    Returns (agents that hit the fortress, bugs that hit the player's base).
"""

import numpy as np  # noqa: F401  (for the implementation)

from swarm_control import config
from swarm_control.sim.pool import UnitPool


def collide(blue: UnitPool, red: UnitPool, radius: float = config.UNIT_RADIUS) -> int:
    raise NotImplementedError


def hit_bases(
    blue: UnitPool, red: UnitPool, enemy_y: float = config.ENEMY_HIT_Y, player_y: float = config.PLAYER_BASE_Y
) -> tuple[int, int]:
    raise NotImplementedError
