Task: polish the browser client for phase 3 (gates, bugs, bases, win/lose) in `swarm_control/web/`.

Read `AGENTS.md` first and follow it. Read `CONTRACTS.md`, `swarm_control/protocol.py`, `swarm_control/config.py`
and the current `swarm_control/web/game.js`, `style.css`, `index.html`. Edit only files in `swarm_control/web/`.
Plain JavaScript, no libraries, no build step. Do not list or read anything outside the working directory.

The server will now send real gates, bugs (the "red" list), falling base HP, and "won"/"lost" status.
Improve the client:
1. Gates: rounded rectangles; "mul" gates green, "add" gates amber; the label (e.g. "x2 fork", "+5 subagents")
   centred in bold, shrinking the font to fit the gate width.
2. Bugs: draw each bug as a small beetle-like shape (body circle plus a few leg strokes) instead of a plain circle,
   still ONE path for all bugs (one beginPath / fill / stroke for the whole red list). Agents stay blue circles.
3. Damage feedback: when bases.enemy_hp drops since the previous state, flash the fortress bright for ~120 ms;
   when bases.player_hp drops, shake the field for ~150 ms and show a brief red edge glow. Show both HP values as
   numbers on their bars (e.g. "83 / 100").
4. Win and lose screens:
   - won:  big "SHIPPED!", a line "Production is bug-free", "+<tokens gained> tokens" (tokens now minus tokens at
     the start of the level), and "Press R to play again".
   - lost: big "OUTAGE", a line "Bugs reached your base", and "Press R to try again".
   Readable in both, centred, with a translucent backdrop.
5. HUD: colour the agent count blue and bug count red; keep level and tokens.
6. Mock mode (?mock=1): add moving gates that multiply mock agents passing through, bugs walking down, falling
   HP on both sides when units reach a base, and switch to "won" after about 20 seconds so the win screen can be
   checked. Keep the mock state valid per protocol.py.
7. Keep the performance rules: one path per colour, no per-unit allocation, requestAnimationFrame loop that
   survives a bad state.

Done when `/data/python/learn/swarm-control/.venv/bin/ruff check .` passes. The orchestrator will playtest in a
browser.
