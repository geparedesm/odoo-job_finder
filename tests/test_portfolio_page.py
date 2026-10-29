"""The public portfolio website page, its photo, and the CV download."""

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
class PortfolioPageTestCase(HttpCase):
    def setUp(self):
        super().setUp()
        self.profile = self.env["job.profile"].create({
            "user_id": self.env.ref("base.user_admin").id,
            **{name: EXPECTED[name] for name in ("full_name", "headline", "email", "phone", "location",
                                                 "linkedin", "website", "github", "summary")},
            "photo": PIXEL,
            "is_published_as_portfolio": True,
        })
        self.profile._set_structured_sections({name: EXPECTED[name] for name in SECTIONS})

    def page(self, path="/"):
        response = self.url_open(path)
        self.assertEqual(response.status_code, 200, path)
        return response.text

    def _portal_user(self):
        return self.env["res.users"].create({
            "name": "Portal Visitor", "login": "portal_visitor", "password": "portal_visitor",
            "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
        })

    def test_portfolio_is_the_website_homepage(self):
        self.assertEqual(self.env.ref("website.default_website").homepage_url, "/portfolio")
        text = self.page("/")
        self.assertIn('class="jf-name"', text)
        self.assertIn("Gabriel Paredes Mendoza", text)

    def test_sections_render_the_public_records(self):
        text = self.page("/portfolio")
        for expected in ("Software development", "Mechatronics", "Selected work", "Custom ERP modules",
                         "Ecuadorian Navy", "Dec 2021 – Jan 2025", "Duodata", "Experience",
                         "Research and academic projects", "Universidad Técnica del Norte",
                         "Passive exoskeleton development", "Skills", "Data &amp; infrastructure", "Education",
                         "ICT60220", "Training and credentials", "Forklift Licence (LF)", "Languages", "Native",
                         "Leadership and volunteering", "Vice Chair, IEEEXtreme Public Relations Committee",
                         "Contact", "gabrielparedesmendoza@gmail.com", 'src="/portfolio/photo"'):
            self.assertIn(expected, text)
        # Navigation lists the sections that have content.
        for anchor in ("#work", "#experience", "#skills", "#about", "#contact"):
            self.assertIn(f'href="/portfolio{anchor}"', text)
        # Featured projects link to their case-study pages.
        erp = self.profile.project_ids.filtered(lambda p: p.name == "Custom ERP modules")
        self.assertIn(f'href="{erp._get_portfolio_path()}"', text)

    def test_hidden_entries_and_phone_stay_private(self):
        role = self.profile.experience_ids.filtered(lambda e: e.company == "AJ Fencing Supplies")
        role.is_public = False
        self.profile.project_ids.filtered(lambda p: p.name == "Frecuento").is_public = False
        self.profile.volunteering_ids.write({"is_public": False})
        text = self.page("/portfolio")
        self.assertNotIn("AJ Fencing Supplies", text)
        self.assertNotIn("Frecuento", text)
        self.assertNotIn("Leadership and volunteering", text)
        self.assertNotIn("+61 415 530 419", text)
        self.profile.is_phone_public = True
        self.assertIn("+61 415 530 419", self.page("/portfolio"))

    def test_nothing_published_shows_an_empty_state(self):
        self.profile.is_published_as_portfolio = False
        text = self.page("/portfolio")
        self.assertIn("Portfolio coming soon", text)
        self.assertNotIn("Gabriel Paredes Mendoza", text)

    def test_text_is_escaped_and_unsafe_links_are_dropped(self):
        self.profile.project_ids[0].write({"name": "<script>alert(1)</script>", "url": "javascript:alert(1)"})
        self.profile.github = "javascript:alert('xss')"
        text = self.page("/portfolio")
        self.assertNotIn("<script>alert(1)</script>", text)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", text)
        self.assertNotIn("javascript:", text)

    def test_photo_is_public_only_for_the_published_profile(self):
        response = self.url_open("/portfolio/photo")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("image/"))
        self.profile.is_published_as_portfolio = False
        self.assertEqual(self.url_open("/portfolio/photo").status_code, 404)

    def test_seo_and_sharing_metadata(self):
        text = self.page("/portfolio")
        self.assertIn("<title>Gabriel Paredes Mendoza | Software development, ICT, Mechatronics</title>", text)
        self.assertEqual(self.profile.display_name, "Gabriel Paredes Mendoza")
        self.assertIn('<meta property="og:title" content="Gabriel Paredes Mendoza | Software development, ICT, Mechatronics"', text)
        self.assertIn('<meta name="description" content="Multidisciplinary professional', text)
        self.assertIn("/portfolio/photo", text.split('property="og:image"')[1][:200])
        self.profile.website_meta_title = "Gabriel — Developer portfolio"
        self.assertIn('content="Gabriel — Developer portfolio"', self.page("/portfolio"))

    def test_spanish_page(self):
        lang = self.env["res.lang"]._activate_lang("es_ES")
        self.env.ref("website.default_website").language_ids = [(4, lang.id)]
        self.env["ir.module.module"]._load_module_terms(["job_finder"], ["es_ES"], overwrite=True)
        text = self.page("/es/portfolio")
        for expected in ("Trabajo destacado", "Experiencia", "Contacto", "Descargar CV", "Nativo", "Iniciar sesión"):
            self.assertIn(expected, text)
        self.assertIn('hreflang="en"', text)

    def test_cv_asks_visitors_to_sign_in(self):
        text = self.page("/portfolio/cv")
        self.assertIn("Sign in to download the complete CV", text)
        self.assertIn('action="/web/login"', text)
        self.assertIn('name="redirect" value="/portfolio/cv"', text)
        self.assertIn('name="csrf_token"', text)
        self.assertIn("mailto:gabrielparedesmendoza@gmail.com?subject=CV%20request", text)
        self.assertNotIn("%PDF", text)
        # Visitors see a lock on the CV buttons.
        self.assertIn("fa-lock", self.page("/portfolio"))

    def test_navigation_button_opens_odoo(self):
        # Visitors sign in to Odoo; the CV buttons of the page stay.
        text = self.page("/portfolio")
        self.assertIn('href="/web/login"', text)
        self.assertIn("Log in", text)
        self.assertNotIn('href="/odoo"', text)
        self.assertIn('href="/portfolio/cv"', text)
        # Internal users open the backend.
        self.authenticate("admin", "admin")
        text = self.page("/portfolio")
        self.assertIn('href="/odoo"', text)
        self.assertIn("Open Odoo", text)
        self.assertNotIn('href="/web/login"', text)
        # Portal users have no backend: no button.
        self._portal_user()
        self.authenticate("portal_visitor", "portal_visitor")
        text = self.page("/portfolio")
        self.assertNotIn('href="/odoo"', text)
        self.assertNotIn('href="/web/login"', text)

    def test_cv_is_refused_to_portal_users(self):
        self._portal_user()
        self.authenticate("portal_visitor", "portal_visitor")
        response = self.url_open("/portfolio/cv", allow_redirects=False)
        self.assertEqual(response.status_code, 403)
        self.assertIn("The complete CV is not available for this account", response.text)
        self.assertNotIn("%PDF", response.text)

    def test_cv_download_for_internal_users(self):
        self.profile.full_name = 'Ana "QA"\r\nX-Injected: 1 / Test'
        self.authenticate("admin", "admin")
        response = self.url_open("/portfolio/cv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "application/pdf")
        self.assertNotIn("X-Injected", response.headers)
        self.assertIn("filename*=UTF-8''Ana%20QA%20X-Injected%201%20Test-cv.pdf",
                      response.headers.get("Content-Disposition", ""))
        self.profile.is_published_as_portfolio = False
        self.assertEqual(self.url_open("/portfolio/cv", allow_redirects=False).status_code, 404)

    def test_no_inline_script(self):
        view = self.env.ref("job_finder.portfolio_page")
        self.assertNotIn("<script", view.arch_db)
        self.assertNotIn("onclick", view.arch_db)
