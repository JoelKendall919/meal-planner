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
  const tagSel = document.querySelector("select[data-tagsel]");
  ok("Type is a dropdown", !!cat && cat.tagName === "SELECT");
  ok("Filter is a dropdown", !!tagSel && tagSel.tagName === "SELECT");
  ok("no filter chips left for type or filter",
    !document.querySelector("[data-fcat],[data-tag]"));

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

  const tg = document.querySelector("select[data-tagsel]");
  tg.value = "vegetarian";
  tg.dispatchEvent(new Event("change", { bubbles: true }));
  ok("choosing a filter tag filters the list",
    filter.tag === "vegetarian" &&
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

  const tags = [...document.querySelector("select[data-tagsel]").options]
    .map(o => o.textContent.trim());
  ok("the Filter dropdown offers only the three wanted tags",
    JSON.stringify(tags) === JSON.stringify(["No filter", "Vegetarian", "Light", "High protein"]),
    tags.join(" | "));

  const values = [...document.querySelector("select[data-tagsel]").options]
    .map(o => o.value).filter(Boolean);
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

try { testCatLabels(); } catch (e){ out.push("FAIL  catLabels threw: " + e.message); }
try { testControls(); } catch (e){ out.push("FAIL  controls threw: " + e.message); }
try { testPortions(); } catch (e){ out.push("FAIL  portions threw: " + e.message); }
try { testDashboard(); } catch (e){ out.push("FAIL  dashboard threw: " + e.message); }
try { testClearDay(); } catch (e){ out.push("FAIL  clearDay threw: " + e.message); }
try { testNutrients(); } catch (e){ out.push("FAIL  nutrients threw: " + e.message); }
try { testFilterRules(); } catch (e){ out.push("FAIL  filterRules threw: " + e.message); }
try { testCopyPrevious(); } catch (e){ out.push("FAIL  copyPrevious threw: " + e.message); }

const pre = document.createElement("pre");
pre.id = "drv";
pre.textContent = out.join("\n");
document.body.appendChild(pre);
