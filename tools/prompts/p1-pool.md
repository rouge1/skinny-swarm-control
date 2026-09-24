Task: implement `UnitPool` in `swarm_control/sim/pool.py`.

Read `AGENTS.md` first and follow it. Then read the contract in the module docstring of
`swarm_control/sim/pool.py` and the acceptance tests in `tests/test_pool.py`.

Requirements:
- Replace the stub class with a full implementation of the documented interface.
- Edit only `swarm_control/sim/pool.py`. Do not edit the tests.
- Vectorise with numpy: no Python loops over units in spawn_many, despawn, step, cull or clear.
- Keep `count` O(1).

Done when both of these succeed with no failures or errors:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_pool.py
    /data/python/learn/swarm-control/.venv/bin/ruff check .
