Created: 2026-02-22
Population file: ol_works_final_population.tsv
Total works: 4833

[Definition]
This population consists of fiction works first published between 1880 and 1950,
retrieved via the Open Library Search API. Works published in English are included,
encompassing both originally English-language works and translations into English.

[Exclusion Rules]
Works were excluded if their subject_keys contained any of the following terms:
  plays, dramatic_works, scripts, poetry, poems, ballads, stories_in_rhyme,
  nonsense_verses, verse, picture_books, literary_criticism, nonfiction,
  biography__autobiography
AND did not contain any of the following strong fiction indicators:
  novel, novels, short_stories, literary_fiction, fiction_general,
  english_fiction, american_fiction

[Known Limitations]
- first_publish_year may be incorrectly recorded in Open Library for some works.
  In a post-filter audit of 200 random samples, 5 works (2.5%) had incorrect
  first_publish_year values placing them outside the 1880-1950 range.
- Non-fiction contamination after filtering is estimated at approximately 1%
  (2 out of 200 audited works were non-fiction despite passing the filter).
- Overall post-filter issue rate: 3.5% (7/200), primarily due to
  first_publish_year errors rather than genre misclassification.
