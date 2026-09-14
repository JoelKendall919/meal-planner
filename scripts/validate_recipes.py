"""Validate a recipe JSON file against the food database.

Usage:  python scripts/validate_recipes.py data/recipes-breakfast.json

Checks every food key resolves, computes macros from raw ingredient weights, and
reports anything outside the plan's targets. Exits non-zero if there are errors.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOODS = json.loads((ROOT / "data" / "foods.json").read_text(encoding="utf-8"))

# slot: (min kcal, max kcal, min protein g)
BANDS = {
    "breakfast": (250, 550, 20),
    "lunch": (350, 700, 30),
    "dinner": (400, 800, 33),
}

REQUIRED = {"id", "name", "slot", "source", "servings", "ingredients", "steps", "tags"}


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

        if r["slot"] not in BANDS:
            errors.append(f"{rid}: slot must be one of {sorted(BANDS)}")
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
        lo, hi, minp = BANDS[r["slot"]]
        if not lo <= kcal <= hi:
            errors.append(f"{rid}: {kcal:.0f} kcal is outside the {r['slot']} band {lo}-{hi}")
        if protein < minp:
            errors.append(f"{rid}: {protein:.0f} g protein is below the {r['slot']} minimum {minp}")
        if kcal and 900 * fat / kcal > 50:
            warnings.append(f"{rid}: {900 * fat / kcal:.0f}% of calories from fat")

        rows.append((rid, r["slot"], kcal, protein, fat, "vegetarian" in r.get("tags", [])))

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
