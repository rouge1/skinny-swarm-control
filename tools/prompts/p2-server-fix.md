Review feedback on your server (swarm_control/server/app.py). Fix all of these; edit only that file.

1. [high] When world.step plus the send takes longer than 1/TICK_HZ, the `delay <= 0` branch never awaits,
   so the game loop monopolises the event loop: with a 20 ms step the whole server wedged (new handshakes
   timed out, SIGTERM ignored, the reader never ran); with 4 clients at 6 ms/step each, clients froze for
   ~500 ms at a time. Always `await asyncio.sleep(max(delay, 0))` once per tick, and cap catch-up at a few
   steps (e.g. 5) before resetting the schedule to now.
2. [medium] A deeply nested JSON frame (e.g. "[" * 200000) makes json.loads raise RecursionError, which kills
   the reader task silently; later inputs/actions are ignored for the rest of the session. Catch decode and
   handling errors per message (including RecursionError) and keep reading; don't swallow unexpected reader
   exceptions silently in `finally` — log them.
3. [low] If sending hello fails the socket is already disconnected; the unguarded close then raises and logs
   "Exception in ASGI application". Just return, or guard the close like the finally block does.
4. [low] On an unexpected exception from world.step/snapshot, close with code 1011, not 1000.
5. [low] Tidy the reader: merge the duplicate except branches, drop the redundant UnicodeDecodeError (it is a
   ValueError) and the inner CancelledError swallow, and replace the per-tick wait_for(disconnected.wait())
   (a task and timer 60x/s) with asyncio.sleep(delay) plus an event/flag check.

Done when these pass:
    /data/python/learn/swarm-control/.venv/bin/python -m pytest tests/test_server.py tests/test_protocol.py
    /data/python/learn/swarm-control/.venv/bin/ruff check .
