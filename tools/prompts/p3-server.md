Small task: in `swarm_control/server/app.py`, make every new WebSocket connection start a real game on level 1
instead of an empty sandbox World.

Read `AGENTS.md` first. Do not list or read anything outside the working directory. Edit only
`swarm_control/server/app.py`.

- The World now exposes `new_game(seed=0) -> World` in `swarm_control/sim/world.py` (level 1). It exists on the
  branch that will be merged next; in your branch, import it with a fallback so the file works either way is NOT
  needed — just import `new_game` from `swarm_control.sim.world` and use it as the default: `create_app(world_factory=new_game)`.
- Nothing else changes: tests pass a custom `world_factory` and must keep working.

Note for this branch only: `new_game` does not exist in your branch's world.py yet, so the module-level `app` will
fail to import here. That is expected; the orchestrator verifies after merging with the World branch. Do not edit
world.py. Run only ruff:
    /data/python/learn/swarm-control/.venv/bin/ruff check .
