"""Render assets/icon.svg to the PNG sizes the web app manifest needs.

Run locally after changing the icon; the PNGs are committed so CI and the
deploy job never need a browser:

    .venv/bin/python scripts/mkicons.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "assets" / "icon.svg"

# name -> pixel size
TARGETS = {
    "icon-192.png": 192,
    "icon-512.png": 512,
    "apple-touch-icon.png": 180,
}

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def find_chrome() -> str:
    for path in CHROME_PATHS:
        if Path(path).exists():
            return path
    found = shutil.which("google-chrome") or shutil.which("chromium")
    if found:
        return found
    sys.exit("Could not find Chrome. Install it, or add its path to CHROME_PATHS.")


def render(chrome: str, size: int, out: Path) -> None:
    """Screenshot the SVG at an exact pixel size.

    The SVG is wrapped in a page with no margin and a body sized to the icon, so
    the screenshot is the artwork edge to edge with no padding.
    """
    svg = SVG.read_text(encoding="utf-8")
    html = (
        "<!doctype html><meta charset='utf-8'>"
        "<style>html,body{margin:0;padding:0;background:transparent}"
        f"svg{{display:block;width:{size}px;height:{size}px}}</style>{svg}"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
        fh.write(html)
        page = Path(fh.name)
    try:
        subprocess.run(
            [
                chrome,
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                "--default-background-color=00000000",
                f"--screenshot={out}",
                f"--window-size={size},{size}",
                f"file://{page}",
            ],
            check=True,
            capture_output=True,
        )
    finally:
        page.unlink(missing_ok=True)


def main() -> None:
    chrome = find_chrome()
    for name, size in TARGETS.items():
        out = SVG.parent / name
        render(chrome, size, out)
        print(f"wrote {out.relative_to(ROOT)} ({size}x{size}, {out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
