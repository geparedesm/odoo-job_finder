"""Tests for the public portfolio page and CV download."""

from odoo.tests import HttpCase, tagged


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
            "is_portfolio_published": True,
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
        """GET / with non-configured host returns standard Odoo behavior."""
        response = self.url_open(
            "/",
            headers={"Host": "localhost:8000"},
        )
        # Should redirect or show login (not the portfolio page)
        # The standard home controller redirects
        self.assertNotEqual(response.status_code, 200)  # Should be 302/redirect

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

    def test_portfolio_page_empty_state(self):
        """When no profile is published, shows empty state."""
        self.profile.is_portfolio_published = False
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

    def test_portfolio_cv_not_found_when_nothing_published(self):
        """GET /portfolio/cv returns 404 when nothing is published."""
        self.authenticate("admin", "admin")
        self.profile.is_portfolio_published = False
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

    def test_portfolio_page_language_selector_es(self):
        """Language selector for ES_ES."""
        # First, activate es_ES language
        self.env["res.lang"]._activate_lang("es_ES")
        response = self.url_open(
            "/?lang=es_ES",
            headers={"Host": "gp-developer.com"},
        )
        self.assertEqual(response.status_code, 200)
        # The template should be rendered, even if translations aren't loaded

    def test_portfolio_page_invalid_language_fallback(self):
        """Invalid language parameter falls back to English."""
        response = self.url_open(
            "/?lang=fr_FR",
            headers={"Host": "gp-developer.com"},
        )
        self.assertEqual(response.status_code, 200)
        # Should render without error

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
