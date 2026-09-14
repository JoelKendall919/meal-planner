// Shopping list aggregation.
//
// This mirrors src/mealplanner/shopping.py exactly. The browser needs it because
// meal selection is interactive, and Python needs it for the CLI and tests.
// tests/test_shopping_parity.py runs both against the same input and fails if
// they disagree, so the two implementations cannot drift apart.

const AISLE_ORDER = ["produce", "meat", "fish", "chilled", "bakery", "frozen", "cupboard"];

const AISLE_LABELS = {
  produce: "Fruit & veg",
  meat: "Meat",
  fish: "Fish",
  chilled: "Chilled & dairy",
  bakery: "Bakery",
  frozen: "Frozen",
  cupboard: "Cupboard",
};

const PINCH_GRAMS = 15;

function plural(word, n) {
  if (n === 1) return word;
  if (/(s|sh|ch|x)$/.test(word)) return word + "es";
  if (/y$/.test(word) && !"aeiou".includes(word[word.length - 2])) return word.slice(0, -1) + "ies";
  return word + "s";
}

function roundGrams(grams) {
  if (grams < 100) return Math.ceil(grams / 5) * 5;
  if (grams < 1000) return Math.ceil(grams / 25) * 25;
  return Math.ceil(grams / 100) * 100;
}

function quantity(groupFoods, grams) {
  if (grams <= PINCH_GRAMS && groupFoods.every((f) => !f.unit)) return "a small amount";

  const units = [...new Set(groupFoods.filter((f) => f.unit).map((f) => f.unit))];
  if (units.length === 1 && groupFoods.every((f) => f.unit_g)) {
    const unitG = groupFoods.reduce((a, f) => a + f.unit_g, 0) / groupFoods.length;
    // Match Python's round(x, 2) before ceil so borderline totals agree.
    const count = Math.max(1, Math.ceil(Math.round((grams / unitG) * 100) / 100));
    return `${count} ${plural(units[0], count)}`;
  }

  const rounded = roundGrams(grams);
  if (rounded >= 1000) return `${(rounded / 1000).toFixed(1)} kg`.replace(".0 kg", " kg");
  return `${rounded} g`;
}

// selections: array of recipe ids (repeat an id to cook it more than once)
function buildShoppingList(recipes, foods, selections) {
  const index = {};
  recipes.forEach((r) => (index[r.id] = r));

  const perFood = {};
  const usedBy = {};
  selections.forEach((rid) => {
    const recipe = index[rid];
    if (!recipe) return;
    recipe.ingredients.forEach((item) => {
      perFood[item.food] = (perFood[item.food] || 0) + item.grams;
      (usedBy[item.food] = usedBy[item.food] || []).push(rid);
    });
  });

  const grouped = {};
  Object.keys(perFood).forEach((key) => {
    const group = foods[key].group;
    (grouped[group] = grouped[group] || []).push(key);
  });

  const lines = Object.entries(grouped).map(([group, keys]) => {
    const groupFoods = keys.map((k) => foods[k]);
    const total = keys.reduce((a, k) => a + perFood[k], 0);
    const components = keys
      .map((k) => ({
        food: k,
        grams: Math.round(perFood[k] * 10) / 10,
        recipes: [...new Set(usedBy[k])].sort(),
      }))
      .sort((a, b) => b.grams - a.grams);
    return {
      group,
      aisle: groupFoods[0].aisle,
      aisle_label: AISLE_LABELS[groupFoods[0].aisle] || groupFoods[0].aisle,
      grams: Math.round(total * 10) / 10,
      quantity: quantity(groupFoods, total),
      merged: keys.length > 1,
      components,
    };
  });

  lines.sort((a, b) => {
    const d = AISLE_ORDER.indexOf(a.aisle) - AISLE_ORDER.indexOf(b.aisle);
    return d !== 0 ? d : a.group.toLowerCase().localeCompare(b.group.toLowerCase());
  });
  return lines;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { buildShoppingList, quantity, roundGrams, plural, AISLE_ORDER, AISLE_LABELS };
}
