"""Render the plan documents to print-quality PDFs using headless Chrome.

There is no pandoc dependency; Chrome is used because it honours the print CSS
below, including the page-break rules that keep tables and recipes intact.

Usage:  python scripts/mkpdf.py [--out DIR]
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import markdown

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
]


def find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if os.path.isfile(candidate) or shutil.which(candidate):
            return candidate
    sys.exit(
        "Could not find Google Chrome or Chromium, which is required to render PDFs.\n"
        "Install Chrome, or set one of: " + ", ".join(CHROME_CANDIDATES)
    )
CSS = """
@page { size: A4; margin: 16mm 14mm 14mm 14mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
  font-size: 9.6pt; line-height: 1.45; color: #1a1a1a; margin: 0; }
h1 { font-size: 21pt; margin: 0 0 4pt; letter-spacing: -0.4pt; }
h2 { font-size: 13pt; margin: 16pt 0 6pt; padding-bottom: 3pt;
  border-bottom: 1.5pt solid #111; page-break-after: avoid; letter-spacing: -0.2pt; }
h3 { font-size: 10.8pt; margin: 12pt 0 4pt; color: #000; page-break-after: avoid; }
h1 + p, h2 + p { margin-top: 0; }
p { margin: 5pt 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 9pt;
  page-break-inside: avoid; font-size: 8.9pt; }
th { background: #f0f0ef; text-align: left; font-weight: 600;
  border-bottom: 1pt solid #bbb; }
th, td { padding: 3.2pt 5pt; vertical-align: top; }
tbody tr { border-bottom: 0.5pt solid #e2e2e0; }
tbody tr:nth-child(even) { background: #fafaf9; }
blockquote { margin: 5pt 0; padding: 5pt 9pt; background: #f6f6f4;
  border-left: 2.5pt solid #999; page-break-inside: avoid; }
blockquote p { margin: 2pt 0; }
ul, ol { margin: 5pt 0; padding-left: 15pt; }
li { margin: 2pt 0; }
hr { border: none; border-top: 0.5pt solid #d8d8d6; margin: 12pt 0; }
code { background: #f0f0ef; padding: 1pt 3pt; border-radius: 2pt; font-size: 8.4pt; }
strong { font-weight: 600; }
em { color: #444; }
h2, h3, table, blockquote { break-inside: avoid; }
"""


def build(name: str, title: str, out_dir: pathlib.Path, chrome: str) -> None:
    src = (CONTENT / f"{name}.md").read_text(encoding="utf-8")
    html = markdown.markdown(src, extensions=["tables", "sane_lists"])
    doc = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head><body>{html}</body></html>"
    tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
    tmp.write(doc)
    tmp.close()
    out = out_dir / f"{name}.pdf"
    subprocess.run(
        [
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={out}",
            "--virtual-time-budget=4000",
            f"file://{tmp.name}",
        ],
        check=True,
        capture_output=True,
    )
    os.unlink(tmp.name)
    print(f"{out.name}  {out.stat().st_size // 1024} KB")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "dist")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    chrome = find_chrome()
    for name, title in [("meal-plan", "Meal Plan"), ("training-plan", "Training Plan")]:
        build(name, title, args.out, chrome)


if __name__ == "__main__":
    main()
