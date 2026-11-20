// ---------------------------------------------------------------- views
const app = document.getElementById("app");
const aside = app.appendChild(h("aside"));
const main = app.appendChild(h("main"));
main.id = "main"; main.tabIndex = -1;
const state = { q: "", kinds: new Set() };

const entryHaystack = (x) => {
  const e = x.entry;
  return [e.id, e.title, e.project, e.kind, kname(e.kind), ...(e.tags || []), ...(e.samples || []).map((s2) => s2.id + " " + (s2.group || "")), e.aim, e.conclusion].join(" ").toLowerCase();
};
const match = (x) => (!state.kinds.size || state.kinds.has(x.entry.kind)) && (!state.q || entryHaystack(x).includes(state.q));

const sidebar = () => {
  aside.textContent = "";
  const bb = aside.appendChild(h("div", "brandbar"));
  const logo = document.getElementById("logo"); if (logo) { logo.hidden = false; bb.appendChild(logo); }
  bb.appendChild(h("div", null, h("div", "t", "Lab journal"), h("div", "s", "PLSI · Research Orchestrator")));
  const sb = aside.appendChild(h("div", "searchbox"));
  sb.appendChild(icon("search"));
  const inp = sb.appendChild(h("input")); inp.type = "search"; inp.placeholder = "Search entries, samples, tags"; inp.value = state.q; inp.setAttribute("aria-label", "Search the journal");
  sb.appendChild(h("span", "kbd", "/"));
  inp.addEventListener("input", () => { state.q = inp.value.trim().toLowerCase(); list(); });
  const kinds = [...new Set(E.map((x) => x.entry.kind))];
  if (kinds.length > 1) {
    const ch = aside.appendChild(h("div", "chips"));
    for (const k of kinds) {
      const b = kvar(ch.appendChild(h("button", "chipf", h("span", "dot"), kname(k))), k); b.setAttribute("aria-pressed", String(state.kinds.has(k)));
      b.addEventListener("click", () => { state.kinds.has(k) ? state.kinds.delete(k) : state.kinds.add(k); b.setAttribute("aria-pressed", String(state.kinds.has(k))); list(); });
    }
  }
  const nav = aside.appendChild(h("nav", "main"));
  const link = (route, ic, text, n) => { const b = nav.appendChild(h("button", "navlink", icon(ic), text, n !== undefined ? h("span", "n", n) : null)); b.dataset.route = route; b.addEventListener("click", () => go(route)); return b; };
  link("today", "clock", "Today"); link("overview", "home", "All projects"); link("calculators", "calc", "Calculators"); link("plasmids", "plasmid", "Plasmids", PL.length); link("bank", "flask", "Cell bank", (P.bank || { vials: [] }).vials.filter((v) => !v.status || v.status === "frozen").length);
  const tree = aside.appendChild(h("div", "group")); tree.id = "tree";
  aside.appendChild(h("div", "asidefoot", `Updated ${stamp(P.generated_at)}`));
  const list = () => {
    tree.textContent = "";
    tree.appendChild(h("div", "ghead", "Entries"));
    const shown = E.filter(match);
    if (!shown.length) { tree.appendChild(h("p", "empty", E.length ? "Nothing matches." : "No entries yet.")).style.padding = "0 10px"; return; }
    const byProj = new Map();
    for (const x of shown) { const p = x.entry.project || "No project"; if (!byProj.has(p)) byProj.set(p, []); byProj.get(p).push(x); }
    for (const [p, xs] of byProj) {
      const d = tree.appendChild(h("details", "proj")); d.open = true;
      d.appendChild(h("summary", null, icon("chev", { class: "chev" }), p, h("span", "n", xs.length)));
      for (const x of xs) {
        const b = kvar(d.appendChild(h("button", "elink", h("span", "dot"), h("span", "tt", x.entry.title), h("span", "dd", day(x.entry.date).replace(/ \d{4}$/, "")))), x.entry.kind);
        b.dataset.route = "entry/" + x.entry.id; b.title = `${kname(x.entry.kind)} · ${x.entry.title}`;
        b.addEventListener("click", () => go("entry/" + x.entry.id));
      }
    }
    mark();
  };
  list();
  document.addEventListener("keydown", (e) => { if (e.key === "/" && document.activeElement !== inp) { e.preventDefault(); inp.focus(); } });
};
const mark = () => { for (const b of aside.querySelectorAll("[data-route]")) b.toggleAttribute("aria-current", b.dataset.route === current()); for (const b of aside.querySelectorAll("[aria-current]")) b.setAttribute("aria-current", "page"); };

const overview = () => {
  const v = h("div");
  const hero = v.appendChild(h("div", "hero"));
  hero.appendChild(h("p", "eyebrow", "PLSI · Wet lab"));
  hero.appendChild(h("h1", null, "Lab journal"));
  hero.appendChild(h("p", "muted", "Every experiment with its protocol, samples, raw results and the numbers drawn from them. Signed entries never change."));
  const running = E.filter((x) => x.status === "running"), signed = E.filter((x) => x.status === "signed");
  v.appendChild(stats([[E.length, "entries"], [running.length, "running now"], [signed.length, "signed"], [PL.length, "plasmids"]]));
  const grid = v.appendChild(h("div", "grid"));
  // activity: the last 18 weeks
  const days = new Map(); for (const x of E) days.set(x.entry.date, (days.get(x.entry.date) || 0) + 1);
  const heat = h("div", "heat"), today = Date.parse(String(P.generated_at).slice(0, 10)), start = today - (18 * 7 - 1) * 864e5 - (new Date(today).getUTCDay() * 864e5);
  for (let t = start; t <= today; t += 864e5) { const k = new Date(t).toISOString().slice(0, 10), n = days.get(k) || 0; const c = heat.appendChild(h("div", n ? "l" + Math.min(3, n) : null)); c.title = `${day(k)}: ${n} entr${n === 1 ? "y" : "ies"}`; }
  const act = h("div"); act.appendChild(heat); act.appendChild(h("p", "faint", "Entries per day, last 18 weeks")).style.margin = "10px 0 0";
  grid.appendChild(card("Activity", "clock", act, { size: "half" }));
  const counts = new Map(); for (const x of E) counts.set(x.entry.kind, (counts.get(x.entry.kind) || 0) + 1);
  const kb = h("div", "kbars"), mx = Math.max(1, ...counts.values());
  for (const [k, n] of [...counts].sort((a, b) => b[1] - a[1])) { kb.appendChild(h("span", null, kname(k))); kvar(kb.appendChild(h("div", "b")), k).style.width = (n / mx * 100) + "%"; kb.appendChild(h("span", "c", n)); }
  grid.appendChild(card("By experiment", "chart", counts.size ? kb : h("p", "empty", "No entries yet."), { size: "half" }));
  const attention = titledChecks(E);
  if (attention.length) grid.appendChild(card("Worth a second look", "warn", checks(attention.slice(0, 12)), { sub: `${attention.length} from the derived results` }));
  const cards = h("div", "cards");
  for (const x of E.slice(0, 24)) {
    cards.appendChild(entryCard(x, true));
  }
  grid.appendChild(card("Recent", "list", E.length ? cards : h("p", "empty", "No entries yet. Ask PLSI to start one: \"new qPCR entry for today\".")));
  return v;
};
