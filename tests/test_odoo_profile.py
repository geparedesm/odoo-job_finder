"""Profile actions, access, views and uniqueness in Odoo; skipped by plain unittest."""

import unittest

try:
    from odoo.exceptions import UserError
    from odoo.tests import TransactionCase, tagged
except ImportError:  # plain `python -m unittest`: these need Odoo
    raise unittest.SkipTest("needs a running Odoo (--test-enable)")

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install")
class TestProfileScreen(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        internal = [(6, 0, [cls.env.ref("base.group_user").id])]
        cls.user = cls.env["res.users"].create({"name": "Job Seeker", "login": "job-seeker", "group_ids": internal})
        cls.other = cls.env["res.users"].create({"name": "Other Seeker", "login": "other-seeker", "group_ids": internal})

    def test_user_uniq_rejects_a_second_profile_for_the_same_user(self):
        profiles = self.env["job.profile"]
        profile = profiles.create({"user_id": self.user.id})
        self.env.flush_all()
        # Roll back the rejected insert before checking the surviving profile.
        with self.assertRaises((IntegrityError, ValidationError)), self.cr.savepoint():
            profiles.create({"user_id": self.user.id})
            self.env.flush_all()
        self.assertEqual(profiles.search([("user_id", "=", self.user.id)]), profile)

    def test_user_uniq_allows_profiles_for_distinct_users(self):
        profiles = self.env["job.profile"]
        mine = profiles.create({"user_id": self.user.id})
        other = profiles.create({"user_id": self.other.id})
        self.env.flush_all()
        self.assertNotEqual(mine.id, other.id)
        self.assertEqual(mine.user_id, self.user)
        self.assertEqual(other.user_id, self.other)

    def open_profile(self, user):
        return self.env.ref("job_finder.action_open_my_profile").with_user(user).run()

    def test_menu_opens_the_users_own_profile_form(self):
        menu = self.env.ref("job_finder.menu_my_profile")
        self.assertTrue(self.env["ir.ui.menu"].with_user(self.user).search([("id", "=", menu.id)]))
        action = self.open_profile(self.user)
        self.assertEqual((action["res_model"], action["views"]), ("job.profile", [(False, "form")]))
        self.assertEqual(self.env["job.profile"].browse(action["res_id"]).user_id, self.user)
        self.assertEqual(self.open_profile(self.user)["res_id"], action["res_id"])  # opened again: the same profile

    def test_internal_users_see_only_their_own_profile(self):
        mine = self.open_profile(self.user)["res_id"]
        self.open_profile(self.other)
        self.assertEqual(self.env["job.profile"].with_user(self.user).search([]).ids, [mine])

    def test_form_view_loads_for_an_internal_user(self):
        views = self.env["job.profile"].with_user(self.user).get_views([(False, "form")])
        self.assertIn("cv_file", views["models"]["job.profile"]["fields"])

    def test_related_jobs_are_ranked_before_pagination(self):
        profile = self.env["job.profile"].browse(self.open_profile(self.user)["res_id"])
        profile.write({"skills": "Python SQL"})
        postings = self.env["job.posting"].create([
            {"title": "Sin coincidencias"},
            {"title": "Python", "description": "SQL"},
            {"title": "Python"},
        ])
        action = profile.with_user(self.user).action_search_related_jobs()
        catalog = self.env["job.posting"].with_user(self.user).with_context(action["context"])
        # Include only our fixtures so pre-existing catalog data cannot affect assertions.
        domain = action["domain"] + [("id", "in", postings.ids)]
        self.assertEqual(catalog.search(domain, limit=1).id, postings[1].id)
        self.assertEqual(catalog.search(domain, offset=1, limit=1).id, postings[2].id)
        self.assertEqual(catalog.search(domain).ids, [postings[1].id, postings[2].id, postings[0].id])
        self.assertEqual(catalog.search(domain, order="id desc").ids, list(reversed(postings.ids)))

    def test_adapt_cv_updates_only_current_users_draft(self):
        mine = self.env["job.profile"].browse(self.open_profile(self.user)["res_id"])
        other = self.env["job.profile"].browse(self.open_profile(self.other)["res_id"])
        mine.write({"summary": "Python developer", "skills": "SQL, Python"})
        posting = self.env["job.posting"].create({"title": "Developer", "description": "Python"})
        action = posting.with_user(self.user).action_adapt_cv()
        self.assertEqual(action["res_id"], mine.id)
        self.assertEqual(mine.adapted_skills, "Python\nSQL")
        self.assertTrue(mine.adapted_summary)
        self.assertEqual((mine.summary, mine.skills), ("Python developer", "SQL, Python"))
        self.assertFalse(other.adapted_summary)
        self.assertFalse(other.adapted_skills)

    def test_adapt_cv_requires_an_existing_profile(self):
        posting = self.env["job.posting"].create({"description": "Python"})
        with self.assertRaisesRegex(UserError, "Cree su perfil profesional"):
            posting.with_user(self.user).action_adapt_cv()
        self.assertFalse(self.env["job.profile"].search([("user_id", "=", self.user.id)]))
