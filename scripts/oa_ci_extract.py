import json, gzip, glob, csv
from pathlib import Path

CI_ISSN = "0093-1896"
OUT = Path("derived/oa_ci_works.tsv")

files = glob.glob("/mnt/d/openalex/works/updated_date=*/part_*.gz")
print(f"Scanning {len(files)} files...")

# 逐次書き込みでメモリを使わない
with OUT.open("w", newline="") as out:
    writer = csv.writer(out, delimiter="\t")
    writer.writerow(["id", "title", "ref_count"])

    for i, fpath in enumerate(files):
        if i % 100 == 0:
            print(f"  {i}/{len(files)} files processed...")

        try:
            with gzip.open(fpath, 'rt') as f:
                for line in f:
                    w = json.loads(line)
                    src = (w.get("primary_location") or {}).get("source") or {}
                    issns = (src.get("issn") or []) + ([src.get("issn_l")] if src.get("issn_l") else [])

                    if CI_ISSN in issns:
                        writer.writerow([
                            w.get("id"),
                            w.get("title"),
                            len(w.get("referenced_works") or [])
                        ])
        except Exception as e:
            print(f"Error in {fpath}: {e}")