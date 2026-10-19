"""Tests for the public portfolio page and CV download."""

import unittest

try:
    from lxml import etree
    from odoo.tests import HttpCase, tagged
except ImportError:
    raise unittest.SkipTest("Odoo not available")


@tagged("post_install", "-at_install")
class PortfolioPageTestCase(HttpCase):
    """Test the public portfolio page with HttpCase."""

    def setUp(self):
        super().setUp()
        # Create a published profile
        self.profile = self.env["job.profile"].create({
            "user_id": self.env.ref("base.user_admin").id,
            "full_name": "Gabriel Paredes",
            "headline": "Systems Developer",
            "location": "San Francisco, CA",
            "email": "gabriel@example.com",
            "phone": "+1 555 1234",
            "linkedin": "https://linkedin.com/in/gabriel",
            "github": "https://github.com/gabriel",
            "website": "example.com",
            "summary": "I am a passionate developer.",
            "skills": "Python\nJavaScript\nRust",
            "projects": "Portfolio Site\nTechnologies: React, Django\nBuilt a modern portfolio",
            "experience": "Senior Dev\nAcme Corp, 2021-2023\nLed a team of 5",
            "education": "BS Computer Science\nUniversity of Tech, 2019",
            "languages": "English\nSpanish",
            "is_published_as_portfolio": True,
        })

    def test_portfolio_page_configured_host_desktop(self):
        """GET / with configured host returns portfolio page (desktop)."""
        response = self.url_open(
            "/",
            headers={"Host": "gp-developer.com"},
        )
        self.assertEqual(response.status_code, 200)
        # Check for profile-specific content (not hardcoded Gabriel text)
        self.assertIn("Systems Developer", response.text)  # Dynamic headline
        self.assertIn("Gabriel Paredes", response.text)  # Dynamic name

    def test_portfolio_page_configured_host_www(self):
        """GET / with www.gp-developer.com returns portfolio page."""
        response = self.url_open(
            "/",
            headers={"Host": "www.gp-developer.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Systems Developer", response.text)

    def test_portfolio_page_case_insensitive(self):
        """Host matching is case-insensitive."""
        response = self.url_open(
            "/",
            headers={"Host": "GP-DEVELOPER.COM"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Systems Developer", response.text)

    def test_portfolio_page_ignores_port(self):
        """Port in Host header is ignored for matching."""
        response = self.url_open(
            "/",
            headers={"Host": "gp-developer.com:8080"},
        )
        self.assertEqual(response.status_code, 200)

    def test_portfolio_page_non_configured_host_fallback(self):
        """GET / with non-configured host returns standard Odoo behavior (not portfolio)."""
        response = self.url_open(
            "/",
            headers={"Host": "localhost:8000"},
        )
        # Should not show the portfolio-specific content (hero with headline)
        # The portfolio content includes the published profile name and headline
        self.assertNotIn("Gabriel Paredes", response.text)

    def test_portfolio_page_content_inclusion(self):
        """Portfolio page includes all published profile sections."""
        response = self.url_open(
            "/",
            headers={"Host": "gp-developer.com"},
        )
        text = response.text
        # Profile data should be present
        self.assertIn("Gabriel Paredes", text)  # Name
        self.assertIn("Systems Developer", text)  # Headline
        self.assertIn("San Francisco, CA", text)  # Location
        self.assertIn("I am a passionate developer", text)  # Summary
        # Skills should be parsed and shown as items
        self.assertIn("Python", text)

    def test_portfolio_page_phone_hidden(self):
        """Phone number never appears in anonymous HTML."""
        response = self.url_open(
            "/",
            headers={"Host": "gp-developer.com"},
        )
        # Phone should not appear
        self.assertNotIn("+1 555 1234", response.text)

    def test_portfolio_page_login_button_visible(self):
        """Login button is always visible to anonymous visitors."""
        response = self.url_open(
            "/",
            headers={"Host": "gp-developer.com"},
        )
        text = response.text
        self.assertIn("/web/login", text)  # Login link present
        self.assertIn("redirect=/", text)  # Redirect back to portfolio

    def test_portfolio_page_download_cv_hidden_anonymous(self):
        """Download CV button is hidden for anonymous visitors."""
        response = self.url_open(
            "/",
            headers={"Host": "gp-developer.com"},
        )
        # Download CV should not be shown
        self.assertNotIn("Download CV", response.text)
        self.assertNotIn("/portfolio/cv", response.text)
        self.assertIn('href="#projects" class="btn-discover"', response.text)

    def test_portfolio_page_download_cv_logged_in_http(self):
        """A logged-in visitor gets Download CV in the rendered hero and Open app instead of Login."""
        # The test server is reached as 127.0.0.1; serving the portfolio there keeps the session cookie valid
        # (HttpCase drops the authenticated session when a request overrides the Host header).
        self.env["ir.config_parameter"].set_param("job_finder.portfolio_hosts", "gp-developer.com,127.0.0.1")
        self.authenticate("admin", "admin")
        text = self.url_open("/").text
        start = text.index('class="portfolio-hero"')
        hero = text[start:text.index("</section>", start)]
        self.assertIn('href="/portfolio/cv"', hero)
        self.assertIn("Discover the work", hero)
        self.assertIn("btn-open-app", text)
        self.assertNotIn("btn-login", text)

    def test_portfolio_page_download_cv_in_hero(self):
        """The hero holds Discover the work and, for logged-in visitors only, Download CV."""
        arch = etree.fromstring(self.env.ref("job_finder.portfolio_page").arch)
        actions = arch.xpath("//section[@id='home']//div[@class='hero-actions']")
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].xpath("a[@class='btn-discover']/@href"), ["#projects"])
        cv = actions[0].xpath("t[@t-if='request.session.uid']/a[@href='/portfolio/cv']")
        self.assertEqual(len(cv), 1)
        # HttpCase does not carry an authenticated session into requests that override the Host header, so the
        # logged-in branch is checked on the arch; the anonymous rendering is covered by the HTTP tests above.

    def test_portfolio_page_empty_state(self):
        """When no profile is published, shows empty state."""
        self.profile.is_published_as_portfolio = False
        response = self.url_open(
            "/",
            headers={"Host": "gp-developer.com"},
        )
        self.assertEqual(response.status_code, 200)
        text = response.text
        # Should show coming soon message
        self.assertTrue(
            "Coming Soon" in text or "coming soon" in text.lower(),
            "Empty state message not found"
        )
        # Login button should still be visible
        self.assertIn("/web/login", text)

    def test_portfolio_cv_anonymous_redirect(self):
        """GET /portfolio/cv without session redirects to login."""
        response = self.url_open("/portfolio/cv", allow_redirects=False)
        # Should be a redirect to login
        self.assertEqual(response.status_code, 303)  # or 302
        self.assertIn("/web/login", response.headers.get("Location", ""))

    def test_portfolio_cv_authenticated_returns_pdf(self):
        """GET /portfolio/cv with session returns PDF."""
        self.authenticate("admin", "admin")
        response = self.url_open(
            "/portfolio/cv",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "application/pdf")

    def test_portfolio_cv_filename_is_sanitized(self):
        """Quotes and line breaks in the profile name cannot break the download header."""
        self.profile.full_name = 'Ana "QA"\r\nX-Injected: 1 / Test'
        self.authenticate("admin", "admin")
        response = self.url_open("/portfolio/cv")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("X-Injected", response.headers)
        disposition = response.headers.get("Content-Disposition", "")
        self.assertIn("attachment", disposition)
        self.assertIn("filename*=UTF-8''Ana%20QA%20X-Injected%201%20Test-cv.pdf", disposition)
        self.assertNotIn('"QA"', disposition)

    def test_portfolio_cv_not_found_when_nothing_published(self):
        """GET /portfolio/cv returns 404 when nothing is published."""
        self.authenticate("admin", "admin")
        self.profile.is_published_as_portfolio = False
        response = self.url_open("/portfolio/cv", allow_redirects=False)
        self.assertEqual(response.status_code, 404)

    def test_portfolio_page_language_selector_en(self):
        """Language selector shows EN as active."""
        response = self.url_open(
            "/?lang=en_US",
            headers={"Host": "gp-developer.com"},
        )
        text = response.text
        # Should have aria-current="page" on EN link
        self.assertIn("aria-current", text)

    def _load_spanish(self):
        self.env["res.lang"]._activate_lang("es_ES")
        self.env["ir.module.module"]._load_module_terms(["job_finder"], ["es_ES"], overwrite=True)

    def test_portfolio_page_language_selector_es(self):
        """?lang=es_ES renders the fixed texts in Spanish and stores the choice in a cookie."""
        self._load_spanish()
        response = self.url_open("/?lang=es_ES", headers={"Host": "gp-developer.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sitio web", response.text)
        self.assertIn("Todos los derechos reservados", response.text)
        self.assertNotIn("All rights reserved", response.text)
        self.assertEqual(response.cookies.get("job_finder_portfolio_lang"), "es_ES")

    def test_portfolio_page_language_cookie_reused(self):
        """After choosing Spanish, a later visit without ?lang stays in Spanish through the cookie."""
        self._load_spanish()
        self.url_open("/?lang=es_ES", headers={"Host": "gp-developer.com"})
        self.assertEqual(self.opener.cookies.get("job_finder_portfolio_lang"), "es_ES")
        response = self.url_open("/", headers={"Host": "gp-developer.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Todos los derechos reservados", response.text)
        self.assertNotIn("All rights reserved", response.text)

    def test_portfolio_page_invalid_language_fallback(self):
        """Unknown or inactive languages fall back to English."""
        self._load_spanish()
        for lang in ("fr_FR", "xx_XX"):
            response = self.url_open(f"/?lang={lang}", headers={"Host": "gp-developer.com"})
            self.assertEqual(response.status_code, 200)
            self.assertIn("All rights reserved", response.text)
            self.assertNotIn("Todos los derechos reservados", response.text)
            self.assertEqual(response.cookies.get("job_finder_portfolio_lang"), "en_US")

    def test_portfolio_page_system_parameter_change(self):
        """Changing the system parameter changes which hosts serve portfolio."""
        # First, verify the portfolio is being served for the current host
        response1 = self.url_open(
            "/",
            headers={"Host": "gp-developer.com"},
        )
        self.assertIn("Systems Developer", response1.text)

        # Now update the parameter to exclude gp-developer.com
        self.env["ir.config_parameter"].set_param(
            "job_finder.portfolio_hosts",
            "other-domain.com"
        )
        response2 = self.url_open(
            "/",
            headers={"Host": "gp-developer.com"},
        )
        # Should now fall back to standard behavior (not portfolio)
        # The portfolio content should not be present
        self.assertNotIn("Systems Developer", response2.text)

    def test_portfolio_page_javascript_url_not_rendered(self):
        """JavaScript URLs in contact fields are not rendered as links."""
        self.profile.github = "javascript:alert('xss')"
        response = self.url_open(
            "/",
            headers={"Host": "gp-developer.com"},
        )
        text = response.text
        # javascript: URL should not appear as a clickable link
        self.assertNotIn("javascript:", text)

    def test_portfolio_page_responsive_no_inline_js(self):
        """Portfolio page uses no inline JavaScript."""
        response = self.url_open(
            "/",
            headers={"Host": "gp-developer.com"},
        )
        text = response.text
        # Should not have inline <script> tags with event handlers
        self.assertNotIn("onclick=", text)
        self.assertNotIn("onload=", text)


if __name__ == "__main__":
    import unittest
    unittest.main()
