#!/usr/bin/env python3
"""
ci_extract_citations.py — Stage 7, Step 1
Critical Inquiry PDF extraction: text, citations, footnotes, metadata.

Usage:
    python3 scripts/ci_extract_citations.py \
        --input "/mnt/c/Users/tsuts/Desktop/色々使えるデータ/Critical Inquiry/2019-2025/" \
        --output_dir derived/

Outputs:
    derived/ci_articles.tsv        — one row per article (metadata + intro text)
    derived/ci_footnotes.tsv       — one row per footnote
    derived/ci_cited_names.tsv     — cited author names extracted from footnotes
    derived/ci_intro_sentences.tsv — sentence-level intro text (first 2 pages)

Runtime: ~10–30 min for 254 PDFs depending on page count.
"""

import argparse
import csv
import logging
import os
import re
import sys
from pathlib import Path
from datetime import datetime

import pdfplumber

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
log_path = Path("logs") / f"ci_extract_{datetime.now().strftime('%Y-%m-%d')}.log"
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
# Regex patterns
# ─────────────────────────────────────────────

# CI footnote marker: superscript digit(s) at start of line, or inline
RE_FOOTNOTE_START = re.compile(r"^\s*(\d{1,3})[.\s]\s+(.+)", re.MULTILINE)

# Author-Year citation patterns (humanities footnote styles)
# e.g. "Said, Orientalism", "Butler (1990)", "Foucault, Discipline and Punish"
RE_AUTHOR_YEAR = re.compile(
    r"\b([A-Z][a-zéèêëàâùûîïôœæ'\-]+(?:\s+[A-Z][a-zéèêëàâùûîïôœæ'\-]+)?)"
    r"(?:,?\s*(?:ed\.|trans\.)?)?"
    r"(?:\s*\((\d{4}[a-z]?)\)|\s*\[(\d{4})\])",
    re.UNICODE
)

# Standalone surname in footnote context (broader catch)
# "See Jameson,", "cf. Derrida,"
RE_SEE_CF = re.compile(
    r"\b(?:see|cf\.?|see also|following|in|after|with|per|quoted in)\s+"
    r"([A-Z][a-zéèêëàâùûîïôœæ'\-]+(?:\s+[A-Z][a-zéèêëàâùûîïôœæ'\-]+)?)",
    re.IGNORECASE | re.UNICODE
)

# Argumentative intro markers
RE_HOWEVER   = re.compile(r"\bhowever\b", re.IGNORECASE)
RE_AGAINST   = re.compile(r"\b(?:against|in contrast to|contrary to|counters?)\b", re.IGNORECASE)
RE_FOLLOWING = re.compile(r"\b(?:following|building on|extending|drawing on|after)\b", re.IGNORECASE)
RE_ARGUES    = re.compile(r"\b\w+\s+(?:argues?|claims?|contends?|suggests?|insists?|asserts?)\b", re.IGNORECASE)

# Volume/Issue from CI filename or first page
# CI filenames: "CI_46_4_2020_ArticleTitle.pdf" or similar
RE_FILENAME_VOL = re.compile(r"[Cc][Ii][\s_\-]?(\d+)[\s_\-](\d)[\s_\-]?(\d{4})", re.IGNORECASE)

# Year from anywhere
RE_YEAR = re.compile(r"\b(201[9]|202[0-5])\b")

# Page header / running head (to skip)
RE_HEADER_SKIP = re.compile(
    r"^Critical Inquiry|^C\s*R\s*I\s*T\s*I|^\d+\s*$|^©\s*\d{4}",
    re.IGNORECASE
)


# ─────────────────────────────────────────────
# Utility functions
# ─────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Remove soft hyphens, ligatures, normalize whitespace."""
    if not text:
        return ""
    text = text.replace("\xad", "")        # soft hyphen
    text = text.replace("\ufb01", "fi")    # fi ligature
    text = text.replace("\ufb02", "fl")    # fl ligature
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_filename_meta(filepath: Path) -> dict:
    """Extract volume/year hints from filename."""
    name = filepath.stem
    m = RE_FILENAME_VOL.search(name)
    if m:
        return {"vol": m.group(1), "issue": m.group(2), "year_hint": m.group(3)}
    # Try year alone
    m2 = RE_YEAR.search(name)
    return {"vol": None, "issue": None, "year_hint": m2.group(1) if m2 else None}


def extract_footnotes_from_page(page) -> list[dict]:
    """
    Extract footnotes from a pdfplumber page.

    Strategy:
      1. Use pdfplumber word-level y-position to find footnote zone
         (bottom 20-25% of page).
      2. Extract text from that zone.
      3. Split on digit markers.
    """
    footnotes = []
    page_height = page.height
    footnote_threshold = page_height * 0.75  # bottom 25%

    # Crop to footnote zone
    try:
        footnote_area = page.crop((0, footnote_threshold, page.width, page_height))
        fn_text = footnote_area.extract_text() or ""
    except Exception:
        fn_text = ""

    if not fn_text.strip():
        return footnotes

    fn_text = clean_text(fn_text)

    # Split on numbered markers: "1. " or "1 " at start of chunks
    chunks = re.split(r"(?<!\d)(\d{1,3})[.\s]\s+", fn_text)
    # chunks: [pre, num1, text1, num2, text2, ...]
    i = 1
    while i < len(chunks) - 1:
        num = chunks[i].strip()
        text = chunks[i + 1].strip() if i + 1 < len(chunks) else ""
        if num.isdigit() and text:
            footnotes.append({"fn_num": int(num), "fn_text": text[:1000]})
        i += 2

    return footnotes


def extract_article_intro(pdf, n_intro_pages: int = 3) -> str:
    """
    Extract intro text from first n pages, skipping running headers.
    Returns cleaned string.
    """
    intro_parts = []
    for i, page in enumerate(pdf.pages[:n_intro_pages]):
        text = page.extract_text() or ""
        lines = [clean_text(l) for l in text.split("\n")]
        lines = [l for l in lines if l and not RE_HEADER_SKIP.match(l)]
        intro_parts.extend(lines)
    return " ".join(intro_parts)


def extract_cited_names_from_text(text: str) -> list[str]:
    """Extract author surnames from footnote text using multiple patterns."""
    names = set()

    # Author (Year) pattern
    for m in RE_AUTHOR_YEAR.finditer(text):
        names.add(m.group(1).strip())

    # See / cf. patterns
    for m in RE_SEE_CF.finditer(text):
        names.add(m.group(1).strip())

    # Filter out common false positives
    stopwords = {
        "The", "This", "In", "On", "For", "University", "Press",
        "Cambridge", "Oxford", "Chicago", "New", "York", "London",
        "Ibid", "See", "Cf", "Also", "Trans", "Ed", "Vol", "No",
        "pp", "Pp", "Ibid"
    }
    names = {n for n in names if n.lower() not in stopwords and len(n) > 2}
    return sorted(names)


def parse_article_header(pdf) -> dict:
    """
    Extract article title, author, year, volume from first page.
    CI layout: title prominent, author below, journal info in header/footer.
    """
    if not pdf.pages:
        return {}

    first_page = pdf.pages[0]
    words = first_page.extract_words(extra_attrs=["size"]) or []

    # Largest font text → likely title
    if words:
        max_size = max(w.get("size", 0) for w in words)
        title_words = [w["text"] for w in words if w.get("size", 0) >= max_size * 0.85]
        title_candidate = clean_text(" ".join(title_words))
    else:
        title_candidate = ""

    # Extract full text of page 1 for year
    page1_text = clean_text(first_page.extract_text() or "")
    year_m = RE_YEAR.search(page1_text)
    year = year_m.group(1) if year_m else None

    return {
        "title_extracted": title_candidate[:200],
        "year_extracted": year,
        "page1_text_sample": page1_text[:500],
    }


# ─────────────────────────────────────────────
# Main extraction
# ─────────────────────────────────────────────

def process_pdf(pdf_path: Path) -> dict:
    """Process a single PDF and return structured result."""
    result = {
        "filename": pdf_path.name,
        "filepath": str(pdf_path),
        "n_pages": 0,
        "title_extracted": "",
        "year_extracted": None,
        "year_hint": None,
        "vol": None,
        "issue": None,
        "intro_text": "",
        "n_footnotes": 0,
        "all_cited_names": "",
        "intro_however_count": 0,
        "intro_against_count": 0,
        "intro_following_count": 0,
        "intro_argues_count": 0,
        "footnotes": [],
        "error": None,
    }

    # Filename metadata
    fn_meta = parse_filename_meta(pdf_path)
    result.update(fn_meta)

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            result["n_pages"] = len(pdf.pages)

            # Article header
            header = parse_article_header(pdf)
            result.update(header)

            # Intro text (pages 1–3)
            intro_text = extract_article_intro(pdf, n_intro_pages=3)
            result["intro_text"] = intro_text[:3000]

            # Intro marker counts
            result["intro_however_count"]  = len(RE_HOWEVER.findall(intro_text))
            result["intro_against_count"]  = len(RE_AGAINST.findall(intro_text))
            result["intro_following_count"] = len(RE_FOLLOWING.findall(intro_text))
            result["intro_argues_count"]   = len(RE_ARGUES.findall(intro_text))

            # Footnote extraction (all pages)
            all_footnotes = []
            for page in pdf.pages:
                fns = extract_footnotes_from_page(page)
                for fn in fns:
                    fn["page_num"] = page.page_number
                    fn["filename"] = pdf_path.name
                    all_footnotes.append(fn)

            result["n_footnotes"] = len(all_footnotes)
            result["footnotes"] = all_footnotes

            # Cited names from ALL footnote text
            all_fn_text = " ".join(fn["fn_text"] for fn in all_footnotes)
            cited_names = extract_cited_names_from_text(all_fn_text)
            result["all_cited_names"] = "|".join(cited_names)

    except Exception as e:
        result["error"] = str(e)
        logger.warning(f"Error processing {pdf_path.name}: {e}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Extract CI article data from PDFs")
    parser.add_argument("--input", required=True, help="Directory containing CI PDFs")
    parser.add_argument("--output_dir", default="derived", help="Output directory")
    args = parser.parse_args()

    input_dir  = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        logger.error(f"No PDFs found in {input_dir}")
        sys.exit(1)

    logger.info(f"Found {len(pdf_files)} PDFs in {input_dir}")

    # Output writers
    articles_path   = output_dir / "ci_articles.tsv"
    footnotes_path  = output_dir / "ci_footnotes.tsv"
    cited_path      = output_dir / "ci_cited_names.tsv"
    intro_sent_path = output_dir / "ci_intro_sentences.tsv"

    article_fields = [
        "filename", "n_pages", "title_extracted", "year_extracted", "year_hint",
        "vol", "issue", "n_footnotes", "all_cited_names",
        "intro_however_count", "intro_against_count",
        "intro_following_count", "intro_argues_count",
        "intro_text", "error",
    ]
    footnote_fields = ["filename", "page_num", "fn_num", "fn_text"]
    cited_fields    = ["filename", "cited_name"]
    intro_fields    = ["filename", "sent_idx", "sentence"]

    with (
        open(articles_path,   "w", newline="", encoding="utf-8") as fa,
        open(footnotes_path,  "w", newline="", encoding="utf-8") as ff,
        open(cited_path,      "w", newline="", encoding="utf-8") as fc,
        open(intro_sent_path, "w", newline="", encoding="utf-8") as fi,
    ):
        w_art  = csv.DictWriter(fa, fieldnames=article_fields,  delimiter="\t", extrasaction="ignore")
        w_fn   = csv.DictWriter(ff, fieldnames=footnote_fields, delimiter="\t", extrasaction="ignore")
        w_cit  = csv.DictWriter(fc, fieldnames=cited_fields,    delimiter="\t", extrasaction="ignore")
        w_sent = csv.DictWriter(fi, fieldnames=intro_fields,    delimiter="\t", extrasaction="ignore")

        for w in [w_art, w_fn, w_cit, w_sent]:
            w.writeheader()

        n_ok, n_err = 0, 0
        for idx, pdf_path in enumerate(pdf_files, 1):
            logger.info(f"[{idx}/{len(pdf_files)}] {pdf_path.name}")
            result = process_pdf(pdf_path)

            # Articles row
            w_art.writerow(result)

            # Footnotes rows
            for fn in result.get("footnotes", []):
                w_fn.writerow(fn)

            # Cited names rows
            for name in result["all_cited_names"].split("|"):
                if name.strip():
                    w_cit.writerow({"filename": result["filename"], "cited_name": name.strip()})

            # Intro sentences
            sentences = re.split(r"(?<=[.!?])\s+", result["intro_text"])
            for s_idx, sent in enumerate(sentences[:50]):  # cap at 50 sentences
                if len(sent.strip()) > 20:
                    w_sent.writerow({
                        "filename": result["filename"],
                        "sent_idx": s_idx,
                        "sentence": sent.strip()[:500],
                    })

            if result["error"]:
                n_err += 1
            else:
                n_ok += 1

    logger.info(f"Done: {n_ok} OK, {n_err} errors")
    logger.info(f"Articles → {articles_path}")
    logger.info(f"Footnotes → {footnotes_path}")
    logger.info(f"Cited names → {cited_path}")
    logger.info(f"Intro sentences → {intro_sent_path}")


if __name__ == "__main__":
    main()