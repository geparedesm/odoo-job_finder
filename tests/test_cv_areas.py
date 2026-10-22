"""CVs for some areas of a profile: their content, the download wizard, the PDF, access, and the portfolio."""

import unittest

try:
    from odoo.exceptions import AccessError, ValidationError
    from odoo.tests import HttpCase, TransactionCase, tagged
except ImportError:
    raise unittest.SkipTest("Odoo not available")

from lxml import etree


def make_profile(env, user):
    """A profile with Backend, Frontend and Hospitality areas and entries tagged with them."""
    profile = env["job.profile"].create({
        "user_id": user.id, "full_name": "Area Candidate", "headline": "SOFTWARE DEVELOPMENT | HOSPITALITY",
        "email": "areas@example.com", "summary": "General summary.",
    })
    backend, frontend, hospitality = env["job_finder.cv_area"].create([
        {"profile_id": profile.id, "name": "Backend", "headline": "Backend Developer",
         "summary": "Backend summary."},
        {"profile_id": profile.id, "name": "Frontend", "headline": "Frontend Developer"},
        {"profile_id": profile.id, "name": "Hospitality", "headline": "Bartender"},
    ])
    developer = env["job_finder.experience"].create({
        "profile_id": profile.id, "role": "Full Stack Developer", "company": "Duodata",
        "cv_area_ids": [(6, 0, (backend | frontend).ids)],
        "project_ids": [
            (0, 0, {"profile_id": profile.id, "name": "General project"}),
            (0, 0, {"profile_id": profile.id, "name": "Frontend app", "cv_area_ids": [(6, 0, frontend.ids)]}),
        ],
    })
    bartender = env["job_finder.experience"].create({
        "profile_id": profile.id, "role": "Bartender", "company": "The Knock",
        "cv_area_ids": [(6, 0, hospitality.ids)],
        "project_ids": [(0, 0, {"profile_id": profile.id, "name": "Event app",
                                "cv_area_ids": [(6, 0, backend.ids)]})],
    })
    env["job_finder.skill_group"].create([
        {"profile_id": profile.id, "name": "APIs", "cv_area_ids": [(6, 0, backend.ids)]},
        {"profile_id": profile.id, "name": "Cocktails", "cv_area_ids": [(6, 0, hospitality.ids)]},
        {"profile_id": profile.id, "name": "Tools"},
    ])
    env["job_finder.training"].create([
        {"profile_id": profile.id, "name": "RSA", "cv_area_ids": [(6, 0, hospitality.ids)]},
        {"profile_id": profile.id, "name": "CCNA"},
    ])
    env["job_finder.education"].create({"profile_id": profile.id, "qualification": "Diploma of IT"})
    env["job_finder.spoken_language"].create({"profile_id": profile.id, "name": "English", "level": "b2"})
    return profile, backend, frontend, hospitality, developer, bartender


@tagged("post_install", "-at_install")
class CvAreasTestCase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.user = self.env["res.users"].create({
            "name": "Area Owner", "login": "area_owner",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        self.other = self.env["res.users"].create({
            "name": "Area Other", "login": "area_other",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        (self.profile, self.backend, self.frontend, self.hospitality,
         self.developer, self.bartender) = make_profile(self.env, self.user)

    def names(self, values, key):
        return [entry["name"] if "name" in entry else entry["title"] for entry in values[key]]

    def test_complete_cv_has_every_entry(self):
        values = self.profile._get_cv_values()
        self.assertEqual(self.names(values, "roles"), ["Full Stack Developer", "Bartender"])
        self.assertEqual([p["name"] for p in values["roles"][0]["projects"]], ["General project", "Frontend app"])
        self.assertEqual(self.names(values, "skills"), ["APIs", "Cocktails", "Tools"])
        self.assertEqual(self.names(values, "trainings"), ["RSA", "CCNA"])
        self.assertEqual(values["headline"], "Software development · Hospitality")
        self.assertEqual(values["summary_paragraphs"], ["General summary."])
        self.assertEqual(values["areas"], [])

    def test_cv_for_one_area(self):
        values = self.profile._get_cv_values(self.backend)
        # The tagged project of the hospitality role brings its role, with only that project.
        self.assertEqual(self.names(values, "roles"), ["Full Stack Developer", "Bartender"])
        self.assertEqual([p["name"] for p in values["roles"][0]["projects"]], ["General project"])
        self.assertEqual([p["name"] for p in values["roles"][1]["projects"]], ["Event app"])
        self.assertEqual(self.names(values, "skills"), ["APIs", "Tools"])
        self.assertEqual(self.names(values, "trainings"), ["CCNA"])
        self.assertEqual([entry["qualification"] for entry in values["education"]], ["Diploma of IT"])
        self.assertEqual(self.names(values, "languages"), ["English"])
        self.assertEqual((values["headline"], values["summary_paragraphs"]), ("Backend Developer", ["Backend summary."]))
        self.assertEqual(values["areas"], ["Backend"])

    def test_cv_for_several_areas(self):
        values = self.profile._get_cv_values(self.backend | self.frontend)
        self.assertEqual([p["name"] for p in values["roles"][0]["projects"]], ["General project", "Frontend app"])
        self.assertEqual(values["headline"], "Backend Developer · Frontend Developer")
        hospitality = self.profile._get_cv_values(self.hospitality)
        self.assertEqual(self.names(hospitality, "roles"), ["Bartender"])
        self.assertEqual(hospitality["roles"][0]["projects"], [])
        self.assertEqual(self.names(hospitality, "skills"), ["Cocktails", "Tools"])
        self.assertEqual(hospitality["summary_paragraphs"], ["General summary."])

    def test_areas_of_another_profile_are_ignored_and_refused(self):
        other_profile, other_backend, *_ = make_profile(self.env, self.other)
        self.assertEqual(self.profile._get_cv_values(other_backend)["areas"], [])
        with self.assertRaises(ValidationError):
            self.developer.cv_area_ids = [(4, other_backend.id)]
        with self.assertRaises(AccessError):
            self.backend.with_user(self.other).read(["name"])
        self.assertFalse(self.env["job_finder.cv_area"].with_user(self.other).search([("id", "=", self.backend.id)]))

    def test_wizard_downloads_the_cv_of_the_chosen_areas(self):
        other_profile, other_backend, *_ = make_profile(self.env, self.other)
        wizard = self.env["job_finder.cv_download"].with_user(self.user).create({
            "profile_id": self.profile.id, "area_ids": [(6, 0, self.backend.ids)],
        })
        action = wizard.action_download()
        self.assertEqual(action["report_name"], "job_finder.report_job_profile")
        self.assertEqual(action["data"], {"area_ids": self.backend.ids})
        # Another profile's areas never reach the report.
        wizard.sudo().area_ids = [(6, 0, (self.backend | other_backend).ids)]
        self.assertEqual(wizard.action_download()["data"], {"area_ids": self.backend.ids})

    def test_pdf_report_uses_the_areas_of_its_data(self):
        report = self.env.ref("job_finder.action_report_job_profile").with_user(self.user).with_context(lang="en_US")
        html, _kind = report._render_qweb_html(report.report_name, self.profile.ids,
                                               data={"area_ids": self.hospitality.ids})
        text = "".join(etree.HTML(html.decode()).itertext())
        for expected in ("Bartender", "The Knock", "Cocktails", "RSA", "Diploma of IT", "English"):
            self.assertIn(expected, text)
        for hidden in ("Full Stack Developer", "APIs", "Frontend app"):
            self.assertNotIn(hidden, text)
        complete, _kind = report._render_qweb_html(report.report_name, self.profile.ids)
        self.assertIn("Full Stack Developer", complete.decode())


@tagged("post_install", "-at_install")
class CvAreasPortfolioTestCase(HttpCase):
    def setUp(self):
        super().setUp()
        self.profile, self.backend, self.frontend, *_ = make_profile(self.env, self.env.ref("base.user_admin"))
        self.profile.is_published_as_portfolio = True

    def test_internal_users_choose_the_cv(self):
        self.authenticate("admin", "admin")
        response = self.url_open("/portfolio/cv")
        self.assertEqual(response.status_code, 200)
        for expected in ("Choose your CV", "Backend", "Frontend Developer", 'name="area"', "/portfolio/cv?download=1"):
            self.assertIn(expected, response.text)
        response = self.url_open(f"/portfolio/cv?download=1&area={self.backend.id}&area={self.frontend.id}&area=x")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "application/pdf")
        self.assertIn("Area%20Candidate%20Backend%20Frontend-cv.pdf", response.headers.get("Content-Disposition", ""))
        response = self.url_open("/portfolio/cv?download=1")
        self.assertIn("Area%20Candidate-cv.pdf", response.headers.get("Content-Disposition", ""))

    def test_visitors_still_sign_in_first(self):
        response = self.url_open("/portfolio/cv?download=1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sign in to download the complete CV", response.text)
        self.assertNotIn("Choose your CV", response.text)
