You are a REVIEWER on Swarm Control. Do not edit, create or delete any file. Do not run git commands that change
state. Do not list or read anything outside the working directory. Do not start the server or a browser. Read code
only (game.js, index.html, style.css) plus a static syntax check.

Another model built the phase 4 SHOP and CAMPAIGN-COMPLETE screen in the web client from the spec below, on top of
the already-committed phase 4 tests (client-only worktree: swarm_control/sim/ still lacks the phase 4 World changes,
so any pytest failures under tests/test_progression.py, tests/test_protocol.py, tests/test_world*.py or the hud-field
parts of tests/test_server.py are expected here and NOT your concern). See what changed with:
    git diff main -- swarm_control/web/

Run: node --check swarm_control/web/game.js (skip if node is not installed) and
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_server.py -q
and note whether it still collects/runs (ignore hud-field-validation failures caused by the missing World changes).

Review for:
1. Shop overlay: shown while status=="won" and hud.has_next; displays tokens, level_name, and each upgrade's
   level/max/price ("MAX" when price is null); rows the player can't afford are visually dimmed.
2. Keys while the shop is shown: 1/2/3 send {"type":"action","action":"buy_fire_rate"|"buy_multishot"|"buy_speed"},
   N sends "next", R sends "restart". Keys must not fire while status != "won" (don't hijack normal play keys) or
   leak buys when maxed/unaffordable (fine to send anyway if the spec allows the server to ignore it, but check the
   prompt's intent: sending an obviously-inert buy for a dimmed row is acceptable, silently changing local state
   without a server round-trip is not).
3. Live refresh: the shop re-renders when tokens/upgrades change while shown (not only on a status transition) —
   look for the render loop reading hud fields every frame/tick rather than caching them once on entry.
4. Campaign-complete screen: shown while status=="won" and not hud.has_next; shows total tokens and final upgrade
   levels; R restarts (replays final level, per existing restart semantics).
5. In-game HUD: level_name and upgrade levels visible somewhere small during play, not just in the shop overlay.
6. Mock mode (?mock=1): still works standalone; mock snapshot carries has_next/upgrades/prices/level_name; mock
   handles next/buy locally with a multi-level (>=3) fake campaign, so the shop and campaign-complete screen are
   both reachable without a server. Check it doesn't call a real network path when in mock mode.
7. Regressions: existing keys (arrows/A/D move, Space fire, P pause, R restart) and the 30 Hz render loop still
   present and untouched in shape; no dead code paths or leftover TODOs that change behavior silently.
8. Robustness: code defends against hud fields being briefly absent/undefined during a state transition (no thrown
   exceptions that would freeze the render loop).

Reply with exactly this format and nothing else:
verdict: pass | changes
issues:
- [high|medium|low] <file:line> <one line: what is wrong and the fix>

SPEC:
Task: build the phase 4 between-levels SHOP and the CAMPAIGN-COMPLETE screen in the Swarm Control web client.
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
