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
    LIGHT_MAX,
    MAIN_SLOTS,
    PLAUSIBLE_KCAL,
    PROTEIN_TAG_G,
    QUICK_MINUTES,
    SLOTS,
    SNACK_PROTEIN_PER_100KCAL,
    load_foods,
    load_recipes,
)
from mealplanner.shopping import build_list

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# Plausibility ranges only. These catch a decimal-point slip or ounces entered as
# grams -- they are not diet targets. The previous version of this table was a
# cutting brief in disguise: it required 20 g of protein at breakfast and capped
# dinner at 800 kcal, which made toast and marmalade, any soup, fish and chips
# and almost every ordinary snack illegal recipes.
BANDS = PLAUSIBLE_KCAL

# The catalogue has to be deep enough that a month of planning does not repeat.
# Counts are per slot and a multi-slot recipe counts towards each of its slots.
MIN_PER_SLOT = {"breakfast": 25, "lunch": 25, "dinner": 25, "snack": 25}


@pytest.fixture(scope="module")
def foods():
    return load_foods()


@pytest.fixture(scope="module")
def recipes(foods):
    return load_recipes(foods)


def test_catalogue_is_complete(recipes):
    by_slot: dict[str, int] = {}
    for r in recipes:
        for slot in r.slots:
            by_slot[slot] = by_slot.get(slot, 0) + 1
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
    for path in (DATA / "recipes").glob("*.json"):
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
    """Plausibility, not diet fitness.

    A recipe is judged against the most generous of its slots, so a dish that
    works as both lunch and dinner only has to be plausible as one of them.
    """
    for r in recipes:
        lo = min(BANDS[s][0] for s in r.slots)
        hi = max(BANDS[s][1] for s in r.slots)
        assert lo <= r.macros["kcal"] <= hi, (
            f"{r.id} is {r.macros['kcal']} kcal, implausible for {'/'.join(r.slots)}"
        )
        floor = 4 * r.macros["protein"] + 9 * r.macros["fat"]
        assert floor <= r.macros["kcal"] + 30, (
            f"{r.id}: protein and fat alone give {floor} kcal but it totals {r.macros['kcal']}"
        )


def test_derived_tags_agree_with_the_numbers(recipes):
    """The bug this guards: 14 of 25 breakfasts were mislabelled high-protein."""
    for r in recipes:
        high = "high-protein" in r.tags
        assert high == (r.macros["protein"] >= PROTEIN_TAG_G), (
            f"{r.id} is tagged high-protein={high} at {r.macros['protein']} g"
        )
        quick = "quick" in r.tags
        limit = max(QUICK_MINUTES[s] for s in r.slots)
        assert quick == (0 < r.total_min <= limit), (
            f"{r.id} is tagged quick={quick} at {r.total_min} min (limit {limit})"
        )
        light = "light" in r.tags
        ceiling = max(LIGHT_MAX[s] for s in r.slots)
        assert light == (r.macros["kcal"] <= ceiling), (
            f"{r.id} is tagged light={light} at {r.macros['kcal']} kcal (ceiling {ceiling})"
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
        pool = [r for r in recipes if slot in r.slots]
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
        for field in (
            "id",
            "name",
            "slots",
            "category",
            "tags",
            "ingredients",
            "steps",
            "macros",
            "total_min",
        ):
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

    The catalogue is now a general cookbook, so this measures the *scoped* pool.
    Chasing protein across everything from cereal to sticky toffee pudding is not
    a workflow anyone has; the planner offers a high-protein scope for exactly
    this, and that scope is what has to be feasible. The unscoped case is covered
    by ``test_a_typical_planned_day_is_not_diluted_by_the_general_catalogue``.
    """
    from itertools import product

    from mealplanner.build import TARGETS

    pool = [r for r in recipes if "high-protein" in r.tags]
    pools = [[r for r in pool if slot in r.slots] for slot in MAIN_SLOTS]
    assert all(pools), "the high-protein scope must cover every main slot"
    snacks = [r for r in recipes if "snack" in r.slots]
    hits = 0
    # Counted over days that fit the calorie budget, not over every combination.
    # Dividing by all combinations conflates two different failures: a day rejected
    # for being 2400 kcal is not a day that missed its protein goal, and padding the
    # catalogue with large recipes would deflate this score without anything
    # actually getting worse for the user.
    eligible = 0
    for combo in product(*pools):
        kcal = sum(r.macros["kcal"] for r in combo)
        protein = sum(r.macros["protein"] for r in combo)
        if kcal > TARGETS["kcal"]:
            continue
        eligible += 1
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
    assert eligible >= 500, f"only {eligible} scoped days fit the calorie budget"
    share = hits / eligible
    # 15%: often enough that the goal is reachable by choosing rather than by luck.
    # The catalogue currently sits at about 33%, so this has real headroom.
    assert share >= 0.15, (
        f"only {hits} of {eligible} calorie-legal high-protein days ({share:.1%}) "
        f"meet the {TARGETS['protein']} g protein goal within {TARGETS['kcal']} kcal"
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


def test_enough_snacks_are_protein_dense_to_top_a_day_up(recipes):
    """The catalogue must keep enough protein-dense snacks to serve a cut.

    This used to assert that *every* snack carried 8 g of protein per 100 kcal,
    which is why an apple, a packet of crisps and a chocolate digestive could not
    exist in the catalogue at all. Ordinary snacks are now allowed, so the rule
    moves from every snack to a supply check on the protein-dense ones, and the
    ratio itself becomes the derived ``protein-snack`` tag.
    """
    snacks = [r for r in recipes if "snack" in r.slots]
    assert len(snacks) >= 25

    dense = [r for r in snacks if "protein-snack" in r.tags]
    # Six rather than eight: retiring the diet-only catalogue took the protein-dense
    # snacks from 20 to 7, which is a real and accepted loss of depth. Six is the
    # floor that still lets a week be planned without eating the same thing daily.
    assert len(dense) >= 6, (
        f"only {len(dense)} protein-dense snacks; the planner cannot top up a short day"
    )
    # A count alone is a weak guard: six trivial 3 g snacks would satisfy it while
    # being useless. What the planner actually needs is a top-up that closes a real
    # gap, so require several that do so without spending the day's calories.
    useful = [r for r in dense if r.macros["protein"] >= 15 and r.macros["kcal"] <= 300]
    assert len(useful) >= 3, (
        f"only {len(useful)} snacks add 15 g protein for under 300 kcal; "
        "a top-up cannot meaningfully close the protein gap"
    )
    for r in dense:
        ratio = r.macros["protein"] / r.macros["kcal"] * 100
        assert ratio >= SNACK_PROTEIN_PER_100KCAL, (
            f"{r.id} is tagged protein-snack at {ratio:.1f} g per 100 kcal"
        )
    for r in snacks:
        if "protein-snack" in r.tags:
            continue
        ratio = r.macros["protein"] / r.macros["kcal"] * 100 if r.macros["kcal"] else 0
        assert ratio < SNACK_PROTEIN_PER_100KCAL, (
            f"{r.id} hits {ratio:.1f} g per 100 kcal but is not tagged protein-snack"
        )


def test_a_day_can_reach_the_protein_goal_within_the_calorie_goal(recipes):
    """The snack top-up has to actually close the gap it exists to close."""
    from mealplanner.build import TARGETS

    def best(slot, key):
        return max(r.macros[key] for r in recipes if slot in r.slots)

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


def test_the_plan_picker_works_like_the_recipes_tab(tmp_path):
    """Choosing a meal should offer the same search and filters as browsing.

    The picker and the Recipes tab share one filter implementation so the two
    cannot drift apart. They keep separate filter state, though: browsing for a
    Tuesday lunch must not silently rewrite what the Recipes tab was showing.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert "function filterRecipes" in html, "the filter logic is not shared"
    assert "function filterControls" in html, "the search and chips are not shared"
    assert html.count("filterControls(") >= 3, "one of the two surfaces is not using it"
    assert "let pickFilter" in html, "the picker has no filter state of its own"
    # The slot you tapped is preselected, so you land on meals that belong there.
    assert "pickFilter = { slot: slot" in html, "the picker does not preselect the slot"
    assert 'data-search="${ns}"' in html, "the search boxes are not namespaced"


def test_recipe_rows_show_every_macro(tmp_path):
    """A row you pick a meal from has to show what the meal costs you.

    Scoped to `recipeRow` on purpose: `macroLine` is used on several surfaces,
    so asserting it appears *somewhere* passed even with the recipe row stripped.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert "function macroLine" in html
    row = html[html.index("function recipeRow") : html.index("function viewRecipes")]
    assert "macroLine(r.macros)" in row, "recipe rows show no macro line"
    assert "MACROS.map" in html[html.index("function macroLine") :], (
        "the macro line is not generated from MACROS, so it can fall out of step"
    )


def test_portions_scale_the_recipe_but_not_the_shopping_list(tmp_path):
    """Portions are a cooking aid.

    The shopping list is built from the plan, and a planned slot is always one
    portion. If the portions control fed into the list as well, cooking two and
    planning it on two days would buy four portions of ingredients.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert "function scaleGrams" in html, "there is no portion scaling"
    assert "data-portions=" in html, "the portions stepper has no handler hook"
    assert "scaleGrams(i.grams, n)" in html, "ingredients do not scale"
    # buildShoppingList is driven by recipe ids from the plan and nothing else,
    # so there is no route from the portions control into the shop.
    shopping = Path("src/mealplanner/templates/shopping.js").read_text(encoding="utf-8")
    assert "portions" not in shopping, "the shopping list knows about portions"


def test_each_macro_has_a_colour_and_a_direction(tmp_path):
    """Colour carries meaning twice over, and the two must not be confused.

    Each macro has a fixed identity colour so a figure is recognisable before
    you read its label. Separately, a figure is scored against its goal. Those
    are different axes: `k-*` classes say what you are looking at, `s-*` classes
    say how you are doing.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    for key in ("kcal", "protein", "fat", "carbs"):
        assert f"--m-{key}:" in html, f"{key} has no colour token"
        assert f".k-{key}{{color:var(--m-{key})}}" in html, f"{key} has no colour class"
    assert "function statusClass" in html, "nothing scores a figure against its goal"
    for cls in ("s-good", "s-warn", "s-bad"):
        assert f".{cls}{{color:var(" in html, f"{cls} has no colour"


def test_protein_is_scored_as_a_target_and_the_rest_as_budgets(tmp_path):
    """Protein is a floor, not a ceiling.

    Scoring it like calories would paint an empty day green and a day that hit
    its goal red, which is exactly backwards.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    block = html[html.index("const MACROS = [") : html.index("const MACRO_BY_KEY")]
    targets = re.findall(r'key: "(\w+)".*?dir: "target"', block)
    budgets = re.findall(r'key: "(\w+)".*?dir: "budget"', block)
    assert targets == ["protein"], f"expected only protein to be a target, got {targets}"
    assert sorted(budgets) == ["carbs", "fat", "kcal"], f"unexpected budgets: {budgets}"
    assert 'dir === "target"' in html, "statusClass ignores the direction"


def test_the_plan_page_has_no_progress_bars(tmp_path):
    """The bars rendered as blocks across the figures, so they were removed.

    `.prog` was an inline span given a height and a percentage-width child. An
    inline box ignores height, so the child resolved against the wrong box and
    painted over the numbers. The one surviving bar is on the Nutrients page,
    whose whole job is comparing against goals, and it is scoped to `.barwrap`
    so it cannot leak back into the macro cards.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert "function macroCards" in html
    cards = html[html.index("function macroCards") : html.index("function macroLine")]
    assert "prog" not in cards, "the macro cards still render a progress bar"
    assert ".barwrap .prog{display:block" in html, "the nutrients bar is not a block"
    assert re.search(r"(?<!barwrap )\.prog\{", html) is None, "an unscoped .prog remains"


def test_a_typical_planned_day_is_not_diluted_by_the_general_catalogue(recipes):
    """A median day must stay edible, not just a best-case day.

    ``test_targets_are_achievable_from_the_catalogue`` is a *ceiling* test: it asks
    whether some combination can reach the goal. That question keeps answering yes
    while the catalogue quietly rots around it, because one heroic combination is
    enough to satisfy it.

    Opening the catalogue to everyday cooking made that blind spot dangerous. The
    pool now contains recipes that will happily fill 1750 kcal with very little
    protein, so the planner can produce a day that passes every calorie check and
    is still a bad day. This measures the *median* instead, which is what a user
    actually gets when they let the planner choose.
    """
    import random
    from statistics import median

    from mealplanner.build import TARGETS

    pools = [[r for r in recipes if slot in r.slots] for slot in MAIN_SLOTS]
    rng = random.Random(20240607)
    days = []
    for _ in range(4000):
        combo = [rng.choice(pool) for pool in pools]
        kcal = sum(r.macros["kcal"] for r in combo)
        if not 0.75 * TARGETS["kcal"] <= kcal <= TARGETS["kcal"]:
            continue
        days.append(sum(r.macros["protein"] for r in combo))

    assert len(days) >= 200, "too few sampled days landed in the calorie window"
    typical = median(days)
    # Not the 140 g goal: an unscoped day is chosen from the whole cookbook and is
    # not trying to hit it. This is a floor on how far a random-but-calorie-correct
    # day may fall, so that adding puddings and white-bread sandwiches in bulk
    # cannot quietly drag the everyday experience down without failing a test.
    assert typical >= 70, (
        f"the median calorie-correct day carries only {typical:.0f} g protein; "
        "the catalogue has been diluted to the point the planner gives bad days"
    )


def test_the_fill_scope_narrows_what_the_planner_draws_from(tmp_path):
    """Filling a day must be able to target part of the catalogue.

    Opening the catalogue up to everyday cooking created a trap: ``fillRange``
    optimises for calories and only breaks protein ties, so drawing from cereal,
    sandwiches and puddings alike will cheerfully produce a day that hits 1750
    kcal with half the protein. The scope is what makes a cut plannable again,
    and it is load-bearing rather than cosmetic -- across the whole catalogue only
    0.5% of calorie-legal days reach 150 g protein, against 11.7% when scoped.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")

    assert "function fillPool(" in html, "fill has no scoped pool"
    # The call site specifically: matching "fillPool(slot)" alone also matches the
    # function's own definition, so it would pass with fillRange never calling it.
    assert "const pool = fillPool(slot, date);" in html, (
        "fillRange does not draw from the scoped pool"
    )
    for scope in ("high-protein", "light"):
        assert f'"{scope}"' in html, f"the {scope} scope is not offered"
    assert "data-scope" in html, "the scope has no control in the plan page"
    # "Anything" is data-scope="", so a truthiness test would silently ignore it.
    # Assert the guard itself, not the phrase: the comment beside it in app.html
    # contains the same words and was quietly satisfying this on its own.
    assert 'if ("scope" in d){' in html, "the reset-to-anything scope button is dead"
    # A scope that matched nothing must not leave the day unfilled. The pool is
    # narrowed by the time limit too, so every combination needs a way out.
    assert "if (scoped.length) return scoped;" in html, "an empty scope has no fallback"
    assert "return anyTime.length ? anyTime : all;" in html, (
        "a scope that no quick recipe satisfies has no fallback"
    )


def test_the_scope_actually_changes_which_recipes_qualify(recipes):
    """The scope must be a real narrowing, not a label on the same pool."""
    for slot in MAIN_SLOTS:
        everything = [r for r in recipes if slot in r.slots]
        scoped = [r for r in everything if "high-protein" in r.tags]
        assert scoped, f"nothing high-protein for {slot}"
        assert len(scoped) < len(everything), (
            f"the high-protein scope for {slot} is the whole catalogue, so it "
            "narrows nothing and the plan it produces is no better"
        )
        lean = sum(r.macros["protein"] for r in scoped) / len(scoped)
        wide = sum(r.macros["protein"] for r in everything) / len(everything)
        assert lean > wide + 5, (
            f"scoped {slot} averages {lean:.0f} g protein against {wide:.0f} g "
            "unscoped; the scope is not buying anything"
        )


# --- the UI tweaks -------------------------------------------------------
#
# These guard behaviour that only exists in the template. Each assertion is
# pinned to a call site rather than a name: matching "fillPool(slot)" once
# passed against the function's own definition, and a "scope" check was being
# satisfied by the explanatory comment beside it.


def js_block(html: str, opener: str) -> str:
    """The text of a brace-delimited JS block, found by its opening line."""
    start = html.index(opener)
    depth = 0
    for i in range(start, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return html[start : i + 1]
    raise AssertionError(f"{opener!r} is never closed")


def test_type_filter_labels_match_the_recipe_shortlist(tmp_path):
    """The filter should name a category the way the catalogue was planned."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    block = js_block(html, "const CAT_LABEL = {")
    for slug, label in {
        "cooked-breakfast": "Hot & hearty",
        "sandwiches": "Sandwiches, toasties & wraps",
        "salads": "Salads & bowls",
        "pasta-and-italian": "Pasta, pizza & Italian",
        "curries": "Curries & spiced",
        "asian": "Asian-style",
        "british-classics": "British classics",
        "traybakes-and-quick": "Traybakes & quick",
    }.items():
        assert f'"{slug}": "{label}"' in block, f"{slug} is not labelled {label!r}"


def test_every_category_has_a_label(tmp_path, recipes):
    """An unlabelled category falls back to its slug, which looks like a bug."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    block = js_block(html, "const CAT_LABEL = {")
    labelled = set(re.findall(r'"([a-z-]+)":\s*"', block))
    used = {r.category for r in recipes}
    assert used <= labelled, f"no label for {sorted(used - labelled)}"


def test_the_filter_dropdown_offers_only_three_tags(tmp_path, recipes):
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    block = js_block(html, "const FILTER_TAGS = [")
    pairs = re.findall(r'\["([a-z-]+)",\s*"([^"]+)"\]', block)
    assert [p[0] for p in pairs] == ["vegetarian", "light", "high-protein"]
    assert [p[1] for p in pairs] == ["Vegetarian", "Light", "High protein"]
    # A filter that matches nothing is worse than no filter.
    for tag, label in pairs:
        assert any(tag in r.tags for r in recipes), f"{label} matches no recipe"
    assert "DATA.tags.map" not in html, "the full tag list is still being offered"


def test_meal_filter_is_capitalised_buttons(tmp_path):
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    block = js_block(html, "const SLOT_LABEL = {")
    for slot in SLOTS:
        assert f'{slot}: "{slot.capitalize()}"' in block, f"{slot} is not capitalised"
    # The label has to reach the button, not just exist.
    assert "SLOT_LABEL[s]}</button>" in html, "the meal buttons do not use the labels"


def test_type_is_a_dropdown(tmp_path):
    """Type alone runs to 21 entries, past the point a chip strip stays usable."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert 'data-${hook}="${ns}"' in html, "the filter select has no handler hook"
    assert "<select" in html, "Type is not a dropdown"
    # Selects report on change; the delegated click handler cannot see them.
    assert "const ns = ds.fcatsel;" in html, "the dropdown is not wired to change"
    assert "data-fcat=" not in html, "Type chips are still being rendered"


def test_the_filter_tags_multi_select_and_narrow(tmp_path):
    """Each tag chosen narrows further: Vegetarian + High protein means both."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert 'data-ftag="${ns}|${id}"' in html, "the filter tags are not buttons"
    assert "[data-ftag]" in html, "the filter buttons are not in the click selector"
    assert "data-tagsel" not in html, "the old single-choice Filter select survives"

    # Toggling adds or removes rather than replacing, so several can be on.
    assert (
        "f.tags = f.tags.includes(tag) ? f.tags.filter(t => t !== tag) : f.tags.concat(tag);"
    ) in html, "choosing a tag replaces the previous one instead of adding to it"

    # AND, not OR. `every` on an empty list is true, so no tags means no filtering.
    match = js_block(html, "function filterRecipes(f){")
    assert "if (!f.tags.every(t => r.tags.includes(t))) return false;" in match, (
        "the chosen tags do not all have to match"
    )
    assert "f.tag " not in match, "the old single-tag check survives"


def test_type_options_follow_the_chosen_meal(tmp_path):
    """Picking breakfast must not leave 'Roasts' on the Type list."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert "r => !f.slot || r.slots.includes(f.slot)" in html, "Type is not scoped to the meal"
    # ...and a type that no longer applies must be dropped, not left selected
    # while the results silently empty.
    assert "f.cat = null;" in html, "a stale category is never cleared"


def test_the_plan_dashboard_is_day_only(tmp_path):
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    plan = js_block(html, "function viewPlan(){")
    assert "const dash = isDay" in plan, "the dashboard is not gated on the day view"
    assert plan.count("macroCards(") == 1, "the dashboard is built more than once"
    assert "${dash}" in plan, "the gated dashboard is never rendered"


def test_the_plan_dashboard_is_not_colour_graded(tmp_path):
    """Scoring a day belongs to Nutrients; the plan just states the figures."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    cards = js_block(html, "function macroCards(")
    assert "statusClass" not in cards, "the plan dashboard still grades against the goal"
    for cls in ("s-good", "s-warn", "s-bad"):
        assert cls not in cards, f"the plan dashboard still emits {cls}"
    # Nutrients must keep its colouring: this is a plan-only change.
    nutrients = js_block(html, "function viewNutrients(){")
    assert "statusClass" in nutrients, "Nutrients lost its colour grading too"


def test_nutrients_has_no_by_day_breakdown(tmp_path):
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert "By day" not in html, "the by-day list is back"
    assert "macroStat" not in html, "macroStat outlived its only caller"


def test_portions_multiply_the_written_quantity(tmp_path):
    """Three portions of "1/2 tin" is "1 1/2 tin", not "3 x 1/2 tin"."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert "function scaleDisplay(" in html, "there is no quantity scaler"
    # The call site, not the definition.
    assert "esc(scaleDisplay(i.display, n))" in html, "the ingredient list does not scale"
    assert "${n} &times; " not in html, "the old 'n x' prefix is still there"
    # Both halves of a line have to move together.
    assert "scaleGrams(i.grams, n)" in html, "the gram weights stopped scaling"


def test_each_day_can_be_cleared_on_its_own(tmp_path):
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert 'data-clearday="${date}"' in html, "the week has no per-day clear button"
    assert "if (d.clearday){ clearDay(d.clearday); return; }" in html, "the button is dead"
    clear = js_block(html, "function clearDay(date){")
    assert "const r = clearDayMeals(date);" in clear, "clearDay does not clear the day"
    assert "[data-clearday]" in html, "the clear button is not in the click selector"
    # Clearing must take the meals out, not just the day's entry: a locked meal
    # has to survive, which means the day itself cannot simply be deleted.
    day_meals = js_block(html, "function clearDayMeals(date){")
    assert "if (isLocked(day[s])){ kept++; return; }" in day_meals, (
        "clearing a day discards locked meals"
    )
    assert "delete day[s];" in day_meals, "clearing a day leaves the meals in place"


def test_the_plan_can_copy_the_previous_period(tmp_path):
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert "if (d.copyprev){ copyPrevious(); return; }" in html, "the copy button is dead"
    labels = js_block(html, "const PREVIOUS_LABEL = {")
    for view, label in (("day", "yesterday"), ("week", "last week"), ("month", "last month")):
        assert f'{view}: "{label}"' in labels, f"{view} has no name for its previous period"
    copy = js_block(html, "function copyPrevious(){")
    # An empty source day must not wipe a planned target day: copying is additive.
    assert "filter(([from]) => from && mealsOn(from).length)" in copy, (
        "copying would clear days the source left empty"
    )
    # Anything genuinely overwritten is confirmed first. Assert the guard, not
    # the word: "confirm(" alone is still a substring of "!xconfirm(", so a
    # gutted check would keep passing.
    assert "if (busy && !confirm(" in copy, "copying replaces planned days without asking"
    assert "const busy = pairs.filter" in copy, "nothing counts what would be replaced"
    # The copy has to be independent of its source: it is rebuilt slot by slot
    # into a fresh object rather than aliasing the day it came from.
    assert "const dst = {};" in copy, "the copy aliases the original"
    assert "S.plan[to] = dst;" in copy, "the rebuilt day is never stored"
    # A leftover copied forward has to point at the copy of the meal it came
    # from, or it would claim to be eating something cooked last week -- and it
    # is deliberately left off the shopping list, so that food would never
    # be bought at all.
    assert "const landed = moved[parts[0]];" in copy, (
        "copied leftovers still point at the original week"
    )
    assert "dst[s] = landed ? Object.assign({}, v, { from: landed" in copy, (
        "copied leftovers are not remapped onto the copied cook"
    )


def test_every_toggleable_control_has_a_visible_selected_state(tmp_path):
    """A control that toggles must look different once it is on.

    The "Fill with" buttons once reused `.tag`, the read-only badge style from
    recipe cards, which has no `.on` rule. Selecting a scope worked and fill
    honoured it, but nothing on screen changed, so the buttons read as dead.
    Any class that gets `" on"` appended needs a matching `.on` rule.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    css = html[html.index("<style>") : html.index("</style>")]

    # Every class attribute whose ternary can yield "on", reduced to the literal
    # class it is built on: `class="chip${cond ? " on" : ""}"` gives "chip".
    # Controls whose whole class is the ternary (`class="${cond ? "on" : ""}"`)
    # are styled contextually, e.g. `.seg button.on`, and are not checked here.
    toggling = set(re.findall(r'class="([a-z][a-z-]*)[^"]{0,60}\?\s*" ?on"', html))
    assert toggling >= {"chip", "fsel"}, f"toggleable controls not found: {toggling}"

    for cls in toggling:
        # The bare `.cls.on` rule specifically. Matching `.cls<anything>.on`
        # is too weak: with .chip.on deleted, .chip.slot-dinner.on would still
        # satisfy it while every plain chip lost its selected state -- which is
        # the exact bug this test exists to catch.
        assert re.search(rf"\.{re.escape(cls)}\.on\s*[,{{]", css), (
            f".{cls} toggles an 'on' class but there is no '.{cls}.on' rule, "
            f"so selecting a plain .{cls} would not be visible"
        )


def test_the_fill_scope_buttons_are_live_and_honoured(tmp_path):
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    # "Anything" is data-scope="", which is falsy, so a truthiness check on the
    # dataset value would make that one button silently do nothing.
    assert 'if ("scope" in d){ S.scope = d.scope || null;' in html, (
        "the scope handler would skip the empty-string 'Anything' button"
    )
    assert "[data-scope]" in html, "the scope buttons are not in the click selector"
    pool = js_block(html, "function fillPool(slot, date){")
    # The scoping line itself. Matching "r.tags.includes(S.scope)" loosely is
    # satisfied by the fallback below it, so the main narrowing could be gutted
    # while this still passed.
    assert "const scoped = inTime.filter(r => r.tags.includes(S.scope));" in pool, (
        "fill ignores the chosen scope"
    )
    assert "if (scoped.length) return scoped;" in pool, "a narrow scope could leave slots unfilled"
    assert "return anyTime.length ? anyTime : all;" in pool, (
        "a scope and a time limit that cannot both be met has no way out"
    )


def test_fill_reaches_the_protein_top_up_on_a_fully_planned_day(tmp_path):
    """A day whose mains are planned can still be short on protein.

    Fill used to return early the moment a day had no empty main slot, so the
    protein top-up was unreachable: the snack tile sat visibly empty while the
    button reported "Nothing empty to fill" and did nothing.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    fill = js_block(html, "function fillRange(){")

    # Refusing to act must consider the empty snacks, not just the empty mains.
    assert 'const openSnacks = dates.filter(d => !takenAt(d, "snack")).length;' in fill, (
        "nothing counts the days that could still be topped up"
    )
    assert "if (!empty && !openSnacks){" in fill, (
        "fill still refuses whenever every main slot is taken"
    )

    # The early return for a fully planned day has to top up before it leaves.
    assert "if (!open.length){\n      // Every main is planned" in fill, (
        "the no-open-slots branch lost its comment, so check what replaced it"
    )
    early = fill[fill.index("if (!open.length){") :]
    assert early.index("topUpProtein(date, used);") < early.index("return;"), (
        "the top-up is still unreachable on a day with no empty main slot"
    )

    # The count reported has to be what actually landed, since a top-up may add
    # nothing and a slot with an empty pool is skipped.
    assert "const added = planned() - before;" in fill, "the toast count is assumed, not measured"
    assert "Nothing more to add" in fill, "a fill that adds nothing gives no feedback"


def test_a_saved_plan_is_pruned_of_recipes_that_no_longer_exist(tmp_path):
    """Retired recipe ids must not linger in a saved plan.

    They are invisible but not absent: the tile renders empty because the id
    does not resolve, yet the slot still counts as taken, so fill skips it and
    the day can never be completed. The v2 migration checked ids; the ordinary
    v3 load did not, so any plan saved before a catalogue edit could rot.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    prune = js_block(html, "function prunePlan(plan){")
    assert "if (day[slot] && !BY_ID[idOf(day[slot])]){ delete day[slot]; dropped++; }" in prune, (
        "unresolvable ids are not dropped"
    )
    assert "if (!Object.keys(plan[date]).length) delete plan[date];" in prune, (
        "a day emptied by pruning is left behind as an empty object"
    )
    # Corrupt state must not throw on the way in.
    assert 'if (!day || typeof day !== "object"){ delete plan[date]; return; }' in prune, (
        "a malformed day would throw during load"
    )

    # It has to run on the ordinary load path, not just the v2 migration.
    load = html[html.index("let S = blank();") : html.index("function save(){")]
    assert "pruned = prunePlan(S.plan);" in load, "the load path never prunes"
    # ...and be written back, or it recurs on every launch.
    assert "if (pruned) save();" in load, "the pruned plan is never saved"

    # Silently deleting planned meals needs saying.
    assert "no longer in the catalogue and" in html, "the user is not told their plan changed"


def test_the_shopping_list_can_be_emptied_and_started_blank(tmp_path):
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")

    # A list you build yourself has no days behind it, so it claims none.
    blank = js_block(html, "function blankList(){")
    assert "from: null, to: null" in blank, "a blank list still claims a date range"
    assert "if (!S.shopping) S.shopping = blankList();" in html, (
        "adding an item with no list creates one dated today"
    )

    # Both routes are offered where there is no list yet.
    shop = js_block(html, "function viewShop(){")
    assert 'data-newlist="1"' in shop and 'data-blank="1"' in shop, (
        "the empty shopping screen does not offer both ways to start"
    )
    assert 'data-clearitems="1"' in shop, "there is no clear button on the list"
    # A null span must not reach the date formatter.
    assert "const span = sh.from" in shop, "the subtitle would format a null date"
    assert '"Your own list"' in shop, "a list with no days has nothing to say for itself"

    for hook in ("[data-blank]", "[data-clearitems]"):
        assert hook in html, f"{hook} is not in the click selector"

    # Destructive actions ask, and a no-op explains itself instead of asking.
    clear_prompt = (
        'if (!confirm(`Remove all ${n} item${n === 1 ? "" : "s"} from the list?`)) return;'
    )
    assert clear_prompt in html, "clearing the list does not ask first"
    assert 'toast("The list is already empty"); return;' in html, (
        "clearing an empty list asks a pointless question"
    )
    # The whole guard, not a fragment: "&& !confirm(" is still a substring of
    # "&& false && !confirm(", so a gutted check would keep passing.
    assert (
        "if (S.shopping && S.shopping.items.length\n      && !confirm(`Replace the current list?"
    ) in html, "starting a blank list would silently discard one that has items on it"
    # Emptying a list leaves it usable rather than deleting it outright.
    assert "S.shopping.items = [];" in html, "clearing does not empty the items"
    assert "S.shopping.from = null;" in html, "an emptied list still claims its old days"


def test_leftovers_are_eaten_but_never_bought(tmp_path):
    """A second serving of a batch cook must not be shopped for twice.

    The shopping list is built by flattening every planned id and summing the
    grams behind them, so a leftover stored as just another copy of the recipe
    id would buy its ingredients again -- you would shop for two dinners and
    cook one. The marker on the slot is what keeps the two apart.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    ids_in = js_block(html, "function idsIn(a, b, cookedOnly){")
    assert "if (cookedOnly && isLeftover(day[s])) return;" in ids_in, (
        "leftovers are not excluded from the cooked-only list"
    )
    # The shopping list has to ask for the cooked-only view; nutrition must not.
    assert "const ids = idsIn(from, to, true);" in html, (
        "the shopping list counts leftovers as food to buy"
    )
    totals = js_block(html, "function totalsOn(date){")
    assert "mealsOn(date)" in totals, "the day's totals stopped counting every serving"
    meals_on = js_block(html, "function mealsOn(date){")
    assert "isLeftover" not in meals_on, (
        "nutrition is skipping leftovers, so days with them read as under-eaten"
    )


def test_a_leftover_cannot_outlive_the_meal_it_came_from(tmp_path):
    """An orphaned leftover is food that was never cooked and never bought.

    This is the stale-id bug in a new form: the slot resolves to a real recipe,
    so nothing looks wrong, but its ingredients were deliberately left off the
    shopping list because another day was supposed to cook them.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    prune = js_block(html, "function prunePlan(plan){")
    orphan = "if (isLeftover(v) && !cooks(plan, v.from, idOf(v))){ delete day[slot]; dropped++; }"
    assert orphan in prune, "a leftover whose source has gone survives the load"

    cooks = js_block(html, "function cooks(plan, ref, id){")
    assert "return !!v && idOf(v) === id && !isLeftover(v);" in cooks, (
        "the source check would accept a leftover of a leftover, or a different dish"
    )

    # Editing the plan by hand has to keep the same promise, not just loading it.
    set_meal = js_block(html, "function setMeal(date, slot, id, extra){")
    assert "if (idOf(prev) !== id) dropLeftoversOf(date, slot);" in set_meal, (
        "changing a cooked meal leaves its leftovers behind"
    )
    unset = js_block(html, "function unsetMeal(date, slot){")
    assert "dropLeftoversOf(date, slot);" in unset, (
        "removing a cooked meal leaves its leftovers behind"
    )
    drop = js_block(html, "function dropLeftoversOf(date, slot){")
    # Only days it actually emptied. setMeal creates an empty day and then calls
    # this before writing into it, so tidying away every empty day would delete
    # the day out from under the caller.
    assert "if (hit && !Object.keys(day).length) delete S.plan[d];" in drop, (
        "dropping leftovers would delete a day it never touched"
    )


def test_the_catalogue_can_actually_support_leftovers(recipes):
    """Cook-once-eat-twice is only worth offering if the pool is deep.

    Measured against the real catalogue rather than assumed: a handful of batch
    recipes would mean the same two dinners every week.
    """
    batch = [r for r in recipes if "batch" in r.tags and "dinner" in r.slots]
    assert len(batch) >= 20, f"only {len(batch)} batch dinners, so leftovers would repeat"

    # A leftover is offered to the next day's lunch first, so the dish has to be
    # allowed in both slots for that to be possible at all.
    both = [r for r in batch if "lunch" in r.slots]
    assert len(both) >= 20, f"only {len(both)} batch dinners also work as lunch"

    # Batch cooking should be reserved for meals worth the effort.
    quick = [r for r in batch if r.total_min < 20]
    assert not quick, f"these are tagged batch but barely take any cooking: {[r.id for r in quick]}"


def test_meals_can_be_scheduled_on_some_days_only(tmp_path):
    """ "Breakfast three days a week" has to mean fill leaves the rest alone."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    eats = js_block(html, "function eats(date, slot){")
    assert 'if (slot === "snack") return true;' in eats, "snacks are on a schedule"
    assert "return days[dowIdx(date)] !== false;" in eats, "the schedule is not consulted"
    # A corrupt or half-written setting must not quietly stop meals being planned.
    assert "if (!Array.isArray(days)) return true;" in eats, (
        "a malformed schedule would leave every slot unplannable"
    )
    norm = js_block(html, "function normaliseSlotDays(saved){")
    assert "Array.isArray(days) && days.length === 7" in norm, (
        "a saved schedule of the wrong shape is trusted"
    )

    fill = js_block(html, "function fillRange(){")
    assert "const openMains = d => MAIN_SLOTS.filter(s => eats(d, s) && !takenAt(d, s));" in fill, (
        "fill still treats a meal you do not eat as an empty slot"
    )
    # The share of the day's calories has to be spread over the meals you do eat,
    # or the days you skip breakfast come in badly under target.
    assert "let share = open.reduce((n, s) => n + SLOT_SHARE[s], 0);" in fill, (
        "the calorie split is not computed from the slots actually being filled"
    )


def test_time_in_the_kitchen_can_be_capped(tmp_path):
    """A 175-minute pie is not a Tuesday."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    pool = js_block(html, "function fillPool(slot, date){")
    assert "const inTime = cap ? all.filter(r => (r.total_min || 0) <= cap) : all;" in pool, (
        "the time limit does not narrow the pool"
    )
    cap = js_block(html, "function timeCap(date){")
    assert "isWeekend(date) ? caps.weekend : caps.week" in cap, (
        "weeknights and weekends share one limit"
    )
    assert "return cap > 0 ? cap : 0;" in cap, "there is no way to ask for no limit"
    # A limit nothing can meet must not strand the slot.
    assert "return inTime.length ? inTime : all;" in pool, (
        "an impossible time limit would leave slots unfilled"
    )


def test_the_catalogue_leaves_room_under_a_time_limit(recipes):
    """Each offered limit has to leave a usable pool, or it is a trap."""
    mains = [r for r in recipes if "lunch" in r.slots or "dinner" in r.slots]
    for limit in (20, 30, 45, 60):
        fits = [r for r in mains if r.total_min <= limit]
        assert len(fits) >= 10, (
            f"only {len(fits)} of {len(mains)} lunches and dinners come in under "
            f"{limit} minutes, so that limit would repeat the same few meals"
        )


def test_fill_prefers_recipes_that_reuse_what_the_week_already_needs(tmp_path):
    """Less half-used food going off in the fridge, without costing nutrition."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    per = js_block(html, "function perishables(r){")
    assert 'FOODS[f].aisle !== "cupboard"' in per, (
        "staples are counted, so every recipe looks equally thrifty and the preference says nothing"
    )
    fill = js_block(html, "function fillRange(){")
    score = "const score = r => r.macros.protein + OVERLAP_WORTH * overlapWith(r, pantry);"
    assert score in fill, "overlap is not part of how a meal is chosen"
    grows = "      used.add(pick.id);\n      perishables(pick).forEach(f => pantry.add(f));"
    assert grows in fill, "the pantry never grows as the week is filled"
    # Seeded from the cooking only: a leftover buys nothing, so its ingredients
    # are not something the week still has to use up.
    assert "const pantry = pantryFrom(idsIn(a, b, true));" in fill, (
        "the pantry counts food that is never bought"
    )
    # Calories stay the first thing that matters.
    assert "Math.abs(x.macros.kcal - target) - Math.abs(y.macros.kcal - target)" in fill, (
        "the calorie ranking has gone, so overlap could drag days off target"
    )


def test_a_locked_meal_survives_being_cleared(tmp_path):
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    day_meals = js_block(html, "function clearDayMeals(date){")
    assert "if (isLocked(day[s])){ kept++; return; }" in day_meals, "Clear ignores locks"

    clear_range = js_block(html, "function clearRange(){")
    assert "const r = clearDayMeals(d);" in clear_range, (
        "clearing a range bypasses the per-day clear, so locks are lost"
    )
    # Clearing nothing because everything is locked has to say so, or the button
    # reads as broken.
    assert "Nothing cleared: all ${kept} planned meals are locked" in clear_range, (
        "a clear that removes nothing gives no feedback"
    )

    toggle = js_block(html, "function toggleLock(date, slot){")
    assert "if (!id) return;" in toggle, "an empty slot can be locked"
    lock = js_block(html, "function setMeal(date, slot, id, extra){")
    assert "if (isLocked(prev)) meta.lock = 1;" in lock, (
        "choosing a different meal for a locked slot silently unlocks it"
    )
    for hook in ("[data-lock]", "[data-fillset]", "[data-slotday]", "[data-maxmin]"):
        assert hook in html, f"{hook} is not in the click selector"
    # Off is data-leftovers="", which is falsy, so a truthiness check would make
    # that button silently do nothing.
    assert 'if ("leftovers" in d){ S.leftovers = !!d.leftovers;' in html, (
        "the leftovers Off button is dead"
    )


def test_a_pinned_meal_is_used_instead_of_being_chosen(tmp_path):
    """Pinning a meal has to short-circuit the picker, not merely bias it.

    The whole point of "breakfast is always yoghurt and fruit" is that fill
    stops deciding. The scope and the time limit are deliberately not consulted
    for a pinned slot: they exist to narrow a search, and there is no search.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    fill = js_block(html, "function fillRange(){")
    assert "let pick = usualFor(slot);\n      if (!pick){" in fill, (
        "fill does not check for a pinned meal before choosing one"
    )
    # The pinned meal still has to be paid for out of the day's calories, or the
    # rest of the day is planned as though breakfast were free.
    tail = "budget = Math.max(0, budget - pick.macros.kcal);"
    assert tail in fill, "a pinned meal is not charged to the day's calorie budget"
    assert fill.index("let pick = usualFor(slot);") < fill.index(tail), (
        "the pin is applied after the budget is spent"
    )


def test_a_pinned_id_is_checked_against_the_catalogue(tmp_path):
    """A pinned id goes stale exactly like a planned one.

    Recipes get renamed and removed. A pin left pointing at a dead id must fall
    back to choosing, not stop that slot being planned at all -- a silently
    unfillable breakfast is far worse than an unwanted one.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    usual = js_block(html, "function usualFor(slot){")
    assert "return r && r.slots.includes(slot) ? r : null;" in usual, (
        "a pinned id is trusted without checking it still serves that slot"
    )
    assert "const r = id ? BY_ID[id] : null;" in usual, "a pinned id is not resolved"
    # Defaults have to be merged on load or an older save has no usual at all.
    merged = "S.usual = Object.assign({ breakfast: null, lunch: null, dinner: null },"
    assert merged in html, "a saved plan from before pinning would load without usual"


def test_leftovers_do_not_steal_a_pinned_slot(tmp_path):
    """Two features both want tomorrow's lunch; the explicit one has to win.

    Leftovers fill the next day's lunch automatically. If that lunch is pinned,
    the pin was a decision the user typed in and the leftover is a convenience,
    so the leftover must look elsewhere.
    """
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    plan = js_block(html, "function planLeftovers(date, last, used){")
    guard = "!takenAt(next, s) && !usualFor(s)"
    assert guard in plan, "a leftover can overwrite a meal you pinned"


def test_every_main_slot_has_something_worth_pinning(tmp_path):
    """The control is only honest if the catalogue can fill it.

    A dropdown offering two breakfasts would make pinning a nuisance rather
    than a shortcut, and no amount of source checking would reveal that.
    """
    recipes = payload()["recipes"]
    for slot in MAIN_SLOTS:
        options = [r for r in recipes if slot in r["slots"]]
        assert len(options) >= 20, f"only {len(options)} recipes can be pinned to {slot}"
        # Pinning the same thing daily should not wreck the day's calories.
        modest = [r for r in options if r["macros"]["kcal"] <= 600]
        assert modest, f"every {slot} option would eat the whole calorie goal"


def test_the_fill_settings_button_says_what_it_opens(tmp_path):
    """ "How fill works" described the sheet's contents, not its purpose."""
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert "How fill works" not in html, "the old settings label is still shown"
    assert "Fill settings &middot; ${esc(fillSummary())}" in html, (
        "the plan bar no longer labels the settings button"
    )
    assert "<h1>Fill settings</h1>" in html, "the settings sheet has no title"
    # The pin control needs a change hook; it is a select, not a button.
    assert "S.usual[ds.usual] = e.target.value || null;" in html, (
        "choosing a usual meal does nothing"
    )
