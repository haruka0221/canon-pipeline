import csv, re, json, gzip, glob, os

def norm(s):
    if not s:
        return ""
    s = re.sub(r'^(the|a|an)\s+', '', s.lower())
    s = re.sub(r"['\-\u2018\u2019\u201c\u201d]", '', s)
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

# extra30の読み込み
rows = list(csv.DictReader(open("derived/jstor_extra29.tsv"), delimiter="\t"))
targets = []
for r in rows:
    tnorm = norm(r["title"])
    last  = r["last_name"]
    if len(tnorm) >= 6:
        targets.append((r["work_key"], tnorm, last, r["title"]))
    else:
        print(f"⚠️ SHORT (skip): '{tnorm}' ({r['title']})")

print(f"スキャン対象: {len(targets)}/30件")

counts = {t[0]: {"via_title": 0, "title_norm": t[1],
                  "last_name": t[2], "orig_title": t[3]}
          for t in targets}

OA_PATH = "/mnt/d/openalex/works/updated_date=*/part_*.gz"
files = sorted(glob.glob(OA_PATH))
print(f"OpenAlexファイル数: {len(files)}")
print("スキャン中（約30分）...")

processed = 0
for i, fpath in enumerate(files):
    try:
        with gzip.open(fpath, 'rt', encoding='utf-8') as f:
            for line in f:
                w = json.loads(line)
                display = norm(w.get("display_name", ""))
                if not display:
                    continue
                for wk, tnorm, last, orig in targets:
                    if tnorm in display and last in display:
                        counts[wk]["via_title"] += 1
    except Exception as e:
        pass
    if (i+1) % 100 == 0:
        print(f"  {i+1}/{len(files)}ファイル完了...")

print("\n=== OpenAlexスキャン結果 ===")
print(f"{'Title':<45} {'OA':>6}")
print("-" * 55)

results = []
for wk, data in sorted(counts.items(),
                        key=lambda x: -x[1]["via_title"]):
    vc = data["via_title"]
    flag = "🔴" if vc == 0 else ""
    print(f"  {data['orig_title']:<45} {vc:>6}  {flag}")
    results.append({
        "work_key": wk,
        "title":    data["orig_title"],
        "last_name": data["last_name"],
        "oa_count": vc,
        "source":   "OA_snapshot_2026",
    })

with open("derived/oa_extra30.tsv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()), delimiter="\t")
    w.writeheader()
    w.writerows(results)

zero = sum(1 for r in results if r["oa_count"] == 0)
print(f"\nOA=0: {zero}/30件")
print("→ derived/oa_extra30.tsv 保存完了")
