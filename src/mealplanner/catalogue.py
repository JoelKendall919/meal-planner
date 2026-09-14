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

SLOTS = ("breakfast", "lunch", "dinner")

# Tags that describe a measurable property are derived from the recipe data rather
# than trusted from the source file. Hand-written labels drift: an early batch
# tagged 14 recipes "high-protein" that were nowhere near the threshold.
PROTEIN_TAG_G = 30
QUICK_MINUTES = {"breakfast": 10, "lunch": 15, "dinner": 25}
DERIVED_TAGS = {"high-protein", "quick"}


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
    slot: str
    source: dict
    servings: int
    ingredients: list[Ingredient]
    steps: list[str]
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
        if self.macros["protein"] >= PROTEIN_TAG_G:
            tags.add("high-protein")
        if self.total_min and self.total_min <= QUICK_MINUTES[self.slot]:
            tags.add("quick")
        self.tags = sorted(tags)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slot": self.slot,
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

    recipes: list[Recipe] = []
    seen: set[str] = set()

    for slot in SLOTS:
        path = data_dir / f"recipes-{slot}.json"
        if not path.exists():
            raise CatalogueError(f"missing recipe file: {path}")

        for raw in json.loads(path.read_text(encoding="utf-8")):
            rid = raw.get("id")
            if not rid:
                raise CatalogueError(f"{path.name}: a recipe has no id")
            if rid in seen:
                raise CatalogueError(f"duplicate recipe id: {rid}")
            seen.add(rid)

            unknown = [i["food"] for i in raw["ingredients"] if i["food"] not in foods]
            if unknown:
                raise CatalogueError(f"{rid}: unknown food keys {unknown}")

            recipes.append(
                Recipe(
                    id=rid,
                    name=raw["name"],
                    slot=raw["slot"],
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
    out: dict[str, list[Recipe]] = {slot: [] for slot in SLOTS}
    for recipe in recipes:
        out[recipe.slot].append(recipe)
    for slot in out:
        out[slot].sort(key=lambda r: r.macros["kcal"])
    return out


def all_tags(recipes: list[Recipe]) -> list[str]:
    return sorted({tag for recipe in recipes for tag in recipe.tags})
