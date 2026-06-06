import argparse
import csv
import json
import math
import re
from pathlib import Path
from collections import Counter, defaultdict

DEFAULT_INPUT = Path("derived/jstor_ll_articles.jsonl")
DEFAULT_OUT_DIR = Path("derived/jstor_hod")

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "he", "her", "his", "in", "into", "is", "it",
    "its", "of", "on", "or", "that", "the", "their", "this", "to",
    "was", "were", "with", "without", "within",
    "heart", "darkness", "conrad", "joseph",
    "book", "review", "reviews", "article", "articles",
}

PERIODS = [
    ("pre_achebe_1940_1974", 1940, 1974),
    ("post_achebe_1975_2019", 1975, 2019),
    ("1940_1959", 1940, 1959),
    ("1960_1974", 1960, 1974),
    ("1975_1989", 1975, 1989),
    ("1990_2004", 1990, 2004),
    ("2005_2019", 2005, 2019),
]


def normalize_text(value):
    value = str(value or "").lower()
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def tokenize(text):
    text = normalize_text(text)
    tokens = []
    for tok in text.split():
        if len(tok) < 3:
            continue
        if tok in STOPWORDS:
            continue
        if tok.isdigit():
            continue
        tokens.append(tok)
    return tokens


def article_text(article, fields):
    parts = []
    for field in fields:
        value = article.get(field, "")
        if isinstance(value, list):
            parts.extend(str(v) for v in value)
        else:
            parts.append(str(value))
    return " ".join(parts)


def log_odds_ratio_with_prior(target_counts, bg_counts, alpha=0.01, min_target=2):
    vocab = set(target_counts) | set(bg_counts)
    target_total = sum(target_counts.values())
    bg_total = sum(bg_counts.values())
    vocab_size = len(vocab)

    rows = []
    for term in sorted(vocab):
        a = target_counts[term]
        b = bg_counts[term]

        if a < min_target:
            continue

        # Monroe-style smoothed log odds, simplified for exploratory keyness.
        p_target = (a + alpha) / (target_total + alpha * vocab_size)
        p_bg = (b + alpha) / (bg_total + alpha * vocab_size)

        log_odds = math.log(p_target / p_bg)

        rows.append({
            "term": term,
            "target_count": a,
            "background_count": b,
            "target_total": target_total,
            "background_total": bg_total,
            "target_per_1000": round(a / target_total * 1000, 4) if target_total else 0,
            "background_per_1000": round(b / bg_total * 1000, 4) if bg_total else 0,
            "log_odds": round(log_odds, 6),
        })

    return sorted(rows, key=lambda r: r["log_odds"], reverse=True)


def main():
    parser = argparse.ArgumentParser(
        description="Extract words that are unusually frequent in JSTOR L&L records whose title mentions Heart of Darkness."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--fields",
        nargs="+",
        default=["title", "keywords"],
        help="Fields to analyze. Default: title keywords",
    )
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument("--min-target", type=int, default=2)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    if not args.input.exists():
        raise FileNotFoundError(args.input)

    articles = []
    with args.input.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                article = json.loads(line)
            except Exception:
                continue

            date = str(article.get("date", ""))
            if not date[:4].isdigit():
                continue

            year = int(date[:4])
            title = str(article.get("title", ""))

            if not (1940 <= year <= 2019):
                continue

            text = article_text(article, args.fields)
            tokens = tokenize(text)

            articles.append({
                "year": year,
                "title": title,
                "is_hod": "heart of darkness" in title.lower(),
                "tokens": tokens,
                "raw_text": text,
            })

    all_rows = []
    example_rows = []

    for period_name, start, end in PERIODS:
        target_counts = Counter()
        bg_counts = Counter()
        target_records = []

        for article in articles:
            if not (start <= article["year"] <= end):
                continue

            if article["is_hod"]:
                target_counts.update(article["tokens"])
                target_records.append(article)
            else:
                bg_counts.update(article["tokens"])

        keyness_rows = log_odds_ratio_with_prior(
            target_counts,
            bg_counts,
            min_target=args.min_target,
        )

        for rank, row in enumerate(keyness_rows[: args.top_n], start=1):
            all_rows.append({
                "period": period_name,
                "rank": rank,
                **row,
            })

        for article in target_records:
            example_rows.append({
                "period": period_name,
                "year": article["year"],
                "title": article["title"],
                "tokens": " ".join(article["tokens"]),
            })

    keyness_path = args.out_dir / "hod_keyness_by_period.csv"
    examples_path = args.out_dir / "hod_keyness_target_records.csv"

    with keyness_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "period", "rank", "term",
            "target_count", "background_count",
            "target_total", "background_total",
            "target_per_1000", "background_per_1000",
            "log_odds",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    with examples_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["period", "year", "title", "tokens"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(example_rows)

    print(f"Analyzed fields: {', '.join(args.fields)}")
    print(f"Saved: {keyness_path}")
    print(f"Saved: {examples_path}")
    print()

    current_period = None
    for row in all_rows:
        if row["period"] != current_period:
            current_period = row["period"]
            print()
            print(f"=== {current_period} ===")
        if row["rank"] <= 20:
            print(
                f"{row['rank']:>2}. {row['term']:<20} "
                f"target={row['target_count']:<3} "
                f"bg={row['background_count']:<6} "
                f"log_odds={row['log_odds']}"
            )


if __name__ == "__main__":
    main()
