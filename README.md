# Meal Planner

A catalogue of 75 recipes with a weekly planner and automatic shopping lists,
built as a single offline-capable web page.

**Live site:** https://joelkendall919.github.io/meal-planner/

Pick meals for any day of the week and the shopping list builds itself, merging
ingredients you would buy as one product — red and yellow peppers become one
entry, and chicken thigh spread across three meals becomes "3 thighs".

## Why this is a repository and not a document

Every calorie and protein figure is **computed from raw ingredient weights**,
never estimated. An early draft overstated protein by about 46 g a day because
recipes were eyeballed. Later, a batch of recipes arrived with 14 of 25 labelled
"high-protein" that were nowhere near the threshold.

So nothing descriptive is trusted if it can be derived instead. Macros are
computed from `data/foods.json`, and the `high-protein` and `quick` tags are
recalculated at load time rather than read from the recipe files. The test suite
fails if a tag, a macro figure, or an ingredient key disagrees with the data, and
the tests gate deployment.

## Layout

| Path | Purpose |
| --- | --- |
| `data/foods.json` | 143 foods: nutrition per 100 g, shopping group, pack size, aisle |
| `data/recipes-*.json` | The recipe catalogue, 25 per meal slot |
| `scripts/build_foods.py` | Generates `foods.json` — **edit this, not the JSON** |
| `scripts/validate_recipes.py` | Checks a recipe file before it is committed |
| `src/mealplanner/catalogue.py` | Loads foods and recipes, computes macros and derived tags |
| `src/mealplanner/shopping.py` | Turns selected recipes into a merged shopping list |
| `src/mealplanner/templates/shopping.js` | The same logic in JS, for the live app |
| `src/mealplanner/build.py` | Inlines the catalogue into a single-file site in `dist/` |
| `tests/` | Catalogue invariants, build guards, and JS/Python parity |

### Legacy

`content/legacy-meal-plan.md`, `src/mealplanner/nutrition.py`, `parse.py` and
`prices.py` are the original fixed seven-day plan with costings. The catalogue
replaced it, but it is kept so its figures stay verifiable —
`tests/test_legacy_plan.py` still checks it against the model.

## Getting started

```sh
make venv     # create .venv and install dependencies
make test     # run the test suite
make build    # build the site into dist/
make serve    # build and serve at http://localhost:8000
```

Run `make help` to list every target.

### In VS Code

Open the folder and accept the recommended extensions. The Python interpreter,
pytest integration, and Ruff formatting are preconfigured in `.vscode/`.

## Adding a recipe

Add an entry to the relevant `data/recipes-*.json`, then:

```sh
.venv/bin/python scripts/validate_recipes.py data/recipes-dinner.json
make test
```

Rules the tests enforce:

- Every `food` key must exist in `data/foods.json`. Add new foods to
  `scripts/build_foods.py` and regenerate.
- **Never write `kcal`, `protein` or `macros` into a recipe file.** They are derived.
- Do not set `high-protein` or `quick` tags by hand; they are recalculated.
- Credit a source by name. Leave `url` as `null` rather than guessing one, and
  write the method steps yourself — published recipe prose is copyrighted.

## The web app

`dist/index.html` is a single self-contained file with no external requests, so it
works fully offline and can be copied straight to a phone. Three tabs — Plan,
Recipes and Shopping — with the week and the ticked shopping list stored in
`localStorage`. It degrades gracefully if storage is blocked, which happens when a
downloaded file is opened from some Android file managers.

The shopping logic exists twice, in Python and JavaScript, because the app has to
recalculate as you tap. `tests/test_shopping_parity.py` runs both over randomised
selections and the whole catalogue, so the two cannot drift apart.

## Privacy

This repository is public so that GitHub Pages can serve it on a free plan.
Personal measurements are deliberately excluded: `private/` and any `.xlsx` files
are ignored by Git.
