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

import copy
import math
import numbers

import numpy as np

from swarm_control import config
from swarm_control.sim.pool import UnitPool

LEVELS: list[dict] = [
    {
        "id": 1,
        "name": "First Contact",
        "enemy_hp": 80.0,
        "player_hp": 20.0,
        "reward": 10,
        "gates": [
            {"x": 80, "y": 300, "w": 120, "h": 30, "op": "mul", "value": 2, "vx": 40, "label": "x2 fork"},
            {
                "x": 340,
                "y": 600,
                "w": 120,
                "h": 30,
                "op": "add",
                "value": 4,
                "vx": -35,
                "label": "+4 subagents",
            },
        ],
        "waves": [
            {"t": 0.0, "count": 6, "x": 270, "spread": 300, "speed": 100},
            {"t": 4.0, "count": 8, "x": 270, "spread": 420, "speed": 110},
            {"t": 8.0, "count": 10, "x": 270, "spread": 500, "speed": 120},
        ],
    },
    {
        "id": 2,
        "name": "Parallel Front",
        "enemy_hp": 200.0,
        "player_hp": 25.0,
        "reward": 25,
        "gates": [
            {"x": 40, "y": 280, "w": 110, "h": 28, "op": "mul", "value": 2, "vx": 45, "label": "x2 fork"},
            {
                "x": 380,
                "y": 470,
                "w": 120,
                "h": 28,
                "op": "add",
                "value": 5,
                "vx": -40,
                "label": "+5 subagents",
            },
            {
                "x": 200,
                "y": 680,
                "w": 110,
                "h": 28,
                "op": "mul",
                "value": 3,
                "vx": 30,
                "label": "x3 worktree",
            },
        ],
        "waves": [
            {"t": 0.0, "count": 8, "x": 200, "spread": 320, "speed": 100},
            {"t": 3.5, "count": 10, "x": 340, "spread": 380, "speed": 110},
            {"t": 7.0, "count": 10, "x": 200, "spread": 480, "speed": 120},
            {"t": 11.0, "count": 12, "x": 340, "spread": 520, "speed": 130},
        ],
    },
    {
        "id": 3,
        "name": "Swarm Cascade",
        "enemy_hp": 450.0,
        "player_hp": 30.0,
        "reward": 50,
        "gates": [
            {"x": 40, "y": 260, "w": 110, "h": 26, "op": "mul", "value": 2, "vx": 50, "label": "x2 fork"},
            {
                "x": 390,
                "y": 420,
                "w": 120,
                "h": 26,
                "op": "add",
                "value": 6,
                "vx": -45,
                "label": "+6 branch clones",
            },
            {
                "x": 180,
                "y": 580,
                "w": 110,
                "h": 26,
                "op": "mul",
                "value": 3,
                "vx": 40,
                "label": "x3 worktree",
            },
            {
                "x": 360,
                "y": 740,
                "w": 110,
                "h": 26,
                "op": "add",
                "value": 5,
                "vx": -35,
                "label": "+5 parallel agents",
            },
        ],
        "waves": [
            {"t": 0.0, "count": 12, "x": 270, "spread": 360, "speed": 105},
            {"t": 3.0, "count": 14, "x": 170, "spread": 440, "speed": 115},
            {"t": 6.5, "count": 16, "x": 370, "spread": 500, "speed": 125},
            {"t": 10.0, "count": 18, "x": 270, "spread": 540, "speed": 135},
        ],
    },
]

_GATE_MIN_Y = float(config.ENEMY_HIT_Y)
_GATE_MAX_Y = float(config.LAUNCHER_Y - config.MUZZLE_OFFSET)
_GATE_MIN_H = config.AGENT_SPEED / config.TICK_HZ


def _finite_number(value: object) -> bool:
    """Return True for finite real numbers (bools and NaN/inf excluded)."""
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(value)


def _finite_int(value: object) -> bool:
    """Return True for integers (bools excluded)."""
    return isinstance(value, numbers.Integral) and not isinstance(value, bool)


def _wave_problems(wave: object, where: str) -> list[str]:
    """Return a list of contract violations for a single wave dict."""
    if not isinstance(wave, dict):
        return [f"{where}: wave must be a dict"]
    problems: list[str] = []
    if "t" not in wave:
        problems.append(f"{where}: missing 't'")
    elif not _finite_number(wave["t"]) or wave["t"] < 0:
        problems.append(f"{where}: 't' must be a finite number >= 0")
    if "count" not in wave:
        problems.append(f"{where}: missing 'count'")
    elif not _finite_int(wave["count"]) or wave["count"] < 1:
        problems.append(f"{where}: 'count' must be an int >= 1")
    if "x" not in wave:
        problems.append(f"{where}: missing 'x'")
    elif not _finite_number(wave["x"]):
        problems.append(f"{where}: 'x' must be a finite number")
    if "spread" not in wave:
        problems.append(f"{where}: missing 'spread'")
    elif not _finite_number(wave["spread"]) or wave["spread"] < 0:
        problems.append(f"{where}: 'spread' must be a finite number >= 0")
    if "speed" not in wave:
        problems.append(f"{where}: missing 'speed'")
    elif not _finite_number(wave["speed"]) or wave["speed"] <= 0:
        problems.append(f"{where}: 'speed' must be a finite number > 0")
    if "hp" in wave and (not _finite_number(wave["hp"]) or wave["hp"] <= 0):
        problems.append(f"{where}: 'hp' must be a finite number > 0")
    if "kind" in wave and (not _finite_int(wave["kind"]) or not -128 <= wave["kind"] <= 127):
        problems.append(f"{where}: 'kind' must be an int that fits in int8")
    return problems


def _gate_problems(gate: object, where: str) -> list[str]:
    """Return a list of contract violations for a single gate dict."""
    if not isinstance(gate, dict):
        return [f"{where}: gate must be a dict"]
    problems: list[str] = []
    for key in ("x", "y", "w", "h"):
        if key not in gate:
            problems.append(f"{where}: missing '{key}'")
        elif not _finite_number(gate[key]):
            problems.append(f"{where}: '{key}' must be a finite number")
    if not problems:
        x, y, w, h = gate["x"], gate["y"], gate["w"], gate["h"]
        if w <= 0 or h <= 0:
            problems.append(f"{where}: 'w' and 'h' must be > 0")
        elif x < 0 or x + w > config.FIELD_W:
            problems.append(f"{where}: gate sticks out of the field")
        elif h < _GATE_MIN_H:
            problems.append(f"{where}: 'h' is too thin for agents to trigger")
        elif not (_GATE_MIN_Y < y and y + h < _GATE_MAX_Y):
            problems.append(f"{where}: gate is outside the band agents can reach")
    if gate.get("op") not in ("mul", "add"):
        problems.append(f"{where}: 'op' must be 'mul' or 'add'")
    if "value" not in gate:
        problems.append(f"{where}: missing 'value'")
    elif not _finite_int(gate["value"]) or gate["value"] < 1:
        problems.append(f"{where}: 'value' must be an int >= 1")
    if not isinstance(gate.get("label"), str) or not gate.get("label"):
        problems.append(f"{where}: 'label' must be a non-empty string")
    if "vx" in gate and not _finite_number(gate["vx"]):
        problems.append(f"{where}: 'vx' must be a finite number")
    return problems


class WaveSpawner:
    """Spawns level waves into a UnitPool as their scheduled time arrives."""

    def __init__(self, waves: list[dict], rng) -> None:
        waves = copy.deepcopy(list(waves))
        problems: list[str] = []
        for i, wave in enumerate(waves):
            problems.extend(_wave_problems(wave, f"waves[{i}]"))
        if problems:
            raise ValueError("invalid waves: " + "; ".join(problems))

        self._rng = rng
        self._waves = sorted(waves, key=lambda wave: wave["t"])
        self._next = 0

    @property
    def remaining(self) -> int:
        """Return the number of waves that have not spawned yet."""
        return len(self._waves) - self._next

    def done(self) -> bool:
        """Return True when every wave has spawned."""
        return self._next >= len(self._waves)

    def update(self, t: float, red: UnitPool, spawn_y: float = config.BUG_SPAWN_Y) -> int:
        """Spawn every wave due at time ``t`` and return how many bugs were spawned."""
        if not _finite_number(t):
            raise ValueError("t must be a finite number")
        if not _finite_number(spawn_y):
            raise ValueError("spawn_y must be a finite number")
        t = float(t)
        spawn_y = float(spawn_y)
        spawned = 0
        while self._next < len(self._waves) and self._waves[self._next]["t"] <= t:
            wave = self._waves[self._next]
            free = red.capacity - red.count
            count = min(int(wave["count"]), max(free, 0))
            if count > 0:
                half = float(wave["spread"]) / 2.0
                x = self._rng.uniform(wave["x"] - half, wave["x"] + half, count)
                x = np.clip(x, config.UNIT_RADIUS, config.FIELD_W - config.UNIT_RADIUS)
                y = spawn_y + self._rng.uniform(0.0, 30.0, count)
                slots = red.spawn_many(
                    x,
                    y,
                    vx=0.0,
                    vy=float(wave["speed"]),
                    kind=int(wave.get("kind", 0)),
                    hp=float(wave.get("hp", 1.0)),
                )
                spawned += int(slots.size)
            self._next += 1
        return spawned


def get_level(n: int) -> dict:
    """Return a deep copy of level ``n`` (1-based). Raise KeyError if it does not exist."""
    if not _finite_int(n):
        raise KeyError(n)
    n = int(n)
    if n < 1 or n > len(LEVELS):
        raise KeyError(n)
    return copy.deepcopy(LEVELS[n - 1])


def validate_level(level: object) -> list[str]:
    """Return the list of contract violations in ``level``; empty means valid."""
    if not isinstance(level, dict):
        return ["level must be a dict"]
    problems: list[str] = []

    if not _finite_int(level.get("id")) or level.get("id", 0) < 1:
        problems.append("'id' must be an int >= 1")
    if not isinstance(level.get("name"), str) or not level.get("name"):
        problems.append("'name' must be a non-empty string")
    for key in ("enemy_hp", "player_hp"):
        if key not in level:
            problems.append(f"missing '{key}'")
        elif not _finite_number(level[key]) or level[key] <= 0:
            problems.append(f"'{key}' must be a finite number > 0")
    if not _finite_int(level.get("reward")) or level.get("reward", -1) < 0:
        problems.append("'reward' must be an int >= 0")

    if "gates" not in level:
        problems.append("missing 'gates'")
    else:
        gates = level["gates"]
        if not isinstance(gates, list):
            problems.append("'gates' must be a list")
        else:
            if len(gates) > config.MAX_GATES:
                problems.append(f"a level may have at most {config.MAX_GATES} gates")
            for i, gate in enumerate(gates):
                problems.extend(_gate_problems(gate, f"gates[{i}]"))

    if "waves" not in level:
        problems.append("missing 'waves'")
    else:
        waves = level["waves"]
        if not isinstance(waves, list):
            problems.append("'waves' must be a list")
        else:
            for i, wave in enumerate(waves):
                problems.extend(_wave_problems(wave, f"waves[{i}]"))
    return problems
