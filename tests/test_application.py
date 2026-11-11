"""Application defaults, validation, status domains and per-user access."""

import unittest

try:
    from odoo import fields
    from odoo.exceptions import AccessError
    from odoo.tests import TransactionCase, tagged
except ImportError:
    raise unittest.SkipTest("needs a running Odoo (--test-enable)") from None

from psycopg2 import IntegrityError
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestApplication(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        users = cls.env["res.users"]
        cls.user, cls.other, cls.admin, cls.portal = users.create([
            {"name": name, "login": login, "group_ids": [(6, 0, [cls.env.ref(group).id])]}
            for name, login, group in [
                ("Applicant", "application-user", "base.group_user"),
                ("Other applicant", "application-other", "base.group_user"),
                ("Application administrator", "application-admin", "base.group_system"),
                ("Portal applicant", "application-portal", "base.group_portal"),
            ]
        ])
        cls.applications = cls.env["job_finder.application"].with_user(cls.user)
        cls.mine = cls.applications.create({"company": "Example", "position": "Developer"})
        cls.theirs = cls.applications.with_user(cls.other).create({
            "company": "Other company", "position": "Analyst",
        })

    def test_defaults_and_optional_notes(self):
        self.assertEqual(self.mine.user_id, self.user)
        self.assertEqual(self.mine.date_applied, fields.Date.context_today(self.applications))
        self.assertEqual(self.mine.status, "sent")
        self.assertFalse(self.mine.notes)

    def test_selection_keys_and_english_labels(self):
        self.assertEqual(self.applications.with_context(lang="en_US").fields_get(["status"])["status"]["selection"], [
            ("sent", "Sent"), ("under_review", "Under review"), ("interview", "Interview"),
            ("rejected", "Rejected"), ("offer_received", "Offer received"),
        ])

    def test_each_status_domain_returns_only_that_status(self):
        statuses = ["sent", "under_review", "interview", "rejected", "offer_received"]
        records = self.applications.create([
            {"company": "Status company", "position": status, "status": status} for status in statuses
        ])
        for status in statuses:
            with self.subTest(status=status):
                found = self.applications.search([("id", "in", records.ids), ("status", "=", status)])
                self.assertEqual(found, records.filtered(lambda record, status=status: record.status == status))

    def test_display_name_tracks_company_and_position(self):
        self.assertEqual(self.mine.display_name, "Example - Developer")
        self.mine.write({"company": "Updated", "position": "Engineer"})
        self.assertEqual(self.mine.display_name, "Updated - Engineer")

    def test_newest_first_with_deterministic_ties(self):
        records = self.applications.create([
            {"company": "Example", "position": "Older", "date_applied": "2024-01-01"},
            {"company": "Example", "position": "Newer", "date_applied": "2024-02-01"},
            {"company": "Example", "position": "Latest tie", "date_applied": "2024-02-01"},
        ])
        self.assertEqual(self.applications.search([("id", "in", records.ids)]).ids, list(reversed(records.ids)))

    def test_required_fields_reject_missing_values(self):
        for field in ("user_id", "company", "position", "date_applied", "status"):
            with self.subTest(field=field):
                with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
                    self.applications.create({"company": "Example", "position": "Developer", field: False})
                    self.env.flush_all()

    def test_invalid_status_rejected_on_create_and_write(self):
        with self.assertRaises(ValueError), self.cr.savepoint():
            self.applications.create({"company": "Example", "position": "Developer", "status": "invalid"})
        with self.assertRaises(ValueError), self.cr.savepoint():
            self.mine.write({"status": "invalid"})

    def test_own_crud_and_multiple_applications(self):
        another = self.applications.create({"company": "Example", "position": "Developer"})
        another.write({"notes": "Follow up", "status": "interview"})
        self.assertEqual(another.read(["notes"])[0]["notes"], "Follow up")
        self.assertEqual(another.status, "interview")
        another.unlink()
        self.assertFalse(another.exists())
        self.assertTrue(self.mine.exists())

    def test_search_is_isolated_for_both_users(self):
        domain = [("id", "in", (self.mine | self.theirs).ids)]
        self.assertEqual(self.applications.search(domain), self.mine)
        self.assertEqual(self.applications.with_user(self.other).search(domain), self.theirs)

    def test_foreign_read_write_and_unlink_are_denied(self):
        foreign = self.theirs.with_user(self.user)
        for operation in (lambda: foreign.read(["company"]), lambda: foreign.write({"notes": "Denied"}), foreign.unlink):
            with self.assertRaises(AccessError), self.cr.savepoint():
                operation()

    def test_creating_for_another_user_and_transferring_ownership_are_denied(self):
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.applications.create({"company": "Example", "position": "Developer", "user_id": self.other.id})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.mine.write({"user_id": self.other.id})

    def test_non_superuser_administrator_has_full_access(self):
        applications = self.applications.with_user(self.admin)
        self.assertFalse(applications.env.su)
        records = applications.search([("id", "in", (self.mine | self.theirs).ids)])
        self.assertEqual(set(records.ids), {self.mine.id, self.theirs.id})
        self.assertEqual(len(records.read(["company"])), 2)
        records.write({"notes": "Administrator update"})
        created = applications.create({"company": "Admin company", "position": "Role", "user_id": self.other.id})
        created.write({"user_id": self.user.id})
        (records | created).unlink()
        self.assertFalse((records | created).exists())

    def test_portal_and_public_users_have_no_access(self):
        for user in (self.portal, self.env.ref("base.public_user")):
            applications = self.applications.with_user(user)
            record = self.mine.with_user(user)
            operations = (
                lambda applications=applications: applications.search([]),
                lambda applications=applications: applications.create({"company": "Example", "position": "Developer"}),
                lambda record=record: record.read(["company"]),
                lambda record=record: record.write({"notes": "Denied"}),
                record.unlink,
            )
            for operation in operations:
                with self.subTest(user=user.name), self.assertRaises(AccessError), self.cr.savepoint():
                    operation()
