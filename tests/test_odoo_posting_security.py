"""Shared catalog access checks inside a running Odoo."""

import unittest

try:
    from odoo.exceptions import AccessError
    from odoo.tests import TransactionCase, tagged
except ImportError:
    raise unittest.SkipTest("needs a running Odoo (--test-enable)")


@tagged("post_install", "-at_install")
class TestPostingSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create({
            "name": "Catalog Reader", "login": "posting-reader",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.admin = cls.env["res.users"].create({
            "name": "Catalog Administrator", "login": "posting-admin",
            "group_ids": [(6, 0, [cls.env.ref("base.group_system").id])],
        })
        cls.posting = cls.env["job.posting"].with_user(cls.admin).create({"title": "Shared Job"})

    def test_internal_user_reads_shared_catalog(self):
        postings = self.env["job.posting"].with_user(self.user)
        self.assertIn(self.posting.id, postings.search([]).ids)
        self.assertEqual(self.posting.with_user(self.user).read(["title"])[0]["title"], "Shared Job")

    def test_internal_user_cannot_mutate_catalog(self):
        posting = self.posting.with_user(self.user)
        operations = (
            lambda: posting.create({"title": "Forbidden"}),
            lambda: posting.write({"title": "Forbidden"}),
            lambda: posting.unlink(),
        )
        for operation in operations:
            with self.assertRaises(AccessError), self.cr.savepoint():
                operation()

    def test_administrator_has_full_crud(self):
        posting = self.env["job.posting"].with_user(self.admin).create({"title": "New Job"})
        self.assertEqual(posting.read(["title"])[0]["title"], "New Job")
        posting.write({"title": "Updated Job"})
        self.assertEqual(posting.title, "Updated Job")
        posting.unlink()
        self.assertFalse(posting.exists())
