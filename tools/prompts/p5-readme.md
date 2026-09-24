Task: write the final phase 5 README.md for Swarm Control.

Read AGENTS.md first and follow it. Do not list or read anything outside the working directory.
Read the current README.md, CONTRACTS.md, AGENTS.md, swarm_control/config.py, swarm_control/web/index.html and
tools/README.md (if it exists) to ground the doc in what actually exists; do not invent features.

Edit only README.md.

Contents, in this rough order:
1. What the game is (one or two lines) — keep the existing pitch tone (Mob Control-style, coding-agent swarm
   theme: fork gates, subagent gates, worktree gates, PRODUCTION as the enemy fortress).
2. How to play: the full current key list (movement, fire, pause, restart, the phase 4 shop keys 1/2/3/N, and the
   phase 5 title screen / help overlay keys ? or H, and M for motion/juice toggle — check swarm_control/web/game.js
   for the exact current key bindings rather than assuming; if a key you'd expect isn't implemented, don't document
   it), the goal (push back the bugs across 3 levels), and how the between-level shop works (tokens, three
   upgrades, buying).
3. How to run it: venv setup + server start (keep accurate to the current pyproject.toml / dependency list) and
   how to run the tests and ruff.
4. Architecture in about 10 lines: the module layout (protocol/config/sim/server/web), the simulation loop and
   WebSocket state flow, and where to find the acceptance-test contracts (CONTRACTS.md).
5. How the swarm built it: this was built by an OpenCode worker swarm (models: luna, muse, flash) coordinated by
   a Claude orchestrator across 5 phases (pool/bake-off, world+server, combat/gates/waves, campaign progression,
   polish+balance+demo), each phase in its own git worktree with every change reviewed (often by 2+ models) before
   merging to main. Link to tools/ (or the swarm-ops repo's ledger/records if tools/README.md exists and explains
   where records live) for the detailed build log; don't fabricate a link if nothing suitable exists — say where
   the records are in plain words instead.

Keep it concise (README, not a design doc) — a few hundred lines at most, prefer well under 150.

Done when: the file is well-formed Markdown (no broken tables/links) and
    /data/python/learn/swarm-control/.venv/bin/python -m pytest -q
still passes (README changes shouldn't affect this; this just confirms you haven't touched anything else).
End with a short summary of the sections you wrote and anything you weren't sure was accurate.
