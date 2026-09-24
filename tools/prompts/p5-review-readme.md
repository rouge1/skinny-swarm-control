You are a REVIEWER on Swarm Control. Do not edit, create or delete any file. Do not run git commands that change
state. Do not list or read anything outside the working directory.

Another model rewrote README.md for phase 5. See what changed with:
    git diff main -- README.md
Cross-check every factual claim against the actual code: swarm_control/web/game.js (key bindings — do not trust
the README, verify each key it documents is really bound, and flag any implemented key it left out), pyproject.toml
or setup instructions actually needed to run the project, CONTRACTS.md, AGENTS.md, and swarm_control/ module
layout (protocol/config/sim/server/web).

Review for:
1. Accuracy: every key, command, and architectural claim matches the code. Flag anything invented or stale
   (leftover from before phase 4/5, e.g. missing the shop keys or the new title/help/motion keys).
2. Completeness against the spec below: how to play (keys, goal, shop), how to run, architecture in ~10 lines,
   and how the swarm built it (models, phases, pointer to build records).
3. Concision: README, not a design doc — flag if it's bloated or duplicates CONTRACTS.md/AGENTS.md content that
   should just be linked instead.
4. Markdown hygiene: tables/links/code blocks well-formed.

Reply with exactly this format and nothing else:
verdict: pass | changes
issues:
- [high|medium|low] <file:line or section> <one line: what is wrong and the fix>

SPEC:
## C. Docs (README.md only)
How to play (keys, goal, shop), how to run, architecture in 10 lines, and how the swarm built it (models, phases,
link to tools/ records). One author, one reviewer.
