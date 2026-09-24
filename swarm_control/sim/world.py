"""The game world: owns the unit pools and advances the simulation.

CONTRACT (acceptance tests: tests/test_world.py, added per phase):

    world = World(seed=0, level=None)
    world.tick           -> int, steps taken (only advances while status == "playing")
    world.status         -> "playing" | "paused" | "won" | "lost"
    world.blue, world.red -> UnitPool (capacities from config)
    world.launcher_x     -> float, starts at FIELD_W / 2
    world.set_input(left: bool, right: bool, fire: bool) -> None
    world.action(name)   -> None; name in protocol.ACTIONS, anything else is ignored
    world.step(dt)       -> None; advances one step (does nothing unless playing)
    world.snapshot()     -> dict, a valid protocol "state" message

The world wires together the launcher, gates, waves, combat and bases. Each
playing step follows the simulation order used by the game, and result states
freeze the simulation until a restart.

    world.load_level(level) -> None; deep-copy and start a new level while
    retaining tokens, held input and the unit pools.

Phase 4 adds campaign progression for the life of one World. ``tokens`` and
``upgrades`` (fire_rate, multishot, speed) survive ``restart``, ``next`` and
``load_level``. The shop actions ``buy_fire_rate``, ``buy_multishot`` and
``buy_speed`` only work while ``status == "won"`` and only when the player can
pay the next price in the matching config tuple. ``next`` loads the following
numbered level via ``get_level`` while ``status == "won"`` and another level
exists; after the final level it does nothing. Fire rate multiplies
``FIRE_INTERVAL`` by ``FIRE_RATE_FACTOR`` per level, multishot adds
``MULTISHOT_AGENTS_PER_LEVEL`` agents per shot fanned ``MULTISHOT_SPACING``
apart around the launcher, and speed multiplies ``LAUNCHER_SPEED`` by
``LAUNCHER_SPEED_FACTOR`` per level. Winning a level pays its integer reward
once per level id; replaying an already-won level pays nothing.
"""

import copy
import math

import numpy as np

from swarm_control import config
from swarm_control.protocol import ACTIONS, pack_units
from swarm_control.sim.combat import collide, hit_bases
from swarm_control.sim.gates import apply_gates, move_gates
from swarm_control.sim.pool import UnitPool
from swarm_control.sim.waves import WaveSpawner, get_level

_UPGRADE_PRICES: dict[str, tuple[int, ...]] = {
    "fire_rate": config.FIRE_RATE_PRICES,
    "multishot": config.MULTISHOT_PRICES,
    "speed": config.SPEED_PRICES,
}
_UPGRADE_ACTIONS: dict[str, str] = {
    "buy_fire_rate": "fire_rate",
    "buy_multishot": "multishot",
    "buy_speed": "speed",
}


class World:
    def __init__(self, seed: int = 0, level: dict | None = None) -> None:
        self.seed = seed
        sandbox = {
            "id": 0,
            "name": "Sandbox",
            "enemy_hp": 100,
            "player_hp": 100,
            "reward": 0,
            "gates": [],
            "waves": [],
        }
        self._level_template = copy.deepcopy(level if level is not None else sandbox)
        self.blue = UnitPool(config.BLUE_CAPACITY)
        self.red = UnitPool(config.RED_CAPACITY)
        self.passed = np.zeros(config.BLUE_CAPACITY, dtype=np.uint32)
        self._input = (False, False, False)
        self.tokens = 0
        self.upgrades = {"fire_rate": 0, "multishot": 0, "speed": 0}
        self._rewarded: set[int] = set()
        self._reset()

    def load_level(self, level: dict) -> None:
        """Load a copied level and reset it while retaining progress and input."""
        self._level_template = copy.deepcopy(level)
        self._reset()

    def _reset(self) -> None:
        """Reset simulation state while retaining pools and current input."""
        self.blue.clear()
        self.red.clear()
        self.passed.fill(0)
        self.level = copy.deepcopy(self._level_template)
        self.level.setdefault("gates", [])
        self.level.setdefault("waves", [])
        self._rng = np.random.default_rng(self.seed)
        self._waves = WaveSpawner(self.level.get("waves", []), self._rng)
        self.tick = 0
        self.elapsed = 0.0
        self.status = "playing"
        self.launcher_x = config.FIELD_W / 2
        self._fire_timer = 0.0
        self.enemy_hp_max = float(self.level.get("enemy_hp", 100.0))
        self.enemy_hp = self.enemy_hp_max
        self.player_hp_max = float(self.level.get("player_hp", 100.0))
        self.player_hp = self.player_hp_max
        self.level_number = int(self.level.get("id", 1))

    def set_input(self, left: bool, right: bool, fire: bool) -> None:
        self._input = (bool(left), bool(right), bool(fire))

    def _next_level(self) -> dict | None:
        """Return a fresh copy of the next numbered level, or None at campaign end."""
        try:
            return get_level(self.level_number + 1)
        except KeyError:
            return None

    def _has_next(self) -> bool:
        """Return True while another numbered level exists after the current one."""
        return self._next_level() is not None

    def _next_price(self, key: str) -> int | None:
        """Return the token price of the next ``key`` level, or None when maxed."""
        prices = _UPGRADE_PRICES[key]
        level = self.upgrades[key]
        return int(prices[level]) if level < len(prices) else None

    def _buy(self, key: str) -> None:
        """Spend the next price and raise ``key`` by one level, if allowed."""
        price = self._next_price(key)
        if self.status != "won" or price is None or self.tokens < price:
            return
        self.tokens -= price
        self.upgrades[key] += 1

    def _launcher_speed(self) -> float:
        """Return the launcher speed in px/s including the speed upgrade."""
        return config.LAUNCHER_SPEED * config.LAUNCHER_SPEED_FACTOR ** self.upgrades["speed"]

    def _fire_interval(self) -> float:
        """Return the seconds between shots including the fire-rate upgrade."""
        return config.FIRE_INTERVAL * config.FIRE_RATE_FACTOR ** self.upgrades["fire_rate"]

    def _agents_per_shot(self) -> int:
        """Return how many agents one shot fires, including the multishot upgrade."""
        return 1 + config.MULTISHOT_AGENTS_PER_LEVEL * self.upgrades["multishot"]

    def action(self, name: str) -> None:
        if name not in ACTIONS:
            return
        if name == "pause" and self.status == "playing":
            self.status = "paused"
        elif name == "resume" and self.status == "paused":
            self.status = "playing"
        elif name == "restart":
            self._reset()
        elif name == "next" and self.status == "won":
            next_level = self._next_level()
            if next_level is not None:
                self.load_level(next_level)
        elif name in _UPGRADE_ACTIONS:
            self._buy(_UPGRADE_ACTIONS[name])

    def _move_launcher(self, dt: float) -> None:
        """Move and clamp the launcher from the current input."""
        left, right, _fire = self._input
        direction = int(right) - int(left)
        self.launcher_x = float(
            np.clip(
                self.launcher_x + direction * self._launcher_speed() * dt,
                config.LAUNCHER_MARGIN,
                config.FIELD_W - config.LAUNCHER_MARGIN,
            )
        )

    def _fire(self, dt: float) -> None:
        """Spawn all shots due during this step, fanned out by multishot."""
        _left, _right, fire = self._input
        interval = self._fire_interval()
        self._fire_timer -= dt
        if not fire:
            self._fire_timer = max(0.0, self._fire_timer)
            return
        if self._fire_timer > 0.0:
            return

        shots = math.floor(-self._fire_timer / interval) + 1
        self._fire_timer += shots * interval
        per_shot = self._agents_per_shot()
        count = shots * per_shot
        offsets = (np.arange(per_shot) - (per_shot - 1) / 2.0) * config.MULTISHOT_SPACING
        slots = self.blue.spawn_many(
            np.full(count, self.launcher_x) + np.tile(offsets, shots),
            np.full(count, config.LAUNCHER_Y - config.MUZZLE_OFFSET),
            vy=-config.AGENT_SPEED,
        )
        self.passed[slots] = 0

    def _move_units(self, dt: float) -> None:
        """Advance units in both pools."""
        self.blue.step(dt)
        self.red.step(dt)

    def _apply_gates(self) -> None:
        """Apply every live gate to the blue pool."""
        apply_gates(self.blue, self.passed, self.level.get("gates", []), self._rng)

    def _spawn_waves(self) -> None:
        """Spawn all waves whose scheduled time has arrived."""
        self._waves.update(self.elapsed, self.red)

    def _resolve_bases(self) -> None:
        """Apply one damage point for each unit reaching either base."""
        blue_hits, red_hits = hit_bases(self.blue, self.red)
        self.enemy_hp = max(0.0, self.enemy_hp - blue_hits)
        self.player_hp = max(0.0, self.player_hp - red_hits)

    def _cull(self) -> None:
        """Free units outside the field bounds."""
        self.blue.cull(0.0, -config.UNIT_RADIUS, config.FIELD_W, config.FIELD_H)
        self.red.cull(0.0, -config.UNIT_RADIUS, config.FIELD_W, config.FIELD_H)

    def step(self, dt: float) -> None:
        if self.status != "playing" or not np.isfinite(dt) or dt < 0:
            return
        self._move_launcher(dt)
        self._fire(dt)
        move_gates(self.level.get("gates", []), dt)
        self._move_units(dt)
        self._apply_gates()
        self._spawn_waves()
        collide(self.blue, self.red)
        self._resolve_bases()
        self._cull()
        self.tick += 1
        self.elapsed += dt
        if self.player_hp == 0.0:
            self.status = "lost"
        elif self.enemy_hp == 0.0:
            self.status = "won"
            if self.level_number not in self._rewarded:
                self._rewarded.add(self.level_number)
                self.tokens += int(self.level.get("reward", 0))

    def snapshot(self) -> dict:
        blue_indices = self.blue.active_indices()
        red_indices = self.red.active_indices()
        return {
            "type": "state",
            "tick": self.tick,
            "status": self.status,
            "launcher": {"x": float(self.launcher_x), "y": config.LAUNCHER_Y},
            "blue": pack_units(
                self.blue.x[blue_indices],
                self.blue.y[blue_indices],
                self.blue.kind[blue_indices],
            ),
            "red": pack_units(
                self.red.x[red_indices],
                self.red.y[red_indices],
                self.red.kind[red_indices],
            ),
            "gates": [
                {
                    "x": float(gate["x"]),
                    "y": float(gate["y"]),
                    "w": float(gate["w"]),
                    "h": float(gate["h"]),
                    "op": gate["op"],
                    "value": int(gate["value"]),
                    "label": gate["label"],
                }
                for gate in self.level.get("gates", [])
            ],
            "bases": {
                "enemy_hp": self.enemy_hp,
                "enemy_hp_max": self.enemy_hp_max,
                "player_hp": self.player_hp,
                "player_hp_max": self.player_hp_max,
            },
            "hud": {
                "blue_count": self.blue.count,
                "red_count": self.red.count,
                "level": self.level_number,
                "tokens": self.tokens,
                "has_next": self._has_next(),
                "upgrades": dict(self.upgrades),
                "prices": {
                    key: self._next_price(key) for key in ("fire_rate", "multishot", "speed")
                },
                "level_name": str(self.level.get("name", "")),
            },
        }


def new_game(seed: int = 0) -> World:
    """Create a world ready to play level one."""
    return World(seed=seed, level=get_level(1))
