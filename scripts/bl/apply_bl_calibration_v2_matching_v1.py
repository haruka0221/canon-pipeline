#!/usr/bin/env python3
"""Apply the matching rules to the BL calibration v2 links and draw the judgment sample.

Rules (protocol §5, frozen before retrieval):
  exact      = v1 R1   (normalize_n1(245$a) == normalize_n1(title))        imported from v1 analyzer
  r2         = v1 R2   (prefix with word boundary)                           imported from v1 analyzer
  r3         = v1 R3   ([ ] stripped, prefix with word boundary)             imported from v1 analyzer
  author     = surname of the target's query author == surname of any 100/700 $a
               (surname = last token of the query author after removing (...) ;
                record surname = text before the first comma in $a); both normalize_n1'd
  r3_author  = r3 and author
  r3_author_initial (diagnostic) = r3 and author and first initial also matches

Titles per target = all OL alias titles of that target (sample_aliases_v1.tsv).
Links = target × record × routes from the private target_record_links_v2.tsv.

Publication dedup key (protocol §5, 9a item 2):
  pub_key = normalize_n1(245$a) | normalize_n1(publisher 264$b or 260$b) | year (264$c/260$c digits, else 008 date1)

multi_w_candidate: a record for which r3 is true for more than one target.

Judgment sample (protocol §5 / addendum 1), seed 20261021, unit = target × record:
  J1  300 rows with r3_author true
  J2  100 rows with r3 true and r3_author false
  J3  100 rows with r3 false
  The input table for the LLM/human carries the record fields and the target's titles/author
  but NOT the rule flags (blind), and a random judgment order.

PRIVATE outputs (--out-dir, default ~/bl_raw/calibration_v2_derived):
  matching_results_v2.tsv   one row per link with flags, pub_key, multi flags
  publications_v2.tsv       one row per (target, pub_key) with record count and marc_001 list
  judgment_sample_v2.tsv    500 rows, with stratum and the hidden flags (for analysis only)
  judgment_input_v2.tsv     the same 500 rows, blind version for the LLM/human
PUBLIC output:
  derived/bl_calibration/calibration_v2/matching_manifest_v1.json  counts and sha256 only
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CAL = ROOT / "derived" / "bl_calibration" / "calibration_v2"
V1_ANALYZER = ROOT / "scripts" / "bl" / "analyze_q1_record_structure_v1.py"
PUBLIC_MANIFEST = CAL / "matching_manifest_v1.json"
SEED = 20261021
QUOTA = {"J1_r3_author": 300, "J2_r3_only": 100, "J3_r3_false": 100}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_v1():
    spec = importlib.util.spec_from_file_location("bl_q1_v1", V1_ANALYZER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def query_author_parts(name: str):
    s = re.sub(r"\([^)]*\)", " ", name)
    toks = [t for t in re.split(r"\s+", s.strip()) if t]
    if not toks:
        return "", ""
    return toks[-1], toks[0][:1]


def record_author_parts(entries: str):
    """Yield (surname, forename_initial) for each 100/700 entry."""
    out = []
    for entry in (entries or "").split("|"):
        m = re.search(r"\$a\s*([^$]+)", entry)
        if not m:
            continue
        a = m.group(1).strip().rstrip(" ,.;:/")
        if "," in a:
            sur, fore = a.split(",", 1)
        else:
            parts = a.split()
            sur, fore = (parts[-1], " ".join(parts[:-1])) if parts else ("", "")
        out.append((sur.strip(), fore.strip()[:1]))
    return out


def year_of(s: str) -> str:
    m = re.search(r"(1[5-9]\d\d|20\d\d)", s or "")
    return m.group(1) if m else ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=str(Path.home() / "bl_raw" / "calibration_v2_derived"))
    args = ap.parse_args()
    out = Path(args.out_dir).expanduser().resolve()
    if ROOT in out.parents or out == ROOT:
        sys.exit("ERROR: --out-dir must be outside the repository")
    for name in ("matching_results_v2.tsv", "judgment_input_v2.tsv"):
        if (out / name).exists():
            sys.exit(f"ERROR: output exists, refusing to overwrite: {out / name}")

    v1 = load_v1()
    n1 = v1.normalize_n1

    rec = pd.read_csv(out / "records_parsed_v2.tsv", sep="\t", dtype=str, keep_default_na=False)
    links = pd.read_csv(out / "target_record_links_v2.tsv", sep="\t", dtype=str, keep_default_na=False)
    al = pd.read_csv(CAL / "sample_aliases_v1.tsv", sep="\t", dtype=str, keep_default_na=False)
    titles = al.groupby("sample_id")["source_title"].agg(lambda s: sorted(set(s))).to_dict()
    authors = al.groupby("sample_id")["query_author_name"].agg(lambda s: sorted({x for x in s if x})).to_dict()
    rec_by_id = rec.set_index("marc_001")

    rows = []
    for L in links.itertuples(index=False):
        r = rec_by_id.loc[L.marc_001]
        t_titles = titles.get(L.sample_id, [])
        r1, r2, r3 = v1.check_matching_rules(r["f245_a"], t_titles)
        rec_auth = record_author_parts(r["f100_entries"]) + record_author_parts(r["f700_entries"])
        a_sur = a_init = False
        for qa in authors.get(L.sample_id, []):
            qs, qi = query_author_parts(qa)
            for rs, ri in rec_auth:
                if qs and n1(rs) == n1(qs):
                    a_sur = True
                    if qi and ri and n1(ri) == n1(qi):
                        a_init = True
        pub = r["f264_b"] or r["f260_b"]
        yr = year_of(r["f264_c"]) or year_of(r["f260_c"]) or (r["cf008_date1"] or "").strip()
        rows.append({
            "sample_id": L.sample_id, "target_id": L.target_id, "marc_001": L.marc_001,
            "routes": L.routes, "via_title_route": L.via_title_route,
            "exact": r1, "r2": r2, "r3": r3, "author_surname": a_sur,
            "r3_author": r3 and a_sur, "r3_author_initial": r3 and a_init,
            "pub_key": f"{n1(r['f245_a'])}|{n1(pub)}|{yr}", "pub_year": yr,
            "cf008_date1": r["cf008_date1"],
        })
    M = pd.DataFrame(rows)

    r3_targets = M[M["r3"]].groupby("marc_001")["sample_id"].nunique()
    multi = set(r3_targets[r3_targets > 1].index)
    M["multi_w_candidate"] = M["marc_001"].isin(multi) & M["r3"]
    M["n_targets_for_record"] = M["marc_001"].map(M.groupby("marc_001")["sample_id"].nunique())

    M = M.sort_values(["sample_id", "marc_001"])
    M.to_csv(out / "matching_results_v2.tsv", sep="\t", index=False, lineterminator="\n")

    P = (M[M["r3"]].groupby(["sample_id", "target_id", "pub_key"])
         .agg(n_records=("marc_001", "size"), marc_001s=("marc_001", lambda s: ";".join(sorted(s))),
              n_r3_author=("r3_author", "sum"))
         .reset_index())
    P.to_csv(out / "publications_v2.tsv", sep="\t", index=False, lineterminator="\n")

    # ---- judgment sample
    rng = np.random.default_rng(SEED)
    strata = {
        "J1_r3_author": M[M["r3_author"]],
        "J2_r3_only": M[M["r3"] & ~M["r3_author"]],
        "J3_r3_false": M[~M["r3"]],
    }
    parts = []
    for name, n in QUOTA.items():
        pool = strata[name].sort_values(["sample_id", "marc_001"]).reset_index(drop=True)
        k = min(n, len(pool))
        pick = pool.iloc[rng.choice(len(pool), size=k, replace=False)].copy()
        pick["stratum"] = name
        parts.append(pick)
    J = pd.concat(parts, ignore_index=True)
    J["judgment_order"] = rng.permutation(len(J)) + 1
    J["judgment_id"] = [f"BLJ2_{i:04d}" for i in range(1, len(J) + 1)]
    J = J.sort_values("judgment_order")
    J.to_csv(out / "judgment_sample_v2.tsv", sep="\t", index=False, lineterminator="\n")

    blind_cols = ["judgment_id", "judgment_order", "sample_id", "target_id", "marc_001"]
    JI = J[blind_cols].merge(rec[["marc_001", "f245_a", "f245_b", "f245_c", "f246_a", "f250_a",
                                  "f260_a", "f260_b", "f260_c", "f264_a", "f264_b", "f264_c",
                                  "f100_entries", "f700_entries", "f240_a", "f130_a", "f041_a", "f041_h",
                                  "has_f505", "has_f600_t", "cf008_date1", "cf008_language"]],
                             on="marc_001", how="left")
    JI["target_titles"] = JI["sample_id"].map(lambda s: " | ".join(titles.get(s, [])))
    JI["target_authors"] = JI["sample_id"].map(lambda s: " | ".join(authors.get(s, [])))
    JI["work_relation"] = ""      # to be filled: VALID / INVALID / UNCERTAIN
    JI["publication_relation"] = ""  # v1 §7 vocabulary
    JI["judge_note"] = ""
    JI["judge"] = "PENDING"
    JI = JI.sort_values("judgment_order")
    JI.to_csv(out / "judgment_input_v2.tsv", sep="\t", index=False, lineterminator="\n")

    per_target = M.groupby("sample_id").agg(n_links=("marc_001", "size"), n_r3=("r3", "sum"),
                                              n_r3_author=("r3_author", "sum"))
    manifest = {
        "release": "bl_calibration_v2_matching_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rules": "exact/r2/r3 imported from analyze_q1_record_structure_v1.py; author = surname rule; r3_author = r3 and author",
        "v1_analyzer_sha256": sha256(V1_ANALYZER),
        "seed": SEED,
        "link_rows": int(len(M)),
        "targets": int(M["sample_id"].nunique()),
        "flags": {k: int(M[k].sum()) for k in ["exact", "r2", "r3", "author_surname", "r3_author", "r3_author_initial", "multi_w_candidate"]},
        "records_r3_for_multiple_targets": len(multi),
        "targets_with_any_r3_author": int((per_target["n_r3_author"] > 0).sum()),
        "targets_with_any_r3": int((per_target["n_r3"] > 0).sum()),
        "publications_r3": int(len(P)),
        "publications_with_duplicate_records": int((P["n_records"] > 1).sum()),
        "judgment_sample": J["stratum"].value_counts().to_dict(),
        "private_files_sha256": {n: sha256(out / n) for n in ["matching_results_v2.tsv", "publications_v2.tsv",
                                                               "judgment_sample_v2.tsv", "judgment_input_v2.tsv"]},
        "note": "Counts only; record content stays in the private directory. Judgment input is blind (no rule flags).",
    }
    PUBLIC_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in manifest.items() if k != "private_files_sha256"}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
