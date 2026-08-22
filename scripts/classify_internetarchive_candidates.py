import os
import json
import time
from pathlib import Path

import pandas as pd
from openai import OpenAI

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")

SRC = Path("audit/internetarchive_llm_test_30.tsv")
OUT = Path("audit/internetarchive_llm_test_30_classified.tsv")

client = OpenAI()

LABELS = [
    "primary_text",
    "scholarly_metatext",
    "pedagogical_metatext",
    "reference_metatext",
    "adaptation_derivative",
    "unrelated",
    "unclear",
]

SUBTYPES = [
    "standalone",
    "collected_or_combined",
    "critical_or_annotated",
    "monograph_or_criticism",
    "essay_collection",
    "study_or_teaching_guide",
    "reference_or_bibliography",
    "adaptation_or_rewriting",
    "other",
    "unclear",
]

SYSTEM_PROMPT = """
You classify Internet Archive text records in relation to a specific
literary work.

The purpose is NOT merely to decide whether a search result is relevant.
We want to distinguish the circulation/preservation of the literary text
itself from books and other texts produced ABOUT that literary work.

Assign exactly one primary label:

primary_text
    The item contains the target literary work itself as a substantial
    primary text. This includes standalone editions, collected editions,
    anthologies containing the work, critical editions, annotated editions,
    and volumes combining the target with other works.

scholarly_metatext
    A scholarly or critical work substantially ABOUT the target literary
    work, such as a scholarly monograph, literary criticism, or academic
    essay collection. It does not substantially reproduce the target work
    itself.

pedagogical_metatext
    A study guide, teaching guide, classroom aid, student guide, or similar
    pedagogical resource ABOUT the target work, where the target literary
    text itself is not the main content.

reference_metatext
    A bibliography, encyclopedia, catalog, reference work, or similar
    resource that records or discusses the target work but is neither
    primarily scholarship about it nor the literary text itself.

adaptation_derivative
    An adaptation, rewriting, screenplay, dramatization, comic adaptation,
    derivative work, or other transformed version rather than an edition
    containing the original literary text.

unrelated
    The item is not meaningfully about or containing the target literary
    work. This includes same-title works and search noise.

unclear
    The supplied metadata is insufficient to classify reliably.

Important rules:

1. A volume containing the COMPLETE or substantial target literary text
   remains primary_text even when it also contains an introduction,
   annotations, scholarly essays, or critical apparatus.

2. A critical edition such as a Norton Critical Edition should normally
   be primary_text with subtype critical_or_annotated if it contains the
   literary work itself.

3. A collection containing the target work together with other literary
   works should be primary_text with subtype collected_or_combined.

4. Do not classify a book as scholarly_metatext merely because its title
   contains the target title. It must actually be criticism/research ABOUT
   the target work.

5. Adaptations and retellings are not primary_text unless the metadata
   indicates that the original literary text is also substantially present.

Also independently determine:

contains_primary_text:
    yes / no / unclear

is_about_target_work:
    yes / no / unclear

"About" here means that discussion, criticism, teaching, reference,
adaptation, or other treatment of the target work is a substantial purpose
of the item. A straightforward edition containing only the literary text
does NOT need to be marked "about" the work.

Return JSON only, with:

{
  "label": "...",
  "subtype": "...",
  "contains_primary_text": "yes|no|unclear",
  "is_about_target_work": "yes|no|unclear",
  "confidence": "high|medium|low",
  "note": "brief explanation grounded only in the supplied metadata"
}
"""


def clean(v):
    if pd.isna(v):
        return ""
    return str(v)


def classify(row):

    metadata = {
        "target_title": clean(row.get("selection_title")),
        "target_author": clean(row.get("selection_author")),
        "internet_archive_identifier": clean(row.get("ia_identifier")),
        "item_title": clean(row.get("ia_title")),
        "item_creator": clean(row.get("ia_creator")),
        "item_date": clean(row.get("ia_date")),
        "item_publisher": clean(row.get("ia_publisher")),
        "item_subject": clean(row.get("ia_subject")),
        "item_description": clean(row.get("ia_description")),
        "item_collection": clean(row.get("ia_collection")),
    }

    prompt = (
        "Classify this Internet Archive record.\n\n"
        + json.dumps(metadata, ensure_ascii=False, indent=2)
    )

    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=prompt,
    )

    text = response.output_text.strip()

    # tolerate fenced JSON if the model happens to return it
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()

    result = json.loads(text)

    label = result.get("label", "unclear")
    subtype = result.get("subtype", "unclear")
    contains = result.get("contains_primary_text", "unclear")
    about = result.get("is_about_target_work", "unclear")
    confidence = result.get("confidence", "low")
    note = result.get("note", "")

    if label not in LABELS:
        label = "unclear"

    if subtype not in SUBTYPES:
        subtype = "unclear"

    if contains not in {"yes", "no", "unclear"}:
        contains = "unclear"

    if about not in {"yes", "no", "unclear"}:
        about = "unclear"

    if confidence not in {"high", "medium", "low"}:
        confidence = "low"

    return {
        "llm_label": label,
        "llm_subtype": subtype,
        "contains_primary_text": contains,
        "is_about_target_work": about,
        "llm_confidence": confidence,
        "llm_note": note,
    }


df = pd.read_csv(SRC, sep="\t")

results = []

for i, (_, row) in enumerate(df.iterrows(), start=1):

    title = row["selection_title"]
    ia_title = row["ia_title"]

    print(f"[{i}/{len(df)}] {title} -> {ia_title}")

    result = None

    for attempt in range(3):

        try:
            result = classify(row)
            break

        except Exception as e:
            print(
                f"  attempt {attempt + 1} failed:",
                repr(e)
            )

            if attempt < 2:
                time.sleep(3 * (attempt + 1))

    if result is None:
        result = {
            "llm_label": "unclear",
            "llm_subtype": "unclear",
            "contains_primary_text": "unclear",
            "is_about_target_work": "unclear",
            "llm_confidence": "low",
            "llm_note": "API/classification failure",
        }

    results.append(result)

    print(
        "   ",
        result["llm_label"],
        "/",
        result["llm_subtype"],
        "/ primary=",
        result["contains_primary_text"],
        "/ about=",
        result["is_about_target_work"],
        "/",
        result["llm_confidence"],
    )

    time.sleep(0.3)


res = pd.DataFrame(results)

# overwrite the blank placeholder columns
for c in res.columns:
    df[c] = res[c]

OUT.parent.mkdir(exist_ok=True)
df.to_csv(OUT, sep="\t", index=False)

print("\nCreated:", OUT)
print("Rows:", len(df))

print("\nLABELS:")
print(df["llm_label"].value_counts(dropna=False))

print("\nSUBTYPES:")
print(df["llm_subtype"].value_counts(dropna=False))

print("\nCONTAINS PRIMARY TEXT:")
print(df["contains_primary_text"].value_counts(dropna=False))

print("\nABOUT TARGET WORK:")
print(df["is_about_target_work"].value_counts(dropna=False))

print("\nCONFIDENCE:")
print(df["llm_confidence"].value_counts(dropna=False))

print("\nRESULTS:")
print(
    df[
        [
            "selection_title",
            "ia_title",
            "llm_label",
            "llm_subtype",
            "contains_primary_text",
            "is_about_target_work",
            "llm_confidence",
            "llm_note",
        ]
    ].to_string(index=False)
)

print("\nIA LLM CLASSIFICATION TEST OK")
