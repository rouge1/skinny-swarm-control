# Swarm Control

A Mob Control-style browser game about managing a swarm of coding agents. Slide the launcher, fire agents
up the field, multiply them through gates like `x2 fork` and `+5 subagents`, and push back the bugs pouring
out of PRODUCTION.

Python (FastAPI + numpy) runs the simulation; the browser draws it on a canvas and sends keyboard input
over a WebSocket.

## How to play

Push back the bugs across 3 levels — First Contact, Parallel Front, Swarm Cascade — by wearing down the
PRODUCTION fortress HP before the bugs overrun your base. Agents that reach the fortress deal 1 damage
each; bugs that reach your base line damage you. Agents and bugs annihilate on contact.

| Key | Action |
|---|---|
| ← / → or A / D | move the launcher |
| Space | start the game / fire agents (hold) |
| P | pause / resume |
| R | restart the level |
| 1 / 2 / 3 (numpad digits work too) | buy fire-rate / multishot / speed in the shop |
| N | advance to the next level from the shop |
| H or ? | open / close the help overlay (Escape closes it too) |
| M | toggle motion effects (hit-flash, particles, screen shake) |

A title screen shows before level 1 — press Space to start.

Between levels a SHIPPED! shop overlay appears. Winning a level pays a one-time token reward (40 / 80 /
120 for levels 1–3); tokens and upgrades persist for the whole session, across restarts. Each shop row
shows its level and next price (or MAX); a row is dimmed until you can afford it:

- **1 — Fire rate** (max 4, prices 20/40/80/160): shots come ×0.85 faster per level.
- **2 — Multishot** (max 2, prices 30/90): +1 agent per shot, fanned 12 px apart.
- **3 — Speed** (max 3, prices 15/30/60): launcher moves ×1.25 faster per level.

Buying only works while the shop is open (`won` status); `N` loads the next numbered level only from the
shop while another level exists. After the final level the campaign-complete screen shows your build and
`R` replays. Without a server, `?mock=1` runs a small standalone demo in the browser.

## Run it

Requires Python ≥ 3.12. Dependencies (`pyproject.toml`): `fastapi`, `uvicorn[standard]`, `numpy`.

    python3 -m venv .venv && .venv/bin/pip install -e .
    .venv/bin/python -m swarm_control.server        # then open http://127.0.0.1:8000

Tests and lint (from the repo root; `pytest`/`ruff` are dev tools, not game deps):

    .venv/bin/pip install pytest httpx ruff
    .venv/bin/python -m pytest
    .venv/bin/ruff check .

## Architecture

- `swarm_control/protocol.py` — WebSocket wire format: `input`/`action` JSON up, `state` JSON down.
- `swarm_control/config.py` — field coordinates (540 × 960, launcher y = 900, fortress y = 70) and tuning.
- `swarm_control/sim/` — `pool` (numpy unit pools), `combat` (contact annihilation, base hits),
  `gates` (multiplier gates), `waves` (spawn schedules + 3 `LEVELS`), `world` (launcher, step, shop).
- `swarm_control/server/app.py` — FastAPI app; one `World` per `/ws` connection.
- `swarm_control/web/` — plain canvas client (`game.js`, no build step): renders state, sends keys.
- Loop: `World.step(1/60)` at 60 Hz, `snapshot()` sent at 30 Hz over `/ws`.
- Acceptance contracts live in [`CONTRACTS.md`](CONTRACTS.md) (data flow, coordinates, phase specs;
  tests in `tests/`); each module's own docstring is its detailed contract.

## How the swarm built it

Built by an OpenCode worker swarm — luna, muse, flash — coordinated by a Claude orchestrator across
5 phases: pool bake-off, world + server, combat/gates/waves, campaign progression, polish + balance +
demo. Each phase ran in its own git worktree, and every change was reviewed by at least one other
model before merging to main (some, like the phase 1 and phase 4 bake-offs, by two or more). See [`tools/README.md`](tools/README.md) for the detailed build log: prompts, ledger,
event records, dashboard, and playtests.
