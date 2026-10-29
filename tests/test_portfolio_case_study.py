"""Case-study data of projects, key figures, secondary roles, and their access rules."""

import importlib.util
from pathlib import Path
import unittest

try:
    from odoo.exceptions import AccessError
    from odoo.tests import TransactionCase, tagged
except ImportError:
    raise unittest.SkipTest("Odoo not available") from None


@tagged("post_install", "-at_install")
class PortfolioCaseStudyTestCase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.user = self.env["res.users"].create({
            "name": "Case Owner", "login": "case_owner",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        self.other_user = self.env["res.users"].create({
            "name": "Case Other", "login": "case_other",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        self.profile = self.env["job.profile"].create({"user_id": self.user.id, "full_name": "Case Owner"})
        self.role = self.env["job_finder.experience"].create({
            "profile_id": self.profile.id, "role": "Developer", "company": "Acme",
            "date_start": "2021-12-01", "date_end": "2025-01-01",
        })
        self.first, self.second = self.env["job_finder.project"].create([
            {"profile_id": self.profile.id, "experience_id": self.role.id, "name": "First", "is_featured": True,
             "sequence": 1, "description": "Built the app. Then shipped it to stores.", "platforms": "Android",
             "highlights": "API: REST services\nTests", "area": "Mobile",
             "metric_ids": [(0, 0, {"value": "+40%", "label": "Throughput"})],
             "step_ids": [(0, 0, {"name": "Devices"}), (0, 0, {"name": "App", "is_highlighted": True})]},
            {"profile_id": self.profile.id, "name": "Second", "is_featured": True, "sequence": 2},
        ])

    def test_case_study_values(self):
        values = self.profile._get_case_study_values(self.first)
        self.assertEqual((values["index"], values["count"], values["area"]), ("01", "02", "Mobile"))
        self.assertEqual((values["lead"], values["overview"]), ("Built the app.", "Then shipped it to stores."))
        self.assertEqual(values["facts"], [("Role", "Developer"), ("Company", "Acme"),
                                           ("Period", "Dec 2021 – Jan 2025"), ("Platforms", "Android")])
        self.assertEqual(values["metrics"], [{"value": "+40%", "label": "Throughput"}])
        self.assertEqual(values["highlights"], [{"title": "API", "description": "REST services"},
                                                {"title": "", "description": "Tests"}])
        self.assertEqual([step["is_highlighted"] for step in values["steps"]], [False, True])
        self.assertIsNone(values["cover_url"])
        # The pager wraps around the featured projects.
        self.assertEqual(values["next"]["name"], "Second")
        self.assertEqual(values["previous"]["name"], "Second")

    def test_single_case_study_has_no_pager(self):
        self.second.is_featured = False
        values = self.profile._get_case_study_values(self.first)
        self.assertIsNone(values["next"])
        self.assertIsNone(values["previous"])

    def test_portfolio_path_uses_a_slug(self):
        self.assertEqual(self.first._get_portfolio_path(), f"/portfolio/project/first-{self.first.id}")

    def test_figures_and_headings(self):
        self.profile.write({
            "summary": "Builds apps. And more.",
            "figure_ids": [(0, 0, {"value": "6 yrs", "label": "Building software"}),
                           (0, 0, {"value": "Hidden", "label": "Hidden", "is_public": False})],
        })
        values = self.profile._get_portfolio_values()
        self.assertEqual(values["figures"], [{"value": "6 yrs", "label": "Building software"}])
        self.assertEqual(values["tagline"], "Builds apps.")
        self.assertEqual(values["headings"]["work"], "Selected work")
        self.profile.write({"tagline": "Apps and hardware.", "work_heading": "Real operations."})
        values = self.profile._get_portfolio_values()
        self.assertEqual((values["tagline"], values["headings"]["work"]), ("Apps and hardware.", "Real operations."))

    def test_secondary_roles_are_grouped(self):
        self.env["job_finder.experience"].create([
            {"profile_id": self.profile.id, "role": "Bartender", "company": "Bar", "is_secondary": True,
             "date_start": "2019-01-01", "date_end": "2023-01-01", "is_year_only": True},
            {"profile_id": self.profile.id, "role": "Operator", "company": "Factory", "is_secondary": True,
             "date_start": "2023-10-01", "is_current": True},
        ])
        values = self.profile._get_portfolio_values()
        self.assertEqual([role["title"] for role in values["roles"]], ["Developer"])
        self.assertEqual({role["title"] for role in values["secondary_roles"]}, {"Bartender", "Operator"})
        self.assertEqual(values["secondary_period"], "2019 – Present")
        self.assertEqual(values["secondary_title"], "Other experience")

    def test_cv_import_marks_roles_without_projects_as_secondary(self):
        self.profile._set_structured_sections({"experience": "\n".join([
            "Full Stack Developer",
            "Acme | Ecuador | Jan 2019 - Feb 2020 | Full-time",
            "Tracking system",
            "Technologies / methods: PHP",
            "• Built it.",
            "Bartender",
            "Bar | Australia | 2023 - 2024 | Casual",
            "• Served drinks.",
        ])})
        roles = {role.role: role.is_secondary for role in self.profile.experience_ids}
        self.assertEqual(roles, {"Full Stack Developer": False, "Bartender": True})

    def test_upgrade_marks_existing_roles_without_projects_as_secondary(self):
        bartender = self.env["job_finder.experience"].create({"profile_id": self.profile.id, "role": "Bartender"})
        research = self.env["job_finder.experience"].create({
            "profile_id": self.profile.id, "role": "Collaborator", "category": "research"})
        spec = importlib.util.spec_from_file_location(
            "job_finder_migration_1_2", Path(__file__).parents[1] / "migrations" / "19.0.1.2.0" / "post-migrate.py")
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.migrate(self.env.cr, "19.0.1.1.0")
        self.env.invalidate_all()
        self.assertEqual((bartender.is_secondary, research.is_secondary, self.role.is_secondary), (True, False, False))

    def test_language_level_bar(self):
        self.env["job_finder.spoken_language"].create([
            {"profile_id": self.profile.id, "name": "Spanish", "level": "native"},
            {"profile_id": self.profile.id, "name": "English", "level": "b2"},
            {"profile_id": self.profile.id, "name": "Quechua"},
        ])
        values = self.profile._get_portfolio_values()
        self.assertEqual([language["percent"] for language in values["languages"]], [100, 70, 0])

    def test_case_study_records_follow_their_profile(self):
        Metric = self.env["job_finder.project_metric"]
        Step = self.env["job_finder.project_step"]
        Figure = self.env["job_finder.profile_figure"]
        figure = Figure.create({"profile_id": self.profile.id, "value": "1", "label": "One"})
        # The owner reaches them.
        self.assertEqual(len(Metric.with_user(self.user).search([("project_id", "=", self.first.id)])), 1)
        self.assertEqual(len(Step.with_user(self.user).search([("project_id", "=", self.first.id)])), 2)
        self.assertEqual(Figure.with_user(self.user).search([("id", "=", figure.id)]), figure)
        # Another user does not, and cannot add records to them.
        self.assertFalse(Metric.with_user(self.other_user).search([("project_id", "=", self.first.id)]))
        self.assertFalse(Step.with_user(self.other_user).search([("project_id", "=", self.first.id)]))
        self.assertFalse(Figure.with_user(self.other_user).search([("id", "=", figure.id)]))
        with self.assertRaises(AccessError):
            Metric.with_user(self.other_user).create({"project_id": self.first.id, "value": "1", "label": "x"})
        with self.assertRaises(AccessError):
            Figure.with_user(self.other_user).create({"profile_id": self.profile.id, "value": "1", "label": "x"})
        with self.assertRaises(AccessError):
            self.first.metric_ids.with_user(self.other_user).write({"value": "0"})
