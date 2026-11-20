// ---------------------------------------------------------------- plasmid map
const FCOL = { cds: "#2563eb", promoter: "#16a34a", terminator: "#dc2626", origin: "#ca8a04", marker: "#ea580c", tag: "#10b981", primer: "#7c3aed", site: "#64748b", misc: "#94a3b8" };
// the unique cutters the map can label without clutter: those inside a feature named MCS or polylinker first,
// then 8-cutters, then the rest; at most the payload's map_cutters (the table lists all)
const mapCutters = (p) => {
  const mcs = (p.features || []).filter((f) => /mcs|polylinker|multiple cloning/i.test(f.name));
  const inMcs = (x) => mcs.some((f) => x.at[0] >= f.start && x.at[0] <= f.end);
  return (p.sites || []).filter((x) => x.cuts === 1 && !x.type_iis)
    .sort((a, b) => (inMcs(b) - inMcs(a)) || (b.site.length - a.site.length) || a.enzyme.localeCompare(b.enzyme)).slice(0, P.tuning.map_cutters);
};
const plasmidMap = (p, opts = {}) => {
  const S = opts.size || 560, c = S / 2, R = S * 0.29, L = p.length;
  const ang = (bp) => (bp - 1) / L * 2 * Math.PI - Math.PI / 2;
  const pt = (a, r) => [c + r * Math.cos(a), c + r * Math.sin(a)];
  const PAD = S * 0.22;  // label room left and right of the circle
  const g = s("svg", { class: "pmap", viewBox: `${-PAD} 0 ${S + 2 * PAD} ${S}`, role: "img", "aria-label": `${p.name} plasmid map` });
  g.appendChild(s("circle", { cx: c, cy: c, r: R, fill: "none", stroke: "var(--line-strong)", "stroke-width": 3 }));
  g.appendChild(s("circle", { cx: c, cy: c, r: R - 7, fill: "none", stroke: "var(--line)", "stroke-width": 1 }));
  const step = niceTicks(0, L, 8)[1] || L;
  for (let t = 0; t < L; t += step) {
    const a = ang(t + 1), [x1, y1] = pt(a, R - 9), [x2, y2] = pt(a, R - 15), [tx, ty] = pt(a, R - 28);
    g.appendChild(s("line", { x1, y1, x2, y2, stroke: "var(--faint)" }));
    if (t) g.appendChild(s("text", { x: tx, y: ty + 4, "text-anchor": "middle", "font-size": 10 }, t >= 1000 ? num(t / 1000) + " kb" : t));
  }
  // feature lanes: an overlapping feature moves outward
  const feats = (p.features || []).map((f, i) => ({ ...f, i, span: ((f.end - f.start + L) % L) + 1 })).sort((a, b) => b.span - a.span);
  const lanes = [];
  const overl = (a, b) => { const inA = (x) => ((x - a.start + L) % L) < a.span; return inA(b.start) || inA(((b.start + b.span - 2) % L) + 1) || ((b.span > a.span) && ((a.start - b.start + L) % L) < b.span); };
  for (const f of feats) { let k = 0; while ((lanes[k] || []).some((o) => overl(o, f))) k++; (lanes[k] = lanes[k] || []).push(f); f.lane = k; }
  const arcs = [];
  for (const f of feats) {
    const r = R + 12 + f.lane * 17, w = 11, a0 = ang(f.start), a1 = ang(f.start) + f.span / L * 2 * Math.PI;
    const rev = f.strand === "-", head = Math.min((a1 - a0) * 0.45, 9 / r * 1.4);
    const ro = r + w / 2, ri = r - w / 2;
    const [b0, b1] = rev ? [a0 + head, a1] : [a0, a1 - head];
    const [ox0, oy0] = pt(b0, ro), [ox1, oy1] = pt(b1, ro), [ix1, iy1] = pt(b1, ri), [ix0, iy0] = pt(b0, ri);
    const [tx, ty] = pt(rev ? a0 : a1, r);
    const lg = b1 - b0 > Math.PI ? 1 : 0;
    const d = rev
      ? `M${ox1},${oy1}A${ro},${ro} 0 ${lg} 0 ${ox0},${oy0}L${tx},${ty}L${ix0},${iy0}A${ri},${ri} 0 ${lg} 1 ${ix1},${iy1}Z`
      : `M${ox0},${oy0}A${ro},${ro} 0 ${lg} 1 ${ox1},${oy1}L${tx},${ty}L${ix1},${iy1}A${ri},${ri} 0 ${lg} 0 ${ix0},${iy0}Z`;
    const col = own(FCOL, f.kind) ? FCOL[f.kind] : FCOL.misc;
    const path = tip(s("path", { d, fill: col, class: "arc", "data-i": f.i, opacity: 0.92 }), `${f.name} · ${f.kind} · ${f.start}..${f.end} (${f.strand}) · ${f.span} bp`);
    g.appendChild(path); arcs.push(path);
    f.mid = (a0 + a1) / 2; f.r = ro;
  }
  // labels: features and unique cutters, pushed apart on each side
  const labels = feats.map((f) => ({ a: f.mid, r: f.r, text: f.name, cls: "fl", i: f.i }))
    .concat(mapCutters(p).map((x) => ({ a: ang(x.at[0]), r: R + 2, text: `${x.enzyme} (${x.at[0]})`, cls: "el", cut: true })));
  const lr = R + 12 + lanes.length * 17 + 26;
  for (const side of [1, -1]) {
    const list = labels.filter((l) => (Math.cos(l.a) >= 0 ? 1 : -1) === side).map((l) => ({ ...l, y: c + lr * Math.sin(l.a) })).sort((a, b) => a.y - b.y);
    for (let k = 1; k < list.length; k++) if (list[k].y - list[k - 1].y < 15) list[k].y = list[k - 1].y + 15;
    const over = list.length ? list[list.length - 1].y - (S - 12) : 0;
    if (over > 0) for (const l of list) l.y -= over;
    for (let k = list.length - 2; k >= 0; k--) if (list[k + 1].y - list[k].y < 15) list[k].y = list[k + 1].y - 15;
    for (const l of list) {
      const [ax, ay] = pt(l.a, l.r + 2), [bx, by] = pt(l.a, lr - 14);
      const ex = c + side * Math.max(Math.abs(bx - c), Math.sqrt(Math.max(0, lr * lr - (l.y - c) ** 2)) * 0.98);
      if (l.cut) { const [cx1, cy1] = pt(l.a, R - 6), [cx2, cy2] = pt(l.a, R + 6); g.appendChild(s("line", { x1: cx1, y1: cy1, x2: cx2, y2: cy2, stroke: "var(--ink)", "stroke-width": 1.6 })); }
      g.appendChild(s("path", { d: `M${ax},${ay}L${bx},${by}L${ex},${l.y}`, fill: "none", stroke: "var(--line-strong)", "stroke-width": 1 }));
      const t = s("text", { x: ex + side * 5, y: l.y + 4, "text-anchor": side > 0 ? "start" : "end", class: l.cls }, l.text);
      g.appendChild(t);
    }
  }
  g.appendChild(s("text", { x: c, y: c - 4, "text-anchor": "middle", class: "fl", "font-size": 17 }, p.title || p.name));
  g.appendChild(s("text", { x: c, y: c + 16, "text-anchor": "middle" }, Number(L).toLocaleString("en-GB") + " bp"));
  g.highlight = (i) => { g.classList.toggle("hl", i !== null); for (const a of arcs) a.classList.toggle("on", String(a.dataset.i) === String(i)); };
  return g;
};
