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

import numpy as np

from swarm_control import config
from swarm_control.sim.pool import UnitPool


def collide(blue: UnitPool, red: UnitPool, radius: float = config.UNIT_RADIUS) -> int:
    """Despawn all units in a maximal set of contacting blue/red pairs."""
    if not isinstance(blue, UnitPool) or not isinstance(red, UnitPool):
        raise TypeError("blue and red must be UnitPool instances")
    try:
        radius = float(radius)
    except (TypeError, ValueError) as exc:
        raise ValueError("radius must be a finite non-negative number") from exc
    if not np.isfinite(radius) or radius < 0:
        raise ValueError("radius must be a finite non-negative number")
    if radius == 0 or blue.count == 0 or red.count == 0:
        return 0

    blue_slots = blue.active_indices()
    red_slots = red.active_indices()
    blue_valid = np.isfinite(blue.x[blue_slots]) & np.isfinite(blue.y[blue_slots])
    red_valid = np.isfinite(red.x[red_slots]) & np.isfinite(red.y[red_slots])
    blue_slots = blue_slots[blue_valid]
    red_slots = red_slots[red_valid]
    if blue_slots.size == 0 or red_slots.size == 0:
        return 0

    cell_size = 2.0 * radius
    with np.errstate(over="ignore", invalid="ignore"):
        blue_cell_x = np.floor(blue.x[blue_slots] / cell_size)
        blue_cell_y = np.floor(blue.y[blue_slots] / cell_size)
        red_cell_x = np.floor(red.x[red_slots] / cell_size)
        red_cell_y = np.floor(red.y[red_slots] / cell_size)

    # Clipping keeps conversion to int64 defined for unusually large coordinates.
    int_min = np.iinfo(np.int64).min
    int_max = np.iinfo(np.int64).max
    blue_cell_x = np.clip(blue_cell_x, int_min, int_max).astype(np.int64)
    blue_cell_y = np.clip(blue_cell_y, int_min, int_max).astype(np.int64)
    red_cell_x = np.clip(red_cell_x, int_min, int_max).astype(np.int64)
    red_cell_y = np.clip(red_cell_y, int_min, int_max).astype(np.int64)
    min_cell_x = min(int(blue_cell_x.min()), int(red_cell_x.min()))
    max_cell_x = max(int(blue_cell_x.max()), int(red_cell_x.max()))
    min_cell_y = min(int(blue_cell_y.min()), int(red_cell_y.min()))
    max_cell_y = max(int(blue_cell_y.max()), int(red_cell_y.max()))
    cell_rows = max_cell_y - min_cell_y + 1
    cell_columns = max_cell_x - min_cell_x + 1
    if cell_rows > int_max // cell_columns:
        raise ValueError("active coordinates span too many collision cells")

    red_keys = (red_cell_x - min_cell_x) * cell_rows + (red_cell_y - min_cell_y)
    red_order = np.argsort(red_keys, kind="stable")
    sorted_red_keys = red_keys[red_order]
    candidate_blue: list[np.ndarray] = []
    candidate_red: list[np.ndarray] = []
    blue_numbers = np.arange(blue_slots.size, dtype=np.int64)

    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            query = (blue_cell_x + dx - min_cell_x) * cell_rows + (
                blue_cell_y + dy - min_cell_y
            )
            left = np.searchsorted(sorted_red_keys, query, side="left")
            right = np.searchsorted(sorted_red_keys, query, side="right")
            counts = right - left
            total = int(counts.sum())
            if total == 0:
                continue
            starts = np.repeat(left, counts)
            offsets = np.arange(total, dtype=np.int64)
            group_starts = np.repeat(np.cumsum(counts) - counts, counts)
            candidate_blue.append(np.repeat(blue_numbers, counts))
            candidate_red.append(red_order[starts + offsets - group_starts])

    if not candidate_blue:
        return 0
    pair_blue = np.concatenate(candidate_blue)
    pair_red = np.concatenate(candidate_red)
    dx = blue.x[blue_slots[pair_blue]] - red.x[red_slots[pair_red]]
    dy = blue.y[blue_slots[pair_blue]] - red.y[red_slots[pair_red]]
    in_contact = dx * dx + dy * dy < cell_size * cell_size
    pair_blue = pair_blue[in_contact]
    pair_red = pair_red[in_contact]

    matched_blue: list[np.ndarray] = []
    matched_red: list[np.ndarray] = []
    while pair_blue.size:
        order = np.lexsort((pair_red, pair_blue))
        ordered_blue = pair_blue[order]
        first_blue = np.r_[True, ordered_blue[1:] != ordered_blue[:-1]]
        selected = order[first_blue]
        selected_red = pair_red[selected]
        red_order_for_selection = np.argsort(selected_red, kind="stable")
        first_red = np.r_[
            True,
            selected_red[red_order_for_selection][1:]
            != selected_red[red_order_for_selection][:-1],
        ]
        selected = selected[red_order_for_selection[first_red]]
        if selected.size == 0:
            break
        matched_blue.append(pair_blue[selected])
        matched_red.append(pair_red[selected])
        remaining = ~np.isin(pair_blue, pair_blue[selected]) & ~np.isin(
            pair_red, pair_red[selected]
        )
        pair_blue = pair_blue[remaining]
        pair_red = pair_red[remaining]

    if not matched_blue:
        return 0
    matched_blue_array = np.concatenate(matched_blue)
    matched_red_array = np.concatenate(matched_red)
    blue.despawn(blue_slots[matched_blue_array])
    red.despawn(red_slots[matched_red_array])
    return int(matched_blue_array.size)


def hit_bases(
    blue: UnitPool, red: UnitPool, enemy_y: float = config.ENEMY_HIT_Y, player_y: float = config.PLAYER_BASE_Y
) -> tuple[int, int]:
    """Despawn units that have reached either base and return both hit counts."""
    if not isinstance(blue, UnitPool) or not isinstance(red, UnitPool):
        raise TypeError("blue and red must be UnitPool instances")
    try:
        enemy_y = float(enemy_y)
        player_y = float(player_y)
    except (TypeError, ValueError) as exc:
        raise ValueError("base lines must be finite numbers") from exc
    if not np.isfinite(enemy_y) or not np.isfinite(player_y):
        raise ValueError("base lines must be finite numbers")

    blue_slots = blue.active_indices()
    red_slots = red.active_indices()
    blue_hits = blue_slots[blue.y[blue_slots] <= enemy_y]
    red_hits = red_slots[red.y[red_slots] >= player_y]
    blue_count = blue.despawn(blue_hits)
    red_count = red.despawn(red_hits)
    return blue_count, red_count
