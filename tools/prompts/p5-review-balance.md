You are a REVIEWER on Swarm Control. Do not edit, create or delete any file. Do not run git commands that change
state. Do not list or read anything outside the working directory. You may run the test suite, ruff, and
scripts/balance.py with /data/python/learn/swarm-control/.venv/bin/python to probe.

Another model retuned swarm_control/sim/waves.py LEVELS to fix phase 5 balance problems, on top of the already-
committed acceptance tests (tests/test_balance.py). See what changed with:
    git diff p5/balance-tests -- swarm_control/sim/waves.py

Run the full suite first: /data/python/learn/swarm-control/.venv/bin/python -m pytest -q
and note the pass/fail count, plus ruff: /data/python/learn/swarm-control/.venv/bin/ruff check .
Then run: /data/python/learn/swarm-control/.venv/bin/python scripts/balance.py --seeds 3
and include its WARNINGS section (or "none") in your notes.

Review for:
1. Targets met: idle and every stand@x player lose every level, every seed; sweep and sweep-fast win every level,
   every seed; sweep's median time-to-win is 45-75s on level 1, 70-100s on level 2, 95-130s on level 3 (rising);
   an upgraded playthrough beats an unupgraded one on every level. tests/test_balance.py is the ground truth for
   this — if it passes, trust it, but still sanity-check the balance.py table matches (no surprising 0% sweep wins
   etc).
2. Minimality: only fields inside LEVELS entries were touched (no changes to get_level, validate_level,
   WaveSpawner, or any file other than waves.py). Diff size vs p5/balance-tests — smaller is better if it still
   meets every target; note the diff's line count.
3. Level integrity: still exactly 3 levels (ids 1,2,3 in order), each still harder than the previous by total bug
   count and enemy_hp (per the waves.py module docstring contract), gate labels still read like the theme (fork /
   subagents / worktree / etc), gates still pass validate_level (in bounds, thick enough, reachable band).
4. No overfitting / cheap tricks: e.g. don't flag a legitimate fix as a trick, but do flag anything that only
   works because of how the specific scripted test players move (e.g. gate placed exactly on a stand@x seam) in
   a way a real human player wouldn't experience as fair, or anything that makes a level trivially easy/hard by
   an extreme value out of step with the level's neighbours.

Reply with exactly this format and nothing else:
verdict: pass | changes
issues:
- [high|medium|low] <file:line> <one line: what is wrong and the fix>
diff_lines: <N>
balance_warnings: <what scripts/balance.py --seeds 3 WARNINGS said, or "none">

SPEC:
## A. Balance (waves.py LEVELS gates/waves/hp/rewards; tests first)
Targets, measured with `scripts/balance.py --seeds 5` and NO upgrades bought:
- idle and every stand@x player LOSE every level on every seed (today stand@180 wins L1 in 43 s: fix it).
- sweep wins 100% on every level; median sweep win time rises with level: L1 45-75 s, L2 70-100 s, L3 95-130 s
  (today L3 is faster than L2). sweep-fast also wins every level.
- With upgrades (buy what level rewards allow, greedily cheapest first), each level is won faster than without.
The winner is the entry that meets all targets with the smallest change.
