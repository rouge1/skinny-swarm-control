You are a REVIEWER on Swarm Control. Do not edit, create or delete any file. Do not run git commands that change
state. Do not list or read anything outside the working directory. Do not start the server or a browser. Read code
only (game.js, index.html, style.css) plus a static syntax check.

Another model added phase 5 client polish (title screen, help overlay, juice effects) to the web client from the
spec below. See what changed with:
    git diff main -- swarm_control/web/

Run `node --check swarm_control/web/game.js` if node exists (skip if not) and
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_server.py -q
and note whether it still collects/passes.

Review for:
1. Title screen shows before the first playing state, has name/pitch/key list/"press Space to start", and Space
   dismisses it into the exact same first-play behaviour as before this change.
2. Help overlay opens on "?" or "H", closes cleanly (on the same keys and/or Escape), doesn't desync game state or
   leak input to the game while open (e.g. movement/fire keys still working underneath, or intentionally
   suppressed — either is fine, but check it doesn't do something broken like firing while the overlay covers
   the canvas).
3. Juice: hit-flash on fortress/player-base retriggers cleanly on repeated hits (not a single fixed animation that
   can only play once or gets stuck); particle burst on gate multiply/add is capped (no unbounded array growth —
   look for a max count or removal of expired particles every frame); screen shake is small, brief and decaying,
   not jarring or permanent. "M" toggles all three together, default on.
4. No new dependencies, no CDN/script tags added, plain canvas/DOM/CSS only.
5. Readable at native 540x960 and when scaled to ~900x1000 — check the resize/scaling code path (existing or
   newly added) actually applies to the new UI (title screen, help overlay), not just the in-game HUD.
6. Regressions: every existing key (arrows/A/D, Space fire, P pause, R restart, 1/2/3 buy, N next) and mock mode
   (?mock=1) still work; the 30 Hz state-handling loop is not slowed by the new effects (no per-frame allocation
   of large arrays, no O(particles^2) work).
7. No console errors introduced (read the code for obvious throw sites: undefined property access on hud fields
   that might be briefly absent during a status transition, array index errors, etc).

Reply with exactly this format and nothing else:
verdict: pass | changes
issues:
- [high|medium|low] <file:line> <one line: what is wrong and the fix>

SPEC:
## B. Client polish (web/ only)
- Title screen before level 1 (name, one-line pitch, keys, "press Space to start"), and a "?" / H help overlay.
- Juice without new deps: brief hit flash on the fortress/base when damaged, small particle burst when a gate
  multiplies, gentle screen shake when the player base is hit (toggle with M for motion). Keep 30 Hz render cheap.
- Readable at 540x960 and scaled down to a 900x1000 browser window; no console errors.
