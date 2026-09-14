"""Generate data/foods.json.

Each food carries nutrition per 100 g plus the metadata the shopping list needs:

  group    Items that can be bought together. Red and yellow peppers share the
           "Peppers" group, so a week needing both lists one combined entry.
  unit_g   Typical weight of one purchasable unit, used to turn grams into
           "3 peppers" rather than "480 g of pepper".
  unit     Singular noun for that unit, or None for items bought by weight.
  aisle    Supermarket section, used to order the shopping list.

Nutrition figures are typical UK supermarket values per 100 g of the edible
portion, drained where relevant.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# key: (kcal, protein, fat, group, unit_g, unit, aisle)
FOODS: dict[str, tuple] = {
    # --- eggs and dairy -----------------------------------------------------
    "egg": (143, 12.6, 9.9, "Eggs", 60, "egg", "chilled"),
    "egg white": (52, 11.0, 0.2, "Eggs", 33, None, "chilled"),
    "greek yoghurt 0%": (57, 10.3, 0.2, "Greek yoghurt", 500, None, "chilled"),
    "greek yoghurt 5%": (97, 8.8, 5.0, "Greek yoghurt", 500, None, "chilled"),
    "skyr": (63, 11.0, 0.2, "Greek yoghurt", 450, None, "chilled"),
    "cottage cheese": (98, 12.4, 4.3, "Cottage cheese", 300, None, "chilled"),
    "quark": (67, 12.0, 0.2, "Quark", 250, None, "chilled"),
    "milk semi": (50, 3.6, 1.8, "Milk", 1000, None, "chilled"),
    "milk skimmed": (35, 3.6, 0.3, "Milk", 1000, None, "chilled"),
    "cheddar grated": (416, 25.0, 34.9, "Cheddar", 200, None, "chilled"),
    "feta": (264, 14.2, 21.3, "Feta", 200, None, "chilled"),
    "mozzarella light": (254, 24.0, 16.0, "Mozzarella", 125, None, "chilled"),
    "parmesan": (402, 32.0, 29.0, "Parmesan", 100, None, "chilled"),
    "halloumi": (321, 22.0, 25.0, "Halloumi", 225, None, "chilled"),
    "cream cheese light": (109, 7.0, 6.5, "Cream cheese", 180, None, "chilled"),
    "butter": (744, 0.6, 82.0, "Butter", 250, None, "chilled"),
    # --- poultry and meat ---------------------------------------------------
    "chicken breast raw": (106, 24.0, 1.1, "Chicken breast", 170, "breast", "meat"),
    "chicken thigh skinless raw": (121, 19.0, 4.8, "Chicken thighs", 90, "thigh", "meat"),
    "chicken thigh roast skinless": (179, 25.0, 8.2, "Chicken thighs", 90, "thigh", "meat"),
    "turkey mince 5% raw": (148, 21.5, 5.0, "Turkey mince", 500, None, "meat"),
    "beef mince 5% raw": (137, 21.0, 5.0, "Beef mince", 500, None, "meat"),
    "sirloin raw trimmed": (150, 22.5, 6.0, "Steak", 225, "steak", "meat"),
    "pork loin raw": (136, 21.8, 5.5, "Pork", 200, None, "meat"),
    "gammon steak raw": (123, 21.0, 4.3, "Gammon", 170, "steak", "meat"),
    "bacon medallions raw": (122, 22.0, 3.5, "Bacon", 200, None, "meat"),
    "chorizo": (343, 21.0, 28.0, "Chorizo", 200, None, "meat"),
    "ham slices": (107, 18.0, 3.5, "Ham", 120, None, "chilled"),
    # --- fish ---------------------------------------------------------------
    "salmon raw": (208, 20.4, 13.6, "Salmon", 130, "fillet", "fish"),
    "smoked salmon": (142, 25.0, 4.3, "Smoked salmon", 100, None, "fish"),
    "cod raw": (82, 18.0, 0.7, "White fish", 140, "fillet", "fish"),
    "haddock raw": (81, 18.3, 0.6, "White fish", 140, "fillet", "fish"),
    "tuna spring water drained": (116, 26.0, 1.0, "Tinned tuna", 112, "tin", "cupboard"),
    "mackerel tinned drained": (204, 19.0, 14.0, "Tinned mackerel", 110, "tin", "cupboard"),
    "sardines tinned drained": (217, 23.0, 14.0, "Tinned sardines", 90, "tin", "cupboard"),
    "prawns cooked": (76, 17.6, 0.6, "Prawns", 180, None, "fish"),
    # --- meat alternatives --------------------------------------------------
    "tofu firm": (144, 15.8, 8.0, "Tofu", 396, "block", "chilled"),
    "tempeh": (192, 20.0, 11.0, "Tempeh", 200, None, "chilled"),
    "quorn mince": (94, 14.5, 2.0, "Quorn", 300, None, "frozen"),
    "edamame frozen": (121, 11.0, 5.2, "Edamame", 500, None, "frozen"),
    # --- pulses and tins ----------------------------------------------------
    "chickpeas drained": (120, 7.5, 2.6, "Chickpeas", 240, "tin", "cupboard"),
    "kidney beans drained": (100, 6.8, 0.5, "Kidney beans", 240, "tin", "cupboard"),
    "black beans drained": (114, 7.0, 0.5, "Black beans", 240, "tin", "cupboard"),
    "cannellini beans drained": (110, 7.0, 0.6, "Cannellini beans", 240, "tin", "cupboard"),
    "butter beans drained": (103, 6.5, 0.6, "Butter beans", 240, "tin", "cupboard"),
    "baked beans": (78, 4.7, 0.2, "Baked beans", 400, "tin", "cupboard"),
    "red lentils dry": (353, 24.0, 1.5, "Red lentils", 500, None, "cupboard"),
    "green lentils cooked": (116, 9.0, 0.5, "Green lentils", 390, "tin", "cupboard"),
    "peanut butter": (600, 25.0, 50.0, "Peanut butter", 340, None, "cupboard"),
    # --- grains and starches ------------------------------------------------
    "oats": (379, 11.2, 8.0, "Oats", 1000, None, "cupboard"),
    "basmati rice dry": (356, 7.5, 0.9, "Rice", 1000, None, "cupboard"),
    "brown rice dry": (362, 8.0, 2.8, "Brown rice", 1000, None, "cupboard"),
    "couscous dry": (376, 12.8, 0.6, "Couscous", 500, None, "cupboard"),
    "quinoa dry": (368, 14.0, 6.1, "Quinoa", 500, None, "cupboard"),
    "pasta dry": (352, 12.5, 1.5, "Pasta", 500, None, "cupboard"),
    "wholewheat pasta dry": (340, 13.5, 2.5, "Wholewheat pasta", 500, None, "cupboard"),
    "noodles wholewheat dry": (350, 13.1, 1.5, "Noodles", 250, None, "cupboard"),
    "wholemeal bread": (247, 10.5, 2.5, "Bread", 800, "loaf", "bakery"),
    "sourdough": (259, 9.0, 1.5, "Sourdough", 500, "loaf", "bakery"),
    "bagel": (268, 10.5, 1.5, "Bagels", 85, "bagel", "bakery"),
    "tortilla wrap": (297, 8.5, 7.0, "Wraps", 62, "wrap", "bakery"),
    "pitta wholemeal": (256, 9.5, 1.5, "Pitta", 65, "pitta", "bakery"),
    "baking potato baked": (93, 2.5, 0.2, "Baking potatoes", 300, "potato", "produce"),
    "new potatoes": (75, 1.7, 0.3, "New potatoes", 1000, None, "produce"),
    "sweet potato raw": (86, 1.6, 0.1, "Sweet potatoes", 200, "potato", "produce"),
    # --- vegetables ---------------------------------------------------------
    "red pepper": (31, 1.0, 0.3, "Peppers", 160, "pepper", "produce"),
    "yellow pepper": (31, 1.0, 0.3, "Peppers", 160, "pepper", "produce"),
    "green pepper": (20, 0.8, 0.2, "Peppers", 160, "pepper", "produce"),
    "onion": (40, 1.2, 0.1, "Onions", 150, "onion", "produce"),
    "red onion": (40, 1.1, 0.1, "Onions", 150, "onion", "produce"),
    "spring onion": (32, 1.8, 0.2, "Spring onions", 100, "bunch", "produce"),
    "garlic": (149, 6.4, 0.5, "Garlic", 60, "bulb", "produce"),
    "root ginger": (80, 1.8, 0.8, "Ginger", 50, None, "produce"),
    "chilli": (40, 1.9, 0.4, "Chillies", 15, "chilli", "produce"),
    "tomato": (18, 0.9, 0.2, "Tomatoes", 100, "tomato", "produce"),
    "cherry tomatoes": (18, 0.9, 0.2, "Cherry tomatoes", 250, None, "produce"),
    "cucumber": (15, 0.7, 0.1, "Cucumber", 300, "cucumber", "produce"),
    "carrot": (41, 0.9, 0.2, "Carrots", 80, "carrot", "produce"),
    "courgette": (17, 1.2, 0.3, "Courgettes", 200, "courgette", "produce"),
    "aubergine": (25, 1.0, 0.2, "Aubergine", 300, "aubergine", "produce"),
    "broccoli": (34, 2.8, 0.4, "Broccoli", 350, "head", "produce"),
    "tenderstem": (35, 3.3, 0.4, "Tenderstem", 200, None, "produce"),
    "cauliflower": (25, 1.9, 0.3, "Cauliflower", 600, "head", "produce"),
    "green beans": (31, 1.8, 0.2, "Green beans", 220, None, "produce"),
    "peas frozen": (81, 5.4, 0.4, "Peas", 500, None, "frozen"),
    "spinach": (23, 2.9, 0.4, "Spinach", 250, None, "produce"),
    "kale": (49, 4.3, 0.9, "Kale", 200, None, "produce"),
    "salad leaves": (17, 1.8, 0.3, "Salad leaves", 100, "bag", "produce"),
    "rocket": (25, 2.6, 0.7, "Salad leaves", 100, "bag", "produce"),
    "cabbage red": (31, 1.4, 0.2, "Cabbage", 500, None, "produce"),
    "mushrooms": (22, 3.1, 0.3, "Mushrooms", 250, None, "produce"),
    "butternut squash": (45, 1.0, 0.1, "Butternut squash", 700, None, "produce"),
    "sweetcorn": (86, 3.2, 1.2, "Sweetcorn", 165, "tin", "cupboard"),
    "beetroot cooked": (46, 1.7, 0.1, "Beetroot", 250, None, "produce"),
    "mixed roast veg": (45, 1.5, 1.5, "Mixed vegetables", 500, None, "produce"),
    "asparagus": (25, 2.9, 0.2, "Asparagus", 200, None, "produce"),
    "leek": (35, 1.5, 0.3, "Leeks", 200, "leek", "produce"),
    "celery": (14, 0.7, 0.2, "Celery", 300, None, "produce"),
    # --- fruit --------------------------------------------------------------
    "banana": (89, 1.1, 0.3, "Bananas", 120, "banana", "produce"),
    "apple": (52, 0.4, 0.2, "Apples", 150, "apple", "produce"),
    "berries frozen": (40, 0.8, 0.3, "Frozen berries", 500, None, "frozen"),
    "blueberries": (57, 0.7, 0.3, "Blueberries", 150, None, "produce"),
    "strawberries": (33, 0.7, 0.3, "Strawberries", 400, None, "produce"),
    "raspberries": (52, 1.2, 0.7, "Raspberries", 150, None, "produce"),
    "satsuma": (35, 0.8, 0.1, "Satsumas", 70, "satsuma", "produce"),
    "orange": (47, 0.9, 0.1, "Oranges", 180, "orange", "produce"),
    "mango": (60, 0.8, 0.4, "Mango", 200, None, "produce"),
    "avocado": (160, 2.0, 14.7, "Avocado", 150, "avocado", "produce"),
    "lemon juice": (22, 0.4, 0.2, "Lemons", 45, "lemon", "produce"),
    "lime juice": (20, 0.4, 0.1, "Limes", 30, "lime", "produce"),
    "dates": (277, 1.8, 0.2, "Dates", 200, None, "cupboard"),
    "raisins": (299, 3.1, 0.5, "Raisins", 375, None, "cupboard"),
    # --- nuts, seeds, oils --------------------------------------------------
    "almonds": (613, 21.0, 54.6, "Almonds", 200, None, "cupboard"),
    "flaked almonds": (613, 21.0, 54.6, "Flaked almonds", 100, None, "cupboard"),
    "walnuts": (654, 15.0, 65.0, "Walnuts", 150, None, "cupboard"),
    "cashews": (553, 18.0, 44.0, "Cashews", 200, None, "cupboard"),
    "mixed seeds": (559, 19.0, 46.0, "Mixed seeds", 250, None, "cupboard"),
    "chia seeds": (486, 17.0, 31.0, "Chia seeds", 200, None, "cupboard"),
    "sesame seeds": (573, 17.7, 49.7, "Sesame seeds", 100, None, "cupboard"),
    "olive oil": (884, 0.0, 100.0, "Olive oil", 500, None, "cupboard"),
    "rapeseed oil": (884, 0.0, 100.0, "Oil", 1000, None, "cupboard"),
    "sunflower oil": (884, 0.0, 100.0, "Oil", 1000, None, "cupboard"),
    "sesame oil": (884, 0.0, 100.0, "Sesame oil", 250, None, "cupboard"),
    "tahini": (595, 17.0, 54.0, "Tahini", 270, None, "cupboard"),
    # --- store cupboard -----------------------------------------------------
    "passata": (35, 1.6, 0.2, "Passata", 500, "bottle", "cupboard"),
    "chopped tomatoes": (32, 1.5, 0.2, "Chopped tomatoes", 400, "tin", "cupboard"),
    "tomato puree": (82, 4.5, 0.5, "Tomato puree", 200, None, "cupboard"),
    "coconut milk light": (73, 0.8, 7.0, "Coconut milk", 400, "tin", "cupboard"),
    "stock cube": (250, 10.0, 15.0, "Stock cubes", 60, "box", "cupboard"),
    "soy sauce": (53, 8.0, 0.0, "Soy sauce", 150, "bottle", "cupboard"),
    "fish sauce": (35, 5.0, 0.0, "Fish sauce", 200, "bottle", "cupboard"),
    "rice wine vinegar": (20, 0.0, 0.0, "Rice wine vinegar", 250, "bottle", "cupboard"),
    "balsamic vinegar": (88, 0.5, 0.0, "Balsamic vinegar", 250, "bottle", "cupboard"),
    "dijon mustard": (143, 8.0, 10.0, "Mustard", 185, "jar", "cupboard"),
    "honey": (322, 0.3, 0.0, "Honey", 340, "jar", "cupboard"),
    "maple syrup": (260, 0.0, 0.0, "Maple syrup", 250, "bottle", "cupboard"),
    "harissa": (120, 3.0, 8.0, "Harissa", 90, "jar", "cupboard"),
    "curry paste": (180, 3.0, 13.0, "Curry paste", 180, "jar", "cupboard"),
    "salsa": (36, 1.3, 0.3, "Salsa", 300, "jar", "cupboard"),
    "light mayo": (260, 0.9, 25.0, "Light mayo", 450, "jar", "cupboard"),
    "spices": (320, 12.0, 10.0, "Spices", 40, "jar", "cupboard"),
    "whey": (400, 80.0, 5.0, "Whey protein", 1000, None, "cupboard"),
    "dark choc 70": (600, 8.0, 42.6, "Dark chocolate", 100, "bar", "cupboard"),
    "sugar": (400, 0.0, 0.0, "Sugar", 1000, None, "cupboard"),
}

FIELDS = ("kcal", "protein", "fat", "group", "unit_g", "unit", "aisle")

AISLES = ["produce", "meat", "fish", "chilled", "bakery", "frozen", "cupboard"]


def build() -> dict:
    foods = {}
    for key, values in FOODS.items():
        if len(values) != len(FIELDS):
            raise ValueError(f"{key}: expected {len(FIELDS)} fields, got {len(values)}")
        entry = dict(zip(FIELDS, values, strict=True))
        if entry["aisle"] not in AISLES:
            raise ValueError(f"{key}: unknown aisle {entry['aisle']!r}")
        foods[key] = entry
    return foods


def main() -> None:
    foods = build()
    out = ROOT / "data" / "foods.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(foods, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    groups = {f["group"] for f in foods.values()}
    print(f"wrote {out.relative_to(ROOT)}: {len(foods)} foods in {len(groups)} shopping groups")


if __name__ == "__main__":
    main()
