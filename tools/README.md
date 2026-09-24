# How this game was built

Swarm Control was built by a small swarm of AI coding agents, with Claude Code as the orchestrator.

- **Orchestrator (Claude Code):** splits the work into phases, writes the interfaces and acceptance tests,
  writes each task prompt, merges, and playtests.
- **Workers (OpenCode):** GPT-5.6 Luna, Muse Spark 1.3 Contributor and DeepSeek V4.1 Flash. Each task runs in
  its own git worktree and branch; workers may only edit the files their task names (see `../AGENTS.md`).
- **Reviewer (Claude subagent):** reads every branch, probes edge cases, and sends findings back to the
  worker that wrote the code for a fix round before anything is merged.

| File | What it is |
|---|---|
| `swarm.py` | Runs a worker (`run`), records time/tokens/cost to the ledger, logs events, prints `status`, exports the dashboard data and a standalone replay page (`export`) |
| `dashboard.html` | The live ops dashboard; also the replay player |
| `playtest.py` | Headless Playwright playtest that plays a scripted run and saves screenshots |
| `prompts/` | Every task and fix prompt given to the workers and the reviewer |
| `records/events.jsonl` | Every event of the build, in order (the dashboard and replay are built from this) |
| `records/ledger.jsonl` | One line per worker run: model, phase, task, wall time, model time, tokens, cost |
| `shots/` | Playtest screenshots per phase |

Phase 1 was a bake-off: all three models got the same task and tests, a blind review scored them, and the
winner was merged. The losing entries are kept on the `p1/pool-flash` and `p1/pool-muse` branches.
