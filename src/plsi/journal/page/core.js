const NS = "http://www.w3.org/2000/svg";
const P = JSON.parse(document.getElementById("plsi-payload").textContent || "{}");
const E = Array.isArray(P.entries) ? P.entries : [], PL = Array.isArray(P.plasmids) ? P.plasmids : [];
const own = (o, k) => o && Object.prototype.hasOwnProperty.call(o, k);

// ---------------------------------------------------------------- dom helpers (textContent only)
const h = (tag, cls, ...kids) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (tag === "button") e.type = "button";  // never a form submit
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) e.appendChild(typeof k === "object" ? k : document.createTextNode(String(k)));
  return e;
};
const s = (tag, attrs, ...kids) => {
  const e = document.createElementNS(NS, tag);
  for (const k of Object.keys(attrs || {})) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, String(attrs[k]));
  for (const k of kids.flat()) if (k !== null && k !== undefined) e.appendChild(typeof k === "object" ? k : document.createTextNode(String(k)));
  return e;
};
const tip = (node, text) => { node.appendChild(s("title", {}, text)); return node; };
const num = (v, d = 3) => {
  if (typeof v !== "number" || !Number.isFinite(v)) return v === null || v === undefined ? "—" : String(v);
  if (v !== 0 && (Math.abs(v) >= 1e5 || Math.abs(v) < 1e-3)) return v.toExponential(2).replace("e+", "e");
  return String(+v.toPrecision(d + (Math.abs(v) >= 100 ? 1 : 0)));
};
const day = (t) => { const d = Date.parse(t); return Number.isFinite(d) ? new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) : String(t || ""); };
const stamp = (t) => { const d = Date.parse(t); return Number.isFinite(d) ? new Date(d).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC" : ""; };

// ---------------------------------------------------------------- icons (24-unit grid, stroked)
const ICON = {
  pcr: ["M8 2.5c0 4.7 8 4.7 8 9.5s-8 4.8-8 9.5", "M16 2.5c0 4.7-8 4.7-8 9.5s8 4.8 8 9.5", "M9.2 4.8h5.6", "M9.2 12h5.6", "M9.2 19.2h5.6"],
  gel: ["M4 3h16v18H4z", "M8 7h2.5", "M13.5 7H16", "M8 11h2.5", "M13.5 13H16", "M8 16h2.5", "M13.5 17H16"],
  qpcr: ["M3 20h18", "M3 20V4", "M5 18c5 0 6-1.5 8-6.5S16 5 20 5"],
  western: ["M4 4h16v16H4z", "M7 9h4", "M13 9h4", "M7 14h4", "M13 14.5h4"],
  xcelligence: ["M3 13h4l2.5-7 4 13 2.5-6H21"],
  fluorimetry: ["M12 2.5v2.5", "M12 19v2.5", "M2.5 12H5", "M19 12h2.5", "M5.3 5.3l1.8 1.8", "M16.9 16.9l1.8 1.8", "M5.3 18.7l1.8-1.8", "M16.9 7.1l1.8-1.8", "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"],
  microscopy: ["M10 3h4", "M11 3v7h2V3", "M12 10v3", "M6 21h12", "M9 21c-2-1.5-3-3.5-3-6a6 6 0 0 1 9.5-4.9", "M10 16h5"],
  culture: ["M9 3h6", "M10 3v6l-5.3 9.2A2 2 0 0 0 6.4 21h11.2a2 2 0 0 0 1.7-2.8L14 9V3", "M7.5 15h9"],
  sorting: ["M3 4h18l-7 8.5V19l-4 2v-8.5z"],
  animal: ["M3.5 16.5c0-4.1 3.5-7.5 8.2-7.5 3.3 0 6 1.7 7.4 4.2l2.9 1.8-2.9 1.4c-.9 1.6-2.8 2.6-5.1 2.6H5.5c-1.1 0-2-.9-2-2.5z", "M12.6 9.2a3.1 3.1 0 1 1 5.6 2.2", "M17.4 13.6h.01", "M3.5 16.5C2.3 17 1.8 18 2.2 19c.5 1.2 2 1.6 3.6 1.4", "M9 19v2", "M14 19v2"],
  cloning: ["M12 21.5a8.5 8.5 0 1 0 0-17 8.5 8.5 0 0 0 0 17z", "M9.5 2.5h5v4h-5z"],
  transfection: ["M12 3v9", "M8.5 8.5L12 12l3.5-3.5", "M4 16.5c0 2.5 3.6 4.5 8 4.5s8-2 8-4.5S16.4 12 12 12s-8 2-8 4.5z"],
  elisa: ["M4 4h16v16H4z", "M8 8h.01", "M12 8h.01", "M16 8h.01", "M8 12h.01", "M12 12h.01", "M16 12h.01", "M8 16h.01", "M12 16h.01", "M16 16h.01"],
  other: ["M6 3h9l4 4v14H6z", "M15 3v4h4", "M9 12h7", "M9 16h5"],
  home: ["M3 11l9-7 9 7", "M5 10v10h14V10", "M10 20v-6h4v6"],
  calc: ["M6 3h12v18H6z", "M9 7h6", "M9 12h.01", "M12 12h.01", "M15 12h.01", "M9 16h.01", "M12 16h.01", "M15 16h.01"],
  plasmid: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M12 3a9 9 0 0 1 7.8 4.5", "M17.2 6.4l2.6 1.1.3-2.8", "M8 12a4 4 0 0 1 4-4"],
  search: ["M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z", "M20 20l-4-4"],
  print: ["M7 9V3h10v6", "M7 18H4v-8h16v8h-3", "M7 14h10v7H7z"],
  warn: ["M12 3l9.5 17H2.5z", "M12 10v4", "M12 17h.01"],
  check: ["M5 12.5l4.5 4.5L19 7.5"],
  file: ["M6 3h8l4 4v14H6z", "M14 3v4h4"],
  seal: ["M12 2l2.4 1.8 3-.2 1 2.8 2.5 1.7-.8 2.9.8 2.9-2.5 1.7-1 2.8-3-.2L12 22l-2.4-1.8-3 .2-1-2.8-2.5-1.7.8-2.9-.8-2.9 2.5-1.7 1-2.8 3 .2z", "M8.5 12l2.5 2.5 4.5-5"],
  flask: ["M9 3h6", "M10 3v6l-5.3 9.2A2 2 0 0 0 6.4 21h11.2a2 2 0 0 0 1.7-2.8L14 9V3"],
  list: ["M8 6h12", "M8 12h12", "M8 18h12", "M4 6h.01", "M4 12h.01", "M4 18h.01"],
  beaker: ["M5 3h14", "M6 3v15a3 3 0 0 0 3 3h6a3 3 0 0 0 3-3V3", "M6 12h12"],
  chart: ["M3 20h18", "M6 16v-5", "M11 16V7", "M16 16v-8", "M21 16v-3"],
  plate: ["M3 6h18v12H3z", "M7 10h.01", "M11 10h.01", "M15 10h.01", "M7 14h.01", "M11 14h.01", "M15 14h.01"],
  image: ["M4 5h16v14H4z", "M4 16l5-5 4 4 2-2 5 5", "M15.5 9.5h.01"],
  clock: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M12 7v5l3 2"],
  eye: ["M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z", "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"],
  chev: ["M9 6l6 6-6 6"],
  camera: ["M4 8h3l1.5-2.5h7L17 8h3v11H4z", "M12 16.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z"],
};
const icon = (name, extra) => {
  const g = s("svg", { viewBox: "0 0 24 24", "aria-hidden": "true", ...(extra || {}) });
  for (const d of ICON[name] || ICON.other) g.appendChild(s("path", { d }));
  return g;
};
const KINDS = {
  pcr: "PCR", gel: "Electrophoresis", qpcr: "RT-qPCR", western: "Western blot", xcelligence: "xCELLigence", fluorimetry: "Fluorimetry",
  microscopy: "Microscopy", culture: "Cell culture", sorting: "Flow · sorting", animal: "Animal study", cloning: "Cloning",
  transfection: "Transfection", elisa: "ELISA", other: "Other",
};
const kname = (k) => (own(KINDS, k) ? KINDS[k] : String(k));
const kvar = (node, k) => { node.style.setProperty("--k", "var(--k-" + (own(KINDS, k) ? k : "other") + ")"); return node; };
const kindBadge = (k) => kvar(h("span", "kind", icon(own(KINDS, k) ? k : "other"), kname(k)), k);
const STATUS = { planned: "Planned", running: "Running", done: "Done", signed: "Signed" };
const pill = (st) => h("span", "pill " + (own(STATUS, st) ? st : ""), own(STATUS, st) ? STATUS[st] : String(st || ""));
const PALETTE = ["#00A607", "#2563eb", "#db2777", "#ea580c", "#7c3aed", "#0891b2", "#ca8a04", "#0d9488", "#e11d48", "#4f46e5"];
const CONTROL = "#94a3b8";
const colorer = (control) => {
  const seen = new Map();
  return (g) => {
    if (control && g === control) return CONTROL;
    if (!seen.has(g)) seen.set(g, PALETTE[seen.size % PALETTE.length]);
    return seen.get(g);
  };
};

// one colour per group for a whole entry, so the samples table, plate map and every chart agree
let paint = colorer(null);
const entryColors = (e) => {
  const r = e.results || {}, c = colorer(r.control_group);
  for (const g of [...(e.samples || []), ...((e.plate || {}).wells || []), ...(r.cts || []), ...(r.bands || []), ...(r.readings || []).filter((x) => x.role !== "blank" && x.standard_conc === undefined)]) c(g.group || g.sample);
  for (const g of [...(r.ci || []), ...(r.groups || [])]) c(g.group || g.name);
  c.control = r.control_group;
  return c;
};

// ---------------------------------------------------------------- generic pieces
const card = (title, iconName, body, opts = {}) => {
  const c = h("section", "card " + (opts.size || ""));
  const hd = c.appendChild(h("header"));
  const t = hd.appendChild(h("h2", null));
  if (iconName) t.appendChild(h("span", "hico", icon(iconName)));
  t.appendChild(document.createTextNode(title));
  if (opts.sub) hd.appendChild(typeof opts.sub === "string" ? h("span", "sub", opts.sub) : opts.sub);
  c.appendChild(body);
  return c;
};
const table = (cols, rows, numeric = []) => {
  const w = h("div", "scroll"), t = w.appendChild(h("table"));
  const tr = t.appendChild(h("thead")).appendChild(h("tr"));
  cols.forEach((c, i) => {  // a unit with µ stays as written: upper case would turn it into a Greek capital
    const m = /^(.*?)(\S*µ\S*)$/.exec(c);
    tr.appendChild(h("th", numeric.includes(i) ? "num" : null, m ? [m[1], h("span", "u", m[2])] : c));
  });
  const tb = t.appendChild(h("tbody"));
  for (const r of rows) {
    const row = tb.appendChild(h("tr"));
    r.forEach((v, i) => row.appendChild(h("td", numeric.includes(i) ? "num" : null, v instanceof Node ? v : (typeof v === "number" ? num(v) : (v ?? "")))));
  }
  return w;
};
const swatch = (color, text) => { const sp = h("span", null); const i = sp.appendChild(h("span", "sw")); i.style.background = color; sp.appendChild(document.createTextNode(text)); return sp; };
const checks = (list) => {
  const box = h("div", "checks");
  for (const c of list) box.appendChild(h("div", "check", icon("warn"), h("span", null, c)));
  return box;
};
const prose = (text) => { const d = h("div", "prose"); for (const para of String(text).split(/\n{2,}/)) d.appendChild(h("p", null, para)); return d; };

// axes: linear or log2 y, numeric or date x
const niceTicks = (lo, hi, n = 5) => {
  if (!(hi > lo)) { hi = lo + 1; }
  const raw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / mag;
  const step = (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag;
  const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toPrecision(12));
  return out;
};
const frame = (W, H, m) => ({ W, H, m, x0: m.l, x1: W - m.r, y0: H - m.b, y1: m.t });
const scaleLin = (d0, d1, r0, r1) => (v) => r0 + (v - d0) / ((d1 - d0) || 1) * (r1 - r0);

// line chart: series [{name, color, points:[{x, y, lo?, hi?}]}]
const lineChart = (series, o = {}) => {
  const all = series.flatMap((sr) => sr.points);
  if (!all.length) return h("p", "empty", "nothing to draw");
  const f = frame(o.w || 640, o.h || 300, { l: 50, r: 18, t: 14, b: 38 });
  let xs = all.map((p) => p.x), ys = all.flatMap((p) => [p.y, p.lo, p.hi]).filter(Number.isFinite);
  if (o.vline !== undefined && o.vline !== null) xs = xs.concat([o.vline]);
  let ylo = Math.min(...ys), yhi = Math.max(...ys);
  if (o.zero) { ylo = Math.min(0, ylo); yhi = Math.max(0, yhi); }
  const pad = (yhi - ylo) * 0.08 || 1; ylo -= pad; yhi += pad;
  const xlo = Math.min(...xs), xhi = Math.max(...xs);
  const X = scaleLin(xlo, xhi === xlo ? xlo + 1 : xhi, f.x0, f.x1), Y = scaleLin(ylo, yhi, f.y0, f.y1);
  const g = s("svg", { class: "chart", viewBox: `0 0 ${f.W} ${f.H}`, role: "img", "aria-label": o.label || "chart" });
  for (const t of niceTicks(ylo, yhi)) { g.appendChild(s("line", { class: "gl", x1: f.x0, x2: f.x1, y1: Y(t), y2: Y(t) })); g.appendChild(s("text", { x: f.x0 - 8, y: Y(t) + 4, "text-anchor": "end" }, num(t))); }
  if (o.dates) {
    const n = Math.min(6, new Set(xs).size);
    for (let i = 0; i < n; i++) { const v = xlo + (xhi - xlo) * (n === 1 ? 0 : i / (n - 1)); g.appendChild(s("text", { x: X(v), y: f.y0 + 18, "text-anchor": "middle" }, new Date(v).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }))); }
  } else for (const t of niceTicks(xlo, xhi, 6)) g.appendChild(s("text", { x: X(t), y: f.y0 + 18, "text-anchor": "middle" }, num(t)));
  g.appendChild(s("line", { class: "ax", x1: f.x0, x2: f.x1, y1: f.y0, y2: f.y0 }));
  if (o.xlabel) g.appendChild(s("text", { x: (f.x0 + f.x1) / 2, y: f.H - 4, "text-anchor": "middle" }, o.xlabel));
  if (o.ylabel) g.appendChild(s("text", { x: 12, y: (f.y0 + f.y1) / 2, transform: `rotate(-90 12 ${(f.y0 + f.y1) / 2})`, "text-anchor": "middle" }, o.ylabel));
  if (o.ref !== undefined) g.appendChild(s("line", { x1: f.x0, x2: f.x1, y1: Y(o.ref), y2: Y(o.ref), stroke: "var(--faint)", "stroke-dasharray": "4 4" }));
  if (o.vline !== undefined && o.vline !== null) {
    g.appendChild(s("line", { x1: X(o.vline), x2: X(o.vline), y1: f.y1, y2: f.y0, stroke: "var(--bad)", "stroke-width": 1.5, "stroke-dasharray": "5 4" }));
    g.appendChild(s("text", { x: X(o.vline) + 6, y: f.y1 + 10, class: "lbl", fill: "var(--bad)" }, o.vlabel || ""));
  }
  for (const sr of series) {
    const pts = sr.points.filter((p) => Number.isFinite(p.y)).sort((a, b) => a.x - b.x);
    const band = pts.filter((p) => Number.isFinite(p.lo) && Number.isFinite(p.hi));
    if (band.length > 1) g.appendChild(s("path", { d: "M" + band.map((p) => `${X(p.x)},${Y(p.hi)}`).join("L") + "L" + band.slice().reverse().map((p) => `${X(p.x)},${Y(p.lo)}`).join("L") + "Z", fill: sr.color, opacity: 0.13 }));
    if (pts.length > 1 && !sr.dots) g.appendChild(s("path", { d: "M" + pts.map((p) => `${X(p.x)},${Y(p.y)}`).join("L"), fill: "none", stroke: sr.color, "stroke-width": 2.4, "stroke-linejoin": "round", "stroke-linecap": "round" }));
    if (pts.length <= 40) for (const p of pts) g.appendChild(tip(s("circle", { cx: X(p.x), cy: Y(p.y), r: 3.6, fill: sr.color, stroke: "var(--surface)", "stroke-width": 1.5 }), `${sr.name}: ${num(p.y)} at ${o.dates ? day(p.x) : num(p.x)}`));
  }
  const box = h("div");
  box.appendChild(g);
  const lg = box.appendChild(h("div", "legend"));
  for (const sr of series) { const it = lg.appendChild(h("span", null)); const i = it.appendChild(h("i", "line")); i.style.background = sr.color; it.appendChild(document.createTextNode(sr.name)); }
  return box;
};

// grouped bars: items [{label, value, lo?, hi?, color, dots?: [v]}]; log2 axis optional
const barChart = (items, o = {}) => {
  if (!items.length) return h("p", "empty", "nothing to draw");
  const tf = o.log2 ? (v) => Math.log2(v) : (v) => v;
  const vals = items.flatMap((i) => [i.value, i.lo, i.hi, ...(i.dots || [])]).filter((v) => Number.isFinite(v) && (!o.log2 || v > 0)).map(tf);
  let lo = Math.min(0, ...vals), hi = Math.max(0, ...vals); const pad = (hi - lo) * 0.12 || 1; hi += pad; if (lo < 0) lo -= pad;
  const f = frame(o.w || Math.max(260, 70 + items.length * 70), o.h || 250, { l: 50, r: 12, t: 16, b: 46 });
  const Y = scaleLin(lo, hi, f.y0, f.y1), bw = Math.min(46, (f.x1 - f.x0) / items.length * 0.62), step = (f.x1 - f.x0) / items.length;
  const g = s("svg", { class: "chart", viewBox: `0 0 ${f.W} ${f.H}`, role: "img", "aria-label": o.label || "bars" });
  for (const t of niceTicks(lo, hi)) {
    g.appendChild(s("line", { class: "gl", x1: f.x0, x2: f.x1, y1: Y(t), y2: Y(t) }));
    g.appendChild(s("text", { x: f.x0 - 8, y: Y(t) + 4, "text-anchor": "end" }, o.log2 ? num(Math.pow(2, t)) : num(t)));
  }
  g.appendChild(s("line", { x1: f.x0, x2: f.x1, y1: Y(0), y2: Y(0), stroke: "var(--ink)", "stroke-width": 1, opacity: 0.5 }));
  if (o.ylabel) g.appendChild(s("text", { x: 12, y: (f.y0 + f.y1) / 2, transform: `rotate(-90 12 ${(f.y0 + f.y1) / 2})`, "text-anchor": "middle" }, o.ylabel));
  items.forEach((it, i) => {
    const cx = f.x0 + step * (i + 0.5), v = tf(it.value);
    if (Number.isFinite(v)) {
      const y = Math.min(Y(v), Y(0)), hgt = Math.abs(Y(v) - Y(0));
      g.appendChild(tip(s("rect", { x: cx - bw / 2, y, width: bw, height: Math.max(1, hgt), rx: 5, fill: it.color, opacity: 0.88 }), `${it.label}: ${num(it.value)}`));
      const marks = [it.value, it.hi, ...(it.dots || [])].filter((m) => Number.isFinite(m) && (!o.log2 || m > 0)).map(tf);
      const top = v >= 0 ? Y(Math.max(...marks)) - 8 : Y(Math.min(...marks)) + 15;
      g.appendChild(s("text", { x: cx, y: top, "text-anchor": "middle", class: "lbl" }, num(it.value)));
    }
    if (Number.isFinite(it.lo) && Number.isFinite(it.hi) && (!o.log2 || (it.lo > 0 && it.hi > 0))) {
      const a = Y(tf(it.lo)), b = Y(tf(it.hi));
      g.appendChild(s("path", { d: `M${cx},${a}V${b}M${cx - 7},${a}H${cx + 7}M${cx - 7},${b}H${cx + 7}`, stroke: "var(--ink)", "stroke-width": 1.4, fill: "none" }));
    }
    (it.dots || []).forEach((d, j) => { if (Number.isFinite(d) && (!o.log2 || d > 0)) g.appendChild(tip(s("circle", { cx: cx + ((j % 5) - 2) * 4, cy: Y(tf(d)), r: 3, fill: "var(--surface)", stroke: "var(--ink)", "stroke-width": 1.3 }), num(d))); });
    const lab = s("text", { x: cx, y: f.y0 + 16, "text-anchor": "middle" }, it.label.length > 14 ? it.label.slice(0, 13) + "…" : it.label);
    g.appendChild(tip(lab, it.label));
  });
  return g;
};
const lightbox = (src, alt) => { const lb = document.body.appendChild(h("div", "lightbox")); const big = lb.appendChild(h("img")); big.src = src; big.alt = alt; lb.addEventListener("click", () => lb.remove()); };
// an entry as a card that opens it; `more` adds the date, project, steps and samples
const entryCard = (x, more) => {
  const e = x.entry, b = kvar(h("button", "ecard"), e.kind);
  b.appendChild(h("div", "top", kindBadge(e.kind), pill(x.status)));
  b.appendChild(h("div", "tt", e.title));
  if (more) {
    const steps = e.protocol || [], done = steps.filter((p) => p.done).length;
    b.appendChild(h("div", "bt", h("span", null, day(e.date)), e.project ? h("span", null, "· " + e.project) : null,
      steps.length ? h("span", null, `· ${done}/${steps.length} steps`) : null, (e.samples || []).length ? h("span", null, `· ${(e.samples || []).length} samples`) : null));
  }
  b.addEventListener("click", () => go("entry/" + e.id));
  return b;
};
const entryChecks = (x) => Object.values(x.derived || {}).flatMap((d) => d.checks || []);
const titledChecks = (xs) => xs.flatMap((x) => entryChecks(x).map((c) => `${x.entry.title}: ${c}`));
// a row of big numbers: [[value, label], ...]
const stats = (pairs) => h("div", "stats", pairs.map(([val, lab]) => h("div", "stat", h("div", "v", val), h("div", "l", lab))));
