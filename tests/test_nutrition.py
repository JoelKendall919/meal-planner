"""Tests for the nutrition model itself."""

from __future__ import annotations

import pytest

from mealplanner import nutrition as n

# Published figures for plan v7. Changing a recipe should force these to be
# reviewed deliberately rather than drifting unnoticed.
PUBLISHED_AVERAGE = {"kcal": 1753, "protein": 186, "fat": 58, "carbs": 122}
PUBLISHED_WHEY_G = 210
PUBLISHED_YOGHURT_G = 3020


def test_every_food_has_three_macros():
    for name, values in n.FOODS.items():
        assert len(values) == 3, f"{name} should have (kcal, protein, fat)"
        assert all(v >= 0 for v in values), f"{name} has a negative value"


def test_every_recipe_ingredient_is_known():
    unknown = {
        ingredient
        for items in n.RECIPES.values()
        for ingredient, _ in items
        if ingredient not in n.FOODS
    }
    assert not unknown, f"ingredients missing from FOODS: {unknown}"


def test_macros_are_physically_consistent():
    """Protein and fat calories must not exceed total calories."""
    for name, items in n.RECIPES.items():
        kcal, protein, fat = n.totals(items)
        if kcal == 0:
            continue
        assert 4 * protein + 9 * fat <= kcal + 1, f"{name} macros exceed its calories"


def test_all_seven_days_present():
    assert list(n.DAYS) == n.DAY_ORDER


def test_every_day_meal_resolves_to_a_recipe():
    for day, meals in n.DAYS.items():
        for meal in meals:
            assert meal in n.RECIPES or meal in n.ALIASES, f"{day}: unknown meal {meal!r}"


def test_leftovers_match_their_parent_portion():
    per = n.recipe_totals()
    for alias, parent in n.ALIASES.items():
        assert per[alias] == per[parent], f"{alias} should equal {parent}"


@pytest.mark.parametrize("day", n.DAY_ORDER)
def test_daily_calories_near_target(day):
    kcal, _, _ = n.day_totals(day)
    assert abs(kcal - n.TARGET_KCAL) <= 70, f"{day} is {kcal:.0f} kcal"


@pytest.mark.parametrize("day", n.DAY_ORDER)
def test_daily_protein_sufficient(day):
    _, protein, _ = n.day_totals(day)
    assert protein >= n.TARGET_PROTEIN, f"{day} has only {protein:.0f} g protein"


@pytest.mark.parametrize("day", n.DAY_ORDER)
def test_daily_fat_within_sensible_range(day):
    """Fat should stay clear of both extremes; one draft hit 44% of intake."""
    kcal, _, fat = n.day_totals(day)
    share = 900 * fat / kcal
    assert 15 <= share <= 40, f"{day} draws {share:.0f}% of calories from fat"


@pytest.mark.parametrize("key,expected", PUBLISHED_AVERAGE.items())
def test_week_average_matches_published_figures(key, expected):
    actual = n.week_average()[key]
    assert abs(actual - expected) <= 1, f"{key}: {actual:.1f} vs published {expected}"


def test_weekly_shopping_quantities_match_published():
    assert abs(n.weekly_grams("whey") - PUBLISHED_WHEY_G) <= 1
    assert abs(n.weekly_grams("greek yoghurt 0%") - PUBLISHED_YOGHURT_G) <= 1


def test_report_renders():
    text = n.report()
    assert "AVG" in text and "whey/week" in text
