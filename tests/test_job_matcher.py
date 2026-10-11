"""Standalone contract tests for the planned keyword-overlap matcher.

Proposed API: score_job(profile, posting_text) returns the number of distinct
shared keywords. Profile is a mapping with skills, experience and summary text.
rank_jobs(profile, posting_texts) returns (posting_text, score) pairs in descending
score order, preserving input order for ties. Partial overlap means sharing only
some keywords, not matching substrings of words.

Only the absent planned module skips these tests; an existing module with a
missing API or broken import must fail. No Odoo package import is needed.
"""

import importlib.util
from pathlib import Path
import unittest


MATCHER_PATH = Path(__file__).resolve().parent.parent / "models" / "job_matcher.py"
matcher = None
if MATCHER_PATH.is_file():
    spec = importlib.util.spec_from_file_location("standalone_job_matcher", MATCHER_PATH)
    matcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(matcher)


@unittest.skipIf(matcher is None, "Planned models/job_matcher.py is not implemented yet")
class TestJobMatcher(unittest.TestCase):
    def test_empty_and_blank_profiles(self):
        for profile in ({}, dict(skills="", experience="", summary=""),
                        dict(skills=" \n\t", experience="  ", summary="\n")):
            with self.subTest(profile=profile):
                self.assertEqual(matcher.score_job(profile, "python sql"), 0)

    def test_empty_and_blank_postings(self):
        for posting in ("", " ", "\n\t"):
            with self.subTest(posting=posting):
                self.assertEqual(matcher.score_job({"skills": "python sql"}, posting), 0)
                self.assertEqual(matcher.score_job({}, posting), 0)

    def test_exact_partial_and_no_keyword_overlap(self):
        profile = {"skills": "python sql docker"}
        for posting, expected in (("python sql docker", 3), ("python sql java", 2),
                                  ("docker java", 1), ("java ruby", 0)):
            with self.subTest(posting=posting):
                self.assertEqual(matcher.score_job(profile, posting), expected)

    def test_each_profile_field_contributes_keywords(self):
        for field in ("skills", "experience", "summary"):
            with self.subTest(field=field):
                self.assertEqual(matcher.score_job({field: "python"}, "python"), 1)
        self.assertEqual(matcher.score_job(
            dict(skills="python", experience="sql", summary="docker"),
            "python sql docker",
        ), 3)

    def test_case_insensitivity(self):
        profile = dict(skills="PyThOn", experience="SQL", summary="Docker")
        for posting in ("PYTHON sql DOCKER", "python SQL docker", "PyThOn SqL DoCkEr"):
            with self.subTest(posting=posting):
                self.assertEqual(matcher.score_job(profile, posting), 3)

    def test_repeated_keywords_count_once(self):
        self.assertEqual(matcher.score_job(
            dict(skills="python python", experience="python", summary="PYTHON"),
            "python python PYTHON",
        ), 1)

    def test_partial_words_are_not_keyword_overlap(self):
        self.assertEqual(matcher.score_job({"skills": "java"}, "javascript"), 0)

    def test_ranking_highest_overlap_first(self):
        profile = dict(skills="python", experience="sql", summary="docker")
        postings = ["java ruby", "python sql", "python sql docker", "docker"]
        self.assertEqual(matcher.rank_jobs(profile, postings), [
            ("python sql docker", 3), ("python sql", 2),
            ("docker", 1), ("java ruby", 0),
        ])

    def test_ties_preserve_input_order(self):
        postings = ["sql java", "python docker", "python sql", "ruby", "go"]
        self.assertEqual(matcher.rank_jobs({"skills": "python sql"}, postings), [
            ("python sql", 2), ("sql java", 1), ("python docker", 1),
            ("ruby", 0), ("go", 0),
        ])

    def test_empty_ranking(self):
        self.assertEqual(matcher.rank_jobs({"skills": "python"}, []), [])
        self.assertEqual(matcher.rank_jobs({}, []), [])

    def test_blank_profile_ranking_retains_all_postings(self):
        postings = ["sql", "", "python", "sql"]
        self.assertEqual(matcher.rank_jobs({"skills": " \n\t"}, postings),
                         [(posting, 0) for posting in postings])


if __name__ == "__main__":
    unittest.main()
