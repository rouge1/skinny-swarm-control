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
"""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from swarm_control import config
from swarm_control.protocol import ACTIONS
from swarm_control.sim.world import World

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _handle_message(world: World, msg: object) -> None:
    """Apply one decoded client message to the world; ignore malformed ones."""
    if not isinstance(msg, dict):
        return
    mtype = msg.get("type")
    if mtype == "input":
        left, right, fire = msg.get("left"), msg.get("right"), msg.get("fire")
        if type(left) is bool and type(right) is bool and type(fire) is bool:
            world.set_input(left, right, fire)
    elif mtype == "action":
        name = msg.get("action")
        if name in ACTIONS:
            world.action(name)


def create_app(world_factory: Callable[[], World] = World) -> FastAPI:
    """Create the FastAPI app; each /ws connection gets `world_factory()`."""
    app = FastAPI()

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        world = world_factory()
        try:
            await websocket.send_json(
                {
                    "type": "hello",
                    "field": {"w": config.FIELD_W, "h": config.FIELD_H},
                    "tick_hz": config.TICK_HZ,
                }
            )
        except (WebSocketDisconnect, RuntimeError):
            await websocket.close()
            return

        disconnected = asyncio.Event()

        async def reader() -> None:
            try:
                while True:
                    try:
                        message = await websocket.receive()
                    except WebSocketDisconnect:
                        disconnected.set()
                        break
                    except RuntimeError:
                        disconnected.set()
                        break
                    if message.get("type") == "websocket.disconnect":
                        disconnected.set()
                        break
                    text = message.get("text")
                    if text is None:
                        continue
                    try:
                        msg = json.loads(text)
                    except (ValueError, UnicodeDecodeError):
                        continue
                    _handle_message(world, msg)
            except asyncio.CancelledError:
                pass

        dt = 1.0 / config.TICK_HZ
        steps_per_send = config.TICK_HZ // config.SEND_HZ
        reader_task = asyncio.create_task(reader())
        try:
            loop = asyncio.get_running_loop()
            next_tick = loop.time()
            steps = 0
            while not disconnected.is_set():
                next_tick += dt
                world.step(dt)
                steps += 1
                if steps % steps_per_send == 0:
                    try:
                        await websocket.send_json(world.snapshot())
                    except (WebSocketDisconnect, RuntimeError):
                        break
                delay = next_tick - loop.time()
                if delay > 0:
                    try:
                        await asyncio.wait_for(disconnected.wait(), timeout=delay)
                    except TimeoutError:
                        pass
                    else:
                        break
                elif delay < -0.25:
                    next_tick = loop.time()
        finally:
            reader_task.cancel()
            try:
                await reader_task
            except (asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                pass
            try:
                await websocket.close()
            except (WebSocketDisconnect, RuntimeError):
                pass

    return app


app = create_app()
