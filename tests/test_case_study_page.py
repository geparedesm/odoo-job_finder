"""The case-study pages of featured projects, their covers, and the redesigned portfolio sections."""

import base64
import json
from pathlib import Path
import unittest

try:
    from odoo.tests import HttpCase, tagged
except ImportError:
    raise unittest.SkipTest("Odoo not available") from None

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = json.loads((ROOT / "tests" / "fixtures" / "complete_cv_expected.json").read_text())
SECTIONS = ("experience", "projects", "skills", "education", "trainings", "volunteering", "languages")
# A 1x1 PNG: enough for an image field.
PIXEL = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360f8cfc0000003010100c9fe92ef0000000049454e44ae426082"))


@tagged("post_install", "-at_install")
class CaseStudyPageTestCase(HttpCase):
    def setUp(self):
        super().setUp()
        self.profile = self.env["job.profile"].create({
            "user_id": self.env.ref("base.user_admin").id,
            **{name: EXPECTED[name] for name in ("full_name", "headline", "email", "location", "summary")},
            "photo": PIXEL,
            "is_published_as_portfolio": True,
        })
        self.profile._set_structured_sections({name: EXPECTED[name] for name in SECTIONS})
        self.zkteco = self.profile.project_ids.filtered(lambda p: p.name.startswith("ZKTeco"))
        self.zkteco.write({
            "area": "Access control",
            "platforms": "Android · iOS · Web",
            "cover_image": PIXEL,
            "highlights": "Device protocol layer: Direct communication with the terminals.\nTests and CI/CD",
            "metric_ids": [(0, 0, {"value": "+40%", "label": "Operations per minute"}),
                           (0, 0, {"value": "90%", "label": "Flutter test coverage"})],
            "step_ids": [(0, 0, {"name": "ZKTeco terminals", "detail": "Fingerprint · face"}),
                         (0, 0, {"name": "Flutter app", "is_highlighted": True})],
        })

    def page(self, path):
        response = self.url_open(path)
        self.assertEqual(response.status_code, 200, path)
        return response.text

    def test_case_study_page_shows_the_project(self):
        text = self.page(self.zkteco._get_portfolio_path())
        for expected in ("ZKTeco biometric administration platform", "Access control", "Android · iOS · Web",
                         "Full Stack Developer", "Duodata", "Dec 2021 – Jan 2025", "+40%", "Operations per minute",
                         "Device protocol layer", "Direct communication with the terminals.", "Tests and CI/CD",
                         "ZKTeco terminals", "Fingerprint · face", "Flask", "Next case study",
                         f'src="/portfolio/project/{self.zkteco.id}/cover"', 'href="/portfolio#work"'):
            self.assertIn(expected, text)

    def test_case_study_sections_are_hidden_when_empty(self):
        erp = self.profile.project_ids.filtered(lambda p: p.name == "Custom ERP modules")
        text = self.page(erp._get_portfolio_path())
        self.assertIn("Custom ERP modules", text)
        for hidden in ("Key outcomes", "What I built", "Architecture", "/cover"):
            self.assertNotIn(hidden, text.split('class="jf-next"')[0])

    def test_long_architecture_fits_desktop_and_mobile(self):
        self.zkteco.step_ids.unlink()
        self.zkteco.write({"step_ids": [(0, 0, {
            "sequence": index,
            "name": name,
            "detail": "Location processing, device commands and notifications for connected GPS trackers.",
        }) for index, name in enumerate((
            "GPS devices", "API and TCP services", "AWS backend",
            "Firebase Realtime Database", "Flutter applications",
        ))]})
        for width in (1200, 1440, 390):
            with self.subTest(width=width):
                self.browser_size = f"{width}x900"
                self.browser_js(self.zkteco._get_portfolio_path(), """
                    const page = document.documentElement;
                    const flow = document.querySelector('.jf-flow');
                    if (flow.children.length !== 5) {
                        throw new Error('Expected all five architecture components');
                    }
                    if (page.scrollWidth > page.clientWidth + 1) {
                        throw new Error('The case study overflows the viewport');
                    }
                    for (const step of flow.children) {
                        if (step.getBoundingClientRect().right > page.clientWidth + 1 ||
                            step.scrollWidth > step.clientWidth + 1) {
                            throw new Error('Architecture content overflows its container');
                        }
                    }
                    console.log('test successful');
                """, ready="document.querySelector('.jf-flow')")

    def test_old_slug_redirects_to_the_current_one(self):
        response = self.url_open(f"/portfolio/project/old-name-{self.zkteco.id}", allow_redirects=False)
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.headers["Location"].endswith(self.zkteco._get_portfolio_path()))

    def test_only_featured_public_projects_of_the_published_profile_have_pages(self):
        path = self.zkteco._get_portfolio_path()
        self.zkteco.is_featured = False
        self.assertEqual(self.url_open(path).status_code, 404)
        self.zkteco.write({"is_featured": True, "is_public": False})
        self.assertEqual(self.url_open(path).status_code, 404)
        self.zkteco.is_public = True
        self.profile.is_published_as_portfolio = False
        self.assertEqual(self.url_open(path).status_code, 404)
        for invalid in ("/portfolio/project/nothing", "/portfolio/project/x-999999"):
            self.assertEqual(self.url_open(invalid).status_code, 404, invalid)

    def test_project_of_another_profile_has_no_page(self):
        user = self.env["res.users"].create({"name": "Other", "login": "other_case_study"})
        other = self.env["job.profile"].create({"user_id": user.id, "full_name": "Other"})
        project = self.env["job_finder.project"].create({
            "profile_id": other.id, "name": "Private", "is_featured": True, "cover_image": PIXEL})
        self.assertEqual(self.url_open(project._get_portfolio_path()).status_code, 404)
        self.assertEqual(self.url_open(f"/portfolio/project/{project.id}/cover").status_code, 404)

    def test_cover_is_public_only_for_published_case_studies(self):
        response = self.url_open(f"/portfolio/project/{self.zkteco.id}/cover")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("image/"))
        self.zkteco.is_public = False
        self.assertEqual(self.url_open(f"/portfolio/project/{self.zkteco.id}/cover").status_code, 404)
        erp = self.profile.project_ids.filtered(lambda p: p.name == "Custom ERP modules")
        self.assertEqual(self.url_open(f"/portfolio/project/{erp.id}/cover").status_code, 404)

    def test_case_study_text_is_escaped(self):
        self.zkteco.write({"highlights": "<b>bold</b>: <script>alert(1)</script>", "url": "javascript:alert(1)"})
        text = self.page(self.zkteco._get_portfolio_path())
        self.assertNotIn("<script>alert(1)</script>", text)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", text)
        self.assertNotIn("javascript:", text)

    def test_home_shows_the_redesigned_sections(self):
        self.profile.write({
            "availability_note": "Open to software roles",
            "work_heading": "Software that runs real operations.",
            "secondary_experience_title": "Production & hospitality",
            "figure_ids": [(0, 0, {"value": "55k+", "label": "App downloads"})],
        })
        text = self.page("/portfolio")
        for expected in ("Open to software roles · Perth, Australia", "Software that runs real operations.",
                         "55k+", "App downloads", "Production &amp; hospitality", "8 roles", "AJ Fencing Supplies",
                         "Show roles", "Access control", "Read case study", "Advanced Diploma of Information Technology · 2025"):
            self.assertIn(expected, text)
        # Secondary roles are not repeated in the main timeline.
        self.assertEqual(text.count("Fencing Production Operator"), 1)

    def test_empty_profile_sections_fall_back_to_their_names(self):
        text = self.page("/portfolio")
        self.assertIn("Other experience", text)
        self.assertIn("Let&#39;s work together.", text)

    def test_portfolio_templates_have_no_inline_script(self):
        views = self.env["ir.ui.view"].search([("key", "=like", "job_finder.%"), ("type", "=", "qweb")])
        self.assertTrue(views)
        for view in views:
            self.assertNotIn("<script", view.arch_db, view.key)
            self.assertNotIn("onclick", view.arch_db, view.key)
