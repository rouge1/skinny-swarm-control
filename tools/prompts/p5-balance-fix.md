Luna reviewed scripts/balance.py. Fix this issue; edit only scripts/balance.py. Do not list or read anything outside
the working directory.
- [medium] balance.py:102-106 runs that reach the 180 s cap are still "playing" but are reported like finished runs,
  and the warning logic treats every non-win as a loss. Record an explicit "timeout" outcome, show timeout counts in
  the table (e.g. a "to%" column), and make the warnings distinguish timeouts from losses (a sweep that times out
  is its own warning).
Done when `/data/python/learn/swarm-control/.venv/bin/python scripts/balance.py --seeds 1` runs and ruff passes.
