"""Complete CV report coverage, freshness, form wiring, and access rules."""

import unittest

try:
    from odoo.tests import TransactionCase, tagged
except ImportError:
    raise unittest.SkipTest("needs Odoo (--test-enable)") from None

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
            "website": "https://candidate.com", "github": "https://github.com/candidate",
            "summary": "Updated professional summary",
        }
        cls.profile = cls.env["job.profile"].with_user(cls.user).create(cls.values)
        python = cls.env["job_finder.technology"].create({"name": "Python"})
        cls.role = cls.env["job_finder.experience"].with_user(cls.user).create({
            "profile_id": cls.profile.id, "role": "Data Engineer", "company": "Acme",
            "location": "Madrid", "employment_type": "full_time",
            "date_start": "2021-12-01", "date_end": "2025-01-01",
            "highlights": "Cut costs by 30%\nLed a team of four",
            "project_ids": [(0, 0, {"profile_id": cls.profile.id, "name": "Research prototype",
                                    "subtitle": "Internal lab", "technology_ids": [(6, 0, python.ids)],
                                    "description": "Built a prototype."})],
        })
        cls.env["job_finder.skill_group"].with_user(cls.user).create({
            "profile_id": cls.profile.id, "name": "Languages", "technology_ids": [(6, 0, python.ids)]})
        cls.env["job_finder.education"].with_user(cls.user).create({
            "profile_id": cls.profile.id, "qualification": "Engineering degree", "institution": "UTN",
            "year_start": 2014, "year_end": 2019, "status": "graduated"})
        cls.env["job_finder.training"].with_user(cls.user).create({
            "profile_id": cls.profile.id, "name": "Advanced workshop", "issuer": "Cisco", "year": 2016,
            "status": "not_renewed"})
        cls.env["job_finder.volunteering"].with_user(cls.user).create({
            "profile_id": cls.profile.id, "title": "Community mentoring", "organisation": "IEEE",
            "recognitions": "President, RAS chapter"})
        cls.env["job_finder.spoken_language"].with_user(cls.user).create({
            "profile_id": cls.profile.id, "name": "English", "level": "b2"})
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
        self.assertEqual(buttons[0].get("name"), str(self.env.ref("job_finder.action_job_finder_cv_download").id))
        self.assertEqual(self.report.paperformat_id, self.env.ref("job_finder.paperformat_cv"))
        action = self.report.with_user(self.user).report_action(self.profile)
        self.assertEqual(action["report_name"], self.report.report_name)
        self.assertEqual(action["report_type"], "qweb-pdf")
        self.assertEqual(action["context"]["active_ids"], self.profile.ids)

    def test_all_professional_fields_and_latest_edits_are_rendered(self):
        html = self.render_html(self.user)
        text = "".join(etree.HTML(html).itertext())
        for value in ("Report Candidate", "Research Engineer", "candidate@example.com", "+34 600 111 222", "Madrid",
                      "linkedin.com/in/candidate", "candidate.com", "github.com/candidate",
                      "Updated professional summary"):
            self.assertIn(value, text)
        for href in ('href="mailto:candidate@example.com"', 'href="tel:+34600111222"',
                     'href="https://linkedin.com/in/candidate"', 'href="https://github.com/candidate"'):
            self.assertIn(href, html)
        for expected in ("Professional summary", "Skills", "Experience", "Education", "Certifications and training",
                         "Leadership and volunteering", "Languages", "Data Engineer", "Acme", "Dec 2021 – Jan 2025",
                         "Full-time", "Cut costs by 30%", "Led a team of four", "Research prototype", "Internal lab",
                         "Technologies: Python", "Languages: Python", "Engineering degree", "2014 – 2019", "Graduated",
                         "Advanced workshop", "Not renewed", "Community mentoring", "President, RAS chapter",
                         "English", "B2 · Upper intermediate"):
            self.assertIn(expected, text)
        # The CV is text for ATS parsers: no images and no layout tables.
        self.assertNotIn("<img", html.split('class="page jf-cv"')[1])
        self.assertNotIn("<table", html.split('class="page jf-cv"')[1])
        self.role.project_ids.write({"name": "New project after parsing <script>"})
        html = self.render_html(self.user)
        self.assertIn("New project after parsing &lt;script&gt;", html)
        self.assertNotIn("Research prototype", html)

    def test_hidden_entries_stay_in_the_complete_cv(self):
        self.role.is_public = False
        self.assertIn("Data Engineer", self.render_html(self.user))

    def test_empty_sections_and_no_upload(self):
        self.assertFalse(self.profile.cv_file)
        self.profile.training_ids.unlink()
        self.profile.experience_ids.unlink()
        html = self.render_html(self.user)
        self.assertNotIn("<h2>Certifications and training</h2>", html)
        self.assertNotIn("<h2>Experience</h2>", html)
        self.assertNotIn("False", html)
        self.assertIn("Report Candidate", html)

    def test_other_users_profile_cannot_be_rendered(self):
        with self.assertRaises(AccessError):
            self.render_html(self.other)
