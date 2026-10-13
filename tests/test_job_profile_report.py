"""Complete CV report coverage, freshness, form wiring, and access rules."""

import unittest

try:
    from odoo.tests import TransactionCase, tagged
except ImportError:
    raise unittest.SkipTest("needs Odoo (--test-enable)")

from lxml import etree
from odoo.exceptions import AccessError


@tagged("post_install", "-at_install")
class TestJobProfileReport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create({
            "name": "CV Report Owner", "login": "cv-report-owner",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.other = cls.env["res.users"].create({
            "name": "CV Report Other", "login": "cv-report-other",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.values = {
            "full_name": "Report Candidate", "headline": "Research Engineer",
            "email": "candidate@example.com", "phone": "+34 600 111 222",
            "location": "Madrid", "linkedin": "https://linkedin.com/in/candidate",
            "summary": "Updated professional summary", "skills": "Python\nSQL",
            "experience": "Industry experience", "education": "Engineering degree",
            "volunteering": "Community mentoring", "projects": "Research prototype",
            "trainings": "Advanced workshop", "certifications": "Professional credential",
            "languages": "English and Spanish", "extra_info": "Available for remote work",
        }
        cls.profile = cls.env["job.profile"].with_user(cls.user).create(cls.values)
        cls.report = cls.env.ref("job_finder.action_report_job_profile")

    def render_html(self, user, ids=None):
        content, kind = self.report.with_user(user).with_context(lang="en_US")._render_qweb_html(
            self.report.report_name, ids or self.profile.ids,
        )
        self.assertEqual(kind, "html")
        return content.decode()

    def test_report_action_and_header_button(self):
        self.assertEqual(self.report.model, "job.profile")
        self.assertEqual(self.report.report_type, "qweb-pdf")
        self.assertEqual(self.report.binding_model_id.model, "job.profile")
        self.assertFalse(self.report.attachment_use)
        view = self.env["job.profile"].with_user(self.user).get_view(
            self.env.ref("job_finder.view_form").id, "form",
        )
        form = etree.fromstring(view["arch"].encode())
        buttons = form.xpath("./header/button[@type='action']")
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].get("name"), str(self.report.id))
        action = self.report.with_user(self.user).report_action(self.profile)
        self.assertEqual(action["report_name"], self.report.report_name)
        self.assertEqual(action["report_type"], "qweb-pdf")
        self.assertEqual(action["context"]["active_ids"], self.profile.ids)

    def test_all_professional_fields_and_latest_edits_are_rendered(self):
        html = self.render_html(self.user)
        text = "".join(etree.HTML(html).itertext())
        for value in self.values.values():
            self.assertIn(value, text)
        self.profile.write({"projects": "New project after parsing <script>"})
        html = self.render_html(self.user)
        self.assertIn("New project after parsing &lt;script&gt;", html)
        self.assertNotIn("Research prototype", html)
        self.assertIn("white-space: pre-wrap", html)

    def test_empty_sections_and_no_upload(self):
        self.assertFalse(self.profile.cv_file)
        self.profile.write({"trainings": False, "extra_info": False})
        html = self.render_html(self.user)
        self.assertNotIn("<h2>Trainings</h2>", html)
        self.assertNotIn("<h2>Additional information</h2>", html)
        self.assertNotIn("False", html)
        self.assertIn("Report Candidate", html)

    def test_other_users_profile_cannot_be_rendered(self):
        with self.assertRaises(AccessError):
            self.render_html(self.other)
