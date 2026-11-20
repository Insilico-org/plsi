// ---------------------------------------------------------------- projects, the day, bench timers
const slug = (name) => String(name || "no project").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "no-project";
const PROJECTS = [...new Set(E.map((x) => x.entry.project || "No project"))];
const projectOf = (sl) => PROJECTS.find((p) => slug(p) === sl);
const pad2 = (n) => String(n).padStart(2, "0");
const isoDay = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const todayIso = () => isoDay(new Date());
const shift = (iso, n) => { const [y, m, d] = iso.split("-").map(Number); return isoDay(new Date(y, m - 1, d + n)); };
const longDay = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" }); };
const DAYS = new Map((Array.isArray(P.days) ? P.days : []).map((d) => [d.date, d]));
const nextStep = (e) => (e.protocol || []).find((p) => !p.done);

const mainTabs = (active) => {
  const bar = h("nav", "mtabs no-print"); bar.setAttribute("role", "tablist");
  const tab = (route, label, ic, n) => {
    const b = bar.appendChild(h("button", null, ic ? icon(ic) : null, label, n !== undefined ? h("span", "n", n) : null));
    b.setAttribute("role", "tab"); b.setAttribute("aria-selected", String(route === active)); b.addEventListener("click", () => go(route));
  };
  tab("today", "Today", "clock"); tab("overview", "All projects", "home", E.length);
  for (const p of PROJECTS) tab("project/" + slug(p), p, null, E.filter((x) => (x.entry.project || "No project") === p).length);
  return bar;
};

// timers: a step's minutes, counted down in the page; kept in localStorage so a reload of the page resumes them
const TKEY = "plsi-journal-timers";
const loadTimers = () => { try { return JSON.parse(localStorage.getItem(TKEY) || "[]"); } catch (e) { return []; } };
const saveTimers = (t) => { try { localStorage.setItem(TKEY, JSON.stringify(t)); } catch (e) { /* no storage: timers last until reload */ } };
let timers = loadTimers();
const dock = document.body.appendChild(h("div", "timers"));
let beeped = new Set();
const beep = () => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.35, 0.7].forEach((t) => { const o = ctx.createOscillator(), g = ctx.createGain(); o.frequency.value = 880; o.connect(g); g.connect(ctx.destination);
      g.gain.setValueAtTime(0.0001, ctx.currentTime + t); g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + t + 0.3); o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 0.32); });
  } catch (e) { /* no audio */ }
};
const drawTimers = () => {
  dock.textContent = "";
  const nowMs = Date.now();
  for (const t of timers) {
    const left = Math.max(0, Math.round((t.end - nowMs) / 1000)), done = left === 0;
    const row = dock.appendChild(h("div", "timer" + (done ? " done" : "")));
    row.appendChild(h("div", "lb", t.label));
    row.appendChild(h("span", "ct", done ? "done" : `${Math.floor(left / 60)}:${pad2(left % 60)}`));
    const x = row.appendChild(h("button", null, "✕")); x.title = done ? "dismiss" : "cancel";
    x.addEventListener("click", () => { timers = timers.filter((y) => y.id !== t.id); saveTimers(timers); drawTimers(); });
    if (done && !beeped.has(t.id)) { beeped.add(t.id); beep(); }
  }
  const ringing = timers.some((t) => t.end <= nowMs);
  document.title = (ringing ? "⏰ " : "") + document.title.replace(/^⏰ /, "");
};
const startTimer = (label, minutes) => { timers.push({ id: Date.now() + Math.random(), label, end: Date.now() + minutes * 60000 }); saveTimers(timers); drawTimers(); };
const timerButton = (label, minutes) => { const b = h("button", "tbtn no-print", `▶ ${num(minutes)} min`); b.title = "start a timer"; b.addEventListener("click", () => startTimer(label, minutes)); return b; };
setInterval(drawTimers, 1000); drawTimers();

const entryLink = (x) => { const a = h("a", "elk", kindBadge(x.entry.kind), h("span", null, x.entry.title)); a.href = "#entry/" + x.entry.id; return a; };
const runRow = (x) => {
  const e = x.entry, steps = e.protocol || [], done = steps.filter((p) => p.done).length, nx = nextStep(e);
  const row = kvar(h("div", "runrow"), e.kind);
  const left = row.appendChild(h("div", null, h("div", "t", entryLink(x))));
  if (nx) {
    const line = left.appendChild(h("div", "nx", "next: ", h("b", null, nx.text)));
    if (nx.minutes) { line.appendChild(document.createTextNode(" ")); line.appendChild(timerButton(`${e.title}: ${nx.text}`, nx.minutes)); }
  } else left.appendChild(h("div", "nx", steps.length ? "all steps done" : "no protocol steps"));
  if (steps.length) { const prog = row.appendChild(h("div", "progress", `${done}/${steps.length}`)); const tr = prog.appendChild(h("div", "track")); tr.appendChild(h("div")).style.width = (done / steps.length * 100) + "%"; }
  else row.appendChild(h("div"));
  return row;
};

// the week around a day: a dot per entry dated that day, coloured by kind
const weekStrip = (iso) => {
  const week = h("div", "week");
  const [y, m, d] = iso.split("-").map(Number), monday = new Date(y, m - 1, d - ((new Date(y, m - 1, d).getDay() + 6) % 7));
  for (let i = 0; i < 7; i++) {
    const di = isoDay(new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i));
    const b = week.appendChild(h("button", (di === iso ? "on " : "") + (di === todayIso() ? "today" : "")));
    b.appendChild(h("span", null, new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i).toLocaleDateString("en-GB", { weekday: "short" })));
    b.appendChild(h("b", null, Number(di.slice(8))));
    const dots = b.appendChild(h("div", "dots"));
    for (const x of E.filter((z) => z.entry.date === di).slice(0, 5)) kvar(dots.appendChild(h("i")), x.entry.kind);
    const n = (DAYS.get(di) || { items: [] }).items.length; if (n) b.title = `${n} planned item(s)`;
    b.addEventListener("click", () => go(di === todayIso() ? "today" : "day/" + di));
  }
  return week;
};

const planCard = (iso, plan, items) => {
  // ticks and new items made on this page live in the browser until PLSI records them: "Copy for PLSI" puts
  // them in a message to paste into the chat; once the journal agrees, the local change disappears
  const LKEY = "plsi-journal-day:" + iso, key = (it) => (it.time || "") + "|" + it.text;
  const local = (() => { try { return JSON.parse(localStorage.getItem(LKEY) || "{}"); } catch (e) { return {}; } })();
  local.ticks = local.ticks || {}; local.adds = local.adds || [];
  for (const it of items) if (local.ticks[key(it)] === !!it.done) delete local.ticks[key(it)];
  local.adds = local.adds.filter((a) => !items.some((it) => it.text.toLowerCase() === a.text.toLowerCase()));
  const store = () => { try { localStorage.setItem(LKEY, JSON.stringify(local)); } catch (e) { /* no storage */ } };
  store();
  const planBox = h("div"), ul = planBox.appendChild(h("ul", "plan"));
  const pending = h("div", "pending no-print");
  const message = () => {
    const done = items.filter((it) => local.ticks[key(it)] === true), undone = items.filter((it) => local.ticks[key(it)] === false);
    const fmtIt = (it) => (it.time ? it.time + " " : "") + it.text;
    const parts = [];
    if (done.length) parts.push("Done: " + done.map(fmtIt).join("; ") + ".");
    if (undone.length) parts.push("Not done after all: " + undone.map(fmtIt).join("; ") + ".");
    if (local.adds.length) parts.push("Add to the plan: " + local.adds.map(fmtIt).join("; ") + ".");
    return parts.length ? `Day plan ${iso}. ${parts.join(" ")}` : "";
  };
  const drawPending = () => {
    pending.textContent = "";
    const text = message();
    if (!text) { pending.hidden = true; return; }
    pending.hidden = false;
    const n = Object.keys(local.ticks).length + local.adds.length;
    pending.appendChild(h("span", null, h("b", null, `${n} change${n > 1 ? "s" : ""} not in the journal yet`), " · paste them into the chat with PLSI"));
    const copy = pending.appendChild(h("button", "btn", "Copy for PLSI"));
    copy.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(text); }
      catch (e) { const ta = document.body.appendChild(h("textarea")); ta.value = text; ta.select(); document.execCommand("copy"); ta.remove(); }
      copy.textContent = "Copied ✓"; setTimeout(() => { copy.textContent = "Copy for PLSI"; }, 2000);
    });
    const undo = pending.appendChild(h("button", "btn ghostbtn", "Undo"));
    undo.addEventListener("click", () => { local.ticks = {}; local.adds = []; store(); render(); });
  };
  const row = (it, isNew) => {
    const k = key(it), mine = !isNew && Object.prototype.hasOwnProperty.call(local.ticks, k), done = isNew ? false : mine ? local.ticks[k] : !!it.done;
    const li = ul.appendChild(h("li", (done ? "done " : "") + (mine || isNew ? "local" : "")));
    li.appendChild(h("span", "tm" + (it.time ? "" : " none"), it.time || "—"));
    const tick = li.appendChild(h("button", "tick", done ? icon("check") : ""));
    tick.title = isNew ? "added here, not in the journal yet" : mine ? "changed here, not in the journal yet" : done ? "mark not done" : "mark done";
    if (!isNew) tick.addEventListener("click", () => { const nv = !done; if (nv === !!it.done) delete local.ticks[k]; else local.ticks[k] = nv; store(); render(); });
    const body = li.appendChild(h("div", null, h("div", "what", it.text)));
    const sub = h("div", "sub"), x = it.entry ? E.find((z) => z.entry.id === it.entry) : null;
    if (x) sub.appendChild(entryLink(x));
    if (it.project) sub.appendChild(h("span", "tag", it.project));
    if (mine || isNew) sub.appendChild(h("span", "lnote", isNew ? "new · not in the journal yet" : "changed here · not in the journal yet"));
    if (x && !done) { const nx = nextStep(x.entry); if (nx && nx.minutes) sub.appendChild(timerButton(`${x.entry.title}: ${nx.text}`, nx.minutes)); }
    if (isNew) { const rm = sub.appendChild(h("button", "tbtn", "remove")); rm.addEventListener("click", () => { local.adds = local.adds.filter((a) => a !== it); store(); render(); }); }
    if (sub.childNodes.length) body.appendChild(sub);
    if (it.note) body.appendChild(h("div", "sn", it.note));
  };
  const all = [...items.map((it) => [it, false]), ...local.adds.map((it) => [it, true])];
  for (const [it, isNew] of all.sort((a, b) => (a[0].time || "99").localeCompare(b[0].time || "99"))) row(it, isNew);
  const add = planBox.appendChild(h("form", "additem no-print"));
  const tIn = add.appendChild(h("input")); tIn.type = "time"; tIn.setAttribute("aria-label", "time (optional)");
  const xIn = add.appendChild(h("input")); xIn.placeholder = "Add an item: order primers, feed HEK293…"; xIn.setAttribute("aria-label", "new item");
  const addBtn = add.appendChild(h("button", "btn", "Add")); addBtn.type = "submit";
  add.addEventListener("submit", (ev) => { ev.preventDefault(); const text = xIn.value.trim(); if (!text) return; local.adds.push({ text, time: tIn.value || undefined }); store(); render(); });
  planBox.appendChild(pending); drawPending();
  if (!items.length && !local.adds.length) ul.replaceWith(h("div", "dropzone", icon("clock"), h("b", null, "Nothing planned"),
    h("span", null, "Add items below, or tell PLSI: “today: thaw HEK293 at 9, qPCR plate at 14:00, order primers”. Ticks and new items made here are sent to PLSI with “Copy for PLSI”.")));
  return card("Plan", "list", planBox, { size: "half", sub: plan.note || (items.length ? `${items.filter((i) => i.done).length} of ${items.length} done in the journal` : "") });
};

const dayView = (iso) => {
  const v = h("div"); v.appendChild(mainTabs(iso === todayIso() ? "today" : "day/" + iso));
  const plan = DAYS.get(iso) || { date: iso, items: [] }, items = (plan.items || []).slice().sort((a, b) => (a.time || "99") .localeCompare(b.time || "99"));
  const head = v.appendChild(h("div", "dayhead"));
  head.appendChild(h("div", null, h("div", "wd", iso === todayIso() ? "Today" : iso < todayIso() ? "Past day" : "Coming day"), h("h1", null, longDay(iso))));
  const nav = head.appendChild(h("div", "daynav"));
  for (const [label, target] of [["← Previous", shift(iso, -1)], ["Today", todayIso()], ["Next →", shift(iso, 1)]]) {
    const b = nav.appendChild(h("button", "btn", label)); b.addEventListener("click", () => go(target === todayIso() ? "today" : "day/" + target));
  }
  v.appendChild(weekStrip(iso));
  const running = E.filter((x) => x.status === "running"), ofDay = E.filter((x) => x.entry.date === iso);
  v.appendChild(stats([[items.filter((i) => !i.done).length, "to do"], [items.filter((i) => i.done).length, "done"], [running.length, "experiments running"], [ofDay.length, "entries dated this day"]]));
  const grid = v.appendChild(h("div", "grid"));
  grid.appendChild(planCard(iso, plan, items));
  const run = h("div", "run"); for (const x of running) run.appendChild(runRow(x));
  grid.appendChild(card("Running", "flask", running.length ? run : h("p", "empty", "Nothing running."), { size: "half", sub: "next step and a timer for it" }));
  if (ofDay.length) { const c = h("div", "cards"); for (const x of ofDay) c.appendChild(entryCard(x));
    grid.appendChild(card("Entries of this day", "list", c)); }
  const flags = titledChecks([...running, ...ofDay.filter((x) => x.status !== "running")]);
  if (flags.length) grid.appendChild(card("Worth a second look", "warn", checks(flags.slice(0, 12)), { sub: `${flags.length} from running and today's entries` }));
  const ahead = E.filter((x) => x.status === "planned" && x.entry.date > iso && x.entry.date <= shift(iso, 7)).sort((a, b) => a.entry.date.localeCompare(b.entry.date));
  const laterPlans = [...DAYS.values()].filter((p) => p.date > iso && p.date <= shift(iso, 7));
  if (ahead.length || laterPlans.length) {
    const box = h("ul", "ptl");
    for (const x of ahead) { const li = kvar(box.appendChild(h("li")), x.entry.kind); li.appendChild(h("div", "d", longDay(x.entry.date))); li.appendChild(entryLink(x)); }
    for (const p of laterPlans) { const li = box.appendChild(h("li")); li.style.setProperty("--k", "var(--faint)"); li.appendChild(h("div", "d", longDay(p.date)));
      const a = li.appendChild(h("a", null, `${p.items.length} planned item(s)`)); a.href = "#day/" + p.date; }
    grid.appendChild(card("Coming up · 7 days", "clock", box));
  }
  return v;
};

const projectView = (name) => {
  const v = h("div"); v.appendChild(mainTabs("project/" + slug(name)));
  const xs = E.filter((x) => (x.entry.project || "No project") === name);
  v.appendChild(h("div", "hero", h("p", "eyebrow", "Project"), h("h1", null, name)));
  const last = xs.map((x) => x.entry.date).sort().pop();
  v.appendChild(stats([[xs.length, "entries"], [xs.filter((x) => x.status === "running").length, "running"], [xs.filter((x) => x.status === "signed").length, "signed"], [last ? day(last) : "—", "last entry"]]));
  const grid = v.appendChild(h("div", "grid"));
  const todayItems = ((DAYS.get(todayIso()) || {}).items || []).filter((i) => i.project === name || (i.entry && xs.some((x) => x.entry.id === i.entry)));
  if (todayItems.length) { const ul = h("ul", "plan"); for (const it of todayItems) { const li = ul.appendChild(h("li", it.done ? "done" : null)); li.appendChild(h("span", "tm" + (it.time ? "" : " none"), it.time || "—")); li.appendChild(h("div", "tick", it.done ? icon("check") : "")); li.appendChild(h("div", "what", it.text)); }
    grid.appendChild(card("Today in this project", "clock", ul, { size: "half" })); }
  const running = xs.filter((x) => x.status === "running");
  if (running.length) { const run = h("div", "run"); for (const x of running) run.appendChild(runRow(x)); grid.appendChild(card("Running", "flask", run, { size: todayItems.length ? "half" : "" })); }
  const counts = new Map(); for (const x of xs) counts.set(x.entry.kind, (counts.get(x.entry.kind) || 0) + 1);
  const kb = h("div", "kbars"), mx = Math.max(1, ...counts.values());
  for (const [k, n] of [...counts].sort((a, b) => b[1] - a[1])) { kb.appendChild(h("span", null, kname(k))); kvar(kb.appendChild(h("div", "b")), k).style.width = (n / mx * 100) + "%"; kb.appendChild(h("span", "c", n)); }
  grid.appendChild(card("Experiments", "chart", kb, { size: "third" }));
  const tl = h("ul", "ptl");
  for (const x of xs.slice().sort((a, b) => b.entry.date.localeCompare(a.entry.date))) {
    const li = kvar(tl.appendChild(h("li")), x.entry.kind);
    li.appendChild(h("div", "d", day(x.entry.date), " · ", kname(x.entry.kind)));
    const a = li.appendChild(h("a", null, x.entry.title)); a.href = "#entry/" + x.entry.id;
    li.appendChild(document.createTextNode(" ")); li.appendChild(pill(x.status));
  }
  grid.appendChild(card("Timeline", "list", tl, { size: "two3" }));
  const flags = titledChecks(xs);
  if (flags.length) grid.appendChild(card("Worth a second look", "warn", checks(flags.slice(0, 14)), { sub: `${flags.length} in this project` }));
  return v;
};
