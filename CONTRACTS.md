# Contracts

The interfaces between modules. Each module's docstring holds its detailed contract; the tests in
`tests/` are the acceptance criteria. Workers build against these and must not change them.

| Module | Owner (phase) | Contract | Acceptance tests |
|---|---|---|---|
| `swarm_control/config.py` | orchestrator (P0) | constants, field coordinates | – |
| `swarm_control/protocol.py` | orchestrator (P0) | WebSocket messages, `pack_units`, `validate_state` | `tests/test_protocol.py` |
| `swarm_control/sim/pool.py` | bake-off (P1) | `UnitPool` fixed-capacity numpy pool | `tests/test_pool.py` |
| `swarm_control/sim/world.py` | P2 world core | `World` step/snapshot/input | `tests/test_world.py` |
| `swarm_control/server/app.py` | P2 server | `create_app`, `/`, `/static`, `/ws` | `tests/test_server.py` |
| `swarm_control/web/` | P2 client | canvas renderer + keyboard | playtest in Chrome |

## Phase 4

`World` owns campaign progression for the life of one browser session. Its `tokens` and
three upgrade levels persist across `restart`, `next`, and `load_level`. `next` loads the
next numbered level only while the current status is `won` and another level exists;
otherwise it has no effect. The shop actions `buy_fire_rate`, `buy_multishot`, and
`buy_speed` work only while `status == "won"`, and only when the player can pay the
next price and has not reached the upgrade maximum. Each successful action spends the
price and increases that upgrade by one. Fire rate multiplies `FIRE_INTERVAL` by 0.85
per level; multishot adds one agent per level, fanned 12 pixels apart and centered on
the launcher; speed multiplies launcher speed by 1.25 per level.

The state HUD includes `has_next` (bool), `upgrades` (the three integer upgrade
levels), `prices` (the next integer price for each upgrade, or `None` when maxed), and
`level_name` (str), in addition to the existing fields. Winning a level adds its
integer reward once. After the final level is won, status remains `won`, `has_next`
is false, and `next` does nothing.

## Data flow

    browser (web/)  --input/action JSON-->  server (/ws)  --set_input/action-->  World
    browser (web/)  <--state JSON 30 Hz---  server        <--snapshot()-------   World.step(1/60)

## Coordinates
Field is 540 × 960 px, origin top-left, y down. Launcher at y = 900. Agents (blue) move up;
bugs (red) come down from the fortress at y = 70.

## Keyboard (client)
| Key | Action |
|---|---|
| ← / → or A / D | move the launcher |
| Space (hold) | fire agents |
| P | pause / resume |
| R | restart |
