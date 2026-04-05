import csv, re, json

# 29件のリスト（work_key, title_norm, last_name）
import re as _re

def norm(s):
    if not s:
        return ""
    s = _re.sub(r'^(the|a|an)\s+', '', s.lower())
    s = _re.sub(r"['\-\u2018\u2019\u201c\u201d]", '', s)
    s = _re.sub(r'[^a-z0-9\s]', ' ', s)
    return _re.sub(r'\s+', ' ', s).strip()

targets = [
    ("/works/OL7055428W",   "We Two",                          "lyall"),
    ("/works/OL1798545W",   "Jan Vedder's Wife",               "barr"),
    ("/works/OL7675136W",   "Anthony Fairfax",                 "hollis"),
    ("/works/OL4451245W",   "A Strong Minded Woman",           "hammond"),
    ("/works/OL1491830W",   "He Fell in Love with His Wife",   "roe"),
    ("/works/OL4606427W",   "That Unfortunate Marriage",       "trollope"),
    ("/works/OL262578W",    "The Doings of Raffles Haw",       "doyle"),
    ("/works/OL1797214W",   "A Question of Time",              "atherton"),
    ("/works/OL1489101W",   "Ships That Pass in the Night",    "harraden"),
    ("/works/OL32747456W",  "Renunciations",                   "wedmore"),
    ("/works/OL6016716W",   "A Prodigal in Love",              "wolf"),
    ("/works/OL18110400W",  "The Comedy of Sentiment",         "nordau"),
    ("/works/OL2339028W",   "The Lady of the Hundred Dresses", "crockett"),
    ("/works/OL16078090W",  "Topham's Folly",                  "stevenson"),
    ("/works/OL7483534W",   "Big Wallace",                     "williams"),
    ("/works/OL36868341W",  "The Valley of Silent Men",        "curwood"),
    ("/works/OL4103590W",   "Drag Harlan",                     "seltzer"),
    ("/works/OL4772826W",   "Admirals of the Caribbean",       "hart"),
    ("/works/OL879241W",    "A Crystal Age",                   "hudson"),
    ("/works/OL4975431W",   "Red Sand",                        "stribling"),
    ("/works/OL788147W",    "The Aloe",                        "mansfield"),
    ("/works/OL31415789W",  "The Outlaw Years",                "coates"),
    ("/works/OL7282228W",   "The Indigo Necklace",             "crane"),
    ("/works/OL37513138W",  "The Adventures of Huckleberry Finn","twain"),
    ("/works/OL8776079W",   "The Little Lady of Lagunitas",    "savage"),
    ("/works/OL17467W",     "Jess",                            "haggard"),
    ("/works/OL24485925W",  "The Maid of Maiden Lane",         "barr"),
    ("/works/OL24661382W",  "The Simian World",                "day"),
    ("/works/OL24797604W",  "The Heart of Unaga",              "cullum"),
]

# title_normを適用
targets_norm = [
    (wk, norm(title), last, title)
    for wk, title, last in targets
]

# 短すぎるタイトルを確認
print("=== title_norm確認 ===")
for wk, tnorm, last, orig in targets_norm:
    flag = "⚠️ SHORT" if len(tnorm) < 6 else "✅"
    print(f"  {flag}  '{tnorm}'  last='{last}'  orig='{orig}'")

# カウント初期化
counts = {t[0]: {"via_jtitle": 0, "via_creators": 0, "title_norm": t[1], "last_name": t[2], "orig_title": t[3]}
          for t in targets_norm}

JSTOR = "data/jstor_metadata_2025-07-04.jsonl"
total = 0
print("\nJSTORスキャン中（約15分）...")

with open(JSTOR, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("content_type") != "article":
            continue
        jtitle   = norm(r.get("title", ""))
        creators = norm(r.get("creators_string", ""))
        combined = jtitle + " " + creators

        for wk, tnorm, last, orig in targets_norm:
            if len(tnorm) < 6:
                continue
            if tnorm in jtitle and last in combined:
                counts[wk]["via_jtitle"] += 1
            elif tnorm in creators and last in combined:
                counts[wk]["via_creators"] += 1

        total += 1
        if total % 2000000 == 0:
            print(f"  {total:,}件処理済み...")

print("\n=== スキャン結果 ===")
print(f"{'Title':<45} {'jstor':>6}  (jtitle / creators)")
print("-" * 70)
rows_out = []
for wk, data in sorted(counts.items(), key=lambda x: -(x[1]["via_jtitle"]+x[1]["via_creators"])):
    vj = data["via_jtitle"]
    vc = data["via_creators"]
    total_c = vj + vc
    flag = "🔴 hollow" if total_c == 0 else ""
    print(f"  {data['orig_title']:<45} {total_c:>6}  ({vj}/{vc}) {flag}")
    rows_out.append({
        "work_key":            wk,
        "title":               data["orig_title"],
        "last_name":           data["last_name"],
        "jstor_mention_count": total_c,
        "via_jtitle":          vj,
        "via_creators":        vc,
        "canonical":           "1",
        "source":              "v3_extra",
    })

# 保存
with open("derived/jstor_extra29.tsv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()), delimiter="\t")
    w.writeheader()
    w.writerows(rows_out)

hollow_extra = [r for r in rows_out if r["jstor_mention_count"] == 0]
print(f"\nhollowになった作品: {len(hollow_extra)}/29件")
print("→ derived/jstor_extra29.tsv 保存完了")
