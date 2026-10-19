"""Structured profile records: import from CV text, migration, rules and access."""

import datetime
import importlib.util
import json
from pathlib import Path
import unittest

try:
    from odoo.exceptions import AccessError, ValidationError
    from odoo.tests import TransactionCase, tagged
    from odoo.tools import mute_logger
except ImportError:
    raise unittest.SkipTest("needs Odoo (--test-enable)")

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = json.loads((ROOT / "tests" / "fixtures" / "complete_cv_expected.json").read_text())
SECTIONS = ("experience", "projects", "skills", "education", "trainings", "volunteering", "languages")


@tagged("post_install", "-at_install")
class TestStructuredProfile(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_user = cls.env.ref("base.group_user")
        cls.owner = cls.env["res.users"].create({
            "name": "Structured Owner", "login": "structured-owner", "group_ids": [(6, 0, [group_user.id])],
        })
        cls.other = cls.env["res.users"].create({
            "name": "Structured Other", "login": "structured-other", "group_ids": [(6, 0, [group_user.id])],
        })
        cls.profile = cls.env["job.profile"].create({"user_id": cls.owner.id, "full_name": "Owner"})

    def _import_reference(self, profile=None):
        profile = profile or self.profile
        profile._set_structured_sections({name: EXPECTED[name] for name in SECTIONS})
        return profile

    def test_reference_cv_becomes_records(self):
        profile = self._import_reference()
        self.assertEqual(len(profile.experience_ids), 13)
        self.assertEqual(len(profile.experience_ids.filtered(lambda e: e.category == "research")), 2)
        self.assertEqual(len(profile.project_ids), 22)
        featured = profile.project_ids.filtered("is_featured")
        self.assertEqual(len(featured), 7)
        self.assertTrue(all(project.category == "work" for project in featured))
        erp = profile.project_ids.filtered(lambda p: p.name == "Custom ERP modules")
        self.assertEqual(erp.subtitle, "Ecuadorian Navy")
        self.assertEqual(erp.experience_id.company, "Duodata")
        self.assertEqual(sorted(erp.technology_ids.mapped("name")), ["Odoo", "PostgreSQL", "Python"])
        self.assertEqual(profile.skill_group_ids.mapped("name"),
                         ["Languages", "Applications", "Data & infrastructure", "Engineering", "ICT analysis"])
        self.assertEqual(len(profile.education_ids), 3)
        self.assertEqual(len(profile.training_ids), 12)
        self.assertEqual(len(profile.volunteering_ids), 3)
        self.assertEqual(profile.spoken_language_ids.mapped("level"), ["native", "b2"])

    def test_import_again_replaces_instead_of_duplicating(self):
        profile = self._import_reference()
        technologies = self.env["job_finder.technology"].search_count([])
        self._import_reference()
        self.assertEqual(len(profile.experience_ids), 13)
        self.assertEqual(len(profile.project_ids), 22)
        self.assertEqual(self.env["job_finder.technology"].search_count([]), technologies)

    def test_missing_section_keeps_its_records(self):
        profile = self._import_reference()
        profile._set_structured_sections({"languages": "French (C1)."})
        self.assertEqual(profile.spoken_language_ids.mapped("name"), ["French"])
        self.assertEqual(len(profile.experience_ids), 13)
        self.assertEqual(len(profile.training_ids), 12)

    def test_technologies_match_case_insensitively(self):
        Technology = self.env["job_finder.technology"]
        python = Technology.create({"name": "Python"})
        found = Technology._find_or_create(["python", "PYTHON", "Rust", "", "rust"])
        self.assertEqual(found.mapped("name"), ["Python", "Rust"])
        self.assertEqual(found[0], python)
        with self.assertRaises(Exception), self.cr.savepoint(), mute_logger("odoo.sql_db"):
            Technology.create({"name": "RUST"})

    def test_period_labels(self):
        profile = self._import_reference()
        duodata = profile.experience_ids.filtered(lambda e: e.company == "Duodata")
        knock = profile.experience_ids.filtered(lambda e: e.company == "The Knock Restaurant")
        martini = profile.experience_ids.filtered(lambda e: e.company == "Martini & Co")
        self.assertEqual(duodata._get_period_label(), "Dec 2021 – Jan 2025")
        self.assertEqual(knock._get_period_label(), "Feb 2025 – Present")
        self.assertEqual(martini._get_period_label(), "2023 – 2024")
        self.env["res.lang"]._activate_lang("es_ES")
        self.assertEqual(duodata.with_context(lang="es_ES")._get_period_label(), "dic 2021 – ene 2025")
        self.assertEqual(profile.education_ids[-1]._get_period_label(), "2014 – 2019")

    def test_completeness_lists_what_is_missing(self):
        self.assertLess(self.profile.completeness, 50)
        self.assertIn("Add a photo.", self.profile.completeness_hints)
        profile = self._import_reference()
        profile.write({"headline": "Developer", "summary": "Summary", "email": "owner@example.com"})
        self.assertEqual(profile.completeness, 90)
        self.assertEqual(profile.completeness_hints, "Add a photo.")

    def test_invalid_dates_and_cross_profile_projects_are_refused(self):
        with self.assertRaises(ValidationError):
            self.env["job_finder.experience"].create({
                "profile_id": self.profile.id, "role": "Engineer",
                "date_start": datetime.date(2024, 5, 1), "date_end": datetime.date(2023, 5, 1),
            })
        current = self.env["job_finder.experience"].create({
            "profile_id": self.profile.id, "role": "Engineer", "date_start": datetime.date(2024, 5, 1),
            "date_end": datetime.date(2023, 5, 1), "is_current": True,
        })
        self.assertTrue(current.is_current)
        other_profile = self.env["job.profile"].create({"user_id": self.other.id})
        with self.assertRaises(ValidationError):
            self.env["job_finder.project"].create({
                "profile_id": other_profile.id, "name": "Borrowed", "experience_id": current.id,
            })
        with self.assertRaises(ValidationError):
            self.env["job_finder.education"].create({
                "profile_id": self.profile.id, "qualification": "Degree", "year_start": 2020, "year_end": 2019,
            })

    def test_users_reach_only_their_own_records(self):
        self._import_reference()
        Experience = self.env["job_finder.experience"]
        self.assertEqual(Experience.with_user(self.owner).search_count([]), 13)
        self.assertEqual(Experience.with_user(self.other).search_count([]), 0)
        role = self.profile.experience_ids[0]
        with self.assertRaises(AccessError):
            role.with_user(self.other).read(["role"])
        with self.assertRaises(AccessError):
            self.env["job_finder.training"].with_user(self.other).create({
                "profile_id": self.profile.id, "name": "Injected",
            })
        admin = self.env.ref("base.user_admin")
        self.assertEqual(Experience.with_user(admin).search_count([("profile_id", "=", self.profile.id)]), 13)

    def test_migration_builds_records_once(self):
        spec = importlib.util.spec_from_file_location(
            "post_migrate", ROOT / "migrations" / "19.0.1.1.0" / "post-migrate.py")
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        legacy = self.env["job.profile"].create({
            "user_id": self.other.id, **{name: EXPECTED[name] for name in SECTIONS},
        })
        website = self.env.ref("website.default_website")
        website.homepage_url = False
        self.env["ir.config_parameter"].set_param("job_finder.portfolio_hosts", "example.com")
        migration.migrate(self.env.cr, "19.0.1.0.0")
        self.assertEqual(len(legacy.experience_ids), 13)
        self.assertEqual(website.homepage_url, "/portfolio")
        self.assertFalse(self.env["ir.config_parameter"].get_param("job_finder.portfolio_hosts"))
        website.homepage_url = "/contactus"
        legacy.experience_ids[0].role = "Edited by the person"
        migration.migrate(self.env.cr, "19.0.1.0.0")
        self.assertEqual(legacy.experience_ids[0].role, "Edited by the person")
        self.assertEqual(len(legacy.experience_ids), 13)
        self.assertEqual(website.homepage_url, "/contactus")  # a homepage chosen later is kept
