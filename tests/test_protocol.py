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
    msg["hud"] = {"blue_count": 0, "red_count": 0, "level": 1, "tokens": 0}
    errors = validate_state(msg)
    assert any("multiple of 3" in e for e in errors) and any("dancing" in e for e in errors)
