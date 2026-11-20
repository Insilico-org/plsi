"""Plasmids (`journal/plasmids/<name>.json`): GenBank import (as SnapGene, Benchling and Addgene export it), and
where the enzymes of enzymes.csv cut the circular sequence (palindromic, degenerate, Type IIS on both strands) with
the ends each leaves."""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from importlib import resources
from typing import Annotated, Any

from pydantic import Field, model_validator

from plsi.errors import NotFound, ValidationError
from plsi.files import atomic_write_json, load_json, read_input_text
from plsi.journal import home
from plsi.journal.results import Short, Slug, Text
from plsi.models import Model, parse
from plsi.vocab.journal import FeatureKind, Strand

class Feature(Model):
    name: Short
    start: int = Field(ge=1)
    end: int = Field(ge=1)
    kind: FeatureKind = FeatureKind.MISC
    strand: Strand = Strand.FORWARD


class Plasmid(Model):
    name: Slug
    title: str | None = None
    length: int = Field(ge=10, le=500_000)
    backbone: str | None = None
    resistance: str | None = None
    features: list[Feature] = []
    sequence: Annotated[str, Field(pattern=r"^[ACGTNacgtn]*$")] | None = None
    note: Text | None = None

    @model_validator(mode="after")
    def _inside(self) -> Plasmid:
        for f in self.features:
            if f.start > self.length or f.end > self.length:
                raise ValueError(f"feature {f.name!r} lies outside the {self.length} bp plasmid")
        if self.sequence and len(self.sequence) != self.length:
            raise ValueError(f"the sequence has {len(self.sequence)} bp, the plasmid {self.length}")
        return self


_KINDS = {"cds": FeatureKind.CDS, "gene": FeatureKind.CDS, "promoter": FeatureKind.PROMOTER,
          "terminator": FeatureKind.TERMINATOR, "rep_origin": FeatureKind.ORIGIN, "primer_bind": FeatureKind.PRIMER,
          "protein_bind": FeatureKind.SITE, "misc_recomb": FeatureKind.SITE, "polya_signal": FeatureKind.TERMINATOR}
_MARKERS = re.compile(r"amp|kan|neo|puro|hygro|bla|zeo|blast|cm\b|cat\b|spec|tet", re.IGNORECASE)
_TAGS = re.compile(r"gfp|egfp|mcherry|rfp|yfp|cfp|flag|myc|\bha\b|his|v5|strep|luc|nluc|tdtomato", re.IGNORECASE)
_LOC = re.compile(r"(complement\()?(?:join\()?<?(\d+)\.\.>?(\d+)")
_QUAL = re.compile(r'^\s{21}/(\w+)="?([^"]*)"?\s*$')


def _kind(gb_kind: str, name: str) -> FeatureKind:
    kind = _KINDS.get(gb_kind.lower(), FeatureKind.MISC)
    if kind in (FeatureKind.CDS, FeatureKind.MISC) and _MARKERS.search(name):
        return FeatureKind.MARKER
    if kind in (FeatureKind.CDS, FeatureKind.MISC) and _TAGS.search(name):
        return FeatureKind.TAG
    return kind


def from_genbank(text: str, name: str) -> Plasmid:
    """LOCUS length, FEATURES (label/gene/note as the name) and ORIGIN sequence; source features are skipped."""
    lines = text.splitlines()
    locus = next((ln for ln in lines if ln.startswith("LOCUS")), "")
    m = re.search(r"(\d+)\s+bp", locus)
    if not m:
        raise ValidationError("not a GenBank file: no LOCUS line with a length in bp", code="GENBANK_INVALID")
    length = int(m.group(1))
    feats: list[dict[str, Any]] = []
    in_feat = in_origin = False
    seq: list[str] = []
    for ln in lines:
        if ln.startswith("FEATURES"):
            in_feat = True
            continue
        if ln.startswith("ORIGIN"):
            in_feat, in_origin = False, True
            continue
        if ln.startswith("//"):
            break
        if in_origin:
            seq.append(re.sub(r"[^A-Za-z]", "", ln))
        elif in_feat and len(ln) > 21 and ln[5] != " ":
            kind, loc = ln[5:21].strip(), ln[21:].strip()
            lm = _LOC.search(loc)
            feats.append({"gb": kind, "loc": lm, "quals": {}})
        elif in_feat and feats and (q := _QUAL.match(ln)):
            feats[-1]["quals"].setdefault(q.group(1), q.group(2))
    features = []
    for f in (f for f in feats if f["gb"] != "source" and f["loc"] is not None):
        q, lm = f["quals"], f["loc"]
        label = (q.get("label") or q.get("gene") or q.get("product") or q.get("note") or f["gb"])[:200]
        features.append({"name": label, "start": int(lm.group(2)), "end": int(lm.group(3)), "kind": _kind(f["gb"], label),
                         "strand": Strand.REVERSE if lm.group(1) else Strand.FORWARD})
    sequence = "".join(seq).upper() or None
    if sequence and len(sequence) != length:
        sequence = None  # an ORIGIN that does not match LOCUS is dropped, the features kept
    return parse(Plasmid, {"name": name, "length": length, "features": features, "sequence": sequence}, "GenBank file", "GENBANK_INVALID")


IUPAC = {"A": "A", "C": "C", "G": "G", "T": "T", "R": "[AG]", "Y": "[CT]", "S": "[CG]", "W": "[AT]", "K": "[GT]",
         "M": "[AC]", "B": "[CGT]", "D": "[AGT]", "H": "[ACT]", "V": "[ACG]", "N": "[ACGT]"}
COMPLEMENT = str.maketrans("ACGTRYSWKMBDHVN", "TGCAYRSWMKVHDBN")
_TYPE_IIS = re.compile(r"^([A-Z]+)\((-?\d+)/(-?\d+)\)$")


@dataclass(frozen=True)
class Enzyme:
    """`site` in IUPAC letters. Palindromic: `top` is where the top strand is cut inside the site. Type IIS: the
    strands are cut `n` and `m` nt past the site's 3' end, on the strand the site is read on."""

    name: str
    site: str
    top: int | None = None
    n: int | None = None
    m: int | None = None

    @property
    def overhang(self) -> int:
        """> 0: a 5' overhang of that length; < 0: a 3' overhang; 0: blunt."""
        return len(self.site) - 2 * self.top if self.top is not None else self.m - self.n


@functools.cache
def enzymes() -> tuple[Enzyme, ...]:
    """The panel in enzymes.csv: G^AATTC marks the top-strand cut; GGTCTC(1/5) a Type IIS enzyme."""
    out = []
    rows = resources.files("plsi.journal").joinpath("enzymes.csv").read_text(encoding="utf-8").splitlines()[1:]
    for row in rows:
        name, site = row.split(",")
        if m := _TYPE_IIS.match(site):
            out.append(Enzyme(name, m.group(1), n=int(m.group(2)), m=int(m.group(3))))
        else:
            out.append(Enzyme(name, site.replace("^", ""), top=site.index("^")))
    return tuple(out)


def _ends(e: Enzyme) -> str:
    return "blunt" if e.overhang == 0 else f"{abs(e.overhang)} nt {'5' if e.overhang > 0 else '3'}' overhang"


def _hits(seq: str, e: Enzyme) -> list[tuple[int, int, int]]:
    """(site start 0-based, top-strand cut, bottom-strand cut) on the circle; cuts are between nt i-1 and i."""
    size, k = len(seq), len(e.site)
    ring = seq + seq[: k - 1]
    out = []
    for strand, site in ((1, e.site), (-1, e.site.translate(COMPLEMENT)[::-1])):
        if strand == -1 and site == e.site:
            break  # a palindrome reads the same on both strands
        for mt in re.finditer("(?=" + "".join(IUPAC[c] for c in site) + ")", ring):
            i = mt.start()
            if e.top is not None:
                top, bottom = i + e.top, i + k - e.top
            elif strand == 1:
                top, bottom = i + k + e.n, i + k + e.m
            else:
                top, bottom = i - e.m, i - e.n
            out.append((i % size, top, bottom))  # cuts unwrapped: they may lie before 0 or past the end
    return sorted({(i, t, b) for i, t, b in out}, key=lambda h: h[0])


def sites(p: Plasmid, region: tuple[int, int] | None = None) -> list[dict[str, Any]]:
    """Each panel enzyme that cuts the circular sequence: cut count, ends, and for one or two cuts the site start,
    the top-strand cut ("after nt") and the overhang read on the top strand. With `region`, only enzymes that cut
    once in the whole plasmid with their site wholly inside it."""
    if not p.sequence:
        return []
    seq = p.sequence.upper()
    out = []
    for e in enzymes():
        hits = _hits(seq, e)
        if not hits:
            continue
        row = {"enzyme": e.name, "site": e.site, "cuts": len(hits), "ends": _ends(e), "type_iis": e.top is None,
               "at": [h[0] + 1 for h in hits] if len(hits) <= 2 else [],
               "cut_after": [(h[1] - 1) % len(seq) + 1 for h in hits] if len(hits) <= 2 else []}
        if len(hits) <= 2 and e.overhang:
            ring = seq * 3  # the overhang's bases on the top strand, read across the origin when it spans it
            row["overhang"] = [ring[min(t, b) + len(seq): max(t, b) + len(seq)] for _, t, b in hits]
        out.append(row)
    if region:
        lo, hi = region
        out = [r for r in out if r["cuts"] == 1 and lo <= r["at"][0] and r["at"][0] + len(r["site"]) - 1 <= hi]
    return sorted(out, key=lambda r: (r["cuts"], r["enzyme"]))


def saved() -> list[Plasmid]:
    folder = home.root() / "plasmids"
    return [parse(Plasmid, load_json(p)) for p in sorted(folder.glob("*.json"))] if folder.is_dir() else []


def _load(name: str) -> Plasmid:
    if not (path := home.plasmid_path(name)).is_file():
        raise NotFound(f"no plasmid {name!r}", code="PLASMID_NOT_FOUND", hint="plsi journal plasmid save")
    return parse(Plasmid, load_json(path))


def save(file: str | None = None, genbank: str | None = None, name: str | None = None) -> dict[str, Any]:
    """`journal plasmid save`: a Plasmid JSON, or a GenBank file read into one (its name given with --name)."""
    if genbank and not name:
        raise ValidationError("--name: the plasmid's short name (lower case) for a GenBank file", code="PLASMID_NAME")
    p = from_genbank(read_input_text(genbank), name) if genbank else parse(Plasmid, load_json(file))
    path = home.plasmid_path(p.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, p.dump(), private=True)
    return {"name": p.name, "length": p.length, "features": len(p.features), "sequence": bool(p.sequence),
            "unique_cutters": [s["enzyme"] for s in sites(p) if s["cuts"] == 1], "path": str(path)}


def list_saved() -> dict[str, Any]:
    return {"plasmids": [{"name": p.name, "title": p.title, "length": p.length, "features": len(p.features)} for p in saved()]}


def show(name: str, region: str | None = None) -> dict[str, Any]:
    """One plasmid with every cutting enzyme; `region` "1984-2048": also the enzymes cutting once, inside it."""
    p = _load(name)
    out = {**p.dump(), "sites": sites(p)}
    out.pop("sequence", None)  # the bases are in the file; the answer needs the sites
    if region:
        lo, sep, hi = region.replace(" ", "").partition("-")
        if not (sep and lo.isdigit() and hi.isdigit() and 1 <= int(lo) <= int(hi) <= p.length):
            raise ValidationError(f"--region {region!r}: give start-end within 1-{p.length}", code="REGION_INVALID")
        out["region"] = {"from": int(lo), "to": int(hi), "unique_cutters": sites(p, (int(lo), int(hi)))}
    return out
