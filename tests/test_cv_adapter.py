"""Standalone contract tests for the planned CV adapter.

The public contract is adapt_profile(fields, job_description), returning a
mapping with string ``summary`` and ``skills`` values. Load the file directly
so importing the Odoo addon is unnecessary. Only an absent implementation is
skipped; import errors or a missing public function must fail once it exists.
"""

from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


ADAPTER_PATH = Path(__file__).resolve().parent.parent / "models" / "cv_adapter.py"
adapter = None
if ADAPTER_PATH.exists():
    spec = importlib.util.spec_from_file_location("standalone_cv_adapter", ADAPTER_PATH)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)


@unittest.skipIf(adapter is None, "models/cv_adapter.py is not implemented yet")
class TestCVAdapter(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "full_name": "Jane Doe",
            "headline": "Developer",
            "summary": "Developer experienced in JavaScript. Builds APIs with Python and SQL.",
            "skills": "JavaScript\nPython\nSQL\nIllustration",
            "experience": "Built internal APIs.",
            "education": "Computer science degree",
        }

    def assert_original_content(self, result):
        self.assertEqual(result["summary"], self.profile["summary"])
        self.assertEqual(result["skills"], self.profile["skills"])

    def test_no_overlap_preserves_original_content(self):
        result = adapter.adapt_profile(self.profile, "Seeking a nurse for patient care.")
        self.assert_original_content(result)

    def test_partial_overlap_emphasizes_matching_keywords(self):
        result = adapter.adapt_profile(
            self.profile, "Seeking PYTHON and SQL expertise; Kubernetes is desirable.",
        )
        self.assertIsInstance(result["summary"], str)
        self.assertIsInstance(result["skills"], str)
        self.assertNotEqual(result["summary"], self.profile["summary"])
        self.assertIn("python", result["summary"].casefold())
        self.assertIn("sql", result["summary"].casefold())
        # Permit either filtering or reordering, without fixing prose or delimiters.
        skills = result["skills"].casefold()
        self.assertIn("python", skills)
        self.assertIn("sql", skills)
        for unmatched in ("javascript", "illustration"):
            if unmatched in skills:
                self.assertLess(skills.index("python"), skills.index(unmatched))
                self.assertLess(skills.index("sql"), skills.index(unmatched))
        # A job requirement alone must not become a claimed skill.
        self.assertNotIn("kubernetes", skills)

    def test_empty_job_description_preserves_original_content(self):
        for description in ("", " \n\t "):
            with self.subTest(description=description):
                self.assert_original_content(adapter.adapt_profile(self.profile, description))

    def test_original_fields_are_never_mutated(self):
        for description in (
            "Python and SQL", "Seeking a nurse for patient care.", "",
        ):
            with self.subTest(description=description):
                fields = deepcopy(self.profile)
                original = deepcopy(fields)
                result = adapter.adapt_profile(fields, description)
                self.assertEqual(fields, original)
                self.assertIsNot(result, fields)
                # Editing an adapted draft must not overwrite the saved profile.
                result["summary"] = "Edited draft summary"
                result["skills"] = "Edited draft skills"
                self.assertEqual(fields, original)


if __name__ == "__main__":
    unittest.main()
