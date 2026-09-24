Luna reviewed scripts/bench.py. Fix these two issues; edit only scripts/bench.py. Do not list or read anything
outside the working directory.
- [high] bench.py:58-74 --loads above the combined pool capacity (2 x config capacity) is silently truncated while the
  report still labels it with the requested load and wrong blue/red counts. Report the actual spawned counts, and
  warn (stderr) when a load was capped.
- [low] bench.py:193-194 the table header always claims ">= 2 s of game time" even when --seconds is shorter; print
  the actual measured duration.
Done when `python scripts/bench.py --loads 500,9000` and `python scripts/bench.py --seconds 0.1 --loads 500` run
correctly (use /data/python/learn/swarm-control/.venv/bin/python) and ruff passes.
