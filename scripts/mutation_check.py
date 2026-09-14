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
        "const scoped = all.filter(r => r.tags.includes(S.scope));",
        "const scoped = all.filter(r => true);",
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
        "      topUpProtein(date, used);\n      return;",
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
        "fillPool drops its empty-pool fallback",
        "return scoped.length ? scoped : all;",
        "return scoped;",
        "test_the_fill_scope_buttons_are_live_and_honoured",
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
