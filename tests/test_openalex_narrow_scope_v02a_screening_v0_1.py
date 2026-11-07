"""No-network, no-data-mutation regression tests for v0.2a source triage."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[1] / "scripts" /
          "build_openalex_narrow_scope_v02a_screening_v0_1.py")
spec = importlib.util.spec_from_file_location("scope_screen_v02a", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def source(w, *, ol=None, year=None, wd_year=None, langs=None, subjects=None, title="A Novel"):
    return {
        "project_work_id": w,
        "current_ol_work_ids_json": json.dumps(ol if ol is not None else ["OL1W"]),
        "historical_titles_json": json.dumps([title]),
        "historical_authors_json": json.dumps(["A. Writer"]),
        "historical_edition_derived_min_years_json": json.dumps(year if year is not None else [1910]),
        "historical_subject_keys_json": json.dumps(subjects if subjects is not None else ["fiction"]),
        "wikidata_qid": "Q123",
        "wd_p577_parsed_positive_years_json": json.dumps(wd_year if wd_year is not None else []),
        "wd_p407_values_json": json.dumps(langs if langs is not None else []),
        "bibliographic_source_combination": "HISTORICAL_OL_AND_WIKIDATA",
    }


def reviewer(n, w, assessment, target="OL1W", novel_only="NOT_ASSESSED"):
    return {
        "random_rank": str(n), "project_work_id":w,
        "source_ol_work_id":target,
        "researcher_accepted_assessment_v02":assessment,
        "novel_novella_only_assessment": novel_only,
        "reviewer_acceptance_status": "RESEARCHER_ACCEPTED_BATCH_PROVISIONAL",
        "release_status": "HOLD_NOT_RELEASED",
        "source_claims_independently_human_verified": "NOT_ALL_SOURCE_CLAIMS_VERIFIED",
        "unresolved_or_qc_notes": "Remaining checks" if assessment == "UNRESOLVED" else "",
    }


class TriageTest(unittest.TestCase):
    def test_single_fiction_source_only_candidate_not_eligibility(self):
        r = module.source_triage(source("W1"))
        self.assertEqual(r["triage_route_not_scope"], "ELIGIBLE_CANDIDATE")
        self.assertEqual(r["auto_analysis_scope_decision"], "NONE_NOT_ADJUDICATED")
        self.assertEqual(r["release_status"], "NOT_RELEASED")
        self.assertEqual(r["original_language_independently_verified"], "")

    def test_translation_clue_does_not_assert_not_english_original(self):
        r = module.source_triage(source("W1", langs=["Q188"], year=[1930]))
        self.assertEqual(r["triage_route_not_scope"], "FORM_OR_IDENTITY_UNRESOLVED")
        self.assertIn("WD_P407_NO_ENGLISH_STATEMENT_NOT_ORIGINAL_LANGUAGE", r["review_reasons_json"])
        self.assertEqual(r["auto_analysis_scope_decision"], "NONE_NOT_ADJUDICATED")

    def test_out_of_period_source_not_historical_origin(self):
        r = module.source_triage(source("W1", year=[1957], subjects=["fiction"]))
        self.assertEqual(r["triage_route_not_scope"], "POSSIBLE_EXCLUSION_FOR_REVIEW")
        self.assertEqual(r["period_signal_source_only"], "ONLY_OUT_OF_PERIOD_SOURCE_DATES_NOT_ORIGINAL_YEAR")
        self.assertEqual(r["release_status"], "NOT_RELEASED")

    def test_conflicting_dates_take_precedence_over_possible_fiction(self):
        r = module.source_triage(source("W1", year=[1910], wd_year=[1850]))
        self.assertEqual(r["triage_route_not_scope"], "FORM_OR_IDENTITY_UNRESOLVED")
        self.assertIn("CONFLICTING_SOURCE_YEAR_PERIODS", r["review_reasons_json"])

    def test_collection_title_is_not_automatically_validated(self):
        r = module.source_triage(source("W1", title="Ten and Other Stories", subjects=[]))
        self.assertEqual(r["triage_route_not_scope"], "ELIGIBLE_CANDIDATE")
        self.assertEqual(r["collection_title_cue"], "True")
        self.assertEqual(r["form_independently_verified"], "")

    def test_nonfiction_mixed_positive_cues_not_auto_out(self):
        r = module.source_triage(source("W1", subjects=["fiction", "literary_criticism"]))
        self.assertEqual(r["triage_route_not_scope"], "POSSIBLE_EXCLUSION_FOR_REVIEW")
        self.assertEqual(r["auto_analysis_scope_decision"], "NONE_NOT_ADJUDICATED")

    def test_multi_ol_identity_review_and_mismatch_flag(self):
        data = [source("W1", ol=["OL1W", "OL2W"]), source("W2")]
        review = [reviewer(1,"W1","IN_SCOPE",target="OL3W"),reviewer(2,"W2","UNRESOLVED")]
        full, risk, audit, diagnostic, summ = module.build(data, review, expected_active=2, expected_random=2)
        self.assertEqual(full[0]["triage_route_not_scope"], "FORM_OR_IDENTITY_UNRESOLVED")
        self.assertEqual(full[0]["random80_openlibrary_source_target_mismatch_flag"], "True")
        self.assertEqual(full[0]["random80_researcher_accepted_provisional_assessment"], "IN_SCOPE")
        self.assertEqual(summ["automatic_in_scope"], 0)
        self.assertFalse(summ["membership_released"])
        self.assertEqual(len(audit), 2)
        self.assertEqual(len(risk), 1)
        self.assertEqual(len(diagnostic), 0)

    def test_sample_review_not_auto_distributed_to_remaining(self):
        full, _, sample, diagnostic, summary = module.build(
            [source("W1"), source("W2"), source("W3")],
            [reviewer(1,"W1","OUT_OF_SCOPE")], expected_active=3, expected_random=1)
        self.assertEqual(summary["active_project_w"], 3)
        self.assertEqual(len(sample), 1)
        self.assertTrue({r["project_work_id"] for r in diagnostic}.isdisjoint({"W1"}))
        self.assertEqual(sum(r["random80_review_provenance"] == "NOT_IN_FROZEN_RANDOM80" for r in full), 2)
        self.assertTrue(all(r["auto_analysis_scope_decision"] == "NONE_NOT_ADJUDICATED" for r in full))

    def test_duplicate_and_nonmatched_W_raise(self):
        with self.assertRaisesRegex(ValueError, "unknown W"):
            module.build([source("W1")],[reviewer(1,"W2","IN_SCOPE")], expected_active=1,expected_random=1)
        with self.assertRaisesRegex(ValueError, "expected 1 active"):
            module.build([source("W1"),source("W1")],[reviewer(1,"W1","IN_SCOPE")], expected_active=1, expected_random=1)

    def test_unreleased_guard(self):
        rev = reviewer(1,"W1","OUT_OF_SCOPE")
        rev["release_status"] = "RELEASED"
        with self.assertRaisesRegex(ValueError, "release changed"):
            module.build([source("W1")],[rev],expected_active=1,expected_random=1)

    def test_no_evidence_is_not_exclusion(self):
        r=module.source_triage(source("W1",ol=[],year=[],wd_year=[],subjects=[]))
        self.assertEqual(r["triage_route_not_scope"], "FORM_OR_IDENTITY_UNRESOLVED")
        self.assertEqual(r["release_status"], "NOT_RELEASED")


if __name__ == "__main__":
    unittest.main()