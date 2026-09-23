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
import logging
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from swarm_control import config
from swarm_control.protocol import ACTIONS
from swarm_control.sim.world import World

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

logger = logging.getLogger(__name__)

MAX_CATCHUP_STEPS = 5


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
            return

        disconnected = asyncio.Event()

        async def reader() -> None:
            while True:
                try:
                    message = await websocket.receive()
                except (WebSocketDisconnect, RuntimeError):
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
                    _handle_message(world, msg)
                except (ValueError, RecursionError):
                    continue
                except Exception:
                    logger.exception("error handling client message")
                    continue

        dt = 1.0 / config.TICK_HZ
        steps_per_send = config.TICK_HZ // config.SEND_HZ
        reader_task = asyncio.create_task(reader())
        close_code = 1000
        try:
            loop = asyncio.get_running_loop()
            next_tick = loop.time()
            steps = 0
            while not disconnected.is_set():
                next_tick += dt
                try:
                    world.step(dt)
                except Exception:
                    logger.exception("world.step failed")
                    close_code = 1011
                    break
                steps += 1
                if steps % steps_per_send == 0:
                    try:
                        snapshot = world.snapshot()
                    except Exception:
                        logger.exception("world.snapshot failed")
                        close_code = 1011
                        break
                    try:
                        await websocket.send_json(snapshot)
                    except (WebSocketDisconnect, RuntimeError):
                        break
                    except Exception:
                        logger.exception("state send failed")
                        close_code = 1011
                        break
                delay = next_tick - loop.time()
                if delay < -MAX_CATCHUP_STEPS * dt:
                    next_tick = loop.time()
                    delay = 0
                await asyncio.sleep(max(delay, 0))
        finally:
            reader_task.cancel()
            try:
                await reader_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("ws reader task failed")
            try:
                await websocket.close(code=close_code)
            except (WebSocketDisconnect, RuntimeError):
                pass

    return app


app = create_app()
