Task: build the browser client: `swarm_control/web/game.js` and `swarm_control/web/style.css`.

Read `AGENTS.md` first and follow it. Then read `CONTRACTS.md`, `swarm_control/protocol.py` (the message
format) and `swarm_control/config.py` (field size and positions). The page shell is
`swarm_control/web/index.html`; you may edit it but must keep `<canvas id="game">` and the
`/static/style.css` and `/static/game.js` paths.

Edit only files in `swarm_control/web/`. Plain JavaScript (no modules, no build step, no libraries, no CDNs).

The game: Swarm Control, a Mob Control-style game. The player's launcher at the bottom fires coding agents
(blue) up the field; bugs (red) come down from the "PRODUCTION" fortress at the top. Gates multiply agents.

Requirements:
1. Connection: open `ws(s)://<host>/ws`. The first message is "hello" with the field size; then "state"
   messages ~30 per second. Show a "Connecting…" overlay until the first state; reconnect with backoff
   if the socket closes.
2. Canvas: the field is 540 x 960 logical px. Scale to fit the window height (and width on narrow screens),
   keep the aspect ratio, centre it, and render sharply on high-DPI screens (devicePixelRatio).
3. Rendering, every animation frame, from the latest state:
   - Dark field with faint vertical lane lines.
   - The fortress at the top (y around 70): a wide block labelled PRODUCTION with an HP bar from
     bases.enemy_hp / enemy_hp_max.
   - The player base line near y = 940 with an HP bar from bases.player_hp / player_hp_max.
   - The launcher at launcher.x, launcher.y: a distinct shape (not a plain circle).
   - Agents (blue list) as small blue circles, bugs (red list) as small red circles, radius about 5.
     There can be 4,000 of each: draw each colour in ONE path (one beginPath/fill per colour), no per-unit
     fill calls, no per-unit object allocation.
   - Gates: translucent rectangles (x, y is the top-left, w, h) with the label centred in bold text.
     Colour "mul" and "add" gates differently.
   - HUD along the top: agents (hud.blue_count), bugs (hud.red_count), level, tokens.
   - Overlays for status "paused", "won" and "lost", each with the keys to continue.
4. Keyboard:
   - ArrowLeft or A: left. ArrowRight or D: right. Space (hold): fire.
   - Send {"type":"input","left":bool,"right":bool,"fire":bool} with the full key state, only when it changes.
   - P: send action "pause" when playing, "resume" when paused. R: send action "restart".
   - Prevent the page from scrolling on Space and the arrows. Ignore key auto-repeat.
   - On window blur, release all keys (send all false).
   - Show a small key legend under or beside the canvas.
5. Mock mode: with `?mock=1` in the URL, do not connect; generate fake but valid state messages locally at
   30 Hz (a moving launcher you can steer with the keys, agents flying up, a few bugs coming down, two gates)
   so the client can be checked without the server.

Keep the code organised in small functions with a short comment per section.

Done when: `node --check swarm_control/web/game.js` passes (if node is installed) and
`/data/python/learn/swarm-control/.venv/bin/ruff check .` passes. The orchestrator will playtest in Chrome.
