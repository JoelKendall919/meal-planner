# Fitness Plan

A weekly meal and training plan, built as a static offline-capable web app.

The plan is built around roughly 1750 kcal a day with a high protein target, and
five training sessions a week (running, cycling, and dumbbell-only weights). It is
deliberately cardio-led, with one dedicated lifting day.

**Live site:** https://joelkendall919.github.io/fitness-plan/

## Why this is a repository and not a document

Every calorie and protein figure in the plan is **computed from raw ingredient
weights**, never estimated. An early draft overstated protein by about 46 g per day
because recipes were eyeballed. The nutrition model is now the single source of
truth, and the test suite fails if the published documents drift away from it.

The tests also gate deployment, so figures that disagree with the model cannot
reach the live site.

## Layout

| Path | Purpose |
| --- | --- |
| `content/meal-plan.md` | The meal plan: targets, week table, recipes, shopping lists |
| `content/training-plan.md` | The training plan |
| `src/fitnessplan/nutrition.py` | Nutrition model — foods, recipes, days. Source of truth for all figures |
| `src/fitnessplan/prices.py` | Estimated UK grocery prices and shelf lives |
| `src/fitnessplan/parse.py` | Parses the meal plan markdown into structured data |
| `src/fitnessplan/build.py` | Builds the static site into `dist/` |
| `src/fitnessplan/templates/app.html` | The web app shell; plan data is inlined at build time |
| `scripts/mkpdf.py` | Renders the documents to PDF via headless Chrome |
| `scripts/build_log.py` | Generates the weight and training log spreadsheet |
| `tests/` | Nutrition invariants and document-drift guards |

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
Build and test tasks are on <kbd>Cmd</kbd>+<kbd>Shift</kbd>+<kbd>B</kbd> and the
Test Explorer respectively.

## Changing the plan

Recipes live in `src/fitnessplan/nutrition.py`. **Do not hand-edit the figures in
the markdown.** After changing a recipe:

```sh
make nutrition   # review the recalculated figures
make test        # confirm the documents still agree with the model
```

If the tests report drift, update the figures in `content/meal-plan.md` to match
the model output, then rebuild.

### Known tolerance

The model rounds each meal before summing, while the documents were generated
from an unrounded sum. That produces a consistent difference of at most 1 kcal or
1 g of protein per day. Tests allow ±2; anything larger is a real error.

## The web app

`dist/index.html` is a single self-contained file with no external requests, so it
works fully offline. It has four tabs — Today, Week, Shopping, and My list — and
stores the working shopping list in `localStorage`. It degrades gracefully if
storage is unavailable, which happens when a downloaded file is opened from some
Android file managers.

## Privacy

This repository is public so that GitHub Pages can serve it on a free plan.
Personal measurements are deliberately excluded: `private/` and any `.xlsx` files
are ignored by Git. Keep logged weights out of `content/`.
