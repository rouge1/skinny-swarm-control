"""Wire protocol between the Python server and the browser client.

Every message is one JSON object with a "type" field.

Server -> client
    {"type": "state", ...}   see STATE_FIELDS; sent SEND_HZ times per second.
    {"type": "hello", "field": {"w": FIELD_W, "h": FIELD_H}, "tick_hz": TICK_HZ}
                             sent once, right after the WebSocket opens.

Client -> server
    {"type": "input", "left": bool, "right": bool, "fire": bool}
        The full current key state. Sent whenever it changes.
     {"type": "action", "action": "pause" | "resume" | "restart" |
      "next" | "buy_fire_rate" | "buy_multishot" | "buy_speed"}

Units travel as flat integer lists to keep messages small:
    "blue": [x0, y0, kind0, x1, y1, kind1, ...]
with x and y rounded to whole field pixels.
"""

from collections.abc import Iterable
from typing import Any

import numpy as np

STATUSES = ("playing", "paused", "won", "lost")
ACTIONS = (
    "pause",
    "resume",
    "restart",
    "next",
    "buy_fire_rate",
    "buy_multishot",
    "buy_speed",
)

# field name -> python type(s) of the value in a "state" message
STATE_FIELDS: dict[str, type | tuple[type, ...]] = {
    "type": str,  # always "state"
    "tick": int,  # simulation step counter, starts at 0
    "status": str,  # one of STATUSES
    "launcher": dict,  # {"x": float, "y": float}
    "blue": list,  # packed agents, see pack_units
    "red": list,  # packed bugs, see pack_units
    "gates": list,  # [{"x","y","w","h": float, "op": "mul"|"add", "value": int, "label": str}]
    "bases": dict,  # {"enemy_hp": float, "enemy_hp_max": float, "player_hp": float, "player_hp_max": float}
    "hud": dict,  # progression, level name, counts and upgrade prices
}


def pack_units(x: np.ndarray, y: np.ndarray, kind: np.ndarray) -> list[int]:
    """Interleave unit arrays as [x0, y0, k0, x1, y1, k1, ...] of Python ints."""
    out = np.empty(len(x) * 3, dtype=np.int32)
    out[0::3] = np.rint(x)
    out[1::3] = np.rint(y)
    out[2::3] = kind
    return out.tolist()


def unpack_units(flat: Iterable[int]) -> list[tuple[int, int, int]]:
    flat = list(flat)
    return [(flat[i], flat[i + 1], flat[i + 2]) for i in range(0, len(flat), 3)]


def validate_state(msg: dict[str, Any]) -> list[str]:
    """Return a list of problems with a state message; empty means valid."""
    errors = []
    for name, typ in STATE_FIELDS.items():
        if name not in msg:
            errors.append(f"missing field {name!r}")
        elif not isinstance(msg[name], typ) or isinstance(msg[name], bool) and typ is int:
            errors.append(f"field {name!r} should be {typ}, got {type(msg[name]).__name__}")
    if errors:
        return errors
    if msg["type"] != "state":
        errors.append("type must be 'state'")
    if msg["status"] not in STATUSES:
        errors.append(f"status {msg['status']!r} not in {STATUSES}")
    for key in ("blue", "red"):
        if len(msg[key]) % 3:
            errors.append(f"{key} length must be a multiple of 3")
        elif not all(isinstance(v, int) and not isinstance(v, bool) for v in msg[key]):
            errors.append(f"{key} must contain only ints")
    for key in ("x", "y"):
        if not isinstance(msg["launcher"].get(key), int | float):
            errors.append(f"launcher.{key} must be a number")
    for key in ("enemy_hp", "enemy_hp_max", "player_hp", "player_hp_max"):
        if not isinstance(msg["bases"].get(key), int | float):
            errors.append(f"bases.{key} must be a number")
    for key in ("blue_count", "red_count", "level", "tokens"):
        if not isinstance(msg["hud"].get(key), int):
            errors.append(f"hud.{key} must be an int")
    if not isinstance(msg["hud"].get("has_next"), bool):
        errors.append("hud.has_next must be a bool")
    if not isinstance(msg["hud"].get("level_name"), str):
        errors.append("hud.level_name must be a str")
    upgrades = msg["hud"].get("upgrades")
    if not isinstance(upgrades, dict):
        errors.append("hud.upgrades must be a dict")
    else:
        for key in ("fire_rate", "multishot", "speed"):
            if not isinstance(upgrades.get(key), int) or isinstance(upgrades.get(key), bool):
                errors.append(f"hud.upgrades.{key} must be an int")
    prices = msg["hud"].get("prices")
    if not isinstance(prices, dict):
        errors.append("hud.prices must be a dict")
    else:
        for key in ("fire_rate", "multishot", "speed"):
            value = prices.get(key)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
                errors.append(f"hud.prices.{key} must be an int or None")
    for i, g in enumerate(msg["gates"]):
        for key in ("x", "y", "w", "h"):
            if not isinstance(g.get(key), int | float):
                errors.append(f"gates[{i}].{key} must be a number")
        if g.get("op") not in ("mul", "add"):
            errors.append(f"gates[{i}].op must be 'mul' or 'add'")
        if not isinstance(g.get("value"), int):
            errors.append(f"gates[{i}].value must be an int")
        if not isinstance(g.get("label"), str):
            errors.append(f"gates[{i}].label must be a str")
    return errors
