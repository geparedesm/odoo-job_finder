"""Exercise the parser through its standalone import contract."""

import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "standalone_cv_parser",
    Path(__file__).resolve().parent.parent / "models" / "cv_parser.py",
)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)


EMPTY_RESULT = dict.fromkeys((
    "full_name", "headline", "email", "phone", "location", "linkedin", "website", "github",
    "summary", "skills", "experience", "education", "languages",
    "volunteering", "projects", "trainings",
), "")


class TestCVParser(unittest.TestCase):
    def test_complete_six_page_reference(self):
        fixtures = Path(__file__).parent / "fixtures"
        text = (fixtures / "gabriel_paredes_cv.txt").read_text()
        expected = json.loads((fixtures / "gabriel_paredes_fields.json").read_text())
        self.assertEqual(len(text.split("\f")), 6)
        self.assertEqual(parser.parse_cv_text(text), expected)

    def test_header_links_leave_linkedin_separate(self):
        result = parser.parse_cv_text(
            "Gabriel Paredes Mendoza\nSOFTWARE DEVELOPMENT | ICT | MECHATRONICS\n"
            "linkedin.com/in/geparedesm | https://gp-developer.com | "
            "https://github.com/geparedesm\nTECHNICAL SKILLS\nLanguages: Dart, Python."
        )
        self.assertEqual(result["linkedin"], "linkedin.com/in/geparedesm")
        self.assertEqual(result["website"], "https://gp-developer.com")
        self.assertEqual(result["github"], "https://github.com/geparedesm")
        self.assertEqual(result["skills"], "Languages: Dart, Python.")
        self.assertEqual(result["languages"], "")

    def test_website_excludes_email_and_social_domains(self):
        for links in (
            "jane@example.com",
            "jane@example.com | example.com",
            "https://www.linkedin.com/in/jane | https://www.github.com/jane",
            "linkedin.com | github.com",
            "HTTPS://WWW.LINKEDIN.COM | HTTPS://WWW.GITHUB.COM",
        ):
            with self.subTest(links=links):
                header = f"Jane Doe\nDeveloper\n{links}"
                result = parser.parse_cv_text(f"{header}\nSKILLS\nPython")
                self.assertEqual(result["website"], "")
                result = parser.parse_cv_text(f"{header} | gp-developer.com\nSKILLS\nPython")
                self.assertEqual(result["website"], "gp-developer.com")

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
            website="", github="",
            skills="Program Language\nDart, Python, JavaScript, TypeScript, React, React Native.",
            summary="•Strong analytical skills.",
            experience="GP-Developer, Ecuador • Full Stack Developer • 01/02/2020 - 01/12/2021\nProject: GP-Security",
            education="2014 – 2019 – Mechatronic Engineering – Universidad Técnica del Norte, Ecuador",
            languages="Spanish (Native), English (B2)",
            volunteering="Volunteer", projects="", trainings="",
        ))

    def test_complete_reference_compound_headings(self):
        # Abbreviated from Gabriel_Paredes_CV_completo.pdf; preserve its
        # headings, separate experience blocks and representative content.
        result = parser.parse_cv_text("""
Gabriel Paredes Mendoza
SOFTWARE DEVELOPMENT | ICT | MECHATRONICS
PROFESSIONAL PROFILE
Multidisciplinary professional.
TECHNICAL SKILLS
Languages: Dart, Python, JavaScript.
PROFESSIONAL EXPERIENCE - SOFTWARE DEVELOPMENT
Full Stack Developer
ACADEMIC RESEARCH - MECHATRONICS
IoT systems
ACADEMIC PROJECTS - ICT ANALYSIS AND NETWORKS
Network design
PROFESSIONAL EXPERIENCE - PRODUCTION AND HOSPITALITY
Production operations
LEADERSHIP AND VOLUNTEERING
Community training
TRAINING AND CREDENTIALS
Technical training
REFERENCES
Someone • someone@example.com
""")
        self.assertEqual(result, {
            **EMPTY_RESULT,
            "full_name": "Gabriel Paredes Mendoza",
            "headline": "SOFTWARE DEVELOPMENT | ICT | MECHATRONICS",
            "summary": "Multidisciplinary professional.",
            "skills": "Languages: Dart, Python, JavaScript.",
            "experience": "Full Stack Developer\nProduction operations",
            "projects": "IoT systems\nNetwork design",
            "volunteering": "Community training",
            "trainings": "Technical training",
        })

    def test_topic_headline_before_contact_line(self):
        result = parser.parse_cv_text("""
Gabriel Paredes Mendoza
SOFTWARE DEVELOPMENT | ICT | MECHATRONICS
Perth, Australia | +61 415 530 419 | gabrielparedesmendoza@gmail.com
linkedin.com/in/geparedesm | gp-developer.com | github.com/geparedesm
PROFESSIONAL PROFILE
Multidisciplinary professional.
""")
        self.assertEqual(result["location"], "Perth, Australia")
        self.assertEqual(result["headline"], "SOFTWARE DEVELOPMENT | ICT | MECHATRONICS")

    def test_running_headers_and_footers(self):
        result = parser.parse_cv_text("""
Gabriel Paredes Mendoza
SOFTWARE DEVELOPMENT | ICT | MECHATRONICS
PROFESSIONAL PROFILE
Multidisciplinary professional.
Gabriel Paredes Mendoza 1 / 6
Gabriel Paredes Mendoza
PROFESSIONAL CV
TECHNICAL SKILLS
Python
PROFESSIONAL EXPERIENCE - SOFTWARE DEVELOPMENT
Full Stack Developer
Gabriel Paredes Mendoza 2/6
GABRIEL PAREDES MENDOZA
PROFESSIONAL CV
Developed ERP modules.
Gabriel Paredes Mendoza
2 / 6
Gabriel Paredes Mendoza
ACADEMIC RESEARCH - MECHATRONICS
Passive exoskeleton development
EDUCATION
Mechatronics Engineering
Gabriel Paredes Mendoza 3 / 6
Gabriel Paredes Mendoza
PROFESSIONAL CV
Degree completed.
ACADEMIC PROJECTS - ICT ANALYSIS AND NETWORKS
Network design
Gabriel Paredes Mendoza 4 / 6
Gabriel Paredes Mendoza
CAREER OVERVIEW
PROFESSIONAL EXPERIENCE - PRODUCTION AND HOSPITALITY
Fencing Production Operator
Bartender
Gabriel Paredes Mendoza 5 / 6
Gabriel Paredes Mendoza
LEADERSHIP AND VOLUNTEERING
Community workshops
TRAINING AND CREDENTIALS
Forklift Licence
Gabriel Paredes Mendoza
REFERENCES
Private reference details
Gabriel Paredes Mendoza 6 / 6
""")
        self.assertEqual(result, {
            **EMPTY_RESULT,
            "full_name": "Gabriel Paredes Mendoza",
            "headline": "SOFTWARE DEVELOPMENT | ICT | MECHATRONICS",
            "summary": "Multidisciplinary professional.",
            "skills": "Python",
            "experience": "Full Stack Developer\nDeveloped ERP modules.\nFencing Production Operator\nBartender",
            "education": "Mechatronics Engineering\nDegree completed.",
            "projects": "Passive exoskeleton development\nNetwork design",
            "volunteering": "Community workshops",
            "trainings": "Forklift Licence",
        })

    def test_running_name_preserves_substantive_following_line(self):
        for content in ("Completed 2025", "A" * 61, "Degree completed.", "Full Stack Developer (continued)",
                        "Substantive short continuation"):
            with self.subTest(content=content):
                result = parser.parse_cv_text(
                    "Jane Doe\nDeveloper\nEDUCATION\nJane Doe\n" + content
                )
                self.assertEqual(result["education"], content)

    def test_heading_qualifiers_do_not_match_body_prefixes(self):
        for separator in (" - ", " – ", " — "):
            with self.subTest(separator=separator):
                result = parser.parse_cv_text(
                    f"TECHNICAL SKILLS{separator}PROGRAMMING\nPython\n"
                    "Skills include teamwork\nProfessional experience with Python\n"
                    f"REFERENCES{separator}AVAILABLE ON REQUEST\nPrivate details"
                )
                self.assertEqual(result, {
                    **EMPTY_RESULT,
                    "skills": "Python\nSkills include teamwork\nProfessional experience with Python",
                })

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

    def test_ignored_headings_stop_collection_and_resume_at_supported_sections(self):
        for heading in ("CERTIFICATION", "CERTIFICATIONS", "  cErTiFiCaTiOnS:  ",
                        "C E R T I F I C A T I O N", "Certifications - Current", "REFERENCES"):
            with self.subTest(heading=heading):
                result = parser.parse_cv_text(
                    f"SKILLS\nPython\n{heading}\nIgnored content\nEDUCATION\nDegree"
                )
                self.assertEqual(result, {**EMPTY_RESULT, "skills": "Python", "education": "Degree"})

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

class TestCompletePDF(unittest.TestCase):
    def test_all_six_pages_and_every_field(self):
        import json
        import pypdf

        fixtures = Path(__file__).parent / "fixtures"
        text = (fixtures / "complete_cv.txt").read_text()
        reader = pypdf.PdfReader(fixtures / "Gabriel_Paredes_CV_completo.pdf")
        self.assertEqual(len(reader.pages), 6)
        self.assertEqual("\n".join(page.extract_text() or "" for page in reader.pages), text)
        expected = json.loads((fixtures / "complete_cv_expected.json").read_text())
        self.assertEqual(parser.parse_cv_text(text), expected)

    def test_training_credentials_are_preserved(self):
        result = parser.parse_cv_text(
            "TRAINING AND CREDENTIALS\nWorkshop | 2025\n"
            "Certificate | 2016 | Not renewed\n"
            "SKILLS\nLanguages: Python, C/C++\n"
            "Languages spoken: Spanish (native), English (B2).\n"
            "REFERENCES\nPrivate reference"
        )
        self.assertEqual(result["trainings"], "Workshop | 2025\nCertificate | 2016 | Not renewed")
        self.assertEqual(result["skills"], "Languages: Python, C/C++")
        self.assertEqual(result["languages"], "Spanish (native), English (B2).")
        self.assertNotIn("Private", str(result))


if __name__ == "__main__":
    unittest.main()
