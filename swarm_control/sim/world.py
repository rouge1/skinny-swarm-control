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

This file is a stub: it produces valid, empty snapshots so the server and the
client can be built before the real simulation exists.
"""

import numpy as np

from swarm_control import config
from swarm_control.protocol import ACTIONS, pack_units
from swarm_control.sim.pool import UnitPool


class World:
    def __init__(self, seed: int = 0, level: dict | None = None) -> None:
        self.seed = seed
        self.level = level or {}
        self._rng = np.random.default_rng(seed)
        self.blue = UnitPool(config.BLUE_CAPACITY)
        self.red = UnitPool(config.RED_CAPACITY)
        self.tick = 0
        self.status = "playing"
        self.launcher_x = config.FIELD_W / 2
        self._input = (False, False, False)
        self._fire_timer = 0.0

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
            self.__init__(self.seed, self.level)

    def step(self, dt: float) -> None:
        if self.status != "playing":
            return

        left, right, fire = self._input
        direction = int(right) - int(left)
        self.launcher_x = float(
            np.clip(
                self.launcher_x + direction * config.LAUNCHER_SPEED * dt,
                config.LAUNCHER_MARGIN,
                config.FIELD_W - config.LAUNCHER_MARGIN,
            )
        )

        if fire:
            if self._fire_timer <= 0.0:
                self.blue.spawn(
                    self.launcher_x,
                    config.LAUNCHER_Y - config.MUZZLE_OFFSET,
                    vy=-config.AGENT_SPEED,
                )
                self._fire_timer = config.FIRE_INTERVAL
            self._fire_timer -= dt
        else:
            self._fire_timer = 0.0

        self.blue.step(dt)
        self.blue.cull(0.0, -config.UNIT_RADIUS, config.FIELD_W, config.FIELD_H)
        self.tick += 1

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
            "gates": [],
            "bases": {"enemy_hp": 100.0, "enemy_hp_max": 100.0, "player_hp": 100.0, "player_hp_max": 100.0},
            "hud": {
                "blue_count": self.blue.count,
                "red_count": self.red.count,
                "level": 1,
                "tokens": 0,
            },
        }
