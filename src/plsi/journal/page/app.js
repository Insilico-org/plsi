// ---------------------------------------------------------------- routing (#overview, #entry/<id>, #plasmid/<name>, #calculators)
const ROUTE = /^(today|overview|calculators|plasmids|bank|entry\/[a-z0-9][a-z0-9_-]{0,63}|plasmid\/[a-z0-9][a-z0-9_-]{0,63}|day\/\d{4}-\d{2}-\d{2}|project\/[a-z0-9-]{1,60})$/;
const current = () => { const r = decodeURIComponent(location.hash.slice(1)); return ROUTE.test(r) ? r : "today"; };
const go = (route) => { if (current() === route && location.hash) render(); else location.hash = route; };
const render = () => {
  const r = current(); main.textContent = "";
  let view;
  if (r.startsWith("entry/")) { const x = E.find((y) => y.entry.id === r.slice(6)); view = x ? entryView(x) : h("p", "empty", "No such entry."); }
  else if (r.startsWith("plasmid/")) { const p = PL.find((y) => y.name === r.slice(8)); view = p ? plasmidView(p) : h("p", "empty", "No such plasmid."); }
  else if (r === "calculators") view = calcView();
  else if (r === "plasmids") view = plasmidsView();
  else if (r === "bank") view = bankView();
  else if (r.startsWith("day/")) view = dayView(r.slice(4));
  else if (r.startsWith("project/")) { const name = projectOf(r.slice(8)); view = name ? projectView(name) : h("p", "empty", "No such project."); }
  else if (r === "overview") { view = h("div"); view.appendChild(mainTabs("overview")); view.appendChild(overview()); }
  else view = dayView(todayIso());
  main.appendChild(view); mark();
  document.title = (r.startsWith("entry/") && view.querySelector("h1") ? view.querySelector("h1").textContent + " · " : "") + "Lab journal";
};
window.addEventListener("hashchange", () => { render(); window.scrollTo(0, 0); });
sidebar(); render();

// a page a command rewrites in place: reload it, back to the same view and scroll; never while someone types
const every = Number.isInteger(P.refresh_seconds) && P.refresh_seconds >= 60 ? P.refresh_seconds : 0;
if (every) {
  const key = "plsi-journal-scroll:" + location.pathname + location.hash;
  try { const y = +sessionStorage.getItem(key); sessionStorage.removeItem(key); if (y > 0) window.scrollTo(0, y); } catch (e) { /* no storage */ }
  let last = Date.now();
  document.addEventListener("input", () => { last = Date.now(); });
  setInterval(() => {
    if (current() === "calculators" || Date.now() - last < 60000 || document.querySelector(".lightbox")) return;
    try { sessionStorage.setItem("plsi-journal-scroll:" + location.pathname + location.hash, String(window.scrollY)); } catch (e) { /* ignore */ }
    location.reload();
  }, every * 1000);
}
