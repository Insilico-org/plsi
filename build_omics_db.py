"""Build a local serverless SQLite omics & clinical database from plsi instances and an optional manifest.

Indexes:
1. subjects: Instance name -> plsi subject id (from instances/<id>/subject.json).
2. wgs_variants: Germline variant annotations from an optional local manifest.
3. methylation_betas: CpG probe beta values across ingested artifacts or manifest matrices (indexed by probe_id).
4. epigenetic_clocks: Aging clock series from states/methylation_clocks/latest.json (plus optional manifest rows).
5. clinical_observations: All non-retracted observations from events.jsonl + derived state coordinates.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_INSTANCES_DIR = REPO_ROOT / "instances"
DEFAULT_MANIFEST = DEFAULT_INSTANCES_DIR / "local_omics_manifest.json"
DEFAULT_DB_PATH = REPO_ROOT / "omics.sqlite"


def load_manifest(manifest_path: Path | None) -> dict[str, Any]:
    if manifest_path and manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    if DEFAULT_MANIFEST.exists():
        return json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    return {}


def discover_instances(instances_dir: Path) -> list[Path]:
    if not instances_dir.exists():
        return []
    return sorted(
        p for p in instances_dir.iterdir()
        if p.is_dir() and (p / "subject.json").exists()
    )


def build_database(
    db_path: Path | None = None,
    instances_dir: Path = DEFAULT_INSTANCES_DIR,
    manifest_path: Path | None = None,
) -> Path:
    manifest = load_manifest(manifest_path)
    target_db = Path(db_path or manifest.get("default_db_path") or DEFAULT_DB_PATH)
    if target_db.exists():
        target_db.unlink()

    conn = sqlite3.connect(target_db)
    cur = conn.cursor()

    # 1. subjects table (instance name -> plsi subject id only; no demographics are copied)
    cur.execute("""
        CREATE TABLE subjects (
            subject_id TEXT PRIMARY KEY,
            plsi_subject_id TEXT
        )
    """)

    instance_dirs = discover_instances(instances_dir)
    subjects_rows = []
    for inst_dir in instance_dirs:
        subj_doc = json.loads((inst_dir / "subject.json").read_text(encoding="utf-8"))
        subjects_rows.append((inst_dir.name, subj_doc.get("id")))
    cur.executemany("INSERT INTO subjects VALUES (?,?)", subjects_rows)

    # 2. wgs_variants table
    cur.execute("""
        CREATE TABLE wgs_variants (
            subject_id TEXT,
            gene TEXT,
            rsid TEXT,
            variant_label TEXT,
            genotype TEXT,
            effect_alleles INTEGER,
            zygosity TEXT,
            category TEXT,
            clinical_impact TEXT
        )
    """)
    wgs_rows = [tuple(r) for r in manifest.get("wgs_variants", [])]
    cur.executemany("INSERT INTO wgs_variants VALUES (?,?,?,?,?,?,?,?,?)", wgs_rows)
    cur.execute("CREATE INDEX idx_wgs_gene ON wgs_variants(gene)")
    cur.execute("CREATE INDEX idx_wgs_rsid ON wgs_variants(rsid)")
    cur.execute("CREATE INDEX idx_wgs_subj ON wgs_variants(subject_id)")

    # 3. methylation_betas table
    print("Loading methylation beta matrices into SQLite...")
    merged: pd.DataFrame | None = None
    matrix_specs = manifest.get("methylation_matrices", [])
    if matrix_specs:
        for spec in matrix_specs:
            col_name = spec["column_name"]
            csv_path = Path(spec["path"])
            if not csv_path.exists():
                continue
            df = pd.read_csv(csv_path)
            df = df.rename(columns={df.columns[0]: "probe_id", df.columns[1]: col_name})
            df["probe_id"] = df["probe_id"].astype(str).str.split("_").str[0]
            df = df.groupby("probe_id", as_index=False)[col_name].mean()
            merged = df if merged is None else merged.merge(df, on="probe_id", how="outer")
        for dspec in manifest.get("methylation_deltas", []):
            dcol, c1, c2 = dspec["column_name"], dspec["minuend"], dspec["subtrahend"]
            if merged is not None and c1 in merged.columns and c2 in merged.columns:
                merged[dcol] = merged[c1] - merged[c2]
    else:
        for inst_dir in instance_dirs:
            art_dir = inst_dir / "artifacts" / "methylation"
            if not art_dir.exists():
                continue
            for idx_a, gz_path in enumerate(sorted(art_dir.glob("*.csv.gz"))):
                col_name = f"{inst_dir.name}_m{idx_a + 1}"
                with gzip.open(gz_path, "rt", encoding="utf-8") as fh:
                    df = pd.read_csv(fh).rename(columns={"cpg": "probe_id", "beta": col_name})
                df["probe_id"] = df["probe_id"].astype(str).str.split("_").str[0]
                df = df.groupby("probe_id", as_index=False)[col_name].mean()
                merged = df if merged is None else merged.merge(df, on="probe_id", how="outer")

    if merged is None:
        merged = pd.DataFrame({"probe_id": pd.Series(dtype="str")})
    merged.to_sql("methylation_betas", conn, if_exists="replace", index=False)
    cur.execute("CREATE UNIQUE INDEX idx_meth_probe ON methylation_betas(probe_id)")
    print(f"Indexed {len(merged):,} CpG probes in methylation_betas.")

    # 4. epigenetic_clocks table
    cur.execute("""
        CREATE TABLE epigenetic_clocks (
            subject_id TEXT,
            sample_date TEXT,
            engine TEXT,
            clock_name TEXT,
            value REAL,
            unit TEXT,
            chronological_age REAL,
            acceleration REAL
        )
    """)
    clock_rows = []
    chrono_map: dict[str, float] = manifest.get("chronological_age_by_sample", {})
    for inst_dir in instance_dirs:
        subj = inst_dir.name
        st_path = inst_dir / "states" / "methylation_clocks" / "latest.json"
        if not st_path.exists():
            continue
        st = json.loads(st_path.read_text(encoding="utf-8"))
        for cid, cval in st.get("coordinates", {}).items():
            if cid == "methylation_betas":
                continue
            unit = cval.get("unit", "a")
            for pt in cval.get("series", []):
                dt = pt["t"][:10]
                val = float(pt["value"])
                ca = chrono_map.get(f"{subj}:{dt}", 0.0)
                accel = (val - ca) if unit == "a" and val > 5.0 and ca > 0.0 else None
                clock_rows.append((subj, dt, "plsi_biolearn", cid, val, unit, ca, accel))

    for extra in manifest.get("extra_clocks", []):
        clock_rows.append(tuple(extra))

    cur.executemany("INSERT INTO epigenetic_clocks VALUES (?,?,?,?,?,?,?,?)", clock_rows)
    cur.execute("CREATE INDEX idx_clocks_subj ON epigenetic_clocks(subject_id, clock_name)")

    # 5. clinical_observations table (from plsi events.jsonl + derived state coordinates)
    cur.execute("""
        CREATE TABLE clinical_observations (
            event_id TEXT PRIMARY KEY,
            subject_id TEXT,
            effective_at TEXT,
            kind TEXT,
            code_system TEXT,
            code TEXT,
            label TEXT,
            value_quantity REAL,
            value_text TEXT,
            unit TEXT,
            ref_low REAL,
            ref_high REAL,
            flag TEXT
        )
    """)
    obs_rows = []
    for inst_dir in instance_dirs:
        subj = inst_dir.name
        ev_path = inst_dir / "events.jsonl"
        if ev_path.exists():
            lines = [json.loads(line) for line in ev_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            retracted = {
                e["payload"].get("event_id") or e["payload"].get("target_event_id")
                for e in lines
                if e.get("type") == "retraction"
            }
            for e in lines:
                if e.get("type") != "observation" or e["id"] in retracted:
                    continue
                p = e["payload"]
                c = p.get("code") or {}
                obs_rows.append((
                    f"{subj}:{e['id']}",
                    subj,
                    str(p.get("effective_at", ""))[:10],
                    p.get("kind"),
                    c.get("system"),
                    c.get("code"),
                    p.get("original_text") or c.get("display") or c.get("code"),
                    p.get("value_quantity"),
                    p.get("value_text"),
                    p.get("unit"),
                    p.get("ref_low"),
                    p.get("ref_high"),
                    p.get("flag"),
                ))

        states_dir = inst_dir / "states"
        if states_dir.exists():
            for map_dir in sorted(states_dir.iterdir()):
                if not map_dir.is_dir() or map_dir.name == "methylation_clocks":
                    continue
                latest_f = map_dir / "latest.json"
                if not latest_f.exists():
                    continue
                st = json.loads(latest_f.read_text(encoding="utf-8"))
                for cid, cval in st.get("coordinates", {}).items():
                    if (cval.get("provenance") or {}).get("match") != "derived":
                        continue
                    for idx_pt, pt in enumerate(cval.get("series", [])):
                        obs_rows.append((
                            f"{subj}:derived:{map_dir.name}:{cid}:{idx_pt}",
                            subj,
                            str(pt.get("t", ""))[:10],
                            "derived_coordinate",
                            map_dir.name,
                            cid,
                            cval.get("label", cid),
                            float(pt["value"]) if isinstance(pt.get("value"), (int, float)) else None,
                            str(pt["value"]) if not isinstance(pt.get("value"), (int, float)) else None,
                            cval.get("unit"),
                            None,
                            None,
                            None,
                        ))
    cur.executemany("INSERT INTO clinical_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", obs_rows)
    cur.execute("CREATE INDEX idx_obs_subj_code ON clinical_observations(subject_id, code, effective_at)")

    conn.commit()
    conn.close()
    print(f"Successfully built {target_db} ({target_db.stat().st_size / (1024*1024):.2f} MB)")
    return target_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SQLite omics & clinical database from plsi instances.")
    parser.add_argument("--db", type=Path, default=None, help="Output SQLite database path")
    parser.add_argument("--instances-dir", type=Path, default=DEFAULT_INSTANCES_DIR, help="Path to plsi instances directory")
    parser.add_argument("--manifest", type=Path, default=None, help="Optional JSON manifest for external omics matrices")
    args = parser.parse_args()
    build_database(db_path=args.db, instances_dir=args.instances_dir, manifest_path=args.manifest)


if __name__ == "__main__":
    main()
