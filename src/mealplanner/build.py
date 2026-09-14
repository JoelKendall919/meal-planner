"""Build the static site into ``dist/``.

Run with ``python -m mealplanner.build``.

The page is a single self-contained HTML file: the catalogue is inlined at the
``__DATA__`` placeholder and the shared shopping-list code at ``__SHOPPING_JS__``,
so the result works offline and from a ``file://`` URL on a phone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from .catalogue import all_tags, load_foods, load_recipes

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = Path(__file__).parent / "templates"
ASSETS = ROOT / "assets"
TEMPLATE = TEMPLATES / "app.html"
SHOPPING_JS = TEMPLATES / "shopping.js"
SW = TEMPLATES / "sw.js"
MANIFEST = TEMPLATES / "manifest.webmanifest"
ICONS = ("icon-192.png", "icon-512.png", "apple-touch-icon.png")
DATA_PLACEHOLDER = "__DATA__"
JS_PLACEHOLDER = "/* __SHOPPING_JS__ */"
VERSION_PLACEHOLDER = "__VERSION__"

# Default daily goals. The user can change these in the app; these are only the
# starting values. They must be reachable from the catalogue: the original plan's
# 180 g protein came from a hand-built week and no combination of these 75 recipes
# can reach it under 1750 kcal (the best is 168 g, in 1 of 14,159 combinations).
# These figures are the median of days landing at 1650-1750 kcal with >=130 g
# protein, so a well-chosen day meets them. See test_targets_are_achievable.
TARGETS = {"kcal": 1750, "protein": 130, "fat": 55, "carbs": 170}

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

    # The service worker's cache name is tied to the content it serves, so a
    # deploy that changes nothing leaves the user's cache alone, and one that
    # changes anything retires it completely. sw.js and the manifest are part of
    # the hash: changing only the worker must still invalidate the old cache.
    sw = SW.read_text(encoding="utf-8")
    if VERSION_PLACEHOLDER not in sw:
        raise RuntimeError(f"{VERSION_PLACEHOLDER} placeholder missing from {SW}")
    manifest = MANIFEST.read_text(encoding="utf-8")
    digest = hashlib.sha256()
    for part in (html, sw, manifest):
        digest.update(part.encode("utf-8"))
    version = digest.hexdigest()[:12]
    (out / "sw.js").write_text(sw.replace(VERSION_PLACEHOLDER, version), encoding="utf-8")

    (out / MANIFEST.name).write_text(manifest, encoding="utf-8")
    missing = [name for name in ICONS if not (ASSETS / name).exists()]
    if missing:
        raise RuntimeError(f"missing icons {missing}; run scripts/mkicons.py")
    for name in ICONS:
        shutil.copy(ASSETS / name, out / name)

    slots: dict[str, int] = {}
    for recipe in data["recipes"]:
        slots[recipe["slot"]] = slots.get(recipe["slot"], 0) + 1
    breakdown = ", ".join(f"{n} {slot}" for slot, n in sorted(slots.items()))
    print(
        f"built {out / 'index.html'} "
        f"({len(data['recipes'])} recipes: {breakdown}; "
        f"{len(data['foods'])} foods; {len(html) // 1024} KB; version {version})"
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the meal planner site.")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    build(args.out)


if __name__ == "__main__":
    main()
