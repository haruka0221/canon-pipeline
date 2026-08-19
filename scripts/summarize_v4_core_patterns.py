import csv
from collections import Counter, defaultdict

INFILE = "derived/divergence_patterns_v4_scoped.tsv"
OUT = "derived/divergence_pattern_summary_v4_core.tsv"

def to_int(x):
    try:
        return int(float(x or 0))
    except Exception:
        return 0

rows = list(csv.DictReader(open(INFILE, encoding="utf-8"), delimiter="\t"))

core = [r for r in rows if r.get("analysis_scope_flag") == "core_analysis"]

counter = Counter(r["divergence_pattern_v3"] for r in core)

with open(OUT, "w", encoding="utf-8", newline="") as f:
    fn = ["divergence_pattern", "count", "example_titles"]
    w = csv.DictWriter(f, fieldnames=fn, delimiter="\t")
    w.writeheader()

    for pat, count in counter.most_common():
        examples = sorted(
            [r for r in core if r["divergence_pattern_v3"] == pat],
            key=lambda r: -(
                to_int(r["academic_signal_v3"])
                + to_int(r["circulation_signal_v3"])
                + to_int(r["reader_signal_v3"])
            )
        )[:15]

        w.writerow({
            "divergence_pattern": pat,
            "count": count,
            "example_titles": " | ".join(
                f'{r["title"]} ({r["author_name"]})'
                for r in examples
            )
        })

print(f"出力: {OUT}")
print(f"core_analysis 件数: {len(core):,}")

print("\n=== v4 core 乖離パターン概要 ===")
for pat, count in counter.most_common():
    print(f"{pat:65s} {count:6,}")

groups = defaultdict(list)
for r in core:
    groups[r["divergence_pattern_v3"]].append(r)

for pat in sorted(groups):
    print("\n" + "=" * 80)
    print(pat)
    print("=" * 80)

    items = sorted(
        groups[pat],
        key=lambda r: (
            -to_int(r["academic_signal_v3"]),
            -to_int(r["circulation_signal_v3"]),
            -to_int(r["reader_signal_v3"])
        )
    )[:20]

    for r in items:
        print(
            f'{r["title"][:36]:36s} '
            f'{r["author_name"][:22]:22s} '
            f'acad={to_int(r["academic_signal_v3"]):5d} '
            f'ed+ht={to_int(r["circulation_signal_v3"]):5d} '
            f'gr={to_int(r["reader_signal_v3"]):8d} '
            f'canon={r["canonical"]}'
        )
