"""Profile actions, access, views and uniqueness in Odoo; skipped by plain unittest."""

import base64
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from odoo.tests import TransactionCase, tagged
except ImportError:  # plain `python -m unittest`: these need Odoo
    raise unittest.SkipTest("needs a running Odoo (--test-enable)")

from psycopg2 import IntegrityError

from odoo.tools import mute_logger
from odoo.exceptions import AccessError


@tagged("post_install", "-at_install")
class TestProfileScreen(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        internal = [(6, 0, [cls.env.ref("base.group_user").id])]
        cls.user = cls.env["res.users"].create({"name": "Job Seeker", "login": "job-seeker", "group_ids": internal})
        cls.other = cls.env["res.users"].create({"name": "Other Seeker", "login": "other-seeker", "group_ids": internal})

    def test_parse_cv_writes_new_sections_and_preserves_empty_values(self):
        profile = self.env["job.profile"].with_user(self.user).create({
            "cv_file": base64.b64encode(b"Invalid PDF"),
            "projects": "Existing project",
        })
        with patch(
            "odoo.addons.job_finder.models.job_profile.parse_cv_text",
            return_value={
                "volunteering": "Mentoring", "projects": "", "trainings": "Workshop",
                "user_id": self.other.id,
                "cv_filename": "Injected filename", "unexpected_field": "Rejected",
            },
        ):
            profile.action_parse_cv()
        self.assertEqual(profile.volunteering, "Mentoring")
        self.assertEqual(profile.projects, "Existing project")
        self.assertEqual(profile.trainings, "Workshop")
        self.assertEqual(profile.user_id, self.user)
        self.assertFalse(profile.cv_filename)

    def test_reference_cv_persists_complete_fields(self):
        # Text extracted with pypdf from Gabriel_Paredes_CV_completo.pdf.
        fixtures = Path(__file__).parent / "fixtures"
        text = (fixtures / "gabriel_paredes_cv.txt").read_text()
        expected = json.loads((fixtures / "gabriel_paredes_fields.json").read_text())
        profile = self.env["job.profile"].with_user(self.user).create({
            "cv_file": base64.b64encode(b"Reference PDF"),
            "cv_filename": "reference.pdf",
        })
        pages = [SimpleNamespace(extract_text=lambda value=page: value)
                 for page in text.split("\f")]
        with patch("pypdf.PdfReader", return_value=SimpleNamespace(pages=pages)):
            profile.action_parse_cv()
        profile.flush_recordset()
        profile.invalidate_recordset()
        for field, value in expected.items():
            with self.subTest(field=field):
                self.assertEqual(profile[field], value)
        self.assertEqual(profile.cv_raw_text, "\n".join(text.split("\f")))
        self.assertTrue(profile.cv_parsed_date)
        self.assertEqual(profile.user_id, self.user)
        self.assertEqual(profile.cv_filename, "reference.pdf")

    def test_empty_parsed_fields_preserve_saved_profile(self):
        fields = ("linkedin", "languages", "trainings",
                  "volunteering", "projects", "education", "experience")
        profile = self.env["job.profile"].with_user(self.user).create({
            "cv_file": base64.b64encode(b"Partial PDF"),
            **{field: "Existing " + field for field in fields},
        })
        page = SimpleNamespace(extract_text=lambda: "TECHNICAL SKILLS\nLanguages: Dart, Python.")
        with patch("pypdf.PdfReader", return_value=SimpleNamespace(pages=[page])):
            profile.action_parse_cv()
        profile.flush_recordset()
        profile.invalidate_recordset()
        self.assertEqual(profile.skills, "Languages: Dart, Python.")
        for field in fields:
            with self.subTest(field=field):
                self.assertEqual(profile[field], "Existing " + field)

    def test_user_uniq_rejects_a_second_profile_for_the_same_user(self):
        profiles = self.env["job.profile"]
        profile = profiles.create({"user_id": self.user.id})
        self.env.flush_all()
        # Roll back the rejected insert before checking the surviving profile.
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            profiles.create({"user_id": self.user.id})
            self.env.flush_all()
        self.assertEqual(profiles.search([("user_id", "=", self.user.id)]), profile)

    def test_user_uniq_allows_profiles_for_distinct_users(self):
        profiles = self.env["job.profile"]
        mine = profiles.create({"user_id": self.user.id})
        other = profiles.create({"user_id": self.other.id})
        self.env.flush_all()
        self.assertNotEqual(mine.id, other.id)
        self.assertEqual(mine.user_id, self.user)
        self.assertEqual(other.user_id, self.other)

    def open_profile(self, user):
        return self.env.ref("job_finder.action_open_my_profile").with_user(user).run()

    def test_menu_opens_the_users_own_profile_form(self):
        menu = self.env.ref("job_finder.menu_my_profile")
        self.assertTrue(self.env["ir.ui.menu"].with_user(self.user).search([("id", "=", menu.id)]))
        action = self.open_profile(self.user)
        self.assertEqual((action["res_model"], action["views"]), ("job.profile", [(False, "form")]))
        self.assertEqual(self.env["job.profile"].browse(action["res_id"]).user_id, self.user)
        self.assertEqual(self.open_profile(self.user)["res_id"], action["res_id"])  # opened again: the same profile

    def test_internal_users_see_only_their_own_profile(self):
        mine = self.open_profile(self.user)["res_id"]
        self.open_profile(self.other)
        self.assertEqual(self.env["job.profile"].with_user(self.user).search([]).ids, [mine])

    def test_form_view_loads_for_an_internal_user(self):
        views = self.env["job.profile"].with_user(self.user).get_views([(False, "form")])
        self.assertIn("cv_file", views["models"]["job.profile"]["fields"])

    def test_real_six_page_pdf_saves_every_field_and_preserves_on_empty(self):
        import pypdf

        fixtures = Path(__file__).parent / "fixtures"
        pdf = (fixtures / "Gabriel_Paredes_CV_completo.pdf").read_bytes()
        expected = json.loads((fixtures / "complete_cv_expected.json").read_text())
        profile = self.env["job.profile"].with_user(self.user).create({
            "cv_file": base64.b64encode(pdf),
        })
        profile.action_parse_cv()
        for field, value in expected.items():
            with self.subTest(field=field):
                self.assertEqual(profile[field], value)
        self.assertEqual(len(pypdf.PdfReader(fixtures / "Gabriel_Paredes_CV_completo.pdf").pages), 6)
        self.assertEqual(profile.cv_raw_text, (fixtures / "complete_cv.txt").read_text())
        self.assertTrue(profile.cv_parsed_date)
        blank_pdf = BytesIO()
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=595, height=842)
        writer.write(blank_pdf)
        for upload in (blank_pdf.getvalue(), b"Invalid PDF", b""):
            profile.cv_file = base64.b64encode(upload)
            profile.action_parse_cv()
            for field, value in expected.items():
                with self.subTest(upload=upload, field=field):
                    self.assertEqual(profile[field], value)

    def test_parse_cv_cannot_write_another_users_profile(self):
        fixtures = Path(__file__).parent / "fixtures"
        profile = self.env["job.profile"].with_user(self.other).create({
            "cv_file": base64.b64encode(
                (fixtures / "Gabriel_Paredes_CV_completo.pdf").read_bytes()
            ),
        })
        with self.assertRaises(AccessError):
            profile.with_user(self.user).action_parse_cv()
