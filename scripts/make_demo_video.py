"""Record a demo video of the EcoRoute AI web UI.

Drives the live dashboard with Playwright: runs two route queries
(heavy truck Delhi->Jaipur, then electric van Mumbai->Pune), lets the
results and the live-impact panel render, and saves the screen
recording to demo/demo_video.webm (converted to .mp4 when ffmpeg is
available).

Usage:
    python scripts/make_demo_video.py            # starts its own server
    python scripts/make_demo_video.py --base-url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Browser

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "http://127.0.0.1:8000"
VIDEO_DIR = ROOT / "demo" / "video"


def wait_for_server(url: str, timeout_s: float = 90.0) -> None:
    import urllib.request

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(1.0)
    raise SystemExit(f"server at {url} did not become healthy in {timeout_s}s")


TITLE_HTML = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>
  body { margin: 0; height: 100vh; display: flex; flex-direction: column;
         align-items: center; justify-content: center; gap: 16px;
         background: #070b12; color: #e9eef6;
         font-family: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif;
         background-image: radial-gradient(900px 480px at 80% -10%, rgba(16,185,129,.12), transparent 60%),
                           radial-gradient(700px 400px at 10% 0%, rgba(56,189,248,.08), transparent 55%); }
  .mark { width: 64px; height: 64px; border-radius: 18px; margin-bottom: 6px;
          background: linear-gradient(135deg, #2dd4a7, #0ea5e9);
          display: grid; place-items: center; box-shadow: 0 10px 40px rgba(16,185,129,.4); }
  .mark svg { width: 34px; height: 34px; }
  h1 { font-size: 58px; margin: 0; font-weight: 800; letter-spacing: -1.5px; }
  .tag { color: #2dd4a7; font: 500 15px "JetBrains Mono", monospace;
         border: 1px solid rgba(45,212,167,.35); background: rgba(45,212,167,.1);
         padding: 7px 16px; border-radius: 999px; }
  .sub { color: #8b96a8; font-size: 18px; margin-top: 14px; }
</style></head><body>
  <div class="mark"><svg viewBox="0 0 24 24" fill="none" stroke="#04110c" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19c4-1 5-4 5-7 0-3 2-6 5-6 3 0 5 2 5 5 0 4-4 6-8 6"/><path d="M4 19c0-6 3-10 10-11"/></svg></div>
  <h1>EcoRoute AI</h1>
  <div class="tag">CPU-native &middot; local RAG &middot; privacy-first</div>
  <div class="sub">Sustainable fleet routing &mdash; ZIROH Build Next 2026</div>
</body></html>"""


def record_title_card(browser: Browser) -> Path:
    """Record a short branded title card matching the UI theme."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        record_video_dir=str(VIDEO_DIR),
        record_video_size={"width": 1280, "height": 800},
    )
    page = context.new_page()
    page.set_content(TITLE_HTML)
    page.wait_for_function("() => document.fonts.ready.then(() => true)", timeout=15_000)
    page.wait_for_timeout(3000)
    video = page.video
    if video is None:
        raise SystemExit("title card video was not recorded")
    title_webm = Path(video.path())
    context.close()
    return title_webm


def record(base_url: str) -> tuple[Path, Path]:
    """Record the title card and the UI walkthrough; return (title, demo)."""
    from playwright.sync_api import sync_playwright

    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    for stale in VIDEO_DIR.glob("*.webm"):
        stale.unlink()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        title_webm = record_title_card(browser)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=str(VIDEO_DIR),
            record_video_size={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # Scene 1: landing state — KPI strip + form + live panels.
        page.goto(f"{base_url}/", wait_until="load")
        page.wait_for_function("() => document.fonts.ready.then(() => true)", timeout=15_000)
        page.wait_for_selector("#impact .stat", timeout=20_000)
        page.wait_for_selector("#cost .save-pill", timeout=20_000)
        page.wait_for_timeout(3000)

        # Scene 2: heavy truck Delhi -> Jaipur (pre-filled defaults).
        page.click("#go")
        page.wait_for_selector("#result .route.rec", timeout=30_000)
        page.wait_for_timeout(4500)

        # Scene 3: switch to an electric van, Mumbai -> Pune, light payload.
        page.fill("#origin", "Mumbai")
        page.fill("#destination", "Pune")
        page.select_option("#vehicle", "electric_van")
        page.fill("#payload", "500")
        page.wait_for_timeout(1200)
        page.click("#go")
        # Wait for the new recommendation (route name now mentions Mumbai).
        page.wait_for_function(
            "() => document.querySelector('#result .route.rec .name')?.textContent?.includes('Mumbai')",
            timeout=30_000,
        )
        page.wait_for_timeout(4500)

        # Scene 4: the cost-at-scale money shot (local CPU vs cloud LLM).
        page.locator("#cost").scroll_into_view_if_needed()
        page.wait_for_timeout(4000)

        # Scene 5: back to the top — KPIs + live impact with the new totals.
        page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(VIDEO_DIR / "final_frame.png"))
        video = page.video
        if video is None:
            raise SystemExit("no video was recorded")
        demo_webm = Path(video.path())
        context.close()
        browser.close()

    return title_webm, demo_webm


def to_mp4(webm: Path, out: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(webm),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
            str(out),
        ],
        check=True,
        capture_output=True,
    )


def concat_mp4(parts: list[Path], out: Path) -> None:
    list_file = out.with_suffix(".concat.txt")
    list_file.write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", str(out)],
        check=True,
        capture_output=True,
    )
    list_file.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()

    server = None
    if args.base_url == BASE_URL:
        import os

        env = dict(os.environ)
        env.update({"API_KEYS": "dev-key-123", "RATE_LIMIT_PER_MINUTE": "100000"})
        server = subprocess.Popen(
            [str(ROOT / ".venv" / "bin" / "python"), "-m", "uvicorn", "main:app",
             "--host", "127.0.0.1", "--port", "8000"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wait_for_server(args.base_url)

    try:
        title_webm, demo_webm = record(args.base_url)
        if shutil.which("ffmpeg") is None:
            print(f"ffmpeg not found; raw recordings: {title_webm}, {demo_webm}")
            return
        title_mp4 = VIDEO_DIR / "_title.mp4"
        demo_mp4 = VIDEO_DIR / "_demo.mp4"
        to_mp4(title_webm, title_mp4)
        to_mp4(demo_webm, demo_mp4)
        final = VIDEO_DIR / "ecoroute_demo.mp4"
        concat_mp4([title_mp4, demo_mp4], final)
        title_mp4.unlink(missing_ok=True)
        demo_mp4.unlink(missing_ok=True)
        print(f"video (mp4): {final}")
    finally:
        if server is not None:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
