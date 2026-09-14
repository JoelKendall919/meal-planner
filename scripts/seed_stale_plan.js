/* A plan saved against an older catalogue: some ids no longer exist.
 * Injected before the app's script so it boots against this, the way a phone
 * with months-old storage does. */
localStorage.clear();
localStorage.setItem("mealplanner.v3", JSON.stringify({
  cursor: "2026-09-16",
  view: "day",
  plan: {
    // Every main is a dead id: the day looks blank but counts as full.
    "2026-09-16": { breakfast: "porridge-with-whey", lunch: "chicken-wrap-old", dinner: "chilli-con-carne-v1" },
    // A mix: one live meal, one dead.
    "2026-09-17": { breakfast: "greek-yoghurt", dinner: "some-retired-dinner" },
    // Nothing but dead ids: the day should disappear entirely.
    "2026-09-18": { lunch: "gone", snack: "also-gone" },
    // Untouched.
    "2026-09-19": { lunch: "greek-yoghurt" },
  },
  goals: { kcal: 1750, protein: 140, fat: 50, carbs: 160 },
}));
