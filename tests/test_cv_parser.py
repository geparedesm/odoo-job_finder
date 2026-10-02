"""Exercise the parser through its standalone import contract."""

import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "standalone_cv_parser",
    Path(__file__).resolve().parent.parent / "models" / "cv_parser.py",
)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)


EMPTY_RESULT = dict.fromkeys((
    "full_name", "headline", "email", "phone", "location", "linkedin",
    "summary", "skills", "experience", "education", "certifications", "languages",
), "")


class TestCVParser(unittest.TestCase):
    def test_sample_format(self):
        # Abbreviated from ATS-Resume-FullStack-17-04-2025.pdf; keep its
        # first two lines, contact line, headings and representative content.
        result = parser.parse_cv_text("""
Gabriel Paredes Mendoza
FULL STACK DEVELOPER
Perth, Australia • (+61) 415 530 419 • gabrielparedesmendoza@gmail.com • linkedin.com/in/geparedesm
SKILLS
Program Language
Dart, Python, JavaScript, TypeScript, React, React Native.
Language
Spanish (Native), English (B2)
PERSONAL ATTRIBUTES
•Strong analytical skills.
PROFESSIONAL EXPERIENCE
GP-Developer, Ecuador • Full Stack Developer • 01/02/2020 - 01/12/2021
Project: GP-Security
EDUCATION
2014 – 2019 – Mechatronic Engineering – Universidad Técnica del Norte, Ecuador
LEADERSHIP & VOLUNTEERING EXPERIENCE
Volunteer
CERTIFICATION
CCNA Switching & Routing – CISCO - EEUU 2016
REFERENCES
Someone • someone@example.com • +61412345678
""")
        self.assertEqual(result, dict(
            full_name="Gabriel Paredes Mendoza", headline="FULL STACK DEVELOPER",
            location="Perth, Australia", phone="(+61) 415 530 419",
            email="gabrielparedesmendoza@gmail.com", linkedin="linkedin.com/in/geparedesm",
            skills="Program Language\nDart, Python, JavaScript, TypeScript, React, React Native.\nLanguage\nSpanish (Native), English (B2)",
            summary="•Strong analytical skills.",
            experience="GP-Developer, Ecuador • Full Stack Developer • 01/02/2020 - 01/12/2021\nProject: GP-Security",
            education="2014 – 2019 – Mechatronic Engineering – Universidad Técnica del Norte, Ecuador",
            certifications="CCNA Switching & Routing – CISCO - EEUU 2016", languages="",
        ))

    def test_empty_and_unrecognized(self):
        for text in (
            "", " \n\t", "Jane Doe\nDeveloper", None, 123,
            "Jane Doe\nDeveloper\nLondon • +44 7700 900123 • jane@example.com\n"
            "linkedin.com/in/jane\nHOBBIES\nReading",
        ):
            with self.subTest(text=text):
                result = parser.parse_cv_text(text)
                self.assertEqual(result, EMPTY_RESULT)

    def test_truncated_text(self):
        for text, fields in (
            ("Gabriel Paredes", {}),
            ("Gabriel Paredes\nFULL STACK DEVELOPER\nPerth,", {}),
            ("SKILLS", {}),
            ("SKILLS\nPython\nEDUCATION", {"skills": "Python"}),
            ("EXPERIENCE\nDeveloper\n•Built", {"experience": "Developer\n•Built"}),
        ):
            with self.subTest(text=text):
                self.assertEqual(parser.parse_cv_text(text), {**EMPTY_RESULT, **fields})

    def test_section_heading_variants_and_order(self):
        sections = (
            ("skills", ("SKILLS", "sKiLlS", "  S K I L L S:  "), "Python\n•SQL"),
            ("summary", ("PERSONAL ATTRIBUTES", "SUMMARY", "PROFILE",
                         "  pErSoNaL\t  AtTrIbUtEs:  "), "Analytical\n•Adaptable"),
            ("experience", ("PROFESSIONAL EXPERIENCE", "EXPERIENCE",
                            "  pRoFeSsIoNaL\t  ExPeRiEnCe:  "), "Developer\n•Built APIs"),
            ("education", ("EDUCATION", "eDuCaTiOn", "  E D U C A T I O N:  "), "Engineering\nDiploma"),
            ("certifications", ("CERTIFICATION", "CERTIFICATIONS",
                                "  cErTiFiCaTiOnS:  "), "CCNA\nLinux"),
            ("languages", ("LANGUAGES", "lAnGuAgEs", "  L A N G U A G E S:  "), "Spanish\nEnglish"),
        )
        expected = {**EMPTY_RESULT, **{field: body for field, _, body in sections}}
        orders = (sections, sections[::-1], sections[3:] + sections[:3])
        for order_index, order in enumerate(orders):
            for field, variants, _ in sections:
                for variant in variants:
                    with self.subTest(order=order_index, field=field, heading=variant):
                        text = "\n".join(
                            f"{variant if key == field else headings[0]}\n{body}"
                            for key, headings, body in order
                        )
                        self.assertEqual(parser.parse_cv_text(text), expected)

    def test_reference_pdf_concatenated_experience_heading(self):
        # The reference PDF extracts this heading without an inter-word space.
        result = parser.parse_cv_text(
            "Gabriel Paredes Mendoza\nFULL STACK DEVELOPER\n"
            "PERSONAL ATTRIBUTES\n•Strong analytical skills.\n"
            "PROFESSIONALEXPERIENCE\nDeveloper • 2020 - 2025\n"
            "Second role • 2018 - 2020\nEDUCATION\nMechatronic Engineering"
        )
        self.assertEqual(result["summary"], "•Strong analytical skills.")
        self.assertEqual(
            result["experience"],
            "Developer • 2020 - 2025\nSecond role • 2018 - 2020",
        )
        self.assertEqual(result["education"], "Mechatronic Engineering")

    def test_variants_and_repeated_sections(self):
        for heading in ("SUMMARY", "Profile", "personal   attributes:", "PERSONALATTRIBUTES"):
            for experience in (
                "EXPERIENCE", "work experience", "Professional Experience:",
                "PROFESSIONALEXPERIENCE", "WorkExperience:",
            ):
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
