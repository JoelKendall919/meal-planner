# Meal Planner

A catalogue of 182 everyday UK recipes with a calendar planner and editable
shopping lists, built as a single offline-capable web page.

**Live site:** https://joelkendall919.github.io/meal-planner/

Pick meals for any day of the week and the shopping list builds itself, merging
ingredients you would buy as one product — red and yellow peppers become one
entry, and chicken thigh spread across three meals becomes "3 thighs".

A list does not have to come from the plan: **Blank list** starts an empty one
you fill in yourself, and it claims no dates because there is no week behind it.
**Clear** empties a list without deleting it, so you can keep adding to the same
list. Both ask before throwing away anything you would miss.

## Portions, and why they do not reach the shopping list

A planned slot is always **one portion**. The portions stepper on a recipe is a
cooking aid: it multiplies the quantities written into each ingredient line — so
three portions of "1/2 tin chopped tomatoes" reads "1 1/2 tin", not "3 x 1/2
tin" — alongside the gram weight beside it. A line with no stated number ("a
knob of butter") keeps its wording, because there is nothing there to multiply
and its gram weight already scales.

The stepper deliberately does not feed into the shopping list. The list is built
from the plan alone, so plan a meal on both days you eat it and the ingredients
are counted twice. Were the stepper to scale the list as well, cooking two and
planning two would buy four portions' worth.

## Finding a recipe

Three controls, deliberately shaped differently because they are used at
different rates:

- **Meal** is buttons, each in its own colour. It is the filter you change
  constantly, so it is worth the space and is readable without being read.
- **Type** is a dropdown of the 21 categories the catalogue was planned under,
  wording and all. It offers only the categories that exist within the meal you
  have chosen, so picking Breakfast does not leave "Roasts" on the list; a type
  that stops applying is cleared rather than left selected over an empty result.
- **Filter** holds only **Vegetarian**, **Light** and **High protein**, and
  takes any number of them at once. Each one narrows further, so Vegetarian and
  High protein together means both rather than either. Recipes carry a dozen
  other authored tags, which stay searchable and still show on a recipe, but a
  filter list that long is a menu to read rather than a control to use.

## The plan, and what it does not tell you

The macro dashboard belongs to the **day** view alone. Over a week or a month it
could only show an average, which reads as a verdict on a period you are still
halfway through planning. Scoring a day is the Nutrients tab's job, which is
also the only place figures are graded green, amber and red — the plan states
what you are eating and leaves it at that.

Each day in the week view carries its own clear button, and **Copy yesterday /
last week / last month** duplicates the previous period onto the one on screen.
Copying is additive: a day the source left empty is skipped rather than wiped,
and anything genuinely being replaced is confirmed first.

## Reading the colours

Colour carries two separate meanings, and they are kept on separate axes:

- **Which macro** — calories, protein, fat and carbs each have a fixed colour
  (`k-*` classes), so a figure is recognisable before you read its label.
- **How you are doing** — `s-good`, `s-warn` and `s-bad` score a figure against
  its goal. Calories, fat and carbs are *budgets*: green with room left, amber
  as they fill, red once exceeded. Protein is a *target* and scores the opposite
  way, because a day with barely any protein is not a green day.

## A cookbook, with the diet as a lens over it

This started as a cutting plan and the schema showed it: a recipe had to clear a
protein floor and sit inside a calorie band *to exist at all*. That encoded a
judgement as if it were a fact. An apple was not a valid snack, because 0.3 g of
protein failed the gate, and beans on toast had to be written out twice to appear
at both breakfast and lunch.

The rules now separate the two:

- **Recipe files hold facts.** Ingredients, weights, method, which meals it suits.
- **Calorie ranges are plausibility checks, not targets.** `PLAUSIBLE_KCAL` exists
  to catch a gram-weight slip — a 4000 kcal sandwich is a typo, not a preference.
  It no longer decides whether a recipe deserves to exist.
- **Diet fitness is derived and filterable.** `high-protein`, `light` and
  `protein-snack` are computed from the numbers, so the same catalogue serves a
  cut and an ordinary Tuesday.

A recipe carries a list of `slots`, so beans on toast is written once and appears
under both. 182 recipes fill 278 meal places, which is why lunch went from 61
options to 97 without anyone writing 36 more recipes.

## Why "fill empty slots" has a scope

Opening the catalogue up has a cost worth stating plainly, because it is not
obvious and it nearly shipped unnoticed. `fillRange` optimises for calories and
only uses protein to break ties. Let it draw from everything — cereal, sandwiches,
crumble — and it will hit 1750 kcal with the protein far short. Measured over a
planned week in the browser, filling from the whole catalogue averages **102 g of
protein**; filling from the high-protein scope averages **125 g for the same
calories**.

So the scope is load-bearing rather than a convenience. Across every calorie-legal
day the catalogue can produce, 150 g of protein is reachable on 0.5% of them
unscoped and 11.7% scoped. The default goal is 140 g for the same reason: it is
1.47 g per kg of a 95 kg goal weight and lands on about a third of scoped days, so
it reads as demanding rather than impossible.

Two tests hold this line. One checks the goal is *achievable* under the scope; the
other checks a **median** day, because an achievability test is a ceiling and will
keep passing while typical days quietly rot beneath it.

## What "fill empty slots" knows about your week

Filling a week used to mean 28 separate cooks, whatever else was going on that
day. Four settings, behind the **How fill works** button, make it fit a real week
instead. Measured over 40 filled weeks each, counting only time spent actually
cooking:

| Settings | Cooks | Cooking | Shopping lines | kcal | Protein |
|---|---|---|---|---|---|
| None of the below | 28.0 | 383 min | 39.5 | 1695 | 102 g |
| Leftovers | 25.4 | **334 min** | 36.4 | 1693 | 103 g |
| + 30 min weeknights | 26.4 | **314 min** | 36.7 | 1693 | 104 g |
| + breakfast 3 days a week | 22.4 | 334 min | 37.2 | 1699 | **114 g** |

**Leftovers** is the one that pays. A dish tagged `batch` makes more than one
serving, so the next day's lunch can claim the second portion — about an hour a
week less at the stove. The serving counts towards what you *eat* and deliberately
not towards what you *buy*, which is the whole correctness problem in one line:
`idsIn` takes a `cookedOnly` flag, and the shopping list passes `true`. Without
it, cooking once would have you buying twice.

That also creates a new way for the plan to lie. A leftover whose source meal has
been deleted still resolves to a real recipe, so nothing *looks* wrong — but it is
food you never cook and never buy. Orphans are dropped in three places: on load,
when a source dish changes, and when one is removed.

**A time limit** on weeknights is honest about what it costs. Only 5 of 44 batch
dishes come in under 30 minutes, so capping weeknights starves the very feature
that saves you the most time: leftovers fall from 2.6 a week to 1.45. The two
settings genuinely pull against each other and the app should not pretend
otherwise — under a cap, big cooks can only land at the weekend.

**Which days you eat which meals** needs no calorie arithmetic of its own: the
share each slot takes is normalised over the slots you actually eat, so dropping
breakfast redistributes its calories rather than losing them. The day still lands
on target, and protein *rises*, because the calories move to main meals.

**Ingredient overlap** was nearly a feature that did nothing. Preferring a recipe
that reuses something the week already needs only matters among meals that fit the
day equally well, and the first attempt moved the weekly shop by 0.6 of a line —
noise. Measuring properly showed the shortlist width, not the calorie window, was
the binding constraint; retuning the weight from 1.5 to 5 takes a week from 43.9
distinct perishables to 41.7 for one gram of protein a day.

A fifth idea was built, measured and **removed**: steering dinner towards batch
dishes when tomorrow had a slot free. Across 60 weeks a setting it made no
difference at any weight worth having (2.5 leftovers either way; forcing it to 3.0
cost 14 minutes and variety), because the choice is already pinned by the calorie
target before preference gets a say. A knob that changes nothing is worse than no
knob.

## Why this is a repository and not a document

Every calorie and protein figure is **computed from raw ingredient weights**,
never estimated. An early draft overstated protein by about 46 g a day because
recipes were eyeballed. Later, a batch of recipes arrived with 14 of 25 labelled
"high-protein" that were nowhere near the threshold.

So nothing descriptive is trusted if it can be derived instead. Macros are
computed from `data/foods.json`, and the `high-protein`, `quick`, `light` and
`protein-snack` tags are recalculated at load time rather than read from the
recipe files. The test suite
fails if a tag, a macro figure, or an ingredient key disagrees with the data, and
the tests gate deployment.

## Layout

| Path | Purpose |
| --- | --- |
| `data/foods.json` | 367 foods: nutrition per 100 g, shopping group, pack size, aisle |
| `data/recipes/*.json` | The catalogue, one file per category: 182 recipes filling 45 breakfast, 97 lunch, 91 dinner and 45 snack places |
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

Add an entry to the matching file in `data/recipes/`, then:

```sh
.venv/bin/python scripts/validate_recipes.py data/recipes/curries.json
make test
```

Rules the tests enforce:

- Every `food` key must exist in `data/foods.json`. Add new foods to
  `scripts/build_foods.py` and regenerate.
- **Never write `kcal`, `protein` or `macros` into a recipe file.** They are derived.
- Do not set `high-protein`, `quick`, `light` or `protein-snack` by hand; all
  four are recalculated from the numbers at load time.
- Give a recipe every `slots` value it genuinely suits. A jacket potato is lunch
  *and* dinner, and saying so once beats writing it out twice.
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
