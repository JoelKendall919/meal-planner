/* Headless driver for the smarter fill: leftovers, per-slot cadence, a time
 * limit, ingredient overlap and locking.
 *
 * Appended to a copy of the built dist/index.html and run under headless
 * Chrome. Everything here drives the real app rather than a model of it: it
 * calls the real fill, mutates the real state and reads the real DOM back.
 */
const out = [];
const ok = (name, cond, detail) =>
  out.push(`${cond ? "PASS" : "FAIL"}  ${name}${detail ? "  -- " + detail : ""}`);

let confirmAnswer = true;
window.confirm = () => confirmAnswer;

const MON = "2026-03-02";          // a Monday
const SUN = "2026-03-08";

function reset(){
  S.plan = {};
  S.cursor = MON;
  S.view = "week";
  S.scope = null;
  S.leftovers = true;
  S.maxMin = { week: 0, weekend: 0 };
  S.slotDays = { breakfast: FULL_WEEK(), lunch: FULL_WEEK(), dinner: FULL_WEEK(),
                 brunch: NO_DAYS() };
  S.usual = { breakfast: null, brunch: null, lunch: null, dinner: null };
}

const week = () => daysBetween(MON, SUN);
const everySlot = fn => week().forEach(d => SLOTS.forEach(s => fn(d, s)));

function leftoverSlots(){
  const found = [];
  everySlot((d, s) => { if (isLeftover(slotAt(d, s))) found.push([d, s]); });
  return found;
}

/* --- the slot model ---------------------------------------------------- */
function testSlotShapes(){
  reset();
  setMeal(MON, "dinner", "beef-and-black-bean-stir-fry");
  ok("an ordinary meal is still stored as a plain string",
    typeof S.plan[MON].dinner === "string", JSON.stringify(S.plan[MON].dinner));

  setMeal("2026-03-03", "lunch", "beef-and-black-bean-stir-fry", { from: MON + "|dinner" });
  const v = slotAt("2026-03-03", "lunch");
  ok("a leftover keeps the recipe and records where it came from",
    idOf(v) === "beef-and-black-bean-stir-fry" && v.from === MON + "|dinner", JSON.stringify(v));
  ok("a leftover reads as a leftover and not as locked",
    isLeftover(v) && !isLocked(v));
  ok("an old plain-string plan still resolves",
    mealAt(MON, "dinner") && mealAt(MON, "dinner").id === "beef-and-black-bean-stir-fry");
}

/* --- leftovers are eaten but never bought ------------------------------ */
function testLeftoversNotBought(){
  reset();
  const batch = RECIPES.find(r => r.tags.includes("batch") && r.slots.includes("dinner")
    && r.slots.includes("lunch"));
  setMeal(MON, "dinner", batch.id);
  setMeal("2026-03-03", "lunch", batch.id, { from: MON + "|dinner" });

  const all = idsIn(MON, SUN);
  const cooked = idsIn(MON, SUN, true);
  ok("nutrition counts both servings", all.filter(id => id === batch.id).length === 2);
  ok("shopping counts the cooking only", cooked.filter(id => id === batch.id).length === 1,
    JSON.stringify(cooked));

  // The figure that actually matters: the same dish planned twice as two real
  // cooks must buy twice, so the saving has to come from the leftover marker
  // and not from the list quietly merging duplicates.
  const withLeftover = generateList(MON, SUN, true);
  setMeal("2026-03-03", "lunch", batch.id);          // same dish, cooked again
  const cookedTwice = generateList(MON, SUN, true);
  const grams = list => list.items.reduce((n, i) => n + (parseFloat(i.qty) || 0), 0);
  ok("cooking it twice buys more than cooking it once",
    grams(cookedTwice) > grams(withLeftover),
    `leftover ${grams(withLeftover)} vs cooked ${grams(cookedTwice)}`);
}

function testFillMakesLeftovers(){
  reset();
  fillRange();
  const found = leftoverSlots();
  ok("filling a week plans some leftovers", found.length > 0, `${found.length} found`);
  const bad = found.filter(([d, s]) => {
    const v = slotAt(d, s);
    const parts = String(v.from).split("|");
    const src = slotAt(parts[0], parts[1]);
    return !src || idOf(src) !== idOf(v) || isLeftover(src)
      || parts[0] !== addDays(d, -1) || !BY_ID[idOf(v)].tags.includes("batch");
  });
  ok("every leftover points at yesterday's batch cook of the same dish",
    !bad.length, JSON.stringify(bad));
  const sameDay = week().filter(d => {
    const ids = MAIN_SLOTS.map(s => idOf(slotAt(d, s))).filter(Boolean);
    return new Set(ids).size !== ids.length;
  });
  ok("no day eats the same dish twice", !sameDay.length, JSON.stringify(sameDay));

  reset();
  S.leftovers = false;
  fillRange();
  ok("turning leftovers off plans none", !leftoverSlots().length);
}

function testLeftoversStayHonest(){
  reset();
  fillRange();
  const found = leftoverSlots();
  if (!found.length){ ok("leftovers exist to test", false); return; }
  const [date, slot] = found[0];
  const parts = String(slotAt(date, slot).from).split("|");

  unsetMeal(parts[0], parts[1]);
  ok("removing the cooked meal removes its leftovers",
    !takenAt(date, slot), JSON.stringify(slotAt(date, slot)));

  reset();
  fillRange();
  const again = leftoverSlots();
  if (!again.length){ ok("leftovers exist to test twice", false); return; }
  const [d2, s2] = again[0];
  const p2 = String(slotAt(d2, s2).from).split("|");
  const other = RECIPES.find(r => r.slots.includes(p2[1]) && r.id !== idOf(slotAt(d2, s2)));
  setMeal(p2[0], p2[1], other.id);
  ok("changing the cooked meal removes its leftovers", !takenAt(d2, s2));

  // The stored form is what gets loaded next time, so the guard has to hold
  // against a plan that was hand-edited rather than one the app just built.
  reset();
  setMeal(MON, "dinner", "beef-and-black-bean-stir-fry");
  S.plan["2026-03-03"] = { lunch: { id: "beef-and-black-bean-stir-fry", from: MON + "|breakfast" } };
  const dropped = prunePlan(S.plan);
  ok("a leftover of a meal that was never cooked is pruned on load",
    dropped === 1 && !takenAt("2026-03-03", "lunch"), "dropped " + dropped);
}

/* --- cadence ------------------------------------------------------------ */
function testCadence(){
  reset();
  // Breakfast on Monday, Wednesday and Friday only.
  S.slotDays.breakfast = [true, false, true, false, true, false, false];
  fillRange();
  const planned = week().filter(d => takenAt(d, "breakfast"));
  ok("breakfast is only planned on the days you eat it",
    planned.length === 3 && planned.every(d => [0, 2, 4].includes(dowIdx(d))),
    JSON.stringify(planned));
  ok("the other main meals are untouched",
    week().every(d => takenAt(d, "lunch") && takenAt(d, "dinner")));

  // A day that skips breakfast still has to land near the calorie goal: the
  // missing meal's share has to go somewhere, or those days come in starving.
  const off = week().filter(d => !takenAt(d, "breakfast"));
  const short = off.filter(d => totalsOn(d).kcal < S.goals.kcal * 0.8);
  ok("days without breakfast still reach the calorie goal", !short.length,
    JSON.stringify(off.map(d => d + ":" + totalsOn(d).kcal)));

  // With nothing left open, fill must say so rather than claim to have worked.
  const before = JSON.stringify(S.plan);
  fillRange();
  ok("a fully planned week is not disturbed by filling again",
    JSON.stringify(S.plan) === before);
}

function testCadenceUI(){
  reset();
  S.slotDays.breakfast = [false, false, false, false, false, false, false];
  S.cursor = MON; S.view = "day";
  render();
  const tiles = document.querySelectorAll(".tile");
  const bTile = tiles[0].textContent;
  ok("a day you skip breakfast says so rather than nagging",
    /not on the menu|Not eaten today/.test(bTile), bTile.slice(0, 80));
  ok("you can still add one by hand",
    /Add one anyway/.test(tiles[0].innerHTML));

  S.view = "week"; render();
  ok("the week grid marks the meal as not eaten",
    /not eaten/.test(document.querySelector(".wk").innerHTML));
}

/* --- time in the kitchen ------------------------------------------------ */
function testTimeCap(){
  reset();
  S.maxMin = { week: 30, weekend: 0 };
  fillRange();
  const over = [];
  week().forEach(d => MAIN_SLOTS.forEach(s => {
    const r = mealAt(d, s);
    if (r && !isWeekend(d) && !isLeftover(slotAt(d, s)) && r.total_min > 30)
      over.push(d + " " + s + " " + r.name + " " + r.total_min);
  }));
  ok("weeknight meals respect the limit", !over.length, JSON.stringify(over));

  // Whether any one weekend happens to draw a long recipe is chance, so ask
  // over enough weeks that "the cap leaked into the weekend" would show up.
  let longWeekends = 0;
  for (let i = 0; i < 20; i++){
    S.plan = {}; S.maxMin = { week: 30, weekend: 0 };
    fillRange();
    if (week().filter(isWeekend).some(d => MAIN_SLOTS.some(s =>
      mealAt(d, s) && mealAt(d, s).total_min > 30))) longWeekends++;
  }
  ok("weekends are still allowed a long cook", longWeekends >= 15,
    longWeekends + "/20 weekends had one");

  // A limit no recipe can meet must not strand the slot: an unfillable day is a
  // worse outcome than a meal that misses a preference.
  reset();
  S.maxMin = { week: 1, weekend: 1 };
  fillRange();
  ok("an impossible limit still fills the week",
    week().every(d => MAIN_SLOTS.filter(s => eats(d, s)).every(s => takenAt(d, s))));
}

/* --- ingredient overlap ------------------------------------------------- */
function distinctPerishables(){
  const set = new Set();
  idsIn(MON, SUN, true).forEach(id => perishables(BY_ID[id]).forEach(f => set.add(f)));
  return set.size;
}

function testOverlap(){
  reset();
  ok("staples are left out of the overlap count",
    perishables(BY_ID["beef-and-black-bean-stir-fry"]).every(f => FOODS[f].aisle !== "cupboard"));

  const pantry = new Set(perishables(BY_ID["beef-and-black-bean-stir-fry"]));
  const self = overlapWith(BY_ID["beef-and-black-bean-stir-fry"], pantry);
  ok("a recipe fully overlaps its own ingredients", self === pantry.size,
    self + " of " + pantry.size);
  ok("an empty pantry overlaps nothing",
    overlapWith(BY_ID["beef-and-black-bean-stir-fry"], new Set()) === 0);

  // Measured rather than asserted: run the real fill repeatedly with the
  // preference on and off, and compare how many different perishables a week
  // ends up needing. Fewer means less half-used food going off in the fridge.
  //
  // The sample is large because the answer is noisy: fill picks at random among
  // equally good meals, and at 40 weeks a run the difference wandered either
  // side of the threshold and made this check flap.
  const sample = worth => {
    const runs = 150;
    let total = 0;
    for (let i = 0; i < runs; i++){
      reset();
      S.leftovers = false;            // isolate overlap from the other saving
      OVERLAP_WORTH = worth;
      fillRange();
      total += distinctPerishables();
    }
    return total / runs;
  };
  const withOverlap = sample(5);
  const without = sample(0);
  // A real saving, not a rounding error: the weight is tuned so a week needs
  // meaningfully fewer separate perishables, which is what stops half a bunch of
  // coriander going off in the fridge.
  ok("preferring shared ingredients narrows the week's shopping",
    without - withOverlap >= 1,
    `${withOverlap.toFixed(1)} vs ${without.toFixed(1)} distinct perishables`);
  OVERLAP_WORTH = 5;

  // It must not buy that saving with your food: calories and protein are the
  // point of the app, and a thriftier week that misses them is not better.
  reset();
  fillRange();
  const days = week().filter(d => mealsOn(d).length);
  const avg = k => days.reduce((n, d) => n + totalsOn(d)[k], 0) / days.length;
  ok("calories still land near the goal",
    Math.abs(avg("kcal") - S.goals.kcal) < S.goals.kcal * 0.15,
    Math.round(avg("kcal")) + " vs " + S.goals.kcal);
  ok("protein is not sacrificed for tidy shopping", avg("protein") > 90,
    Math.round(avg("protein")) + " g");
}

/* --- locking ------------------------------------------------------------ */
function testLocking(){
  reset();
  fillRange();
  const keep = idOf(slotAt(MON, "dinner"));
  toggleLock(MON, "dinner");
  ok("locking marks the slot", isLocked(slotAt(MON, "dinner")));
  ok("locking keeps the meal", idOf(slotAt(MON, "dinner")) === keep);

  clearDay(MON);
  ok("clearing a day keeps the locked meal",
    idOf(slotAt(MON, "dinner")) === keep, JSON.stringify(S.plan[MON]));
  ok("clearing a day removes everything else",
    !takenAt(MON, "lunch") && !takenAt(MON, "breakfast"));

  clearRange();
  ok("clearing the week keeps the locked meal", idOf(slotAt(MON, "dinner")) === keep);
  ok("clearing the week removes the rest",
    !week().some(d => MAIN_SLOTS.some(s => (d !== MON || s !== "dinner") && takenAt(d, s))));

  toggleLock(MON, "dinner");
  ok("unlocking returns it to a plain meal",
    !isLocked(slotAt(MON, "dinner")) && typeof slotAt(MON, "dinner") === "string",
    JSON.stringify(slotAt(MON, "dinner")));
  clearDay(MON);
  ok("an unlocked meal clears normally", !takenAt(MON, "dinner"));

  // Choosing a different meal by hand is deliberate, so the slot stays protected.
  reset();
  setMeal(MON, "dinner", "beef-and-black-bean-stir-fry");
  toggleLock(MON, "dinner");
  const other = RECIPES.find(r => r.slots.includes("dinner")
    && r.id !== "beef-and-black-bean-stir-fry");
  setMeal(MON, "dinner", other.id);
  ok("swapping a locked meal keeps the lock", isLocked(slotAt(MON, "dinner")));
}

function testLockingUI(){
  reset();
  setMeal(MON, "dinner", "beef-and-black-bean-stir-fry");
  S.cursor = MON; S.view = "day"; render();
  const tile = [...document.querySelectorAll(".tile")]
    .find(t => /dinner/i.test(t.querySelector(".slotname").textContent));
  const lock = tile.querySelector("[data-lock]");
  ok("a planned meal offers a lock", !!lock && lock.textContent.trim() === "Lock");
  lock.click();
  const after = [...document.querySelectorAll(".tile")]
    .find(t => /dinner/i.test(t.querySelector(".slotname").textContent));
  ok("the tile shows it is locked", /locked/.test(after.textContent), after.textContent.slice(0, 90));
  ok("and offers to unlock it",
    after.querySelector("[data-lock]").textContent.trim() === "Unlock");
}

/* --- leftovers survive being copied ------------------------------------- */
function testCopyPrevious(){
  reset();
  fillRange();
  const found = leftoverSlots();
  if (!found.length){ ok("leftovers exist to copy", false); return; }
  S.cursor = addDays(MON, 7);
  confirmAnswer = true;
  copyPrevious();
  const copied = [];
  daysBetween(addDays(MON, 7), addDays(SUN, 7)).forEach(d =>
    SLOTS.forEach(s => { if (isLeftover(slotAt(d, s))) copied.push([d, s]); }));
  ok("copying a week carries its leftovers", copied.length > 0, copied.length + " found");
  const broken = copied.filter(([d, s]) => {
    const parts = String(slotAt(d, s).from).split("|");
    return parts[0] !== addDays(d, -1) || idOf(slotAt(parts[0], parts[1])) !== idOf(slotAt(d, s));
  });
  ok("copied leftovers point at the copied cook, not last week's",
    !broken.length, JSON.stringify(broken));
  ok("nothing in the copied week is orphaned", prunePlan(S.plan) === 0);
}

/* --- the settings sheet ------------------------------------------------- */
function testSettingsSheet(){
  reset();
  S.cursor = MON; S.view = "week"; render();
  document.querySelector("[data-fillset]").click();
  ok("the settings sheet opens", /Fill settings/.test(sheet.innerHTML));
  const boxes = sheet.querySelectorAll("[data-slotday]");
  ok("every main meal has a box for every day", boxes.length === MAIN_SLOTS.length * 7,
    boxes.length + " boxes");
  // Brunch is the exception: it is opted into, so it starts on no day.
  const daily = [...boxes].filter(b => b.dataset.slotday.split("|")[0] !== "brunch");
  ok("the meals you eat daily all start ticked",
    daily.every(b => b.classList.contains("on")));

  sheet.querySelector('[data-slotday="breakfast|1"]').click();
  ok("unticking a day is remembered", S.slotDays.breakfast[1] === false);
  ok("the sheet stays open and redraws",
    !sheet.querySelector('[data-slotday="breakfast|1"]').classList.contains("on"));

  sheet.querySelector('[data-maxmin="week|30"]').click();
  ok("a time limit is remembered", S.maxMin.week === 30);
  ok("the chosen limit is the one highlighted",
    sheet.querySelector('[data-maxmin="week|30"]').classList.contains("on"));

  sheet.querySelector('[data-leftovers=""]').click();
  ok("leftovers can be turned off", S.leftovers === false);
  sheet.querySelector('[data-leftovers="1"]').click();
  ok("and back on", S.leftovers === true);

  closeSheet(); render();
  const btn = document.querySelector("[data-fillset]").textContent;
  ok("the plan page summarises the settings",
    /breakfast 6\/7/.test(btn) && /30 min/.test(btn), btn.trim());

  reset(); render();
  ok("defaults read plainly",
    /every meal, every day/.test(document.querySelector("[data-fillset]").textContent));
}

/* --- pinning a usual meal ------------------------------------------------ */
function testPinnedMeals(){
  reset();
  const pot = RECIPES.find(r => r.slots.includes("breakfast") && /yoghurt/i.test(r.name));
  ok("the catalogue has a yoghurt breakfast to pin", !!pot, pot && pot.name);

  S.usual.breakfast = pot.id;
  fillRange();
  const days = daysBetween(MON, SUN);
  const bf = days.map(d => idOf(slotAt(d, "breakfast")));
  ok("every breakfast is the pinned meal",
    bf.every(id => id === pot.id), new Set(bf).size + " distinct");
  // The rest of the day must still be planned around it.
  const kcal = days.map(d => totalsOn(d).kcal);
  ok("days still land on the calorie goal with a pin",
    kcal.every(k => k > S.goals.kcal * 0.9 && k < S.goals.kcal * 1.1),
    Math.min.apply(null, kcal) + "-" + Math.max.apply(null, kcal));
  const lunches = new Set(days.map(d => idOf(slotAt(d, "lunch"))));
  ok("pinning one slot does not flatten the others", lunches.size >= 4, lunches.size);

  // A pin beats the scope and the time limit: you asked for it by name.
  reset();
  S.usual.breakfast = pot.id;
  S.maxMin = { week: 20, weekend: 20 };
  S.scope = "high-protein";
  fillRange();
  ok("a pin overrules the scope and the time limit",
    idOf(slotAt(MON, "breakfast")) === pot.id,
    (mealAt(MON, "breakfast") || {}).name);

  // A pinned slot is not something leftovers may claim.
  reset();
  S.usual.lunch = "ham-and-cheese-sandwich";
  S.leftovers = true;
  fillRange();
  const stolen = days.filter(d => {
    const v = slotAt(d, "lunch");
    return idOf(v) !== "ham-and-cheese-sandwich" || isLeftover(v);
  });
  ok("leftovers never take a pinned slot", stolen.length === 0, stolen.join(", "));

  // A pin left pointing at a dead id must not strand the slot.
  reset();
  S.usual.breakfast = "no-such-recipe-xyz";
  ok("a stale pin resolves to nothing", usualFor("breakfast") === null);
  fillRange();
  ok("a stale pin still leaves breakfast planned",
    !!mealAt(MON, "breakfast"), (mealAt(MON, "breakfast") || {}).name);
}

function testPinnedMealsUI(){
  reset(); render();
  document.querySelector("[data-fillset]").click();
  const btn = sheet.querySelector('[data-usual="breakfast"]');
  ok("the settings sheet offers a breakfast pin", !!btn);
  ok("it starts out saying nothing is pinned",
    btn.textContent.trim() === "None", btn.textContent.trim());
  // The four rows are a column of choices, so their buttons have to line up.
  const xs = [...sheet.querySelectorAll(".facet.pin .sec")]
    .map(b => b.getBoundingClientRect().x);
  ok("the pin buttons line up", Math.max.apply(null, xs) - Math.min.apply(null, xs) < 0.5,
    "spread " + (Math.max.apply(null, xs) - Math.min.apply(null, xs)).toFixed(2) + "px");

  // Pinning uses the plan page's picker, not a dropdown of names.
  btn.click();
  ok("tapping it opens the meal picker", !!sheet.querySelector('[data-search]'));
  ok("the picker knows what it is for", sheet.dataset.usual === "breakfast");
  ok("it is titled for the slot",
    /always have for breakfast/i.test(sheet.querySelector("h1").textContent),
    sheet.querySelector("h1").textContent.trim());
  ok("it opens filtered to that slot",
    sheet.querySelectorAll("[data-set]").length
      === RECIPES.filter(r => r.slots.includes("breakfast")).length,
    sheet.querySelectorAll("[data-set]").length + " rows");
  // The rows carry the numbers a dropdown could not.
  const first = sheet.querySelector("[data-set]").textContent;
  ok("rows show calories and protein", /kcal/.test(first) && /\dg/.test(first),
    first.replace(/\s+/g, " ").trim().slice(0, 60));

  // Searching must not lose the fact that this is a pin, not a day.
  const q = sheet.querySelector("[data-search]");
  q.value = "yoghurt";
  q.dispatchEvent(new Event("input", { bubbles: true }));
  ok("filtering keeps it in pin mode", sheet.dataset.usual === "breakfast");
  const pot = [...sheet.querySelectorAll("[data-set]")]
    .find(b => b.dataset.set === "fruit-and-yoghurt-pot");
  ok("the search finds the yoghurt pot", !!pot);

  pot.click();
  ok("choosing one records it", S.usual.breakfast === "fruit-and-yoghurt-pot",
    S.usual.breakfast);
  ok("and returns to the settings",
    /Fill settings/.test(sheet.querySelector("h1").textContent));
  const btn2 = sheet.querySelector('[data-usual="breakfast"]');
  ok("the control now names the meal and its calories",
    /Fruit and yoghurt pot/.test(btn2.textContent) && /294 kcal/.test(btn2.textContent),
    btn2.textContent.trim());
  ok("and marks itself as set", /\bon\b/.test(btn2.className), btn2.className);
  ok("the sheet counts what pinning costs",
    /1 pinned, taking \d+ kcal/.test(sheet.textContent), usualNote());

  closeSheet(); render();
  ok("the plan button names the pinned meal",
    /breakfast is always/.test(document.querySelector("[data-fillset]").textContent),
    document.querySelector("[data-fillset]").textContent.trim());

  // And it can be taken off again from inside the picker.
  document.querySelector("[data-fillset]").click();
  sheet.querySelector('[data-usual="breakfast"]').click();
  ok("the picker shows what is currently pinned",
    /Fruit and yoghurt pot/.test(sheet.querySelector(".mealname").textContent));
  sheet.querySelector("[data-unusual]").click();
  ok("stop pinning goes back to choosing", S.usual.breakfast === null);
  ok("and the note says so", /Nothing pinned/.test(usualNote()), usualNote());
  closeSheet();
}

/* Choosing in one picker must never act on the other. */
function testPickersStaySeparate(){
  reset();
  S.view = "day";
  S.usual.breakfast = "fruit-and-yoghurt-pot";
  render();
  const pick = document.querySelector("[data-pick]");
  pick.click();
  ok("the plan picker is not in pin mode", sheet.dataset.usual === undefined,
    String(sheet.dataset.usual));
  ok("it knows its day and slot",
    sheet.dataset.date === MON && !!sheet.dataset.slot, sheet.dataset.date);
  const q = sheet.querySelector("[data-search]");
  q.value = "eggs";
  q.dispatchEvent(new Event("input", { bubbles: true }));
  ok("filtering keeps the day", sheet.dataset.date === MON);
  const row = sheet.querySelector("[data-set]");
  const chosen = row.dataset.set;
  row.click();
  ok("choosing plans that day", idOf(slotAt(MON, "breakfast")) === chosen,
    JSON.stringify(S.plan[MON]));
  ok("and leaves the pin alone", S.usual.breakfast === "fruit-and-yoghurt-pot");
  reset();
}


/* --- brunch ------------------------------------------------------------- */

const WEEKEND = [5, 6];
function brunchOn(days){
  S.slotDays.brunch = NO_DAYS();
  days.forEach(i => { S.slotDays.brunch[i] = true; });
}

function testBrunch(){
  reset();
  brunchOn(WEEKEND);
  fillRange();
  const days = week();
  const weekend = days.filter(isWeekend);
  const weekdays = days.filter(d => !isWeekend(d));

  ok("every brunch day gets a brunch",
    weekend.every(d => !!mealAt(d, "brunch")),
    weekend.map(d => (mealAt(d, "brunch") || {}).name).join(", "));
  // The whole point: it replaces two meals rather than being a fourth.
  ok("a brunch day has no breakfast or lunch",
    weekend.every(d => !takenAt(d, "breakfast") && !takenAt(d, "lunch")));
  ok("weekdays are untouched",
    weekdays.every(d => takenAt(d, "breakfast") && takenAt(d, "lunch")
      && !takenAt(d, "brunch")));
  ok("brunch days still hit the calorie goal",
    weekend.every(d => {
      const k = totalsOn(d).kcal;
      return k > S.goals.kcal * 0.9 && k < S.goals.kcal * 1.1;
    }),
    weekend.map(d => totalsOn(d).kcal).join("/"));

  // A brunch is one meal doing the work of two, so it has to be bigger than the
  // breakfasts it replaces or the day is carried entirely by dinner.
  const brunchKcal = weekend.map(d => mealAt(d, "brunch").macros.kcal);
  const bfKcal = weekdays.map(d => mealAt(d, "breakfast").macros.kcal);
  const mean = xs => xs.reduce((a, b) => a + b, 0) / xs.length;
  ok("a brunch is bigger than a breakfast",
    mean(brunchKcal) > mean(bfKcal) * 1.4,
    Math.round(mean(brunchKcal)) + " vs " + Math.round(mean(bfKcal)));

  // ...and made of things you would actually eat at eleven in the morning.
  ok("no roasts or curries are served as brunch",
    weekend.every(d => ["roasts", "curries", "soups"]
      .indexOf(mealAt(d, "brunch").category) === -1),
    weekend.map(d => mealAt(d, "brunch").category).join(", "));
}

function testBrunchKeepsWhatYouPlanned(){
  // Plan a normal Saturday first, then switch brunch on for that day.
  reset();
  fillRange();
  const sat = week().filter(isWeekend)[0];
  const had = idOf(slotAt(sat, "breakfast"));
  ok("the Saturday breakfast was planned", !!had);

  brunchOn(WEEKEND);
  ok("switching brunch on does not delete it", idOf(slotAt(sat, "breakfast")) === had);
  ok("and it is still on screen", visibleSlots(sat).indexOf("breakfast") !== -1,
    visibleSlots(sat).join(", "));
  // An empty replaced slot, though, should get out of the way.
  const mon = MON;
  brunchOn([0]);
  clearDayMeals(mon);
  ok("an empty breakfast is hidden on a brunch day",
    visibleSlots(mon).indexOf("breakfast") === -1, visibleSlots(mon).join(", "));
  reset();
}

function testBrunchTakesLeftovers(){
  reset();
  brunchOn(WEEKEND);
  // Saturday's brunch turning up again on Sunday is the common case: most batch
  // dinners are curries and pasta, which are not brunch. Sample wide enough
  // that the check is about the feature rather than about the draw.
  let found = 0;
  const WEEKS = 250;
  for (let i = 0; i < WEEKS; i++){
    S.plan = {};
    fillRange();
    week().forEach(d => { if (isLeftover(slotAt(d, "brunch"))) found++; });
  }
  ok("a brunch can be eaten again as leftovers", found >= 20,
    found + " in " + WEEKS + " weeks");
  reset();
}

function testOldPlansLoadWithoutBrunch(){
  // A plan saved before brunch existed has no brunch key at all. Reading a
  // missing day as "yes" -- which is right for every other meal -- would load
  // it with breakfast and lunch gone from all seven days.
  const before = localStorage.getItem(KEY);
  try {
    localStorage.setItem(KEY, JSON.stringify({
      plan: {}, goals: S.goals,
      slotDays: { breakfast: FULL_WEEK(), lunch: FULL_WEEK(), dinner: FULL_WEEK() },
    }));
    const days = normaliseSlotDays(JSON.parse(localStorage.getItem(KEY)).slotDays);
    ok("an old save has brunch on no day",
      days.brunch.every(v => v === false), JSON.stringify(days.brunch));
    ok("and keeps its other meals every day",
      days.breakfast.every(Boolean) && days.lunch.every(Boolean));
  } finally {
    if (before === null) localStorage.removeItem(KEY); else localStorage.setItem(KEY, before);
  }
}

function testBrunchUI(){
  reset();
  brunchOn(WEEKEND);
  render();
  fillSettingsSheet();
  const sheet = document.querySelector(".sheet");
  const box = s => Array.prototype.slice.call(
    sheet.querySelectorAll("[data-slotday]"))
    .filter(b => b.dataset.slotday.split("|")[0] === s);
  const boxes = box("brunch");
  ok("the settings sheet has a brunch row", boxes.length === 7, boxes.length + " boxes");
  ok("the weekend boxes are on",
    boxes[5].classList.contains("on") && boxes[6].classList.contains("on"));
  // The days brunch overrules must say so rather than silently disagreeing.
  const bf = box("breakfast");
  ok("breakfast reads as overruled on a brunch day",
    bf[5].classList.contains("over") && !bf[0].classList.contains("over"),
    bf[5].className);
  ok("the summary names the brunch days", /brunch Sat, Sun/.test(fillSummary()),
    fillSummary());
  sheet.remove();
  reset();
}


function testPickerKeepsTheSearchBox(){
  // The bug this guards: a filter change rebuilt the whole sheet, so the input
  // you were typing into was destroyed and recreated. A browser cannot keep
  // focus on an element that no longer exists, and on a phone that takes the
  // keyboard down -- the search simply did not work.
  reset(); render();
  document.querySelector("[data-fillset]").click();
  sheet.querySelector('[data-usual="breakfast"]').click();
  const before = sheet;
  const q = sheet.querySelector("[data-search]");
  q.focus();
  "kedg".split("").forEach(ch => {
    q.value += ch;
    q.dispatchEvent(new Event("input", { bubbles: true }));
  });
  ok("typing does not replace the sheet", document.querySelector(".sheet") === before);
  ok("typing does not replace the search box",
    sheet.querySelector("[data-search]") === q);
  ok("the search box keeps focus", document.activeElement === q);
  ok("and the results still narrow", sheet.querySelectorAll("[data-set]").length === 1,
    sheet.querySelector("[data-count]").textContent);

  // The Type dropdown must not destroy it either.
  q.value = ""; q.dispatchEvent(new Event("input", { bubbles: true }));
  const sel = sheet.querySelector("[data-fcatsel]");
  sel.value = "eggs";
  sel.dispatchEvent(new Event("change", { bubbles: true }));
  ok("choosing a type does not replace the search box",
    sheet.querySelector("[data-search]") === q);
  ok("choosing a type narrows the list",
    [...sheet.querySelectorAll("[data-set]")].every(r => BY_ID[r.dataset.set].category === "eggs"),
    sheet.querySelectorAll("[data-set]").length + " rows");

  // A meal chip changes which types exist, so the facets must redraw.
  sheet.querySelector('[data-fslot="pick|dinner"]').click();
  const types = [...sheet.querySelectorAll("[data-fcatsel] option")].map(o => o.value);
  ok("the type list follows the meal", types.indexOf("roasts") !== -1, types.join(","));
  ok("the search box survives that too", sheet.querySelector("[data-search]") === q);
  reset();
}

/* --- run ---------------------------------------------------------------- */
[testSlotShapes, testLeftoversNotBought, testFillMakesLeftovers, testLeftoversStayHonest,
 testCadence, testCadenceUI, testTimeCap, testOverlap, testLocking, testLockingUI,
 testCopyPrevious, testSettingsSheet,
 testPinnedMeals, testPinnedMealsUI, testPickersStaySeparate,
 testPickerKeepsTheSearchBox,
 testBrunch, testBrunchKeepsWhatYouPlanned, testBrunchTakesLeftovers,
 testOldPlansLoadWithoutBrunch, testBrunchUI].forEach(fn => {
  try { fn(); }
  catch (err){ ok(fn.name + " threw", false, String(err && err.stack || err)); }
});

const pre = document.createElement("pre");
pre.id = "drv";
pre.textContent = out.join("\n") + `\n\n${out.filter(l => l.startsWith("PASS")).length}/${
  out.length} checks passed`;
document.body.appendChild(pre);
