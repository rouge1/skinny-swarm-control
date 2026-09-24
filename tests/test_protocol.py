import numpy as np

from swarm_control.protocol import pack_units, unpack_units, validate_state
from swarm_control.sim.world import World


def test_pack_units_rounds_and_interleaves():
    x = np.array([1.4, 2.6], np.float32)
    y = np.array([3.5, 4.49], np.float32)
    flat = pack_units(x, y, np.array([0, 2], np.int8))
    assert flat == [1, 4, 0, 3, 4, 2]
    assert all(type(v) is int for v in flat)
    assert unpack_units(flat) == [(1, 4, 0), (3, 4, 2)]


def test_world_snapshot_is_valid():
    assert validate_state(World().snapshot()) == []


def test_validate_state_catches_problems():
    msg = World().snapshot()
    msg["blue"] = [1, 2]
    msg["status"] = "dancing"
    del msg["hud"]
    errors = validate_state(msg)
    assert any("hud" in e for e in errors)
    msg["hud"] = {
        "blue_count": 0,
        "red_count": 0,
        "level": 1,
        "tokens": 0,
        "has_next": True,
        "upgrades": {"fire_rate": 0, "multishot": 0, "speed": 0},
        "prices": {"fire_rate": 20, "multishot": 30, "speed": 15},
        "level_name": "Sandbox",
    }
    errors = validate_state(msg)
    assert any("multiple of 3" in e for e in errors) and any("dancing" in e for e in errors)


def test_validate_state_checks_phase_four_hud_types():
    msg = World().snapshot()
    msg["hud"]["has_next"] = 1
    msg["hud"]["upgrades"]["speed"] = False
    msg["hud"]["prices"]["fire_rate"] = "20"
    msg["hud"]["level_name"] = 4
    errors = validate_state(msg)
    assert any("has_next" in e for e in errors)
    assert any("upgrades.speed" in e for e in errors)
    assert any("prices.fire_rate" in e for e in errors)
    assert any("level_name" in e for e in errors)


def test_validate_state_requires_each_phase_four_hud_field():
    for field in ("has_next", "upgrades", "prices", "level_name"):
        msg = World().snapshot()
        del msg["hud"][field]
        errors = validate_state(msg)
        assert any(field in error for error in errors)


def test_validate_state_rejects_bool_hud_counts_and_level():
    for field in ("blue_count", "red_count", "level", "tokens"):
        msg = World().snapshot()
        msg["hud"][field] = True
        errors = validate_state(msg)
        assert any(f"hud.{field}" in error for error in errors)
