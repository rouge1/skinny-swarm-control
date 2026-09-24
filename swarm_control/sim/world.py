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


class World:
    def __init__(self, seed: int = 0, level: dict | None = None) -> None:
        self.seed = seed
        self._level_template = copy.deepcopy(level if level is not None else {})
        self.blue = UnitPool(config.BLUE_CAPACITY)
        self.red = UnitPool(config.RED_CAPACITY)
        self.passed = np.zeros(config.BLUE_CAPACITY, dtype=np.uint32)
        self._input = (False, False, False)
        self.tokens = 0
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

    def action(self, name: str) -> None:
        if name not in ACTIONS:
            return
        if name == "pause" and self.status == "playing":
            self.status = "paused"
        elif name == "resume" and self.status == "paused":
            self.status = "playing"
        elif name == "restart":
            self._reset()

    def _move_launcher(self, dt: float) -> None:
        """Move and clamp the launcher from the current input."""
        left, right, _fire = self._input
        direction = int(right) - int(left)
        self.launcher_x = float(
            np.clip(
                self.launcher_x + direction * config.LAUNCHER_SPEED * dt,
                config.LAUNCHER_MARGIN,
                config.FIELD_W - config.LAUNCHER_MARGIN,
            )
        )

    def _fire(self, dt: float) -> None:
        """Spawn all shots due during this step."""
        _left, _right, fire = self._input
        self._fire_timer -= dt
        if not fire:
            self._fire_timer = max(0.0, self._fire_timer)
            return
        if self._fire_timer > 0.0:
            return

        shots = math.floor(-self._fire_timer / config.FIRE_INTERVAL) + 1
        self._fire_timer += shots * config.FIRE_INTERVAL
        slots = self.blue.spawn_many(
            np.full(shots, self.launcher_x),
            np.full(shots, config.LAUNCHER_Y - config.MUZZLE_OFFSET),
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
        if self.enemy_hp == 0.0:
            self.status = "won"
            self.tokens += int(self.level.get("reward", 0))
        elif self.player_hp == 0.0:
            self.status = "lost"

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
            },
        }


def new_game(seed: int = 0) -> World:
    """Create a world ready to play level one."""
    return World(seed=seed, level=get_level(1))
