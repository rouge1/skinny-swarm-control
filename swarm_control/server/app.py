"""FastAPI app: serves the web client and runs one World per WebSocket.

CONTRACT (acceptance tests: tests/test_server.py):

    create_app(world_factory=World) -> FastAPI
    app = create_app()                    module-level app for uvicorn

    GET  /            -> swarm_control/web/index.html
    GET  /static/...  -> files in swarm_control/web/
    WS   /ws          -> sends {"type": "hello", ...} first, then "state"
                         messages at SEND_HZ while stepping the world at TICK_HZ
                         with fixed dt = 1 / TICK_HZ. Applies "input" and "action"
                         messages (see protocol.py). Malformed messages are ignored,
                         never crash the connection.

Run locally:  python -m swarm_control.server   (http://127.0.0.1:8000)
This file is a stub.
"""
