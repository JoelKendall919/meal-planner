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
    assert "const pool = fillPool(slot);" in html, "fillRange does not draw from the scoped pool"
    for scope in ("high-protein", "light"):
        assert f'"{scope}"' in html, f"the {scope} scope is not offered"
    assert "data-scope" in html, "the scope has no control in the plan page"
    # "Anything" is data-scope="", so a truthiness test would silently ignore it.
    # Assert the guard itself, not the phrase: the comment beside it in app.html
    # contains the same words and was quietly satisfying this on its own.
    assert 'if ("scope" in d){' in html, "the reset-to-anything scope button is dead"
    # A scope that matched nothing must not leave the day unfilled.
    assert "scoped.length ? scoped : all" in html, "an empty scope has no fallback"


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


def test_type_and_filter_are_dropdowns(tmp_path):
    html = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert 'data-${hook}="${ns}"' in html, "the filter selects have no handler hook"
    assert "<select" in html, "the filters are not dropdowns"
    # Selects report on change; the delegated click handler cannot see them.
    assert "ds.fcatsel || ds.tagsel" in html, "the dropdowns are not wired to change"
    for dead in ("data-fcat=", "data-tag="):
        assert dead not in html, f"{dead} chips are still being rendered"


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
    assert "delete S.plan[date];" in clear, "clearDay does not clear the day"
    assert "[data-clearday]" in html, "the clear button is not in the click selector"


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
    # The copy has to be independent of its source.
    assert "Object.assign({}, S.plan[from])" in copy, "the copy aliases the original"
