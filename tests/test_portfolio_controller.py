"""Public portfolio route tests."""

import unittest

try:
    from odoo.tests import HttpCase, tagged
except ImportError:
    raise unittest.SkipTest("needs a running Odoo (--test-enable)")


@tagged("post_install", "-at_install")
class TestPortfolioController(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create({
            "name": "Public Portfolio User",
            "login": "public-portfolio-user",
            "portfolio_slug": "public-portfolio",
        })
        cls.env["job.profile"].create({
            "user_id": cls.user.id,
            "full_name": "Public Portfolio User",
            "headline": "Product engineer",
            "summary": "Builds useful tools.",
        })

    def test_public_portfolio_renders_profile_and_user(self):
        response = self.url_open("/portfolio/public-portfolio")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Public Portfolio User", response.content)
        self.assertIn(b"Product engineer", response.content)
        self.assertIn(b"Builds useful tools.", response.content)

    def test_unknown_portfolio_returns_not_found(self):
        response = self.url_open("/portfolio/does-not-exist", timeout=10)
        self.assertEqual(response.status_code, 404)

    def test_invalid_portfolio_slug_returns_not_found(self):
        response = self.url_open("/portfolio/Invalid_Slug", timeout=10)
        self.assertEqual(response.status_code, 404)
