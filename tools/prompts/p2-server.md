Task: implement the FastAPI server in `swarm_control/server/app.py`.

Read `AGENTS.md` first and follow it. Then read `CONTRACTS.md`, the contract in the module docstring of
`swarm_control/server/app.py`, `swarm_control/protocol.py`, `swarm_control/config.py`, and the
`World` interface in `swarm_control/sim/world.py` (a stub right now; build against its interface).

Edit only `swarm_control/server/app.py`. Keep the documented interface.

Behaviour:
- `create_app(world_factory=World) -> FastAPI`, and a module-level `app = create_app()`.
- `GET /` returns `swarm_control/web/index.html`; `/static/...` serves files from `swarm_control/web/`.
  Resolve the web directory relative to this file, not the working directory.
- `WS /ws`: accept, create one world with `world_factory()`, send the hello message from `protocol.py`,
  then run a fixed-timestep loop: `world.step(1 / TICK_HZ)` at TICK_HZ, and send `world.snapshot()` every
  TICK_HZ // SEND_HZ steps. Correct for drift (schedule against a monotonic clock, not plain sleeps).
- Read client messages concurrently with the game loop (a separate asyncio task). Apply "input" only when
  left, right and fire are all real booleans; apply "action" only when it is one of `protocol.ACTIONS`.
  Ignore anything malformed (bad JSON, non-objects, unknown types, wrong field types) without closing.
- On disconnect, stop the loop and the reader task cleanly, with no errors logged.
- Never block the event loop.

Done when these succeed with no failures or errors:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_server.py tests/test_protocol.py
    /data/python/learn/swarm-control/.venv/bin/ruff check .
