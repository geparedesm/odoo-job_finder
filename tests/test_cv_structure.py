"""Structured entries parsed from CV section texts (standard library only)."""

import datetime
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cv_structure", ROOT / "models" / "cv_structure.py")
cv_structure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cv_structure)

EXPECTED = json.loads((ROOT / "tests" / "fixtures" / "complete_cv_expected.json").read_text())


class TestRoles(unittest.TestCase):
    def setUp(self):
        self.roles = cv_structure.parse_roles(EXPECTED["experience"], "work")

    def test_every_role_with_company_dates_and_type(self):
        self.assertEqual(len(self.roles), 11)
        first = self.roles[0]
        self.assertEqual((first["role"], first["company"], first["location"]),
                         ("Full Stack Developer", "Duodata", "Ecuador / remote from Australia"))
        self.assertEqual((first["date_start"], first["date_end"]), (datetime.date(2021, 12, 1), datetime.date(2025, 1, 1)))
        self.assertEqual(first["employment_type"], "full_time")
        self.assertFalse(first["is_current"] or first["is_year_only"])

    def test_continued_role_merges_its_projects(self):
        names = [project["name"] for project in self.roles[0]["projects"]]
        self.assertEqual(names, ["Custom ERP modules", "Security log data warehouse",
                                 "ZKTeco biometric administration platform", "The Hit", "Frecuento"])
        self.assertNotIn("Full Stack Developer (continued)", [role["role"] for role in self.roles])

    def test_project_subtitle_technologies_and_wrapped_description(self):
        erp, _warehouse, zkteco, the_hit = self.roles[0]["projects"][:4]
        self.assertEqual((erp["subtitle"], erp["technologies"]), ("Ecuadorian Navy", ["Odoo", "Python", "PostgreSQL"]))
        self.assertEqual(the_hit["subtitle"], "music social application")
        self.assertTrue(zkteco["description"].startswith("Developed a cross-platform administration application"))
        self.assertIn("cut deployment time by 50% through CI/CD.", zkteco["description"])
        self.assertNotIn("\n", zkteco["description"])

    def test_role_bullets_before_projects_are_highlights(self):
        founder = self.roles[1]
        self.assertEqual(founder["role"], "Founder & Full Stack Developer")
        self.assertEqual(founder["highlights"], ["Independently developed approximately 15 technology projects for clients."])
        self.assertEqual(founder["employment_type"], "freelance")
        gp_security = founder["projects"][0]
        self.assertEqual(gp_security["description"].count("\n"), 3)  # four bullets
        self.assertIn("Fusion 360", gp_security["technologies"])

    def test_current_and_year_only_roles(self):
        knock = next(role for role in self.roles if role["company"] == "The Knock Restaurant")
        self.assertTrue(knock["is_current"])
        self.assertIsNone(knock["date_end"])
        martini = next(role for role in self.roles if role["company"] == "Martini & Co")
        self.assertTrue(martini["is_year_only"])
        self.assertEqual((martini["date_start"].year, martini["date_end"].year), (2023, 2024))
        self.assertEqual(martini["employment_type"], "casual")

    def test_research_roles_with_wrapped_meta_and_split_header(self):
        research = cv_structure.parse_roles(EXPECTED["projects"], "research")
        self.assertEqual(len(research), 2)
        mechatronics, nit = research
        self.assertEqual(mechatronics["role"], "Mechatronics Research Collaborator")
        self.assertEqual(mechatronics["employment_type"], "academic")  # 'Academic' + wrapped 'collaboration'
        self.assertEqual(len(mechatronics["projects"]), 5)
        self.assertEqual((nit["company"], nit["location"]), ("National Institute of Technology (NIT)", "Australia"))
        self.assertEqual(nit["date_start"], datetime.date(2024, 7, 1))
        self.assertEqual(len(nit["projects"]), 10)
        self.assertTrue(all(project["category"] == "research" for project in nit["projects"]))

    def test_empty_and_unknown_input(self):
        self.assertEqual(cv_structure.parse_roles(""), [])
        self.assertEqual(cv_structure.parse_roles(None), [])
        [role] = cv_structure.parse_roles("Engineer\nAcme | Perth | 2020 - 2021 | Apprenticeship\n• Built things.")
        self.assertIsNone(role["employment_type"])
        self.assertEqual(role["highlights"], ["Built things."])


class TestOtherSections(unittest.TestCase):
    def test_skill_groups_with_wrapped_line_and_capitalized_tags(self):
        groups = cv_structure.parse_skill_groups(EXPECTED["skills"])
        self.assertEqual([group["name"] for group in groups],
                         ["Languages", "Applications", "Data & infrastructure", "Engineering", "ICT analysis"])
        data = groups[2]["technologies"]
        self.assertEqual(data[-3:], ["AWS", "Terraform", "CI/CD"])  # continued on the next line, final '.' removed
        self.assertIn("Microcontrollers", groups[3]["technologies"])

    def test_spoken_languages_with_levels(self):
        self.assertEqual(cv_structure.parse_spoken_languages(EXPECTED["languages"]),
                         [{"name": "Spanish", "level": "native"}, {"name": "English", "level": "b2"}])
        self.assertEqual(cv_structure.parse_spoken_languages("French"), [{"name": "French", "level": None}])

    def test_education_details(self):
        advanced, diploma, degree = cv_structure.parse_education(EXPECTED["education"])
        self.assertEqual((advanced["code"], advanced["institution"], advanced["location"], advanced["status"], advanced["year_end"]),
                         ("ICT60220", "National Institute of Technology", "Australia", "completed", 2025))
        self.assertEqual(diploma["code"], "ICT50220")
        self.assertEqual((degree["year_start"], degree["year_end"], degree["status"]), (2014, 2019, "graduated"))

    def test_trainings_with_status(self):
        trainings = cv_structure.parse_trainings(EXPECTED["trainings"])
        self.assertEqual(len(trainings), 12)
        self.assertEqual(trainings[0], {"name": "Forklift Licence (LF)", "issuer": "WorkSafe WA", "year": 2025, "status": "current"})
        ccna = next(t for t in trainings if t["name"].startswith("CCNA"))
        self.assertEqual((ccna["year"], ccna["status"]), (2016, "not_renewed"))

    def test_volunteering_with_recognitions(self):
        nit, ieee, mentor = cv_structure.parse_volunteering(EXPECTED["volunteering"])
        self.assertEqual(nit["period"], "Ambassador: 2025 - 2026 | Volunteer: 2024 - 2025")
        self.assertEqual(len(nit["highlights"]), 2)
        self.assertEqual(len(ieee["recognitions"]), 7)
        self.assertEqual(ieee["recognitions"][0], "Vice Chair, IEEEXtreme Public Relations Committee (2019 - 2021)")
        self.assertEqual(mentor["location"], "Ibarra, Ecuador")

    def test_periods(self):
        self.assertEqual(cv_structure.parse_period("Feb 2025 - Present"), (datetime.date(2025, 2, 1), None, True, False))
        self.assertEqual(cv_structure.parse_period("2024"), (datetime.date(2024, 1, 1), datetime.date(2024, 12, 1), False, True))
        self.assertEqual(cv_structure.parse_period("unknown"), (None, None, False, False))


if __name__ == "__main__":
    unittest.main()
