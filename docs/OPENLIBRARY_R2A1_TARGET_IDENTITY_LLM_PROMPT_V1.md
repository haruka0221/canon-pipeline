# Open Library R2+A1 target identity adjudication — LLM protocol v1

## Purpose

Evaluate the bibliographic identity and corpus-scope semantics of one
Open Library Work record using only the supplied frozen/current metadata.

This is NOT an OpenAlex relevance judgment.

Do not decide whether an OpenAlex scholarly record refers to the target.
Do not use candidate counts, retrieval risk, or visibility magnitude.

The supplied Open Library metadata may contain imperfect Work clustering.
Your task is to distinguish:

1. whether the Work record represents a coherent intellectual/bibliographic
   entity; and
2. what kind of literary/bibliographic entity that is for a fiction corpus.

Use only the supplied evidence. Do not browse the web. Do not treat general
background knowledge as stronger evidence than the supplied metadata.

---

## Axis 1: entity status

Choose exactly one.

### COHERENT_SINGLE_WORK

The editions plausibly represent manifestations, translations, reprints,
or title variants of one specific intellectual work.

A work can have many editions, publishers, or minor title variants and
still be coherent.

### COHERENT_COLLECTION

The editions plausibly represent one identifiable collection, anthology,
selected-works volume, collected edition, or other coherent multi-text work.

The entity may contain multiple stories, poems, essays, or other component
texts, but the evidence supports treating the collection itself as a stable
bibliographic/intellectual work.

### HETEROGENEOUS_CLUSTER

The Open Library Work appears to combine materially different intellectual
works or substantially different collections that should not normally be
treated as manifestations of one Work.

Examples include edition titles that clearly identify unrelated works or
different collections under one Work record.

Do not choose this merely because editions have minor title variations,
different publishers, translations, or reprint dates.

### NONWORK_OR_HEADING_ARTIFACT

The record appears not to identify a stable work or stable collection at all.
It behaves primarily like an author/person heading, generic cataloguing
container, or metadata artifact.

Use this conservatively. An eponymous title such as an author's name is not
automatically an artifact if the editions plausibly represent a real,
coherent publication or collection.

### UNCERTAIN

The supplied metadata is insufficient or genuinely conflicting.

---

## Axis 2: corpus content type

Choose exactly one.

### SPECIFIC_FICTION_WORK

The entity is a specific work of fiction: for example a novel, novella,
single fictional narrative, or another clearly bounded fictional work.

### FICTION_COLLECTION_OR_ANTHOLOGY

The entity is a collection or anthology whose primary contents are fiction,
such as a short-story collection or a coherent collection of fictional works.

### BROAD_AUTHOR_OEUVRE_OR_MIXED_COLLECTION

The entity represents selected works, collected works, a broad author
anthology, portable-author volume, or another collection spanning multiple
works and/or genres rather than one specific fiction work or bounded fiction
collection.

### NONFICTION_OR_OTHER_LITERARY_FORM

The entity is primarily biography, autobiography, criticism, letters,
journals, essays, poetry, drama, historical/medical/religious writing,
reference material, or another non-fiction/non-fiction-corpus form.

### MIXED_OR_UNCLEAR

The supplied evidence does not establish a stable content type, or the
record mixes categories so substantially that no category above is adequate.

---

## Axis 3: date-window assessment

The dissertation corpus targets works whose original intellectual work
belongs to 1880–1950.

Choose exactly one.

### LIKELY_ORIGINAL_1880_1950

The supplied evidence supports an original intellectual-work date within
1880–1950.

### LIKELY_ORIGINAL_OUTSIDE_1880_1950

The supplied evidence supports that the underlying intellectual work or
contents originate outside 1880–1950. Later reprints or editions do not by
themselves make an older work an 1880–1950 work.

### INSUFFICIENT_DATE_EVIDENCE

Edition publication dates, the Open Library first-publish field, or other
supplied metadata do not reliably establish the original intellectual-work
date.

Do not infer an original date merely because an edition was published
between 1880 and 1950.

---

## Evidence discipline

Pay particular attention to:

- current Open Library Work title;
- frozen target title and first-publish metadata;
- Work description and subjects;
- edition titles and subtitles;
- whether edition titles are mutually compatible;
- edition publication dates;
- publishers.

An Open Library `first_publish_year` or `first_publish_date` is evidence,
but it may describe the current Work cluster rather than the true first
publication of its intellectual contents. Treat it cautiously.

The number of editions is not evidence by itself that the Work is valid
or invalid.

---

## Confidence

HIGH:
The supplied metadata strongly supports the classification.

MEDIUM:
The classification is more likely than alternatives, but some ambiguity
remains.

LOW:
A classification is required but evidence is weak. Prefer UNCERTAIN /
MIXED_OR_UNCLEAR / INSUFFICIENT_DATE_EVIDENCE where appropriate rather
than forcing a strong conclusion.

---

## Notes

Give a concise evidence-based explanation. Mention the decisive edition-title,
description, subject, or date evidence. Do not discuss OpenAlex retrieval
volume or downstream policy.
