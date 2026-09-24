You are a REVIEWER on Swarm Control. Do not edit, create or delete any file. Do not run git commands that change
state. Do not list or read anything outside the working directory. You may run the scripts and short python probes
with /data/python/learn/swarm-control/.venv/bin/python.

Two other models wrote measurement scripts for phase 5 (balance tuning and performance):
- scripts/balance.py: plays every level headlessly with scripted players (sweep, sweep-fast, idle, stand@x) and
  reports win rate, times, HP, peak counts, plus WARNINGS.
- scripts/bench.py: per-step timing at 500..4000 units with a per-phase breakdown, snapshot+json timing, --profile.
Both must use only the public World API / outside-in monkeypatching and must NOT change game behaviour.

Review for: measurements that are wrong or misleading (wrong timer placement, phases double-counted, statistics
computed wrong, scripted players that don't do what their name says, warnings that miss or false-alarm), the
monkeypatching leaking into or altering the simulation, crashes on edge cases (--seeds 0, --loads with odd numbers,
level ending early), and anything that makes the numbers unreliable for tuning decisions. Run both scripts.

Reply with exactly this format and nothing else:
verdict: pass | changes
issues:
- [high|medium|low] <file:line> <one line: what is wrong and the fix>
