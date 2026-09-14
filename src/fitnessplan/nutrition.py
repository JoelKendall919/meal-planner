"""Nutrition model: the single source of truth for every calorie and protein figure.

Every number in the plan documents is computed from this module. Figures are never
estimated by hand -- an early version of this plan overstated protein by ~46 g/day
because recipes were eyeballed. The tests enforce that the documents match this model.

FOODS maps an ingredient to (kcal, protein_g, fat_g) per 100 g or 100 ml.
"""

FOODS: dict[str, tuple[float, float, float]] = {
    "greek yoghurt 0%": (57, 10.3, 0.2),
    "berries frozen": (40, 0.8, 0.3),
    "honey": (322, 0.3, 0),
    "sesame seeds": (573, 17.7, 49.7),
    "oats": (379, 11.2, 8),
    "milk semi": (50, 3.6, 1.8),
    "whey": (400, 80, 5),
    "banana": (89, 1.1, 0.3),
    "egg": (143, 12.6, 9.9),
    "wholemeal bread": (247, 10.5, 2.5),
    "spinach": (23, 2.9, 0.4),
    "chicken thigh roast skinless": (179, 25.0, 8.2),
    "mixed roast veg": (45, 1.5, 1.5),
    "salad leaves": (17, 1.8, 0.3),
    "cherry tomatoes": (18, 0.9, 0.2),
    "olive oil": (884, 0, 100),
    "chickpeas drained": (120, 7.5, 2.6),
    "couscous dry": (376, 12.8, 0.6),
    "feta": (264, 14.2, 21.3),
    "cucumber": (15, 0.7, 0.1),
    "red onion": (40, 1.1, 0.1),
    "lime juice": (20, 0.4, 0.1),
    "baking potato baked": (93, 2.5, 0.2),
    "tuna spring water drained": (116, 26, 1),
    "light mayo": (260, 0.9, 25),
    "spring onion": (32, 1.8, 0.2),
    "turkey mince 5% raw": (148, 21.5, 5),
    "onion": (40, 1.2, 0.1),
    "pepper": (31, 1.0, 0.3),
    "passata": (35, 1.6, 0.2),
    "kidney beans drained": (100, 6.8, 0.5),
    "spices": (320, 12, 10),
    "stock cube": (250, 10, 15),
    "basmati rice dry": (356, 7.5, 0.9),
    "tofu firm": (144, 15.8, 8),
    "noodles wholewheat dry": (350, 13.1, 1.5),
    "carrot": (41, 0.9, 0.2),
    "tenderstem": (35, 3.3, 0.4),
    "soy sauce": (53, 8, 0),
    "peanut butter": (600, 25, 50),
    "sugar": (400, 0, 0),
    "sesame oil": (884, 0, 100),
    "sunflower oil": (884, 0, 100),
    "salmon raw": (208, 20.4, 13.6),
    "new potatoes": (75, 1.7, 0.3),
    "sirloin raw trimmed": (150, 22.5, 6),
    "sweet potato raw": (86, 1.6, 0.1),
    "broccoli": (34, 2.8, 0.4),
    "beef mince 5% raw": (137, 21, 5),
    "black beans drained": (114, 7, 0.5),
    "sweetcorn": (86, 3.2, 1.2),
    "cheddar grated": (416, 25, 34.9),
    "salsa": (36, 1.3, 0.3),
    "red lentils dry": (353, 24, 1.5),
    "coconut milk light": (73, 0.8, 7),
    "satsuma": (35, 0.8, 0.1),
    "apple": (52, 0.4, 0.2),
    "almonds": (613, 21, 54.6),
    "dark choc 70": (600, 8, 42.6),
    "green beans": (31, 1.8, 0.2),
    "edamame frozen": (121, 11.0, 5.2),
    "smoked salmon": (142, 25.0, 4.3),
}

# Recipes as (ingredient, grams). Weights are edible/drained weights.
RECIPES: dict[str, list[tuple[str, float]]] = {
    "W1 Shakshuka (V)": [
        ("egg", 250),
        ("passata", 100),
        ("pepper", 80),
        ("onion", 50),
        ("chickpeas drained", 50),
        ("feta", 60),
        ("spinach", 50),
        ("olive oil", 2),
        ("spices", 4),
        ("greek yoghurt 0%", 100),
    ],
    "W2 Smoked Salmon Scramble + yoghurt bowl": [
        ("egg", 200),
        ("smoked salmon", 100),
        ("new potatoes", 60),
        ("spinach", 40),
        ("cherry tomatoes", 75),
        ("olive oil", 3),
        ("greek yoghurt 0%", 200),
        ("berries frozen", 100),
        ("honey", 0),
    ],
    "L1 Roast Chicken Salad": [
        ("chicken thigh roast skinless", 215),
        ("mixed roast veg", 200),
        ("new potatoes", 60),
        ("salad leaves", 50),
        ("cherry tomatoes", 75),
        ("olive oil", 4),
    ],
    "L4 Chickpea & Feta Couscous (V)": [
        ("chickpeas drained", 115),
        ("couscous dry", 15),
        ("feta", 50),
        ("egg", 150),
        ("cucumber", 75),
        ("cherry tomatoes", 75),
        ("red onion", 30),
        ("olive oil", 1),
        ("lime juice", 10),
        ("greek yoghurt 0%", 150),
    ],
    "L5 Tuna Jacket Potato": [
        ("baking potato baked", 300),
        ("tuna spring water drained", 200),
        ("light mayo", 25),
        ("spring onion", 15),
        ("salad leaves", 50),
        ("olive oil", 5),
    ],
    "D1 Turkey Chilli + rice": [
        ("turkey mince 5% raw", 250),
        ("onion", 40),
        ("pepper", 40),
        ("passata", 75),
        ("kidney beans drained", 120),
        ("spices", 3),
        ("stock cube", 2.5),
        ("olive oil", 4),
        ("basmati rice dry", 22),
    ],
    "D2 Tofu Stir-Fry (V)": [
        ("tofu firm", 225),
        ("edamame frozen", 170),
        ("noodles wholewheat dry", 0),
        ("pepper", 75),
        ("carrot", 60),
        ("tenderstem", 100),
        ("spring onion", 15),
        ("soy sauce", 15),
        ("peanut butter", 3),
        ("sugar", 0),
        ("sesame oil", 1),
        ("sunflower oil", 2),
    ],
    "D3 Salmon, Potatoes & Greens": [
        ("salmon raw", 200),
        ("new potatoes", 100),
        ("tenderstem", 150),
        ("green beans", 100),
        ("olive oil", 2),
        ("greek yoghurt 0%", 70),
    ],
    "D4 Steak, Wedges & Broccoli": [
        ("sirloin raw trimmed", 225),
        ("sweet potato raw", 200),
        ("broccoli", 200),
        ("olive oil", 6),
    ],
    "D5 Beef & Bean Burrito Bowl": [
        ("beef mince 5% raw", 250),
        ("black beans drained", 120),
        ("onion", 40),
        ("basmati rice dry", 12),
        ("sweetcorn", 50),
        ("cheddar grated", 10),
        ("salsa", 30),
        ("lime juice", 10),
    ],
    "D6 Lentil & Chickpea Dahl (V)": [
        ("red lentils dry", 80),
        ("chickpeas drained", 75),
        ("onion", 50),
        ("passata", 100),
        ("coconut milk light", 10),
        ("spinach", 50),
        ("spices", 4),
        ("sunflower oil", 2),
        ("basmati rice dry", 0),
        ("greek yoghurt 0%", 350),
    ],
    "D7 Roast Chicken Thighs & Veg": [
        ("chicken thigh roast skinless", 215),
        ("mixed roast veg", 200),
        ("new potatoes", 100),
        ("olive oil", 3),
    ],
    "SB Protein shake + satsuma": [("whey", 30), ("satsuma", 70)],
    "SD Apple, yoghurt & almonds": [("apple", 150), ("greek yoghurt 0%", 150), ("almonds", 10)],
    "SH Yoghurt pot": [("greek yoghurt 0%", 150)],
    "SE Dark chocolate": [("dark choc 70", 20)],
    "SK Daily shake": [("whey", 30)],
    "SG Yoghurt & berries": [("greek yoghurt 0%", 200), ("berries frozen", 60)],
    "SJ Two boiled eggs": [("egg", 120)],
}

# Leftover lunches inherit their parent dinner's portion exactly.
ALIASES: dict[str, str] = {
    "L2 Leftover Turkey Chilli": "D1 Turkey Chilli + rice",
    "L3 Leftover Tofu Stir-Fry (V)": "D2 Tofu Stir-Fry (V)",
}

DAYS: dict[str, list[str]] = {
    "Mon": [
        "L1 Roast Chicken Salad",
        "D1 Turkey Chilli + rice",
        "SK Daily shake",
        "SD Apple, yoghurt & almonds",
        "SG Yoghurt & berries",
    ],
    "Tue": [
        "L2 Leftover Turkey Chilli",
        "D2 Tofu Stir-Fry (V)",
        "SK Daily shake",
        "SG Yoghurt & berries",
        "SJ Two boiled eggs",
    ],
    "Wed": [
        "L3 Leftover Tofu Stir-Fry (V)",
        "D3 Salmon, Potatoes & Greens",
        "SK Daily shake",
        "SG Yoghurt & berries",
        "SD Apple, yoghurt & almonds",
    ],
    "Thu": [
        "L5 Tuna Jacket Potato",
        "D5 Beef & Bean Burrito Bowl",
        "SK Daily shake",
        "SD Apple, yoghurt & almonds",
        "SG Yoghurt & berries",
    ],
    "Fri": [
        "L4 Chickpea & Feta Couscous (V)",
        "D4 Steak, Wedges & Broccoli",
        "SK Daily shake",
        "SG Yoghurt & berries",
        "SJ Two boiled eggs",
    ],
    "Sat": [
        "W1 Shakshuka (V)",
        "D6 Lentil & Chickpea Dahl (V)",
        "SK Daily shake",
        "SH Yoghurt pot",
        "SG Yoghurt & berries",
    ],
    "Sun": [
        "W2 Smoked Salmon Scramble + yoghurt bowl",
        "D7 Roast Chicken Thighs & Veg",
        "SK Daily shake",
        "SE Dark chocolate",
        "SH Yoghurt pot",
        "SG Yoghurt & berries",
    ],
}

DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

TARGET_KCAL = 1750
TARGET_PROTEIN = 165


def totals(items: list[tuple[str, float]]) -> tuple[float, float, float]:
    """Return unrounded (kcal, protein, fat) for a list of (ingredient, grams)."""
    kcal = protein = fat = 0.0
    for name, grams in items:
        k, p, f = FOODS[name]
        kcal += k * grams / 100
        protein += p * grams / 100
        fat += f * grams / 100
    return kcal, protein, fat


def _resolve(meal: str) -> list[tuple[str, float]]:
    return RECIPES[ALIASES.get(meal, meal)]


def recipe_totals(rounded: bool = True) -> dict[str, tuple[float, float, float]]:
    """Per-recipe totals, including leftover aliases."""
    out = {name: totals(items) for name, items in RECIPES.items()}
    for alias, parent in ALIASES.items():
        out[alias] = out[parent]
    if rounded:
        out = {k: (round(a), round(b), round(c)) for k, (a, b, c) in out.items()}
    return out


def day_totals(day: str, rounded_meals: bool = True) -> tuple[float, float, float]:
    """Totals for one day.

    The published documents round each meal before summing (``rounded_meals=True``),
    which can differ from the unrounded sum by ~1 g. Tests allow that tolerance.
    """
    per = recipe_totals(rounded=rounded_meals)
    k = sum(per[m][0] for m in DAYS[day])
    p = sum(per[m][1] for m in DAYS[day])
    f = sum(per[m][2] for m in DAYS[day])
    return k, p, f


def carbs(kcal: float, protein: float, fat: float) -> float:
    """Carbohydrate grams derived by difference."""
    return (kcal - 4 * protein - 9 * fat) / 4


def week_average() -> dict[str, float]:
    t = [day_totals(d, rounded_meals=False) for d in DAY_ORDER]
    k = sum(x[0] for x in t) / 7
    p = sum(x[1] for x in t) / 7
    f = sum(x[2] for x in t) / 7
    return {"kcal": k, "protein": p, "fat": f, "carbs": carbs(k, p, f)}


def weekly_grams(ingredient: str) -> float:
    """Total grams of one ingredient consumed across the week."""
    return sum(
        g
        for day in DAY_ORDER
        for meal in DAYS[day]
        for name, g in _resolve(meal)
        if name == ingredient
    )


def report() -> str:
    lines = [f"{'RECIPE':<40}{'kcal':>7}{'prot':>7}{'fat':>6}"]
    per = recipe_totals()
    for name in RECIPES:
        k, p, f = per[name]
        lines.append(f"{name:<40}{k:>7.0f}{p:>7.0f}{f:>6.0f}")
    lines.append("")
    lines.append(
        f"{'DAY':<6}{'kcal':>7}{'vs tgt':>8}{'prot':>7}{'fat':>6}{'carb':>6}{'P%':>5}{'F%':>5}"
    )
    for d in DAY_ORDER:
        k, p, f = day_totals(d)
        c = carbs(k, p, f)
        lines.append(
            f"{d:<6}{k:>7.0f}{k - TARGET_KCAL:>+8.0f}{p:>7.0f}{f:>6.0f}{c:>6.0f}"
            f"{400 * p / k:>5.0f}{900 * f / k:>5.0f}"
        )
    avg = week_average()
    lines.append(
        f"{'AVG':<6}{avg['kcal']:>7.0f}{avg['kcal'] - TARGET_KCAL:>+8.0f}"
        f"{avg['protein']:>7.0f}{avg['fat']:>6.0f}{avg['carbs']:>6.0f}"
    )
    lines.append("")
    lines.append(
        f"whey/week {weekly_grams('whey'):.0f} g   yoghurt/week {weekly_grams('greek yoghurt 0%'):.0f} g"  # noqa: E501
    )
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
