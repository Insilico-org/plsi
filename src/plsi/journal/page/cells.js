// ---------------------------------------------------------------- vessels and the cell bank
const vesselIcon = (type) => {
  const g = s("svg", { viewBox: "0 0 52 44", class: "vico", "aria-hidden": "true" });
  const t = String(type || "other");
  if (/^t(25|75|175)$/.test(t)) {  // a flask on its side: body, neck, cap, medium
    g.appendChild(s("path", { d: "M4 12h30l8 6v8l-8 6H4z", class: "glass" })); g.appendChild(s("path", { d: "M4 25h30l8-2v3l-8 6H4z", class: "med" }));
    g.appendChild(s("rect", { x: 42, y: 17, width: 7, height: 10, rx: 1.5, class: "cap" })); g.appendChild(s("text", { x: 17, y: 21, "text-anchor": "middle" }, t.toUpperCase()));
  } else if (t.startsWith("dish")) {
    g.appendChild(s("ellipse", { cx: 26, cy: 24, rx: 22, ry: 12, class: "glass" })); g.appendChild(s("ellipse", { cx: 26, cy: 25, rx: 18, ry: 8.5, class: "med" }));
    g.appendChild(s("text", { x: 26, y: 9, "text-anchor": "middle" }, t.replace("dish_", "")));
  } else if (t.startsWith("plate")) {
    const n = Number(t.split("_")[1]) || 6, [rows, cols] = { 6: [2, 3], 12: [3, 4], 24: [4, 6], 48: [6, 8], 96: [8, 12] }[n] || [2, 3];
    g.appendChild(s("rect", { x: 3, y: 7, width: 46, height: 31, rx: 3, class: "glass" }));
    const r = Math.min(40 / cols, 27 / rows) * 0.38;
    for (let i = 0; i < rows; i++) for (let j = 0; j < cols; j++) g.appendChild(s("circle", { cx: 6 + (j + 0.5) * 40 / cols, cy: 10 + (i + 0.5) * 25 / rows, r, class: "well" }));
  } else if (t === "cryovial") {
    g.appendChild(s("rect", { x: 19, y: 3, width: 14, height: 8, rx: 2, class: "cap" })); g.appendChild(s("path", { d: "M20 11h12v24a6 6 0 0 1-12 0z", class: "glass" }));
    g.appendChild(s("path", { d: "M20 26h12v9a6 6 0 0 1-12 0z", class: "med" }));
  } else if (t.startsWith("tube")) {
    g.appendChild(s("rect", { x: 18, y: 2, width: 16, height: 6, rx: 1.5, class: "cap" })); g.appendChild(s("path", { d: "M19 8h14v26l-7 8-7-8z", class: "glass" }));
    g.appendChild(s("path", { d: "M19 26h14v8l-7 8-7-8z", class: "med" }));
  } else g.appendChild(s("rect", { x: 10, y: 8, width: 32, height: 28, rx: 5, class: "glass" }));
  return g;
};
const VTYPE = { t25: "T25 flask", t75: "T75 flask", t175: "T175 flask", dish_6cm: "6 cm dish", dish_10cm: "10 cm dish", dish_15cm: "15 cm dish", plate_6: "6-well plate",
  plate_12: "12-well plate", plate_24: "24-well plate", plate_48: "48-well plate", plate_96: "96-well plate", cryovial: "cryovial", tube_15: "15 mL tube", tube_50: "50 mL tube", other: "vessel" };
const vesselsView = (rows) => {
  const wrap = h("div", "vessels");
  for (const v of rows) {
    const gone = v.status && !["in_use", "frozen"].includes(v.status);
    const t = wrap.appendChild(h("div", "vessel" + (gone ? " gone" : "")));
    t.appendChild(vesselIcon(v.type));
    const b = t.appendChild(h("div", null, h("b", null, v.id), h("div", "m", [VTYPE[v.type] || v.type, v.cell_line, v.passage !== undefined && v.passage !== null ? "P" + v.passage : null].filter(Boolean).join(" · "))));
    const facts = [v.date ? day(v.date) : null, v.cells ? num(v.cells) + " cells" : null, v.confluence_pct !== undefined && v.confluence_pct !== null ? num(v.confluence_pct) + "% confluent" : null,
      v.box ? `box ${v.box}${v.position ? " · " + v.position : ""}` : v.location || null].filter(Boolean);
    if (facts.length) b.appendChild(h("div", "m", facts.join(" · ")));
    if (v.status) b.appendChild(h("span", "tag", v.status.replace(/_/g, " ")));
    if (v.note) b.appendChild(h("div", "sn", v.note));
  }
  return wrap;
};
const boxGrid = (box, slots, colour) => {
  const big = Object.keys(slots).some((p) => /^J|10$/.test(p)), n = big ? 10 : 9;
  const f = h("div", "fbox"); f.appendChild(h("h3", null, `Box ${box}`, h("span", "faint", ` · ${Object.keys(slots).length} of ${n * n}`)));
  const g = f.appendChild(h("div", "fgrid")); g.style.gridTemplateColumns = `16px repeat(${n}, 30px)`;
  g.appendChild(h("div"));
  for (let c = 1; c <= n; c++) g.appendChild(h("div", "ax", c));
  for (let r = 0; r < n; r++) {
    const L = String.fromCharCode(65 + r); g.appendChild(h("div", "ax", L));
    for (let c = 1; c <= n; c++) {
      const v = slots[L + c], cell = g.appendChild(h("div", "slot" + (v ? " on" : "")));
      if (v) { cell.style.background = colour(v.cell_line || "unnamed"); cell.textContent = v.passage !== undefined && v.passage !== null ? "P" + v.passage : "";
        cell.title = `${L}${c} · ${v.id} · ${v.cell_line || "no line"}${v.passage !== undefined && v.passage !== null ? " P" + v.passage : ""}${v.date ? " · frozen " + day(v.date) : ""}${v.cells ? " · " + num(v.cells) + " cells" : ""}`; }
      else cell.title = L + c;
    }
  }
  return f;
};
const BANK = P.bank || { vials: [], boxes: [], stock: [], checks: [] };
const bankView = () => {
  const v = h("div");
  v.appendChild(h("div", "hero", h("p", "eyebrow", "Cells"), h("h1", null, "Cell bank")));
  v.lastChild.appendChild(h("p", "muted", "Every cryovial in the journal at its latest record. Hover a position for its label, line, passage and date."));
  const colour = colorer(null), grid = v.appendChild(h("div", "grid")); grid.style.marginTop = "16px";
  if (!BANK.vials.length) { grid.appendChild(card("Vials", "flask", h("div", "dropzone", icon("flask"), h("b", null, "No vials yet"), h("span", null, "Tell PLSI when you freeze cells: line, passage, how many vials, box and positions.")))); return v; }
  grid.appendChild(card("In stock", "flask", table(["Cell line", "Passage", "Vials"], BANK.stock.map((x) => [swatch(colour(x.cell_line), x.cell_line), x.passage ?? "—", x.vials]), [2]), { size: "third" }));
  const boxes = h("div", "boxes"); for (const b of BANK.boxes) boxes.appendChild(boxGrid(b.box, b.slots, colour));
  grid.appendChild(card("Freezer boxes", "plate", BANK.boxes.length ? boxes : h("p", "empty", "No vial has a box position."), { size: "two3" }));
  grid.appendChild(card("All vials", "list", table(["Vial", "Cell line", "P", "Frozen", "Box", "Position", "Status", "Entry"], BANK.vials.map((x) => {
    const a = h("a", null, x.entry_title); a.href = "#entry/" + x.entry;
    return [h("b", null, x.id), x.cell_line || "", x.passage ?? "", x.date ? day(x.date) : "", x.box || "", x.position || "", x.status ? x.status.replace(/_/g, " ") : "—", a];
  }))));
  if ((BANK.checks || []).length) grid.appendChild(card("Worth a second look", "warn", checks(BANK.checks)));
  return v;
};
