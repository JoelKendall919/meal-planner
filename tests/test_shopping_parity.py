"""The JavaScript and Python shopping-list implementations must agree.

The browser aggregates the shopping list interactively, so the logic exists twice.
This test runs both against the same randomised selections and compares the
output, which is the only reliable way to stop them drifting apart.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from mealplanner.catalogue import load_foods, load_recipes
from mealplanner.shopping import build_list

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "src" / "mealplanner" / "templates" / "shopping.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def run_js(recipes: list[dict], foods: dict, selections: list[str], tmp_path: Path) -> list[dict]:
    payload = tmp_path / "payload.json"
    payload.write_text(
        json.dumps({"recipes": recipes, "foods": foods, "selections": selections}),
        encoding="utf-8",
    )
    runner = tmp_path / "run.js"
    runner.write_text(
        f"""
const {{ buildShoppingList }} = require({str(JS)!r});
const data = require({str(payload)!r});
process.stdout.write(JSON.stringify(
  buildShoppingList(data.recipes, data.foods, data.selections)
));
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["node", str(runner)], capture_output=True, text=True, check=True, cwd=tmp_path
    )
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def catalogue():
    foods = load_foods()
    recipes = load_recipes(foods)
    return foods, recipes


def serialisable(foods) -> dict:
    return {
        k: {
            "kcal": f.kcal,
            "protein": f.protein,
            "fat": f.fat,
            "group": f.group,
            "unit_g": f.unit_g,
            "unit": f.unit,
            "aisle": f.aisle,
        }
        for k, f in foods.items()
    }


@pytest.mark.parametrize("seed", range(12))
def test_js_matches_python(catalogue, tmp_path, seed):
    foods, recipes = catalogue
    rng = random.Random(seed)
    selections = [r.id for r in rng.sample(recipes, k=rng.randint(3, 14))]
    # Occasionally cook something twice, which exercises the summing path.
    if selections and rng.random() < 0.5:
        selections.append(rng.choice(selections))

    expected = build_list(recipes, foods, selections)
    actual = run_js([r.to_dict() for r in recipes], serialisable(foods), selections, tmp_path)

    assert actual == expected, f"implementations diverged for seed {seed}"


def test_whole_catalogue_matches(catalogue, tmp_path):
    foods, recipes = catalogue
    selections = [r.id for r in recipes]
    expected = build_list(recipes, foods, selections)
    actual = run_js([r.to_dict() for r in recipes], serialisable(foods), selections, tmp_path)
    assert actual == expected
