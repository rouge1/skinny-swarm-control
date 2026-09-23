# Rules for worker agents

You are a worker on **Swarm Control**, a Mob Control-style browser game written in Python.
An orchestrator assigns you one task at a time and a reviewer reads every line you write.

## Hard rules
1. **Edit only the files your task names.** Create new files only where your task says so.
2. **Never edit** anything in `tests/`, `CONTRACTS.md`, `AGENTS.md`, `pyproject.toml`,
   `swarm_control/config.py` or `swarm_control/protocol.py`. If you think one of them is wrong,
   say so in your final message instead.
3. **Stay inside the current working directory.** Do not read or write files outside it.
4. **Do not run git commands** that change state (no commit, branch, checkout, reset, stash).
5. **No new dependencies.** Available: Python 3.12 standard library, numpy, fastapi, uvicorn.
   The web client is plain HTML/CSS/JavaScript with no build step and no CDN libraries.
6. Do not start long-running servers. Do not use `sudo`.

## Checking your work
Use the shared virtualenv (it is outside this directory, which is allowed for running it):

    /data/python/learn/swarm-control/.venv/bin/python -m pytest
    /data/python/learn/swarm-control/.venv/bin/ruff check .

Your task is done when the tests named in the task pass and ruff reports no errors.

## Style
- Match the surrounding code. Type hints on public functions. Short docstrings.
- numpy: vectorise bulk work; no Python loops over units.
- Keep the public interface exactly as documented in the module docstring / CONTRACTS.md.

## Finish
End with a short summary: files changed, what you did, test result, anything you could not do.
