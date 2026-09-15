/* Headless driver for the eight UI tweaks.
 *
 * Appended to a copy of the built dist/index.html and run under headless
 * Chrome. Everything here drives the real app: it renders real views, opens
 * real sheets and dispatches real pointer events, then reads the DOM back.
 * Results are printed into #drv, which --dump-dom returns.
 */
const out = [];
const ok = (name, cond, detail) =>
  out.push(`${cond ? "PASS" : "FAIL"}  ${name}${detail ? "  -- " + detail : ""}`);

// Headless Chrome dismisses dialogs, which would silently cancel anything that
// asks before overwriting. Drive confirm() explicitly instead.
let confirms = [];
let confirmAnswer = true;
window.confirm = msg => { confirms.push(msg); return confirmAnswer; };

function reset(){
  S.plan = {};
  S.cursor = "2026-03-02";        // a Monday
  S.view = "day";
  Object.assign(filter, { slot: null, cat: null, tag: null, q: "" });
  Object.assign(pickFilter, { slot: null, cat: null, tag: null, q: "" });
  dragMode = "move";
}

/* --- 7. type labels follow the shortlist headings --------------------- */
function testCatLabels(){
  const want = {
    "cooked-breakfast": "Hot & hearty",
    "sandwiches": "Sandwiches, toasties & wraps",
    "salads": "Salads & bowls",
    "pasta-and-italian": "Pasta, pizza & Italian",
    "curries": "Curries & spiced",
    "asian": "Asian-style",
    "british-classics": "British classics",
    "traybakes-and-quick": "Traybakes & quick",
  };
  const bad = Object.entries(want).filter(([k, v]) => catLabel(k) !== v);
  ok("category labels match the shortlist headings", !bad.length, JSON.stringify(bad));

  // and they actually reach the rendered dropdown
  reset();
  tab = "recipes";
  render();
  const sel = document.querySelector("select[data-fcatsel]");
  const texts = sel ? [...sel.options].map(o => o.textContent.trim()) : [];
  ok("shortlist wording reaches the Type dropdown",
    texts.includes("Hot & hearty") && texts.includes("Sandwiches, toasties & wraps") &&
    texts.includes("Pasta, pizza & Italian"),
    texts.slice(0, 4).join(" | "));
}

/* --- 8. meal = colour-coded buttons, type/filter = dropdowns ----------- */
function testControls(){
  reset();
  tab = "recipes";
  render();

  const cat = document.querySelector("select[data-fcatsel]");
  ok("Type is a dropdown", !!cat && cat.tagName === "SELECT");
  const tagBtns = [...document.querySelectorAll("[data-ftag]")];
  ok("Filter is buttons", tagBtns.length === 3 && tagBtns.every(b => b.tagName === "BUTTON"),
    tagBtns.map(b => b.tagName).join(","));
  ok("no filter chips left for type", !document.querySelector("[data-fcat]"));

  const meals = [...document.querySelectorAll("[data-fslot]")];
  ok("Meal is still buttons", meals.length === 4 && meals.every(b => b.tagName === "BUTTON"),
    meals.map(b => b.tagName).join(","));
  ok("each meal button carries its own colour class",
    ["breakfast", "lunch", "dinner", "snack"].every(s =>
      meals.some(b => b.classList.contains("slot-" + s))),
    meals.map(b => b.className).join(" / "));
  const colours = ["breakfast", "lunch", "dinner", "snack"].map(s =>
    getComputedStyle(document.querySelector(".chip.slot-" + s)).color);
  ok("the four meal colours are all different", new Set(colours).size === 4, colours.join(" "));

  // the dropdowns must actually filter
  const before = filterRecipes(filter).length;
  cat.value = "soups";
  cat.dispatchEvent(new Event("change", { bubbles: true }));
  const after = filterRecipes(filter).length;
  ok("choosing a type filters the list",
    filter.cat === "soups" && after < before && after > 0, `${before} -> ${after}`);

  const soupRows = document.querySelectorAll("[data-open]").length;
  ok("the filtered list is what gets rendered", soupRows === after, `${soupRows} vs ${after}`);

  // selecting the blank option clears it again
  const sel2 = document.querySelector("select[data-fcatsel]");
  sel2.value = "";
  sel2.dispatchEvent(new Event("change", { bubbles: true }));
  ok("the blank option clears the type filter",
    filter.cat === null && filterRecipes(filter).length === before);

  document.querySelector('[data-ftag="tab|vegetarian"]').click();
  ok("choosing a filter tag filters the list",
    filter.tags.includes("vegetarian") &&
    filterRecipes(filter).every(r => r.tags.includes("vegetarian")));

  // Type must stay scoped to the chosen meal
  reset();
  render();
  document.querySelector('[data-fslot="tab|breakfast"]').click();
  const opts = [...document.querySelector("select[data-fcatsel]").options]
    .map(o => o.value).filter(Boolean);
  ok("Type only offers categories that exist in the chosen meal",
    opts.length && opts.every(c =>
      RECIPES.some(r => r.category === c && r.slots.includes("breakfast"))) &&
    !opts.includes("roasts"),
    opts.join(","));
}

/* --- 6. portions multiply the written quantities ----------------------- */
function testPortions(){
  ok("scaleDisplay multiplies a whole number",
    scaleDisplay("3 rashers back bacon", 2) === "6 rashers back bacon");
  ok("scaleDisplay turns a half into a whole",
    scaleDisplay("1/2 tin chopped tomatoes", 2) === "1 tin chopped tomatoes");
  ok("scaleDisplay makes a mixed fraction",
    scaleDisplay("1/2 tin chopped tomatoes", 3) === "1 1/2 tin chopped tomatoes");
  ok("scaleDisplay resolves a mixed fraction",
    scaleDisplay("1 1/2 tbsp olive oil", 2) === "3 tbsp olive oil");
  ok("scaleDisplay scales a stated gram weight",
    scaleDisplay("60 g oats", 3) === "180 g oats");
  ok("scaleDisplay leaves prose alone",
    scaleDisplay("a knob of butter", 4) === "a knob of butter");
  ok("scaleDisplay is identity at one portion",
    scaleDisplay("1/2 tin chopped tomatoes", 1) === "1/2 tin chopped tomatoes");

  // and in the real sheet
  const r = BY_ID["bacon-roll"];
  recipeSheet("bacon-roll", 1);
  const one = [...document.querySelectorAll(".ing li span:first-child")].map(s => s.textContent.trim());
  recipeSheet("bacon-roll", 3);
  const three = [...document.querySelectorAll(".ing li span:first-child")].map(s => s.textContent.trim());
  const grams = [...document.querySelectorAll(".ing li .g")].map(s => s.textContent.trim());
  closeSheet();
  ok("the sheet shows multiplied quantities, not an 'n x' prefix",
    three[0] === "9 rashers back bacon" && one[0] === "3 rashers back bacon",
    `1x: ${one[0]} | 3x: ${three[0]}`);
  ok("no 'x' prefix survives anywhere in the list",
    !three.some(t => /^\s*\d+\s*(x|\u00d7)\s/i.test(t)), three.join(" | "));
  ok("grams still scale alongside the text",
    grams[0] === String(r.ingredients[0].grams * 3) + " g", grams.join(" | "));
  ok("prose lines are untouched but their grams still scale",
    three[3] === "a squirt of brown sauce" && grams[3] === "45 g",
    `${three[3]} / ${grams[3]}`);
}

/* --- 4 + 2. dashboard is day-only and uncoloured ----------------------- */
function testDashboard(){
  reset();
  tab = "plan";
  // a full day, well over every goal, so colouring would definitely show
  S.plan["2026-03-02"] = { breakfast: "full-english", lunch: "fish-and-chips", dinner: "beef-lasagne" };
  const pick = slot => (RECIPES.find(r => r.slots.includes(slot)) || {}).id;
  S.plan["2026-03-02"] = {
    breakfast: pick("breakfast"), lunch: pick("lunch"), dinner: pick("dinner"),
  };

  S.view = "day"; render();
  const dayDash = document.querySelectorAll("#view .macros").length;
  ok("the day view still has its dashboard", dayDash >= 1, String(dayDash));
  ok("the day dashboard is not colour-graded",
    !document.querySelector("#view .macros .s-good, #view .macros .s-warn, #view .macros .s-bad"));
  ok("nothing in the whole plan view is colour-graded",
    !document.querySelector("#view .s-good, #view .s-warn, #view .s-bad"));

  S.view = "week"; render();
  ok("the week view has no dashboard",
    !document.querySelector("#view .macros"),
    document.querySelectorAll("#view .macros").length + " found");

  S.view = "month"; render();
  ok("the month view has no dashboard", !document.querySelector("#view .macros"));

  // the figures themselves must still be there in day view
  S.view = "day"; render();
  const txt = document.querySelector("#view .macros").textContent;
  ok("day figures still show the goal", /of\s*1750/.test(txt.replace(/\s+/g, " ")), txt.trim().slice(0, 80));
}

/* --- 1. a clear button on each day ------------------------------------ */
function testClearDay(){
  reset();
  tab = "plan";
  S.view = "week";
  const pick = slot => (RECIPES.find(r => r.slots.includes(slot)) || {}).id;
  S.plan["2026-03-02"] = { breakfast: pick("breakfast"), dinner: pick("dinner") };
  S.plan["2026-03-03"] = { lunch: pick("lunch") };
  render();

  const btns = [...document.querySelectorAll("[data-clearday]")];
  ok("every day in the week has a clear button", btns.length === 7, String(btns.length));
  ok("empty days have it disabled",
    btns.filter(b => !b.disabled).length === 2,
    btns.map(b => b.dataset.clearday + (b.disabled ? ":off" : ":on")).join(" "));

  document.querySelector('[data-clearday="2026-03-02"]').click();
  ok("clearing a day empties only that day",
    !S.plan["2026-03-02"] && !!S.plan["2026-03-03"],
    JSON.stringify(Object.keys(S.plan)));

  const still = document.querySelectorAll("[data-clearday]").length;
  ok("the week redraws after clearing", still === 7, String(still));
}

/* --- 5. no By day section in nutrients -------------------------------- */
function testNutrients(){
  reset();
  tab = "nutrients";
  const pick = slot => (RECIPES.find(r => r.slots.includes(slot)) || {}).id;
  ["2026-03-02", "2026-03-03", "2026-03-04"].forEach(d => {
    S.plan[d] = { breakfast: pick("breakfast"), lunch: pick("lunch"), dinner: pick("dinner") };
  });
  ["day", "week", "month"].forEach(v => {
    S.view = v;
    render();
    const heads = [...document.querySelectorAll("#view h2")].map(h => h.textContent.trim());
    ok(`no "By day" section in nutrients (${v} view)`,
      !heads.some(h => /by day/i.test(h)), heads.join(" | "));
  });
  // the rest of the tab must survive
  S.view = "week"; render();
  const heads = [...document.querySelectorAll("#view h2")].map(h => h.textContent.trim());
  ok("nutrients keeps its other sections",
    heads.some(h => /daily goals/i.test(h)) && heads.some(h => /daily average/i.test(h)),
    heads.join(" | "));
  ok("nutrients is still colour-graded (only plan lost it)",
    !!document.querySelector("#view .s-good, #view .s-warn, #view .s-bad"));
}

/* --- filters: capitals, scoped types, three tags ---------------------- */
function testFilterRules(){
  reset();
  tab = "recipes";
  render();

  const meals = [...document.querySelectorAll("[data-fslot]")].map(b => b.textContent.trim());
  ok("meal buttons are capitalised",
    JSON.stringify(meals) === JSON.stringify(["Breakfast", "Lunch", "Dinner", "Snack"]),
    meals.join(","));

  const tags = [...document.querySelectorAll("[data-ftag]")].map(b => b.textContent.trim());
  ok("the Filter row offers only the three wanted tags",
    JSON.stringify(tags) === JSON.stringify(["Vegetarian", "Light", "High protein"]),
    tags.join(" | "));

  const values = [...document.querySelectorAll("[data-ftag]")]
    .map(b => b.dataset.ftag.split("|")[1]);
  ok("each Filter tag actually matches recipes",
    values.every(v => RECIPES.some(r => r.tags.includes(v))),
    values.map(v => v + ":" + RECIPES.filter(r => r.tags.includes(v)).length).join(" "));

  // Type must follow the chosen meal
  const all = [...document.querySelector("select[data-fcatsel]").options].length - 1;
  const seen = {};
  ["Breakfast", "Dinner", "Snack"].forEach(label => {
    const slot = label.toLowerCase();
    // reset the meal choice, then pick this one
    Object.assign(filter, { slot: null, cat: null, tag: null, q: "" });
    render();
    document.querySelector(`[data-fslot="tab|${slot}"]`).click();
    const opts = [...document.querySelector("select[data-fcatsel]").options]
      .map(o => o.value).filter(Boolean);
    seen[slot] = opts;
    ok(`Type is scoped to ${label}`,
      opts.length > 0 && opts.length < all &&
      opts.every(c => RECIPES.some(r => r.category === c && r.slots.includes(slot))),
      `${opts.length} of ${all}: ${opts.join(",")}`);
  });
  ok("different meals really do offer different types",
    JSON.stringify(seen.breakfast) !== JSON.stringify(seen.dinner) &&
    !seen.breakfast.includes("roasts") && seen.dinner.includes("roasts"));

  // switching meal must drop a type that no longer applies
  Object.assign(filter, { slot: null, cat: null, tag: null, q: "" });
  render();
  document.querySelector('[data-fslot="tab|dinner"]').click();
  const sel = document.querySelector("select[data-fcatsel]");
  sel.value = "roasts";
  sel.dispatchEvent(new Event("change", { bubbles: true }));
  ok("a dinner type can be chosen", filter.cat === "roasts");
  document.querySelector('[data-fslot="tab|dinner"]').click();   // back to all meals
  document.querySelector('[data-fslot="tab|breakfast"]').click();
  ok("switching to a meal without that type clears it, not silently empties the list",
    filter.cat === null && filterRecipes(filter).length > 0,
    `cat=${filter.cat} results=${filterRecipes(filter).length}`);
}

/* --- copy yesterday / last week --------------------------------------- */
function testCopyPrevious(){
  const pick = slot => (RECIPES.find(r => r.slots.includes(slot)) || {}).id;
  const full = () => ({ breakfast: pick("breakfast"), lunch: pick("lunch"), dinner: pick("dinner") });

  // the button names the period
  reset(); tab = "plan";
  const labels = {};
  ["day", "week", "month"].forEach(v => {
    S.view = v; render();
    labels[v] = document.querySelector("[data-copyprev]").textContent.trim();
  });
  ok("the copy button names the period",
    labels.day === "Copy yesterday" && labels.week === "Copy last week" &&
    labels.month === "Copy last month", JSON.stringify(labels));

  // day: copies yesterday onto today
  reset(); tab = "plan"; S.view = "day";
  S.plan["2026-03-01"] = full();
  render();
  document.querySelector("[data-copyprev]").click();
  ok("copy yesterday fills the day on screen",
    JSON.stringify(S.plan["2026-03-02"]) === JSON.stringify(S.plan["2026-03-01"]),
    JSON.stringify(S.plan["2026-03-02"]));

  // it is a copy, not a move
  ok("yesterday is left alone", !!S.plan["2026-03-01"]);

  // and the copy is independent
  S.plan["2026-03-02"].lunch = "changed";
  ok("editing the copy does not touch the original",
    S.plan["2026-03-01"].lunch !== "changed");

  // week: pairs day to day
  reset(); S.view = "week";
  S.plan["2026-02-23"] = full();          // the Monday before
  S.plan["2026-02-25"] = { dinner: pick("dinner") };
  render();
  document.querySelector("[data-copyprev]").click();
  ok("copy last week lands Monday on Monday and Wednesday on Wednesday",
    JSON.stringify(S.plan["2026-03-02"]) === JSON.stringify(S.plan["2026-02-23"]) &&
    JSON.stringify(S.plan["2026-03-04"]) === JSON.stringify(S.plan["2026-02-25"]),
    JSON.stringify(Object.keys(S.plan)));
  ok("days the source had empty are not created",
    !S.plan["2026-03-03"] && !S.plan["2026-03-05"], JSON.stringify(Object.keys(S.plan)));

  // nothing to copy
  reset(); S.view = "week"; render();
  document.querySelector("[data-copyprev]").click();
  ok("copying an empty period changes nothing",
    Object.keys(S.plan).length === 0);

  // an empty source day must not wipe a planned target day
  reset(); S.view = "week";
  S.plan["2026-02-23"] = full();            // last Monday only
  S.plan["2026-03-05"] = { dinner: pick("dinner") };   // this Thursday, already planned
  const keep = JSON.stringify(S.plan["2026-03-05"]);
  render();
  confirms = [];
  document.querySelector("[data-copyprev]").click();
  ok("a planned day is kept when the matching source day was empty",
    JSON.stringify(S.plan["2026-03-05"]) === keep, JSON.stringify(S.plan["2026-03-05"]));
  ok("no confirmation is asked when nothing would be replaced",
    confirms.length === 0, confirms.join(" / "));

  // replacing real work asks first, and declining leaves the plan untouched
  reset(); S.view = "week";
  S.plan["2026-02-23"] = full();
  S.plan["2026-03-02"] = { dinner: pick("dinner") };
  const before = JSON.stringify(S.plan["2026-03-02"]);
  render();
  confirms = []; confirmAnswer = false;
  document.querySelector("[data-copyprev]").click();
  ok("replacing planned days asks first", confirms.length === 1, confirms.join(" / "));
  ok("declining the confirmation changes nothing",
    JSON.stringify(S.plan["2026-03-02"]) === before, JSON.stringify(S.plan["2026-03-02"]));

  confirmAnswer = true;
  document.querySelector("[data-copyprev]").click();
  ok("accepting the confirmation does the copy",
    JSON.stringify(S.plan["2026-03-02"]) === JSON.stringify(S.plan["2026-02-23"]),
    JSON.stringify(S.plan["2026-03-02"]));
}

/* The "Fill with" scope buttons: they must show which one is chosen, and the
   choice must actually steer what fill picks. The original bug was invisible
   selection -- the state changed correctly but nothing on screen moved. */
function testFillScope(){
  tab = "plan"; S.view = "day"; S.cursor = "2026-02-17"; S.scope = null;
  S.plan = {}; render();

  const btns = () => [...document.querySelectorAll("[data-scope]")];
  ok("the fill scopes are rendered", btns().length === 3, btns().length + " buttons");

  const lit = () => btns().filter(b => b.classList.contains("on")).map(b => b.textContent);
  ok("exactly one scope is lit by default", lit().length === 1 && lit()[0] === "Anything",
    lit().join(","));

  // A visibly distinct selected state, computed rather than assumed from CSS text.
  const onBtn = btns().find(b => b.classList.contains("on"));
  const offBtn = btns().find(b => !b.classList.contains("on"));
  const bg = el => getComputedStyle(el).backgroundColor;
  ok("the selected scope looks different from the others", bg(onBtn) !== bg(offBtn),
    "on=" + bg(onBtn) + " off=" + bg(offBtn));

  const hp = btns().find(b => b.textContent === "High protein");
  hp.click();
  ok("clicking a scope selects it", S.scope === "high-protein", String(S.scope));
  ok("the newly selected scope is the lit one",
    lit().length === 1 && lit()[0] === "High protein", lit().join(","));

  // Re-querying after render: the old nodes are gone.
  btns().find(b => b.textContent === "Anything").click();
  ok("the empty-valued 'Anything' button works", S.scope === null, String(S.scope));
  ok("'Anything' is lit again", lit()[0] === "Anything", lit().join(","));

  // The choice has to reach the filling itself.
  S.scope = "high-protein"; render();
  S.plan = {}; document.querySelector("[data-fill]").click();
  const day = S.plan[S.cursor] || {};
  const filled = SLOTS.map(s => [s, BY_ID[day[s]]]).filter(([, r]) => r);
  ok("filling with a scope fills the day", filled.length === 4, filled.length + " slots");
  // Judge each slot against the pool fill was actually allowed to draw from,
  // so the documented "scope would leave nothing" fallback is not read as a bug.
  // Snack is excluded on purpose: it is not filled by fillRange at all, but by
  // topUpProtein, which closes the day's protein gap and ignores the scope.
  const wrong = filled.filter(([slot, r]) =>
    MAIN_SLOTS.includes(slot) && !fillPool(slot).some(p => p.id === r.id));
  ok("a scoped fill picks only from that slot's scoped pool", wrong.length === 0,
    wrong.map(([slot, r]) => slot + "=" + r.name).join(", "));
  const snack = filled.find(([slot]) => slot === "snack");
  ok("the snack is a protein top-up, chosen for protein rather than the scope",
    !snack || snack[1].macros.protein > 0, snack ? snack[1].name : "no snack");
  ok("scoping changes what lands in the day",
    filled.filter(([slot, r]) => r.tags.includes("high-protein")).length >= 3,
    filled.map(([slot, r]) => slot + "=" + r.name + (r.tags.includes("high-protein") ? "*" : "")).join(", "));

  S.scope = null; S.plan = {}; render();
}

/* The Filter row: any number of tags at once, each one narrowing further. */
function testMultiFilter(){
  tab = "recipes";
  Object.assign(filter, { slot: null, cat: null, tags: [], q: "" });
  render();

  const btns = () => [...document.querySelectorAll('[data-ftag^="tab|"]')];
  ok("the filter tags are buttons", btns().length === 3, btns().length + " buttons");
  ok("no select survives for Filter",
    !document.querySelector("[data-tagsel]"), "a tag select is still rendered");

  const count = () => document.querySelectorAll("[data-open]").length;
  const all = count();

  const click = label => btns().find(b => b.textContent === label).click();

  click("Vegetarian");
  const veg = count();
  ok("one tag filters", veg > 0 && veg < all, veg + " of " + all);
  ok("the chosen tag is lit",
    btns().find(b => b.textContent === "Vegetarian").classList.contains("on"), "not lit");

  click("High protein");
  const both = count();
  ok("two tags stay selected together", filter.tags.length === 2, filter.tags.join(","));
  ok("both chosen tags are lit",
    btns().filter(b => b.classList.contains("on")).length === 2, "not both lit");
  // The point of AND: adding a tag can only ever narrow.
  ok("a second tag narrows rather than widens", both > 0 && both <= veg,
    both + " with both vs " + veg + " with one");

  // ...and every survivor genuinely has both tags.
  const shown = filterRecipes(filter);
  const bad = shown.filter(r => !r.tags.includes("vegetarian") || !r.tags.includes("high-protein"));
  ok("every result has both tags", bad.length === 0, bad.map(r => r.name).join(", "));

  click("Vegetarian");
  ok("clicking again removes just that tag",
    filter.tags.length === 1 && filter.tags[0] === "high-protein", filter.tags.join(","));

  click("High protein");
  ok("clearing every tag restores the full list", count() === all, count() + " of " + all);

  // The same controls live in the plan's meal picker, which re-renders through
  // pickSheet rather than render(), so the wiring has to work in both.
  tab = "plan"; S.view = "day"; S.cursor = "2026-02-17"; S.plan = {}; render();
  pickSheet("2026-02-17", "dinner");
  const pbtns = () => [...document.querySelectorAll('[data-ftag^="pick|"]')];
  ok("the picker has the same filter buttons", pbtns().length === 3, pbtns().length + "");
  const pcount = () => document.querySelectorAll(".sheet [data-set]").length;
  const pall = pcount();
  pbtns().find(b => b.textContent === "Vegetarian").click();
  ok("filtering inside the picker narrows it", pcount() > 0 && pcount() < pall,
    pcount() + " of " + pall);
  ok("the picker keeps the button lit after its own re-render",
    pbtns().find(b => b.textContent === "Vegetarian").classList.contains("on"), "not lit");
  ok("the picker filter is independent of the Recipes tab",
    filter.tags.length === 0, filter.tags.join(","));
  closeSheet();
}

/* The recipe sheet's meta line: HTML entities must not be escaped as text. */
function testRecipeMeta(){
  const r = RECIPES.find(x => x.slots.length > 1);
  recipeSheet(r.id);
  const sub = document.querySelector(".sheet .sub").textContent;
  ok("the slot separator renders as a dot, not markup",
    !sub.includes("&middot") && !sub.includes("&amp"), sub);
  ok("the separator is actually there", sub.includes("\u00b7"), sub);
  closeSheet();
}

/* Fill on a day whose mains are all planned. The snack tile is visibly empty,
   so "Fill empty slots" must either close the protein gap or say why not --
   silently reporting "nothing empty" while a tile sits blank reads as broken. */
function testFillTopsUpAPlannedDay(){
  const toastText = () => document.getElementById("toast").textContent;
  tab = "plan"; S.view = "day"; S.cursor = "2026-09-16"; S.scope = null;

  S.plan = {}; render();
  document.querySelector("[data-fill]").click();
  const day = () => S.plan[S.cursor] || {};
  // Brunch is a slot most days do not have, so ask the day what it eats.
  const eaten = () => SLOTS.filter(s => eats(S.cursor, s));
  ok("a clean day fills completely", eaten().every(s => day()[s]), JSON.stringify(day()));

  // Mains planned, snack cleared: the state the app was silently refusing.
  delete S.plan[S.cursor].snack;
  const short = S.goals.protein - totalsOn(S.cursor).protein;
  render();
  document.querySelector("[data-fill]").click();
  ok("filling a mains-only day is not refused",
    toastText() !== "Nothing empty to fill in this view", toastText());
  ok("the empty snack is filled when the day is short on protein",
    short <= 0 || !!day().snack, "short by " + short + "g, snack=" + (day().snack || "none"));
  ok("the top-up closes some of the protein gap",
    short <= 0 || totalsOn(S.cursor).protein > S.goals.protein - short,
    totalsOn(S.cursor).protein + "g vs goal " + S.goals.protein);
  ok("topping up does not disturb the planned mains",
    MAIN_SLOTS.filter(s => eats(S.cursor, s)).every(s => day()[s]), JSON.stringify(day()));

  // A genuinely complete day must still say so rather than pile on snacks.
  document.querySelector("[data-fill]").click();
  ok("a complete day is reported, not refilled",
    toastText() === "Nothing empty to fill in this view", toastText());

  // A day already at its protein goal must not gain a snack it does not need.
  S.plan = {}; render();
  document.querySelector("[data-fill]").click();
  delete S.plan[S.cursor].snack;
  const goals = S.goals;
  S.goals = Object.assign({}, goals, { protein: 1 });
  render();
  document.querySelector("[data-fill]").click();
  ok("a day already on target gains no snack", !day().snack, day().snack || "none");
  ok("...and says so plainly",
    toastText() === "Nothing more to add: every day is on target or full", toastText());
  S.goals = goals;

  S.plan = {}; render();
}

/* The header subtitle and the portions sheet, after both bits of chatter were
   removed. The scaling itself must survive: only the prose went. */
function testChatterRemoved(){
  const hsub = () => document.getElementById("hsub").textContent.trim();

  S.plan = {}; S.cursor = "2026-09-16"; tab = "plan"; S.view = "day"; render();
  document.querySelector("[data-fill]").click();
  tab = "plan"; render();
  ok("the plan header says nothing", hsub() === "", hsub());

  tab = "nutrients"; render();
  ok("the nutrients header says nothing", hsub() === "", hsub());

  tab = "recipes"; render();
  ok("the recipes header still counts recipes", hsub() === RECIPES.length + " recipes", hsub());

  // No days-planned count anywhere, even with a plan in place.
  ok("no planned-days count survives", !/day(s)? planned/.test(document.body.textContent),
    (document.body.textContent.match(/\d+ days? planned/) || ["none"])[0]);

  // The portions sheet: stepper and scaled quantities, no explanatory blurb.
  const r = RECIPES.find(x => x.ingredients.some(i => /^\d/.test(i.display)));
  recipeSheet(r.id, 3);
  const body = document.querySelector(".sheet .body").textContent;
  ok("no portions blurb at n>1", !body.includes("Quantities below make"), "");
  ok("no total-for-n-portions line", !/kcal and \d+ g protein in total/.test(body), "");
  // Read the stepper itself rather than the prose: it uses a real minus sign.
  const stepper = document.querySelector(".sheet .portions");
  ok("the stepper still reports the count",
    stepper && stepper.querySelector("b").textContent === "3",
    stepper ? stepper.textContent.replace(/\s+/g, " ").trim() : "no stepper");

  // The actual point of the stepper still works.
  const line = r.ingredients.find(i => /^\d/.test(i.display));
  const shown = [...document.querySelectorAll(".sheet .ing li")]
    .map(li => li.textContent).find(t => t.includes(scaleDisplay(line.display, 3)));
  ok("quantities are still scaled", !!shown,
    "expected " + scaleDisplay(line.display, 3) + " from " + line.display);
  ok("grams are still scaled", document.querySelector(".sheet .ing .g").textContent
    === scaleGrams(r.ingredients[0].grams, 3) + " g",
    document.querySelector(".sheet .ing .g").textContent);
  ok("macros stay per portion", body.includes("Per portion."), "");
  closeSheet();
  S.plan = {};
}

/* Emptying a list, and starting one with nothing on it. */
function testShoppingClearAndBlank(){
  const toastText = () => document.getElementById("toast").textContent;
  const items = () => (S.shopping ? S.shopping.items.length : -1);

  // A list built from a planned week, so there is something real to clear.
  S.plan = {}; S.view = "week"; S.cursor = "2026-09-16"; tab = "plan"; render();
  document.querySelector("[data-fill]").click();
  S.shopping = null; tab = "shop"; render();

  ok("the empty screen offers both routes",
    !!document.querySelector("[data-newlist]") && !!document.querySelector("[data-blank]"),
    "a starting option is missing");

  // Blank from the empty screen.
  document.querySelector("[data-blank]").click();
  ok("a blank list is created", items() === 0, items() + " items");
  ok("a blank list claims no dates", !S.shopping.from && !S.shopping.to,
    S.shopping.from + " - " + S.shopping.to);
  ok("the header says whose list it is",
    document.querySelector(".card .sub").textContent.startsWith("Your own list"),
    document.querySelector(".card .sub").textContent);

  // Build a real list from the plan.
  const [a, b] = range();
  createList(a, b, true);
  tab = "shop"; render();
  const built = items();
  ok("a list from the plan has items", built > 0, built + " items");
  ok("a list from the plan states its days", !!S.shopping.from,
    document.querySelector(".card .sub").textContent);

  // Clear, declined.
  confirms = []; confirmAnswer = false;
  document.querySelector("[data-clearitems]").click();
  ok("clearing asks first", confirms.length === 1, confirms.join(" / "));
  ok("declining keeps every item", items() === built, items() + " of " + built);

  // Clear, accepted.
  confirmAnswer = true;
  document.querySelector("[data-clearitems]").click();
  ok("clearing empties the list", items() === 0, items() + " items");
  ok("the emptied list stops claiming those days", !S.shopping.from, String(S.shopping.from));
  ok("the list itself still exists to add to", !!S.shopping, "the list was deleted entirely");
  ok("clearing is reported", /Removed \d+ items?/.test(toastText()), toastText());

  // Clearing nothing says so rather than asking a pointless question.
  confirms = [];
  document.querySelector("[data-clearitems]").click();
  ok("clearing an empty list asks nothing", confirms.length === 0, confirms.join(" / "));
  ok("...and says why", toastText() === "The list is already empty", toastText());

  // A blank list must not silently discard a list with things on it.
  createList(a, b, true); tab = "shop"; render();
  confirms = []; confirmAnswer = false;
  document.querySelector("[data-newlist]").click();
  document.querySelector("[data-blank]").click();
  ok("replacing a full list asks first", confirms.length === 1, confirms.join(" / "));
  ok("declining keeps the list", items() > 0, items() + " items");
  closeSheet();

  // The point of a blank list: you can put things on it.
  S.shopping = null; tab = "shop"; render();
  document.querySelector("[data-blank]").click();
  const add = txt => {
    document.getElementById("addi").value = txt;
    document.getElementById("addf").dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true }));
  };
  add("Washing up liquid");
  add("Bin bags");
  ok("items can be added to a blank list", items() === 2, items() + " items");
  ok("added items keep their names",
    S.shopping.items.map(i => i.name).join(", ") === "Washing up liquid, Bin bags",
    S.shopping.items.map(i => i.name).join(", "));
  ok("they survive a re-render", (render(), document.body.textContent.includes("Bin bags")),
    "the item vanished from the page");

  S.shopping = null; S.plan = {}; S.view = "day"; tab = "plan"; render();
}

try { testCatLabels(); } catch (e){ out.push("FAIL  catLabels threw: " + e.message); }
try { testControls(); } catch (e){ out.push("FAIL  controls threw: " + e.message); }
try { testPortions(); } catch (e){ out.push("FAIL  portions threw: " + e.message); }
try { testDashboard(); } catch (e){ out.push("FAIL  dashboard threw: " + e.message); }
try { testClearDay(); } catch (e){ out.push("FAIL  clearDay threw: " + e.message); }
try { testNutrients(); } catch (e){ out.push("FAIL  nutrients threw: " + e.message); }
try { testFilterRules(); } catch (e){ out.push("FAIL  filterRules threw: " + e.message); }
try { testCopyPrevious(); } catch (e){ out.push("FAIL  copyPrevious threw: " + e.message); }
try { testFillScope(); } catch (e){ out.push("FAIL  fillScope threw: " + e.message); }
try { testMultiFilter(); } catch (e){ out.push("FAIL  multiFilter threw: " + e.message); }
try { testRecipeMeta(); } catch (e){ out.push("FAIL  recipeMeta threw: " + e.message); }
try { testFillTopsUpAPlannedDay(); } catch (e){ out.push("FAIL  fillTopUp threw: " + e.message); }
try { testChatterRemoved(); } catch (e){ out.push("FAIL  chatterRemoved threw: " + e.message); }
try { testShoppingClearAndBlank(); } catch (e){ out.push("FAIL  shoppingClear threw: " + e.message); }

const pre = document.createElement("pre");
pre.id = "drv";
pre.textContent = out.join("\n");
document.body.appendChild(pre);
