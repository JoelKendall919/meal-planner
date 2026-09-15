"""Break one thing at a time and check the suite notices.

A test that cannot fail is worse than no test, so every assertion guarding the
UI tweaks is checked here against a mutation that should break it. Reported as
DEAD (the suite caught it) or ALIVE (the test is vacuous and needs tightening).

Run with the project interpreter:  .venv/bin/python scripts/mutation_check.py
"""

import subprocess
import sys
from pathlib import Path

PY_BIN = ".venv/bin/python"
APP = Path("src/mealplanner/templates/app.html")


def run(test: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY_BIN, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "tests/test_app.py", "-k", test],
        capture_output=True,
        text=True,
    )


CASES = [
    (
        "Filter reverts to single-choice",
        "f.tags = f.tags.includes(tag) ? f.tags.filter(t => t !== tag) : f.tags.concat(tag);",
        "f.tags = [tag];",
        "test_the_filter_tags_multi_select_and_narrow",
    ),
    (
        "matching becomes OR instead of AND",
        "if (!f.tags.every(t => r.tags.includes(t))) return false;",
        "if (f.tags.length && !f.tags.some(t => r.tags.includes(t))) return false;",
        "test_the_filter_tags_multi_select_and_narrow",
    ),
    (
        "filter tags dropped from the click selector",
        "[data-scope],[data-ftag]",
        "[data-scope]",
        "test_the_filter_tags_multi_select_and_narrow",
    ),
    (
        "ftag buttons lose their hook",
        'data-ftag="${ns}|${id}"',
        'data-xftag="${ns}|${id}"',
        "test_the_filter_tags_multi_select_and_narrow",
    ),
    (
        "Type stops being wired to change",
        "const ns = ds.fcatsel;",
        "const ns = null;",
        "test_type_is_a_dropdown",
    ),
    (
        "scope buttons revert to the unstyled .tag badge",
        '<button class="chip${S.scope === sc.id ? " on" : ""}"',
        '<button class="tag${S.scope === sc.id ? " on" : ""}"',
        "test_every_toggleable_control_has_a_visible_selected_state",
    ),
    (
        "the .chip.on rule is deleted",
        ".chip.on{background:var(--accent);color:#fff;border-color:var(--accent);font-weight:600}",
        "",
        "test_every_toggleable_control_has_a_visible_selected_state",
    ),
    (
        "scope handler uses a truthiness check, losing 'Anything'",
        'if ("scope" in d){ S.scope = d.scope || null;',
        "if (d.scope){ S.scope = d.scope || null;",
        "test_the_fill_scope_buttons_are_live_and_honoured",
    ),
    (
        "fillPool ignores the chosen scope",
        "const scoped = inTime.filter(r => r.tags.includes(S.scope));",
        "const scoped = inTime.filter(r => true);",
        "test_the_fill_scope_buttons_are_live_and_honoured",
    ),
    (
        "fill refuses again whenever every main slot is taken",
        "if (!empty && !openSnacks){",
        "if (!empty){",
        "test_fill_reaches_the_protein_top_up_on_a_fully_planned_day",
    ),
    (
        "the top-up goes back to being unreachable on a planned day",
        "      topUpProtein(date, used);\n      planLeftovers(date, b, used);\n      return;",
        "      return;",
        "test_fill_reaches_the_protein_top_up_on_a_fully_planned_day",
    ),
    (
        "the toast count goes back to being assumed",
        "const added = planned() - before;",
        "const added = empty;",
        "test_fill_reaches_the_protein_top_up_on_a_fully_planned_day",
    ),
    (
        "the load path stops pruning stale ids",
        "pruned = prunePlan(S.plan);",
        "pruned = 0;",
        "test_a_saved_plan_is_pruned_of_recipes_that_no_longer_exist",
    ),
    (
        "the pruned plan is never written back",
        "if (pruned) save();",
        "if (false) save();",
        "test_a_saved_plan_is_pruned_of_recipes_that_no_longer_exist",
    ),
    (
        "pruning leaves emptied days behind",
        "    if (!Object.keys(plan[date]).length) delete plan[date];",
        "",
        "test_a_saved_plan_is_pruned_of_recipes_that_no_longer_exist",
    ),
    (
        "clearing the list no longer asks first",
        'if (!confirm(`Remove all ${n} item${n === 1 ? "" : "s"} from the list?`)) return;',
        "",
        "test_the_shopping_list_can_be_emptied_and_started_blank",
    ),
    (
        "a blank list silently discards one with items on it",
        "&& !confirm(`Replace the current list?",
        "&& false && !confirm(`Replace the current list?",
        "test_the_shopping_list_can_be_emptied_and_started_blank",
    ),
    (
        "a blank list goes back to claiming today",
        "from: null, to: null",
        "from: todayISO(), to: todayISO()",
        "test_the_shopping_list_can_be_emptied_and_started_blank",
    ),
    (
        "an emptied list keeps claiming its old days",
        "S.shopping.from = null;",
        "",
        "test_the_shopping_list_can_be_emptied_and_started_blank",
    ),
    (
        "the blank option is dropped from the empty screen",
        'data-blank="1" style="flex:1"',
        'data-xblank="1" style="flex:1"',
        "test_the_shopping_list_can_be_emptied_and_started_blank",
    ),
    (
        "fillPool drops its empty-pool fallback",
        "if (scoped.length) return scoped;\n  if (inTime.length) return inTime;",
        "return scoped;\n  if (inTime.length) return inTime;",
        "test_the_fill_scope_buttons_are_live_and_honoured",
    ),
    (
        "leftovers land on the shopping list",
        "if (cookedOnly && isLeftover(day[s])) return;",
        "if (false && isLeftover(day[s])) return;",
        "test_leftovers_are_eaten_but_never_bought",
    ),
    (
        "the shopping list stops asking for the cooking only",
        "const ids = idsIn(from, to, true);",
        "const ids = idsIn(from, to);",
        "test_leftovers_are_eaten_but_never_bought",
    ),
    (
        "nutrition starts skipping leftovers",
        "  return SLOTS.map(s => mealAt(date, s)).filter(Boolean);",
        "  return SLOTS.map(s => isLeftover(slotAt(date, s)) ? null : mealAt(date, s))"
        ".filter(Boolean);",
        "test_leftovers_are_eaten_but_never_bought",
    ),
    (
        "an orphaned leftover survives the load",
        "if (isLeftover(v) && !cooks(plan, v.from, idOf(v))){ delete day[slot]; dropped++; }",
        "if (false){ delete day[slot]; dropped++; }",
        "test_a_leftover_cannot_outlive_the_meal_it_came_from",
    ),
    (
        "a leftover of a leftover counts as cooked",
        "return !!v && idOf(v) === id && !isLeftover(v);",
        "return !!v && idOf(v) === id;",
        "test_a_leftover_cannot_outlive_the_meal_it_came_from",
    ),
    (
        "changing a cooked meal leaves its leftovers behind",
        "if (idOf(prev) !== id) dropLeftoversOf(date, slot);",
        "if (false) dropLeftoversOf(date, slot);",
        "test_a_leftover_cannot_outlive_the_meal_it_came_from",
    ),
    (
        "dropping leftovers deletes days it never touched",
        "if (hit && !Object.keys(day).length) delete S.plan[d];",
        "if (!Object.keys(day).length) delete S.plan[d];",
        "test_a_leftover_cannot_outlive_the_meal_it_came_from",
    ),
    (
        "the meal schedule is ignored",
        "  return days[dowIdx(date)] !== false;",
        "  return true;",
        "test_meals_can_be_scheduled_on_some_days_only",
    ),
    (
        "a malformed schedule is trusted",
        "  if (!Array.isArray(days)) return true;",
        "  if (false) return true;",
        "test_meals_can_be_scheduled_on_some_days_only",
    ),
    (
        "fill treats an unscheduled meal as a gap",
        "const openMains = d => MAIN_SLOTS.filter(s => eats(d, s) && !takenAt(d, s));",
        "const openMains = d => MAIN_SLOTS.filter(s => !takenAt(d, s));",
        "test_meals_can_be_scheduled_on_some_days_only",
    ),
    (
        "the time limit stops narrowing the pool",
        "const inTime = cap ? all.filter(r => (r.total_min || 0) <= cap) : all;",
        "const inTime = all;",
        "test_time_in_the_kitchen_can_be_capped",
    ),
    (
        "weeknights and weekends share one limit",
        "const cap = isWeekend(date) ? caps.weekend : caps.week;",
        "const cap = caps.week;",
        "test_time_in_the_kitchen_can_be_capped",
    ),
    (
        "an impossible time limit strands the slot",
        "  if (!S.scope) return inTime.length ? inTime : all;",
        "  if (!S.scope) return inTime;",
        "test_time_in_the_kitchen_can_be_capped",
    ),
    (
        "cupboard staples count towards ingredient overlap",
        '.filter(f => FOODS[f] && FOODS[f].aisle !== "cupboard");',
        ".filter(f => FOODS[f]);",
        "test_fill_prefers_recipes_that_reuse_what_the_week_already_needs",
    ),
    (
        "overlap drops out of how a meal is chosen",
        "const score = r => r.macros.protein + OVERLAP_WORTH * overlapWith(r, pantry);",
        "const score = r => r.macros.protein;",
        "test_fill_prefers_recipes_that_reuse_what_the_week_already_needs",
    ),
    (
        "the pantry never grows as the week fills",
        "      used.add(pick.id);\n      perishables(pick).forEach(f => pantry.add(f));",
        "      used.add(pick.id);",
        "test_fill_prefers_recipes_that_reuse_what_the_week_already_needs",
    ),
    (
        "Clear ignores locks",
        "if (isLocked(day[s])){ kept++; return; }",
        "if (false){ kept++; return; }",
        "test_a_locked_meal_survives_being_cleared",
    ),
    (
        "clearing a range bypasses the per-day clear",
        "    const r = clearDayMeals(d);",
        "    const r = { removed: 0, kept: 0 }; delete S.plan[d];",
        "test_a_locked_meal_survives_being_cleared",
    ),
    (
        "swapping a locked meal silently unlocks it",
        "if (isLocked(prev)) meta.lock = 1;",
        "if (false) meta.lock = 1;",
        "test_a_locked_meal_survives_being_cleared",
    ),
    (
        "the leftovers Off button goes dead",
        'if ("leftovers" in d){ S.leftovers = !!d.leftovers;',
        "if (d.leftovers){ S.leftovers = !!d.leftovers;",
        "test_a_locked_meal_survives_being_cleared",
    ),
    (
        "the lock control loses its click hook",
        "[data-lock],[data-fillset],[data-slotday],[data-maxmin],[data-leftovers],",
        "[data-fillset],[data-slotday],[data-maxmin],[data-leftovers],",
        "test_a_locked_meal_survives_being_cleared",
    ),
    (
        "a pinned meal is ignored and fill chooses anyway",
        "let pick = usualFor(slot);\n      if (!pick){",
        "let pick = null;\n      if (!pick){",
        "test_a_pinned_meal_is_used_instead_of_being_chosen",
    ),
    (
        "a pinned meal is not charged to the day's calories",
        "budget = Math.max(0, budget - pick.macros.kcal);",
        "budget = Math.max(0, budget);",
        "test_a_pinned_meal_is_used_instead_of_being_chosen",
    ),
    (
        "a stale pin is trusted and strands the slot",
        "return r && servesSlot(r, slot) ? r : null;",
        "return r || null;",
        "test_a_pinned_id_is_checked_against_the_catalogue",
    ),
    (
        "an older save loads with no usual meals at all",
        "S.usual = Object.assign({ breakfast: null, lunch: null, dinner: null },",
        "S.usual = Object.assign({},",
        "test_a_pinned_id_is_checked_against_the_catalogue",
    ),
    (
        "a leftover overwrites the lunch you pinned",
        "!takenAt(next, s) && !usualFor(s)",
        "!takenAt(next, s)",
        "test_leftovers_do_not_steal_a_pinned_slot",
    ),
    (
        "choosing a usual meal does nothing",
        "S.usual[pinned] = d.set;",
        "S.usual[pinned] = S.usual[pinned];",
        "test_the_fill_settings_button_says_what_it_opens",
    ),
    (
        "the pin picker plans a day's meal instead of a standing choice",
        "const pinned = sheet.dataset.pinslot;",
        "const pinned = null;",
        "test_the_fill_settings_button_says_what_it_opens",
    ),
    (
        "the pin picker forgets which slot it is for",
        "sheet.dataset.pinslot = slot;",
        "sheet.dataset.slotpin = slot;",
        "test_the_fill_settings_button_says_what_it_opens",
    ),
    (
        "the pin sheet marks itself with a live click hook again",
        "sheet.dataset.pinslot = slot;",
        "sheet.dataset.usual = slot;",
        "test_no_sheet_marker_doubles_as_a_click_hook",
    ),
    (
        "a pin cannot be taken off again",
        "if (d.unusual){\n    S.usual[d.unusual] = null;",
        "if (false){\n    S.usual[d.unusual] = null;",
        "test_the_fill_settings_button_says_what_it_opens",
    ),
    (
        "a brunch day asks for breakfast and lunch on top of the brunch",
        'if ((slot === "breakfast" || slot === "lunch") && isBrunchDay(date)) return false;\n  const days',
        'const days',
        "test_a_brunch_day_replaces_breakfast_and_lunch",
    ),
    (
        "brunch is never actually eaten",
        'if (slot === "brunch") return isBrunchDay(date);\n  if ((slot === "breakfast"',
        'if (slot === "brunch") return false;\n  if ((slot === "breakfast"',
        "test_a_brunch_day_replaces_breakfast_and_lunch",
    ),
    (
        "switching brunch on hides a breakfast you already planned",
        '    if (takenAt(date, slot)) return true;\n    if (slot === "brunch") return isBrunchDay(date);',
        '    if (slot === "brunch") return isBrunchDay(date);',
        "test_turning_brunch_on_does_not_delete_the_meals_it_replaces",
    ),
    (
        "brunch defaults on, silently removing two meals from every old plan",
        "(brunch ? NO_DAYS() : FULL_WEEK())",
        "FULL_WEEK()",
        "test_brunch_is_off_unless_you_ask_for_it",
    ),
    (
        "a saved brunch day is read with the lenient default",
        "days.map(v => (brunch ? v === true : v !== false))",
        "days.map(v => v !== false)",
        "test_brunch_is_off_unless_you_ask_for_it",
    ),
    (
        "brunch draws on every breakfast and lunch, roasts included",
        "BRUNCH_CATEGORIES.indexOf(r.category) !== -1",
        "true",
        "test_brunch_is_made_of_things_you_would_eat_at_eleven",
    ),
    (
        "the snack reserve is sized for a day with a brunch in it",
        "const typical = DAILY_SLOTS.reduce((n, slot) =>",
        "const typical = MAIN_SLOTS.reduce((n, slot) =>",
        "test_brunch_does_not_skew_what_a_normal_day_looks_like",
    ),
    (
        "the Recipes page offers a Brunch filter for a tag no recipe has",
        '${row("Meal", `<div class="chips">${CATALOGUE_SLOTS.map(s =>',
        '${row("Meal", `<div class="chips">${SLOTS.map(s =>',
        "test_the_recipes_page_does_not_offer_a_brunch_filter",
    ),
    (
        "a filter change rebuilds the sheet and kills the keyboard",
        'if (ns === "pick") refreshPicker(true);\n  else render();',
        'if (ns === "pick") reopenPicker();\n  else render();',
        "test_the_picker_never_redraws_the_box_you_are_typing_into",
    ),
    (
        "typing replaces the dropdown mid-word",
        "    refreshPicker(false);",
        "    refreshPicker(true);",
        "test_the_picker_never_redraws_the_box_you_are_typing_into",
    ),
    (
        "the search box is dragged back inside the redrawn region",
        '<div data-facets="${ns}">${facetRows(f, ns)}</div>',
        '<div data-facets="${ns}"><input data-search="${ns}">${facetRows(f, ns)}</div>',
        "test_the_picker_never_redraws_the_box_you_are_typing_into",
    ),
    (
        "the refresh forgets to update the recipe list",
        "  const list = sheet && sheet.querySelector(\".rlist\");",
        "  const list = sheet && sheet.querySelector(\".rlist-gone\");",
        "test_the_picker_never_redraws_the_box_you_are_typing_into",
    ),
    (
        "an unpinned slot goes back to saying something different",
        '                      : "None"}</button>',
        '                      : "Something different"}</button>',
        "test_the_pinned_meals_card_reads_as_a_list_of_choices",
    ),
    (
        "the pin label can push its button out of line again",
        ".facet.pin .flab{flex:0 0 68px;min-width:0;",
        ".facet.pin .flab{flex:0 0 68px;",
        "test_the_pinned_meals_card_reads_as_a_list_of_choices",
    ),
]


def main() -> int:
    # Prove the runner works before trusting a single result. This script once
    # reported a clean sweep purely because `python` resolved to an interpreter
    # with no pytest, so every run exited non-zero and looked like a catch.
    base = run("")
    if base.returncode != 0:
        print("baseline is not green -- results would be meaningless")
        print(base.stdout[-800:], base.stderr[-400:])
        return 2
    print("baseline:", base.stdout.strip().splitlines()[-1])

    orig = APP.read_text()
    alive = []
    try:
        for desc, find, repl, test in CASES:
            hits = orig.count(find)
            if hits != 1:
                print(f"SKIP      {desc} -- {hits} matches, target is ambiguous")
                alive.append(desc)
                continue
            APP.write_text(orig.replace(find, repl, 1))
            r = run(test)
            if r.returncode == 0:
                alive.append(desc)
            # Anything other than "tests ran, some failed" means the harness
            # broke rather than the test catching the mutation.
            note = "" if r.returncode in (0, 1) else f"  (rc={r.returncode}, harness error)"
            print(f"{'ALIVE   ' if r.returncode == 0 else 'DEAD    '}  {desc}{note}")
            if note:
                alive.append(desc)
    finally:
        APP.write_text(orig)

    print()
    print(f"{len(CASES) - len(alive)}/{len(CASES)} mutations caught")
    if alive:
        print("tests that failed to notice:", "; ".join(alive))
    return 1 if alive else 0


if __name__ == "__main__":
    sys.exit(main())
