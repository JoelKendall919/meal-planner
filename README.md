# Meal Planner

A catalogue of 197 recipes with a calendar planner and editable shopping lists,
built as a single offline-capable web page.

**Live site:** https://joelkendall919.github.io/meal-planner/

Pick meals for any day of the week and the shopping list builds itself, merging
ingredients you would buy as one product — red and yellow peppers become one
entry, and chicken thigh spread across three meals becomes "3 thighs".

## Portions, and why they do not reach the shopping list

A planned slot is always **one portion**. The portions stepper on a recipe is a
cooking aid: it scales the ingredient quantities so you can cook two at once and
take the second to work, but it deliberately does not feed into the shopping
list. The list is built from the plan alone, so plan a meal on both days you eat
it and the ingredients are counted twice. Were the stepper to scale the list as
well, cooking two and planning two would buy four portions' worth.

## Reading the colours

Colour carries two separate meanings, and they are kept on separate axes:

- **Which macro** — calories, protein, fat and carbs each have a fixed colour
  (`k-*` classes), so a figure is recognisable before you read its label.
- **How you are doing** — `s-good`, `s-warn` and `s-bad` score a figure against
  its goal. Calories, fat and carbs are *budgets*: green with room left, amber
  as they fill, red once exceeded. Protein is a *target* and scores the opposite
  way, because a day with barely any protein is not a green day.

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
| `data/foods.json` | 236 foods: nutrition per 100 g, shopping group, pack size, aisle |
| `data/recipes-*.json` | The recipe catalogue: 35 breakfasts, 61 lunches, 61 dinners, 40 snacks |
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
works fully offline. Three tabs — Plan, Recipes and Shopping — with the week and
the ticked shopping list stored in `localStorage`.

### Putting it on a phone home screen

Open https://joelkendall919.github.io/meal-planner/ in Chrome on Android, then
**⋮ → Add to Home screen** (on iOS, Safari's Share → Add to Home Screen). It
installs as a standalone app with its own icon and no browser chrome.

A service worker caches the app on first visit, so it opens instantly and works
in the shop with no signal. Each visit still fetches the current page first and
only falls back to the cache when offline, so **changes pushed to this repository
appear the next time the app is opened** — there is nothing to reinstall.

The cache is named after a hash of the built page, the worker and the manifest.
An unchanged deploy leaves the cache alone; any change retires it and the app
reloads itself onto the new version. `tests/test_pwa.py` covers both.

### Changing the icon

Edit `assets/icon.svg`, then regenerate the PNGs and commit them:

```sh
.venv/bin/python scripts/mkicons.py
```

The PNGs are committed so CI never needs a browser.

### Verifying the service worker by hand

Headless Chrome will not exit while a service worker is active, so
`scripts/probe_server.py` serves `dist/` and logs whatever the page reports to
`/probe?msg=...`. Start it, point a browser at it, and read `/tmp/probe.log`.

The shopping logic exists twice, in Python and JavaScript, because the app has to
recalculate as you tap. `tests/test_shopping_parity.py` runs both over randomised
selections and the whole catalogue, so the two cannot drift apart.

## Privacy

This repository is public so that GitHub Pages can serve it on a free plan.
Personal measurements are deliberately excluded: `private/` and any `.xlsx` files
are ignored by Git.

## Goals have to be reachable

Daily goals default to 1750 kcal, 150 g protein, 50 g fat, 160 g carbs, and the
app lets you change them. The defaults are not chosen by feel: an earlier
version shipped a 180 g protein goal inherited from a hand-built week, and no
combination of the catalogue at the time could reach it inside 1750 kcal — the
best possible day was 168 g, in 1 of 14,159 combinations. Every day would have
read as a failure.

`test_targets_are_achievable_from_the_catalogue` now brute-forces every
breakfast/lunch/dinner combination, allows for one snack, and fails if the
shipped goals are met by fewer than 5% of possible days.

Snacks exist for this reason. They are a protein top-up rather than a fourth
meal: "fill empty slots" plans the three main meals against the calorie goal,
then adds a snack only when the day is short on protein and has calories spare.
Filling a month currently averages 1700 kcal and 145 g protein per day, with no
day going over the calorie goal.
