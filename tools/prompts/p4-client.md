Task: build the phase 4 between-levels SHOP and the CAMPAIGN-COMPLETE screen in the Swarm Control web client.

Read AGENTS.md first and follow it. Do not list or read anything outside the working directory.
Read CONTRACTS.md (the "Phase 4" section), swarm_control/protocol.py (docstring, ACTIONS, validate_state for the new
hud fields), swarm_control/config.py (phase 4 upgrade constants) and swarm_control/web/ (index.html, style.css,
game.js). The server already forwards any action in protocol.ACTIONS to the World.

Edit only swarm_control/web/game.js, swarm_control/web/style.css and swarm_control/web/index.html.

Behaviour (from the state message; hud now also has has_next, upgrades, prices, level_name):
- While status == "won" and hud.has_next: the win overlay becomes the shop. Show tokens, the level just beaten
  (level_name), and three rows: fire rate / multishot / speed, each with current level, max level and next price
  ("MAX" when price is null). Rows the player can't afford are dimmed. Keys: 1 = buy_fire_rate, 2 = buy_multishot,
  3 = buy_speed, N = next, R = restart (replay). Send them as {"type":"action","action":...}.
  The overlay must refresh when tokens/upgrades change while it is shown (today it only redraws on status change).
- While status == "won" and not hud.has_next: a campaign-complete screen (total tokens, final upgrades, R to replay).
- Show level_name and the upgrade levels somewhere small in the in-game HUD.
- Mock mode (?mock=1) must keep working standalone: extend the mock snapshot with the new hud fields and let the
  mock handle next/buy locally (a 3-level mock campaign is enough), so the shop can be tried without the server.
- Keep the existing keys (arrows/A/D move, Space fire, P pause, R restart) and the 30 Hz render performance.

Done when: `node --check swarm_control/web/game.js` passes (if node exists), and
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_server.py -q
still collects and runs (server tests may fail only on the hud-field validation the world hasn't implemented yet).
