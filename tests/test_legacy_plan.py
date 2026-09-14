"""Tests that the archived fixed-week plan still agrees with the model.

The catalogue app superseded this document; it is kept so the original figures
stay verifiable. ``test_app.py`` covers the current planner.

The plan's documents state calorie and protein figures explicitly. These tests
exist because those figures were once hand-written and drifted badly from the
underlying recipes. Every published number must trace back to ``nutrition.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mealplanner import nutrition as n
from mealplanner.parse import ParseError, parse

ROOT = Path(__file__).resolve().parents[1]
MEAL_PLAN = ROOT / "content" / "legacy-meal-plan.md"

# The model rounds each meal before summing; the documents were generated from an
# unrounded sum. That accounts for a consistent +/-1. Anything larger is a real bug.
TOLERANCE = 2


@pytest.fixture(scope="module")
def plan() -> dict:
    return parse(MEAL_PLAN)


@pytest.fixture(scope="module")
def by_code() -> dict[str, tuple[float, float, float]]:
    """Model totals keyed by meal code, e.g. 'D1'."""
    return {name.split()[0]: totals for name, totals in n.recipe_totals().items()}


def test_documents_exist():
    assert MEAL_PLAN.exists()


def test_meal_plan_structure_intact(plan):
    """Guards against the silent truncation that once lost whole sections."""
    assert len(plan["days"]) == 7
    assert len(plan["recipes"]) == 14
    assert len(plan["snacks"]) == 6
    assert len(plan["lists"]) == 3


def test_every_meal_in_week_table_resolves(plan):
    """A leftover written as prose once resolved to null and rendered an empty card."""
    for day in plan["days"]:
        assert day["first"], f"{day['day']} has no first meal"
        assert day["dinner"], f"{day['day']} has no dinner"
        assert day["first"] in plan["recipes"], f"{day['day']}: {day['first']} not a recipe"
        assert day["dinner"] in plan["recipes"], f"{day['day']}: {day['dinner']} not a recipe"


def test_every_recipe_has_ingredients_and_steps(plan):
    for code, recipe in plan["recipes"].items():
        if recipe["alias"]:
            continue  # leftovers point at their parent recipe
        assert recipe["ingredients"], f"{code} has no ingredients"
        assert recipe["steps"], f"{code} has no method steps"


def test_daily_figures_match_the_model(plan):
    drift = []
    for day in plan["days"]:
        kcal, protein, _ = n.day_totals(day["day"])
        if abs(day["kcal"] - kcal) > TOLERANCE:
            drift.append(f"{day['day']} kcal: document {day['kcal']} vs model {kcal:.0f}")
        if abs(day["protein"] - protein) > TOLERANCE:
            drift.append(f"{day['day']} protein: document {day['protein']} vs model {protein:.0f}")
    assert not drift, "documents have drifted from the nutrition model:\n" + "\n".join(drift)


def test_recipe_figures_match_the_model(plan, by_code):
    drift = []
    for code, recipe in plan["recipes"].items():
        if recipe["kcal"] is None or code not in by_code:
            continue
        kcal, protein, _ = by_code[code]
        if abs(recipe["kcal"] - kcal) > TOLERANCE:
            drift.append(f"{code} kcal: document {recipe['kcal']} vs model {kcal:.0f}")
        if abs(recipe["protein"] - protein) > TOLERANCE:
            drift.append(f"{code} protein: document {recipe['protein']} vs model {protein:.0f}")
    assert not drift, "recipes have drifted from the nutrition model:\n" + "\n".join(drift)


def test_snack_figures_match_the_model(plan, by_code):
    drift = []
    for code, snack in plan["snacks"].items():
        if code not in by_code:
            continue
        kcal, protein, _ = by_code[code]
        if abs(snack["kcal"] - kcal) > TOLERANCE:
            drift.append(f"{code} kcal: document {snack['kcal']} vs model {kcal:.0f}")
        if abs(snack["protein"] - protein) > TOLERANCE:
            drift.append(f"{code} protein: document {snack['protein']} vs model {protein:.0f}")
    assert not drift, "snacks have drifted from the nutrition model:\n" + "\n".join(drift)


def test_parse_fails_loudly_on_a_broken_document(tmp_path):
    broken = tmp_path / "broken.md"
    broken.write_text("# Not the meal plan\n")
    with pytest.raises(ParseError):
        parse(broken)


# --- costing -----------------------------------------------------------------


def test_every_shopping_item_is_priced(plan):
    for shopping_list in plan["lists"]:
        for item in shopping_list["items"]:
            assert "price" in item, f"{shopping_list['id']}: {item['item']} has no price"


def test_list_totals_sum_their_items(plan):
    for shopping_list in plan["lists"]:
        expected = round(sum(i["price"] for i in shopping_list["items"]), 2)
        assert abs(shopping_list["total"] - expected) < 0.01


def test_cost_summary_is_internally_consistent(plan):
    cost = plan["cost"]
    assert abs(cost["weekly"] - (cost["lidl"] + cost["tesco"])) < 0.01
    assert abs(cost["true"] - (cost["weekly"] + cost["amortised"])) < 0.01
    assert abs(cost["perday"] - cost["true"] / 7) < 0.01


def test_long_life_items_are_not_on_weekly_lists(plan):
    """Anything lasting longer than a week belongs on the as-needed list."""
    weekly_ids = {"lidl", "tesco"}
    offenders = [
        f"{sl['id']}: {i['item']}"
        for sl in plan["lists"]
        if sl["id"] in weekly_ids
        for i in sl["items"]
        if "weeks" in i
    ]
    assert not offenders, f"long-life items on a weekly list: {offenders}"
