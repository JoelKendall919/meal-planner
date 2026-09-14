/* How the app boots against a plan holding ids that no longer resolve. */
const out = [];
const ok = (name, pass, detail) =>
  out.push(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? "  -- " + detail : ""}`);

try {
  ok("dead ids are gone from the loaded plan",
    !S.plan["2026-09-16"], JSON.stringify(S.plan["2026-09-16"] || null));
  ok("a day keeps the meals that still exist",
    S.plan["2026-09-17"] && S.plan["2026-09-17"].breakfast === "greek-yoghurt"
      && !S.plan["2026-09-17"].dinner, JSON.stringify(S.plan["2026-09-17"]));
  ok("a day of nothing but dead ids is dropped",
    !S.plan["2026-09-18"], JSON.stringify(S.plan["2026-09-18"] || null));
  ok("an untouched day is left alone",
    S.plan["2026-09-19"] && S.plan["2026-09-19"].lunch === "greek-yoghurt",
    JSON.stringify(S.plan["2026-09-19"]));

  // Every id the plan still holds has to resolve to a real recipe.
  const dangling = [];
  Object.entries(S.plan).forEach(([d, day]) =>
    Object.entries(day).forEach(([slot, id]) => { if (!BY_ID[id]) dangling.push(d + "/" + slot); }));
  ok("no dangling ids survive the load", dangling.length === 0, dangling.join(", "));

  ok("the user is told why their plan changed",
    document.getElementById("toast").classList.contains("on"),
    document.getElementById("toast").textContent);

  // The prune has to be written back, or it recurs on every launch.
  const stored = JSON.parse(localStorage.getItem("mealplanner.v3"));
  ok("the cleaned plan is saved, not just held in memory",
    !stored.plan["2026-09-16"] && !stored.plan["2026-09-18"],
    JSON.stringify(Object.keys(stored.plan)));

  // The actual complaint: filling that day now fills it.
  tab = "plan"; S.view = "day"; S.cursor = "2026-09-16"; render();
  document.querySelector("[data-fill]").click();
  const day = S.plan["2026-09-16"] || {};
  ok("filling the day now fills every slot", SLOTS.every(s => day[s]), JSON.stringify(day));
  ok("...and they are real recipes",
    SLOTS.every(s => BY_ID[day[s]]), SLOTS.map(s => BY_ID[day[s]] ? "ok" : s + "=BAD").join(" "));
} catch (e) {
  out.push("FAIL  stale-plan driver threw: " + e.message);
}

const pre = document.createElement("pre");
pre.id = "drv";
pre.textContent = out.join("\n");
document.body.appendChild(pre);
