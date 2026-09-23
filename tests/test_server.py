"""Acceptance tests for the FastAPI server (phase 2)."""

import json
import time

from fastapi.testclient import TestClient

from swarm_control import config
from swarm_control.protocol import validate_state
from swarm_control.server.app import create_app
from swarm_control.sim.world import World


class SpyWorld(World):
    instances: list["SpyWorld"] = []

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.inputs, self.actions = [], []
        SpyWorld.instances.append(self)

    def set_input(self, left, right, fire):
        self.inputs.append((left, right, fire))
        super().set_input(left, right, fire)

    def action(self, name):
        self.actions.append(name)
        super().action(name)


def client():
    SpyWorld.instances.clear()
    return TestClient(create_app(world_factory=SpyWorld))


def next_state(ws):
    while True:
        msg = ws.receive_json()
        if msg.get("type") == "state":
            return msg


def test_index_served():
    r = client().get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "<canvas" in r.text


def test_static_served():
    r = client().get("/static/index.html")
    assert r.status_code == 200


def test_module_level_app_exists():
    from swarm_control.server import app as mod

    assert mod.app is not None


def test_hello_then_valid_states():
    with client().websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello == {"type": "hello", "field": {"w": config.FIELD_W, "h": config.FIELD_H},
                         "tick_hz": config.TICK_HZ}
        s1 = next_state(ws)
        s2 = next_state(ws)
        assert validate_state(s1) == [] and validate_state(s2) == []
        assert s2["tick"] > s1["tick"]


def test_send_rate_and_tick_rate():
    with client().websocket_connect("/ws") as ws:
        ws.receive_json()
        first = next_state(ws)
        t0 = time.perf_counter()
        n = 0
        while time.perf_counter() - t0 < 1.0:
            last = next_state(ws)
            n += 1
        elapsed = time.perf_counter() - t0
        assert 0.6 * config.SEND_HZ <= n / elapsed <= 1.4 * config.SEND_HZ
        ticks_per_s = (last["tick"] - first["tick"]) / elapsed
        assert 0.6 * config.TICK_HZ <= ticks_per_s <= 1.4 * config.TICK_HZ


def test_input_and_actions_reach_the_world():
    with client().websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "input", "left": True, "right": False, "fire": True})
        ws.send_json({"type": "action", "action": "pause"})
        deadline = time.time() + 2
        while time.time() < deadline:
            s = next_state(ws)
            if s["status"] == "paused":
                break
        world = SpyWorld.instances[-1]
        assert (True, False, True) in world.inputs
        assert "pause" in world.actions
        assert s["status"] == "paused"


def test_malformed_messages_are_ignored():
    with client().websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_text("this is not json")
        ws.send_text(json.dumps([1, 2, 3]))
        ws.send_json({"type": "input"})
        ws.send_json({"type": "input", "left": "yes", "right": None, "fire": 3})
        ws.send_json({"type": "action", "action": "explode"})
        ws.send_json({"type": "teleport"})
        a = next_state(ws)
        b = next_state(ws)
        assert b["tick"] > a["tick"]
        assert "explode" not in SpyWorld.instances[-1].actions


def test_each_connection_gets_its_own_world():
    c = client()
    with c.websocket_connect("/ws") as ws1, c.websocket_connect("/ws") as ws2:
        ws1.receive_json()
        ws2.receive_json()
        next_state(ws1)
        next_state(ws2)
    assert len(SpyWorld.instances) == 2
