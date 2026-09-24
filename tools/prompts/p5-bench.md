Task: write a headless PERFORMANCE BENCHMARK for the Swarm Control simulation, used in phase 5.

Read AGENTS.md first and follow it. Do not list or read anything outside the working directory.
Read swarm_control/config.py, swarm_control/sim/world.py, swarm_control/sim/pool.py, swarm_control/sim/combat.py,
swarm_control/sim/gates.py, swarm_control/protocol.py (pack_units) and tests/test_world_p3.py
(test_step_performance_under_load shows how to load a world with units).

Create only scripts/bench.py (new; do not edit any other file). It must:
- For unit loads of 500, 1000, 2000, 3000 and 4000 total (half blue, half red, spread over the field as in the
  test; configurable with --loads), with the level-1 gates active, measure per-step time over at least 2 s of game
  time: mean, p50, p95, max in milliseconds, and the fraction of the 60 Hz budget (16.7 ms) used.
- Break the step down by phase (movement, gates, combat, bases/cleanup, snapshot+pack) by timing the World's
  internal calls from the outside (e.g. wrap functions with time.perf_counter via monkeypatching in the script
  only). If a phase cannot be isolated, say so in the output instead of guessing.
- Also time snapshot() + json.dumps at each load (this runs at 30 Hz on the server).
- Optional --profile runs cProfile at the heaviest load and prints the top 15 functions by cumulative time.
- Print an aligned text table; --json writes the data to a file. Standard library + numpy only. No game-code edits.

Done when:
    /data/python/learn/swarm-control/.venv/bin/python scripts/bench.py
runs in under 2 minutes and prints the table, and `/data/python/learn/swarm-control/.venv/bin/ruff check .` passes.
