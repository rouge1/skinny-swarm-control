Stop investigating. You already have the world.py diffs for all three entries and the config-vs-waves reward
comparison. Do not run any more tools. Emit ONLY the required final output now, exactly in this format:

consensus: <N> confirmed, <M> rejected
fix list (verified real defects, by entry):
- luna: [sev] <file:line> <fix>  (or "none")
- flash: [sev] <file:line> <fix>  (or "none")
- muse: [sev] <file:line> <fix>  (or "none")
rejected:
- <issue> — <why it doesn't hold up>  (or "none")
scores:
- luna: <0-100> — <one line why>
- flash: <0-100> — <one line why>
- muse: <0-100> — <one line why>
winner: luna | flash | muse

If a single claim is genuinely unresolved, mark it rejected/unverified rather than investigating further.
