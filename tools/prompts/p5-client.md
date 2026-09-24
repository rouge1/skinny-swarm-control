Task: phase 5 client polish for the Swarm Control web client — title screen, help overlay, and juice.

Read AGENTS.md first and follow it. Do not list or read anything outside the working directory.
Read CONTRACTS.md, swarm_control/protocol.py (docstring, hud fields), swarm_control/config.py, and
swarm_control/web/ (index.html, style.css, game.js) to see the current renderer, state machine and mock mode.

Edit only swarm_control/web/game.js, swarm_control/web/style.css and swarm_control/web/index.html.

Behaviour:
1. Title screen: shown before level 1 starts (i.e. before any state has been received / before the first "playing"
   status), with the game name, a one-line pitch, the key list (arrows/A/D move, Space fire, P pause, R restart,
   M motion toggle, H help), and "press Space to start". Space dismisses it and starts play exactly like today's
   first frame did (do not change how the connection/mock is opened).
2. Help overlay: toggled by "?" or "H" at any time (even mid-game; pauses render updates the same way P does, or
   simply draws on top without altering game state — your call, but it must not desync input while open and must
   close on "?"/H/Escape). Content: the same key list as the title screen plus a one-line reminder of the goal
   (push back the bugs, multiply through gates, win 3 levels) and the shop keys (1/2/3 buy, N next, R restart).
3. Juice (no new dependencies, canvas/DOM + CSS only):
   - Brief hit flash on the fortress (enemy base) when it takes damage, and on the player base when a bug reaches
     it — a short (~100-150 ms) color/opacity flash, not a fixed-duration animation that drifts out of sync with
     repeated hits (retrigger cleanly on each hit).
   - Small particle burst (a handful of short-lived dots/sparks, plain canvas drawing, no images) when a gate
     multiplies (op "mul") or adds (op "add") agents, at the gate's position.
   - Gentle screen shake (small, brief canvas translate offset, a few px, decaying quickly) when the player base
     is hit. Toggle all three juice effects together with "M" (motion), default ON; state persists only for the
     session (no localStorage needed unless trivial).
   Keep the render loop cheap: still 30 Hz state handling, effects must not allocate unboundedly (cap particle
   count, reuse arrays/objects where the existing code already has a pattern for it).
4. Must stay readable and functional at the native 540x960 canvas size AND when the browser window is resized/
   scaled down to about 900x1000 (canvas scaling / CSS, whatever the existing responsive approach is — extend it,
   don't replace it). No console errors in either size.
5. Keep every existing key/behaviour working: arrows/A/D move, Space fire, P pause, R restart, N/1/2/3 shop keys
   from phase 4, mock mode (?mock=1), campaign-complete screen.

Done when: `node --check swarm_control/web/game.js` passes (if node exists), and
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_server.py -q
still collects and passes (server tests don't touch the client, so this just confirms you haven't broken the
Python side by mistake). End with a short summary: files changed, what you implemented, any tradeoffs.
