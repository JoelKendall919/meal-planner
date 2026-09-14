"""Turn a set of chosen meals into a consolidated shopping list.

Two meals that both need a red pepper should produce one line reading
"Peppers - 2", not two separate entries. Aggregation happens in two stages:

1. Identical ingredients are summed by food key.
2. Food keys sharing a ``group`` are merged into one line, because they are the
   same purchase in practice. Red, yellow, and green peppers all become
   "Peppers"; the individual varieties are kept as components so the card can
   still show what the recipes actually asked for.

Quantities are converted to whole purchasable units where the food has a unit
weight, since "3 peppers" is more useful in a supermarket than "480 g pepper".
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from .catalogue import Food, Recipe

AISLE_ORDER = ["produce", "meat", "fish", "chilled", "bakery", "frozen", "cupboard"]

AISLE_LABELS = {
    "produce": "Fruit & veg",
    "meat": "Meat",
    "fish": "Fish",
    "chilled": "Chilled & dairy",
    "bakery": "Bakery",
    "frozen": "Frozen",
    "cupboard": "Cupboard",
}

# Ingredients used in trivial amounts are worth listing, but not worth
# converting into a precise quantity.
PINCH_GRAMS = 15


@dataclass
class Component:
    food: str
    grams: float
    recipes: list[str] = field(default_factory=list)


@dataclass
class Line:
    group: str
    aisle: str
    grams: float
    quantity: str
    components: list[Component]

    @property
    def merged(self) -> bool:
        """True when this line combines more than one distinct ingredient."""
        return len(self.components) > 1

    def to_dict(self) -> dict:
        return {
            "group": self.group,
            "aisle": self.aisle,
            "aisle_label": AISLE_LABELS.get(self.aisle, self.aisle.title()),
            "grams": round(self.grams, 1),
            "quantity": self.quantity,
            "merged": self.merged,
            "components": [
                {"food": c.food, "grams": round(c.grams, 1), "recipes": sorted(set(c.recipes))}
                for c in sorted(self.components, key=lambda c: -c.grams)
            ],
        }


def _plural(word: str, n: int) -> str:
    if n == 1:
        return word
    if word.endswith(("s", "sh", "ch", "x")):
        return word + "es"
    if word.endswith("y") and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def _round_grams(grams: float) -> int:
    """Round up to a weight that is sensible to buy."""
    if grams < 100:
        return int(math.ceil(grams / 5) * 5)
    if grams < 1000:
        return int(math.ceil(grams / 25) * 25)
    return int(math.ceil(grams / 100) * 100)


def _quantity(group_foods: list[Food], grams: float) -> str:
    """Describe a total as units where possible, otherwise as a weight."""
    if grams <= PINCH_GRAMS and all(f.unit is None for f in group_foods):
        return "a small amount"

    units = {f.unit for f in group_foods if f.unit}
    if len(units) == 1 and all(f.unit_g for f in group_foods):
        unit = units.pop()
        # Foods in a group can differ slightly in size; use the mean.
        unit_g = sum(f.unit_g for f in group_foods) / len(group_foods)
        count = max(1, math.ceil(round(grams / unit_g, 2)))
        return f"{count} {_plural(unit, count)}"

    rounded = _round_grams(grams)
    if rounded >= 1000:
        return f"{rounded / 1000:.1f} kg".replace(".0 kg", " kg")
    return f"{rounded} g"


def build_list(
    recipes: list[Recipe],
    foods: dict[str, Food],
    selections: list[str] | None = None,
) -> list[dict]:
    """Build a shopping list for the given recipe ids.

    ``selections`` may repeat an id to indicate the meal is cooked more than once.
    """
    index = {r.id: r for r in recipes}
    chosen = selections if selections is not None else [r.id for r in recipes]

    missing = [rid for rid in chosen if rid not in index]
    if missing:
        raise KeyError(f"unknown recipe ids: {missing}")

    per_food: dict[str, float] = defaultdict(float)
    used_by: dict[str, list[str]] = defaultdict(list)
    for rid in chosen:
        for item in index[rid].ingredients:
            per_food[item.food] += item.grams
            used_by[item.food].append(rid)

    grouped: dict[str, list[str]] = defaultdict(list)
    for key in per_food:
        grouped[foods[key].group].append(key)

    lines: list[Line] = []
    for group, keys in grouped.items():
        group_foods = [foods[k] for k in keys]
        total = sum(per_food[k] for k in keys)
        lines.append(
            Line(
                group=group,
                aisle=group_foods[0].aisle,
                grams=total,
                quantity=_quantity(group_foods, total),
                components=[Component(food=k, grams=per_food[k], recipes=used_by[k]) for k in keys],
            )
        )

    lines.sort(key=lambda ln: (AISLE_ORDER.index(ln.aisle), ln.group.lower()))
    return [ln.to_dict() for ln in lines]


def summarise(lines: list[dict]) -> dict:
    return {
        "lines": len(lines),
        "merged": sum(1 for ln in lines if ln["merged"]),
        "aisles": len({ln["aisle"] for ln in lines}),
    }
