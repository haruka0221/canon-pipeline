import csv, re, json

CLEAN = {
    "/works/OL715553W":   ("new grub street",                 "gissing"),
    "/works/OL16025215W": ("adventures of huckleberry finn",  "twain"),
    "/works/OL3045976W":  ("pointed roofs",                   "richardson"),
    "/works/OL1797345W":  ("uncalled",                        "dunbar"),
    "/works/OL1794917W":  ("octopus",                         "norris"),
    "/works/OL69032W":    ("rise of silas lapham",            "howells"),
}

rows = list(csv.DictReader(open("derived/jstor_mentions.tsv"), delimiter="\t"))
for r in rows:
    wid = r.get("work_id", r.get("work_key", ""))
    if wid in CLEAN:
        old = r["title_norm"]
        r["title_norm"], r["last_name"] = CLEAN[wid]
        print(f"Cleaned: '{old}' → '{r['title_norm']}'")

with open("derived/jstor_mentions.tsv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter="\t")
    w.writeheader()
    w.writerows(rows)
print("title_norm更新完了")

# JSTORスキャン（6件・単純文字列マッチ）
targets = [
    ("/works/OL715553W",   "new grub street",                "gissing"),
    ("/works/OL16025215W", "adventures of huckleberry finn", "twain"),
    ("/works/OL3045976W",  "pointed roofs",                  "richardson"),
    ("/works/OL1797345W",  "uncalled",                       "dunbar"),
    ("/works/OL1794917W",  "octopus",                        "norris"),
    ("/works/OL69032W",    "rise of silas lapham",           "howells"),
]

counts = {t[0]: {"via_jtitle": 0, "via_creators": 0} for t in targets}

def norm(s):
    s = re.sub(r'^(the|a|an)\s+', '', s.lower())
    s = re.sub(r"['\-\u2018\u2019\u201c\u201d]", '', s)
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

JSTOR = "data/jstor_metadata_2025-07-04.jsonl"
total = 0
print("JSTORスキャン中（約15分）...")
with open(JSTOR, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("content_type") != "article":
            continue
        jtitle   = norm(r.get("title") or "")
        creators = norm(r.get("creators_string") or "")
        combined = jtitle + " " + creators

        for work_id, title_norm, last_name in targets:
            if title_norm in jtitle and last_name in combined:
                counts[work_id]["via_jtitle"] += 1
            elif title_norm in creators and last_name in combined:
                counts[work_id]["via_creators"] += 1

        total += 1
        if total % 2000000 == 0:
            print(f"  {total:,}件処理済み...")

print("\n=== スキャン結果 ===")
for work_id, title_norm, last_name in targets:
    vj = counts[work_id]["via_jtitle"]
    vc = counts[work_id]["via_creators"]
    print(f"  {title_norm:<42} jstor={vj+vc:>4} (jtitle={vj}, creators={vc})")

rows = list(csv.DictReader(open("derived/jstor_mentions.tsv"), delimiter="\t"))
for r in rows:
    wid = r.get("work_id", r.get("work_key", ""))
    if wid in counts:
        vj = counts[wid]["via_jtitle"]
        vc = counts[wid]["via_creators"]
        r["jstor_mention_count"] = str(vj + vc)
        r["via_jtitle"]          = str(vj)
        r["via_creators"]        = str(vc)

with open("derived/jstor_mentions.tsv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter="\t")
    w.writeheader()
    w.writerows(rows)
print("jstor_mentions.tsv 更新完了")