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
    blue_valid = (
        np.isfinite(blue.x[blue_slots])
        & np.isfinite(blue.y[blue_slots])
        & (np.abs(blue.x[blue_slots]) <= 1.0e12)
        & (np.abs(blue.y[blue_slots]) <= 1.0e12)
    )
    red_valid = (
        np.isfinite(red.x[red_slots])
        & np.isfinite(red.y[red_slots])
        & (np.abs(red.x[red_slots]) <= 1.0e12)
        & (np.abs(red.y[red_slots]) <= 1.0e12)
    )
    blue_slots = blue_slots[blue_valid]
    red_slots = red_slots[red_valid]
    if blue_slots.size == 0 or red_slots.size == 0:
        return 0

    cell_size = radius
    blue_x = np.floor(blue.x[blue_slots] / cell_size).astype(np.int64)
    blue_y = np.floor(blue.y[blue_slots] / cell_size).astype(np.int64)
    red_x = np.floor(red.x[red_slots] / cell_size).astype(np.int64)
    red_y = np.floor(red.y[red_slots] / cell_size).astype(np.int64)
    min_x = min(int(blue_x.min()), int(red_x.min()))
    max_x = max(int(blue_x.max()), int(red_x.max()))
    min_y = min(int(blue_y.min()), int(red_y.min()))
    max_y = max(int(blue_y.max()), int(red_y.max()))
    rows = max_y - min_y + 1
    columns = max_x - min_x + 1
    int_max = np.iinfo(np.int64).max
    if rows > int_max // columns:
        return 0

    blue_keys = (blue_x - min_x) * rows + (blue_y - min_y)
    red_keys = (red_x - min_x) * rows + (red_y - min_y)
    blue_order = np.argsort(blue_keys, kind="stable")
    red_order = np.argsort(red_keys, kind="stable")
    sorted_blue_keys = blue_keys[blue_order]
    sorted_red_keys = red_keys[red_order]

    # A radius-sized cell has a diagonal shorter than the contact diameter.
    red_left = np.searchsorted(sorted_red_keys, sorted_blue_keys, side="left")
    red_right = np.searchsorted(sorted_red_keys, sorted_blue_keys, side="right")
    blue_group_start = np.flatnonzero(
        np.r_[True, sorted_blue_keys[1:] != sorted_blue_keys[:-1]]
    )
    blue_group_counts = np.diff(np.r_[blue_group_start, sorted_blue_keys.size])
    blue_group_starts = np.repeat(blue_group_start, blue_group_counts)
    blue_rank = np.arange(sorted_blue_keys.size) - blue_group_starts
    same_cell = blue_rank < (red_right - red_left)
    matched_blue = [blue_order[same_cell]]
    matched_red = [red_order[red_left[same_cell] + blue_rank[same_cell]]]
    blue_available = np.ones(blue_slots.size, dtype=np.bool_)
    red_available = np.ones(red_slots.size, dtype=np.bool_)
    blue_available[matched_blue[0]] = False
    red_available[matched_red[0]] = False

    work_blue = np.flatnonzero(blue_available)
    work_red = np.flatnonzero(red_available)
    if work_blue.size and work_red.size:
        candidate_blue: list[np.ndarray] = []
        candidate_red: list[np.ndarray] = []
        work_x = blue_x[work_blue]
        work_y = blue_y[work_blue]
        work_red_keys = red_keys[work_red]
        work_red_order = np.argsort(work_red_keys, kind="stable")
        sorted_work_red_keys = work_red_keys[work_red_order]
        work_numbers = np.arange(work_blue.size, dtype=np.int64)
        for offset_x in range(-2, 3):
            query_x = work_x + offset_x
            x_in_bounds = (query_x >= min_x) & (query_x <= max_x)
            for offset_y in range(-2, 3):
                query_y = work_y + offset_y
                in_bounds = x_in_bounds & (query_y >= min_y) & (query_y <= max_y)
                query = (query_x - min_x) * rows + (query_y - min_y)
                left = np.searchsorted(sorted_work_red_keys, query, side="left")
                right = np.searchsorted(sorted_work_red_keys, query, side="right")
                counts = np.where(in_bounds, right - left, 0)
                total = int(counts.sum())
                if total == 0:
                    continue
                starts = np.repeat(left, counts)
                offsets = np.arange(total, dtype=np.int64)
                group_starts = np.repeat(np.cumsum(counts) - counts, counts)
                candidate_blue.append(np.repeat(work_numbers, counts))
                candidate_red.append(work_red_order[starts + offsets - group_starts])

        if candidate_blue:
            pair_blue = np.concatenate(candidate_blue)
            pair_red = np.concatenate(candidate_red)
            blue_coords = work_blue[pair_blue]
            red_coords = work_red[pair_red]
            distance_x = blue.x[blue_slots[blue_coords]] - red.x[red_slots[red_coords]]
            distance_y = blue.y[blue_slots[blue_coords]] - red.y[red_slots[red_coords]]
            in_contact = distance_x * distance_x + distance_y * distance_y < (2 * radius) ** 2
            pair_blue = blue_coords[in_contact]
            pair_red = red_coords[in_contact]
            if pair_blue.size:
                edge_order = np.lexsort((pair_red, pair_blue))
                pair_blue = pair_blue[edge_order]
                pair_red = pair_red[edge_order]
                round_number = 0
                while pair_blue.size:
                    starts = np.flatnonzero(
                        np.r_[True, pair_blue[1:] != pair_blue[:-1]]
                    )
                    counts = np.diff(np.r_[starts, pair_blue.size])
                    proposed = starts + (pair_blue[starts] + round_number) % counts
                    proposed_red = pair_red[proposed]
                    _, first = np.unique(proposed_red, return_index=True)
                    selected = proposed[first]
                    selected_blue = pair_blue[selected]
                    selected_red = pair_red[selected]
                    matched_blue.append(selected_blue)
                    matched_red.append(selected_red)
                    blue_available[selected_blue] = False
                    red_available[selected_red] = False
                    remaining = blue_available[pair_blue] & red_available[pair_red]
                    pair_blue = pair_blue[remaining]
                    pair_red = pair_red[remaining]
                    round_number += 1

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
