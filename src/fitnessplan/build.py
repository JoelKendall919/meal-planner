"""Build the static site into ``dist/``.

Run with ``python -m fitnessplan.build``.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .parse import parse, to_json

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).parent / "templates" / "app.html"
DATA_PLACEHOLDER = "__DATA__"


def build(content: Path | None = None, out: Path | None = None) -> Path:
    content = content or ROOT / "content" / "meal-plan.md"
    out = out or ROOT / "dist"
    out.mkdir(parents=True, exist_ok=True)

    data = parse(content)
    payload = to_json(data)

    template = TEMPLATE.read_text(encoding="utf-8")
    if DATA_PLACEHOLDER not in template:
        raise RuntimeError(f"{DATA_PLACEHOLDER} placeholder missing from {TEMPLATE}")

    (out / "index.html").write_text(template.replace(DATA_PLACEHOLDER, payload), encoding="utf-8")
    (out / "plan.json").write_text(payload, encoding="utf-8")

    for doc in ("meal-plan.md", "training-plan.md"):
        src = ROOT / "content" / doc
        if src.exists():
            shutil.copy(src, out / doc)

    print(
        f"built {out / 'index.html'} "
        f"({len(data['days'])} days, {len(data['recipes'])} recipes, "
        f"{len(data['snacks'])} snacks, "
        f"{sum(len(sl['items']) for sl in data['lists'])} shopping items)"
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the fitness plan site.")
    ap.add_argument("--content", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    build(args.content, args.out)


if __name__ == "__main__":
    main()
