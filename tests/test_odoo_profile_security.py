"""ACLs and record rules protect profiles, including their adapted CV drafts."""

import unittest

try:
    from odoo.exceptions import AccessError
    from odoo.tests import TransactionCase, tagged
except ImportError:
    raise unittest.SkipTest("needs a running Odoo (--test-enable)")


@tagged("post_install", "-at_install")
class TestProfileSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        users = cls.env["res.users"]
        internal = [(6, 0, [cls.env.ref("base.group_user").id])]
        cls.user = users.create({"name": "Private Seeker", "login": "private-seeker", "group_ids": internal})
        cls.other = users.create({"name": "Other Private Seeker", "login": "other-private-seeker", "group_ids": internal})
        cls.admin = users.create({
            "name": "Profile Administrator", "login": "profile-security-admin",
            "group_ids": [(6, 0, [cls.env.ref("base.group_system").id])],
        })
        cls.portal = users.create({
            "name": "Portal Seeker", "login": "portal-seeker",
            "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
        })
        cls.mine = cls.env["job.profile"].with_user(cls.user).create({"skills": "SQL, Python"})
        cls.theirs = cls.env["job.profile"].with_user(cls.other).create({"skills": "Java"})
        cls.posting = cls.env["job.posting"].with_user(cls.admin).create({
            "title": "Python role", "description": "Python",
        })

    def test_other_users_profile_and_adapted_cv_are_hidden(self):
        self.posting.with_user(self.other).action_adapt_cv()
        profiles = self.env["job.profile"].with_user(self.user)
        self.assertEqual(profiles.search([("id", "in", (self.mine | self.theirs).ids)]), self.mine.with_user(self.user))
        with self.assertRaises(AccessError):
            self.theirs.with_user(self.user).read(["skills", "adapted_summary", "adapted_skills"])

    def test_other_users_profile_and_draft_cannot_be_changed_or_deleted(self):
        target = self.theirs.with_user(self.user)
        for operation in (
            lambda: target.write({"skills": "Forbidden"}),
            lambda: target.write({"adapted_summary": "Forbidden", "adapted_skills": "Forbidden"}),
            lambda: target.unlink(),
        ):
            with self.subTest(operation=operation), self.assertRaises(AccessError), self.cr.savepoint():
                operation()

    def test_user_cannot_create_profile_for_another_user(self):
        # Use a user without a profile so uniqueness cannot mask the record rule.
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["job.profile"].with_user(self.user).create({"user_id": self.portal.id})

    def test_adapting_shared_posting_writes_only_callers_draft(self):
        self.theirs.write({"adapted_summary": "Other draft", "adapted_skills": "Java"})
        action = self.posting.with_user(self.user).action_adapt_cv()
        self.assertEqual(action["res_id"], self.mine.id)
        self.assertEqual(self.mine.adapted_skills, "Python\nSQL")
        self.assertEqual((self.theirs.adapted_summary, self.theirs.adapted_skills), ("Other draft", "Java"))

    def test_owner_can_update_and_delete_profile(self):
        profile = self.mine.with_user(self.user)
        profile.write({"summary": "My summary"})
        self.assertEqual(profile.read(["summary"])[0]["summary"], "My summary")
        profile.unlink()
        self.assertFalse(profile.exists())

    def test_administrator_can_read_and_update_other_users_draft(self):
        profile = self.theirs.with_user(self.admin)
        self.assertEqual(profile.read(["skills"])[0]["skills"], "Java")
        profile.write({"adapted_summary": "Reviewed draft"})
        self.assertEqual(profile.adapted_summary, "Reviewed draft")

    def test_portal_has_no_access_to_profiles_or_postings(self):
        for model, record in (("job.profile", self.mine), ("job.posting", self.posting)):
            with self.subTest(model=model):
                with self.assertRaises(AccessError):
                    record.with_user(self.portal).read(["id"])
                with self.assertRaises(AccessError), self.cr.savepoint():
                    record.with_user(self.portal).write({"summary" if model == "job.profile" else "title": "Forbidden"})
                with self.assertRaises(AccessError), self.cr.savepoint():
                    self.env[model].with_user(self.portal).create({})
