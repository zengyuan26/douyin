#!/usr/bin/env python3
"""Playwright截图 v2"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML_DIR = Path("/Volumes/增元/项目/douyin/.cursor/skill/content-creator/输出/脚本/南漳香肠/图文_S5_下班懒得做饭蒸香肠10分钟搞定/imgs")
OUT_DIR = HTML_DIR / "screenshots_v2"
OUT_DIR.mkdir(exist_ok=True)

PAGES = [
    ("slide01_cover.html", "01_封面.png"),
    ("slide02_pain.html", "02_痛点.png"),
    ("slide03_method.html", "03_做法.png"),
    ("slide04_combo.html", "04_搭配.png"),
    ("slide05_ending.html", "05_结尾.png"),
]

W, H = 1080, 1920
SCALE = 2

def capture(html_file, out_file):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": W+200, "height": H+200}, device_scale_factor=SCALE)
        page = ctx.new_page()
        page.goto(f"file://{html_file.resolve()}", wait_until="networkidle")
        page.wait_for_timeout(1800)
        page.set_viewport_size({"width": W, "height": H})
        page.wait_for_timeout(300)
        page.screenshot(path=str(out_file), type="png", full_page=False, timeout=30000)
        browser.close()
        print(f"  OK: {out_file.name} ({W*SCALE}x{H*SCALE})")

for html_name, out_name in PAGES:
    hp = HTML_DIR / html_name
    op = OUT_DIR / out_name
    try:
        capture(hp, op)
    except Exception as e:
        print(f"  ERROR {html_name}: {e}")
