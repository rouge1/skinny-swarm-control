Review feedback on your web client. Fix all of these; edit only files in swarm_control/web/.

1. [medium] style.css: `#stage { line-height: 0 }` is inherited by `#overlay`, so two-line overlays ("PAUSED\nPress P
   to resume", win/lose) draw both lines on top of each other. Give #overlay a normal line-height (e.g. 1.4).
2. [low] frame(): request the next animation frame before rendering (or try/catch render) so one bad state
   cannot stop the render loop forever.
3. [low] Keyboard: ignore key events with ctrlKey/metaKey/altKey (Ctrl+R currently sends "restart" before reload,
   Ctrl+A registers as left).
4. [low] ArrowLeft and A share one boolean: holding both and releasing one stops the launcher. Track held keys
   by e.code in a Set and derive left/right/fire from it.
5. [low] Mock mode rounds unit y every frame, so speed depends on refresh rate. Keep float positions in the mock
   simulation and round only when building the mock state message.
6. [low] Also re-read devicePixelRatio when it changes (matchMedia `(resolution: ${dpr}dppx)` change listener,
   re-registered each time), not only on window resize.
7. [low] Mock mode: `?mock=0` currently enables mock. Use `get("mock") === "1"`.
8. [low] Reconnect: reset the backoff on the first "state" message, not on open, and add a little jitter.

Done when `/data/python/learn/swarm-control/.venv/bin/ruff check .` passes. The orchestrator will playtest.
