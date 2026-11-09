"""Fast CLI query utility for a plsi SQLite omics & clinical database.

Allows users or AI agents to query germline variants, CpG methylation probes,
aging clocks, and clinical observations
across plsi instances in <5 milliseconds without loading large files.

Usage examples:
    python query_omics.py --summary
    python query_omics.py --gene <GENE_SYMBOL>
    python query_omics.py --rsid <RSID>
    python query_omics.py --cpg <CPG_ID>
    python query_omics.py --clocks
    python query_omics.py --labs <BIOMARKER_CODE_OR_LABEL>
    python query_omics.py --sql "SELECT * FROM wgs_variants WHERE effect_alleles >= 1"
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = REPO_ROOT / "instances" / "local_omics_manifest.json"
DEFAULT_DB_PATH = REPO_ROOT / "omics.sqlite"


def resolve_db_path(explicit_db: Path | None) -> Path:
    if explicit_db:
        return explicit_db
    if DEFAULT_MANIFEST.exists():
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        if manifest.get("default_db_path"):
            return Path(manifest["default_db_path"])
    return DEFAULT_DB_PATH


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def print_rows(rows: list[sqlite3.Row], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps([dict(r) for r in rows], indent=2))
        return
    if not rows:
        print("(no rows matched)")
        return
    cols = list(rows[0].keys())
    widths = {c: max(len(c), *(len(str(r[c] if r[c] is not None else "")) for r in rows)) for c in cols}
    header = " | ".join(c.ljust(widths[c]) for c in cols)
    sep = "-+-".join("-" * widths[c] for c in cols)
    print(header)
    print(sep)
    for r in rows:
        print(" | ".join(str(r[c] if r[c] is not None else "").ljust(widths[c]) for c in cols))


def main() -> None:
    parser = argparse.ArgumentParser(description="Query plsi SQLite omics & clinical database")
    parser.add_argument("--db", type=Path, default=None, help="Path to SQLite database")
    parser.add_argument("--summary", action="store_true", help="Show table counts and subject summary")
    parser.add_argument("--gene", type=str, help="Query germline variants by gene symbol (substring match)")
    parser.add_argument("--rsid", type=str, help="Query germline variants by rsID")
    parser.add_argument("--category", type=str, help="Query germline variants by clinical category")
    parser.add_argument("--cpg", nargs="+", help="Query methylation beta values across all arrays for CpG ID(s)")
    parser.add_argument("--clocks", action="store_true", help="List epigenetic clock values across all arrays")
    parser.add_argument("--labs", nargs="+", help="Query clinical observations by label, code, or coordinate")
    parser.add_argument("--sql", type=str, help="Execute a read-only SQL SELECT query")
    parser.add_argument("--json", action="store_true", help="Format output as JSON")
    args = parser.parse_args()

    db_path = resolve_db_path(args.db)
    conn = connect(db_path)
    cur = conn.cursor()

    if args.summary or not any([args.gene, args.rsid, args.category, args.cpg, args.clocks, args.labs, args.sql]):
        tables = ["subjects", "wgs_variants", "methylation_betas", "epigenetic_clocks", "clinical_observations"]
        summary_rows = []
        for t in tables:
            cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            summary_rows.append({"table_name": t, "row_count": cnt})
        print("=== DATABASE TABLE SUMMARY ===")
        for item in summary_rows:
            print(f"  {item['table_name']:24s}: {item['row_count']:,} rows")
        print("\n=== SUBJECTS ===")
        rows = cur.execute("SELECT * FROM subjects ORDER BY subject_id").fetchall()
        print_rows(rows, args.json)

    if args.gene:
        print(f"\n=== VARIANTS MATCHING GENE '{args.gene}' ===")
        rows = cur.execute(
            "SELECT subject_id, gene, rsid, variant_label, genotype, effect_alleles, zygosity, category, clinical_impact "
            "FROM wgs_variants WHERE UPPER(gene) LIKE UPPER(?) ORDER BY gene, subject_id",
            (f"%{args.gene}%",),
        ).fetchall()
        print_rows(rows, args.json)

    if args.rsid:
        print(f"\n=== VARIANTS MATCHING RSID '{args.rsid}' ===")
        rows = cur.execute(
            "SELECT subject_id, gene, rsid, variant_label, genotype, effect_alleles, zygosity, category, clinical_impact "
            "FROM wgs_variants WHERE LOWER(rsid) LIKE LOWER(?) ORDER BY rsid, subject_id",
            (f"%{args.rsid}%",),
        ).fetchall()
        print_rows(rows, args.json)

    if args.category:
        print(f"\n=== VARIANTS IN CATEGORY '{args.category}' ===")
        rows = cur.execute(
            "SELECT subject_id, gene, rsid, variant_label, genotype, effect_alleles, zygosity, clinical_impact "
            "FROM wgs_variants WHERE LOWER(category) LIKE LOWER(?) ORDER BY gene, subject_id",
            (f"%{args.category}%",),
        ).fetchall()
        print_rows(rows, args.json)

    if args.cpg:
        placeholders = ",".join("?" for _ in args.cpg)
        col_info = cur.execute("PRAGMA table_info(methylation_betas)").fetchall()
        select_exprs = [
            "probe_id" if c["name"] == "probe_id" else f"ROUND({c['name']}, 4) AS {c['name']}"
            for c in col_info
        ]
        print(f"\n=== METHYLATION BETAS FOR {args.cpg} ===")
        rows = cur.execute(
            f"SELECT {', '.join(select_exprs)} FROM methylation_betas WHERE probe_id IN ({placeholders}) ORDER BY probe_id",
            args.cpg,
        ).fetchall()
        print_rows(rows, args.json)

    if args.clocks:
        print("\n=== EPIGENETIC CLOCKS ===")
        rows = cur.execute(
            "SELECT subject_id, sample_date, engine, clock_name, "
            "ROUND(value, 3) AS value, unit, ROUND(chronological_age, 2) AS chrono_age, "
            "ROUND(acceleration, 2) AS accel "
            "FROM epigenetic_clocks ORDER BY clock_name, subject_id, sample_date"
        ).fetchall()
        print_rows(rows, args.json)

    if args.labs:
        for term in args.labs:
            print(f"\n=== CLINICAL OBSERVATIONS MATCHING '{term}' ===")
            rows = cur.execute(
                "SELECT subject_id, effective_at, kind, code_system, code, label, "
                "ROUND(value_quantity, 4) AS value_quantity, value_text, unit, flag "
                "FROM clinical_observations "
                "WHERE LOWER(label) LIKE LOWER(?) OR LOWER(code) LIKE LOWER(?) OR LOWER(code_system) LIKE LOWER(?) "
                "ORDER BY subject_id, effective_at, code",
                (f"%{term}%", f"%{term}%", f"%{term}%"),
            ).fetchall()
            print_rows(rows, args.json)

    if args.sql:
        if not args.sql.strip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are permitted via --sql.")
        print("\n=== CUSTOM SQL QUERY ===")
        rows = cur.execute(args.sql).fetchall()
        print_rows(rows, args.json)

    conn.close()


if __name__ == "__main__":
    main()
