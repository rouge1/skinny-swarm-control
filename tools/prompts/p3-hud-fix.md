Review feedback on your client polish (quality 25/30, no correctness bugs). Fix these; edit only files in
swarm_control/web/. Do not list or read anything outside the working directory.

1. [medium] drawGates() calls fitFont() every frame for every gate (a measureText shrink loop of up to ~14
   iterations). Cache the fitted font size keyed by label + gate width and recompute only when either changes.
2. [medium] drawBugs() adds 6 leg segments per bug to the path that is then stroked: ~24,000 disjoint segments at
   4,000 bugs, the most likely frame-rate risk at full load. Keep one path per colour, but draw legs only while the
   bug count is below ~800 (above that, bodies only), and use at most 4 short legs per bug.
3. [low] fitFont()'s `while (size > 8)` never applies the 8 px floor; make the floor inclusive.

Done when `/data/python/learn/swarm-control/.venv/bin/ruff check .` passes.
