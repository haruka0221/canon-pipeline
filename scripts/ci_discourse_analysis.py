#!/usr/bin/env python3
"""
ci_discourse_analysis.py — Stage 7, Step 2
Discourse analysis of extracted Critical Inquiry data.

Usage:
    python3 scripts/ci_discourse_analysis.py

Inputs  (produced by ci_extract_citations.py):
    derived/ci_articles.tsv
    derived/ci_footnotes.tsv
    derived/ci_cited_names.tsv
    derived/ci_intro_sentences.tsv

Cross-validation inputs:
    derived/jstor_mentions.tsv
    derived/openalex_snapshot_mentions.tsv

Outputs:
    derived/ci_author_freq.tsv        — most-cited critics / scholars
    derived/ci_concept_freq.tsv       — concept keyword frequency
    derived/ci_intro_patterns.tsv     — argumentative structure per article
    derived/ci_tension_zones.tsv      — works that are shadow/hollow vs CI-cited
    derived/ci_discourse_summary.txt  — human-readable findings
"""

import csv
from itertools import count
import re
import sys
import logging
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
log_path = Path("logs") / f"ci_discourse_{datetime.now().strftime('%Y-%m-%d')}.log"
log_path.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Concept keyword taxonomy
# (drawn from WORKFLOW.md research questions)
# ─────────────────────────────────────────────

CONCEPT_GROUPS = {
    # Canon and field formation
    "canon":           [r"\bcanon(ical|icity|ization|izing)?\b"],
    "modernism":       [r"\bmodernism\b", r"\bmodernist\b", r"\bmodernity\b"],
    "field_formation": [r"\bliterary\s+(?:field|studies|criticism|history|canon)\b",
                        r"\bdiscipline\b", r"\binstitution(?:al)?\b",
                        r"\bperiodization\b"],
    "world_lit":       [r"\bworld\s+literature\b", r"\bcomparative\s+literature\b",
                        r"\bglobal\s+(?:novel|literature|fiction)\b"],
    # Critical theory axes
    "postcolonial":    [r"\bpostcolonial\b", r"\bcolonial(?:ism|ity)?\b",
                        r"\bdecoloni[sz]e\b", r"\bimperial(?:ism)?\b"],
    "gender_sexuality":[r"\bgender\b", r"\bfeminis[tm]\b", r"\bqueer\b",
                        r"\bsexuality\b", r"\bwomen\b"],
    "race":            [r"\brace\b", r"\bracial(?:iz)?\b", r"\bBlackness\b",
                        r"\bwhiteness\b", r"\bAfrican\s+American\b"],
    "class":           [r"\bclass\b", r"\bMarxis[mt]\b", r"\blabor\b",
                        r"\bcapital(?:ism)?\b"],
    # Method and form
    "distant_reading": [r"\bdistant\s+reading\b", r"\bcomputational\b",
                        r"\bquantitative\b", r"\bdigital\s+humanities\b"],
    "close_reading":   [r"\bclose\s+reading\b", r"\btextual\s+analysis\b"],
    "form":            [r"\bform(?:alism)?\b", r"\bnarrativ(?:e|ology)\b",
                        r"\bgenre\b", r"\bstyle\b", r"\bpoetics\b"],
    # Institutional / market
    "publishing":      [r"\bpublish(?:ing|er)?\b", r"\bmarket\b",
                        r"\bcommercial\b", r"\bcommodif\w+\b"],
    "pedagogy":        [r"\bteach(?:ing)?\b", r"\bpedagog\w+\b",
                        r"\bcurricul\w+\b", r"\bsyllab\w+\b"],
    # Temporal
    "expansion":       [r"\bexpansion\b", r"\benlargement\b",
                        r"\bdiversif\w+\b", r"\binclusion\b"],
    "archive":         [r"\barchive\b", r"\barchival\b"],
}

# ─────────────────────────────────────────────
# Key critics / theorists to track specifically
# (combine with frequency-based discovery)
# ─────────────────────────────────────────────

KEY_SCHOLARS = [
    # Field formation
    "Rainey", "Moretti", "Casanova", "Guillory", "Dimock",
    "Kadir", "Damrosch", "Spivak", "Bhabha", "Said",
    # Feminist / gender
    "Butler", "Showalter", "Gilbert", "Gubar", "Irigaray",
    "Kristeva", "Cixous",
    # Postcolonial
    "Fanon", "Achebe", "Glissant", "Wynter",
    # Theory
    "Derrida", "Foucault", "Lacan", "Althusser", "Jameson",
    "Lukacs", "Benjamin", "Adorno", "Bourdieu",
    # Modernism
    "Woolf", "Joyce", "Pound", "Eliot", "Stein",
    "Williams", "Levenson", "Mao", "Walkowitz",
    # Digital / distant
    "Underwood", "Jockers", # "Long" removed — common adjective causes false positives in intro_text scan "So",
    # Huyssen
    "Huyssen",
]


# ─────────────────────────────────────────────
# Argumentative pattern markers
# ─────────────────────────────────────────────

ARG_PATTERNS = {
    "position_to_overcome": re.compile(
        r"\b(?:however|but|yet|although|while|whereas|against|despite|"
        r"in\s+contrast|contrary\s+to|has\s+been\s+argued|conventionally)\b",
        re.IGNORECASE
    ),
    "positive_alignment": re.compile(
        r"\b(?:following|building\s+on|extending|drawing\s+on|after|"
        r"in\s+the\s+tradition\s+of|like|as|with)\b",
        re.IGNORECASE
    ),
    "claim_assertion": re.compile(
        r"\b\w+\s+(?:argues?|claims?|contends?|suggests?|insists?|"
        r"asserts?|demonstrates?|shows?|proposes?)\b",
        re.IGNORECASE
    ),
    "gap_identification": re.compile(
        r"\b(?:little\s+attention|underexplored|overlooked|neglected|"
        r"has\s+not\s+(?:been\s+)?(?:considered|examined|addressed)|"
        r"remains\s+under(?:explored|studied|theorized))\b",
        re.IGNORECASE
    ),
    "intervention_marker": re.compile(
        r"\b(?:this\s+(?:essay|article|paper|reading)\s+"
        r"(?:argues?|examines?|explores?|proposes?|offers?|seeks?\s+to|"
        r"turns?\s+to|contends?))\b",
        re.IGNORECASE
    ),
}


# ─────────────────────────────────────────────
# I/O helpers
# ─────────────────────────────────────────────

def load_tsv(path: Path) -> list[dict]:
    if not path.exists():
        logger.warning(f"Missing: {path}")
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write_tsv(rows: list[dict], path: Path, fieldnames: list[str]):
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    logger.info(f"Written {len(rows)} rows → {path}")


# ─────────────────────────────────────────────
# Analysis functions
# ─────────────────────────────────────────────

def analyse_author_frequency(
    cited_rows: list[dict],
    articles: list[dict]
) -> list[dict]:
    """
    Count how many articles cite each author name, plus total mention count.
    Combines regex-extracted names with KEY_SCHOLARS list.
    """
    # Count by article (unique per article) and total
    name_article_set = defaultdict(set)   # name → set of filenames
    name_total       = Counter()

    for row in cited_rows:
        name = row.get("cited_name", "").strip()
        if not name:
            continue
        name_article_set[name].add(row["filename"])
        name_total[name] += 1

    # Also scan intro_text for KEY_SCHOLARS (in case footnote extraction missed them)
    for art in articles:
        intro = art.get("intro_text", "")
        for scholar in KEY_SCHOLARS:
            pattern = re.compile(r"(?<![A-Za-z])" + re.escape(scholar) + r"(?![a-z])")
            if pattern.search(intro):
                name_article_set[scholar].add(art["filename"])
                count = len(pattern.findall(intro))
                name_total[scholar] += count

    rows_out = []
    for name, article_set in name_article_set.items():
        rows_out.append({
            "cited_name":    name,
            "n_articles":    len(article_set),
            "n_total_mentions": name_total[name],
            "is_key_scholar": 1 if name in KEY_SCHOLARS else 0,
        })

    NOISE = {
        "so", "ibid", "cf", "id", "op", "et", "al", "pp", "ed", "trans",
        "action", "profession", "illuminations", "sciences", "british",
        "muets", "tatour",
    }
    rows_out = [
        r for r in rows_out
        if r["cited_name"].lower() not in NOISE
        and not r["cited_name"].lower().startswith("the ")
        and not r["cited_name"].lower().startswith("a ")
        and len(r["cited_name"]) < 30
        and not any(c.isdigit() for c in r["cited_name"])
        and (" " not in r["cited_name"] or len(r["cited_name"].split()) <= 3)
    ]
    rows_out.sort(key=lambda r: (-r["n_articles"], -r["n_total_mentions"]))
    return rows_out


def analyse_concepts(articles: list[dict]) -> list[dict]:
    """
    Count concept group occurrences across all article intro texts and footnotes.
    Returns one row per concept per article, and an aggregate.
    """
    compiled = {
        group: [re.compile(p, re.IGNORECASE) for p in patterns]
        for group, patterns in CONCEPT_GROUPS.items()
    }

    rows_out = []
    for art in articles:
        text = (art.get("intro_text", "")).lower()
        year = art.get("year_extracted") or art.get("year_hint", "")

        for group, patterns in compiled.items():
            count = sum(len(p.findall(text)) for p in patterns)
            if count > 0:
                rows_out.append({
                    "filename": art["filename"],
                    "year":     year,
                    "concept_group": group,
                    "count":    count,
                })

    # Also build aggregate
    agg = Counter()
    for row in rows_out:
        agg[row["concept_group"]] += row["count"]

    # Merge aggregate as summary rows (filename=__TOTAL__)
    for group, total in agg.most_common():
        rows_out.append({
            "filename": "__TOTAL__",
            "year":     "all",
            "concept_group": group,
            "count":    total,
        })

    return rows_out


def analyse_intro_patterns(
    articles: list[dict],
    intro_sentences: list[dict]
) -> list[dict]:
    """
    For each article, count argumentative markers in intro text.
    Also extract exemplar sentences for each pattern.
    """
    # Group sentences by filename
    sents_by_file = defaultdict(list)
    for s in intro_sentences:
        sents_by_file[s["filename"]].append(s.get("sentence", ""))

    rows_out = []
    for art in articles:
        filename = art["filename"]
        intro_text = art.get("intro_text", "")
        year       = art.get("year_extracted") or art.get("year_hint", "")

        row = {
            "filename": filename,
            "year":     year,
            "n_pages":  art.get("n_pages", ""),
            "n_footnotes": art.get("n_footnotes", ""),
        }

        # Count each pattern type
        for pname, pattern in ARG_PATTERNS.items():
            matches = pattern.findall(intro_text)
            row[f"{pname}_count"] = len(matches)

            # Find first exemplar sentence
            exemplar = ""
            for sent in sents_by_file[filename]:
                if pattern.search(sent):
                    exemplar = sent[:200]
                    break
            row[f"{pname}_example"] = exemplar

        # Dominant pattern
        pattern_counts = {
            pname: row[f"{pname}_count"] for pname in ARG_PATTERNS
        }
        dominant = max(pattern_counts, key=pattern_counts.get) if pattern_counts else ""
        row["dominant_pattern"] = dominant if pattern_counts.get(dominant, 0) > 0 else "none"

        rows_out.append(row)

    return rows_out


def analyse_tension_zones(
    articles: list[dict],
    jstor_rows: list[dict],
    oa_rows: list[dict],
) -> list[dict]:
    """
    Find works that are:
    - Hollow canon (canonical=1, jstor=0) but appear in CI citations
    - Shadow canon (canonical=0, jstor≥5) and appear in CI citations
    Cross-validates pipeline data with CI discourse.
    """
    # Build CI mentioned work titles from intro texts
    ci_combined_text = " ".join(
        art.get("intro_text", "")
        for art in articles
    ).lower()

    rows_out = []

    for row in jstor_rows:
        title      = row.get("title", "")
        canonical  = int(row.get("canonical", 0))
        jstor_count = int(row.get("jstor_mention_count", 0))
        author     = row.get("author", "")
        work_id    = row.get("work_id", "")

        # Hollow canon: canonical but no JSTOR hits
        is_hollow = (canonical == 1 and jstor_count == 0)
        # Shadow canon: not canonical but ≥5 JSTOR hits
        is_shadow = (canonical == 0 and jstor_count >= 5)

        if not (is_hollow or is_shadow):
            continue

        # Check if title appears in CI text
        title_norm = re.sub(r"[^a-z\s]", "", title.lower()).strip()
        title_words = title_norm.split()[:4]  # first 4 words for matching
        if not title_words:
            continue

        search_phrase = " ".join(title_words)
        if len(title_words) < 3 or len(search_phrase) < 12:
            continue  # too short for reliable matching
        ci_present = search_phrase in ci_combined_text

        rows_out.append({
            "work_id":     work_id,
            "title":       title,
            "author":      author,
            "canonical":   canonical,
            "jstor_count": jstor_count,
            "is_hollow":   1 if is_hollow else 0,
            "is_shadow":   1 if is_shadow else 0,
            "in_ci_text":  1 if ci_present else 0,
            "zone_type": (
                "hollow_in_ci"  if is_hollow and ci_present else
                "hollow_absent" if is_hollow and not ci_present else
                "shadow_in_ci"  if is_shadow and ci_present else
                "shadow_absent"
            ),
        })

    rows_out.sort(key=lambda r: (-r["in_ci_text"], -r["jstor_count"]))
    return rows_out


def write_summary(
    articles: list[dict],
    author_freq: list[dict],
    concept_freq: list[dict],
    intro_patterns: list[dict],
    tension_zones: list[dict],
    output_path: Path,
):
    """Write human-readable summary for dissertation reference."""
    lines = []
    lines.append("=" * 70)
    lines.append("CRITICAL INQUIRY DISCOURSE ANALYSIS — SUMMARY")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 70)

    lines.append(f"\n[CORPUS] {len(articles)} articles processed")
    years = [a.get("year_extracted") or a.get("year_hint") for a in articles]
    years = [y for y in years if y]
    from collections import Counter as C
    year_dist = C(years).most_common()
    lines.append("Year distribution: " + ", ".join(f"{y}:{n}" for y, n in sorted(year_dist)))

    lines.append("\n" + "-" * 60)
    lines.append("TOP 30 MOST-CITED SCHOLARS/CRITICS (by n_articles)")
    lines.append("-" * 60)
    for r in author_freq[:30]:
        flag = " [KEY]" if r["is_key_scholar"] else ""
        lines.append(
            f"  {r['cited_name']:<30}  articles={r['n_articles']:>4}  "
            f"mentions={r['n_total_mentions']:>5}{flag}"
        )

    lines.append("\n" + "-" * 60)
    lines.append("CONCEPT GROUP TOTALS (across all articles)")
    lines.append("-" * 60)
    totals = [r for r in concept_freq if r["filename"] == "__TOTAL__"]
    totals.sort(key=lambda r: -int(r["count"]))
    for r in totals:
        lines.append(f"  {r['concept_group']:<25}  {r['count']:>6}")

    lines.append("\n" + "-" * 60)
    lines.append("ARGUMENTATIVE PATTERNS (aggregate over all articles)")
    lines.append("-" * 60)
    for pname in ARG_PATTERNS:
        col = f"{pname}_count"
        total = sum(int(r.get(col, 0)) for r in intro_patterns)
        lines.append(f"  {pname:<35}  total={total:>5}")
    dom_counts = Counter(r.get("dominant_pattern", "none") for r in intro_patterns)
    lines.append("\nDominant pattern per article:")
    for p, n in dom_counts.most_common():
        lines.append(f"  {p:<35}  n={n}")

    lines.append("\n" + "-" * 60)
    lines.append("STRUCTURAL TENSION ZONES")
    lines.append("-" * 60)
    hollow_in_ci = [r for r in tension_zones if r["zone_type"] == "hollow_in_ci"]
    shadow_in_ci = [r for r in tension_zones if r["zone_type"] == "shadow_in_ci"]
    lines.append(f"\nHollow canon works present in CI text (n={len(hollow_in_ci)}):")
    for r in hollow_in_ci[:10]:
        lines.append(f"  {r['title']:<45} jstor={r['jstor_count']}")
    lines.append(f"\nShadow canon works present in CI text (n={len(shadow_in_ci)}):")
    for r in shadow_in_ci[:10]:
        lines.append(f"  {r['title']:<45} jstor={r['jstor_count']}")

    lines.append("\n" + "=" * 70)
    lines.append("END OF SUMMARY")

    text = "\n".join(lines)
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    logger.info(f"Summary → {output_path}")
    print(text)


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    derived = Path("derived")

    # Load extraction outputs
    articles        = load_tsv(derived / "ci_articles.tsv")
    footnotes       = load_tsv(derived / "ci_footnotes.tsv")
    cited_names     = load_tsv(derived / "ci_cited_names.tsv")
    intro_sentences = load_tsv(derived / "ci_intro_sentences.tsv")

    if not articles:
        logger.error("ci_articles.tsv not found or empty — run ci_extract_citations.py first")
        sys.exit(1)

    logger.info(f"Loaded {len(articles)} articles, {len(cited_names)} cited name rows, "
                f"{len(footnotes)} footnote rows, {len(intro_sentences)} intro sentences")

    # Cross-validation inputs (optional)
    jstor_rows = load_tsv(derived / "jstor_mentions.tsv")
    oa_rows    = load_tsv(derived / "openalex_snapshot_mentions.tsv")
    logger.info(f"JSTOR rows: {len(jstor_rows)}, OA rows: {len(oa_rows)}")

    # ── Analysis 1: Author frequency
    logger.info("Analysing author frequency...")
    author_freq = analyse_author_frequency(cited_names, articles)
    write_tsv(
        author_freq,
        derived / "ci_author_freq.tsv",
        ["cited_name", "n_articles", "n_total_mentions", "is_key_scholar"],
    )

    # ── Analysis 2: Concept frequency
    logger.info("Analysing concept frequency...")
    concept_freq = analyse_concepts(articles)
    write_tsv(
        concept_freq,
        derived / "ci_concept_freq.tsv",
        ["filename", "year", "concept_group", "count"],
    )

    # ── Analysis 3: Intro argumentative patterns
    logger.info("Analysing intro patterns...")
    pattern_fields = ["filename", "year", "n_pages", "n_footnotes", "dominant_pattern"]
    for pname in ARG_PATTERNS:
        pattern_fields += [f"{pname}_count", f"{pname}_example"]
    intro_patterns = analyse_intro_patterns(articles, intro_sentences)
    write_tsv(intro_patterns, derived / "ci_intro_patterns.tsv", pattern_fields)

    # ── Analysis 4: Structural tension zones (cross-validation)
    if jstor_rows:
        logger.info("Analysing structural tension zones...")
        tension_zones = analyse_tension_zones(articles, jstor_rows, oa_rows)
        write_tsv(
            tension_zones,
            derived / "ci_tension_zones.tsv",
            ["work_id", "title", "author", "canonical", "jstor_count",
             "is_hollow", "is_shadow", "in_ci_text", "zone_type"],
        )
    else:
        tension_zones = []
        logger.warning("Skipping tension zone analysis (jstor_mentions.tsv not found)")

    # ── Summary
    write_summary(
        articles, author_freq, concept_freq, intro_patterns, tension_zones,
        derived / "ci_discourse_summary.txt",
    )


if __name__ == "__main__":
    main()