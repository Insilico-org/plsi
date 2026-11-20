// ---------------------------------------------------------------- experiment views
const plateMap = (plate, samples) => {
  const dims = { "6": [2, 3], "12": [3, 4], "24": [4, 6], "48": [6, 8], "96": [8, 12], "384": [16, 24] };
  const [R, C] = dims[plate.format] || dims["96"];
  const size = C > 12 ? 22 : C > 8 ? 34 : 52;
  const color = paint;
  const sgroup = new Map((samples || []).map((x) => [x.id, x.group]));
  const byWell = new Map((plate.wells || []).map((w) => [w.well, w]));
  const box = h("div");
  const grid = box.appendChild(h("div", "plate"));
  grid.style.gridTemplateColumns = `18px repeat(${C}, ${size}px)`;
  grid.appendChild(h("div"));
  for (let c = 1; c <= C; c++) grid.appendChild(h("div", "ax", c));
  const groups = new Map();
  for (let r = 0; r < R; r++) {
    const L = String.fromCharCode(65 + r);
    grid.appendChild(h("div", "ax", L));
    for (let c = 1; c <= C; c++) {
      const w = byWell.get(L + c), well = grid.appendChild(h("div", "well"));
      if (w) {
        const g = w.group || sgroup.get(w.sample) || w.sample || "";
        const col = color(g || "—"); groups.set(g || "—", col);
        well.classList.add("on"); well.style.background = col;
        if (size >= 34) well.textContent = (w.label || w.sample || "").slice(0, size >= 52 ? 8 : 4);
        well.title = `${L}${c} · ${w.sample || ""}${g ? " · " + g : ""}${w.label ? " · " + w.label : ""}`;
      } else well.title = L + c;
    }
  }
  const lg = box.appendChild(h("div", "legend"));
  for (const [g, col] of groups) { const it = lg.appendChild(h("span", null)); it.appendChild(h("i")).style.background = col; it.appendChild(document.createTextNode(g)); }
  lg.appendChild(h("span", "faint", `${(plate.wells || []).length} of ${R * C} wells used`));
  return box;
};

const thermal = (cycling) => {
  const steps = cycling.map((c) => ({ ...c, w: Math.max(1, Math.log10((c.seconds || 1) + 1)) }));
  const total = steps.reduce((a, c) => a + c.w, 0);
  const f = frame(680, 220, { l: 46, r: 16, t: 26, b: 44 });
  const temps = steps.map((c) => c.temp_c), lo = Math.min(4, ...temps) - 4, hi = Math.max(...temps) + 6;
  const Y = scaleLin(lo, hi, f.y0, f.y1), X = scaleLin(0, total, f.x0, f.x1);
  const g = s("svg", { class: "chart", viewBox: `0 0 ${f.W} ${f.H}`, role: "img", "aria-label": "cycling program" });
  for (const t of niceTicks(lo, hi, 4)) { g.appendChild(s("line", { class: "gl", x1: f.x0, x2: f.x1, y1: Y(t), y2: Y(t) })); g.appendChild(s("text", { x: f.x0 - 8, y: Y(t) + 4, "text-anchor": "end" }, num(t) + "°")); }
  let x = 0, d = "", first = true; const cycStart = steps.findIndex((c) => c.cycles > 1), cycEnd = steps.map((c) => c.cycles > 1).lastIndexOf(true);
  let cx0 = null, cx1 = null;
  steps.forEach((c, i) => {
    const xa = X(x), xb = X(x + c.w), y = Y(c.temp_c);
    d += (first ? `M${xa},${y}` : `L${xa + 6},${y}`) + `L${xb},${y}`; first = false;
    if (i === cycStart) cx0 = xa; if (i === cycEnd) cx1 = xb;
    g.appendChild(s("text", { x: (xa + xb) / 2, y: y - 8, "text-anchor": "middle", class: "lbl" }, num(c.temp_c) + "°"));
    g.appendChild(s("text", { x: (xa + xb) / 2, y: f.y0 + 16, "text-anchor": "middle" }, c.seconds >= 60 ? num(c.seconds / 60) + " min" : num(c.seconds) + " s"));
    g.appendChild(tip(s("text", { x: (xa + xb) / 2, y: f.y0 + 30, "text-anchor": "middle", class: "faint" }, c.step.length > 12 ? c.step.slice(0, 11) + "…" : c.step), c.step));
    x += c.w;
  });
  if (cx0 !== null) {
    g.appendChild(s("rect", { x: cx0, y: f.y1 - 18, width: cx1 - cx0, height: f.y0 - f.y1 + 18, fill: "var(--k-pcr)", opacity: 0.06, rx: 8 }));
    g.appendChild(s("text", { x: (cx0 + cx1) / 2, y: f.y1 - 6, "text-anchor": "middle", class: "lbl", fill: "var(--k-pcr)" }, `× ${steps[cycStart].cycles} cycles`));
  }
  g.appendChild(s("path", { d, fill: "none", stroke: "var(--k-pcr)", "stroke-width": 3, "stroke-linejoin": "round" }));
  return g;
};

// ladder lanes recorded without sizes get their product's standard bands (derived.gel.ladders)
const withLadders = (lanes, gel) => {
  const std = new Map(((gel || {}).ladders || []).map((x) => [x.lane, x]));
  return lanes.map((l) => std.has(l.lane) && !(l.observed_bp || []).length ? { ...l, observed_bp: std.get(l.lane).bp, product: std.get(l.lane).ladder } : l);
};

// a gel or blot drawn from the recorded bands (migration on a log scale), never a photo
const gelView = (lanes, o = {}) => {
  const sizes = lanes.flatMap((l) => [...(l.observed_bp || []), ...(l.faint_bp || []), l.expected_bp]).filter((v) => v > 0);
  if (!sizes.length) return h("p", "empty", "no band sizes recorded");
  const lo = Math.log10(Math.min(...sizes) * 0.7), hi = Math.log10(Math.max(...sizes) * 1.4);
  const n = Math.max(...lanes.map((l) => l.lane)), lw = 44, W = (o.marks ? 120 : 70) + n * lw, H = o.blot ? 170 : o.marks ? 260 : 330;
  const Y = (bp) => 40 + (hi - Math.log10(bp)) / (hi - lo) * (H - 70);
  const blot = !!o.blot, g = s("svg", { class: blot ? "blot" : "gel", viewBox: `0 0 ${W} ${H}`, width: W, role: "img", "aria-label": o.label || "gel" });
  const defs = g.appendChild(s("defs"));
  const fl = defs.appendChild(s("filter", { id: "glow" + (o.id || ""), x: "-50%", y: "-200%", width: "200%", height: "500%" }));
  fl.appendChild(s("feGaussianBlur", { stdDeviation: blot ? 1.2 : 2.2 }));
  const max = Math.max(1, ...lanes.flatMap((l) => l.intensities || [1]));
  const labelled = [];  // bp labels on the axis, kept 11 px apart where ladder bands crowd
  for (const l of lanes) {
    const x = (o.marks ? 100 : 50) + (l.lane - 1) * lw;
    g.appendChild(s("rect", { x: x + 6, y: 20, width: lw - 12, height: 8, rx: 2, fill: blot ? "#d9d6cd" : "#000", opacity: blot ? 1 : 0.7 }));
    g.appendChild(tip(s("text", { x: x + lw / 2, y: H - 12, "text-anchor": "middle" }, o.names ? String(l.sample || l.lane).slice(0, 7) : String(l.lane)), l.sample || ""));
    const bands = [...(l.observed_bp || []).map((bp) => [bp, false]), ...(l.faint_bp || []).map((bp) => [bp, true])];
    bands.forEach(([bp, faint], j) => {
      const a = l.intensities ? Math.max(0.25, l.intensities[j] / max) : faint ? 0.32 : (l.ladder ? 0.55 : 0.95);
      const band = s("rect", { x: x + 7, y: Y(bp) - 3, width: lw - 14, height: 6, rx: 3, fill: blot ? "#1d1f24" : "var(--gel-band)", opacity: a, filter: `url(#glow${o.id || ""})` });
      g.appendChild(tip(band, `${l.sample || "lane " + l.lane}: ≈${num(bp)} ${o.unit || "bp"}${faint ? ", faint" : ""}`));
      g.appendChild(s("rect", { x: x + 9, y: Y(bp) - 1.5, width: lw - 18, height: 3, rx: 1.5, fill: blot ? "#111" : "#fff6e0", opacity: a }));
      if (l.ladder && labelled.every((y) => Math.abs(y - Y(bp)) >= 11)) {
        labelled.push(Y(bp));
        g.appendChild(s("text", { x: 44, y: Y(bp) + 3.5, "text-anchor": "end" }, num(bp)));
      }
    });
    if (l.expected_bp) g.appendChild(tip(s("path", { d: `M${x + lw - 4},${Y(l.expected_bp)}l5,-4v8z`, fill: blot ? "#b45309" : "#7dd3fc" }), `expected ${num(l.expected_bp)} ${o.unit || "bp"}`));
  }
  for (const mk of o.marks || []) {  // reference sizes: what each band means
    g.appendChild(s("line", { x1: 46, x2: W - 8, y1: Y(mk.bp), y2: Y(mk.bp), stroke: blot ? "#9aa0a6" : "rgba(255,255,255,.18)", "stroke-dasharray": "3 4" }));
    g.appendChild(s("text", { x: 44, y: Y(mk.bp) + 3.5, "text-anchor": "end" }, mk.label));
  }
  g.appendChild(s("text", { x: 8, y: 14 }, o.unit || "bp"));
  return g;
};

const qpcrView = (q) => {
  const box = h("div");
  const color = paint;
  const targets = [...new Set((q.groups || []).map((x) => x.target))];
  const charts = box.appendChild(h("div", "charts"));
  for (const t of targets) {
    const fig = charts.appendChild(h("div"));
    fig.appendChild(h("p", "chart-title", t));
    const items = q.groups.filter((x) => x.target === t).map((x) => ({
      label: x.group, value: x.fold, lo: x.low, hi: x.high, color: color(x.group),
      dots: (q.rows || []).filter((r) => r.target === t && r.group === x.group).map((r) => r.fold),
    }));
    fig.appendChild(barChart(items, { log2: true, ylabel: "fold change (2^-ΔΔCt)", label: t }));
  }
  box.appendChild(h("p", "muted", `Reference: ${(q.references || []).join(", ") || "—"} · calibrator: ${q.control || "—"} · bars: group mean, whiskers ±1 SD of ΔΔCt, dots: samples · log₂ axis`));
  box.appendChild(table(["Sample", "Group", "Target", "Ct", "ΔCt", "ΔΔCt", "Fold"],
    (q.rows || []).map((r) => [r.sample, swatch(color(r.group), r.group), r.target, r.ct, r.dct, r.ddct, r.fold]), [3, 4, 5, 6]));
  return box;
};

const westernView = (w, bands) => {
  const box = h("div");
  const color = paint;
  const targets = [...new Set(bands.map((b) => b.target))];
  const wrap = box.appendChild(h("div", "gelwrap"));
  targets.forEach((t, i) => {
    const lanes = bands.filter((b) => b.target === t).map((b) => ({ lane: b.lane, sample: b.sample, observed_bp: [b.kda || 50], intensities: [b.intensity] }));
    const f = wrap.appendChild(h("div"));
    f.appendChild(h("p", "chart-title", t));
    f.appendChild(gelView(lanes, { blot: true, unit: "kDa", id: "w" + i, label: t }));
  });
  const charts = box.appendChild(h("div", "charts"));
  for (const t of targets) {
    const fig = charts.appendChild(h("div"));
    fig.appendChild(h("p", "chart-title", t + " ÷ loading control, relative to " + (paint.control || "the control")));
    fig.appendChild(barChart((w.groups || []).filter((x) => x.target === t).map((x) => ({
      label: x.group, value: x.mean, lo: x.sd ? x.mean - x.sd : null, hi: x.sd ? x.mean + x.sd : null, color: color(x.group),
      dots: (w.rows || []).filter((r) => r.target === t && r.group === x.group).map((r) => r.relative) })), { ylabel: "relative level" }));
  }
  box.appendChild(table(["Lane", "Sample", "Group", "Target", "Band ÷ loading", "Relative"],
    (w.rows || []).map((r) => [r.lane, r.sample, swatch(color(r.group), r.group), r.target, r.ratio, r.relative]), [0, 4, 5]));
  return box;
};

const ciView = (ci) => {
  const color = paint, useNorm = ci.treated_at_h !== null && ci.treated_at_h !== undefined && ci.series.some((x) => x.points.some((p) => p.norm !== null));
  const series = ci.series.map((sr) => ({ name: sr.group + (sr.well ? " · " + sr.well : ""), color: color(sr.group),
    points: sr.points.map((p) => ({ x: p.t, y: useNorm ? p.norm : p.ci })).filter((p) => Number.isFinite(p.y)) }));
  const box = h("div");
  box.appendChild(lineChart(series, { xlabel: "time (h)", ylabel: useNorm ? "normalised cell index" : "cell index", vline: ci.treated_at_h, vlabel: "treatment", ref: useNorm ? 1 : undefined, w: 760, h: 320 }));
  if ((ci.blanks || []).length) box.appendChild(h("p", "muted", "Blank wells, not drawn: " +
    ci.blanks.map((b) => `${b.well || b.group} max CI ${num(b.max, 2)}`).join(" · ")));
  return box;
};

const readingsView = (rd, r) => {
  const box = h("div", "charts");
  const color = paint;
  const bars = h("div");
  bars.appendChild(h("p", "chart-title", "Blank-subtracted signal" + (r.reading ? " · " + r.reading : "")));
  bars.appendChild(barChart((rd.groups || []).map((g) => ({ label: g.group, value: g.mean, lo: g.sd ? g.mean - g.sd : null, hi: g.sd ? g.mean + g.sd : null, color: color(g.group),
    dots: (rd.rows || []).filter((x) => x.group === g.group).map((x) => x.net) })), { ylabel: "signal − blank" }));
  box.appendChild(bars);
  if (rd.curve) {
    const c = rd.curve, fig = box.appendChild(h("div"));
    fig.appendChild(h("p", "chart-title", `Standard curve · r² ${num(c.r2, 4)}`));
    const xs = c.points.map((p) => p[0]), x0 = Math.min(...xs), x1 = Math.max(...xs);
    fig.appendChild(lineChart([
      { name: "fit", color: "var(--k-fluorimetry)", points: [{ x: x0, y: c.intercept + c.slope * x0 }, { x: x1, y: c.intercept + c.slope * x1 }] },
      { name: "standards", color: "var(--ink)", dots: true, points: c.points.map((p) => ({ x: p[0], y: p[1] })) },
    ], { xlabel: "concentration", ylabel: "signal − blank", w: 380, h: 250 }));
  }
  const out = h("div"); out.appendChild(box);
  out.appendChild(table(["Sample", "Group", "Signal − blank", "Concentration"], (rd.rows || []).map((x) => [x.sample, swatch(color(x.group), x.group), x.net, x.conc]), [2, 3]));
  out.appendChild(h("p", "muted", `Blank mean ${num(rd.blank)}`));
  return out;
};

const gallery = (images, files) => {
  const box = h("div");
  const byName = new Map((files || []).map((f) => [f.name, f]));
  const shown = new Set();
  const gal = box.appendChild(h("div", "gallery"));
  const add = (name, meta) => {
    const f = byName.get(name); shown.add(name);
    if (!f || !f.src) return;
    const fig = gal.appendChild(h("figure"));
    const img = fig.appendChild(h("img")); img.src = f.src; img.alt = name; img.loading = "lazy";
    img.addEventListener("click", () => lightbox(f.src, name));
    const cap = fig.appendChild(h("figcaption", null, h("b", null, name)));
    if (meta) {
      if (meta.channel) cap.appendChild(h("span", "ch " + String(meta.channel).toLowerCase().replace(/[^a-z]/g, ""), meta.channel));
      if (meta.objective) cap.appendChild(h("span", "ch", meta.objective));
      if (meta.sample) cap.appendChild(h("span", "ch", meta.sample));
      if (meta.animal) cap.appendChild(h("span", "ch", meta.animal));
      if (meta.note) cap.appendChild(h("span", "muted", meta.note));
    }
  };
  for (const im of images || []) add(im.file, im);
  for (const f of files || []) if (!shown.has(f.name)) add(f.name, null);
  const rest = (files || []).filter((f) => !f.src);
  if (rest.length) {
    const fl = box.appendChild(h("div", "filelist"));
    for (const f of rest) fl.appendChild(h("span", "file", icon("file"), f.name, f.missing ? h("span", "faint", " · not attached yet") : f.bytes ? h("span", "faint", ` · ${num(f.bytes / 1048576, 2)} MB, kept with the entry`) : null));
  }
  if (!gal.childNodes.length) gal.remove();
  return box;
};

const cultureView = (passages, growth) => {
  const box = h("div");
  const ul = kvar(box.appendChild(h("ul", "tl")), "culture");
  for (const p of passages.slice().sort((a, b) => String(a.date).localeCompare(String(b.date)))) {
    const li = ul.appendChild(h("li"));
    const w = li.appendChild(h("div", "when", day(p.date)));
    if (p.passage !== null && p.passage !== undefined) w.appendChild(h("span", "tag", "P" + p.passage));
    li.appendChild(h("div", "what", p.action));
    const x = li.appendChild(h("div", "sx"));
    if (p.confluence_pct !== undefined && p.confluence_pct !== null) { const m = h("span", "mini", "confluence"); const t = m.appendChild(h("span", "track")); t.appendChild(h("div")).style.width = p.confluence_pct + "%"; m.appendChild(document.createTextNode(num(p.confluence_pct) + "%")); x.appendChild(m); }
    if (p.viability_pct !== undefined && p.viability_pct !== null) x.appendChild(h("span", null, "viability " + num(p.viability_pct) + "%"));
    if (p.cells) x.appendChild(h("span", null, num(p.cells) + " cells"));
    if (p.note) li.appendChild(h("div", "sn", p.note));
  }
  if (growth && growth.rows) box.appendChild(table(["From", "To", "Doubling time (h)"], growth.rows.map((r) => [day(r.from), day(r.to), r.doubling_h]), [2]));
  return box;
};

const gatesView = (gt) => {
  const box = h("div");
  const bySample = new Map();
  for (const r of gt.rows) { if (!bySample.has(r.sample || "")) bySample.set(r.sample || "", []); bySample.get(r.sample || "").push(r); }
  for (const [sample, rows] of bySample) {
    if (sample) box.appendChild(h("h3", null, sample));
    const kids = new Map(); for (const r of rows) { const k = r.parent || ""; if (!kids.has(k)) kids.set(k, []); kids.get(k).push(r); }
    const walk = (parent, depth) => {
      for (const r of kids.get(parent) || []) {
        const row = box.appendChild(h("div", "gate"));
        const nm = row.appendChild(h("div", "nm", r.gate)); nm.style.setProperty("--d", depth);
        const known = r.of_parent !== null && r.of_parent !== undefined;  // none: a root gate, or a parent with no events
        const bar = row.appendChild(h("div", "bar")); bar.appendChild(h("div")).style.width = (known ? r.of_parent : r.parent ? 0 : 100) + "%";
        row.appendChild(h("div", "p", known ? num(r.of_parent) + "%" : r.parent ? "—" : "all"));
        row.appendChild(h("div", "e", Number(r.events).toLocaleString("en-GB")));
        row.title = `${r.gate}: ${num(r.of_total)}% of all events`;
        if (depth < 12) walk(r.gate, depth + 1);
      }
    };
    walk("", 0);
  }
  return box;
};

const animalView = (r, wt) => {
  const box = h("div");
  const color = paint;
  if (r.groups && r.groups.length) {
    const cs = box.appendChild(h("div", "cohorts"));
    for (const g of r.groups) {
      const c = cs.appendChild(h("div", "cohort")); c.style.setProperty("--g", color(g.name));
      c.appendChild(h("b", null, g.name)); c.appendChild(h("div", "big", "n = " + g.n));
      if (g.treatment) c.appendChild(h("div", null, g.treatment));
      if (g.dose) c.appendChild(h("div", "muted", g.dose));
    }
  }
  if (wt && wt.series && wt.series.length) {
    const groups = [...new Set(wt.series.map((x) => x.group))];
    const series = groups.map((g) => ({ name: g, color: color(g), points: wt.series.filter((x) => x.group === g).map((x) => ({ x: Date.parse(x.date), y: x.mean, lo: x.sd !== null ? x.mean - x.sd : undefined, hi: x.sd !== null ? x.mean + x.sd : undefined })) }));
    const fig = box.appendChild(h("div")); fig.style.marginTop = "18px";
    fig.appendChild(h("p", "chart-title", "Body weight, % change from each animal's first weight (mean ± SD)"));
    fig.appendChild(lineChart(series, { dates: true, ylabel: "% change", ref: 0, zero: true, w: 760, h: 300 }));
  }
  return box;
};
