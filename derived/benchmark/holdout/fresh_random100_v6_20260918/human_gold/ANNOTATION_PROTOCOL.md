# Wikidata v6 Fresh Holdout Human-Gold Annotation Protocol

## Status

This protocol and the completed human gold were frozen before inspecting or
running any v6 predictions on the fresh holdout.

## 1. Entity-resolution gold

The target is the underlying conceptual literary work represented by the
Open Library record.

Allowed labels:

- MATCH: a Wikidata item can be identified as the same conceptual work.
- NO_MATCH: no appropriate Wikidata work item can be verified.
- AMBIGUOUS: available evidence does not support a unique work-level decision.

The gold QID may be outside the supplied candidate set. Candidate retrieval
recall is evaluated separately from judgment accuracy.

## 2. Editions, translations, and derivative works

- Different editions of the same work are treated as the same conceptual work.
- Ordinary translations are treated as the same conceptual work as the source
  work.
- A Wikidata edition/translation item is not preferred when an underlying
  abstract work item can be identified.
- Explicit adaptations, abridgements, retellings, or works "based on" another
  work are not automatically treated as identical to the source work.
- Editorial or responsibility wording such as "edited by", "translated by",
  or "adapted and edited by" does not by itself establish a distinct
  conceptual work.
- Work-title fields and related-title evidence are supportive but not decisive
  on their own.

## 3. Population eligibility

Entity identity and population eligibility are annotated independently.

Primary evaluation uses records marked INCLUDE.

### INCLUDE

The target represents a coherent novel or novel-like book-length fiction work
whose underlying conceptual work belongs to the intended 1880-1950 population.

Juvenile fiction is not excluded merely because it is written for children.
Novellas and other short book-length fictional narratives are not excluded
solely on length.

### EXCLUDE_OUT_OF_SCOPE

Used only when independent bibliographic evidence shows that the sampled record
does not belong to the intended novel population, including:

- underlying conceptual work first published outside 1880-1950;
- poetry or poetry collections;
- plays;
- short-story collections or anthologies;
- nonfiction, scholarship, manuals, bibliographies, memoirs, biographies, or
  comparable non-novel works;
- clearly corrupted metadata pointing to an out-of-scope underlying work.

Excluded records remain in the frozen 100-record sample and are not replaced
or resampled.

## 4. Dates

The date of the underlying conceptual work is distinguished from dates of
later editions or translations.

A later edition or translation dated 1880-1950 does not make an older
conceptual work eligible.

## 5. Live Wikidata research

Live Wikidata and external bibliographic sources may be used for human-gold
research only.

Live Wikidata is not used to generate v6 predictions or candidates.

If a correct QID exists outside the frozen candidate set, this is recorded as
a candidate-retrieval miss rather than changing the identity gold.

## 6. Confidence

- HIGH: identity/genre/date is supported by clear bibliographic or Wikidata
  evidence.
- MEDIUM: the preferred decision is supported but a meaningful bibliographic
  or genre boundary remains.
- LOW: evidence is insufficient; such cases should normally be considered for
  AMBIGUOUS rather than forced.

## 7. Evaluation reporting

Final reporting should distinguish:

1. primary entity-resolution results on INCLUDE records;
2. sensitivity results on all 100 sampled records;
3. candidate-retrieval recall separately from judgment accuracy;
4. number and reasons for population exclusions.
