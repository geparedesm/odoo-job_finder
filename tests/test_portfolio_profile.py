"""Tests for portfolio profile publishing and public values."""

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class PortfolioProfileTestCase(TransactionCase):
    """Test portfolio publishing and access control."""

    def setUp(self):
        super().setUp()
        self.profile1 = self.env["job.profile"].create({
            "user_id": self.env.user.id,
            "full_name": "Test User",
            "headline": "Software Engineer",
            "email": "test@example.com",
            "phone": "+1 555 1234",
            "location": "San Francisco",
            "linkedin": "https://linkedin.com/in/test",
            "skills": "Python\nJavaScript\nRust",
            "summary": "A software engineer with experience",
            "projects": "Project 1\nTechnologies: Python, Django\nBuilt a web app",
        })
        self.profile2 = self.env["job.profile"].create({
            "user_id": self.env.ref("base.user_admin").id,
            "full_name": "Admin User",
            "headline": "Tech Lead",
        })

    def test_single_portfolio_published(self):
        """Only one profile can be published as portfolio."""
        # Publish profile1
        self.profile1.is_portfolio_published = True
        # Publishing profile2 should raise ValidationError
        with self.assertRaises(ValidationError) as cm:
            self.profile2.is_portfolio_published = True
        self.assertIn("Only one profile", str(cm.exception))

    def test_unpublish_allows_another(self):
        """Unpublishing one profile allows publishing another."""
        self.profile1.is_portfolio_published = True
        self.profile1.is_portfolio_published = False
        # Should not raise
        self.profile2.is_portfolio_published = True
        self.assertTrue(self.profile2.is_portfolio_published)

    def test_admin_only_field_visibility(self):
        """Non-admin users cannot see or edit is_portfolio_published."""
        user = self.env["res.users"].create({
            "name": "Test User",
            "login": "testuser",
            "email": "test@example.com",
        })
        # Create profile for this user
        profile = self.env["job.profile"].create({
            "user_id": user.id,
            "full_name": "Regular User",
        })
        # Try to write as non-admin should raise AccessError
        with self.assertRaises(AccessError):
            profile.with_user(user).write({"is_portfolio_published": True})

    def test_get_portfolio_values_whitelist(self):
        """_get_portfolio_values returns only whitelisted fields."""
        self.profile1.is_portfolio_published = True
        values = self.profile1._get_portfolio_values()

        # Should include public fields
        self.assertEqual(values["name"], "Test User")
        self.assertEqual(values["headline"], "Software Engineer")
        self.assertEqual(values["location"], "San Francisco")
        self.assertEqual(values["email"], "test@example.com")

        # Should NOT include phone (hidden from public)
        self.assertNotIn(self.profile1.phone, str(values))

    def test_get_portfolio_values_parsed_content(self):
        """_get_portfolio_values parses multi-line fields into lists."""
        values = self.profile1._get_portfolio_values()

        # Skills should be parsed into list
        self.assertIsInstance(values["skills"], list)
        self.assertIn("Python", values["skills"])
        self.assertIn("JavaScript", values["skills"])

        # Projects should be parsed into list of dicts
        self.assertIsInstance(values["projects"], list)
        self.assertEqual(len(values["projects"]), 1)
        self.assertEqual(values["projects"][0]["title"], "Project 1")

    def test_get_portfolio_values_safe_urls(self):
        """_get_portfolio_values uses safe_url for contact fields."""
        self.profile1.linkedin = "linkedin.com/in/test"
        self.profile1.github = "https://github.com/test"
        self.profile1.website = "example.com"
        values = self.profile1._get_portfolio_values()

        # safe_url should add https:// to bare domains
        self.assertTrue(values["linkedin"].startswith("https://"))
        self.assertTrue(values["github"].startswith("https://"))
        self.assertTrue(values["website"].startswith("https://"))

    def test_get_portfolio_values_empty_fields(self):
        """_get_portfolio_values handles empty fields gracefully."""
        user = self.env["res.users"].create({
            "name": "Empty Test User",
            "login": "emptytest",
            "email": "empty@example.com",
        })
        profile = self.env["job.profile"].create({
            "user_id": user.id,
            "full_name": "Empty Profile",
        })
        values = profile._get_portfolio_values()

        # Empty fields should be empty strings or empty lists
        self.assertEqual(values["summary"], "")
        self.assertEqual(values["skills"], [])
        self.assertEqual(values["projects"], [])


if __name__ == "__main__":
    import unittest
    unittest.main()
