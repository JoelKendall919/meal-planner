"""Validate a recipe JSON file against the food database.

Usage:  python scripts/validate_recipes.py data/recipes/soups.json

Checks every food key resolves, computes macros from raw ingredient weights, and
reports anything implausible. Exits non-zero if there are errors.

The kcal ranges below are plausibility checks, not diet targets. They catch a
decimal-point slip or ounces entered as grams. A rich meal is a valid recipe:
whether it suits a given day is the planner's job, not the catalogue's.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mealplanner.catalogue import (  # noqa: E402
    CATEGORIES,
    PLAUSIBLE_KCAL,
    SLOTS,
)

FOODS = json.loads((ROOT / "data" / "foods.json").read_text(encoding="utf-8"))

REQUIRED = {
    "id",
    "name",
    "slots",
    "category",
    "source",
    "servings",
    "ingredients",
    "steps",
    "tags",
}

# Never authored. Macros are derived from ingredients, always.
FORBIDDEN = {"kcal", "protein", "fat", "carbs", "macros", "slot"}


def macros(ingredients: list[dict]) -> tuple[float, float, float]:
    kcal = protein = fat = 0.0
    for item in ingredients:
        food = FOODS[item["food"]]
        grams = item["grams"]
        kcal += food["kcal"] * grams / 100
        protein += food["protein"] * grams / 100
        fat += food["fat"] * grams / 100
    return kcal, protein, fat


def validate(path: Path) -> int:
    recipes = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(recipes, list):
        print("ERROR: top level must be a JSON list of recipe objects")
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    ids = Counter(r.get("id", "?") for r in recipes)
    for dup, n in ids.items():
        if n > 1:
            errors.append(f"duplicate id {dup!r} ({n} times)")

    rows = []
    for r in recipes:
        rid = r.get("id", "<no id>")

        missing = REQUIRED - set(r)
        if missing:
            errors.append(f"{rid}: missing fields {sorted(missing)}")
            continue

        stored = FORBIDDEN & set(r)
        if stored:
            errors.append(
                f"{rid}: must not store {sorted(stored)} -- macros are derived from ingredients"
            )
            continue

        slots = r["slots"]
        if not isinstance(slots, list) or not slots:
            errors.append(f"{rid}: 'slots' must be a non-empty list, e.g. ['lunch', 'dinner']")
            continue
        bad_slots = [s for s in slots if s not in SLOTS]
        if bad_slots:
            errors.append(f"{rid}: unknown slots {bad_slots}; pick from {sorted(SLOTS)}")
            continue

        if r["category"] not in CATEGORIES:
            errors.append(f"{rid}: category {r['category']!r} is not in the controlled vocabulary")
            continue

        if not isinstance(r["ingredients"], list) or not r["ingredients"]:
            errors.append(f"{rid}: needs at least one ingredient")
            continue

        bad_keys = [i["food"] for i in r["ingredients"] if i["food"] not in FOODS]
        if bad_keys:
            errors.append(f"{rid}: unknown food keys {bad_keys}")
            continue

        for i in r["ingredients"]:
            if not isinstance(i.get("grams"), (int, float)) or i["grams"] <= 0:
                errors.append(f"{rid}: {i['food']} needs a positive gram weight")
            if not i.get("display"):
                errors.append(f"{rid}: {i['food']} needs a human-readable 'display'")

        if len(r["steps"]) < 2:
            errors.append(f"{rid}: needs at least 2 method steps")
        if any(len(s) > 300 for s in r["steps"]):
            warnings.append(f"{rid}: has a very long step; keep them concise")

        src = r.get("source") or {}
        if not src.get("name"):
            errors.append(f"{rid}: source.name is required for provenance")

        kcal, protein, fat = macros(r["ingredients"])
        # Judged against the most generous of its slots: a dish that works as
        # both lunch and dinner only has to be plausible as one of them.
        lo = min(PLAUSIBLE_KCAL[s][0] for s in slots)
        hi = max(PLAUSIBLE_KCAL[s][1] for s in slots)
        if not lo <= kcal <= hi:
            errors.append(
                f"{rid}: {kcal:.0f} kcal is implausible for {'/'.join(slots)} "
                f"({lo}-{hi}); check for a decimal slip"
            )
        if 4 * protein + 9 * fat > kcal + 30:
            errors.append(
                f"{rid}: protein and fat alone come to {4 * protein + 9 * fat:.0f} kcal "
                f"but the recipe totals {kcal:.0f}; a gram weight is wrong"
            )

        rows.append((rid, "/".join(slots), kcal, protein, fat, "vegetarian" in r.get("tags", [])))

    print(f"{path.name}: {len(recipes)} recipes")
    if rows:
        rows.sort(key=lambda x: x[2])
        print(f"  kcal range {rows[0][2]:.0f}-{rows[-1][2]:.0f}")
        veg = sum(1 for r in rows if r[5])
        print(f"  vegetarian: {veg}")
        print(f"  mean protein: {sum(r[3] for r in rows) / len(rows):.0f} g")

    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")

    print(f"  -> {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rc = 0
    for arg in sys.argv[1:]:
        rc |= validate(Path(arg))
    sys.exit(rc)


if __name__ == "__main__":
    main()
