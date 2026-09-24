You are doing CONSENSUS + RANKING for a 2-way balance bake-off. Do not edit, create or delete any file. Do not run
any git command that changes state (no checkout/switch/worktree/commit/merge) — read-only commands only
(git show <ref>:<path>, git diff <refA>..<refB> -- <path>, git log) are fine. Do not list or read anything outside
the working directory, except via `git show <branch>:<path>` / `git diff` against the branches named below.

Two models each independently retuned swarm_control/sim/waves.py LEVELS to fix phase 5 balance problems, on the
same starting point (branch p5/balance-tests, which added tests/test_balance.py — read-only, do not judge it).
Two reviewers checked each entry (one review of muse's entry needed a resumed session after it ran out of time
mid-investigation; both its parts are included below). Your job: verify each review claim by reading the actual
code with `git show <branch>:<path>` (cite exact lines) and, for the flagged exploit, you may also run a short
python snippet with /data/python/learn/swarm-control/.venv/bin/python to confirm it (a handful of World.step
calls at fixed launcher_x, like the reviews did — keep it under ~20 runs, do not re-scan exhaustively). Then rank
the two entries and score each 0-100 (100 = meets every target with minimal, non-exploitable changes; deduct for
confirmed bugs by severity: high ~25-40 pts, medium ~10-15, low ~2-5; a confirmed high-severity violation of a
hard target — "idle/stand always loses" — is disqualifying even if the entry's own test suite passes, since the
tests only sample 5 fixed stand positions and can miss a narrow exploit band).

ENTRIES:
- muse: branch p5/balance-muse, commit 9ad5d9b. Verified: 148/148 tests pass, ruff clean, diff = 12 lines
  (enemy_hp on L1/L2/L3 plus L1 gate2 x/w/vx). scripts/balance.py --seeds 3 warnings: none.
- flash: branch p5/balance-flash, commit b2286e1. Verified: 148/148 tests pass, ruff clean, diff = 8 lines
  (L1 wave counts +2 each, L3 enemy_hp). scripts/balance.py --seeds 3 warnings: none.

REVIEWS OF muse's ENTRY (by luna and flash):
--- luna ---
verdict: pass
issues:
- none (pytest: 148 passed, 0 failed; ruff: clean)
diff_lines: 12
balance_warnings: none
--- flash --- (session had to be resumed after a 900s timeout spent over-probing; the orchestrator independently
reconfirmed the finding below with its own short python snippet before resuming flash to get this formatted reply)
verdict: changes
issues:
- [high] swarm_control/sim/waves.py:56 L1's narrowed +4 gate at x=390..460 lets a stationary player defeat level 1
  (e.g. x≈405 seed 1 wins in 17.2s; win band ≈365-460 varies by seed) while the sampled STAND_X (90/180/270/360/450)
  in tests/test_balance.py and scripts/balance.py miss it; fix by making a fixed firing column unable to win
  (raise L1 enemy_hp, lower the +4 value, or reposition/keep the gate moving).
diff_lines: 12
balance_warnings: none

REVIEWS OF flash's ENTRY (by luna and muse):
--- luna ---
verdict: pass
issues:
- none (pytest: 148 passed, 0 failed; ruff: clean)
diff_lines: 8
balance_warnings: none
--- muse ---
verdict: pass
issues:
- none
diff_lines: 8
balance_warnings: (none)

Reply with exactly this format and nothing else:
consensus: <N> confirmed, <M> rejected
fix list (verified real defects, by entry):
- muse: [sev] <file:line> <fix>  (or "none")
- flash: [sev] <file:line> <fix>  (or "none")
rejected:
- <issue> — <why it doesn't hold up>  (or "none")
scores:
- muse: <0-100> — <one line why>
- flash: <0-100> — <one line why>
winner: muse | flash

SPEC:
## A. Balance (waves.py LEVELS gates/waves/hp/rewards; tests first)
Targets, measured with `scripts/balance.py --seeds 5` and NO upgrades bought:
- idle and every stand@x player LOSE every level on every seed (today stand@180 wins L1 in 43 s: fix it).
- sweep wins 100% on every level; median sweep win time rises with level: L1 45-75 s, L2 70-100 s, L3 95-130 s
  (today L3 is faster than L2). sweep-fast also wins every level.
- With upgrades (buy what level rewards allow, greedily cheapest first), each level is won faster than without.
The winner is the entry that meets all targets with the smallest change; balance.py output goes in the review.
