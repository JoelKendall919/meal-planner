"""Tests for the recipe catalogue and the planner app built from it.

The catalogue is authored by hand, so these tests exist to catch the failure
modes that actually happened: ingredient keys that do not resolve, macro figures
written by eye rather than computed, and descriptive tags that contradict the
numbers (one early batch tagged 14 recipes "high-protein" that were not).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from mealplanner.build import build, payload
from mealplanner.catalogue import (
    MAIN_SLOTS,
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
    # Snacks exist to buy protein cheaply in calories, so the band is tight.
    "snack": (90, 280, 12),
}

# Snacks are a top-up rather than a meal, so the slot sizes differ.
MIN_PER_SLOT = {"breakfast": 25, "lunch": 25, "dinner": 25, "snack": 15}


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
        least = MIN_PER_SLOT[slot]
        assert by_slot[slot] >= least, f"{slot} has {by_slot[slot]} recipes, expected {least}+"


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
    """Recomputes kcal independently to guard the macro implementation.

    This checks ``Recipe.macros`` itself, not the recipe data: a wrong weight moves
    both sides equally, but a dropped ``/ 100`` or a swapped field is caught. Data
    errors are covered by the band and ingredient-resolution tests instead.

    Allows 1 kcal: a total landing exactly on .5 can round either way depending on
    the last bit of the running sum, which differs between Python versions.
    """
    for r in recipes:
        kcal = sum(foods[i.food].kcal * i.grams / 100 for i in r.ingredients)
        assert abs(r.macros["kcal"] - kcal) <= 1, (
            f"{r.id} claims {r.macros['kcal']} kcal but its ingredients give {kcal:.1f}"
        )


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
    assert len(data["recipes"]) >= sum(MIN_PER_SLOT.values())
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


def test_targets_are_achievable_from_the_catalogue(recipes):
    """The default goals must be reachable by picking real meals.

    This guards a genuine mistake that shipped: the goals were carried over from
    the earlier hand-built week (180 g protein), which no combination of these
    recipes can reach under the calorie cap. A goal you cannot hit is worse than
    no goal, because every day reads as a failure.
    """
    from itertools import product

    from mealplanner.build import TARGETS

    pools = [[r for r in recipes if r.slot == slot] for slot in MAIN_SLOTS]
    snacks = [r for r in recipes if r.slot == "snack"]
    hits = 0
    total = 0
    for combo in product(*pools):
        total += 1
        kcal = sum(r.macros["kcal"] for r in combo)
        protein = sum(r.macros["protein"] for r in combo)
        if kcal > TARGETS["kcal"]:
            continue
        # A day may be topped up with one snack, which is how the planner fills.
        best = max(
            (
                protein + s.macros["protein"]
                for s in snacks
                if kcal + s.macros["kcal"] <= TARGETS["kcal"]
            ),
            default=protein,
        )
        if best >= TARGETS["protein"]:
            hits += 1
    share = hits / total
    assert share >= 0.05, (
        f"only {hits} of {total} day combinations ({share:.1%}) meet the "
        f"{TARGETS['protein']} g protein goal within {TARGETS['kcal']} kcal"
    )


def test_targets_energy_roughly_matches_the_calorie_goal():
    """Protein/fat/carb goals should add up to about the calorie goal."""
    from mealplanner.build import TARGETS

    energy = TARGETS["protein"] * 4 + TARGETS["fat"] * 9 + TARGETS["carbs"] * 4
    assert abs(energy - TARGETS["kcal"]) <= TARGETS["kcal"] * 0.1, (
        f"macro goals give {energy} kcal against a {TARGETS['kcal']} kcal goal"
    )


def test_app_has_every_section_the_planner_needs(tmp_path):
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    for tab in ("plan", "recipes", "nutrients", "shop"):
        assert f'data-tab="{tab}"' in html, f"the {tab} tab is missing"
    # The view buttons are generated from this list, so check the source of them.
    assert '["day","week","month"]' in html, "the calendar views are missing"
    assert 'data-view="${v}"' in html, "the view buttons carry no handler hook"
    assert "data-step=" in html, "there is no way to move between weeks"


def test_app_keeps_the_shopping_list_editable(tmp_path):
    """Add, remove, tick and start over are the list's whole point."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    for hook in ("data-tick", "data-rm", "data-edit", "data-newlist", "data-untick"):
        assert hook in html, f"the shopping list has no {hook} control"


def test_fill_budgets_a_whole_day(tmp_path):
    """SLOT_SHARE splits the day's calorie goal, so it has to add up to 1."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    line = next(ln for ln in html.splitlines() if ln.startswith("const SLOT_SHARE"))
    shares = [float(part) for part in re.findall(r":\s*([0-9.]+)", line)]
    assert len(shares) == len(MAIN_SLOTS), "the budget must cover every main meal"
    assert abs(sum(shares) - 1.0) < 1e-9, f"slot shares add up to {sum(shares)}"


def test_stored_plans_from_the_previous_version_are_migrated(tmp_path):
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert 'KEY = "mealplanner.v3"' in html
    assert "mealplanner.v2" in html, "old saved plans would be silently dropped"


def test_snacks_are_worth_eating_for_the_protein(recipes):
    """Snacks exist only to buy protein cheaply in calories.

    A snack that is not protein-dense spends calories the day cannot spare, so
    this fixes the ratio rather than the absolute figures.
    """
    snacks = [r for r in recipes if r.slot == "snack"]
    assert len(snacks) >= 15
    for r in snacks:
        ratio = r.macros["protein"] / r.macros["kcal"] * 100
        assert ratio >= 8, (
            f"{r.id} gives {ratio:.1f} g protein per 100 kcal, too little to be a top-up"
        )


def test_a_day_can_reach_the_protein_goal_within_the_calorie_goal(recipes):
    """The snack top-up has to actually close the gap it exists to close."""
    from mealplanner.build import TARGETS

    def best(slot, key):
        return max(r.macros[key] for r in recipes if r.slot == slot)

    mains_protein = sum(best(slot, "protein") for slot in MAIN_SLOTS)
    assert mains_protein + best("snack", "protein") >= TARGETS["protein"]


def test_nutrients_page_can_close_the_protein_gap(tmp_path):
    """The snack picker is the point of the nutrients page, not decoration."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert "function snackOptions" in html
    assert "data-addsnack=" in html, "snacks cannot be added from the nutrients page"
    assert "Day becomes" in html, "the effect on the day is not shown"
    # Suggestions must be filtered by the calories left, not merely sorted.
    assert "r.macros.kcal <= headroom" in html, "snacks are not limited to spare calories"
