// ---------------------------------------------------------------- animals: roster, genotyping, Mendelian ratios
const GT_COLOURS = ["#2563eb", "#00A607", "#db2777", "#ea580c", "#7c3aed", "#0891b2", "#ca8a04"];
const gtColour = (() => { const seen = new Map(); return (g) => { if (!seen.has(g)) seen.set(g, GT_COLOURS[seen.size % GT_COLOURS.length]); return seen.get(g); }; })();
const gtChip = (call, fromBands) => {
  if (!call) return h("span", "faint", "—");
  const c = h("span", "gt" + (call === "failed" ? " failed" : ""), call);
  if (call !== "failed") c.style.setProperty("--g", gtColour(call));
  if (fromBands) c.title = "called from the genotyping bands";
  return c;
};
const sameGt = (a, b) => { const n = (g) => String(g).replace(/−/g, "-").split("/").map((x) => x.trim().toLowerCase()).sort().join("/"); return n(a) === n(b); };
const weeks = (born, on) => { const a = Date.parse(born), b = Date.parse(on); return Number.isFinite(a) && Number.isFinite(b) ? Math.floor((b - a) / (7 * 864e5)) : null; };
// the head from above, nose up: the animal's left ear on the left; a notch is a bite out of the rim, a hole a ring
const earSchema = (punches, size = 64) => {
  const g = s("svg", { viewBox: "0 0 84 56", width: size, height: size * 56 / 84, class: "ears", role: "img",
    "aria-label": punches === null || punches === undefined ? "ear marks not recorded"
      : punches.length ? punches.map((p) => `${p.ear} ${p.at}`).join(", ") : "no ear marks" });
  const ears = { left: [17, 25], right: [67, 25] }, R = 14;
  const uid = "e" + Math.random().toString(36).slice(2), defs = g.appendChild(s("defs"));
  for (const [side, [cx, cy]] of Object.entries(ears)) {
    g.appendChild(s("circle", { cx, cy, r: R, class: "ear" }));
    defs.appendChild(s("clipPath", { id: uid + side })).appendChild(s("circle", { cx, cy, r: R }));
  }
  g.appendChild(s("path", { d: "M42 2 C35 8 31 17 31 28 C31 41 36 53 42 53 C48 53 53 41 53 28 C53 17 49 8 42 2 Z", class: "head" }));
  g.appendChild(s("circle", { cx: 38, cy: 17, r: 1.7, class: "eye" })); g.appendChild(s("circle", { cx: 46, cy: 17, r: 1.7, class: "eye" }));
  g.appendChild(s("circle", { cx: 42, cy: 3.5, r: 1.7, class: "nose" }));
  if (punches === null || punches === undefined) { g.appendChild(s("text", { x: 42, y: 40, "text-anchor": "middle", class: "q" }, "?")); return g; }
  const ANG = { front: -90, back: 90 }, used = new Map();
  for (const p of punches) {
    const [cx, cy] = ears[p.ear] || ears.left, key = p.ear + p.at, k = used.get(key) || 0; used.set(key, k + 1);
    if (p.at === "hole") { g.appendChild(s("circle", { cx: cx + (p.ear === "left" ? -2 : 2) + k * 7 * (p.ear === "left" ? -1 : 1), cy, r: 4, class: "hole" })); continue; }
    const base = p.at === "outer" ? (p.ear === "left" ? 180 : 0) : ANG[p.at];
    const a = (base + (k ? (k % 2 ? 24 : -24) * Math.ceil(k / 2) : 0) * (p.ear === "left" ? -1 : 1)) * Math.PI / 180;
    const nx = cx + R * Math.cos(a), ny = cy + R * Math.sin(a);  // a bite out of the rim: cut, then its edge inside the ear
    g.appendChild(s("circle", { cx: nx, cy: ny, r: 5.6, class: "cut" }));
    g.appendChild(s("circle", { cx: nx, cy: ny, r: 5.6, class: "notch", "clip-path": `url(#${uid}${p.ear === "right" ? "right" : "left"})` }));
  }
  g.appendChild(s("text", { x: 17, y: 52, "text-anchor": "middle", class: "lr" }, "L")); g.appendChild(s("text", { x: 67, y: 52, "text-anchor": "middle", class: "lr" }, "R"));
  tip(g, punches.length ? punches.map((p) => `${p.ear} ear: ${p.at === "hole" ? "hole" : p.at + " notch"}`).join(" · ") : "no ear marks");
  return g;
};
const earCode = (punches) => punches === null || punches === undefined ? "marks not recorded" : !punches.length ? "no marks"
  : punches.map((p) => `${p.ear === "left" ? "L" : "R"} ${p.at}`).join(" · ");
const cagesView = (an) => {
  const byCage = new Map();
  for (const a of an.rows) { const c = a.cage || "no cage"; if (!byCage.has(c)) byCage.set(c, []); byCage.get(c).push(a); }
  const wrap = h("div", "cages");
  for (const [cage, list] of byCage) {
    const c = wrap.appendChild(h("div", "cage"));
    const sexes = list.reduce((m, a) => ({ ...m, [a.sex || "?"]: (m[a.sex || "?"] || 0) + 1 }), {});
    c.appendChild(h("div", "ch-head", h("b", null, cage), h("span", "faint", Object.entries(sexes).map(([k, n]) => `${n} ${k === "F" ? "♀" : k === "M" ? "♂" : k}`).join(" · "))));
    for (const a of list) {
      const off = a.status && a.status !== "alive";  // faded only on a recorded off-study status
      const m = c.appendChild(h("div", "mouse" + (off ? " gone" : "")));
      m.appendChild(earSchema(a.ear_punch, 76));
      m.appendChild(h("div", null, h("b", null, a.id), h("div", "earcode", earCode(a.ear_punch)), h("div", null, gtChip(a.call, a.from_bands)), off ? h("div", "faint", a.status.replace(/_/g, " ")) : null));
    }
  }
  return wrap;
};
const photosOf = (e, files) => {
  const src = new Map((files || []).filter((f) => f.src).map((f) => [f.name, f.src])), out = new Map();
  for (const im of (e.results || {}).images || []) if (im.animal && src.has(im.file)) { if (!out.has(im.animal)) out.set(im.animal, []); out.get(im.animal).push({ ...im, src: src.get(im.file) }); }
  return out;
};
const animalPhotos = (an, e, files) => {
  const photos = photosOf(e, files), box = h("div");
  if (!photos.size) {
    box.appendChild(h("div", "dropzone", icon("camera"), h("b", null, "No photos yet"),
      h("span", null, "Send PLSI a photo of an animal (identification, phenotype, a lesion or a tumour) and say which one: it is kept with this entry and shown here.")));
    return box;
  }
  const gal = box.appendChild(h("div", "gallery"));
  for (const a of an.rows) for (const im of photos.get(a.id) || []) {
    const fig = gal.appendChild(h("figure")), img = fig.appendChild(h("img")); img.src = im.src; img.alt = a.id; img.loading = "lazy";
    img.addEventListener("click", () => lightbox(im.src, a.id));
    fig.appendChild(h("figcaption", null, h("b", null, a.id), gtChip(a.call, a.from_bands), a.group ? h("span", "ch", a.group) : null, im.note ? h("span", "muted", im.note) : null));
  }
  return box;
};
const rosterView = (an, e, files) => {
  const photos = photosOf(e, files);
  const rows = an.rows.map((a) => {
    const ph = earSchema(a.ear_punch, 64);
    let cam = null;
    if (photos.has(a.id)) { cam = h("button", "cam", icon("camera")); cam.title = `photo of ${a.id}`; cam.addEventListener("click", () => lightbox(photos.get(a.id)[0].src, a.id)); }
    const age = weeks(a.born, e.date);
    const chg = a.change === null || a.change === undefined ? "" : h("span", "chg " + (a.change <= -P.tuning.weight_loss_pct ? "down" : a.change > 0 ? "up" : ""), (a.change > 0 ? "+" : "") + num(a.change, 2) + "%");
    return [ph, h("div", null, h("b", null, a.id), cam, h("div", "earcode", earCode(a.ear_punch)), a.ear_tag ? h("div", "faint", "tag " + a.ear_tag) : null, a.note ? h("div", "sn", a.note) : null),
      a.sex ? h("span", "sex " + a.sex, a.sex === "F" ? "♀ F" : a.sex === "M" ? "♂ M" : a.sex) : "",
      age !== null ? `${age} wk` : "", a.group ? swatch(paint(a.group), a.group) : "", a.cage || "", a.strain || "",
      h("span", null, gtChip(a.call, a.from_bands), a.genotype && a.from_bands && !sameGt(a.genotype, a.call) ? h("span", "check-inline", ` ⚠ written ${a.genotype}`) : null), a.weight ? h("span", null, num(a.weight) + " g ", chg) : "", a.status ? h("span", "tag", a.status.replace(/_/g, " ")) : h("span", "faint", "—")];
  });
  const t = table(["Ears", "Animal", "Sex", "Age", "Group", "Cage", "Strain", "Genotype", "Weight", "Status"], rows);
  t.querySelector("table").classList.add("roster");
  return t;
};
const genotypingView = (an, r) => {
  const box = h("div");
  const typed = an.rows.filter((a) => a.bands !== null && a.bands !== undefined);
  if (typed.length) {
    const lanes = typed.map((a, i) => ({ lane: i + 1, sample: a.id, observed_bp: a.bands }));
    const wrap = box.appendChild(h("div", "gelwrap"));
    wrap.appendChild(gelView(lanes, { id: "geno", names: true, marks: (r.alleles || []).map((al) => ({ bp: al.bp, label: `${al.name} ${num(al.bp)}` })), label: "genotyping gel" }));
    const calls = wrap.appendChild(h("div"));
    calls.style.flex = "1 1 260px"; calls.style.alignSelf = "center";
    const counts = an.counts || {};
    const kb = calls.appendChild(h("div", "kbars")), max = Math.max(1, ...Object.values(counts));
    for (const [g, n] of Object.entries(counts)) { kb.appendChild(gtChip(g)); const b = kb.appendChild(h("div", "b")); b.style.width = (n / max * 100) + "%"; b.style.background = gtColour(g); kb.appendChild(h("span", "c", n)); }
  }
  const m = an.mendel;
  if (m) {
    box.appendChild(h("h3", null, "Against the cross · observed vs expected"));
    const grid = box.appendChild(h("div", "mendel")), top = Math.max(...m.rows.map((x) => Math.max(x.observed, x.expected))) * 1.1 || 1;
    for (const row of m.rows) {
      grid.appendChild(gtChip(row.genotype));
      const tr = grid.appendChild(h("div", "tr")), ob = tr.appendChild(h("div", "ob"));
      ob.style.width = (row.observed / top * 100) + "%"; ob.style.setProperty("--g", gtColour(row.genotype));
      tr.appendChild(h("div", "ex")).style.left = (row.expected / top * 100) + "%";
      tr.title = `${row.genotype}: ${row.observed} seen, ${num(row.expected)} expected`;
      grid.appendChild(h("span", "nums", h("b", null, row.observed), ` seen · ${num(row.expected)} expected`));
    }
    const v = box.appendChild(h("div", "verdict"));
    v.appendChild(h("b", null, `χ² = ${num(m.chi2)}, df ${m.df}, p = ${m.p === null ? "—" : num(m.p, 2)}`));
    v.appendChild(document.createTextNode(` · n = ${m.n} · bars: animals seen, dashed line: expected from the cross`));
  }
  return box;
};
