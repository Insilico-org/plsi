const entryView = (x) => {
  const e = x.entry, r = e.results || {}, d = x.derived || {};
  paint = entryColors(e);
  const v = kvar(h("div"), e.kind);
  v.appendChild(h("div", "crumbs", h("span", null, e.project || "No project"), h("span", null, kname(e.kind)), h("span", "mono", e.id)));
  const head = v.appendChild(h("div", "head"));
  const left = head.appendChild(h("div", null));
  const tl = left.appendChild(h("div", null)); tl.style.display = "flex"; tl.style.gap = "14px"; tl.style.alignItems = "center";
  tl.appendChild(kvar(h("div", "kico", icon(own(KINDS, e.kind) ? e.kind : "other")), e.kind));
  tl.appendChild(h("h1", null, e.title));
  const meta = left.appendChild(h("div", "meta"));
  meta.appendChild(pill(x.status));
  meta.appendChild(h("span", null, h("b", null, day(e.date))));
  meta.appendChild(h("span", null, `version ${x.version} · saved ${stamp(x.saved_at)}`));
  for (const t of e.tags || []) meta.appendChild(h("span", "tag", "#" + t));
  if (e.amends) { const a = meta.appendChild(h("a", null, "amends " + e.amends)); a.href = "#entry/" + e.amends; }
  for (const rid of e.related || []) {  // what this entry builds on, by title when it is in the journal
    const other = E.find((y) => y.entry.id === rid), a = meta.appendChild(h("a", "tag", "↳ " + (other ? other.entry.title : rid)));
    a.href = "#entry/" + rid;
  }
  const after = E.filter((y) => (y.entry.related || []).includes(e.id));
  for (const y of after) { const a = meta.appendChild(h("a", "tag", "→ " + y.entry.title)); a.href = "#entry/" + y.entry.id; a.title = "builds on this entry"; }
  const tools = head.appendChild(h("div", "tools"));
  const pr = tools.appendChild(h("button", "btn", icon("print"), "Print")); pr.addEventListener("click", () => window.print());
  if (x.signed) v.appendChild(h("div", "seal", icon("seal"), h("div", null, h("b", null, `Signed by ${x.signed.by}${x.signed.witness ? ", witnessed by " + x.signed.witness : ""}`), h("span", "muted", `${stamp(x.signed.at)} · `), h("span", "mono faint", String(x.signed.hash).slice(0, 19))))).style.marginBottom = "16px";
  if (e.aim) v.appendChild(h("div", "aim", h("small", null, "Aim"), e.aim));
  const grid = v.appendChild(h("div", "grid"));
  // protocol
  const steps = e.protocol || [];
  if (steps.length) {
    const done = steps.filter((p) => p.done).length, mins = steps.reduce((a, p) => a + (p.minutes || 0), 0);
    const prog = h("div", "progress", `${done} of ${steps.length}`); const tr = prog.appendChild(h("div", "track")); tr.appendChild(h("div")).style.width = (done / steps.length * 100) + "%";
    if (mins) prog.appendChild(h("span", null, `${mins >= 90 ? num(mins / 60, 2) + " h" : num(mins) + " min"} hands-on`));
    const ol = h("ol", "steps");
    steps.forEach((p, i) => {
      const li = ol.appendChild(h("li", p.done ? "done" : null));
      li.appendChild(h("div", "tick", p.done ? icon("check") : String(i + 1)));
      const body = li.appendChild(h("div", null, h("div", "st", p.text)));
      const sx = h("div", "sx"); if (p.temp_c !== undefined && p.temp_c !== null) sx.appendChild(h("span", null, num(p.temp_c) + " °C")); if (p.minutes) sx.appendChild(h("span", null, num(p.minutes) + " min"));
      if (p.minutes && !p.done && x.status !== "signed") sx.appendChild(timerButton(`${e.title}: ${p.text}`, p.minutes));
      if (sx.childNodes.length) body.appendChild(sx);
      if (p.note) body.appendChild(h("div", "sn", p.note));
    });
    grid.appendChild(card("Protocol", "list", ol, { size: (e.reagents || []).length || (e.samples || []).length ? "half" : "", sub: prog }));
  }
  if ((e.reagents || []).length || (e.samples || []).length) {
    const box = h("div");
    if ((e.samples || []).length) { box.appendChild(h("h3", null, "Samples")).style.marginTop = "0"; const col = paint;
      box.appendChild(table(["Sample", "Group", "Type", "Detail"], e.samples.map((x2) => [h("b", null, x2.id), x2.group ? swatch(col(x2.group), x2.group) : "", x2.type || "", x2.detail || ""]))); }
    if ((e.reagents || []).length) { box.appendChild(h("h3", null, "Reagents"));
      box.appendChild(table(["Reagent", "Supplier · catalog", "Lot", "Stock", "Used"], e.reagents.map((g) => [h("b", null, g.name), [g.supplier, g.catalog].filter(Boolean).join(" · "), g.lot ? h("span", "mono", g.lot) : "", g.stock || "", g.amount || ""]))); }
    grid.appendChild(card("Materials", "beaker", box, { size: steps.length ? "half" : "" }));
  }
  if (e.plate) grid.appendChild(card("Plate map" + (e.plate.name ? " · " + e.plate.name : ""), "plate", plateMap(e.plate, e.samples), { sub: `${e.plate.format}-well` }));
  // results by what was recorded
  if ((r.cycling || []).length) grid.appendChild(card("Cycling program", "clock", thermal(r.cycling), { sub: `${r.cycling.reduce((a, c) => a + c.seconds * (c.cycles || 1), 0) >= 3600 ? num(r.cycling.reduce((a, c) => a + c.seconds * (c.cycles || 1), 0) / 3600, 2) + " h" : num(r.cycling.reduce((a, c) => a + c.seconds * (c.cycles || 1), 0) / 60) + " min"} at temperature` }));
  const lanes = withLadders(r.lanes || [], d.gel);
  if (lanes.some((l) => (l.observed_bp || []).length || (l.faint_bp || []).length || l.expected_bp)) {
    const box = h("div", "gelwrap");
    box.appendChild(gelView(lanes, { id: "g", label: "gel" }));
    const seen = (l) => l.product ? `standard bands (${l.product})` : [...(l.observed_bp || []).map((b) => "≈" + num(b)), ...(l.faint_bp || []).map((b) => `≈${num(b)} (faint)`)].join(", ");
    box.appendChild(h("div", null, table(["Lane", "Sample", "Expected", "Observed", "Note"], lanes.map((l) => [l.lane, l.ladder ? h("b", null, l.sample || "ladder") : (l.sample || ""), l.expected_bp ? num(l.expected_bp) + " bp" : "", seen(l), l.note || ""]), [0])));
    grid.appendChild(card("Gel", "gel", box, { sub: r.gel ? r.gel + " · drawn from the recorded bands" : "drawn from the recorded bands" }));
  }
  if (d.qpcr && (d.qpcr.groups || []).length) grid.appendChild(card("Relative expression · ΔΔCt", "qpcr", qpcrView(d.qpcr)));
  if (d.western && (d.western.rows || []).length) grid.appendChild(card("Western blot", "western", westernView(d.western, r.bands || []), { sub: "blot drawn from the recorded intensities" }));
  if (d.ci) grid.appendChild(card("Cell index", "xcelligence", ciView(d.ci)));
  if (d.readings) grid.appendChild(card("Readings", "fluorimetry", readingsView(d.readings, r)));
  if ((r.groups || []).length || d.weights) grid.appendChild(card("Animal study", "animal", animalView(r, d.weights)));
  if (d.animals && d.animals.rows.some((a) => a.cage || a.ear_punch)) grid.appendChild(card("Cages", "plate", cagesView(d.animals), { sub: "ear marks seen from above, nose up" }));
  if (d.animals) grid.appendChild(card("Animals", "animal", rosterView(d.animals, e, x.files), { sub: `${d.animals.rows.length} on the roster` }));
  if (d.animals) grid.appendChild(card("Photos", "camera", animalPhotos(d.animals, e, x.files), { sub: "each photo kept with its animal" }));
  if (d.animals && (r.alleles || []).length) grid.appendChild(card("Genotyping", "gel", genotypingView(d.animals, r), { sub: r.genotyping || "drawn from the recorded bands" }));
  if ((r.passages || []).length) grid.appendChild(card("Culture log", "flask", cultureView(r.passages, d.growth), { size: d.gates ? "half" : "" }));
  if (d.vessels) {
    grid.appendChild(card("Plates, flasks and vials", "flask", vesselsView(d.vessels.rows), { sub: `${d.vessels.rows.length} recorded` }));
    const frozen = d.vessels.rows.filter((v) => v.box && v.position && (!v.status || v.status === "frozen")), byBox = {};
    for (const v of frozen) (byBox[v.box] = byBox[v.box] || {})[v.position] = v;
    if (frozen.length) { const colour = colorer(null), wrap = h("div", "boxes"); for (const [b, slots] of Object.entries(byBox)) wrap.appendChild(boxGrid(b, slots, colour));
      const link = h("a", null, "Open the cell bank →"); link.href = "#bank"; const box = h("div"); box.appendChild(wrap); box.appendChild(h("p", null, link));
      grid.appendChild(card("Frozen in this entry", "plate", box)); }
  }
  if (d.flow) grid.appendChild(card("Flow cytometry", "sorting", flowView(d.flow), { sub: "gates counted from the events" }));
  if (d.gates) grid.appendChild(card("Gating", "sorting", gatesView(d.gates), { size: (r.passages || []).length ? "half" : "" }));
  if (r.plasmid) { const p = PL.find((q) => q.name === r.plasmid); if (p) { const box = h("div"); box.appendChild(plasmidMap(p, { size: 460 })); const a = box.appendChild(h("a", null, "Open the plasmid →")); a.href = "#plasmid/" + p.name; grid.appendChild(card("Plasmid · " + (p.title || p.name), "plasmid", box, { size: "half" })); } }
  if ((r.images || []).length || (x.files || []).length) grid.appendChild(card("Images and files", "image", gallery(r.images, x.files)));
  const all = entryChecks(x);
  if (all.length) grid.appendChild(card("Checks", "warn", checks(all), { sub: "from the arithmetic, for the scientist to judge" }));
  for (const [title, text, ic] of [["Observations", e.observations, "eye"], ["Conclusion", e.conclusion, "check"], ["Next steps", e.next_steps, "chev"]])
    if (text) grid.appendChild(card(title, ic, prose(text), { size: "third" }));
  const audit = h("ul", "audit");
  for (const hst of (x.history || []).slice().reverse()) audit.appendChild(h("li", null, h("b", null, "v" + hst.version), h("span", null, stamp(hst.saved_at)), h("span", null, hst.signed_by ? "signed · " + hst.signed_by : hst.status), h("span", "mono", String(hst.hash).slice(0, 23))));
  const hist = h("div"); hist.appendChild(audit);
  if (e.record) { const d = hist.appendChild(h("details", "record")); d.appendChild(h("summary", null, "How this entry was made")); d.appendChild(prose(e.record)); }
  grid.appendChild(card("History", "clock", hist, { sub: "every save, with the hash of what was saved" }));
  return v;
};

const plasmidView = (p) => {
  const v = h("div");
  v.appendChild(h("div", "crumbs", h("span", null, "Plasmids"), h("span", "mono", p.name)));
  const head = v.appendChild(h("div", "head"));
  const left = head.appendChild(h("div"));
  left.appendChild(h("h1", null, p.title || p.name));
  left.appendChild(h("div", "meta", h("b", null, Number(p.length).toLocaleString("en-GB") + " bp"), p.backbone ? h("span", null, "backbone " + p.backbone) : null, p.resistance ? h("span", "tag", p.resistance) : null, h("span", null, `${(p.features || []).length} features`)));
  const tools = head.appendChild(h("div", "tools")); const pr = tools.appendChild(h("button", "btn", icon("print"), "Print")); pr.addEventListener("click", () => window.print());
  const wrap = v.appendChild(h("div", "pwrap"));
  const map = plasmidMap(p);
  wrap.appendChild(card("Map", "plasmid", map));
  const side = wrap.appendChild(h("div")); side.style.display = "grid"; side.style.gap = "16px"; side.style.alignContent = "start";
  const ft = table(["Feature", "Kind", "Position", "Strand", "Length"], (p.features || []).map((f) => [swatch(own(FCOL, f.kind) ? FCOL[f.kind] : FCOL.misc, f.name), f.kind, `${f.start}..${f.end}`, f.strand, ((f.end - f.start + p.length) % p.length) + 1]), [4]);
  ft.querySelector("table").classList.add("ftable");
  ft.querySelectorAll("tbody tr").forEach((tr, i) => { tr.addEventListener("mouseenter", () => map.highlight(i)); tr.addEventListener("mouseleave", () => map.highlight(null)); });
  side.appendChild(card("Features", "list", ft));
  if ((p.sites || []).length) {
    const box = h("div"), filt = box.appendChild(h("div", "fsamples")), holder = box.appendChild(h("div"));
    const FILTERS = [["once", (x) => x.cuts === 1], ["twice", (x) => x.cuts === 2], ["5′ ends", (x) => x.ends.includes("5'")],
      ["3′ ends", (x) => x.ends.includes("3'")], ["blunt", (x) => x.ends === "blunt"], ["Type IIS", (x) => x.type_iis], ["all", () => true]];
    const draw = (name) => {
      holder.textContent = "";
      for (const b of filt.childNodes) b.setAttribute("aria-pressed", String(b.dataset.f === name));
      const keep = FILTERS.find((f) => f[0] === name)[1];
      const rows = p.sites.filter(keep).map((x) => [x.cuts === 1 ? h("span", "unique", x.enzyme) : x.enzyme, h("span", "mono", x.site), x.cuts,
        (x.at || []).join(", ") || "—", (x.cut_after || []).join(", ") || "—", x.ends, (x.overhang || []).filter(Boolean).join(", ") || "—"]);
      holder.appendChild(rows.length ? table(["Enzyme", "Site", "Cuts", "Site at", "Cuts after", "Ends", "Overhang"], rows, [2]) : h("p", "empty", "none"));
    };
    for (const [name] of FILTERS) { const b = filt.appendChild(h("button", null, name)); b.dataset.f = name; b.addEventListener("click", () => draw(name)); }
    draw("once");
    v.appendChild(h("div", "grid")).appendChild(card("Restriction sites", "gel", box, { sub: `${p.sites.length} of the panel cut · unique cutters on the map` }));
    v.lastChild.style.marginTop = "16px";
  }
  if (p.note) side.appendChild(card("Note", "eye", prose(p.note)));
  const used = E.filter((x) => (x.entry.results || {}).plasmid === p.name);
  if (used.length) { const ul = h("div", "cards"); for (const x of used) ul.appendChild(entryCard(x)); v.appendChild(h("div", "grid")).appendChild(card("Used in", "list", ul)); }
  return v;
};

const plasmidsView = () => {
  const v = h("div");
  v.appendChild(h("div", "hero", h("p", "eyebrow", "Constructs"), h("h1", null, "Plasmids")));
  v.lastChild.appendChild(h("p", "muted", "Saved from GenBank (SnapGene, Benchling, Addgene) or written by PLSI. Hover a feature to find it on the map."));
  if (!PL.length) { v.appendChild(h("p", "empty", "No plasmids yet: hand PLSI a .gb file.")); return v; }
  const cards = v.appendChild(h("div", "cards")); cards.style.marginTop = "16px";
  for (const p of PL) {
    const b = cards.appendChild(h("button", "ecard")); b.style.setProperty("--k", "var(--k-cloning)");
    b.appendChild(plasmidMap(p, { size: 300 }));
    b.appendChild(h("div", "tt", p.title || p.name));
    b.appendChild(h("div", "bt", `${Number(p.length).toLocaleString("en-GB")} bp · ${(p.features || []).length} features`, p.resistance ? " · " + p.resistance : ""));
    b.addEventListener("click", () => go("plasmid/" + p.name));
  }
  return v;
};

const calcView = () => {
  const v = h("div");
  v.appendChild(h("div", "hero", h("p", "eyebrow", "Bench"), h("h1", null, "Calculators")));
  v.lastChild.appendChild(h("p", "muted", "Live as you type. The same arithmetic as plsi journal calc, so PLSI can record the numbers in an entry."));
  const c = v.appendChild(calculators()); c.style.marginTop = "18px";
  return v;
};
