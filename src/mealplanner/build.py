"""Build the static site into ``dist/``.

Run with ``python -m mealplanner.build``.

The page is a single self-contained HTML file: the catalogue is inlined at the
``__DATA__`` placeholder and the shared shopping-list code at ``__SHOPPING_JS__``,
so the result works offline and from a ``file://`` URL on a phone.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .catalogue import all_tags, load_foods, load_recipes

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).parent / "templates" / "app.html"
SHOPPING_JS = Path(__file__).parent / "templates" / "shopping.js"
DATA_PLACEHOLDER = "__DATA__"
JS_PLACEHOLDER = "/* __SHOPPING_JS__ */"

# Daily targets each planned day is scored against.
TARGETS = {"kcal": 1750, "protein": 180}

# Tag filters are ordered by usefulness rather than alphabetically.
TAG_ORDER = ["high-protein", "quick", "vegetarian", "no-cook", "packable", "batch", "one-pan"]


def payload() -> dict:
    foods = load_foods()
    recipes = load_recipes(foods)
    seen = set(all_tags(recipes))
    tags = [t for t in TAG_ORDER if t in seen] + sorted(seen - set(TAG_ORDER))
    return {
        "foods": {
            key: {k: v for k, v in asdict(food).items() if k != "key"}
            for key, food in foods.items()
        },
        "recipes": [r.to_dict() for r in recipes],
        "tags": tags,
        "targets": TARGETS,
    }


def build(out: Path | None = None) -> Path:
    out = out or ROOT / "dist"
    out.mkdir(parents=True, exist_ok=True)

    data = payload()
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    template = TEMPLATE.read_text(encoding="utf-8")
    for placeholder in (DATA_PLACEHOLDER, JS_PLACEHOLDER):
        if placeholder not in template:
            raise RuntimeError(f"{placeholder} placeholder missing from {TEMPLATE}")

    html = template.replace(DATA_PLACEHOLDER, blob)
    html = html.replace(JS_PLACEHOLDER, SHOPPING_JS.read_text(encoding="utf-8"))

    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "catalogue.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    slots: dict[str, int] = {}
    for recipe in data["recipes"]:
        slots[recipe["slot"]] = slots.get(recipe["slot"], 0) + 1
    breakdown = ", ".join(f"{n} {slot}" for slot, n in sorted(slots.items()))
    print(
        f"built {out / 'index.html'} "
        f"({len(data['recipes'])} recipes: {breakdown}; "
        f"{len(data['foods'])} foods; {len(html) // 1024} KB)"
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the meal planner site.")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    build(args.out)


if __name__ == "__main__":
    main()
