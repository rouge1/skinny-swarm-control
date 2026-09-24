# Swarm Control

A Mob Control-style browser game about managing a swarm of coding agents. Slide the launcher, fire agents
up the field, multiply them through gates like `x2 fork` and `+5 subagents`, and push back the bugs pouring
out of PRODUCTION.

Python (FastAPI + numpy) runs the simulation; the browser draws it on a canvas and sends keyboard input
over a WebSocket.

## Run it

    python3 -m venv .venv && .venv/bin/pip install fastapi 'uvicorn[standard]' numpy
    .venv/bin/python -m swarm_control.server        # then open http://127.0.0.1:8000

| Key | Action |
|---|---|
| ← / → or A / D | move the launcher |
| Space (hold) | fire agents |
| P | pause / resume |
| R | restart |

## Tests

    .venv/bin/pip install pytest httpx ruff
    .venv/bin/python -m pytest && .venv/bin/ruff check .

## How it was built

By AI agents working in phases, each in its own git worktree, with every branch reviewed before merging.
See [`tools/README.md`](tools/README.md), [`CONTRACTS.md`](CONTRACTS.md) and [`AGENTS.md`](AGENTS.md).
