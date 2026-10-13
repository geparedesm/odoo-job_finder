"""Check the guided form through Odoo's view loading API without a browser."""

import unittest

try:
    from odoo.tests import HttpCase, tagged
except ImportError:
    raise unittest.SkipTest("needs Odoo (--test-enable)")

from lxml import etree


@tagged("post_install", "-at_install")
class TestGuidedProfileForm(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create({
            "name": "Profile Form Reviewer",
            "login": "profile-form-reviewer",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

    def test_internal_user_loads_guided_form(self):
        views = self.env["job.profile"].with_user(self.user).with_context(
            lang="en_US",
        ).get_views([(self.env.ref("job_finder.view_form").id, "form")])
        form = etree.fromstring(views["views"]["form"]["arch"].encode())
        fields = views["models"]["job.profile"]["fields"]
        expected = [
            "summary", "skills", "experience", "volunteering", "projects",
            "education", "trainings", "certifications", "languages", "extra_info",
        ]
        self.assertEqual(
            form.xpath("./sheet/notebook/page/field/@name"), expected,
        )
        for field in expected:
            self.assertIn(field, fields)
            self.assertEqual(len(form.xpath(f".//field[@name='{field}']")), 1)
        sheet = form.find("sheet")
        self.assertEqual([node.get("name") for node in list(sheet)[:3]], [
            "cv_guidance", "contact_details", "cv_upload",
        ])
        self.assertIn("Upload your PDF CV", " ".join(sheet[0].itertext()))
        self.assertIn("Review the extracted details", " ".join(sheet[0].itertext()))
        self.assertEqual(form.xpath(
            ".//group[@name='professional_identity']/field/@name",
        ), ["full_name", "headline", "location"])
        self.assertEqual(form.xpath(
            ".//group[@name='contact_channels']/field/@name",
        ), ["email", "phone", "linkedin"])
        button = form.xpath(".//group[@name='cv_upload']/button")[0]
        self.assertEqual(button.get("name"), "action_parse_cv")
        self.assertEqual(button.get("type"), "object")
        self.assertEqual(button.get("invisible"), "not cv_file")
        self.assertEqual(form.xpath(".//field[@name='cv_file']/@filename"), ["cv_filename"])
        self.assertEqual(form.xpath(".//field[@name='cv_parsed_date']/@readonly"), ["True"])
        self.assertFalse(form.xpath(".//tree | .//*[@attrs] | .//*[@states] | .//script"))
