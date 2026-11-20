// ---------------------------------------------------------------- flow cytometry: density plots with gates
const RAMP = [[0, [43, 60, 255]], [0.25, [0, 200, 255]], [0.5, [46, 230, 46]], [0.75, [255, 228, 0]], [1, [255, 26, 0]]];
const ramp = (t) => {
  for (let i = 1; i < RAMP.length; i++) if (t <= RAMP[i][0]) {
    const [a, ca] = RAMP[i - 1], [b, cb] = RAMP[i], f = (t - a) / (b - a);
    return ca.map((v, k) => Math.round(v + (cb[k] - v) * f));
  }
  return RAMP[RAMP.length - 1][1];
};
// events as dots, each coloured by the density where it lies, densest drawn last; 3x pixels so it stays sharp
const bytes = (b64) => { const r = atob(b64), out = new Uint8Array(r.length); for (let i = 0; i < r.length; i++) out[i] = r.charCodeAt(i); return out; };
const dotsImage = (d, w, h) => {
  const S = 3, cv = document.createElement("canvas"); cv.width = Math.round(w * S); cv.height = Math.round(h * S);
  const ctx = cv.getContext("2d"), xs = bytes(d.x), ys = bytes(d.y), lv = bytes(d.level), size = 1.15 * S;
  const colours = []; for (let v = 0; v < 256; v++) colours.push(`rgb(${ramp(Math.max(0, v - 1) / 254).join(",")})`);
  for (let i = 0; i < d.n; i++) {
    const fx = (xs[2 * i] | (xs[2 * i + 1] << 8)) / 65535, fy = (ys[2 * i] | (ys[2 * i + 1] << 8)) / 65535;
    ctx.fillStyle = colours[lv[i]];
    ctx.fillRect(fx * cv.width - size / 2, (1 - fy) * cv.height - size / 2, size, size);
  }
  return cv.toDataURL("image/png");
};
const dotPlot = (pl) => {
  const W = 330, H = 320, m = { l: 50, r: 10, t: 10, b: 46 }, x0 = m.l, x1 = W - m.r, y0 = H - m.b, y1 = m.t;
  const X = scaleLin(pl.x.lo, pl.x.hi, x0, x1);
  const twoD = !!pl.y, Y = twoD ? scaleLin(pl.y.lo, pl.y.hi, y0, y1) : null;
  const g = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", "aria-label": `${pl.x.label}${twoD ? " vs " + pl.y.label : ""}` });
  const defs = g.appendChild(s("defs")); const clipId = "c" + Math.random().toString(36).slice(2);
  defs.appendChild(s("clipPath", { id: clipId })).appendChild(s("rect", { x: x0, y: y1, width: x1 - x0, height: y0 - y1 }));
  g.appendChild(s("rect", { x: x0, y: y1, width: x1 - x0, height: y0 - y1, fill: "var(--surface-2)", stroke: "var(--line-strong)" }));
  const body = g.appendChild(s("g", { "clip-path": `url(#${clipId})` }));
  if (twoD && pl.dots && pl.dots.n) body.appendChild(s("image", { href: dotsImage(pl.dots, x1 - x0, y0 - y1), x: x0, y: y1, width: x1 - x0, height: y0 - y1, preserveAspectRatio: "none" }));
  let Yh = null;
  if (!twoD && pl.histogram) {
    const n = pl.histogram.length, max = Math.max(1, ...pl.histogram); Yh = scaleLin(0, max * 1.1, y0, y1);
    const step = (pl.x.hi - pl.x.lo) / n;
    const d = "M" + x0 + "," + y0 + pl.histogram.map((c, i) => `L${X(pl.x.lo + (i + 0.5) * step)},${Yh(c)}`).join("") + `L${x1},${y0}Z`;
    body.appendChild(s("path", { d, fill: "var(--k-sorting)", opacity: 0.22, stroke: "var(--k-sorting)", "stroke-width": 1.5 }));
  }
  let last = -1e9;  // a label too close to the one before (around zero) is left out
  for (const [v, lab] of pl.x.ticks) { const px = X(v); if (px < x0 - 1 || px > x1 + 1 || px - last < 22) continue; last = px; g.appendChild(s("line", { x1: px, x2: px, y1: y0, y2: y0 + 4, stroke: "var(--faint)" })); g.appendChild(s("text", { x: px, y: y0 + 15, "text-anchor": "middle" }, lab)); }
  last = 1e9;
  if (twoD) for (const [v, lab] of pl.y.ticks) { const py = Y(v); if (py < y1 - 1 || py > y0 + 1 || last - py < 14) continue; last = py; g.appendChild(s("line", { x1: x0 - 4, x2: x0, y1: py, y2: py, stroke: "var(--faint)" })); g.appendChild(s("text", { x: x0 - 7, y: py + 3.5, "text-anchor": "end" }, lab)); }
  g.appendChild(s("text", { x: (x0 + x1) / 2, y: H - 8, "text-anchor": "middle", class: "glab" }, pl.x.label));
  g.appendChild(s("text", { x: 12, y: (y0 + y1) / 2, transform: `rotate(-90 12 ${(y0 + y1) / 2})`, "text-anchor": "middle", class: "glab" }, twoD ? pl.y.label : "events"));
  for (const gt of pl.gates || []) {
    const label = `${gt.name}${gt.pct !== null && gt.pct !== undefined ? " " + num(gt.pct) + "%" : ""}`;
    let lx, ly;
    if (gt.points && twoD) {
      const pts = gt.points.map(([a, b]) => [X(a), Y(b)]);
      body.appendChild(s("path", { d: "M" + pts.map((p) => p.join(",")).join("L") + "Z", fill: "none", stroke: "var(--ink)", "stroke-width": 1.6, "stroke-linejoin": "round" }));
      const top = pts.reduce((a, b) => (b[1] < a[1] ? b : a));
      lx = Math.min(Math.max(top[0], x0 + 4), x1 - 80); ly = Math.max(top[1] - 6, y1 + 12);
    } else if (gt.lo !== undefined) {
      const a = X(gt.lo), b = X(gt.hi), yb = y1 + 26;
      body.appendChild(s("path", { d: `M${a},${yb + 8}V${yb}H${b}V${yb + 8}`, fill: "none", stroke: "var(--ink)", "stroke-width": 1.6 }));
      body.appendChild(s("rect", { x: a, y: yb, width: Math.max(0, b - a), height: y0 - yb, fill: "var(--ink)", opacity: 0.04 }));
      lx = Math.min(Math.max(a, x0 + 4), x1 - 80); ly = yb - 6;
    } else continue;
    g.appendChild(s("text", { x: lx, y: ly, class: "glab" }, label));
  }
  return g;
};
const flowView = (fl) => {
  const box = h("div");
  const samples = fl.samples || [];
  if (!samples.length) { box.appendChild(h("p", "empty", "No FCS file could be read.")); if ((fl.checks || []).length) box.appendChild(checks(fl.checks)); return box; }
  const pick = box.appendChild(h("div", "fsamples")), view = box.appendChild(h("div"));
  const draw = (smp) => {
    view.textContent = "";
    for (const b of pick.childNodes) b.setAttribute("aria-pressed", String(b.dataset.s === smp.sample));
    view.appendChild(h("div", "fmeta", h("b", null, Number(smp.events).toLocaleString("en-GB") + " events"), h("span", "mono", smp.file),
      h("span", "tag", smp.compensated && smp.compensated.length ? `compensated · ${smp.compensated.length} channels` : "not compensated"),
      h("span", null, "density", h("span", "ramp"), "high")));
    const plots = view.appendChild(h("div", "fplots"));
    for (const pl of smp.plots || []) {
      const c = plots.appendChild(h("div", "fplot"));
      c.appendChild(h("p", "t", h("b", null, pl.parent), ` · ${Number(pl.events).toLocaleString("en-GB")} events`));
      c.appendChild(dotPlot(pl));
    }
    if ((smp.gates || []).length) { const t = view.appendChild(h("div")); t.style.marginTop = "16px"; t.appendChild(gatesView({ rows: smp.gates.map((r) => ({ ...r, sample: "" })) })); }
  };
  for (const smp of samples) { const b = pick.appendChild(h("button", null, smp.sample)); b.dataset.s = smp.sample; b.addEventListener("click", () => draw(smp)); }
  if (samples.length < 2) pick.remove();
  draw(samples[0]);
  const sm = fl.summary || {};
  if (samples.length > 1 && (sm.gates || []).length) {
    box.appendChild(h("h3", null, "Across samples · % of parent"));
    box.appendChild(table(["Sample", ...sm.gates], sm.rows.map((r) => r.map((v, i) => (i && typeof v === "number" ? num(v) + "%" : v ?? "—"))), sm.gates.map((_, i) => i + 1)));
  }
  return box;
};
