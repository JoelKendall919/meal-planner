#!/usr/bin/env bash
# Render the built app with a driver script appended, and print what it reported.
#
# The planner's behaviour lives in the browser, so the checks that matter most
# have to run there: this loads dist/index.html under headless Chrome with a
# driver appended, lets the driver exercise the real views and read the DOM
# back, and prints its results.
#
#   ./scripts/run_driver.sh scripts/drive_tweaks.js
#
# Set CHROME to point at a different browser binary.
set -euo pipefail

cd "$(dirname "$0")/.."
driver="${1:?usage: run_driver.sh <driver.js>}"

chrome="${CHROME:-}"
if [ -z "$chrome" ]; then
  for candidate in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "$(command -v google-chrome || true)" \
    "$(command -v chromium || true)"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then chrome="$candidate"; break; fi
  done
fi
if [ -z "$chrome" ]; then
  echo "no Chrome found; set CHROME to the browser binary" >&2
  exit 1
fi

if [ ! -f dist/index.html ]; then
  echo "dist/index.html is missing; run 'make build' first" >&2
  exit 1
fi

python - "$driver" <<'PY'
import sys
from pathlib import Path

built = Path("dist/index.html").read_text(encoding="utf-8")
driver = Path(sys.argv[1]).read_text(encoding="utf-8")
Path("dist/drv.html").write_text(
    built.replace("</body>", f"<script>\n{driver}\n</script>\n</body>"), encoding="utf-8"
)
PY

# A tall window so every day of the week is laid out rather than clipped.
"$chrome" --headless --disable-gpu --no-sandbox \
  --window-size=1000,5000 --virtual-time-budget=9000 --dump-dom \
  "file://$PWD/dist/drv.html" 2>/dev/null \
  | python -c "
import html, re, sys
page = sys.stdin.read()
found = re.search(r'<pre id=\"drv\">(.*?)</pre>', page, re.S)
if not found:
    print('NO DRIVER OUTPUT -- the driver threw before it could report')
    sys.exit(1)
report = html.unescape(found.group(1))
print(report)
sys.exit(1 if 'FAIL' in report else 0)
"
