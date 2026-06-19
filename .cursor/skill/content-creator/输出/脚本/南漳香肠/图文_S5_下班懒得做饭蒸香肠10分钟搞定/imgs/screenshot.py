#!/usr/bin/env python3
"""Playwright截图：1080x1920 @2x = 2160x3840"""
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

HTML_DIR = Path("/Volumes/增元/项目/douyin/.cursor/skill/content-creator/输出/脚本/南漳香肠/图文_S5_下班懒得做饭蒸香肠10分钟搞定/imgs")
OUT_DIR = HTML_DIR / "screenshots"
OUT_DIR.mkdir(exist_ok=True)

PAGES = [
    ("slide01_cover.html", "01_封面_下班懒得做饭蒸香肠10分钟搞定.png"),
    ("slide02_pain.html", "02_痛点_下班后最大的难题来了.png"),
    ("slide03_method.html", "03_做法_香肠蒸着吃10分钟出锅.png"),
    ("slide04_combo.html", "04_搭配_香肠配一配一顿像样的晚餐就有了.png"),
    ("slide05_ending.html", "05_结尾_香肠不是大菜才吃.png"),
]

WIDTH = 1080
HEIGHT = 1920
SCALE = 2

def capture_page(html_file, output_file):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": WIDTH + 100, "height": HEIGHT + 100},
            device_scale_factor=SCALE,
        )
        page = context.new_page()
        url = f"file://{html_file.resolve()}"
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.set_viewport_size({"width": WIDTH, "height": HEIGHT})
        page.wait_for_timeout(300)
        page.screenshot(path=str(output_file), type="png", full_page=False, timeout=30000)
        browser.close()
        print(f"  OK: {output_file.name} ({WIDTH*SCALE}x{HEIGHT*SCALE})")

def main():
    print("=" * 60)
    print("Playwright Screenshot: 1080x1920 @2x")
    print(f"Output: {OUT_DIR}")
    print("=" * 60)
    for html_name, out_name in PAGES:
        html_path = HTML_DIR / html_name
        out_path = OUT_DIR / out_name
        if not html_path.exists():
            print(f"  SKIP: {html_path} not found")
            continue
        try:
            capture_page(html_path, out_path)
        except Exception as e:
            print(f"  ERROR {html_name}: {e}")
    print("=" * 60)
    print("Done!")

if __name__ == "__main__":
    main()
