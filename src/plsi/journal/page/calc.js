// ---------------------------------------------------------------- calculators (the same arithmetic as plsi journal calc)
const U = P.units || {};
const qty = (id, label, unitFamily, unit, value) => {
  const f = h("div", "field"), lab = f.appendChild(h("label", null, label)); lab.htmlFor = id;
  const q = f.appendChild(h("div", "qty")), inp = q.appendChild(h("input")); inp.id = id; inp.type = "number"; inp.step = "any"; inp.inputMode = "decimal";
  if (value !== undefined) inp.value = value;
  let sel = null;
  if (unitFamily) {
    sel = q.appendChild(h("select")); sel.setAttribute("aria-label", label + " unit");
    for (const u of Object.keys(unitFamily).filter((u) => /^[\x20-\x7e]+$/.test(u))) { const o = sel.appendChild(h("option", null, u.replace(/^u/, "µ"))); o.value = u; }
    if (unit) sel.value = unit;
  } else if (unit) q.appendChild(h("span", "faint", unit)).style.padding = "7px 9px";
  f.read = () => { const v = parseFloat(inp.value); return unitFamily ? v * unitFamily[sel.value] : v; };
  f.unit = () => (sel ? sel.value : "");
  f.inputs = [inp, sel].filter(Boolean);
  return f;
};
const show = (v, fam) => {
  const units = []; const seen = new Set();
  for (const [u, sc] of Object.entries(fam)) if (!seen.has(sc) && /^[\x20-\x7e]+$/.test(u) && u !== "%") { seen.add(sc); units.push([u, sc]); }
  units.sort((a, b) => b[1] - a[1]);
  const min = Math.min(...units.map((x) => x[1]));
  const pipette = fam === (U.volume || {}) && Math.abs(v) >= 1e-7 && Math.abs(v) < 1e-6;  // 0.4 µL, not 400 nL
  if (pipette) return num(v / 1e-6, 4) + " µL";
  for (const [u, sc] of units) if (Math.abs(v) >= sc || sc === min) return num(v / sc, 4) + " " + u.replace(/^u/, "µ");
  return num(v);
};
const calcCard = (title, desc, fields, compute) => {
  const c = h("section", "calc");
  c.appendChild(h("h2", null, h("span", "hico", icon("calc")), title));
  c.appendChild(h("p", "d", desc));
  const grid = c.appendChild(h("div", "fields")); for (const f of fields) grid.appendChild(f);
  const ans = c.appendChild(h("div", "answer"));
  const run = () => {
    ans.textContent = ""; ans.className = "answer";
    try {
      const r = compute();
      if (!r) { ans.appendChild(h("span", "faint", "fill in the fields")); return; }
      ans.appendChild(h("div", "big", r.big));
      if (r.table) ans.appendChild(r.table);
      if (r.lines) { const ul = ans.appendChild(h("ul", "lines")); for (const l of r.lines) ul.appendChild(h("li", null, l)); }
    } catch (e) { ans.className = "answer err"; ans.textContent = e.message; }
  };
  c.addEventListener("input", run); c.addEventListener("change", run); run();
  c.run = run;
  return c;
};
const need = (...vals) => vals.every((v) => Number.isFinite(v));
const calculators = () => {
  const M = U.molar || {}, V = U.volume || {}, MS = U.mass || {}, MC = U.mass_conc || {};
  const wrap = h("div", "calcs");
  { const c1 = qty("d-c1", "Stock (C1)", M, "mM", 10), c2 = qty("d-c2", "Final (C2)", M, "uM", 100), v2 = qty("d-v2", "Final volume (V2)", V, "mL", 1);
    wrap.appendChild(calcCard("Dilution", "C1·V1 = C2·V2: how much stock and diluent.", [c1, c2, v2], () => {
      const a = c1.read(), b = c2.read(), v = v2.read(); if (!need(a, b, v) || !a) return null;
      if (b > a) throw new Error("the final concentration is above the stock");
      const v1 = b * v / a; return { big: show(v1, V) + " stock", lines: [`+ ${show(v - v1, V)} diluent → ${show(v, V)}`, `${num(a / b)}-fold dilution`] };
    })); }
  { const mass = qty("m-mass", "Mass", MS, "mg"), mw = qty("m-mw", "Molecular weight", null, "g/mol", 58.44), conc = qty("m-c", "Concentration", M, "mM", 100), vol = qty("m-v", "Volume", V, "mL", 50);
    wrap.appendChild(calcCard("Molarity", "Leave one field empty: it is calculated from the other three.", [mass, mw, conc, vol], () => {
      const g = mass.read(), w = mw.read(), m = conc.read(), v = vol.read(), empty = [g, w, m, v].filter((x) => !Number.isFinite(x)).length;
      if (empty !== 1) return null;
      if (!Number.isFinite(g)) return { big: show(m * v * w, MS), lines: ["mass = concentration × volume × MW"] };
      if (!Number.isFinite(m)) return { big: show(g / w / v, M), lines: ["concentration = mass ÷ MW ÷ volume"] };
      if (!Number.isFinite(v)) return { big: show(g / w / m, V), lines: ["volume = mass ÷ MW ÷ concentration"] };
      return { big: num(g / m / v, 5) + " g/mol", lines: ["MW = mass ÷ concentration ÷ volume"] };
    })); }
  { const live = h("div", "field"); live.appendChild(h("label", null, "Live cells per large square")); const li = live.appendChild(h("div", "qty")).appendChild(h("input")); li.placeholder = "e.g. 52, 48, 55, 50"; li.value = "52, 48, 55, 50";
    const dead = h("div", "field"); dead.appendChild(h("label", null, "Dead (blue) per square")); const di = dead.appendChild(h("div", "qty")).appendChild(h("input")); di.value = "3, 2, 4, 1";
    const dfac = qty("h-df", "Dilution (trypan 1:1 = 2)", null, "×", 2), vol = qty("h-v", "Suspension volume", V, "mL", 5);
    wrap.appendChild(calcCard("Hemocytometer", "Cells per mL and viability from a Neubauer count.", [live, dead, dfac, vol], () => {
      const nums = (t) => t.split(/[,;\s]+/).map(Number).filter(Number.isFinite);
      const L = nums(li.value), D = nums(di.value), df = dfac.read(); if (!L.length || !need(df)) return null;
      const ml = L.reduce((a, b) => a + b, 0) / L.length, md = D.length ? D.reduce((a, b) => a + b, 0) / D.length : 0, per = ml * df * 1e4, v = vol.read();
      return { big: num(per, 4) + " cells/mL", lines: [`viability ${num(ml / (ml + md) * 100, 3)}%`, Number.isFinite(v) ? `${num(per * v * 1e3, 4)} cells in total` : "", `mean ${num(ml)} per square × ${df} × 10⁴`].filter(Boolean) };
    })); }
  { const stock = qty("s-st", "Cells per mL (counted)", null, "/mL", 1.2e6);
    const plate = h("div", "field"); plate.appendChild(h("label", null, "Plate")); const ps = plate.appendChild(h("div", "qty")).appendChild(h("select")); ps.style.borderLeft = "0"; ps.style.width = "100%";
    for (const k of Object.keys(U.wells || {})) { const o = ps.appendChild(h("option", null, k + "-well")); o.value = k; } ps.value = "96";
    const per = qty("s-pw", "Cells per well", null, "cells", 10000), wells = qty("s-w", "Wells", null, "", 60), vol = qty("s-v", "Volume per well", V, "uL", 100), over = qty("s-o", "Overage", null, "%", 10);
    wrap.appendChild(calcCard("Cell seeding", "Suspension and medium for a plate.", [stock, plate, per, wells, vol, over], () => {
      const st = stock.read(), pw = per.read(), n = wells.read(), v = vol.read() * 1e3, o = 1 + (over.read() || 0) / 100; if (!need(st, pw, n, v) || !st) return null;
      const cells = pw * n * o, susp = cells / st, total = v * n * o, wl = (U.wells || {})[ps.value];
      if (susp > total) throw new Error("the suspension is too dilute: spin down and resuspend");
      return { big: show(susp / 1e3, V) + " suspension", lines: [`+ ${show((total - susp) / 1e3, V)} medium = ${show(total / 1e3, V)}`, `${num(cells, 4)} cells with overage`, wl ? `${num(pw / wl.area, 4)} cells/cm² (${wl.area} cm² per well)` : ""].filter(Boolean) };
    })); }
  { const n = qty("mm-n", "Reactions", null, "", 24), o = qty("mm-o", "Overage", null, "%", 10), rv = qty("mm-r", "Reaction volume", V, "uL", 20), tv = qty("mm-t", "Template per reaction", V, "uL", 2);
    const rows = h("div", "field"); rows.style.gridColumn = "1 / -1"; rows.appendChild(h("label", null, "Components: name · stock · final (same unit family)"));
    const list = rows.appendChild(h("div")); list.style.display = "grid"; list.style.gap = "6px";
    const addRow = (name, st, fin) => {
      const r = list.appendChild(h("div")); r.style.display = "grid"; r.style.gridTemplateColumns = "1.2fr 1fr 1fr"; r.style.gap = "6px";
      const mk = (val, ph) => { const q = r.appendChild(h("div", "qty")).appendChild(h("input")); q.value = val; q.placeholder = ph; return q; };
      r.cells = [mk(name, "name"), mk(st, "stock e.g. 10X"), mk(fin, "final e.g. 1X")];
    };
    addRow("buffer", "10X", "1X"); addRow("dNTPs", "10 mM", "200 uM"); addRow("primer F", "10 uM", "0.5 uM"); addRow("primer R", "10 uM", "0.5 uM"); addRow("polymerase", "", "0.2 uL");
    const more = rows.appendChild(h("button", "mini-btn", "+ component"));
    const FOLD = { X: 1, x: 1 };
    const parse = (t) => { const m = /^\s*([\d.eE+-]+)\s*(\S*)\s*$/.exec(t || ""); if (!m) return null; const v = parseFloat(m[1]), u = m[2].replace("µ", "u");
      for (const fam of [M, MC, FOLD]) if (own(fam, u)) return { v: v * fam[u], fam }; if (own(V, u)) return { v: v * V[u], vol: true }; return null; };
    const card = calcCard("Master mix", "Per reaction and for the whole mix; water fills to volume.", [n, o, rv, tv, rows], () => {
      const N = n.read(), k = N * (1 + (o.read() || 0) / 100), R = rv.read(), T = tv.read() || 0; if (!need(N, R) || !R) return null;
      let used = T; const out = [];
      for (const r of list.childNodes) {
        const [nm, st, fi] = r.cells.map((c) => c.value); if (!nm) continue;
        const f = parse(fi), sv = parse(st); let per;
        if (f && f.vol) per = f.v; else if (f && sv && f.fam === sv.fam && sv.v) per = f.v / sv.v * R; else throw new Error(`${nm}: give stock and final in one unit family, or a final volume`);
        used += per; out.push([nm, show(per, V), show(per * k, V)]);
      }
      if (used > R + 1e-12) throw new Error("the components add up to more than the reaction volume");
      out.unshift(["water", show(R - used, V), show((R - used) * k, V)]);
      return { big: `${num(k, 3)} reactions of mix`, table: table(["Component", "Per reaction", "Mix"], out), lines: [`aliquot ${show(R - T, V)} per tube, then ${show(T, V)} template`] };
    });
    more.addEventListener("click", () => { addRow("", "", ""); card.run(); });
    wrap.appendChild(card); }
  { const vm = qty("l-vm", "Vector", MS, "ng", 50), vl = qty("l-vl", "Vector length", null, "bp", 5000), il = qty("l-il", "Insert length", null, "bp", 1000), ra = qty("l-r", "Insert : vector (molar)", null, ": 1", 3), ic = qty("l-ic", "Insert concentration", MC, "ng/uL", 20);
    wrap.appendChild(calcCard("Ligation", "Insert mass for a molar ratio.", [vm, vl, il, ra, ic], () => {
      const v = vm.read() * 1e9, a = vl.read(), b = il.read(), r = ra.read(); if (!need(v, a, b, r) || !a) return null;
      const ins = r * v * b / a, c = ic.read() * 1e3;
      return { big: num(ins, 4) + " ng insert", lines: [Number.isFinite(c) && c ? `${num(ins / c, 3)} µL of insert` : "", `${r} × ${num(v)} ng × ${b} ÷ ${a} bp`].filter(Boolean) };
    })); }
  { const m = qty("dm-m", "DNA", MS, "ng", 500), l = qty("dm-l", "Length", null, "bp", 3000);
    const st = h("div", "field"); st.appendChild(h("label", null, "Strands")); const ss = st.appendChild(h("div", "qty")).appendChild(h("select")); ss.style.width = "100%"; ss.style.borderLeft = "0";
    for (const [v, t] of [["ds", "double-stranded"], ["ss", "single-stranded"]]) { const o = ss.appendChild(h("option", null, t)); o.value = v; }
    wrap.appendChild(calcCard("DNA mass ↔ moles", "ng to pmol, for ligations, Gibson and transfections.", [m, l, st], () => {
      const ng = m.read() * 1e9, bp = l.read(); if (!need(ng, bp) || !bp) return null;
      const mw = ss.value === "ds" ? bp * 617.96 + 36.04 : bp * 308.97 + 18.02;
      return { big: num(ng / mw * 1e3, 4) + " pmol", lines: [`MW ${num(mw, 5)} g/mol`, `${num(ng / mw * 1e3 * 6.022e11, 3)} copies`] };
    })); }
  { const t = qty("p-t", "Protein per lane", MS, "ug", 20), lv = qty("p-l", "Lane volume", V, "uL", 20), bx = qty("p-b", "Sample buffer", null, "X", 4), cs = h("div", "field"); cs.style.gridColumn = "1 / -1";
    cs.appendChild(h("label", null, "Concentrations (µg/µL), one per sample: name=value"));
    const ci = cs.appendChild(h("div", "qty")).appendChild(h("input")); ci.value = "ctrl=2.1, treated=1.6, KO=2.8";
    wrap.appendChild(calcCard("Western loading", "Equal µg per lane from BCA concentrations.", [t, lv, bx, cs], () => {
      const ug = t.read() * 1e6, L = lv.read() * 1e6, X = bx.read(); if (!need(ug, L, X) || !X) return null;
      const buf = L / X, rows = [];
      for (const part of ci.value.split(",")) { const [nm, v] = part.split("="); const c = parseFloat(v); if (!nm || !Number.isFinite(c) || !c) continue;
        const vol = ug / c; if (vol > L - buf) throw new Error(`${nm.trim()}: ${num(vol)} µL does not fit`); rows.push([nm.trim(), num(vol), num(buf), num(L - buf - vol)]); }
      return { big: `${num(buf)} µL buffer per lane`, table: table(["Sample", "Lysate µL", "Buffer µL", "Water µL"], rows, [1, 2, 3]) };
    })); }
  { const d = qty("ds-d", "Dose", null, "mg/kg", 10), st = qty("ds-s", "Stock", MC, "mg/mL", 1), ws = h("div", "field"); ws.appendChild(h("label", null, "Body weights (g)"));
    const wi = ws.appendChild(h("div", "qty")).appendChild(h("input")); wi.value = "24.1, 25.3, 23.8, 26.0";
    wrap.appendChild(calcCard("Animal dosing", "Volume per animal from mg/kg and the stock.", [d, st, ws], () => {
      const mgkg = d.read(), stock = st.read(); if (!need(mgkg, stock) || !stock) return null;
      const rows = wi.value.split(/[,;\s]+/).map(Number).filter((x) => x > 0).map((w) => [num(w), num(mgkg * w / 1e3), num(mgkg * w / 1e3 / stock * 1e3)]);
      return { big: `${num(mgkg / stock)} mL/kg`, table: table(["Weight g", "mg", "Volume µL"], rows, [0, 1, 2]) };
    })); }
  { const st = qty("sd-s", "Top concentration", M, "uM", 100), f = qty("sd-f", "Fold per step", null, "×", 2), n = qty("sd-n", "Steps", null, "", 8), v = qty("sd-v", "Volume per tube", V, "uL", 200);
    wrap.appendChild(calcCard("Serial dilution", "A standard curve or a dose series.", [st, f, n, v], () => {
      const c0 = st.read(), F = f.read(), N = Math.round(n.read()), vol = v.read(); if (!need(c0, F, N, vol) || F <= 1 || N < 1 || N > 24) return null;
      const t = vol / F, rows = []; for (let i = 1; i <= N; i++) rows.push([i, show(c0 / Math.pow(F, i), M)]);
      return { big: `move ${show(t, V)} each step`, lines: [`${show(vol - t, V)} diluent in each tube`], table: table(["Tube", "Concentration"], rows, [0]) };
    })); }
  { const p = qty("ag-p", "Agarose", null, "%", 1), v = qty("ag-v", "Gel volume", V, "mL", 50);
    wrap.appendChild(calcCard("Agarose gel", "Grams of agarose for the gel.", [p, v], () => {
      const pc = p.read(), ml = v.read() * 1e3; if (!need(pc, ml)) return null;
      return { big: num(pc * ml / 100) + " g agarose", lines: [`in ${num(ml)} mL 1X buffer`] };
    })); }
  { const a = qty("dt-a", "Cells at start", null, "", 2e5), b = qty("dt-b", "Cells at end", null, "", 1.6e6), t = qty("dt-t", "Time", null, "h", 72);
    wrap.appendChild(calcCard("Doubling time", "Population doubling time between two counts.", [a, b, t], () => {
      const n0 = a.read(), n1 = b.read(), hrs = t.read(); if (!need(n0, n1, hrs) || n1 <= n0 || n0 <= 0) return null;
      const g = Math.log2(n1 / n0); return { big: num(hrs / g) + " h", lines: [`${num(g)} doublings`] };
    })); }
  return wrap;
};
