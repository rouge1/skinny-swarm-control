Task: implement `swarm_control/sim/gates.py` for Swarm Control phase 3.

Read `AGENTS.md` first and follow it. Then read the contract in the module docstring of
`swarm_control/sim/gates.py` (it is the spec), the acceptance tests in `tests/test_gates.py`,
`swarm_control/config.py` and `swarm_control/sim/pool.py` (the UnitPool you work with; do not change it).

Edit only `swarm_control/sim/gates.py`. Replace the stubs with a full implementation of the documented
interface. Remove the "noqa ... (for the implementation)" placeholder comments on imports you use and
delete imports you do not use.

Correctness beyond the tests matters: a reviewer will probe edge cases (empty pools, boundaries,
bad input, determinism) and read every line. Validate inputs before changing any state.
Vectorise bulk work with numpy; no Python loops over units.

Done when these pass with no failures or errors:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_gates.py tests/test_pool.py
    /data/python/learn/swarm-control/.venv/bin/ruff check .
