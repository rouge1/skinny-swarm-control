Your previous turn stopped after a bash command was denied (it listed a directory outside your working
directory). Nothing was written yet. Continue the task now:

- Do not list or read directories outside the current working directory. You do not need to inspect the
  virtualenv; just run the two commands below exactly as written.
- Write the full implementation of `swarm_control/sim/waves.py` (WaveSpawner, LEVELS with at least 3 themed
  levels, get_level, validate_level) as specified in its module docstring and tests/test_waves.py.

Done when these pass:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_waves.py tests/test_pool.py
    /data/python/learn/swarm-control/.venv/bin/ruff check .
