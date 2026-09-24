#!/usr/bin/env python3
"""Headless playtest of Swarm Control with Playwright: plays a short scripted run and saves screenshots.

Usage: .venv/bin/python playtest.py [--url http://127.0.0.1:8000] [--out shots/p2] [--video]
"""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000/")
    ap.add_argument("--out", default="shots/latest")
    ap.add_argument("--video", action="store_true", help="also record a .webm of the run")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    log = {"console": [], "errors": [], "shots": []}

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(channel="chrome")
        ctx_args = {"viewport": {"width": 900, "height": 1000}, "device_scale_factor": 1}
        if a.video:
            ctx_args["record_video_dir"] = str(out)
            ctx_args["record_video_size"] = {"width": 900, "height": 1000}
        ctx = browser.new_context(**ctx_args)
        page = ctx.new_page()
        page.on("console", lambda m: log["console"].append(f"{m.type}: {m.text}"))
        page.on("pageerror", lambda e: log["errors"].append(str(e)))

        def shot(name):
            path = out / f"{len(log['shots']):02d}-{name}.png"
            page.screenshot(path=str(path))
            log["shots"].append(str(path))

        page.goto(a.url)
        page.wait_for_timeout(1200)
        shot("loaded")

        page.keyboard.down("Space")
        page.wait_for_timeout(1200)
        shot("firing-centre")

        page.keyboard.down("ArrowRight")
        page.wait_for_timeout(500)
        page.keyboard.up("ArrowRight")
        page.keyboard.down("ArrowLeft")
        page.wait_for_timeout(900)
        page.keyboard.up("ArrowLeft")
        page.wait_for_timeout(600)
        shot("firing-sweep")
        page.keyboard.up("Space")

        page.keyboard.press("p")
        page.wait_for_timeout(400)
        shot("paused")
        page.keyboard.press("p")
        page.wait_for_timeout(300)

        page.keyboard.press("r")
        page.wait_for_timeout(500)
        shot("restarted")

        page.goto(a.url.rstrip("/") + "/?mock=1")
        page.wait_for_timeout(1500)
        shot("mock-mode")

        ctx.close()
        browser.close()

    (out / "playtest.json").write_text(json.dumps(log, indent=1))
    print(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
