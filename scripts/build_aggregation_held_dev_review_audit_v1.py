import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

source = Path(
    "derived/identity/aggregation_held_dev_review_draft_v1/"
    "development_review_sheet_v1.tsv"
)
out_dir = Path(
    "derived/identity/aggregation_held_dev_review_audit_v1"
)

# Primary issues are AI-assisted classifications,
# NOT independently adjudicated human labels.
issues = {
    "E000005163": "collection_contents_ambiguity",
    "E000022268": "alternate_publication_title",
    "E000021061": "duplicate_source_work",
    "E000031310": "alternate_title_translation",
    "E000020209": "volume_granularity",
    "E000005779": "collection_vs_constituent",
    "E000007121": "later_edition_separate_work",
    "E000017398": "bibliographic_year_conflict",
    "E000002390": "contributor_role",
    "E000004873": "collected_series_volume",
    "E000019600": "multi_volume_completeness",
    "E000005348": "part_whole_translation_abridgment",
    "E000004501": "educational_abridgment",
    "E000034716": "source_work_internal_heterogeneity",
    "E000001231": "audio_part_vs_whole",
    "E000033606": "collection_scope_collision",
    "E000009675": "author_id_discrepancy",
    "E000001842": "multiple_translations",
    "E000014424": "later_edition_separate_work",
    "E000016328": "author_attribution_anomaly",
}

with source.open(encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f, delimiter="\t"))

assert len(rows) == 20
assert {r["unit_anchor_entity_id"] for r in rows} == set(issues)
assert all(r["review_status"] == "NOT_ADJUDICATED" for r in rows)
assert all(not r["human_decision"] for r in rows)

summary = []
for r in rows:
    note = r["preliminary_discussion_note"]
    match = re.search(
        r"\b(ONE_WORK|MULTIPLE_WORKS|UNRESOLVED)\b",
        note[:300]
    )
    assert match, r["unit_anchor_entity_id"]

    summary.append({
        "review_order": r["review_order"],
        "unit_anchor_entity_id": r["unit_anchor_entity_id"],
        "ai_preliminary_category": match.group(1),
        "primary_issue_ai_assisted": issues[
            r["unit_anchor_entity_id"]
        ],
        "url_recorded_in_note": (
            "YES" if re.search(r"https?://", note) else "NO"
        ),
        "source_content_verified_by_audit": "NO",
        "human_review_status": r["review_status"],
    })

counts = Counter(
    r["ai_preliminary_category"] for r in summary
)
assert counts == {
    "ONE_WORK": 12,
    "MULTIPLE_WORKS": 2,
    "UNRESOLVED": 6,
}

missing = [
    r["unit_anchor_entity_id"]
    for r in summary if r["url_recorded_in_note"] == "NO"
]
assert set(missing) == {
    "E000005163", "E000022268", "E000021061"
}

if out_dir.exists():
    raise SystemExit("STOP: audit output already exists")

out_dir.mkdir(parents=True, exist_ok=False)
out_file = out_dir / "development_review_audit_v1.tsv"

with out_file.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=list(summary[0]), delimiter="\t"
    )
    writer.writeheader()
    writer.writerows(summary)

sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

manifest = {
    "status": "AI_ASSISTED_DEVELOPMENT_AUDIT",
    "input_ledger": str(source),
    "input_sha256": sha(source),
    "output_sha256": sha(out_file),
    "units": len(summary),
    "preliminary_counts": dict(sorted(counts.items())),
    "missing_url_in_note": missing,
    "human_decisions": 0,
    "limitations": [
        "Preliminary categories are not human gold labels.",
        "Primary issues are illustrative, not exhaustive.",
        "URL presence does not establish source validity.",
        "The audit does not verify bibliographic claims.",
        "The sample does not estimate full-population rates.",
    ],
}

manifest_file = out_dir / "manifest_v1.json"
manifest_file.write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8"
)

print("=== AUDIT V1 ===")
print("Units:", len(summary))
print("Preliminary categories:", dict(counts))
print("No URL in note:", len(missing))
print("Human decisions:", 0)
print("Input SHA256:", sha(source))
print("Output:", out_file)
print("Manifest:", manifest_file)
print("Existing ledger and Project W unchanged")
