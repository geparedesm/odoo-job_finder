"""Portfolio slug generation and uniqueness tests."""

import unittest

try:
    from odoo.tests import TransactionCase, tagged
except ImportError:
    raise unittest.SkipTest("needs a running Odoo (--test-enable)")

from psycopg2 import IntegrityError

from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestPortfolioSlug(TransactionCase):
    def test_slug_is_generated_from_login(self):
        user = self.env["res.users"].create({
            "name": "Gabriel Paredes",
            "login": "gabriel.paredes",
        })
        self.assertEqual(user.portfolio_slug, "gabriel-paredes")

    def test_slug_generation_normalizes_case_accents_and_separators(self):
        user = self.env["res.users"].create({
            "name": "José User",
            "login": "José.User+portfolio@example.com",
        })
        self.assertEqual(user.portfolio_slug, "jose-user-portfolio-example-com")

    def test_explicit_slug_is_preserved(self):
        user = self.env["res.users"].create({
            "name": "Custom User",
            "login": "custom.user",
            "portfolio_slug": "my-custom-slug",
        })
        self.assertEqual(user.portfolio_slug, "my-custom-slug")

    def test_slug_can_be_null(self):
        user = self.env["res.users"].create({
            "name": "No Slug User",
            "login": "no-slug.user",
            "portfolio_slug": False,
        })
        self.assertFalse(user.portfolio_slug)

    def test_slug_generation_with_only_special_characters(self):
        users = self.env["res.users"].create([
            {"name": "Dash User", "login": "---"},
            {"name": "Plus User", "login": "+++"},
        ])
        self.assertFalse(users[0].portfolio_slug)
        self.assertFalse(users[1].portfolio_slug)

    def test_slug_is_not_regenerated_when_login_changes(self):
        user = self.env["res.users"].create({
            "name": "Custom User",
            "login": "original.user",
        })
        user.write({"login": "updated.user"})
        self.assertEqual(user.portfolio_slug, "original-user")

    def test_duplicate_slugs_are_rejected(self):
        self.env["res.users"].create({
            "name": "First User",
            "login": "duplicate.slug",
        })
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.env["res.users"].create({
                "name": "Second User",
                "login": "duplicate-slug",
            })
            self.env.flush_all()


if __name__ == "__main__":
    unittest.main()
