"""Seed a disposable Odoo database with a synthetic long-email portfolio preview.

Run with ``odoo shell -d <preview-db> < .hermes/preview-seed.py`` and set
``JOB_FINDER_PREVIEW_DATABASE`` to the exact disposable database name. This guard
prevents accidental writes to any database that was not explicitly selected.
"""

import os


expected_database = os.environ.get("JOB_FINDER_PREVIEW_DATABASE")
if (not expected_database or expected_database != env.cr.dbname
        or not (expected_database.startswith("preview") or "_preview" in expected_database)):
    raise RuntimeError(
        "Use a disposable database whose name starts with 'preview' or contains '_preview', and set "
        "JOB_FINDER_PREVIEW_DATABASE to its exact name."
    )

preview_user = env["res.users"].with_context(no_reset_password=True).search(
    [("login", "=", "job-finder-portfolio-preview")], limit=1
)
if not preview_user:
    preview_user = env["res.users"].create({
        "name": "Portfolio Preview",
        "login": "job-finder-portfolio-preview",
        "group_ids": [(6, 0, [env.ref("base.group_user").id])],
    })

profile = env["job.profile"].search([("user_id", "=", preview_user.id)], limit=1)
values = {
    "full_name": "Portfolio Preview",
    "headline": "Software development, ICT, Mechatronics",
    "email": "long.address.for.responsive.preview." + "segment." * 8 + "@example.com",
    "location": "Perth, Australia",
    "summary": "Synthetic content for checking the portfolio at desktop and mobile widths.",
    "is_published_as_portfolio": True,
}
if profile:
    profile.write(values)
else:
    profile = env["job.profile"].create({"user_id": preview_user.id, **values})

print("Synthetic portfolio preview is ready for database %s (profile ID %s)." % (env.cr.dbname, profile.id))
