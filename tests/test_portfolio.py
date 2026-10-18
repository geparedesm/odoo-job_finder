"""End-to-end tests for public portfolio pages and their access boundary."""

import unittest

try:
    from lxml import html
    from odoo.tests import HttpCase, tagged
    from odoo.tools import mute_logger
except ImportError:
    raise unittest.SkipTest("needs a running Odoo (--test-enable)")

from psycopg2 import IntegrityError


@tagged("post_install", "-at_install")
class TestPortfolio(HttpCase):
    """Exercise portfolio URLs as an anonymous HTTP client."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create({
            "name": "Portfolio Owner",
            "login": "portfolio-owner",
            "email": "private-user-email@example.com",
        })
        cls.profile = cls.env["job.profile"].create({
            "user_id": cls.user.id,
            "full_name": "Portfolio Owner",
            "headline": "Product engineer",
            "email": "hello@portfolio.example",
            "summary": "Builds accessible tools.",
            "skills": "Python\nOdoo",
        })

    def test_public_route_is_available_without_authentication(self):
        response = self.url_open("/portfolio/portfolio-owner")

        self.assertEqual(response.status_code, 200)

    def test_portfolio_displays_job_profile_data(self):
        response = self.url_open("/portfolio/portfolio-owner")

        self.assertIn(b"Portfolio Owner", response.content)
        self.assertIn(b"Product engineer", response.content)
        self.assertIn(b"Builds accessible tools.", response.content)
        self.assertIn(b"Python", response.content)
        self.assertIn(b"hello@portfolio.example", response.content)

    def test_public_page_does_not_expose_private_user_data(self):
        response = self.url_open("/portfolio/portfolio-owner")

        self.assertNotIn(b"private-user-email@example.com", response.content)
        self.assertNotIn(b"portfolio.owner@example.com", response.content)
        self.assertNotIn(b"password", response.content.lower())

    def test_unknown_and_invalid_slugs_return_404(self):
        for slug in ("missing-portfolio", "Invalid_Slug", "../private"):
            with self.subTest(slug=slug):
                response = self.url_open(f"/portfolio/{slug}", timeout=10)
                self.assertEqual(response.status_code, 404)

    def test_slug_is_generated_from_login(self):
        user = self.env["res.users"].create({
            "name": "A Different Display Name",
            "login": "login-source@example.com",
        })

        self.assertEqual(user.portfolio_slug, "login-source-example-com")

    def test_duplicate_portfolio_slugs_are_rejected(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.env["res.users"].create({
                "name": "Another Owner",
                "login": "another-owner@example.com",
                "portfolio_slug": self.user.portfolio_slug,
            })
            self.env.flush_all()

    def test_page_has_basic_wcag_structure(self):
        response = self.url_open("/portfolio/portfolio-owner")
        document = html.fromstring(response.content)

        self.assertEqual(len(document.xpath("//main[contains(@class, 'pf-page')]")), 1)
        self.assertEqual(len(document.xpath("//h1")), 1)
        self.assertEqual(
            document.xpath("//nav[@aria-label='Portfolio sections']"),
            [document.xpath("//nav")[0]],
        )
        self.assertTrue(document.xpath("//nav//a[@href='#top']"))
        self.assertTrue(document.xpath("//a[@href='#work']"))


if __name__ == "__main__":
    unittest.main()
