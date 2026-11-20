"""`plsi journal template --kind K`: a starter entry per experiment kind, with the protocol's usual steps and an
example of the results it records. Placeholders are in <angle brackets>; nothing names a compound or a dose."""

from __future__ import annotations

from typing import Any

from plsi.clock import now
from plsi.vocab.journal import ExperimentKind as K

_STEPS: dict[K, list[str]] = {
    K.PCR: ["Thaw reagents on ice; vortex and spin primers", "Make the master mix (journal calc --kind mastermix)",
            "Aliquot mix, add template; include a no-template control", "Run the cycling program", "Check on a gel"],
    K.GEL: ["Cast <percent>% agarose in 1X TAE with stain (journal calc --kind agarose)", "Load ladder and samples",
            "Run at <V> V for <min> min", "Image on the transilluminator; attach the photo"],
    K.QPCR: ["Extract RNA; record concentration and A260/280", "DNase treat; reverse transcribe <ng> RNA per reaction",
             "Plan the plate: controls in the left columns, cases to the right, 4 replicates per sample, "
             "NTC and no-RT in their own column", "Make the master mix per target",
             "Run: 95 °C 2 min, 40 × (95 °C 15 s, 60 °C 60 s), melt curve", "Export Cts; check melt peaks"],
    K.WESTERN: ["Lyse cells in buffer with inhibitors on ice", "Quantify protein (BCA); equalise loads (journal calc --kind protein_load)",
                "Denature 95 °C 5 min; load gel with ladder", "Transfer to membrane; check with Ponceau",
                "Block 1 h; primary antibody overnight 4 °C", "Wash; secondary 1 h RT; wash", "Image; quantify bands and loading control"],
    K.XCELLIGENCE: ["Background read with medium only", "Seed cells (journal calc --kind seeding)",
                    "Monitor until the growth phase", "Treat at <h> h", "Export the cell index"],
    K.FLUORIMETRY: ["Plan the plate: blanks, standards, samples in triplicate", "Prepare the standard curve (journal calc --kind serial)",
                    "Incubate <min> min at <°C>, protected from light", "Read at ex <nm> / em <nm>, gain <g>"],
    K.MICROSCOPY: ["Fix <min> min; permeabilise; block", "Primary antibodies; wash; secondaries with nuclear stain",
                   "Mount", "Image with the same settings for every condition; attach the images"],
    K.CULTURE: ["Check morphology and confluence", "Wash with PBS; detach", "Count (journal calc --kind hemocytometer)",
                "Split or seed; label passage number", "Record medium lot; next mycoplasma test due"],
    K.SORTING: ["Stain: viability dye, then surface antibodies", "Single-stain and FMO controls",
                "Set voltages and compensation", "Gate: cells, singlets, live, populations", "Sort into collection medium; re-analyse purity"],
    K.ANIMAL: ["Approved protocol number: <id>", "Acclimatise <days> days; randomise into groups", "Baseline weights",
               "Dose per schedule (journal calc --kind dose)", "Weigh and score <times> a week", "Endpoint and tissue collection"],
    K.CLONING: ["Digest vector and insert", "Gel-purify fragments", "Ligate at a molar ratio (journal calc --kind ligation)",
                "Transform competent cells; plate on selection", "Pick colonies; miniprep; verify by digest and sequencing"],
    K.TRANSFECTION: ["Seed cells the day before (journal calc --kind seeding)", "Dilute DNA and reagent in serum-free medium",
                     "Combine, incubate, add dropwise", "Change medium at <h> h; read out at <h> h"],
    K.ELISA: ["Coat or use the pre-coated plate", "Standards, blanks and samples in duplicate", "Detection antibody; wash",
              "Substrate; stop", "Read at <nm>; fit the standard curve"],
    K.OTHER: ["<step>"],
}

_RESULTS: dict[K, dict[str, Any]] = {
    K.PCR: {"cycling": [{"step": "initial denaturation", "temp_c": 98, "seconds": 30},
                        {"step": "denaturation", "temp_c": 98, "seconds": 10, "cycles": 30},
                        {"step": "annealing", "temp_c": 60, "seconds": 20, "cycles": 30},
                        {"step": "extension", "temp_c": 72, "seconds": 30, "cycles": 30},
                        {"step": "final extension", "temp_c": 72, "seconds": 300}]},
    K.GEL: {"gel": "1% agarose, 120 V, 40 min", "lanes": [{"lane": 1, "sample": "<ladder product, e.g. GeneRuler 1 kb Plus>", "ladder": True},
                                                       {"lane": 2, "sample": "<sample>", "expected_bp": 500, "observed_bp": [500]}]},
    K.QPCR: {"reference_targets": ["<reference gene>"], "control_group": "control",
             "cts": [{"sample": "<sample>", "group": "control", "target": "<gene>", "ct": 24.1}]},
    K.WESTERN: {"control_group": "control",
                "bands": [{"lane": 1, "sample": "<sample>", "group": "control", "target": "<protein>", "intensity": 1000, "loading": 2000}]},
    K.XCELLIGENCE: {"treated_at_h": 24, "ci": [{"group": "control", "points": [{"t_h": 0, "ci": 0.1}, {"t_h": 24, "ci": 1.0}]}]},
    K.FLUORIMETRY: {"reading": "ex <nm> / em <nm>", "readings": [{"sample": "blank", "value": 120, "role": "blank"},
                                                                 {"sample": "std 1", "value": 900, "standard_conc": 1}]},
    K.MICROSCOPY: {"images": [{"file": "<image>.png", "channel": "<channel>", "objective": "<20x>"}]},
    K.CULTURE: {"passages": [{"date": "<YYYY-MM-DD>", "passage": 5, "action": "split 1:5", "confluence_pct": 80}]},
    K.SORTING: {"fcs": [{"sample": "<sample>", "file": "<sample>.fcs"}], "gates": [
        {"name": "cells", "x": "FSC-A", "y": "SSC-A", "polygon": [[40000, 10000], [240000, 40000], [240000, 200000], [60000, 120000]]},
        {"name": "singlets", "parent": "cells", "x": "FSC-A", "y": "FSC-H", "polygon": [[40000, 30000], [240000, 190000], [240000, 245000], [40000, 60000]]},
        {"name": "live", "parent": "singlets", "x": "<viability dye>", "interval": [-2000, 1500]},
        {"name": "<population>", "parent": "live", "x": "<marker>", "y": "<marker>", "rect": [1500, 262144, -2000, 262144]}]},
    K.ANIMAL: {"genotyping": "<assay as written>", "alleles": [{"name": "WT", "bp": 250}, {"name": "<allele>", "bp": 330}],
               "expected": {"WT/WT": 1, "WT/<allele>": 2, "<allele>/<allele>": 1},
               "animals": [{"id": "<id>", "group": "vehicle", "sex": "F", "born": "<YYYY-MM-DD>", "cage": "<cage>",
                            "ear_tag": "<tag>", "bands": [250, 330]}],
               "groups": [{"name": "vehicle", "n": 8}, {"name": "treated", "n": 8, "treatment": "<treatment>", "dose": "<as written>"}],
               "weights": [{"animal": "<id>", "group": "vehicle", "date": "<YYYY-MM-DD>", "grams": 25.0}]},
    K.CLONING: {"plasmid": "<saved plasmid name>"},
    K.TRANSFECTION: {"plasmid": "<saved plasmid name>"},
    K.ELISA: {"readings": [{"sample": "blank", "value": 0.05, "role": "blank"}, {"sample": "std 1", "value": 1.2, "standard_conc": 1000}]},
}


def starter(kind: K) -> dict[str, Any]:
    return {"entry": {"id": f"{kind.value}-{now():%Y%m%d}", "title": "<what this experiment asks>", "kind": kind.value,
                      "date": now().date().isoformat(), "project": "<project>", "status": "planned", "aim": "<one line>",
                      "protocol": [{"text": s} for s in _STEPS[kind]], "reagents": [], "samples": [],
                      "results": _RESULTS.get(kind, {}), "observations": "", "conclusion": "", "tags": []},
            "hint": "replace every <placeholder>, drop what was not done, then plsi journal save --file <entry.json>"}
