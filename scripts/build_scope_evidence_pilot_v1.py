#!/usr/bin/env python3
"""Prepare a NON-ADJUDICATIVE Project-W scope-evidence pilot from frozen inputs.

Run from the server worktree with:
  python -B scripts/build_scope_evidence_pilot_v1.py

New outputs only: derived/scope/scope_evidence_pilot_v1/.
No identity, OpenAlex disposition, held-out, or Edition-audit data are modified.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "derived/scope"
OUT = SCOPE / "scope_evidence_pilot_v1"
OA = ROOT / "derived/openalex_production"
ID = ROOT / "derived/identity"
V2 = OA / "integrated_work_visibility_v2"
REG = OA / "registry_v4"
POP = Path.home() / "canon-pipeline/derived/ol_dump_population_with_author.tsv"
CREATED_AT = "2026-10-20"
SEED = "scope-evidence-pilot-v1:20261020"

# Independent simple-random sample for later pilot design (not an estimator yet).
N_RANDOM_ACTIVE = 80
# Diagnostic supplements, not part of the independent random sample.
N_RANDOM_NOT_QUERIED = 12
N_RANDOM_NONASCII = 12

# IDs were detected in the read-only Jaccard >= 0.95 screen on 2026-10-20.
# Inclusion in this review cohort does NOT assert conceptual identity.
OVERLAP_DIAGNOSTIC_W = {
    "W000016985", "W000017666", "W000030950",  # Ulysses
    "W000014272", "W000014830", "W000017583", "W000030652",  # Heart of Darkness
    "W000014829", "W000020297", "W000030490", "W000020329",  # Lamb
    "W000000366", "W000018899",  # Notre-Dame
    "W000019122", "W000020009",  # The Novels of Jane Austen
}

# Contrast cases from earlier OpenAlex scope checks, without adjudicating them.
CONTRAST_W = {
    "W000020154",  # Pride and Prejudice
    "W000016806",  # Jane Eyre
    "W000001290",  # The Waste Land
    "W000001288",  # Ezra Pound
    "W000031539",  # Dracula, corrected OL target
    "W000014515",  # Alcott, not remeasured
    "W000018010",  # Mrs Dalloway
    "W000018025",  # To the Lighthouse
    "W000030951",  # Finnegans Wake
    "W000030952",  # Dubliners
    "W000030670",  # The Picture of Dorian Gray
    "W000018013",  # Orlando
}


def abort(msg: str) -> None:
    raise SystemExit("STOP: " + msg)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def read_tsv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        abort(f"Required input not found: {path}")
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, low_memory=False)


def normalize_ol(value: object) -> str:
    m = re.search(r"OL\d+W", str(value))
    return m.group(0) if m else ""


def ascii_tokens(value: str) -> list[str]:
    s = unicodedata.normalize("NFKD", str(value))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.findall(r"[a-z]+", s.casefold())


def author_like_flag(title: str, author: str) -> str:
    t, a = ascii_tokens(title), ascii_tokens(author)
    if not t or not a:
        return "UNDETERMINED_ASCII_SCREEN"
    if sorted(t) == sorted(a):
        return "FULL_NAME_MATCH"
    if len(t) == 1 and t[0] in a:
        return "SINGLE_NAME_MATCH"
    return "NOT_FLAGGED"


def numeric_or_symbol_title(title: str) -> bool:
    return not any(unicodedata.category(c).startswith("L") for c in title)


def rank_key(group: str, w: str) -> str:
    return hashlib.sha256(f"{SEED}\x1f{group}\x1f{w}".encode("utf-8")).hexdigest()


def select_sample(group: str, pool: set[str], count: int) -> set[str]:
    if len(pool) < count:
        abort(f"{group}: pool smaller than sample: {len(pool)} < {count}")
    return set(sorted(pool, key=lambda w: (rank_key(group, w), w))[:count])


def joined(values: list[str]) -> str:
    return " || ".join(dict.fromkeys(str(v) for v in values if str(v).strip()))


def main() -> None:
    if OUT.exists():
        abort(f"Output already exists: {OUT}; never overwrite a release")

    metrics_path = V2 / "openalex_visibility_by_project_work_v2.tsv"
    v2_manifest_path = V2 / "integrated_visibility_manifest_v2.json"
    queries_path = REG / "openalex_queries_v4.tsv"
    works_path = ID / "project_works_v7.tsv"
    identity_path = ID / "work_identity_map_v7.tsv"
    sources_path = ID / "source_entities_v3.tsv"
    corrections_path = ID / "openlibrary_target_corrections_v1.tsv"
    inputs = [metrics_path, v2_manifest_path, queries_path, works_path,
              identity_path, sources_path, POP, corrections_path]
    for path in inputs:
        if not path.is_file():
            abort(f"Required input not found: {path}")

    # Check that the scope pilot reads precisely the frozen v2 work summary.
    m = json.loads(v2_manifest_path.read_text(encoding="utf-8"))
    expected_hash = (m.get("output_sha256") or m.get("outputs") or {}).get(metrics_path.name)
    if not expected_hash or sha(metrics_path) != expected_hash:
        abort("Integrated v2 work-summary hash missing or mismatched")

    v = read_tsv(metrics_path)
    works = read_tsv(works_path)
    identities = read_tsv(identity_path)
    entities = read_tsv(sources_path)
    queries = read_tsv(queries_path)
    population = read_tsv(POP)
    corrections = read_tsv(corrections_path)

    if len(v) != 32066 or not v.project_work_id.is_unique:
        abort("Expected exactly 32,066 unique active W in integrated v2")
    v["operational_pairs"] = pd.to_numeric(v["total_operational_pairs"], errors="coerce")
    if (int(v.operational_pairs.sum()) != 226221
            or int(v.operational_pairs.isna().sum()) != 1
            or int(v.operational_pairs.fillna(0).gt(0).sum()) != 7077):
        abort("Unexpected frozen v2 counts; do not continue")

    statuses = works.set_index("project_work_id")["status"].to_dict()
    if any(statuses.get(w) != "active" for w in v.project_work_id):
        abort("v2 contains a nonactive W")

    r2 = queries.loc[
        queries.target_lane.eq("resolved_w") & queries.query_route.eq("R2"),
        ["project_work_id", "query_title", "query_author", "query_id"],
    ].copy()
    active = set(v.project_work_id)
    r2 = r2.loc[r2.project_work_id.isin(active)]
    if len(r2) != 31714 or not r2.project_work_id.is_unique:
        abort("Unexpected active R2 query count or duplicate")

    frame = v[["project_work_id", "measurement_status", "operational_pairs"]].merge(
        r2, on="project_work_id", how="left", validate="one_to_one"
    )
    frame["query_title"] = frame["query_title"].fillna("")
    frame["query_author"] = frame["query_author"].fillna("")
    frame["query_id"] = frame["query_id"].fillna("")
    frame["author_name_title_flag"] = [
        author_like_flag(t, a) if q else "NO_R2_QUERY"
        for t, a, q in zip(frame.query_title, frame.query_author, frame.query_id)
    ]
    frame["nonascii_ascii_screen_flag"] = [
        bool(q and (not ascii_tokens(t) or not ascii_tokens(a)))
        for t, a, q in zip(frame.query_title, frame.query_author, frame.query_id)
    ]
    frame["no_letter_title_flag"] = [
        bool(q and numeric_or_symbol_title(t))
        for t, q in zip(frame.query_title, frame.query_id)
    ]
    frame["retrieval_coverage_diagnostic"] = [
        "NOT_REMEASURED" if pd.isna(n) else
        "NOT_QUERIED_R2_R3" if not q else
        "OPERATIONAL_CANDIDATE_PRESENT" if n > 0 else
        "QUERIED_NO_OPERATIONAL_CANDIDATE"
        for n, q in zip(frame.operational_pairs, frame.query_id)
    ]

    actual_coverage = Counter(frame.retrieval_coverage_diagnostic)
    expected_coverage = {
        "NOT_REMEASURED": 1,
        "NOT_QUERIED_R2_R3": 352,
        "OPERATIONAL_CANDIDATE_PRESENT": 7077,
        "QUERIED_NO_OPERATIONAL_CANDIDATE": 24636,
    }
    if dict(actual_coverage) != expected_coverage:
        abort(f"Unexpected coverage diagnostics: {actual_coverage}")

    author_flags = frame.loc[frame.author_name_title_flag.isin(
        ["FULL_NAME_MATCH", "SINGLE_NAME_MATCH"])]
    if len(author_flags) != 21 or int(author_flags.operational_pairs.sum()) != 34521:
        abort("Previously checked 21-W author-name flag QC does not reproduce")
    if frame.nonascii_ascii_screen_flag.sum() != 186:
        abort("Previously checked 186-W non-ASCII screen does not reproduce")
    if frame.no_letter_title_flag.sum() != 13:
        abort("Previously checked 13-W no-letter title screen does not reproduce")

    top30 = set(frame.loc[frame.operational_pairs.notna()].sort_values(
        ["operational_pairs", "project_work_id"], ascending=[False, True]
    ).head(30).project_work_id)
    if not OVERLAP_DIAGNOSTIC_W.issubset(active) or not CONTRAST_W.issubset(active):
        abort("One or more predeclared purposive W IDs are no longer active")

    cohorts = defaultdict(set)
    def mark(group: str, ids: set[str]) -> None:
        for w in ids:
            cohorts[w].add(group)

    mark("PURPOSIVE_TOP30", top30)
    mark("PURPOSIVE_AUTHOR_NAME_TITLE_21", set(author_flags.project_work_id))
    mark("PURPOSIVE_HIGH_JACCARD_15", OVERLAP_DIAGNOSTIC_W)
    mark("PURPOSIVE_CONTRAST_12", CONTRAST_W)
    mark("PURPOSIVE_NO_LETTER_TITLE_13", set(frame.loc[
        frame.no_letter_title_flag, "project_work_id"]))
    mark("RANDOM_ACTIVE_80", select_sample("RANDOM_ACTIVE_80", active, N_RANDOM_ACTIVE))
    mark("RANDOM_NOT_QUERIED_12", select_sample(
        "RANDOM_NOT_QUERIED_12", set(frame.loc[
            frame.retrieval_coverage_diagnostic.eq("NOT_QUERIED_R2_R3"),
            "project_work_id"]), N_RANDOM_NOT_QUERIED))
    mark("RANDOM_NONASCII_12", select_sample(
        "RANDOM_NONASCII_12", set(frame.loc[
            frame.nonascii_ascii_screen_flag, "project_work_id"]),
        N_RANDOM_NONASCII))

    selected = set(cohorts)
    frame["in_scope_evidence_pilot_v1"] = frame.project_work_id.isin(selected)
    frame["selection_cohorts"] = frame.project_work_id.map(
        lambda w: ";".join(sorted(cohorts.get(w, set()))))
    frame["simple_random_active_selected"] = frame.selection_cohorts.str.contains(
        "RANDOM_ACTIVE_80", regex=False)

    # Provenance joins only. NO identity or conceptual-year adjudication.
    target_members = identities.loc[
        identities.project_work_id.isin(selected)
        & identities.membership_role.eq("current_analysis_target"),
        ["project_work_id", "source_entity_id", "membership_role"],
    ]
    if target_members.duplicated(["project_work_id", "source_entity_id"]).any():
        abort("Duplicate current target membership in input identity map")
    source_lookup = entities.loc[
        entities.source.eq("openlibrary") & entities.source_namespace.eq("work"),
        ["entity_id", "source_id", "source_artifact"],
    ]
    if not source_lookup.entity_id.is_unique:
        abort("Duplicate Open Library source entity ID")
    target_sources = target_members.merge(
        source_lookup, left_on="source_entity_id", right_on="entity_id",
        how="left", validate="many_to_one")
    target_sources["ol_work_id"] = target_sources.source_id.map(normalize_ol)

    if not population.work_key.is_unique:
        abort("Historical author-enriched population has duplicate work_key")
    population["ol_work_id"] = population.work_key.map(normalize_ol)
    pop_lookup = population.set_index("ol_work_id")

    corrected = defaultdict(list)
    for r in corrections.itertuples(index=False):
        corrected[str(r.corrected_ol_work_id)].append(str(r.historical_ol_work_id))

    by_work = defaultdict(list)
    for r in target_sources.to_dict("records"):
        by_work[r["project_work_id"]].append(r)

    reviewed_rows = []
    for item in frame.loc[frame.in_scope_evidence_pilot_v1].sort_values(
        "project_work_id").to_dict("records"):
        w = item["project_work_id"]
        src = by_work.get(w, [])
        ol_ids = [s["ol_work_id"] for s in src if s["ol_work_id"]]
        matched = []
        for ol in ol_ids:
            if ol in pop_lookup.index:
                r = pop_lookup.loc[ol]
                matched.append((ol, r))
        historical_correction_ids = [h for ol in ol_ids for h in corrected.get(ol, [])]
        if not ol_ids:
            metadata_state = "NO_CURRENT_OL_TARGET"
        elif len(matched) == len(ol_ids):
            metadata_state = "ALL_CURRENT_TARGETS_IN_HISTORICAL_ENRICHED_POPULATION"
        elif historical_correction_ids:
            metadata_state = "PARTIAL_OR_NO_MATCH_WITH_KNOWN_TARGET_CORRECTION"
        else:
            metadata_state = "PARTIAL_OR_NO_HISTORICAL_ENRICHED_POPULATION_MATCH"

        reviewed_rows.append({
            "project_work_id": w,
            "cohort_labels": item["selection_cohorts"],
            "is_independent_random_active_sample": bool(item["simple_random_active_selected"]),
            "operational_pairs_v2": "" if pd.isna(item["operational_pairs"]) else int(item["operational_pairs"]),
            "measurement_status_v2": item["measurement_status"],
            "retrieval_coverage_diagnostic": item["retrieval_coverage_diagnostic"],
            "author_name_title_flag": item["author_name_title_flag"],
            "nonascii_ascii_screen_flag": item["nonascii_ascii_screen_flag"],
            "no_letter_title_flag": item["no_letter_title_flag"],
            "r2_query_id": item["query_id"],
            "r2_query_title": item["query_title"],
            "r2_query_author": item["query_author"],
            "current_ol_work_ids": joined(ol_ids),
            "ol_source_entity_ids": joined([s["source_entity_id"] for s in src]),
            "source_artifact_names": joined([s.get("source_artifact", "") for s in src]),
            "historical_population_ol_work_ids": joined([ol for ol, _ in matched]),
            "historical_population_title": joined([r["title"] for _, r in matched]),
            "historical_population_author_name": joined([r["author_name"] for _, r in matched]),
            "historical_edition_derived_min_year": joined([r["first_publish_year"] for _, r in matched]),
            "historical_population_subject_signals": joined([r["subject_keys_str"] for _, r in matched]),
            "known_target_correction_prior_ol_ids": joined(historical_correction_ids),
            "historical_metadata_join_status": metadata_state,
            # Everything below is an EMPTY manual review decision, not an assertion.
            "work_form_review": "",
            "resolved_original_work_year_review": "",
            "resolved_first_english_manifestation_year_review": "",
            "period_basis_review": "",
            "period_status_review": "",
            "language_status_review": "",
            "genre_status_review": "",
            "analysis_scope_status_review": "",
            "evidence_ids_review": "",
            "independent_sources_review": "",
            "reviewer_review": "",
            "review_method_review": "",
            "review_notes": "",
            "review_status": "NOT_REVIEWED",
        })
    review_df = pd.DataFrame(reviewed_rows)
    if len(review_df) != len(selected) or not review_df.project_work_id.is_unique:
        abort("Selected pilot has duplicate/missing W")

    outputs = {
        "sampling_frame_v1.tsv": frame,
        "scope_evidence_review_template_v1.tsv": review_df,
    }
    summary = {
        "release": "scope-evidence-pilot-v1",
        "date": CREATED_AT,
        "state": "NON_ADJUDICATIVE_EVIDENCE_TEMPLATE",
        "active_project_works": len(frame),
        "pilot_unique_project_works": len(review_df),
        "pilot_cohorts": dict(sorted(Counter(
            label for labels in cohorts.values() for label in labels).items())),
        "coverage_diagnostics": dict(sorted(actual_coverage.items())),
        "author_name_title_flagged_works": len(author_flags),
        "author_name_title_flagged_operational_pairs": int(author_flags.operational_pairs.sum()),
        "nonascii_ascii_screen_works": int(frame.nonascii_ascii_screen_flag.sum()),
        "no_letter_title_works": int(frame.no_letter_title_flag.sum()),
        "manual_scope_judgments_created": 0,
        "simple_random_design": {
            "population": "all 32,066 active Project W in integrated v2",
            "sampling_unit": "project_work_id",
            "draw": "deterministic SHA256 rank, 80 without replacement",
            "seed": SEED,
            "warning": "Purposive and diagnostic cohorts must NOT be pooled with this random cohort for prevalence estimates. Pilot is not an accuracy/precision estimate.",
        },
        "limits": [
            "Historical first_publish_year is MIN parsed linked-Edition publish_date, NOT conceptual original-work year.",
            "Author-enriched OL Work record is historical source evidence, not a verified novel or a final scope decision.",
            "Corrected OL target IDs may not be present in historical source population; never substitute historical erroneous metadata as current source truth.",
            "No held-out decisions, identity or Edition judgments, or OpenAlex v2 dispositions are changed.",
        ],
    }
    readme = """# Scope evidence pilot v1 — NON-ADJUDICATIVE

Generated from frozen OpenAlex integrated v2, Project W v7, OpenAlex registry v4,
Open Library author-enriched historical source population, and current identity
provenance. No outside publication-year or genre adjudication is performed.

## Contents
- `sampling_frame_v1.tsv`: all 32,066 active Project W, with sampling membership,
  OpenAlex count, and query-coverage diagnostics.
- `scope_evidence_review_template_v1.tsv`: one row per selected Project W,
  source-native data, identity provenance, and EMPTY reviewer decision fields.
- `summary_v1.json`: counts, sampling design, limitations.
- `manifest_v1.json`: SHA256 inputs and generated outputs.

## Sampling
`RANDOM_ACTIVE_80` is an independent, uniformly ranked SHA256 draw from the
entire active W frame (deterministic fixed seed). Other cohorts are purposive:
Top 30, the frozen 21-W author-name screen, 15 high-Jaccard diagnostic W,
12 contrast W, 13 numeric/symbol-only titles, 12 random NOT_QUERIED, and
12 random non-ASCII-screen W. Cohorts overlap; selection labels are retained.
The mixed pilot is NOT a representative sample for an unweighted prevalence
estimate. Do not use targeted records as an independent held-out precision set.

## Evidence and non-decisions
`historical_edition_derived_min_year` reproduces OL source evidence and MUST NOT
be treated as the original publication year of the conceptual work. Titles,
authors, and subject signals are copied from the historical OL source layer and
may mix translations, collections, non-novels, or corrupted records.

All `*_review` decision fields start blank; `review_status=NOT_REVIEWED`.
Document external independent evidence before issuing any scope decision.
A sample row or `*_flag` never constitutes `IN_SCOPE` / `OUT_*` adjudication.
Do not overwrite frozen W identity, earlier human/LLM decisions, OpenAlex v2,
or the closed OL Edition audit. Do not auto-retrieve or reopen held work.

`NOT_QUERIED_R2_R3` means that the frozen registry lacks the production
R2/R3 queries; R4 title-only calibration queries are not operationally counted.
`NOT_REMEASURED` is a separate missingness category. `QUERIED_NO_OPERATIONAL_CANDIDATE`
is NOT a claim that no scholarly reference exists.
"""

    SCOPE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".scope_pilot_stage_", dir=SCOPE) as temp:
        stage = Path(temp)
        for name, df in outputs.items():
            df.to_csv(stage / name, sep="\t", index=False, lineterminator="\n")
        (stage / "summary_v1.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        (stage / "README.md").write_text(readme, encoding="utf-8")
        manifest = {
            "release": summary["release"],
            "inputs_sha256": {str(p): sha(p) for p in inputs},
            "outputs_sha256": {p.name: sha(p) for p in sorted(stage.iterdir())},
            "status": summary["state"],
        }
        (stage / "manifest_v1.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        if OUT.exists():
            abort(f"Output appeared while staging: {OUT}")
        stage.rename(OUT)

    print("=== SCOPE EVIDENCE PILOT V1 ===")
    print("Active W:", len(frame))
    print("Independent random W:", N_RANDOM_ACTIVE)
    print("Pilot unique W:", len(review_df))
    print("All human scope decisions: NOT_REVIEWED")
    print("Retrieval coverage:", dict(sorted(actual_coverage.items())))
    print("Cohorts:", dict(sorted(summary["pilot_cohorts"].items())))
    print("Output:", OUT)
    print("QC: PASSED")


if __name__ == "__main__":
    main()
