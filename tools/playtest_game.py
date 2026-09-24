#!/usr/bin/env python3
"""Plays a real level in the browser: sweep left/right while firing until the game ends; screenshots + video."""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

url, out, limit = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 120
out.mkdir(parents=True, exist_ok=True)
log = {"errors": [], "console": [], "shots": [], "result": None}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 900, "height": 1000}, record_video_dir=str(out),
                        record_video_size={"width": 900, "height": 1000})
    page = ctx.new_page()
    page.on("pageerror", lambda e: log["errors"].append(str(e)))
    page.on("console", lambda m: m.type in ("error", "warning") and log["console"].append(m.text))
    status = {"s": None}
    page.on("websocket", lambda ws: ws.on("framereceived", lambda f: status.update(
        s=(json.loads(f).get("status") if isinstance(f, str) and '"status"' in f[:200] else status["s"]))))
    page.goto(url)
    page.wait_for_timeout(1000)
    page.keyboard.down("Space")
    shots_at = {3, 10, 20, 35, 50, 65, 80, 95, 110}
    for sec in range(limit):
        key = "ArrowLeft" if (sec // 2) % 2 == 0 else "ArrowRight"
        page.keyboard.down(key)
        page.wait_for_timeout(1000)
        page.keyboard.up(key)
        if sec in shots_at:
            path = out / f"{sec:03d}s.png"
            page.screenshot(path=str(path))
            log["shots"].append(str(path))
        if status["s"] in ("won", "lost"):
            page.wait_for_timeout(800)
            path = out / f"{sec:03d}s-{status['s']}.png"
            page.screenshot(path=str(path))
            log["shots"].append(str(path))
            log["result"] = f"{status['s']} after ~{sec + 1}s"
            break
    page.keyboard.up("Space")
    ctx.close()
    b.close()
print(json.dumps(log, indent=1))
