# Conrad Narcissus: bibliographic review worksheet (DRAFT)

Status: **NOT REVIEWED, NOT ADJUDICATED**. Prepared 2026-10-20.
Frozen source snapshot: `OL_EDITIONS_2026-02-28`; no live-API source mixing.

Scope: ten deliberately selected Editions currently linked to `OL38815W`,
under held unit `E000019634`. This is exploratory selection, **not** a random
sample. A second Work ID, `OL44245458W`, is recorded separately to retain
work-identity context. Neither historical ONE_WORK nor Project W is modified.

The Edition worksheet contains source-derived **excerpts**. To inspect the
complete contents, notes, and other raw fields, consult the immutable
`raw_edition_enrichment_v2.tsv` by `edition_key`. `source_records_json` preserves
source-record pointers, **not** proof of cataloguing accuracy.

Researcher judgment cells are intentionally blank. Fill them only after
checking suitable evidence for each Edition (catalogue, digitized copy,
contents, or authoritative original record). Recommended controlled values:

- `researcher_target_presence`: `PRESENT_CONFIRMED`, `ABSENT_CONFIRMED`,
  `UNDETERMINED`.
- `researcher_publication_scope`: `SINGLE_WORK`, `COLLECTION_OR_JOINT_VOLUME`,
  `CRITICAL_OR_ANNOTATED`, `AUTHOR_PARATEXT`, `OTHER`, `UNDETERMINED`.
- `researcher_physical_relationship`: `PUBLISHER_JOINT_VOLUME`,
  `COPY_SPECIFIC_BOUND_WITH`, `SEPARATE_VOLUMES_IN_CASE`, `NOT_APPLICABLE`,
  `UNDETERMINED`.
- `researcher_edition_work_linkage`: `SUPPORTED`, `QUESTIONABLE`,
  `UNSUPPORTED`, `UNDETERMINED`.

These axes are not interchangeable: a collection may include the target
novel, a copy-specific `Bound with` note does not establish edition-wide
publication scope, and a lack of title mention is not proof of absence.

`machine_observation_cues_json` lists **descriptive hints only**. Example:
`TOC_EXPLICIT_TARGET_TITLE_MENTION` means the original OL metadata explicitly
mentions the target in a contents field; it is not a researcher-confirmed
full-text inspection. `TOC_CHARACTER_SPLIT_SUSPECT` flags the observed
letter-by-letter contents metadata anomaly. `NO_DEFINED_CUE_NOT_ABSENCE`
does NOT mean the target novel is absent.

`work_identity_context_v1.tsv` is deliberately separate: it does not decide
whether the two OL Work IDs represent one conceptual literary work. Edition
review must not silently overwrite or re-interpret frozen held-out labels.

Methodological note: This exploration follows exposure to earlier held-out
and development cases. Do **not** use it as independent evaluation of screen
accuracy or an estimate of overall OL Edition linkage-error prevalence.

Do not edit this generated draft in-place after it is frozen; make a new
researcher-annotated copy with provenance/versioning for actual decisions.
