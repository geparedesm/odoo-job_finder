"""Exercise the parser through its standalone import contract."""

import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "standalone_cv_parser", Path(__file__).resolve().parents[1] / "models/cv_parser.py"
)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)


class TestCVParser(unittest.TestCase):
    def test_sample_format(self):
        result = parser.parse_cv_text("""
Gabriel Paredes Mendoza
FULL STACK DEVELOPER
Perth, Australia • (+61) 415 530 419 • gabriel@example.com • linkedin.com/in/geparedesm
SKILLS
Python, Dart
Language
Spanish (Native), English (B2)
PERSONAL ATTRIBUTES
•Strong analytical skills.
PROFESSIONAL EXPERIENCE
Developer • 2020 - 2025
EDUCATION
Mechatronic Engineering
LEADERSHIP & VOLUNTEERING EXPERIENCE
Volunteer
CERTIFICATION
CCNA
REFERENCES
Someone • someone@example.com • +61412345678
""")
        self.assertEqual(result, dict(
            full_name="Gabriel Paredes Mendoza", headline="FULL STACK DEVELOPER",
            location="Perth, Australia", phone="(+61) 415 530 419",
            email="gabriel@example.com", linkedin="linkedin.com/in/geparedesm",
            skills="Python, Dart\nLanguage\nSpanish (Native), English (B2)",
            summary="•Strong analytical skills.", experience="Developer • 2020 - 2025",
            education="Mechatronic Engineering", certifications="CCNA", languages="",
        ))

    def test_empty_and_unrecognized(self):
        for text in ("", " \n\t", "Jane Doe\nDeveloper", None, 123):
            with self.subTest(text=text):
                result = parser.parse_cv_text(text)
                self.assertEqual(len(result), 12)
                self.assertTrue(all(value == "" for value in result.values()))

    def test_variants_and_repeated_sections(self):
        for heading in ("SUMMARY", "Profile", "personal   attributes:"):
            for experience in ("EXPERIENCE", "work experience", "Professional Experience:"):
                result = parser.parse_cv_text(
                    f"Jane Doe\nDeveloper\n{heading}\nAbout me\n{experience}\nJob\n"
                    "certifications:\nAward\nLanguages\nEnglish\nSkills\nPython\nSKILLS\nSQL"
                )
                self.assertEqual(result["summary"], "About me")
                self.assertEqual(result["experience"], "Job")
                self.assertEqual(result["certifications"], "Award")
                self.assertEqual(result["languages"], "English")
                self.assertEqual(result["skills"], "Python\nSQL")

    def test_headline_and_contact_limits(self):
        for second in ("Engineer 2", "jane@example.com", "x" * 101):
            result = parser.parse_cv_text(f"Jane Doe\n{second}\nSKILLS\nPython")
            self.assertEqual(result["headline"], "")
        result = parser.parse_cv_text(
            "Jane Doe\nDeveloper\nLondon | +44 7700 900123 | jane@example.com | "
            "https://www.linkedin.com/in/jane\nEXPERIENCE\n"
            "reference@example.com +12345678900\nPython skills are useful"
        )
        self.assertEqual(result["location"], "London")
        self.assertEqual(result["phone"], "+44 7700 900123")
        self.assertEqual(result["linkedin"], "https://www.linkedin.com/in/jane")
        self.assertEqual(result["skills"], "")


if __name__ == "__main__":
    unittest.main()
