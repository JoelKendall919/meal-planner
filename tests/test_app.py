"""Tests for the recipe catalogue and the planner app built from it.

The catalogue is authored by hand, so these tests exist to catch the failure
modes that actually happened: ingredient keys that do not resolve, macro figures
written by eye rather than computed, and descriptive tags that contradict the
numbers (one early batch tagged 14 recipes "high-protein" that were not).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mealplanner.build import build, payload
from mealplanner.catalogue import (
    PROTEIN_TAG_G,
    QUICK_MINUTES,
    SLOTS,
    load_foods,
    load_recipes,
)
from mealplanner.shopping import build_list

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# Per-slot sanity bands. These are deliberately wider than the authoring brief:
# they catch a decimal-point error, not a recipe that is 20 kcal off target.
BANDS = {
    "breakfast": (250, 550, 20),
    "lunch": (350, 700, 30),
    "dinner": (400, 800, 33),
}


@pytest.fixture(scope="module")
def foods():
    return load_foods()


@pytest.fixture(scope="module")
def recipes(foods):
    return load_recipes(foods)


def test_catalogue_is_complete(recipes):
    by_slot: dict[str, int] = {}
    for r in recipes:
        by_slot[r.slot] = by_slot.get(r.slot, 0) + 1
    assert set(by_slot) == set(SLOTS)
    for slot in SLOTS:
        assert by_slot[slot] == 25, f"{slot} has {by_slot[slot]} recipes, expected 25"


def test_recipe_ids_are_unique(recipes):
    ids = [r.id for r in recipes]
    assert len(ids) == len(set(ids))


def test_every_ingredient_resolves(recipes, foods):
    for r in recipes:
        assert r.ingredients, f"{r.id} has no ingredients"
        for item in r.ingredients:
            assert item.food in foods, f"{r.id} references unknown food {item.food!r}"
            assert item.grams > 0, f"{r.id} has a non-positive weight for {item.food}"
            assert item.display.strip(), f"{r.id} has an empty display line"


def test_every_recipe_has_method_and_source(recipes):
    for r in recipes:
        assert len(r.steps) >= 2, f"{r.id} has too few steps"
        assert all(s.strip() for s in r.steps), f"{r.id} has an empty step"
        assert r.source.get("name"), f"{r.id} does not credit a source"


def test_no_invented_source_urls(recipes):
    """Agents were told to leave the URL null rather than guess one."""
    for r in recipes:
        url = r.source.get("url")
        assert url is None or url.startswith("http"), f"{r.id} has a malformed url {url!r}"


def test_macros_are_computed_not_stored(recipes):
    """Source files must not carry macro figures that could drift from the food data."""
    for path in DATA.glob("recipes-*.json"):
        for raw in json.loads(path.read_text(encoding="utf-8")):
            overlap = {"kcal", "protein", "fat", "carbs", "macros"} & set(raw)
            assert not overlap, f"{raw['id']} stores {overlap}; macros must be derived"


def test_macros_match_the_food_data(recipes, foods):
    for r in recipes:
        kcal = sum(foods[i.food].kcal * i.grams / 100 for i in r.ingredients)
        assert r.macros["kcal"] == round(kcal), f"{r.id} kcal disagrees with its ingredients"


def test_recipes_sit_in_sensible_bands(recipes):
    for r in recipes:
        lo, hi, min_protein = BANDS[r.slot]
        assert lo <= r.macros["kcal"] <= hi, f"{r.id} is {r.macros['kcal']} kcal"
        assert r.macros["protein"] >= min_protein, f"{r.id} has {r.macros['protein']} g protein"


def test_derived_tags_agree_with_the_numbers(recipes):
    """The bug this guards: 14 of 25 breakfasts were mislabelled high-protein."""
    for r in recipes:
        high = "high-protein" in r.tags
        assert high == (r.macros["protein"] >= PROTEIN_TAG_G), (
            f"{r.id} is tagged high-protein={high} at {r.macros['protein']} g"
        )
        quick = "quick" in r.tags
        limit = QUICK_MINUTES[r.slot]
        assert quick == (0 < r.total_min <= limit), (
            f"{r.id} is tagged quick={quick} at {r.total_min} min (limit {limit})"
        )


def test_vegetarian_tag_has_no_meat_or_fish(recipes, foods):
    meat_aisles = {"meat", "fish"}
    for r in recipes:
        if "vegetarian" not in r.tags:
            continue
        offenders = [i.food for i in r.ingredients if foods[i.food].aisle in meat_aisles]
        assert not offenders, f"{r.id} is tagged vegetarian but contains {offenders}"


def test_there_is_enough_variety_to_plan_a_week(recipes):
    """A week needs 7 of each slot without repeating, and some meat-free options."""
    for slot in SLOTS:
        pool = [r for r in recipes if r.slot == slot]
        assert len(pool) >= 7
        veg = [r for r in pool if "vegetarian" in r.tags]
        assert len(veg) >= 5, f"only {len(veg)} vegetarian {slot} options"


def test_shopping_list_covers_every_ingredient(recipes, foods):
    lines = build_list(recipes, foods, [r.id for r in recipes])
    listed = {c["food"] for line in lines for c in line["components"]}
    used = {i.food for r in recipes for i in r.ingredients}
    assert listed == used


def test_shopping_list_merges_interchangeable_items(recipes, foods):
    lines = build_list(recipes, foods, [r.id for r in recipes])
    assert any(line["merged"] for line in lines), "nothing merged across the whole catalogue"
    for line in lines:
        groups = {foods[c["food"]].group for c in line["components"]}
        assert groups == {line["group"]}


def test_build_produces_a_self_contained_site(tmp_path):
    out = build(tmp_path)
    html = (out / "index.html").read_text(encoding="utf-8")

    assert "__DATA__" not in html, "data placeholder was not substituted"
    assert "/* __SHOPPING_JS__ */" not in html, "shopping code was not inlined"
    assert "buildShoppingList" in html, "shopping code missing from the page"
    assert "<script src=" not in html, "the app must work offline with no external scripts"
    assert "<link rel=stylesheet" not in html and 'rel="stylesheet"' not in html

    data = json.loads((out / "catalogue.json").read_text(encoding="utf-8"))
    assert len(data["recipes"]) == 75
    assert data["targets"]["kcal"] > 0
    assert "high-protein" in data["tags"]


def test_payload_recipes_carry_what_the_app_renders():
    data = payload()
    for r in data["recipes"]:
        for field in ("id", "name", "slot", "tags", "ingredients", "steps", "macros", "total_min"):
            assert field in r, f"{r.get('id')} payload is missing {field}"
        for key in ("kcal", "protein", "fat", "carbs"):
            assert key in r["macros"]
    for food in data["foods"].values():
        for field in ("group", "aisle", "kcal", "protein"):
            assert field in food
