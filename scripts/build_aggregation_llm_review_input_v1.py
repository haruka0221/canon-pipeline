from pathlib import Path
import hashlib
import json
import os
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

DECISIONS = (
    ROOT / "derived/identity/aggregation_decisions_v3.parquet"
)

MEMBERS = (
    ROOT / "derived/identity/aggregation_review_members_v1.parquet"
)

TARGETS = (
    ROOT / "derived/identity/openlibrary_analysis_targets_v1.parquet"
)

HISTORICAL_POPULATION = Path(
    "/home/haruka221/canon-pipeline/"
    "derived/ol_dump_population_fiction_2026-02-28.tsv"
)

ENTITIES = (
    ROOT / "derived/identity/source_entities_v2.parquet"
)

ASSERTIONS = (
    ROOT / "derived/identity/identity_assertions_v1.parquet"
)

PROMPT = (
    ROOT / "prompts/aggregation_llm_review_v1.md"
)

OUT_DIR = ROOT / "derived/identity"

OUT_JSONL = (
    OUT_DIR / "aggregation_llm_review_input_v1.jsonl"
)

OUT_INDEX = (
    OUT_DIR / "aggregation_llm_review_index_v1.tsv"
)

OUT_MANIFEST = (
    OUT_DIR / "aggregation_llm_review_input_v1_manifest.json"
)

CREATED_AT = "2026-09-27"

EXPECTED_UNITS = 1194
EXPECTED_CURRENT_TARGETS = 3006
EXPECTED_EXTERNAL_ENTITIES = 1774
EXPECTED_MEMBER_ENTITIES = 4780


def require(path):
    if not path.exists():
        raise FileNotFoundError(path)


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def norm_title(value):
    value = unicodedata.normalize(
        "NFKC",
        str(value),
    ).casefold()

    return "".join(
        ch
        for ch in value
        if ch.isalnum()
    )


def json_safe(value):
    if isinstance(value, dict):
        return {
            str(k): json_safe(v)
            for k, v in value.items()
        }

    if isinstance(value, list):
        return [
            json_safe(v)
            for v in value
        ]

    if pd.isna(value):
        return ""

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


def parse_evidence(value):
    if isinstance(value, dict):
        return json_safe(value)

    value = str(value).strip()

    if not value:
        return {}

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {
            "_unparsed_evidence": value
        }


def title_pattern(ol):
    titles = {
        norm_title(x)
        for x in ol["title"]
        if str(x).strip()
    }

    authors = {
        str(x).strip()
        for x in ol["author_keys"]
        if str(x).strip()
    }

    years = {
        str(x).strip()
        for x in ol["first_publish_year"]
        if str(x).strip()
    }

    if (
        len(titles) == 1
        and len(authors) == 1
        and len(years) == 1
    ):
        return "same_title_author_year"

    if (
        len(titles) == 1
        and len(authors) == 1
    ):
        return "same_title_author"

    if len(titles) == 1:
        return "same_title_only"

    return "different_titles"


def main():
    for path in [
        DECISIONS,
        MEMBERS,
        TARGETS,
        HISTORICAL_POPULATION,
        ENTITIES,
        ASSERTIONS,
        PROMPT,
    ]:
        require(path)

    decisions = pd.read_parquet(
        DECISIONS
    ).fillna("")

    members = pd.read_parquet(
        MEMBERS
    ).fillna("")

    targets = pd.read_parquet(
        TARGETS
    ).fillna("")

    historical_population = pd.read_csv(
        HISTORICAL_POPULATION,
        sep="\t",
        dtype=str,
    ).fillna("")

    historical_population[
        "historical_ol_work_id"
    ] = historical_population[
        "work_key"
    ].str.replace(
        "/works/",
        "",
        regex=False,
    )

    subject_lookup = (
        historical_population
        .set_index("historical_ol_work_id")[
            "subject_keys_str"
        ]
        .to_dict()
    )

    entities = pd.read_parquet(
        ENTITIES
    ).fillna("")

    assertions = pd.read_parquet(
        ASSERTIONS
    ).fillna("")

    pending = decisions[
        decisions["aggregation_decision"].eq(
            "MANUAL_REVIEW_REQUIRED"
        )
    ].copy()

    pending = pending.sort_values(
        "unit_anchor_entity_id",
        kind="stable",
    ).reset_index(drop=True)

    assert len(pending) == EXPECTED_UNITS

    pending_anchors = set(
        pending["unit_anchor_entity_id"]
    )

    pending_members = members[
        members["unit_anchor_entity_id"].isin(
            pending_anchors
        )
    ].copy()

    assert len(pending_members) == EXPECTED_MEMBER_ENTITIES

    assert int(
        pending_members["is_current_target"].sum()
    ) == EXPECTED_CURRENT_TARGETS

    assert int(
        (~pending_members["is_current_target"]).sum()
    ) == EXPECTED_EXTERNAL_ENTITIES

    entity_lookup = entities.set_index(
        "entity_id"
    ).to_dict("index")

    packets = []
    index_rows = []

    for drow in pending.itertuples(index=False):
        anchor = drow.unit_anchor_entity_id

        z = pending_members[
            pending_members[
                "unit_anchor_entity_id"
            ].eq(anchor)
        ].copy()

        z = z.sort_values(
            [
                "is_current_target",
                "source",
                "entity_id",
            ],
            ascending=[
                False,
                True,
                True,
            ],
            kind="stable",
        )

        current = z[
            z["is_current_target"]
        ].copy()

        ol = current.merge(
            targets,
            left_on="entity_id",
            right_on="current_entity_id",
            how="left",
            validate="one_to_one",
        )

        assert ol["current_ol_work_id"].notna().all()

        ol = ol.sort_values(
            "entity_id",
            kind="stable",
        )

        ol_records = []

        for r in ol.itertuples(index=False):
            ol_records.append(
                {
                    "entity_id": r.entity_id,
                    "current_ol_work_id": (
                        r.current_ol_work_id
                    ),
                    "historical_entity_id": (
                        r.historical_entity_id
                    ),
                    "historical_ol_work_id": (
                        r.historical_ol_work_id
                    ),
                    "target_resolution": (
                        r.target_resolution
                    ),
                    "title": r.title,
                    "author_keys": r.author_keys,
                    "first_publish_year": (
                        r.first_publish_year
                    ),
                    "subject_keys": (
                        subject_lookup.get(
                            r.historical_ol_work_id,
                            "",
                        )
                    ),
                }
            )

        external_records = []

        external = z[
            ~z["is_current_target"]
        ].copy()

        for r in external.itertuples(index=False):
            meta = entity_lookup.get(
                r.entity_id,
                {},
            )

            external_records.append(
                {
                    "entity_id": r.entity_id,
                    "source": r.source,
                    "source_id": meta.get(
                        "source_id",
                        "",
                    ),
                    "source_snapshot": meta.get(
                        "source_snapshot",
                        "",
                    ),
                    "membership_role": (
                        r.member_role
                    ),
                }
            )

        member_ids = set(
            z["entity_id"]
        )

        az = assertions[
            assertions["left_entity_id"].isin(
                member_ids
            )
            & assertions[
                "right_entity_id"
            ].isin(member_ids)
        ].copy()

        az = az.sort_values(
            "assertion_id",
            kind="stable",
        )

        assertion_records = []

        for r in az.itertuples(index=False):
            left_meta = entity_lookup.get(
                r.left_entity_id,
                {},
            )

            right_meta = entity_lookup.get(
                r.right_entity_id,
                {},
            )

            assertion_records.append(
                {
                    "assertion_id": r.assertion_id,
                    "left_entity_id": (
                        r.left_entity_id
                    ),
                    "left_source": left_meta.get(
                        "source",
                        "",
                    ),
                    "left_source_id": (
                        left_meta.get(
                            "source_id",
                            "",
                        )
                    ),
                    "right_entity_id": (
                        r.right_entity_id
                    ),
                    "right_source": (
                        right_meta.get(
                            "source",
                            "",
                        )
                    ),
                    "right_source_id": (
                        right_meta.get(
                            "source_id",
                            "",
                        )
                    ),
                    "identity_decision": (
                        r.identity_decision
                    ),
                    "method": r.method,
                    "method_version": (
                        r.method_version
                    ),
                    "confidence": (
                        r.confidence
                    ),
                    "evidence": parse_evidence(
                        r.evidence
                    ),
                }
            )

        ol_ids = set(
            current["entity_id"]
        )

        gr_ids = set(
            external.loc[
                external["source"].eq(
                    "goodreads"
                ),
                "entity_id",
            ]
        )

        wd_ids = set(
            external.loc[
                external["source"].eq(
                    "wikidata"
                ),
                "entity_id",
            ]
        )

        direct_gr = {
            x["left_entity_id"]
            for x in assertion_records
            if (
                x["left_entity_id"] in ol_ids
                and x["right_entity_id"] in gr_ids
                and x["identity_decision"] == "SAME"
            )
        }

        direct_wd = {
            x["left_entity_id"]
            for x in assertion_records
            if (
                x["left_entity_id"] in ol_ids
                and x["right_entity_id"] in wd_ids
                and x["identity_decision"] == "SAME"
            )
        }

        packet = {
            "review_schema": (
                "aggregation_llm_review_v1"
            ),
            "unit_anchor_entity_id": anchor,
            "structural_class": (
                drow.structural_class
            ),
            "current_target_count": int(
                drow.current_target_count
            ),
            "goodreads_entity_count": len(
                gr_ids
            ),
            "wikidata_entity_count": len(
                wd_ids
            ),
            "metadata_profile": {
                "pattern": title_pattern(ol),
                "all_ol_direct_to_goodreads": (
                    bool(gr_ids)
                    and direct_gr == ol_ids
                ),
                "all_ol_direct_to_wikidata": (
                    bool(wd_ids)
                    and direct_wd == ol_ids
                ),
            },
            "openlibrary_records": (
                ol_records
            ),
            "external_entities": (
                external_records
            ),
            "identity_assertions": (
                assertion_records
            ),
        }

        packets.append(packet)

        index_rows.append(
            {
                "unit_anchor_entity_id": anchor,
                "structural_class": (
                    drow.structural_class
                ),
                "current_target_count": (
                    len(ol_records)
                ),
                "goodreads_entity_count": (
                    len(gr_ids)
                ),
                "wikidata_entity_count": (
                    len(wd_ids)
                ),
                "external_entity_count": (
                    len(external_records)
                ),
                "assertion_count": (
                    len(assertion_records)
                ),
                "metadata_pattern": (
                    packet[
                        "metadata_profile"
                    ]["pattern"]
                ),
                "all_ol_direct_to_goodreads": (
                    packet[
                        "metadata_profile"
                    ][
                        "all_ol_direct_to_goodreads"
                    ]
                ),
                "all_ol_direct_to_wikidata": (
                    packet[
                        "metadata_profile"
                    ][
                        "all_ol_direct_to_wikidata"
                    ]
                ),
            }
        )

    assert len(packets) == EXPECTED_UNITS

    tmp = OUT_JSONL.with_name(
        OUT_JSONL.name + ".tmp"
    )

    with tmp.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as f:
        for packet in packets:
            f.write(
                json.dumps(
                    json_safe(packet),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            f.write("\n")

    os.replace(tmp, OUT_JSONL)

    index = pd.DataFrame(index_rows)

    assert len(index) == EXPECTED_UNITS
    assert index[
        "unit_anchor_entity_id"
    ].is_unique

    tmp = OUT_INDEX.with_name(
        OUT_INDEX.name + ".tmp"
    )

    index.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, OUT_INDEX)

    manifest = {
        "release": (
            "aggregation-llm-review-input-v1"
        ),
        "created_at": CREATED_AT,
        "purpose": (
            "Deterministic review packets for the "
            "1,194 aggregation units still pending "
            "after aggregation_decisions_v3."
        ),
        "review_policy": {
            "prompt": (
                "prompts/"
                "aggregation_llm_review_v1.md"
            ),
            "prompt_sha256": (
                sha256_file(PROMPT)
            ),
            "allowed_decisions": [
                "ONE_WORK",
                "MULTIPLE_WORKS",
                "UNRESOLVED",
            ],
            "note": (
                "The LLM reviews partitions of current "
                "Open Library targets. External source "
                "entities are evidence, not the objects "
                "being partitioned."
            ),
        },
        "inputs": {
            "aggregation_decisions_v3": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_decisions_v3.parquet"
                ),
                "sha256": (
                    sha256_file(DECISIONS)
                ),
            },
            "aggregation_review_members_v1": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_review_members_v1.parquet"
                ),
                "sha256": (
                    sha256_file(MEMBERS)
                ),
            },
            "openlibrary_analysis_targets_v1": {
                "artifact": (
                    "derived/identity/"
                    "openlibrary_analysis_targets_v1.parquet"
                ),
                "sha256": (
                    sha256_file(TARGETS)
                ),
            },
            "historical_openlibrary_population": {
                "artifact": (
                    "derived/"
                    "ol_dump_population_fiction_2026-02-28.tsv"
                ),
                "read_from": (
                    "/home/haruka221/canon-pipeline/"
                    "derived/"
                    "ol_dump_population_fiction_2026-02-28.tsv"
                ),
                "sha256": (
                    sha256_file(HISTORICAL_POPULATION)
                ),
                "fields_used": [
                    "work_key",
                    "subject_keys_str"
                ],
            },
            "source_entities_v2": {
                "artifact": (
                    "derived/identity/"
                    "source_entities_v2.parquet"
                ),
                "sha256": (
                    sha256_file(ENTITIES)
                ),
            },
            "identity_assertions_v1": {
                "artifact": (
                    "derived/identity/"
                    "identity_assertions_v1.parquet"
                ),
                "sha256": (
                    sha256_file(ASSERTIONS)
                ),
            },
        },
        "counts": {
            "review_units": EXPECTED_UNITS,
            "current_openlibrary_targets": (
                EXPECTED_CURRENT_TARGETS
            ),
            "external_entities": (
                EXPECTED_EXTERNAL_ENTITIES
            ),
            "member_entities": (
                EXPECTED_MEMBER_ENTITIES
            ),
        },
        "outputs": {
            "jsonl": (
                "derived/identity/"
                "aggregation_llm_review_input_v1.jsonl"
            ),
            "index_tsv": (
                "derived/identity/"
                "aggregation_llm_review_index_v1.tsv"
            ),
        },
    }

    manifest["outputs"]["jsonl_sha256"] = (
        sha256_file(OUT_JSONL)
    )

    manifest["outputs"]["index_tsv_sha256"] = (
        sha256_file(OUT_INDEX)
    )

    tmp = OUT_MANIFEST.with_name(
        OUT_MANIFEST.name + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    os.replace(tmp, OUT_MANIFEST)

    print("=== LLM REVIEW INPUT V1 ===")
    print("units:", len(index))
    print(
        "current OL targets:",
        int(index["current_target_count"].sum()),
    )
    print(
        "external entities:",
        int(index["external_entity_count"].sum()),
    )

    print("\n=== STRUCTURAL CLASS ===")
    print(
        index["structural_class"]
        .value_counts()
        .to_string()
    )

    print("\n=== METADATA PATTERN ===")
    print(
        index["metadata_pattern"]
        .value_counts()
        .to_string()
    )

    print("\n=== DIRECT-EDGE COVERAGE ===")
    print(
        index.groupby(
            [
                "all_ol_direct_to_goodreads",
                "all_ol_direct_to_wikidata",
            ]
        )
        .size()
        .to_string()
    )

    print("\n=== PACKET SIZE ===")
    print(
        "jsonl bytes:",
        OUT_JSONL.stat().st_size,
    )

    print("\n=== OUTPUT SHA256 ===")
    print(
        "jsonl:",
        sha256_file(OUT_JSONL),
    )
    print(
        "index:",
        sha256_file(OUT_INDEX),
    )
    print(
        "manifest:",
        sha256_file(OUT_MANIFEST),
    )

    print("\nNo API calls were made.")


if __name__ == "__main__":
    main()
