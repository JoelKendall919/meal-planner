"""The recipe catalogue: loading, validating, and costing recipes.

Recipes are stored as data (``data/recipes-*.json``) rather than prose, so that
macros are always computed from raw ingredient weights instead of being written
by hand. Nothing in this project states a calorie or protein figure that was not
derived here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# The three meals that make up a day, plus an optional snack. Snacks are a
# protein top-up rather than a fourth meal: the catalogue of main meals cannot
# reach a useful protein figure inside 1750 kcal on its own, so the planner adds
# a snack only when a day is short on protein and has calories to spare.
MAIN_SLOTS = ("breakfast", "lunch", "dinner")
SLOTS = (*MAIN_SLOTS, "snack")

# Tags that describe a measurable property are derived from the recipe data rather
# than trusted from the source file. Hand-written labels drift: an early batch
# tagged 14 recipes "high-protein" that were nowhere near the threshold.
PROTEIN_TAG_G = 30
QUICK_MINUTES = {"breakfast": 10, "lunch": 15, "dinner": 25, "snack": 10}

# A recipe is "light" if it fits the share of a 1750 kcal day that its slot would
# normally take. This used to be enforced as a gate, which made a bowl of soup or
# a bacon sandwich an illegal recipe. It is a label now, not a rule.
LIGHT_MAX = {"breakfast": 400, "lunch": 500, "dinner": 600, "snack": 150}

# Snacks that buy protein cheaply in calories. Also once a gate, which banned
# every ordinary snack: an apple could not exist in the catalogue.
SNACK_PROTEIN_PER_100KCAL = 8

DERIVED_TAGS = {"high-protein", "quick", "light", "protein-snack"}

# Controlled category vocabulary. Free-text tags grew an unusable long tail --
# "traybake", "risotto" and "weekend" each appeared on one or two recipes while
# the filter strip rendered every one of them as a chip. Categories are a closed
# set so that filtering still works at several hundred recipes.
CATEGORIES = {
    "cereal-and-cold",
    "toast-and-bakery",
    "eggs",
    "cooked-breakfast",
    "sandwiches",
    "jacket-potatoes",
    "soups",
    "salads",
    "bakery-and-picky",
    "british-classics",
    "roasts",
    "pasta-and-italian",
    "curries",
    "asian",
    "fish",
    "traybakes-and-quick",
    "fruit-and-veg",
    "dairy-and-protein",
    "bread-and-baked",
    "savoury-treats",
    "sweet-treats",
}

# Plausibility ranges, per slot. These exist only to catch a decimal-point slip
# or a gram weight entered as an ounce -- a recipe outside these is a data error,
# not a rich meal. They replace the old bands, which encoded a cutting diet and
# would have rejected fish and chips, any soup, and almost every normal snack.
PLAUSIBLE_KCAL = {
    "breakfast": (80, 1000),
    "lunch": (100, 1200),
    "dinner": (150, 1600),
    "snack": (20, 600),
}


class CatalogueError(RuntimeError):
    """Raised when recipe or food data is malformed."""


@dataclass(frozen=True)
class Food:
    key: str
    kcal: float
    protein: float
    fat: float
    group: str
    unit_g: float | None
    unit: str | None
    aisle: str


@dataclass(frozen=True)
class Ingredient:
    food: str
    grams: float
    display: str


@dataclass
class Recipe:
    id: str
    name: str
    slots: list[str]
    category: str
    source: dict
    servings: int
    ingredients: list[Ingredient]
    steps: list[str]
    cuisine: str = "other"
    tags: list[str] = field(default_factory=list)
    prep_min: int = 0
    cook_min: int = 0

    _foods: dict[str, Food] = field(default=None, repr=False, compare=False)

    @cached_property
    def macros(self) -> dict[str, float]:
        kcal = protein = fat = 0.0
        for item in self.ingredients:
            food = self._foods[item.food]
            kcal += food.kcal * item.grams / 100
            protein += food.protein * item.grams / 100
            fat += food.fat * item.grams / 100
        carbs = max((kcal - 4 * protein - 9 * fat) / 4, 0.0)
        return {
            "kcal": round(kcal),
            "protein": round(protein),
            "fat": round(fat),
            "carbs": round(carbs),
        }

    @property
    def total_min(self) -> int:
        return self.prep_min + self.cook_min

    def normalise_tags(self) -> None:
        """Replace derived tags with values computed from the recipe itself."""
        tags = {t for t in self.tags if t not in DERIVED_TAGS}
        macros = self.macros
        if macros["protein"] >= PROTEIN_TAG_G:
            tags.add("high-protein")
        # A recipe used for both lunch and dinner is judged against the most
        # generous of its slots: it only has to be quick or light somewhere.
        if self.total_min and self.total_min <= max(QUICK_MINUTES[s] for s in self.slots):
            tags.add("quick")
        if macros["kcal"] <= max(LIGHT_MAX[s] for s in self.slots):
            tags.add("light")
        if "snack" in self.slots and macros["kcal"]:
            density = macros["protein"] / macros["kcal"] * 100
            if density >= SNACK_PROTEIN_PER_100KCAL:
                tags.add("protein-snack")
        self.tags = sorted(tags)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slots": self.slots,
            "category": self.category,
            "cuisine": self.cuisine,
            "source": self.source,
            "servings": self.servings,
            "prep_min": self.prep_min,
            "cook_min": self.cook_min,
            "total_min": self.total_min,
            "tags": self.tags,
            "ingredients": [
                {"food": i.food, "grams": i.grams, "display": i.display} for i in self.ingredients
            ],
            "steps": self.steps,
            "macros": self.macros,
        }


def load_foods(path: Path | None = None) -> dict[str, Food]:
    path = path or DATA / "foods.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        key: Food(
            key=key,
            kcal=v["kcal"],
            protein=v["protein"],
            fat=v["fat"],
            group=v["group"],
            unit_g=v["unit_g"],
            unit=v["unit"],
            aisle=v["aisle"],
        )
        for key, v in raw.items()
    }


def load_recipes(
    foods: dict[str, Food] | None = None, data_dir: Path | None = None
) -> list[Recipe]:
    foods = foods or load_foods()
    data_dir = data_dir or DATA

    # Recipes live in data/recipes/*.json. The filenames are for humans only:
    # a recipe declares its own slots, so storage no longer dictates whether a
    # dish can be both a lunch and a dinner.
    recipe_dir = data_dir / "recipes"
    if not recipe_dir.is_dir():
        raise CatalogueError(f"missing recipe directory: {recipe_dir}")
    paths = sorted(recipe_dir.glob("*.json"))
    if not paths:
        raise CatalogueError(f"no recipe files in {recipe_dir}")

    recipes: list[Recipe] = []
    seen: set[str] = set()

    for path in paths:
        for raw in json.loads(path.read_text(encoding="utf-8")):
            rid = raw.get("id")
            if not rid:
                raise CatalogueError(f"{path.name}: a recipe has no id")
            if rid in seen:
                raise CatalogueError(f"duplicate recipe id: {rid}")
            seen.add(rid)

            stored = {"kcal", "protein", "fat", "carbs", "macros"} & set(raw)
            if stored:
                raise CatalogueError(
                    f"{rid}: stores {sorted(stored)}; macros are always derived from ingredients"
                )

            slots = raw.get("slots") or []
            if not slots:
                raise CatalogueError(f"{rid}: no slots")
            bad = [s for s in slots if s not in SLOTS]
            if bad:
                raise CatalogueError(f"{rid}: unknown slots {bad}")

            category = raw.get("category")
            if category not in CATEGORIES:
                raise CatalogueError(f"{rid}: unknown category {category!r}")

            unknown = [i["food"] for i in raw["ingredients"] if i["food"] not in foods]
            if unknown:
                raise CatalogueError(f"{rid}: unknown food keys {unknown}")

            recipes.append(
                Recipe(
                    id=rid,
                    name=raw["name"],
                    slots=list(slots),
                    category=category,
                    cuisine=raw.get("cuisine", "other"),
                    source=raw.get("source") or {},
                    servings=raw.get("servings", 1),
                    ingredients=[Ingredient(**i) for i in raw["ingredients"]],
                    steps=raw["steps"],
                    tags=raw.get("tags", []),
                    prep_min=raw.get("prep_min", 0),
                    cook_min=raw.get("cook_min", 0),
                    _foods=foods,
                )
            )

    if not recipes:
        raise CatalogueError("no recipes loaded")
    for recipe in recipes:
        recipe.normalise_tags()
    return recipes


def by_slot(recipes: list[Recipe]) -> dict[str, list[Recipe]]:
    """Index recipes by slot. A multi-slot recipe appears under each of its slots."""
    out: dict[str, list[Recipe]] = {slot: [] for slot in SLOTS}
    for recipe in recipes:
        for slot in recipe.slots:
            out[slot].append(recipe)
    for slot in out:
        out[slot].sort(key=lambda r: r.macros["kcal"])
    return out


def all_tags(recipes: list[Recipe]) -> list[str]:
    return sorted({tag for recipe in recipes for tag in recipe.tags})


def all_categories(recipes: list[Recipe]) -> list[str]:
    return sorted({recipe.category for recipe in recipes})


def all_cuisines(recipes: list[Recipe]) -> list[str]:
    return sorted({recipe.cuisine for recipe in recipes})
