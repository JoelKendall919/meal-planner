/* What the smarter fill actually buys, measured against the real catalogue.
 *
 * Throwaway: run it to justify (or kill) the defaults, not as a test.
 */
const out = [];
window.confirm = () => true;
const MON = "2026-03-02", SUN = "2026-03-08";

function reset(){
  S.plan = {}; S.cursor = MON; S.view = "week"; S.scope = null;
  S.leftovers = true; S.maxMin = { week: 0, weekend: 0 };
  S.slotDays = { breakfast: FULL_WEEK(), lunch: FULL_WEEK(), dinner: FULL_WEEK() };
}
const days = () => daysBetween(MON, SUN);

function measure(label, setup, runs){
  runs = runs || 40;
  let cooks = 0, mins = 0, lines = 0, kcal = 0, prot = 0, lo = 0, longest = 0;
  for (let i = 0; i < runs; i++){
    reset();
    setup();
    fillRange();
    const cooked = idsIn(MON, SUN, true);
    cooks += cooked.length;
    // Time at the stove is the cooking only: a leftover is reheated, not made.
    mins += cooked.reduce((n, id) => n + (BY_ID[id].total_min || 0), 0);
    lines += generateList(MON, SUN, false).items.length;
    kcal += days().reduce((n, d) => n + totalsOn(d).kcal, 0) / 7;
    prot += days().reduce((n, d) => n + totalsOn(d).protein, 0) / 7;
    days().forEach(d => SLOTS.forEach(s => { if (isLeftover(slotAt(d, s))) lo++; }));
    // The worst single weekday cook, which is what makes a plan undoable.
    days().filter(d => !isWeekend(d)).forEach(d => MAIN_SLOTS.forEach(s => {
      const r = mealAt(d, s);
      if (r && !isLeftover(slotAt(d, s))) longest = Math.max(longest, r.total_min || 0);
    }));
  }
  const f = x => (x / runs).toFixed(1);
  out.push(`${label.padEnd(30)} ${f(cooks).padStart(5)} cooks  ${f(mins).padStart(6)} min  `
    + `${f(lines).padStart(5)} lines  ${f(kcal).padStart(6)} kcal  ${f(prot).padStart(5)} g  `
    + `${f(lo).padStart(4)} leftovers  worst weeknight ${longest} min`);
}

out.push("A filled week, averaged over 40 runs. Minutes count cooking only.");
out.push("");
measure("everything off", () => { S.leftovers = false; });
measure("leftovers on", () => {});
measure("leftovers + 30 min weeknights", () => { S.maxMin = { week: 30, weekend: 0 }; });
measure("+ breakfast 3 days a week", () => {
  S.maxMin = { week: 30, weekend: 0 };
  S.slotDays.breakfast = [true, false, true, false, true, false, false];
});

const pre = document.createElement("pre");
pre.id = "drv";
pre.textContent = out.join("\n");
document.body.appendChild(pre);
