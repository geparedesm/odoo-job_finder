"""Check the structured profile form through Odoo's view loading API without a browser."""

import unittest

try:
    from odoo.tests import HttpCase, tagged
except ImportError:
    raise unittest.SkipTest("needs Odoo (--test-enable)")

from lxml import etree


@tagged("post_install", "-at_install")
class TestStructuredProfileForm(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create({
            "name": "Profile Form Reviewer",
            "login": "profile-form-reviewer",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

    def _form(self, user):
        views = self.env["job.profile"].with_user(user).with_context(lang="en_US").get_views(
            [(self.env.ref("job_finder.view_form").id, "form")])
        return etree.fromstring(views["views"]["form"]["arch"].encode()), views["models"]

    def test_tabs_edit_records_instead_of_text(self):
        form, models = self._form(self.user)
        pages = form.xpath("./sheet/notebook/page/@name")
        self.assertEqual(pages, ["summary", "experience", "projects", "skills", "education", "trainings",
                                 "volunteering", "languages", "cv_import"])
        for name in ("experience_ids", "project_ids", "skill_group_ids", "education_ids", "training_ids",
                     "volunteering_ids", "spoken_language_ids"):
            [field] = form.xpath(f"./sheet/notebook/page/field[@name='{name}']")
            self.assertEqual(field.xpath("./list/field[@name='sequence']/@widget"), ["handle"], name)
            self.assertEqual(field.get("context"), "{'default_profile_id': id}")
        # Roles and volunteering open a dialog; the other lists are edited inline.
        self.assertFalse(form.xpath("//field[@name='experience_ids']/list/@editable"))
        self.assertEqual(form.xpath("//field[@name='spoken_language_ids']/list/@editable"), ["bottom"])
        for model in ("job_finder.experience", "job_finder.project", "job_finder.spoken_language"):
            self.assertIn(model, models)

    def test_header_identity_completeness_and_cv_import(self):
        form, _models = self._form(self.user)
        self.assertEqual(form.xpath("./sheet/field[@name='photo']/@widget"), ["image"])
        self.assertEqual(form.xpath("//div[@name='identity']//field/@name"), ["full_name", "headline"])
        self.assertEqual(form.xpath("//field[@name='completeness']/@widget"), ["progressbar"])
        [button] = form.xpath("./header/button[@name='action_parse_cv']")
        self.assertEqual((button.get("type"), button.get("invisible")), ("object", "not cv_file"))
        self.assertTrue(button.get("confirm"))
        guidance = " ".join(form.xpath("//div[@name='cv_guidance']")[0].itertext())
        self.assertIn("Analyze CV", guidance)
        self.assertEqual(form.xpath(".//field[@name='cv_file']/@filename"), ["cv_filename"])
        imported = form.xpath("//group[@name='imported_text']/field/@name")
        self.assertEqual(sorted(imported), sorted(["experience", "projects", "skills", "education", "trainings",
                                                   "volunteering", "languages"]))

    def test_publish_toggle_only_for_administrators(self):
        form, _models = self._form(self.user)
        self.assertFalse(form.xpath("//field[@name='is_published_as_portfolio']"))
        form, _models = self._form(self.env.ref("base.user_admin"))
        self.assertEqual(form.xpath("//field[@name='is_published_as_portfolio']/@widget"), ["boolean_toggle"])

    def test_role_dialog_lists_its_projects(self):
        views = self.env["job_finder.experience"].with_user(self.user).get_views(
            [(self.env.ref("job_finder.view_job_finder_experience_form").id, "form")])
        form = etree.fromstring(views["views"]["form"]["arch"].encode())
        self.assertEqual(form.xpath("//field[@name='date_end']/@invisible"), ["is_current"])
        self.assertEqual(form.xpath("//field[@name='project_ids']/@context"), ["{'default_profile_id': profile_id}"])
        self.assertEqual(form.xpath("//field[@name='project_ids']/list/field[@name='is_featured']/@widget"),
                         ["boolean_favorite"])
