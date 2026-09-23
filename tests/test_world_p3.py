"""Acceptance tests for World phase 3: levels, gates, waves, combat, bases, win/lose."""

import copy
import time

import numpy as np
import pytest

from swarm_control import config
from swarm_control.protocol import validate_state
from swarm_control.sim.waves import get_level
from swarm_control.sim.world import World, new_game

DT = 1 / config.TICK_HZ
MID = config.FIELD_W / 2


def level(**kw):
    lv = {"id": 7, "name": "Test", "enemy_hp": 100, "player_hp": 100, "reward": 25, "gates": [], "waves": []}
    lv.update(kw)
    return lv


def run(world, seconds, left=False, right=False, fire=False):
    world.set_input(left, right, fire)
    for _ in range(round(seconds * config.TICK_HZ)):
        world.step(DT)


def test_default_world_is_an_empty_level():
    w = World()
    assert w.level["gates"] == [] and w.level["waves"] == []
    assert w.enemy_hp == w.enemy_hp_max == 100 and w.player_hp == w.player_hp_max == 100


def test_new_game_uses_level_one():
    w = new_game()
    assert w.level["id"] == 1 and w.level["gates"] == get_level(1)["gates"]
    s = w.snapshot()
    assert validate_state(s) == [] and s["hud"]["level"] == 1
    assert len(s["gates"]) == len(get_level(1)["gates"])


def test_level_dict_is_copied():
    g = {"x": 10, "y": 500, "w": 100, "h": 30, "op": "mul", "value": 2, "label": "x2 fork", "vx": 50}
    lv = level(gates=[g])
    before = copy.deepcopy(lv)
    w = World(level=lv)
    run(w, 1)
    assert lv == before


def test_hp_from_level_and_in_snapshot():
    w = World(level=level(enemy_hp=40, player_hp=30))
    b = w.snapshot()["bases"]
    assert b == {"enemy_hp": 40, "enemy_hp_max": 40, "player_hp": 30, "player_hp_max": 30}


def test_gates_move_and_are_snapshotted():
    g = {"x": 100, "y": 500, "w": 100, "h": 30, "op": "add", "value": 3, "label": "+3 subagents", "vx": 60}
    w = World(level=level(gates=[g]))
    run(w, 0.5)
    sg = w.snapshot()["gates"]
    assert len(sg) == 1
    assert sg[0]["x"] == pytest.approx(130, abs=0.5)
    assert (sg[0]["op"], sg[0]["value"], sg[0]["label"]) == ("add", 3, "+3 subagents")


def test_gate_multiplies_fired_agents():
    g = {"x": MID - 70, "y": 600, "w": 140, "h": 30, "op": "mul", "value": 3, "label": "x3 worktree"}
    w = World(level=level(gates=[g]))
    run(w, DT, fire=True)  # exactly one shot
    run(w, 2.0)
    assert w.blue.count == 3


def test_agent_passes_gate_only_once_even_if_it_lingers():
    g = {"x": MID - 70, "y": 600, "w": 140, "h": 30, "op": "mul", "value": 2, "label": "x2 fork"}
    w = World(level=level(gates=[g]))
    run(w, DT, fire=True)
    run(w, 2.0)
    assert w.blue.count == 2


def test_slot_reuse_does_not_inherit_gate_marks():
    g = {"x": MID - 70, "y": 600, "w": 140, "h": 30, "op": "mul", "value": 2, "label": "x2 fork"}
    w = World(level=level(gates=[g], enemy_hp=10_000))
    run(w, DT, fire=True)
    run(w, 4.0)  # both agents reach the fortress and free their slots
    assert w.blue.count == 0
    run(w, DT, fire=True)  # the new shot reuses a freed slot
    run(w, 2.0)
    assert w.blue.count == 2


def test_waves_spawn_on_schedule():
    wave = {"t": 0.5, "count": 5, "x": 100, "spread": 20, "speed": 40}
    w = World(level=level(waves=[wave]))
    run(w, 0.45)
    assert w.red.count == 0
    run(w, 0.1)
    assert w.red.count == 5
    s = w.snapshot()
    assert s["hud"]["red_count"] == 5 and len(s["red"]) == 15


def test_agents_and_bugs_annihilate():
    w = World(level=level())
    w.blue.spawn(300, 500, vy=-config.AGENT_SPEED)
    w.red.spawn(300, 490, vy=100)
    run(w, DT)
    assert w.blue.count == 0 and w.red.count == 0


def test_agents_damage_fortress_and_win():
    w = World(level=level(enemy_hp=5, reward=25))
    run(w, 1.0, fire=True)
    run(w, 4.0)
    assert w.enemy_hp == 0 and w.status == "won"
    assert w.tokens == 25
    s = w.snapshot()
    assert s["status"] == "won" and s["hud"]["tokens"] == 25 and s["bases"]["enemy_hp"] == 0


def test_bugs_damage_base_and_lose():
    wave = {"t": 0, "count": 5, "x": 500, "spread": 0, "speed": 400}
    w = World(level=level(player_hp=3, waves=[wave]))
    run(w, 3.0)
    assert w.player_hp == 0 and w.status == "lost"
    assert w.tokens == 0


def test_hp_never_negative():
    wave = {"t": 0, "count": 50, "x": 500, "spread": 30, "speed": 400}
    w = World(level=level(player_hp=3, waves=[wave]))
    run(w, 3.0)
    assert w.player_hp == 0


def test_game_freezes_after_result():
    w = World(level=level(enemy_hp=1))
    run(w, 0.2, fire=True)
    run(w, 4.0, fire=True)
    assert w.status == "won"
    tick, n = w.tick, w.blue.count
    run(w, 1.0, fire=True)
    assert (w.tick, w.blue.count) == (tick, n)


def test_restart_restores_level_but_keeps_tokens():
    g = {"x": 100, "y": 500, "w": 100, "h": 30, "op": "add", "value": 3, "label": "+3 subagents", "vx": 60}
    wave = {"t": 0.1, "count": 3, "x": 100, "spread": 0, "speed": 40}
    w = World(level=level(enemy_hp=3, reward=10, gates=[g], waves=[wave]))
    run(w, 5.0, fire=True)
    assert w.status == "won" and w.tokens == 10
    w.action("restart")
    assert w.status == "playing" and w.enemy_hp == 3 and w.tokens == 10
    assert w.snapshot()["gates"][0]["x"] == 100
    assert w.red.count == 0
    run(w, 0.2)
    assert w.red.count == 3  # waves are re-armed


def test_deterministic_full_level():
    def play():
        w = new_game(seed=5)
        run(w, 2, fire=True, right=True)
        run(w, 3, fire=True, left=True)
        return w.snapshot()

    assert play() == play()


def test_every_level_is_winnable_by_a_scripted_player():
    from swarm_control.sim.waves import LEVELS

    for n in range(1, len(LEVELS) + 1):
        w = World(seed=1, level=get_level(n))
        # sweep the launcher back and forth while firing, for up to 3 minutes of game time
        for k in range(180):
            run(w, 1.0, fire=True, left=(k // 2) % 2 == 0, right=(k // 2) % 2 == 1)
            if w.status != "playing":
                break
        assert w.status == "won", f"level {n} ended {w.status} (enemy {w.enemy_hp}, player {w.player_hp})"


def test_step_performance_under_load():
    w = new_game()
    rng = np.random.default_rng(0)
    w.blue.spawn_many(rng.uniform(0, 540, 1500), rng.uniform(400, 900, 1500), vy=-config.AGENT_SPEED)
    w.red.spawn_many(rng.uniform(0, 540, 1500), rng.uniform(150, 500, 1500), vy=80.0)
    t = time.perf_counter()
    run(w, 2.0, fire=True)
    assert (time.perf_counter() - t) / 120 < 0.004
