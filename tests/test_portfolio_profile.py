"""Tests for portfolio profile publishing and public values."""

import unittest

try:
    import psycopg2
    from odoo.exceptions import AccessError, ValidationError
    from odoo.tests import TransactionCase, tagged
    from odoo.tools import mute_logger
except ImportError:
    raise unittest.SkipTest("Odoo not available")


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
            "summary": "A software engineer with experience",
        })
        self.profile2 = self.env["job.profile"].create({
            "user_id": self.env.ref("base.user_admin").id,
            "full_name": "Admin User",
            "headline": "Tech Lead",
        })

    def test_single_portfolio_published(self):
        """Only one profile can be published as portfolio."""
        # Publish profile1
        self.profile1.is_published_as_portfolio = True
        # Publishing profile2 should raise ValidationError
        with self.assertRaises(ValidationError) as cm:
            self.profile2.is_published_as_portfolio = True
        self.assertIn("Only one profile", str(cm.exception))

    def test_unpublish_allows_another(self):
        """Unpublishing one profile allows publishing another."""
        self.profile1.is_published_as_portfolio = True
        self.profile1.is_published_as_portfolio = False
        # Should not raise
        self.profile2.is_published_as_portfolio = True
        self.assertTrue(self.profile2.is_published_as_portfolio)

    def test_single_portfolio_enforced_by_database(self):
        """Two published profiles are refused by the database even when the Python check is bypassed."""
        self.profile1.is_published_as_portfolio = True
        self.env.flush_all()
        with self.assertRaises(psycopg2.IntegrityError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            self.env.cr.execute("UPDATE job_profile SET is_published_as_portfolio = true WHERE id = %s", [self.profile2.id])
            self.env.cr.execute("SET CONSTRAINTS job_profile_single_portfolio IMMEDIATE")

    def test_admin_only_field_visibility(self):
        """Non-admin users cannot see or edit is_published_as_portfolio."""
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
            profile.with_user(user).write({"is_published_as_portfolio": True})

    def test_get_portfolio_values_whitelist(self):
        """Only public fields: no phone unless the person shows it."""
        values = self.profile1._get_portfolio_values()
        self.assertEqual((values["name"], values["headline_parts"], values["location"], values["email"]),
                         ("Test User", ["Software Engineer"], "San Francisco", "test@example.com"))
        self.assertNotIn(self.profile1.phone, str(values))
        self.profile1.is_phone_public = True
        self.assertEqual(self.profile1._get_portfolio_values()["phone"], "+1 555 1234")

    def test_get_portfolio_values_from_records(self):
        """Featured projects, roles and skills come from the records shown on the portfolio."""
        role = self.env["job_finder.experience"].create({
            "profile_id": self.profile1.id, "role": "Developer", "company": "Acme",
            "date_start": "2021-12-01", "date_end": "2025-01-01", "employment_type": "full_time",
            "highlights": "Shipped things. Many things.",
        })
        python = self.env["job_finder.technology"].create({"name": "Python"})
        self.env["job_finder.project"].create([
            {"profile_id": self.profile1.id, "experience_id": role.id, "name": "Shown", "is_featured": True,
             "subtitle": "internal tool", "description": "Built it. Then more.", "technology_ids": [(6, 0, python.ids)]},
            {"profile_id": self.profile1.id, "experience_id": role.id, "name": "Hidden", "is_featured": True,
             "is_public": False},
        ])
        self.env["job_finder.skill_group"].create({
            "profile_id": self.profile1.id, "name": "Languages", "technology_ids": [(6, 0, python.ids)]})
        values = self.profile1._get_portfolio_values()
        [project] = values["featured_projects"]
        shown = self.profile1.project_ids.filtered(lambda p: p.name == "Shown")
        self.assertEqual(project, {
            "name": "Shown", "subtitle": "Internal tool", "source": "Acme / Dec 2021 – Jan 2025",
            "description": "Built it.", "technologies": "Python", "technology_names": ["Python"], "url": None,
            "area": "", "index": "01", "metrics": [], "cover_url": None, "page_url": shown._get_portfolio_path(),
        })
        [entry] = values["roles"]
        self.assertEqual((entry["title"], entry["company"], entry["highlight"], entry["type"]),
                         ("Developer", "Acme", "Shipped things.", "Full-time"))
        self.assertEqual(entry["projects"], [{"name": "Shown", "url": shown._get_portfolio_path()}])
        self.assertEqual(values["skills"], [{"name": "Languages", "items": "Python", "technology_names": ["Python"],
                                             "icon": "fa-code"}])

    def test_get_portfolio_values_safe_urls(self):
        """Links get https:// and a short label; unsafe ones are dropped."""
        self.profile1.write({"linkedin": "linkedin.com/in/test", "github": "javascript:alert(1)",
                             "website": "https://www.example.com/"})
        links = {item["kind"]: item for item in self.profile1._get_portfolio_values()["links"]}
        self.assertEqual(links["linkedin"]["href"], "https://linkedin.com/in/test")
        self.assertEqual(links["website"]["label"], "example.com")
        self.assertNotIn("github", links)

    def test_get_portfolio_values_empty_fields(self):
        """An empty profile gives empty sections."""
        user = self.env["res.users"].create({"name": "Empty Test User", "login": "emptytest"})
        values = self.env["job.profile"].create({"user_id": user.id, "full_name": "Empty Profile"})._get_portfolio_values()
        self.assertEqual(values["summary_paragraphs"], [])
        for section in ("featured_projects", "roles", "secondary_roles", "research_groups", "skills", "education",
                        "trainings", "languages", "volunteering", "links", "figures"):
            self.assertEqual(values[section], [], section)

if __name__ == "__main__":
    import unittest
    unittest.main()
