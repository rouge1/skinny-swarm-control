#!/usr/bin/env python3
"""Playwright check of the client's mock mode: screenshots over ~24 s, up to the win screen."""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

url, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
log = {"errors": [], "console": []}
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 900, "height": 1000})
    page.on("pageerror", lambda e: log["errors"].append(str(e)))
    page.on("console", lambda m: m.type in ("error", "warning") and log["console"].append(m.text))
    page.goto(url)
    page.keyboard.down("Space")
    prev = 0
    for t, name in ((3, "03s-firing"), (8, "08s-gates"), (14, "14s-battle"), (24, "24s-end")):
        page.wait_for_timeout((t - (0 if name.startswith("03") else prev)) * 1000)
        prev = t
        page.screenshot(path=str(out / f"{name}.png"))
    b.close()
print(json.dumps(log))
