You are doing CONSENSUS + RANKING for a 2-way client bake-off. Do not edit, create or delete any file. Do not run
any git command that changes state (no checkout/switch/worktree/commit/merge) — read-only commands only
(git show <ref>:<path>, git diff <refA>..<refB> -- <path>, git log) are fine. Do not list or read anything outside
the working directory, except via `git show <branch>:<path>` / `git diff` against the branches named below.

Two models each independently built the phase 4 SHOP + CAMPAIGN-COMPLETE screen in swarm_control/web/ from the
SPEC below, on the same starting point (branch p4/tests, which this worktree is checked out on). Two other models
(the one who did not write it, plus a third) reviewed each entry. The orchestrator ALSO play-tested both entries
live in a browser (Playwright, ?mock=1: play level 1 to a win, screenshot the shop, buy an upgrade, screenshot
again, continue through a 3-level mock campaign to the campaign-complete screen) and confirms: both entries
visually work correctly end to end (shop shows tokens/level/upgrade rows with level/max/price, buying updates
tokens and the row immediately, "N" advances levels, campaign-complete shows final tokens/upgrades) — no visual
regressions or crashes in either. Below are the entries' branches/commits and the review issues. Your job: verify
each review claim by reading the actual code with `git show <branch>:<path>` (cite exact lines), then rank the two
entries and score each 0-100 (100 = perfect spec compliance + clean, defensive code; deduct for confirmed bugs by
severity: high ~25-40 pts, medium ~10-15, low ~2-5).

ENTRIES:
- flash: branch p4/client-flash, commit 9bd0ae3.
- muse: branch p4/client-muse, commit 3635e31.

REVIEWS OF flash's ENTRY (by luna and muse):
--- luna ---
verdict: pass
issues:
- none
--- muse ---
verdict: pass
issues:
(none reported)

REVIEWS OF muse's ENTRY (by luna and flash):
--- luna ---
verdict: changes
issues:
- [medium] swarm_control/web/game.js:259-266 Shop-only keys are handled regardless of game status, so N and 1/2/3 send actions during normal play, paused/lost states, and campaign completion; gate them on `status === "won"` and `hud.has_next` before calling `doAction`.
--- flash ---
verdict: changes
issues:
- [medium] swarm_control/web/game.js:259-267 `onKeyDown` fires `next`/`buy_*` for N and 1/2/3 regardless of status; gate these on `latest && latest.status === "won"` so they don't get sent during playing/paused/lost (mock already guards via `mockNext`/`mockBuy`, network path does not).
- [low] swarm_control/web/game.js:141-143 `trackLevel` assigns `levelStartTokens = s.hud.tokens` without defaulting, so a state whose `hud` briefly lacks `tokens` makes `shopHtml`'s `gained` NaN and renders "+(NaN) tokens"; use `s.hud.tokens || 0`.

Reply with exactly this format and nothing else:
consensus: <N> confirmed, <M> rejected
fix list (verified real defects, by entry):
- flash: [sev] <file:line> <fix>  (or "none")
- muse: [sev] <file:line> <fix>  (or "none")
rejected:
- <issue> — <why it doesn't hold up>  (or "none")
scores:
- flash: <0-100> — <one line why>
- muse: <0-100> — <one line why>
winner: flash | muse

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
