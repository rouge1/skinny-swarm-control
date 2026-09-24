"""World acceptance tests added after the phase 3 review: ties, sandbox level, loading the next level."""

from swarm_control import config
from swarm_control.sim.waves import get_level
from swarm_control.sim.world import World

DT = 1 / config.TICK_HZ


def level(**kw):
    lv = {"id": 7, "name": "Test", "enemy_hp": 100, "player_hp": 100, "reward": 25, "gates": [], "waves": []}
    lv.update(kw)
    return lv


def run(world, seconds, left=False, right=False, fire=False):
    world.set_input(left, right, fire)
    for _ in range(round(seconds * config.TICK_HZ)):
        world.step(DT)


def test_both_bases_falling_in_one_step_is_a_loss():
    w = World(level=level(enemy_hp=1, player_hp=1, reward=25))
    w.blue.spawn(100, config.ENEMY_HIT_Y + 2, vy=-config.AGENT_SPEED)
    w.red.spawn(400, config.PLAYER_BASE_Y - 2, vy=260)
    run(w, DT)
    assert w.enemy_hp == 0 and w.player_hp == 0
    assert w.status == "lost" and w.tokens == 0


def test_sandbox_level_has_every_key():
    w = World()
    for key in ("id", "name", "enemy_hp", "player_hp", "reward", "gates", "waves"):
        assert key in w.level, key
    assert w.level["reward"] == 0 and w.level["enemy_hp"] == 100


def test_load_level_keeps_tokens_pools_and_keys():
    w = World(level=level(enemy_hp=1, reward=10))
    run(w, 0.2, fire=True)
    run(w, 4.0)
    assert w.status == "won" and w.tokens == 10
    pool = w.blue
    w.set_input(False, True, False)
    w.load_level(get_level(2))
    assert w.status == "playing" and w.level["id"] == 2
    assert w.tokens == 10 and w.blue is pool and w.blue.count == 0 and w.red.count == 0
    assert w.enemy_hp == w.enemy_hp_max == get_level(2)["enemy_hp"] and w.tick == 0
    run(w, 0.25, right=True)
    assert w.launcher_x > config.FIELD_W / 2  # held keys survive loading
    w.action("restart")
    assert w.level["id"] == 2  # restart replays the loaded level


def test_load_level_copies_the_level():
    lv = get_level(1)
    w = World()
    w.load_level(lv)
    run(w, 1.0)
    assert lv == get_level(1)
